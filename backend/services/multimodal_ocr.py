from __future__ import annotations

from collections.abc import Sequence

from config import MODEL_NAME, MULTIMODAL_ENABLED, VISION_MODEL_ALLOWLIST


MULTIMODAL_IMAGE_AGENT_IDS = frozenset({"router", "supervisor", "ocr"})


def _normalize_allowlist(
    vision_model_allowlist: Sequence[str] | None,
) -> tuple[str, ...]:
    if vision_model_allowlist is None:
        return VISION_MODEL_ALLOWLIST
    return tuple(str(item).strip() for item in vision_model_allowlist if str(item).strip())


def model_supports_multimodal_ocr(
    *,
    model_name: str | None = None,
    multimodal_enabled: bool | None = None,
    vision_model_allowlist: Sequence[str] | None = None,
) -> bool:
    enabled = MULTIMODAL_ENABLED if multimodal_enabled is None else bool(multimodal_enabled)
    if not enabled:
        return False

    normalized_model_name = str(model_name or MODEL_NAME).strip()
    if not normalized_model_name:
        return False

    allowlist = _normalize_allowlist(vision_model_allowlist)
    return normalized_model_name in allowlist


def should_attach_multimodal_images(
    agent_id: str | None,
    *,
    model_name: str | None = None,
    multimodal_enabled: bool | None = None,
    vision_model_allowlist: Sequence[str] | None = None,
) -> bool:
    normalized_agent_id = str(agent_id or "").strip()
    if normalized_agent_id not in MULTIMODAL_IMAGE_AGENT_IDS:
        return False

    return model_supports_multimodal_ocr(
        model_name=model_name,
        multimodal_enabled=multimodal_enabled,
        vision_model_allowlist=vision_model_allowlist,
    )


def resolve_ocr_availability(
    *,
    has_image_attachments: bool,
    api_key_configured: bool,
    model_name: str | None = None,
    multimodal_enabled: bool | None = None,
    vision_model_allowlist: Sequence[str] | None = None,
) -> tuple[bool, str | None]:
    if not has_image_attachments:
        return False, "No image attachments were provided for OCR."

    if not api_key_configured:
        return False, "ANTHROPIC_API_KEY is not configured, so OCR is unavailable."

    if not model_supports_multimodal_ocr(
        model_name=model_name,
        multimodal_enabled=multimodal_enabled,
        vision_model_allowlist=vision_model_allowlist,
    ):
        return (
            False,
            "The current model does not have vision enabled. Switch to a vision-capable model for OCR.",
        )

    return True, None


def build_multimodal_capability_context(
    *,
    agent_id: str | None,
    has_image_attachments: bool,
    api_key_configured: bool,
    model_name: str | None = None,
    multimodal_enabled: bool | None = None,
    vision_model_allowlist: Sequence[str] | None = None,
) -> str | None:
    if not has_image_attachments:
        return None

    available, reason = resolve_ocr_availability(
        has_image_attachments=has_image_attachments,
        api_key_configured=api_key_configured,
        model_name=model_name,
        multimodal_enabled=multimodal_enabled,
        vision_model_allowlist=vision_model_allowlist,
    )
    normalized_agent_id = str(agent_id or "").strip() or "router"

    if available:
        return (
            "Multimodal OCR is available for this turn. If the user needs text extracted from images, "
            f"`{normalized_agent_id}` can route the task to `ocr`."
        )

    return (
        f"Multimodal OCR is unavailable for this turn: {reason} "
        f"`{normalized_agent_id}` must do not call `ocr`; explain the limitation instead."
    )
