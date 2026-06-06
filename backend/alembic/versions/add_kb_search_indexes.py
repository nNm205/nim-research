"""Add pg_trgm GIN indexes for KB article search.

Revision ID: add_kb_search_001
Revises: add_perf_indexes_001
Create Date: 2026-06-04 22:30:00.000000

The KB list endpoint runs ``ILIKE '%term%'`` on three columns
(title / excerpt / content). Without indexes that's a sequential scan +
substring match on the full TEXT for every row.

pg_trgm splits each value into trigrams and a GIN index over the trigrams
turns ``%foo%`` lookups into index seeks. We index ``content`` too — it's
TOAST-large, but the GIN index doesn't store the original value, only
trigrams, so the size cost is bounded.

We use IF NOT EXISTS so re-running the migration on a partially-applied
DB stays safe.
"""
from alembic import op


revision = "add_kb_search_001"
down_revision = "add_perf_indexes_001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")

    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_kb_articles_title_trgm "
        "ON knowledge_base_articles USING gin (title gin_trgm_ops)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_kb_articles_excerpt_trgm "
        "ON knowledge_base_articles USING gin (excerpt gin_trgm_ops)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_kb_articles_content_trgm "
        "ON knowledge_base_articles USING gin (content gin_trgm_ops)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_kb_articles_content_trgm")
    op.execute("DROP INDEX IF EXISTS idx_kb_articles_excerpt_trgm")
    op.execute("DROP INDEX IF EXISTS idx_kb_articles_title_trgm")
    # Don't drop the extension on downgrade — other code may rely on it.
