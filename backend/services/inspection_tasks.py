from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Awaitable, Callable

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from agent import run_agent
from services.agent_event_state import AgentEventState
from services.conversation_messages import save_message
from services.conversation_state import create_conversation, get_conversation, resolve_agent_id
from db.session import AsyncSessionLocal
from models import Conversation, InspectionTask, InspectionTaskRun, Message


SessionFactory = async_sessionmaker[AsyncSession]
AgentRunner = Callable[..., Awaitable[None]]

TASK_NAME_MAX_LENGTH = 200


def _normalize_task_name(name: str) -> str:
    normalized = str(name or "").strip()
    if not normalized:
        raise ValueError("name is required")
    if len(normalized) > TASK_NAME_MAX_LENGTH:
        raise ValueError(f"name must be at most {TASK_NAME_MAX_LENGTH} characters")
    return normalized


def _normalize_cron_expr(cron_expr: str) -> str:
    normalized = str(cron_expr or "").strip()
    parts = normalized.split()
    if len(parts) != 5:
        raise ValueError("cron_expr must contain 5 fields")

    for index, part in enumerate(parts):
        _parse_cron_field(part, index)

    return normalized


def _parse_cron_field(field: str, index: int) -> set[int]:
    limits = ((0, 59), (0, 23), (1, 31), (1, 12), (0, 6))
    minimum, maximum = limits[index]
    normalized = field.strip()

    if normalized == "*":
        return set(range(minimum, maximum + 1))

    if normalized.startswith("*/"):
        step_text = normalized[2:]
        if not step_text.isdigit():
            raise ValueError(f"invalid cron field: {field}")
        step = int(step_text)
        if step <= 0:
            raise ValueError(f"invalid cron step: {field}")
        return set(range(minimum, maximum + 1, step))

    values: set[int] = set()
    for chunk in normalized.split(","):
        candidate = chunk.strip()
        if not candidate.isdigit():
            raise ValueError(f"invalid cron field: {field}")
        value = int(candidate)
        if value < minimum or value > maximum:
            raise ValueError(f"cron value out of range: {field}")
        values.add(value)

    if not values:
        raise ValueError(f"invalid cron field: {field}")
    return values


def next_cron_run_at(cron_expr: str, after: datetime) -> datetime:
    normalized = _normalize_cron_expr(cron_expr)
    minute_values, hour_values, dom_values, month_values, dow_values = (
        _parse_cron_field(part, index)
        for index, part in enumerate(normalized.split())
    )

    candidate = after.replace(second=0, microsecond=0) + timedelta(minutes=1)
    for _ in range(366 * 24 * 60):
        python_weekday = candidate.weekday()
        cron_weekday = (python_weekday + 1) % 7
        if (
            candidate.minute in minute_values
            and candidate.hour in hour_values
            and candidate.day in dom_values
            and candidate.month in month_values
            and cron_weekday in dow_values
        ):
            return candidate
        candidate += timedelta(minutes=1)

    raise ValueError("unable to resolve next cron run within one year")


async def build_inspection_task_draft(
    conversation_id: str,
    *,
    session_factory: SessionFactory = AsyncSessionLocal,
) -> dict[str, Any]:
    async with session_factory() as session:
        conversation = await get_conversation(session, conversation_id)
        if conversation is None:
            raise LookupError("conversation not found")

        result = await session.execute(
            select(Message)
            .where(
                Message.conversation_id == conversation_id,
                Message.role == "user",
                Message.type == "text",
            )
            .order_by(Message.created_at.desc())
        )
        latest_user_message = result.scalars().first()

    if latest_user_message is None:
        raise LookupError("conversation has no user message to template")

    return {
        "source_conversation_id": conversation.id,
        "name": conversation.title,
        "agent_id": conversation.agent_id,
        "skill_id": None,
        "prompt_template": latest_user_message.content,
        "target_payload": None,
        "schedule_type": "cron",
        "cron_expr": "0 9 * * *",
        "enabled": True,
    }


