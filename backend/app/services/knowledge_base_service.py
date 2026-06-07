from uuid import UUID
from fastapi import HTTPException, status
from sqlalchemy import select, func, update as sql_update
from sqlalchemy.orm import Session, defer, selectinload, load_only
from app.models.knowledge_base import KnowledgeBaseArticle, KnowledgeBaseSubmission
from app.models.user import User
from app.schemas.knowledge_base import KnowledgeBaseArticleCreate, KnowledgeBaseArticleUpdate, KnowledgeBaseSubmissionCreate, KnowledgeBaseSubmissionReject
from app.utils.logger import logger
from app.utils.constants import KnowledgeBaseArticleStatus, KnowledgeBaseSubmissionStatus
from datetime import datetime, timezone

_USER_INFO_COLUMNS = (User.id, User.full_name, User.email)

def create_article(
    db: Session,
    article_data: KnowledgeBaseArticleCreate,
    created_by: UUID | None = None
) -> KnowledgeBaseArticle:
    logger.info(f"Creating knowledge base article: {article_data.title}")

    try:
        article = KnowledgeBaseArticle(
            title=article_data.title,
            excerpt=article_data.excerpt,
            content=article_data.content,
            category=article_data.category,
            tags=article_data.tags,
            created_by=created_by,
            status=KnowledgeBaseArticleStatus.PUBLISHED.value
        )

        db.add(article)
        db.commit()
        db.refresh(article)

        logger.success(f"Knowledge base article created: {article.id}")

        return article

    except Exception as e:
        db.rollback()

        logger.error(f"Article creation failed: {str(e)}")

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )

def get_article_by_id(
    db: Session,
    article_id: UUID,
) -> KnowledgeBaseArticle:
    logger.info(f"Fetching article: {article_id}")

    article = db.scalar(
        select(KnowledgeBaseArticle)
        .options(
            selectinload(KnowledgeBaseArticle.creator).load_only(
                *_USER_INFO_COLUMNS
            ),
        )
        .where(KnowledgeBaseArticle.id == article_id)
    )

    if not article:
        logger.warning(f"Article not found: {article_id}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Article not found",
        )

    return article

def get_all_articles(
    db: Session,
    category: str | None = None,
    search: str | None = None,
    skip: int = 0,
    limit: int = 50,
) -> tuple[list[KnowledgeBaseArticle], int]:
    """Paginated published-articles list — list-view columns only.

    - ``content`` is deferred (TEXT toàn văn không cần ở list).
    - ``creator`` được kèm qua explicit ``selectinload(...).load_only`` để
      chỉ lấy 3 cột User cần cho ``UserInfo``, không kéo cả password_hash.
    - Tổng số được tính bằng window function ``count(*) OVER ()`` trong
      cùng 1 query thay vì 2 round trip.
    """
    logger.info(f"Fetching articles - category: {category}, search: {search}")

    try:
        base_conditions = [
            KnowledgeBaseArticle.status == KnowledgeBaseArticleStatus.PUBLISHED.value
        ]

        if category and category != "all":
            base_conditions.append(KnowledgeBaseArticle.category == category)

        if search:
            # pg_trgm GIN index (added in add_kb_search_001) makes ``ilike``
            # on these columns an index scan instead of seq scan.
            search_term = f"%{search}%"
            base_conditions.append(
                (KnowledgeBaseArticle.title.ilike(search_term))
                | (KnowledgeBaseArticle.excerpt.ilike(search_term))
                | (KnowledgeBaseArticle.content.ilike(search_term))
            )

        total_col = func.count().over().label("total_count")

        query = (
            select(KnowledgeBaseArticle, total_col)
            .options(
                defer(KnowledgeBaseArticle.content),
                selectinload(KnowledgeBaseArticle.creator).load_only(
                    *_USER_INFO_COLUMNS
                ),
            )
            .order_by(KnowledgeBaseArticle.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        for condition in base_conditions:
            query = query.where(condition)

        rows = db.execute(query).all()
        articles = [row[0] for row in rows]
        total = int(rows[0][1]) if rows else 0

        logger.success(f"Retrieved {len(articles)} articles (total={total})")
        return articles, total

    except Exception as e:
        logger.error(f"Failed to fetch articles: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )

def get_categories_with_counts(
    db: Session
) -> dict[str, int]:
    logger.info("Fetching article categories with counts")

    try:
        result = db.execute(
            select(
                KnowledgeBaseArticle.category,
                func.count(KnowledgeBaseArticle.id).label("count")
            ).where(KnowledgeBaseArticle.status == KnowledgeBaseArticleStatus.PUBLISHED.value)
            .group_by(KnowledgeBaseArticle.category)
        )

        categories = {}
        for category, count in result.all():
            categories[category] = count

        logger.success(f"Retrieved {len(categories)} categories")

        return categories

    except Exception as e:
        logger.error(f"Failed to fetch categories: {str(e)}")

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )

def update_article(
    db: Session,
    article: KnowledgeBaseArticle,
    update_data: KnowledgeBaseArticleUpdate
) -> KnowledgeBaseArticle:
    logger.info(f"Updating article: {article.id}")

    update_dict = update_data.model_dump(exclude_unset=True)

    try:
        for key, value in update_dict.items():
            setattr(article, key, value)

        db.commit()
        # No db.refresh: expire_on_commit=False keeps the in-memory ORM
        # values fresh, and update_dict already reflects the new values.

        logger.success(f"Article updated: {article.id}")

        return article

    except Exception as e:
        db.rollback()

        logger.error(f"Article update failed for {article.id}: {str(e)}")

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )

def delete_article(
    db: Session,
    article: KnowledgeBaseArticle
) -> None:
    logger.info(f"Deleting article: {article.id}")

    try:
        db.delete(article)
        db.commit()

        logger.success(f"Article deleted: {article.id}")

    except Exception as e:
        db.rollback()

        logger.error(f"Article deletion failed for {article.id}: {str(e)}")

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )

