import sys
import types


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

from agent import _compose_user_message_with_contexts


def test_compose_user_message_with_contexts_includes_memory_and_attachment_blocks():
    composed = _compose_user_message_with_contexts(
        "请分析附件里的 SQL 结果",
        "memory summary",
        "attachment summary",
    )

    assert "<memory_context>" in composed
    assert "memory summary" in composed
    assert "<attachment_context>" in composed
    assert "attachment summary" in composed
    assert composed.endswith("请分析附件里的 SQL 结果")


def test_compose_user_message_with_contexts_returns_original_message_without_context():
    assert _compose_user_message_with_contexts("hello", None, None) == "hello"
