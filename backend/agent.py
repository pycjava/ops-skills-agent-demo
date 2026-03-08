"""Claude Agent 核心模块 (DeepAgents 版)

使用 langchain-ai/deepagents 的 create_deep_agent 实现 Agent 对话。
提供了文件读写、Shell 执行、Skills 读取等能力，并支持真正的流式输出。
"""

import os
from contextlib import AsyncExitStack
from pathlib import Path
from typing import Any, Callable, Awaitable

from deepagents import create_deep_agent
from deepagents.backends import CompositeBackend, StoreBackend
from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from langgraph.store.sqlite.aio import AsyncSqliteStore

from config import MAX_TURNS, MODEL_NAME, PROJECT_DIR, SQLITE_PATH
from utils.agent_backend import FriendlyLocalShellBackend
from utils.logger import logger


# 用于推送给前端的事件类型
EVENT_TEXT = "text"
EVENT_TEXT_DELTA = "text_delta"
EVENT_THINKING_DELTA = "thinking_delta"
EVENT_TOOL_CALL = "tool_call"
EVENT_TOOL_RESULT = "tool_result"
EVENT_DONE = "done"
EVENT_ERROR = "error"


# ─── 自定义本地 Tools ──────────────────────────────────────────

# 根据 DeepAgents 的设计，我们不再需要自定义 skill 读取工具，
# create_deep_agent 会通过 skills=["./skills/"] 参数原生自动加载和管理。

# ─── 核心引擎 ──────────────────────────────────────────────────


def _build_shell_env_overrides() -> dict[str, str]:
    """为 LocalShellBackend 注入可复用环境:

    1. 继承当前进程环境变量（含 .env 读取结果）
    2. 优先把项目虚拟环境目录加入 PATH，确保 skills 里的 python 命令可用
    """
    overrides: dict[str, str] = {}
    current_path = os.environ.get("PATH", "")
    project_dir = Path(PROJECT_DIR)

    candidate_bins = [
        project_dir / ".venv" / "bin",  # backend/.venv/bin
        project_dir / ".venv" / "Scripts",  # backend/.venv/Scripts (Windows)
        project_dir.parent / ".venv" / "bin",  # repo/.venv/bin
        project_dir.parent / ".venv" / "Scripts",  # repo/.venv/Scripts (Windows)
    ]
    existing_bins = [str(p) for p in candidate_bins if p.exists()]

    if existing_bins:
        path_items = existing_bins + ([current_path] if current_path else [])
        overrides["PATH"] = os.pathsep.join(path_items)
        overrides["VIRTUAL_ENV"] = str(Path(existing_bins[0]).parent)

    return overrides


# ─── 持久化存储（延迟异步初始化） ──────────────────────────────

# 异步版本需要在 async 上下文中初始化，在 FastAPI startup 中调用 init_agent_runtime()
_sqlite_saver: AsyncSqliteSaver | None = None
_sqlite_store: AsyncSqliteStore | None = None
_resource_stack: AsyncExitStack | None = None
_agent = None


def get_memory_store() -> AsyncSqliteStore | None:
    return _sqlite_store


async def init_agent_runtime():
    """在 FastAPI startup 中调用，异步初始化 SQLite checkpointer、store 和 Agent。"""
    global _sqlite_saver, _sqlite_store, _resource_stack, _agent

    if _agent is not None:
        return

    Path(SQLITE_PATH).parent.mkdir(parents=True, exist_ok=True)

    _resource_stack = AsyncExitStack()

    try:
        _sqlite_saver = await _resource_stack.enter_async_context(
            AsyncSqliteSaver.from_conn_string(SQLITE_PATH)
        )
        await _sqlite_saver.setup()

        _sqlite_store = await _resource_stack.enter_async_context(
            AsyncSqliteStore.from_conn_string(SQLITE_PATH)
        )
        await _sqlite_store.setup()
    except Exception:
        await _resource_stack.aclose()
        _resource_stack = None
        _sqlite_saver = None
        _sqlite_store = None
        raise

    logger.info("SQLite checkpointer + store 初始化完成")

    # ─── 初始化 Agent ──────────────────────────────────────────
    _llm = ChatAnthropic(
        model_name=MODEL_NAME,
        temperature=1,  # extended thinking 要求 temperature=1
        thinking={"type": "enabled", "budget_tokens": 10000},
    )

    _agent = create_deep_agent(
        model=_llm,
        memory=["./AGENTS.md"],
        skills=["./skills/"],
        store=_sqlite_store,
        backend=_make_backend,
        checkpointer=_sqlite_saver,
    )
    logger.info("Deep Agent 初始化完成")


