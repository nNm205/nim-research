"""Schemas for the QualityAssuranceAgent endpoints."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class QAStartRequest(BaseModel):
    """Optional LLM overrides for a QA run."""
    llm_provider: str | None = None
    llm_model: str | None = None


class QAStatusResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    project_id: UUID
    title: str
    qa_status: str | None
    qa_started_at: datetime | None
    qa_completed_at: datetime | None
    qa_error: str | None
    qa_progress: dict | None = None


class QAReportResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    project_id: UUID
    title: str
    qa_status: str | None
    qa_report: dict | None
    qa_started_at: datetime | None
    qa_completed_at: datetime | None
    qa_error: str | None
