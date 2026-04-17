"""Run Alembic migrations against the configured database."""

from __future__ import annotations

import asyncio
from collections import defaultdict

import asyncpg
from alembic.config import Config
from sqlalchemy import Numeric

from alembic import command
from ima.config import settings
from ima.db.models import Base

FIXED_POINT_SCHEMA_COLUMNS = (
    ("creators", "avg_engagement_30d"),
    ("creators", "growth_score"),
    ("creators", "niche_fit_score"),
    ("creators", "commercial_score"),
    ("creators", "fraud_score"),
    ("creators", "evidence_coverage_score"),
    ("creators", "email_confidence"),
    ("creator_content", "sponsor_probability"),
    ("evidence_items", "confidence"),
)


def _build_config() -> Config:
    """Return the shared Alembic config for command execution."""

    return Config("alembic.ini")


def main() -> None:
    """Upgrade the configured database to the latest Alembic head."""

    config = _build_config()
    command.upgrade(config, "head")


def _expected_numeric_columns() -> dict[str, dict[str, tuple[int, int]]]:
    """Return the canonical precision/scale for critical fixed-point columns."""

    expected: dict[str, dict[str, tuple[int, int]]] = defaultdict(dict)
    for table_name, column_name in FIXED_POINT_SCHEMA_COLUMNS:
        column = Base.metadata.tables[table_name].c[column_name]
        if not isinstance(column.type, Numeric):
            raise RuntimeError(f"{table_name}.{column_name} ist kein Numeric-ORM-Feld.")
        if column.type.precision is None or column.type.scale is None:
            raise RuntimeError(
                f"{table_name}.{column_name} braucht explizite Numeric precision/scale."
            )
        expected[table_name][column_name] = (column.type.precision, column.type.scale)
    return dict(expected)


async def _assert_schema_matches_models_async() -> None:
    """Validate migrated Postgres columns against critical ORM numeric metadata."""

    expected = _expected_numeric_columns()
    connection = await asyncpg.connect(settings.database_url.replace("+asyncpg", ""))
    try:
        for table_name, columns in expected.items():
            rows = await connection.fetch(
                """
                SELECT column_name, data_type, numeric_precision, numeric_scale
                FROM information_schema.columns
                WHERE table_schema = 'public'
                  AND table_name = $1
                  AND column_name = ANY($2::text[])
                """,
                table_name,
                list(columns.keys()),
            )
            actual = {row["column_name"]: row for row in rows}
            missing = set(columns) - set(actual)
            if missing:
                raise RuntimeError(
                    f"{table_name} fehlt Score-Spalten im migrierten Schema: {sorted(missing)}"
                )

            for column_name, (precision, scale) in columns.items():
                row = actual[column_name]
                if row["data_type"] != "numeric":
                    raise RuntimeError(
                        f"{table_name}.{column_name} ist {row['data_type']} statt numeric."
                    )
                if row["numeric_precision"] != precision or row["numeric_scale"] != scale:
                    raise RuntimeError(
                        f"{table_name}.{column_name} ist numeric({row['numeric_precision']}, "
                        f"{row['numeric_scale']}) statt numeric({precision}, {scale})."
                    )
    finally:
        await connection.close()


def assert_schema_matches_models() -> None:
    """Fail when critical migrated score columns drift away from ORM metadata."""

    asyncio.run(_assert_schema_matches_models_async())


if __name__ == "__main__":
    main()
