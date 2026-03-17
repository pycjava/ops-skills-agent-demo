from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import httpx
from sqlalchemy import select

from agent_profiles import get_agent_memory_roots
from config import (
    RAG_CHROMA_PATH,
    RAG_CHUNK_OVERLAP,
    RAG_CHUNK_SIZE,
    RAG_COLLECTION_NAME,
    RAG_EMBEDDING_API_KEY,
    RAG_EMBEDDING_API_URL,
    RAG_EMBEDDING_MODEL,
    RAG_ENABLED,
    RAG_STATUS_PATH,
    RAG_TOP_K,
)
from db.session import AsyncSessionLocal
from models import ConversationAttachment
from utils.logger import logger


MEMORY_INSTRUCTIONS_PATH = "/memories/instructions.txt"


@dataclass(slots=True)
class RagSourceDocument:
    source_type: str
    source_id: str
    title: str
    path_or_filename: str
    content: str
    conversation_id: str | None = None
    agent_id: str | None = None
    updated_at: str | None = None


class RemoteEmbeddingClient:
    def __init__(
        self,
        *,
        api_url: str,
        model: str,
        api_key: str = "",
        timeout_seconds: float = 30.0,
    ) -> None:
        self.api_url = api_url.strip()
        self.model = model.strip()
        self.api_key = api_key.strip()
        self.timeout_seconds = timeout_seconds

    @property
    def available(self) -> bool:
        return bool(self.api_url and self.model)

    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        if not self.available:
            raise RuntimeError("RAG embedding client is not configured")

        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
            response = await client.post(
                self.api_url,
                headers=headers,
                json={"model": self.model, "input": texts},
            )
            response.raise_for_status()
            payload = response.json()

        raw_items = payload.get("data")
        if not isinstance(raw_items, list):
            raise RuntimeError("Invalid embedding response payload")

        sorted_items = sorted(
            raw_items,
            key=lambda item: int(item.get("index", 0))
            if isinstance(item, dict)
            else 0,
        )
        embeddings: list[list[float]] = []
        for item in sorted_items:
            if not isinstance(item, dict) or not isinstance(item.get("embedding"), list):
                raise RuntimeError("Embedding payload is missing vectors")
            embeddings.append([float(value) for value in item["embedding"]])

        if len(embeddings) != len(texts):
            raise RuntimeError("Embedding result count does not match input count")

        return embeddings


class ChromaIndexBackend:
    def __init__(self, *, path: str | Path, collection_name: str) -> None:
        self.path = Path(path).resolve()
        self.collection_name = collection_name
        self._client = None
        self._collection = None
        self.available = True
        self.disabled_reason: str | None = None

        try:
            import chromadb  # type: ignore
        except ImportError:
            self.available = False
            self.disabled_reason = "chromadb is not installed"
            self._chromadb = None
            return

        self._chromadb = chromadb
        self.path.mkdir(parents=True, exist_ok=True)

    def _get_collection(self):
        if not self.available:
            raise RuntimeError(self.disabled_reason or "RAG index backend is unavailable")
        if self._client is None:
            self._client = self._chromadb.PersistentClient(path=str(self.path))
        if self._collection is None:
            self._collection = self._client.get_or_create_collection(
                name=self.collection_name
            )
        return self._collection

    async def query(
        self,
        *,
        query_embedding: list[float],
        limit: int,
        where: dict[str, object] | None = None,
    ) -> list[dict]:
        def _run() -> list[dict]:
            collection = self._get_collection()
            raw = collection.query(
                query_embeddings=[query_embedding],
                n_results=max(1, limit),
                where=where or None,
                include=["documents", "metadatas", "distances"],
            )
            ids = raw.get("ids", [[]])[0]
            documents = raw.get("documents", [[]])[0]
            metadatas = raw.get("metadatas", [[]])[0]
            distances = raw.get("distances", [[]])[0]
            rows: list[dict] = []
            for chunk_id, document, metadata, distance in zip(
                ids,
                documents,
                metadatas,
                distances,
            ):
                rows.append(
                    {
                        "id": chunk_id,
                        "document": document,
                        "metadata": metadata or {},
                        "distance": float(distance) if distance is not None else 0.0,
                    }
                )
            return rows

        return await asyncio.to_thread(_run)

    async def upsert_chunks(self, chunks: list[dict]) -> int:
        if not chunks:
            return 0

        def _run() -> int:
            collection = self._get_collection()
            collection.upsert(
                ids=[chunk["id"] for chunk in chunks],
                documents=[chunk["document"] for chunk in chunks],
                metadatas=[chunk["metadata"] for chunk in chunks],
                embeddings=[chunk["embedding"] for chunk in chunks],
            )
            return len(chunks)

        return await asyncio.to_thread(_run)

    async def delete_source(self, *, source_type: str, source_id: str) -> int:
        def _run() -> int:
            collection = self._get_collection()
            rows = collection.get(
                where={"source_type": source_type, "source_id": source_id},
                include=["metadatas"],
            )
            ids = rows.get("ids") or []
            if ids:
                collection.delete(ids=ids)
            return len(ids)

        return await asyncio.to_thread(_run)

    async def list_metadatas(self) -> list[dict]:
        def _run() -> list[dict]:
            collection = self._get_collection()
            rows = collection.get(include=["metadatas"])
            return list(rows.get("metadatas") or [])

        return await asyncio.to_thread(_run)