async def create_inspection_task(
    *,
    name: str,
    source_conversation_id: str | None = None,
    agent_id: str,
    skill_id: str | None,
    prompt_template: str,
    target_payload: dict[str, Any] | None,
    cron_expr: str,
    enabled: bool,
    now: datetime | None = None,
    session_factory: SessionFactory = AsyncSessionLocal,
) -> InspectionTask:
    normalized_name = _normalize_task_name(name)
    resolved_agent_id = resolve_agent_id(agent_id)
    normalized_prompt = str(prompt_template or "").strip()
    if not normalized_prompt:
        raise ValueError("prompt_template is required")
    normalized_cron_expr = _normalize_cron_expr(cron_expr)
    current_time = now or datetime.now()

    task = InspectionTask(
        name=normalized_name,
        source_conversation_id=source_conversation_id,
        agent_id=resolved_agent_id,
        skill_id=(skill_id or "").strip() or None,
        prompt_template=normalized_prompt,
        target_payload=target_payload,
        schedule_type="cron",
        cron_expr=normalized_cron_expr,
        enabled=bool(enabled),
        last_status="idle",
        next_run_at=next_cron_run_at(normalized_cron_expr, current_time)
        if enabled
        else None,
    )

    async with session_factory() as session:
        session.add(task)
        await session.commit()
        await session.refresh(task)
        return task


async def list_inspection_tasks(
    *,
    session_factory: SessionFactory = AsyncSessionLocal,
) -> list[InspectionTask]:
    async with session_factory() as session:
        result = await session.execute(
            select(InspectionTask).order_by(InspectionTask.updated_at.desc())
        )
        return list(result.scalars().all())


async def get_inspection_task(
    task_id: str,
    *,
    session_factory: SessionFactory = AsyncSessionLocal,
) -> InspectionTask:
    async with session_factory() as session:
        task = await session.get(InspectionTask, task_id)
        if task is None:
            raise LookupError("inspection task not found")
        return task


async def list_inspection_task_runs(
    task_id: str | None = None,
    *,
    session_factory: SessionFactory = AsyncSessionLocal,
) -> list[InspectionTaskRun]:
    async with session_factory() as session:
        stmt = select(InspectionTaskRun).order_by(InspectionTaskRun.started_at.desc())
        if task_id:
            stmt = stmt.where(InspectionTaskRun.task_id == task_id)
        result = await session.execute(stmt)
        return list(result.scalars().all())


async def update_inspection_task(
    task_id: str,
    *,
    name: str | None = None,
    skill_id: str | None = None,
    prompt_template: str | None = None,
    target_payload: dict[str, Any] | None = None,
    cron_expr: str | None = None,
    enabled: bool | None = None,
    now: datetime | None = None,
    session_factory: SessionFactory = AsyncSessionLocal,
) -> InspectionTask:
    current_time = now or datetime.now()
    async with session_factory() as session:
        task = await session.get(InspectionTask, task_id)
        if task is None:
            raise LookupError("inspection task not found")

        if name is not None:
            task.name = _normalize_task_name(name)
        if skill_id is not None:
            task.skill_id = skill_id.strip() or None
        if prompt_template is not None:
            normalized_prompt = str(prompt_template or "").strip()
            if not normalized_prompt:
                raise ValueError("prompt_template is required")
            task.prompt_template = normalized_prompt
        if target_payload is not None:
            task.target_payload = target_payload
        if cron_expr is not None:
            task.cron_expr = _normalize_cron_expr(cron_expr)
        if enabled is not None:
            task.enabled = enabled

        task.next_run_at = (
            next_cron_run_at(task.cron_expr, current_time) if task.enabled else None
        )
        await session.commit()
        await session.refresh(task)
        return task


