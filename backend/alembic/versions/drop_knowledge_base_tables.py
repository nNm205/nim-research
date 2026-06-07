"""Drop knowledge base tables

Revision ID: drop_kb_001
Revises: add_report_syn_qa_001
Create Date: 2026-06-07 18:00:00.000000

The Knowledge Base feature was retired — the FE pages, routes, and
service layer are gone, so the underlying tables and indexes follow.
The ``is_admin`` column on ``users`` is intentionally kept: it was
introduced alongside KB but is now also consumed by auth flows.

We use ``IF EXISTS`` everywhere so re-running is safe and partially-
applied DBs (e.g. if a previous KB migration was skipped) don't trip
the drop.
"""
from alembic import op


revision = "drop_kb_001"
down_revision = "add_report_syn_qa_001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── Drop KB-specific GIN trigram indexes first ─────────────────────
    op.execute("DROP INDEX IF EXISTS idx_kb_articles_content_trgm")
    op.execute("DROP INDEX IF EXISTS idx_kb_articles_excerpt_trgm")
    op.execute("DROP INDEX IF EXISTS idx_kb_articles_title_trgm")

    # ── Drop submissions (depends on users via FK) ─────────────────────
    op.execute("DROP TABLE IF EXISTS knowledge_base_submissions CASCADE")

    # ── Drop articles ──────────────────────────────────────────────────
    op.execute("DROP TABLE IF EXISTS knowledge_base_articles CASCADE")


def downgrade() -> None:
    """No-op downgrade.

    Recreating the KB tables from scratch isn't useful — the data they
    held has been deleted, and the application code that wrote to them
    is gone too. If the feature is re-introduced later, a fresh
    migration with the new schema is the right move.
    """
    pass
