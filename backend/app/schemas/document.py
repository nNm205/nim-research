import uuid 
from pydantic import BaseModel
from datetime import datetime

class DocumentCreate(BaseModel):
    title: str
    source_url: str | None = None
    source_type: str | None = None
    content: str | None = None

class DocumentUpdate(BaseModel):
    title: str | None = None
    source_url: str | None = None
    source_type: str | None = None
    content: str | None = None
    processed: bool | None = None
    relevance_score: float | None = None

class DocumentResponse(BaseModel):
    """Detail-view document response — includes full ``content``."""

    id: uuid.UUID
    project_id: uuid.UUID
    title: str
    source_url: str | None
    source_type: str | None
    content: str | None
    file_path: str | None
    processed: bool
    relevance_score: float | None
    created_at: datetime

    class Config:
        from_attributes = True


class DocumentListItemResponse(BaseModel):
    """Compact document row for list endpoints — no full text content.

    The list view (project documents page) doesn't render ``content``; it
    only shows title + source + processed flag. Excluding ``content`` here
    saves megabytes per request when a project has many large PDFs.
    """

    id: uuid.UUID
    project_id: uuid.UUID
    title: str
    source_url: str | None
    source_type: str | None
    file_path: str | None
    processed: bool
    relevance_score: float | None
    created_at: datetime

    class Config:
        from_attributes = True

class URLIngestRequest(BaseModel):
    url: str
    source_type: str = "web"  # "web" | "academic"
    embedding_provider: str | None = None   # override default provider
    embedding_model: str | None = None      # override default model


class SearchResultIngestRequest(BaseModel):
    """Body for POST /projects/{project_id}/documents/ingest-search-result.

    Identifies a SearchResult row to ingest into the project. The server
    locates a downloadable PDF for the result (Unpaywall / arXiv / page
    scrape) and falls back to ingesting the landing page HTML.
    """

    result_id: uuid.UUID
    embedding_provider: str | None = None
    embedding_model: str | None = None
