from __future__ import annotations

import asyncio
from contextlib import suppress
from datetime import datetime

from services.inspection_tasks import execute_inspection_task, get_due_inspection_task_ids
from db.session import AsyncSessionLocal
from utils.logger import logger


class InspectionSchedulerRuntime:
    def __init__(self, poll_interval_seconds: float = 30.0):
        self._poll_interval_seconds = poll_interval_seconds
        self._task: asyncio.Task | None = None
        self._stop_event = asyncio.Event()

    async def start(self):
        if self._task and not self._task.done():
            return
        self._stop_event = asyncio.Event()
        self._task = asyncio.create_task(self._run_loop(), name="inspection-scheduler")

    async def stop(self):
        self._stop_event.set()
        if self._task is None:
            return
        self._task.cancel()
        with suppress(asyncio.CancelledError):
            await self._task
        self._task = None

    async def _run_loop(self):
        while not self._stop_event.is_set():
            try:
                due_task_ids = await get_due_inspection_task_ids(
                    now=datetime.now(),
                    session_factory=AsyncSessionLocal,
                )
                for task_id in due_task_ids:
                    try:
                        await execute_inspection_task(
                            task_id,
                            trigger_type="scheduled",
                            now=datetime.now(),
                            session_factory=AsyncSessionLocal,
                        )
                    except Exception as exc:
                        logger.warning(f"Inspection task {task_id} failed during schedule run: {exc}")
            except Exception as exc:
                logger.warning(f"Inspection scheduler poll failed: {exc}")

            try:
                await asyncio.wait_for(
                    self._stop_event.wait(),
                    timeout=self._poll_interval_seconds,
                )
            except asyncio.TimeoutError:
                continue
