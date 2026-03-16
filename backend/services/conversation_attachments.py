from __future__ import annotations

import base64
import re
import uuid
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from fastapi import HTTPException
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from config import BASE_DIR
from db.session import AsyncSessionLocal
from models import Conversation, ConversationAttachment


ATTACHMENTS_ROOT = (BASE_DIR / "data" / "conversation_attachments").resolve()
TEXT_ATTACHMENT_EXTENSIONS = frozenset(
    {".txt", ".md", ".markdown", ".csv", ".json", ".sql", ".log"}
)
IMAGE_ATTACHMENT_EXTENSIONS = frozenset({".png", ".jpg", ".jpeg", ".webp"})
ALLOWED_ATTACHMENT_EXTENSIONS = frozenset(
    {*TEXT_ATTACHMENT_EXTENSIONS, *IMAGE_ATTACHMENT_EXTENSIONS}
)
ATTACHMENT_MIME_TYPE_BY_EXTENSION = {
    ".txt": "text/plain",
    ".md": "text/markdown",
    ".markdown": "text/markdown",
    ".csv": "text/csv",
    ".json": "application/json",
    ".sql": "application/sql",
    ".log": "text/plain",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
}
TEXT_DECODING_CANDIDATES = ("utf-8", "utf-8-sig", "gb18030")
MAX_ATTACHMENT_SIZE_BYTES = 1024 * 1024
MAX_CONVERSATION_ATTACHMENTS = 50
OCR_RESULT_DIRNAME = "_ocr"

SessionFactory = async_sessionmaker[AsyncSession]


def _attachment_name_parts(filename: str) -> tuple[str, str]:
    candidate = Path(str(filename or "").strip()).name
    if not candidate:
        raise HTTPException(status_code=400, detail="Attachment filename is required")

    suffix = Path(candidate).suffix.lower()
    if suffix not in ALLOWED_ATTACHMENT_EXTENSIONS:
        raise HTTPException(status_code=400, detail="Unsupported attachment type")

    return candidate, suffix


def _normalize_attachment_name(filename: str) -> tuple[str, str]:
    candidate, _ = _attachment_name_parts(filename)

    stem = re.sub(r"[^A-Za-z0-9._-]+", "-", Path(candidate).stem).strip("-.")
    if not stem:
        stem = "attachment"

    stored_name = f"{stem}-{uuid.uuid4().hex[:8]}{Path(candidate).suffix.lower()}"
    return candidate, stored_name


def _infer_mime_type(filename: str) -> str:
    _, suffix = _attachment_name_parts(filename)
    return ATTACHMENT_MIME_TYPE_BY_EXTENSION.get(suffix, "text/plain")


def _normalize_mime_type(original_name: str, mime_type: str | None) -> str:
    normalized = (mime_type or "").strip().lower()
    if normalized:
        normalized = normalized.split(";", 1)[0].strip()

    if normalized.count("/") == 1:
        major, minor = normalized.split("/", 1)
        if major and minor and not any(ch.isspace() for ch in normalized):
            return normalized

    return _infer_mime_type(original_name)


def is_image_attachment(*, original_name: str, mime_type: str | None = None) -> bool:
    _, suffix = _attachment_name_parts(original_name)
    normalized_mime_type = _normalize_mime_type(original_name, mime_type)
    return suffix in IMAGE_ATTACHMENT_EXTENSIONS or normalized_mime_type.startswith("image/")


def is_image_attachment_record(attachment: ConversationAttachment | dict[str, Any]) -> bool:
    original_name = str(getattr(attachment, "original_name", None) or attachment.get("original_name") or "")
    mime_type = getattr(attachment, "mime_type", None) or attachment.get("mime_type")
    if not original_name:
        return False
    return is_image_attachment(original_name=original_name, mime_type=mime_type)


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


def _ocr_directory(conversation_id: str) -> Path:
    return _attachment_directory(conversation_id) / OCR_RESULT_DIRNAME


def _write_attachment_file(
    stored_file_path: Path,
    *,
    original_name: str,
    mime_type: str,
    content_bytes: bytes,
) -> None:
    if is_image_attachment(original_name=original_name, mime_type=mime_type):
        stored_file_path.write_bytes(content_bytes)
        return

    decoded_content = _decode_attachment_content(content_bytes)
    stored_file_path.write_text(decoded_content, encoding="utf-8")


def validate_attachment_upload(
    *,
    original_name: str,
    content_bytes: bytes,
    mime_type: str | None,
) -> None:
    if len(content_bytes) > MAX_ATTACHMENT_SIZE_BYTES:
        raise HTTPException(status_code=400, detail="Attachment is too large")

    _attachment_name_parts(original_name)
    normalized_mime_type = _normalize_mime_type(original_name, mime_type)
    if is_image_attachment(original_name=original_name, mime_type=normalized_mime_type):
        return

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
    normalized_mime_type = _normalize_mime_type(normalized_name, mime_type)

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
        _write_attachment_file(
            stored_file_path,
            original_name=normalized_name,
            mime_type=normalized_mime_type,
            content_bytes=content_bytes,
        )

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


