from pathlib import Path
from typing import Any

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - Python < 3.11 compatibility
    import tomli as tomllib

from .schema import (
    AgentManifest,
    ExecutionMode,
    LoadedAgentRegistry,
    RegistryConfig,
    RiskLevel,
)


BACKEND_ROOT = Path(__file__).resolve().parents[1]
VALID_RISK_LEVELS: set[RiskLevel] = {"low", "medium", "high"}
VALID_EXECUTION_MODES: set[ExecutionMode] = {"direct", "router", "supervisor"}


class AgentRegistryLoaderError(ValueError):
    def __init__(
        self,
        *,
        source_path: Path | str,
        reason: str,
        field_name: str | None = None,
        agent_id: str | None = None,
        cause: Exception | None = None,
    ) -> None:
        self.source_path = Path(source_path)
        self.reason = str(reason).strip() or "invalid agent registry configuration"
        self.field_name = field_name
        self.agent_id = agent_id
        self.cause = cause

        qualifiers = [f'"{self.source_path}"']
        if self.field_name:
            qualifiers.append(f'field "{self.field_name}"')
        if self.agent_id:
            qualifiers.append(f'agent "{self.agent_id}"')

        detail = self.reason
        if cause is not None:
            cause_text = str(cause).strip() or type(cause).__name__
            if not cause_text.startswith(f"{type(cause).__name__}:"):
                cause_text = f"{type(cause).__name__}: {cause_text}"
            detail = f"{detail}: {cause_text}"

        super().__init__(" ".join([*qualifiers, detail]))


def load_agent_registry(backend_root: Path | None = None) -> LoadedAgentRegistry:
    resolved_backend_root = (backend_root or BACKEND_ROOT).resolve()
    agents_root = resolved_backend_root / "agents"
    registry_path = agents_root / "registry.toml"
    config = _load_registry_config(registry_path)
    manifests = _load_agent_manifests(agents_root, resolved_backend_root)
    _validate_registry(config, manifests, registry_path=registry_path)
    return LoadedAgentRegistry(config=config, manifests=manifests)


def _load_registry_config(registry_path: Path) -> RegistryConfig:
    document = _read_toml(registry_path)
    default_agent_id = _read_string(
        document.get("default_agent_id"),
        field_name="default_agent_id",
        source_path=registry_path,
    )
    public_agent_ids = tuple(
        _read_string_list(
            document.get("public_agent_ids"),
            field_name="public_agent_ids",
            source_path=registry_path,
        )
    )

    aliases_raw = document.get("aliases") or {}
    if not isinstance(aliases_raw, dict):
        raise AgentRegistryLoaderError(
            source_path=registry_path,
            field_name="aliases",
            reason="must be a table",
        )

    aliases: dict[str, str] = {}
    for raw_alias, raw_target in aliases_raw.items():
        alias = _read_string(
            raw_alias, field_name="aliases.<key>", source_path=registry_path
        )
        target = _read_string(
            raw_target, field_name=f"aliases.{alias}", source_path=registry_path
        )
        aliases[alias] = target

    return RegistryConfig(
        default_agent_id=default_agent_id,
        public_agent_ids=public_agent_ids,
        aliases=aliases,
    )


def _load_agent_manifests(
    agents_root: Path, backend_root: Path
) -> dict[str, AgentManifest]:
    manifests: dict[str, AgentManifest] = {}

    for manifest_path in sorted(agents_root.glob("*/agent.toml")):
        manifest = _load_agent_manifest(manifest_path, backend_root)
        existing_manifest = manifests.get(manifest.id)
        if existing_manifest is not None:
            raise AgentRegistryLoaderError(
                source_path=manifest_path,
                agent_id=manifest.id,
                reason=(
                    f'duplicates manifest already loaded from "{_manifest_source_path(existing_manifest)}"'
                ),
            )
        manifests[manifest.id] = manifest

    if not manifests:
        raise AgentRegistryLoaderError(
            source_path=agents_root,
            reason='does not contain any "*/agent.toml" manifests',
        )

    return manifests


