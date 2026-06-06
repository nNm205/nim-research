"""Public entry point for the deterministic report generator.

Composes the aggregator + renderers + theme into a single function the
report service consumes.
"""

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
    """Generate ``(markdown, html)`` for a report.

    Pure read-only — does not mutate the DB. The caller is responsible
    for persisting the result on the ``Report`` row.

    Returns:
        ``(markdown_content, html_content)``: the markdown is suitable
        for a ``.md`` download, and the HTML is a fully self-contained
        styled document suitable for in-browser viewing or ``.html``
        download.
    """
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
