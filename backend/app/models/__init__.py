"""SQLAlchemy ORM model re-exports.

Importing this module triggers ``Base.metadata`` registration for every
table — alembic's ``env.py`` relies on that side effect for autogenerate.
"""

from app.models.analysis import DocumentAnalysis
from app.models.chunk_embedding import ChunkEmbedding
from app.models.document import Document
from app.models.document_chunk import DocumentChunk
from app.models.knowledge_base import (
    KnowledgeBaseArticle,
    KnowledgeBaseSubmission,
)
from app.models.notification import Notification
from app.models.project import Project
from app.models.report import Report
from app.models.research import ResearchSession, SearchResult
from app.models.user import User

__all__ = [
    "ChunkEmbedding",
    "Document",
    "DocumentAnalysis",
    "DocumentChunk",
    "KnowledgeBaseArticle",
    "KnowledgeBaseSubmission",
    "Notification",
    "Project",
    "Report",
    "ResearchSession",
    "SearchResult",
    "User",
]
