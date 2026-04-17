"""Drop week-2 legacy compatibility columns once canonical fields are live."""

from __future__ import annotations

from sqlalchemy import inspect

from alembic import op

revision = "20260417_006"
down_revision = "20260417_005"
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
    """Drop legacy compatibility fields that are no longer canonical."""

    if _index_exists("evidence_items", "ix_evidence_items_evidence_type"):
        op.execute("DROP INDEX IF EXISTS ix_evidence_items_evidence_type;")

    if _column_exists("creators", "sub_niches"):
        op.execute("ALTER TABLE creators DROP COLUMN sub_niches;")
    if _column_exists("creators", "niche"):
        op.execute("ALTER TABLE creators DROP COLUMN niche;")
    if _column_exists("evidence_items", "evidence_type"):
        op.execute("ALTER TABLE evidence_items DROP COLUMN evidence_type;")


def downgrade() -> None:
    """Recreate dropped compatibility fields for rollback safety."""

    if not _column_exists("creators", "niche"):
        op.execute("ALTER TABLE creators ADD COLUMN niche VARCHAR(64) NULL;")
    if not _column_exists("creators", "sub_niches"):
        op.execute(
            "ALTER TABLE creators ADD COLUMN sub_niches JSONB NOT NULL DEFAULT '[]'::jsonb;"
        )
    if not _column_exists("evidence_items", "evidence_type"):
        op.execute("ALTER TABLE evidence_items ADD COLUMN evidence_type VARCHAR(64) NULL;")
        op.execute(
            "UPDATE evidence_items SET evidence_type = source_type WHERE evidence_type IS NULL;"
        )
        op.execute("ALTER TABLE evidence_items ALTER COLUMN evidence_type SET NOT NULL;")

    if not _index_exists("evidence_items", "ix_evidence_items_evidence_type"):
        op.execute(
            "CREATE INDEX ix_evidence_items_evidence_type ON evidence_items (evidence_type);"
        )
