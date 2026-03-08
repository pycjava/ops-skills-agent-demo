"""Claude Agent 核心模块 (Multi-Agent 版)."""

from collections import defaultdict, deque
from typing import Any, Awaitable, Callable

from langchain_core.messages import HumanMessage

from agent_manager import AgentManager
from config import MAX_TURNS
from utils.logger import logger


EVENT_TEXT_DELTA = "text_delta"
EVENT_THINKING_DELTA = "thinking_delta"
EVENT_TOOL_CALL = "tool_call"
EVENT_TOOL_RESULT = "tool_result"
EVENT_DONE = "done"
EVENT_ERROR = "error"

ARTIFACT_KIND_MEMORY = "memory"
ARTIFACT_KIND_REPORT = "report"
ARTIFACT_KIND_FILE = "file"
REPORT_EXTENSIONS = (".md", ".html", ".pdf")


_manager = AgentManager()


def list_agent_profiles():
    return _manager.list_profiles()


def resolve_default_agent() -> str:
    return _manager.resolve_default_agent()


def get_memory_store():
    return _manager.get_memory_store()


async def init_agent_runtime():
    await _manager.init()


async def close_agent_runtime():
    await _manager.close()


async def invalidate_runtime_cache():
    await _manager.invalidate_runtime_cache()


async def get_runtime(agent_id: str):
    return await _manager.get_runtime(agent_id)


def classify_artifact_kind(
    tool_name: str, tool_input: dict[str, Any] | None
) -> str | None:
    if tool_name not in {"write_file", "edit_file"} or not isinstance(tool_input, dict):
        return None

    raw_path = tool_input.get("file_path") or tool_input.get("path")
    if not isinstance(raw_path, str):
        return None

    normalized_path = raw_path.strip().lower()
    if not normalized_path:
        return None

    if normalized_path.startswith("/memories/"):
        return ARTIFACT_KIND_MEMORY
    if normalized_path.endswith(REPORT_EXTENSIONS):
        return ARTIFACT_KIND_REPORT
    return ARTIFACT_KIND_FILE


async def run_agent(
    user_message: str,
    conv_id: str,
    on_event: Callable[[dict[str, Any]], Awaitable[None]],
    agent_id: str | None = None,
):
    """使用 deepagents (LangGraph) 运行指定 Agent，并处理流式事件。"""
    resolved_agent_id = agent_id or resolve_default_agent()
    runtime = await get_runtime(resolved_agent_id)

    inputs = {"messages": [HumanMessage(content=user_message)]}
    pending_tool_inputs: dict[str, deque[dict[str, Any]]] = defaultdict(deque)

    try:
        config = {
            "configurable": {"thread_id": conv_id},
            "recursion_limit": MAX_TURNS * 8,
        }
        async for event in runtime.astream_events(inputs, config=config, version="v2"):
            kind = event["event"]
            name = event.get("name", "")

            if kind == "on_chat_model_stream":
                chunk = event["data"]["chunk"]
                content = chunk.content
                if content:
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
                                                "agent_id": resolved_agent_id,
                                            }
                                        )
                            elif isinstance(block, str):
                                text_delta += block

                    if text_delta:
                        await on_event(
                            {
                                "type": EVENT_TEXT_DELTA,
                                "content": text_delta,
                                "agent_id": resolved_agent_id,
                            }
                        )

            elif kind == "on_tool_start":
                tool_input = event["data"].get("input", {})
                if isinstance(tool_input, dict):
                    pending_tool_inputs[name].append(tool_input)
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
                        "agent_id": resolved_agent_id,
                    }
                )

            elif kind == "on_tool_end":
                output = event["data"].get("output", "")
                tool_input = None
                queued_inputs = pending_tool_inputs.get(name)
                if queued_inputs:
                    tool_input = queued_inputs.popleft()
                    if not queued_inputs:
                        pending_tool_inputs.pop(name, None)
                artifact_kind = classify_artifact_kind(name, tool_input)

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
                        "tool_input": tool_input,
                        "artifact_kind": artifact_kind,
                        "agent_id": resolved_agent_id,
                    }
                )

        await on_event({"type": EVENT_DONE, "agent_id": resolved_agent_id})

    except Exception as exc:
        logger.exception(f"Agent 执行异常: {exc}")
        await on_event(
            {
                "type": EVENT_ERROR,
                "content": f"Agent 执行出错: {str(exc)}",
                "agent_id": resolved_agent_id,
            }
        )
