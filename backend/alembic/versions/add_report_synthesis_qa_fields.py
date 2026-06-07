"""Add synthesis + QA fields to reports for SynthesisAgent and QualityAssuranceAgent.

Revision ID: add_report_syn_qa_001
Revises: add_notifications_001
Create Date: 2026-06-06 10:00:00.000000
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "add_report_syn_qa_001"
down_revision = "add_notifications_001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── Synthesis fields ─────────────────────────────────────────────────
    op.add_column(
        "reports",
        sa.Column("synthesis_status", sa.String(50), nullable=True),
    )
    op.add_column(
        "reports",
        sa.Column(
            "synthesis_progress",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
    )
    op.add_column(
        "reports",
        sa.Column(
            "synthesis_metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
    )
    op.add_column(
        "reports",
        sa.Column(
            "synthesis_started_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )
    op.add_column(
        "reports",
        sa.Column(
            "synthesis_completed_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )
    op.add_column(
        "reports",
        sa.Column("synthesis_error", sa.Text(), nullable=True),
    )

    # ── QA fields ────────────────────────────────────────────────────────
    op.add_column(
        "reports",
        sa.Column("qa_status", sa.String(50), nullable=True),
    )
    op.add_column(
        "reports",
        sa.Column(
            "qa_progress",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
    )
    op.add_column(
        "reports",
        sa.Column(
            "qa_report",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
    )
    op.add_column(
        "reports",
        sa.Column(
            "qa_started_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )
    op.add_column(
        "reports",
        sa.Column(
            "qa_completed_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )
    op.add_column(
        "reports",
        sa.Column("qa_error", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    for col in (
        "qa_error",
        "qa_completed_at",
        "qa_started_at",
        "qa_report",
        "qa_progress",
        "qa_status",
        "synthesis_error",
        "synthesis_completed_at",
        "synthesis_started_at",
        "synthesis_metadata",
        "synthesis_progress",
        "synthesis_status",
    ):
        op.drop_column("reports", col)