def _load_agent_manifest(manifest_path: Path, backend_root: Path) -> AgentManifest:
    document = _read_toml(manifest_path)
    agent_id = _read_string(document.get("id"), field_name="id", source_path=manifest_path)
    directory_name = manifest_path.parent.name
    if agent_id != directory_name:
        raise AgentRegistryLoaderError(
            source_path=manifest_path,
            field_name="id",
            agent_id=agent_id,
            reason=f'must match directory "{directory_name}"',
        )

    label = _read_string(document.get("label"), field_name="label", source_path=manifest_path)
    description = _read_string(
        document.get("description"),
        field_name="description",
        source_path=manifest_path,
    )
    prompt_paths = tuple(
        _read_string_list(
            document.get("prompt_paths"),
            field_name="prompt_paths",
            source_path=manifest_path,
        )
    )
    skills = tuple(
        _read_string_list(
            document.get("skills", []),
            field_name="skills",
            source_path=manifest_path,
        )
    )
    capabilities = tuple(
        _read_string_list(
            document.get("capabilities", []),
            field_name="capabilities",
            source_path=manifest_path,
        )
    )
    risk_level = _read_choice(
        document.get("risk_level"),
        field_name="risk_level",
        source_path=manifest_path,
        valid_values=VALID_RISK_LEVELS,
    )
    execution_mode = _read_choice(
        document.get("execution_mode"),
        field_name="execution_mode",
        source_path=manifest_path,
        valid_values=VALID_EXECUTION_MODES,
    )
    allowed_handoffs = tuple(
        _read_string_list(
            document.get("allowed_handoffs", []),
            field_name="allowed_handoffs",
            source_path=manifest_path,
        )
    )
    subagent_configs = tuple(
        _read_string_list(
            document.get("subagent_configs", []),
            field_name="subagent_configs",
            source_path=manifest_path,
        )
    )

    if not prompt_paths:
        raise AgentRegistryLoaderError(
            source_path=manifest_path,
            field_name="prompt_paths",
            agent_id=agent_id,
            reason="must declare at least one prompt path",
        )

    if execution_mode == "direct" and subagent_configs:
        raise AgentRegistryLoaderError(
            source_path=manifest_path,
            field_name="subagent_configs",
            agent_id=agent_id,
            reason="cannot be declared in direct mode",
        )

    backend_root = backend_root.resolve()
    for prompt_path in prompt_paths:
        resolved_prompt_path = (backend_root / prompt_path).resolve()
        if not resolved_prompt_path.is_relative_to(backend_root):
            raise AgentRegistryLoaderError(
                source_path=manifest_path,
                field_name="prompt_paths",
                agent_id=agent_id,
                reason=f'prompt "{prompt_path}" must stay inside backend root',
            )
        if not resolved_prompt_path.is_file():
            raise AgentRegistryLoaderError(
                source_path=manifest_path,
                field_name="prompt_paths",
                agent_id=agent_id,
                reason=f'references missing prompt file "{prompt_path}"',
            )

    return AgentManifest(
        id=agent_id,
        label=label,
        description=description,
        prompt_paths=prompt_paths,
        skills=skills,
        capabilities=capabilities,
        risk_level=risk_level,
        execution_mode=execution_mode,
        allowed_handoffs=allowed_handoffs,
        subagent_configs=subagent_configs,
        source_path=manifest_path.resolve(),
    )


def _validate_registry(
    config: RegistryConfig,
    manifests: dict[str, AgentManifest],
    *,
    registry_path: Path,
) -> None:
    if config.default_agent_id not in manifests:
        raise AgentRegistryLoaderError(
            source_path=registry_path,
            field_name="default_agent_id",
            reason=f'Default agent "{config.default_agent_id}" is not defined',
        )
    if config.default_agent_id not in config.public_agent_ids:
        raise AgentRegistryLoaderError(
            source_path=registry_path,
            field_name="public_agent_ids",
            reason=(
                f'Default agent "{config.default_agent_id}" must be included in public_agent_ids'
            ),
        )

    for public_agent_id in config.public_agent_ids:
        if public_agent_id not in manifests:
            raise AgentRegistryLoaderError(
                source_path=registry_path,
                field_name="public_agent_ids",
                reason=f'Public agent "{public_agent_id}" is not defined',
            )

    for alias, target in config.aliases.items():
        if alias in manifests:
            raise AgentRegistryLoaderError(
                source_path=registry_path,
                field_name=f"aliases.{alias}",
                reason=f'Alias "{alias}" conflicts with a real agent id',
            )
        if target not in manifests:
            raise AgentRegistryLoaderError(
                source_path=registry_path,
                field_name=f"aliases.{alias}",
                reason=f'Alias "{alias}" points to unknown agent "{target}"',
            )

    for manifest in manifests.values():
        _validate_manifest_relationships(manifest, manifests)


