from typing import Any

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from auth.dependencies import require_permission
from services.cloud_credentials import (
    get_cloud_credentials_registry,
    resolve_cloud_request_context,
    save_cloud_credentials_registry,
)


router = APIRouter(prefix="/api/cloud-credentials", tags=["cloud-credentials"])


class CloudCredentialItemInput(BaseModel):
    credential_ref: str = Field(..., description="Stable credential reference")
    display_name: str = Field("", description="Human readable display name")
    note: str = Field("", description="Optional note")
    default_region: str = Field("cn-shanghai", description="Default region")
    enabled: bool = Field(True, description="Whether the credential ref is enabled")


class CloudCredentialRegistryUpdateRequest(BaseModel):
    provider: str = Field("volcengine", description="Cloud provider")
    credentials: list[CloudCredentialItemInput] = Field(default_factory=list)
    project_bindings: dict[str, str] = Field(default_factory=dict)
    instance_overrides: dict[str, str] = Field(default_factory=dict)


class CloudCredentialResolveRequest(BaseModel):
    message: str = Field(..., description="User message to resolve")
    agent_id: str = Field("db-runtime", description="Agent id for memory scope")
    credential_ref: str | None = Field(
        default=None, description="Optional explicit credential ref"
    )


@router.get(
    "/registry",
    dependencies=[Depends(require_permission("cloud_credentials:read"))],
)
async def get_registry():
    return JSONResponse(await get_cloud_credentials_registry())


@router.put(
    "/registry",
    dependencies=[Depends(require_permission("cloud_credentials:write"))],
)
async def update_registry(body: CloudCredentialRegistryUpdateRequest):
    payload: dict[str, Any] = {
        "provider": body.provider,
        "credentials": [item.model_dump() for item in body.credentials],
        "project_bindings": body.project_bindings,
        "instance_overrides": body.instance_overrides,
    }
    return JSONResponse(await save_cloud_credentials_registry(payload))


@router.post(
    "/resolve",
    dependencies=[Depends(require_permission("cloud_credentials:read"))],
)
async def resolve_registry_context(body: CloudCredentialResolveRequest):
    return JSONResponse(
        await resolve_cloud_request_context(
            body.message,
            agent_id=body.agent_id,
            credential_ref=body.credential_ref,
        )
    )
