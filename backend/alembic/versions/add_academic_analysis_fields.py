"""Add academic analysis fields to document_analyses

Revision ID: add_academic_analysis_001
Revises: add_analysis_agent_001
Create Date: 2026-06-01 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "add_academic_analysis_001"
down_revision = "add_analysis_agent_001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Research contribution — what's new vs prior work
    op.add_column(
        "document_analyses",
        sa.Column("research_contribution", sa.Text(), nullable=True),
    )
    # Critical assessment — strengths and weaknesses of methodology
    op.add_column(
        "document_analyses",
        sa.Column("critical_assessment", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
    # Research questions — main questions the paper addresses
    op.add_column(
        "document_analyses",
        sa.Column("research_questions", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
    # Evidence quality — type and quality of evidence used
    op.add_column(
        "document_analyses",
        sa.Column("evidence_quality", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
    # Citation context — papers cited and why
    op.add_column(
        "document_analyses",
        sa.Column("citation_context", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("document_analyses", "citation_context")
    op.drop_column("document_analyses", "evidence_quality")
    op.drop_column("document_analyses", "research_questions")
    op.drop_column("document_analyses", "critical_assessment")
    op.drop_column("document_analyses", "research_contribution")
