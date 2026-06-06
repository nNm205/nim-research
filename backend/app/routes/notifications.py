"""Notifications API.

Endpoints (all scoped to the current user via ``get_current_user``):

  GET    /notifications                      — list + unread count
  POST   /notifications/mark-read            — mark some/all as read
  DELETE /notifications/{id}                 — delete one
  DELETE /notifications                      — clear all
"""

from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.schemas.notification import (
    NotificationListResponse,
    NotificationMarkReadRequest,
)
from app.services.notification_service import (
    clear_all_notifications,
    delete_notification,
    list_notifications,
    mark_read,
)

router = APIRouter(prefix="/api/v1/notifications", tags=["Notifications"])


@router.get("", response_model=NotificationListResponse)
def get_notifications(
    limit: int = Query(default=30, ge=1, le=100),
    only_unread: bool = Query(default=False),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    rows, unread = list_notifications(
        db,
        user_id=current_user.id,
        limit=limit,
        only_unread=only_unread,
    )
    return {"notifications": rows, "unread_count": unread}


@router.post("/mark-read")
def mark_notifications_read(
    payload: NotificationMarkReadRequest | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Mark some or all unread notifications as read.

    Body is optional. When ``ids`` is provided, only those are marked.
    Otherwise every unread notification belonging to the user is marked.
    """
    affected = mark_read(
        db,
        user_id=current_user.id,
        ids=payload.ids if payload else None,
    )
    return {"marked_read": affected}


@router.delete(
    "/{notification_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_one(
    notification_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    delete_notification(db, current_user.id, notification_id)
    return None


@router.delete("", status_code=status.HTTP_200_OK)
def clear_all(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    deleted = clear_all_notifications(db, user_id=current_user.id)
    return {"deleted": deleted}
