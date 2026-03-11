from datetime import datetime

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.routers import inspection_tasks as inspection_tasks_router
from models import Conversation, Message


def create_test_client(session_factory):
    app = FastAPI()
    inspection_tasks_router.AsyncSessionLocal = session_factory
    app.include_router(inspection_tasks_router.router)
    return TestClient(app)


@pytest.mark.asyncio
async def test_create_draft_route_extracts_conversation_prompt(session_factory):
    async with session_factory() as session:
        conversation = Conversation(
            title="Peets Weekly Inspection",
            source="web",
            agent_id="dba",
        )
        session.add(conversation)
        await session.flush()
        session.add(
            Message(
                conversation_id=conversation.id,
                role="user",
                content="请巡检 peets-prod-member-mysql 最近 30 天状态",
                type="text",
                agent_id="dba",
            )
        )
        await session.commit()
        await session.refresh(conversation)

    client = create_test_client(session_factory)
    response = client.post(
        "/api/inspection-tasks/draft",
        json={"conversation_id": conversation.id},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["source_conversation_id"] == conversation.id
    assert payload["name"] == "Peets Weekly Inspection"
    assert payload["prompt_template"] == "请巡检 peets-prod-member-mysql 最近 30 天状态"


def test_create_and_list_tasks_round_trip(session_factory):
    client = create_test_client(session_factory)

    response = client.post(
        "/api/inspection-tasks",
        json={
            "name": "Peets Daily Inspection",
            "agent_id": "dba",
            "skill_id": "volcengine-rds-health-analyzer",
            "prompt_template": "请巡检 peets-prod-pos-mysql 最近 7 天状态",
            "target_payload": {"instance_name": "peets-prod-pos-mysql"},
            "cron_expr": "0 9 * * *",
            "enabled": True,
            "source_conversation_id": None,
            "now": "2026-03-11T08:00:00",
        },
    )

    assert response.status_code == 200
    created = response.json()
    assert created["name"] == "Peets Daily Inspection"
    assert created["next_run_at"] == "2026-03-11T09:00:00.000"

    list_response = client.get("/api/inspection-tasks")
    assert list_response.status_code == 200
    payload = list_response.json()
    assert len(payload) == 1
    assert payload[0]["id"] == created["id"]
    assert payload[0]["last_status"] == "idle"


def test_trigger_route_returns_created_run(session_factory, monkeypatch):
    client = create_test_client(session_factory)

    created = client.post(
        "/api/inspection-tasks",
        json={
            "name": "Peets Daily Inspection",
            "agent_id": "dba",
            "skill_id": "volcengine-rds-health-analyzer",
            "prompt_template": "请巡检 peets-prod-pos-mysql 最近 7 天状态",
            "target_payload": {"instance_name": "peets-prod-pos-mysql"},
            "cron_expr": "0 9 * * *",
            "enabled": True,
            "now": "2026-03-11T08:00:00",
        },
    ).json()

    async def fake_execute_inspection_task(
        task_id,
        *,
        trigger_type,
        session_factory,
        now=None,
        agent_runner=None,
    ):
        assert task_id == created["id"]
        assert trigger_type == "manual"
        return {
            "id": "run-1",
            "task_id": task_id,
            "trigger_type": "manual",
            "status": "running",
            "conversation_id": None,
            "started_at": datetime(2026, 3, 11, 8, 30).isoformat(timespec="milliseconds"),
            "finished_at": None,
            "error_message": None,
        }

    monkeypatch.setattr(
        inspection_tasks_router,
        "execute_inspection_task",
        fake_execute_inspection_task,
    )

    response = client.post(f"/api/inspection-tasks/{created['id']}/trigger")

    assert response.status_code == 200
    payload = response.json()
    assert payload["task_id"] == created["id"]
    assert payload["trigger_type"] == "manual"
    assert payload["status"] == "running"
