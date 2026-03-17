"""AgentWeave 核心模块 (Multi-Agent 版)."""

from collections import defaultdict, deque
import re
from typing import Any, Awaitable, Callable

from langchain_core.messages import HumanMessage

from agent_manager import AgentManager
from agent_profiles import canonicalize_agent_id, get_agent_memory_roots
from config import ANTHROPIC_API_KEY, MAX_TURNS
from services.agent_event_state import AgentEventSnapshot, AgentEventState
from services.agent_event_identity import resolve_event_agent_id
from services.conversation_attachments import save_ocr_result
from services.message_preprocess import resolve_message_preprocess_plan
from services.multimodal_ocr import (
    build_multimodal_capability_context,
    should_attach_multimodal_images,
)
from utils.logger import logger


EVENT_TEXT_DELTA = "text_delta"
EVENT_THINKING_DELTA = "thinking_delta"
EVENT_TOOL_CALL = "tool_call"
EVENT_TOOL_RESULT = "tool_result"
EVENT_DONE = "done"
EVENT_ERROR = "error"
EVENT_OCR_STATUS = "ocr_status"
EVENT_OCR_RESULT = "ocr_result"

ARTIFACT_KIND_MEMORY = "memory"
ARTIFACT_KIND_REPORT = "report"
ARTIFACT_KIND_FILE = "file"
REPORT_EXTENSIONS = (".md", ".html", ".pdf")
REPORT_MEMORY_PREFIX = "/memories/reports/"
MEMORY_INSTRUCTIONS_PATH = "/memories/instructions.txt"
DBA_CLOUD_REGISTRY_PATH = "/memories/agents/dba/cloud_credentials_registry.json"
MEMORY_EXCERPT_MAX_LINES = 24
MEMORY_EXCERPT_MAX_CHARS = 1600
MEMORY_MATCH_LIMIT = 3
_manager = AgentManager()


def list_agent_profiles(*, include_legacy: bool = True):
    return _manager.list_profiles(include_legacy=include_legacy)


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


def _flatten_memory_nodes(nodes: list[dict[str, Any]]) -> list[str]:
    paths: list[str] = []
    for node in nodes:
        path = node.get("path")
        kind = node.get("kind")
        if kind == "file" and isinstance(path, str):
            paths.append(path)
        children = node.get("children")
        if isinstance(children, list):
            paths.extend(_flatten_memory_nodes(children))
    return paths


def _extract_message_keywords(user_message: str) -> list[str]:
    raw_tokens = re.findall(r"[A-Za-z0-9][A-Za-z0-9._-]{1,}", user_message.lower())
    tokens: list[str] = []
    seen: set[str] = set()
    for token in raw_tokens:
        if token in seen:
            continue
        seen.add(token)
        tokens.append(token)
    return tokens


def _build_memory_excerpt(content: str) -> str:
    lines = [line.rstrip() for line in content.splitlines()]
    excerpt_lines: list[str] = []
    char_count = 0

    for line in lines:
        if not line.strip() and excerpt_lines and not excerpt_lines[-1]:
            continue
        excerpt_lines.append(line)
        char_count += len(line) + 1
        if len(excerpt_lines) >= MEMORY_EXCERPT_MAX_LINES:
            break
        if char_count >= MEMORY_EXCERPT_MAX_CHARS:
            break

    excerpt = "\n".join(excerpt_lines).strip()
    if len(content) > len(excerpt):
        excerpt = f"{excerpt}\n..."
    return excerpt


def _score_memory_document(path: str, content: str, keywords: list[str]) -> int:
    path_lower = path.lower()
    content_lower = content.lower()
    score = 0

    for keyword in keywords:
        if keyword in path_lower:
            score += 8
        if keyword in content_lower:
            score += 4

    return score


