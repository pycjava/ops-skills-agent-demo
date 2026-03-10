from datetime import datetime

from sqlalchemy import select, update

from models import Conversation, Message
from services.conversation_messages import (
    TITLE_MAX_LENGTH,
    save_message,
    update_conversation_title,
)


async def test_save_message_persists_and_refreshes_conversation_timestamp(
    session_factory, seeded_conversation
):
    old_timestamp = datetime(2000, 1, 1, 0, 0, 0)

    async with session_factory() as session:
        await session.execute(
            update(Conversation)
            .where(Conversation.id == seeded_conversation.id)
            .values(updated_at=old_timestamp)
        )
        await session.commit()

    await save_message(
        seeded_conversation.id,
        "user",
        "hello",
        "text",
        agent_id="general",
        session_factory=session_factory,
    )

    async with session_factory() as session:
        message_result = await session.execute(
            select(Message).where(Message.conversation_id == seeded_conversation.id)
        )
        conversation = await session.get(Conversation, seeded_conversation.id)

    message = message_result.scalar_one()
    assert message.content == "hello"
    assert conversation is not None
    assert conversation.updated_at is not None
    assert conversation.updated_at > old_timestamp


async def test_update_conversation_title_trims_and_persists(
    session_factory, seeded_conversation
):
    updated = await update_conversation_title(
        seeded_conversation.id,
        "  已重命名标题  ",
        session_factory=session_factory,
    )

    assert updated.title == "已重命名标题"

    async with session_factory() as session:
        saved = await session.get(Conversation, seeded_conversation.id)

    assert saved is not None
    assert saved.title == "已重命名标题"


async def test_update_conversation_title_rejects_invalid_values(
    session_factory, seeded_conversation
):
    for invalid_title in ("   ", "a" * (TITLE_MAX_LENGTH + 1)):
        try:
            await update_conversation_title(
                seeded_conversation.id,
                invalid_title,
                session_factory=session_factory,
            )
        except ValueError:
            pass
        else:
            raise AssertionError("expected ValueError for invalid title")

