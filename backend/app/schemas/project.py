from pydantic import BaseModel, Field, model_validator
from uuid import UUID
from datetime import datetime
from typing import Optional, Any


class ProjectCreate(BaseModel):
    name: str = Field(..., min_length=3, max_length=255)
    description: Optional[str] = None
    topic: Optional[str] = None
    research_scope: Optional[str] = None


class ProjectUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    topic: Optional[str] = None
    research_scope: Optional[str] = None
    status: Optional[str] = None
    is_archived: Optional[bool] = None


class ProjectResponse(BaseModel):
    id: UUID
    user_id: UUID
    name: str
    description: Optional[str]
    topic: Optional[str]
    research_scope: Optional[str]
    status: str
    is_archived: bool
    created_at: datetime
    updated_at: datetime
    document_count: int = 0
    research_session_count: int = 0
    analysis_count: int = 0
    report_count: int = 0

    model_config = {"from_attributes": True}

    @model_validator(mode="before")
    @classmethod
    def populate_counts(cls, data: Any) -> Any:
        if isinstance(data, dict):
            return data

        result = {}

        for field in ["id", "user_id", "name", "description", "topic",
                      "research_scope", "status", "is_archived",
                      "created_at", "updated_at"]:
            result[field] = getattr(data, field, None)

        for attr, key in [
            ("_document_count", "document_count"),
            ("_research_session_count", "research_session_count"),
            ("_analysis_count", "analysis_count"),
            ("_report_count", "report_count"),
        ]:
            value = getattr(data, attr, None)
            result[key] = int(value) if value is not None else 0

        return result
