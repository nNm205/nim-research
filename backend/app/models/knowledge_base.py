import uuid 
from datetime import datetime, timezone
from sqlalchemy import (
    String,
    Text,
    DateTime,
    Index,
    ForeignKey
)
from sqlalchemy.dialects.postgresql import UUID, ARRAY
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database.base import Base

class KnowledgeBaseArticle(Base):
    __tablename__ = "knowledge_base_articles"

    __table_args__ = (
        Index("idx_kb_articles_category", "category"),
        Index("idx_kb_articles_created_at", "created_at"),
        Index("idx_kb_articles_status", "status"),
        Index("idx_kb_articles_created_by", "created_by"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        index=True,
        default=uuid.uuid4
    )

    title: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
        index=True
    )

    excerpt: Mapped[str] = mapped_column(
        Text,
        nullable=False
    )

    content: Mapped[str] = mapped_column(
        Text,
        nullable=False
    )

    category: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True
    )

    tags: Mapped[list[str] | None] = mapped_column(
        ARRAY(String),
        nullable=True
    )

    status: Mapped[str] = mapped_column(
        String(50),
        default="published",
        index=True
    )

    views: Mapped[int] = mapped_column(
        default=0
    )

    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        index=True
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc)
    )

    # relationships
    creator = relationship(
        "User",
        foreign_keys=[created_by],
    )


class KnowledgeBaseSubmission(Base):
    __tablename__ = "knowledge_base_submissions"

    __table_args__ = (
        Index("idx_kb_submissions_status", "status"),
        Index("idx_kb_submissions_created_by", "created_by"),
        Index("idx_kb_submissions_created_at", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        index=True,
        default=uuid.uuid4
    )

    title: Mapped[str] = mapped_column(
        String(500),
        nullable=False
    )

    excerpt: Mapped[str] = mapped_column(
        Text,
        nullable=False
    )

    content: Mapped[str] = mapped_column(
        Text,
        nullable=False
    )

    category: Mapped[str] = mapped_column(
        String(100),
        nullable=False
    )

    tags: Mapped[list[str] | None] = mapped_column(
        ARRAY(String),
        nullable=True
    )

    status: Mapped[str] = mapped_column(
        String(50),
        default="pending",
        index=True
    )

    created_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    rejection_reason: Mapped[str | None] = mapped_column(
        Text,
        nullable=True
    )

    reviewed_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True
    )

    reviewed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        index=True
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc)
    )

    # relationships
    creator = relationship(
        "User",
        foreign_keys=[created_by],
    )

    reviewer = relationship(
        "User",
        foreign_keys=[reviewed_by],
    )
