"""Add section insights, narrative synthesis, and document outline to document_analyses

Revision ID: add_section_insights_001
Revises: add_academic_analysis_001
Create Date: 2026-06-04 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "add_section_insights_001"
down_revision = "add_academic_analysis_001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Per-section structured insights (list of section insight objects)
    op.add_column(
        "document_analyses",
        sa.Column(
            "section_insights",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
    )
    # Cross-section synthesis (narrative, conflicts, gaps, novelty)
    op.add_column(
        "document_analyses",
        sa.Column(
            "narrative_synthesis",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
    )
    # Document-level outline (title, document_type, main_topics, section list)
    op.add_column(
        "document_analyses",
        sa.Column(
            "document_outline",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("document_analyses", "document_outline")
    op.drop_column("document_analyses", "narrative_synthesis")
    op.drop_column("document_analyses", "section_insights")
