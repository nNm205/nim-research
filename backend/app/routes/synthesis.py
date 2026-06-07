from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.database.session import get_async_db
from app.dependencies import get_current_user
from app.models.user import User
from app.schemas.qa import (
    QAReportResponse,
    QAStartRequest,
    QAStatusResponse,
)
from app.schemas.synthesis import (
    SynthesisResultResponse,
    SynthesisStartRequest,
    SynthesisStatusResponse,
)
from app.services.project_service import verify_project_ownership_async
from app.services.qa_service import (
    dispatch_qa_agent,
    get_report_async as get_report_for_qa,
    mark_report_qa_pending,
)
from app.services.synthesis_service import (
    dispatch_synthesis_agent,
    get_report_async as get_report_for_synthesis,
    mark_report_synthesis_pending,
)
from app.utils.constants import SynthesisStatus
from app.utils.logger import logger


router = APIRouter(prefix="/api/v1", tags=["Synthesis & QA"])

@router.post(
    "/reports/{report_id}/synthesize",
    response_model=SynthesisStatusResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def start_synthesis(
    report_id: UUID,
    body: SynthesisStartRequest = SynthesisStartRequest(),
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(get_current_user),
):
    report = await get_report_for_synthesis(db=db, report_id=report_id)
    await verify_project_ownership_async(
        db=db, project_id=report.project_id, user_id=current_user.id
    )
    if report.synthesis_status == SynthesisStatus.RUNNING.value:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Synthesis is already running for this report",
        )

    report = await mark_report_synthesis_pending(db=db, report=report)
    dispatch_synthesis_agent(
        report.id,
        llm_provider=body.llm_provider,
        llm_model=body.llm_model,
    )
    return report


@router.get(
    "/reports/{report_id}/synthesis/status",
    response_model=SynthesisStatusResponse,
)
async def get_synthesis_status(
    report_id: UUID,
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(get_current_user),
):
    report = await get_report_for_synthesis(db=db, report_id=report_id)
    await verify_project_ownership_async(
        db=db, project_id=report.project_id, user_id=current_user.id
    )
    return report


@router.get(
    "/reports/{report_id}/synthesis",
    response_model=SynthesisResultResponse,
)
async def get_synthesis_result(
    report_id: UUID,
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(get_current_user),
):
    report = await get_report_for_synthesis(db=db, report_id=report_id)
    await verify_project_ownership_async(
        db=db, project_id=report.project_id, user_id=current_user.id
    )
    return report


@router.post(
    "/reports/{report_id}/synthesis/rollback",
    response_model=SynthesisResultResponse,
)
async def rollback_synthesis(
    report_id: UUID,
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(get_current_user),
):
    report = await get_report_for_synthesis(db=db, report_id=report_id)
    await verify_project_ownership_async(
        db=db, project_id=report.project_id, user_id=current_user.id
    )

    meta = report.synthesis_metadata or {}
    if not isinstance(meta, dict) or not (
        meta.get("original_template_md") or meta.get("original_template_html")
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No template snapshot available to rollback to",
        )

    original_md = meta.get("original_template_md")
    original_html = meta.get("original_template_html")

    if isinstance(original_md, str):
        report.content = original_md
    if isinstance(original_html, str):
        report.html_content = original_html

    report.synthesis_status = None
    report.synthesis_error = None
    report.synthesis_metadata = None
    report.synthesis_completed_at = None
    report.synthesis_started_at = None
    report.synthesis_progress = None

    await db.commit()
    await db.refresh(report)
    logger.info(f"Synthesis rollback applied for report {report.id}")
    return report

@router.post(
    "/reports/{report_id}/qa",
    response_model=QAStatusResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def start_qa(
    report_id: UUID,
    body: QAStartRequest = QAStartRequest(),
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(get_current_user),
):
    report = await get_report_for_qa(db=db, report_id=report_id)
    await verify_project_ownership_async(
        db=db, project_id=report.project_id, user_id=current_user.id
    )
    if report.qa_status == "running":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="QA is already running for this report",
        )
    if not (report.content or "").strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Report has no content to QA",
        )

    report = await mark_report_qa_pending(db=db, report=report)
    dispatch_qa_agent(
        report.id,
        llm_provider=body.llm_provider,
        llm_model=body.llm_model,
    )
    return report


@router.get(
    "/reports/{report_id}/qa/status",
    response_model=QAStatusResponse,
)
async def get_qa_status(
    report_id: UUID,
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(get_current_user),
):
    report = await get_report_for_qa(db=db, report_id=report_id)
    await verify_project_ownership_async(
        db=db, project_id=report.project_id, user_id=current_user.id
    )
    return report


@router.get(
    "/reports/{report_id}/qa/report",
    response_model=QAReportResponse,
)
async def get_qa_report(
    report_id: UUID,
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(get_current_user),
):
    report = await get_report_for_qa(db=db, report_id=report_id)
    await verify_project_ownership_async(
        db=db, project_id=report.project_id, user_id=current_user.id
    )
    return report

@router.post(
    "/reports/{report_id}/full-pipeline",
    response_model=SynthesisStatusResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def start_full_pipeline(
    report_id: UUID,
    body: SynthesisStartRequest = SynthesisStartRequest(),
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(get_current_user),
):
    report = await get_report_for_synthesis(db=db, report_id=report_id)
    await verify_project_ownership_async(
        db=db, project_id=report.project_id, user_id=current_user.id
    )
    if report.synthesis_status == SynthesisStatus.RUNNING.value:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Synthesis is already running for this report",
        )

    report = await mark_report_synthesis_pending(db=db, report=report)
    dispatch_qa_agent(
        report.id,
        llm_provider=body.llm_provider,
        llm_model=body.llm_model,
        run_synthesis_first=True,
    )
    return report
