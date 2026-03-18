from __future__ import annotations

import json
from pathlib import Path

import pytest

from services.rag import RagService, RagSourceDocument


class FakeEmbeddingClient:
    def __init__(self, vector: list[float] | None = None):
        self.vector = vector or [0.1, 0.2, 0.3]
        self.calls: list[list[str]] = []

    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        self.calls.append(list(texts))
        return [list(self.vector) for _ in texts]


class FakeIndexBackend:
    def __init__(self):
        self.available = True
        self.disabled_reason: str | None = None
        self.query_results: dict[tuple[str, str | None], list[dict]] = {}
        self.upserted_chunks: list[dict] = []
        self.deleted_sources: list[tuple[str, str]] = []

    async def query(
        self,
        *,
        query_embedding: list[float],
        limit: int,
        where: dict[str, object] | None = None,
    ) -> list[dict]:
        source_type = str((where or {}).get("source_type") or "")
        conversation_id = where.get("conversation_id") if where else None
        return list(self.query_results.get((source_type, conversation_id), []))[:limit]

    async def upsert_chunks(self, chunks: list[dict]) -> int:
        self.upserted_chunks.extend(chunks)
        return len(chunks)

    async def delete_source(self, *, source_type: str, source_id: str) -> int:
        self.deleted_sources.append((source_type, source_id))
        return 1

    async def list_metadatas(self) -> list[dict]:
        return [chunk["metadata"] for chunk in self.upserted_chunks]


@pytest.mark.asyncio
async def test_rag_service_search_combines_current_attachment_and_allowed_memory_sources(
    monkeypatch,
    tmp_path,
):
    backend = FakeIndexBackend()
    backend.query_results[("attachment", "conv-1")] = [
        {
            "id": "attachment-1#0",
            "document": "SELECT * FROM orders WHERE status = 'failed';",
            "metadata": {
                "source_type": "attachment",
                "source_id": "attachment-1",
                "conversation_id": "conv-1",
                "path_or_filename": "data/conversation_attachments/conv-1/query.sql",
                "title": "query.sql",
            },
            "distance": 0.19,
        }
    ]
    backend.query_results[("memory", None)] = [
        {
            "id": "memory-1#0",
            "document": "prod mysql endpoint is db-a.internal.example.com",
            "metadata": {
                "source_type": "memory",
                "source_id": "/memories/agents/db-runtime/instances.md",
                "path_or_filename": "/memories/agents/db-runtime/instances.md",
                "title": "instances.md",
            },
            "distance": 0.08,
        },
        {
            "id": "memory-2#0",
            "document": "ops-only secret that should not be exposed",
            "metadata": {
                "source_type": "memory",
                "source_id": "/memories/agents/ops-runtime/secrets.md",
                "path_or_filename": "/memories/agents/ops-runtime/secrets.md",
                "title": "secrets.md",
            },
            "distance": 0.01,
        },
        {
            "id": "memory-3#0",
            "document": "Always cite the source path in the answer.",
            "metadata": {
                "source_type": "memory",
                "source_id": "/memories/instructions.txt",
                "path_or_filename": "/memories/instructions.txt",
                "title": "instructions.txt",
            },
            "distance": 0.24,
        },
    ]

    monkeypatch.setattr(
        "services.rag.get_agent_memory_roots",
        lambda agent_id: ("/memories/agents/db-runtime/",),
    )

    service = RagService(
        backend=backend,
        embedding_client=FakeEmbeddingClient(),
        status_path=tmp_path / "rag-status.json",
    )

    results = await service.search(
        "find the prod mysql endpoint",
        conversation_id="conv-1",
        agent_id="db-runtime",
        limit=4,
    )

    assert [result["source_id"] for result in results] == [
        "/memories/agents/db-runtime/instances.md",
        "attachment-1",
        "/memories/instructions.txt",
    ]
    assert all("ops-runtime" not in result["source_id"] for result in results)

    context = await service.build_context(
        "find the prod mysql endpoint",
        conversation_id="conv-1",
        agent_id="db-runtime",
        limit=4,
    )

    assert context is not None
    assert "<rag_context>" not in context
    assert "db-a.internal.example.com" in context
    assert "query.sql" in context
    assert "/memories/instructions.txt" in context
    assert "ops-only secret" not in context


@pytest.mark.asyncio
async def test_rag_service_reindex_upserts_attachment_and_memory_sources_and_persists_status(
    monkeypatch,
    tmp_path,
):
    backend = FakeIndexBackend()
    status_path = tmp_path / "rag-status.json"

    async def fake_load_memory_source_documents(*, agent_id=None):
        return [
            RagSourceDocument(
                source_type="memory",
                source_id="/memories/agents/general/guide.md",
                title="guide.md",
                path_or_filename="/memories/agents/general/guide.md",
                content="general operating guidance",
                conversation_id=None,
                agent_id="general",
                updated_at="2026-03-17T08:00:00",
            )
        ]

    async def fake_load_attachment_source_documents(*, conversation_id=None):
        return [
            RagSourceDocument(
                source_type="attachment",
                source_id="attachment-9",
                title="report.md",
                path_or_filename="data/conversation_attachments/conv-9/report.md",
                content="error report details",
                conversation_id="conv-9",
                agent_id=None,
                updated_at="2026-03-17T09:00:00",
            )
        ]

    monkeypatch.setattr(
        "services.rag.load_memory_source_documents",
        fake_load_memory_source_documents,
    )
    monkeypatch.setattr(
        "services.rag.load_attachment_source_documents",
        fake_load_attachment_source_documents,
    )

    service = RagService(
        backend=backend,
        embedding_client=FakeEmbeddingClient(),
        status_path=status_path,
    )

    summary = await service.reindex(scope="all")

    assert summary["scope"] == "all"
    assert summary["sources_indexed"] == 2
    assert summary["chunks_indexed"] == 2
    assert len(backend.upserted_chunks) == 2

    persisted = json.loads(status_path.read_text(encoding="utf-8"))
    assert persisted["scope"] == "all"
    assert persisted["sources_indexed"] == 2

    status = await service.status()

    assert status["enabled"] is True
    assert status["document_count"] == 2
    assert status["chunk_count"] == 2
    assert status["last_reindex_at"]

