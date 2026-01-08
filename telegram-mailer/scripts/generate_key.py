#!/usr/bin/env python3
"""Generate encryption key for Telegram Mailer."""

from cryptography.fernet import Fernet


def main():
    """Generate and print a new Fernet encryption key."""
    key = Fernet.generate_key()
    print("Generated encryption key:")
    print(key.decode())
    print("\nAdd this to your .env file as:")
    print(f"ENCRYPTION_KEY={key.decode()}")


if __name__ == "__main__":
    main()
