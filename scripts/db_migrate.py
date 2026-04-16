"""Run the week-1 SQL migration against the configured database."""

from __future__ import annotations

import asyncio
from pathlib import Path

import asyncpg

from ima.config import settings


async def main() -> None:
    """Execute the initial SQL migration in an idempotent way."""

    migration_path = Path("src/ima/db/migrations/001_initial.sql")
    sql = migration_path.read_text(encoding="utf-8")
    connection = await asyncpg.connect(settings.database_url.replace("+asyncpg", ""))
    try:
        await connection.execute(sql)
    finally:
        await connection.close()
    print("Migration applied: 001_initial.sql")


if __name__ == "__main__":
    asyncio.run(main())
