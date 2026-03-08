from collections.abc import Iterable
from datetime import datetime
from typing import Any, Literal

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from agent_profiles import get_agent_profile
from config import MCP_DEFAULT_TIMEOUT_SECONDS
from db.session import AsyncSessionLocal
from models import McpServer
from utils.logger import logger


McpTransport = Literal["http", "sse"]
McpTestStatus = Literal["untested", "ok", "error"]


class McpRegistryService:
    def __init__(self, *, timeout_seconds: float = MCP_DEFAULT_TIMEOUT_SECONDS):
        self._timeout_seconds = timeout_seconds

    async def list_servers(self) -> list[McpServer]:
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(McpServer).order_by(McpServer.created_at.desc(), McpServer.name.asc())
            )
            return list(result.scalars().all())

    async def get_server(self, server_id: str) -> McpServer | None:
        async with AsyncSessionLocal() as session:
            return await session.get(McpServer, server_id)

    async def create_server(
        self,
        *,
        name: str,
        transport: McpTransport,
        url: str,
        enabled: bool,
        agent_ids: Iterable[str],
        headers: dict[str, str] | None,
    ) -> McpServer:
        normalized_agent_ids = self._normalize_agent_ids(agent_ids)
        normalized_headers = self._normalize_headers(headers)

        record = McpServer(
            name=self._normalize_name(name),
            transport=transport,
            url=self._normalize_url(url),
            enabled=bool(enabled),
            agent_ids=normalized_agent_ids,
            headers=normalized_headers or None,
            last_test_status="untested",
            last_tested_at=None,
            last_error=None,
            last_tools=[],
        )

        async with AsyncSessionLocal() as session:
            session.add(record)
            try:
                await session.commit()
            except IntegrityError as exc:
                await session.rollback()
                raise ValueError("MCP server name already exists") from exc
            await session.refresh(record)

        logger.info(f"Created MCP server: {record.name} ({record.transport})")
        return record

    async def update_server(
        self,
        server_id: str,
        *,
        name: str,
        transport: McpTransport,
        url: str,
        enabled: bool,
        agent_ids: Iterable[str],
        replace_headers: bool,
        headers: dict[str, str] | None,
    ) -> McpServer:
        async with AsyncSessionLocal() as session:
            record = await session.get(McpServer, server_id)
            if record is None:
                raise LookupError("MCP server not found")

            record.name = self._normalize_name(name)
            record.transport = transport
            record.url = self._normalize_url(url)
            record.enabled = bool(enabled)
            record.agent_ids = self._normalize_agent_ids(agent_ids)
            if replace_headers:
                normalized_headers = self._normalize_headers(headers)
                record.headers = normalized_headers or None

            record.last_test_status = "untested"
            record.last_tested_at = None
            record.last_error = None
            record.last_tools = []

            try:
                await session.commit()
            except IntegrityError as exc:
                await session.rollback()
                raise ValueError("MCP server name already exists") from exc

            await session.refresh(record)

        logger.info(f"Updated MCP server: {record.name} ({record.transport})")
        return record

    async def delete_server(self, server_id: str) -> None:
        async with AsyncSessionLocal() as session:
            record = await session.get(McpServer, server_id)
            if record is None:
                raise LookupError("MCP server not found")

            await session.delete(record)
            await session.commit()

        logger.info(f"Deleted MCP server: {server_id}")

    async def get_agent_connections(self, agent_id: str) -> dict[str, dict[str, object]]:
        get_agent_profile(agent_id)

        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(McpServer)
                .where(McpServer.enabled.is_(True))
                .order_by(McpServer.created_at.asc(), McpServer.name.asc())
            )
            servers = result.scalars().all()

        connections: dict[str, dict[str, object]] = {}
        for server in servers:
            if agent_id not in (server.agent_ids or []):
                continue
            connections[server.name] = server.to_connection_dict(
                timeout=self._timeout_seconds
            )
        return connections

    async def test_server(self, server_id: str) -> dict[str, Any]:
        from langchain_mcp_adapters.client import MultiServerMCPClient

        async with AsyncSessionLocal() as session:
            record = await session.get(McpServer, server_id)
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
                record.last_test_status = "ok"
                record.last_tested_at = tested_at
                record.last_error = None
                record.last_tools = tool_previews
                await session.commit()
                await session.refresh(record)
                logger.info(
                    f"MCP test succeeded: {record.name}, tools={len(tool_previews)}"
                )
                return {
                    "ok": True,
                    "tested_at": tested_at.isoformat(timespec="milliseconds"),
                    "error": None,
                    "tools": tool_previews,
                    "server": record.to_public_dict(),
                }
            except Exception as exc:
                error_message = str(exc).strip() or exc.__class__.__name__
                record.last_test_status = "error"
                record.last_tested_at = tested_at
                record.last_error = error_message
                record.last_tools = []
                await session.commit()
                await session.refresh(record)
                logger.warning(f"MCP test failed: {record.name}, error={error_message}")
                return {
                    "ok": False,
                    "tested_at": tested_at.isoformat(timespec="milliseconds"),
                    "error": error_message,
                    "tools": [],
                    "server": record.to_public_dict(),
                }

    @staticmethod
    def _normalize_name(value: str) -> str:
        normalized = str(value or "").strip()
        if not normalized:
            raise ValueError("MCP server name is required")
        return normalized

    @staticmethod
    def _normalize_url(value: str) -> str:
        normalized = str(value or "").strip()
        if not normalized:
            raise ValueError("MCP server url is required")
        if not (
            normalized.startswith("http://") or normalized.startswith("https://")
        ):
            raise ValueError("MCP server url must start with http:// or https://")
        return normalized

    @staticmethod
    def _normalize_agent_ids(agent_ids: Iterable[str]) -> list[str]:
        normalized: list[str] = []
        seen: set[str] = set()
        for raw_agent_id in agent_ids:
            agent_id = str(raw_agent_id or "").strip()
            if not agent_id or agent_id in seen:
                continue
            get_agent_profile(agent_id)
            normalized.append(agent_id)
            seen.add(agent_id)

        if not normalized:
            raise ValueError("At least one agent_id is required")
        return normalized

    @staticmethod
    def _normalize_headers(headers: dict[str, str] | None) -> dict[str, str]:
        if not headers:
            return {}

        normalized: dict[str, str] = {}
        for raw_key, raw_value in headers.items():
            key = str(raw_key or "").strip()
            value = str(raw_value or "").strip()
            if not key:
                continue
            normalized[key] = value
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
