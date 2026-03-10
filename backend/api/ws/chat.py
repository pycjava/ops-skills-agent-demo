import asyncio
import json

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from sqlalchemy import select

from agent import resolve_default_agent, run_agent
from config import ANTHROPIC_API_KEY
from db.session import AsyncSessionLocal
from models import Message
from services.agent_event_state import AgentEventState
from services.conversation_attachments import build_attachment_snapshot
from services.conversation_messages import auto_title, save_message
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


@router.websocket("/chat")
async def websocket_chat(ws: WebSocket):
    await ws.accept()
    logger.info("WebSocket 客户端已连接")
    current_conv_id: str | None = None
    current_agent_id = resolve_default_agent()
    agent_task: asyncio.Task | None = None

    abort_event = asyncio.Event()
    event_state = AgentEventState()
    delta_buffer = ""
    flush_task: asyncio.Task | None = None

    async def flush_delta():
        nonlocal delta_buffer
        if delta_buffer:
            chunk = delta_buffer
            delta_buffer = ""
            await ws.send_text(
                json.dumps(
                    {
                        "type": "text_delta",
                        "content": chunk,
                        "agent_id": current_agent_id,
                    },
                    ensure_ascii=False,
                )
            )

    async def self_flush_after(delay: float):
        await asyncio.sleep(delay)
        await flush_delta()

    async def on_event(event: dict):
        nonlocal delta_buffer, flush_task, current_agent_id

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
            await ws.send_text(json.dumps(normalized_event, ensure_ascii=False))
            return

        if delta_buffer:
            await flush_delta()
            if flush_task and not flush_task.done():
                flush_task.cancel()

        await ws.send_text(json.dumps(normalized_event, ensure_ascii=False))

        if etype == "tool_call":
            desc = normalized_event.get(
                "tool_desc", f"执行 Tool: {normalized_event.get('tool_name', '')}"
            )
            await save_message(
                current_conv_id,
                "system",
                desc,
                "tool_call",
                agent_id=event_agent_id,
                tool_name=normalized_event.get("tool_name"),
                tool_input=normalized_event.get("tool_input"),
                thinking=event_state.pop_step_thinking(),
            )
        elif etype == "tool_result":
            await save_message(
                current_conv_id,
                "system",
                normalized_event.get("result", ""),
                "tool_result",
                agent_id=event_agent_id,
                tool_name=normalized_event.get("tool_name"),
                tool_input=normalized_event.get("tool_input"),
            )
        elif etype == "error":
            logger.error(f"Agent 报错事件: {normalized_event.get('content')}")
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
                json.dumps(
                    {"type": "done", "agent_id": current_agent_id},
                    ensure_ascii=False,
                )
            )
        except Exception:
            pass

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
                    json.dumps(
                        {
                            "type": "session",
                            "session_id": current_conv_id,
                            "conversation_id": current_conv_id,
                            "agent_id": current_agent_id,
                        },
                        ensure_ascii=False,
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
                    json.dumps(
                        {"type": "cleared", "agent_id": current_agent_id},
                        ensure_ascii=False,
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
                        json.dumps(
                            {
                                "type": "error",
                                "content": "未配置 ANTHROPIC_API_KEY，请在 backend/.env 文件中设置",
                                "agent_id": current_agent_id,
                            },
                            ensure_ascii=False,
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
                                json.dumps(
                                    {
                                        "type": "error",
                                        "content": str(exc),
                                        "agent_id": current_agent_id,
                                    },
                                    ensure_ascii=False,
                                )
                            )
                            continue
                        current_conv_id = conversation.id
                        current_agent_id = conversation.agent_id
                        logger.info(
                            f"收到新消息，已自动新建对话 {conversation.id}, agent_id={current_agent_id}"
                        )
                    await ws.send_text(
                        json.dumps(
                            {
                                "type": "session",
                                "session_id": current_conv_id,
                                "conversation_id": current_conv_id,
                                "agent_id": current_agent_id,
                            },
                            ensure_ascii=False,
                        )
                    )

                if current_agent_id == "dba" and contains_plaintext_cloud_credentials(
                    content
                ):
                    await ws.send_text(
                        json.dumps(
                            {
                                "type": "error",
                                "content": cloud_credentials_rejection_message(),
                                "agent_id": current_agent_id,
                            },
                            ensure_ascii=False,
                        )
                    )
                    continue

                attachments_snapshot = await build_attachment_snapshot(
                    current_conv_id,
                    attachment_ids if isinstance(attachment_ids, list) else [],
                    session_factory=AsyncSessionLocal,
                )

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
                    if conversation and conversation.title == "新对话":
                        title = await auto_title(current_conv_id, content)
                        await ws.send_text(
                            json.dumps(
                                {
                                    "type": "title_update",
                                    "conversation_id": current_conv_id,
                                    "title": title,
                                    "agent_id": current_agent_id,
                                },
                                ensure_ascii=False,
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
    except Exception as exc:
        logger.exception(f"WebSocket 异常错误: {exc}")
        if agent_task and not agent_task.done():
            agent_task.cancel()
        try:
            await ws.send_text(
                json.dumps(
                    {
                        "type": "error",
                        "content": f"服务器错误: {str(exc)}",
                        "agent_id": current_agent_id,
                    },
                    ensure_ascii=False,
                )
            )
        except Exception:
            pass
