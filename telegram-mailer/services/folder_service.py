"""Folder service - business logic for folder management."""

from typing import Optional
from uuid import UUID

from common.exceptions import NotFoundError, ValidationError
from common.logger import get_logger
from database import get_db_manager
from database.models import Folder
from database.repositories import FolderRepository, AccountRepository
from worker.folder_parser import FolderParser

logger = get_logger(__name__)


class FolderService:
    """
    Service for folder management.

    Handles folder CRUD, parsing, and synchronization.
    """

    async def get_by_id(
        self,
        folder_id: UUID,
        user_id: Optional[UUID] = None,
    ) -> Optional[Folder]:
        """
        Get folder by ID.

        Args:
            folder_id: Folder UUID
            user_id: Owner user ID (optional, for validation)

        Returns:
            Folder or None
        """
        db_manager = get_db_manager()

        async with db_manager.readonly_session() as session:
            repo = FolderRepository(session)
            folder = await repo.get_by_id(folder_id)

            if folder and user_id and folder.user_id != user_id:
                return None

            return folder

    async def get_user_folders(self, user_id: UUID) -> list[Folder]:
        """
        Get all folders for user.

        Args:
            user_id: User UUID

        Returns:
            List of folders
        """
        db_manager = get_db_manager()

        async with db_manager.readonly_session() as session:
            repo = FolderRepository(session)
            return await repo.get_by_user(user_id)

    async def add_folder(
        self,
        user_id: UUID,
        folder_link: str,
        name: Optional[str] = None,
    ) -> Folder:
        """
        Add new folder from link.

        Args:
            user_id: Owner user ID
            folder_link: Telegram folder link
            name: Optional name

        Returns:
            Created folder

        Raises:
            ValidationError: If folder link is invalid
        """
        # Validate folder link format
        if not self._validate_folder_link(folder_link):
            raise ValidationError("Invalid folder link format")

        db_manager = get_db_manager()

        async with db_manager.session() as session:
            repo = FolderRepository(session)

            # Check for duplicates
            existing = await repo.get_by_link(user_id, folder_link)
            if existing:
                raise ValidationError("Folder already exists")

            folder = await repo.create(
                user_id=user_id,
                folder_link=folder_link,
                name=name,
            )

            logger.info(f"Folder added: {folder.id} for user {user_id}")
            return folder

    async def delete_folder(
        self,
        folder_id: UUID,
        user_id: UUID,
    ) -> bool:
        """
        Delete folder.

        Args:
            folder_id: Folder UUID
            user_id: Owner user ID

        Returns:
            True if deleted
        """
        folder = await self.get_by_id(folder_id, user_id)
        if not folder:
            raise NotFoundError("Folder not found")

        db_manager = get_db_manager()

        async with db_manager.session() as session:
            repo = FolderRepository(session)
            result = await repo.delete(folder_id)

            if result:
                logger.info(f"Folder deleted: {folder_id}")

            return result

    async def sync_folder(
        self,
        folder_id: UUID,
        user_id: UUID,
        account_id: UUID,
    ) -> tuple[int, str]:
        """
        Sync folder - parse chats from Telegram.

        Args:
            folder_id: Folder UUID
            user_id: Owner user ID
            account_id: Account to use for parsing

        Returns:
            Tuple of (chat_count, message)
        """
        folder = await self.get_by_id(folder_id, user_id)
        if not folder:
            raise NotFoundError("Folder not found")

        # Get account
        db_manager = get_db_manager()

        async with db_manager.readonly_session() as session:
            account_repo = AccountRepository(session)
            account = await account_repo.get_by_id(account_id)

            if not account or account.user_id != user_id:
                raise NotFoundError("Account not found")

        # Build proxy config
        proxy = None
        if account.proxy:
            proxy = {
                "type": account.proxy.type.value,
                "host": account.proxy.host,
                "port": account.proxy.port,
                "username": account.proxy.username,
                "password": account.proxy.password,
            }

        # Parse folder
        parser = FolderParser()
        try:
            chat_ids = await parser.parse_folder(
                folder_link=folder.folder_link,
                session_path=account.session_path,
                proxy=proxy,
            )

            if not chat_ids:
                return 0, "No chats found in folder"

            # Update folder with chat IDs
            async with db_manager.session() as session:
                repo = FolderRepository(session)
                await repo.update_chat_ids(folder_id, chat_ids)

            logger.info(f"Folder {folder_id} synced: {len(chat_ids)} chats")
            return len(chat_ids), f"Found {len(chat_ids)} chats"

        except Exception as e:
            logger.error(f"Folder sync error: {e}")
            return 0, f"Sync error: {str(e)}"

    async def bind_account(
        self,
        folder_id: UUID,
        account_id: UUID,
        user_id: UUID,
    ) -> Folder:
        """
        Bind account to folder.

        Args:
            folder_id: Folder UUID
            account_id: Account UUID
            user_id: Owner user ID

        Returns:
            Updated folder
        """
        folder = await self.get_by_id(folder_id, user_id)
        if not folder:
            raise NotFoundError("Folder not found")

        db_manager = get_db_manager()

        async with db_manager.session() as session:
            # Verify account belongs to user
            account_repo = AccountRepository(session)
            account = await account_repo.get_by_id(account_id)

            if not account or account.user_id != user_id:
                raise NotFoundError("Account not found")

            folder_repo = FolderRepository(session)
            folder = await folder_repo.get_by_id(folder_id)
            folder.account_id = account_id
            await session.flush()

            logger.info(f"Account {account_id} bound to folder {folder_id}")
            return folder

    async def unbind_account(
        self,
        folder_id: UUID,
        user_id: UUID,
    ) -> Folder:
        """
        Unbind account from folder.

        Args:
            folder_id: Folder UUID
            user_id: Owner user ID

        Returns:
            Updated folder
        """
        db_manager = get_db_manager()

        async with db_manager.session() as session:
            repo = FolderRepository(session)
            folder = await repo.get_by_id(folder_id)

            if not folder or folder.user_id != user_id:
                raise NotFoundError("Folder not found")

            folder.account_id = None
            await session.flush()

            logger.info(f"Account unbound from folder {folder_id}")
            return folder

    async def get_chat_count(self, folder_id: UUID) -> int:
        """
        Get number of chats in folder.

        Args:
            folder_id: Folder UUID

        Returns:
            Chat count
        """
        db_manager = get_db_manager()

        async with db_manager.readonly_session() as session:
            repo = FolderRepository(session)
            folder = await repo.get_by_id(folder_id)

            if not folder:
                return 0

            return len(folder.chat_ids or [])

    async def get_folders_with_account(
        self,
        user_id: UUID,
        account_id: UUID,
    ) -> list[Folder]:
        """
        Get folders bound to specific account.

        Args:
            user_id: User UUID
            account_id: Account UUID

        Returns:
            List of folders
        """
        db_manager = get_db_manager()

        async with db_manager.readonly_session() as session:
            repo = FolderRepository(session)
            return await repo.get_by_account(user_id, account_id)

    def _validate_folder_link(self, folder_link: str) -> bool:
        """
        Validate folder link format.

        Args:
            folder_link: Folder link string

        Returns:
            True if valid
        """
        # Expected format: https://t.me/addlist/XXXX or t.me/addlist/XXXX
        if not folder_link:
            return False

        folder_link = folder_link.strip().lower()

        if "t.me/addlist/" in folder_link:
            return True

        # Also accept folder hash directly
        if len(folder_link) > 5 and folder_link.isalnum():
            return True

        return False

    def format_folder(self, folder: Folder) -> str:
        """
        Format folder for display.

        Args:
            folder: Folder model

        Returns:
            Formatted string
        """
        chat_count = len(folder.chat_ids or [])
        name = folder.name or "Без имени"

        return f"📁 {name} ({chat_count} чатов)"
