import asyncio
import json
from datetime import datetime
from typing import Any, AsyncGenerator

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel
from sqlalchemy import select

from auth.dependencies import require_permission
from db.session import AsyncSessionLocal
from models import Conversation, InspectionTaskRun, Message
from services.conversation_state import get_conversation_agent_id
from services.inspection_task_llm import (
    analyze_task_creation_intent,
    summarize_task_template_from_conversation,
)
from services.inspection_tasks import (
    _build_task_intent_analysis,
    _filter_task_summary_messages,
    _is_task_configuration_message_any_language,
    _load_conversation_messages,
    build_inspection_task_draft,
    create_inspection_task,
    create_inspection_task_from_conversation_message,
    delete_inspection_task,
    execute_inspection_task,
    get_inspection_task,
    list_inspection_task_runs,
    list_inspection_tasks,
    update_inspection_task,
)


router = APIRouter(prefix="/api/inspection-tasks", tags=["inspection-tasks"])
_RUN_CONVERSATION_STREAM_POLL_INTERVAL_SECONDS = 0.25


def _sse_event(data: dict) -> str:
    """将字典编码为 SSE data 行。"""
    return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"


async def _load_inspection_task_run_stream_state(
    run_id: str,
    *,
    session_factory=AsyncSessionLocal,
) -> tuple[InspectionTaskRun, Conversation, list[Message]]:
    async with session_factory() as session:
        run = await session.get(InspectionTaskRun, run_id)
        if run is None:
            raise LookupError("inspection task run not found")
        if not run.conversation_id:
            raise ValueError("inspection task run has no conversation")

        conversation = await session.get(Conversation, run.conversation_id)
        if conversation is None:
            raise LookupError("conversation not found")

        result = await session.execute(
            select(Message)
            .where(Message.conversation_id == run.conversation_id)
            .order_by(Message.created_at.asc())
        )
        messages = list(result.scalars().all())

    return run, conversation, messages


def _build_run_status_event(
    run: InspectionTaskRun,
    *,
    conversation_id: str,
) -> dict[str, Any]:
    return {
        "type": "run_status",
        "run_id": run.id,
        "conversation_id": conversation_id,
        "status": run.status,
        "finished_at": (
            run.finished_at.isoformat(timespec="milliseconds")
            if run.finished_at
            else None
        ),
        "error_message": run.error_message,
    }


async def _stream_inspection_task_run_conversation(
    run_id: str,
    *,
    session_factory=AsyncSessionLocal,
    initial_state: tuple[InspectionTaskRun, Conversation, list[Message]] | None = None,
) -> AsyncGenerator[str, None]:
    run, conversation, messages = initial_state or await _load_inspection_task_run_stream_state(
        run_id,
        session_factory=session_factory,
    )
    emitted_message_ids: set[str] = set()
    last_reported_status: str | None = None

    yield _sse_event(
        {
            "type": "history_start",
            "run_id": run.id,
            "conversation_id": conversation.id,
            "agent_id": get_conversation_agent_id(conversation),
            "title": conversation.title,
            "status": run.status,
        }
    )

    for message in messages:
        emitted_message_ids.add(message.id)
        yield _sse_event({"type": "message", "message": message.to_dict()})

    yield _sse_event(
        {
            "type": "history_done",
            "run_id": run.id,
            "conversation_id": conversation.id,
        }
    )

    yield _sse_event(_build_run_status_event(run, conversation_id=conversation.id))
    last_reported_status = run.status

    while run.status == "running":
        await asyncio.sleep(_RUN_CONVERSATION_STREAM_POLL_INTERVAL_SECONDS)
        run, conversation, messages = await _load_inspection_task_run_stream_state(
            run_id,
            session_factory=session_factory,
        )

        for message in messages:
            if message.id in emitted_message_ids:
                continue
            emitted_message_ids.add(message.id)
            yield _sse_event({"type": "message", "message": message.to_dict()})

        if run.status != last_reported_status:
            last_reported_status = run.status
            yield _sse_event(
                _build_run_status_event(run, conversation_id=conversation.id)
            )

    yield _sse_event(
        {
            "type": "done",
            "run_id": run.id,
            "conversation_id": conversation.id,
            "status": run.status,
            "error_message": run.error_message,
        }
    )


