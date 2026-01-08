#!/usr/bin/env python3
"""Script to create invite keys."""

import asyncio
import sys

from database import init_db, get_db_manager
from database.repositories import InviteKeyRepository


async def create_invite_key(count: int = 1) -> list[str]:
    """
    Create invite keys.

    Args:
        count: Number of keys to create

    Returns:
        List of created keys
    """
    await init_db()
    db_manager = get_db_manager()

    keys = []
    async with db_manager.session() as session:
        repo = InviteKeyRepository(session)
        for _ in range(count):
            key = await repo.generate_key()
            keys.append(key)

    return keys


async def main():
    """Main entry point."""
    count = int(sys.argv[1]) if len(sys.argv) > 1 else 1

    print(f"Creating {count} invite key(s)...")
    keys = await create_invite_key(count)

    print("\nCreated invite keys:")
    for key in keys:
        print(f"  - {key}")


if __name__ == "__main__":
    asyncio.run(main())