def _flatten_memory_nodes(nodes: list[dict[str, Any]]) -> list[str]:
    paths: list[str] = []
    for node in nodes:
        if node.get("kind") == "file" and isinstance(node.get("path"), str):
            paths.append(node["path"])
        children = node.get("children")
        if isinstance(children, list):
            paths.extend(_flatten_memory_nodes(children))
    return paths


def _extract_memory_agent_id(path: str) -> str | None:
    prefix = "/memories/agents/"
    if not path.startswith(prefix):
        return None
    suffix = path[len(prefix) :]
    return suffix.split("/", 1)[0] or None


def _memory_path_allowed(path: str, agent_id: str | None) -> bool:
    if path == MEMORY_INSTRUCTIONS_PATH:
        return True
    if not path.startswith("/memories/agents/"):
        return True
    return any(path.startswith(root) for root in get_agent_memory_roots(agent_id))


def _chunk_text(content: str, *, chunk_size: int, overlap: int) -> list[str]:
    text = (content or "").strip()
    if not text:
        return []
    if len(text) <= chunk_size:
        return [text]

    chunks: list[str] = []
    start = 0
    while start < len(text):
        end = min(len(text), start + chunk_size)
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end >= len(text):
            break
        start = max(end - overlap, start + 1)
    return chunks


def _chunk_id(source_type: str, source_id: str, index: int) -> str:
    return f"{source_type}:{source_id}#{index}"


def _serialize_result(row: dict[str, Any]) -> dict[str, Any]:
    metadata = row.get("metadata") or {}
    return {
        "chunk_id": row.get("id"),
        "source_type": metadata.get("source_type"),
        "source_id": metadata.get("source_id"),
        "title": metadata.get("title"),
        "path_or_filename": metadata.get("path_or_filename"),
        "conversation_id": metadata.get("conversation_id"),
        "agent_id": metadata.get("agent_id"),
        "updated_at": metadata.get("updated_at"),
        "content": row.get("document", ""),
        "distance": float(row.get("distance") or 0.0),
    }


def _source_label(result: dict[str, Any]) -> str:
    source_type = result.get("source_type")
    if source_type == "attachment":
        return "attachment"
    if source_type == "memory":
        return "memory"
    return str(source_type or "source")


async def load_memory_source_documents(
    *,
    agent_id: str | None = None,
) -> list[RagSourceDocument]:
    from services.memory import list_memory_tree, read_memory_document

    tree = await list_memory_tree()
    documents: list[RagSourceDocument] = []
    for path in _flatten_memory_nodes(tree):
        if agent_id and not _memory_path_allowed(path, agent_id):
            continue
        document = await read_memory_document(path)
        content = document.get("content", "")
        if not isinstance(content, str) or not content.strip():
            continue
        documents.append(
            RagSourceDocument(
                source_type="memory",
                source_id=path,
                title=str(document.get("name") or Path(path).name),
                path_or_filename=path,
                content=content,
                conversation_id=None,
                agent_id=_extract_memory_agent_id(path),
                updated_at=str(document.get("updated_at") or ""),
            )
        )
    return documents


