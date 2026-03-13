from agent_manager import AgentManager
from agent_profiles import get_agent_profile, list_public_agent_profiles


ANTI_EXCUSE_MARKER = "【反逃避借口要求】"
FLOWCHART_AUTHORITY_MARKER = "【DOT流程图权威规则】"
MANUAL_TESTING_EXCUSE = "我已经手动测试过了"
GUESS_AND_PATCH_EXCUSE = "我先大概改一下再看"


def test_composed_system_prompts_repeat_anti_excuse_rule_in_base_and_role_prompts():
    manager = AgentManager()
    role_headers = {
        "general": "你是“通用助手”。",
        "dba": "你是“数据库助手”",
        "ops": "你是“运维助手”。",
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
    assert "只处理 router 升级上来的复杂任务" in supervisor_prompt


def test_public_agent_profiles_hide_legacy_orchestrator():
    public_ids = [profile.id for profile in list_public_agent_profiles()]

    assert public_ids == ["router", "supervisor", "general", "dba", "ops"]


def test_router_and_supervisor_profiles_have_expected_subagent_layout():
    router_profile = get_agent_profile("router")
    supervisor_profile = get_agent_profile("supervisor")

    assert router_profile.execution_mode == "router"
    assert router_profile.allowed_handoffs == ("general", "dba", "ops", "supervisor")
    assert router_profile.subagent_configs == ("general", "dba", "ops", "supervisor")

    assert supervisor_profile.execution_mode == "supervisor"
    assert supervisor_profile.allowed_handoffs == ("general", "dba", "ops")
    assert supervisor_profile.subagent_configs == ("general", "dba", "ops")


def test_build_subagents_supports_router_and_supervisor_hierarchy():
    manager = AgentManager()
    manager._llm = object()

    router_subagents = manager._build_subagents(get_agent_profile("router"))

    assert [subagent["name"] for subagent in router_subagents] == [
        "general",
        "dba",
        "ops",
        "supervisor",
    ]

    supervisor_subagent = next(
        subagent for subagent in router_subagents if subagent["name"] == "supervisor"
    )
    assert [subagent["name"] for subagent in supervisor_subagent["subagents"]] == [
        "general",
        "dba",
        "ops",
    ]
