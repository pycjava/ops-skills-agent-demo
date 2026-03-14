import importlib.util
import re
import sys
import types
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest


MODULE_PATH = Path(__file__).resolve().parents[1] / "agent_profiles.py"
REGISTRY_PATH = MODULE_PATH.parent / "agents" / "registry.toml"


def _make_manifest(
    agent_id: str,
    *,
    execution_mode: str = "direct",
    allowed_handoffs: tuple[str, ...] = (),
    subagent_configs: tuple[str, ...] = (),
) -> SimpleNamespace:
    return SimpleNamespace(
        id=agent_id,
        label=agent_id.title(),
        description=f"{agent_id} description",
        prompt_paths=(f"prompts/{agent_id}.md",),
        skills=(f"{agent_id}-skill",),
        capabilities=(f"{agent_id}-capability",),
        risk_level="low",
        execution_mode=execution_mode,
        allowed_handoffs=allowed_handoffs,
        subagent_configs=subagent_configs,
    )


def _load_probe_module(monkeypatch: pytest.MonkeyPatch, load_impl):
    loader_module = types.ModuleType("agents.loader")
    loader_module.load_agent_registry = load_impl

    schema_module = types.ModuleType("agents.schema")
    schema_module.AgentManifest = object
    schema_module.ExecutionMode = str
    schema_module.RiskLevel = str

    agents_package = types.ModuleType("agents")
    agents_package.loader = loader_module
    agents_package.schema = schema_module

    module_name = f"probe_agent_profiles_{uuid4().hex}"
    module_spec = importlib.util.spec_from_file_location(module_name, MODULE_PATH)
    if module_spec is None or module_spec.loader is None:
        raise AssertionError("Failed to create module spec for agent_profiles")

    module = importlib.util.module_from_spec(module_spec)

    monkeypatch.setitem(sys.modules, "agents", agents_package)
    monkeypatch.setitem(sys.modules, "agents.loader", loader_module)
    monkeypatch.setitem(sys.modules, "agents.schema", schema_module)
    monkeypatch.setitem(sys.modules, module_name, module)

    module_spec.loader.exec_module(module)
    return module


def test_agent_profiles_module_import_is_safe_when_registry_loading_fails(monkeypatch):
    load_calls = 0

    def boom():
        nonlocal load_calls
        load_calls += 1
        raise ValueError("simulated registry failure")

    module = _load_probe_module(monkeypatch, boom)

    assert load_calls == 0
    assert module.AgentProfile.__name__ == "AgentProfile"

    with pytest.raises(
        module.AgentRegistryLoadError,
        match=re.escape(
            f'Failed to load agent registry configuration from "{REGISTRY_PATH}": '
            "ValueError: simulated registry failure"
        ),
    ):
        module.list_agent_profiles()

    assert load_calls == 1


def test_agent_profiles_failed_registry_load_is_cached(monkeypatch):
    load_calls = 0

    def boom():
        nonlocal load_calls
        load_calls += 1
        raise ValueError("simulated registry failure")

    module = _load_probe_module(monkeypatch, boom)

    with pytest.raises(module.AgentRegistryLoadError, match="simulated registry failure"):
        module.list_public_agent_profiles()

    with pytest.raises(module.AgentRegistryLoadError, match="simulated registry failure"):
        module.get_default_agent_id()

    assert module.resolve_known_agent_id(None, allow_none=True) is None
    assert load_calls == 1


def test_agent_registry_load_error_includes_registry_path_and_reason(monkeypatch):
    module = _load_probe_module(monkeypatch, lambda: None)

    error = module.AgentRegistryLoadError(
        registry_path=REGISTRY_PATH,
        cause=ValueError("broken manifest"),
    )

    assert str(error) == (
        f'Failed to load agent registry configuration from "{REGISTRY_PATH}": '
        "ValueError: broken manifest"
    )


def test_agent_profiles_successful_registry_load_is_cached(monkeypatch):
    load_calls = 0

    def load_registry():
        nonlocal load_calls
        load_calls += 1
        return SimpleNamespace(
            config=SimpleNamespace(
                default_agent_id="router",
                aliases={"legacy-router": "router"},
                public_agent_ids=("router", "general"),
            ),
            manifests={
                "router": _make_manifest(
                    "router",
                    execution_mode="router",
                    allowed_handoffs=("general",),
                    subagent_configs=("general",),
                ),
                "general": _make_manifest("general"),
            },
        )

    module = _load_probe_module(monkeypatch, load_registry)

    assert load_calls == 0
    assert module.get_default_agent_id() == "router"
    assert module.canonicalize_agent_id("legacy-router") == "router"
    assert module.get_agent_profiles()["general"].id == "general"
    assert [profile.id for profile in module.list_public_agent_profiles()] == [
        "router",
        "general",
    ]
    with pytest.raises(AttributeError):
        _ = module.DEFAULT_AGENT_ID
    with pytest.raises(AttributeError):
        _ = module.AGENT_PROFILES
    assert load_calls == 1


def test_get_agent_profile_uses_resolved_key_in_error_message(monkeypatch):
    def load_registry():
        return SimpleNamespace(
            config=SimpleNamespace(
                default_agent_id="router",
                aliases={},
                public_agent_ids=("router",),
            ),
            manifests={
                "router": _make_manifest("router"),
            },
        )

    module = _load_probe_module(monkeypatch, load_registry)
    monkeypatch.setattr(module, "resolve_known_agent_id", lambda agent_id: "resolved-ghost")
    monkeypatch.setattr(module, "get_agent_profiles", lambda: {})

    with pytest.raises(ValueError, match="resolved-ghost"):
        module.get_agent_profile("legacy-ghost")


def test_resolve_known_agent_id_uses_normalized_value_in_error_message(monkeypatch):
    def load_registry():
        return SimpleNamespace(
            config=SimpleNamespace(
                default_agent_id="router",
                aliases={"legacy-ghost": "resolved-ghost"},
                public_agent_ids=("router",),
            ),
            manifests={
                "router": _make_manifest("router"),
            },
        )

    module = _load_probe_module(monkeypatch, load_registry)

    with pytest.raises(ValueError, match="resolved-ghost"):
        module.resolve_known_agent_id("legacy-ghost")