async def load_attachment_source_documents(
    *,
    conversation_id: str | None = None,
) -> list[RagSourceDocument]:
    from services.conversation_attachments import ATTACHMENTS_ROOT, is_image_attachment_record

    async with AsyncSessionLocal() as session:
        query = select(ConversationAttachment)
        if conversation_id:
            query = query.where(ConversationAttachment.conversation_id == conversation_id)
        query = query.order_by(ConversationAttachment.created_at)
        result = await session.execute(query)
        attachments = list(result.scalars().all())

    documents: list[RagSourceDocument] = []
    for attachment in attachments:
        if is_image_attachment_record(attachment):
            continue

        stored_file = (ATTACHMENTS_ROOT / attachment.conversation_id / attachment.stored_name).resolve()
        if not stored_file.is_file():
            continue

        content = stored_file.read_text(encoding="utf-8").strip()
        if not content:
            continue

        documents.append(
            RagSourceDocument(
                source_type="attachment",
                source_id=attachment.id,
                title=attachment.original_name,
                path_or_filename=attachment.relative_path,
                content=content,
                conversation_id=attachment.conversation_id,
                agent_id=None,
                updated_at=(
                    attachment.created_at.isoformat(timespec="seconds")
                    if attachment.created_at
                    else None
                ),
            )
        )
    return documents


async def build_attachment_source_document(
    attachment: ConversationAttachment | dict[str, Any],
) -> RagSourceDocument | None:
    from services.conversation_attachments import ATTACHMENTS_ROOT, is_image_attachment_record

    if is_image_attachment_record(attachment):
        return None

    conversation_id = str(
        getattr(attachment, "conversation_id", None)
        or attachment.get("conversation_id")
        or ""
    ).strip()
    stored_name = str(
        getattr(attachment, "stored_name", None) or attachment.get("stored_name") or ""
    ).strip()
    relative_path = str(
        getattr(attachment, "relative_path", None)
        or attachment.get("relative_path")
        or ""
    ).strip()
    source_id = str(getattr(attachment, "id", None) or attachment.get("id") or "").strip()
    title = str(
        getattr(attachment, "original_name", None)
        or attachment.get("original_name")
        or stored_name
    ).strip()

    if not conversation_id or not stored_name or not source_id:
        return None

    stored_file = (ATTACHMENTS_ROOT / conversation_id / stored_name).resolve()
    if not stored_file.is_file():
        return None

    content = stored_file.read_text(encoding="utf-8").strip()
    if not content:
        return None

    raw_created_at = getattr(attachment, "created_at", None) or attachment.get("created_at")
    updated_at = (
        raw_created_at.isoformat(timespec="seconds")
        if hasattr(raw_created_at, "isoformat")
        else str(raw_created_at or "")
    )

    return RagSourceDocument(
        source_type="attachment",
        source_id=source_id,
        title=title,
        path_or_filename=relative_path or title,
        content=content,
        conversation_id=conversation_id,
        agent_id=None,
        updated_at=updated_at or None,
    )


async def build_memory_source_document(path: str) -> RagSourceDocument | None:
    from services.memory import read_memory_document

    document = await read_memory_document(path)
    content = document.get("content", "")
    if not isinstance(content, str) or not content.strip():
        return None

    return RagSourceDocument(
        source_type="memory",
        source_id=path,
        title=str(document.get("name") or Path(path).name),
        path_or_filename=path,
        content=content,
        conversation_id=None,
        agent_id=_extract_memory_agent_id(path),
        updated_at=str(document.get("updated_at") or ""),
    )


