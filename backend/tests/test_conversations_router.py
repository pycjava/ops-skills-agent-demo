import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.routers import conversations as conversations_router
from models import Conversation, Message


def create_test_client(session_factory):
    app = FastAPI()
    conversations_router.AsyncSessionLocal = session_factory
    app.include_router(conversations_router.router)
    return TestClient(app)


def test_patch_conversation_title_success(session_factory, seeded_conversation):
    client = create_test_client(session_factory)

    response = client.patch(
        f"/api/conversations/{seeded_conversation.id}",
        json={"title": "新的标题"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["id"] == seeded_conversation.id
    assert payload["title"] == "新的标题"


def test_patch_conversation_title_rejects_empty_and_too_long(
    session_factory, seeded_conversation
):
    client = create_test_client(session_factory)

    empty_response = client.patch(
        f"/api/conversations/{seeded_conversation.id}",
        json={"title": "   "},
    )
    long_response = client.patch(
        f"/api/conversations/{seeded_conversation.id}",
        json={"title": "a" * 201},
    )

    assert empty_response.status_code == 400
    assert long_response.status_code == 400


def test_patch_conversation_title_returns_404_for_unknown_conversation(session_factory):
    client = create_test_client(session_factory)

    response = client.patch(
        "/api/conversations/missing-conversation",
        json={"title": "新的标题"},
    )

    assert response.status_code == 404


def test_patch_conversation_title_rejects_invalid_body(
    session_factory, seeded_conversation
):
    client = create_test_client(session_factory)

    response = client.patch(
        f"/api/conversations/{seeded_conversation.id}",
        json={},
    )

    assert response.status_code == 400


@pytest.mark.asyncio
async def test_get_messages_returns_attachment_snapshot(
    session_factory, seeded_conversation
):
    async with session_factory() as session:
        session.add(
            Message(
                conversation_id=seeded_conversation.id,
                role="user",
                content="attachment summary request",
                type="text",
                agent_id="general",
                attachments_snapshot=[
                    {
                        "id": "att-1",
                        "original_name": "report-a.md",
                        "stored_name": "report-a.md",
                        "relative_path": f"data/conversation_attachments/{seeded_conversation.id}/report-a.md",
                        "mime_type": "text/markdown",
                        "size_bytes": 120,
                        "created_at": "2026-03-10T10:00:00.000",
                    }
                ],
            )
        )
        await session.commit()

    client = create_test_client(session_factory)
    response = client.get(f"/api/conversations/{seeded_conversation.id}/messages")

    assert response.status_code == 200
    payload = response.json()
    assert payload[0]["attachments_snapshot"] == [
        {
            "id": "att-1",
            "original_name": "report-a.md",
            "stored_name": "report-a.md",
            "relative_path": f"data/conversation_attachments/{seeded_conversation.id}/report-a.md",
            "mime_type": "text/markdown",
            "size_bytes": 120,
            "created_at": "2026-03-10T10:00:00.000",
        }
    ]


@pytest.mark.asyncio
async def test_list_conversations_includes_task_source_metadata(session_factory):
    async with session_factory() as session:
        conversation = Conversation(
            title="任务生成的巡检",
            source="task",
            agent_id="dba",
            source_task_id="task-1",
            source_task_run_id="run-1",
            source_task_trigger_type="scheduled",
        )
        session.add(conversation)
        await session.commit()

    client = create_test_client(session_factory)
    response = client.get("/api/conversations")

    assert response.status_code == 200
    payload = response.json()
    assert payload[0]["source_task_id"] == "task-1"
    assert payload[0]["source_task_run_id"] == "run-1"
    assert payload[0]["source_task_trigger_type"] == "scheduled"
