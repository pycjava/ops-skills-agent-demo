from fastapi import APIRouter
from fastapi.responses import JSONResponse

from agent import list_agent_profiles, resolve_default_agent


router = APIRouter(prefix="/api/agents", tags=["agents"])


@router.get("")
async def list_agents():
    default_agent_id = resolve_default_agent()
    payload = [
        profile.to_dict(is_default=profile.id == default_agent_id)
        for profile in list_agent_profiles()
    ]
    return JSONResponse(payload)

