from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from app.database.session import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.schemas.knowledge_base import (
    KnowledgeBaseArticleCreate,
    KnowledgeBaseArticleUpdate,
    KnowledgeBaseArticleResponse,
    KnowledgeBaseArticleListResponse,
    KnowledgeBaseSubmissionCreate,
    KnowledgeBaseSubmissionResponse,
    KnowledgeBaseSubmissionListResponse,
    KnowledgeBaseSubmissionApprove,
    KnowledgeBaseSubmissionReject
)
from app.services.knowledge_base_service import (
    create_article,
    get_article_by_id,
    get_all_articles,
    get_categories_with_counts,
    update_article,
    delete_article,
    increment_article_views,
    create_submission,
    get_submission_by_id,
    get_pending_submissions,
    get_user_submissions,
    approve_submission,
    reject_submission
)

router = APIRouter(prefix="/api/v1", tags=["Knowledge Base"])

@router.get(
    "/knowledge-base/articles",
    response_model=KnowledgeBaseArticleListResponse
)
def list_articles(
    category: str | None = Query(None),
    search: str | None = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db)
):
    articles, total = get_all_articles(
        db=db,
        category=category,
        search=search,
        skip=skip,
        limit=limit
    )

    categories = get_categories_with_counts(db=db)

    return {
        "articles": articles,
        "total": total,
        "categories": categories
    }

@router.get(
    "/knowledge-base/articles/{article_id}",
    response_model=KnowledgeBaseArticleResponse
)
def get_article_details(
    article_id: UUID,
    db: Session = Depends(get_db)
):
    article = get_article_by_id(
        db=db,
        article_id=article_id
    )

    increment_article_views(db=db, article=article)

    return article

@router.post(
    "/knowledge-base/submissions",
    response_model=KnowledgeBaseSubmissionResponse,
    status_code=status.HTTP_201_CREATED
)
def create_new_submission(
    submission_data: KnowledgeBaseSubmissionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    submission = create_submission(
        db=db,
        submission_data=submission_data,
        created_by=current_user.id
    )

    return submission

@router.get(
    "/knowledge-base/submissions/my",
    response_model=KnowledgeBaseSubmissionListResponse
)
def get_my_submissions(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    submissions, total = get_user_submissions(
        db=db,
        user_id=current_user.id,
        skip=skip,
        limit=limit
    )

    return {
        "submissions": submissions,
        "total": total
    }

@router.get(
    "/knowledge-base/submissions/pending",
    response_model=KnowledgeBaseSubmissionListResponse
)
def list_pending_submissions(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins can view pending submissions"
        )

    submissions, total = get_pending_submissions(
        db=db,
        skip=skip,
        limit=limit
    )

    return {
        "submissions": submissions,
        "total": total
    }

@router.post(
    "/knowledge-base/submissions/{submission_id}/approve",
    response_model=KnowledgeBaseArticleResponse,
    status_code=status.HTTP_201_CREATED
)
def approve_new_submission(
    submission_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins can approve submissions"
        )

    submission = get_submission_by_id(
        db=db,
        submission_id=submission_id
    )

    article = approve_submission(
        db=db,
        submission=submission,
        reviewed_by=current_user.id
    )

    return article

@router.post(
    "/knowledge-base/submissions/{submission_id}/reject",
    response_model=KnowledgeBaseSubmissionResponse
)
def reject_new_submission(
    submission_id: UUID,
    rejection_data: KnowledgeBaseSubmissionReject,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins can reject submissions"
        )

    submission = get_submission_by_id(
        db=db,
        submission_id=submission_id
    )

    submission = reject_submission(
        db=db,
        submission=submission,
        rejection_data=rejection_data,
        reviewed_by=current_user.id
    )

    return submission

@router.post(
    "/knowledge-base/articles",
    response_model=KnowledgeBaseArticleResponse,
    status_code=status.HTTP_201_CREATED
)
def create_new_article(
    article_data: KnowledgeBaseArticleCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins can create articles directly"
        )

    article = create_article(
        db=db,
        article_data=article_data,
        created_by=current_user.id
    )

    return article

@router.put(
    "/knowledge-base/articles/{article_id}",
    response_model=KnowledgeBaseArticleResponse
)
def update_existing_article(
    article_id: UUID,
    article_data: KnowledgeBaseArticleUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins can update articles"
        )

    article = get_article_by_id(
        db=db,
        article_id=article_id
    )

    return update_article(
        db=db,
        article=article,
        update_data=article_data
    )

@router.delete(
    "/knowledge-base/articles/{article_id}",
    status_code=status.HTTP_204_NO_CONTENT
)
def delete_existing_article(
    article_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins can delete articles"
        )

    article = get_article_by_id(
        db=db,
        article_id=article_id
    )

    delete_article(
        db=db,
        article=article
    )

    return None
