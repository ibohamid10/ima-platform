"""Expand agent_run validation statuses for preflight failure auditability."""

from __future__ import annotations

from sqlalchemy import inspect

from alembic import op

revision = "20260418_008"
down_revision = "20260417_007"
branch_labels = None
depends_on = None


def _constraint_exists(table_name: str, constraint_name: str) -> bool:
    """Return whether the given check constraint exists in the current schema."""

    bind = op.get_bind()
    inspector = inspect(bind)
    constraints = inspector.get_check_constraints(table_name)
    return any(constraint["name"] == constraint_name for constraint in constraints)


def upgrade() -> None:
    """Allow new preflight agent_run statuses in Postgres schemas."""

    if _constraint_exists("agent_runs", "agent_runs_validation_status_check"):
        op.execute("ALTER TABLE agent_runs DROP CONSTRAINT agent_runs_validation_status_check;")

    op.execute(
        """
        ALTER TABLE agent_runs
        ADD CONSTRAINT agent_runs_validation_status_check
        CHECK (
            validation_status IN (
                'pending',
                'success',
                'schema_retry',
                'schema_failed',
                'budget_exceeded',
                'provider_unavailable',
                'provider_error'
            )
        );
        """
    )


def downgrade() -> None:
    """Remove the extended preflight statuses from the Postgres check constraint."""

    if _constraint_exists("agent_runs", "agent_runs_validation_status_check"):
        op.execute("ALTER TABLE agent_runs DROP CONSTRAINT agent_runs_validation_status_check;")

    op.execute(
        """
        ALTER TABLE agent_runs
        ADD CONSTRAINT agent_runs_validation_status_check
        CHECK (
            validation_status IN (
                'pending',
                'success',
                'schema_retry',
                'schema_failed',
                'provider_error'
            )
        );
        """
    )
