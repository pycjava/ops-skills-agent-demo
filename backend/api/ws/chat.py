import asyncio
import json
from collections.abc import Mapping, Sequence
from datetime import date, datetime, time
from pathlib import Path
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from sqlalchemy import select

from agent import resolve_default_agent, run_agent
from auth.config import get_auth_settings
from auth.dependencies import ensure_websocket_permission
from config import ANTHROPIC_API_KEY
from db.session import AsyncSessionLocal
from models import Message
from services.agent_event_state import AgentEventState
from services.conversation_attachments import (
    build_attachment_snapshot,
    is_image_attachment_record,
    save_ocr_result,
)
from services.multimodal_ocr import resolve_ocr_availability
from services.conversation_messages import (
    auto_title,
    is_default_conversation_title,
    save_message,
)
from services.realtime_events import realtime_event_manager
from services.conversation_state import (
    create_conversation,
    get_conversation,
    get_conversation_agent_id,
    resolve_agent_id,
)
from utils.credential_safety import (
    cloud_credentials_rejection_message,
    contains_plaintext_cloud_credentials,
)
from utils.logger import logger


router = APIRouter(prefix="/ws", tags=["websocket"])


SUBAGENT_LABELS = {
    "router": "智能编排助手",
    "supervisor": "复杂任务协调器",
    "general": "通用助手",
    "dba": "数据库助手",
    "ops": "运维助手",
    "general-purpose": "通用助手",
}


SUBAGENT_LABELS.update(
    {
        "router": "智能编排助手",
        "supervisor": "复杂任务协调器",
        "general": "通用助手",
        "general-purpose": "通用助手",
        "backend": "后端工程助手",
        "frontend": "前端工程助手",
        "db-schema": "数据库设计助手",
        "db-runtime": "数据库运行态助手",
        "dba": "数据库运行态助手",
        "ops-runtime": "运行时运维助手",
        "ops": "运行时运维助手",
        "platform": "平台交付助手",
        "security": "安全与权限助手",
        "dev": "后端工程助手",
        "ui": "前端工程助手",
        "sec": "安全与权限助手",
    }
)


def _should_suppress_normalized_event(normalized_event: dict) -> bool:
    tool_name = normalized_event.get("tool_name")
    tool_input = normalized_event.get("tool_input")
    return (
        normalized_event.get("type") == "tool_result"
        and tool_name == "task"
        and isinstance(tool_input, dict)
        and tool_input.get("subagent_type") == "ocr"
    )


def _build_ocr_status_payload(
    current_turn_attachments: list[dict],
) -> tuple[dict[str, str], bool]:
    image_count = len(
        [
            attachment
            for attachment in current_turn_attachments
            if is_image_attachment_record(attachment)
        ]
    )
    available, reason = resolve_ocr_availability(
        has_image_attachments=image_count > 0,
        api_key_configured=bool(ANTHROPIC_API_KEY),
    )
    payload = {
        "type": "ocr_status",
        "status": "processing" if available else "failed",
        "content": (
            f"OCR is analyzing {max(1, image_count)} image attachment(s)..."
            if available
            else str(reason or "OCR is unavailable.")
        ),
        "agent_id": "ocr",
    }
    return payload, not available


def _json_safe_value(value: Any, *, depth: int = 0, max_depth: int = 5) -> Any:
    if depth >= max_depth:
        return str(value)

    if value is None or isinstance(value, bool | int | float | str):
        return value

    if isinstance(value, datetime | date | time | Path):
        return str(value.isoformat() if hasattr(value, "isoformat") else value)

    if isinstance(value, bytes | bytearray | memoryview):
        return bytes(value).decode("utf-8", errors="replace")

    if isinstance(value, Mapping):
        return {
            str(key): _json_safe_value(item, depth=depth + 1, max_depth=max_depth)
            for key, item in value.items()
        }

    if isinstance(value, Sequence) and not isinstance(
        value, str | bytes | bytearray | memoryview
    ):
        return [
            _json_safe_value(item, depth=depth + 1, max_depth=max_depth)
            for item in value
        ]

    model_dump = getattr(value, "model_dump", None)
    if callable(model_dump):
        try:
            return _json_safe_value(
                model_dump(), depth=depth + 1, max_depth=max_depth
            )
        except Exception:
            return str(value)

    dict_method = getattr(value, "dict", None)
    if callable(dict_method):
        try:
            return _json_safe_value(
                dict_method(), depth=depth + 1, max_depth=max_depth
            )
        except Exception:
            return str(value)

    return str(value)


