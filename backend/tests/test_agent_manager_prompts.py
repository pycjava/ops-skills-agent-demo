from agent_manager import AgentManager
from agent_profiles import get_agent_profile


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
