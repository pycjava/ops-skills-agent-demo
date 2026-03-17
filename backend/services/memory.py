import posixpath
from datetime import datetime
from dataclasses import dataclass
from typing import Any

from deepagents.backends.store import StoreBackend
from fastapi import HTTPException
from langgraph.store.base import BaseStore, Item

from agent import get_memory_store


MEMORY_NAMESPACE = ("filesystem",)
MEMORY_ROUTE_PREFIX = "/memories"


@dataclass
class _StoreRuntimeAdapter:
    store: BaseStore


def _get_store() -> BaseStore:
    store = get_memory_store()
    if store is None:
        raise HTTPException(status_code=503, detail="Memory store is not initialized")
    return store


def _get_backend() -> StoreBackend:
    return StoreBackend(
        _StoreRuntimeAdapter(store=_get_store()),
        namespace=lambda _ctx: MEMORY_NAMESPACE,
    )


def _normalize_memory_path(path: str, *, allow_directory: bool) -> str:
    raw_path = (path or "").strip()
    if not raw_path:
        raise HTTPException(status_code=400, detail="Memory path is required")

    candidate = raw_path if raw_path.startswith("/") else f"/{raw_path}"
    had_trailing_slash = candidate.endswith("/")
    normalized = posixpath.normpath(candidate)

    if had_trailing_slash and normalized != "/":
        normalized = normalized.rstrip("/") + "/"

    if normalized == MEMORY_ROUTE_PREFIX:
        if allow_directory:
            return f"{MEMORY_ROUTE_PREFIX}/"
        return normalized

    if not normalized.startswith(f"{MEMORY_ROUTE_PREFIX}/"):
        raise HTTPException(
            status_code=400, detail="Only /memories/ paths are supported"
        )

    return normalized


def _to_internal_path(public_path: str) -> str:
    normalized = _normalize_memory_path(public_path, allow_directory=True)
    suffix = normalized[len(MEMORY_ROUTE_PREFIX) :]
    return suffix or "/"


def _to_public_path(internal_path: str) -> str:
    normalized = internal_path if internal_path.startswith("/") else f"/{internal_path}"
    if normalized == "/":
        return f"{MEMORY_ROUTE_PREFIX}/"
    return f"{MEMORY_ROUTE_PREFIX}{normalized}"


def _path_name(path: str) -> str:
    stripped = path.rstrip("/")
    if not stripped:
        return "memories"
    return stripped.rsplit("/", 1)[-1]


def _serialize_timestamp(raw_value: Any, fallback: str | None = None) -> str | None:
    if isinstance(raw_value, str) and raw_value.strip():
        return raw_value
    return fallback


async def _build_nodes(backend: StoreBackend, internal_path: str) -> list[dict[str, Any]]:
    infos = await backend.als_info(internal_path)
    directories = sorted(
        [info for info in infos if info.get("is_dir")], key=lambda info: info["path"]
    )
    files = sorted(
        [info for info in infos if not info.get("is_dir")], key=lambda info: info["path"]
    )

    nodes: list[dict[str, Any]] = []
    for info in directories + files:
        item_path = str(info["path"])
        is_dir = bool(info.get("is_dir"))
        node: dict[str, Any] = {
            "path": _to_public_path(item_path),
            "name": _path_name(item_path),
            "kind": "directory" if is_dir else "file",
        }

        updated_at = _serialize_timestamp(info.get("modified_at"))
        if updated_at:
            node["updated_at"] = updated_at

        if is_dir:
            node["children"] = await _build_nodes(backend, item_path)

        nodes.append(node)

    return nodes


def _extract_document_content(item: Item) -> str:
    raw_content = item.value.get("content")
    if not isinstance(raw_content, list):
        raise HTTPException(
            status_code=500, detail="Memory document content format is invalid"
        )
    return "\n".join(str(line) for line in raw_content)


def _require_file_path(path: str) -> str:
    normalized = _normalize_memory_path(path, allow_directory=False)
    if normalized in {MEMORY_ROUTE_PREFIX, f"{MEMORY_ROUTE_PREFIX}/"}:
        raise HTTPException(status_code=400, detail="Memory file path is required")
    if normalized.endswith("/"):
        raise HTTPException(status_code=400, detail="Directory paths are not supported")
    return normalized


async def list_memory_tree() -> list[dict[str, Any]]:
    backend = _get_backend()
    return await _build_nodes(backend, "/")


async def read_memory_document(path: str) -> dict[str, Any]:
    normalized = _require_file_path(path)
    internal_path = _to_internal_path(normalized)
    store = _get_store()
    item = await store.aget(MEMORY_NAMESPACE, internal_path)
    if item is None:
        raise HTTPException(status_code=404, detail="Memory document not found")

    updated_at = _serialize_timestamp(
        item.value.get("modified_at"),
        fallback=item.updated_at.isoformat() if item.updated_at else None,
    )

    return {
        "path": _to_public_path(internal_path),
        "name": _path_name(internal_path),
        "content": _extract_document_content(item),
        "updated_at": updated_at,
    }


async def write_memory_document(path: str, content: str) -> dict[str, Any]:
    normalized = _require_file_path(path)
    internal_path = _to_internal_path(normalized)
    store = _get_store()

    text = content if isinstance(content, str) else str(content or "")
    payload = {
        "content": text.splitlines(),
        "modified_at": datetime.now().isoformat(),
    }
    await store.aput(MEMORY_NAMESPACE, internal_path, payload)

    try:
        from services.rag import sync_memory_document

        await sync_memory_document(_to_public_path(internal_path))
    except Exception as exc:
        from utils.logger import logger

        logger.warning(f"Failed to sync memory document {internal_path} into RAG: {exc}")

    return {
        "path": _to_public_path(internal_path),
        "name": _path_name(internal_path),
        "content": text,
        "updated_at": payload["modified_at"],
    }


async def delete_memory_document(path: str) -> dict[str, Any]:
    normalized = _require_file_path(path)
    internal_path = _to_internal_path(normalized)
    store = _get_store()
    item = await store.aget(MEMORY_NAMESPACE, internal_path)
    if item is None:
        raise HTTPException(status_code=404, detail="Memory document not found")

    await store.adelete(MEMORY_NAMESPACE, internal_path)

    try:
        from services.rag import delete_memory_source

        await delete_memory_source(_to_public_path(internal_path))
    except Exception as exc:
        from utils.logger import logger

        logger.warning(
            f"Failed to delete memory document {internal_path} from RAG index: {exc}"
        )

    return {"ok": True, "path": _to_public_path(internal_path)}
