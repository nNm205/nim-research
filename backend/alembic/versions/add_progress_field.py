"""Add progress JSONB column to document_analyses for live agent status.

Revision ID: add_progress_001
Revises: 604d16dec77c
Create Date: 2026-06-04 17:00:00.000000
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "add_progress_001"
down_revision = "604d16dec77c"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "document_analyses",
        sa.Column(
            "progress",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("document_analyses", "progress")
