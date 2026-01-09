"""Extended account model with trust scoring and warming.

Revision ID: 002_extended_accounts
Revises: 001_initial
Create Date: 2024-01-15 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "002_extended_accounts"
down_revision: Union[str, None] = "001_initial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Update account_status enum to include new values
    op.execute("ALTER TYPE account_status ADD VALUE IF NOT EXISTS 'warming_up'")
    op.execute("ALTER TYPE account_status ADD VALUE IF NOT EXISTS 'quarantine'")

    # Update proxy_status enum
    op.execute("ALTER TYPE proxy_status ADD VALUE IF NOT EXISTS 'suspicious'")

    # Create new enum types FIRST (before using them)
    op.execute("CREATE TYPE trust_level AS ENUM ('quarantine', 'warming', 'low', 'medium', 'high')")
    op.execute("CREATE TYPE warming_phase AS ENUM ('phase_1', 'phase_2', 'phase_3', 'phase_4')")

    # Add new columns to accounts table (without batch mode for PostgreSQL)
    # Telegram account data
    op.add_column("accounts", sa.Column("telegram_id", sa.BigInteger(), nullable=True))
    op.add_column("accounts", sa.Column("phone", sa.String(20), nullable=True))
    op.add_column("accounts", sa.Column("username", sa.String(100), nullable=True))
    op.add_column("accounts", sa.Column("first_name", sa.String(200), nullable=True))
    op.add_column("accounts", sa.Column("session_string", sa.Text(), nullable=True))

    # Trust score system
    op.add_column("accounts", sa.Column("trust_score", sa.Integer(), nullable=False, server_default="10"))
    op.add_column("accounts", sa.Column(
        "trust_level",
        sa.Enum('quarantine', 'warming', 'low', 'medium', 'high', name='trust_level', create_type=False),
        nullable=False,
        server_default="quarantine"
    ))
    op.add_column("accounts", sa.Column("is_premium", sa.Boolean(), nullable=False, server_default="false"))

    # Warming system
    op.add_column("accounts", sa.Column(
        "warming_phase",
        sa.Enum('phase_1', 'phase_2', 'phase_3', 'phase_4', name='warming_phase', create_type=False),
        nullable=False,
        server_default="phase_1"
    ))
    op.add_column("accounts", sa.Column("warming_started_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("accounts", sa.Column("last_warming_activity", sa.DateTime(timezone=True), nullable=True))
    op.add_column("accounts", sa.Column("age_days", sa.Integer(), nullable=False, server_default="0"))

    # Message statistics
    op.add_column("accounts", sa.Column("messages_sent_total", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("accounts", sa.Column("messages_sent_today", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("accounts", sa.Column("successful_messages", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("accounts", sa.Column("last_message_time", sa.DateTime(timezone=True), nullable=True))
    op.add_column("accounts", sa.Column("organic_activity_count", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("accounts", sa.Column("contacts_count", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("accounts", sa.Column("groups_count", sa.Integer(), nullable=False, server_default="0"))

    # Ban and FloodWait tracking
    op.add_column("accounts", sa.Column("total_bans", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("accounts", sa.Column("last_ban_date", sa.DateTime(timezone=True), nullable=True))
    op.add_column("accounts", sa.Column("days_since_last_ban", sa.Integer(), nullable=False, server_default="999"))
    op.add_column("accounts", sa.Column("flood_wait_count_today", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("accounts", sa.Column("last_flood_wait", sa.DateTime(timezone=True), nullable=True))

    # Quarantine
    op.add_column("accounts", sa.Column("is_quarantined", sa.Boolean(), nullable=False, server_default="false"))
    op.add_column("accounts", sa.Column("quarantine_reason", sa.Text(), nullable=True))
    op.add_column("accounts", sa.Column("quarantine_start", sa.DateTime(timezone=True), nullable=True))

    # Device fingerprint
    op.add_column("accounts", sa.Column("device_fingerprint", postgresql.JSONB(astext_type=sa.Text()), nullable=True))

    # Create indexes
    op.create_index("ix_accounts_telegram_id", "accounts", ["telegram_id"], unique=True)
    op.create_index("ix_accounts_trust_level", "accounts", ["trust_level"])

    # Create error_logs table
    op.create_table(
        "error_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("account_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("chat_id", sa.BigInteger(), nullable=True),
        sa.Column("error_type", sa.String(100), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["account_id"], ["accounts.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_error_logs_account_id", "error_logs", ["account_id"])
    op.create_index("ix_error_logs_error_type", "error_logs", ["error_type"])
    op.create_index("ix_error_logs_created_at", "error_logs", ["created_at"])

    # Create trust_score_history table
    op.create_table(
        "trust_score_history",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("account_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("old_score", sa.Integer(), nullable=False),
        sa.Column("new_score", sa.Integer(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["account_id"], ["accounts.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_trust_score_history_account_id", "trust_score_history", ["account_id"])

    # Create chat_status_cache table
    op.create_table(
        "chat_status_cache",
        sa.Column("chat_id", sa.BigInteger(), nullable=False),
        sa.Column("chat_username", sa.String(100), nullable=True),
        sa.Column("is_available", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("last_checked", sa.DateTime(timezone=True), nullable=True),
        sa.Column("unavailable_for_accounts", postgresql.ARRAY(postgresql.UUID(as_uuid=True)), nullable=True),
        sa.PrimaryKeyConstraint("chat_id"),
    )


def downgrade() -> None:
    # Drop new tables
    op.drop_table("chat_status_cache")
    op.drop_table("trust_score_history")
    op.drop_table("error_logs")

    # Drop indexes
    op.drop_index("ix_accounts_trust_level", "accounts")
    op.drop_index("ix_accounts_telegram_id", "accounts")

    # Drop new columns from accounts
    op.drop_column("accounts", "device_fingerprint")
    op.drop_column("accounts", "quarantine_start")
    op.drop_column("accounts", "quarantine_reason")
    op.drop_column("accounts", "is_quarantined")
    op.drop_column("accounts", "last_flood_wait")
    op.drop_column("accounts", "flood_wait_count_today")
    op.drop_column("accounts", "days_since_last_ban")
    op.drop_column("accounts", "last_ban_date")
    op.drop_column("accounts", "total_bans")
    op.drop_column("accounts", "groups_count")
    op.drop_column("accounts", "contacts_count")
    op.drop_column("accounts", "organic_activity_count")
    op.drop_column("accounts", "last_message_time")
    op.drop_column("accounts", "successful_messages")
    op.drop_column("accounts", "messages_sent_today")
    op.drop_column("accounts", "messages_sent_total")
    op.drop_column("accounts", "age_days")
    op.drop_column("accounts", "last_warming_activity")
    op.drop_column("accounts", "warming_started_at")
    op.drop_column("accounts", "warming_phase")
    op.drop_column("accounts", "is_premium")
    op.drop_column("accounts", "trust_level")
    op.drop_column("accounts", "trust_score")
    op.drop_column("accounts", "session_string")
    op.drop_column("accounts", "first_name")
    op.drop_column("accounts", "username")
    op.drop_column("accounts", "phone")
    op.drop_column("accounts", "telegram_id")

    # Drop enum types
    op.execute("DROP TYPE IF EXISTS warming_phase")
    op.execute("DROP TYPE IF EXISTS trust_level")
