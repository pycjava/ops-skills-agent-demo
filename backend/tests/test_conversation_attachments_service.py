from models import Conversation
from services.conversation_attachments import (
    build_attachment_context,
    create_attachment_record,
)


async def test_build_attachment_context_lists_all_session_attachments(
    session_factory, tmp_path, monkeypatch
):
    async with session_factory() as session:
        conversation = Conversation(source="web", agent_id="general")
        session.add(conversation)
        await session.commit()
        await session.refresh(conversation)

    monkeypatch.setattr(
        "services.conversation_attachments.ATTACHMENTS_ROOT",
        tmp_path,
    )

    await create_attachment_record(
        conversation.id,
        original_name="sample.log",
        content_bytes=b"line-1\nline-2\n",
        mime_type="text/plain",
        session_factory=session_factory,
    )
    await create_attachment_record(
        conversation.id,
        original_name="query.sql",
        content_bytes=b"select 1;",
        mime_type="text/plain",
        session_factory=session_factory,
    )

    context = await build_attachment_context(
        conversation.id,
        session_factory=session_factory,
    )

    assert context is not None
    assert "<attachment_context>" not in context
    assert "sample.log" in context
    assert "query.sql" in context
    assert f"data/conversation_attachments/{conversation.id}/" in context


async def test_create_attachment_record_infers_mime_type_when_missing(
    session_factory, tmp_path, monkeypatch
):
    async with session_factory() as session:
        conversation = Conversation(source="web", agent_id="general")
        session.add(conversation)
        await session.commit()
        await session.refresh(conversation)

    monkeypatch.setattr(
        "services.conversation_attachments.ATTACHMENTS_ROOT",
        tmp_path,
    )

    attachment = await create_attachment_record(
        conversation.id,
        original_name="payload.json",
        content_bytes=b'{"ok": true}\n',
        mime_type=None,
        session_factory=session_factory,
    )

    assert attachment.mime_type == "application/json"