def _json_safe_dict(value: Any) -> dict[str, Any] | None:
    safe_value = _json_safe_value(value)
    return safe_value if isinstance(safe_value, dict) else None


def _dump_ws_payload(payload: Mapping[str, Any]) -> str:
    return json.dumps(_json_safe_value(dict(payload)), ensure_ascii=False)


@router.websocket("/chat")
async def websocket_chat(ws: WebSocket):
    if get_auth_settings().enabled:
        if await ensure_websocket_permission(ws, "conversations:write") is None:
            return
    await ws.accept()
    await realtime_event_manager.register(ws)
    logger.info("WebSocket 客户端已连接")
    current_conv_id: str | None = None
    current_agent_id = resolve_default_agent()
    agent_task: asyncio.Task | None = None

    abort_event = asyncio.Event()
    event_state = AgentEventState()
    delta_buffer = ""
    flush_task: asyncio.Task | None = None
    current_turn_attachments: list[dict] = []
    suppress_ocr_tool_result = False

    async def flush_delta():
        nonlocal delta_buffer
        if delta_buffer:
            chunk = delta_buffer
            delta_buffer = ""
            await ws.send_text(
                _dump_ws_payload(
                    {
                        "type": "text_delta",
                        "content": chunk,
                        "agent_id": current_agent_id,
                    }
                )
            )

    async def self_flush_after(delay: float):
        await asyncio.sleep(delay)
        await flush_delta()

    async def on_event(event: dict):
        nonlocal delta_buffer, flush_task, current_agent_id, suppress_ocr_tool_result

        if abort_event.is_set():
            raise asyncio.CancelledError("用户中断")

        normalized_event = event_state.apply_event(event)
        etype = normalized_event.get("type")
        event_agent_id = event.get("agent_id") or current_agent_id
        current_agent_id = event_agent_id

        if etype == "text_delta":
            delta_buffer += normalized_event.get("content", "")
            if flush_task is None or flush_task.done():
                flush_task = asyncio.create_task(self_flush_after(0.08))
            return

        if etype == "thinking_delta":
            await ws.send_text(_dump_ws_payload(normalized_event))
            return

        if delta_buffer:
            await flush_delta()
            if flush_task and not flush_task.done():
                flush_task.cancel()

        if not _should_suppress_normalized_event(normalized_event):
            await ws.send_text(_dump_ws_payload(normalized_event))

        if etype == "tool_call":
            tool_name = normalized_event.get("tool_name", "")
            tool_input = _json_safe_dict(normalized_event.get("tool_input")) or {}
            desc = normalized_event.get(
                "tool_desc", f"执行 Tool: {tool_name}"
            )

            if tool_name == "task":
                subagent_type = tool_input.get("subagent_type", "unknown") if tool_input else "unknown"
                subagent_label = SUBAGENT_LABELS.get(subagent_type, subagent_type)
                source_agent_label = SUBAGENT_LABELS.get(event_agent_id, event_agent_id)
                if subagent_type == "ocr":
                    image_count = len(
                        [
                            attachment
                            for attachment in current_turn_attachments
                            if is_image_attachment_record(attachment)
                        ]
                    )
                    available, reason = resolve_ocr_availability(
                        has_image_attachments=image_count > 0,
                        api_key_configured=bool(ANTHROPIC_API_KEY),
                    )
                    suppress_ocr_tool_result = not available
                    if available:
                        await ws.send_text(
                        _dump_ws_payload(
                            {
                                "type": "ocr_status",
                                "status": "processing",
                                "content": f"OCR 正在分析 {max(1, image_count)} 张图片附件…",
                                "agent_id": "ocr",
                            },
                        )
                    )
                    else:
                        await ws.send_text(
                            _dump_ws_payload(
                                {
                                    "type": "ocr_status",
                                    "status": "failed",
                                    "content": reason,
                                    "agent_id": "ocr",
                                },
                            )
                        )
                await ws.send_text(
                    _dump_ws_payload(
                        {
                            "type": "routing",
                            "subagent_type": subagent_type,
                            "subagent_label": subagent_label,
                            "source_agent_id": event_agent_id,
                            "source_agent_label": source_agent_label,
                            "agent_id": event_agent_id,
                        },
                    )
                )

            await save_message(
                current_conv_id,
                "system",
                desc,
                "tool_call",
                agent_id=event_agent_id,
                tool_name=tool_name,
                tool_input=tool_input,
                thinking=event_state.pop_step_thinking(),
            )
        elif etype == "tool_result":
            tool_name = normalized_event.get("tool_name")
            tool_input = _json_safe_dict(normalized_event.get("tool_input"))
            if (
                tool_name == "task"
                and isinstance(tool_input, dict)
                and tool_input.get("subagent_type") == "ocr"
            ):
                if suppress_ocr_tool_result:
                    suppress_ocr_tool_result = False
                    await save_message(
                        current_conv_id,
                        "system",
                        normalized_event.get("result", ""),
                        "tool_result",
                        agent_id=event_agent_id,
                        tool_name=tool_name,
                        tool_input=tool_input,
                    )
                    return

                image_attachments = [
                    attachment
                    for attachment in current_turn_attachments
                    if is_image_attachment_record(attachment)
                ]
                ocr_result_path = (
                    save_ocr_result(
                        current_conv_id,
                        image_attachments,
                        normalized_event.get("result", ""),
                    )
                    if current_conv_id and image_attachments
                    else None
                )
                ocr_message = "OCR 已完成，结果已加入会话上下文。"
                if ocr_result_path:
                    ocr_message += f"\n\nSaved OCR result: `{ocr_result_path}`"
                ocr_message += f"\n\n{normalized_event.get('result', '')}"

                await ws.send_text(
                    _dump_ws_payload(
                        {
                            "type": "ocr_result",
                            "content": ocr_message,
                            "agent_id": "ocr",
                            "ocr_path": ocr_result_path,
                        },
                    )
                )
                await save_message(
                    current_conv_id,
                    "system",
                    ocr_message,
                    "text",
                    agent_id="ocr",
                )

            await save_message(
                current_conv_id,
                "system",
                normalized_event.get("result", ""),
                "tool_result",
                agent_id=event_agent_id,
                tool_name=tool_name,
                tool_input=tool_input,
            )
            suppress_ocr_tool_result = False
        elif etype == "error":
            logger.error(f"Agent 报错事件: {normalized_event.get('content')}")
            if event_agent_id == "ocr":
                await ws.send_text(
                    _dump_ws_payload(
                        {
                            "type": "ocr_status",
                            "status": "failed",
                            "content": "OCR 分析失败，请稍后重试。",
                            "agent_id": "ocr",
                        },
                    )
                )
            await save_message(
                current_conv_id,
                "system",
                normalized_event.get("content", ""),
                "error",
                agent_id=event_agent_id,
            )
        elif etype == "done":
            snapshot = event_state.snapshot()
            if snapshot.text:
                await save_message(
                    current_conv_id,
                    "assistant",
                    snapshot.text,
                    "text",
                    agent_id=event_agent_id,
                    thinking=snapshot.thinking or None,
                )

    async def do_abort():
        nonlocal agent_task
        if agent_task and not agent_task.done():
            agent_task.cancel()
            try:
                await agent_task
            except (asyncio.CancelledError, Exception):
                pass

        if delta_buffer:
            try:
                await flush_delta()
            except Exception:
                pass

        snapshot = event_state.snapshot()
        if snapshot.text and current_conv_id:
            partial = snapshot.text + "\n\n> ⚠️ *（回答被用户中断）*"
            await save_message(
                current_conv_id,
                "assistant",
                partial,
                "text",
                agent_id=current_agent_id,
                thinking=snapshot.thinking or None,
            )

        try:
            await ws.send_text(
                _dump_ws_payload(
                    {"type": "done", "agent_id": current_agent_id},
                )
            )
        except Exception:
            pass
        await realtime_event_manager.unregister(ws)

        agent_task = None
        logger.info(f"对话 {current_conv_id} 已被用户中断")

    try:
        while True:
            if agent_task and not agent_task.done():
                recv_task = asyncio.create_task(ws.receive_text())
                done_set, _ = await asyncio.wait(
                    {agent_task, recv_task},
                    return_when=asyncio.FIRST_COMPLETED,
                )

                if recv_task in done_set:
                    raw = recv_task.result()
                else:
                    recv_task.cancel()
                    try:
                        await recv_task
                    except (asyncio.CancelledError, Exception):
                        pass
                    if agent_task.done() and not agent_task.cancelled():
                        exc = agent_task.exception()
                        if exc:
                            logger.exception(f"Agent Task 异常: {exc}")
                    agent_task = None
                    continue
            else:
                raw = await ws.receive_text()

            data = json.loads(raw)
            msg_type = data.get("type", "message")
            logger.debug(f"收到 WS 消息类型: {msg_type}")

            if msg_type == "abort":
                abort_event.set()
                await do_abort()
                continue

            if msg_type == "init":
                conv_id = data.get("conversation_id")

                async with AsyncSessionLocal() as session:
                    if conv_id:
                        conversation = await get_conversation(session, conv_id)
                        if conversation:
                            current_conv_id = conv_id
                            current_agent_id = get_conversation_agent_id(conversation)
                            logger.info(
                                f"已绑定到现有对话 {conv_id}, agent_id={current_agent_id}"
                            )
                        else:
                            try:
                                conversation = await create_conversation(
                                    session,
                                    source="web",
                                    agent_id=data.get("agent_id"),
                                )
                            except ValueError:
                                current_conv_id = None
                                current_agent_id = resolve_default_agent()
                            else:
                                current_conv_id = conversation.id
                                current_agent_id = conversation.agent_id
                                logger.info(
                                    f"未找到对话 {conv_id}，已新建 {conversation.id}, agent_id={current_agent_id}"
                                )
                    else:
                        current_conv_id = None
                        requested_agent_id = data.get("agent_id")
                        try:
                            current_agent_id = resolve_agent_id(requested_agent_id)
                        except ValueError:
                            current_agent_id = resolve_default_agent()
                        logger.info(
                            "客户端 init 未传 conversation_id，等待首条消息创建对话"
                        )

                await ws.send_text(
                    _dump_ws_payload(
                        {
                            "type": "session",
                            "session_id": current_conv_id,
                            "conversation_id": current_conv_id,
                            "agent_id": current_agent_id,
                        },
                    )
                )
                continue

            if msg_type == "clear":
                if current_conv_id:
                    async with AsyncSessionLocal() as session:
                        result = await session.execute(
                            select(Message).where(
                                Message.conversation_id == current_conv_id
                            )
                        )
                        deleted_count = 0
                        for message in result.scalars().all():
                            await session.delete(message)
                            deleted_count += 1
                        await session.commit()
                        logger.info(
                            f"已清空对话 {current_conv_id} 的 {deleted_count} 条消息记录"
                        )
                await ws.send_text(
                    _dump_ws_payload(
                        {"type": "cleared", "agent_id": current_agent_id},
                    )
                )
                continue

            if msg_type == "message":
                content = data.get("content", "")
                requested_agent_id = data.get("agent_id")
                attachment_ids = data.get("attachment_ids")

                if not ANTHROPIC_API_KEY:
                    logger.warning("收到消息，但未配置 ANTHROPIC_API_KEY")
                    await ws.send_text(
                        _dump_ws_payload(
                            {
                                "type": "error",
                                "content": "未配置 ANTHROPIC_API_KEY，请在 backend/.env 文件中设置",
                                "agent_id": current_agent_id,
                            },
                        )
                    )
                    continue

                if not current_conv_id:
                    async with AsyncSessionLocal() as session:
                        try:
                            conversation = await create_conversation(
                                session,
                                source="web",
                                agent_id=requested_agent_id,
                            )
                        except ValueError as exc:
                            await ws.send_text(
                                _dump_ws_payload(
                                    {
                                        "type": "error",
                                        "content": str(exc),
                                        "agent_id": current_agent_id,
                                    },
                                )
                            )
                            continue
                        current_conv_id = conversation.id
                        current_agent_id = conversation.agent_id
                        logger.info(
                            f"收到新消息，已自动新建对话 {conversation.id}, agent_id={current_agent_id}"
                        )
                    await ws.send_text(
                        _dump_ws_payload(
                            {
                                "type": "session",
                                "session_id": current_conv_id,
                                "conversation_id": current_conv_id,
                                "agent_id": current_agent_id,
                            },
                        )
                    )

                if current_agent_id == "db-runtime" and contains_plaintext_cloud_credentials(
                    content
                ):
                    await ws.send_text(
                        _dump_ws_payload(
                            {
                                "type": "error",
                                "content": cloud_credentials_rejection_message(),
                                "agent_id": current_agent_id,
                            },
                        )
                    )
                    continue

                attachments_snapshot = await build_attachment_snapshot(
                    current_conv_id,
                    attachment_ids if isinstance(attachment_ids, list) else [],
                    session_factory=AsyncSessionLocal,
                )
                current_turn_attachments = attachments_snapshot or []

                await save_message(
                    current_conv_id,
                    "user",
                    content,
                    "text",
                    agent_id=current_agent_id,
                    attachments_snapshot=attachments_snapshot or None,
                )

                async with AsyncSessionLocal() as session:
                    conversation = await get_conversation(session, current_conv_id)
                    if conversation and is_default_conversation_title(conversation.title):
                        title = await auto_title(current_conv_id, content)
                        await ws.send_text(
                            _dump_ws_payload(
                                {
                                    "type": "title_update",
                                    "conversation_id": current_conv_id,
                                    "title": title,
                                    "agent_id": current_agent_id,
                                },
                            )
                        )

                event_state = AgentEventState()
                delta_buffer = ""
                abort_event.clear()

                logger.info(
                    f"正在为对话 {current_conv_id} 启动 Agent, agent_id={current_agent_id}"
                )
                agent_task = asyncio.create_task(
                    run_agent(
                        user_message=content,
                        conv_id=current_conv_id,
                        on_event=on_event,
                        agent_id=current_agent_id,
                    )
                )

    except WebSocketDisconnect:
        logger.info("WebSocket 客户端已正常断开连接")
        if agent_task and not agent_task.done():
            agent_task.cancel()
        await realtime_event_manager.unregister(ws)
    except Exception as exc:
        logger.exception(f"WebSocket 异常错误: {exc}")
        if agent_task and not agent_task.done():
            agent_task.cancel()
        try:
            await ws.send_text(
                _dump_ws_payload(
                    {
                        "type": "error",
                        "content": f"服务器错误: {str(exc)}",
                        "agent_id": current_agent_id,
                    },
                )
            )
        except Exception:
            pass
        await realtime_event_manager.unregister(ws)
