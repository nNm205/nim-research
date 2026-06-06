"""Report endpoints.

Endpoints:

  POST   /projects/{project_id}/reports                — create + auto-generate
  GET    /projects/{project_id}/reports                — list (metadata only)
  GET    /reports/{report_id}                          — full detail (HTML/MD)
  PUT    /reports/{report_id}                          — edit (auto-regen on
                                                         structural changes)
  DELETE /reports/{report_id}                          — delete
  POST   /reports/{report_id}/regenerate               — re-run the generator
  GET    /reports/{report_id}/download/{format}        — md / html / docx
                                                         (returns a file)

The legacy ``POST /reports/{id}/export`` endpoint is preserved as a
deprecated shim that just redirects callers to the download endpoint.
"""

import re
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.dependencies import get_current_user
from app.models.project import Project
from app.models.user import User
from app.schemas.report import (
    ReportCreate,
    ReportListResponse,
    ReportResponse,
    ReportUpdate,
)
from app.services.project_service import verify_project_ownership
from app.services.report_generator.docx_exporter import generate_report_docx
from app.services.report_service import (
    create_report,
    delete_report,
    get_project_reports,
    get_report_by_id,
    regenerate_report_content,
    update_report,
)

router = APIRouter(prefix="/api/v1", tags=["Reports"])


# ── helpers ─────────────────────────────────────────────────────────────────


def _safe_filename(title: str, *, ext: str) -> str:
    """Convert a free-text title into something safe for ``Content-Disposition``.

    Strips characters that are invalid on Windows / macOS / common HTTP
    parsers, collapses whitespace, and truncates to a sane length so we
    don't blow past header size limits.
    """
    base = (title or "report").strip()
    # Replace path separators / control chars / Windows-illegal chars
    base = re.sub(r'[\\/:*?"<>|\r\n\t]+', " ", base)
    base = re.sub(r"\s+", "_", base).strip("._")
    if not base:
        base = "report"
    return f"{base[:80]}.{ext}"


# ── CRUD endpoints ──────────────────────────────────────────────────────────


@router.post(
    "/projects/{project_id}/reports",
    response_model=ReportResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_new_report(
    project_id: UUID,
    report_data: ReportCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    verify_project_ownership(
        db=db, project_id=project_id, user_id=current_user.id
    )
    return create_report(db=db, project_id=project_id, report_data=report_data)


@router.get(
    "/projects/{project_id}/reports",
    response_model=ReportListResponse,
)
def list_project_reports(
    project_id: UUID,
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    verify_project_ownership(
        db=db, project_id=project_id, user_id=current_user.id
    )
    reports = get_project_reports(
        db=db, project_id=project_id, skip=skip, limit=limit
    )
    return {"reports": reports}


@router.get(
    "/reports/{report_id}",
    response_model=ReportResponse,
)
def get_report_details(
    report_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    report = get_report_by_id(db=db, report_id=report_id)
    verify_project_ownership(
        db=db, project_id=report.project_id, user_id=current_user.id
    )
    return report


@router.put(
    "/reports/{report_id}",
    response_model=ReportResponse,
)
def update_existing_report(
    report_id: UUID,
    report_data: ReportUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    report = get_report_by_id(db=db, report_id=report_id)
    verify_project_ownership(
        db=db, project_id=report.project_id, user_id=current_user.id
    )
    return update_report(db=db, report=report, update_data=report_data)


@router.delete(
    "/reports/{report_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_existing_report(
    report_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    report = get_report_by_id(db=db, report_id=report_id)
    verify_project_ownership(
        db=db, project_id=report.project_id, user_id=current_user.id
    )
    delete_report(db=db, report=report)
    return None


# ── Generation / export ─────────────────────────────────────────────────────


@router.post(
    "/reports/{report_id}/regenerate",
    response_model=ReportResponse,
)
def regenerate_existing_report(
    report_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Re-run the deterministic generator and overwrite report content.

    Useful when fresh analyses have been completed since the report
    was first generated and the user wants the report to pick up the
    new data.
    """
    report = get_report_by_id(db=db, report_id=report_id)
    verify_project_ownership(
        db=db, project_id=report.project_id, user_id=current_user.id
    )
    return regenerate_report_content(db=db, report=report)


@router.post(
    "/reports/{report_id}/export",
    deprecated=True,
)
def export_report(
    report_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Deprecated — kept for backwards compatibility with older FE builds.

    Use ``GET /reports/{report_id}/download/{format}`` instead.
    """
    report = get_report_by_id(db=db, report_id=report_id)
    verify_project_ownership(
        db=db, project_id=report.project_id, user_id=current_user.id
    )
    return {
        "message": "Use GET /api/v1/reports/{id}/download/{format} instead",
        "formats": ["md", "html", "docx"],
    }


_FORMAT_MIME = {
    "md": "text/markdown; charset=utf-8",
    "html": "text/html; charset=utf-8",
    "docx": (
        "application/vnd.openxmlformats-officedocument."
        "wordprocessingml.document"
    ),
}


@router.get("/reports/{report_id}/download/{format}")
def download_report(
    report_id: UUID,
    format: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Download the report as ``.md``, ``.html``, or ``.docx``.

    For ``md`` / ``html`` we return the cached content stored on the
    report row (regenerating it on the fly if it's missing). For
    ``docx`` we render a fresh Word document from the project data via
    :func:`generate_report_docx` — that function reads the analyses + 
    documents directly so it always reflects the latest data.
    """
    fmt = format.lower()
    if fmt not in _FORMAT_MIME:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Format not supported. Use 'md', 'html', or 'docx'.",
        )

    report = get_report_by_id(db=db, report_id=report_id)
    verify_project_ownership(
        db=db, project_id=report.project_id, user_id=current_user.id
    )

    filename = _safe_filename(report.title, ext=fmt)
    headers = {
        "Content-Disposition": f'attachment; filename="{filename}"',
    }

    if fmt == "md":
        content = report.content
        if not content:
            # Cache miss — regenerate inline and persist for next time.
            report = regenerate_report_content(db=db, report=report)
            content = report.content or ""
        return Response(
            content=content,
            media_type=_FORMAT_MIME[fmt],
            headers=headers,
        )

    if fmt == "html":
        content = report.html_content
        if not content:
            report = regenerate_report_content(db=db, report=report)
            content = report.html_content or ""
        return Response(
            content=content,
            media_type=_FORMAT_MIME[fmt],
            headers=headers,
        )

    # fmt == "docx"
    project = db.scalar(
        select(Project).where(Project.id == report.project_id)
    )
    if project is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found",
        )
    included = (
        [UUID(str(x)) for x in (report.included_documents or [])]
        if report.included_documents
        else None
    )
    blob = generate_report_docx(
        db=db,
        project=project,
        report_title=report.title,
        report_type=report.report_type,
        included_documents=included,
    )
    return Response(
        content=blob,
        media_type=_FORMAT_MIME[fmt],
        headers=headers,
    )
