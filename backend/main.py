"""FastAPI 应用入口。

提供 WebSocket 端点用于对话，REST API 用于会话管理。
"""

import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware

from agent import init_agent_runtime, list_agent_profiles
from api.routers import (
    agent,
    agents,
    auth,
    cloud_credentials,
    conversation_attachments,
    conversations,
    inspection_tasks,
    mcp,
    memories,
    rag,
    skills,
    task_notifications,
)
from api.ws import chat
from auth.config import get_auth_settings
from config import ANTHROPIC_API_KEY, BASE_DIR, SKILLS_DIR, get_cors_allowed_origins
from db.session import close_db, init_db
from services.browser_runtime import verify_agent_browser_cli
from services.inspection_scheduler import InspectionSchedulerRuntime
from utils.logger import logger

app = FastAPI(title="AgentWeave Demo", version="0.2.0")
inspection_scheduler = InspectionSchedulerRuntime()
auth_settings = get_auth_settings()

app.add_middleware(
    SessionMiddleware,
    secret_key=auth_settings.session_secret,
    session_cookie=auth_settings.session_cookie_name,
    same_site=auth_settings.session_cookie_same_site,
    https_only=auth_settings.session_cookie_secure,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=get_cors_allowed_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

RELOAD_EXCLUDE_DIRS = ("tmp", "metric_data", "logs", "data", "memories")


def build_uvicorn_reload_kwargs() -> dict[str, object]:
    current_working_directory = Path.cwd()
    reload_excludes = [
        Path(
            os.path.relpath((BASE_DIR / directory).resolve(), current_working_directory)
        ).as_posix()
        for directory in RELOAD_EXCLUDE_DIRS
    ]
    return {
        "reload": True,
        "reload_dirs": [str(BASE_DIR)],
        "reload_excludes": reload_excludes,
        "app_dir": str(BASE_DIR),
    }


@app.on_event("startup")
async def startup():
    verify_agent_browser_cli()
    await init_db()
    await init_agent_runtime()
    await inspection_scheduler.start()

    logger.info(f"Skills 目录: {SKILLS_DIR}")
    if ANTHROPIC_API_KEY:
        logger.info("ANTHROPIC_API_KEY 已配置")
    else:
        logger.warning("未设置 ANTHROPIC_API_KEY，Agent 功能不可用")

    skills_path = Path(SKILLS_DIR)
    if skills_path.exists():
        skill_dirs = [
            directory.name
            for directory in skills_path.iterdir()
            if directory.is_dir() and (directory / "SKILL.md").exists()
        ]
        logger.info(f"发现 {len(skill_dirs)} 个 Skills: {skill_dirs}")

    logger.info(f"可用 Agents: {[profile.id for profile in list_agent_profiles()]}")


@app.on_event("shutdown")
async def shutdown():
    from agent import close_agent_runtime

    await inspection_scheduler.stop()
    await close_agent_runtime()
    await close_db()


app.include_router(conversations.router)
app.include_router(conversation_attachments.router)
app.include_router(inspection_tasks.router)
app.include_router(task_notifications.router)
app.include_router(auth.router)
app.include_router(agents.router)
app.include_router(skills.router)
app.include_router(mcp.router)
app.include_router(cloud_credentials.router)
app.include_router(agent.router)
app.include_router(memories.router)
app.include_router(rag.router)
app.include_router(chat.router)


@app.get("/api/health")
async def health():
    return {
        "status": "ok",
        "api_key_configured": bool(ANTHROPIC_API_KEY),
    }


if __name__ == "__main__":
    import uvicorn

    logger.info("正在 http://0.0.0.0:8000 启动 Uvicorn 服务器")
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        **build_uvicorn_reload_kwargs(),
    )
