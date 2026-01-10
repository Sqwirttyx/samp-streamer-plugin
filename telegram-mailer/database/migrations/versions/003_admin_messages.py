"""Add admin_messages table for 8h window campaigns.

Revision ID: 003_admin_messages
Revises: 002_extended_accounts
Create Date: 2024-01-16 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "003_admin_messages"
down_revision: Union[str, None] = "002_extended_accounts"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create admin_messages table for 8-hour admin window campaigns
    op.create_table(
        "admin_messages",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("message_text", sa.Text(), nullable=True),
        sa.Column("message_media", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("priority", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("usage_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("target_folders", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("footer_text", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    # Create indexes
    op.create_index("ix_admin_messages_is_active", "admin_messages", ["is_active"])
    op.create_index("ix_admin_messages_priority", "admin_messages", ["priority"])


def downgrade() -> None:
    # Drop indexes
    op.drop_index("ix_admin_messages_priority", "admin_messages")
    op.drop_index("ix_admin_messages_is_active", "admin_messages")

    # Drop table
    op.drop_table("admin_messages")
