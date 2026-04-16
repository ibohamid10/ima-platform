"""Run SQL migrations against the configured database."""

from __future__ import annotations

import asyncio
from pathlib import Path

import asyncpg

from ima.config import settings


async def ensure_migration_table(connection: asyncpg.Connection) -> None:
    """Create the lightweight migration tracking table if needed."""

    await connection.execute(
        """
        CREATE TABLE IF NOT EXISTS schema_migrations (
            version VARCHAR(255) PRIMARY KEY,
            applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
        """
    )


async def applied_versions(connection: asyncpg.Connection) -> set[str]:
    """Return already applied migration versions."""

    rows = await connection.fetch("SELECT version FROM schema_migrations;")
    return {row["version"] for row in rows}


async def main() -> None:
    """Execute all SQL migrations in lexical order and track them."""

    migrations_dir = Path("src/ima/db/migrations")
    migration_paths = sorted(migrations_dir.glob("*.sql"))
    connection = await asyncpg.connect(settings.database_url.replace("+asyncpg", ""))
    try:
        await ensure_migration_table(connection)
        already_applied = await applied_versions(connection)

        for migration_path in migration_paths:
            if migration_path.name in already_applied:
                continue
            sql = migration_path.read_text(encoding="utf-8")
            async with connection.transaction():
                await connection.execute(sql)
                await connection.execute(
                    "INSERT INTO schema_migrations(version) VALUES($1) ON CONFLICT DO NOTHING;",
                    migration_path.name,
                )
            print(f"Migration applied: {migration_path.name}")
    finally:
        await connection.close()


if __name__ == "__main__":
    asyncio.run(main())
