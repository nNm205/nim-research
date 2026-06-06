from uuid import UUID
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, defer
from app.models.project import Project
from app.models.report import Report
from app.schemas.report import ReportCreate, ReportUpdate
from app.utils.constants import ReportStatus
from app.utils.logger import logger

def create_report(
    db: Session,
    project_id: UUID,
    report_data: ReportCreate
) -> Report:
    logger.info(f"Creating report for project: {project_id}")

    result = db.execute(
        select(Project).where(
            Project.id == project_id
        )
    )
    project = result.scalar_one_or_none()

    if not project:
        logger.warning(f"Project not found: {project_id}")

        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found"
        )

    try:
        included_documents = report_data.included_documents or None

        report = Report(
            project_id=project_id,
            title=report_data.title,
            report_type=report_data.report_type.value,
            included_documents=included_documents,
            status=ReportStatus.DRAFT.value
        )

        db.add(report)
        db.commit()
        db.refresh(report)

        logger.success(f"Report created successfully: {report.id}")

        return report

    except Exception as e:
        db.rollback()

        logger.error(f"Report creation failed: {str(e)}")

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )

def get_report_by_id(
    db: Session,
    report_id: UUID
) -> Report:
    logger.info(f"Fetching report: {report_id}")

    result = db.execute(
        select(Report).where(
            Report.id == report_id
        )
    )
    report = result.scalar_one_or_none()

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

    try:
        for key, value in update_dict.items():
            if hasattr(value, "value"):
                value = value.value
            
            if key == "included_documents" and value is not None:
                value = value  # keep as list[UUID], JSONB handles serialization

            setattr(report, key, value)

        db.commit()
        db.refresh(report)

        logger.success(f"Report updated successfully: {report.id}")
        return report

    except Exception as e:
        db.rollback()

        logger.error(f"Report update failed for {report.id}: {str(e)}")

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
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
            detail="Internal server error"
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
            detail="Internal server error"
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
            detail="Internal server error"
        )
