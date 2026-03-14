import json
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Literal

from agent_profiles import resolve_known_agent_id
from config import MCP_CONFIG_PATH, MCP_DEFAULT_TIMEOUT_SECONDS
from utils.logger import logger


McpTransport = Literal["http", "sse", "stdio"]
McpTestStatus = Literal["untested", "ok", "error"]


@dataclass(slots=True)
class McpTestState:
    status: McpTestStatus = "untested"
    tested_at: datetime | None = None
    error: str | None = None
    tools: list[dict[str, str]] = field(default_factory=list)


@dataclass(slots=True)
class McpServerRecord:
    name: str
    transport: McpTransport
    url: str | None = None
    command: str | None = None
    args: list[str] = field(default_factory=list)
    env: dict[str, str] | None = None
    enabled: bool = True
    agent_ids: list[str] = field(default_factory=list)
    headers: dict[str, str] | None = None
    last_test_status: McpTestStatus = "untested"
    last_tested_at: datetime | None = None
    last_error: str | None = None
    last_tools: list[dict[str, str]] = field(default_factory=list)

    def to_public_dict(self) -> dict[str, object]:
        header_keys = sorted(
            key
            for key in (self.headers or {}).keys()
            if isinstance(key, str) and key.strip()
        )
        env_keys = sorted(
            key for key in (self.env or {}).keys() if isinstance(key, str) and key.strip()
        )

        return {
            "id": self.name,
            "name": self.name,
            "transport": self.transport,
            "url": self.url,
            "command": self.command,
            "args": list(self.args or []),
            "env": self.env,
            "has_env": bool(env_keys),
            "env_keys": env_keys,
            "enabled": self.enabled,
            "agent_ids": list(self.agent_ids or []),
            "has_headers": bool(header_keys),
            "header_keys": header_keys,
            "last_test_status": self.last_test_status,
            "last_tested_at": (
                self.last_tested_at.isoformat(timespec="milliseconds")
                if self.last_tested_at
                else None
            ),
            "last_error": self.last_error,
            "last_tools": list(self.last_tools or []),
        }

    def to_connection_dict(self, *, timeout: float) -> dict[str, object]:
        if self.transport == "stdio":
            payload: dict[str, object] = {
                "transport": "stdio",
                "command": self.command,
                "args": list(self.args or []),
            }
            if self.env:
                payload["env"] = dict(self.env)
            return payload

        payload = {
            "transport": self.transport,
            "url": self.url,
            "timeout": timeout,
        }
        if self.headers:
            payload["headers"] = dict(self.headers)
        return payload


