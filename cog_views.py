"""Nextcord UI views, embed builders, and shame mode assets for the Honeypot extension.

Governed by:
- inv-500-loc-ceiling: 500 LOC module ceiling
- inv-split-stack-isolation: Discord UI views and embed formatting
"""

from __future__ import annotations

from datetime import datetime, timezone
import random

import nextcord

INSULTS: list[str] = [
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


def get_shame_insult() -> str:
    """Returns a random shame insult from the catalog."""
    return random.choice(INSULTS)


class Confirm(nextcord.ui.View):
    """Interactive confirmation dialog view for destructive honeypot admin actions."""

    def __init__(self) -> None:
        super().__init__()
        self.value: bool | None = None

    @nextcord.ui.button(label="Confirm", style=nextcord.ButtonStyle.green)
    async def confirm(self, button: nextcord.ui.Button, interaction: nextcord.Interaction) -> None:
        await interaction.response.send_message("Confirming...", ephemeral=True)
        self.value = True
        self.stop()

    @nextcord.ui.button(label="Cancel", style=nextcord.ButtonStyle.grey)
    async def cancel(self, button: nextcord.ui.Button, interaction: nextcord.Interaction) -> None:
        await interaction.response.send_message("Cancelling...", ephemeral=True)
        self.value = False
        self.stop()


def build_honeypot_status_embed(
    time_limit: int, shame_mode: bool, log_channel_id: int | None, channels: set[int]
) -> nextcord.Embed:
    """Builds a formatted Nextcord Embed displaying current honeypot configuration."""
    channels_list = ", ".join(f"<#{c}>" for c in channels) if channels else "None"
    log_channel_str = f"<#{log_channel_id}>" if log_channel_id else "None"

    embed = nextcord.Embed(title="Honeypot Status", color=nextcord.Color.orange())
    embed.add_field(name="Time Limit", value=f"{time_limit} seconds", inline=True)
    embed.add_field(name="Shame Mode", value="Enabled" if shame_mode else "Disabled", inline=True)
    embed.add_field(name="Log Channel", value=log_channel_str, inline=True)
    embed.add_field(name="Honeypot Channels", value=channels_list, inline=False)
    return embed


def build_honeypot_ban_embed(
    user: nextcord.User | nextcord.Member,
    reason: str,
    timestamp: datetime | None = None,
    shame_mode: bool = False,
) -> nextcord.Embed:
    """Builds a formatted Nextcord Embed for ban execution logs."""
    ts = timestamp or datetime.now(timezone.utc)
    embed = nextcord.Embed(
        title="🍯 Honeypot Ban Executed",
        description=f"**User:** {user.mention} (`{user.id}`)\n**Reason:** {reason}",
        color=nextcord.Color.red(),
        timestamp=ts,
    )
    if shame_mode:
        embed.set_footer(text=get_shame_insult())
    return embed
