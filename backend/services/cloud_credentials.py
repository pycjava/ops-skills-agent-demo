import json
import re
from copy import deepcopy
from typing import Any

from dotenv import dotenv_values
from fastapi import HTTPException

from config import BASE_DIR
from services.cloud_instance_candidates import (
    extract_keywords,
    parse_instance_records,
    resolve_candidate_selection,
    score_instance_candidate,
)
from services.memory import (
    list_memory_tree,
    read_memory_document,
    write_memory_document,
)


REGISTRY_PATH = "/memories/agents/dba/cloud_credentials_registry.json"
SUPPORTED_PROVIDER = "volcengine"

DEFAULT_REGISTRY: dict[str, Any] = {
    "provider": SUPPORTED_PROVIDER,
    "credentials": [],
    "project_bindings": {},
    "instance_overrides": {},
}


def _normalize_text(value: Any) -> str:
    return str(value or "").strip()


def normalize_credential_ref(value: Any) -> str:
    normalized = _normalize_text(value).lower()
    normalized = re.sub(r"[^a-z0-9_-]+", "_", normalized)
    normalized = re.sub(r"_+", "_", normalized).strip("_")
    if not normalized:
        raise HTTPException(status_code=400, detail="credential_ref is required")
    return normalized


def credential_env_prefix(credential_ref: str) -> str:
    suffix = re.sub(r"[^A-Za-z0-9]+", "_", credential_ref).strip("_").upper()
    if not suffix:
        raise HTTPException(status_code=400, detail="credential_ref is invalid")
    return f"VOLC_CREDENTIAL_{suffix}"


def credential_env_keys(credential_ref: str) -> tuple[str, str]:
    prefix = credential_env_prefix(credential_ref)
    return f"{prefix}_AK", f"{prefix}_SK"


def _default_registry_copy() -> dict[str, Any]:
    return deepcopy(DEFAULT_REGISTRY)


def _flatten_memory_nodes(nodes: list[dict[str, Any]]) -> list[str]:
    paths: list[str] = []
    for node in nodes:
        path = node.get("path")
        if node.get("kind") == "file" and isinstance(path, str):
            paths.append(path)
        children = node.get("children")
        if isinstance(children, list):
            paths.extend(_flatten_memory_nodes(children))
    return paths


def _load_env_values() -> dict[str, str]:
    env_path = BASE_DIR / ".env"
    values = dotenv_values(env_path)
    return {
        str(key): str(value or "").strip()
        for key, value in values.items()
        if isinstance(key, str)
    }


def _credential_status(credential_ref: str) -> dict[str, str]:
    env_values = _load_env_values()
    ak_key, sk_key = credential_env_keys(credential_ref)
    configured = bool(env_values.get(ak_key)) and bool(env_values.get(sk_key))
    return {
        "env_ak_key": ak_key,
        "env_sk_key": sk_key,
        "status": "configured" if configured else "missing",
    }


def _normalize_registry(data: dict[str, Any]) -> dict[str, Any]:
    registry = _default_registry_copy()
    provider = _normalize_text(data.get("provider")) or SUPPORTED_PROVIDER
    if provider != SUPPORTED_PROVIDER:
        raise HTTPException(
            status_code=400,
            detail=f"Only provider '{SUPPORTED_PROVIDER}' is supported",
        )
    registry["provider"] = provider

    credentials: list[dict[str, Any]] = []
    seen_refs: set[str] = set()
    for item in data.get("credentials", []):
        if not isinstance(item, dict):
            continue
        credential_ref = normalize_credential_ref(item.get("credential_ref"))
        if credential_ref in seen_refs:
            raise HTTPException(
                status_code=400,
                detail=f"Duplicate credential_ref: {credential_ref}",
            )
        seen_refs.add(credential_ref)
        credentials.append(
            {
                "credential_ref": credential_ref,
                "display_name": _normalize_text(item.get("display_name"))
                or credential_ref,
                "note": _normalize_text(item.get("note")),
                "default_region": _normalize_text(item.get("default_region"))
                or "cn-shanghai",
                "enabled": bool(item.get("enabled", True)),
            }
        )

    valid_refs = {item["credential_ref"] for item in credentials}

    def _normalize_binding_map(value: Any, field_name: str) -> dict[str, str]:
        result: dict[str, str] = {}
        if not isinstance(value, dict):
            return result
        for raw_key, raw_ref in value.items():
            key = _normalize_text(raw_key)
            if not key:
                continue
            credential_ref = normalize_credential_ref(raw_ref)
            if credential_ref not in valid_refs:
                raise HTTPException(
                    status_code=400,
                    detail=f"{field_name} references unknown credential_ref: {credential_ref}",
                )
            result[key] = credential_ref
        return result

    registry["credentials"] = credentials
    registry["project_bindings"] = _normalize_binding_map(
        data.get("project_bindings"), "project_bindings"
    )
    registry["instance_overrides"] = _normalize_binding_map(
        data.get("instance_overrides"), "instance_overrides"
    )
    return registry