class McpRegistryService:
    def __init__(
        self,
        *,
        config_path: str | Path = MCP_CONFIG_PATH,
        timeout_seconds: float = MCP_DEFAULT_TIMEOUT_SECONDS,
    ):
        self._config_path = Path(config_path)
        self._timeout_seconds = timeout_seconds
        self._test_states: dict[str, McpTestState] = {}

    async def load_config_text(self) -> str:
        if not self._config_path.exists():
            return self._default_config_text()
        return self._config_path.read_text(encoding="utf-8")

    async def list_servers(self) -> list[McpServerRecord]:
        _document, servers = self._parse_config_text(await self.load_config_text())
        return servers

    async def get_server(self, server_name: str) -> McpServerRecord | None:
        for record in await self.list_servers():
            if record.name == server_name:
                return record
        return None

    async def save_config_text(
        self, config_text: str
    ) -> tuple[str, list[McpServerRecord]]:
        document, servers = self._parse_config_text(config_text)
        normalized_text = self._serialize_config_document(document)
        self._config_path.write_text(normalized_text, encoding="utf-8")
        self._test_states.clear()
        logger.info(f"Saved MCP config: {self._config_path}")
        return normalized_text, servers

    async def get_agent_connections(self, agent_id: str) -> dict[str, dict[str, object]]:
        resolved_agent_id = resolve_known_agent_id(agent_id)

        connections: dict[str, dict[str, object]] = {}
        for server in await self.list_servers():
            if not server.enabled:
                continue
            if server.agent_ids and resolved_agent_id not in server.agent_ids:
                continue
            connections[server.name] = server.to_connection_dict(
                timeout=self._timeout_seconds
            )
        return connections

    async def test_server(self, server_name: str) -> dict[str, Any]:
        from langchain_mcp_adapters.client import MultiServerMCPClient

        record = await self.get_server(server_name)
        if record is None:
            raise LookupError("MCP server not found")

        connection = {
            record.name: record.to_connection_dict(timeout=self._timeout_seconds)
        }
        client = MultiServerMCPClient(connection, tool_name_prefix=True)
        tested_at = datetime.now()

        try:
            tools = await client.get_tools(server_name=record.name)
            tool_previews = self._serialize_tools(tools)
            self._test_states[record.name] = McpTestState(
                status="ok",
                tested_at=tested_at,
                error=None,
                tools=tool_previews,
            )
            refreshed = await self.get_server(record.name)
            logger.info(
                f"MCP test succeeded: {record.name}, tools={len(tool_previews)}"
            )
            return {
                "ok": True,
                "tested_at": tested_at.isoformat(timespec="milliseconds"),
                "error": None,
                "tools": tool_previews,
                "server": refreshed.to_public_dict() if refreshed else None,
            }
        except Exception as exc:
            error_message = str(exc).strip() or exc.__class__.__name__
            self._test_states[record.name] = McpTestState(
                status="error",
                tested_at=tested_at,
                error=error_message,
                tools=[],
            )
            refreshed = await self.get_server(record.name)
            logger.warning(f"MCP test failed: {record.name}, error={error_message}")
            return {
                "ok": False,
                "tested_at": tested_at.isoformat(timespec="milliseconds"),
                "error": error_message,
                "tools": [],
                "server": refreshed.to_public_dict() if refreshed else None,
            }

    def _parse_config_text(
        self, config_text: str
    ) -> tuple[dict[str, Any], list[McpServerRecord]]:
        try:
            document = json.loads(config_text or "")
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid JSON: {exc.msg}") from exc

        if not isinstance(document, dict):
            raise ValueError("MCP config must be a JSON object")

        mcp_servers = document.get("mcpServers")
        if not isinstance(mcp_servers, dict):
            raise ValueError('"mcpServers" must be a JSON object')

        normalized_document = dict(document)
        normalized_servers: dict[str, dict[str, Any]] = {}
        records: list[McpServerRecord] = []

        for raw_name, raw_server in mcp_servers.items():
            name = self._normalize_name(raw_name)
            if not isinstance(raw_server, dict):
                raise ValueError(f'MCP server "{name}" must be a JSON object')
            normalized_entry = dict(raw_server)
            record = self._parse_server(name, normalized_entry)
            normalized_servers[name] = normalized_entry
            records.append(self._with_test_state(record))

        normalized_document["mcpServers"] = normalized_servers
        return normalized_document, records

    def _parse_server(self, name: str, entry: dict[str, Any]) -> McpServerRecord:
        raw_command = entry.get("command")
        command = str(raw_command or "").strip() if raw_command is not None else ""
        raw_url = entry.get("url")
        url = str(raw_url or "").strip() if raw_url is not None else ""

        if not command and not url:
            raise ValueError(f'MCP server "{name}" must provide command or url')

        transport = self._resolve_transport(entry, command=command, url=url, name=name)
        args = self._normalize_args(entry.get("args"), name=name)
        env = self._normalize_mapping(entry.get("env"), field_name="env", name=name)
        headers = self._normalize_mapping(
            entry.get("headers"), field_name="headers", name=name
        )
        enabled = self._normalize_enabled(entry.get("enabled"))
        agent_ids = self._normalize_agent_ids(entry.get("agentIds"), name=name)

        entry["enabled"] = enabled
        entry["agentIds"] = list(agent_ids)

        if transport == "stdio":
            if not command:
                raise ValueError(f'MCP server "{name}" command is required')
            if raw_url not in (None, ""):
                raise ValueError(
                    f'MCP server "{name}" cannot define both command and url'
                )
            return McpServerRecord(
                name=name,
                transport="stdio",
                command=command,
                args=args,
                env=env or None,
                enabled=enabled,
                agent_ids=agent_ids,
            )

        if not url:
            raise ValueError(f'MCP server "{name}" url is required')
        if raw_command not in (None, ""):
            raise ValueError(f'MCP server "{name}" cannot define both command and url')
        return McpServerRecord(
            name=name,
            transport=transport,
            url=self._normalize_url(url, name=name),
            enabled=enabled,
            agent_ids=agent_ids,
            headers=headers or None,
        )

    def _with_test_state(self, record: McpServerRecord) -> McpServerRecord:
        state = self._test_states.get(record.name)
        if state is None:
            return record
        record.last_test_status = state.status
        record.last_tested_at = state.tested_at
        record.last_error = state.error
        record.last_tools = list(state.tools)
        return record

    @staticmethod
    def _default_config_text() -> str:
        return '{\n  "mcpServers": {}\n}\n'

    @staticmethod
    def _serialize_config_document(document: dict[str, Any]) -> str:
        return json.dumps(document, ensure_ascii=False, indent=2) + "\n"

    @staticmethod
    def _normalize_name(value: object) -> str:
        normalized = str(value or "").strip()
        if not normalized:
            raise ValueError("MCP server name is required")
        return normalized

    @staticmethod
    def _resolve_transport(
        entry: dict[str, Any], *, command: str, url: str, name: str
    ) -> McpTransport:
        raw_transport = entry.get("transport", entry.get("type"))
        if raw_transport is not None:
            normalized_transport = str(raw_transport or "").strip().lower()
            if normalized_transport == "stdio":
                return "stdio"
            if normalized_transport == "sse":
                return "sse"
            if normalized_transport in {"http", "streamable_http", "streamable-http"}:
                return "http"
            raise ValueError(
                f'MCP server "{name}" transport must be stdio, sse, or http'
            )

        if command and not url:
            return "stdio"
        if url and not command:
            return "http"
        raise ValueError(f'MCP server "{name}" must provide command or url')

    @staticmethod
    def _normalize_url(value: str, *, name: str) -> str:
        normalized = str(value or "").strip()
        if not normalized:
            raise ValueError(f'MCP server "{name}" url is required')
        if not (
            normalized.startswith("http://") or normalized.startswith("https://")
        ):
            raise ValueError(
                f'MCP server "{name}" url must start with http:// or https://'
            )
        return normalized

    @staticmethod
    def _normalize_args(value: Any, *, name: str) -> list[str]:
        if value is None:
            return []
        if not isinstance(value, list):
            raise ValueError(f'MCP server "{name}" args must be an array')
        return [str(item or "").strip() for item in value if str(item or "").strip()]

    @staticmethod
    def _normalize_mapping(
        value: Any, *, field_name: str, name: str
    ) -> dict[str, str]:
        if value is None:
            return {}
        if not isinstance(value, dict):
            raise ValueError(f'MCP server "{name}" {field_name} must be an object')

        normalized: dict[str, str] = {}
        for raw_key, raw_value in value.items():
            key = str(raw_key or "").strip()
            if not key:
                continue
            normalized[key] = str(raw_value or "").strip()
        return normalized

    @staticmethod
    def _normalize_enabled(value: Any) -> bool:
        if value is None:
            return True
        return bool(value)

    @staticmethod
    def _normalize_agent_ids(value: Any, *, name: str) -> list[str]:
        if value is None:
            return []
        if not isinstance(value, list):
            raise ValueError(f'MCP server "{name}" agentIds must be an array')

        normalized: list[str] = []
        seen: set[str] = set()
        for raw_agent_id in value:
            agent_id = str(raw_agent_id or "").strip()
            if not agent_id:
                continue
            resolved_agent_id = resolve_known_agent_id(agent_id)
            if resolved_agent_id in seen:
                continue
            normalized.append(resolved_agent_id)
            seen.add(resolved_agent_id)
        return normalized

    @staticmethod
    def _serialize_tools(tools: Iterable[Any]) -> list[dict[str, str]]:
        tool_previews: list[dict[str, str]] = []
        for tool in tools:
            name = str(getattr(tool, "name", "") or "").strip()
            description = str(getattr(tool, "description", "") or "").strip()
            if not name:
                continue
            tool_previews.append({"name": name, "description": description})
        return tool_previews
