import asyncio
import json
from collections import defaultdict, deque

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from sqlalchemy import func, select, update

from agent import resolve_default_agent, run_agent
from config import ANTHROPIC_API_KEY
from db.session import AsyncSessionLocal
from models import Conversation, Message
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


async def save_message(
    conv_id: str,
    role: str,
    content: str,
    msg_type: str = "text",
    tool_name: str | None = None,
    tool_input: dict | None = None,
    thinking: str | None = None,
    agent_id: str | None = None,
):
    """保存消息到数据库"""
    async with AsyncSessionLocal() as session:
        msg = Message(
            conversation_id=conv_id,
            role=role,
            content=content,
            type=msg_type,
            agent_id=agent_id,
            tool_name=tool_name,
            tool_input=tool_input,
            thinking=thinking,
        )
        session.add(msg)
        await session.execute(
            update(Conversation)
            .where(Conversation.id == conv_id)
            .values(updated_at=func.now())
        )
        await session.commit()
        logger.debug(
            f"已保存消息到对话 {conv_id} (role={role}, type={msg_type}, agent_id={agent_id})"
        )
        return msg


async def auto_title(conv_id: str, first_message: str):
    """用第一条消息的前 30 个字符作为会话标题"""
    title = first_message[:30].replace("\n", " ")
    if len(first_message) > 30:
        title += "..."
    async with AsyncSessionLocal() as session:
        await session.execute(
            update(Conversation).where(Conversation.id == conv_id).values(title=title)
        )
        await session.commit()
    logger.info(f"已为对话 {conv_id} 自动生成标题: {title}")


@router.websocket("/chat")
async def websocket_chat(ws: WebSocket):
    await ws.accept()
    logger.info("WebSocket 客户端已连接")
    current_conv_id: str | None = None
    current_agent_id = resolve_default_agent()
    agent_task: asyncio.Task | None = None

    abort_event = asyncio.Event()
    streaming_text = ""
    streaming_thinking = ""
    step_thinking = ""
    delta_buffer = ""
    flush_task: asyncio.Task | None = None
    pending_tool_inputs: dict[str, deque[dict]] = defaultdict(deque)

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
        nonlocal streaming_text, streaming_thinking, delta_buffer, flush_task
        nonlocal step_thinking, current_agent_id

        if abort_event.is_set():
            raise asyncio.CancelledError("用户中断")

        etype = event.get("type")
        tool_name = event.get("tool_name")
        event_agent_id = event.get("agent_id") or current_agent_id
        current_agent_id = event_agent_id

        if etype == "text_delta":
            streaming_text += event.get("content", "")
            delta_buffer += event.get("content", "")
            if flush_task is None or flush_task.done():
                flush_task = asyncio.create_task(self_flush_after(0.08))
            return

        if etype == "thinking_delta":
            streaming_thinking += event.get("content", "")
            step_thinking += event.get("content", "")
            await ws.send_text(json.dumps(event, ensure_ascii=False))
            return

        if delta_buffer:
            await flush_delta()
            if flush_task and not flush_task.done():
                flush_task.cancel()

        if etype == "tool_call":
            tool_input = event.get("tool_input")
            if tool_name and isinstance(tool_input, dict):
                pending_tool_inputs[tool_name].append(tool_input)
        elif etype == "tool_result" and tool_name:
            tool_input = event.get("tool_input")
            queued_inputs = pending_tool_inputs.get(tool_name)
            if isinstance(tool_input, dict):
                if queued_inputs:
                    queued_inputs.popleft()
                    if not queued_inputs:
                        pending_tool_inputs.pop(tool_name, None)
            elif queued_inputs:
                event["tool_input"] = queued_inputs.popleft()
                if not queued_inputs:
                    pending_tool_inputs.pop(tool_name, None)

        await ws.send_text(json.dumps(event, ensure_ascii=False))

        if etype == "tool_call":
            desc = event.get("tool_desc", f"执行 Tool: {event.get('tool_name', '')}")
            await save_message(
                current_conv_id,
                "system",
                desc,
                "tool_call",
                agent_id=event_agent_id,
                tool_name=event.get("tool_name"),
                tool_input=event.get("tool_input"),
                thinking=step_thinking or None,
            )
            step_thinking = ""
        elif etype == "tool_result":
            await save_message(
                current_conv_id,
                "system",
                event.get("result", ""),
                "tool_result",
                agent_id=event_agent_id,
                tool_name=event.get("tool_name"),
                tool_input=event.get("tool_input"),
            )
        elif etype == "error":
            logger.error(f"Agent 报错事件: {event.get('content')}")
            await save_message(
                current_conv_id,
                "system",
                event.get("content", ""),
                "error",
                agent_id=event_agent_id,
            )
        elif etype == "done":
            if streaming_text:
                await save_message(
                    current_conv_id,
                    "assistant",
                    streaming_text,
                    "text",
                    agent_id=event_agent_id,
                    thinking=step_thinking or None,
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

        if streaming_text and current_conv_id:
            partial = streaming_text + "\n\n> ⚠️ *（回答被用户中断）*"
            await save_message(
                current_conv_id,
                "assistant",
                partial,
                "text",
                agent_id=current_agent_id,
                thinking=streaming_thinking or None,
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

                await save_message(
                    current_conv_id,
                    "user",
                    content,
                    "text",
                    agent_id=current_agent_id,
                )

                async with AsyncSessionLocal() as session:
                    conversation = await get_conversation(session, current_conv_id)
                    if conversation and conversation.title == "新对话":
                        await auto_title(current_conv_id, content)
                        await ws.send_text(
                            json.dumps(
                                {
                                    "type": "title_update",
                                    "conversation_id": current_conv_id,
                                    "title": content[:30]
                                    + ("..." if len(content) > 30 else ""),
                                    "agent_id": current_agent_id,
                                },
                                ensure_ascii=False,
                            )
                        )

                streaming_text = ""
                streaming_thinking = ""
                step_thinking = ""
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
