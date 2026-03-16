from typing import Any

from fastapi import HTTPException, Request, WebSocket, status

from auth.config import get_auth_settings
from auth.service import AUTH_SESSION_USER_ID_KEY, get_user_by_id
from db.session import AsyncSessionLocal


async def get_current_user_optional(request: Request):
    settings = get_auth_settings()
    if not settings.enabled:
        return None

    session_data: dict[str, Any] = request.session
    user_id = session_data.get(AUTH_SESSION_USER_ID_KEY)
    if not isinstance(user_id, str) or not user_id.strip():
        return None

    user = await get_user_by_id(user_id)
    if user is None or not user.is_active:
        request.session.clear()
        return None
    return user


async def get_current_user(request: Request):
    user = await get_current_user_optional(request)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
        )
    return user


def require_permission(permission: str):
    async def dependency(request: Request):
        settings = get_auth_settings()
        if not settings.enabled:
            return None

        user = await get_current_user(request)
        if permission not in user.permission_names():
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Missing permission: {permission}",
            )
        return user

    return dependency


async def ensure_websocket_permission(ws: WebSocket, permission: str):
    settings = get_auth_settings()
    if not settings.enabled:
        return None

    session_data = ws.scope.get("session") or {}
    user_id = session_data.get(AUTH_SESSION_USER_ID_KEY)
    if not isinstance(user_id, str) or not user_id.strip():
        await ws.close(code=4401, reason="Authentication required")
        return None

    user = await get_user_by_id(user_id)
    if user is None or not user.is_active:
        await ws.close(code=4401, reason="Authentication required")
        return None

    if permission not in user.permission_names():
        await ws.close(code=4403, reason=f"Missing permission: {permission}")
        return None

    return user

