"""Add reserved budget tracking to agent_runs for atomic budget gating."""

from __future__ import annotations

from sqlalchemy import inspect

from alembic import op

revision = "20260418_009"
down_revision = "20260418_008"
branch_labels = None
depends_on = None


def _column_exists(table_name: str, column_name: str) -> bool:
    """Return whether the given column exists in the current schema."""

    bind = op.get_bind()
    inspector = inspect(bind)
    columns = inspector.get_columns(table_name)
    return any(column["name"] == column_name for column in columns)


def upgrade() -> None:
    """Add reserved_cost_usd so budget checks can reserve capacity atomically."""

    if not _column_exists("agent_runs", "reserved_cost_usd"):
        op.execute(
            """
            ALTER TABLE agent_runs
            ADD COLUMN reserved_cost_usd NUMERIC(12, 6) NOT NULL DEFAULT 0;
            """
        )


def downgrade() -> None:
    """Drop the reserved budget column from agent_runs."""

    if _column_exists("agent_runs", "reserved_cost_usd"):
        op.execute("ALTER TABLE agent_runs DROP COLUMN reserved_cost_usd;")
