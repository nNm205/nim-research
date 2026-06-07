from uuid import UUID
from datetime import datetime
from typing import Optional, Any
from pydantic import BaseModel, Field, ConfigDict
from app.utils.constants import ResearchStatus, SearchType, SearchSource

class ResearchCreate(BaseModel):
    query: str = Field(..., min_length=3, max_length=1000)
    max_results: int = Field(default=10, ge=1, le=50)


class AutoResearchCreate(BaseModel):
    """Body for the auto-research pipeline.

    Combines search + ingest + analyse in one shot. ``max_documents``
    bounds how many top-ranked results we ingest and analyse. The LLM
    and embedding overrides flow through to the respective downstream
    services.

    Three optional add-on stages run *after* analyse:
      - ``auto_report``      → create a project Report (deterministic)
      - ``auto_synthesize``  → run SynthesisAgent on that Report (LLM)
      - ``auto_qa``          → run QualityAssuranceAgent on that Report (LLM)

    Synthesis and QA implicitly require a Report — the orchestrator
    silently drops them when ``auto_report=False`` to avoid wasting
    LLM calls on a no-op.
    """

    query: str = Field(..., min_length=3, max_length=1000)
    max_results: int = Field(default=10, ge=1, le=50)
    max_documents: int = Field(default=3, ge=1, le=5)

    embedding_provider: Optional[str] = None
    embedding_model: Optional[str] = None
    llm_provider: Optional[str] = None
    llm_model: Optional[str] = None

    # Add-on stages — all default off so existing callers keep the
    # original "search + ingest + analyse" behaviour.
    auto_report: bool = False
    auto_synthesize: bool = False
    auto_qa: bool = False
    report_type: Optional[str] = None  # one of ReportType values; None → default research_summary

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
    # ``progress.mode`` is the only field the FE needs from the history
    # list (to badge auto-research sessions). The full progress JSON is
    # only fetched on the status endpoint to keep history payloads small.
    progress: dict[str, Any] | None = None
