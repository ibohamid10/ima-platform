"""Align week-2 schema with the target deliverable specification."""

from __future__ import annotations

from sqlalchemy import inspect

from alembic import op

revision = "20260417_005"
down_revision = "20260417_004"
branch_labels = None
depends_on = None


def _column_exists(table_name: str, column_name: str) -> bool:
    """Return whether the given column exists in the current schema."""

    bind = op.get_bind()
    inspector = inspect(bind)
    columns = inspector.get_columns(table_name)
    return any(column["name"] == column_name for column in columns)


def _index_exists(table_name: str, index_name: str) -> bool:
    """Return whether the given index exists in the current schema."""

    bind = op.get_bind()
    inspector = inspect(bind)
    indexes = inspector.get_indexes(table_name)
    return any(index["name"] == index_name for index in indexes)


def upgrade() -> None:
    """Rename and extend creator, content, and evidence schemas."""

    if _column_exists("creators", "follower_count") and not _column_exists("creators", "followers"):
        op.execute("ALTER TABLE creators RENAME COLUMN follower_count TO followers;")
    if _column_exists("creators", "primary_language") and not _column_exists(
        "creators", "language"
    ):
        op.execute("ALTER TABLE creators RENAME COLUMN primary_language TO language;")
    if _column_exists("creators", "commercial_readiness_score") and not _column_exists(
        "creators", "commercial_score"
    ):
        op.execute(
            "ALTER TABLE creators RENAME COLUMN commercial_readiness_score TO commercial_score;"
        )
    if _column_exists("creators", "fraud_risk_score") and not _column_exists(
        "creators", "fraud_score"
    ):
        op.execute("ALTER TABLE creators RENAME COLUMN fraud_risk_score TO fraud_score;")
    if _column_exists("creators", "consent_status") and not _column_exists(
        "creators", "consent_basis"
    ):
        op.execute("ALTER TABLE creators RENAME COLUMN consent_status TO consent_basis;")

    op.execute(
        "ALTER TABLE creators "
        "ADD COLUMN IF NOT EXISTS niche_labels JSONB NOT NULL DEFAULT '[]'::jsonb;"
    )
    op.execute("ALTER TABLE creators ADD COLUMN IF NOT EXISTS geo VARCHAR(64) NULL;")
    op.execute("ALTER TABLE creators ADD COLUMN IF NOT EXISTS avg_views_30d BIGINT NULL;")
    op.execute("ALTER TABLE creators ADD COLUMN IF NOT EXISTS avg_views_90d BIGINT NULL;")
    op.execute(
        "ALTER TABLE creators ADD COLUMN IF NOT EXISTS avg_engagement_30d DOUBLE PRECISION NULL;"
    )
    op.execute(
        "ALTER TABLE creators ADD COLUMN IF NOT EXISTS niche_fit_score DOUBLE PRECISION NULL;"
    )
    op.execute("ALTER TABLE creators ADD COLUMN IF NOT EXISTS email VARCHAR(255) NULL;")
    op.execute(
        "ALTER TABLE creators ADD COLUMN IF NOT EXISTS email_confidence DOUBLE PRECISION NULL;"
    )

    op.execute(
        """
        UPDATE creators
        SET niche_labels = CASE
            WHEN COALESCE(jsonb_array_length(niche_labels), 0) > 0 THEN niche_labels
            WHEN niche IS NOT NULL AND jsonb_array_length(sub_niches) > 0
                THEN to_jsonb(ARRAY[niche]::text[]) || sub_niches
            WHEN niche IS NOT NULL THEN to_jsonb(ARRAY[niche]::text[])
            ELSE '[]'::jsonb
        END;
        """
    )

    op.execute(
        """
        UPDATE creators
        SET avg_views_30d = snapshots.average_views_30d,
            avg_engagement_30d = snapshots.engagement_rate_30d::double precision
        FROM (
            SELECT DISTINCT ON (creator_id)
                creator_id,
                average_views_30d,
                engagement_rate_30d
            FROM creator_metric_snapshots
            ORDER BY creator_id, captured_at DESC
        ) AS snapshots
        WHERE creators.id = snapshots.creator_id;
        """
    )

    op.execute(
        """
        ALTER TABLE creators
            ALTER COLUMN growth_score TYPE DOUBLE PRECISION USING growth_score::double precision,
            ALTER COLUMN commercial_score TYPE DOUBLE PRECISION
                USING commercial_score::double precision,
            ALTER COLUMN fraud_score TYPE DOUBLE PRECISION USING fraud_score::double precision,
            ALTER COLUMN evidence_coverage_score TYPE DOUBLE PRECISION
                USING evidence_coverage_score::double precision;
        """
    )

    if _column_exists("creator_content", "caption_text") and not _column_exists(
        "creator_content", "caption"
    ):
        op.execute("ALTER TABLE creator_content RENAME COLUMN caption_text TO caption;")
    if _column_exists("creator_content", "top_hashtags") and not _column_exists(
        "creator_content", "hashtags"
    ):
        op.execute("ALTER TABLE creator_content RENAME COLUMN top_hashtags TO hashtags;")

    op.execute("ALTER TABLE creator_content ADD COLUMN IF NOT EXISTS detected_brands JSONB NULL;")
    op.execute(
        "ALTER TABLE creator_content "
        "ADD COLUMN IF NOT EXISTS sponsor_probability DOUBLE PRECISION NULL;"
    )
    op.execute("ALTER TABLE creator_content ADD COLUMN IF NOT EXISTS raw_snapshot_uri TEXT NULL;")

    if _column_exists("evidence_items", "source_kind") and not _column_exists(
        "evidence_items", "source_type"
    ):
        op.execute("ALTER TABLE evidence_items RENAME COLUMN source_kind TO source_type;")

    op.execute("ALTER TABLE evidence_items ADD COLUMN IF NOT EXISTS entity_type VARCHAR(32) NULL;")
    op.execute("ALTER TABLE evidence_items ADD COLUMN IF NOT EXISTS entity_id UUID NULL;")
    op.execute(
        "ALTER TABLE evidence_items "
        "ADD COLUMN IF NOT EXISTS confidence DOUBLE PRECISION NOT NULL DEFAULT 1.0;"
    )

    op.execute(
        """
        UPDATE evidence_items
        SET entity_type = COALESCE(entity_type, 'creator'),
            entity_id = COALESCE(entity_id, creator_id),
            source_type = COALESCE(source_type, evidence_type);
        """
    )
    op.execute("ALTER TABLE evidence_items ALTER COLUMN entity_type SET NOT NULL;")
    op.execute("ALTER TABLE evidence_items ALTER COLUMN entity_id SET NOT NULL;")

    if not _index_exists("evidence_items", "ix_evidence_items_entity_type_entity_id"):
        op.execute(
            """
            CREATE INDEX ix_evidence_items_entity_type_entity_id
                ON evidence_items (entity_type, entity_id);
            """
        )


def downgrade() -> None:
    """Downgrade is intentionally not implemented for the spec-alignment migration."""

    raise NotImplementedError(
        "Downgrade fuer die Week-2-Schema-Angleichung ist absichtlich nicht implementiert."
    )
