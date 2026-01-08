"""Initial migration - create all tables.

Revision ID: 001_initial
Revises:
Create Date: 2024-01-01 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create enum types
    account_status = postgresql.ENUM(
        "active", "paused", "banned", "error",
        name="account_status",
        create_type=True,
    )
    proxy_type = postgresql.ENUM(
        "socks5", "http", "mtproxy",
        name="proxy_type",
        create_type=True,
    )
    proxy_status = postgresql.ENUM(
        "active", "checking", "dead",
        name="proxy_status",
        create_type=True,
    )
    folder_status = postgresql.ENUM(
        "active", "syncing", "error",
        name="folder_status",
        create_type=True,
    )
    campaign_status = postgresql.ENUM(
        "draft", "scheduled", "active", "paused", "completed", "error",
        name="campaign_status",
        create_type=True,
    )

    # Create users table
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("telegram_id", sa.BigInteger(), nullable=False),
        sa.Column("username", sa.String(255), nullable=True),
        sa.Column("invite_key", sa.String(64), nullable=True),
        sa.Column("is_admin", sa.Boolean(), nullable=False, default=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, default=True),
        sa.Column("settings", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("telegram_id"),
    )
    op.create_index("ix_users_telegram_id", "users", ["telegram_id"])

    # Create proxies table
    op.create_table(
        "proxies",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("type", proxy_type, nullable=False),
        sa.Column("host", sa.String(255), nullable=False),
        sa.Column("port", sa.Integer(), nullable=False),
        sa.Column("username", sa.String(255), nullable=True),
        sa.Column("password", sa.String(255), nullable=True),
        sa.Column("status", proxy_status, nullable=False, default="active"),
        sa.Column("last_check", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_proxies_user_id", "proxies", ["user_id"])

    # Create accounts table
    op.create_table(
        "accounts",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("phone_hash", sa.String(64), nullable=False),
        sa.Column("session_path", sa.String(512), nullable=False),
        sa.Column("proxy_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("status", account_status, nullable=False, default="active"),
        sa.Column("health_score", sa.Integer(), nullable=False, default=100),
        sa.Column("last_health_check", sa.DateTime(timezone=True), nullable=True),
        sa.Column("flood_wait_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("total_sent", sa.Integer(), nullable=False, default=0),
        sa.Column("total_errors", sa.Integer(), nullable=False, default=0),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["proxy_id"], ["proxies.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_accounts_user_id", "accounts", ["user_id"])
    op.create_index("ix_accounts_status", "accounts", ["status"])

    # Create folders table
    op.create_table(
        "folders",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("account_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("folder_link", sa.String(512), nullable=False),
        sa.Column("folder_id", sa.Integer(), nullable=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("chat_count", sa.Integer(), nullable=False, default=0),
        sa.Column("chat_ids", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("last_sync", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", folder_status, nullable=False, default="active"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["account_id"], ["accounts.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_folders_user_id", "folders", ["user_id"])

    # Create campaigns table
    op.create_table(
        "campaigns",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("account_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("folder_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("message_text", sa.Text(), nullable=True),
        sa.Column("message_media", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("interval_min", sa.Integer(), nullable=False, default=25),
        sa.Column("interval_max", sa.Integer(), nullable=False, default=45),
        sa.Column("work_hours", sa.Integer(), nullable=False, default=4),
        sa.Column("rest_minutes", sa.Integer(), nullable=False, default=30),
        sa.Column("is_admin_campaign", sa.Boolean(), nullable=False, default=False),
        sa.Column("admin_footer", sa.Text(), nullable=True),
        sa.Column("status", campaign_status, nullable=False, default="draft"),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["account_id"], ["accounts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["folder_id"], ["folders.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_campaigns_user_id", "campaigns", ["user_id"])
    op.create_index("ix_campaigns_account_id", "campaigns", ["account_id"])
    op.create_index("ix_campaigns_status", "campaigns", ["status"])

    # Create campaign_progress table
    op.create_table(
        "campaign_progress",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("campaign_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("current_chat_index", sa.Integer(), nullable=False, default=0),
        sa.Column("cycle_count", sa.Integer(), nullable=False, default=0),
        sa.Column("last_sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("next_send_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["campaign_id"], ["campaigns.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("campaign_id"),
    )

    # Create stats_hourly table
    op.create_table(
        "stats_hourly",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("campaign_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("account_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("hour", sa.DateTime(timezone=True), nullable=False),
        sa.Column("sent_count", sa.Integer(), nullable=False, default=0),
        sa.Column("error_count", sa.Integer(), nullable=False, default=0),
        sa.Column("flood_wait_count", sa.Integer(), nullable=False, default=0),
        sa.Column("spam_block", sa.Boolean(), nullable=False, default=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["campaign_id"], ["campaigns.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["account_id"], ["accounts.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_stats_hourly_campaign_id", "stats_hourly", ["campaign_id"])
    op.create_index("ix_stats_hourly_account_id", "stats_hourly", ["account_id"])
    op.create_index("ix_stats_hourly_hour", "stats_hourly", ["hour"])

    # Create invite_keys table
    op.create_table(
        "invite_keys",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("key", sa.String(64), nullable=False),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("used_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("max_uses", sa.Integer(), nullable=False, default=1),
        sa.Column("current_uses", sa.Integer(), nullable=False, default=0),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["used_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("key"),
    )
    op.create_index("ix_invite_keys_key", "invite_keys", ["key"])


def downgrade() -> None:
    # Drop tables in reverse order
    op.drop_table("invite_keys")
    op.drop_table("stats_hourly")
    op.drop_table("campaign_progress")
    op.drop_table("campaigns")
    op.drop_table("folders")
    op.drop_table("accounts")
    op.drop_table("proxies")
    op.drop_table("users")

    # Drop enum types
    op.execute("DROP TYPE IF EXISTS campaign_status")
    op.execute("DROP TYPE IF EXISTS folder_status")
    op.execute("DROP TYPE IF EXISTS proxy_status")
    op.execute("DROP TYPE IF EXISTS proxy_type")
    op.execute("DROP TYPE IF EXISTS account_status")
