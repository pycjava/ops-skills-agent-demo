from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from agent_profiles import DEFAULT_AGENT_ID, canonicalize_agent_id, get_agent_profile
from models import Conversation
from services.conversation_messages import DEFAULT_CONVERSATION_TITLE


def resolve_agent_id(agent_id: str | None) -> str:
    candidate = canonicalize_agent_id(agent_id)
    get_agent_profile(candidate)
    return candidate


def get_conversation_agent_id(conversation: Conversation) -> str:
    candidate = canonicalize_agent_id(conversation.agent_id)
    try:
        get_agent_profile(candidate)
    except ValueError:
        return DEFAULT_AGENT_ID
    return candidate


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
    title: str | None = None,
    source_task_id: str | None = None,
    source_task_run_id: str | None = None,
    source_task_trigger_type: str | None = None,
) -> Conversation:
    resolved_agent_id = resolve_agent_id(agent_id)
    conversation = Conversation(
        title=(title or "").strip() or DEFAULT_CONVERSATION_TITLE,
        source=source,
        agent_id=resolved_agent_id,
        source_task_id=source_task_id,
        source_task_run_id=source_task_run_id,
        source_task_trigger_type=source_task_trigger_type,
    )
    session.add(conversation)
    await session.commit()
    await session.refresh(conversation)
    return conversation