async def close_agent_runtime():
    """关闭 Agent 运行时持有的 SQLite 资源。"""
    global _sqlite_saver, _sqlite_store, _resource_stack, _agent

    if _resource_stack is not None:
        await _resource_stack.aclose()

    _sqlite_saver = None
    _sqlite_store = None
    _resource_stack = None
    _agent = None
    logger.info("Deep Agent 运行时资源已关闭")


# ─── Backend 路由 ──────────────────────────────────────────────


def _make_backend(runtime):
    """CompositeBackend 路由:
    - /memories/ 路径 → StoreBackend (持久化存储，跨会话共享)
    - 其他路径 → FriendlyLocalShellBackend (以 backend/ 为虚拟根的本地文件系统)
    """
    return CompositeBackend(
        default=FriendlyLocalShellBackend(
            root_dir=PROJECT_DIR,
            virtual_mode=True,
            inherit_env=True,
            env=_build_shell_env_overrides(),
        ),
        routes={
            "/memories/": StoreBackend(runtime),
        },
    )


async def run_agent(
    user_message: str,
    conv_id: str,
    on_event: Callable[[dict[str, Any]], Awaitable[None]],
):
    """
    使用 deepagents (LangGraph) 运行 Agent，并处理细粒度的流式事件。
    """
    if _agent is None:
        raise RuntimeError("Agent 尚未初始化，请先调用 init_agent_runtime()")

    inputs = {"messages": [HumanMessage(content=user_message)]}

    try:
        # 传入带有 thread_id 的 config，让 MemorySaver 为同一个对话保持上下文
        # recursion_limit 控制 LangGraph 图的最大递归步数（每轮 Agent 循环约消耗 2-4 步）
        config = {
            "configurable": {"thread_id": conv_id},
            "recursion_limit": MAX_TURNS * 8,
        }
        # 使用 astream_events 获取逐 token 的细粒度流
        async for event in _agent.astream_events(inputs, config=config, version="v2"):
            kind = event["event"]
            name = event.get("name", "")

            # --- 文本 Token 流式输出 ---
            if kind == "on_chat_model_stream":
                chunk = event["data"]["chunk"]
                content = chunk.content
                if content:
                    # content 可能是字符串，也可能是包含 text block/thinking block 字典的列表
                    text_delta = ""
                    if isinstance(content, str):
                        text_delta = content
                    if isinstance(content, list):
                        for block in content:
                            logger.debug(
                                f"Stream block type={type(block).__name__}, keys={block.keys() if isinstance(block, dict) else 'N/A'}, block={str(block)[:200]}"
                            )
                            if isinstance(block, dict):
                                if "text" in block:
                                    text_delta += block.get("text", "")
                                elif "thinking" in block:
                                    thinking_text = block.get("thinking", "")
                                    if thinking_text:
                                        await on_event(
                                            {
                                                "type": EVENT_THINKING_DELTA,
                                                "content": thinking_text,
                                            }
                                        )
                            elif isinstance(block, str):
                                text_delta += block

                    if text_delta:
                        await on_event(
                            {"type": EVENT_TEXT_DELTA, "content": text_delta}
                        )

            # --- 工具调用开始 ---
            elif kind == "on_tool_start":
                tool_input = event["data"].get("input", {})
                tool_desc = f"正在调用工具: {name}..."
                if name == "execute":
                    tool_desc = "正在打开终端执行 Shell 命令..."
                elif name in ["read_file", "ls", "glob", "grep"]:
                    tool_desc = "正在检索项目文件..."
                elif name in ["write_file", "edit_file", "write_todos"]:
                    tool_desc = "正在修改本地代码/文件..."

                await on_event(
                    {
                        "type": EVENT_TOOL_CALL,
                        "tool_name": name,
                        "tool_desc": tool_desc,
                        "tool_input": tool_input,
                    }
                )

            # --- 工具调用结束 ---
            elif kind == "on_tool_end":
                output = event["data"].get("output", "")

                # output 可能是一个 Langchain ToolMessage 对象
                if hasattr(output, "content"):
                    result_text = str(output.content)
                elif isinstance(output, dict) and "content" in output:
                    result_text = str(output["content"])
                else:
                    result_text = str(output)

                await on_event(
                    {
                        "type": EVENT_TOOL_RESULT,
                        "tool_name": name,
                        "result": result_text[:2000]
                        + ("\n...[截断]" if len(result_text) > 2000 else ""),
                    }
                )

        # 整个图执行完毕
        await on_event({"type": EVENT_DONE})

    except Exception as e:
        logger.exception(f"Agent 执行异常: {e}")
        await on_event(
            {
                "type": EVENT_ERROR,
                "content": f"Agent 执行出错: {str(e)}",
            }
        )
