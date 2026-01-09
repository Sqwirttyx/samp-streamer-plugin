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
    # Create new enum types
    trust_level = postgresql.ENUM(
        "quarantine", "warming", "low", "medium", "high",
        name="trust_level",
        create_type=True,
    )
    warming_phase = postgresql.ENUM(
        "phase_1", "phase_2", "phase_3", "phase_4",
        name="warming_phase",
        create_type=True,
    )

    # Update account_status enum to include new values
    # Note: PostgreSQL doesn't allow easy enum modification,
    # so we drop and recreate with all values
    op.execute("ALTER TYPE account_status ADD VALUE IF NOT EXISTS 'warming_up'")
    op.execute("ALTER TYPE account_status ADD VALUE IF NOT EXISTS 'quarantine'")

    # Update proxy_status enum
    op.execute("ALTER TYPE proxy_status ADD VALUE IF NOT EXISTS 'suspicious'")

    # Add new columns to accounts table
    with op.batch_alter_table("accounts") as batch_op:
        # Telegram account data
        batch_op.add_column(
            sa.Column("telegram_id", sa.BigInteger(), nullable=True)
        )
        batch_op.add_column(
            sa.Column("phone", sa.String(20), nullable=True)
        )
        batch_op.add_column(
            sa.Column("username", sa.String(100), nullable=True)
        )
        batch_op.add_column(
            sa.Column("first_name", sa.String(200), nullable=True)
        )
        batch_op.add_column(
            sa.Column("session_string", sa.Text(), nullable=True)
        )

        # Trust score system
        batch_op.add_column(
            sa.Column("trust_score", sa.Integer(), nullable=False, server_default="10")
        )
        batch_op.add_column(
            sa.Column("trust_level", trust_level, nullable=False, server_default="quarantine")
        )
        batch_op.add_column(
            sa.Column("is_premium", sa.Boolean(), nullable=False, server_default="false")
        )

        # Warming system
        batch_op.add_column(
            sa.Column("warming_phase", warming_phase, nullable=False, server_default="phase_1")
        )
        batch_op.add_column(
            sa.Column("warming_started_at", sa.DateTime(timezone=True), nullable=True)
        )
        batch_op.add_column(
            sa.Column("last_warming_activity", sa.DateTime(timezone=True), nullable=True)
        )
        batch_op.add_column(
            sa.Column("age_days", sa.Integer(), nullable=False, server_default="0")
        )

        # Message statistics
        batch_op.add_column(
            sa.Column("messages_sent_total", sa.Integer(), nullable=False, server_default="0")
        )
        batch_op.add_column(
            sa.Column("messages_sent_today", sa.Integer(), nullable=False, server_default="0")
        )
        batch_op.add_column(
            sa.Column("successful_messages", sa.Integer(), nullable=False, server_default="0")
        )
        batch_op.add_column(
            sa.Column("last_message_time", sa.DateTime(timezone=True), nullable=True)
        )
        batch_op.add_column(
            sa.Column("organic_activity_count", sa.Integer(), nullable=False, server_default="0")
        )
        batch_op.add_column(
            sa.Column("contacts_count", sa.Integer(), nullable=False, server_default="0")
        )
        batch_op.add_column(
            sa.Column("groups_count", sa.Integer(), nullable=False, server_default="0")
        )

        # Ban and FloodWait tracking
        batch_op.add_column(
            sa.Column("total_bans", sa.Integer(), nullable=False, server_default="0")
        )
        batch_op.add_column(
            sa.Column("last_ban_date", sa.DateTime(timezone=True), nullable=True)
        )
        batch_op.add_column(
            sa.Column("days_since_last_ban", sa.Integer(), nullable=False, server_default="999")
        )
        batch_op.add_column(
            sa.Column("flood_wait_count_today", sa.Integer(), nullable=False, server_default="0")
        )
        batch_op.add_column(
            sa.Column("last_flood_wait", sa.DateTime(timezone=True), nullable=True)
        )

        # Quarantine
        batch_op.add_column(
            sa.Column("is_quarantined", sa.Boolean(), nullable=False, server_default="false")
        )
        batch_op.add_column(
            sa.Column("quarantine_reason", sa.Text(), nullable=True)
        )
        batch_op.add_column(
            sa.Column("quarantine_start", sa.DateTime(timezone=True), nullable=True)
        )

        # Device fingerprint
        batch_op.add_column(
            sa.Column("device_fingerprint", postgresql.JSONB(astext_type=sa.Text()), nullable=True)
        )

    # Create indexes
    op.create_index("ix_accounts_telegram_id", "accounts", ["telegram_id"], unique=True)
    op.create_index("ix_accounts_trust_level", "accounts", ["trust_level"])

    # Create error_logs table for tracking errors
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
    with op.batch_alter_table("accounts") as batch_op:
        batch_op.drop_column("device_fingerprint")
        batch_op.drop_column("quarantine_start")
        batch_op.drop_column("quarantine_reason")
        batch_op.drop_column("is_quarantined")
        batch_op.drop_column("last_flood_wait")
        batch_op.drop_column("flood_wait_count_today")
        batch_op.drop_column("days_since_last_ban")
        batch_op.drop_column("last_ban_date")
        batch_op.drop_column("total_bans")
        batch_op.drop_column("groups_count")
        batch_op.drop_column("contacts_count")
        batch_op.drop_column("organic_activity_count")
        batch_op.drop_column("last_message_time")
        batch_op.drop_column("successful_messages")
        batch_op.drop_column("messages_sent_today")
        batch_op.drop_column("messages_sent_total")
        batch_op.drop_column("age_days")
        batch_op.drop_column("last_warming_activity")
        batch_op.drop_column("warming_started_at")
        batch_op.drop_column("warming_phase")
        batch_op.drop_column("is_premium")
        batch_op.drop_column("trust_level")
        batch_op.drop_column("trust_score")
        batch_op.drop_column("session_string")
        batch_op.drop_column("first_name")
        batch_op.drop_column("username")
        batch_op.drop_column("phone")
        batch_op.drop_column("telegram_id")

    # Drop enum types
    op.execute("DROP TYPE IF EXISTS warming_phase")
    op.execute("DROP TYPE IF EXISTS trust_level")
