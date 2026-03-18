from types import SimpleNamespace

import pytest
from fastapi import HTTPException

import agent as agent_module
from api.routers import agent as agent_router


class EmptyMessageFailingRuntime:
    async def astream_events(self, *args, **kwargs):
        raise NotImplementedError()
        yield


class ExplicitMessageFailingRuntime:
    async def astream_events(self, *args, **kwargs):
        raise NotImplementedError("browser command unsupported")
        yield


async def _return_none(*args, **kwargs):
    return None


async def _return_empty_list(*args, **kwargs):
    return []


def _stub_agent_context_builders(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(agent_module, "_build_rag_context", _return_none)
    monkeypatch.setattr(agent_module, "_build_memory_context", _return_none)
    monkeypatch.setattr(agent_module, "_build_attachment_context", _return_none)
    monkeypatch.setattr(agent_module, "_build_multimodal_context", _return_none)
    monkeypatch.setattr(agent_module, "_build_image_attachment_blocks", _return_empty_list)


@pytest.mark.asyncio
async def test_run_agent_emits_exception_type_when_runtime_error_message_is_empty(
    monkeypatch: pytest.MonkeyPatch,
):
    emitted_events: list[dict] = []

    async def fake_get_runtime(agent_id: str):
        assert agent_id == "browser-runtime"
        return EmptyMessageFailingRuntime()

    async def on_event(event: dict):
        emitted_events.append(event)

    _stub_agent_context_builders(monkeypatch)
    monkeypatch.setattr(agent_module, "get_runtime", fake_get_runtime)

    snapshot = await agent_module.run_agent(
        user_message="Inspect this page in the browser",
        conv_id="conv-1",
        on_event=on_event,
        agent_id="browser-runtime",
    )

    assert snapshot is not None
    assert emitted_events == [
        {
            "type": "error",
            "content": "Agent 执行出错: NotImplementedError",
            "agent_id": "browser-runtime",
            "error_type": "NotImplementedError",
            "error_message": "",
        }
    ]


@pytest.mark.asyncio
async def test_run_agent_preserves_explicit_runtime_error_message(
    monkeypatch: pytest.MonkeyPatch,
):
    emitted_events: list[dict] = []

    async def fake_get_runtime(agent_id: str):
        assert agent_id == "browser-runtime"
        return ExplicitMessageFailingRuntime()

    async def on_event(event: dict):
        emitted_events.append(event)

    _stub_agent_context_builders(monkeypatch)
    monkeypatch.setattr(agent_module, "get_runtime", fake_get_runtime)

    snapshot = await agent_module.run_agent(
        user_message="Inspect this page in the browser",
        conv_id="conv-1",
        on_event=on_event,
        agent_id="browser-runtime",
    )

    assert snapshot is not None
    assert emitted_events == [
        {
            "type": "error",
            "content": "Agent 执行出错: browser command unsupported",
            "agent_id": "browser-runtime",
            "error_type": "NotImplementedError",
            "error_message": "browser command unsupported",
        }
    ]


class _SessionContext:
    async def __aenter__(self):
        return object()

    async def __aexit__(self, exc_type, exc, tb):
        return False


class _SessionFactory:
    def __call__(self):
        return _SessionContext()


@pytest.mark.asyncio
async def test_agent_chat_uses_error_type_when_error_content_is_blank(
    monkeypatch: pytest.MonkeyPatch,
):
    async def fake_create_conversation(session, *, source, agent_id):
        assert source == "api"
        assert agent_id == "browser-runtime"
        return SimpleNamespace(id="conv-1", agent_id="browser-runtime")

    async def fake_save_message(*args, **kwargs):
        return None

    async def fake_run_agent(*, user_message, conv_id, on_event, agent_id=None, **kwargs):
        assert user_message == "Inspect this page in the browser"
        assert conv_id == "conv-1"
        assert agent_id == "browser-runtime"
        await on_event(
            {
                "type": "error",
                "content": "",
                "agent_id": "browser-runtime",
                "error_type": "NotImplementedError",
                "error_message": "",
            }
        )

    monkeypatch.setattr(agent_router, "ANTHROPIC_API_KEY", "test-api-key")
    monkeypatch.setattr(agent_router, "AsyncSessionLocal", _SessionFactory())
    monkeypatch.setattr(agent_router, "create_conversation", fake_create_conversation)
    monkeypatch.setattr(agent_router, "save_message", fake_save_message)
    monkeypatch.setattr(
        agent_router,
        "contains_plaintext_cloud_credentials",
        lambda message: False,
    )
    monkeypatch.setattr(agent_router, "run_agent", fake_run_agent)

    with pytest.raises(HTTPException) as exc_info:
        await agent_router.agent_chat(
            agent_router.ChatRequest(
                message="Inspect this page in the browser",
                agent_id="browser-runtime",
            )
        )

    assert exc_info.value.status_code == 500
    assert exc_info.value.detail == "Agent 执行出错: NotImplementedError"
