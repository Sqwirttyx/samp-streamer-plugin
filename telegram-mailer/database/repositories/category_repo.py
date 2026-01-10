"""Repository for ChatCategory and FolderCategory models."""

from typing import List, Optional, Sequence
from uuid import UUID

from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from database.models.category import ChatCategory, FolderCategory
from database.repositories.base import BaseRepository


class CategoryRepository(BaseRepository[ChatCategory]):
    """Repository for ChatCategory CRUD operations."""

    def __init__(self, session: AsyncSession):
        super().__init__(ChatCategory, session)

    async def get_by_slug(self, slug: str) -> Optional[ChatCategory]:
        """Get category by slug."""
        result = await self.session.execute(
            select(ChatCategory).where(ChatCategory.slug == slug)
        )
        return result.scalar_one_or_none()

    async def get_active(self) -> Sequence[ChatCategory]:
        """Get all active categories ordered by priority."""
        result = await self.session.execute(
            select(ChatCategory)
            .where(ChatCategory.is_active == True)
            .order_by(ChatCategory.priority.desc(), ChatCategory.name)
        )
        return result.scalars().all()

    async def create(
        self,
        name: str,
        slug: str,
        icon: str = "📁",
        color: str = "#808080",
        keywords: Optional[List[str]] = None,
        description: Optional[str] = None,
    ) -> ChatCategory:
        """Create new category."""
        category = ChatCategory(
            name=name,
            slug=slug,
            icon=icon,
            color=color,
            keywords=keywords or [],
            description=description,
            is_active=True,
            priority=0,
        )
        self.session.add(category)
        await self.session.flush()
        return category

    async def update_keywords(
        self,
        category_id: UUID,
        keywords: List[str],
    ) -> Optional[ChatCategory]:
        """Update category keywords."""
        category = await self.get_by_id(category_id)
        if category:
            category.keywords = keywords
            await self.session.flush()
        return category

    async def ensure_defaults(self) -> int:
        """
        Ensure default categories exist.

        Returns:
            Number of categories created
        """
        from services.categorizer import DEFAULT_CATEGORIES

        created = 0
        for slug, data in DEFAULT_CATEGORIES.items():
            existing = await self.get_by_slug(slug)
            if not existing:
                await self.create(
                    name=data["name"],
                    slug=slug,
                    icon=data.get("icon", "📁"),
                    keywords=data.get("keywords", []),
                )
                created += 1

        return created


class FolderCategoryRepository(BaseRepository[FolderCategory]):
    """Repository for FolderCategory (M:M relation) operations."""

    def __init__(self, session: AsyncSession):
        super().__init__(FolderCategory, session)

    async def get_folder_categories(
        self,
        folder_id: UUID,
    ) -> Sequence[FolderCategory]:
        """Get all categories for a folder."""
        result = await self.session.execute(
            select(FolderCategory)
            .where(FolderCategory.folder_id == str(folder_id))
            .order_by(FolderCategory.confidence.desc())
        )
        return result.scalars().all()

    async def get_folders_by_category(
        self,
        category_id: UUID,
    ) -> Sequence[FolderCategory]:
        """Get all folders with a category."""
        result = await self.session.execute(
            select(FolderCategory)
            .where(FolderCategory.category_id == str(category_id))
        )
        return result.scalars().all()

    async def assign_category(
        self,
        folder_id: UUID,
        category_id: UUID,
        confidence: float = 1.0,
        is_manual: bool = True,
    ) -> FolderCategory:
        """Assign category to folder."""
        # Check if already exists
        result = await self.session.execute(
            select(FolderCategory)
            .where(FolderCategory.folder_id == str(folder_id))
            .where(FolderCategory.category_id == str(category_id))
        )
        existing = result.scalar_one_or_none()

        if existing:
            existing.confidence = confidence
            existing.is_manual = is_manual
            await self.session.flush()
            return existing

        # Create new
        fc = FolderCategory(
            folder_id=str(folder_id),
            category_id=str(category_id),
            confidence=confidence,
            is_manual=is_manual,
        )
        self.session.add(fc)
        await self.session.flush()
        return fc

    async def remove_category(
        self,
        folder_id: UUID,
        category_id: UUID,
    ) -> bool:
        """Remove category from folder."""
        result = await self.session.execute(
            delete(FolderCategory)
            .where(FolderCategory.folder_id == str(folder_id))
            .where(FolderCategory.category_id == str(category_id))
        )
        return result.rowcount > 0

    async def clear_folder_categories(
        self,
        folder_id: UUID,
        manual_only: bool = False,
    ) -> int:
        """Clear all categories from folder."""
        query = delete(FolderCategory).where(
            FolderCategory.folder_id == str(folder_id)
        )
        if manual_only:
            query = query.where(FolderCategory.is_manual == True)

        result = await self.session.execute(query)
        return result.rowcount
