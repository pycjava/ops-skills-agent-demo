from datetime import datetime
from typing import Any

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from db.session import AsyncSessionLocal
from services.inspection_tasks import (
    build_inspection_task_draft,
    create_inspection_task,
    execute_inspection_task,
    get_inspection_task,
    list_inspection_task_runs,
    list_inspection_tasks,
    update_inspection_task,
)


router = APIRouter(prefix="/api/inspection-tasks", tags=["inspection-tasks"])


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


@router.post("/draft")
async def create_inspection_task_draft(body: DraftRequest):
    try:
        draft = await build_inspection_task_draft(
            body.conversation_id,
            session_factory=AsyncSessionLocal,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return JSONResponse(draft)


@router.get("")
async def get_inspection_tasks():
    tasks = await list_inspection_tasks(session_factory=AsyncSessionLocal)
    return JSONResponse([task.to_dict() for task in tasks])


@router.post("")
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


@router.get("/{task_id}")
async def get_inspection_task_route(task_id: str):
    try:
        task = await get_inspection_task(task_id, session_factory=AsyncSessionLocal)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return JSONResponse(task.to_dict())


@router.patch("/{task_id}")
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


@router.post("/{task_id}/trigger")
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


@router.get("/{task_id}/runs")
async def get_inspection_task_runs(task_id: str):
    runs = await list_inspection_task_runs(task_id, session_factory=AsyncSessionLocal)
    return JSONResponse([run.to_dict() for run in runs])


@router.get("/runs/all")
async def get_all_inspection_task_runs():
    runs = await list_inspection_task_runs(session_factory=AsyncSessionLocal)
    return JSONResponse([run.to_dict() for run in runs])