class DraftRequest(BaseModel):
    conversation_id: str


class CreateInspectionTaskRequest(BaseModel):
    name: str
    source_conversation_id: str | None = None
    agent_id: str
    skill_id: str | None = None
    prompt_template: str
    target_payload: dict[str, Any] | None = None
    cron_expr: str
    enabled: bool = True
    now: datetime | None = None


class UpdateInspectionTaskRequest(BaseModel):
    name: str | None = None
    skill_id: str | None = None
    prompt_template: str | None = None
    target_payload: dict[str, Any] | None = None
    cron_expr: str | None = None
    enabled: bool | None = None
    now: datetime | None = None


class CreateInspectionTaskFromConversationMessageRequest(BaseModel):
    conversation_id: str
    message: str
    now: datetime | None = None
    previous_context: dict[str, Any] | None = None


@router.post("/draft", dependencies=[Depends(require_permission("inspection_tasks:write"))])
async def create_inspection_task_draft(body: DraftRequest):
    try:
        draft = await build_inspection_task_draft(
            body.conversation_id,
            session_factory=AsyncSessionLocal,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return JSONResponse(draft)


@router.get("", dependencies=[Depends(require_permission("inspection_tasks:read"))])
async def get_inspection_tasks():
    tasks = await list_inspection_tasks(session_factory=AsyncSessionLocal)
    return JSONResponse([task.to_dict() for task in tasks])


@router.post("", dependencies=[Depends(require_permission("inspection_tasks:write"))])
async def create_inspection_task_route(body: CreateInspectionTaskRequest):
    try:
        task = await create_inspection_task(
            name=body.name,
            source_conversation_id=body.source_conversation_id,
            agent_id=body.agent_id,
            skill_id=body.skill_id,
            prompt_template=body.prompt_template,
            target_payload=body.target_payload,
            cron_expr=body.cron_expr,
            enabled=body.enabled,
            now=body.now,
            session_factory=AsyncSessionLocal,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return JSONResponse(task.to_dict())


@router.post(
    "/from-conversation-message",
    dependencies=[Depends(require_permission("inspection_tasks:write"))],
)
async def create_inspection_task_from_conversation_message_route(
    body: CreateInspectionTaskFromConversationMessageRequest,
):
    try:
        result = await create_inspection_task_from_conversation_message(
            body.conversation_id,
            body.message,
            session_factory=AsyncSessionLocal,
            now=body.now,
            previous_context=body.previous_context,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return JSONResponse(result)


@router.post(
    "/from-conversation-message/stream",
    dependencies=[Depends(require_permission("inspection_tasks:write"))],
)
async def create_inspection_task_from_conversation_message_stream_route(
    body: CreateInspectionTaskFromConversationMessageRequest,
):
    """
    以 SSE 流式方式生成定时任务。
    推送 tool_call / tool_result / done / error 事件，和 DeepAgent 对话流风格一致。
    直接创建任务，不需要用户在草稿页确认。
    """

    async def generate() -> AsyncGenerator[str, None]:
        now = body.now
        normalized_message = str(body.message or "").strip()
        if not normalized_message:
            yield _sse_event({"type": "error", "content": "message 不能为空"})
            return

        # Load recent conversation messages for context
        recent_messages: list[tuple[str, str]] = []
        try:
            conversation, messages = await _load_conversation_messages(
                body.conversation_id,
                session_factory=AsyncSessionLocal,
            )
            # Get last 5 messages for context (excluding task configuration messages)
            filtered_for_context = [
                (msg.role, msg.content)
                for msg in messages[-5:]
                if msg.content and msg.role in ("user", "assistant")
                and not _is_task_configuration_message_any_language(msg.content)
            ]
            recent_messages = filtered_for_context
        except Exception:
            # If we can't load conversation, proceed without context
            pass

        # ── Step 1: 意图分析 ──────────────────────────────────────────────
        yield _sse_event({
            "type": "tool_call",
            "tool_name": "inspection_task_intent",
            "tool_desc": "正在执行 Tool: **inspection_task_intent**（定时任务意图分析）",
            "tool_input": {"message": normalized_message},
        })

        try:
            intent = await analyze_task_creation_intent(
                normalized_message,
                recent_messages=recent_messages if recent_messages else None,
                previous_context=body.previous_context,
            )
        except Exception as exc:
            yield _sse_event({"type": "error", "content": f"意图分析失败: {exc}"})
            return

        # 不是任务创建意图，直接结束
        if not intent.is_task_creation:
            yield _sse_event({
                "type": "tool_result",
                "tool_name": "inspection_task_intent",
                "result": "未识别到定时任务创建意图，将作为普通消息处理。",
            })
            yield _sse_event({"type": "done", "status": "not_task_creation"})
            return

        # 识别到意图但无法解析 cron 表达式
        if not intent.cron_expr:
            error_message = (
                intent.error_message
                or "未能从当前这句话中识别完整调度时间，请补充执行频率或具体时间。"
            )
            clarification_prompt = (
                intent.clarification_prompt
                or "您希望这个定时任务在什么时间执行？例如：每天早上9点、每周一上午10点、每月1号凌晨2点等。"
            )
            intent_analysis = _build_task_intent_analysis(
                outcome="error",
                cron_expr=None,
                reason=error_message,
            )
            yield _sse_event({
                "type": "tool_result",
                "tool_name": "inspection_task_intent",
                "result": intent_analysis["summary"],
                "tool_input": {
                    "outcome": "error",
                    "cron_expr": None,
                    "reason": error_message,
                },
            })

            yield _sse_event({
                "type": "clarification_needed",
                "content": clarification_prompt,
                "original_message": normalized_message,
            })

            yield _sse_event({
                "type": "done",
                "status": "clarification_needed",
                "message": error_message,
                "clarification_prompt": clarification_prompt,
                "intent_analysis": intent_analysis,
            })
            return

        # 意图分析成功，有 cron 表达式
        yield _sse_event({
            "type": "tool_result",
            "tool_name": "inspection_task_intent",
            "result": f"已识别调度表达式：{intent.cron_expr}，正在生成任务模板…",
            "tool_input": {
                "outcome": "creating",
                "cron_expr": intent.cron_expr,
            },
        })

        # ── Step 2: 加载对话消息，生成任务摘要 ─────────────────────────────
        yield _sse_event({
            "type": "tool_call",
            "tool_name": "create_inspection_task",
            "tool_desc": "正在执行 Tool: **create_inspection_task**（生成定时任务）",
            "tool_input": {"cron_expr": intent.cron_expr},
        })

        try:
            conversation, messages = await _load_conversation_messages(
                body.conversation_id,
                session_factory=AsyncSessionLocal,
            )
        except LookupError as exc:
            yield _sse_event({
                "type": "tool_result",
                "tool_name": "create_inspection_task",
                "result": f"加载对话失败: {exc}",
            })
            yield _sse_event({"type": "error", "content": str(exc)})
            return

        filtered_messages = _filter_task_summary_messages(messages)
        if not filtered_messages:
            error_msg = "对话中没有可用于生成任务的巡检消息"
            yield _sse_event({
                "type": "tool_result",
                "tool_name": "create_inspection_task",
                "result": error_msg,
            })
            yield _sse_event({"type": "error", "content": error_msg})
            return

        try:
            summary = await summarize_task_template_from_conversation(
                conversation, filtered_messages
            )
        except Exception as exc:
            yield _sse_event({
                "type": "tool_result",
                "tool_name": "create_inspection_task",
                "result": f"任务摘要生成失败: {exc}",
            })
            yield _sse_event({"type": "error", "content": str(exc)})
            return

        # ── Step 3: 创建任务（使用对话的 agent_id 确保正确绑定）─────────────
        try:
            task = await create_inspection_task(
                name=(summary.name or "").strip() or conversation.title,
                source_conversation_id=conversation.id,
                agent_id=get_conversation_agent_id(conversation),
                skill_id=summary.skill_id,
                prompt_template=summary.prompt_template,
                target_payload=summary.target_payload,
                cron_expr=intent.cron_expr,
                enabled=True,
                now=now,
                session_factory=AsyncSessionLocal,
            )
        except ValueError as exc:
            yield _sse_event({
                "type": "tool_result",
                "tool_name": "create_inspection_task",
                "result": f"任务创建失败: {exc}",
            })
            yield _sse_event({"type": "error", "content": str(exc)})
            return

        final_intent_analysis = _build_task_intent_analysis(
            outcome="created",
            cron_expr=intent.cron_expr,
            task_name=task.name,
        )

        yield _sse_event({
            "type": "tool_result",
            "tool_name": "create_inspection_task",
            "result": final_intent_analysis["summary"],
            "tool_input": {
                "task_id": task.id,
                "task_name": task.name,
                "agent_id": task.agent_id,
                "cron_expr": task.cron_expr,
            },
        })

        yield _sse_event({
            "type": "done",
            "status": "created",
            "task": task.to_dict(),
            "intent_analysis": final_intent_analysis,
        })

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@router.get(
    "/runs/{run_id}/conversation/stream",
    dependencies=[Depends(require_permission("inspection_tasks:read"))],
)
async def stream_inspection_task_run_conversation_route(run_id: str):
    try:
        initial_state = await _load_inspection_task_run_stream_state(
            run_id,
            session_factory=AsyncSessionLocal,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return StreamingResponse(
        _stream_inspection_task_run_conversation(
            run_id,
            session_factory=AsyncSessionLocal,
            initial_state=initial_state,
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/{task_id}", dependencies=[Depends(require_permission("inspection_tasks:read"))])
async def get_inspection_task_route(task_id: str):
    try:
        task = await get_inspection_task(task_id, session_factory=AsyncSessionLocal)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return JSONResponse(task.to_dict())


@router.patch("/{task_id}", dependencies=[Depends(require_permission("inspection_tasks:write"))])
async def update_inspection_task_route(task_id: str, body: UpdateInspectionTaskRequest):
    try:
        task = await update_inspection_task(
            task_id,
            name=body.name,
            skill_id=body.skill_id,
            prompt_template=body.prompt_template,
            target_payload=body.target_payload,
            cron_expr=body.cron_expr,
            enabled=body.enabled,
            now=body.now,
            session_factory=AsyncSessionLocal,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return JSONResponse(task.to_dict())


@router.delete("/{task_id}", dependencies=[Depends(require_permission("inspection_tasks:delete"))])
async def delete_inspection_task_route(task_id: str):
    try:
        await delete_inspection_task(task_id, session_factory=AsyncSessionLocal)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return JSONResponse({"status": "deleted", "task_id": task_id})


@router.post(
    "/{task_id}/trigger",
    dependencies=[Depends(require_permission("inspection_tasks:trigger"))],
)
async def trigger_inspection_task(task_id: str):
    try:
        run = await execute_inspection_task(
            task_id,
            trigger_type="manual",
            session_factory=AsyncSessionLocal,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    if hasattr(run, "to_dict"):
        return JSONResponse(run.to_dict())
    return JSONResponse(run)


@router.get(
    "/{task_id}/runs",
    dependencies=[Depends(require_permission("inspection_tasks:read"))],
)
async def get_inspection_task_runs(task_id: str):
    runs = await list_inspection_task_runs(task_id, session_factory=AsyncSessionLocal)
    return JSONResponse([run.to_dict() for run in runs])


@router.get("/runs/all", dependencies=[Depends(require_permission("inspection_tasks:read"))])
async def get_all_inspection_task_runs():
    runs = await list_inspection_task_runs(session_factory=AsyncSessionLocal)
    return JSONResponse([run.to_dict() for run in runs])
