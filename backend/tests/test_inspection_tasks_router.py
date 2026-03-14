import sys
import types
import json
from datetime import datetime

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

def _install_dependency_stubs() -> None:
    if "deepagents" not in sys.modules:
        deepagents_module = types.ModuleType("deepagents")
        deepagents_module.create_deep_agent = lambda *args, **kwargs: None
        deepagents_module.SubAgent = dict
        deepagents_module.__path__ = []
        sys.modules["deepagents"] = deepagents_module
    elif not hasattr(sys.modules["deepagents"], "SubAgent"):
        sys.modules["deepagents"].SubAgent = dict

    if "deepagents.backends" not in sys.modules:
        backends_module = types.ModuleType("deepagents.backends")
        backends_module.CompositeBackend = type("CompositeBackend", (), {})
        backends_module.StoreBackend = type("StoreBackend", (), {})
        backends_module.__path__ = []
        sys.modules["deepagents.backends"] = backends_module

    if "deepagents.backends.local_shell" not in sys.modules:
        local_shell_module = types.ModuleType("deepagents.backends.local_shell")
        local_shell_module.LocalShellBackend = type("LocalShellBackend", (), {})
        sys.modules["deepagents.backends.local_shell"] = local_shell_module

    if "deepagents.backends.protocol" not in sys.modules:
        protocol_module = types.ModuleType("deepagents.backends.protocol")
        protocol_module.ExecuteResponse = type("ExecuteResponse", (), {})
        sys.modules["deepagents.backends.protocol"] = protocol_module

    if "langchain_anthropic" not in sys.modules:
        anthropic_module = types.ModuleType("langchain_anthropic")
        anthropic_module.ChatAnthropic = type("ChatAnthropic", (), {})
        sys.modules["langchain_anthropic"] = anthropic_module

    if "langgraph.checkpoint.sqlite.aio" not in sys.modules:
        checkpoint_module = types.ModuleType("langgraph.checkpoint.sqlite.aio")
        checkpoint_module.AsyncSqliteSaver = type("AsyncSqliteSaver", (), {})
        sys.modules["langgraph.checkpoint.sqlite.aio"] = checkpoint_module

    if "langgraph.store.sqlite.aio" not in sys.modules:
        store_module = types.ModuleType("langgraph.store.sqlite.aio")
        store_module.AsyncSqliteStore = type("AsyncSqliteStore", (), {})
        sys.modules["langgraph.store.sqlite.aio"] = store_module


_install_dependency_stubs()

from api.routers import inspection_tasks as inspection_tasks_router
from models import Conversation, InspectionTask, InspectionTaskRun, Message


def create_test_client(session_factory):
    app = FastAPI()
    inspection_tasks_router.AsyncSessionLocal = session_factory
    app.include_router(inspection_tasks_router.router)
    return TestClient(app)


def parse_sse_events(payload: str) -> list[dict]:
    return [
        json.loads(line[6:])
        for line in payload.splitlines()
        if line.startswith("data: ")
    ]


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
                content="Please inspect peets-prod-member-mysql for the last 30 days",
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
    assert payload["prompt_template"] == "Please inspect peets-prod-member-mysql for the last 30 days"


