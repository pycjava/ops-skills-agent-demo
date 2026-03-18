from __future__ import annotations

from collections.abc import Mapping
from typing import Any


AGENT_ERROR_PREFIX = "Agent 执行出错"


def _resolve_error_suffix(
    *,
    error_type: str | None,
    error_message: str | None,
) -> str:
    message = (error_message or "").strip()
    if message:
        return message

    return (error_type or "").strip()


def build_agent_error_event(
    exc: BaseException,
    *,
    agent_id: str,
) -> dict[str, Any]:
    error_type = exc.__class__.__name__
    error_message = str(exc)
    error_suffix = _resolve_error_suffix(
        error_type=error_type,
        error_message=error_message,
    )
    content = (
        f"{AGENT_ERROR_PREFIX}: {error_suffix}"
        if error_suffix
        else AGENT_ERROR_PREFIX
    )
    return {
        "type": "error",
        "content": content,
        "agent_id": agent_id,
        "error_type": error_type,
        "error_message": error_message,
    }


def resolve_error_event_content(
    event: Mapping[str, Any],
    *,
    fallback_prefix: str = AGENT_ERROR_PREFIX,
) -> str:
    content = str(event.get("content", "") or "").strip()
    if content:
        return content

    error_suffix = _resolve_error_suffix(
        error_type=str(event.get("error_type", "") or ""),
        error_message=str(event.get("error_message", "") or ""),
    )
    if error_suffix:
        return f"{fallback_prefix}: {error_suffix}"

    return fallback_prefix
