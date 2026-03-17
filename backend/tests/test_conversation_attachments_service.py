from models import Conversation
from services.conversation_attachments import (
    build_attachment_context,
    create_attachment_record,
    delete_conversation_attachment,
    save_ocr_result,
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


async def test_build_attachment_context_mentions_image_attachments_and_saved_ocr_results(
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

    image_attachment = await create_attachment_record(
        conversation.id,
        original_name="console.png",
        content_bytes=(
            b"\x89PNG\r\n\x1a\n"
            b"\x00\x00\x00\rIHDR"
            b"\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02\x00\x00\x00"
            b"\x90wS\xde"
            b"\x00\x00\x00\nIDATx\x9cc`\x00\x00\x00\x02\x00\x01"
            b"\xe2!\xbc3"
            b"\x00\x00\x00\x00IEND\xaeB`\x82"
        ),
        mime_type="image/png",
        session_factory=session_factory,
    )

    ocr_path = save_ocr_result(
        conversation.id,
        [image_attachment],
        "## OCR Result\n\n- source: console.png\n- text: mysql error 1045",
    )

    context = await build_attachment_context(
        conversation.id,
        session_factory=session_factory,
    )

    assert context is not None
    assert "console.png" in context
    assert "图片附件" in context
    assert "OCR" in context
    assert ocr_path in context


async def test_attachment_lifecycle_syncs_rag_index(
    session_factory,
    tmp_path,
    monkeypatch,
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

    synced_attachment_ids: list[str] = []
    deleted_attachment_ids: list[str] = []

    async def fake_sync_attachment_record(attachment):
        synced_attachment_ids.append(attachment.id)
        return 1

    async def fake_delete_attachment_source(attachment_id: str):
        deleted_attachment_ids.append(attachment_id)
        return 1

    monkeypatch.setattr(
        "services.rag.sync_attachment_record",
        fake_sync_attachment_record,
    )
    monkeypatch.setattr(
        "services.rag.delete_attachment_source",
        fake_delete_attachment_source,
    )

    attachment = await create_attachment_record(
        conversation.id,
        original_name="incident.md",
        content_bytes=b"service outage summary\n",
        mime_type="text/markdown",
        session_factory=session_factory,
    )

    assert synced_attachment_ids == [attachment.id]

    await delete_conversation_attachment(
        conversation.id,
        attachment.id,
        session_factory=session_factory,
    )

    assert deleted_attachment_ids == [attachment.id]
