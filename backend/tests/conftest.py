import sys
from pathlib import Path

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine


BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from models import Base, Conversation


@pytest.fixture
async def session_factory(tmp_path):
    db_path = tmp_path / "test.db"
    engine = create_async_engine(
        f"sqlite+aiosqlite:///{db_path.as_posix()}",
        connect_args={"check_same_thread": False, "timeout": 30},
    )

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    factory = async_sessionmaker(engine, expire_on_commit=False)

    try:
        yield factory
    finally:
        await engine.dispose()


@pytest.fixture
async def seeded_conversation(session_factory):
    async with session_factory() as session:
        conversation = Conversation(title="新对话", source="web", agent_id="general")
        session.add(conversation)
        await session.commit()
        await session.refresh(conversation)
        return conversation

