import uuid
from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from db.base_class import Base


class McpServer(Base):
    __tablename__ = "mcp_servers"
    __table_args__ = (UniqueConstraint("name", name="uq_mcp_servers_name"),)

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    transport: Mapped[str] = mapped_column(String(20), nullable=False)
    url: Mapped[str | None] = mapped_column(Text, nullable=True)
    command: Mapped[str | None] = mapped_column(Text, nullable=True)
    args: Mapped[list[str]] = mapped_column(
        JSON, default=list, nullable=False, server_default="[]"
    )
    env: Mapped[dict[str, str] | None] = mapped_column(JSON, nullable=True)
    enabled: Mapped[bool] = mapped_column(
        Boolean, default=True, server_default="1", nullable=False
    )
    agent_ids: Mapped[list[str]] = mapped_column(
        JSON, default=list, nullable=False, server_default="[]"
    )
    headers: Mapped[dict[str, str] | None] = mapped_column(JSON, nullable=True)
    last_test_status: Mapped[str] = mapped_column(
        String(20), default="untested", server_default="untested", nullable=False
    )
    last_tested_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_tools: Mapped[list[dict[str, str]]] = mapped_column(
        JSON, default=list, nullable=False, server_default="[]"
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    def to_public_dict(self) -> dict[str, object]:
        header_keys = sorted(
            key
            for key in (self.headers or {}).keys()
            if isinstance(key, str) and key.strip()
        )
        env_keys = sorted(
            key
            for key in (self.env or {}).keys()
            if isinstance(key, str) and key.strip()
        )
        tools = []
        for item in self.last_tools or []:
            if not isinstance(item, dict):
                continue
            name = str(item.get("name") or "").strip()
            description = str(item.get("description") or "").strip()
            if not name:
                continue
            tools.append({"name": name, "description": description})

        return {
            "id": self.id,
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
            "last_tools": tools,
            "created_at": (
                self.created_at.isoformat(timespec="milliseconds")
                if self.created_at
                else None
            ),
            "updated_at": (
                self.updated_at.isoformat(timespec="milliseconds")
                if self.updated_at
                else None
            ),
        }

    def to_connection_dict(self, *, timeout: float) -> dict[str, object]:
        if self.transport == "stdio":
            payload: dict[str, object] = {
                "transport": "stdio",
                "command": self.command,
                "args": list(self.args or []),
            }
            if self.env:
                payload["env"] = {
                    str(key): str(value)
                    for key, value in self.env.items()
                    if str(key).strip()
                }
            return payload
        else:
            payload: dict[str, object] = {
                "transport": self.transport,
                "url": self.url,
                "timeout": timeout,
            }
            if self.headers:
                payload["headers"] = {
                    str(key): str(value)
                    for key, value in self.headers.items()
                    if str(key).strip()
                }
            return payload
