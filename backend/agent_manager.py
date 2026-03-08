import asyncio
import os
from contextlib import AsyncExitStack
from pathlib import Path
from typing import Any

from deepagents import create_deep_agent
from deepagents.backends import CompositeBackend, StoreBackend
from langchain_anthropic import ChatAnthropic
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from langgraph.store.sqlite.aio import AsyncSqliteStore

from agent_profiles import (
    DEFAULT_AGENT_ID,
    AgentProfile,
    get_agent_profile,
    list_agent_profiles,
)
from config import MODEL_NAME, PROJECT_DIR, SQLITE_PATH
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
        self._init_lock = asyncio.Lock()
        self._runtime_lock = asyncio.Lock()

    def resolve_default_agent(self) -> str:
        return DEFAULT_AGENT_ID

    def list_profiles(self) -> list[AgentProfile]:
        return list_agent_profiles()

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
            logger.info("Multi-agent SQLite checkpointer + store 初始化完成")

    async def close(self):
        if self._resource_stack is not None:
            await self._resource_stack.aclose()

        self._sqlite_saver = None
        self._sqlite_store = None
        self._resource_stack = None
        self._llm = None
        self._runtimes.clear()
        logger.info("Multi-agent 运行时资源已关闭")

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

            runtime = self._build_runtime(profile)
            self._runtimes[profile.id] = runtime
            logger.info(
                f"Deep Agent 初始化完成: agent_id={profile.id}, skills={list(profile.skills)}"
            )
            return runtime

    def _build_runtime(self, profile: AgentProfile):
        if self._llm is None or self._sqlite_store is None or self._sqlite_saver is None:
            raise RuntimeError("AgentManager 尚未初始化")

        return create_deep_agent(
            model=self._llm,
            system_prompt=self._compose_system_prompt(profile),
            skills=resolve_skill_paths(profile.skills),
            store=self._sqlite_store,
            backend=self._make_backend,
            checkpointer=self._sqlite_saver,
            name=profile.id,
        )

    def _compose_system_prompt(self, profile: AgentProfile) -> str:
        project_root = Path(PROJECT_DIR)
        sections: list[str] = []

        for relative_path in profile.prompt_paths:
            prompt_path = project_root / relative_path
            try:
                content = prompt_path.read_text(encoding="utf-8").strip()
            except FileNotFoundError as exc:
                raise RuntimeError(
                    f"找不到 agent prompt 文件: {relative_path}"
                ) from exc
            if content:
                sections.append(content)

        sections.append(self._build_runtime_hint(profile))
        return "\n\n".join(section for section in sections if section)

    def _build_runtime_hint(self, profile: AgentProfile) -> str:
        allowed_handoffs = (
            "、".join(profile.allowed_handoffs) if profile.allowed_handoffs else "暂无"
        )
        capabilities = "、".join(profile.capabilities)
        memory_root = f"/memories/agents/{profile.id}/"

        return (
            "## 当前 Agent 运行时\n"
            f"- 你的 agent_id 是 `{profile.id}`，显示名称是“{profile.label}”。\n"
            f"- 你的能力边界是：{capabilities}。\n"
            f"- 你的风险等级是：{profile.risk_level}。\n"
            f"- 当前执行模式是：{profile.execution_mode}。\n"
            f"- 当前允许的 handoff 目标：{allowed_handoffs}。\n"
            f"- 当需要写入新的长期记忆时，优先写入 `{memory_root}`。\n"
            "- 当前会话固定绑定到你这个 Agent；如果问题明显超出你的职责范围，应明确说明并建议切换 Agent。\n"
            "- 你只能使用当前 runtime 已注入的 Skills，不要假装可以调用未授权技能。"
        )

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
