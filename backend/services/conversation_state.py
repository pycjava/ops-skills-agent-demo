from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from agent_profiles import DEFAULT_AGENT_ID, get_agent_profile
from models import Conversation


def resolve_agent_id(agent_id: str | None) -> str:
    candidate = (agent_id or "").strip() or DEFAULT_AGENT_ID
    get_agent_profile(candidate)
    return candidate


def get_conversation_agent_id(conversation: Conversation) -> str:
    return (conversation.agent_id or "").strip() or DEFAULT_AGENT_ID


async def get_conversation(
    session: AsyncSession, conv_id: str
) -> Conversation | None:
    result = await session.execute(
        select(Conversation).where(Conversation.id == conv_id)
    )
    return result.scalar_one_or_none()


async def create_conversation(
    session: AsyncSession,
    *,
    source: str = "web",
    agent_id: str | None = None,
) -> Conversation:
    resolved_agent_id = resolve_agent_id(agent_id)
    conversation = Conversation(source=source, agent_id=resolved_agent_id)
    session.add(conversation)
    await session.commit()
    await session.refresh(conversation)
    return conversation

