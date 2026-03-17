import importlib
import json
import sys
import types
from datetime import UTC, datetime

import tomli
from langgraph.prebuilt import ToolRuntime


sys.modules.setdefault("tomllib", tomli)

previous_agent_module = sys.modules.get("agent")
stub_agent = types.ModuleType("agent")
stub_agent.resolve_default_agent = lambda: "router"
stub_agent.run_agent = None
sys.modules["agent"] = stub_agent
sys.modules.pop("api.ws.chat", None)

chat_module = importlib.import_module("api.ws.chat")
if previous_agent_module is not None:
    sys.modules["agent"] = previous_agent_module
else:
    sys.modules.pop("agent", None)


def test_should_suppress_normalized_event_for_ocr_task_results():
    assert chat_module._should_suppress_normalized_event(
        {
            "type": "tool_result",
            "tool_name": "task",
            "tool_input": {"subagent_type": "ocr"},
        }
    )
    assert not chat_module._should_suppress_normalized_event(
        {
            "type": "tool_result",
            "tool_name": "task",
            "tool_input": {"subagent_type": "general"},
        }
    )
    assert not chat_module._should_suppress_normalized_event({"type": "text"})


def test_build_ocr_status_payload_returns_failed_status_when_ocr_is_unavailable(monkeypatch):
    monkeypatch.setattr(
        chat_module,
        "resolve_ocr_availability",
        lambda **_: (False, "Vision OCR is unavailable for the current model."),
    )

    payload, suppress_result = chat_module._build_ocr_status_payload(
        [
            {
                "id": "att-1",
                "original_name": "console.png",
                "mime_type": "image/png",
            }
        ]
    )

    assert payload == {
        "type": "ocr_status",
        "status": "failed",
        "content": "Vision OCR is unavailable for the current model.",
        "agent_id": "ocr",
    }
    assert suppress_result is True


def test_dump_ws_payload_stringifies_runtime_objects():
    runtime = ToolRuntime(
        state={"messages": []},
        context=None,
        config={},
        stream_writer=lambda *_: None,
        tool_call_id="call-1",
        store=None,
    )

    payload = {
        "type": "tool_call",
        "tool_name": "MiniMax_web_search",
        "tool_input": {
            "query": "latest status",
            "runtime": runtime,
        },
    }

    dumped = chat_module._dump_ws_payload(payload)
    restored = json.loads(dumped)

    assert restored["tool_input"]["query"] == "latest status"
    assert "ToolRuntime(" in restored["tool_input"]["runtime"]


def test_dump_ws_payload_preserves_plain_json_values():
    payload = {
        "type": "session",
        "conversation_id": "conv-1",
        "agent_id": "router",
        "flags": [True, False],
    }

    assert json.loads(chat_module._dump_ws_payload(payload)) == payload


async def test_persist_ocr_result_event_saves_text_message(monkeypatch):
    saved_records = []

    async def fake_save_message(
        conv_id,
        role,
        content,
        msg_type,
        *,
        agent_id=None,
        **kwargs,
    ):
        saved_records.append(
            {
                "conv_id": conv_id,
                "role": role,
                "content": content,
                "msg_type": msg_type,
                "agent_id": agent_id,
                "kwargs": kwargs,
            }
        )

    monkeypatch.setattr(chat_module, "save_message", fake_save_message)
    monkeypatch.setattr(
        chat_module,
        "save_ocr_result",
        lambda conversation_id, source_attachments, content: (
            "data/conversation_attachments/conv-1/_ocr/ocr-preprocessed.md"
        ),
    )

    payload = await chat_module._persist_ocr_result_event(
        current_conv_id="conv-1",
        current_turn_attachments=[
            {
                "id": "att-1",
                "original_name": "console.png",
                "stored_name": "console.png",
                "relative_path": "data/conversation_attachments/conv-1/console.png",
                "mime_type": "image/png",
                "size_bytes": 123,
                "created_at": datetime.now(UTC).isoformat(),
            }
        ],
        result_text="mysql error 1045",
    )

    assert payload["type"] == "ocr_result"
    assert payload["agent_id"] == "ocr"
    assert "mysql error 1045" in payload["content"]
    assert "Saved OCR result:" in payload["content"]
    assert payload["ocr_path"] == "data/conversation_attachments/conv-1/_ocr/ocr-preprocessed.md"

    assert len(saved_records) == 1
    assert saved_records[0]["conv_id"] == "conv-1"
    assert saved_records[0]["role"] == "system"
    assert saved_records[0]["msg_type"] == "text"
    assert saved_records[0]["agent_id"] == "ocr"
    assert "mysql error 1045" in saved_records[0]["content"]
