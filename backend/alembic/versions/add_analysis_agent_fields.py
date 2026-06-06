"""Add LangGraph AnalysisAgent fields to document_analyses

Revision ID: add_analysis_agent_001
Revises: acd48066cb11
Create Date: 2026-06-01 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "add_analysis_agent_001"
down_revision = "acd48066cb11"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "document_analyses",
        sa.Column("sections", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
    op.add_column(
        "document_analyses",
        sa.Column("methodology", sa.Text(), nullable=True),
    )
    op.add_column(
        "document_analyses",
        sa.Column("limitations", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
    op.add_column(
        "document_analyses",
        sa.Column("future_work", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
    op.add_column(
        "document_analyses",
        sa.Column("relationships", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
    op.add_column(
        "document_analyses",
        sa.Column("metrics", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("document_analyses", "metrics")
    op.drop_column("document_analyses", "relationships")
    op.drop_column("document_analyses", "future_work")
    op.drop_column("document_analyses", "limitations")
    op.drop_column("document_analyses", "methodology")
    op.drop_column("document_analyses", "sections")