def increment_article_views(
    db: Session,
    article: KnowledgeBaseArticle,
) -> KnowledgeBaseArticle:
    """Atomically bump ``views`` via a single UPDATE.

    The previous version did ``article.views += 1; commit; refresh()`` which
    is non-atomic (lost updates under concurrent reads), and adds 2 extra
    round trips per detail page hit. The atomic UPDATE runs as one
    statement and we mirror the new count on the in-memory ORM object so
    the response reflects it without re-fetching.
    """
    try:
        db.execute(
            sql_update(KnowledgeBaseArticle)
            .where(KnowledgeBaseArticle.id == article.id)
            .values(views=KnowledgeBaseArticle.views + 1)
        )
        db.commit()
        # Mirror the increment locally so the response model serialises the
        # new count without round-tripping for a refresh.
        article.views = (article.views or 0) + 1
        return article

    except Exception as e:
        db.rollback()
        logger.error(f"Failed to increment views for {article.id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )

# Submission functions
def create_submission(
    db: Session,
    submission_data: KnowledgeBaseSubmissionCreate,
    created_by: UUID
) -> KnowledgeBaseSubmission:
    logger.info(f"Creating submission: {submission_data.title}")

    try:
        submission = KnowledgeBaseSubmission(
            title=submission_data.title,
            excerpt=submission_data.excerpt,
            content=submission_data.content,
            category=submission_data.category,
            tags=submission_data.tags,
            created_by=created_by,
            status=KnowledgeBaseSubmissionStatus.PENDING.value
        )

        db.add(submission)
        db.commit()
        db.refresh(submission)

        logger.success(f"Submission created: {submission.id}")

        return submission

    except Exception as e:
        db.rollback()

        logger.error(f"Submission creation failed: {str(e)}")

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )

def get_submission_by_id(
    db: Session,
    submission_id: UUID,
) -> KnowledgeBaseSubmission:
    logger.info(f"Fetching submission: {submission_id}")

    submission = db.scalar(
        select(KnowledgeBaseSubmission)
        .options(
            selectinload(KnowledgeBaseSubmission.creator).load_only(
                *_USER_INFO_COLUMNS
            ),
            selectinload(KnowledgeBaseSubmission.reviewer).load_only(
                *_USER_INFO_COLUMNS
            ),
        )
        .where(KnowledgeBaseSubmission.id == submission_id)
    )

    if not submission:
        logger.warning(f"Submission not found: {submission_id}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Submission not found",
        )

    return submission

