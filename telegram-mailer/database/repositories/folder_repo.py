"""Folder repository."""

from datetime import datetime
from typing import Optional, Sequence
from uuid import UUID

from sqlalchemy import select, update

from common.constants import FolderStatus
from database.models.folder import Folder
from database.repositories.base import BaseRepository


class FolderRepository(BaseRepository[Folder]):
    """Repository for Folder model operations."""

    model = Folder

    async def get_by_user(
        self,
        user_id: UUID,
        status: Optional[FolderStatus] = None,
        offset: int = 0,
        limit: int = 100,
    ) -> Sequence[Folder]:
        """
        Get folders by user ID.

        Args:
            user_id: User UUID
            status: Filter by status (optional)
            offset: Pagination offset
            limit: Pagination limit

        Returns:
            List of folders
        """
        query = select(Folder).where(Folder.user_id == user_id)

        if status:
            query = query.where(Folder.status == status)

        query = query.offset(offset).limit(limit)
        result = await self.session.execute(query)
        return result.scalars().all()

    async def get_by_account(self, account_id: UUID) -> Sequence[Folder]:
        """
        Get folders bound to account.

        Args:
            account_id: Account UUID

        Returns:
            List of folders
        """
        result = await self.session.execute(
            select(Folder).where(Folder.account_id == account_id)
        )
        return result.scalars().all()

    async def get_unbound(self, user_id: UUID) -> Sequence[Folder]:
        """
        Get folders not bound to any account.

        Args:
            user_id: User UUID

        Returns:
            List of unbound folders
        """
        result = await self.session.execute(
            select(Folder)
            .where(
                Folder.user_id == user_id,
                Folder.account_id == None,
                Folder.status == FolderStatus.ACTIVE,
            )
        )
        return result.scalars().all()

    async def create_folder(
        self,
        user_id: UUID,
        folder_link: str,
        name: str,
        account_id: Optional[UUID] = None,
    ) -> Folder:
        """
        Create a new folder.

        Args:
            user_id: User UUID
            folder_link: Folder invite link
            name: Folder name
            account_id: Bound account ID (optional)

        Returns:
            Created folder instance
        """
        return await self.create(
            user_id=user_id,
            folder_link=folder_link,
            name=name,
            account_id=account_id,
            status=FolderStatus.ACTIVE,
            chat_count=0,
            chat_ids=[],
        )

    async def bind_to_account(
        self,
        folder_id: UUID,
        account_id: Optional[UUID],
    ) -> Optional[Folder]:
        """
        Bind folder to account or unbind.

        Args:
            folder_id: Folder UUID
            account_id: Account UUID or None to unbind

        Returns:
            Updated folder or None
        """
        await self.session.execute(
            update(Folder)
            .where(Folder.id == folder_id)
            .values(account_id=account_id)
        )
        await self.session.flush()
        return await self.get_by_id(folder_id)

    async def update_sync_data(
        self,
        folder_id: UUID,
        folder_telegram_id: int,
        chat_ids: list[int],
    ) -> Optional[Folder]:
        """
        Update folder sync data.

        Args:
            folder_id: Folder UUID
            folder_telegram_id: Telegram folder ID
            chat_ids: List of chat IDs

        Returns:
            Updated folder or None
        """
        await self.session.execute(
            update(Folder)
            .where(Folder.id == folder_id)
            .values(
                folder_id=folder_telegram_id,
                chat_ids=chat_ids,
                chat_count=len(chat_ids),
                last_sync=datetime.utcnow(),
                status=FolderStatus.ACTIVE,
            )
        )
        await self.session.flush()
        return await self.get_by_id(folder_id)

    async def update_status(
        self,
        folder_id: UUID,
        status: FolderStatus,
    ) -> Optional[Folder]:
        """
        Update folder status.

        Args:
            folder_id: Folder UUID
            status: New status

        Returns:
            Updated folder or None
        """
        await self.session.execute(
            update(Folder)
            .where(Folder.id == folder_id)
            .values(status=status)
        )
        await self.session.flush()
        return await self.get_by_id(folder_id)

    async def set_syncing(self, folder_id: UUID) -> Optional[Folder]:
        """
        Set folder status to syncing.

        Args:
            folder_id: Folder UUID

        Returns:
            Updated folder or None
        """
        return await self.update_status(folder_id, FolderStatus.SYNCING)

    async def set_error(self, folder_id: UUID) -> Optional[Folder]:
        """
        Set folder status to error.

        Args:
            folder_id: Folder UUID

        Returns:
            Updated folder or None
        """
        return await self.update_status(folder_id, FolderStatus.ERROR)

    async def count_by_user(self, user_id: UUID) -> int:
        """
        Count folders for user.

        Args:
            user_id: User UUID

        Returns:
            Number of folders
        """
        return await self.count(user_id=user_id)

    async def get_synced(self, user_id: UUID) -> Sequence[Folder]:
        """
        Get synced folders (with chat list).

        Args:
            user_id: User UUID

        Returns:
            List of synced folders
        """
        result = await self.session.execute(
            select(Folder)
            .where(
                Folder.user_id == user_id,
                Folder.status == FolderStatus.ACTIVE,
                Folder.chat_ids != None,
                Folder.chat_count > 0,
            )
        )
        return result.scalars().all()
