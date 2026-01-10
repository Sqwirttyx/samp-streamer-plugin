"""Error log repository."""

from datetime import datetime, timedelta
from typing import Optional, Sequence
from uuid import UUID

from sqlalchemy import delete, select

from database.models.error_log import ErrorLog
from database.repositories.base import BaseRepository


class ErrorLogRepository(BaseRepository[ErrorLog]):
    """Repository for ErrorLog model operations."""

    model = ErrorLog

    async def create_error(
        self,
        account_id: UUID,
        error_type: str,
        error_message: Optional[str] = None,
        chat_id: Optional[int] = None,
    ) -> ErrorLog:
        """
        Create a new error log entry.

        Args:
            account_id: Account UUID
            error_type: Type of error
            error_message: Detailed error message
            chat_id: Telegram chat ID where error occurred

        Returns:
            Created error log
        """
        return await self.create(
            account_id=account_id,
            error_type=error_type,
            error_message=error_message,
            chat_id=chat_id,
        )

    async def get_by_account(
        self,
        account_id: UUID,
        limit: int = 50,
    ) -> Sequence[ErrorLog]:
        """
        Get error logs for account.

        Args:
            account_id: Account UUID
            limit: Maximum number of records

        Returns:
            List of error logs
        """
        result = await self.session.execute(
            select(ErrorLog)
            .where(ErrorLog.account_id == account_id)
            .order_by(ErrorLog.created_at.desc())
            .limit(limit)
        )
        return result.scalars().all()

    async def get_recent(
        self,
        user_id: UUID,
        hours: int = 24,
        limit: int = 50,
    ) -> Sequence[ErrorLog]:
        """
        Get recent error logs for user's accounts.

        Args:
            user_id: User UUID
            hours: Number of hours to look back
            limit: Maximum number of records

        Returns:
            List of error logs
        """
        from database.models.account import Account

        since = datetime.utcnow() - timedelta(hours=hours)
        result = await self.session.execute(
            select(ErrorLog)
            .join(Account, Account.id == ErrorLog.account_id)
            .where(
                Account.user_id == user_id,
                ErrorLog.created_at >= since,
            )
            .order_by(ErrorLog.created_at.desc())
            .limit(limit)
        )
        return result.scalars().all()

    async def get_by_type(
        self,
        error_type: str,
        hours: int = 24,
        limit: int = 100,
    ) -> Sequence[ErrorLog]:
        """
        Get error logs by type.

        Args:
            error_type: Error type to filter
            hours: Number of hours to look back
            limit: Maximum number of records

        Returns:
            List of error logs
        """
        since = datetime.utcnow() - timedelta(hours=hours)
        result = await self.session.execute(
            select(ErrorLog)
            .where(
                ErrorLog.error_type == error_type,
                ErrorLog.created_at >= since,
            )
            .order_by(ErrorLog.created_at.desc())
            .limit(limit)
        )
        return result.scalars().all()

    async def count_by_type(
        self,
        account_id: UUID,
        error_type: str,
        hours: int = 24,
    ) -> int:
        """
        Count errors of specific type for account.

        Args:
            account_id: Account UUID
            error_type: Error type to count
            hours: Number of hours to look back

        Returns:
            Number of errors
        """
        since = datetime.utcnow() - timedelta(hours=hours)
        result = await self.session.execute(
            select(ErrorLog)
            .where(
                ErrorLog.account_id == account_id,
                ErrorLog.error_type == error_type,
                ErrorLog.created_at >= since,
            )
        )
        return len(result.scalars().all())

    async def cleanup_old(self, days: int = 7) -> int:
        """
        Delete old error logs.

        Args:
            days: Number of days to keep

        Returns:
            Number of deleted records
        """
        cutoff = datetime.utcnow() - timedelta(days=days)
        result = await self.session.execute(
            delete(ErrorLog).where(ErrorLog.created_at < cutoff)
        )
        await self.session.flush()
        return result.rowcount
