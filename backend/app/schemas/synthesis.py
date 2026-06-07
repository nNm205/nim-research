from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, ConfigDict

class SynthesisStartRequest(BaseModel):
    llm_provider: str | None = None
    llm_model: str | None = None

class SynthesisStatusResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    project_id: UUID
    title: str
    synthesis_status: str | None
    synthesis_started_at: datetime | None
    synthesis_completed_at: datetime | None
    synthesis_error: str | None
    synthesis_progress: dict | None = None

class SynthesisResultResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    project_id: UUID
    title: str
    synthesis_status: str | None
    synthesis_metadata: dict | None
    synthesis_started_at: datetime | None
    synthesis_completed_at: datetime | None
    synthesis_error: str | None
