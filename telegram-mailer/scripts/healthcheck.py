#!/usr/bin/env python3
"""Health check script for Docker containers."""

import asyncio
import sys
from typing import Optional

import asyncpg
import redis.asyncio as redis

from common.config import settings


async def check_database() -> tuple[bool, str]:
    """Check database connection."""
    try:
        # Parse database URL
        db_url = settings.DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://")
        conn = await asyncpg.connect(db_url)
        await conn.fetchval("SELECT 1")
        await conn.close()
        return True, "Database OK"
    except Exception as e:
        return False, f"Database error: {e}"


async def check_redis() -> tuple[bool, str]:
    """Check Redis connection."""
    try:
        client = redis.from_url(settings.REDIS_URL)
        await client.ping()
        await client.close()
        return True, "Redis OK"
    except Exception as e:
        return False, f"Redis error: {e}"


async def main(service: Optional[str] = None) -> int:
    """
    Run health checks.

    Args:
        service: Specific service to check (database, redis, or all)

    Returns:
        Exit code (0 for success, 1 for failure)
    """
    checks = []

    if service in (None, "all", "database", "db"):
        checks.append(("Database", check_database()))

    if service in (None, "all", "redis"):
        checks.append(("Redis", check_redis()))

    all_ok = True
    results = []

    for name, coro in checks:
        ok, message = await coro
        results.append((name, ok, message))
        if not ok:
            all_ok = False

    # Print results
    for name, ok, message in results:
        status = "✅" if ok else "❌"
        print(f"{status} {name}: {message}")

    return 0 if all_ok else 1


if __name__ == "__main__":
    service = sys.argv[1] if len(sys.argv) > 1 else None
    exit_code = asyncio.run(main(service))
    sys.exit(exit_code)
