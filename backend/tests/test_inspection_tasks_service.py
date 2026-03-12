from datetime import datetime

import pytest
from sqlalchemy import select

from models import Conversation, InspectionTask, Message
from services.inspection_tasks import (
    TaskConversationSummary,
    TaskCreationIntentResult,
    build_inspection_task_draft,
    create_inspection_task,
    create_inspection_task_from_conversation_message,
    delete_inspection_task,
    execute_inspection_task,
    next_cron_run_at,
)


@pytest.mark.asyncio
async def test_build_inspection_task_draft_uses_latest_non_task_user_message(session_factory):
    async with session_factory() as session:
        conversation = Conversation(
            title="Peets POS Inspection",
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
                    content="Check the baseline metrics first",
                    type="text",
                    agent_id="dba",
                ),
                Message(
                    conversation_id=conversation.id,
                    role="assistant",
                    content="Acknowledged",
                    type="text",
                    agent_id="dba",
                ),
                Message(
                    conversation_id=conversation.id,
                    role="user",
                    content="Please inspect peets-prod-pos-mysql for the last 7 days",
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
    assert draft["name"] == "Peets POS Inspection"
    assert draft["prompt_template"] == "Please inspect peets-prod-pos-mysql for the last 7 days"


@pytest.mark.asyncio
async def test_build_inspection_task_draft_skips_task_creation_messages(session_factory):
    async with session_factory() as session:
        conversation = Conversation(
            title="Peets POS Inspection",
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
                    content="Please inspect peets-prod-pos-mysql for the last 7 days",
                    type="text",
                    agent_id="dba",
                ),
                Message(
                    conversation_id=conversation.id,
                    role="assistant",
                    content="Acknowledged",
                    type="text",
                    agent_id="dba",
                ),
                Message(
                    conversation_id=conversation.id,
                    role="user",
                    content="Create a scheduled task and run it every day at 9:00",
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

    assert draft["prompt_template"] == "Please inspect peets-prod-pos-mysql for the last 7 days"


def test_next_cron_run_at_returns_the_next_matching_minute():
    now = datetime(2026, 3, 11, 8, 5)

    assert next_cron_run_at("0 9 * * *", now) == datetime(2026, 3, 11, 9, 0)
    assert next_cron_run_at("*/15 * * * *", now) == datetime(2026, 3, 11, 8, 15)


@pytest.mark.asyncio
async def test_create_inspection_task_from_conversation_message_creates_task(session_factory):
    async with session_factory() as session:
        conversation = Conversation(
            title="Peets POS Inspection",
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
                    content="Inspect peets-prod-pos-mysql for slow queries and replication lag",
                    type="text",
                    agent_id="dba",
                ),
                Message(
                    conversation_id=conversation.id,
                    role="assistant",
                    content="I found elevated replication lag after 02:00.",
                    type="text",
                    agent_id="dba",
                ),
            ]
        )
        await session.commit()
        await session.refresh(conversation)

    analyzer_calls: list[str] = []
    summarizer_calls: list[tuple[str, list[str]]] = []

    async def fake_intent_analyzer(message: str) -> TaskCreationIntentResult:
        analyzer_calls.append(message)
        return TaskCreationIntentResult(
            is_task_creation=True,
            cron_expr="0 9 * * *",
            error_message=None,
        )

    async def fake_summarizer(
        source_conversation: Conversation,
        messages: list[Message],
    ) -> TaskConversationSummary:
        summarizer_calls.append(
            (
                source_conversation.id,
                [message.content for message in messages],
            )
        )
        return TaskConversationSummary(
            name="Peets Daily Inspection",
            prompt_template="Inspect peets-prod-pos-mysql for slow queries and replication lag",
            skill_id="volcengine-rds-health-analyzer",
            target_payload={"instance_name": "peets-prod-pos-mysql"},
        )

    result = await create_inspection_task_from_conversation_message(
        conversation.id,
        "Generate a scheduled task and run it every day at 09:00",
        session_factory=session_factory,
        intent_analyzer=fake_intent_analyzer,
        conversation_summarizer=fake_summarizer,
        now=datetime(2026, 3, 11, 8, 0),
    )

    assert result["status"] == "created"
    assert result["task"]["name"] == "Peets Daily Inspection"
    assert result["task"]["source_conversation_id"] == conversation.id
    assert result["task"]["cron_expr"] == "0 9 * * *"
    assert result["intent_analysis"]["intent_matched"] is True
    assert result["intent_analysis"]["outcome"] == "created"
    assert result["intent_analysis"]["cron_expr"] == "0 9 * * *"
    assert "Peets Daily Inspection" in result["intent_analysis"]["summary"]
    assert result["intent_analysis"]["reason"] is None
    assert analyzer_calls == ["Generate a scheduled task and run it every day at 09:00"]
    assert summarizer_calls == [
        (
            conversation.id,
            [
                "Inspect peets-prod-pos-mysql for slow queries and replication lag",
                "I found elevated replication lag after 02:00.",
            ],
        )
    ]

    async with session_factory() as session:
        stored_tasks = (await session.execute(select(InspectionTask))).scalars().all()

    assert len(stored_tasks) == 1
    assert stored_tasks[0].source_conversation_id == conversation.id


