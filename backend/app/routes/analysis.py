from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.database.session import get_async_db
from app.dependencies import get_current_user
from app.models.document import Document
from app.models.user import User
from app.schemas.analysis import (
    AnalysisCreate,
    AnalysisListItemResponse,
    DocumentAnalysisResponse,
    AnalysisResultsResponse,
    AnalysisStatusResponse,
)
from app.services.project_service import verify_project_ownership_async
from app.services.analysis_service import (
    create_document_analysis,
    get_document_analysis_by_id,
    get_document_analysis_by_document,
    get_project_analyses,
    get_user_analyses,
    delete_document_analysis,
    dispatch_analysis_agent,
)

router = APIRouter(prefix="/api/v1", tags=["Analysis"])

LLM_PROVIDERS_CATALOG = [
    {
        "value": "gemini",
        "label": "Google Gemini",
        "description": "Gemini API — chính xác cao, free tier 5 RPM",
        "models": [
            {
                "value": "gemini-2.5-flash",
                "label": "Gemini 2.5 Flash",
                "description": "Cân bằng tốc độ và chất lượng — khuyên dùng",
                "recommended": True,
            },
            {
                "value": "gemini-2.5-flash-lite",
                "label": "Gemini 2.5 Flash Lite",
                "description": "Nhanh và rẻ nhất, chất lượng vừa phải",
            },
            {
                "value": "gemini-2.5-pro",
                "label": "Gemini 2.5 Pro",
                "description": "Chất lượng cao nhất, chậm hơn, quota nhỏ",
            },
            {
                "value": "gemini-2.0-flash",
                "label": "Gemini 2.0 Flash",
                "description": "Thế hệ trước, vẫn còn hỗ trợ",
            },
        ],
    },
    {
        "value": "groq",
        "label": "Groq",
        "description": "Inference cực nhanh — free tier 30 RPM",
        "models": [
            {
                "value": "llama-3.3-70b-versatile",
                "label": "Llama 3.3 70B Versatile",
                "description": "Chất lượng cao nhất của Groq",
                "recommended": True,
            },
            {
                "value": "llama-3.1-8b-instant",
                "label": "Llama 3.1 8B Instant",
                "description": "Nhanh nhất, phù hợp tài liệu ngắn",
            },
            {
                "value": "openai/gpt-oss-20b",
                "label": "GPT-OSS 20B",
                "description": "Mô hình mở của OpenAI, chất lượng tốt",
            },
            {
                "value": "openai/gpt-oss-120b",
                "label": "GPT-OSS 120B",
                "description": "Phiên bản lớn hơn, chất lượng cao",
            },
        ],
    },
    {
        "value": "openai",
        "label": "OpenAI",
        "description": "GPT API — chất lượng ổn định, có phí",
        "models": [
            {
                "value": "gpt-4o-mini",
                "label": "GPT-4o Mini",
                "description": "Cân bằng chi phí và chất lượng",
                "recommended": True,
            },
            {
                "value": "gpt-4o",
                "label": "GPT-4o",
                "description": "Chất lượng cao, đắt hơn",
            },
            {
                "value": "gpt-4-turbo",
                "label": "GPT-4 Turbo",
                "description": "Phiên bản tối ưu của GPT-4",
            },
        ],
    },
    {
        "value": "claude",
        "label": "Anthropic Claude",
        "description": "Claude API — phân tích văn bản dài rất tốt",
        "models": [
            {
                "value": "claude-3-5-sonnet-20241022",
                "label": "Claude 3.5 Sonnet",
                "description": "Cân bằng chất lượng và tốc độ",
                "recommended": True,
            },
            {
                "value": "claude-3-5-haiku-20241022",
                "label": "Claude 3.5 Haiku",
                "description": "Nhanh và rẻ",
            },
            {
                "value": "claude-3-opus-20240229",
                "label": "Claude 3 Opus",
                "description": "Chất lượng cao nhất, chậm và đắt",
            },
        ],
    },
    {
        "value": "openrouter",
        "label": "OpenRouter",
        "description": "Truy cập đa nhà cung cấp qua một API duy nhất",
        "models": [
            {
                "value": "openai/gpt-4o-mini",
                "label": "GPT-4o Mini (qua OpenRouter)",
                "description": "Chuyển tiếp qua OpenRouter",
                "recommended": True,
            },
            {
                "value": "anthropic/claude-3.5-sonnet",
                "label": "Claude 3.5 Sonnet (qua OpenRouter)",
                "description": "Chuyển tiếp qua OpenRouter",
            },
            {
                "value": "google/gemini-2.5-flash",
                "label": "Gemini 2.5 Flash (qua OpenRouter)",
                "description": "Chuyển tiếp qua OpenRouter",
            },
        ],
    },
]


@router.get("/llm/providers")
def get_llm_providers(current_user: User = Depends(get_current_user)):
    """Return all available LLM providers and their models for analysis."""
    return LLM_PROVIDERS_CATALOG


