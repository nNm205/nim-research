from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class NotificationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    title: str
    message: str | None
    notification_type: str
    category: str
    entity_id: UUID | None
    entity_kind: str | None
    project_id: UUID | None
    is_read: bool
    created_at: datetime
    read_at: datetime | None


class NotificationListResponse(BaseModel):
    """Response payload for the list endpoint.

    ``unread_count`` is included so the FE can update the bell badge in
    one round-trip without a second ``/unread-count`` call.
    """
    notifications: list[NotificationResponse]
    unread_count: int


class NotificationMarkReadRequest(BaseModel):
    """Optional payload for the mark-read endpoint. When ``ids`` is
    omitted the endpoint marks every unread notification as read."""
    ids: list[UUID] | None = None
