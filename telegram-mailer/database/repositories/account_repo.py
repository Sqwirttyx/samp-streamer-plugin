"""Account repository."""

from datetime import datetime
from typing import Optional, Sequence
from uuid import UUID

from sqlalchemy import select, update

from common.constants import AccountStatus
from database.models.account import Account
from database.repositories.base import BaseRepository


class AccountRepository(BaseRepository[Account]):
    """Repository for Account model operations."""

    model = Account

    async def get_by_user(
        self,
        user_id: UUID,
        status: Optional[AccountStatus] = None,
        offset: int = 0,
        limit: int = 100,
    ) -> Sequence[Account]:
        """
        Get accounts by user ID.

        Args:
            user_id: User UUID
            status: Filter by status (optional)
            offset: Pagination offset
            limit: Pagination limit

        Returns:
            List of accounts
        """
        query = select(Account).where(Account.user_id == user_id)

        if status:
            query = query.where(Account.status == status)

        query = query.offset(offset).limit(limit)
        result = await self.session.execute(query)
        return result.scalars().all()

    async def get_active_by_user(self, user_id: UUID) -> Sequence[Account]:
        """
        Get active and warming accounts for user.

        Args:
            user_id: User UUID

        Returns:
            List of usable accounts (active + warming_up)
        """
        result = await self.session.execute(
            select(Account)
            .where(
                Account.user_id == user_id,
                Account.status.in_([AccountStatus.ACTIVE, AccountStatus.WARMING_UP]),
            )
        )
        return result.scalars().all()

    async def get_available(self, user_id: UUID) -> Sequence[Account]:
        """
        Get available accounts (active and not in flood wait).

        Args:
            user_id: User UUID

        Returns:
            List of available accounts
        """
        now = datetime.utcnow()
        result = await self.session.execute(
            select(Account)
            .where(
                Account.user_id == user_id,
                Account.status == AccountStatus.ACTIVE,
                (Account.flood_wait_until == None) | (Account.flood_wait_until <= now),
            )
        )
        return result.scalars().all()

    async def update_status(
        self,
        account_id: UUID,
        status: AccountStatus,
    ) -> Optional[Account]:
        """
        Update account status.

        Args:
            account_id: Account UUID
            status: New status

        Returns:
            Updated account or None
        """
        await self.session.execute(
            update(Account)
            .where(Account.id == account_id)
            .values(status=status)
        )
        await self.session.flush()
        return await self.get_by_id(account_id)

    async def update_health(
        self,
        account_id: UUID,
        health_score: int,
    ) -> Optional[Account]:
        """
        Update account health score.

        Args:
            account_id: Account UUID
            health_score: New health score (0-100)

        Returns:
            Updated account or None
        """
        await self.session.execute(
            update(Account)
            .where(Account.id == account_id)
            .values(
                health_score=max(0, min(100, health_score)),
                last_health_check=datetime.utcnow(),
            )
        )
        await self.session.flush()
        return await self.get_by_id(account_id)

    async def set_flood_wait(
        self,
        account_id: UUID,
        until: datetime,
    ) -> Optional[Account]:
        """
        Set flood wait expiry time.

        Args:
            account_id: Account UUID
            until: FloodWait expiry datetime

        Returns:
            Updated account or None
        """
        await self.session.execute(
            update(Account)
            .where(Account.id == account_id)
            .values(flood_wait_until=until)
        )
        await self.session.flush()
        return await self.get_by_id(account_id)

    async def clear_flood_wait(self, account_id: UUID) -> Optional[Account]:
        """
        Clear flood wait status.

        Args:
            account_id: Account UUID

        Returns:
            Updated account or None
        """
        await self.session.execute(
            update(Account)
            .where(Account.id == account_id)
            .values(flood_wait_until=None)
        )
        await self.session.flush()
        return await self.get_by_id(account_id)

    async def bind_proxy(
        self,
        account_id: UUID,
        proxy_id: Optional[UUID],
    ) -> Optional[Account]:
        """
        Bind or unbind proxy to account.

        Args:
            account_id: Account UUID
            proxy_id: Proxy UUID or None to unbind

        Returns:
            Updated account or None
        """
        await self.session.execute(
            update(Account)
            .where(Account.id == account_id)
            .values(proxy_id=proxy_id)
        )
        await self.session.flush()
        return await self.get_by_id(account_id)

    async def increment_sent(self, account_id: UUID) -> None:
        """
        Increment sent messages counter.

        Args:
            account_id: Account UUID
        """
        await self.session.execute(
            update(Account)
            .where(Account.id == account_id)
            .values(total_sent=Account.total_sent + 1)
        )
        await self.session.flush()

    async def increment_errors(self, account_id: UUID) -> None:
        """
        Increment errors counter.

        Args:
            account_id: Account UUID
        """
        await self.session.execute(
            update(Account)
            .where(Account.id == account_id)
            .values(total_errors=Account.total_errors + 1)
        )
        await self.session.flush()

    async def count_by_user(self, user_id: UUID) -> int:
        """
        Count accounts for user.

        Args:
            user_id: User UUID

        Returns:
            Number of accounts
        """
        return await self.count(user_id=user_id)

    async def mark_banned(self, account_id: UUID) -> Optional[Account]:
        """
        Mark account as banned (spam block).

        Args:
            account_id: Account UUID

        Returns:
            Updated account or None
        """
        return await self.update_status(account_id, AccountStatus.BANNED)
