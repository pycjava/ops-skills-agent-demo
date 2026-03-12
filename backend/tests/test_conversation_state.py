from services.conversation_messages import DEFAULT_CONVERSATION_TITLE
from services.conversation_state import create_conversation


async def test_create_conversation_uses_readable_default_title(session_factory):
    async with session_factory() as session:
        conversation = await create_conversation(session)

    assert conversation.title == DEFAULT_CONVERSATION_TITLE
