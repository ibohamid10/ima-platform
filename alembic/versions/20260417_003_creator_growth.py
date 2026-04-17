"""Add historical creator metric snapshots and growth score."""

from __future__ import annotations

from alembic import op

revision = "20260417_003"
down_revision = "20260417_002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add the original growth-tracking schema additions."""

    op.execute(
        """
        ALTER TABLE creators
            ADD COLUMN IF NOT EXISTS growth_score INTEGER NULL CHECK (
                growth_score IS NULL OR growth_score BETWEEN 0 AND 100
            );
        """
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS creator_metric_snapshots (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            creator_id UUID NOT NULL REFERENCES creators (id) ON DELETE CASCADE,
            captured_at TIMESTAMPTZ NOT NULL,
            follower_count BIGINT NULL,
            average_views_30d BIGINT NULL,
            average_likes_30d BIGINT NULL,
            average_comments_30d BIGINT NULL,
            engagement_rate_30d NUMERIC(8, 4) NULL,
            source VARCHAR(64) NOT NULL DEFAULT 'system',
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_creator_metric_snapshots_creator_id_captured_at "
        "ON creator_metric_snapshots (creator_id, captured_at);"
    )


def downgrade() -> None:
    """Drop the original growth-tracking additions."""

    op.execute("DROP TABLE IF EXISTS creator_metric_snapshots CASCADE;")
    op.execute("ALTER TABLE creators DROP COLUMN IF EXISTS growth_score;")
