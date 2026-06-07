import asyncio
from uuid import UUID
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import load_only, selectinload
from app.agents.analysis_agent import AnalysisAgent
from app.database.session import AsyncSessionLocal
from app.models.analysis import DocumentAnalysis
from app.models.document import Document
from app.utils.constants import AnalysisStatus
from app.utils.logger import logger

_LIST_COLUMNS = (
    DocumentAnalysis.id,
    DocumentAnalysis.document_id,
    DocumentAnalysis.status,
    DocumentAnalysis.started_at,
    DocumentAnalysis.completed_at,
    DocumentAnalysis.error_message,
    DocumentAnalysis.processed_by,
)
_STATUS_COLUMNS = (
    DocumentAnalysis.id,
    DocumentAnalysis.document_id,
    DocumentAnalysis.status,
    DocumentAnalysis.started_at,
    DocumentAnalysis.completed_at,
    DocumentAnalysis.error_message,
    DocumentAnalysis.progress,
)


async def create_document_analysis(
    db: AsyncSession, document_id: UUID
) -> DocumentAnalysis:
    logger.info(f"Creating analysis for document: {document_id}")

    doc_exists = await db.scalar(
        select(Document.id).where(Document.id == document_id)
    )
    if not doc_exists:
        logger.warning(f"Document not found: {document_id}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Document not found"
        )

    existing = await db.scalar(
        select(DocumentAnalysis.id).where(
            DocumentAnalysis.document_id == document_id
        )
    )
    if existing:
        logger.warning(f"Analysis already exists for document: {document_id}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Document analysis already exists",
        )

    try:
        analysis = DocumentAnalysis(
            document_id=document_id,
            status=AnalysisStatus.PENDING.value,
        )
        db.add(analysis)
        await db.commit()
        await db.refresh(analysis)
        logger.success(f"Document analysis created: {analysis.id}")
        return analysis

    except Exception as e:
        await db.rollback()
        logger.error(f"Document analysis creation failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


async def get_document_analysis_by_id(
    db: AsyncSession,
    analysis_id: UUID,
    *,
    light: bool = False,
    with_document: bool = False,
) -> DocumentAnalysis:
    stmt = select(DocumentAnalysis).where(DocumentAnalysis.id == analysis_id)

    if light:
        stmt = stmt.options(load_only(*_STATUS_COLUMNS))

    if with_document:
        stmt = stmt.options(
            selectinload(DocumentAnalysis.document).load_only(
                Document.id, Document.project_id, Document.title
            )
        )

    analysis = await db.scalar(stmt)
    if analysis is None:
        logger.warning(f"Analysis not found: {analysis_id}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Analysis not found"
        )
    return analysis


async def get_document_analysis_by_document(
    db: AsyncSession,
    document_id: UUID,
    *,
    with_document: bool = False,
) -> DocumentAnalysis:
    stmt = select(DocumentAnalysis).where(
        DocumentAnalysis.document_id == document_id
    )
    if with_document:
        stmt = stmt.options(
            selectinload(DocumentAnalysis.document).load_only(
                Document.id, Document.project_id, Document.title
            )
        )
    analysis = await db.scalar(stmt)
    if analysis is None:
        logger.warning(f"Analysis not found for document: {document_id}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document analysis not found",
        )
    return analysis


async def delete_document_analysis(
    db: AsyncSession, analysis: DocumentAnalysis
) -> None:
    logger.info(f"Deleting analysis: {analysis.id}")
    try:
        await db.delete(analysis)
        await db.commit()
        logger.success(f"Analysis deleted: {analysis.id}")
    except Exception as e:
        await db.rollback()
        logger.error(f"Analysis deletion failed for {analysis.id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


async def get_project_analyses(
    db: AsyncSession, project_id: UUID
) -> list[DocumentAnalysis]:
    logger.info(f"Fetching analyses for project: {project_id}")
    try:
        stmt = (
            select(DocumentAnalysis)
            .options(
                load_only(*_LIST_COLUMNS),
                # We need document.title for the FE list; pull just that.
                selectinload(DocumentAnalysis.document).load_only(
                    Document.id, Document.project_id, Document.title
                ),
            )
            .join(Document, DocumentAnalysis.document_id == Document.id)
            .where(Document.project_id == project_id)
            .order_by(DocumentAnalysis.started_at.desc())
        )
        result = await db.execute(stmt)
        analyses = list(result.scalars().all())
        logger.success(
            f"Found {len(analyses)} analyses for project: {project_id}"
        )
        return analyses

    except Exception as e:
        logger.error(
            f"Failed to fetch analyses for project {project_id}: {e}"
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


async def get_user_analyses(
    db: AsyncSession, user_id: UUID
) -> list[DocumentAnalysis]:
    from app.models.project import Project

    logger.info(f"Fetching analyses for user: {user_id}")
    try:
        stmt = (
            select(DocumentAnalysis)
            .options(
                load_only(*_LIST_COLUMNS),
                selectinload(DocumentAnalysis.document).load_only(
                    Document.id, Document.project_id, Document.title
                ),
            )
            .join(Document, DocumentAnalysis.document_id == Document.id)
            .join(Project, Project.id == Document.project_id)
            .where(Project.user_id == user_id)
            .order_by(DocumentAnalysis.started_at.desc())
        )
        result = await db.execute(stmt)
        analyses = list(result.scalars().all())
        logger.success(
            f"Found {len(analyses)} analyses for user: {user_id}"
        )
        return analyses

    except Exception as e:
        logger.error(f"Failed to fetch analyses for user {user_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


async def _run_agent_in_background(
    analysis_id: UUID,
    llm_provider: str | None = None,
    llm_model: str | None = None,
) -> None:
    try:
        async with AsyncSessionLocal() as db:
            agent = AnalysisAgent(
                db,
                llm_provider=llm_provider,
                llm_model=llm_model,
            )
            await agent.run(analysis_id)
    except Exception as e:
        logger.error(f"Background analysis task failed for {analysis_id}: {e}")

_BACKGROUND_TASKS: set[asyncio.Task] = set()


def dispatch_analysis_agent(
    analysis_id: UUID,
    llm_provider: str | None = None,
    llm_model: str | None = None,
) -> None:
    try:
        task = asyncio.create_task(
            _run_agent_in_background(
                analysis_id,
                llm_provider=llm_provider,
                llm_model=llm_model,
            )
        )
        _BACKGROUND_TASKS.add(task)
        task.add_done_callback(_BACKGROUND_TASKS.discard)
    except Exception as e:
        logger.error(f"Failed to dispatch analysis agent for {analysis_id}: {e}")