async def build_attachment_snapshot(
    conversation_id: str,
    attachment_ids: list[str] | tuple[str, ...] | None,
    *,
    session_factory: SessionFactory = AsyncSessionLocal,
) -> list[dict]:
    normalized_ids = [str(attachment_id).strip() for attachment_id in attachment_ids or []]
    ordered_ids = [attachment_id for attachment_id in normalized_ids if attachment_id]
    if not ordered_ids:
        return []

    async with session_factory() as session:
        result = await session.execute(
            select(ConversationAttachment).where(
                ConversationAttachment.conversation_id == conversation_id,
                ConversationAttachment.id.in_(ordered_ids),
            )
        )
        attachments = {
            attachment.id: attachment.to_dict()
            for attachment in result.scalars().all()
        }

    return [
        attachments[attachment_id]
        for attachment_id in ordered_ids
        if attachment_id in attachments
    ]


def save_ocr_result(
    conversation_id: str,
    source_attachments: Sequence[ConversationAttachment | dict[str, Any]],
    content: str,
) -> str:
    ocr_dir = _ocr_directory(conversation_id)
    ocr_dir.mkdir(parents=True, exist_ok=True)
    stored_name = f"ocr-{uuid.uuid4().hex[:8]}.md"
    relative_path = (
        Path("data")
        / "conversation_attachments"
        / conversation_id
        / OCR_RESULT_DIRNAME
        / stored_name
    ).as_posix()

    source_names = [
        str(getattr(attachment, "original_name", None) or attachment.get("original_name") or "").strip()
        for attachment in source_attachments
    ]
    source_names = [name for name in source_names if name]

    lines = ["# OCR Result", ""]
    if source_names:
        lines.append("## Source Attachments")
        lines.extend(f"- {name}" for name in source_names)
        lines.append("")
    lines.append("## Extracted Text")
    lines.append("")
    lines.append((content or "").strip() or "(empty)")

    (ocr_dir / stored_name).write_text("\n".join(lines).strip() + "\n", encoding="utf-8")
    return relative_path


def list_saved_ocr_results(conversation_id: str) -> list[str]:
    ocr_dir = _ocr_directory(conversation_id)
    if not ocr_dir.exists():
        return []

    return sorted(
        (
            (
                Path("data")
                / "conversation_attachments"
                / conversation_id
                / OCR_RESULT_DIRNAME
                / path.name
            ).as_posix()
            for path in ocr_dir.glob("*.md")
            if path.is_file()
        )
    )


def build_image_attachment_blocks(
    conversation_id: str,
    attachments: Sequence[ConversationAttachment | dict[str, Any]],
) -> list[dict[str, Any]]:
    blocks: list[dict[str, Any]] = []

    for attachment in attachments:
        original_name = str(
            getattr(attachment, "original_name", None) or attachment.get("original_name") or ""
        )
        mime_type = str(
            getattr(attachment, "mime_type", None) or attachment.get("mime_type") or ""
        )
        stored_name = str(
            getattr(attachment, "stored_name", None) or attachment.get("stored_name") or ""
        )
        if not stored_name or not is_image_attachment(
            original_name=original_name,
            mime_type=mime_type,
        ):
            continue

        stored_file_path = (_attachment_directory(conversation_id) / stored_name).resolve()
        if not stored_file_path.is_file():
            continue

        blocks.append(
            {
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": _normalize_mime_type(original_name, mime_type),
                    "data": base64.b64encode(stored_file_path.read_bytes()).decode("ascii"),
                },
            }
        )

    return blocks


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

    has_image_attachments = False
    for attachment in attachments:
        if is_image_attachment(
            original_name=attachment.original_name,
            mime_type=attachment.mime_type,
        ):
            has_image_attachments = True
            lines.append(
                "- "
                f"`{attachment.original_name}` | "
                "type: 图片附件 | "
                f"path: `{attachment.relative_path}` | "
                f"mime: `{attachment.mime_type}` | "
                f"size: {attachment.size_bytes} bytes"
            )
            continue

        lines.append(
            "- "
            f"`{attachment.original_name}` | "
            "type: 文本附件 | "
            f"path: `{attachment.relative_path}` | "
            f"mime: `{attachment.mime_type}` | "
            f"size: {attachment.size_bytes} bytes"
        )

    if has_image_attachments:
        lines.append(
            "- 图片附件不能直接按文本读取；需要识别其中内容时，优先调用 OCR agent。"
        )

    saved_ocr_results = list_saved_ocr_results(conversation_id)
    if saved_ocr_results:
        lines.append("- 已保存的 OCR 结果如下，后续分析优先复用这些结果：")
        for result_path in saved_ocr_results:
            lines.append(f"- OCR result: `{result_path}`")

    return "\n".join(lines)
