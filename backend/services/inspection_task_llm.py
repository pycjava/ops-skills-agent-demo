from __future__ import annotations

from datetime import datetime
from typing import Any, TypeVar

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from config import MODEL_NAME
from models import Conversation, Message

StructuredModel = TypeVar("StructuredModel", bound=BaseModel)


class TaskCreationIntentResult(BaseModel):
    is_task_creation: bool = Field(
        description="Whether the current sentence is asking to create a scheduled inspection task."
    )
    cron_expr: str | None = Field(
        default=None,
        description="The inferred 5-field cron expression when the schedule is fully clear.",
    )
    error_message: str | None = Field(
        default=None,
        description="A direct Chinese error message when this is task creation but the schedule is missing or unsupported.",
    )
    clarification_prompt: str | None = Field(
        default=None,
        description="A friendly Chinese follow-up question to ask the user for missing schedule information.",
    )


class TaskConversationSummary(BaseModel):
    name: str = Field(description="A concise task title.")
    prompt_template: str = Field(
        description="The inspection prompt that should be executed each time the task runs."
    )
    skill_id: str | None = Field(
        default=None,
        description="A stable skill id only when the conversation clearly implies one.",
    )
    target_payload: dict[str, Any] | None = Field(
        default=None,
        description="Optional structured target parameters extracted from the conversation.",
    )


def _build_structured_llm() -> ChatAnthropic:
    return ChatAnthropic(
        model_name=MODEL_NAME,
        temperature=0,
    )


async def _ainvoke_structured_output(
    schema: type[StructuredModel],
    *,
    system_prompt: str,
    user_prompt: str,
) -> StructuredModel:
    llm = _build_structured_llm().with_structured_output(schema)
    result = await llm.ainvoke(
        [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_prompt),
        ]
    )
    if isinstance(result, schema):
        return result
    return schema.model_validate(result)


async def analyze_task_creation_intent(
    message: str,
    *,
    recent_messages: list[tuple[str, str]] | None = None,
    previous_context: dict[str, Any] | None = None,
) -> TaskCreationIntentResult:
    """
    Analyze whether the message is asking to create a scheduled inspection task.

    Args:
        message: The current user message to analyze
        recent_messages: Optional list of (role, content) tuples for conversation context.
                        Used to understand follow-up responses like "每月1号9点"
                        that reference a previous task creation attempt.
        previous_context: Optional context from a previous clarification-needed state.
                         Contains 'original_message' and optionally 'intent_analysis'.
    """
    today = datetime.now().strftime("%Y-%m-%d")

    context_hint = ""
    if previous_context:
        original_msg = previous_context.get("original_message", "")
        if original_msg:
            context_hint = f"\n\nPrevious task creation request: {original_msg}"

    if recent_messages or previous_context:
        system_prompt = f"""
You classify whether a user's latest sentence is asking to create a recurring inspection task.

Rules:
- Consider the conversation context to understand if this is a follow-up response providing missing information.
- If the current message is brief (e.g., "每月1号9点") and a previous message mentioned task creation, combine them contextually.
- Return a 5-field cron expression: minute hour day month weekday.
- If the sentence is not asking to create a scheduled task, set is_task_creation=false and leave cron_expr/error_message/clarification_prompt null.
- If it is asking to create a scheduled task but the recurring schedule is missing, ambiguous, one-time only, or unsupported by cron:
  - Set is_task_creation=true, cron_expr=null
  - Provide a short Chinese error_message explaining what's missing
  - Provide a friendly Chinese clarification_prompt asking the user for the missing information with examples
- Do not fabricate a schedule.
- Today is {today}. Relative one-time phrases like "tomorrow at 9" are not valid recurring cron schedules.

Examples of good clarification_prompt:
- "您希望这个定时任务在什么时间执行？例如：每天早上9点、每周一上午10点、每月1号凌晨2点等。"
- "请告诉我执行频率和具体时间，比如：每天、每周几、每月几号，以及几点几分。"
""".strip()

        context_lines = []
        if recent_messages:
            context_lines.append("Recent conversation:")
            for role, content in recent_messages:
                context_lines.append(f"[{role}] {content}")
        if context_hint:
            context_lines.append(context_hint)
        context_lines.append(f"\nCurrent message to analyze:\n{message.strip()}")
        user_prompt = "\n".join(context_lines)
    else:
        system_prompt = f"""
You classify whether a user's latest sentence is asking to create a recurring inspection task.

Rules:
- Use only the current sentence. Do not rely on conversation history for schedule inference.
- Return a 5-field cron expression: minute hour day month weekday.
- If the sentence is not asking to create a scheduled task, set is_task_creation=false and leave cron_expr/error_message/clarification_prompt null.
- If it is asking to create a scheduled task but the recurring schedule is missing, ambiguous, one-time only, or unsupported by cron:
  - Set is_task_creation=true, cron_expr=null
  - Provide a short Chinese error_message explaining what's missing
  - Provide a friendly Chinese clarification_prompt asking the user for the missing information with examples
- Do not fabricate a schedule.
- Today is {today}. Relative one-time phrases like "tomorrow at 9" are not valid recurring cron schedules.

Examples of good clarification_prompt:
- "您希望这个定时任务在什么时间执行？例如：每天早上9点、每周一上午10点、每月1号凌晨2点等。"
- "请告诉我执行频率和具体时间，比如：每天、每周几、每月几号，以及几点几分。"
""".strip()
        user_prompt = f"Current sentence:\n{message.strip()}"

    return await _ainvoke_structured_output(
        TaskCreationIntentResult,
        system_prompt=system_prompt,
        user_prompt=user_prompt,
    )


def _format_conversation_history(
    conversation: Conversation,
    messages: list[Message],
) -> str:
    lines = [
        f"Conversation title: {conversation.title}",
        f"Agent id: {conversation.agent_id}",
        "History:",
    ]

    for message in messages:
        content = (message.content or "").strip()
        if not content:
            continue
        lines.append(f"[{message.role}] {content}")

    return "\n".join(lines)


async def summarize_task_template_from_conversation(
    conversation: Conversation,
    messages: list[Message],
) -> TaskConversationSummary:
    system_prompt = """
You generate a reusable scheduled inspection task from a historical conversation.

Rules:
- Use only the supplied conversation history.
- Ignore any meta discussion about creating tasks or scheduling.
- Extract the stable inspection goal, key targets, and important constraints.
- `name` should be concise and usable as a task title.
- `prompt_template` must be a standalone inspection instruction that can be executed in a fresh conversation.
- `skill_id` should only be set when the history clearly implies a stable skill choice.
- `target_payload` should only contain stable structured fields that are explicit in the history.
- Do not include schedule information in the prompt.
""".strip()

    user_prompt = _format_conversation_history(conversation, messages)
    return await _ainvoke_structured_output(
        TaskConversationSummary,
        system_prompt=system_prompt,
        user_prompt=user_prompt,
    )
