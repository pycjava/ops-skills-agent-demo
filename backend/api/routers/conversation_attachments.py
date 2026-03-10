from fastapi import APIRouter, File, Form, UploadFile
from fastapi.responses import JSONResponse

from db.session import AsyncSessionLocal
from services.conversation_attachments import (
    create_attachment_record,
    delete_conversation_attachment,
    list_conversation_attachments,
    validate_attachment_upload,
)
from services.conversation_state import create_conversation, get_conversation


router = APIRouter(prefix="/api/conversations", tags=["conversation-attachments"])


@router.post("/attachments")
async def upload_conversation_attachment(
    file: UploadFile = File(...),
    conversation_id: str | None = Form(default=None),
    agent_id: str | None = Form(default=None),
):
    content_bytes = await file.read()
    validate_attachment_upload(
        original_name=file.filename or "",
        content_bytes=content_bytes,
        mime_type=file.content_type,
    )

    async with AsyncSessionLocal() as session:
        if conversation_id:
            conversation = await get_conversation(session, conversation_id)
            if conversation is None:
                return JSONResponse({"detail": "Conversation not found"}, status_code=404)
        else:
            conversation = await create_conversation(
                session,
                source="web",
                agent_id=agent_id,
            )

    attachment = await create_attachment_record(
        conversation.id,
        original_name=file.filename or "",
        content_bytes=content_bytes,
        mime_type=file.content_type,
        session_factory=AsyncSessionLocal,
    )

    return JSONResponse(
        {
            "conversation": conversation.to_dict(),
            "attachment": attachment.to_dict(),
        }
    )


@router.get("/{conv_id}/attachments")
async def get_conversation_attachments(conv_id: str):
    attachments = await list_conversation_attachments(
        conv_id,
        session_factory=AsyncSessionLocal,
    )
    return JSONResponse([attachment.to_dict() for attachment in attachments])


@router.delete("/{conv_id}/attachments/{attachment_id}")
async def remove_conversation_attachment(conv_id: str, attachment_id: str):
    await delete_conversation_attachment(
        conv_id,
        attachment_id,
        session_factory=AsyncSessionLocal,
    )
    return JSONResponse({"ok": True})
