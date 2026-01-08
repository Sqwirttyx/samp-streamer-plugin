"""Base repository with common CRUD operations."""

from typing import Any, Generic, Optional, Sequence, Type, TypeVar
from uuid import UUID

from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from database.models.base import BaseModel

ModelType = TypeVar("ModelType", bound=BaseModel)


class BaseRepository(Generic[ModelType]):
    """
    Base repository providing common CRUD operations.

    All specific repositories should inherit from this class.
    """

    model: Type[ModelType]

    def __init__(self, session: AsyncSession):
        """
        Initialize repository with database session.

        Args:
            session: SQLAlchemy async session
        """
        self.session = session

    async def create(self, **kwargs: Any) -> ModelType:
        """
        Create a new record.

        Args:
            **kwargs: Model field values

        Returns:
            Created model instance
        """
        instance = self.model(**kwargs)
        self.session.add(instance)
        await self.session.flush()
        await self.session.refresh(instance)
        return instance

    async def get_by_id(self, id: UUID) -> Optional[ModelType]:
        """
        Get a record by ID.

        Args:
            id: Record UUID

        Returns:
            Model instance or None
        """
        result = await self.session.execute(
            select(self.model).where(self.model.id == id)
        )
        return result.scalar_one_or_none()

    async def get_all(
        self,
        offset: int = 0,
        limit: int = 100,
        **filters: Any,
    ) -> Sequence[ModelType]:
        """
        Get all records with optional filtering and pagination.

        Args:
            offset: Number of records to skip
            limit: Maximum number of records to return
            **filters: Field filters (field=value)

        Returns:
            List of model instances
        """
        query = select(self.model)

        for field, value in filters.items():
            if hasattr(self.model, field) and value is not None:
                query = query.where(getattr(self.model, field) == value)

        query = query.offset(offset).limit(limit)
        result = await self.session.execute(query)
        return result.scalars().all()

    async def update(self, id: UUID, **kwargs: Any) -> Optional[ModelType]:
        """
        Update a record by ID.

        Args:
            id: Record UUID
            **kwargs: Fields to update

        Returns:
            Updated model instance or None
        """
        if not kwargs:
            return await self.get_by_id(id)

        await self.session.execute(
            update(self.model)
            .where(self.model.id == id)
            .values(**kwargs)
        )
        await self.session.flush()
        return await self.get_by_id(id)

    async def delete(self, id: UUID) -> bool:
        """
        Delete a record by ID.

        Args:
            id: Record UUID

        Returns:
            True if deleted, False if not found
        """
        result = await self.session.execute(
            delete(self.model).where(self.model.id == id)
        )
        await self.session.flush()
        return result.rowcount > 0

    async def count(self, **filters: Any) -> int:
        """
        Count records with optional filtering.

        Args:
            **filters: Field filters

        Returns:
            Number of matching records
        """
        query = select(func.count(self.model.id))

        for field, value in filters.items():
            if hasattr(self.model, field) and value is not None:
                query = query.where(getattr(self.model, field) == value)

        result = await self.session.execute(query)
        return result.scalar_one()

    async def exists(self, id: UUID) -> bool:
        """
        Check if a record exists.

        Args:
            id: Record UUID

        Returns:
            True if exists, False otherwise
        """
        result = await self.session.execute(
            select(func.count(self.model.id)).where(self.model.id == id)
        )
        return result.scalar_one() > 0
