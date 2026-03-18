import pytest

from services import browser_runtime


def test_build_followup_screenshot_returns_none_for_non_browser_actions():
    assert (
        browser_runtime.build_followup_screenshot(
            "echo hello",
            conversation_id="conv-1",
            step_index=1,
        )
        is None
    )
    assert (
        browser_runtime.build_followup_screenshot(
            "agent-browser screenshot tmp/already-shot.png",
            conversation_id="conv-1",
            step_index=1,
        )
        is None
    )
    assert (
        browser_runtime.build_followup_screenshot(
            "agent-browser title",
            conversation_id="conv-1",
            step_index=1,
        )
        is None
    )


def test_build_followup_screenshot_preserves_session_and_uses_step_path():
    followup = browser_runtime.build_followup_screenshot(
        'agent-browser --session review click "#submit"',
        conversation_id="conv-1",
        step_index=1,
    )

    assert followup is not None
    assert followup.path == "tmp/browser-runtime-conv-1-step-001.png"
    assert followup.args == (
        "agent-browser",
        "--session",
        "review",
        "screenshot",
        "tmp/browser-runtime-conv-1-step-001.png",
    )
    assert (
        followup.command
        == 'agent-browser --session review screenshot "tmp/browser-runtime-conv-1-step-001.png"'
    )


@pytest.mark.asyncio
async def test_run_followup_screenshot_emits_execute_events():
    emitted = []

    async def capture_event(event):
        emitted.append(event)

    async def fake_runner(followup):
        assert (
            followup.command
            == 'agent-browser --session review screenshot "tmp/browser-runtime-conv-1-step-001.png"'
        )
        return "Saved screenshot"

    followup = browser_runtime.build_followup_screenshot(
        'agent-browser --session review click "#submit"',
        conversation_id="conv-1",
        step_index=1,
    )

    await browser_runtime.run_followup_screenshot(
        followup=followup,
        agent_id="browser-runtime",
        emit=capture_event,
        runner=fake_runner,
    )

    assert emitted == [
        {
            "type": "tool_call",
            "tool_name": "execute",
            "tool_desc": "Capturing browser screenshot after action...",
            "tool_input": {
                "command": 'agent-browser --session review screenshot "tmp/browser-runtime-conv-1-step-001.png"'
            },
            "agent_id": "browser-runtime",
        },
        {
            "type": "tool_result",
            "tool_name": "execute",
            "result": "Saved screenshot",
            "tool_input": {
                "command": 'agent-browser --session review screenshot "tmp/browser-runtime-conv-1-step-001.png"'
            },
            "artifact_kind": None,
            "agent_id": "browser-runtime",
        },
    ]


def test_verify_agent_browser_cli_reports_install_guidance_when_missing():
    with pytest.raises(RuntimeError, match="npm install -g agent-browser"):
        browser_runtime.verify_agent_browser_cli(which=lambda _: None)
