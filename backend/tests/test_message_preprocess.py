import pytest

import agent as agent_module
import services.message_preprocess as message_preprocess
from services.agent_event_state import AgentEventSnapshot
from services.message_preprocess import resolve_message_preprocess_plan


IMAGE_ATTACHMENT = {
    "id": "att-image-1",
    "conversation_id": "conv-1",
    "original_name": "console.png",
    "stored_name": "console.png",
    "relative_path": "data/conversation_attachments/conv-1/console.png",
    "mime_type": "image/png",
    "size_bytes": 128,
    "created_at": "2026-03-17T10:00:00.000",
}


def test_resolve_message_preprocess_plan_routes_router_image_turns_to_supervisor_after_ocr(
    monkeypatch,
):
    monkeypatch.setattr(
        message_preprocess,
        "resolve_ocr_availability",
        lambda **_: (True, None),
    )
    plan = resolve_message_preprocess_plan(
        user_message="帮我分析这张图里的报错原因",
        agent_id="router",
        attachments=[IMAGE_ATTACHMENT],
        api_key_configured=True,
    )

    assert plan is not None
    assert plan.policy_id == "image_attachment_ocr"
    assert plan.ocr_required is True
    assert plan.blocked_reason is None
    assert plan.downstream_agent_id == "supervisor"


@pytest.mark.asyncio
async def test_run_agent_turn_runs_ocr_before_downstream_agent(monkeypatch):
    calls: list[dict] = []
    monkeypatch.setattr(agent_module, "ANTHROPIC_API_KEY", "test-api-key")
    monkeypatch.setattr(
        message_preprocess,
        "resolve_ocr_availability",
        lambda **_: (True, None),
    )

    async def fake_run_agent(
        *,
        user_message,
        conv_id,
        on_event,
        agent_id=None,
        attachment_records=None,
        allow_image_blocks=True,
        emit_done=True,
    ):
        calls.append(
            {
                "user_message": user_message,
                "conv_id": conv_id,
                "agent_id": agent_id,
                "attachment_records": attachment_records,
                "allow_image_blocks": allow_image_blocks,
                "emit_done": emit_done,
            }
        )
        if agent_id == "ocr":
            return AgentEventSnapshot(
                text="## OCR Result\n\n### Extracted Text\n- ERROR 1045 Access denied",
                thinking="",
                tool_results=[],
            )
        return AgentEventSnapshot(
            text="最终分析结论",
            thinking="",
            tool_results=[],
        )

    monkeypatch.setattr(agent_module, "run_agent", fake_run_agent)
    monkeypatch.setattr(
        agent_module,
        "save_ocr_result",
        lambda conversation_id, source_attachments, content: "data/conversation_attachments/conv-1/_ocr/ocr-1.md",
    )

    emitted_events: list[dict] = []

    async def on_event(event: dict):
        emitted_events.append(event)

    snapshot = await agent_module.run_agent_turn(
        user_message="帮我分析这张图里的报错原因",
        conv_id="conv-1",
        on_event=on_event,
        agent_id="router",
        attachment_records=[IMAGE_ATTACHMENT],
    )

    assert snapshot.text == "最终分析结论"
    assert [call["agent_id"] for call in calls] == ["ocr", "supervisor"]
    assert calls[0]["attachment_records"] == [IMAGE_ATTACHMENT]
    assert calls[0]["allow_image_blocks"] is True
    assert calls[0]["emit_done"] is False
    assert "OCR preprocessing stage" in calls[0]["user_message"]
    assert calls[1]["allow_image_blocks"] is False
    assert "ERROR 1045 Access denied" in calls[1]["user_message"]
    assert any(event["type"] == "ocr_status" for event in emitted_events)
    assert any(
        event["type"] == "ocr_result"
        and event.get("ocr_path") == "data/conversation_attachments/conv-1/_ocr/ocr-1.md"
        for event in emitted_events
    )


@pytest.mark.asyncio
async def test_run_agent_turn_stops_when_ocr_stage_fails(monkeypatch):
    monkeypatch.setattr(agent_module, "ANTHROPIC_API_KEY", "test-api-key")
    monkeypatch.setattr(
        message_preprocess,
        "resolve_ocr_availability",
        lambda **_: (True, None),
    )
    calls: list[str] = []
    emitted_events: list[dict] = []

    async def fake_run_agent(
        *,
        user_message,
        conv_id,
        on_event,
        agent_id=None,
        attachment_records=None,
        allow_image_blocks=True,
        emit_done=True,
    ):
        del user_message, conv_id, attachment_records, allow_image_blocks, emit_done
        calls.append(str(agent_id))
        if agent_id == "ocr":
            await on_event(
                {
                    "type": "error",
                    "content": "OCR stage failed",
                    "agent_id": "ocr",
                }
            )
            return AgentEventSnapshot(text="", thinking="", tool_results=[])

        return AgentEventSnapshot(text="should not run", thinking="", tool_results=[])

    async def on_event(event: dict):
        emitted_events.append(event)

    monkeypatch.setattr(agent_module, "run_agent", fake_run_agent)

    snapshot = await agent_module.run_agent_turn(
        user_message="帮我分析这张图里的报错原因",
        conv_id="conv-1",
        on_event=on_event,
        agent_id="router",
        attachment_records=[IMAGE_ATTACHMENT],
    )

    assert snapshot.text == ""
    assert calls == ["ocr"]
    assert any(
        event["type"] == "error" and event["content"] == "OCR stage failed"
        for event in emitted_events
    )