async def _build_memory_context(user_message: str, agent_id: str) -> str | None:
    try:
        from services.memory import list_memory_tree, read_memory_document

        tree = await list_memory_tree()
        all_paths = _flatten_memory_nodes(tree)
        if not all_paths:
            return None

        keywords = _extract_message_keywords(user_message)
        agent_roots = get_agent_memory_roots(agent_id)

        selected_docs: list[tuple[str, str, int]] = []

        if MEMORY_INSTRUCTIONS_PATH in all_paths:
            instructions = await read_memory_document(MEMORY_INSTRUCTIONS_PATH)
            content = instructions.get("content", "")
            if isinstance(content, str) and content.strip():
                selected_docs.append((MEMORY_INSTRUCTIONS_PATH, content, 10_000))

        if agent_id == "db-runtime" and DBA_CLOUD_REGISTRY_PATH in all_paths:
            registry = await read_memory_document(DBA_CLOUD_REGISTRY_PATH)
            content = registry.get("content", "")
            if isinstance(content, str) and content.strip():
                selected_docs.append((DBA_CLOUD_REGISTRY_PATH, content, 9_500))

        agent_paths = [
            path for path in all_paths if any(path.startswith(root) for root in agent_roots)
        ]
        fallback_paths = [
            path
            for path in all_paths
            if path.startswith("/memories/agents/")
            and not any(path.startswith(root) for root in agent_roots)
        ]

        async def load_ranked(paths: list[str]) -> list[tuple[str, str, int]]:
            ranked: list[tuple[str, str, int]] = []
            for path in paths:
                document = await read_memory_document(path)
                content = document.get("content", "")
                if not isinstance(content, str) or not content.strip():
                    continue
                score = _score_memory_document(path, content, keywords)
                ranked.append((path, content, score))
            ranked.sort(key=lambda item: (item[2], item[0]), reverse=True)
            return ranked

        ranked_agent_docs = await load_ranked(agent_paths)
        matched_agent_docs = [item for item in ranked_agent_docs if item[2] > 0]

        if matched_agent_docs:
            selected_docs.extend(matched_agent_docs[:MEMORY_MATCH_LIMIT])
        else:
            selected_docs.extend(ranked_agent_docs[:1])
            ranked_fallback_docs = await load_ranked(fallback_paths)
            selected_docs.extend(
                [item for item in ranked_fallback_docs if item[2] > 0][
                    : max(0, MEMORY_MATCH_LIMIT - len(selected_docs))
                ]
            )

        deduped_docs: list[tuple[str, str, int]] = []
        seen_paths: set[str] = set()
        for path, content, score in selected_docs:
            if path in seen_paths:
                continue
            seen_paths.add(path)
            deduped_docs.append((path, content, score))

        if not deduped_docs:
            return None

        matched_keywords_text = "、".join(keywords) if keywords else "无明确关键词"
        sections = [
            "以下是本轮请求可用的长期记忆摘要，来自 `/memories/`。",
            f"- 当前 agent: `{agent_id}`",
            f"- 当前消息命中关键词: {matched_keywords_text}",
            "- 如果摘要里已经包含实例 ID、区域、环境或别名映射，不要再次向用户重复索取这些信息。",
            "- 如果摘要里出现多个候选实例，先让用户在候选之间做确认，不要直接要求用户重新提供实例 ID。",
        ]

        for path, content, _score in deduped_docs:
            sections.append(f"\n### {path}\n{_build_memory_excerpt(content)}")

        return "\n".join(sections)
    except Exception as exc:
        logger.warning(f"Failed to build memory context for agent {agent_id}: {exc}")
        return None


async def _build_attachment_context(conv_id: str) -> str | None:
    if not conv_id:
        return None

    try:
        from services.conversation_attachments import build_attachment_context

        return await build_attachment_context(conv_id)
    except Exception as exc:
        logger.warning(f"Failed to build attachment context for conversation {conv_id}: {exc}")
        return None


async def _build_rag_context(
    user_message: str,
    conv_id: str,
    agent_id: str,
) -> str | None:
    try:
        from services.rag import build_rag_context

        return await build_rag_context(
            user_message,
            conversation_id=conv_id or None,
            agent_id=agent_id,
        )
    except Exception as exc:
        logger.warning(f"Failed to build RAG context for conversation {conv_id}: {exc}")
        return None


