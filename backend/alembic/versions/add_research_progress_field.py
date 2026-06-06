"""Add progress JSONB column to research_sessions for live agent status.

The new column mirrors ``document_analyses.progress`` — it stores the
``ResearchProgressTracker`` state so the frontend can render a live
stepper for ordinary research sessions AND for auto-research pipelines
(which produce a single ResearchSession row spanning four stages).

Revision ID: add_research_progress_001
Revises: add_kb_search_001
Create Date: 2026-06-05 17:00:00.000000
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "add_research_progress_001"
down_revision = "add_kb_search_001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "research_sessions",
        sa.Column(
            "progress",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("research_sessions", "progress")
