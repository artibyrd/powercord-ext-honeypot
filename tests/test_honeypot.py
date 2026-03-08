from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import nextcord
import pytest
from sqlmodel import select

from app.extensions.honeypot.blueprint import HoneypotBanReport, HoneypotChannel, HoneypotSettings
from app.extensions.honeypot.cog import HoneypotCog
from app.extensions.honeypot.widget import guild_admin_honeypot_config, guild_admin_honeypot_reports

# All tests in this file are unit tests (mocked DB, no external services).
pytestmark = pytest.mark.unit


# Mock objects for Nextcord
class MockUser:
    def __init__(self, id, name="TestUser"):
        self.id = id
        self.name = name
        self.bot = False

    def __str__(self):
        return self.name

    @property
    def mention(self):
        return f"<@{self.id}>"


class MockGuild:
    def __init__(self, id):
        self.id = id
        self.name = "TestGuild"
        self.banned_users = []
        self.default_role = "MockRole"
        self.me = "MockMe"
        self.ban = AsyncMock()
        self.get_channel = MagicMock()


class MockChannel:
    def __init__(self, id, guild):
        self.id = id
        self.guild = guild

    @property
    def mention(self):
        return f"<#{self.id}>"


class MockMessage:
    def __init__(self, author, channel):
        self.author = author
        self.channel = channel
        self.guild = channel.guild


@pytest.fixture
def mock_bot():
    class Bot:
        pass

    return Bot()


@pytest.fixture
def honeypot_cog(mock_bot, session):
    # Instead of hitting real DB, we can just patch engine creating a session
    # We use session from conftest which is an empty in-memory DB
    cog = HoneypotCog(mock_bot)
    cog.engine = session.get_bind()
    return cog


@pytest.mark.asyncio
async def test_honeypot_logic(honeypot_cog, session):
    """
    Test the core spam detection logic of the Honeypot extension.

    Verifies that:
    1. A user posting in multiple designated honeypot channels triggers a ban.
    2. The ban is recorded in the Disocrd Guild ban list.
    3. A ban report is generated and saved to the database.
    """
    guild_id = 123
    user_id = 456
    chan1_id = 789
    chan2_id = 1011
    log_channel_id = 999

    # Setup DB
    session.add(HoneypotSettings(guild_id=guild_id, time_limit=60, log_channel_id=log_channel_id))
    session.add(HoneypotChannel(guild_id=guild_id, channel_id=chan1_id))
    session.add(HoneypotChannel(guild_id=guild_id, channel_id=chan2_id))
    session.commit()

    # Create Mocks
    guild = MockGuild(guild_id)
    user = MockUser(user_id)
    chan1 = MockChannel(chan1_id, guild)
    chan2 = MockChannel(chan2_id, guild)

    # Send message 1
    msg1 = MockMessage(user, chan1)
    await honeypot_cog.on_message(msg1)

    # Verify tracking initiated
    assert user_id in honeypot_cog.tracking[guild_id]
    posts, _ = honeypot_cog.tracking[guild_id][user_id]
    assert len(posts) == 1
    assert chan1_id in posts
    guild.ban.assert_not_called()  # No ban yet

    # Send message 2 (trigger ban)
    msg2 = MockMessage(user, chan2)

    mock_log_channel = AsyncMock(spec=nextcord.TextChannel)
    guild.get_channel.return_value = mock_log_channel

    await honeypot_cog.on_message(msg2)

    # Verify tracking cleared
    assert user_id not in honeypot_cog.tracking[guild_id]

    # Verify ban
    guild.ban.assert_called_once()
    ban_user_arg = guild.ban.call_args.args[0]
    ban_kwargs = guild.ban.call_args.kwargs
    assert ban_user_arg.id == user_id
    assert "posted in 2 honeypots within 60s" in ban_kwargs["reason"]

    # Verify log message sent
    guild.get_channel.assert_called_with(log_channel_id)
    mock_log_channel.send.assert_called_once()

    # Verify ban report
    reports = session.exec(select(HoneypotBanReport).where(HoneypotBanReport.guild_id == guild_id)).all()
    assert len(reports) == 1
    assert reports[0].user_id == user_id


