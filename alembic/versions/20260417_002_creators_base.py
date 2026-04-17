"""Create the base creators and creator_content tables."""

from __future__ import annotations

from alembic import op

revision = "20260417_002"
down_revision = "20260417_001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create the original creator discovery tables."""

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS creators (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            platform VARCHAR(32) NOT NULL CHECK (
                platform IN ('youtube', 'instagram', 'tiktok')
            ),
            external_id VARCHAR(255) NULL,
            handle VARCHAR(255) NOT NULL,
            profile_url TEXT NULL,
            display_name VARCHAR(255) NULL,
            bio TEXT NULL,
            follower_count BIGINT NULL,
            primary_language VARCHAR(8) NULL,
            niche VARCHAR(64) NULL,
            sub_niches JSONB NOT NULL DEFAULT '[]'::jsonb,
            commercial_readiness_score INTEGER NULL CHECK (
                commercial_readiness_score IS NULL
                OR commercial_readiness_score BETWEEN 0 AND 100
            ),
            fraud_risk_score INTEGER NULL CHECK (
                fraud_risk_score IS NULL
                OR fraud_risk_score BETWEEN 0 AND 100
            ),
            evidence_coverage_score INTEGER NULL CHECK (
                evidence_coverage_score IS NULL
                OR evidence_coverage_score BETWEEN 0 AND 100
            ),
            consent_status VARCHAR(32) NOT NULL DEFAULT 'unknown' CHECK (
                consent_status IN (
                    'unknown',
                    'legitimate_interest',
                    'consented',
                    'suppressed'
                )
            ),
            consent_recorded_at TIMESTAMPTZ NULL,
            source_labels JSONB NOT NULL DEFAULT '[]'::jsonb,
            is_qualified BOOLEAN NOT NULL DEFAULT FALSE,
            last_seen_at TIMESTAMPTZ NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            CONSTRAINT uq_creators_platform_handle UNIQUE (platform, handle)
        );
        """
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS creator_content (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            creator_id UUID NOT NULL REFERENCES creators (id) ON DELETE CASCADE,
            platform_content_id VARCHAR(255) NULL,
            content_type VARCHAR(32) NOT NULL CHECK (
                content_type IN ('video', 'short', 'post', 'reel', 'tiktok')
            ),
            url TEXT NULL,
            title VARCHAR(255) NULL,
            caption_text TEXT NULL,
            published_at TIMESTAMPTZ NULL,
            view_count BIGINT NULL,
            like_count BIGINT NULL,
            comment_count BIGINT NULL,
            top_hashtags JSONB NOT NULL DEFAULT '[]'::jsonb,
            raw_payload JSONB NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_creators_platform_handle "
        "ON creators (platform, handle);"
    )
    op.execute("CREATE INDEX IF NOT EXISTS ix_creators_qualified ON creators (is_qualified);")
    op.execute("CREATE INDEX IF NOT EXISTS ix_creators_last_seen_at ON creators (last_seen_at);")
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_creator_content_creator_id_published_at "
        "ON creator_content (creator_id, published_at);"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_creator_content_platform_content_id "
        "ON creator_content (platform_content_id);"
    )


def downgrade() -> None:
    """Drop the base creator tables."""

    op.execute("DROP TABLE IF EXISTS creator_content CASCADE;")
    op.execute("DROP TABLE IF EXISTS creators CASCADE;")
