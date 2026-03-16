from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, field_validator

from agent import invalidate_runtime_cache
from auth.dependencies import require_permission
from services.mcp_registry import McpRegistryService


router = APIRouter(prefix="/api/mcp", tags=["mcp"])
service = McpRegistryService()


class McpConfigUpdateRequest(BaseModel):
    config_text: str = Field(..., description="Raw mcp.json document")

    @field_validator("config_text")
    @classmethod
    def _validate_config_text(cls, value: str) -> str:
        normalized = str(value or "").strip()
        if not normalized:
            raise ValueError("config_text is required")
        return value


@router.get("/config", dependencies=[Depends(require_permission("mcp_servers:read"))])
async def get_mcp_config():
    records = await service.list_servers()
    return JSONResponse(
        {
            "config_text": await service.load_config_text(),
            "servers": [record.to_public_dict() for record in records],
        }
    )


@router.put("/config", dependencies=[Depends(require_permission("mcp_servers:write"))])
async def update_mcp_config(body: McpConfigUpdateRequest):
    try:
        config_text, records = await service.save_config_text(body.config_text)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    await invalidate_runtime_cache()
    return JSONResponse(
        {
            "config_text": config_text,
            "servers": [record.to_public_dict() for record in records],
        }
    )


@router.get("/servers", dependencies=[Depends(require_permission("mcp_servers:read"))])
async def list_mcp_servers():
    records = await service.list_servers()
    return JSONResponse([record.to_public_dict() for record in records])


@router.post(
    "/servers/{server_name}/test",
    dependencies=[Depends(require_permission("mcp_servers:test"))],
)
async def test_mcp_server(server_name: str):
    try:
        result = await service.test_server(server_name)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    if result.get("ok"):
        await invalidate_runtime_cache()
    return JSONResponse(result)
