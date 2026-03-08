"""SQLAlchemy 异步数据库引擎"""

from sqlalchemy import event
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
    """为 SQLite 连接开启外键与更合适的并发配置。"""
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


async def init_db():
    """创建所有表"""
    # 局部导入 Base 以避免循环引用，并注册 metadata
    from models import Base

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("数据库表已就绪")


async def get_session() -> AsyncSession:
    """获取数据库 session"""
    async with AsyncSessionLocal() as session:
        yield session


async def close_db():
    """关闭数据库连接池。"""
    await engine.dispose()
    logger.info("数据库连接已关闭")
