"""Public schema re-exports.

Convenience layer so callers can ``from app.schemas import ProjectResponse``
without remembering each file. Add new top-level schemas here when you
introduce them.
"""

from app.schemas.analysis import (
    AnalysisStatusResponse,
    DocumentAnalysisResponse,
)
from app.schemas.document import (
    DocumentCreate,
    DocumentResponse,
    DocumentUpdate,
)
from app.schemas.project import (
    ProjectCreate,
    ProjectResponse,
    ProjectUpdate,
)
from app.schemas.qa import (
    QAReportResponse,
    QAStartRequest,
    QAStatusResponse,
)
from app.schemas.report import (
    ReportCreate,
    ReportListResponse,
    ReportResponse,
    ReportUpdate,
)
from app.schemas.research import (
    ResearchCreate,
    ResearchResponse,
    ResearchResultsResponse,
    ResearchStatusResponse,
    SearchResultResponse,
)
from app.schemas.synthesis import (
    SynthesisResultResponse,
    SynthesisStartRequest,
    SynthesisStatusResponse,
)
from app.schemas.user import (
    UserLogin,
    UserRegister,
    UserResponse,
)

__all__ = [
    # analysis
    "AnalysisStatusResponse",
    "DocumentAnalysisResponse",
    # document
    "DocumentCreate",
    "DocumentResponse",
    "DocumentUpdate",
    # project
    "ProjectCreate",
    "ProjectResponse",
    "ProjectUpdate",
    # qa
    "QAReportResponse",
    "QAStartRequest",
    "QAStatusResponse",
    # report
    "ReportCreate",
    "ReportListResponse",
    "ReportResponse",
    "ReportUpdate",
    # research
    "ResearchCreate",
    "ResearchResponse",
    "ResearchResultsResponse",
    "ResearchStatusResponse",
    "SearchResultResponse",
    # synthesis
    "SynthesisResultResponse",
    "SynthesisStartRequest",
    "SynthesisStatusResponse",
    # user
    "UserLogin",
    "UserRegister",
    "UserResponse",
]
