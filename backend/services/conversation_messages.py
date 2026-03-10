from __future__ import annotations

from collections.abc import Callable

from sqlalchemy import func, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from db.session import AsyncSessionLocal
from models import Conversation, Message
from utils.logger import logger


TITLE_MAX_LENGTH = 200
AUTO_TITLE_PREVIEW_LENGTH = 30

SessionFactory = async_sessionmaker[AsyncSession]


def normalize_conversation_title(title: str) -> str:
    normalized = str(title or "").strip()
    if not normalized:
        raise ValueError("title is required")
    if len(normalized) > TITLE_MAX_LENGTH:
        raise ValueError(f"title must be at most {TITLE_MAX_LENGTH} characters")
    return normalized


def build_auto_title(first_message: str) -> str:
    normalized = str(first_message or "").replace("\n", " ").strip()
    if not normalized:
        return "新对话"
    preview = normalized[:AUTO_TITLE_PREVIEW_LENGTH]
    if len(normalized) > AUTO_TITLE_PREVIEW_LENGTH:
        preview += "..."
    return preview


async def save_message(
    conv_id: str,
    role: str,
    content: str,
    msg_type: str = "text",
    *,
    tool_name: str | None = None,
    tool_input: dict | None = None,
    attachments_snapshot: list[dict] | None = None,
    thinking: str | None = None,
    agent_id: str | None = None,
    session_factory: SessionFactory = AsyncSessionLocal,
) -> Message:
    async with session_factory() as session:
        message = Message(
            conversation_id=conv_id,
            role=role,
            content=content,
            type=msg_type,
            agent_id=agent_id,
            tool_name=tool_name,
            tool_input=tool_input,
            attachments_snapshot=attachments_snapshot,
            thinking=thinking,
        )
        session.add(message)
        await session.execute(
            update(Conversation)
            .where(Conversation.id == conv_id)
            .values(updated_at=func.now())
        )
        await session.commit()
        await session.refresh(message)
        logger.debug(
            f"已保存消息到对话 {conv_id} (role={role}, type={msg_type}, agent_id={agent_id})"
        )
        return message


async def auto_title(
    conv_id: str,
    first_message: str,
    *,
    session_factory: SessionFactory = AsyncSessionLocal,
) -> str:
    title = build_auto_title(first_message)
    async with session_factory() as session:
        await session.execute(
            update(Conversation).where(Conversation.id == conv_id).values(title=title)
        )
        await session.commit()
    logger.info(f"已为对话 {conv_id} 自动生成标题: {title}")
    return title


async def update_conversation_title(
    conv_id: str,
    title: str,
    *,
    session_factory: SessionFactory = AsyncSessionLocal,
) -> Conversation:
    normalized_title = normalize_conversation_title(title)

    async with session_factory() as session:
        conversation = await session.get(Conversation, conv_id)
        if conversation is None:
            raise LookupError("会话不存在")

        conversation.title = normalized_title
        await session.commit()
        await session.refresh(conversation)

    logger.info(f"已更新对话标题 {conv_id}: {normalized_title}")
    return conversation
