from uuid import UUID
from fastapi import (
    HTTPException,
    APIRouter,
    Depends,
    File,
    Form,
    UploadFile,
    status,
)
from sqlalchemy.orm import Session
from sqlalchemy.ext.asyncio import AsyncSession
from app.database.session import get_db, get_async_db
from app.dependencies import get_current_user
from app.schemas.document import (
    DocumentCreate,
    DocumentUpdate,
    DocumentResponse,
    DocumentListItemResponse,
    URLIngestRequest,
    SearchResultIngestRequest,
)
import app.services.project_service as project_service
import app.services.document_service as document_service

router = APIRouter(prefix="/api/v1/projects", tags=["Documents"])
ingest_router = APIRouter(prefix="/api/v1/projects", tags=["Documents"])
meta_router = APIRouter(prefix="/api/v1/embeddings", tags=["Embeddings"])

# Cross-project list endpoint — exposes /api/v1/documents (no project scope).
all_router = APIRouter(prefix="/api/v1", tags=["Documents"])


@all_router.get(
    "/documents",
    response_model=list[DocumentListItemResponse],
)
def get_all_user_documents(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """All documents owned by the current user, across every project.

    Used by the ``Documents`` page that lists everything the user has
    uploaded so they can filter by project on the client side without
    making N round-trips (one per project).
    """
    return document_service.get_user_documents(db=db, user_id=current_user.id)


# ── Embedding providers metadata ─────────────────────────────────────────────

EMBEDDING_PROVIDERS_CATALOG = [
    {
        "value": "huggingface",
        "label": "HuggingFace",
        "description": "Inference API — miễn phí, đa ngôn ngữ",
        "models": [
            {
                "value": "ibm-granite/granite-embedding-97m-multilingual-r2",
                "label": "Granite Multilingual 97M",
                "dimensions": 384,
                "description": "Đa ngôn ngữ, nhẹ, phù hợp tiếng Việt",
                "recommended": True,
            },
            {
                "value": "sentence-transformers/all-MiniLM-L6-v2",
                "label": "all-MiniLM-L6-v2",
                "dimensions": 384,
                "description": "Nhanh, nhẹ, tiếng Anh",
            },
            {
                "value": "sentence-transformers/all-mpnet-base-v2",
                "label": "all-mpnet-base-v2",
                "dimensions": 768,
                "description": "Chất lượng cao hơn, tiếng Anh",
            },
            {
                "value": "BAAI/bge-small-en-v1.5",
                "label": "BGE Small EN",
                "dimensions": 384,
                "description": "BGE nhỏ, tiếng Anh",
            },
            {
                "value": "BAAI/bge-base-en-v1.5",
                "label": "BGE Base EN",
                "dimensions": 768,
                "description": "BGE chuẩn, tiếng Anh",
            },
            {
                "value": "BAAI/bge-large-en-v1.5",
                "label": "BGE Large EN",
                "dimensions": 1024,
                "description": "BGE lớn, chất lượng cao nhất, tiếng Anh",
            },
        ],
    },
    {
        "value": "jina",
        "label": "Jina AI",
        "description": "API thương mại — chất lượng cao, đa ngôn ngữ",
        "models": [
            {
                "value": "jina-embeddings-v3",
                "label": "Jina Embeddings v3",
                "dimensions": 1024,
                "description": "Mới nhất, đa ngôn ngữ, chất lượng cao",
                "recommended": True,
            },
            {
                "value": "jina-embeddings-v2-base-en",
                "label": "Jina v2 Base EN",
                "dimensions": 768,
                "description": "Tiếng Anh, cân bằng tốc độ/chất lượng",
            },
            {
                "value": "jina-embeddings-v2-small-en",
                "label": "Jina v2 Small EN",
                "dimensions": 512,
                "description": "Tiếng Anh, nhanh và nhẹ",
            },
            {
                "value": "jina-clip-v2",
                "label": "Jina CLIP v2",
                "dimensions": 1024,
                "description": "Multimodal (text + image)",
            },
        ],
    },
    {
        "value": "googleai",
        "label": "Google AI",
        "description": "Gemini Embedding API — chất lượng rất cao",
        "models": [
            {
                "value": "gemini-embedding-001",
                "label": "Gemini Embedding 001",
                "dimensions": 3072,
                "description": "Mới nhất, chiều cao nhất, chất lượng tốt nhất",
                "recommended": True,
            },
            {
                "value": "text-embedding-004",
                "label": "Text Embedding 004",
                "dimensions": 768,
                "description": "Ổn định, tiêu chuẩn",
            },
            {
                "value": "embedding-001",
                "label": "Embedding 001",
                "dimensions": 768,
                "description": "Phiên bản cũ hơn",
            },
        ],
    },
]


@meta_router.get("/providers")
def get_embedding_providers(current_user=Depends(get_current_user)):
    """Return all available embedding providers and their models."""
    return EMBEDDING_PROVIDERS_CATALOG


# ── Standard CRUD endpoints (sync) ──────────────────────────────────────────

@router.get(
    "/{project_id}/documents",
    response_model=list[DocumentListItemResponse],
)
def get_project_documents(
    project_id: UUID,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    project_service.verify_project_ownership(
        db=db, project_id=project_id, user_id=current_user.id
    )
    return document_service.get_project_documents(db=db, project_id=project_id)


@router.post(
    "/{project_id}/documents",
    response_model=DocumentResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_project_document(
    project_id: UUID,
    document_data: DocumentCreate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    project_service.verify_project_ownership(
        db=db, project_id=project_id, user_id=current_user.id
    )
    return document_service.create_document(
        db=db, project_id=project_id, document_data=document_data
    )


@router.get(
    "/{project_id}/documents/{document_id}",
    response_model=DocumentResponse,
)
def get_project_document(
    project_id: UUID,
    document_id: UUID,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    project_service.verify_project_ownership(
        db=db, project_id=project_id, user_id=current_user.id
    )
    document = document_service.verify_document_ownership(
        db=db, document_id=document_id, user_id=current_user.id
    )
    if document.project_id != project_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    return document


@router.patch(
    "/{project_id}/documents/{document_id}",
    response_model=DocumentResponse,
)
def update_project_document(
    project_id: UUID,
    document_id: UUID,
    update_data: DocumentUpdate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    project_service.verify_project_ownership(
        db=db, project_id=project_id, user_id=current_user.id
    )
    document = document_service.verify_document_ownership(
        db=db, document_id=document_id, user_id=current_user.id
    )
    if document.project_id != project_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    return document_service.update_document(db=db, document=document, update_data=update_data)


@router.delete(
    "/{project_id}/documents/{document_id}",
    status_code=status.HTTP_200_OK,
)
def delete_project_document(
    project_id: UUID,
    document_id: UUID,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    project_service.verify_project_ownership(
        db=db, project_id=project_id, user_id=current_user.id
    )
    document = document_service.verify_document_ownership(
        db=db, document_id=document_id, user_id=current_user.id
    )
    if document.project_id != project_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    document_service.delete_document(db=db, document=document)
    return {"message": "Document deleted successfully"}


# ── URL Ingestion endpoint (async — uses DocumentIngestionService) ────────────

@ingest_router.post(
    "/{project_id}/documents/ingest-url",
    response_model=DocumentResponse,
    status_code=status.HTTP_201_CREATED,
)
async def ingest_url_as_document(
    project_id: UUID,
    request: URLIngestRequest,
    db: AsyncSession = Depends(get_async_db),
    current_user=Depends(get_current_user),
):
    """Fetch a URL (PDF or HTML), extract content, chunk, embed, and save as Document."""
    from app.services.project_service import verify_project_ownership_async
    from app.services.document_ingestion_service import DocumentIngestionService

    await verify_project_ownership_async(
        db=db, project_id=project_id, user_id=current_user.id
    )

    service = DocumentIngestionService(
        db,
        embedding_provider=request.embedding_provider,
        embedding_model=request.embedding_model,
    )
    try:
        document = await service.ingest_url(
            project_id=project_id,
            url=request.url,
            source_type=request.source_type,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e),
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Could not ingest URL: {str(e)}",
        )

    return document


# ── Search-result ingest endpoint ────────────────────────────────────────────

@ingest_router.post(
    "/{project_id}/documents/ingest-search-result",
    response_model=DocumentResponse,
    status_code=status.HTTP_201_CREATED,
)
async def ingest_search_result_as_document(
    project_id: UUID,
    payload: SearchResultIngestRequest,
    db: AsyncSession = Depends(get_async_db),
    current_user=Depends(get_current_user),
):
    """Ingest a research-search result into the project.

    Looks up the ``SearchResult`` row by ``result_id``, locates a PDF
    (existing ``pdf_url`` / arXiv-derived / Unpaywall via DOI / scraped
    from the landing page), and falls back to ingesting the landing
    HTML if no PDF is found. Marks the search-result row with the new
    ``document_id`` so the FE can show "Đã thêm".
    """
    from sqlalchemy import select
    from app.models.research import SearchResult, ResearchSession
    from app.services.project_service import verify_project_ownership_async
    from app.services.document_ingestion_service import DocumentIngestionService
    from app.utils.logger import logger

    logger.info(
        f"ingest-search-result: project={project_id} result={payload.result_id} "
        f"embedding_provider={payload.embedding_provider} "
        f"embedding_model={payload.embedding_model}"
    )

    await verify_project_ownership_async(
        db=db, project_id=project_id, user_id=current_user.id
    )

    stmt = (
        select(SearchResult)
        .join(
            ResearchSession,
            ResearchSession.id == SearchResult.research_session_id,
        )
        .where(
            SearchResult.id == payload.result_id,
            ResearchSession.project_id == project_id,
        )
    )
    result_row = (await db.execute(stmt)).scalar_one_or_none()
    if result_row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Search result not found in this project",
        )

    if result_row.document_id is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Search result đã được thêm vào dự án trước đó.",
        )

    service = DocumentIngestionService(
        db,
        embedding_provider=payload.embedding_provider,
        embedding_model=payload.embedding_model,
    )
    try:
        document = await service.ingest_from_search_result(
            project_id=project_id,
            search_result=result_row,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e),
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Không thể xử lý kết quả tìm kiếm: {e}",
        )

    # Link the search result row to the new document so future loads can
    # render an "Đã thêm" badge without re-querying.
    result_row.document_id = document.id
    await db.commit()

    return document


# ── File upload endpoint (multipart — PDF / HTML) ────────────────────────────

# Hard cap on uploaded file size. 50 MB covers >99 % of academic PDFs while
# preventing accidental DoS. Adjust if your users routinely upload bigger files.
_MAX_UPLOAD_BYTES = 50 * 1024 * 1024


@ingest_router.post(
    "/{project_id}/documents/upload-file",
    response_model=DocumentResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upload_file_as_document(
    project_id: UUID,
    file: UploadFile = File(...),
    embedding_provider: str | None = Form(None),
    embedding_model: str | None = Form(None),
    db: AsyncSession = Depends(get_async_db),
    current_user=Depends(get_current_user),
):
    """Upload a PDF or HTML file directly, extract content, chunk and embed.

    Same backend pipeline as ``ingest-url`` but the file is supplied as a
    multipart upload instead of being fetched. Useful for documents the
    user has locally that aren't on the public web.
    """
    from app.services.project_service import verify_project_ownership_async
    from app.services.document_ingestion_service import DocumentIngestionService

    await verify_project_ownership_async(
        db=db, project_id=project_id, user_id=current_user.id
    )

    raw = await file.read()
    if not raw:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="File rỗng.",
        )
    if len(raw) > _MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File quá lớn (tối đa {_MAX_UPLOAD_BYTES // (1024 * 1024)} MB).",
        )

    service = DocumentIngestionService(
        db,
        embedding_provider=embedding_provider,
        embedding_model=embedding_model,
    )
    try:
        document = await service.ingest_uploaded_file(
            project_id=project_id,
            file_bytes=raw,
            filename=file.filename or "uploaded",
            content_type=file.content_type,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e),
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Không thể xử lý file: {str(e)}",
        )

    return document
