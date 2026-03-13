from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse

from auth.dependencies import require_permission
from skill_catalog import list_skills
from utils.logger import logger

router = APIRouter(prefix="/api/skills", tags=["skills"])


@router.get("", dependencies=[Depends(require_permission("agents:read"))])
async def list_skills_route(agent_id: str | None = None):
    """返回已加载的 Skills 列表"""
    logger.info(f"正在获取可用技能(Skills)列表, agent_id={agent_id}")
    try:
        skills = [skill.to_dict() for skill in list_skills(agent_id)]
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    logger.debug(f"成功加载了 {len(skills)} 个技能")
    return JSONResponse(skills)

