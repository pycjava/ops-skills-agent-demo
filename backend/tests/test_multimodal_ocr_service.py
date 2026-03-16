from services.multimodal_ocr import (
    build_multimodal_capability_context,
    model_supports_multimodal_ocr,
    resolve_ocr_availability,
    should_attach_multimodal_images,
)


VISION_MODEL = "claude-sonnet-4-5-20250929"
VISION_ALLOWLIST = (VISION_MODEL,)


def test_model_supports_multimodal_ocr_only_for_allowlisted_enabled_models():
    assert model_supports_multimodal_ocr(
        model_name=VISION_MODEL,
        multimodal_enabled=True,
        vision_model_allowlist=VISION_ALLOWLIST,
    )
    assert not model_supports_multimodal_ocr(
        model_name="claude-3-haiku",
        multimodal_enabled=True,
        vision_model_allowlist=VISION_ALLOWLIST,
    )
    assert not model_supports_multimodal_ocr(
        model_name=VISION_MODEL,
        multimodal_enabled=False,
        vision_model_allowlist=VISION_ALLOWLIST,
    )


def test_should_attach_multimodal_images_only_for_routing_and_ocr_agents():
    assert should_attach_multimodal_images(
        "router",
        model_name=VISION_MODEL,
        multimodal_enabled=True,
        vision_model_allowlist=VISION_ALLOWLIST,
    )
    assert should_attach_multimodal_images(
        "supervisor",
        model_name=VISION_MODEL,
        multimodal_enabled=True,
        vision_model_allowlist=VISION_ALLOWLIST,
    )
    assert should_attach_multimodal_images(
        "ocr",
        model_name=VISION_MODEL,
        multimodal_enabled=True,
        vision_model_allowlist=VISION_ALLOWLIST,
    )
    assert not should_attach_multimodal_images(
        "general",
        model_name=VISION_MODEL,
        multimodal_enabled=True,
        vision_model_allowlist=VISION_ALLOWLIST,
    )


def test_resolve_ocr_availability_reports_missing_images_first():
    available, reason = resolve_ocr_availability(
        has_image_attachments=False,
        api_key_configured=True,
        model_name=VISION_MODEL,
        multimodal_enabled=True,
        vision_model_allowlist=VISION_ALLOWLIST,
    )

    assert available is False
    assert "image attachments" in reason.lower()


def test_resolve_ocr_availability_reports_missing_api_key():
    available, reason = resolve_ocr_availability(
        has_image_attachments=True,
        api_key_configured=False,
        model_name=VISION_MODEL,
        multimodal_enabled=True,
        vision_model_allowlist=VISION_ALLOWLIST,
    )

    assert available is False
    assert "ANTHROPIC_API_KEY" in reason


def test_resolve_ocr_availability_reports_vision_model_requirement():
    available, reason = resolve_ocr_availability(
        has_image_attachments=True,
        api_key_configured=True,
        model_name="claude-3-haiku",
        multimodal_enabled=True,
        vision_model_allowlist=VISION_ALLOWLIST,
    )

    assert available is False
    assert "vision" in reason.lower()


def test_build_multimodal_capability_context_warns_router_when_ocr_is_unavailable():
    context = build_multimodal_capability_context(
        agent_id="router",
        has_image_attachments=True,
        api_key_configured=True,
        model_name="claude-3-haiku",
        multimodal_enabled=True,
        vision_model_allowlist=VISION_ALLOWLIST,
    )

    assert context is not None
    assert "`ocr`" in context
    assert "do not call" in context.lower()


def test_build_multimodal_capability_context_guides_router_to_ocr_when_available():
    context = build_multimodal_capability_context(
        agent_id="router",
        has_image_attachments=True,
        api_key_configured=True,
        model_name=VISION_MODEL,
        multimodal_enabled=True,
        vision_model_allowlist=VISION_ALLOWLIST,
    )

    assert context is not None
    assert "`ocr`" in context
    assert "can route" in context.lower()