def _validate_manifest_relationships(
    manifest: AgentManifest,
    manifests: dict[str, AgentManifest],
) -> None:
    manifest_path = _manifest_source_path(manifest)

    if manifest.id in manifest.allowed_handoffs:
        raise AgentRegistryLoaderError(
            source_path=manifest_path,
            agent_id=manifest.id,
            field_name="allowed_handoffs",
            reason="cannot hand off to itself",
        )
    if manifest.id in manifest.subagent_configs:
        raise AgentRegistryLoaderError(
            source_path=manifest_path,
            agent_id=manifest.id,
            field_name="subagent_configs",
            reason="cannot register itself as a subagent",
        )

    for handoff_id in manifest.allowed_handoffs:
        if handoff_id not in manifests:
            raise AgentRegistryLoaderError(
                source_path=manifest_path,
                agent_id=manifest.id,
                field_name="allowed_handoffs",
                reason=f'references unknown agent "{handoff_id}"',
            )

    for subagent_id in manifest.subagent_configs:
        if subagent_id not in manifests:
            raise AgentRegistryLoaderError(
                source_path=manifest_path,
                agent_id=manifest.id,
                field_name="subagent_configs",
                reason=f'references unknown agent "{subagent_id}"',
            )
        if subagent_id not in manifest.allowed_handoffs:
            raise AgentRegistryLoaderError(
                source_path=manifest_path,
                agent_id=manifest.id,
                field_name="subagent_configs",
                reason=(
                    f'subagent "{subagent_id}" must also be declared in allowed_handoffs'
                ),
            )


def _read_toml(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise AgentRegistryLoaderError(
            source_path=path,
            reason="missing TOML file",
        )

    try:
        with path.open("rb") as handle:
            data = tomllib.load(handle)
    except tomllib.TOMLDecodeError as exc:
        raise AgentRegistryLoaderError(
            source_path=path,
            reason="contains invalid TOML",
            cause=exc,
        ) from exc
    except OSError as exc:
        raise AgentRegistryLoaderError(
            source_path=path,
            reason="could not be read",
            cause=exc,
        ) from exc

    if not isinstance(data, dict):
        raise AgentRegistryLoaderError(
            source_path=path,
            reason="must contain a top-level table",
        )
    return data


def _read_string(value: Any, *, field_name: str, source_path: Path) -> str:
    normalized = str(value or "").strip()
    if not normalized:
        raise AgentRegistryLoaderError(
            source_path=source_path,
            field_name=field_name,
            reason="must be a non-empty string",
        )
    return normalized


def _read_string_list(value: Any, *, field_name: str, source_path: Path) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise AgentRegistryLoaderError(
            source_path=source_path,
            field_name=field_name,
            reason="must be an array",
        )

    normalized: list[str] = []
    seen: set[str] = set()
    for item in value:
        text = _read_string(item, field_name=field_name, source_path=source_path)
        if text in seen:
            continue
        normalized.append(text)
        seen.add(text)
    return normalized


def _read_choice(
    value: Any,
    *,
    field_name: str,
    source_path: Path,
    valid_values: set[str],
) -> str:
    normalized = _read_string(value, field_name=field_name, source_path=source_path)
    if normalized not in valid_values:
        allowed = ", ".join(sorted(valid_values))
        raise AgentRegistryLoaderError(
            source_path=source_path,
            field_name=field_name,
            reason=f"must be one of: {allowed}",
        )
    return normalized


def _manifest_source_path(manifest: AgentManifest) -> Path:
    if manifest.source_path is not None:
        return manifest.source_path
    return Path("agents") / manifest.id / "agent.toml"
