import importlib
import sys
import types

import tomli


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