async def load_cloud_credentials_registry() -> tuple[dict[str, Any], str | None]:
    try:
        document = await read_memory_document(REGISTRY_PATH)
    except HTTPException as exc:
        if exc.status_code == 404:
            return _default_registry_copy(), None
        raise

    raw_content = document.get("content", "")
    if not isinstance(raw_content, str) or not raw_content.strip():
        return _default_registry_copy(), document.get("updated_at")

    try:
        parsed = json.loads(raw_content)
    except json.JSONDecodeError as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Cloud credentials registry is not valid JSON: {exc.msg}",
        ) from exc

    if not isinstance(parsed, dict):
        raise HTTPException(
            status_code=500,
            detail="Cloud credentials registry must be a JSON object",
        )

    return _normalize_registry(parsed), document.get("updated_at")


def _build_registry_response(
    registry: dict[str, Any], updated_at: str | None
) -> dict[str, Any]:
    credentials: list[dict[str, Any]] = []
    for item in registry["credentials"]:
        status = _credential_status(item["credential_ref"])
        credentials.append(
            {
                **item,
                "env_ak_key": status["env_ak_key"],
                "env_sk_key": status["env_sk_key"],
                "status": status["status"],
            }
        )

    return {
        "path": REGISTRY_PATH,
        "updated_at": updated_at,
        "provider": registry["provider"],
        "credentials": credentials,
        "project_bindings": registry["project_bindings"],
        "instance_overrides": registry["instance_overrides"],
    }


async def get_cloud_credentials_registry() -> dict[str, Any]:
    registry, updated_at = await load_cloud_credentials_registry()
    return _build_registry_response(registry, updated_at)


async def save_cloud_credentials_registry(payload: dict[str, Any]) -> dict[str, Any]:
    registry = _normalize_registry(payload)
    content = json.dumps(registry, ensure_ascii=False, indent=2)
    result = await write_memory_document(REGISTRY_PATH, content)
    return _build_registry_response(registry, result.get("updated_at"))


def resolve_credential_ref(
    registry: dict[str, Any],
    *,
    explicit_credential_ref: str | None = None,
    instance_id: str | None = None,
    project_key: str | None = None,
) -> tuple[str | None, str]:
    if explicit_credential_ref:
        return normalize_credential_ref(explicit_credential_ref), "explicit"
    if instance_id:
        override = registry["instance_overrides"].get(instance_id)
        if override:
            return override, "instance_override"
    if project_key:
        binding = registry["project_bindings"].get(project_key)
        if binding:
            return binding, "project_binding"
    return None, "none"


