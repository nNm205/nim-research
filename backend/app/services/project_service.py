from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.analysis import DocumentAnalysis
from app.models.document import Document
from app.models.project import Project
from app.models.report import Report
from app.models.research import ResearchSession
from app.schemas.project import ProjectCreate, ProjectUpdate
from app.utils.logger import logger


def _annotate_counts(
    db: Session,
    projects: list[Project],
) -> list[Project]:
    """Attach scalar count attributes to each project in the list.

    Counts ``_document_count`` / ``_research_session_count`` /
    ``_analysis_count`` / ``_report_count`` are computed in one query per
    relation (``GROUP BY project_id``) instead of pulling full child
    rows just to call ``len()`` on them.

    ``_analysis_count`` requires a join through ``Document`` because
    DocumentAnalysis has no direct ``project_id`` column — analyses live
    one level removed, attached to a document.
    """
    if not projects:
        return projects

    project_ids = [p.id for p in projects]

    def _count(model, fk):
        rows = db.execute(
            select(fk, func.count(model.id))
            .where(fk.in_(project_ids))
            .group_by(fk)
        ).all()
        return {pid: cnt for pid, cnt in rows}

    doc_counts = _count(Document, Document.project_id)
    rs_counts = _count(ResearchSession, ResearchSession.project_id)
    rep_counts = _count(Report, Report.project_id)

    # Analyses: join through Document. We GROUP BY ``Document.project_id``
    # so the result is keyed by project.
    analysis_rows = db.execute(
        select(Document.project_id, func.count(DocumentAnalysis.id))
        .join(Document, Document.id == DocumentAnalysis.document_id)
        .where(Document.project_id.in_(project_ids))
        .group_by(Document.project_id)
    ).all()
    analysis_counts = {pid: cnt for pid, cnt in analysis_rows}

    for p in projects:
        p._document_count = doc_counts.get(p.id, 0)
        p._research_session_count = rs_counts.get(p.id, 0)
        p._analysis_count = analysis_counts.get(p.id, 0)
        p._report_count = rep_counts.get(p.id, 0)

    return projects


def create_project(
    db: Session,
    user_id: UUID,
    project_data: ProjectCreate
) -> Project:

    logger.info(
        f"Creating project '{project_data.name}' "
        f"for user: {user_id}"
    )

    result = db.execute(
        select(Project).where(
            Project.user_id == user_id,
            Project.name == project_data.name
        )
    )

    existing_project = result.scalar_one_or_none()

    if existing_project:

        logger.warning(
            f"Duplicate project name: "
            f"'{project_data.name}' for user {user_id}"
        )

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Project name already exists"
        )

    try:
        new_project = Project(
            user_id=user_id,
            **project_data.model_dump()
        )

        db.add(new_project)
        db.commit()
        db.refresh(new_project)

        # Newly-created project has zero of every related collection.
        new_project._document_count = 0
        new_project._research_session_count = 0
        new_project._analysis_count = 0
        new_project._report_count = 0

        logger.success(
            f"Project created successfully: "
            f"{new_project.id}"
        )

        return new_project

    except Exception as e:
        db.rollback()

        logger.error(
            f"Project creation failed: {str(e)}"
        )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )


def get_user_projects(
    db: Session,
    user_id: UUID
) -> list[Project]:

    logger.info(
        f"Fetching projects for user: {user_id}"
    )

    try:
        result = db.execute(
            select(Project)
            .where(Project.user_id == user_id)
            .order_by(Project.created_at.desc())
        )

        projects = list(result.scalars().all())
        _annotate_counts(db, projects)

        logger.info(
            f"Retrieved {len(projects)} projects "
            f"for user: {user_id}"
        )

        return projects

    except Exception as e:

        logger.error(
            f"Failed to fetch projects "
            f"for user {user_id}: {str(e)}"
        )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )


def get_project_by_id(
    db: Session,
    project_id: UUID,
    user_id: UUID
) -> Project:

    logger.info(
        f"Fetching project {project_id} "
        f"for user {user_id}"
    )

    result = db.execute(
        select(Project).where(
            Project.id == project_id,
            Project.user_id == user_id
        )
    )

    project = result.scalar_one_or_none()

    if not project:

        logger.warning(
            f"Project not found: {project_id}"
        )

        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found"
        )

    _annotate_counts(db, [project])
    return project


def verify_project_ownership(
    db: Session,
    project_id: UUID,
    user_id: UUID
) -> Project:

    logger.info(
        f"Verifying ownership for project "
        f"{project_id} and user {user_id}"
    )

    result = db.execute(
        select(Project).where(
            Project.id == project_id,
            Project.user_id == user_id
        )
    )

    project = result.scalar_one_or_none()

    if not project:

        logger.warning(
            f"Unauthorized project access attempt. "
            f"Project: {project_id}, User: {user_id}"
        )

        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found"
        )

    return project


def update_project(
    db: Session,
    project: Project,
    update_data: ProjectUpdate
) -> Project:

    logger.info(
        f"Updating project: {project.id}"
    )

    update_dict = update_data.model_dump(
        exclude_unset=True
    )

    try:

        if "name" in update_dict:

            result = db.execute(
                select(Project).where(
                    Project.user_id == project.user_id,
                    Project.name == update_dict["name"],
                    Project.id != project.id
                )
            )

            existing_project = result.scalar_one_or_none()

            if existing_project:

                logger.warning(
                    f"Duplicate project name: "
                    f"{update_dict['name']}"
                )

                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Project name already exists"
                )

        for key, value in update_dict.items():
            setattr(project, key, value)

        db.commit()
        db.refresh(project)

        # Re-annotate counts so the response stays consistent.
        _annotate_counts(db, [project])

        logger.success(
            f"Project updated successfully: "
            f"{project.id}"
        )

        return project

    except HTTPException:
        raise

    except Exception as e:
        db.rollback()

        logger.error(
            f"Project update failed "
            f"for {project.id}: {str(e)}"
        )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )


def delete_project(
    db: Session,
    project: Project
) -> None:

    logger.info(
        f"Deleting project: {project.id}"
    )

    try:
        db.delete(project)
        db.commit()

        logger.success(
            f"Project deleted successfully: "
            f"{project.id}"
        )

    except Exception as e:
        db.rollback()

        logger.error(
            f"Project deletion failed "
            f"for {project.id}: {str(e)}"
        )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )


async def verify_project_ownership_async(
    db,
    project_id: UUID,
    user_id: UUID
) -> Project:
    from sqlalchemy.ext.asyncio import AsyncSession as _AsyncSession

    logger.info(
        f"Verifying ownership for project "
        f"{project_id} and user {user_id}"
    )

    result = await db.execute(
        select(Project).where(
            Project.id == project_id,
            Project.user_id == user_id
        )
    )

    project = result.scalar_one_or_none()

    if not project:
        logger.warning(
            f"Unauthorized project access attempt. "
            f"Project: {project_id}, User: {user_id}"
        )

        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found"
        )

    return project