def test_create_and_list_tasks_round_trip(session_factory):
    client = create_test_client(session_factory)

    response = client.post(
        "/api/inspection-tasks",
        json={
            "name": "Peets Daily Inspection",
            "agent_id": "dba",
            "skill_id": "volcengine-rds-health-analyzer",
            "prompt_template": "Please inspect peets-prod-pos-mysql for the last 7 days",
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


@pytest.mark.asyncio
async def test_list_tasks_falls_back_for_removed_legacy_agent_id(session_factory):
    async with session_factory() as session:
        task = InspectionTask(
            name="Legacy task",
            source_conversation_id=None,
            agent_id="orchestrator",
            skill_id=None,
            prompt_template="Please inspect the environment",
            target_payload=None,
            schedule_type="cron",
            cron_expr="0 9 * * *",
            enabled=True,
            last_status="idle",
        )
        session.add(task)
        await session.commit()

    client = create_test_client(session_factory)
    response = client.get("/api/inspection-tasks")

    assert response.status_code == 200
    payload = response.json()
    assert payload[0]["agent_id"] == "router"


def test_create_from_conversation_message_route_returns_created_task(
    session_factory,
    monkeypatch,
):
    client = create_test_client(session_factory)

    async def fake_create_from_message(
        conversation_id,
        message,
        *,
        session_factory,
        now=None,
        previous_context=None,
    ):
        assert conversation_id == "conv-1"
        assert message == "Generate a scheduled task and run it every day at 09:00"
        assert now == datetime(2026, 3, 11, 8, 0)
        assert previous_context is None
        return {
            "status": "created",
            "intent_analysis": {
                "intent_matched": True,
                "outcome": "created",
                "cron_expr": "0 9 * * *",
                "summary": "已命中定时任务创建意图，识别到调度表达式 0 9 * * *，并已创建任务「Peets Daily Inspection」。",
                "reason": None,
            },
            "task": {
                "id": "task-1",
                "name": "Peets Daily Inspection",
                "source_conversation_id": conversation_id,
                "agent_id": "dba",
                "skill_id": "volcengine-rds-health-analyzer",
                "prompt_template": "Inspect peets-prod-pos-mysql for slow queries",
                "target_payload": {"instance_name": "peets-prod-pos-mysql"},
                "schedule_type": "cron",
                "cron_expr": "0 9 * * *",
                "enabled": True,
                "last_run_at": None,
                "next_run_at": "2026-03-11T09:00:00.000",
                "last_status": "idle",
                "created_at": "2026-03-11T08:00:00.000",
                "updated_at": "2026-03-11T08:00:00.000",
            },
        }

    monkeypatch.setattr(
        inspection_tasks_router,
        "create_inspection_task_from_conversation_message",
        fake_create_from_message,
    )

    response = client.post(
        "/api/inspection-tasks/from-conversation-message",
        json={
            "conversation_id": "conv-1",
            "message": "Generate a scheduled task and run it every day at 09:00",
            "now": "2026-03-11T08:00:00",
        },
    )

    assert response.status_code == 200
    assert response.json()["status"] == "created"
    assert response.json()["task"]["id"] == "task-1"
    assert response.json()["intent_analysis"]["intent_matched"] is True
    assert response.json()["intent_analysis"]["outcome"] == "created"


def test_create_from_conversation_message_route_returns_not_task_creation(
    session_factory,
    monkeypatch,
):
    client = create_test_client(session_factory)

    async def fake_create_from_message(
        conversation_id,
        message,
        *,
        session_factory,
        now=None,
        previous_context=None,
    ):
        assert conversation_id == "conv-1"
        assert message == "Can you summarize the latest findings?"
        assert now is None
        assert previous_context is None
        return {"status": "not_task_creation"}

    monkeypatch.setattr(
        inspection_tasks_router,
        "create_inspection_task_from_conversation_message",
        fake_create_from_message,
    )

    response = client.post(
        "/api/inspection-tasks/from-conversation-message",
        json={
            "conversation_id": "conv-1",
            "message": "Can you summarize the latest findings?",
        },
    )

    assert response.status_code == 200
    assert response.json() == {"status": "not_task_creation"}
    assert "intent_analysis" not in response.json()


def test_create_from_conversation_message_route_returns_error_status(
    session_factory,
    monkeypatch,
):
    client = create_test_client(session_factory)

    async def fake_create_from_message(
        conversation_id,
        message,
        *,
        session_factory,
        now=None,
        previous_context=None,
    ):
        assert conversation_id == "conv-1"
        assert message == "Create a scheduled task for this conversation"
        assert now is None
        assert previous_context is None
        return {
            "status": "error",
            "message": "未能从当前这句话中识别完整调度时间，请补充执行频率或具体时间。",
            "intent_analysis": {
                "intent_matched": True,
                "outcome": "error",
                "cron_expr": None,
                "summary": "已命中定时任务创建意图，未完成创建。调度表达式：未识别。 原因：未能从当前这句话中识别完整调度时间，请补充执行频率或具体时间。",
                "reason": "未能从当前这句话中识别完整调度时间，请补充执行频率或具体时间。",
            },
        }

    monkeypatch.setattr(
        inspection_tasks_router,
        "create_inspection_task_from_conversation_message",
        fake_create_from_message,
    )

    response = client.post(
        "/api/inspection-tasks/from-conversation-message",
        json={
            "conversation_id": "conv-1",
            "message": "Create a scheduled task for this conversation",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload == {
        "status": "error",
        "message": "未能从当前这句话中识别完整调度时间，请补充执行频率或具体时间。",
        "intent_analysis": {
            "intent_matched": True,
            "outcome": "error",
            "cron_expr": None,
            "summary": "已命中定时任务创建意图，未完成创建。调度表达式：未识别。 原因：未能从当前这句话中识别完整调度时间，请补充执行频率或具体时间。",
            "reason": "未能从当前这句话中识别完整调度时间，请补充执行频率或具体时间。",
        },
    }


def test_trigger_route_returns_created_run(session_factory, monkeypatch):
    client = create_test_client(session_factory)

    created = client.post(
        "/api/inspection-tasks",
        json={
            "name": "Peets Daily Inspection",
            "agent_id": "dba",
            "skill_id": "volcengine-rds-health-analyzer",
            "prompt_template": "Please inspect peets-prod-pos-mysql for the last 7 days",
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


def test_delete_task_route_deletes_task(session_factory):
    client = create_test_client(session_factory)

    created = client.post(
        "/api/inspection-tasks",
        json={
            "name": "Peets Daily Inspection",
            "agent_id": "dba",
            "skill_id": "volcengine-rds-health-analyzer",
            "prompt_template": "Please inspect peets-prod-pos-mysql for the last 7 days",
            "target_payload": {"instance_name": "peets-prod-pos-mysql"},
            "cron_expr": "0 9 * * *",
            "enabled": True,
            "now": "2026-03-11T08:00:00",
        },
    ).json()

    response = client.delete(f"/api/inspection-tasks/{created['id']}")

    assert response.status_code == 200
    assert response.json() == {"status": "deleted", "task_id": created["id"]}

    list_response = client.get("/api/inspection-tasks")
    assert list_response.status_code == 200
    assert list_response.json() == []


@pytest.mark.asyncio
async def test_run_conversation_stream_route_replays_history_and_finishes(session_factory):
    started_at = datetime(2026, 3, 11, 8, 30)
    finished_at = datetime(2026, 3, 11, 8, 31)

    async with session_factory() as session:
        conversation = Conversation(
            title="Peets Daily Inspection 路 03-11 08:30",
            source="task",
            agent_id="dba",
            source_task_id="task-1",
            source_task_run_id="run-1",
            source_task_trigger_type="manual",
        )
        task = InspectionTask(
            id="task-1",
            name="Peets Daily Inspection",
            source_conversation_id=None,
            agent_id="dba",
            skill_id="volcengine-rds-health-analyzer",
            prompt_template="Inspect peets-prod-pos-mysql for slow queries",
            target_payload={"instance_name": "peets-prod-pos-mysql"},
            schedule_type="cron",
            cron_expr="0 9 * * *",
            enabled=True,
            last_status="succeeded",
        )
        session.add_all([conversation, task])
        await session.flush()

        run = InspectionTaskRun(
            id="run-1",
            task_id=task.id,
            trigger_type="manual",
            status="succeeded",
            conversation_id=conversation.id,
            started_at=started_at,
            finished_at=finished_at,
        )
        first_message = Message(
            id="msg-1",
            conversation_id=conversation.id,
            role="user",
            content="Inspect peets-prod-pos-mysql for slow queries",
            type="text",
            agent_id="dba",
        )
        second_message = Message(
            id="msg-2",
            conversation_id=conversation.id,
            role="assistant",
            content="Inspection complete",
            type="text",
            agent_id="dba",
        )
        session.add_all([run, first_message, second_message])
        await session.commit()

    client = create_test_client(session_factory)
    with client.stream(
        "GET",
        "/api/inspection-tasks/runs/run-1/conversation/stream",
    ) as response:
        payload = "".join(
            chunk.decode("utf-8") if isinstance(chunk, bytes) else chunk
            for chunk in response.iter_text()
        )

    events = parse_sse_events(payload)

    assert response.status_code == 200
    assert [event["type"] for event in events] == [
        "history_start",
        "message",
        "message",
        "history_done",
        "run_status",
        "done",
    ]
    assert events[0]["conversation_id"] is not None
    assert events[0]["agent_id"] == "dba"
    assert events[0]["title"] == "Peets Daily Inspection 路 03-11 08:30"
    assert events[1]["message"]["id"] == "msg-1"
    assert events[2]["message"]["content"] == "Inspection complete"
    assert events[4]["status"] == "succeeded"
    assert events[5]["status"] == "succeeded"


@pytest.mark.asyncio
async def test_stream_inspection_task_run_conversation_tails_messages_until_run_finishes(
    session_factory,
    monkeypatch,
):
    conversation = Conversation(
        id="conv-1",
        title="Peets Daily Inspection 路 03-11 08:30",
        source="task",
        agent_id="dba",
    )
    first_message = Message(
        id="msg-1",
        conversation_id="conv-1",
        role="user",
        content="Inspect peets-prod-pos-mysql for slow queries",
        type="text",
        agent_id="dba",
    )
    second_message = Message(
        id="msg-2",
        conversation_id="conv-1",
        role="assistant",
        content="Inspection complete",
        type="text",
        agent_id="dba",
    )

    snapshots = iter(
        [
            (
                InspectionTaskRun(
                    id="run-1",
                    task_id="task-1",
                    trigger_type="manual",
                    status="running",
                    conversation_id="conv-1",
                    started_at=datetime(2026, 3, 11, 8, 30),
                ),
                conversation,
                [first_message],
            ),
            (
                InspectionTaskRun(
                    id="run-1",
                    task_id="task-1",
                    trigger_type="manual",
                    status="running",
                    conversation_id="conv-1",
                    started_at=datetime(2026, 3, 11, 8, 30),
                ),
                conversation,
                [first_message],
            ),
            (
                InspectionTaskRun(
                    id="run-1",
                    task_id="task-1",
                    trigger_type="manual",
                    status="succeeded",
                    conversation_id="conv-1",
                    started_at=datetime(2026, 3, 11, 8, 30),
                    finished_at=datetime(2026, 3, 11, 8, 31),
                ),
                conversation,
                [first_message, second_message],
            ),
        ]
    )

    async def fake_load_run_stream_state(run_id: str, *, session_factory):
        assert run_id == "run-1"
        return next(snapshots)

    monkeypatch.setattr(
        inspection_tasks_router,
        "_load_inspection_task_run_stream_state",
        fake_load_run_stream_state,
    )
    monkeypatch.setattr(
        inspection_tasks_router,
        "_RUN_CONVERSATION_STREAM_POLL_INTERVAL_SECONDS",
        0,
    )

    chunks: list[str] = []
    async for chunk in inspection_tasks_router._stream_inspection_task_run_conversation(
        "run-1",
        session_factory=session_factory,
    ):
        chunks.append(chunk)

    events = parse_sse_events("".join(chunks))

    assert [event["type"] for event in events] == [
        "history_start",
        "message",
        "history_done",
        "run_status",
        "message",
        "run_status",
        "done",
    ]
    assert events[1]["message"]["id"] == "msg-1"
    assert events[3]["status"] == "running"
    assert events[4]["message"]["id"] == "msg-2"
    assert events[5]["status"] == "succeeded"
    assert events[6]["status"] == "succeeded"
