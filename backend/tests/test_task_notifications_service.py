from datetime import datetime

import pytest
from sqlalchemy import select

from models import Conversation, TaskNotification
from services.inspection_tasks import create_inspection_task, execute_inspection_task


@pytest.mark.asyncio
async def test_execute_inspection_task_creates_success_notification_with_latest_report(
    session_factory,
):
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
    published_events: list[dict] = []

    async def fake_agent_runner(*, user_message, conv_id, on_event, agent_id=None):
        assert user_message == "Inspect peets-prod-pos-mysql for the last 7 days"
        assert agent_id == "db-runtime"
        await on_event(
            {
                "type": "tool_result",
                "tool_name": "write_file",
                "tool_input": {
                    "file_path": "/memories/reports/report-a.md",
                    "content": "# report-a",
                },
                "artifact_kind": "report",
                "result": "Saved report A",
                "agent_id": "db-runtime",
            }
        )
        await on_event(
            {
                "type": "tool_result",
                "tool_name": "write_file",
                "tool_input": {
                    "file_path": "/memories/reports/report-b.md",
                    "content": "# report-b",
                },
                "artifact_kind": "report",
                "result": "Saved report B",
                "agent_id": "db-runtime",
            }
        )
        await on_event(
            {
                "type": "text_delta",
                "content": "Summary line 1\nSummary line 2\nSummary line 3\nSummary line 4",
                "agent_id": "db-runtime",
            }
        )
        await on_event({"type": "done", "agent_id": "db-runtime"})

    async def fake_notification_publisher(event: dict):
        published_events.append(event)

    run = await execute_inspection_task(
        task.id,
        trigger_type="scheduled",
        now=datetime(2026, 3, 11, 9, 0),
        session_factory=session_factory,
        agent_runner=fake_agent_runner,
        notification_publisher=fake_notification_publisher,
    )

    assert run.status == "succeeded"
    assert run.report_name == "report-b.md"
    assert run.report_path == "/memories/reports/report-b.md"

    async with session_factory() as session:
        notifications = (
            await session.execute(
                select(TaskNotification).order_by(TaskNotification.created_at.desc())
            )
        ).scalars().all()
        conversation = await session.get(Conversation, run.conversation_id)

    assert conversation is not None
    assert len(notifications) == 1
    notification = notifications[0]
    assert notification.task_id == task.id
    assert notification.task_run_id == run.id
    assert notification.conversation_id == run.conversation_id
    assert notification.status == "succeeded"
    assert notification.title == "Peets Daily Inspection"
    assert notification.summary == "Summary line 1\nSummary line 2\nSummary line 3"
    assert notification.report_name == "report-b.md"
    assert notification.report_path == "/memories/reports/report-b.md"
    assert notification.read_at is None
    assert published_events == [
        {
            "type": "task_notification",
            "notification": notification.to_dict(),
            "unread_count": 1,
        }
    ]


@pytest.mark.asyncio
async def test_execute_inspection_task_creates_failed_notification_without_report(
    session_factory,
):
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
    published_events: list[dict] = []

    async def fake_agent_runner(*, user_message, conv_id, on_event, agent_id=None):
        raise RuntimeError("agent execution failed")

    async def fake_notification_publisher(event: dict):
        published_events.append(event)

    run = await execute_inspection_task(
        task.id,
        trigger_type="scheduled",
        now=datetime(2026, 3, 11, 9, 0),
        session_factory=session_factory,
        agent_runner=fake_agent_runner,
        notification_publisher=fake_notification_publisher,
    )

    assert run.status == "failed"
    assert run.report_name is None
    assert run.report_path is None

    async with session_factory() as session:
        notifications = (
            await session.execute(
                select(TaskNotification).order_by(TaskNotification.created_at.desc())
            )
        ).scalars().all()

    assert len(notifications) == 1
    notification = notifications[0]
    assert notification.status == "failed"
    assert notification.summary == "agent execution failed"
    assert notification.report_name is None
    assert notification.report_path is None
    assert published_events == [
        {
            "type": "task_notification",
            "notification": notification.to_dict(),
            "unread_count": 1,
        }
    ]
