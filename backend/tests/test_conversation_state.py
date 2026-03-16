import pytest

from services.conversation_messages import DEFAULT_CONVERSATION_TITLE
from services.conversation_state import create_conversation, get_conversation_agent_id, resolve_agent_id


async def test_create_conversation_uses_readable_default_title(session_factory):
    async with session_factory() as session:
        conversation = await create_conversation(session)

    assert conversation.title == DEFAULT_CONVERSATION_TITLE


def test_resolve_agent_id_rejects_removed_orchestrator_id():
    with pytest.raises(ValueError, match="agent_id"):
        resolve_agent_id("orchestrator")


class _Conversation:
    def __init__(self, agent_id: str | None):
        self.agent_id = agent_id


def test_get_conversation_agent_id_falls_back_for_removed_legacy_agent():
    assert get_conversation_agent_id(_Conversation("orchestrator")) == "router"
