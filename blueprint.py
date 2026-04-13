from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import BigInteger, Column
from sqlmodel import Field, SQLModel


class HoneypotSettings(SQLModel, table=True):
    """Stores configuration for the honeypot extension per guild."""

    __tablename__ = "honeypot_settings"
    __table_args__ = {"extend_existing": True}

    id: Optional[int] = Field(default=None, primary_key=True)
    guild_id: int = Field(sa_column=Column(BigInteger, unique=True))
    time_limit: int = Field(default=60)  # Time limit in seconds
    log_channel_id: Optional[int] = Field(default=None, sa_column=Column(BigInteger, nullable=True))
    shame_mode: bool = Field(default=False)


class HoneypotChannel(SQLModel, table=True):
    """Tracks which channels are designated as honeypots."""

    __tablename__ = "honeypot_channels"
    __table_args__ = {"extend_existing": True}

    id: Optional[int] = Field(default=None, primary_key=True)
    guild_id: int = Field(sa_column=Column(BigInteger))
    channel_id: int = Field(sa_column=Column(BigInteger, unique=True))
    added_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class HoneypotBanReport(SQLModel, table=True):
    """Log of bans executed by the honeypot extension."""

    __tablename__ = "honeypot_ban_reports"
    __table_args__ = {"extend_existing": True}

    id: Optional[int] = Field(default=None, primary_key=True)
    guild_id: int = Field(sa_column=Column(BigInteger))
    user_id: int = Field(sa_column=Column(BigInteger))
    username: str = Field(max_length=255)
    banned_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    reason: str = Field(max_length=500, default="Auto-banned by honeypot extension.")