async def resolve_cloud_request_context(
    user_message: str,
    *,
    agent_id: str = "dba",
    credential_ref: str | None = None,
) -> dict[str, Any]:
    registry, _updated_at = await load_cloud_credentials_registry()
    explicit_ref = normalize_credential_ref(credential_ref) if credential_ref else None
    keywords = extract_keywords(user_message)

    tree = await list_memory_tree()
    all_paths = _flatten_memory_nodes(tree)
    memory_paths = [
        path
        for path in all_paths
        if path.startswith(f"/memories/agents/{agent_id}/")
        and path.endswith(".md")
        and not path.endswith("cloud_credentials_registry.json")
    ]

    candidates: list[dict[str, Any]] = []
    for path in memory_paths:
        try:
            document = await read_memory_document(path)
        except HTTPException:
            continue
        content = document.get("content", "")
        if not isinstance(content, str) or not content.strip():
            continue
        for record in parse_instance_records(content, path, normalize_credential_ref):
            score = score_instance_candidate(record, keywords)
            if score <= 0 and not explicit_ref:
                continue
            resolved_ref, source = resolve_credential_ref(
                registry,
                explicit_credential_ref=explicit_ref or record.get("credential_ref"),
                instance_id=record.get("instance_id"),
                project_key=record.get("project_key"),
            )
            status = (
                _credential_status(resolved_ref)["status"] if resolved_ref else "missing"
            )
            candidates.append(
                {
                    "instance_id": record.get("instance_id"),
                    "instance_name": record.get("instance_name"),
                    "project_key": record.get("project_key"),
                    "region": record.get("region"),
                    "environment": record.get("environment"),
                    "credential_ref": resolved_ref,
                    "credential_status": status,
                    "source": source,
                    "score": score,
                }
            )

    candidates.sort(
        key=lambda item: (
            int(item.get("score") or 0),
            item.get("instance_id") or "",
        ),
        reverse=True,
    )

    if not candidates and explicit_ref:
        status = _credential_status(explicit_ref)["status"]
        return {
            "matched": False,
            "ambiguous": False,
            "provider": SUPPORTED_PROVIDER,
            "credential_ref": explicit_ref,
            "credential_status": status,
            "source": "explicit",
            "candidates": [],
            "message": "已识别 credential_ref，但尚未命中实例或项目绑定",
        }

    if not candidates:
        return {
            "matched": False,
            "ambiguous": False,
            "provider": SUPPORTED_PROVIDER,
            "credential_ref": None,
            "credential_status": None,
            "source": "none",
            "candidates": [],
            "message": "未命中实例或项目绑定",
        }

    candidate_resolution = resolve_candidate_selection(candidates)
    top_candidates = candidate_resolution["top_candidates"]

    if candidate_resolution["ambiguous"]:
        project_keys = {
            item.get("project_key") for item in top_candidates if item.get("project_key")
        }
        credential_refs = {
            item.get("credential_ref")
            for item in top_candidates
            if item.get("credential_ref")
        }
        credential_ref_value = (
            next(iter(credential_refs)) if len(credential_refs) == 1 else None
        )
        credential_status = (
            _credential_status(credential_ref_value)["status"]
            if credential_ref_value
            else None
        )
        return {
            "matched": False,
            "ambiguous": True,
            "provider": SUPPORTED_PROVIDER,
            "project_key": next(iter(project_keys)) if len(project_keys) == 1 else None,
            "credential_ref": credential_ref_value,
            "credential_status": credential_status,
            "source": "project_binding" if credential_ref_value else "none",
            "candidates": candidate_resolution["display_candidates"],
            "message": f"命中 {len(candidate_resolution['display_candidates'])} 个实例候选，请先确认具体实例",
        }

    selected = candidate_resolution["selected"]
    return {
        "matched": True,
        "ambiguous": False,
        "provider": SUPPORTED_PROVIDER,
        "instance_id": selected.get("instance_id"),
        "instance_name": selected.get("instance_name"),
        "project_key": selected.get("project_key"),
        "region": selected.get("region"),
        "environment": selected.get("environment"),
        "credential_ref": selected.get("credential_ref"),
        "credential_status": selected.get("credential_status"),
        "source": selected.get("source"),
        "candidates": candidate_resolution["display_candidates"],
        "message": (
            "已命中实例与凭证引用"
            if selected.get("credential_ref")
            else "已命中实例，但缺少凭证绑定"
        ),
    }