@pytest.mark.asyncio
async def test_create_inspection_task_from_conversation_message_returns_not_task_creation(
    session_factory,
):
    async with session_factory() as session:
        conversation = Conversation(
            title="General Chat",
            source="web",
            agent_id="general",
        )
        session.add(conversation)
        await session.commit()
        await session.refresh(conversation)

    summarizer_called = False

    async def fake_intent_analyzer(_message: str) -> TaskCreationIntentResult:
        return TaskCreationIntentResult(
            is_task_creation=False,
            cron_expr=None,
            error_message=None,
        )

    async def fake_summarizer(
        _conversation: Conversation,
        _messages: list[Message],
    ) -> TaskConversationSummary:
        nonlocal summarizer_called
        summarizer_called = True
        raise AssertionError("summarizer should not be called")

    result = await create_inspection_task_from_conversation_message(
        conversation.id,
        "Can you summarize the latest findings?",
        session_factory=session_factory,
        intent_analyzer=fake_intent_analyzer,
        conversation_summarizer=fake_summarizer,
    )

    assert result == {"status": "not_task_creation"}
    assert summarizer_called is False


@pytest.mark.asyncio
async def test_create_inspection_task_from_conversation_message_returns_error_when_schedule_missing(
    session_factory,
):
    async with session_factory() as session:
        conversation = Conversation(
            title="Peets POS Inspection",
            source="web",
            agent_id="dba",
        )
        session.add(conversation)
        await session.commit()
        await session.refresh(conversation)

    summarizer_called = False

    async def fake_intent_analyzer(_message: str) -> TaskCreationIntentResult:
        return TaskCreationIntentResult(
            is_task_creation=True,
            cron_expr=None,
            error_message="未能从当前这句话中识别完整调度时间，请补充执行频率或具体时间。",
        )

    async def fake_summarizer(
        _conversation: Conversation,
        _messages: list[Message],
    ) -> TaskConversationSummary:
        nonlocal summarizer_called
        summarizer_called = True
        raise AssertionError("summarizer should not be called")

    result = await create_inspection_task_from_conversation_message(
        conversation.id,
        "Create a scheduled task for this conversation",
        session_factory=session_factory,
        intent_analyzer=fake_intent_analyzer,
        conversation_summarizer=fake_summarizer,
    )

    assert result["status"] == "error"
    assert result["message"] == "未能从当前这句话中识别完整调度时间，请补充执行频率或具体时间。"
    assert result["intent_analysis"]["intent_matched"] is True
    assert result["intent_analysis"]["outcome"] == "error"
    assert result["intent_analysis"]["cron_expr"] is None
    assert result["intent_analysis"]["reason"] == result["message"]
    assert "未完成创建" in result["intent_analysis"]["summary"]
    assert summarizer_called is False


@pytest.mark.asyncio
async def test_delete_inspection_task_removes_task(session_factory):
    task = await create_inspection_task(
        name="Peets Daily Inspection",
        source_conversation_id=None,
        agent_id="dba",
        skill_id="volcengine-rds-health-analyzer",
        prompt_template="Inspect peets-prod-pos-mysql for the last 7 days",
        target_payload={"instance_name": "peets-prod-pos-mysql"},
        cron_expr="0 9 * * *",
        enabled=True,
        now=datetime(2026, 3, 11, 8, 0),
        session_factory=session_factory,
    )

    await delete_inspection_task(task.id, session_factory=session_factory)

    async with session_factory() as session:
        stored_task = await session.get(InspectionTask, task.id)

    assert stored_task is None


@pytest.mark.asyncio
async def test_delete_inspection_task_raises_for_missing_task(session_factory):
    with pytest.raises(LookupError, match="inspection task not found"):
        await delete_inspection_task("missing-task-id", session_factory=session_factory)


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
        prompt_template="Inspect peets-prod-pos-mysql for the last 7 days",
        target_payload={"instance_name": "peets-prod-pos-mysql"},
        cron_expr="0 9 * * *",
        enabled=True,
        now=datetime(2026, 3, 11, 8, 0),
        session_factory=session_factory,
    )

    async def fake_agent_runner(*, user_message, conv_id, on_event, agent_id=None):
        assert user_message == "Inspect peets-prod-pos-mysql for the last 7 days"
        assert agent_id == "dba"
        await on_event({"type": "text_delta", "content": "Inspection complete", "agent_id": "dba"})
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
    assert messages[0].content == "Inspect peets-prod-pos-mysql for the last 7 days"
    assert messages[1].content == "Inspection complete"
