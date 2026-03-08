from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlmodel import Session, select

from app.common.alchemy import get_session

from .blueprint import HoneypotChannel, HoneypotSettings

router = APIRouter()


@router.post("/config/{guild_id}/settings")
async def update_settings(
    request: Request,
    guild_id: int,
    time_limit: int = Form(...),
    log_channel_id: int = Form(...),
    shame_mode: bool = Form(False),
    session: Session = Depends(get_session),
):
    """Update the settings for the honeypot extension via the dashboard."""
    if time_limit <= 0:
        raise HTTPException(status_code=400, detail="Time limit must be positive.")

    settings = session.exec(select(HoneypotSettings).where(HoneypotSettings.guild_id == guild_id)).first()

    # If log_channel_id is 0, it means "None"
    actual_log_channel = None if log_channel_id == 0 else log_channel_id

    if not settings:
        settings = HoneypotSettings(
            guild_id=guild_id, time_limit=time_limit, log_channel_id=actual_log_channel, shame_mode=shame_mode
        )
        session.add(settings)
    else:
        settings.time_limit = time_limit
        settings.log_channel_id = actual_log_channel
        settings.shame_mode = shame_mode

    session.commit()

    # Redirect back to the dashboard via Referer, failing back to a generic relative path
    referer = request.headers.get("referer")
    return RedirectResponse(referer or f"/dashboard/{guild_id}", status_code=303)


@router.post("/config/{guild_id}/remove_channel")
async def remove_channel(
    request: Request, guild_id: int, channel_id: int = Form(...), session: Session = Depends(get_session)
):
    """Remove a channel from honeypot list via dashboard."""
    channel = session.exec(
        select(HoneypotChannel).where(HoneypotChannel.guild_id == guild_id, HoneypotChannel.channel_id == channel_id)
    ).first()

    if channel:
        session.delete(channel)
        session.commit()

    # Redirect back to the dashboard
    referer = request.headers.get("referer")
    return RedirectResponse(referer or f"/dashboard/{guild_id}", status_code=303)


@router.post("/config/{guild_id}/clear_channels")
async def clear_channels(request: Request, guild_id: int, session: Session = Depends(get_session)):
    """Remove all channels from honeypot list via dashboard."""
    channels = session.exec(select(HoneypotChannel).where(HoneypotChannel.guild_id == guild_id)).all()

    for channel in channels:
        session.delete(channel)
    session.commit()

    referer = request.headers.get("referer")
    return RedirectResponse(referer or f"/dashboard/{guild_id}", status_code=303)
