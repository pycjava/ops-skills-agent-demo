from typing import Literal

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from auth.dependencies import require_permission
from services.rag import get_rag_service


router = APIRouter(prefix="/api/rag", tags=["rag"])


class RagSearchRequest(BaseModel):
    query: str = Field(..., description="Search query")
    conversation_id: str | None = Field(None, description="Conversation scope")
    agent_id: str | None = Field(None, description="Agent scope")
    limit: int | None = Field(None, ge=1, le=20, description="Result limit")


class RagReindexRequest(BaseModel):
    scope: Literal["all", "memories", "conversation_attachments"] = Field(
        ...,
        description="Reindex scope",
    )
    conversation_id: str | None = Field(None, description="Optional attachment scope")
    agent_id: str | None = Field(None, description="Optional memory scope")


@router.get("/status", dependencies=[Depends(require_permission("conversations:read"))])
async def get_rag_status():
    return JSONResponse(await get_rag_service().status())


@router.post("/search", dependencies=[Depends(require_permission("conversations:read"))])
async def search_rag(body: RagSearchRequest):
    items = await get_rag_service().search(
        body.query,
        conversation_id=body.conversation_id,
        agent_id=body.agent_id,
        limit=body.limit,
    )
    return JSONResponse({"items": items})


@router.post("/reindex", dependencies=[Depends(require_permission("conversations:write"))])
async def reindex_rag(body: RagReindexRequest):
    result = await get_rag_service().reindex(
        scope=body.scope,
        conversation_id=body.conversation_id,
        agent_id=body.agent_id,
    )
    return JSONResponse(result)
