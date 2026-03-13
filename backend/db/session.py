"""Async SQLAlchemy database session helpers."""

from sqlalchemy import event, inspect, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from config import DATABASE_URL
from utils.logger import logger

engine = create_async_engine(
    DATABASE_URL,
    echo=False,
    connect_args={
        "check_same_thread": False,
        "timeout": 30,
    },
)


@event.listens_for(engine.sync_engine, "connect")
def _set_sqlite_pragma(dbapi_connection, _connection_record):
    """Configure SQLite pragmas for each new connection."""
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA synchronous=NORMAL")
    cursor.close()


AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


def _has_column(sync_conn, table_name: str, column_name: str) -> bool:
    inspector = inspect(sync_conn)
    columns = inspector.get_columns(table_name)
    return any(column["name"] == column_name for column in columns)


def _has_table(sync_conn, table_name: str) -> bool:
    inspector = inspect(sync_conn)
    return inspector.has_table(table_name)


def _bootstrap_sqlite_compat_columns(sync_conn):
    if not _has_column(sync_conn, "conversations", "agent_id"):
        sync_conn.execute(
            text(
                "ALTER TABLE conversations "
                "ADD COLUMN agent_id VARCHAR(50) DEFAULT 'general'"
            )
        )

    sync_conn.execute(
        text(
            "UPDATE conversations "
            "SET agent_id = 'general' "
            "WHERE agent_id IS NULL OR TRIM(agent_id) = ''"
        )
    )
    sync_conn.execute(
        text(
            "UPDATE conversations "
            "SET title = '新对话' "
            "WHERE title = '鏂板璇?'"
        )
    )

    if not _has_column(sync_conn, "conversations", "source_task_id"):
        sync_conn.execute(text("ALTER TABLE conversations ADD COLUMN source_task_id VARCHAR(36)"))

    if not _has_column(sync_conn, "conversations", "source_task_run_id"):
        sync_conn.execute(
            text("ALTER TABLE conversations ADD COLUMN source_task_run_id VARCHAR(36)")
        )

    if not _has_column(sync_conn, "conversations", "source_task_trigger_type"):
        sync_conn.execute(
            text(
                "ALTER TABLE conversations "
                "ADD COLUMN source_task_trigger_type VARCHAR(20)"
            )
        )

    if not _has_column(sync_conn, "messages", "agent_id"):
        sync_conn.execute(text("ALTER TABLE messages ADD COLUMN agent_id VARCHAR(50)"))

    if not _has_column(sync_conn, "messages", "attachments_snapshot"):
        sync_conn.execute(text("ALTER TABLE messages ADD COLUMN attachments_snapshot JSON"))

    sync_conn.execute(
        text(
            "UPDATE messages "
            "SET agent_id = 'general' "
            "WHERE agent_id IS NULL OR TRIM(agent_id) = ''"
        )
    )

    if _has_table(sync_conn, "mcp_servers"):
        if not _has_column(sync_conn, "mcp_servers", "command"):
            sync_conn.execute(text("ALTER TABLE mcp_servers ADD COLUMN command TEXT"))

        if not _has_column(sync_conn, "mcp_servers", "args"):
            sync_conn.execute(
                text("ALTER TABLE mcp_servers ADD COLUMN args JSON DEFAULT '[]'")
            )

        if not _has_column(sync_conn, "mcp_servers", "env"):
            sync_conn.execute(text("ALTER TABLE mcp_servers ADD COLUMN env JSON"))


async def init_db():
    """Create tables and backfill compatibility columns."""
    from models import Base
    from auth.service import ensure_authorization_seed_data

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await conn.run_sync(_bootstrap_sqlite_compat_columns)

    async with AsyncSessionLocal() as session:
        await ensure_authorization_seed_data(session)
        await session.commit()
    logger.info("Database tables initialized")


async def close_db():
    """Dispose the database engine."""
    await engine.dispose()
    logger.info("Database connections closed")
