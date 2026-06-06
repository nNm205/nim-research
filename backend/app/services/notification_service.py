"""Notification service.

Two surfaces:

  1. **Public API** — ``list_notifications`` / ``mark_read`` /
     ``mark_all_read`` / ``delete_notification``. Used by the FE bell
     dropdown.

  2. **Internal helper** — ``create_notification(...)`` (sync) and
     ``create_notification_async(...)`` (async). Called from agent
     pipelines whenever a long-running task finalises so the user
     gets a persistent alert even if they navigated to a different
     page.

The async helper opens its own ``AsyncSessionLocal`` so it can be
called from background tasks that don't have a request-scoped session
attached.

Design choices:

- We never raise from ``create_notification*``. A notification write
  failure must NEVER block the actual pipeline result write. We log
  and swallow.
- Reads happen through the sync ``Session`` because the bell endpoint
  is wired to the sync stack (matches reports / projects routes).
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from app.database.session import AsyncSessionLocal, SessionLocal
from app.models.notification import Notification
from app.utils.logger import logger


# ── Categories the backend produces. The FE may choose to group/filter
# by these but the backend stays open — any string is accepted.
CATEGORY_RESEARCH = "research"
CATEGORY_AUTO_RESEARCH = "auto_research"
CATEGORY_ANALYSIS = "analysis"
CATEGORY_REPORT = "report"
CATEGORY_DOCUMENT = "document"
CATEGORY_GENERAL = "general"

# ── Notification types — drive icon + tint on the FE.
TYPE_SUCCESS = "success"
TYPE_ERROR = "error"
TYPE_INFO = "info"


# ── Public API ──────────────────────────────────────────────────────────────


def list_notifications(
    db: Session,
    user_id: UUID,
    *,
    limit: int = 30,
    only_unread: bool = False,
) -> tuple[list[Notification], int]:
    """Return ``(rows, unread_count)`` for the given user.

    The unread count is computed in a separate aggregate so the bell
    badge stays accurate even when the list is filtered to a small
    page.
    """
    try:
        stmt = (
            select(Notification)
            .where(Notification.user_id == user_id)
            .order_by(Notification.created_at.desc())
            .limit(limit)
        )
        if only_unread:
            stmt = stmt.where(Notification.is_read.is_(False))
        rows = list(db.execute(stmt).scalars().all())

        unread_count = (
            db.execute(
                select(func.count(Notification.id))
                .where(Notification.user_id == user_id)
                .where(Notification.is_read.is_(False))
            ).scalar()
            or 0
        )

        return rows, unread_count
    except Exception as e:
        logger.error(
            f"Failed to list notifications for user {user_id}: {e}"
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


def mark_read(
    db: Session,
    user_id: UUID,
    *,
    ids: list[UUID] | None = None,
) -> int:
    """Mark notifications as read.

    When ``ids`` is None / empty, every unread notification belonging to
    ``user_id`` is marked. Returns the number of rows affected.
    """
    try:
        now = datetime.now(timezone.utc)
        stmt = (
            update(Notification)
            .where(Notification.user_id == user_id)
            .where(Notification.is_read.is_(False))
            .values(is_read=True, read_at=now)
        )
        if ids:
            stmt = stmt.where(Notification.id.in_(ids))
        result = db.execute(stmt)
        db.commit()
        return result.rowcount or 0
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to mark notifications read: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


def delete_notification(
    db: Session, user_id: UUID, notification_id: UUID
) -> None:
    """Hard-delete a single notification owned by ``user_id``."""
    try:
        n = db.scalar(
            select(Notification)
            .where(Notification.id == notification_id)
            .where(Notification.user_id == user_id)
        )
        if n is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Notification not found",
            )
        db.delete(n)
        db.commit()
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to delete notification {notification_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


def clear_all_notifications(db: Session, user_id: UUID) -> int:
    """Delete every notification belonging to ``user_id``."""
    try:
        from sqlalchemy import delete

        result = db.execute(
            delete(Notification).where(Notification.user_id == user_id)
        )
        db.commit()
        return result.rowcount or 0
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to clear notifications for {user_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


# ── Internal helper used by agents ──────────────────────────────────────────


def _build_notification(
    *,
    user_id: UUID,
    title: str,
    message: str | None,
    notification_type: str,
    category: str,
    entity_id: UUID | None,
    entity_kind: str | None,
    project_id: UUID | None,
) -> Notification:
    return Notification(
        user_id=user_id,
        title=title[:200] if title else "",
        message=message,
        notification_type=notification_type,
        category=category,
        entity_id=entity_id,
        entity_kind=entity_kind,
        project_id=project_id,
    )


def create_notification(
    db: Session,
    *,
    user_id: UUID,
    title: str,
    message: str | None = None,
    notification_type: str = TYPE_INFO,
    category: str = CATEGORY_GENERAL,
    entity_id: UUID | None = None,
    entity_kind: str | None = None,
    project_id: UUID | None = None,
) -> Notification | None:
    """Synchronous create. Errors are swallowed."""
    try:
        n = _build_notification(
            user_id=user_id,
            title=title,
            message=message,
            notification_type=notification_type,
            category=category,
            entity_id=entity_id,
            entity_kind=entity_kind,
            project_id=project_id,
        )
        db.add(n)
        db.commit()
        db.refresh(n)
        return n
    except Exception as e:
        try:
            db.rollback()
        except Exception:
            pass
        logger.warning(
            f"create_notification failed for user={user_id}: {e}"
        )
        return None


async def create_notification_async(
    db: AsyncSession | None = None,
    *,
    user_id: UUID,
    title: str,
    message: str | None = None,
    notification_type: str = TYPE_INFO,
    category: str = CATEGORY_GENERAL,
    entity_id: UUID | None = None,
    entity_kind: str | None = None,
    project_id: UUID | None = None,
) -> None:
    """Async create. Opens its own session if ``db`` is omitted, so it
    works from background tasks where no session is in scope.

    Errors are swallowed — see module docstring.
    """
    try:
        n = _build_notification(
            user_id=user_id,
            title=title,
            message=message,
            notification_type=notification_type,
            category=category,
            entity_id=entity_id,
            entity_kind=entity_kind,
            project_id=project_id,
        )

        if db is not None:
            db.add(n)
            await db.commit()
            return

        async with AsyncSessionLocal() as session:
            session.add(n)
            await session.commit()
    except Exception as e:
        logger.warning(
            f"create_notification_async failed for user={user_id}: {e}"
        )


# ── Convenience wrapper for sync code paths that have no session yet ──────


def create_notification_in_new_session(**kwargs) -> None:
    """Open a fresh sync session, write, and close.

    Useful when the caller is sync but the surrounding session may be
    in a poisoned state (e.g. inside an except branch after a rollback).
    """
    try:
        with SessionLocal() as session:
            create_notification(session, **kwargs)
    except Exception as e:
        logger.warning(f"create_notification_in_new_session failed: {e}")
