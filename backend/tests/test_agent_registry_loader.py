from pathlib import Path

import pytest

from agents.loader import AgentRegistryLoaderError, load_agent_registry


def _write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content.strip() + "\n", encoding="utf-8")


def _bootstrap_minimal_registry(
    backend_root: Path, *, general_prompt_path: str = "prompts/general.md"
) -> None:
    _write_text(backend_root / "prompts" / "base.md", "# Base Prompt")
    _write_text(backend_root / "prompts" / "router.md", "# Router Prompt")
    _write_text(backend_root / "prompts" / "general.md", "# General Prompt")

    _write_text(
        backend_root / "agents" / "registry.toml",
        """
        default_agent_id = "router"
        public_agent_ids = ["router", "general"]
        """,
    )
    _write_text(
        backend_root / "agents" / "router" / "agent.toml",
        """
        id = "router"
        label = "智能编排助手"
        description = "默认入口"
        execution_mode = "router"
        risk_level = "low"

        prompt_paths = ["prompts/base.md", "prompts/router.md"]
        skills = ["using-superpowers"]
        capabilities = ["轻量路由"]
        allowed_handoffs = ["general"]
        subagent_configs = ["general"]
        """,
    )
    _write_text(
        backend_root / "agents" / "general" / "agent.toml",
        f"""
        id = "general"
        label = "通用助手"
        description = "通用处理"
        execution_mode = "direct"
        risk_level = "low"

        prompt_paths = ["{general_prompt_path}"]
        skills = []
        capabilities = ["通用问答"]
        allowed_handoffs = []
        subagent_configs = []
        """,
    )


def test_load_agent_registry_reads_manifests_without_legacy_aliases(tmp_path):
    _bootstrap_minimal_registry(tmp_path)

    registry = load_agent_registry(tmp_path)

    assert registry.config.default_agent_id == "router"
    assert registry.config.public_agent_ids == ("router", "general")
    assert registry.config.aliases == {}
    assert registry.manifests["router"].execution_mode == "router"
    assert registry.manifests["router"].subagent_configs == ("general",)
    assert registry.manifests["router"].source_path == (
        tmp_path / "agents" / "router" / "agent.toml"
    ).resolve()


def test_load_agent_registry_rejects_missing_prompt_file(tmp_path):
    _bootstrap_minimal_registry(tmp_path, general_prompt_path="prompts/missing.md")

    with pytest.raises(AgentRegistryLoaderError, match="missing prompt file") as exc_info:
        load_agent_registry(tmp_path)

    assert exc_info.value.source_path == (
        tmp_path / "agents" / "general" / "agent.toml"
    ).resolve()
    assert exc_info.value.field_name == "prompt_paths"
    assert exc_info.value.agent_id == "general"


def test_load_agent_registry_reports_registry_path_for_invalid_default_agent(tmp_path):
    _bootstrap_minimal_registry(tmp_path)
    _write_text(
        tmp_path / "agents" / "registry.toml",
        """
        default_agent_id = "ghost"
        public_agent_ids = ["router", "general"]
        """,
    )

    with pytest.raises(AgentRegistryLoaderError, match='Default agent "ghost" is not defined') as exc_info:
        load_agent_registry(tmp_path)

    assert exc_info.value.source_path == (tmp_path / "agents" / "registry.toml").resolve()
    assert exc_info.value.field_name == "default_agent_id"
    assert exc_info.value.agent_id is None


def test_load_agent_registry_reports_manifest_path_for_unknown_handoff(tmp_path):
    _bootstrap_minimal_registry(tmp_path)
    _write_text(
        tmp_path / "agents" / "router" / "agent.toml",
        """
        id = "router"
        label = "智能编排助手"
        description = "默认入口"
        execution_mode = "router"
        risk_level = "low"

        prompt_paths = ["prompts/base.md", "prompts/router.md"]
        skills = ["using-superpowers"]
        capabilities = ["轻量路由"]
        allowed_handoffs = ["ghost"]
        subagent_configs = []
        """,
    )

    with pytest.raises(AgentRegistryLoaderError, match='references unknown agent "ghost"') as exc_info:
        load_agent_registry(tmp_path)

    assert exc_info.value.source_path == (
        tmp_path / "agents" / "router" / "agent.toml"
    ).resolve()
    assert exc_info.value.field_name == "allowed_handoffs"
    assert exc_info.value.agent_id == "router"
