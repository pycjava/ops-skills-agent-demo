import asyncio
import os
from contextlib import AsyncExitStack
from pathlib import Path
from typing import Any

from deepagents import SubAgent, create_deep_agent
from deepagents.backends import CompositeBackend, StoreBackend
from langchain_anthropic import ChatAnthropic
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from langgraph.store.sqlite.aio import AsyncSqliteStore

from agent_profiles import (
    AGENT_PROFILES,
    DEFAULT_AGENT_ID,
    AgentProfile,
    get_agent_profile,
    list_agent_profiles,
)
from config import MODEL_NAME, PROJECT_DIR, SQLITE_PATH
from services.mcp_registry import McpRegistryService
from skill_catalog import resolve_skill_paths
from utils.agent_backend import FriendlyLocalShellBackend
from utils.logger import logger


def _build_shell_env_overrides() -> dict[str, str]:
    overrides: dict[str, str] = {}
    current_path = os.environ.get("PATH", "")
    project_dir = Path(PROJECT_DIR)

    candidate_bins = [
        project_dir / ".venv" / "bin",
        project_dir / ".venv" / "Scripts",
        project_dir.parent / ".venv" / "bin",
        project_dir.parent / ".venv" / "Scripts",
    ]
    existing_bins = [str(path) for path in candidate_bins if path.exists()]

    if existing_bins:
        path_items = existing_bins + ([current_path] if current_path else [])
        overrides["PATH"] = os.pathsep.join(path_items)
        overrides["VIRTUAL_ENV"] = str(Path(existing_bins[0]).parent)

    return overrides


