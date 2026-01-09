"""Account authorization manager - auth by code instead of .session files."""

import asyncio
import time
from datetime import datetime
from typing import Dict, Optional
from uuid import UUID

from telethon import TelegramClient
from telethon.errors import (
    PhoneCodeExpiredError,
    PhoneCodeInvalidError,
    PhoneNumberBannedError,
    PhoneNumberFloodError,
    SessionPasswordNeededError,
    FloodWaitError,
)
from telethon.sessions import StringSession

from common.logger import get_logger
from services.auth.fingerprint import DeviceFingerprint

logger = get_logger(__name__)


class PendingAuth:
    """Pending authorization data."""

    def __init__(
        self,
        phone: str,
        client: TelegramClient,
        phone_code_hash: str,
        api_id: int,
        api_hash: str,
    ):
        self.phone = phone
        self.client = client
        self.phone_code_hash = phone_code_hash
        self.api_id = api_id
        self.api_hash = api_hash
        self.attempts = 0
        self.created_at = time.time()
        self.fingerprint = DeviceFingerprint.generate()

    @property
    def is_expired(self) -> bool:
        """Check if auth session is expired (5 minutes)."""
        return time.time() - self.created_at > 300


class AccountAuthManager:
    """
    Account authorization manager.

    Handles authorization flow:
    1. Send code request
    2. Verify code
    3. Handle 2FA if needed
    4. Save session

    Usage:
        manager = AccountAuthManager(api_id, api_hash)

        # Step 1: Request code
        result = await manager.start_auth(user_id, "+79001234567")

        # Step 2: Verify code
        result = await manager.verify_code(user_id, "12345")

        # Step 3: If 2FA needed
        if result['status'] == 'need_2fa':
            result = await manager.verify_2fa(user_id, "password")
    """

    def __init__(self, api_id: int, api_hash: str, sessions_path: str = "sessions"):
        """
        Initialize auth manager.

        Args:
            api_id: Telegram API ID
            api_hash: Telegram API Hash
            sessions_path: Path to store sessions
        """
        self.api_id = api_id
        self.api_hash = api_hash
        self.sessions_path = sessions_path
        self.pending_auths: Dict[int, PendingAuth] = {}

    async def start_auth(self, user_id: int, phone: str) -> dict:
        """
        Step 1: Start authorization - request code.

        Args:
            user_id: Bot user ID (owner)
            phone: Phone number in international format

        Returns:
            Result dict with status
        """
        # Clean up expired sessions
        await self._cleanup_expired()

        # Check if already pending
        if user_id in self.pending_auths:
            existing = self.pending_auths[user_id]
            if not existing.is_expired:
                return {
                    "status": "already_pending",
                    "message": f"Code already sent to {existing.phone}",
                    "phone": existing.phone,
                }
            else:
                await self._cleanup_auth(user_id)

        # Generate device fingerprint
        fingerprint = DeviceFingerprint.generate()

        # Create client with fingerprint
        client = TelegramClient(
            StringSession(),
            self.api_id,
            self.api_hash,
            device_model=fingerprint["device_model"],
            system_version=fingerprint["system_version"],
            app_version=fingerprint["app_version"],
            lang_code=fingerprint["lang_code"],
            system_lang_code=fingerprint["system_lang_code"],
        )

        try:
            await client.connect()

            # Send code request
            result = await client.send_code_request(phone)

            # Save pending auth
            pending = PendingAuth(
                phone=phone,
                client=client,
                phone_code_hash=result.phone_code_hash,
                api_id=self.api_id,
                api_hash=self.api_hash,
            )
            pending.fingerprint = fingerprint
            self.pending_auths[user_id] = pending

            logger.info(f"Code sent to {phone[:4]}*** for user {user_id}")

            return {
                "status": "code_sent",
                "phone": phone,
                "phone_code_hash": result.phone_code_hash,
                "timeout": result.timeout or 120,
            }

        except PhoneNumberBannedError:
            await client.disconnect()
            return {
                "status": "error",
                "error_type": "phone_banned",
                "message": "This phone number is banned by Telegram",
            }

        except PhoneNumberFloodError:
            await client.disconnect()
            return {
                "status": "error",
                "error_type": "phone_flood",
                "message": "Too many attempts. Try again later",
            }

        except FloodWaitError as e:
            await client.disconnect()
            return {
                "status": "error",
                "error_type": "flood_wait",
                "message": f"Too many requests. Wait {e.seconds} seconds",
                "wait_seconds": e.seconds,
            }

        except Exception as e:
            await client.disconnect()
            logger.error(f"Auth error for {phone}: {e}")
            return {
                "status": "error",
                "error_type": "unknown",
                "message": str(e),
            }

    async def verify_code(self, user_id: int, code: str) -> dict:
        """
        Step 2: Verify the received code.

        Args:
            user_id: Bot user ID
            code: 5-digit code from Telegram

        Returns:
            Result dict with status
        """
        if user_id not in self.pending_auths:
            return {
                "status": "error",
                "error_type": "no_pending",
                "message": "No pending authorization. Start again",
            }

        pending = self.pending_auths[user_id]

        if pending.is_expired:
            await self._cleanup_auth(user_id)
            return {
                "status": "error",
                "error_type": "expired",
                "message": "Session expired. Request new code",
            }

        try:
            await pending.client.sign_in(
                pending.phone,
                code,
                phone_code_hash=pending.phone_code_hash,
            )

            # Success - no 2FA
            return await self._complete_auth(user_id)

        except SessionPasswordNeededError:
            # 2FA required
            return {
                "status": "need_2fa",
                "message": "Two-factor authentication required",
            }

        except PhoneCodeExpiredError:
            await self._cleanup_auth(user_id)
            return {
                "status": "error",
                "error_type": "code_expired",
                "message": "Code expired. Request new one",
            }

        except PhoneCodeInvalidError:
            pending.attempts += 1
            if pending.attempts >= 3:
                await self._cleanup_auth(user_id)
                return {
                    "status": "error",
                    "error_type": "max_attempts",
                    "message": "Too many wrong attempts. Start again",
                }
            return {
                "status": "error",
                "error_type": "invalid_code",
                "message": f"Invalid code. {3 - pending.attempts} attempts left",
                "attempts_left": 3 - pending.attempts,
            }

        except Exception as e:
            logger.error(f"Code verification error: {e}")
            return {
                "status": "error",
                "error_type": "unknown",
                "message": str(e),
            }

    async def verify_2fa(self, user_id: int, password: str) -> dict:
        """
        Step 3: Verify 2FA password.

        Args:
            user_id: Bot user ID
            password: 2FA password

        Returns:
            Result dict with status
        """
        if user_id not in self.pending_auths:
            return {
                "status": "error",
                "error_type": "no_pending",
                "message": "No pending authorization",
            }

        pending = self.pending_auths[user_id]

        try:
            await pending.client.sign_in(password=password)
            return await self._complete_auth(user_id)

        except Exception as e:
            pending.attempts += 1
            if pending.attempts >= 3:
                await self._cleanup_auth(user_id)
                return {
                    "status": "error",
                    "error_type": "max_attempts",
                    "message": "Too many wrong attempts",
                }
            return {
                "status": "error",
                "error_type": "invalid_password",
                "message": f"Wrong 2FA password. {3 - pending.attempts} attempts left",
            }

    async def _complete_auth(self, user_id: int) -> dict:
        """
        Complete authorization and return account data.

        Args:
            user_id: Bot user ID

        Returns:
            Result dict with account info
        """
        pending = self.pending_auths[user_id]
        client = pending.client

        try:
            # Get account info
            me = await client.get_me()

            # Get dialogs count for age estimation
            dialogs = await client.get_dialogs(limit=0)
            dialogs_count = dialogs.total if hasattr(dialogs, 'total') else 0

            # Save session as string
            session_string = client.session.save()

            account_data = {
                "telegram_id": me.id,
                "phone": pending.phone,
                "username": me.username,
                "first_name": me.first_name,
                "session_string": session_string,
                "is_premium": getattr(me, "premium", False),
                "device_fingerprint": pending.fingerprint,
                "dialogs_count": dialogs_count,
                "created_at": datetime.utcnow(),
            }

            logger.info(
                f"Auth completed for {pending.phone[:4]}***, "
                f"telegram_id={me.id}, premium={account_data['is_premium']}"
            )

            # Cleanup
            await self._cleanup_auth(user_id)

            return {
                "status": "success",
                "account": account_data,
            }

        except Exception as e:
            logger.error(f"Complete auth error: {e}")
            await self._cleanup_auth(user_id)
            return {
                "status": "error",
                "error_type": "complete_failed",
                "message": str(e),
            }

    async def cancel_auth(self, user_id: int) -> dict:
        """
        Cancel pending authorization.

        Args:
            user_id: Bot user ID

        Returns:
            Result dict
        """
        if user_id in self.pending_auths:
            await self._cleanup_auth(user_id)
            return {"status": "cancelled"}
        return {"status": "no_pending"}

    async def _cleanup_auth(self, user_id: int) -> None:
        """Clean up pending auth for user."""
        if user_id in self.pending_auths:
            pending = self.pending_auths[user_id]
            try:
                if pending.client.is_connected():
                    await pending.client.disconnect()
            except Exception:
                pass
            del self.pending_auths[user_id]

    async def _cleanup_expired(self) -> None:
        """Clean up all expired pending auths."""
        expired = [
            uid for uid, pending in self.pending_auths.items()
            if pending.is_expired
        ]
        for uid in expired:
            await self._cleanup_auth(uid)

    def get_pending_status(self, user_id: int) -> Optional[dict]:
        """Get status of pending auth."""
        if user_id not in self.pending_auths:
            return None

        pending = self.pending_auths[user_id]
        return {
            "phone": pending.phone[:4] + "***",
            "attempts": pending.attempts,
            "is_expired": pending.is_expired,
            "created_at": pending.created_at,
        }
