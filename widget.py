# mypy: ignore-errors
from fasthtml.common import *
from sqlmodel import Session, desc, select

from app.common.alchemy import init_connection_engine
from app.db.models import DiscordChannel
from app.ui.components import Card

from .blueprint import HoneypotBanReport, HoneypotChannel, HoneypotSettings

engine = init_connection_engine()


def guild_admin_honeypot_config(guild_id: int):
    """Widget to configure the honeypot extension for a specific guild.

    This widget fetches the current time limit and tracked channels from the
    database and renders a FastHTML form to allow admins to update these settings.
    It expects the endpoints in `sprocket.py` to handle the POST responses.
    """
    with Session(engine) as session:
        settings = session.exec(select(HoneypotSettings).where(HoneypotSettings.guild_id == guild_id)).first()
        time_limit = settings.time_limit if settings else 60
        log_channel_id_val = settings.log_channel_id if settings else 0
        shame_mode_val = settings.shame_mode if settings else False

        channels = session.exec(select(HoneypotChannel).where(HoneypotChannel.guild_id == guild_id)).all()
        discord_channels = session.exec(select(DiscordChannel).where(DiscordChannel.guild_id == guild_id)).all()
        channel_names = {dc.id: dc.name for dc in discord_channels}

    # Form to update settings

    channel_options = [Option("None", value="0", selected=(log_channel_id_val == 0))]
    for dc in discord_channels:
        if dc.type == "text":
            channel_options.append(Option(f"#{dc.name}", value=str(dc.id), selected=(log_channel_id_val == dc.id)))

    settings_form = Form(
        Div(
            Label("Time Limit (seconds):", cls="label-text opacity-80 mb-2 block"),
            Input(
                type="number",
                name="time_limit",
                value=str(time_limit),
                min="1",
                cls="input input-bordered input-sm w-32",
            ),
            cls="mb-4",
        ),
        Div(
            Label("Ban Report Channel:", cls="label-text opacity-80 mb-2 block"),
            Select(*channel_options, name="log_channel_id", cls="select select-bordered select-sm w-full max-w-xs"),
            cls="mb-4",
        ),
        Div(
            Label(
                Span("Enable Shame Mode", cls="label-text opacity-80 mr-2"),
                Input(
                    type="checkbox",
                    name="shame_mode",
                    value="true",
                    checked=shame_mode_val,
                    cls="checkbox checkbox-sm checkbox-primary",
                ),
                cls="cursor-pointer flex items-center",
            ),
            cls="mb-4",
        ),
        Button("Save Settings", cls="btn btn-primary btn-sm"),
        action=f"http://127.0.0.1:8000/honeypot/config/{guild_id}/settings",
        method="post",
        cls="mb-6 p-4 bg-base-200 rounded-lg",
    )

    # List of honeypot channels with remove buttons
    channel_items = []
    clear_all_form = ""
    if not channels:
        channel_items.append(
            P(
                "No honeypot channels configured. Use the bot command /honeypot add_channel.",
                cls="text-sm opacity-60 italic",
            )
        )
    else:
        clear_all_form = Form(
            Button("Remove All", cls="btn btn-error btn-sm"),
            action=f"http://127.0.0.1:8000/honeypot/config/{guild_id}/clear_channels",
            method="post",
            cls="mb-4",
        )
        for ch in channels:
            c_name = channel_names.get(ch.channel_id, "Unknown")
            channel_items.append(
                Li(
                    Div(
                        Span(f"#{c_name} ({ch.channel_id})", cls="font-mono text-sm"),
                        Form(
                            Hidden(name="channel_id", value=str(ch.channel_id)),
                            Button("Remove", cls="btn btn-error btn-xs"),
                            action=f"http://127.0.0.1:8000/honeypot/config/{guild_id}/remove_channel",
                            method="post",
                            cls="inline-block ml-4",
                        ),
                        cls="flex items-center justify-between mb-2 p-2 bg-base-200 rounded",
                    )
                )
            )

    return Card(
        "Honeypot Configuration",
        Div(
            settings_form,
            Div(
                Div(
                    H4("Active Honeypot Channels", cls="font-semibold text-sm opacity-80"),
                    clear_all_form,
                    cls="flex justify-between items-center mb-2",
                ),
                Ul(*channel_items),
            ),
            cls="w-full",
        ),
    )


def guild_admin_honeypot_reports(guild_id: int):
    """Widget to view recent ban reports from the honeypot extension.

    Queries the database for the 10 most recent automated bans in this specific
    guild, rendering them in a FastHTML table for easy auditing.
    """
    with Session(engine) as session:
        reports = session.exec(
            select(HoneypotBanReport)
            .where(HoneypotBanReport.guild_id == guild_id)
            .order_by(desc(HoneypotBanReport.banned_at))
            .limit(10)
        ).all()

    if not reports:
        return Card(
            "Honeypot Ban Reports",
            Div(P("No spammers have been banned yet.", cls="opacity-60 italic"), cls="text-center p-4"),
        )

    rows = []
    for report in reports:
        dt_str = report.banned_at.strftime("%Y-%m-%d %H:%M:%S UTC")
        rows.append(
            Tr(
                Td(report.username, cls="font-semibold"),
                Td(str(report.user_id), cls="font-mono text-xs opacity-70"),
                Td(dt_str, cls="text-sm"),
            )
        )

    table = Table(
        Thead(
            Tr(
                Th("Username"),
                Th("User ID"),
                Th("Date/Time"),
            )
        ),
        Tbody(*rows),
        cls="table table-zebra table-sm w-full",
    )

    return Card(
        "Honeypot Ban Reports",
        Div(
            table,
            P("Showing the 10 most recent auto-bans.", cls="text-xs opacity-50 mt-4 text-center"),
            cls="overflow-x-auto",
        ),
    )
