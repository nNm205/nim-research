from uuid import UUID
from datetime import datetime
from pydantic import BaseModel, ConfigDict, computed_field
from app.utils.constants import AnalysisStatus


class AnalysisCreate(BaseModel):
    document_id: UUID
    llm_provider: str | None = None
    llm_model: str | None = None


class AnalysisListItemResponse(BaseModel):
    """Compact analysis row for list endpoints.

    Excludes every heavy JSONB / TEXT column. The frontend list view
    (project analyses, dashboard) only needs status + dates + the document
    title — everything else is fetched on-demand from the detail page.
    """
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    document_id: UUID
    status: AnalysisStatus
    started_at: datetime
    completed_at: datetime | None
    error_message: str | None
    processed_by: str | None

    @computed_field
    @property
    def document_title(self) -> str | None:
        doc = getattr(self, "document", None)
        if doc is None:
            return None
        return getattr(doc, "title", None)

    @computed_field
    @property
    def project_id(self) -> UUID | None:
        """The owning project — derived from the eagerly-loaded document.

        Used by the cross-project Analysis page so the FE can group by
        project without a second round-trip.
        """
        doc = getattr(self, "document", None)
        if doc is None:
            return None
        return getattr(doc, "project_id", None)


class DocumentAnalysisResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    document_id: UUID
    status: AnalysisStatus
    summary: str | None
    key_findings: list | None
    extracted_entities: dict | list | None
    extracted_tables: list | None
    keywords: list[str] | None
    sentiment: str | None
    # New LangGraph fields
    sections: list | None = None
    methodology: str | None = None
    limitations: list | None = None
    future_work: list | None = None
    relationships: list | None = None
    metrics: dict | None = None
    # Academic analysis fields
    research_contribution: str | None = None
    critical_assessment: dict | None = None
    research_questions: list | None = None
    evidence_quality: dict | None = None
    citation_context: list | None = None
    # Section-level deep insights (new pipeline)
    section_insights: list | None = None
    narrative_synthesis: dict | None = None
    document_outline: dict | None = None
    progress: dict | None = None
    # Timestamps & meta
    started_at: datetime
    completed_at: datetime | None
    error_message: str | None
    processed_by: str | None

    @computed_field
    @property
    def document_title(self) -> str | None:
        doc = getattr(self, "document", None)
        if doc is None:
            return None
        return getattr(doc, "title", None)

    @computed_field
    @property
    def project_id(self) -> UUID | None:
        """The owning project — derived from the eagerly-loaded document.

        Exposed so the FE results page can pass ``projectId`` down to
        the inline progress component (which polls the
        per-project status endpoint).
        """
        doc = getattr(self, "document", None)
        if doc is None:
            return None
        return getattr(doc, "project_id", None)


class AnalysisStatusResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    document_id: UUID
    status: AnalysisStatus
    started_at: datetime
    completed_at: datetime | None
    error_message: str | None
    progress: dict | None = None

    @computed_field
    @property
    def document_title(self) -> str | None:
        doc = getattr(self, "document", None)
        if doc is None:
            return None
        return getattr(doc, "title", None)


class AnalysisResultsResponse(DocumentAnalysisResponse):
    pass
