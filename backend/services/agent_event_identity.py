from typing import Any


def _normalize_agent_id(value: Any) -> str | None:
    if value is None:
        return None

    normalized = str(value).strip()
    return normalized or None


def resolve_event_agent_id(event: dict[str, Any], fallback_agent_id: str) -> str:
    explicit_agent_id = _normalize_agent_id(event.get("agent_id"))
    if explicit_agent_id:
        return explicit_agent_id

    metadata = event.get("metadata")
    if isinstance(metadata, dict):
        metadata_agent_id = _normalize_agent_id(metadata.get("lc_agent_name"))
        if metadata_agent_id:
            return metadata_agent_id

    return fallback_agent_id
