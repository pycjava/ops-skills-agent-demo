from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.routers import rag as rag_router


class FakeRagService:
    async def status(self):
        return {
            "enabled": True,
            "document_count": 3,
            "chunk_count": 7,
            "last_reindex_at": "2026-03-17T10:00:00",
        }

    async def search(
        self,
        query: str,
        *,
        conversation_id: str | None,
        agent_id: str | None,
        limit: int | None = None,
    ):
        return [
            {
                "source_type": "attachment",
                "source_id": "attachment-1",
                "path_or_filename": "data/conversation_attachments/conv-1/query.sql",
                "title": "query.sql",
                "content": "select * from orders;",
                "distance": 0.13,
            }
        ]

    async def reindex(
        self,
        *,
        scope: str,
        conversation_id: str | None = None,
        agent_id: str | None = None,
    ):
        return {
            "enabled": True,
            "scope": scope,
            "conversation_id": conversation_id,
            "agent_id": agent_id,
            "sources_indexed": 2,
            "chunks_indexed": 5,
            "last_reindex_at": "2026-03-17T10:05:00",
        }


def create_test_client(monkeypatch):
    app = FastAPI()
    monkeypatch.setattr(rag_router, "get_rag_service", lambda: FakeRagService())
    app.include_router(rag_router.router)
    return TestClient(app)


def test_rag_status_route_returns_index_summary(monkeypatch):
    client = create_test_client(monkeypatch)

    response = client.get("/api/rag/status")

    assert response.status_code == 200
    assert response.json()["enabled"] is True
    assert response.json()["document_count"] == 3


def test_rag_search_route_returns_scoped_results(monkeypatch):
    client = create_test_client(monkeypatch)

    response = client.post(
        "/api/rag/search",
        json={
            "query": "find failed orders query",
            "conversation_id": "conv-1",
            "agent_id": "db-runtime",
            "limit": 4,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["items"][0]["source_id"] == "attachment-1"
    assert payload["items"][0]["title"] == "query.sql"


def test_rag_reindex_route_returns_summary(monkeypatch):
    client = create_test_client(monkeypatch)

    response = client.post(
        "/api/rag/reindex",
        json={
            "scope": "conversation_attachments",
            "conversation_id": "conv-9",
            "agent_id": "general",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["scope"] == "conversation_attachments"
    assert payload["conversation_id"] == "conv-9"
    assert payload["sources_indexed"] == 2