async def _build_image_attachment_blocks(
    conv_id: str,
    agent_id: str,
    *,
    attachment_records: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    if not conv_id or not should_attach_multimodal_images(agent_id):
        return []

    try:
        from services.conversation_attachments import build_image_attachment_blocks

        attachments = attachment_records
        if attachments is None:
            from services.conversation_attachments import list_conversation_attachments

            attachments = await list_conversation_attachments(conv_id)
        return build_image_attachment_blocks(conv_id, attachments)
    except Exception as exc:
        logger.warning(
            f"Failed to build image attachment blocks for conversation {conv_id}: {exc}"
        )
        return []


async def _build_multimodal_context(
    conv_id: str,
    agent_id: str,
    *,
    attachment_records: list[dict[str, Any]] | None = None,
) -> str | None:
    if not conv_id:
        return None

    try:
        from services.conversation_attachments import is_image_attachment_record

        attachments = attachment_records
        if attachments is None:
            from services.conversation_attachments import list_conversation_attachments

            attachments = await list_conversation_attachments(conv_id)
        has_image_attachments = any(
            is_image_attachment_record(attachment) for attachment in attachments
        )
        return build_multimodal_capability_context(
            agent_id=agent_id,
            has_image_attachments=has_image_attachments,
            api_key_configured=bool(ANTHROPIC_API_KEY),
        )
    except Exception as exc:
        logger.warning(
            f"Failed to build multimodal context for conversation {conv_id}: {exc}"
        )
        return None


def _compose_user_message_with_contexts(
    user_message: str,
    memory_context: str | None,
    attachment_context: str | None,
    multimodal_context: str | None,
    *,
    rag_context: str | None = None,
) -> str:
    if (
        not rag_context
        and not memory_context
        and not attachment_context
        and not multimodal_context
    ):
        return user_message

    sections: list[str] = []
    if rag_context:
        sections.append(
            "<rag_context>\n"
            f"{rag_context}\n"
            "</rag_context>"
        )
    if memory_context:
        sections.append(
            "<memory_context>\n"
            f"{memory_context}\n"
            "</memory_context>"
        )
    if attachment_context:
        sections.append(
            "<attachment_context>\n"
            f"{attachment_context}\n"
            "</attachment_context>"
        )
    if multimodal_context:
        sections.append(
            "<multimodal_context>\n"
            f"{multimodal_context}\n"
            "</multimodal_context>"
        )

    sections.append(
        "以上是本轮请求可复用的上下文；长期记忆里已有的实例、区域、环境或别名映射优先复用，"
        "如需基于附件分析，先读取相关附件内容再给出结论。"
    )
    sections.append(user_message)
    return "\n\n".join(sections)


def _build_human_message_content(
    composed_user_message: str,
    image_blocks: list[dict[str, Any]] | None = None,
    *,
    allow_image_blocks: bool = True,
) -> str | list[dict[str, Any]]:
    if not allow_image_blocks or not image_blocks:
        return composed_user_message

    return [{"type": "text", "text": composed_user_message}, *image_blocks]


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

    if normalized_path.startswith(REPORT_MEMORY_PREFIX) and normalized_path.endswith(
        REPORT_EXTENSIONS
    ):
        return ARTIFACT_KIND_REPORT
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
    attachment_records: list[dict[str, Any]] | None = None,
    allow_image_blocks: bool = True,
    emit_done: bool = True,
) -> AgentEventSnapshot | None:
    """使用 deepagents (LangGraph) 运行指定 Agent，并处理流式事件。"""
    resolved_agent_id = canonicalize_agent_id(agent_id)
    runtime = await get_runtime(resolved_agent_id)
    event_state = AgentEventState()

    async def emit(event: dict[str, Any]) -> None:
        event_state.apply_event(event)
        await on_event(event)

    rag_context = await _build_rag_context(user_message, conv_id, resolved_agent_id)
    memory_context = None
    attachment_context = None
    if rag_context is None:
        memory_context = await _build_memory_context(user_message, resolved_agent_id)
        attachment_context = await _build_attachment_context(conv_id)
    multimodal_context = await _build_multimodal_context(
        conv_id,
        resolved_agent_id,
        attachment_records=attachment_records,
    )
    image_blocks = await _build_image_attachment_blocks(
        conv_id,
        resolved_agent_id,
        attachment_records=attachment_records,
    )
    composed_user_message = _compose_user_message_with_contexts(
        user_message,
        memory_context,
        attachment_context,
        multimodal_context,
        rag_context=rag_context,
    )
    messages: list[Any] = [
        HumanMessage(
            content=_build_human_message_content(
                composed_user_message,
                image_blocks,
                allow_image_blocks=allow_image_blocks
                and should_attach_multimodal_images(resolved_agent_id),
            )
        )
    ]
    inputs = {"messages": messages}
    pending_tool_inputs: dict[str, deque[dict[str, Any]]] = defaultdict(deque)

    try:
        config = {
            "configurable": {"thread_id": conv_id},
            "recursion_limit": MAX_TURNS * 20,
        }
        event_agent_id = resolved_agent_id
        async for event in runtime.astream_events(inputs, config=config, version="v2"):
            kind = event["event"]
            name = event.get("name", "")
            event_agent_id = resolve_event_agent_id(event, resolved_agent_id)

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
                                        await emit(
                                            {
                                                "type": EVENT_THINKING_DELTA,
                                                "content": thinking_text,
                                                "agent_id": event_agent_id,
                                            }
                                        )
                            elif isinstance(block, str):
                                text_delta += block

                    if text_delta:
                        await emit(
                            {
                                "type": EVENT_TEXT_DELTA,
                                "content": text_delta,
                                "agent_id": event_agent_id,
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
                    memory_path = ""
                    if isinstance(tool_input, dict):
                        raw_path = (
                            tool_input.get("path")
                            or tool_input.get("file_path")
                            or tool_input.get("pattern")
                        )
                        if isinstance(raw_path, str):
                            memory_path = raw_path
                    tool_desc = (
                        "正在检索长期记忆..."
                        if memory_path.startswith("/memories/")
                        else "正在检索项目文件..."
                    )
                elif name in ["write_file", "edit_file", "write_todos"]:
                    tool_desc = "正在修改本地代码/文件..."

                await emit(
                    {
                        "type": EVENT_TOOL_CALL,
                        "tool_name": name,
                        "tool_desc": tool_desc,
                        "tool_input": tool_input,
                        "agent_id": event_agent_id,
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

                await emit(
                    {
                        "type": EVENT_TOOL_RESULT,
                        "tool_name": name,
                        "result": result_text[:2000]
                        + ("\n...[截断]" if len(result_text) > 2000 else ""),
                        "tool_input": tool_input,
                        "artifact_kind": artifact_kind,
                        "agent_id": event_agent_id,
                    }
                )

        if emit_done:
            await emit({"type": EVENT_DONE, "agent_id": event_agent_id})
        return event_state.snapshot()

    except Exception as exc:
        logger.exception(f"Agent 执行异常: {exc}")
        await emit(
            {
                "type": EVENT_ERROR,
                "content": f"Agent 执行出错: {str(exc)}",
                "agent_id": resolved_agent_id,
            }
        )
        return event_state.snapshot()


def _build_ocr_stage_message(user_message: str) -> str:
    return (
        "OCR preprocessing stage: extract text from current-turn image attachments "
        "and preserve original order.\n\n"
        f"User request: {user_message}"
    )


def _build_downstream_message(
    user_message: str,
    *,
    ocr_text: str,
    ocr_path: str | None,
) -> str:
    ocr_result_body = (ocr_text or "").strip() or "(empty)"
    path_line = f"\nOCR result path: {ocr_path}" if ocr_path else ""
    return (
        f"{user_message}\n\n"
        "<ocr_preprocess_result>\n"
        "OCR preprocessing has completed for this turn."
        f"{path_line}\n\n"
        f"{ocr_result_body}\n"
        "</ocr_preprocess_result>"
    )


def _resolve_snapshot(
    maybe_snapshot: AgentEventSnapshot | None,
    event_state: AgentEventState,
) -> AgentEventSnapshot:
    if isinstance(maybe_snapshot, AgentEventSnapshot):
        return maybe_snapshot
    return event_state.snapshot()


async def run_agent_turn(
    user_message: str,
    conv_id: str,
    on_event: Callable[[dict[str, Any]], Awaitable[None]],
    agent_id: str | None = None,
    attachment_records: list[dict[str, Any]] | None = None,
) -> AgentEventSnapshot:
    resolved_agent_id = canonicalize_agent_id(agent_id)
    current_turn_attachments = list(attachment_records or [])
    preprocess_plan = resolve_message_preprocess_plan(
        user_message=user_message,
        agent_id=resolved_agent_id,
        attachments=current_turn_attachments,
        api_key_configured=bool(ANTHROPIC_API_KEY),
    )
    if preprocess_plan is None:
        passthrough_state = AgentEventState()

        async def on_passthrough_event(event: dict[str, Any]) -> None:
            passthrough_state.apply_event(event)
            await on_event(event)

        passthrough_result = await run_agent(
            user_message=user_message,
            conv_id=conv_id,
            on_event=on_passthrough_event,
            agent_id=resolved_agent_id,
            attachment_records=current_turn_attachments,
        )
        return _resolve_snapshot(passthrough_result, passthrough_state)

    if preprocess_plan.blocked_reason:
        await on_event(
            {
                "type": EVENT_OCR_STATUS,
                "status": "failed",
                "content": preprocess_plan.blocked_reason,
                "agent_id": "ocr",
            }
        )
        await on_event(
            {
                "type": EVENT_ERROR,
                "content": preprocess_plan.blocked_reason,
                "agent_id": "ocr",
            }
        )
        return AgentEventSnapshot(text="", thinking="", tool_results=[])

    await on_event(
        {
            "type": EVENT_OCR_STATUS,
            "status": "processing",
            "content": (
                f"OCR preprocessing is analyzing {max(1, len(preprocess_plan.image_attachments))} "
                "image attachment(s)..."
            ),
            "agent_id": "ocr",
        }
    )
    ocr_event_state = AgentEventState()
    ocr_error_message: str | None = None

    async def on_ocr_event(event: dict[str, Any]) -> None:
        nonlocal ocr_error_message
        ocr_event_state.apply_event(event)
        if event.get("type") == EVENT_ERROR:
            ocr_error_message = (
                str(event.get("content", "")).strip() or "OCR preprocessing failed."
            )

    ocr_result = await run_agent(
        user_message=_build_ocr_stage_message(user_message),
        conv_id=conv_id,
        on_event=on_ocr_event,
        agent_id="ocr",
        attachment_records=list(preprocess_plan.image_attachments),
        allow_image_blocks=True,
        emit_done=False,
    )
    if ocr_error_message:
        await on_event(
            {
                "type": EVENT_ERROR,
                "content": ocr_error_message,
                "agent_id": "ocr",
            }
        )
        return AgentEventSnapshot(text="", thinking="", tool_results=[])
    ocr_snapshot = _resolve_snapshot(ocr_result, ocr_event_state)
    ocr_text = ocr_snapshot.text.strip()
    ocr_path = (
        save_ocr_result(
            conv_id,
            list(preprocess_plan.image_attachments),
            ocr_text,
        )
        if conv_id
        else None
    )
    await on_event(
        {
            "type": EVENT_OCR_RESULT,
            "content": ocr_text or "(empty)",
            "agent_id": "ocr",
            "ocr_path": ocr_path,
        }
    )

    downstream_state = AgentEventState()

    async def on_downstream_event(event: dict[str, Any]) -> None:
        downstream_state.apply_event(event)
        await on_event(event)

    downstream_result = await run_agent(
        user_message=_build_downstream_message(
            user_message,
            ocr_text=ocr_text,
            ocr_path=ocr_path,
        ),
        conv_id=conv_id,
        on_event=on_downstream_event,
        agent_id=preprocess_plan.downstream_agent_id,
        attachment_records=[],
        allow_image_blocks=False,
    )
    return _resolve_snapshot(downstream_result, downstream_state)
