from sqlmodel import Session, SQLModel, col, delete

from app.common.alchemy import init_connection_engine
from app.common.extension_hooks import register_hook

from .blueprint import (
    HoneypotBanReport as HoneypotBanReport,
)
from .blueprint import (
    HoneypotChannel as HoneypotChannel,
)
from .blueprint import (
    HoneypotSettings as HoneypotSettings,
)

try:
    engine = init_connection_engine()
    # Create tables if they don't exist
    SQLModel.metadata.create_all(engine)
except Exception as e:
    print(f"Warning: Could not create tables for honeypot extension: {e}")


def _delete_guild_data(guild_id: int) -> None:
    """Remove all honeypot data for a specific guild."""
    _engine = init_connection_engine()
    with Session(_engine) as session:
        session.exec(delete(HoneypotSettings).where(col(HoneypotSettings.guild_id) == guild_id))
        session.exec(delete(HoneypotChannel).where(col(HoneypotChannel.guild_id) == guild_id))
        session.exec(delete(HoneypotBanReport).where(col(HoneypotBanReport.guild_id) == guild_id))
        session.commit()


register_hook("honeypot", "delete_guild_data", _delete_guild_data)
