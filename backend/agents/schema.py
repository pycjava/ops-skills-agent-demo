from dataclasses import dataclass
from pathlib import Path
from typing import Literal


RiskLevel = Literal["low", "medium", "high"]
ExecutionMode = Literal["direct", "router", "supervisor"]


@dataclass(frozen=True, slots=True)
class RegistryConfig:
    default_agent_id: str
    public_agent_ids: tuple[str, ...]
    aliases: dict[str, str]


@dataclass(frozen=True, slots=True)
class AgentManifest:
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
    source_path: Path | None = None


@dataclass(frozen=True, slots=True)
class LoadedAgentRegistry:
    config: RegistryConfig
    manifests: dict[str, AgentManifest]
