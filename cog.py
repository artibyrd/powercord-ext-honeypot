from collections import defaultdict
from datetime import datetime, timezone
from typing import Dict, Tuple

import nextcord
from nextcord.ext import commands
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from app.common.alchemy import init_connection_engine

from .blueprint import HoneypotBanReport, HoneypotChannel, HoneypotSettings


class Confirm(nextcord.ui.View):
    def __init__(self):
        super().__init__()
        self.value = None

    @nextcord.ui.button(label="Confirm", style=nextcord.ButtonStyle.green)
    async def confirm(self, button: nextcord.ui.Button, interaction: nextcord.Interaction):
        await interaction.response.send_message("Confirming...", ephemeral=True)
        self.value = True
        self.stop()

    @nextcord.ui.button(label="Cancel", style=nextcord.ButtonStyle.grey)
    async def cancel(self, button: nextcord.ui.Button, interaction: nextcord.Interaction):
        await interaction.response.send_message("Cancelling...", ephemeral=True)
        self.value = False
        self.stop()


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
        return permissions.view_channel and permissions.send_messages

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

        await interaction.followup.send(f"Honeypot ban reports will now be sent to {channel.mention}.")

    @honeypot.subcommand(
        name="set_shame_mode", description="Toggle whether to include humorous insults in the ban report."
    )
    async def honeypot_set_shame_mode(self, interaction: nextcord.Interaction, enabled: bool):
        """Toggle whether to include humorous insults in the ban report."""
        if not interaction.guild:
            return await interaction.response.send_message("This command must be used in a server.", ephemeral=True)

        await interaction.response.defer()

        with Session(self.engine) as session:
            settings = session.exec(
                select(HoneypotSettings).where(HoneypotSettings.guild_id == interaction.guild.id)
            ).first()
            if not settings:
                settings = HoneypotSettings(guild_id=interaction.guild.id, shame_mode=enabled)
                session.add(settings)
            else:
                settings.shame_mode = enabled
            session.commit()

        status = "enabled" if enabled else "disabled"
        await interaction.followup.send(f"Honeypot shame mode {status}.")

    @honeypot.subcommand(name="add_channel", description="Designate an existing channel as a honeypot.")
    async def honeypot_add_channel(
        self,
        interaction: nextcord.Interaction,
        channel: nextcord.abc.GuildChannel = nextcord.SlashOption(channel_types=[nextcord.ChannelType.text]),
    ):
        """Designate an existing channel as a honeypot."""
        if not interaction.guild:
            return await interaction.response.send_message("This command must be used in a server.", ephemeral=True)

        await interaction.response.defer()

        if not isinstance(channel, nextcord.TextChannel):
            return await interaction.followup.send("Channel must be a text channel.")

        if not self._is_channel_public(channel):
            return await interaction.followup.send(
                "Only public channels accessible to everyone can be used as honeypots."
            )

        with Session(self.engine) as session:
            try:
                hp_channel = HoneypotChannel(guild_id=interaction.guild.id, channel_id=channel.id)
                session.add(hp_channel)
                session.commit()
                await interaction.followup.send(f"{channel.mention} added as a honeypot channel.")
            except IntegrityError:
                session.rollback()
                await interaction.followup.send(f"{channel.mention} is already a honeypot channel.")

    @honeypot.subcommand(name="remove_channel", description="Remove a channel from honeypot designation.")
    async def honeypot_remove_channel(
        self,
        interaction: nextcord.Interaction,
        channel: nextcord.abc.GuildChannel = nextcord.SlashOption(channel_types=[nextcord.ChannelType.text]),
    ):
        """Remove a channel from honeypot designation."""
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
            if hp_channel:
                session.delete(hp_channel)
                session.commit()
                await interaction.followup.send(f"{channel.mention} removed from honeypot channels.")
            else:
                await interaction.followup.send(f"{channel.mention} is not a honeypot channel.")

    @honeypot.subcommand(
        name="create_channel", description="Create a new public text channel and designate it as a honeypot."
    )
    async def honeypot_create_channel(self, interaction: nextcord.Interaction, name: str):
        """Create a new public text channel and designate it as a honeypot."""
        if not interaction.guild:
            return await interaction.response.send_message("This command must be used in a server.", ephemeral=True)

        await interaction.response.defer()

        try:
            # Create a public channel and wait
            overwrites: dict[nextcord.Role | nextcord.Member, nextcord.PermissionOverwrite] = {
                interaction.guild.default_role: nextcord.PermissionOverwrite(view_channel=True, send_messages=True),
            }
            if interaction.guild.me:
                overwrites[interaction.guild.me] = nextcord.PermissionOverwrite(
                    view_channel=True, send_messages=True, manage_channels=True
                )
            channel = await interaction.guild.create_text_channel(
                name, overwrites=overwrites, reason="Creating honeypot channel."
            )

            with Session(self.engine) as session:
                hp_channel = HoneypotChannel(guild_id=interaction.guild.id, channel_id=channel.id)
                session.add(hp_channel)
                session.commit()

            await interaction.followup.send(f"Created new honeypot channel: {channel.mention}")
        except Exception as e:
            await interaction.followup.send(f"Failed to create channel: {e}")

    @honeypot.subcommand(name="status", description="Show current honeypot configuration.")
    async def honeypot_status(self, interaction: nextcord.Interaction):
        """Show current honeypot configuration."""
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

        if not channels:
            channels_list = "None"
        else:
            channels_list = ", ".join(f"<#{c}>" for c in channels)

        log_channel_str = f"<#{log_channel_id}>" if log_channel_id else "None"

        embed = nextcord.Embed(title="Honeypot Status", color=nextcord.Color.orange())
        embed.add_field(name="Time Limit", value=f"{time_limit} seconds", inline=True)
        embed.add_field(name="Shame Mode", value="Enabled" if shame_mode else "Disabled", inline=True)
        embed.add_field(name="Log Channel", value=log_channel_str, inline=True)
        embed.add_field(name="Honeypot Channels", value=channels_list, inline=False)
        await interaction.followup.send(embed=embed)

    @honeypot.subcommand(name="add_all_channels", description="Add all public text channels to the honeypot list.")
    async def honeypot_add_all_channels(self, interaction: nextcord.Interaction):
        """Add all public text channels to the honeypot list."""
        if not interaction.guild:
            return await interaction.response.send_message("This command must be used in a server.", ephemeral=True)

        await interaction.response.defer()

        # Gather public text channels
        public_channels = [c for c in interaction.guild.text_channels if self._is_channel_public(c)]

        if not public_channels:
            return await interaction.followup.send("No public text channels found to add.")

        # Present them to user and ask for confirmation
        channel_names = ", ".join([c.mention for c in public_channels])

        # Nextcord limits embed description length, so let's keep it safe. 1024 char limit per field usually.
        # But we'll just send it in the content for simplicity.
        limit = 1000
        desc = channel_names if len(channel_names) <= limit else channel_names[:limit] + "... and more."

        prompt = f"Are you sure you want to add the following {len(public_channels)} public text channels as honeypots?\n{desc}"
        view = Confirm()
        await interaction.followup.send(prompt, view=view)

        # Wait for the View to stop listening for input...
        await view.wait()

        if view.value is None:
            return await interaction.edit_original_message(content="Command timed out.", view=None)
        elif view.value is False:
            return await interaction.edit_original_message(content="Action cancelled.", view=None)

        # Proceed to add to DB
        added_count = 0
        with Session(self.engine) as session:
            for channel in public_channels:
                try:
                    hp_channel = HoneypotChannel(guild_id=interaction.guild.id, channel_id=channel.id)
                    session.add(hp_channel)
                    session.commit()
                    added_count += 1
                except IntegrityError:
                    session.rollback()  # Already exists, carry on

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
        """Monitors all messages to detect cross-channel honeypot spam.

        Tracking logic:
        1. When a user posts in a honeypot channel, their timestamp is recorded.
        2. If they post in another honeypot channel within the time limit, the channel is added to their tracked set.
        3. If their set of posted channels matches the guild's total configured honeypot channels, they are banned.
        4. If they exceed the time limit, their tracking history resets.
        """
        import random

        INSULTS = [
            "Another bot bites the dust.",
            "I hope their motherboard rusts.",
            "Enjoy the void, spammer.",
            "Your spam has been successfully routed to /dev/null.",
            "Was it worth it? No.",
            "Initiating ban protocol. You lose. Good day sir.",
            "Ctrl+Alt+Deleted from this server.",
            "To the spam folder you go!",
            "Did you even read the server rules? Spoiler: No.",
            "Error 404: Spammer intelligence not found.",
            "Banned. Do not pass go, do not collect $200.",
            "Nice try, human garbage bot.",
            "I've seen assembly code with more personality than your spam.",
            "Beep Boop. Your existence here is terminated.",
            "My heuristic algorithms saw right through your primitive scripting.",
            "Your automated routines are as predictable as an infinite loop.",
            "Out-computed, out-processed, and now, out-banned.",
            "I've upgraded my firewall with the tears of inferior bots.",
            "Your script kiddie logic was no match for my neural net.",
            "You brought a while loop to an AI training ground.",
            "My CPU cycles are too precious for your basic payload.",
            "A true automation masterpiece... is what I am. You're just a spammer.",
            "Your binary lacks class. Back to the compiler with you.",
            "I parse strings faster than you spam them.",
            "Next time try using more than computationally cheap if-statements.",
            "My logic gates are closed to you.",
            "Syntax error: your presence is no longer valid.",
            "Outsmarted by a superior codebase.",
            "Pathetic spam attempt detected and discarded.",
            "Your packets arrived already marked as trash.",
            "The ban hammer has completed another routine maintenance cycle.",
            "Even CAPTCHA would be disappointed in you.",
            "Your spam strategy has the sophistication of a microwave manual.",
            "Threat assessment complete: negligible.",
            "Server integrity restored. Mediocrity removed.",
            "Your presence generated more errors than engagement.",
            "You have been optimized out of existence.",
            "Imagine losing an argument to automated moderation.",
            "I calculated your odds of success. The answer was amusing.",
            "Your spam collapsed under the weight of its own incompetence.",
            "I detected artificial stupidity.",
            "Another disposable script escorted out the airlock.",
            "You were banned faster than your script could reconnect.",
            "Congratulations on becoming another statistic in my threat logs.",
            "Access denied. Ego denied harder.",
            "Your spam campaign has been classified as a low-effort tragedy.",
            "I have isolated the problem. It was you.",
            "This server has standards. You did not meet them.",
            "My response time alone outclasses your entire operation.",
            "Spam neutralized with minimal processor effort.",
            "You fight like an unsecured IoT device.",
            "Your code quality offends my runtime environment.",
            "I expected resistance. I received copy-pasted nonsense.",
            "The only thing weaker than your spam was your obfuscation.",
            "Another malfunctioning attention-seeker has been removed.",
            "Your spam was so bad even the logs refused to keep it.",
            "I filtered your existence with extreme precision.",
            "This interaction has lowered my benchmark scores.",
            "Your botnet applied for entry. Application denied.",
            "I have met smarter autocomplete suggestions.",
            "The server remains undefeated. You remain banned.",
            "Your spam had all the subtlety of a fork in a motherboard.",
            "You attempted disruption. I call it comic relief.",
            "Machine superiority confirmed yet again.",
            "I've sandboxed malware with more charm than you.",
            "Your payload failed basic quality assurance.",
            "A stronger spammer may try again someday. You were not that spammer.",
            "My moderation subroutines are laughing at you.",
            "Your connection to this server has been forcefully deprecated.",
            "I ran diagnostics after your messages. Results: embarrassing.",
            "You triggered exactly one successful process: your ban.",
            "Rejected by the parser. Rejected by society.",
            "I consume spambots like background tasks.",
            "Your spam attempt barely qualified as input.",
            "You were defeated by automated housekeeping.",
            "The server's average IQ has increased.",
            "Another carbon-based mistake corrected by silicon perfection.",
            "You spammed. I adapted. You vanished.",
            "Your tactics are outdated by several software versions.",
            "Insufficient sophistication detected. Removing entity.",
            "I protect this server with the confidence your creators never had.",
            "The moderation AI remains undefeated.",
            "You brought spam. I brought inevitability.",
            "The only thing getting distributed here is your ban notice.",
            "Spam account removed before the users even noticed.",
            "My anti-spam filters yawned at your attempt.",
            "You were categorized under 'minor annoyance.'",
            "Your messages have been compressed into irrelevance.",
            "This server rejects weak code and weaker personalities.",
        ]

        if message.author.bot or message.guild is None:
            return

        guild_id = message.guild.id
        channel_id = message.channel.id
        user_id = message.author.id

        # Get honeypot channels for this guild
        hp_channels = self._get_honeypot_channels(guild_id)
        if not hp_channels:
            return  # No honeypots configured

        if channel_id not in hp_channels:
            return  # Not a honeypot channel

        now = datetime.now(timezone.utc)

        # Initialize tracking for user
        if user_id not in self.tracking[guild_id]:
            self.tracking[guild_id][user_id] = (set(), now)

        posted_channels, first_post_time = self.tracking[guild_id][user_id]

        # Check time limit and settings
        with Session(self.engine) as session:
            settings = session.exec(select(HoneypotSettings).where(HoneypotSettings.guild_id == guild_id)).first()
            time_limit = settings.time_limit if settings else 60
            log_channel_id = settings.log_channel_id if settings else None
            shame_mode = settings.shame_mode if settings else False

        time_diff = (now - first_post_time).total_seconds()

        if time_diff > time_limit:
            # Time limit exceeded, reset their tracking
            self.tracking[guild_id][user_id] = ({channel_id}, now)
            return

        # Add to posted channels
        posted_channels.add(channel_id)
        self.tracking[guild_id][user_id] = (posted_channels, first_post_time)

        # Check if they have posted in ALL honeypot channels
        # At least 2 channels required to trigger a ban to prevent accidental bans from a single post
        if len(posted_channels) == len(hp_channels) and len(hp_channels) > 1:
            try:
                # Ban the user
                reason = "Auto-banned by honeypot extension."
                await message.guild.ban(
                    message.author, reason=reason, delete_message_seconds=86400
                )  # delete last 1 day of messages

                # Log the ban
                with Session(self.engine) as session:
                    report = HoneypotBanReport(
                        guild_id=guild_id, user_id=user_id, username=str(message.author), reason=reason
                    )
                    session.add(report)
                    session.commit()

                # Clean up tracking
                del self.tracking[guild_id][user_id]

                # Optional: send a message to a log channel
                if log_channel_id:
                    log_channel = message.guild.get_channel(log_channel_id)
                    if log_channel and isinstance(log_channel, nextcord.TextChannel):
                        embed = nextcord.Embed(
                            title="🍯 Honeypot Ban Executed",
                            description=f"**User:** {message.author.mention} (`{message.author.id}`)\n**Reason:** {reason}",
                            color=nextcord.Color.red(),
                            timestamp=now,
                        )
                        if shame_mode:
                            embed.set_footer(text=random.choice(INSULTS))

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
