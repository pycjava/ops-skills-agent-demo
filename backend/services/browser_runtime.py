from __future__ import annotations

import asyncio
import re
import shlex
import shutil
import subprocess
from dataclasses import dataclass
from typing import Awaitable, Callable, Sequence

from config import PROJECT_DIR


BROWSER_RUNTIME_AGENT_ID = "browser-runtime"
AGENT_BROWSER_CLI = "agent-browser"
FOLLOWUP_SCREENSHOT_TOOL_DESC = "Capturing browser screenshot after action..."
READ_ONLY_SUBCOMMANDS = frozenset(
    {
        "screenshot",
        "title",
        "url",
        "html",
        "text",
        "snapshot",
        "status",
        "ls",
        "list",
        "inspect",
        "console",
        "network",
        "cookies",
        "storage",
        "wait",
        "help",
        "install",
        "version",
    }
)
_SANITIZE_PATH_RE = re.compile(r"[^A-Za-z0-9._-]+")


@dataclass(frozen=True, slots=True)
class BrowserFollowupScreenshot:
    command: str
    args: tuple[str, ...]
    path: str


def verify_agent_browser_cli(
    *,
    which: Callable[[str], str | None] = shutil.which,
    runner: Callable[[Sequence[str]], subprocess.CompletedProcess[str]] | None = None,
) -> None:
    resolved = which(AGENT_BROWSER_CLI)
    if not resolved:
        raise RuntimeError(
            "`browser-runtime` requires the `agent-browser` CLI. "
            "Install it with `npm install -g agent-browser` and run `agent-browser install`."
        )

    check_runner = runner or _run_cli_check
    try:
        result = check_runner((resolved, "--help"))
    except OSError as exc:
        raise RuntimeError(
            "`browser-runtime` could not execute `agent-browser`. "
            "Install it with `npm install -g agent-browser` and run `agent-browser install`."
        ) from exc

    if result.returncode != 0:
        output = (result.stderr or result.stdout or "").strip() or "unknown error"
        raise RuntimeError(
            "`browser-runtime` failed the `agent-browser` startup check: "
            f"{output}. Install it with `npm install -g agent-browser` "
            "and run `agent-browser install`."
        )


def build_followup_screenshot(
    command: str,
    *,
    conversation_id: str,
    step_index: int,
) -> BrowserFollowupScreenshot | None:
    tokens = _tokenize_command(command)
    if not tokens or tokens[0].lower() != AGENT_BROWSER_CLI:
        return None

    prefix, subcommand = _extract_global_prefix(tokens)
    if not subcommand or subcommand in READ_ONLY_SUBCOMMANDS:
        return None

    safe_conversation_id = _SANITIZE_PATH_RE.sub("-", conversation_id).strip("-") or "session"
    screenshot_path = (
        f"tmp/browser-runtime-{safe_conversation_id}-step-{max(step_index, 1):03d}.png"
    )
    screenshot_args = (*prefix, "screenshot", screenshot_path)
    return BrowserFollowupScreenshot(
        command=_format_command(screenshot_args),
        args=screenshot_args,
        path=screenshot_path,
    )


async def maybe_capture_followup_screenshot(
    *,
    agent_id: str,
    tool_name: str,
    tool_input: dict[str, object] | None,
    conversation_id: str,
    step_index: int,
    emit: Callable[[dict[str, object]], Awaitable[None]],
    runner: Callable[[BrowserFollowupScreenshot], Awaitable[str]] | None = None,
) -> int:
    if agent_id != BROWSER_RUNTIME_AGENT_ID or tool_name != "execute":
        return step_index

    command = str((tool_input or {}).get("command") or "").strip()
    if not command:
        return step_index

    followup = build_followup_screenshot(
        command,
        conversation_id=conversation_id,
        step_index=step_index,
    )
    if followup is None:
        return step_index

    await run_followup_screenshot(
        followup=followup,
        agent_id=agent_id,
        emit=emit,
        runner=runner,
    )
    return step_index + 1


async def run_followup_screenshot(
    *,
    followup: BrowserFollowupScreenshot | None,
    agent_id: str,
    emit: Callable[[dict[str, object]], Awaitable[None]],
    runner: Callable[[BrowserFollowupScreenshot], Awaitable[str]] | None = None,
) -> None:
    if followup is None:
        return

    event_payload = {"command": followup.command}
    await emit(
        {
            "type": "tool_call",
            "tool_name": "execute",
            "tool_desc": FOLLOWUP_SCREENSHOT_TOOL_DESC,
            "tool_input": event_payload,
            "agent_id": agent_id,
        }
    )

    command_runner = runner or _run_followup_screenshot
    result = await command_runner(followup)

    await emit(
        {
            "type": "tool_result",
            "tool_name": "execute",
            "result": result,
            "tool_input": event_payload,
            "artifact_kind": None,
            "agent_id": agent_id,
        }
    )


def _run_cli_check(args: Sequence[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        list(args),
        cwd=PROJECT_DIR,
        capture_output=True,
        text=True,
        timeout=15,
        check=False,
    )


async def _run_followup_screenshot(followup: BrowserFollowupScreenshot) -> str:
    process = await asyncio.create_subprocess_exec(
        *followup.args,
        cwd=PROJECT_DIR,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await process.communicate()
    stdout_text = stdout.decode("utf-8", errors="replace").strip()
    stderr_text = stderr.decode("utf-8", errors="replace").strip()

    if process.returncode != 0:
        detail = stderr_text or stdout_text or f"exit code {process.returncode}"
        raise RuntimeError(f"Post-action browser screenshot failed: {detail}")

    return stdout_text or stderr_text or f"Saved screenshot to {followup.path}"


def _tokenize_command(command: str) -> list[str]:
    normalized = str(command or "").strip()
    if not normalized:
        return []
    return shlex.split(normalized, posix=True)


def _extract_global_prefix(tokens: Sequence[str]) -> tuple[tuple[str, ...], str]:
    prefix: list[str] = [tokens[0]]
    index = 1

    while index < len(tokens):
        token = tokens[index]
        if token == "--session" and index + 1 < len(tokens):
            prefix.extend([token, tokens[index + 1]])
            index += 2
            continue
        if token.startswith("-"):
            prefix.append(token)
            index += 1
            continue
        return tuple(prefix), token.lower()

    return tuple(prefix), ""


def _format_command(args: Sequence[str]) -> str:
    formatted: list[str] = []
    for arg in args:
        text = str(arg)
        if text.endswith(".png"):
            formatted.append(f'"{text}"')
            continue
        if re.search(r"\s|[\"']", text):
            escaped = text.replace('"', '\\"')
            formatted.append(f'"{escaped}"')
            continue
        formatted.append(text)
    return " ".join(formatted)
