from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class ToolResultRecord:
    tool_name: str
    tool_input: dict[str, Any] | None
    artifact_kind: str | None
    result: str


@dataclass(frozen=True, slots=True)
class AgentEventSnapshot:
    text: str
    thinking: str
    tool_results: list[ToolResultRecord]


@dataclass
class AgentEventState:
    text: str = ""
    thinking: str = ""
    _step_thinking: str = ""
    _pending_tool_inputs: dict[str, deque[dict[str, Any]]] = field(
        default_factory=lambda: defaultdict(deque)
    )
    _tool_results: list[ToolResultRecord] = field(default_factory=list)

    def apply_event(self, event: dict[str, Any]) -> dict[str, Any]:
        normalized_event = dict(event)
        event_type = normalized_event.get("type")

        if event_type == "text_delta":
            self.text += str(normalized_event.get("content", ""))
            return normalized_event

        if event_type == "thinking_delta":
            content = str(normalized_event.get("content", ""))
            self.thinking += content
            self._step_thinking += content
            return normalized_event

        if event_type == "tool_call":
            tool_name = str(normalized_event.get("tool_name", "") or "").strip()
            tool_input = normalized_event.get("tool_input")
            if tool_name and isinstance(tool_input, dict):
                self._pending_tool_inputs[tool_name].append(tool_input)
            return normalized_event

        if event_type == "tool_result":
            tool_name = str(normalized_event.get("tool_name", "") or "").strip()
            tool_input = normalized_event.get("tool_input")
            resolved_input = self._resolve_tool_input(tool_name, tool_input)
            normalized_event["tool_input"] = resolved_input
            self._tool_results.append(
                ToolResultRecord(
                    tool_name=tool_name,
                    tool_input=resolved_input,
                    artifact_kind=self._optional_text(normalized_event.get("artifact_kind")),
                    result=str(normalized_event.get("result", "")),
                )
            )
            return normalized_event

        return normalized_event

    def pop_step_thinking(self) -> str | None:
        if not self._step_thinking:
            return None
        step_thinking = self._step_thinking
        self._step_thinking = ""
        return step_thinking

    def snapshot(self) -> AgentEventSnapshot:
        return AgentEventSnapshot(
            text=self.text,
            thinking=self.thinking,
            tool_results=list(self._tool_results),
        )

    def _resolve_tool_input(
        self, tool_name: str, tool_input: Any
    ) -> dict[str, Any] | None:
        if not tool_name:
            return tool_input if isinstance(tool_input, dict) else None

        queued_inputs = self._pending_tool_inputs.get(tool_name)
        if isinstance(tool_input, dict):
            if queued_inputs:
                queued_inputs.popleft()
                if not queued_inputs:
                    self._pending_tool_inputs.pop(tool_name, None)
            return tool_input

        if queued_inputs:
            resolved = queued_inputs.popleft()
            if not queued_inputs:
                self._pending_tool_inputs.pop(tool_name, None)
            return resolved

        return None

    @staticmethod
    def _optional_text(value: Any) -> str | None:
        if value is None:
            return None
        text = str(value).strip()
        return text or None

