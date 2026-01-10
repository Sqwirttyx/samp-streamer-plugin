"""Add spintax and targeting support.

Revision ID: 004_spintax_targeting
Revises: 003_admin_messages
Create Date: 2024-01-17 00:00:00.000000

This migration adds:
- ChatCategory table for categorizing folders/chats
- FolderCategory table for M:M relation
- Updates admin_messages to replace target_folders with target_categories
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "004_spintax_targeting"
down_revision: Union[str, None] = "003_admin_messages"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create chat_categories table
    op.create_table(
        "chat_categories",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("slug", sa.String(50), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("keywords", postgresql.ARRAY(sa.String()), nullable=True),
        sa.Column("icon", sa.String(10), nullable=False, server_default="📁"),
        sa.Column("color", sa.String(7), nullable=False, server_default="#808080"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("priority", sa.Integer(), nullable=False, server_default="0"),
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
    op.create_index("ix_chat_categories_slug", "chat_categories", ["slug"], unique=True)
    op.create_index("ix_chat_categories_is_active", "chat_categories", ["is_active"])

    # Create folder_categories table (M:M relation)
    op.create_table(
        "folder_categories",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("folder_id", sa.String(36), nullable=False),
        sa.Column("category_id", sa.String(36), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False, server_default="1.0"),
        sa.Column("is_manual", sa.Boolean(), nullable=False, server_default="false"),
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
    op.create_index("ix_folder_categories_folder_id", "folder_categories", ["folder_id"])
    op.create_index("ix_folder_categories_category_id", "folder_categories", ["category_id"])

    # Update admin_messages: replace target_folders (JSONB) with target_categories (ARRAY)
    # First drop the old column if exists
    try:
        op.drop_column("admin_messages", "target_folders")
    except Exception:
        pass  # Column might not exist

    # Add new target_categories column
    op.add_column(
        "admin_messages",
        sa.Column("target_categories", postgresql.ARRAY(sa.String()), nullable=True),
    )

    # Insert default categories
    op.execute("""
        INSERT INTO chat_categories (name, slug, icon, keywords, priority) VALUES
        ('Крипто', 'crypto', '💰', ARRAY['bitcoin', 'btc', 'crypto', 'крипто', 'биткоин', 'ethereum', 'eth', 'blockchain', 'defi', 'nft', 'binance'], 10),
        ('Бизнес', 'business', '💼', ARRAY['бизнес', 'business', 'заработок', 'деньги', 'инвестиц', 'доход', 'прибыль', 'стартап', 'млм'], 9),
        ('Знакомства', 'dating', '💕', ARRAY['знакомств', 'dating', 'девушк', 'парн', 'отношени', 'любов', 'романтик', 'флирт'], 8),
        ('Гемблинг', 'gambling', '🎰', ARRAY['казино', 'casino', 'ставки', 'betting', 'слот', 'покер', 'рулетка', '1xbet', '1win'], 7),
        ('Обучение', 'education', '📚', ARRAY['обучение', 'курс', 'урок', 'школа', 'вебинар', 'тренинг', 'мастер-класс'], 6),
        ('Маркетинг', 'marketing', '📢', ARRAY['маркетинг', 'реклама', 'smm', 'seo', 'таргет', 'продвижени', 'трафик'], 5),
        ('IT/Технологии', 'tech', '💻', ARRAY['программ', 'разработ', 'код', 'python', 'javascript', 'it', 'софт', 'веб'], 4),
        ('Новости', 'news', '📰', ARRAY['новост', 'news', 'события', 'политик', 'экономик', 'обзор'], 3),
        ('Развлечения', 'entertainment', '🎬', ARRAY['мем', 'юмор', 'приколы', 'фильм', 'музык', 'игр', 'аним', 'видео'], 2),
        ('Здоровье', 'health', '🏥', ARRAY['здоров', 'фитнес', 'спорт', 'похуд', 'питани', 'йога', 'медицин'], 1)
        ON CONFLICT DO NOTHING
    """)


def downgrade() -> None:
    # Drop target_categories from admin_messages
    op.drop_column("admin_messages", "target_categories")

    # Re-add target_folders
    op.add_column(
        "admin_messages",
        sa.Column("target_folders", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )

    # Drop folder_categories indexes and table
    op.drop_index("ix_folder_categories_category_id", "folder_categories")
    op.drop_index("ix_folder_categories_folder_id", "folder_categories")
    op.drop_table("folder_categories")

    # Drop chat_categories indexes and table
    op.drop_index("ix_chat_categories_is_active", "chat_categories")
    op.drop_index("ix_chat_categories_slug", "chat_categories")
    op.drop_table("chat_categories")
