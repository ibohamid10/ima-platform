"""Create the initial agent_runs table."""

from __future__ import annotations

from alembic import op

revision = "20260417_001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create the initial agent run audit table."""

    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto;")
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS agent_runs (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            agent_name VARCHAR(255) NOT NULL,
            contract_version VARCHAR(32) NOT NULL,
            provider VARCHAR(64) NOT NULL,
            model VARCHAR(128) NOT NULL,
            input_hash CHAR(64) NOT NULL,
            input_json JSONB NOT NULL,
            output_json JSONB NULL,
            validation_status VARCHAR(32) NOT NULL CHECK (
                validation_status IN (
                    'pending',
                    'success',
                    'schema_retry',
                    'schema_failed',
                    'provider_error'
                )
            ),
            validation_attempts INTEGER NOT NULL DEFAULT 1,
            input_tokens INTEGER NULL,
            output_tokens INTEGER NULL,
            cost_usd NUMERIC(12, 6) NULL,
            latency_ms INTEGER NOT NULL DEFAULT 0,
            error_message TEXT NULL,
            started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            completed_at TIMESTAMPTZ NULL,
            trace_id VARCHAR(128) NULL
        );
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS ix_agent_runs_agent_name ON agent_runs (agent_name);")
    op.execute("CREATE INDEX IF NOT EXISTS ix_agent_runs_started_at ON agent_runs (started_at);")
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_agent_runs_validation_status "
        "ON agent_runs (validation_status);"
    )


def downgrade() -> None:
    """Drop the initial agent run audit table."""

    op.execute("DROP TABLE IF EXISTS agent_runs CASCADE;")
