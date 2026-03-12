from typing import Literal

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, field_validator, model_validator

from agent import invalidate_runtime_cache
from services.mcp_registry import McpRegistryService


router = APIRouter(prefix="/api/mcp", tags=["mcp"])
service = McpRegistryService()


class McpServerCreateRequest(BaseModel):
    name: str = Field(..., description="MCP server name")
    transport: Literal["http", "sse", "stdio"] = Field(..., description="MCP transport")
    url: str | None = Field(None, description="MCP server URL (required for http/sse)")
    command: str | None = Field(None, description="Command to start MCP server (required for stdio)")
    args: list[str] = Field(default_factory=list, description="Command arguments (for stdio)")
    env: dict[str, str] | None = Field(None, description="Environment variables (for stdio)")
    enabled: bool = Field(True, description="Whether the server is enabled")
    agent_ids: list[str] = Field(default_factory=list, description="Bound agent ids")
    headers: dict[str, str] | None = Field(
        default=None, description="Optional request headers (for http/sse)"
    )

    @field_validator("name")
    @classmethod
    def _strip_name(cls, value: str) -> str:
        normalized = str(value or "").strip()
        if not normalized:
            raise ValueError("Field is required")
        return normalized

    @field_validator("agent_ids")
    @classmethod
    def _normalize_agent_ids(cls, value: list[str]) -> list[str]:
        return [str(item or "").strip() for item in value]

    @field_validator("headers")
    @classmethod
    def _normalize_headers(
        cls, value: dict[str, str] | None
    ) -> dict[str, str] | None:
        if value is None:
            return None
        return {str(key): str(item) for key, item in value.items()}

    @field_validator("env")
    @classmethod
    def _normalize_env(
        cls, value: dict[str, str] | None
    ) -> dict[str, str] | None:
        if value is None:
            return None
        return {str(key): str(item) for key, item in value.items()}

    @model_validator(mode="after")
    def _validate_transport_fields(self):
        if self.transport == "stdio":
            if not self.command or not self.command.strip():
                raise ValueError("command is required for stdio transport")
        else:
            if not self.url or not self.url.strip():
                raise ValueError("url is required for http/sse transport")
        return self


class McpServerUpdateRequest(McpServerCreateRequest):
    replace_headers: bool = Field(
        False, description="Whether to replace stored headers"
    )
    replace_env: bool = Field(
        False, description="Whether to replace stored env variables"
    )


@router.get("/servers")
async def list_mcp_servers():
    records = await service.list_servers()
    return JSONResponse([record.to_public_dict() for record in records])


@router.post("/servers")
async def create_mcp_server(body: McpServerCreateRequest):
    try:
        record = await service.create_server(
            name=body.name,
            transport=body.transport,
            url=body.url,
            command=body.command,
            args=body.args,
            env=body.env,
            enabled=body.enabled,
            agent_ids=body.agent_ids,
            headers=body.headers,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    await invalidate_runtime_cache()
    return JSONResponse(record.to_public_dict())


@router.put("/servers/{server_id}")
async def update_mcp_server(server_id: str, body: McpServerUpdateRequest):
    try:
        record = await service.update_server(
            server_id,
            name=body.name,
            transport=body.transport,
            url=body.url,
            command=body.command,
            args=body.args,
            env=body.env,
            enabled=body.enabled,
            agent_ids=body.agent_ids,
            replace_headers=body.replace_headers,
            replace_env=body.replace_env,
            headers=body.headers,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    await invalidate_runtime_cache()
    return JSONResponse(record.to_public_dict())


@router.delete("/servers/{server_id}")
async def delete_mcp_server(server_id: str):
    try:
        await service.delete_server(server_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    await invalidate_runtime_cache()
    return JSONResponse({"ok": True})


@router.post("/servers/{server_id}/test")
async def test_mcp_server(server_id: str):
    try:
        result = await service.test_server(server_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    if result.get("ok"):
        await invalidate_runtime_cache()
    return JSONResponse(result)
