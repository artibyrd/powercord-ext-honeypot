# mypy: ignore-errors
"""Honeypot UI routes — auto-registered by the Powercord extension loader.

Provides browser-facing endpoints that handle form submissions from the
honeypot dashboard widget.  Each route performs the database operation
directly and returns a re-rendered widget HTML fragment so HTMX can
swap the updated content in-place without a full page reload.

These routes run on the FastHTML server (the same origin as the
dashboard), eliminating the routing mismatch that occurs when widget
forms attempt to POST to the FastAPI backend.

The sprocket (``sprocket.py``) remains available as a JSON API for
external consumers (Flet companion client, bots, third-party tools).
"""

import logging

from fasthtml.common import *
from sqlmodel import Session, select

from app.common.alchemy import init_connection_engine

from .blueprint import HoneypotChannel, HoneypotSettings

logger = logging.getLogger(__name__)


def register_routes(rt):
    """Called by the Powercord extension loader to mount extension-specific
    UI routes onto the FastHTML app.  ``rt`` is the route decorator."""

    @rt("/honeypot/config/{guild_id}/settings", methods=["POST"])
    async def save_honeypot_settings(guild_id: int, req):
        """Persist honeypot settings from the dashboard form.

        Reads ``time_limit``, ``log_channel_id``, and ``shame_mode`` from the
        submitted form data, upserts the ``HoneypotSettings`` row, and returns
        the re-rendered configuration widget for HTMX to swap in.
        """
        form_data = await req.form()
        time_limit = int(form_data.get("time_limit", 60))
        log_channel_id = int(form_data.get("log_channel_id", 0))
        shame_mode = form_data.get("shame_mode") == "true"

        if time_limit <= 0:
            return P(
                "Error: Time limit must be a positive number.",
                cls="text-error text-sm font-semibold p-4",
            )

        actual_log_channel = None if log_channel_id == 0 else log_channel_id

        engine = init_connection_engine()
        with Session(engine) as session:
            settings = session.exec(select(HoneypotSettings).where(HoneypotSettings.guild_id == guild_id)).first()

            if not settings:
                settings = HoneypotSettings(
                    guild_id=guild_id,
                    time_limit=time_limit,
                    log_channel_id=actual_log_channel,
                    shame_mode=shame_mode,
                )
                session.add(settings)
            else:
                settings.time_limit = time_limit
                settings.log_channel_id = actual_log_channel
                settings.shame_mode = shame_mode

            session.commit()

        logger.info("Honeypot settings saved for guild %s", guild_id)

        # Import the widget renderer and return the updated fragment
        from .widget import guild_admin_honeypot_config

        return guild_admin_honeypot_config(guild_id)

    @rt("/honeypot/config/{guild_id}/remove_channel", methods=["POST"])
    async def remove_honeypot_channel(guild_id: int, req):
        """Remove a single channel from the honeypot tracking list.

        Reads ``channel_id`` from the submitted form data, deletes the
        matching ``HoneypotChannel`` row, and returns the re-rendered
        configuration widget.
        """
        form_data = await req.form()
        channel_id = int(form_data.get("channel_id", 0))

        if channel_id == 0:
            return P(
                "Error: No channel specified.",
                cls="text-error text-sm font-semibold p-4",
            )

        engine = init_connection_engine()
        with Session(engine) as session:
            channel = session.exec(
                select(HoneypotChannel).where(
                    HoneypotChannel.guild_id == guild_id,
                    HoneypotChannel.channel_id == channel_id,
                )
            ).first()

            if channel:
                session.delete(channel)
                session.commit()
                logger.info(
                    "Removed honeypot channel %s from guild %s",
                    channel_id,
                    guild_id,
                )

        from .widget import guild_admin_honeypot_config

        return guild_admin_honeypot_config(guild_id)

    @rt("/honeypot/config/{guild_id}/clear_channels", methods=["POST"])
    async def clear_honeypot_channels(guild_id: int, req):
        """Remove all honeypot channels for a guild.

        Deletes every ``HoneypotChannel`` row for the given guild and
        returns the re-rendered configuration widget.
        """
        engine = init_connection_engine()
        with Session(engine) as session:
            channels = session.exec(select(HoneypotChannel).where(HoneypotChannel.guild_id == guild_id)).all()

            for channel in channels:
                session.delete(channel)
            session.commit()

        logger.info("Cleared all honeypot channels for guild %s", guild_id)

        from .widget import guild_admin_honeypot_config

        return guild_admin_honeypot_config(guild_id)
