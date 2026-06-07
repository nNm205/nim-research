from uuid import UUID
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, defer
from app.models.project import Project
from app.models.report import Report
from app.schemas.report import ReportCreate, ReportUpdate
from app.services.report_generator import generate_report_content
from app.services.report_generator.styles import wrap_html
from app.utils.constants import ReportStatus, ReportType
from app.utils.logger import logger


def _render_user_markdown_to_html(markdown_text: str, title: str) -> str:
    if not markdown_text or not markdown_text.strip():
        return wrap_html(title or "Báo cáo", "")

    try:
        from markdown_it import MarkdownIt

        md = (
            MarkdownIt("commonmark", {"html": False, "breaks": True})
            .enable("table")
            .enable("strikethrough")
        )
        body_html = md.render(markdown_text)
    except Exception as e:
        logger.warning(
            f"Markdown→HTML render failed; falling back to <pre>: {e}"
        )
        from html import escape as _esc
        body_html = f"<pre>{_esc(markdown_text)}</pre>"

    return wrap_html(title or "Báo cáo", body_html)


def _generate_and_attach(
    db: Session,
    project: Project,
    report: Report,
) -> None:
    try:
        included = (
            [UUID(str(x)) for x in (report.included_documents or [])]
            if report.included_documents
            else None
        )
        markdown, html = generate_report_content(
            db=db,
            project=project,
            report_title=report.title,
            report_type=report.report_type,
            included_documents=included,
        )
        report.content = markdown
        report.html_content = html
        logger.info(
            f"Report {report.id} content generated "
            f"(md={len(markdown)} chars, html={len(html)} chars)"
        )
    except Exception as e:
        logger.error(
            f"Report content generation failed for {report.id}: {e}"
        )


def create_report(
    db: Session,
    project_id: UUID,
    report_data: ReportCreate
) -> Report:
    logger.info(f"Creating report for project: {project_id}")

    project = db.scalar(
        select(Project).where(Project.id == project_id)
    )

    if not project:
        logger.warning(f"Project not found: {project_id}")

        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found"
        )

    try:
        included_documents = (
            [str(doc_id) for doc_id in report_data.included_documents]
            if report_data.included_documents
            else None
        )

        report = Report(
            project_id=project_id,
            title=report_data.title,
            report_type=report_data.report_type.value,
            included_documents=included_documents,
            status=ReportStatus.DRAFT.value,
        )

        db.add(report)
        db.flush()

        _generate_and_attach(db, project, report)

        db.commit()
        db.refresh(report)

        logger.success(f"Report created successfully: {report.id}")

        try:
            from app.services.notification_service import (
                CATEGORY_REPORT,
                TYPE_SUCCESS,
                create_notification,
            )

            create_notification(
                db,
                user_id=project.user_id,
                title="Báo cáo đã được tạo",
                message=(
                    f"'{(report.title or '')[:120]}' đã được tạo từ "
                    "Documents + Analysis của dự án."
                ),
                notification_type=TYPE_SUCCESS,
                category=CATEGORY_REPORT,
                entity_id=report.id,
                entity_kind="report",
                project_id=project.id,
            )
        except Exception as e:
            logger.warning(
                f"Failed to write report-created notification: {e}"
            )

        return report

    except Exception as e:
        db.rollback()
        logger.error(f"Report creation failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )


def regenerate_report_content(
    db: Session,
    report: Report,
) -> Report:
    logger.info(f"Regenerating content for report: {report.id}")

    project = db.scalar(
        select(Project).where(Project.id == report.project_id)
    )
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found",
        )

    try:
        included = (
            [UUID(str(x)) for x in (report.included_documents or [])]
            if report.included_documents
            else None
        )
        markdown, html = generate_report_content(
            db=db,
            project=project,
            report_title=report.title,
            report_type=report.report_type,
            included_documents=included,
        )
        report.content = markdown
        report.html_content = html
        db.commit()
        db.refresh(report)
        logger.success(f"Report content regenerated: {report.id}")
        return report
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Report regenerate failed for {report.id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


def get_report_by_id(
    db: Session,
    report_id: UUID
) -> Report:
    logger.info(f"Fetching report: {report_id}")

    report = db.scalar(
        select(Report).where(Report.id == report_id)
    )

    if not report:
        logger.warning(f"Report not found: {report_id}")

        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Report not found"
        )

    return report


def get_project_reports(
    db: Session,
    project_id: UUID,
    *,
    limit: int = 50,
    skip: int = 0,
) -> list[Report]:
    logger.info(f"Fetching reports for project: {project_id}")

    try:
        result = db.execute(
            select(Report)
            .options(
                defer(Report.content),
                defer(Report.html_content),
                defer(Report.included_documents),
            )
            .where(Report.project_id == project_id)
            .order_by(Report.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        reports = list(result.scalars().all())

        logger.info(f"Retrieved {len(reports)} reports for project: {project_id}")

        return reports

    except Exception as e:
        logger.error(f"Failed to fetch reports for project {project_id}: {str(e)}")

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )


def update_report(
    db: Session,
    report: Report,
    update_data: ReportUpdate
) -> Report:
    logger.info(f"Updating report: {report.id}")

    update_dict = update_data.model_dump(exclude_unset=True)
    structural_fields = {"title", "report_type", "included_documents"}
    structural_changed = any(k in update_dict for k in structural_fields)
    content_supplied = "content" in update_dict
    html_supplied = "html_content" in update_dict

    try:
        for key, value in update_dict.items():
            if hasattr(value, "value"):
                value = value.value
           
            if key == "included_documents" and value is not None:
                value = [str(x) for x in value]
            setattr(report, key, value)

        if content_supplied and not html_supplied:
            report.html_content = _render_user_markdown_to_html(
                report.content or "", report.title
            )
            logger.info(
                f"Report {report.id}: re-rendered HTML from edited "
                f"markdown ({len(report.content or '')} chars in, "
                f"{len(report.html_content or '')} chars out)"
            )
        elif structural_changed and not (content_supplied or html_supplied):
            project = db.scalar(
                select(Project).where(Project.id == report.project_id)
            )
            if project is not None:
                _generate_and_attach(db, project, report)

        db.commit()
        db.refresh(report)

        logger.success(f"Report updated successfully: {report.id}")
        return report

    except Exception as e:
        db.rollback()
        logger.error(f"Report update failed for {report.id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


def publish_report(
    db: Session,
    report: Report
) -> Report:
    logger.info(f"Publishing report: {report.id}")

    try:
        report.status = ReportStatus.PUBLISHED.value
        db.commit()
        db.refresh(report)
        logger.success(f"Report published successfully: {report.id}")
        return report
    except Exception as e:
        db.rollback()
        logger.error(f"Report publish failed for {report.id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


def archive_report(
    db: Session,
    report: Report
) -> Report:
    logger.info(f"Archiving report: {report.id}")

    try:
        report.status = ReportStatus.ARCHIVED.value
        db.commit()
        db.refresh(report)
        logger.success(f"Report archived successfully: {report.id}")
        return report
    except Exception as e:
        db.rollback()
        logger.error(f"Report archive failed for {report.id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


def delete_report(
    db: Session,
    report: Report
) -> None:
    logger.info(f"Deleting report: {report.id}")

    try:
        db.delete(report)
        db.commit()
        logger.success(f"Report deleted successfully: {report.id}")
    except Exception as e:
        db.rollback()
        logger.error(f"Report deletion failed for {report.id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )

VALID_REPORT_TYPES = {t.value for t in ReportType}
