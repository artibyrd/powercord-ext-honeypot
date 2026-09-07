"""A honeypot extension for automatically banning spammers across monitored channels.

Governed by:
- inv-500-loc-ceiling: 500 LOC module ceiling
- inv-split-stack-isolation: FastHTML vs FastAPI vs Nextcord boundary
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from typing import Dict, Tuple

import nextcord
from nextcord.ext import commands
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from app.common.alchemy import init_connection_engine

from .blueprint import HoneypotBanReport, HoneypotChannel, HoneypotSettings
from .cog_views import Confirm, build_honeypot_ban_embed, build_honeypot_status_embed


class HoneypotCog(commands.Cog):
    """A honeypot extension for automatically banning spammers."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.engine = init_connection_engine()
        # guild_id -> user_id -> set(channel_id), datetime of first post
        self.tracking: Dict[int, Dict[int, Tuple[set, datetime]]] = defaultdict(dict)

    def _get_time_limit(self, guild_id: int) -> int:
        with Session(self.engine) as session:
            settings = session.exec(select(HoneypotSettings).where(HoneypotSettings.guild_id == guild_id)).first()
            return settings.time_limit if settings else 60

    def _get_honeypot_channels(self, guild_id: int) -> set[int]:
        with Session(self.engine) as session:
            channels = session.exec(select(HoneypotChannel).where(HoneypotChannel.guild_id == guild_id)).all()
            return {c.channel_id for c in channels}

    def _is_channel_public(self, channel: nextcord.TextChannel) -> bool:
        """Check if the @everyone role has view_channel and send_messages permissions.

        This verification is crucial because honeypot channels must be accessible
        to standard users in order to catch broad spam bots.
        """
        everyone_role = channel.guild.default_role
        permissions = channel.permissions_for(everyone_role)
        return bool(permissions.view_channel and permissions.send_messages)

    @nextcord.slash_command(
        name="honeypot",
        description="Manage the honeypot extension.",
        default_member_permissions=nextcord.Permissions(administrator=True),
    )
    async def honeypot(self, interaction: nextcord.Interaction):
        """Manage the honeypot extension."""
        pass

    @honeypot.subcommand(
        name="set_time_limit",
        description="Set the time limit (in seconds) for a user to post in all honeypot channels to trigger a ban.",
    )
    async def honeypot_set_time_limit(self, interaction: nextcord.Interaction, seconds: int):
        """Set the time limit (in seconds) for a user to post in all honeypot channels to trigger a ban."""
        if not interaction.guild:
            return await interaction.response.send_message("This command must be used in a server.", ephemeral=True)

        await interaction.response.defer()

        if seconds <= 0:
            return await interaction.followup.send("Time limit must be greater than 0.")

        with Session(self.engine) as session:
            settings = session.exec(
                select(HoneypotSettings).where(HoneypotSettings.guild_id == interaction.guild.id)
            ).first()
            if not settings:
                settings = HoneypotSettings(guild_id=interaction.guild.id, time_limit=seconds)
                session.add(settings)
            else:
                settings.time_limit = seconds
            session.commit()

        await interaction.followup.send(f"Honeypot time limit set to {seconds} seconds.")

    @honeypot.subcommand(name="set_log_channel", description="Set the channel where honeypot ban reports will be sent.")
    async def honeypot_set_log_channel(
        self,
        interaction: nextcord.Interaction,
        channel: nextcord.abc.GuildChannel = nextcord.SlashOption(channel_types=[nextcord.ChannelType.text]),
    ):
        """Set the channel where honeypot ban reports will be sent."""
        if not interaction.guild:
            return await interaction.response.send_message("This command must be used in a server.", ephemeral=True)

        await interaction.response.defer()

        if not isinstance(channel, nextcord.TextChannel):
            return await interaction.followup.send("Log channel must be a text channel.")

        with Session(self.engine) as session:
            settings = session.exec(
                select(HoneypotSettings).where(HoneypotSettings.guild_id == interaction.guild.id)
            ).first()
            if not settings:
                settings = HoneypotSettings(guild_id=interaction.guild.id, log_channel_id=channel.id)
                session.add(settings)
            else:
                settings.log_channel_id = channel.id
            session.commit()

        await interaction.followup.send(f"Honeypot log channel set to {channel.mention}.")

    @honeypot.subcommand(name="add_channel", description="Add a channel to the honeypot list.")
    async def honeypot_add_channel(
        self,
        interaction: nextcord.Interaction,
        channel: nextcord.abc.GuildChannel = nextcord.SlashOption(channel_types=[nextcord.ChannelType.text]),
    ):
        """Add a channel to the honeypot list."""
        if not interaction.guild:
            return await interaction.response.send_message("This command must be used in a server.", ephemeral=True)

        await interaction.response.defer()

        if not isinstance(channel, nextcord.TextChannel):
            return await interaction.followup.send("Channel must be a text channel.")

        if not self._is_channel_public(channel):
            return await interaction.followup.send(
                "Honeypot channels must be public! (The `@everyone` role must have "
                "`view_channel` and `send_messages` permissions)."
            )

        with Session(self.engine) as session:
            hp_channel = HoneypotChannel(guild_id=interaction.guild.id, channel_id=channel.id)
            session.add(hp_channel)
            try:
                session.commit()
            except IntegrityError:
                session.rollback()
                return await interaction.followup.send("Channel is already a honeypot channel.")

        await interaction.followup.send(f"Added {channel.mention} to honeypot channels.")

    @honeypot.subcommand(name="remove_channel", description="Remove a channel from the honeypot list.")
    async def honeypot_remove_channel(
        self,
        interaction: nextcord.Interaction,
        channel: nextcord.abc.GuildChannel = nextcord.SlashOption(channel_types=[nextcord.ChannelType.text]),
    ):
        """Remove a channel from the honeypot list."""
        if not interaction.guild:
            return await interaction.response.send_message("This command must be used in a server.", ephemeral=True)

        await interaction.response.defer()

        if not isinstance(channel, nextcord.TextChannel):
            return await interaction.followup.send("Channel must be a text channel.")

        with Session(self.engine) as session:
            statement = select(HoneypotChannel).where(
                HoneypotChannel.guild_id == interaction.guild.id, HoneypotChannel.channel_id == channel.id
            )
            hp_channel = session.exec(statement).first()
            if not hp_channel:
                return await interaction.followup.send("Channel is not a honeypot channel.")
            session.delete(hp_channel)
            session.commit()

        await interaction.followup.send(f"Removed {channel.mention} from honeypot channels.")

    @honeypot.subcommand(name="toggle_shame", description="Toggle shame mode (insult spammers in the log channel).")
    async def honeypot_toggle_shame(self, interaction: nextcord.Interaction):
        """Toggle shame mode (insult spammers in the log channel)."""
        if not interaction.guild:
            return await interaction.response.send_message("This command must be used in a server.", ephemeral=True)

        await interaction.response.defer()

        with Session(self.engine) as session:
            settings = session.exec(
                select(HoneypotSettings).where(HoneypotSettings.guild_id == interaction.guild.id)
            ).first()
            if not settings:
                settings = HoneypotSettings(guild_id=interaction.guild.id, shame_mode=True)
                session.add(settings)
            else:
                settings.shame_mode = not settings.shame_mode
            session.commit()
            status = "enabled" if settings.shame_mode else "disabled"

        await interaction.followup.send(f"Honeypot shame mode {status}.")

    @honeypot.subcommand(name="status", description="Show the current honeypot settings and channels.")
    async def honeypot_status(self, interaction: nextcord.Interaction):
        """Show the current honeypot settings and channels."""
        if not interaction.guild:
            return await interaction.response.send_message("This command must be used in a server.", ephemeral=True)

        await interaction.response.defer()

        with Session(self.engine) as session:
            settings = session.exec(
                select(HoneypotSettings).where(HoneypotSettings.guild_id == interaction.guild.id)
            ).first()
            time_limit = settings.time_limit if settings else 60
            log_channel_id = settings.log_channel_id if settings else None
            shame_mode = settings.shame_mode if settings else False

        channels = self._get_honeypot_channels(interaction.guild.id)
        embed = build_honeypot_status_embed(time_limit, shame_mode, log_channel_id, channels)
        await interaction.followup.send(embed=embed)

    @honeypot.subcommand(name="add_all_channels", description="Add all public text channels to the honeypot list.")
    async def honeypot_add_all_channels(self, interaction: nextcord.Interaction):
        """Add all public text channels to the honeypot list."""
        if not interaction.guild:
            return await interaction.response.send_message("This command must be used in a server.", ephemeral=True)

        await interaction.response.defer()

        public_channels = [c for c in interaction.guild.text_channels if self._is_channel_public(c)]
        if not public_channels:
            return await interaction.followup.send("No public text channels found to add.")

        channel_names = ", ".join([c.mention for c in public_channels])
        limit = 1000
        desc = channel_names if len(channel_names) <= limit else channel_names[:limit] + "... and more."

        prompt = (
            f"Are you sure you want to add the following {len(public_channels)} public text channels as honeypots?\n{desc}"
        )
        view = Confirm()
        await interaction.followup.send(prompt, view=view)
        await view.wait()

        if view.value is None:
            return await interaction.edit_original_message(content="Command timed out.", view=None)
        elif view.value is False:
            return await interaction.edit_original_message(content="Action cancelled.", view=None)

        added_count = 0
        with Session(self.engine) as session:
            for channel in public_channels:
                try:
                    hp_channel = HoneypotChannel(guild_id=interaction.guild.id, channel_id=channel.id)
                    session.add(hp_channel)
                    session.commit()
                    added_count += 1
                except IntegrityError:
                    session.rollback()

        await interaction.edit_original_message(
            content=f"Successfully added {added_count} new honeypot channels.", view=None
        )

    @honeypot.subcommand(name="clear_channels", description="Clear all registered honeypot channels for this server.")
    async def honeypot_clear_channels(self, interaction: nextcord.Interaction):
        """Clear all registered honeypot channels for this server."""
        if not interaction.guild:
            return await interaction.response.send_message("This command must be used in a server.", ephemeral=True)

        await interaction.response.defer()

        with Session(self.engine) as session:
            statement = select(HoneypotChannel).where(HoneypotChannel.guild_id == interaction.guild.id)
            channels = session.exec(statement).all()

            count = len(channels)
            if count == 0:
                return await interaction.followup.send("There are no honeypot channels to clear.")

            for channel in channels:
                session.delete(channel)
            session.commit()

        await interaction.followup.send(f"Cleared {count} honeypot channel(s).")

    @commands.Cog.listener()
    async def on_message(self, message: nextcord.Message):
        """Monitors all messages to detect cross-channel honeypot spam."""
        if message.author.bot or message.guild is None:
            return

        guild_id = message.guild.id
        channel_id = message.channel.id
        user_id = message.author.id

        hp_channels = self._get_honeypot_channels(guild_id)
        if not hp_channels or channel_id not in hp_channels:
            return

        now = datetime.now(timezone.utc)

        if user_id not in self.tracking[guild_id]:
            self.tracking[guild_id][user_id] = (set(), now)

        posted_channels, first_post_time = self.tracking[guild_id][user_id]

        with Session(self.engine) as session:
            settings = session.exec(select(HoneypotSettings).where(HoneypotSettings.guild_id == guild_id)).first()
            time_limit = settings.time_limit if settings else 60
            log_channel_id = settings.log_channel_id if settings else None
            shame_mode = settings.shame_mode if settings else False

        time_diff = (now - first_post_time).total_seconds()
        if time_diff > time_limit:
            self.tracking[guild_id][user_id] = ({channel_id}, now)
            return

        posted_channels.add(channel_id)
        self.tracking[guild_id][user_id] = (posted_channels, first_post_time)

        # At least 2 channels required to trigger a ban to prevent accidental bans from a single post
        if len(posted_channels) == len(hp_channels) and len(hp_channels) > 1:
            try:
                reason = "Auto-banned by honeypot extension."
                await message.guild.ban(message.author, reason=reason, delete_message_seconds=86400)

                with Session(self.engine) as session:
                    report = HoneypotBanReport(
                        guild_id=guild_id, user_id=user_id, username=str(message.author), reason=reason
                    )
                    session.add(report)
                    session.commit()

                del self.tracking[guild_id][user_id]

                if log_channel_id:
                    log_channel = message.guild.get_channel(log_channel_id)
                    if log_channel and isinstance(log_channel, nextcord.TextChannel):
                        embed = build_honeypot_ban_embed(message.author, reason, timestamp=now, shame_mode=shame_mode)
                        try:
                            await log_channel.send(embed=embed)
                        except (nextcord.Forbidden, nextcord.HTTPException):
                            pass

            except nextcord.Forbidden:
                print(f"Honeypot: Failed to ban {message.author} in {message.guild.name} (Forbidden)")
            except nextcord.HTTPException as e:
                print(f"Honeypot: Failed to ban {message.author} in {message.guild.name} ({e})")


def setup(bot: commands.Bot):
    bot.add_cog(HoneypotCog(bot))
