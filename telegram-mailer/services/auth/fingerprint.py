"""Device fingerprint generation for accounts."""

import hashlib
import random
from datetime import datetime
from typing import Optional

from common.constants import DEVICE_MODELS, ANDROID_VERSIONS


class DeviceFingerprint:
    """
    Device fingerprint management for accounts.

    CRITICAL: Fingerprint must be:
    1. Unique for each account
    2. IMMUTABLE throughout account lifetime
    3. Realistic (popular devices)
    """

    # Current Telegram app version (update periodically)
    TELEGRAM_APP_VERSION = "10.14.5"
    TELEGRAM_LAYER = 185

    @classmethod
    def generate(cls, seed: Optional[str] = None) -> dict:
        """
        Generate unique but realistic device fingerprint.

        Args:
            seed: Optional seed for deterministic generation

        Returns:
            Fingerprint dictionary

        Note:
            Call ONLY when creating new account!
            Store and reuse forever after.
        """
        if seed:
            random.seed(seed)

        # Pick random device
        brand, model, name = random.choice(DEVICE_MODELS)
        android_version, sdk = random.choice(ANDROID_VERSIONS)

        # Generate unique device hash
        unique_data = f"{model}:{datetime.utcnow().isoformat()}:{random.random()}"
        device_hash = hashlib.md5(unique_data.encode()).hexdigest()[:16]

        fingerprint = {
            # Device info
            "device_brand": brand,
            "device_model": model,
            "device_name": name,

            # System info
            "system_version": f"SDK {sdk}",
            "sdk_version": sdk,

            # App info
            "app_version": cls.TELEGRAM_APP_VERSION,
            "app_version_code": str(cls.TELEGRAM_LAYER),

            # Language
            "lang_code": "ru",
            "system_lang_code": "ru-RU",

            # Unique identifier
            "device_hash": device_hash,

            # Metadata
            "created_at": datetime.utcnow().isoformat(),
            "is_immutable": True,
        }

        # Reset random seed
        if seed:
            random.seed()

        return fingerprint

    @classmethod
    def get_telethon_params(cls, fingerprint: dict) -> dict:
        """
        Get parameters for Telethon client initialization.

        Args:
            fingerprint: Stored fingerprint

        Returns:
            Dict with Telethon client params
        """
        return {
            "device_model": fingerprint.get("device_model", "Samsung SM-G998B"),
            "system_version": fingerprint.get("system_version", "SDK 33"),
            "app_version": fingerprint.get("app_version", cls.TELEGRAM_APP_VERSION),
            "lang_code": fingerprint.get("lang_code", "ru"),
            "system_lang_code": fingerprint.get("system_lang_code", "ru-RU"),
        }

    @classmethod
    def validate(cls, fingerprint: dict) -> bool:
        """
        Validate fingerprint has required fields.

        Args:
            fingerprint: Fingerprint to validate

        Returns:
            True if valid
        """
        required = ["device_model", "system_version", "app_version"]
        return all(field in fingerprint for field in required)

    @classmethod
    def should_update_app_version(cls, fingerprint: dict) -> bool:
        """
        Check if app version in fingerprint is outdated.

        Note: Don't update too often - suspicious behavior!
        Only update if very outdated (6+ months old versions)

        Args:
            fingerprint: Stored fingerprint

        Returns:
            True if should update (carefully!)
        """
        stored_version = fingerprint.get("app_version", "")

        # Parse versions
        try:
            stored_parts = [int(x) for x in stored_version.split(".")]
            current_parts = [int(x) for x in cls.TELEGRAM_APP_VERSION.split(".")]

            # Only update if major version is 2+ behind
            if stored_parts[0] < current_parts[0] - 1:
                return True

        except (ValueError, IndexError):
            return False

        return False
