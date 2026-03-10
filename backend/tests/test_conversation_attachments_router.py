import asyncio
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from api.routers import conversation_attachments as conversation_attachments_router
from models import Conversation
from services import conversation_attachments as attachment_service


def create_test_client(session_factory):
    app = FastAPI()
    conversation_attachments_router.AsyncSessionLocal = session_factory
    app.include_router(conversation_attachments_router.router)
    return TestClient(app)


def test_upload_attachment_creates_conversation_and_supports_list_and_delete(
    session_factory, tmp_path, monkeypatch
):
    client = create_test_client(session_factory)
    monkeypatch.setattr(attachment_service, "ATTACHMENTS_ROOT", tmp_path)

    upload_response = client.post(
        "/api/conversations/attachments",
        data={"agent_id": "dba"},
        files={"file": ("sample.csv", b"id,name\n1,alice\n", "text/csv")},
    )

    assert upload_response.status_code == 200
    payload = upload_response.json()
    conversation = payload["conversation"]
    attachment = payload["attachment"]

    assert conversation["agent_id"] == "dba"
    assert attachment["conversation_id"] == conversation["id"]
    assert attachment["original_name"] == "sample.csv"
    assert attachment["mime_type"] == "text/csv"
    assert attachment["size_bytes"] == len(b"id,name\n1,alice\n")

    stored_file = tmp_path / conversation["id"] / attachment["stored_name"]
    assert stored_file.exists()
    assert stored_file.read_text(encoding="utf-8") == "id,name\n1,alice\n"

    list_response = client.get(f"/api/conversations/{conversation['id']}/attachments")
    assert list_response.status_code == 200
    attachments = list_response.json()
    assert len(attachments) == 1
    assert attachments[0]["id"] == attachment["id"]

    delete_response = client.delete(
        f"/api/conversations/{conversation['id']}/attachments/{attachment['id']}"
    )
    assert delete_response.status_code == 200
    assert delete_response.json() == {"ok": True}
    assert not stored_file.exists()

    list_after_delete_response = client.get(
        f"/api/conversations/{conversation['id']}/attachments"
    )
    assert list_after_delete_response.status_code == 200
    assert list_after_delete_response.json() == []


def test_upload_attachment_rejects_unsupported_extension(
    session_factory, tmp_path, monkeypatch
):
    client = create_test_client(session_factory)
    monkeypatch.setattr(attachment_service, "ATTACHMENTS_ROOT", tmp_path)

    response = client.post(
        "/api/conversations/attachments",
        data={"agent_id": "general"},
        files={"file": ("report.pdf", b"%PDF-1.4", "application/pdf")},
    )

    assert response.status_code == 400
    assert "attachment" in response.json()["detail"].lower()

    created_paths = [
        path.relative_to(tmp_path).as_posix()
        for path in Path(tmp_path).rglob("*")
        if path.name != "test.db"
    ]
    assert created_paths == []

    async def count_conversations() -> int:
        async with session_factory() as session:
            result = await session.execute(select(func.count(Conversation.id)))
            return int(result.scalar() or 0)

    assert asyncio.run(count_conversations()) == 0


def test_upload_attachment_accepts_generic_mime_for_supported_text_file(
    session_factory, tmp_path, monkeypatch
):
    client = create_test_client(session_factory)
    monkeypatch.setattr(attachment_service, "ATTACHMENTS_ROOT", tmp_path)

    response = client.post(
        "/api/conversations/attachments",
        data={"agent_id": "ops"},
        files={"file": ("server.log", b"line-1\nline-2\n", "application/octet-stream")},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["attachment"]["original_name"] == "server.log"
    assert payload["attachment"]["mime_type"] == "application/octet-stream"


def test_upload_attachment_accepts_noncanonical_csv_mime(
    session_factory, tmp_path, monkeypatch
):
    client = create_test_client(session_factory)
    monkeypatch.setattr(attachment_service, "ATTACHMENTS_ROOT", tmp_path)

    response = client.post(
        "/api/conversations/attachments",
        data={"agent_id": "ops"},
        files={"file": ("report.csv", b"id,name\n1,alice\n", "application/vnd.ms-excel")},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["attachment"]["original_name"] == "report.csv"
    assert payload["attachment"]["mime_type"] == "application/vnd.ms-excel"


def test_upload_attachment_rejects_supported_extension_with_binary_content(
    session_factory, tmp_path, monkeypatch
):
    client = create_test_client(session_factory)
    monkeypatch.setattr(attachment_service, "ATTACHMENTS_ROOT", tmp_path)

    response = client.post(
        "/api/conversations/attachments",
        data={"agent_id": "ops"},
        files={"file": ("server.log", b"\x80\xff\x80", "application/octet-stream")},
    )

    assert response.status_code == 400
    assert "encoding" in response.json()["detail"].lower()


def test_upload_attachment_allows_fifty_attachments_and_rejects_fifty_first(
    session_factory, tmp_path, monkeypatch
):
    client = create_test_client(session_factory)
    monkeypatch.setattr(attachment_service, "ATTACHMENTS_ROOT", tmp_path)

    conversation_id = None

    for index in range(50):
        data = {"agent_id": "ops"} if conversation_id is None else {"conversation_id": conversation_id}
        response = client.post(
            "/api/conversations/attachments",
            data=data,
            files={
                "file": (
                    f"notes-{index}.txt",
                    f"line-{index}\n".encode("utf-8"),
                    "text/plain",
                )
            },
        )

        assert response.status_code == 200
        payload = response.json()
        conversation_id = payload["conversation"]["id"]

    overflow_response = client.post(
        "/api/conversations/attachments",
        data={"conversation_id": conversation_id},
        files={"file": ("notes-overflow.txt", b"overflow\n", "text/plain")},
    )

    assert overflow_response.status_code == 400
    assert overflow_response.json()["detail"] == "Too many attachments in conversation"
