from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import JSONResponse, RedirectResponse
from pydantic import BaseModel

from auth import service as auth_service
from auth.config import get_auth_settings
from auth.dependencies import get_current_user_optional
from auth.service import (
    AUTH_SESSION_ID_TOKEN_KEY,
    AUTH_SESSION_NEXT_KEY,
    AUTH_SESSION_STATE_KEY,
    AUTH_SESSION_USER_ID_KEY,
    build_auth_response_payload,
    sanitize_next_path,
)


router = APIRouter(prefix="/api/auth", tags=["auth"])


class PasswordLoginRequest(BaseModel):
    username: str
    password: str
    next: str = "/"


@router.get("/me")
async def auth_me(request: Request):
    settings = get_auth_settings()
    if not settings.enabled:
        return JSONResponse(build_auth_response_payload(authenticated=False))

    user = await get_current_user_optional(request)
    return JSONResponse(
        build_auth_response_payload(authenticated=user is not None, user=user)
    )


@router.get("/login")
async def auth_login(
    request: Request,
    next: str = Query("/", description="Relative path to redirect to after login"),
):
    settings = get_auth_settings()
    if not settings.enabled:
        raise HTTPException(status_code=404, detail="Authentication is disabled")
    if not settings.oidc_login_enabled:
        raise HTTPException(status_code=404, detail="OIDC login is disabled")

    oidc_configuration = await auth_service.fetch_oidc_configuration()
    state = auth_service.generate_login_state()
    request.session[AUTH_SESSION_STATE_KEY] = state
    request.session[AUTH_SESSION_NEXT_KEY] = sanitize_next_path(next)
    authorization_url = auth_service.build_authorization_url(
        oidc_configuration=oidc_configuration,
        state=state,
    )
    return RedirectResponse(authorization_url, status_code=307)


@router.get("/callback")
async def auth_callback(request: Request, code: str, state: str):
    settings = get_auth_settings()
    if not settings.enabled:
        raise HTTPException(status_code=404, detail="Authentication is disabled")
    if not settings.oidc_login_enabled:
        raise HTTPException(status_code=404, detail="OIDC login is disabled")

    expected_state = request.session.get(AUTH_SESSION_STATE_KEY)
    if not isinstance(expected_state, str) or expected_state != state:
        raise HTTPException(status_code=400, detail="Invalid OIDC state")

    oidc_configuration = await auth_service.fetch_oidc_configuration()
    token_response = await auth_service.exchange_authorization_code(code=code)
    access_token = str(token_response.get("access_token") or "").strip()
    if not access_token:
        raise HTTPException(status_code=502, detail="OIDC token response missing access_token")

    userinfo = await auth_service.fetch_userinfo(
        access_token=access_token,
        oidc_configuration=oidc_configuration,
        token_response=token_response,
    )
    async with auth_service.AsyncSessionLocal() as session:
        user = await auth_service.sync_user_from_claims(userinfo, session=session)
        await session.commit()

    next_path = sanitize_next_path(request.session.get(AUTH_SESSION_NEXT_KEY))
    request.session.pop(AUTH_SESSION_STATE_KEY, None)
    request.session.pop(AUTH_SESSION_NEXT_KEY, None)
    request.session[AUTH_SESSION_USER_ID_KEY] = user.id
    if token_response.get("id_token"):
        request.session[AUTH_SESSION_ID_TOKEN_KEY] = token_response["id_token"]
    return RedirectResponse(next_path, status_code=307)


@router.post("/login/password")
async def auth_password_login(request: Request, payload: PasswordLoginRequest):
    settings = get_auth_settings()
    if not settings.enabled:
        raise HTTPException(status_code=404, detail="Authentication is disabled")
    if not settings.password_login_enabled:
        raise HTTPException(status_code=404, detail="Password login is disabled")

    if not auth_service.verify_local_admin_credentials(
        username=payload.username,
        password=payload.password,
    ):
        raise HTTPException(status_code=401, detail="Invalid username or password")

    async with auth_service.AsyncSessionLocal() as session:
        user = await auth_service.sync_local_admin_user(session=session)
        await session.commit()

    redirect_target = sanitize_next_path(payload.next)
    request.session.pop(AUTH_SESSION_STATE_KEY, None)
    request.session.pop(AUTH_SESSION_NEXT_KEY, None)
    request.session.pop(AUTH_SESSION_ID_TOKEN_KEY, None)
    request.session[AUTH_SESSION_USER_ID_KEY] = user.id

    response_payload = build_auth_response_payload(authenticated=True, user=user)
    response_payload["redirect_to"] = redirect_target
    return JSONResponse(response_payload)


@router.get("/logout")
async def auth_logout(
    request: Request,
    next: str = Query("/", description="Relative path to redirect to after logout"),
):
    redirect_target = sanitize_next_path(next)
    settings = get_auth_settings()
    id_token_hint = request.session.get(AUTH_SESSION_ID_TOKEN_KEY)
    request.session.clear()

    if not settings.enabled:
        return RedirectResponse(redirect_target, status_code=307)

    try:
        oidc_configuration = await auth_service.fetch_oidc_configuration()
    except Exception:
        return RedirectResponse(redirect_target, status_code=307)

    end_session_endpoint = oidc_configuration.get("end_session_endpoint")
    if not end_session_endpoint:
        return RedirectResponse(redirect_target, status_code=307)

    params = {"post_logout_redirect_uri": redirect_target}
    if isinstance(id_token_hint, str) and id_token_hint.strip():
        params["id_token_hint"] = id_token_hint

    from urllib.parse import urlencode

    return RedirectResponse(
        f"{end_session_endpoint}?{urlencode(params)}",
        status_code=307,
    )
