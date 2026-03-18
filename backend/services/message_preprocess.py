from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from services.conversation_attachments import is_image_attachment_record
from services.multimodal_ocr import resolve_ocr_availability


@dataclass(frozen=True, slots=True)
class MessagePreprocessPlan:
    policy_id: str
    ocr_required: bool
    downstream_agent_id: str
    blocked_reason: str | None
    image_attachments: tuple[dict[str, Any], ...]


def resolve_message_preprocess_plan(
    *,
    user_message: str,
    agent_id: str | None,
    attachments: list[dict[str, Any]] | tuple[dict[str, Any], ...] | None,
    api_key_configured: bool,
) -> MessagePreprocessPlan | None:
    del user_message

    normalized_agent_id = str(agent_id or "").strip() or "router"
    if normalized_agent_id == "ocr":
        return None

    normalized_attachments = tuple(
        attachment
        for attachment in (attachments or [])
        if isinstance(attachment, dict)
    )
    image_attachments = tuple(
        attachment
        for attachment in normalized_attachments
        if is_image_attachment_record(attachment)
    )
    if not image_attachments:
        return None

    available, reason = resolve_ocr_availability(
        has_image_attachments=True,
        api_key_configured=api_key_configured,
    )
    downstream_agent_id = (
        "supervisor" if normalized_agent_id == "router" else normalized_agent_id
    )
    return MessagePreprocessPlan(
        policy_id="image_attachment_ocr",
        ocr_required=True,
        downstream_agent_id=downstream_agent_id,
        blocked_reason=None if available else reason,
        image_attachments=image_attachments,
    )
