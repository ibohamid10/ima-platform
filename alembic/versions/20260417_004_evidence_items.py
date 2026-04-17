"""Create the original evidence_items table."""

from __future__ import annotations

from alembic import op

revision = "20260417_004"
down_revision = "20260417_003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create the original evidence_items table."""

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS evidence_items (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            creator_id UUID NOT NULL REFERENCES creators(id) ON DELETE CASCADE,
            content_id UUID NULL REFERENCES creator_content(id) ON DELETE CASCADE,
            snapshot_id UUID NULL REFERENCES creator_metric_snapshots(id) ON DELETE CASCADE,
            source_key VARCHAR(255) NOT NULL UNIQUE,
            evidence_type VARCHAR(64) NOT NULL,
            source_kind VARCHAR(64) NOT NULL,
            claim_text TEXT NOT NULL,
            source_uri TEXT NOT NULL,
            artifact_uri TEXT NULL,
            snippet_text TEXT NULL,
            metadata_json JSONB NOT NULL DEFAULT '{}'::jsonb,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_evidence_items_creator_id "
        "ON evidence_items (creator_id);"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_evidence_items_content_id "
        "ON evidence_items (content_id);"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_evidence_items_snapshot_id "
        "ON evidence_items (snapshot_id);"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_evidence_items_evidence_type "
        "ON evidence_items (evidence_type);"
    )


def downgrade() -> None:
    """Drop the original evidence_items table."""

    op.execute("DROP TABLE IF EXISTS evidence_items CASCADE;")
