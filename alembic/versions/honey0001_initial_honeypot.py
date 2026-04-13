"""initial_honeypot

Revision ID: honey0001
Revises:
Create Date: 2026-04-10 22:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel.sql.sqltypes


# revision identifiers, used by Alembic.
revision: str = "honey0001"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = inspector.get_table_names()

    if "honeypot_settings" not in existing_tables:
        op.create_table(
            "honeypot_settings",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("guild_id", sa.BigInteger(), nullable=True),
            sa.Column("time_limit", sa.Integer(), nullable=False),
            sa.Column("log_channel_id", sa.BigInteger(), nullable=True),
            sa.Column("shame_mode", sa.Boolean(), nullable=False),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(op.f("ix_honeypot_settings_guild_id"), "honeypot_settings", ["guild_id"], unique=True)

    if "honeypot_channels" not in existing_tables:
        op.create_table(
            "honeypot_channels",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("guild_id", sa.BigInteger(), nullable=True),
            sa.Column("channel_id", sa.BigInteger(), nullable=True),
            sa.Column("added_at", sa.DateTime(), nullable=False),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("channel_id"),
        )
        op.create_index(op.f("ix_honeypot_channels_guild_id"), "honeypot_channels", ["guild_id"], unique=False)

    if "honeypot_ban_reports" not in existing_tables:
        op.create_table(
            "honeypot_ban_reports",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("guild_id", sa.BigInteger(), nullable=True),
            sa.Column("user_id", sa.BigInteger(), nullable=True),
            sa.Column("username", sqlmodel.sql.sqltypes.AutoString(length=255), nullable=False),
            sa.Column("banned_at", sa.DateTime(), nullable=False),
            sa.Column("reason", sqlmodel.sql.sqltypes.AutoString(length=500), nullable=False),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(op.f("ix_honeypot_ban_reports_guild_id"), "honeypot_ban_reports", ["guild_id"], unique=False)
        op.create_index(op.f("ix_honeypot_ban_reports_user_id"), "honeypot_ban_reports", ["user_id"], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = inspector.get_table_names()

    if "honeypot_ban_reports" in existing_tables:
        op.drop_index(op.f("ix_honeypot_ban_reports_user_id"), table_name="honeypot_ban_reports")
        op.drop_index(op.f("ix_honeypot_ban_reports_guild_id"), table_name="honeypot_ban_reports")
        op.drop_table("honeypot_ban_reports")

    if "honeypot_channels" in existing_tables:
        op.drop_index(op.f("ix_honeypot_channels_guild_id"), table_name="honeypot_channels")
        op.drop_table("honeypot_channels")

    if "honeypot_settings" in existing_tables:
        op.drop_index(op.f("ix_honeypot_settings_guild_id"), table_name="honeypot_settings")
        op.drop_table("honeypot_settings")