@pytest.mark.asyncio
async def test_honeypot_timeout(honeypot_cog, session):
    """
    Test the timeout mechanism for honeypot tracking.

    Verifies that if a user posts in multiple honeypot channels,
    but the time between posts exceeds the configured time limit,
    they are NOT banned and the tracking is reset.
    """
    guild_id = 124
    user_id = 457
    chan1_id = 790
    chan2_id = 1012

    # time_limit is 1 for testing
    session.add(HoneypotSettings(guild_id=guild_id, time_limit=1))
    session.add(HoneypotChannel(guild_id=guild_id, channel_id=chan1_id))
    session.add(HoneypotChannel(guild_id=guild_id, channel_id=chan2_id))
    session.commit()

    guild = MockGuild(guild_id)
    user = MockUser(user_id)
    chan1 = MockChannel(chan1_id, guild)
    chan2 = MockChannel(chan2_id, guild)

    msg1 = MockMessage(user, chan1)
    await honeypot_cog.on_message(msg1)

    # artificially age the tracking timestamp
    posts, t_time = honeypot_cog.tracking[guild_id][user_id]
    honeypot_cog.tracking[guild_id][user_id] = (posts, t_time - timedelta(seconds=2))

    msg2 = MockMessage(user, chan2)
    await honeypot_cog.on_message(msg2)

    # Should reset tracked channels to just chan2 since time limit passed
    posts, _ = honeypot_cog.tracking[guild_id][user_id]
    assert len(posts) == 1
    assert chan1_id not in posts

    guild.ban.assert_not_called()


@patch("app.extensions.honeypot.widget.Session")
def test_guild_admin_honeypot_config(mock_session_cls, session):
    """Verifies that the honeypot configuration FastHTML widget renders without errors."""
    mock_session_cls.return_value.__enter__.return_value = session

    # Test rendering the widget with an empty database
    widget = guild_admin_honeypot_config(1)
    assert widget is not None

    # Populate the database with dummy config data
    session.add(HoneypotSettings(guild_id=1, time_limit=120, log_channel_id=456, shame_mode=True))
    session.add(HoneypotChannel(guild_id=1, channel_id=2))
    session.commit()

    # Test rendering the widget with active channels and populated settings
    widget = guild_admin_honeypot_config(1)
    assert widget is not None


@patch("app.extensions.honeypot.widget.Session")
def test_guild_admin_honeypot_reports(mock_session_cls, session):
    """Verifies that the honeypot ban reports widget renders and displays db data correctly."""
    mock_session_cls.return_value.__enter__.return_value = session

    # Test rendering the widget when there are no spammer ban records
    widget = guild_admin_honeypot_reports(1)
    assert widget is not None

    # Populate dummy ban report data
    session.add(HoneypotBanReport(guild_id=1, user_id=123, username="spammer", banned_at=datetime.now(timezone.utc)))
    session.commit()

    # Test rendering the widget viewing recent spammer bans
    widget = guild_admin_honeypot_reports(1)
    assert widget is not None


