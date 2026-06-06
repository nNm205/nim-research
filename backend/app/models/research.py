import uuid
from datetime import datetime, timezone
from sqlalchemy import (
    Float, 
    String,
    Integer,
    ForeignKey,
    DateTime,
    Text,
    Index,
    Boolean,
    Enum 
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database.base import Base
from app.utils.constants import ResearchStatus, SearchType, SearchSource

class ResearchSession(Base):
    __tablename__ = "research_sessions"

    __table_args__ = (
        Index("idx_research_sessions_project_id", "project_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        index=True,
        default=uuid.uuid4
    )

    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False
    )

    query: Mapped[str] = mapped_column(
        String(1000),
        nullable=False
    )

    max_results: Mapped[int] = mapped_column(
        Integer,
        nullable=False, 
        default=10 
    )

    status: Mapped[str] = mapped_column(
        String(50),
        default=ResearchStatus.PENDING.value 
    )

    results_count: Mapped[int] = mapped_column(
        Integer,
        default=0
    )

    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc)
    )

    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True
    )

    error_message: Mapped[str | None] = mapped_column(
        Text,
        nullable=True
    )

    # Live progress (ResearchProgressTracker writes here). Mirrors the
    # ``document_analyses.progress`` JSONB column.
    progress: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True,
    )

    # relationships
    project = relationship(
        "Project",
        back_populates="research_sessions",
        lazy="selectin"
    )

    search_results = relationship(
        "SearchResult",
        back_populates="research_session",
        cascade="all, delete-orphan",
        lazy="selectin"
    )

class SearchResult(Base):
    __tablename__ = "search_results"

    __table_args__ = (
        Index(
            "idx_search_results_research_session_id",
            "research_session_id"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        index=True,
        default=uuid.uuid4
    )

    research_session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "research_sessions.id",
            ondelete="CASCADE"
        ),
        nullable=False
    )

    document_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "documents.id",
            ondelete="SET NULL"
        ),
        nullable=True
    )

    title: Mapped[str] = mapped_column(
        String(500),
        nullable=False
    )

    url: Mapped[str] = mapped_column(
        Text,
        nullable=False
    )

    snippet: Mapped[str | None] = mapped_column(
        Text,
        nullable=True
    )

    content_preview: Mapped[str | None] = mapped_column(
        Text,
        nullable=True
    )

    source: Mapped[SearchSource] = mapped_column(
        Enum(SearchSource, name="search_source_enum"),
        default=SearchSource.WEB,
        nullable=False
    )

    search_type: Mapped[SearchType] = mapped_column(
        Enum(SearchType, name="search_type_enum"),
        default=SearchType.WEB,
        nullable=False
    )

    search_query: Mapped[str | None] = mapped_column(
        Text,
        nullable=True
    )

    source_id: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True
    )

    rank: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True
    )

    authors: Mapped[list[str] | None] = mapped_column(
        JSONB,
        nullable=True
    )

    published_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True
    )

    doi: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True
    )

    pdf_url: Mapped[str | None] = mapped_column(
        Text,
        nullable=True
    )

    retrieval_score: Mapped[float | None] = mapped_column(
        Float,
        nullable=True
    )

    relevance_score: Mapped[float | None] = mapped_column(
        Float,
        nullable=True
    )

    is_selected: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False
    )

    embedding_id: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True
    )

    raw_metadata: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False
    )

    # relationships 
    research_session = relationship(
        "ResearchSession",
        back_populates="search_results",
        lazy="selectin"
    )

    document = relationship(
        "Document",
        back_populates="search_results",
        lazy="selectin"
    )