from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.routers import conversations as conversations_router


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
