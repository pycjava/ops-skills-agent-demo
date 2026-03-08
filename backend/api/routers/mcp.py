from typing import Literal

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, field_validator

from agent import invalidate_runtime_cache
from services.mcp_registry import McpRegistryService


router = APIRouter(prefix="/api/mcp", tags=["mcp"])
service = McpRegistryService()


class McpServerCreateRequest(BaseModel):
    name: str = Field(..., description="MCP server name")
    transport: Literal["http", "sse"] = Field(..., description="MCP transport")
    url: str = Field(..., description="MCP server URL")
    enabled: bool = Field(True, description="Whether the server is enabled")
    agent_ids: list[str] = Field(default_factory=list, description="Bound agent ids")
    headers: dict[str, str] | None = Field(
        default=None, description="Optional request headers"
    )

    @field_validator("name", "url")
    @classmethod
    def _strip_required(cls, value: str) -> str:
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


class McpServerUpdateRequest(McpServerCreateRequest):
    replace_headers: bool = Field(
        False, description="Whether to replace stored headers"
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
            enabled=body.enabled,
            agent_ids=body.agent_ids,
            replace_headers=body.replace_headers,
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
