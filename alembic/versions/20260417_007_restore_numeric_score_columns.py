"""Restore fixed-point numeric score columns after the temporary float drift."""

from __future__ import annotations

from sqlalchemy import inspect

from alembic import op

revision = "20260417_007"
down_revision = "20260417_006"
branch_labels = None
depends_on = None


def _column_exists(table_name: str, column_name: str) -> bool:
    """Return whether the given column exists in the current schema."""

    bind = op.get_bind()
    inspector = inspect(bind)
    columns = inspector.get_columns(table_name)
    return any(column["name"] == column_name for column in columns)


def upgrade() -> None:
    """Restore canonical NUMERIC precision for score and confidence fields."""

    creator_columns = {
        "avg_engagement_30d",
        "growth_score",
        "niche_fit_score",
        "commercial_score",
        "fraud_score",
        "evidence_coverage_score",
        "email_confidence",
    }
    if any(_column_exists("creators", column_name) for column_name in creator_columns):
        op.execute(
            """
            ALTER TABLE creators
                ALTER COLUMN avg_engagement_30d TYPE NUMERIC(8, 4)
                    USING CASE
                        WHEN avg_engagement_30d IS NULL THEN NULL
                        WHEN ABS(avg_engagement_30d) > 1
                            THEN ROUND((avg_engagement_30d::numeric / 100), 4)
                        ELSE ROUND(avg_engagement_30d::numeric, 4)
                    END,
                ALTER COLUMN growth_score TYPE NUMERIC(6, 4)
                    USING CASE
                        WHEN growth_score IS NULL THEN NULL
                        WHEN ABS(growth_score) > 1 THEN ROUND((growth_score::numeric / 100), 4)
                        ELSE ROUND(growth_score::numeric, 4)
                    END,
                ALTER COLUMN niche_fit_score TYPE NUMERIC(6, 4)
                    USING CASE
                        WHEN niche_fit_score IS NULL THEN NULL
                        WHEN ABS(niche_fit_score) > 1
                            THEN ROUND((niche_fit_score::numeric / 100), 4)
                        ELSE ROUND(niche_fit_score::numeric, 4)
                    END,
                ALTER COLUMN commercial_score TYPE NUMERIC(6, 4)
                    USING CASE
                        WHEN commercial_score IS NULL THEN NULL
                        WHEN ABS(commercial_score) > 1
                            THEN ROUND((commercial_score::numeric / 100), 4)
                        ELSE ROUND(commercial_score::numeric, 4)
                    END,
                ALTER COLUMN fraud_score TYPE NUMERIC(6, 4)
                    USING CASE
                        WHEN fraud_score IS NULL THEN NULL
                        WHEN ABS(fraud_score) > 1 THEN ROUND((fraud_score::numeric / 100), 4)
                        ELSE ROUND(fraud_score::numeric, 4)
                    END,
                ALTER COLUMN evidence_coverage_score TYPE NUMERIC(6, 4)
                    USING CASE
                        WHEN evidence_coverage_score IS NULL THEN NULL
                        WHEN ABS(evidence_coverage_score) > 1
                            THEN ROUND((evidence_coverage_score::numeric / 100), 4)
                        ELSE ROUND(evidence_coverage_score::numeric, 4)
                    END,
                ALTER COLUMN email_confidence TYPE NUMERIC(6, 4)
                    USING CASE
                        WHEN email_confidence IS NULL THEN NULL
                        WHEN ABS(email_confidence) > 1
                            THEN ROUND((email_confidence::numeric / 100), 4)
                        ELSE ROUND(email_confidence::numeric, 4)
                    END;
            """
        )

    if _column_exists("creator_content", "sponsor_probability"):
        op.execute(
            """
            ALTER TABLE creator_content
                ALTER COLUMN sponsor_probability TYPE NUMERIC(6, 4)
                    USING CASE
                        WHEN sponsor_probability IS NULL THEN NULL
                        WHEN ABS(sponsor_probability) > 1
                            THEN ROUND((sponsor_probability::numeric / 100), 4)
                        ELSE ROUND(sponsor_probability::numeric, 4)
                    END;
            """
        )

    if _column_exists("evidence_items", "confidence"):
        op.execute(
            """
            ALTER TABLE evidence_items
                ALTER COLUMN confidence TYPE NUMERIC(6, 4)
                    USING CASE
                        WHEN confidence IS NULL THEN NULL
                        WHEN ABS(confidence) > 1 THEN ROUND((confidence::numeric / 100), 4)
                        ELSE ROUND(confidence::numeric, 4)
                    END;
            """
        )


def downgrade() -> None:
    """Downgrade is intentionally not implemented for the precision repair."""

    raise NotImplementedError(
        "Downgrade fuer die Score-Precision-Reparatur ist absichtlich nicht implementiert."
    )