class RagService:
    def __init__(
        self,
        *,
        backend: Any | None = None,
        embedding_client: Any | None = None,
        status_path: str | Path | None = None,
        top_k: int = RAG_TOP_K,
        chunk_size: int = RAG_CHUNK_SIZE,
        chunk_overlap: int = RAG_CHUNK_OVERLAP,
    ) -> None:
        self.backend = backend or ChromaIndexBackend(
            path=RAG_CHROMA_PATH,
            collection_name=RAG_COLLECTION_NAME,
        )
        self.embedding_client = embedding_client or RemoteEmbeddingClient(
            api_url=RAG_EMBEDDING_API_URL,
            api_key=RAG_EMBEDDING_API_KEY,
            model=RAG_EMBEDDING_MODEL,
        )
        self.status_path = Path(status_path or RAG_STATUS_PATH).resolve()
        self.top_k = top_k
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    def _disabled_reason(self) -> str | None:
        if not RAG_ENABLED:
            return "RAG is disabled by configuration"
        if not getattr(self.backend, "available", True):
            return getattr(self.backend, "disabled_reason", None) or "RAG backend is unavailable"
        if not getattr(self.embedding_client, "available", True):
            return "RAG embedding client is not configured"
        return None

    @property
    def enabled(self) -> bool:
        return self._disabled_reason() is None

    async def _embed_query(self, query: str) -> list[float]:
        embeddings = await self.embedding_client.embed_texts([query])
        if not embeddings:
            raise RuntimeError("RAG embedding client returned no query vector")
        return embeddings[0]

    async def upsert_source_document(self, source: RagSourceDocument) -> int:
        if not self.enabled:
            return 0

        chunks = _chunk_text(
            source.content,
            chunk_size=self.chunk_size,
            overlap=self.chunk_overlap,
        )
        if not chunks:
            await self.backend.delete_source(
                source_type=source.source_type,
                source_id=source.source_id,
            )
            return 0

        embeddings = await self.embedding_client.embed_texts(chunks)
        await self.backend.delete_source(
            source_type=source.source_type,
            source_id=source.source_id,
        )

        payload: list[dict] = []
        for index, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
            payload.append(
                {
                    "id": _chunk_id(source.source_type, source.source_id, index),
                    "document": chunk,
                    "metadata": {
                        "source_type": source.source_type,
                        "source_id": source.source_id,
                        "title": source.title,
                        "path_or_filename": source.path_or_filename,
                        "conversation_id": source.conversation_id,
                        "agent_id": source.agent_id,
                        "updated_at": source.updated_at,
                    },
                    "embedding": embedding,
                }
            )

        return await self.backend.upsert_chunks(payload)

    async def delete_source(self, *, source_type: str, source_id: str) -> int:
        if not getattr(self.backend, "available", True):
            return 0
        return await self.backend.delete_source(source_type=source_type, source_id=source_id)

    async def search(
        self,
        query: str,
        *,
        conversation_id: str | None,
        agent_id: str | None,
        limit: int | None = None,
    ) -> list[dict[str, Any]]:
        if not self.enabled:
            return []

        final_limit = max(1, limit or self.top_k)
        query_embedding = await self._embed_query(query)

        attachment_results: list[dict[str, Any]] = []
        if conversation_id:
            attachment_results = await self.backend.query(
                query_embedding=query_embedding,
                limit=final_limit * 2,
                where={
                    "source_type": "attachment",
                    "conversation_id": conversation_id,
                },
            )

        memory_candidates = await self.backend.query(
            query_embedding=query_embedding,
            limit=final_limit * 4,
            where={"source_type": "memory"},
        )
        memory_results = [
            row
            for row in memory_candidates
            if _memory_path_allowed(
                str((row.get("metadata") or {}).get("source_id") or ""),
                agent_id,
            )
        ]

        combined = [_serialize_result(row) for row in attachment_results + memory_results]
        combined.sort(key=lambda item: (item["distance"], str(item["source_id"])))
        return combined[:final_limit]

    def format_context(
        self,
        results: list[dict[str, Any]],
        *,
        query: str,
    ) -> str | None:
        if not results:
            return None

        lines = [
            "Below are retrieved knowledge snippets for this request.",
            f"- Query: {query}",
            "- Prefer these sources before asking the user to repeat known details.",
            "- If the retrieved context is insufficient, say so explicitly.",
        ]
        for result in results:
            lines.append(
                "\n### "
                f"[{_source_label(result)}] {result.get('title') or result.get('source_id')}"
            )
            lines.append(f"Source: {result.get('path_or_filename')}")
            lines.append(str(result.get("content") or "").strip())
        return "\n".join(lines).strip()

    async def build_context(
        self,
        query: str,
        *,
        conversation_id: str | None,
        agent_id: str | None,
        limit: int | None = None,
    ) -> str | None:
        results = await self.search(
            query,
            conversation_id=conversation_id,
            agent_id=agent_id,
            limit=limit,
        )
        return self.format_context(results, query=query)

    async def reindex(
        self,
        *,
        scope: str,
        conversation_id: str | None = None,
        agent_id: str | None = None,
    ) -> dict[str, Any]:
        if scope not in {"all", "memories", "conversation_attachments"}:
            raise ValueError(f"Unsupported RAG reindex scope: {scope}")

        if not self.enabled:
            summary = {
                "enabled": False,
                "scope": scope,
                "sources_indexed": 0,
                "chunks_indexed": 0,
                "disabled_reason": self._disabled_reason(),
                "last_reindex_at": None,
            }
            self._write_status(summary)
            return summary

        sources: list[RagSourceDocument] = []
        if scope in {"all", "memories"}:
            sources.extend(await load_memory_source_documents(agent_id=agent_id))
        if scope in {"all", "conversation_attachments"}:
            sources.extend(
                await load_attachment_source_documents(conversation_id=conversation_id)
            )

        total_chunks = 0
        for source in sources:
            total_chunks += await self.upsert_source_document(source)

        summary = {
            "enabled": True,
            "scope": scope,
            "conversation_id": conversation_id,
            "agent_id": agent_id,
            "sources_indexed": len(sources),
            "chunks_indexed": total_chunks,
            "last_reindex_at": datetime.now().isoformat(timespec="seconds"),
        }
        self._write_status(summary)
        return summary

    def _write_status(self, payload: dict[str, Any]) -> None:
        self.status_path.parent.mkdir(parents=True, exist_ok=True)
        self.status_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def _read_status(self) -> dict[str, Any]:
        if not self.status_path.is_file():
            return {}
        try:
            return json.loads(self.status_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            logger.warning(f"Failed to parse RAG status file: {self.status_path}")
            return {}

    async def status(self) -> dict[str, Any]:
        persisted = self._read_status()
        if getattr(self.backend, "available", True):
            metadatas = await self.backend.list_metadatas()
        else:
            metadatas = []

        document_ids = {
            (str(metadata.get("source_type") or ""), str(metadata.get("source_id") or ""))
            for metadata in metadatas
        }
        return {
            "enabled": self.enabled,
            "disabled_reason": self._disabled_reason(),
            "collection_name": getattr(self.backend, "collection_name", RAG_COLLECTION_NAME),
            "chroma_path": str(getattr(self.backend, "path", Path(RAG_CHROMA_PATH))),
            "document_count": len(document_ids),
            "chunk_count": len(metadatas),
            "last_reindex_at": persisted.get("last_reindex_at"),
            "last_reindex_scope": persisted.get("scope"),
        }


_RAG_SERVICE: RagService | None = None


def get_rag_service() -> RagService:
    global _RAG_SERVICE
    if _RAG_SERVICE is None:
        _RAG_SERVICE = RagService()
    return _RAG_SERVICE


async def build_rag_context(
    query: str,
    *,
    conversation_id: str | None,
    agent_id: str | None,
    limit: int | None = None,
) -> str | None:
    return await get_rag_service().build_context(
        query,
        conversation_id=conversation_id,
        agent_id=agent_id,
        limit=limit,
    )


async def sync_attachment_record(attachment: ConversationAttachment | dict[str, Any]) -> int:
    source = await build_attachment_source_document(attachment)
    if source is None:
        return 0
    return await get_rag_service().upsert_source_document(source)


async def delete_attachment_source(attachment_id: str) -> int:
    return await get_rag_service().delete_source(
        source_type="attachment",
        source_id=attachment_id,
    )


async def sync_memory_document(path: str) -> int:
    source = await build_memory_source_document(path)
    if source is None:
        return 0
    return await get_rag_service().upsert_source_document(source)


async def delete_memory_source(path: str) -> int:
    return await get_rag_service().delete_source(source_type="memory", source_id=path)
