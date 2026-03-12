import pytest

from models import Conversation, Message
from services import inspection_task_llm
from services.inspection_task_llm import TaskConversationSummary


@pytest.mark.asyncio
async def test_summarize_task_template_prompt_requires_action_and_specific_object(monkeypatch):
    captured: dict[str, str] = {}

    async def fake_ainvoke_structured_output(schema, *, system_prompt: str, user_prompt: str):
        captured["schema_name"] = schema.__name__
        captured["system_prompt"] = system_prompt
        captured["user_prompt"] = user_prompt
        return TaskConversationSummary(
            name="巡检 prod-kafka 集群消费堆积",
            prompt_template="巡检 prod-kafka 集群消费堆积",
            skill_id=None,
            target_payload=None,
        )

    monkeypatch.setattr(
        inspection_task_llm,
        "_ainvoke_structured_output",
        fake_ainvoke_structured_output,
    )

    conversation = Conversation(
        title="Kafka backlog troubleshooting",
        source="web",
        agent_id="ops",
    )
    messages = [
        Message(
            conversation_id="conv-1",
            role="user",
            content="请检查 prod-kafka 集群的消费堆积，重点看 payment-events topic。",
            type="text",
            agent_id="ops",
        )
    ]

    summary = await inspection_task_llm.summarize_task_template_from_conversation(
        conversation,
        messages,
    )

    assert summary.name == "巡检 prod-kafka 集群消费堆积"
    assert captured["schema_name"] == "TaskConversationSummary"
    assert "primary action and specific object" in captured["system_prompt"]
    assert "instance names, service names, cluster names, topic names, and hostnames" in captured[
        "system_prompt"
    ]
    assert "Prefer titles like" in captured["system_prompt"]
    assert "Conversation title: Kafka backlog troubleshooting" in captured["user_prompt"]
    assert "[user] 请检查 prod-kafka 集群的消费堆积，重点看 payment-events topic。" in captured[
        "user_prompt"
    ]
