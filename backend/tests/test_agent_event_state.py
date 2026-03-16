from services.agent_event_state import AgentEventState


def test_agent_event_state_matches_tool_inputs_and_builds_snapshot():
    state = AgentEventState()

    state.apply_event({"type": "thinking_delta", "content": "先思考"})
    state.apply_event({"type": "text_delta", "content": "最终回答"})

    state.apply_event(
        {
            "type": "tool_call",
            "tool_name": "read_file",
            "tool_input": {"path": "/tmp/demo.md"},
        }
    )

    resolved = state.apply_event(
        {
            "type": "tool_result",
            "tool_name": "read_file",
            "tool_input": None,
            "artifact_kind": "memory",
            "result": "ok",
        }
    )

    assert state.pop_step_thinking() == "先思考"
    assert resolved["tool_input"] == {"path": "/tmp/demo.md"}

    snapshot = state.snapshot()

    assert snapshot.text == "最终回答"
    assert snapshot.thinking == "先思考"
    assert len(snapshot.tool_results) == 1
    assert snapshot.tool_results[0].tool_name == "read_file"
    assert snapshot.tool_results[0].tool_input == {"path": "/tmp/demo.md"}
    assert snapshot.tool_results[0].artifact_kind == "memory"
    assert snapshot.tool_results[0].result == "ok"


def test_pop_step_thinking_clears_only_current_step():
    state = AgentEventState()

    state.apply_event({"type": "thinking_delta", "content": "A"})
    assert state.pop_step_thinking() == "A"
    assert state.pop_step_thinking() is None

    state.apply_event({"type": "thinking_delta", "content": "B"})
    snapshot = state.snapshot()

    assert snapshot.thinking == "AB"
    assert state.pop_step_thinking() == "B"

