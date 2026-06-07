from __future__ import annotations
from uuid import UUID
from sqlalchemy.orm import Session
from app.models.project import Project
from app.services.report_generator.aggregator import build_report_context
from app.services.report_generator.renderers import render
from app.services.report_generator.styles import wrap_html

def generate_report_content(
    db: Session,
    project: Project,
    *,
    report_title: str,
    report_type: str,
    included_documents: list[UUID] | None,
) -> tuple[str, str]:
    ctx = build_report_context(
        db=db,
        project=project,
        report_title=report_title,
        report_type=report_type,
        included_documents=included_documents,
    )
    body_md, body_html = render(ctx)
    full_html = wrap_html(report_title, body_html)
    return body_md, full_html
