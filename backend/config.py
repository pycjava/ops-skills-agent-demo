"""配置模块"""

import os
from pathlib import Path

from dotenv import load_dotenv

# 项目 backend 根目录
BASE_DIR = Path(__file__).resolve().parent

# 显式加载 backend/.env，并覆盖同名系统环境变量，
# 避免本机已有的 ANTHROPIC_* 配置串到当前项目
load_dotenv(BASE_DIR / ".env", override=True)

# API Key（claude-agent-sdk 会自动从环境变量读取，这里保留用于健康检查）
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")

# 项目根目录 (由于是前后端分离，限制只在 backend 内)
PROJECT_DIR = str(BASE_DIR)
WORKSPACE_DIR = str(BASE_DIR.parent)

# Skills 目录
SKILLS_DIR = str(BASE_DIR / "skills")

# Agent 配置
MODEL_NAME = os.getenv("MODEL_NAME", "claude-sonnet-4-5-20250929")
MULTIMODAL_ENABLED = os.getenv("MULTIMODAL_ENABLED", "true").strip().lower() not in {
    "0",
    "false",
    "no",
    "off",
}
VISION_MODEL_ALLOWLIST = tuple(
    item.strip()
    for item in os.getenv(
        "VISION_MODEL_ALLOWLIST",
        "claude-sonnet-4-5-20250929",
    ).split(",")
    if item.strip()
)
MAX_TURNS = int(os.getenv("MAX_TURNS", "10"))
MCP_DEFAULT_TIMEOUT_SECONDS = 15.0
MCP_CONFIG_PATH = str((Path(WORKSPACE_DIR) / "mcp.json").resolve())

# ─── SQLite 配置 ──────────────────────────────────────
DEFAULT_SQLITE_PATH = "data/app.db"

_sqlite_file = Path(os.getenv("SQLITE_PATH", DEFAULT_SQLITE_PATH))
if not _sqlite_file.is_absolute():
    _sqlite_file = BASE_DIR / _sqlite_file

SQLITE_FILE = _sqlite_file.resolve()
SQLITE_FILE.parent.mkdir(parents=True, exist_ok=True)
SQLITE_PATH = SQLITE_FILE.as_posix()

# SQLAlchemy 异步 / 同步连接串
DATABASE_URL = f"sqlite+aiosqlite:///{SQLITE_PATH}"
DATABASE_URL_SYNC = f"sqlite:///{SQLITE_PATH}"

# ─── 日志配置 ────────────────────────────────────────
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
LOG_FILE = os.getenv("LOG_FILE", str(BASE_DIR / "logs" / "app.log"))
LOG_MAX_SIZE_MB = int(os.getenv("LOG_MAX_SIZE_MB", "10"))
LOG_BACKUP_COUNT = int(os.getenv("LOG_BACKUP_COUNT", "5"))


def get_cors_allowed_origins() -> list[str]:
    raw = os.getenv(
        "CORS_ALLOW_ORIGINS",
        "http://localhost:5173,"
        "http://127.0.0.1:5173,"
        "http://localhost:4173,"
        "http://127.0.0.1:4173",
    )
    origins = [item.strip() for item in raw.split(",") if item.strip()]
    return origins or ["http://localhost:5173"]
