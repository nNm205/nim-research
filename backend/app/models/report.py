import uuid 
from datetime import datetime, timezone
from sqlalchemy import (
    String,
    Text,
    ForeignKey,
    DateTime,
    Index
)
from sqlalchemy.dialects.postgresql import UUID, JSONB 
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database.base import Base 
from app.utils.constants import ReportStatus, ReportType

class Report(Base):
    __tablename__ = "reports"

    __table_args__ = (
        Index("idx_reports_project_id", "project_id"),
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

    title: Mapped[str] = mapped_column(
        String(500),
        nullable=False
    )

    report_type: Mapped[str] = mapped_column(
        String(100),
        nullable=False, 
        default=ReportType.RESEARCH_SUMMARY.value 
    )

    content: Mapped[str | None] = mapped_column(
        Text,
        nullable=True
    )

    html_content: Mapped[str | None] = mapped_column(
        Text,
        nullable=True
    )

    included_documents: Mapped[list | None] = mapped_column(
        JSONB,
        nullable=True 
    )

    status: Mapped[str] = mapped_column(
        String(50),
        default=ReportStatus.DRAFT.value 
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc)
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc)
    )

    # relationships
    project = relationship(
        "Project",
        back_populates="reports",
    )