@router.post(
    "/projects/{project_id}/analyze",
    response_model=DocumentAnalysisResponse,
    status_code=status.HTTP_201_CREATED
)
async def start_analysis(
    project_id: UUID,
    analysis_data: AnalysisCreate,
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(get_current_user)
):
    await verify_project_ownership_async(
        db=db,
        project_id=project_id,
        user_id=current_user.id
    )

    doc_result = await db.execute(
        select(Document).where(Document.id == analysis_data.document_id)
    )
    document = doc_result.scalar_one_or_none()
    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found"
        )

    if document.project_id != project_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Document does not belong to project"
        )

    analysis = await create_document_analysis(
        db=db,
        document_id=analysis_data.document_id
    )

    dispatch_analysis_agent(
        analysis.id,
        llm_provider=analysis_data.llm_provider,
        llm_model=analysis_data.llm_model,
    )

    return analysis


@router.get(
    "/projects/{project_id}/analysis/{task_id}",
    response_model=AnalysisStatusResponse
)
async def get_analysis_status(
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

    analysis = await get_document_analysis_by_id(
        db=db,
        analysis_id=task_id,
        light=True,
        with_document=True,
    )

    if analysis.document.project_id != project_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Analysis does not belong to project"
        )

    return analysis


@router.get(
    "/analysis/{task_id}/results",
    response_model=AnalysisResultsResponse
)
async def get_analysis_results(
    task_id: UUID,
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(get_current_user)
):
    analysis = await get_document_analysis_by_id(
        db=db,
        analysis_id=task_id,
        with_document=True,
    )

    await verify_project_ownership_async(
        db=db,
        project_id=analysis.document.project_id,
        user_id=current_user.id
    )

    return analysis


@router.get(
    "/documents/{doc_id}/summary"
)
async def get_document_summary(
    doc_id: UUID,
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(get_current_user)
):
    analysis = await get_document_analysis_by_document(
        db=db,
        document_id=doc_id,
        with_document=True,
    )

    await verify_project_ownership_async(
        db=db,
        project_id=analysis.document.project_id,
        user_id=current_user.id
    )

    return {"summary": analysis.summary}


@router.get(
    "/documents/{doc_id}/entities"
)
async def get_document_entities(
    doc_id: UUID,
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(get_current_user)
):
    analysis = await get_document_analysis_by_document(
        db=db,
        document_id=doc_id,
        with_document=True,
    )

    await verify_project_ownership_async(
        db=db,
        project_id=analysis.document.project_id,
        user_id=current_user.id
    )

    return {"entities": analysis.extracted_entities}


@router.get(
    "/documents/{doc_id}/sections"
)
async def get_document_sections(
    doc_id: UUID,
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(get_current_user)
):
    analysis = await get_document_analysis_by_document(
        db=db,
        document_id=doc_id,
        with_document=True,
    )

    await verify_project_ownership_async(
        db=db,
        project_id=analysis.document.project_id,
        user_id=current_user.id
    )

    return {
        "section_insights": analysis.section_insights or [],
        "outline": analysis.document_outline,
    }


@router.get(
    "/documents/{doc_id}/sections/{section_index}"
)
async def get_document_section(
    doc_id: UUID,
    section_index: int,
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(get_current_user)
):
    analysis = await get_document_analysis_by_document(
        db=db,
        document_id=doc_id,
        with_document=True,
    )

    await verify_project_ownership_async(
        db=db,
        project_id=analysis.document.project_id,
        user_id=current_user.id
    )

    sections = analysis.section_insights or []
    match = next(
        (s for s in sections if s.get("section_index") == section_index),
        None,
    )
    if match is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Section {section_index} not found in this analysis",
        )
    return match


@router.get(
    "/documents/{doc_id}/synthesis"
)
async def get_document_synthesis(
    doc_id: UUID,
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(get_current_user)
):
    analysis = await get_document_analysis_by_document(
        db=db,
        document_id=doc_id,
        with_document=True,
    )

    await verify_project_ownership_async(
        db=db,
        project_id=analysis.document.project_id,
        user_id=current_user.id
    )

    return analysis.narrative_synthesis or {}


@router.get(
    "/projects/{project_id}/analyses",
    response_model=list[AnalysisListItemResponse],
)
async def get_project_analyses_endpoint(
    project_id: UUID,
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(get_current_user)
):
    await verify_project_ownership_async(
        db=db,
        project_id=project_id,
        user_id=current_user.id
    )

    return await get_project_analyses(
        db=db,
        project_id=project_id
    )


@router.get(
    "/analyses",
    response_model=list[AnalysisListItemResponse],
)
async def get_all_user_analyses(
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(get_current_user),
):
    return await get_user_analyses(db=db, user_id=current_user.id)


@router.delete(
    "/analysis/{analysis_id}",
    status_code=status.HTTP_204_NO_CONTENT
)
async def delete_analysis(
    analysis_id: UUID,
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(get_current_user)
):
    analysis = await get_document_analysis_by_id(
        db=db,
        analysis_id=analysis_id,
        with_document=True,
    )

    await verify_project_ownership_async(
        db=db,
        project_id=analysis.document.project_id,
        user_id=current_user.id
    )

    await delete_document_analysis(db=db, analysis=analysis)