async def execute_inspection_task(
    task_id: str,
    *,
    trigger_type: str,
    session_factory: SessionFactory = AsyncSessionLocal,
    now: datetime | None = None,
    agent_runner: AgentRunner = run_agent,
) -> InspectionTaskRun:
    current_time = now or datetime.now()

    async with session_factory() as session:
        task = await session.get(InspectionTask, task_id)
        if task is None:
            raise LookupError("inspection task not found")

        run = InspectionTaskRun(
            task_id=task.id,
            trigger_type=trigger_type,
            status="running",
            started_at=current_time,
        )
        session.add(run)
        await session.flush()

        conversation = await create_conversation(
            session,
            source="task",
            agent_id=task.agent_id,
            title=f"{task.name} · {current_time.strftime('%m-%d %H:%M')}",
            source_task_id=task.id,
            source_task_run_id=run.id,
            source_task_trigger_type=trigger_type,
        )
        run.conversation_id = conversation.id
        task.last_status = "running"
        task.last_run_at = current_time
        if trigger_type == "scheduled" and task.enabled:
            task.next_run_at = next_cron_run_at(task.cron_expr, current_time)
        await session.commit()
        await session.refresh(run)
        await session.refresh(task)

    await save_message(
        run.conversation_id,
        "user",
        task.prompt_template,
        "text",
        agent_id=task.agent_id,
        session_factory=session_factory,
    )

    event_state = AgentEventState()

    async def on_event(event: dict[str, Any]):
        normalized_event = event_state.apply_event(event)
        event_type = normalized_event.get("type")
        event_agent_id = event.get("agent_id") or task.agent_id

        if event_type == "text_delta":
            return

        if event_type == "tool_call":
            await save_message(
                run.conversation_id,
                "system",
                normalized_event.get("tool_desc", ""),
                "tool_call",
                agent_id=event_agent_id,
                tool_name=normalized_event.get("tool_name"),
                tool_input=normalized_event.get("tool_input")
                if isinstance(normalized_event.get("tool_input"), dict)
                else None,
                thinking=event_state.pop_step_thinking(),
                session_factory=session_factory,
            )
            return

        if event_type == "tool_result":
            await save_message(
                run.conversation_id,
                "system",
                normalized_event.get("result", ""),
                "tool_result",
                agent_id=event_agent_id,
                tool_name=normalized_event.get("tool_name"),
                tool_input=normalized_event.get("tool_input")
                if isinstance(normalized_event.get("tool_input"), dict)
                else None,
                session_factory=session_factory,
            )
            return

        if event_type == "done":
            snapshot = event_state.snapshot()
            if snapshot.text:
                await save_message(
                    run.conversation_id,
                    "assistant",
                    snapshot.text,
                    "text",
                    agent_id=event_agent_id,
                    thinking=snapshot.thinking or None,
                    session_factory=session_factory,
                )

    try:
        await agent_runner(
            user_message=task.prompt_template,
            conv_id=run.conversation_id,
            on_event=on_event,
            agent_id=task.agent_id,
        )
    except Exception as exc:
        async with session_factory() as session:
            db_run = await session.get(InspectionTaskRun, run.id)
            db_task = await session.get(InspectionTask, task.id)
            if db_run is not None:
                db_run.status = "failed"
                db_run.finished_at = datetime.now()
                db_run.error_message = str(exc)
            if db_task is not None:
                db_task.last_status = "failed"
            await session.commit()
            if db_run is not None:
                await session.refresh(db_run)
                return db_run
        raise

    async with session_factory() as session:
        db_run = await session.get(InspectionTaskRun, run.id)
        db_task = await session.get(InspectionTask, task.id)
        if db_run is None or db_task is None:
            raise LookupError("inspection task run not found after execution")
        db_run.status = "succeeded"
        db_run.finished_at = datetime.now()
        db_task.last_status = "succeeded"
        if trigger_type != "scheduled" and db_task.enabled:
            db_task.next_run_at = next_cron_run_at(db_task.cron_expr, current_time)
        await session.commit()
        await session.refresh(db_run)
        return db_run


async def get_due_inspection_task_ids(
    *,
    now: datetime | None = None,
    session_factory: SessionFactory = AsyncSessionLocal,
) -> list[str]:
    current_time = now or datetime.now()
    async with session_factory() as session:
        result = await session.execute(
            select(InspectionTask.id).where(
                InspectionTask.enabled.is_(True),
                InspectionTask.next_run_at.is_not(None),
                InspectionTask.next_run_at <= current_time,
            )
        )
        return [task_id for task_id in result.scalars().all()]