class AgentManager:
    def __init__(self):
        self._sqlite_saver: AsyncSqliteSaver | None = None
        self._sqlite_store: AsyncSqliteStore | None = None
        self._resource_stack: AsyncExitStack | None = None
        self._llm: ChatAnthropic | None = None
        self._runtimes: dict[str, Any] = {}
        self._mcp_registry = McpRegistryService()
        self._init_lock = asyncio.Lock()
        self._runtime_lock = asyncio.Lock()

    def resolve_default_agent(self) -> str:
        return DEFAULT_AGENT_ID

    def list_profiles(self, *, include_legacy: bool = True) -> list[AgentProfile]:
        return list_agent_profiles(include_legacy=include_legacy)

    def get_profile(self, agent_id: str) -> AgentProfile:
        return get_agent_profile(agent_id)

    def get_memory_store(self) -> AsyncSqliteStore | None:
        return self._sqlite_store

    async def init(self):
        async with self._init_lock:
            if self._resource_stack is not None:
                return

            Path(SQLITE_PATH).parent.mkdir(parents=True, exist_ok=True)

            stack = AsyncExitStack()
            try:
                sqlite_saver = await stack.enter_async_context(
                    AsyncSqliteSaver.from_conn_string(SQLITE_PATH)
                )
                await sqlite_saver.setup()

                sqlite_store = await stack.enter_async_context(
                    AsyncSqliteStore.from_conn_string(SQLITE_PATH)
                )
                await sqlite_store.setup()
            except Exception:
                await stack.aclose()
                raise

            self._resource_stack = stack
            self._sqlite_saver = sqlite_saver
            self._sqlite_store = sqlite_store
            self._llm = ChatAnthropic(
                model_name=MODEL_NAME,
                temperature=1,
                thinking={"type": "enabled", "budget_tokens": 10000},
            )
            logger.info("Multi-agent SQLite checkpointer + store initialized")

    async def close(self):
        if self._resource_stack is not None:
            await self._resource_stack.aclose()

        self._sqlite_saver = None
        self._sqlite_store = None
        self._resource_stack = None
        self._llm = None
        self._runtimes.clear()
        logger.info("Multi-agent runtime resources released")

    async def invalidate_runtime_cache(self):
        async with self._runtime_lock:
            self._runtimes.clear()
        logger.info("Deep Agent runtime cache invalidated")

    async def get_runtime(self, agent_id: str):
        profile = self.get_profile(agent_id)
        await self.init()

        cached = self._runtimes.get(profile.id)
        if cached is not None:
            return cached

        async with self._runtime_lock:
            cached = self._runtimes.get(profile.id)
            if cached is not None:
                return cached

            runtime = await self._build_runtime(profile)
            self._runtimes[profile.id] = runtime
            logger.info(
                "Deep Agent initialized: "
                f"agent_id={profile.id}, mode={profile.execution_mode}"
            )
            return runtime

    async def _build_runtime(self, profile: AgentProfile):
        if (
            self._llm is None
            or self._sqlite_store is None
            or self._sqlite_saver is None
        ):
            raise RuntimeError("AgentManager is not initialized")

        mcp_tools = await self._load_mcp_tools(profile.id)
        subagents = self._build_subagents(profile) if profile.subagent_configs else None

        return create_deep_agent(
            model=self._llm,
            system_prompt=self._compose_system_prompt(profile),
            skills=resolve_skill_paths(profile.skills),
            tools=mcp_tools,
            store=self._sqlite_store,
            backend=self._make_backend,
            checkpointer=self._sqlite_saver,
            name=profile.id,
            subagents=subagents,
        )

    def _build_subagents(
        self,
        profile: AgentProfile,
        *,
        lineage: tuple[str, ...] = (),
    ) -> list[SubAgent]:
        if self._llm is None:
            raise RuntimeError("AgentManager is not initialized")

        subagents: list[SubAgent] = []

        for subagent_id in profile.subagent_configs:
            if subagent_id not in AGENT_PROFILES:
                logger.warning(f"Unknown subagent config: {subagent_id}")
                continue

            if subagent_id in lineage:
                logger.warning(
                    "Skipping recursive subagent config: "
                    f"{' -> '.join((*lineage, subagent_id))}"
                )
                continue

            subagent_profile = AGENT_PROFILES[subagent_id]
            nested_subagents = (
                self._build_subagents(
                    subagent_profile,
                    lineage=(*lineage, profile.id),
                )
                if subagent_profile.subagent_configs
                else None
            )

            subagent: SubAgent = {
                "name": subagent_profile.id,
                "description": f"{subagent_profile.label}：{subagent_profile.description}",
                "system_prompt": self._compose_system_prompt(subagent_profile),
                "model": self._llm,
                "tools": [],
                "skills": resolve_skill_paths(subagent_profile.skills),
            }
            if nested_subagents:
                subagent["subagents"] = nested_subagents

            subagents.append(subagent)
            logger.info(
                "Registered subagent: "
                f"{subagent_profile.id} for {profile.id}"
            )

        return subagents

    async def _load_mcp_tools(self, agent_id: str) -> list[Any]:
        try:
            connections = await self._mcp_registry.get_agent_connections(agent_id)
        except Exception as exc:
            logger.warning(f"Failed to resolve MCP servers for agent {agent_id}: {exc}")
            return []

        if not connections:
            return []

        try:
            from langchain_mcp_adapters.client import MultiServerMCPClient
        except Exception as exc:
            logger.warning(f"Failed to import MCP adapters: {exc}")
            return []

        client = MultiServerMCPClient(connections, tool_name_prefix=True)
        tools: list[Any] = []

        for server_name in connections:
            try:
                server_tools = await client.get_tools(server_name=server_name)
            except Exception as exc:
                logger.warning(
                    f"Skipping MCP server {server_name} for agent {agent_id}: {exc}"
                )
                continue
            tools.extend(server_tools)

        if tools:
            logger.info(f"Loaded {len(tools)} MCP tools for agent {agent_id}")
        return tools

    def _compose_system_prompt(self, profile: AgentProfile) -> str:
        project_root = Path(PROJECT_DIR)
        sections: list[str] = []

        for relative_path in profile.prompt_paths:
            prompt_path = project_root / relative_path
            try:
                content = prompt_path.read_text(encoding="utf-8").strip()
            except FileNotFoundError as exc:
                raise RuntimeError(
                    f"Missing agent prompt file: {relative_path}"
                ) from exc
            if content:
                sections.append(content)

        sections.append(self._build_runtime_hint(profile))
        return "\n\n".join(section for section in sections if section)

    def _build_runtime_hint(self, profile: AgentProfile) -> str:
        allowed_handoffs = "、".join(profile.allowed_handoffs) if profile.allowed_handoffs else "暂无"
        capabilities = "、".join(profile.capabilities)
        memory_root = f"/memories/agents/{profile.id}/"

        lines = [
            "## 当前 Agent 运行时",
            f"- 你的 agent_id 是 `{profile.id}`，显示名称是“{profile.label}”。",
            f"- 你的执行模式是：{profile.execution_mode}。",
            f"- 你的能力边界是：{capabilities}。",
            f"- 你的风险等级是：{profile.risk_level}。",
        ]

        if profile.subagent_configs:
            lines.append(f"- 你可调度的子 Agent：{allowed_handoffs}。")

        if profile.execution_mode == "router":
            lines.extend(
                [
                    "- 你是默认入口，只做一次路由决策：直达叶子 Agent，或升级给 supervisor。",
                    "- 命中复杂、多域、冲突、异常升级场景时，立即使用 task 转交 supervisor。",
                    "- 不要自行展开复杂并行诊断或最终整合结论。",
                ]
            )
        elif profile.execution_mode == "supervisor":
            lines.extend(
                [
                    "- 你只处理 router 升级上来的复杂任务，不要把任务回交 router。",
                    "- 你可以串行或并行调用多个叶子 Agent，并负责统一整合结论、证据和建议。",
                ]
            )
        elif profile.execution_mode == "orchestrator":
            lines.append("- 你是兼容别名，仅用于旧入口兼容；行为边界按 router 处理。")

        lines.extend(
            [
                f"- 需要写入新的长期记忆时，优先写入 `{memory_root}`。",
                "- 你只能使用当前 runtime 已注入的 Skills 和工具。",
            ]
        )

        return "\n".join(lines)

    def _make_backend(self, runtime):
        return CompositeBackend(
            default=FriendlyLocalShellBackend(
                root_dir=PROJECT_DIR,
                env=_build_shell_env_overrides(),
                inherit_env=True,
                virtual_mode=True,
            ),
            routes={
                "/memories/": StoreBackend(runtime),
            },
        )
