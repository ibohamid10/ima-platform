"""Add week-3 niche, brand, match, and suppression foundations."""

from __future__ import annotations

from sqlalchemy import inspect

from alembic import op

revision = "20260418_010"
down_revision = "20260418_009"
branch_labels = None
depends_on = None


def _table_exists(table_name: str) -> bool:
    """Return whether the given table exists in the current schema."""

    bind = op.get_bind()
    inspector = inspect(bind)
    return table_name in inspector.get_table_names()


def _column_exists(table_name: str, column_name: str) -> bool:
    """Return whether the given column exists in the current schema."""

    bind = op.get_bind()
    inspector = inspect(bind)
    if table_name not in inspector.get_table_names():
        return False
    columns = inspector.get_columns(table_name)
    return any(column["name"] == column_name for column in columns)


def upgrade() -> None:
    """Create week-3 schema primitives for niches, brands, matching, and suppression."""

    if not _table_exists("brands"):
        op.execute(
            """
            CREATE TABLE brands (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                name VARCHAR(255) NOT NULL,
                domain VARCHAR(255) NOT NULL,
                category VARCHAR(128) NULL,
                niche_ids JSONB NOT NULL DEFAULT '[]'::jsonb,
                geo_markets JSONB NOT NULL DEFAULT '[]'::jsonb,
                spend_intent_score NUMERIC(6, 4) NULL,
                branded_content_score NUMERIC(6, 4) NULL,
                hiring_signal_score NUMERIC(6, 4) NULL,
                creator_program_score NUMERIC(6, 4) NULL,
                contact_email VARCHAR(255) NULL,
                influencer_contact_email VARCHAR(255) NULL,
                contact_confidence NUMERIC(6, 4) NULL,
                website_snapshot_uri TEXT NULL,
                consent_basis VARCHAR(64) NULL,
                last_seen_at TIMESTAMPTZ NULL,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            );
            """
        )
        op.execute("CREATE UNIQUE INDEX ix_brands_domain ON brands (domain);")
        op.execute("CREATE INDEX ix_brands_category ON brands (category);")
        op.execute("CREATE INDEX ix_brands_spend_intent_score ON brands (spend_intent_score);")
        op.execute("CREATE INDEX ix_brands_niche_ids_gin ON brands USING GIN (niche_ids);")

    if not _table_exists("creator_niche_scores"):
        op.execute(
            """
            CREATE TABLE creator_niche_scores (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                creator_id UUID NOT NULL REFERENCES creators(id) ON DELETE CASCADE,
                niche_id VARCHAR(64) NOT NULL,
                niche_fit_score NUMERIC(6, 4) NOT NULL,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            );
            """
        )
        op.execute(
            "CREATE UNIQUE INDEX ix_creator_niche_scores_creator_id_niche_id "
            "ON creator_niche_scores (creator_id, niche_id);"
        )
        op.execute(
            "CREATE INDEX ix_creator_niche_scores_niche_id ON creator_niche_scores (niche_id);"
        )
        op.execute(
            "CREATE INDEX ix_creator_niche_scores_niche_fit_score "
            "ON creator_niche_scores (niche_fit_score);"
        )

    if not _table_exists("brand_creator_matches"):
        op.execute(
            """
            CREATE TABLE brand_creator_matches (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                brand_id UUID NOT NULL REFERENCES brands(id) ON DELETE CASCADE,
                creator_id UUID NOT NULL REFERENCES creators(id) ON DELETE CASCADE,
                niche_id VARCHAR(64) NOT NULL,
                match_score NUMERIC(6, 4) NOT NULL,
                niche_fit_component NUMERIC(6, 4) NULL,
                audience_alignment_component NUMERIC(6, 4) NULL,
                commercial_readiness_component NUMERIC(6, 4) NULL,
                brand_spend_intent_component NUMERIC(6, 4) NULL,
                geo_fit_component NUMERIC(6, 4) NULL,
                competitor_penalty_component NUMERIC(6, 4) NULL,
                growth_momentum_component NUMERIC(6, 4) NULL,
                best_angle VARCHAR(255) NULL,
                offer_shape VARCHAR(255) NULL,
                conflict_flags JSONB NULL,
                rationale_json JSONB NULL,
                status VARCHAR(32) NOT NULL DEFAULT 'pending',
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            );
            """
        )
        op.execute(
            "CREATE UNIQUE INDEX ix_brand_creator_matches_brand_creator "
            "ON brand_creator_matches (brand_id, creator_id);"
        )
        op.execute(
            "CREATE INDEX ix_brand_creator_matches_niche_id "
            "ON brand_creator_matches (niche_id);"
        )
        op.execute(
            "CREATE INDEX ix_brand_creator_matches_match_score "
            "ON brand_creator_matches (match_score);"
        )
        op.execute(
            "CREATE INDEX ix_brand_creator_matches_status ON brand_creator_matches (status);"
        )

    for table_name in (
        "suppression_unsubscribe",
        "suppression_hard_bounce",
        "suppression_spam_complaint",
        "suppression_wrong_person",
        "suppression_manual",
    ):
        if _table_exists(table_name):
            continue
        op.execute(
            f"""
            CREATE TABLE {table_name} (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                email VARCHAR(255) NOT NULL,
                entity_type VARCHAR(64) NOT NULL,
                entity_id UUID NULL,
                reason TEXT NULL,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            );
            """
        )
        op.execute(f"CREATE UNIQUE INDEX ix_{table_name}_email ON {table_name} (email);")

    if not _column_exists("evidence_items", "brand_id"):
        op.execute(
            """
            ALTER TABLE evidence_items
            ADD COLUMN brand_id UUID NULL REFERENCES brands(id) ON DELETE CASCADE;
            """
        )
        op.execute("CREATE INDEX ix_evidence_items_brand_id ON evidence_items (brand_id);")

    if _column_exists("evidence_items", "creator_id"):
        op.execute("ALTER TABLE evidence_items ALTER COLUMN creator_id DROP NOT NULL;")


def downgrade() -> None:
    """Drop week-3 brand-side schema primitives."""

    if _column_exists("evidence_items", "brand_id"):
        op.execute("DROP INDEX IF EXISTS ix_evidence_items_brand_id;")
        op.execute("ALTER TABLE evidence_items DROP COLUMN brand_id;")

    for table_name in (
        "suppression_manual",
        "suppression_wrong_person",
        "suppression_spam_complaint",
        "suppression_hard_bounce",
        "suppression_unsubscribe",
        "brand_creator_matches",
        "creator_niche_scores",
        "brands",
    ):
        if _table_exists(table_name):
            op.execute(f"DROP TABLE {table_name} CASCADE;")
