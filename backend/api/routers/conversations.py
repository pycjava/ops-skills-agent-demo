from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy import func, select

from db.session import AsyncSessionLocal
from models import Conversation, Message
from services.conversation_state import create_conversation
from utils.logger import logger

router = APIRouter(prefix="/api/conversations", tags=["conversations"])


class CreateConversationRequest(BaseModel):
    agent_id: str | None = None


@router.get("")
async def list_conversations(q: str | None = None):
    """获取所有会话列表，按更新时间倒序。支持 ?q=关键词 按标题模糊搜索"""
    logger.info(f"正在获取对话列表, 搜索关键词: {q}")
    async with AsyncSessionLocal() as session:
        stmt = select(Conversation)
        if q and q.strip():
            keyword = f"%{q.strip().lower()}%"
            stmt = stmt.where(func.lower(Conversation.title).like(keyword))
        stmt = stmt.order_by(Conversation.updated_at.desc())
        result = await session.execute(stmt)
        conversations = result.scalars().all()
        return JSONResponse([conversation.to_dict() for conversation in conversations])


@router.post("")
async def create_conversation_route(body: CreateConversationRequest | None = None):
    """新建会话"""
    logger.info("正在创建新对话")
    async with AsyncSessionLocal() as session:
        try:
            conversation = await create_conversation(
                session,
                source="web",
                agent_id=body.agent_id if body else None,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return JSONResponse(conversation.to_dict())


@router.get("/{conv_id}/messages")
async def get_messages(conv_id: str):
    """获取某个会话的所有消息"""
    logger.info(f"正在获取对话 {conv_id} 的消息记录")
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(Message)
            .where(Message.conversation_id == conv_id)
            .order_by(Message.created_at)
        )
        messages = result.scalars().all()
        return JSONResponse([message.to_dict() for message in messages])


@router.delete("/{conv_id}")
async def delete_conversation(conv_id: str):
    """删除会话及其所有消息"""
    logger.info(f"正在删除对话 {conv_id}")
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(Conversation).where(Conversation.id == conv_id)
        )
        conversation = result.scalar_one_or_none()
        if not conversation:
            logger.warning(f"要删除的对话 {conv_id} 未找到")
            return JSONResponse({"error": "会话不存在"}, status_code=404)
        await session.delete(conversation)
        await session.commit()
        return JSONResponse({"ok": True})


@router.patch("/{conv_id}")
async def update_conversation(conv_id: str, body: dict = None):
    """更新会话标题"""
    logger.info(f"正在更新对话 {conv_id}，数据: {body}")
    pass

