"""Account service - business logic for account management."""

from typing import Optional
from uuid import UUID

from common.constants import AccountStatus
from common.exceptions import NotFoundError, ValidationError
from common.logger import get_logger
from database import get_db_manager
from database.models import Account
from database.repositories import AccountRepository, ProxyRepository
from storage.session_storage import get_session_storage
from worker.session_manager import get_session_manager

logger = get_logger(__name__)


class AccountService:
    """
    Service for account management.

    Handles account CRUD, session validation, and status management.
    """

    def __init__(self):
        """Initialize account service."""
        self.session_storage = get_session_storage()

    async def get_by_id(
        self,
        account_id: UUID,
        user_id: Optional[UUID] = None,
    ) -> Optional[Account]:
        """
        Get account by ID.

        Args:
            account_id: Account UUID
            user_id: Owner user ID (optional, for validation)

        Returns:
            Account or None
        """
        db_manager = get_db_manager()

        async with db_manager.readonly_session() as session:
            repo = AccountRepository(session)
            account = await repo.get_by_id(account_id)

            if account and user_id and account.user_id != user_id:
                return None

            return account

    async def get_user_accounts(
        self,
        user_id: UUID,
        status: Optional[AccountStatus] = None,
    ) -> list[Account]:
        """
        Get all accounts for user.

        Args:
            user_id: User UUID
            status: Filter by status (optional)

        Returns:
            List of accounts
        """
        db_manager = get_db_manager()

        async with db_manager.readonly_session() as session:
            repo = AccountRepository(session)
            return await repo.get_by_user(user_id, status=status)

    async def add_account(
        self,
        user_id: UUID,
        session_data: bytes,
        phone: str,
    ) -> Account:
        """
        Add new account from session file.

        Args:
            user_id: Owner user ID
            session_data: Session file content
            phone: Phone number

        Returns:
            Created account

        Raises:
            ValidationError: If session is invalid
        """
        # Validate session
        if not await self._validate_session(session_data):
            raise ValidationError("Invalid session file")

        # Save session
        session_path = await self.session_storage.save_session(
            session_data=session_data,
            user_id=user_id,
            phone=phone,
        )

        db_manager = get_db_manager()

        async with db_manager.session() as session:
            repo = AccountRepository(session)

            # Check if phone already exists for user
            existing = await repo.get_by_phone_hash(user_id, phone)
            if existing:
                raise ValidationError("Account with this phone already exists")

            account = await repo.create(
                user_id=user_id,
                phone=phone,
                session_path=session_path,
            )

            logger.info(f"Account added: {account.id} for user {user_id}")
            return account

    async def delete_account(
        self,
        account_id: UUID,
        user_id: UUID,
    ) -> bool:
        """
        Delete account.

        Args:
            account_id: Account UUID
            user_id: Owner user ID

        Returns:
            True if deleted
        """
        account = await self.get_by_id(account_id, user_id)
        if not account:
            raise NotFoundError("Account not found")

        # Delete session file
        if account.session_path:
            await self.session_storage.delete_session(account.session_path)

        db_manager = get_db_manager()

        async with db_manager.session() as session:
            repo = AccountRepository(session)
            result = await repo.delete(account_id)

            if result:
                logger.info(f"Account deleted: {account_id}")

            return result

    async def bind_proxy(
        self,
        account_id: UUID,
        proxy_id: UUID,
        user_id: UUID,
    ) -> Account:
        """
        Bind proxy to account.

        Args:
            account_id: Account UUID
            proxy_id: Proxy UUID
            user_id: Owner user ID

        Returns:
            Updated account
        """
        account = await self.get_by_id(account_id, user_id)
        if not account:
            raise NotFoundError("Account not found")

        db_manager = get_db_manager()

        async with db_manager.session() as session:
            # Verify proxy belongs to user
            proxy_repo = ProxyRepository(session)
            proxy = await proxy_repo.get_by_id(proxy_id)

            if not proxy or proxy.user_id != user_id:
                raise NotFoundError("Proxy not found")

            account_repo = AccountRepository(session)
            account = await account_repo.get_by_id(account_id)
            account.proxy_id = proxy_id
            await session.flush()

            logger.info(f"Proxy {proxy_id} bound to account {account_id}")
            return account

    async def unbind_proxy(
        self,
        account_id: UUID,
        user_id: UUID,
    ) -> Account:
        """
        Unbind proxy from account.

        Args:
            account_id: Account UUID
            user_id: Owner user ID

        Returns:
            Updated account
        """
        db_manager = get_db_manager()

        async with db_manager.session() as session:
            repo = AccountRepository(session)
            account = await repo.get_by_id(account_id)

            if not account or account.user_id != user_id:
                raise NotFoundError("Account not found")

            account.proxy_id = None
            await session.flush()

            logger.info(f"Proxy unbound from account {account_id}")
            return account

    async def update_status(
        self,
        account_id: UUID,
        status: AccountStatus,
    ) -> Account:
        """
        Update account status.

        Args:
            account_id: Account UUID
            status: New status

        Returns:
            Updated account
        """
        db_manager = get_db_manager()

        async with db_manager.session() as session:
            repo = AccountRepository(session)
            account = await repo.update_status(account_id, status)

            if not account:
                raise NotFoundError("Account not found")

            logger.info(f"Account {account_id} status updated to {status}")
            return account

    async def validate_account(
        self,
        account_id: UUID,
        user_id: UUID,
    ) -> tuple[bool, str]:
        """
        Validate account session is working.

        Args:
            account_id: Account UUID
            user_id: Owner user ID

        Returns:
            Tuple of (is_valid, message)
        """
        account = await self.get_by_id(account_id, user_id)
        if not account:
            return False, "Account not found"

        # Build proxy config
        proxy = None
        if account.proxy_id:
            db_manager = get_db_manager()
            async with db_manager.readonly_session() as session:
                proxy_repo = ProxyRepository(session)
                proxy_obj = await proxy_repo.get_by_id(account.proxy_id)
                if proxy_obj:
                    proxy = {
                        "type": proxy_obj.type.value,
                        "host": proxy_obj.host,
                        "port": proxy_obj.port,
                        "username": proxy_obj.username,
                        "password": proxy_obj.password,
                    }

        # Try to connect using session manager
        session_manager = get_session_manager()
        client = None

        try:
            # Load session and connect
            client = await session_manager.load_session(user_id, account_id, proxy)

            # Validate by checking authorization
            is_valid = await session_manager.validate_session(client)

            if is_valid:
                # Update health score
                db_manager = get_db_manager()
                async with db_manager.session() as session:
                    repo = AccountRepository(session)
                    await repo.update_health(account_id, 100)

                return True, "Account is valid"
            else:
                await self.update_status(account_id, AccountStatus.ERROR)
                return False, "Session expired or invalid"

        except Exception as e:
            logger.error(f"Account validation error: {e}")
            await self.update_status(account_id, AccountStatus.ERROR)
            return False, f"Validation error: {str(e)}"

        finally:
            if client:
                await session_manager.close_session(account_id)

    async def get_active_accounts(self, user_id: UUID) -> list[Account]:
        """
        Get active accounts for user.

        Args:
            user_id: User UUID

        Returns:
            List of active accounts
        """
        return await self.get_user_accounts(user_id, status=AccountStatus.ACTIVE)

    async def get_health_status(
        self,
        account_id: UUID,
    ) -> dict:
        """
        Get account health status.

        Args:
            account_id: Account UUID

        Returns:
            Health status dictionary
        """
        db_manager = get_db_manager()

        async with db_manager.readonly_session() as session:
            repo = AccountRepository(session)
            account = await repo.get_by_id(account_id)

            if not account:
                raise NotFoundError("Account not found")

            return {
                "account_id": str(account_id),
                "health_score": account.health_score,
                "status": account.status.value,
                "last_flood_wait": (
                    account.last_flood_wait.isoformat()
                    if account.last_flood_wait
                    else None
                ),
                "is_healthy": account.health_score >= 70,
            }

    async def _validate_session(self, session_data: bytes) -> bool:
        """
        Validate session file format.

        Args:
            session_data: Session file content

        Returns:
            True if valid format
        """
        return await self.session_storage.validate_session_data(session_data)
