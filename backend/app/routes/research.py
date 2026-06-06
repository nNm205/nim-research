from uuid import UUID
from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.database.session import get_async_db
from app.schemas.research import (
    ResearchCreate,
    AutoResearchCreate,
    ResearchResponse,
    ResearchStatusResponse,
    ResearchResultsResponse,
    ResearchHistoryResponse,
)
from app.services.project_service import verify_project_ownership_async
from app.services.research_service import (
    create_research_session,
    get_research_session_by_id,
    get_project_research_sessions,
    dispatch_research_agent,
)
from app.services.auto_research_service import dispatch_auto_research
from app.dependencies import get_current_user
from app.models.user import User

router = APIRouter(prefix="/api/v1", tags=["Research"])


@router.post(
    "/projects/{project_id}/research",
    response_model=ResearchResponse,
    status_code=status.HTTP_201_CREATED
)
async def start_research_session(
    project_id: UUID,
    research_data: ResearchCreate,
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(get_current_user)
):
    await verify_project_ownership_async(
        db=db,
        project_id=project_id,
        user_id=current_user.id
    )

    research_session = await create_research_session(
        db=db,
        project_id=project_id,
        research_data=research_data
    )

    dispatch_research_agent(research_session.id)

    return research_session


@router.post(
    "/projects/{project_id}/auto-research",
    response_model=ResearchResponse,
    status_code=status.HTTP_201_CREATED,
)
async def start_auto_research(
    project_id: UUID,
    payload: AutoResearchCreate,
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(get_current_user),
):
    """Kick off the full auto-research pipeline.

    Stages run in the background after the response is returned:

      1. Search arXiv / Google Scholar / Semantic Scholar.
      2. Ingest top ``max_documents`` results into this project.
      3. Run AnalysisAgent on each successfully-ingested document.

    The response carries the ``ResearchSession`` row created for the
    search stage; the FE polls it for ``status`` and follows up with
    project ``documents`` / ``analyses`` endpoints to see results
    appear as the pipeline progresses.
    """
    await verify_project_ownership_async(
        db=db, project_id=project_id, user_id=current_user.id
    )

    # Reuse the existing helper to create the ResearchSession row.
    research_session = await create_research_session(
        db=db,
        project_id=project_id,
        research_data=ResearchCreate(
            query=payload.query,
            max_results=payload.max_results,
        ),
    )

    dispatch_auto_research(
        research_session_id=research_session.id,
        max_documents=payload.max_documents,
        embedding_provider=payload.embedding_provider,
        embedding_model=payload.embedding_model,
        llm_provider=payload.llm_provider,
        llm_model=payload.llm_model,
    )

    return research_session


@router.get(
    "/projects/{project_id}/research",
    response_model=list[ResearchHistoryResponse],
)
async def get_research_history(
    project_id: UUID,
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(get_current_user)
):
    await verify_project_ownership_async(
        db=db,
        project_id=project_id,
        user_id=current_user.id
    )

    return await get_project_research_sessions(
        db=db,
        project_id=project_id
    )


@router.get(
    "/projects/{project_id}/research/{task_id}",
    response_model=ResearchStatusResponse
)
async def get_research_status(
    project_id: UUID,
    task_id: UUID,
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(get_current_user)
):
    await verify_project_ownership_async(
        db=db,
        project_id=project_id,
        user_id=current_user.id
    )

    research_session = await get_research_session_by_id(
        db=db,
        research_session_id=task_id
    )

    return research_session


@router.get(
    "/research/{task_id}/results",
    response_model=ResearchResultsResponse
)
async def get_research_results(
    task_id: UUID,
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(get_current_user)
):
    research_session = await get_research_session_by_id(
        db=db,
        research_session_id=task_id
    )

    await verify_project_ownership_async(
        db=db,
        project_id=research_session.project_id,
        user_id=current_user.id
    )

    return {
        "session": research_session,
        "results": research_session.search_results
    }


@router.post(
    "/research/{task_id}/save-documents"
)
async def save_research_documents(task_id: UUID):
    return {
        "message": "Save documents endpoint"
    }
