"""Add notifications table

Revision ID: add_notifications_001
Revises: add_research_progress_001
Create Date: 2026-06-06 17:30:00.000000
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "add_notifications_001"
down_revision = "add_research_progress_001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "notifications",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            nullable=False,
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column(
            "notification_type",
            sa.String(length=20),
            nullable=False,
            server_default="info",
        ),
        sa.Column(
            "category",
            sa.String(length=50),
            nullable=False,
            server_default="general",
        ),
        sa.Column(
            "entity_id", postgresql.UUID(as_uuid=True), nullable=True
        ),
        sa.Column("entity_kind", sa.String(length=50), nullable=True),
        sa.Column(
            "project_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("projects.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "is_read",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "idx_notifications_user_created",
        "notifications",
        ["user_id", "created_at"],
    )
    op.create_index(
        "idx_notifications_user_read",
        "notifications",
        ["user_id", "is_read"],
    )
    op.create_index(
        op.f("ix_notifications_id"), "notifications", ["id"], unique=False
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_notifications_id"), table_name="notifications")
    op.drop_index(
        "idx_notifications_user_read", table_name="notifications"
    )
    op.drop_index(
        "idx_notifications_user_created", table_name="notifications"
    )
    op.drop_table("notifications")
