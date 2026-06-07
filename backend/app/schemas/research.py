from uuid import UUID
from datetime import datetime
from typing import Optional, Any
from pydantic import BaseModel, Field, ConfigDict
from app.utils.constants import ResearchStatus, SearchType, SearchSource

class ResearchCreate(BaseModel):
    query: str = Field(..., min_length=3, max_length=1000)
    max_results: int = Field(default=10, ge=1, le=50)

class AutoResearchCreate(BaseModel):
    query: str = Field(..., min_length=3, max_length=1000)
    max_results: int = Field(default=10, ge=1, le=50)
    max_documents: int = Field(default=3, ge=1, le=5)
    embedding_provider: Optional[str] = None
    embedding_model: Optional[str] = None
    llm_provider: Optional[str] = None
    llm_model: Optional[str] = None
    auto_report: bool = False
    auto_synthesize: bool = False
    auto_qa: bool = False
    report_type: Optional[str] = None 

class SearchResultBase(BaseModel):
    title: str
    url: str
    snippet: Optional[str] = None
    content_preview: Optional[str] = None
    source: SearchSource
    search_type: SearchType
    authors: Optional[list[str]] = None
    published_at: Optional[datetime] = None
    rank: Optional[int] = None
    retrieval_score: Optional[float] = None
    relevance_score: Optional[float] = None
    doi: Optional[str] = None
    pdf_url: Optional[str] = None
    source_id: Optional[str] = None
    search_query: Optional[str] = None
    is_selected: Optional[bool] = False
    embedding_id: Optional[str] = None
    raw_metadata: Optional[dict[str, Any]] = None

class SearchResultResponse(SearchResultBase):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    research_session_id: UUID
    document_id: Optional[UUID] = None
    created_at: datetime

class ResearchResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    project_id: UUID
    query: str
    status: ResearchStatus
    results_count: int
    started_at: datetime
    completed_at: datetime | None
    error_message: str | None

class ResearchStatusResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    status: ResearchStatus
    results_count: int
    started_at: datetime
    completed_at: datetime | None
    error_message: str | None
    progress: dict[str, Any] | None = None

class ResearchResultsResponse(BaseModel):
    session: ResearchResponse
    results: list[SearchResultResponse]

class ResearchHistoryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    query: str
    status: ResearchStatus
    results_count: int
    started_at: datetime
    completed_at: datetime | None
    error_message: str | None
    progress: dict[str, Any] | None = None
