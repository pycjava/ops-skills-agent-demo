from dataclasses import dataclass
from pathlib import Path
from threading import Lock
from typing import NoReturn

from agents.loader import load_agent_registry
from agents.schema import AgentManifest, ExecutionMode, RiskLevel
from utils.logger import logger


@dataclass(frozen=True, slots=True)
class AgentProfile:
    id: str
    label: str
    description: str
    prompt_paths: tuple[str, ...]
    skills: tuple[str, ...]
    capabilities: tuple[str, ...]
    risk_level: RiskLevel
    execution_mode: ExecutionMode = "direct"
    allowed_handoffs: tuple[str, ...] = ()
    subagent_configs: tuple[str, ...] = ()

    def to_dict(self, *, is_default: bool = False) -> dict[str, object]:
        return {
            "id": self.id,
            "label": self.label,
            "description": self.description,
            "prompt_paths": list(self.prompt_paths),
            "skills": list(self.skills),
            "capabilities": list(self.capabilities),
            "risk_level": self.risk_level,
            "execution_mode": self.execution_mode,
            "allowed_handoffs": list(self.allowed_handoffs),
            "subagent_configs": list(self.subagent_configs),
            "is_default": is_default,
        }


class AgentRegistryLoadError(RuntimeError):
    def __init__(
        self,
        *,
        registry_path: Path | str,
        cause: Exception | str,
    ) -> None:
        self.registry_path = Path(registry_path)
        self.cause = cause
        reason = str(cause).strip()
        if not reason:
            reason = type(cause).__name__ if isinstance(cause, Exception) else "unknown error"
        elif isinstance(cause, Exception):
            reason = f"{type(cause).__name__}: {reason}"
        super().__init__(
            f'Failed to load agent registry configuration from "{self.registry_path}": '
            f"{reason}"
        )


@dataclass(frozen=True, slots=True)
class _AgentRegistrySnapshot:
    default_agent_id: str
    legacy_agent_aliases: dict[str, str]
    public_agent_ids: tuple[str, ...]
    agent_profiles: dict[str, AgentProfile]


def _build_agent_profile(manifest: AgentManifest) -> AgentProfile:
    return AgentProfile(
        id=manifest.id,
        label=manifest.label,
        description=manifest.description,
        prompt_paths=manifest.prompt_paths,
        skills=manifest.skills,
        capabilities=manifest.capabilities,
        risk_level=manifest.risk_level,
        execution_mode=manifest.execution_mode,
        allowed_handoffs=manifest.allowed_handoffs,
        subagent_configs=manifest.subagent_configs,
    )


_REGISTRY_LOCK = Lock()
_REGISTRY_SNAPSHOT: _AgentRegistrySnapshot | None = None
_REGISTRY_LOAD_ERROR: Exception | None = None
_AGENT_REGISTRY_PATH = Path(__file__).resolve().parent / "agents" / "registry.toml"


def _build_registry_snapshot() -> _AgentRegistrySnapshot:
    loaded_registry = load_agent_registry()
    return _AgentRegistrySnapshot(
        default_agent_id=loaded_registry.config.default_agent_id,
        legacy_agent_aliases=dict(loaded_registry.config.aliases),
        public_agent_ids=loaded_registry.config.public_agent_ids,
        agent_profiles={
            agent_id: _build_agent_profile(manifest)
            for agent_id, manifest in loaded_registry.manifests.items()
        },
    )


def _raise_registry_load_error(exc: Exception) -> NoReturn:
    if isinstance(exc, AgentRegistryLoadError):
        raise exc
    raise AgentRegistryLoadError(
        registry_path=_AGENT_REGISTRY_PATH,
        cause=exc,
    ) from exc


def _get_registry_snapshot() -> _AgentRegistrySnapshot:
    global _REGISTRY_SNAPSHOT, _REGISTRY_LOAD_ERROR

    if _REGISTRY_SNAPSHOT is not None:
        return _REGISTRY_SNAPSHOT
    if _REGISTRY_LOAD_ERROR is not None:
        _raise_registry_load_error(_REGISTRY_LOAD_ERROR)

    with _REGISTRY_LOCK:
        if _REGISTRY_SNAPSHOT is not None:
            return _REGISTRY_SNAPSHOT
        if _REGISTRY_LOAD_ERROR is not None:
            _raise_registry_load_error(_REGISTRY_LOAD_ERROR)

        try:
            _REGISTRY_SNAPSHOT = _build_registry_snapshot()
        except Exception as exc:
            _REGISTRY_LOAD_ERROR = exc
            logger.error(
                f'Failed to load agent registry configuration from "{_AGENT_REGISTRY_PATH}": {exc}'
            )
            _raise_registry_load_error(exc)

    return _REGISTRY_SNAPSHOT


def get_default_agent_id() -> str:
    return _get_registry_snapshot().default_agent_id


def get_agent_profiles() -> dict[str, AgentProfile]:
    return _get_registry_snapshot().agent_profiles


def canonicalize_agent_id(agent_id: str | None) -> str:
    """Normalize empty values and configured aliases without validating existence."""
    candidate = str(agent_id or "").strip()
    if not candidate:
        return get_default_agent_id()
    return _get_registry_snapshot().legacy_agent_aliases.get(candidate, candidate)


def resolve_known_agent_id(
    agent_id: str | None,
    *,
    allow_none: bool = False,
    default_on_unknown: bool = False,
) -> str | None:
    candidate = str(agent_id or "").strip()
    if not candidate:
        return None if allow_none else get_default_agent_id()

    normalized = canonicalize_agent_id(candidate)
    if normalized in get_agent_profiles():
        return normalized
    if default_on_unknown:
        return get_default_agent_id()
    if allow_none:
        return None
    raise ValueError(f"Unknown agent_id: {normalized}")


def list_agent_profiles(*, include_legacy: bool = True) -> list[AgentProfile]:
    snapshot = _get_registry_snapshot()
    ordered_ids = list(snapshot.public_agent_ids)
    if include_legacy:
        ordered_ids.extend(
            agent_id
            for agent_id in snapshot.agent_profiles
            if agent_id not in snapshot.public_agent_ids
        )
    return [
        snapshot.agent_profiles[agent_id]
        for agent_id in ordered_ids
        if agent_id in snapshot.agent_profiles
    ]


def list_public_agent_profiles() -> list[AgentProfile]:
    return list_agent_profiles(include_legacy=False)


def get_agent_profile(agent_id: str | None) -> AgentProfile:
    key = resolve_known_agent_id(agent_id)
    profile = get_agent_profiles().get(key)
    if profile is None:
        raise ValueError(f"Unknown agent_id: {key}")
    return profile
