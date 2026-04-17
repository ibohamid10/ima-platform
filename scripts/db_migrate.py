"""Run Alembic migrations against the configured database."""

from __future__ import annotations

from alembic.config import Config

from alembic import command


def main() -> None:
    """Upgrade the configured database to the latest Alembic head."""

    config = Config("alembic.ini")
    command.upgrade(config, "head")


if __name__ == "__main__":
    main()
