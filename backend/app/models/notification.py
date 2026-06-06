"""Notification model — persistent, user-scoped task completion alerts.

Each row is a single event the user should be aware of. The agent
pipelines write rows here whenever a long-running task finishes (or
fails) so the user can see the outcome from any page via the bell icon
in the header — no need to camp on the originating page.

Why persistent (DB) instead of websocket-only:
- Survives backend restarts and tab switches.
- Read/unread state is per-user and durable across devices.
- Simpler than websockets given the rest of the app is HTTP-polling.

Categories map 1:1 to the major workflows so the FE can group them:
  - research        — single search session
  - auto_research   — search + ingest + analyse pipeline
  - analysis        — DocumentAnalysis pipeline
  - report          — Report generation / regeneration
  - document        — document ingest (URL / file / search-result)
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base


class Notification(Base):
    __tablename__ = "notifications"

    # We expect to query by ``(user_id, is_read)`` and
    # ``(user_id, created_at)`` more than anything else; both lookups go
    # through the same composite index.
    __table_args__ = (
        Index("idx_notifications_user_created", "user_id", "created_at"),
        Index("idx_notifications_user_read", "user_id", "is_read"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        index=True,
        default=uuid.uuid4,
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Short, human-friendly title. Capped at 200 chars to keep dropdown
    # rows compact.
    title: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
    )

    # Optional secondary message (1-2 sentences). Long-form details
    # (e.g. an error stack) can live in ``error_message`` of the source
    # row, not here.
    message: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    # ``success`` / ``error`` / ``info`` — drives the icon + tint.
    notification_type: Mapped[str] = mapped_column(
        String(20),
        default="info",
        nullable=False,
    )

    # Which workflow produced this notification.
    category: Mapped[str] = mapped_column(
        String(50),
        default="general",
        nullable=False,
    )

    # Source row that the notification points at — used to build the
    # FE deep-link. ``entity_kind`` says how to interpret the id:
    # "analysis", "research", "report", "document", "project".
    entity_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
    )
    entity_kind: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
    )

    # Optional secondary entity for nested deep-links — e.g. an analysis
    # that belongs to a project, so the FE can route to
    # ``/projects/{project_id}/...`` if needed.
    project_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="SET NULL"),
        nullable=True,
    )

    is_read: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    read_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    user = relationship("User")
