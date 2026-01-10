"""Custom application exceptions."""


class TelegramMailerError(Exception):
    """Base exception for all application errors."""

    def __init__(self, message: str = "An error occurred"):
        self.message = message
        super().__init__(self.message)


# Database Exceptions
class DatabaseError(TelegramMailerError):
    """Base database exception."""

    pass


class RecordNotFoundError(DatabaseError):
    """Record not found in database."""

    def __init__(self, model: str, identifier: str):
        super().__init__(f"{model} with id '{identifier}' not found")
        self.model = model
        self.identifier = identifier


class DuplicateRecordError(DatabaseError):
    """Duplicate record error."""

    def __init__(self, model: str, field: str, value: str):
        super().__init__(f"{model} with {field}='{value}' already exists")
        self.model = model
        self.field = field
        self.value = value


# Account Exceptions
class AccountError(TelegramMailerError):
    """Base account exception."""

    pass


class AccountNotFoundError(AccountError):
    """Account not found."""

    pass


class AccountBannedError(AccountError):
    """Account is banned (spam block)."""

    pass


class AccountSessionInvalidError(AccountError):
    """Account session is invalid or expired."""

    pass


class AccountLimitExceededError(AccountError):
    """User exceeded maximum accounts limit."""

    pass


# Proxy Exceptions
class ProxyError(TelegramMailerError):
    """Base proxy exception."""

    pass


class ProxyConnectionError(ProxyError):
    """Failed to connect through proxy."""

    pass


class ProxyNotFoundError(ProxyError):
    """Proxy not found."""

    pass


class ProxyLimitExceededError(ProxyError):
    """User exceeded maximum proxies limit."""

    pass


# Folder Exceptions
class FolderError(TelegramMailerError):
    """Base folder exception."""

    pass


class FolderNotFoundError(FolderError):
    """Folder not found."""

    pass


class FolderSyncError(FolderError):
    """Failed to sync folder."""

    pass


class InvalidFolderLinkError(FolderError):
    """Invalid folder link format."""

    pass


class FolderLimitExceededError(FolderError):
    """User exceeded maximum folders limit."""

    pass


# Campaign Exceptions
class CampaignError(TelegramMailerError):
    """Base campaign exception."""

    pass


class CampaignNotFoundError(CampaignError):
    """Campaign not found."""

    pass


class CampaignAlreadyRunningError(CampaignError):
    """Campaign is already running."""

    pass


class CampaignNotActiveError(CampaignError):
    """Campaign is not in active state."""

    pass


class CampaignLimitExceededError(CampaignError):
    """User exceeded maximum campaigns limit."""

    pass


# Session Exceptions
class SessionError(TelegramMailerError):
    """Base session exception."""

    pass


class SessionNotFoundError(SessionError):
    """Session file not found."""

    pass


class SessionDecryptionError(SessionError):
    """Failed to decrypt session."""

    pass


class SessionValidationError(SessionError):
    """Session validation failed."""

    pass


# Encryption Exceptions
class EncryptionError(TelegramMailerError):
    """Base encryption exception."""

    pass


class EncryptionKeyError(EncryptionError):
    """Invalid or missing encryption key."""

    pass


# Worker Exceptions
class WorkerError(TelegramMailerError):
    """Base worker exception."""

    pass


class WorkerBusyError(WorkerError):
    """Worker is busy with another task."""

    pass


class WorkerStoppedError(WorkerError):
    """Worker was stopped."""

    pass


# Auth Exceptions
class AuthError(TelegramMailerError):
    """Base authentication exception."""

    pass


class UnauthorizedError(AuthError):
    """User is not authorized."""

    pass


class InvalidInviteKeyError(AuthError):
    """Invalid or expired invite key."""

    pass


class InviteKeyUsedError(AuthError):
    """Invite key has already been used."""

    pass


# Telegram Exceptions (wrappers)
class TelegramError(TelegramMailerError):
    """Base Telegram API exception."""

    pass


class FloodWaitError(TelegramError):
    """FloodWait from Telegram."""

    def __init__(self, seconds: int):
        super().__init__(f"FloodWait: need to wait {seconds} seconds")
        self.seconds = seconds


class SpamBlockError(TelegramError):
    """Spam block (PeerFloodError) from Telegram."""

    pass


class ChatAccessError(TelegramError):
    """Cannot access chat (banned, private, etc.)."""

    pass


# Generic aliases for common use
class NotFoundError(TelegramMailerError):
    """Generic not found error."""

    pass


class ValidationError(TelegramMailerError):
    """Generic validation error."""

    pass
