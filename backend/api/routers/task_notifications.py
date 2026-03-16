from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse

from auth.dependencies import require_permission
from db.session import AsyncSessionLocal
from services.task_notifications import (
    list_task_notifications,
    mark_all_task_notifications_read,
    mark_task_notification_read,
)


router = APIRouter(prefix="/api/task-notifications", tags=["task-notifications"])


@router.get("", dependencies=[Depends(require_permission("task_notifications:read"))])
async def get_task_notifications():
    notifications, unread_count = await list_task_notifications(
        session_factory=AsyncSessionLocal
    )
    return JSONResponse(
        {
            "items": [notification.to_dict() for notification in notifications],
            "unread_count": unread_count,
        }
    )


@router.post(
    "/read-all",
    dependencies=[Depends(require_permission("task_notifications:update"))],
)
async def read_all_task_notifications():
    updated_count = await mark_all_task_notifications_read(
        session_factory=AsyncSessionLocal
    )
    return JSONResponse({"updated_count": updated_count})


@router.post(
    "/{notification_id}/read",
    dependencies=[Depends(require_permission("task_notifications:update"))],
)
async def read_task_notification(notification_id: str):
    try:
        notification = await mark_task_notification_read(
            notification_id,
            session_factory=AsyncSessionLocal,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return JSONResponse(notification.to_dict())