def get_pending_submissions(
    db: Session,
    skip: int = 0,
    limit: int = 50,
) -> tuple[list[KnowledgeBaseSubmission], int]:
    """Pending submissions list — defers ``content``, single window-count query.

    Loads ``creator`` and ``reviewer`` via explicit selectinload with the
    minimal User columns we surface in ``UserInfo``. Avoids the previous
    cascade that pulled full User rows (incl. password_hash) per submission.
    """
    logger.info("Fetching pending submissions")

    try:
        total_col = func.count().over().label("total_count")
        query = (
            select(KnowledgeBaseSubmission, total_col)
            .options(
                defer(KnowledgeBaseSubmission.content),
                selectinload(KnowledgeBaseSubmission.creator).load_only(
                    *_USER_INFO_COLUMNS
                ),
                selectinload(KnowledgeBaseSubmission.reviewer).load_only(
                    *_USER_INFO_COLUMNS
                ),
            )
            .where(
                KnowledgeBaseSubmission.status
                == KnowledgeBaseSubmissionStatus.PENDING.value
            )
            .order_by(KnowledgeBaseSubmission.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        rows = db.execute(query).all()
        submissions = [row[0] for row in rows]
        total = int(rows[0][1]) if rows else 0

        logger.success(
            f"Retrieved {len(submissions)} pending submissions (total={total})"
        )
        return submissions, total

    except Exception as e:
        logger.error(f"Failed to fetch submissions: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )

def get_user_submissions(
    db: Session,
    user_id: UUID,
    skip: int = 0,
    limit: int = 50,
) -> tuple[list[KnowledgeBaseSubmission], int]:
    """My-submissions list — same loading strategy as ``get_pending_submissions``."""
    logger.info(f"Fetching submissions for user: {user_id}")

    try:
        total_col = func.count().over().label("total_count")
        query = (
            select(KnowledgeBaseSubmission, total_col)
            .options(
                defer(KnowledgeBaseSubmission.content),
                selectinload(KnowledgeBaseSubmission.creator).load_only(
                    *_USER_INFO_COLUMNS
                ),
                selectinload(KnowledgeBaseSubmission.reviewer).load_only(
                    *_USER_INFO_COLUMNS
                ),
            )
            .where(KnowledgeBaseSubmission.created_by == user_id)
            .order_by(KnowledgeBaseSubmission.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        rows = db.execute(query).all()
        submissions = [row[0] for row in rows]
        total = int(rows[0][1]) if rows else 0

        logger.success(
            f"Retrieved {len(submissions)} submissions for user (total={total})"
        )
        return submissions, total

    except Exception as e:
        logger.error(f"Failed to fetch user submissions: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )

def approve_submission(
    db: Session,
    submission: KnowledgeBaseSubmission,
    reviewed_by: UUID
) -> KnowledgeBaseArticle:
    logger.info(f"Approving submission: {submission.id}")

    try:
        # Create published article from submission
        article = KnowledgeBaseArticle(
            title=submission.title,
            excerpt=submission.excerpt,
            content=submission.content,
            category=submission.category,
            tags=submission.tags,
            created_by=submission.created_by,
            status=KnowledgeBaseArticleStatus.PUBLISHED.value
        )

        db.add(article)

        # Update submission status
        submission.status = KnowledgeBaseSubmissionStatus.APPROVED.value
        submission.reviewed_by = reviewed_by
        submission.reviewed_at = datetime.now(timezone.utc)

        db.commit()
        # We still need ``article.id`` (server-side default UUID isn't used —
        # SQLAlchemy generated it client-side via ``default=uuid.uuid4``) so
        # one refresh on the new article is enough; the submission already
        # had its values set in-memory.
        db.refresh(article)

        logger.success(f"Submission approved: {submission.id}")

        return article

    except Exception as e:
        db.rollback()

        logger.error(f"Submission approval failed for {submission.id}: {str(e)}")

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )

def reject_submission(
    db: Session,
    submission: KnowledgeBaseSubmission,
    rejection_data: KnowledgeBaseSubmissionReject,
    reviewed_by: UUID
) -> KnowledgeBaseSubmission:
    logger.info(f"Rejecting submission: {submission.id}")

    try:
        submission.status = KnowledgeBaseSubmissionStatus.REJECTED.value
        submission.rejection_reason = rejection_data.rejection_reason
        submission.reviewed_by = reviewed_by
        submission.reviewed_at = datetime.now(timezone.utc)

        db.commit()
        # No db.refresh: in-memory submission already has the new fields.

        logger.success(f"Submission rejected: {submission.id}")

        return submission

    except Exception as e:
        db.rollback()

        logger.error(f"Submission rejection failed for {submission.id}: {str(e)}")

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )
