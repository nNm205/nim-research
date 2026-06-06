import uuid 
from datetime import datetime, timezone
from sqlalchemy import (
    String, 
    Text,
    ForeignKey,
    DateTime,
    Index
)
from sqlalchemy.dialects.postgresql import UUID, JSONB, ARRAY
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database.base import Base
from app.utils.constants import AnalysisStatus

class DocumentAnalysis(Base):
    __tablename__ = "document_analyses"

    __table_args__ = (
        Index("idx_document_analyses_document_id", "document_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        index=True,
        default=uuid.uuid4
    )

    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
        unique=True 
    )

    status: Mapped[str] = mapped_column(
        String(50),
        default=AnalysisStatus.PENDING.value 
    )

    summary: Mapped[str | None] = mapped_column(
        Text,
        nullable=True
    )

    key_findings: Mapped[list | None] = mapped_column(
        JSONB,
        nullable=True 
    )

    extracted_entities: Mapped[dict | list | None] = mapped_column(
        JSONB,
        nullable=True
    )

    extracted_tables: Mapped[list | None] = mapped_column(
        JSONB,
        nullable=True 
    )

    keywords: Mapped[list[str] | None] = mapped_column(
        ARRAY(Text),
        nullable=True 
    )

    sentiment: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True
    )

    # ── New fields added for LangGraph AnalysisAgent ──────────────────
    sections: Mapped[list | None] = mapped_column(
        JSONB,
        nullable=True,
        comment="List of detected document sections with type and content"
    )

    methodology: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Extracted methodology description"
    )

    limitations: Mapped[list | None] = mapped_column(
        JSONB,
        nullable=True,
        comment="List of extracted limitations"
    )

    future_work: Mapped[list | None] = mapped_column(
        JSONB,
        nullable=True,
        comment="List of extracted future work items"
    )

    relationships: Mapped[list | None] = mapped_column(
        JSONB,
        nullable=True,
        comment="List of extracted entity relationships (subject, relation, object)"
    )

    metrics: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True,
        comment="Extracted numerical metrics (accuracy, precision, recall, etc.)"
    )

    # ── Academic analysis fields ───────────────────────────────────────
    research_contribution: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="What new contribution this paper makes vs prior work"
    )

    critical_assessment: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True,
        comment="Strengths and weaknesses of methodology, validity, sample"
    )

    research_questions: Mapped[list | None] = mapped_column(
        JSONB,
        nullable=True,
        comment="Main research questions the paper addresses"
    )

    evidence_quality: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True,
        comment="Type and quality of evidence (RCT, observational, etc.)"
    )

    citation_context: Mapped[list | None] = mapped_column(
        JSONB,
        nullable=True,
        comment="Key papers cited and the reason they are cited"
    )

    # ── Section-level deep insights (new pipeline) ─────────────────────
    section_insights: Mapped[list | None] = mapped_column(
        JSONB,
        nullable=True,
        comment="Per-section structured insights: claims, evidence, critique, quotes"
    )

    narrative_synthesis: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True,
        comment="Cross-section synthesis: narrative, conflicts, gaps, novelty"
    )

    document_outline: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True,
        comment="Document-level outline: title, document_type, main_topics, sections"
    )

    progress: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True,
        comment="Live agent progress: current_step, steps[], section_progress, events[]"
    )
    # ──────────────────────────────────────────────────────────────────

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

    processed_by: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True
    )

    # relationships
    document = relationship(
        "Document",
        back_populates="analysis",
    )