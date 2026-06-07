from enum import Enum


class ResearchStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class AnalysisStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class ReportStatus(str, Enum):
    DRAFT = "draft"
    PUBLISHED = "published"
    ARCHIVED = "archived"


class ReportType(str, Enum):
    LITERATURE_REVIEW = "literature_review"
    DATA_ANALYSIS = "data_analysis"
    RESEARCH_SUMMARY = "research_summary"
    CUSTOM = "custom"


class SynthesisStatus(str, Enum):
    """Status of the cross-document SynthesisAgent run on a Report."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class QAStatus(str, Enum):
    """Status of the QualityAssuranceAgent run on a Report."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class QAVerdict(str, Enum):
    """Overall verdict produced by the QualityAssuranceAgent."""
    EXCELLENT = "excellent"     # >= 90
    GOOD = "good"                # 75-89
    NEEDS_REVIEW = "needs_review"  # 60-74
    POOR = "poor"                # < 60


class DocumentSourceType(str, Enum):
    WEB = "web"
    ACADEMIC = "academic"
    UPLOADED = "uploaded"
    PDF = "pdf"


class TaskType(str, Enum):
    RESEARCH = "research"
    ANALYSIS = "analysis"
    REPORT = "report"


class TaskStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class SearchType(str, Enum):
    WEB = "web"
    ACADEMIC = "academic"
    WIKIPEDIA = "wikipedia"
    SEMANTIC = "semantic"
    HYBRID = "hybrid"
    NEWS = "news"
    CODE = "code"


class SearchSource(str, Enum):
    ARXIV = "arxiv"
    GOOGLE_SCHOLAR = "google_scholar"
    SEMANTIC_SCHOLAR = "semantic_scholar"
    WEB = "web"