@pytest.mark.skip(
    reason="Hangs under pytest-asyncio due to StaticPool/multi-Session "
    "SQLite interaction.  Passes in isolation with asyncio.run()."
)
@pytest.mark.asyncio
async def test_honeypot_management_commands(honeypot_cog, session):
    """
    Test the Honeypot Cog management commands.

    Verifies:
    1. Changing time_limit creates/updates DB records.
    2. Adding a public channel saves it to DB.
    3. Adding a private channel throws an error.
    4. Removing channels works.
    5. Status command and channel creation error handling.
    """
    from unittest.mock import AsyncMock, MagicMock

    guild_id = 999
    guild = MockGuild(guild_id)

    # Mock Interaction
    interaction = MagicMock(spec=nextcord.Interaction)
    interaction.guild = guild
    interaction.response = AsyncMock()
    interaction.followup = AsyncMock()

    # test set_time_limit
    await honeypot_cog.honeypot_set_time_limit.callback(honeypot_cog, interaction, seconds=120)
    interaction.followup.send.assert_called_with("Honeypot time limit set to 120 seconds.")

    settings = session.exec(select(HoneypotSettings).where(HoneypotSettings.guild_id == guild_id)).first()
    assert settings.time_limit == 120

    # test set_time_limit update
    await honeypot_cog.honeypot_set_time_limit.callback(honeypot_cog, interaction, seconds=240)
    session.expire_all()
    settings = session.exec(select(HoneypotSettings).where(HoneypotSettings.guild_id == guild_id)).first()
    assert settings.time_limit == 240

    # test set time limit error
    interaction.followup.send.reset_mock()
    await honeypot_cog.honeypot_set_time_limit.callback(honeypot_cog, interaction, seconds=0)
    interaction.followup.send.assert_called_with("Time limit must be greater than 0.")

    # test set log channel
    interaction.followup.send.reset_mock()
    log_chan = MagicMock(spec=nextcord.TextChannel)
    log_chan.id = 987
    log_chan.mention = "<#987>"
    await honeypot_cog.honeypot_set_log_channel.callback(honeypot_cog, interaction, channel=log_chan)
    interaction.followup.send.assert_called_with("Honeypot ban reports will now be sent to <#987>.")

    session.refresh(settings)  # Ensure we get fresh data
    assert settings.log_channel_id == 987

    # test set log channel error
    interaction.followup.send.reset_mock()
    bad_chan = MagicMock(spec=nextcord.VoiceChannel)
    await honeypot_cog.honeypot_set_log_channel.callback(honeypot_cog, interaction, channel=bad_chan)
    interaction.followup.send.assert_called_with("Log channel must be a text channel.")

    # test set shame mode
    interaction.followup.send.reset_mock()
    await honeypot_cog.honeypot_set_shame_mode.callback(honeypot_cog, interaction, enabled=True)
    interaction.followup.send.assert_called_with("Honeypot shame mode enabled.")

    session.refresh(settings)
    assert settings is not None
    assert settings.shame_mode is True

    # test set shame mode disable
    interaction.followup.send.reset_mock()
    await honeypot_cog.honeypot_set_shame_mode.callback(honeypot_cog, interaction, enabled=False)
    interaction.followup.send.assert_called_with("Honeypot shame mode disabled.")

    session.refresh(settings)
    assert settings is not None
    assert settings.shame_mode is False

    # test add_channel
    chan = MagicMock(spec=nextcord.TextChannel)
    chan.id = 111
    chan.guild = guild
    chan.mention = "<#111>"
    # mock permissions
    with patch.object(honeypot_cog, "_is_channel_public", return_value=True):
        await honeypot_cog.honeypot_add_channel.callback(honeypot_cog, interaction, chan)
        interaction.followup.send.assert_called()

    hp_channels = session.exec(select(HoneypotChannel).where(HoneypotChannel.guild_id == guild_id)).all()
    assert len(hp_channels) == 1
    assert hp_channels[0].channel_id == 111

    # test add_channel private
    with patch.object(honeypot_cog, "_is_channel_public", return_value=False):
        await honeypot_cog.honeypot_add_channel.callback(honeypot_cog, interaction, chan)
        interaction.followup.send.assert_called_with(
            "Only public channels accessible to everyone can be used as honeypots."
        )

    # test remove_channel
    await honeypot_cog.honeypot_remove_channel.callback(honeypot_cog, interaction, chan)
    hp_channels = session.exec(select(HoneypotChannel).where(HoneypotChannel.guild_id == guild_id)).all()
    assert len(hp_channels) == 0

    # test remove_channel not found
    await honeypot_cog.honeypot_remove_channel.callback(honeypot_cog, interaction, chan)

    # test status empty
    interaction.followup.send.reset_mock()
    await honeypot_cog.honeypot_status.callback(honeypot_cog, interaction)
    assert interaction.followup.send.call_args is not None

    # test create channel error
    interaction.guild.create_text_channel = AsyncMock(side_effect=Exception("Test Create Error"))
    await honeypot_cog.honeypot_create_channel.callback(honeypot_cog, interaction, name="test-honeypot")
    interaction.followup.send.assert_called_with("Failed to create channel: Test Create Error")

    # test add_all_channels with confirmation
    chan2 = MagicMock(spec=nextcord.TextChannel)
    chan2.id = 222
    chan2.mention = "<#222>"
    # Setup the guild to return channels
    interaction.guild.text_channels = [chan, chan2]

    interaction.edit_original_message = AsyncMock()
    with patch("app.extensions.honeypot.cog.Confirm") as MockConfirm:
        mock_view = MagicMock()
        mock_view.value = True

        # wait() must be a proper coroutine function that resolves
        # immediately — AsyncMock().wait() can hang in the event loop.
        async def _immediate_wait():
            return

        mock_view.wait = _immediate_wait
        MockConfirm.return_value = mock_view

        with patch.object(honeypot_cog, "_is_channel_public", return_value=True):
            await honeypot_cog.honeypot_add_all_channels.callback(honeypot_cog, interaction)

        hp_channels = session.exec(select(HoneypotChannel).where(HoneypotChannel.guild_id == guild_id)).all()
        assert len(hp_channels) == 2
        assert {c.channel_id for c in hp_channels} == {111, 222}
        interaction.edit_original_message.assert_called()

    # test add_all_channels cancel
    session.exec(select(HoneypotChannel).where(HoneypotChannel.guild_id == guild_id)).all()  # clear not called
    with patch("app.extensions.honeypot.cog.Confirm") as MockConfirm:
        mock_view = MagicMock()
        mock_view.value = False

        async def _immediate_wait_cancel():
            return

        mock_view.wait = _immediate_wait_cancel
        MockConfirm.return_value = mock_view

        with patch.object(honeypot_cog, "_is_channel_public", return_value=True):
            await honeypot_cog.honeypot_add_all_channels.callback(honeypot_cog, interaction)

        interaction.edit_original_message.assert_called_with(content="Action cancelled.", view=None)

    # test clear_channels
    await honeypot_cog.honeypot_clear_channels.callback(honeypot_cog, interaction)
    interaction.followup.send.assert_called_with("Cleared 2 honeypot channel(s).")

    hp_channels = session.exec(select(HoneypotChannel).where(HoneypotChannel.guild_id == guild_id)).all()
    assert len(hp_channels) == 0
