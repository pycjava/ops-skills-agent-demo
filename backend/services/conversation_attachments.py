from __future__ import annotations

import re
import uuid
from pathlib import Path

from fastapi import HTTPException
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from config import BASE_DIR
from db.session import AsyncSessionLocal
from models import Conversation, ConversationAttachment


ATTACHMENTS_ROOT = (BASE_DIR / "data" / "conversation_attachments").resolve()
ALLOWED_ATTACHMENT_EXTENSIONS = frozenset(
    {".txt", ".md", ".markdown", ".csv", ".json", ".sql", ".log"}
)
ALLOWED_ATTACHMENT_MIME_TYPES = frozenset(
    {
        "text/plain",
        "text/markdown",
        "text/csv",
        "application/json",
        "application/sql",
        "application/x-sql",
    }
)
TEXT_DECODING_CANDIDATES = ("utf-8", "utf-8-sig", "gb18030")
MAX_ATTACHMENT_SIZE_BYTES = 1024 * 1024
MAX_CONVERSATION_ATTACHMENTS = 10

SessionFactory = async_sessionmaker[AsyncSession]


def _normalize_attachment_name(filename: str) -> tuple[str, str]:
    candidate = Path(str(filename or "").strip()).name
    if not candidate:
        raise HTTPException(status_code=400, detail="Attachment filename is required")

    suffix = Path(candidate).suffix.lower()
    if suffix not in ALLOWED_ATTACHMENT_EXTENSIONS:
        raise HTTPException(status_code=400, detail="Unsupported attachment type")

    stem = re.sub(r"[^A-Za-z0-9._-]+", "-", Path(candidate).stem).strip("-.")
    if not stem:
        stem = "attachment"

    stored_name = f"{stem}-{uuid.uuid4().hex[:8]}{suffix}"
    return candidate, stored_name


def _normalize_mime_type(mime_type: str | None) -> str:
    normalized = (mime_type or "").strip().lower()
    if not normalized:
        return "text/plain"
    if normalized.startswith("text/") or normalized in ALLOWED_ATTACHMENT_MIME_TYPES:
        return normalized
    raise HTTPException(status_code=400, detail="Unsupported attachment MIME type")


def _decode_attachment_content(content_bytes: bytes) -> str:
    if not content_bytes:
        return ""

    for encoding in TEXT_DECODING_CANDIDATES:
        try:
            return content_bytes.decode(encoding)
        except UnicodeDecodeError:
            continue

    raise HTTPException(
        status_code=400,
        detail="Attachment content must be a supported text encoding",
    )


def _attachment_directory(conversation_id: str) -> Path:
    return ATTACHMENTS_ROOT / conversation_id


def validate_attachment_upload(
    *,
    original_name: str,
    content_bytes: bytes,
    mime_type: str | None,
) -> None:
    if len(content_bytes) > MAX_ATTACHMENT_SIZE_BYTES:
        raise HTTPException(status_code=400, detail="Attachment is too large")

    _normalize_attachment_name(original_name)
    _normalize_mime_type(mime_type)
    _decode_attachment_content(content_bytes)


