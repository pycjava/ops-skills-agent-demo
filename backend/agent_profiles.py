from dataclasses import dataclass
from typing import Literal


RiskLevel = Literal["low", "medium", "high"]
ExecutionMode = Literal["direct", "router", "supervisor"]


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
            "is_default": is_default,
        }


DEFAULT_AGENT_ID = "general"


AGENT_PROFILES: dict[str, AgentProfile] = {
    "general": AgentProfile(
        id="general",
        label="通用助手",
        description="负责通用问答、文件阅读、代码解释与多能力协调。",
        prompt_paths=("prompts/base.md", "prompts/general.md"),
        skills=("file_reader", "code_explainer", "obsidian-markdown"),
        capabilities=("通用问答", "文档阅读", "代码解释"),
        risk_level="low",
    ),
    "dba": AgentProfile(
        id="dba",
        label="数据库助手",
        description="负责 MySQL SQL 分析、Volcengine RDS 健康巡检与数据库诊断。",
        prompt_paths=("prompts/base.md", "prompts/dba.md"),
        skills=(
            "mysql-sql-analyzer",
            "volcengine-rds-health-analyzer",
            "volcengine-rds-report-summarizer",
        ),
        capabilities=("SQL 分析", "RDS 巡检", "数据库诊断"),
        risk_level="medium",
    ),
    "ops": AgentProfile(
        id="ops",
        label="运维助手",
        description="负责远程运维、Docker 排查与 Kubernetes 诊断。",
        prompt_paths=("prompts/base.md", "prompts/ops.md"),
        skills=("remote-ops", "docker", "kubernetes"),
        capabilities=("远程运维", "Docker 排查", "Kubernetes 诊断"),
        risk_level="high",
    ),
}


def list_agent_profiles() -> list[AgentProfile]:
    return list(AGENT_PROFILES.values())


def get_agent_profile(agent_id: str) -> AgentProfile:
    key = (agent_id or "").strip()
    profile = AGENT_PROFILES.get(key)
    if profile is None:
        raise ValueError(f"未知 agent_id: {agent_id}")
    return profile

