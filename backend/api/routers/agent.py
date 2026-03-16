"""HTTP Agent API — 供程序调用的同步 Agent 接口

POST /api/agent/chat
程序发送问题，等待 Agent 完整执行后返回最终结果。
"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from agent import run_agent
from auth.dependencies import require_permission
from config import ANTHROPIC_API_KEY
from db.session import AsyncSessionLocal
from services.agent_event_state import AgentEventState
from services.conversation_messages import save_message
from services.conversation_state import (
    create_conversation,
    get_conversation,
    get_conversation_agent_id,
)
from utils.credential_safety import (
    cloud_credentials_rejection_message,
    contains_plaintext_cloud_credentials,
)
from utils.logger import logger


router = APIRouter(prefix="/api/agent", tags=["agent"])


class ChatRequest(BaseModel):
    message: str = Field(..., description="用户问题")
    conversation_id: str | None = Field(None, description="会话 ID，传入可继续上下文")
    skill: str | None = Field(
        None, description="指定使用的 Skill 名称，如 mysql-sql-analyzer"
    )
    agent_id: str | None = Field(None, description="指定目标 Agent，如 dba / ops")


class ToolCallRecord(BaseModel):
    tool_name: str
    tool_input: dict | None = None
    artifact_kind: str | None = None
    result: str = ""


class ChatResponse(BaseModel):
    conversation_id: str
    agent_id: str
    content: str = Field("", description="Agent 最终回复文本")
    thinking: str = Field("", description="Agent 思考过程")
    tool_calls: list[ToolCallRecord] = Field(
        default_factory=list, description="工具调用记录"
    )


@router.post(
    "/chat",
    response_model=ChatResponse,
    dependencies=[Depends(require_permission("conversations:write"))],
)
async def agent_chat(req: ChatRequest):
    """
    同步调用 Agent，等待完整执行后返回最终结果。

    适用于程序集成 — 告警系统、CI/CD、运维脚本等。
    """
    if not ANTHROPIC_API_KEY:
        raise HTTPException(status_code=503, detail="未配置 ANTHROPIC_API_KEY")

    conv_id = req.conversation_id
    resolved_agent_id = req.agent_id

    async with AsyncSessionLocal() as session:
        if conv_id:
            conversation = await get_conversation(session, conv_id)
            if conversation is None:
                raise HTTPException(status_code=404, detail="会话不存在")
            resolved_agent_id = get_conversation_agent_id(conversation)
        else:
            try:
                conversation = await create_conversation(
                    session,
                    source="api",
                    agent_id=req.agent_id,
                )
            except ValueError as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from exc
            conv_id = conversation.id
            resolved_agent_id = conversation.agent_id
            logger.info(
                f"[HTTP API] 新建对话 {conv_id}, agent_id={resolved_agent_id}"
            )

    user_message = req.message
    if req.skill:
        user_message = f"@{req.skill} {user_message}"

    if resolved_agent_id == "db-runtime" and contains_plaintext_cloud_credentials(
        user_message
    ):
        raise HTTPException(status_code=400, detail=cloud_credentials_rejection_message())

    await save_message(
        conv_id,
        "user",
        user_message,
        "text",
        agent_id=resolved_agent_id,
    )

    event_state = AgentEventState()
    tool_calls: list[ToolCallRecord] = []

    async def on_event(event: dict):
        normalized_event = event_state.apply_event(event)
        etype = normalized_event.get("type")
        tool_name = normalized_event.get("tool_name", "")
        event_agent_id = event.get("agent_id") or resolved_agent_id

        if etype == "text_delta":
            return

        elif etype == "thinking_delta":
            return

        elif etype == "tool_call":
            return

        elif etype == "tool_result":
            tool_calls.append(
                ToolCallRecord(
                    tool_name=tool_name,
                    tool_input=normalized_event.get("tool_input")
                    if isinstance(normalized_event.get("tool_input"), dict)
                    else None,
                    artifact_kind=normalized_event.get("artifact_kind"),
                    result=normalized_event.get("result", ""),
                )
            )
            await save_message(
                conv_id,
                "system",
                normalized_event.get("result", ""),
                "tool_result",
                agent_id=event_agent_id,
                tool_name=tool_name,
                tool_input=normalized_event.get("tool_input")
                if isinstance(normalized_event.get("tool_input"), dict)
                else None,
            )

        elif etype == "error":
            raise HTTPException(
                status_code=500, detail=normalized_event.get("content", "Agent 执行出错")
            )

        elif etype == "done":
            snapshot = event_state.snapshot()
            if snapshot.text:
                await save_message(
                    conv_id,
                    "assistant",
                    snapshot.text,
                    "text",
                    agent_id=event_agent_id,
                    thinking=snapshot.thinking or None,
                )

    logger.info(
        f"[HTTP API] 对话 {conv_id} 开始执行 Agent, agent_id={resolved_agent_id}"
    )
    await run_agent(
        user_message=user_message,
        conv_id=conv_id,
        on_event=on_event,
        agent_id=resolved_agent_id,
    )

    return ChatResponse(
        conversation_id=conv_id,
        agent_id=resolved_agent_id or "",
        content=event_state.snapshot().text,
        thinking=event_state.snapshot().thinking,
        tool_calls=tool_calls,
    )
