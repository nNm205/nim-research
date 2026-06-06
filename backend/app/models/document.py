import uuid 
from datetime import datetime, timezone
from typing import Any
from sqlalchemy import (
    String,
    Text,
    Float,
    Boolean,
    ForeignKey,
    DateTime
)
from sqlalchemy.dialects.postgresql import UUID, JSONB, BYTEA 
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database.base import Base 
from app.utils.constants import DocumentSourceType

class Document(Base):
    __tablename__ = "documents"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        index=True,
        default=uuid.uuid4,
    )

    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
    )

    title: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
    )

    source_url: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    source_type: Mapped[str] = mapped_column(
        String(50),
        default=DocumentSourceType.PDF.value 
    )

    content: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    raw_content: Mapped[bytes | None] = mapped_column(
        BYTEA,
        nullable=True,
    )

    document_metadata: Mapped[dict[str, Any] | None] = mapped_column(
        "metadata",
        JSONB,
        nullable=True,
    )

    file_path: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
    )

    relevance_score: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )

    processed: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    # relationships 
    project = relationship(
        "Project",
        back_populates="documents",
    )

    search_results = relationship(
        "SearchResult",
        back_populates="document",
    )

    analysis = relationship(
        "DocumentAnalysis",
        back_populates="document",
        uselist=False,
        cascade="all, delete-orphan",
    )

    chunks = relationship(
        "DocumentChunk",
        back_populates="document",
        cascade="all, delete-orphan"
    )



