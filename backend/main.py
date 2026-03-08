"""FastAPI 应用入口

提供 WebSocket 端点用于对话，REST API 用于会话管理。
"""

from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from agent import init_agent_runtime, list_agent_profiles
from api.routers import agent, agents, conversations, mcp, memories, skills
from api.ws import chat
from config import ANTHROPIC_API_KEY, SKILLS_DIR
from db.session import close_db, init_db
from utils.logger import logger

app = FastAPI(title="Claude Agent Demo", version="0.2.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def startup():
    await init_db()
    await init_agent_runtime()

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

    await close_agent_runtime()
    await close_db()


app.include_router(conversations.router)
app.include_router(agents.router)
app.include_router(skills.router)
app.include_router(mcp.router)
app.include_router(agent.router)
app.include_router(memories.router)
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
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
