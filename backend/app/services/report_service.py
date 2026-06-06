"""Report service.

Two responsibilities:

1. **CRUD** for ``Report`` rows (create / list / get / update / delete /
   archive / publish).
2. **Generation** — wire the deterministic
   :mod:`app.services.report_generator` pipeline into the report
   lifecycle so a freshly-created report immediately has Markdown +
   styled HTML content the FE can display.

Generation is intentionally synchronous because the pipeline is pure
in-memory aggregation over data the AnalysisAgent already persisted.
A typical project (10 documents, 8 analyses) generates in well under a
second; there's no benefit to pushing it onto a background task and
forcing the FE into a polling loop.
"""

from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, defer

from app.models.project import Project
from app.models.report import Report
from app.schemas.report import ReportCreate, ReportUpdate
from app.services.report_generator import generate_report_content
from app.utils.constants import ReportStatus, ReportType
from app.utils.logger import logger


def _generate_and_attach(
    db: Session,
    project: Project,
    report: Report,
) -> None:
    """Run the generator and write ``content`` / ``html_content`` onto
    the report row.

    Generation failures are NEVER propagated to the caller — a missing
    ``content`` should not block report creation. The user can always
    regenerate from the UI later. We log the failure so the developer
    can diagnose it.
    """
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
        # JSONB needs JSON-serializable values. Pydantic gives us a list
        # of ``UUID`` objects, but psycopg2's default JSON encoder doesn't
        # know how to handle ``uuid.UUID`` and raises
        # ``TypeError: Object of type UUID is not JSON serializable``.
        # Coerce to strings here so the column round-trips cleanly. The
        # reverse conversion (str → UUID) happens automatically when the
        # ``ReportResponse`` schema is built.
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
        db.flush()  # populate report.id without committing yet

        # Build initial content from analyses + documents already in the
        # project. Failures are absorbed inside ``_generate_and_attach``.
        _generate_and_attach(db, project, report)

        db.commit()
        db.refresh(report)

        logger.success(f"Report created successfully: {report.id}")

        # Best-effort persistent notification so the user sees the
        # outcome from any page (the create endpoint is sync, so the
        # write is cheap and we wait for it).
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
    """Re-run the generator and overwrite ``content`` / ``html_content``.

    Used by the explicit "Regenerate" button on the report detail page —
    handy after the user has run new analyses and wants the report to
    pick up the fresh data.
    """
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
    """List reports for a project — list-view columns only.

    ``content`` and ``html_content`` (TEXT, often hundreds of KB) are
    deferred so the list payload stays metadata-only. The detail endpoint
    fetches the full report on demand.
    """
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

    # If structural fields change (title / report_type / included_documents)
    # the cached content is stale — wipe it so the next view triggers a
    # regeneration through the explicit endpoint, OR rebuild it inline if
    # the caller did NOT also send a new ``content``. Inline rebuild keeps
    # the FE single-roundtrip on field edits.
    structural_fields = {"title", "report_type", "included_documents"}
    structural_changed = any(k in update_dict for k in structural_fields)
    user_supplied_content = "content" in update_dict or "html_content" in update_dict

    try:
        for key, value in update_dict.items():
            if hasattr(value, "value"):
                value = value.value
            # JSONB serialization quirk: ``included_documents`` arrives
            # from pydantic as ``list[UUID]``, but psycopg2's default
            # JSON encoder can't serialize ``uuid.UUID``. Coerce to
            # strings so the column round-trips cleanly. (We do the
            # same in ``create_report``.)
            if key == "included_documents" and value is not None:
                value = [str(x) for x in value]
            setattr(report, key, value)

        # Auto-regenerate when structural fields changed and the user did
        # not manually override the content.
        if structural_changed and not user_supplied_content:
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


# ── Constants re-exported for routes ────────────────────────────────────────

VALID_REPORT_TYPES = {t.value for t in ReportType}
