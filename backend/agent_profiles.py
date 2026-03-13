from dataclasses import dataclass
from typing import Literal


RiskLevel = Literal["low", "medium", "high"]
ExecutionMode = Literal["direct", "router", "supervisor", "orchestrator"]


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


DEFAULT_AGENT_ID = "router"
LEGACY_AGENT_ALIASES: dict[str, str] = {
    "orchestrator": "router",
}
PUBLIC_AGENT_IDS: tuple[str, ...] = ("router", "supervisor", "general", "dba", "ops")


AGENT_PROFILES: dict[str, AgentProfile] = {
    "router": AgentProfile(
        id="router",
        label="智能编排助手",
        description="默认入口，负责轻量意图识别、单域分流与复杂问题升级。",
        prompt_paths=("prompts/base.md", "prompts/router.md"),
        skills=("using-superpowers",),
        capabilities=("意图识别", "轻量路由", "升级判断"),
        risk_level="low",
        execution_mode="router",
        allowed_handoffs=("general", "dba", "ops", "supervisor"),
        subagent_configs=("general", "dba", "ops", "supervisor"),
    ),
    "supervisor": AgentProfile(
        id="supervisor",
        label="复杂任务协调器",
        description="负责多域任务编排、异常升级诊断、并行调度与统一整合输出。",
        prompt_paths=("prompts/base.md", "prompts/supervisor.md"),
        skills=("using-superpowers",),
        capabilities=("复杂任务编排", "跨域诊断", "结果整合"),
        risk_level="low",
        execution_mode="supervisor",
        allowed_handoffs=("general", "dba", "ops"),
        subagent_configs=("general", "dba", "ops"),
    ),
    "orchestrator": AgentProfile(
        id="orchestrator",
        label="智能编排助手（兼容）",
        description="兼容旧会话与旧 API 的历史入口，新请求会归一化到 router。",
        prompt_paths=("prompts/base.md", "prompts/router.md"),
        skills=("using-superpowers",),
        capabilities=("兼容别名", "轻量路由", "升级判断"),
        risk_level="low",
        execution_mode="orchestrator",
        allowed_handoffs=("general", "dba", "ops", "supervisor"),
        subagent_configs=("general", "dba", "ops", "supervisor"),
    ),
    "general": AgentProfile(
        id="general",
        label="通用助手",
        description="负责通用问答、文档阅读、代码解释与轻量内容整理。",
        prompt_paths=("prompts/base.md", "prompts/general.md"),
        skills=("file_reader", "code_explainer", "obsidian-markdown", "using-superpowers"),
        capabilities=("通用问答", "文档阅读", "代码解释"),
        risk_level="low",
    ),
    "dba": AgentProfile(
        id="dba",
        label="数据库助手",
        description="负责 MySQL SQL 分析、Volcengine RDS 巡检与数据库诊断。",
        prompt_paths=("prompts/base.md", "prompts/dba.md"),
        skills=(
            "mysql-sql-analyzer",
            "volcengine-rds-health-analyzer",
            "volcengine-rds-report-summarizer",
            "using-superpowers",
        ),
        capabilities=("SQL 分析", "RDS 巡检", "数据库诊断"),
        risk_level="medium",
    ),
    "ops": AgentProfile(
        id="ops",
        label="运维助手",
        description="负责远程运维、Docker 排障与 Kubernetes 诊断。",
        prompt_paths=("prompts/base.md", "prompts/ops.md"),
        skills=("remote-ops", "docker", "kubernetes", "using-superpowers"),
        capabilities=("远程运维", "Docker 排障", "Kubernetes 诊断"),
        risk_level="high",
    ),
}


def canonicalize_agent_id(agent_id: str | None) -> str:
    candidate = (agent_id or "").strip()
    if not candidate:
        return DEFAULT_AGENT_ID
    return LEGACY_AGENT_ALIASES.get(candidate, candidate)


def list_agent_profiles(*, include_legacy: bool = True) -> list[AgentProfile]:
    profiles = list(AGENT_PROFILES.values())
    if include_legacy:
        return profiles
    return [profile for profile in profiles if profile.id in PUBLIC_AGENT_IDS]


def list_public_agent_profiles() -> list[AgentProfile]:
    return list_agent_profiles(include_legacy=False)


def get_agent_profile(agent_id: str) -> AgentProfile:
    key = (agent_id or "").strip()
    profile = AGENT_PROFILES.get(key)
    if profile is None:
        raise ValueError(f"未知 agent_id: {agent_id}")
    return profile
