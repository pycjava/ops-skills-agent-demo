from datetime import datetime

import pytest
from sqlalchemy import select

from models import Conversation, Message
from services.inspection_tasks import (
    build_inspection_task_draft,
    create_inspection_task,
    execute_inspection_task,
    next_cron_run_at,
)


@pytest.mark.asyncio
async def test_build_inspection_task_draft_uses_latest_user_message(session_factory):
    async with session_factory() as session:
        conversation = Conversation(
            title="Peets POS 巡检",
            source="web",
            agent_id="dba",
        )
        session.add(conversation)
        await session.flush()
        session.add_all(
            [
                Message(
                    conversation_id=conversation.id,
                    role="user",
                    content="先看一下基础指标",
                    type="text",
                    agent_id="dba",
                ),
                Message(
                    conversation_id=conversation.id,
                    role="assistant",
                    content="好的",
                    type="text",
                    agent_id="dba",
                ),
                Message(
                    conversation_id=conversation.id,
                    role="user",
                    content="请巡检 peets-prod-pos-mysql 最近 7 天状态",
                    type="text",
                    agent_id="dba",
                ),
            ]
        )
        await session.commit()
        await session.refresh(conversation)

    draft = await build_inspection_task_draft(
        conversation.id,
        session_factory=session_factory,
    )

    assert draft["source_conversation_id"] == conversation.id
    assert draft["agent_id"] == "dba"
    assert draft["name"] == "Peets POS 巡检"
    assert draft["prompt_template"] == "请巡检 peets-prod-pos-mysql 最近 7 天状态"


def test_next_cron_run_at_returns_the_next_matching_minute():
    now = datetime(2026, 3, 11, 8, 5)

    assert next_cron_run_at("0 9 * * *", now) == datetime(2026, 3, 11, 9, 0)
    assert next_cron_run_at("*/15 * * * *", now) == datetime(2026, 3, 11, 8, 15)


@pytest.mark.asyncio
async def test_execute_inspection_task_creates_conversation_and_run_record(
    session_factory,
):
    async with session_factory() as session:
        source_conversation = Conversation(
            title="Peets Daily Inspection",
            source="web",
            agent_id="dba",
        )
        session.add(source_conversation)
        await session.commit()
        await session.refresh(source_conversation)

    task = await create_inspection_task(
        name="Peets Daily Inspection",
        source_conversation_id=source_conversation.id,
        agent_id="dba",
        skill_id="volcengine-rds-health-analyzer",
        prompt_template="请巡检 peets-prod-pos-mysql 最近 7 天状态",
        target_payload={"instance_name": "peets-prod-pos-mysql"},
        cron_expr="0 9 * * *",
        enabled=True,
        now=datetime(2026, 3, 11, 8, 0),
        session_factory=session_factory,
    )

    async def fake_agent_runner(*, user_message, conv_id, on_event, agent_id=None):
        assert user_message == "请巡检 peets-prod-pos-mysql 最近 7 天状态"
        assert agent_id == "dba"
        await on_event({"type": "text_delta", "content": "巡检完成", "agent_id": "dba"})
        await on_event({"type": "done", "agent_id": "dba"})

    run = await execute_inspection_task(
        task.id,
        trigger_type="manual",
        now=datetime(2026, 3, 11, 8, 30),
        session_factory=session_factory,
        agent_runner=fake_agent_runner,
    )

    assert run.status == "succeeded"
    assert run.trigger_type == "manual"
    assert run.conversation_id

    async with session_factory() as session:
        conversation = await session.get(Conversation, run.conversation_id)
        messages = (
            await session.execute(
                select(Message)
                .where(Message.conversation_id == run.conversation_id)
                .order_by(Message.created_at)
            )
        ).scalars().all()

    assert conversation is not None
    assert conversation.source == "task"
    assert conversation.source_task_id == task.id
    assert conversation.source_task_trigger_type == "manual"
    assert [message.role for message in messages] == ["user", "assistant"]
    assert messages[0].content == "请巡检 peets-prod-pos-mysql 最近 7 天状态"
    assert messages[1].content == "巡检完成"
