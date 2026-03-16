from datetime import datetime

from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.routers import task_notifications as task_notifications_router
from models import Conversation, InspectionTaskRun, TaskNotification
from services.inspection_tasks import create_inspection_task


def create_test_client(session_factory):
    app = FastAPI()
    task_notifications_router.AsyncSessionLocal = session_factory
    app.include_router(task_notifications_router.router)
    return TestClient(app)


async def create_notification(session_factory, *, status: str, read_at=None):
    task = await create_inspection_task(
        name="Peets Daily Inspection",
        source_conversation_id=None,
        agent_id="dba",
        skill_id="volcengine-rds-health-analyzer",
        prompt_template="Inspect peets-prod-pos-mysql for the last 7 days",
        target_payload={"instance_name": "peets-prod-pos-mysql"},
        cron_expr="0 9 * * *",
        enabled=True,
        now=datetime(2026, 3, 11, 8, 0),
        session_factory=session_factory,
    )

    async with session_factory() as session:
        conversation = Conversation(
            title=f"{task.name} run",
            source="task",
            agent_id="dba",
        )
        session.add(conversation)
        await session.flush()
        run = InspectionTaskRun(
            task_id=task.id,
            trigger_type="scheduled",
            status=status,
            conversation_id=conversation.id,
            started_at=datetime(2026, 3, 11, 9, 0),
            finished_at=datetime(2026, 3, 11, 9, 5),
        )
        session.add(run)
        await session.flush()
        notification = TaskNotification(
            task_id=task.id,
            task_run_id=run.id,
            conversation_id=conversation.id,
            status=status,
            title=task.name,
            summary=f"{status} summary",
            report_name="report-a.md" if status == "succeeded" else None,
            report_path="/memories/reports/report-a.md" if status == "succeeded" else None,
            read_at=read_at,
            created_at=datetime(2026, 3, 11, 9, 5),
        )
        session.add(notification)
        await session.commit()
        await session.refresh(notification)
        return notification


async def test_list_task_notifications_returns_items_and_unread_count(session_factory):
    unread = await create_notification(session_factory, status="succeeded", read_at=None)
    read = await create_notification(
        session_factory,
        status="failed",
        read_at=datetime(2026, 3, 11, 10, 0),
    )
    client = create_test_client(session_factory)

    response = client.get("/api/task-notifications")

    assert response.status_code == 200
    payload = response.json()
    assert payload["unread_count"] == 1
    assert {item["id"] for item in payload["items"]} == {read.id, unread.id}


async def test_mark_task_notification_read_updates_read_at(session_factory):
    notification = await create_notification(session_factory, status="succeeded", read_at=None)
    client = create_test_client(session_factory)

    response = client.post(f"/api/task-notifications/{notification.id}/read")

    assert response.status_code == 200
    payload = response.json()
    assert payload["id"] == notification.id
    assert payload["read_at"] is not None


async def test_mark_all_task_notifications_read_returns_updated_count(session_factory):
    await create_notification(session_factory, status="succeeded", read_at=None)
    await create_notification(session_factory, status="failed", read_at=None)
    client = create_test_client(session_factory)

    response = client.post("/api/task-notifications/read-all")

    assert response.status_code == 200
    assert response.json() == {"updated_count": 2}

    list_response = client.get("/api/task-notifications")
    assert list_response.status_code == 200
    assert list_response.json()["unread_count"] == 0
