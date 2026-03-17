import sys
import types

import tomli


def _install_agent_dependency_stubs() -> None:
    if "deepagents" not in sys.modules:
        deepagents_module = types.ModuleType("deepagents")
        deepagents_module.create_deep_agent = lambda *args, **kwargs: None
        deepagents_module.SubAgent = dict
        deepagents_module.__path__ = []
        sys.modules["deepagents"] = deepagents_module
    elif not hasattr(sys.modules["deepagents"], "SubAgent"):
        sys.modules["deepagents"].SubAgent = dict

    if "deepagents.backends" not in sys.modules:
        backends_module = types.ModuleType("deepagents.backends")
        backends_module.CompositeBackend = type("CompositeBackend", (), {})
        backends_module.StoreBackend = type("StoreBackend", (), {})
        backends_module.__path__ = []
        sys.modules["deepagents.backends"] = backends_module

    if "deepagents.backends.local_shell" not in sys.modules:
        local_shell_module = types.ModuleType("deepagents.backends.local_shell")
        local_shell_module.LocalShellBackend = type("LocalShellBackend", (), {})
        sys.modules["deepagents.backends.local_shell"] = local_shell_module

    if "deepagents.backends.protocol" not in sys.modules:
        protocol_module = types.ModuleType("deepagents.backends.protocol")
        protocol_module.ExecuteResponse = type(
            "ExecuteResponse",
            (),
            {},
        )
        sys.modules["deepagents.backends.protocol"] = protocol_module

    if "langchain_anthropic" not in sys.modules:
        anthropic_module = types.ModuleType("langchain_anthropic")
        anthropic_module.ChatAnthropic = type("ChatAnthropic", (), {})
        sys.modules["langchain_anthropic"] = anthropic_module

    if "langgraph.checkpoint.sqlite.aio" not in sys.modules:
        checkpoint_module = types.ModuleType("langgraph.checkpoint.sqlite.aio")
        checkpoint_module.AsyncSqliteSaver = type("AsyncSqliteSaver", (), {})
        sys.modules["langgraph.checkpoint.sqlite.aio"] = checkpoint_module

    if "langgraph.store.sqlite.aio" not in sys.modules:
        store_module = types.ModuleType("langgraph.store.sqlite.aio")
        store_module.AsyncSqliteStore = type("AsyncSqliteStore", (), {})
        sys.modules["langgraph.store.sqlite.aio"] = store_module


_install_agent_dependency_stubs()
sys.modules.setdefault("tomllib", tomli)

from agent import _build_human_message_content, _compose_user_message_with_contexts


def test_compose_user_message_with_contexts_includes_memory_and_attachment_blocks():
    composed = _compose_user_message_with_contexts(
        "Please analyze the SQL result in the attachment",
        "memory summary",
        "attachment summary",
        None,
    )

    assert "<memory_context>" in composed
    assert "memory summary" in composed
    assert "<attachment_context>" in composed
    assert "attachment summary" in composed
    assert composed.endswith("Please analyze the SQL result in the attachment")


def test_compose_user_message_with_contexts_returns_original_message_without_context():
    assert _compose_user_message_with_contexts("hello", None, None, None) == "hello"


def test_compose_user_message_with_contexts_includes_rag_context_block():
    composed = _compose_user_message_with_contexts(
        "Answer using the indexed knowledge base",
        None,
        None,
        None,
        rag_context="retrieved chunk summary",
    )

    assert "<rag_context>" in composed
    assert "retrieved chunk summary" in composed
    assert composed.endswith("Answer using the indexed knowledge base")


def test_compose_user_message_with_contexts_includes_multimodal_context_block():
    composed = _compose_user_message_with_contexts(
        "Please inspect this screenshot",
        None,
        "attachment summary",
        "vision enabled",
    )

    assert "<multimodal_context>" in composed
    assert "vision enabled" in composed


def test_build_human_message_content_wraps_image_blocks_for_multimodal_input():
    content = _build_human_message_content(
        "Please extract the text from the screenshot",
        [
            {
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": "image/png",
                    "data": "ZmFrZS1wbmc=",
                },
            }
        ],
        allow_image_blocks=True,
    )

    assert isinstance(content, list)
    assert content[0] == {
        "type": "text",
        "text": "Please extract the text from the screenshot",
    }
    assert content[1]["type"] == "image"
    assert content[1]["source"]["media_type"] == "image/png"


def test_build_human_message_content_omits_image_blocks_when_not_allowed():
    content = _build_human_message_content(
        "Please extract the text from the screenshot",
        [
            {
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": "image/png",
                    "data": "ZmFrZS1wbmc=",
                },
            }
        ],
        allow_image_blocks=False,
    )

    assert content == "Please extract the text from the screenshot"
