"""Database connection management using SQLAlchemy with asyncpg."""

from contextlib import asynccontextmanager
from typing import AsyncGenerator, Optional

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.pool import NullPool

from common.logger import get_logger

logger = get_logger(__name__)


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy models."""

    pass


class DatabaseManager:
    """
    Database connection manager.

    Handles async engine and session creation for PostgreSQL with asyncpg.
    """

    def __init__(
        self,
        database_url: str,
        echo: bool = False,
        pool_size: int = 10,
        max_overflow: int = 20,
    ):
        """
        Initialize database manager.

        Args:
            database_url: PostgreSQL connection URL
            echo: Echo SQL queries to stdout
            pool_size: Connection pool size
            max_overflow: Max overflow connections
        """
        self._database_url = database_url
        self._echo = echo
        self._pool_size = pool_size
        self._max_overflow = max_overflow
        self._engine: Optional[AsyncEngine] = None
        self._session_factory: Optional[async_sessionmaker[AsyncSession]] = None

    @property
    def engine(self) -> AsyncEngine:
        """Get the async engine, creating if necessary."""
        if self._engine is None:
            self._engine = create_async_engine(
                self._database_url,
                echo=self._echo,
                pool_size=self._pool_size,
                max_overflow=self._max_overflow,
                pool_pre_ping=True,
                pool_recycle=3600,
            )
            logger.info("Database engine created")
        return self._engine

    @property
    def session_factory(self) -> async_sessionmaker[AsyncSession]:
        """Get the session factory, creating if necessary."""
        if self._session_factory is None:
            self._session_factory = async_sessionmaker(
                bind=self.engine,
                class_=AsyncSession,
                expire_on_commit=False,
                autocommit=False,
                autoflush=False,
            )
        return self._session_factory

    async def init(self) -> None:
        """Initialize database connection and create tables."""
        logger.info("Initializing database connection")
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("Database initialized successfully")

    async def close(self) -> None:
        """Close database connection."""
        if self._engine is not None:
            await self._engine.dispose()
            self._engine = None
            self._session_factory = None
            logger.info("Database connection closed")

    @asynccontextmanager
    async def session(self) -> AsyncGenerator[AsyncSession, None]:
        """
        Get a database session context manager.

        Yields:
            AsyncSession: Database session

        Example:
            async with db_manager.session() as session:
                result = await session.execute(query)
        """
        session = self.session_factory()
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()

    @asynccontextmanager
    async def readonly_session(self) -> AsyncGenerator[AsyncSession, None]:
        """
        Get a read-only database session (no commit on exit).

        Yields:
            AsyncSession: Read-only database session
        """
        session = self.session_factory()
        try:
            yield session
        finally:
            await session.close()


# Global database manager instance
_db_manager: Optional[DatabaseManager] = None


def get_db_manager() -> DatabaseManager:
    """Get the global database manager instance."""
    global _db_manager
    if _db_manager is None:
        from common.config import settings

        _db_manager = DatabaseManager(
            database_url=settings.database_url,
            echo=settings.database_echo,
        )
    return _db_manager


async def init_db() -> None:
    """Initialize the global database connection."""
    manager = get_db_manager()
    await manager.init()


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Dependency for getting database sessions.

    Yields:
        AsyncSession: Database session
    """
    manager = get_db_manager()
    async with manager.session() as session:
        yield session


def create_test_engine(database_url: str) -> AsyncEngine:
    """
    Create a test engine with NullPool for testing.

    Args:
        database_url: Test database URL

    Returns:
        AsyncEngine: Test engine
    """
    return create_async_engine(
        database_url,
        echo=True,
        poolclass=NullPool,
    )
