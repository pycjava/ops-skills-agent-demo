import sys
import types

import pytest
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
        protocol_module.ExecuteResponse = type("ExecuteResponse", (), {})
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

from agent_manager import AgentManager
from agent_profiles import get_agent_profile, list_public_agent_profiles


ANTI_EXCUSE_MARKER = "【反逃避借口要求】"
FLOWCHART_AUTHORITY_MARKER = "【DOT流程图权威规则】"
MANUAL_TESTING_EXCUSE = "我已经手动测试过了"
GUESS_AND_PATCH_EXCUSE = "我先大概改一下再看"

ROUTER_LEAF_AGENTS = [
    "general",
    "ocr",
    "backend",
    "frontend",
    "browser-runtime",
    "db-schema",
    "db-runtime",
    "ops-runtime",
    "platform",
    "security",
    "supervisor",
]

SUPERVISOR_LEAF_AGENTS = [
    "general",
    "ocr",
    "backend",
    "frontend",
    "browser-runtime",
    "db-schema",
    "db-runtime",
    "ops-runtime",
    "platform",
    "security",
]


def test_composed_system_prompts_repeat_anti_excuse_rule_in_base_and_role_prompts():
    manager = AgentManager()
    role_headers = {
        "general": "你是“通用助手”。",
        "db-runtime": "你是“数据库运行态助手”",
        "ops-runtime": "你是“运行时运维助手”",
    }

    for agent_id, role_header in role_headers.items():
        prompt = manager._compose_system_prompt(get_agent_profile(agent_id))

        assert role_header in prompt
        assert prompt.count(ANTI_EXCUSE_MARKER) >= 2
        assert prompt.count(FLOWCHART_AUTHORITY_MARKER) >= 2
        assert prompt.count(MANUAL_TESTING_EXCUSE) >= 2
        assert prompt.count(GUESS_AND_PATCH_EXCUSE) >= 2


def test_router_and_supervisor_prompts_are_composed_with_runtime_hints():
    manager = AgentManager()

    router_prompt = manager._compose_system_prompt(get_agent_profile("router"))
    supervisor_prompt = manager._compose_system_prompt(get_agent_profile("supervisor"))

    assert "Router Agent Prompt" in router_prompt
    assert "只做一次路由决策" in router_prompt
    assert "Supervisor Agent Prompt" in supervisor_prompt
    assert "仅处理由 `router` 升级上来的复杂问题" in supervisor_prompt


def test_public_agent_profiles_match_router_only_topology():
    public_ids = [profile.id for profile in list_public_agent_profiles()]

    assert public_ids == ["router"]


def test_unknown_agent_profile_raises_for_removed_orchestrator_id():
    with pytest.raises(ValueError, match="agent_id"):
        get_agent_profile("orchestrator")


def test_legacy_aliases_resolve_to_runtime_agents():
    assert get_agent_profile("dba").id == "db-runtime"
    assert get_agent_profile("ops").id == "ops-runtime"
    assert get_agent_profile("general-purpose").id == "general"


def test_ocr_agent_profile_is_registered():
    assert get_agent_profile("ocr").id == "ocr"


def test_browser_runtime_agent_profile_is_registered_with_expected_skill_boundary():
    profile = get_agent_profile("browser-runtime")

    assert profile.id == "browser-runtime"
    assert profile.execution_mode == "direct"
    assert list(profile.skills) == ["agent-browser", "using-superpowers"]
    assert profile.allowed_handoffs == ()
    assert profile.subagent_configs == ()


def test_router_and_supervisor_profiles_have_expected_subagent_layout():
    router_profile = get_agent_profile("router")
    supervisor_profile = get_agent_profile("supervisor")

    assert router_profile.execution_mode == "router"
    assert list(router_profile.allowed_handoffs) == ROUTER_LEAF_AGENTS
    assert list(router_profile.subagent_configs) == ROUTER_LEAF_AGENTS

    assert supervisor_profile.execution_mode == "supervisor"
    assert list(supervisor_profile.allowed_handoffs) == SUPERVISOR_LEAF_AGENTS
    assert list(supervisor_profile.subagent_configs) == SUPERVISOR_LEAF_AGENTS


def test_build_subagents_supports_router_and_supervisor_hierarchy():
    manager = AgentManager()
    manager._llm = object()

    router_subagents = manager._build_subagents(get_agent_profile("router"))

    assert [subagent["name"] for subagent in router_subagents] == ROUTER_LEAF_AGENTS

    supervisor_subagent = next(
        subagent for subagent in router_subagents if subagent["name"] == "supervisor"
    )
    assert [subagent["name"] for subagent in supervisor_subagent["subagents"]] == (
        SUPERVISOR_LEAF_AGENTS
    )


def test_router_supervisor_and_ocr_prompts_define_multimodal_ocr_boundaries():
    manager = AgentManager()

    router_prompt = manager._compose_system_prompt(get_agent_profile("router"))
    supervisor_prompt = manager._compose_system_prompt(get_agent_profile("supervisor"))
    ocr_prompt = manager._compose_system_prompt(get_agent_profile("ocr"))

    assert "route image-only OCR requests to `ocr`" in router_prompt
    assert "call `ocr` first for image extraction before domain analysis" in supervisor_prompt
    assert "If image input is unavailable, say so explicitly and do not guess." in ocr_prompt


def test_router_supervisor_and_browser_runtime_prompts_define_browser_boundaries():
    manager = AgentManager()

    router_prompt = manager._compose_system_prompt(get_agent_profile("router"))
    supervisor_prompt = manager._compose_system_prompt(get_agent_profile("supervisor"))
    browser_prompt = manager._compose_system_prompt(get_agent_profile("browser-runtime"))

    assert (
        "route explicit browser automation or live webpage inspection requests to `browser-runtime`"
        in router_prompt
    )
    assert (
        "delegate live browser interaction and evidence capture to `browser-runtime`"
        in supervisor_prompt
    )
    assert (
        "After every browser action, immediately run `agent-browser screenshot`"
        in browser_prompt
    )
