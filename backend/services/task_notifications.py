from __future__ import annotations

import os
import re
from datetime import datetime

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from db.session import AsyncSessionLocal
from models import InspectionTask, InspectionTaskRun, Message, TaskNotification

SessionFactory = async_sessionmaker[AsyncSession]

REPORT_EXTENSIONS = (".md", ".html", ".pdf")
REPORT_MEMORY_PREFIX = "/memories/reports/"


def _normalize_summary(content: str) -> str:
    lines = [
        re.sub(r"\s+", " ", line).strip()
        for line in str(content or "").splitlines()
        if line.strip()
    ]
    if not lines:
        return ""
    return "\n".join(lines[:3])


def _extract_report_path(message: Message) -> str | None:
    if message.type != "tool_result" or message.tool_name not in {"write_file", "edit_file"}:
        return None
    if not isinstance(message.tool_input, dict):
        return None

    raw_path = message.tool_input.get("file_path") or message.tool_input.get("path")
    if not isinstance(raw_path, str):
        return None

    normalized = raw_path.strip()
    lowered = normalized.lower()
    if lowered.startswith(REPORT_MEMORY_PREFIX) and lowered.endswith(REPORT_EXTENSIONS):
        return normalized
    if lowered.endswith(REPORT_EXTENSIONS):
        return normalized
    return None


def extract_latest_report_path(messages: list[Message]) -> str | None:
    return next(
        (
            report_path
            for report_path in (_extract_report_path(message) for message in reversed(messages))
            if report_path
        ),
        None,
    )


def extract_latest_report_reference(messages: list[Message]) -> tuple[str | None, str | None]:
    latest_report_path = extract_latest_report_path(messages)
    return (
        os.path.basename(latest_report_path) if latest_report_path else None,
        latest_report_path,
    )


async def create_task_notification_for_run(
    task_id: str,
    task_run_id: str,
    *,
    session_factory: SessionFactory = AsyncSessionLocal,
    fallback_summary: str | None = None,
) -> tuple[TaskNotification, int]:
    async with session_factory() as session:
        task = await session.get(InspectionTask, task_id)
        run = await session.get(InspectionTaskRun, task_run_id)
        if task is None or run is None:
            raise LookupError("task notification source not found")

        messages: list[Message] = []
        if run.conversation_id:
            messages = list(
                (
                    await session.execute(
                        select(Message)
                        .where(Message.conversation_id == run.conversation_id)
                        .order_by(Message.created_at.asc())
                    )
                ).scalars().all()
            )

        latest_assistant = next(
            (
                message
                for message in reversed(messages)
                if message.role == "assistant"
                and message.type == "text"
                and (message.content or "").strip()
            ),
            None,
        )
        report_name = None
        latest_report_path = None
        if run.status == "succeeded":
            report_name, latest_report_path = extract_latest_report_reference(messages)
            latest_report_path = run.report_path or latest_report_path
            report_name = run.report_name or report_name or (
                os.path.basename(latest_report_path) if latest_report_path else None
            )

        summary = _normalize_summary(
            latest_assistant.content if latest_assistant else (fallback_summary or "")
        )
        if not summary:
            summary = "Task completed successfully" if run.status == "succeeded" else "Task failed"

        notification = TaskNotification(
            task_id=task.id,
            task_run_id=run.id,
            conversation_id=run.conversation_id,
            status=run.status,
            title=task.name,
            summary=summary,
            report_name=report_name,
            report_path=latest_report_path,
        )
        session.add(notification)
        await session.commit()
        await session.refresh(notification)

        unread_count = int(
            (
                await session.execute(
                    select(func.count(TaskNotification.id)).where(TaskNotification.read_at.is_(None))
                )
            ).scalar()
            or 0
        )
        return notification, unread_count


async def list_task_notifications(
    *,
    limit: int = 50,
    session_factory: SessionFactory = AsyncSessionLocal,
) -> tuple[list[TaskNotification], int]:
    async with session_factory() as session:
        notifications = list(
            (
                await session.execute(
                    select(TaskNotification)
                    .order_by(TaskNotification.created_at.desc())
                    .limit(limit)
                )
            ).scalars().all()
        )
        unread_count = int(
            (
                await session.execute(
                    select(func.count(TaskNotification.id)).where(TaskNotification.read_at.is_(None))
                )
            ).scalar()
            or 0
        )
        return notifications, unread_count


async def mark_task_notification_read(
    notification_id: str,
    *,
    session_factory: SessionFactory = AsyncSessionLocal,
    now: datetime | None = None,
) -> TaskNotification:
    async with session_factory() as session:
        notification = await session.get(TaskNotification, notification_id)
        if notification is None:
            raise LookupError("task notification not found")

        if notification.read_at is None:
            notification.read_at = now or datetime.now()
            await session.commit()
            await session.refresh(notification)

        return notification


async def mark_all_task_notifications_read(
    *,
    session_factory: SessionFactory = AsyncSessionLocal,
    now: datetime | None = None,
) -> int:
    async with session_factory() as session:
        result = await session.execute(
            update(TaskNotification)
            .where(TaskNotification.read_at.is_(None))
            .values(read_at=now or datetime.now())
        )
        await session.commit()
        return int(result.rowcount or 0)


def build_task_notification_event(
    notification: TaskNotification,
    unread_count: int,
) -> dict:
    return {
        "type": "task_notification",
        "notification": notification.to_dict(),
        "unread_count": unread_count,
    }