async def create_attachment_record(
    conversation_id: str,
    *,
    original_name: str,
    content_bytes: bytes,
    mime_type: str | None,
    session_factory: SessionFactory = AsyncSessionLocal,
) -> ConversationAttachment:
    validate_attachment_upload(
        original_name=original_name,
        content_bytes=content_bytes,
        mime_type=mime_type,
    )
    normalized_name, stored_name = _normalize_attachment_name(original_name)
    normalized_mime_type = _normalize_mime_type(mime_type)
    decoded_content = _decode_attachment_content(content_bytes)

    attachment_dir = _attachment_directory(conversation_id)
    attachment_dir.mkdir(parents=True, exist_ok=True)
    relative_path = (
        Path("data") / "conversation_attachments" / conversation_id / stored_name
    ).as_posix()

    async with session_factory() as session:
        conversation = await session.get(Conversation, conversation_id)
        if conversation is None:
            raise HTTPException(status_code=404, detail="Conversation not found")

        count_result = await session.execute(
            select(func.count(ConversationAttachment.id)).where(
                ConversationAttachment.conversation_id == conversation_id
            )
        )
        attachment_count = int(count_result.scalar() or 0)
        if attachment_count >= MAX_CONVERSATION_ATTACHMENTS:
            raise HTTPException(status_code=400, detail="Too many attachments in conversation")

        stored_file_path = attachment_dir / stored_name
        stored_file_path.write_text(decoded_content, encoding="utf-8")

        attachment = ConversationAttachment(
            conversation_id=conversation_id,
            original_name=normalized_name,
            stored_name=stored_name,
            relative_path=relative_path,
            mime_type=normalized_mime_type,
            size_bytes=len(content_bytes),
        )
        session.add(attachment)
        await session.execute(
            update(Conversation)
            .where(Conversation.id == conversation_id)
            .values(updated_at=func.now())
        )
        await session.commit()
        await session.refresh(attachment)
        return attachment


async def list_conversation_attachments(
    conversation_id: str,
    *,
    session_factory: SessionFactory = AsyncSessionLocal,
) -> list[ConversationAttachment]:
    async with session_factory() as session:
        conversation = await session.get(Conversation, conversation_id)
        if conversation is None:
            raise HTTPException(status_code=404, detail="Conversation not found")

        result = await session.execute(
            select(ConversationAttachment)
            .where(ConversationAttachment.conversation_id == conversation_id)
            .order_by(ConversationAttachment.created_at)
        )
        return list(result.scalars().all())


async def delete_conversation_attachment(
    conversation_id: str,
    attachment_id: str,
    *,
    session_factory: SessionFactory = AsyncSessionLocal,
) -> None:
    async with session_factory() as session:
        result = await session.execute(
            select(ConversationAttachment).where(
                ConversationAttachment.id == attachment_id,
                ConversationAttachment.conversation_id == conversation_id,
            )
        )
        attachment = result.scalar_one_or_none()
        if attachment is None:
            raise HTTPException(status_code=404, detail="Attachment not found")

        stored_file_path = (_attachment_directory(conversation_id) / attachment.stored_name).resolve()
        if stored_file_path.exists():
            stored_file_path.unlink()

        attachment_dir = _attachment_directory(conversation_id)
        if attachment_dir.exists() and not any(attachment_dir.iterdir()):
            attachment_dir.rmdir()

        await session.delete(attachment)
        await session.execute(
            update(Conversation)
            .where(Conversation.id == conversation_id)
            .values(updated_at=func.now())
        )
        await session.commit()


async def delete_all_conversation_attachments(
    conversation_id: str,
    *,
    session_factory: SessionFactory = AsyncSessionLocal,
) -> None:
    attachments = await list_conversation_attachments(
        conversation_id,
        session_factory=session_factory,
    )
    for attachment in attachments:
        await delete_conversation_attachment(
            conversation_id,
            attachment.id,
            session_factory=session_factory,
        )


async def build_attachment_context(
    conversation_id: str,
    *,
    session_factory: SessionFactory = AsyncSessionLocal,
) -> str | None:
    attachments = await list_conversation_attachments(
        conversation_id,
        session_factory=session_factory,
    )
    if not attachments:
        return None

    lines = [
        "以下是当前会话默认可用的附件清单。",
        "- 这些附件会默认参与当前会话后续每一条消息的分析。",
        "- 如果用户要求基于附件分析，先读取相关附件内容，再给出结论。",
        "- 不要只根据文件名猜测附件内容。",
    ]

    for attachment in attachments:
        lines.append(
            "- "
            f"`{attachment.original_name}` | "
            f"path: `{attachment.relative_path}` | "
            f"mime: `{attachment.mime_type}` | "
            f"size: {attachment.size_bytes} bytes"
        )

    return "\n".join(lines)
