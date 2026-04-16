ALTER TABLE creators
    ADD COLUMN IF NOT EXISTS growth_score INTEGER NULL CHECK (
        growth_score IS NULL OR growth_score BETWEEN 0 AND 100
    );

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

CREATE INDEX IF NOT EXISTS ix_creator_metric_snapshots_creator_id_captured_at
    ON creator_metric_snapshots (creator_id, captured_at);
