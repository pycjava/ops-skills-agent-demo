from datetime import datetime, timezone
import secrets
from typing import Any
from urllib.parse import urlencode

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from auth.config import get_auth_settings
from auth.permissions import (
    PERMISSION_DESCRIPTIONS,
    ROLE_DESCRIPTIONS,
    ROLE_PERMISSIONS,
    all_permissions,
)
from db.session import AsyncSessionLocal
from models import Permission, Role, User


AUTH_SESSION_USER_ID_KEY = "user_id"
AUTH_SESSION_STATE_KEY = "oidc_state"
AUTH_SESSION_NEXT_KEY = "post_auth_redirect"
AUTH_SESSION_ID_TOKEN_KEY = "oidc_id_token"
LOCAL_ADMIN_SUBJECT = "local:admin"


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def sanitize_next_path(next_path: str | None) -> str:
    candidate = (next_path or "/").strip()
    if not candidate.startswith("/") or candidate.startswith("//"):
        return "/"
    return candidate


def build_auth_response_payload(*, authenticated: bool, user: User | None = None) -> dict[str, Any]:
    settings = get_auth_settings()
    permissions = user.permission_names() if user else []
    return {
        "auth_enabled": settings.enabled,
        "authenticated": authenticated,
        "oidc_login_enabled": settings.oidc_login_enabled,
        "password_login_enabled": settings.password_login_enabled,
        "login_methods": settings.login_methods,
        "login_url": "/api/auth/login",
        "logout_url": "/api/auth/logout",
        "user": serialize_user(user) if user else None,
        "permissions": permissions,
        "available_permissions": all_permissions(),
    }


def serialize_user(user: User) -> dict[str, Any]:
    return {
        "id": user.id,
        "subject": user.subject,
        "email": user.email,
        "display_name": user.display_name,
        "roles": user.role_names(),
        "permissions": user.permission_names(),
    }


def build_authorization_url(*, oidc_configuration: dict[str, Any], state: str) -> str:
    settings = get_auth_settings()
    params = urlencode(
        {
            "client_id": settings.oidc_client_id,
            "response_type": "code",
            "redirect_uri": settings.oidc_redirect_uri,
            "scope": settings.oidc_scope,
            "state": state,
        }
    )
    return f"{oidc_configuration['authorization_endpoint']}?{params}"


def generate_login_state() -> str:
    return secrets.token_urlsafe(24)


def _require_oidc_settings():
    settings = get_auth_settings()
    if not settings.oidc_login_enabled:
        raise RuntimeError("OIDC login is disabled")
    missing = []
    if not settings.oidc_issuer_url:
        missing.append("OIDC_ISSUER_URL")
    if not settings.oidc_client_id:
        missing.append("OIDC_CLIENT_ID")
    if not settings.oidc_client_secret:
        missing.append("OIDC_CLIENT_SECRET")
    if not settings.oidc_redirect_uri:
        missing.append("OIDC_REDIRECT_URI")
    if missing:
        raise RuntimeError(
            "Missing OIDC configuration: " + ", ".join(missing)
        )
    return settings


async def fetch_oidc_configuration() -> dict[str, Any]:
    settings = _require_oidc_settings()
    discovery_url = (
        settings.oidc_issuer_url.rstrip("/") + "/.well-known/openid-configuration"
    )
    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.get(discovery_url)
        response.raise_for_status()
        return response.json()


async def exchange_authorization_code(*, code: str) -> dict[str, Any]:
    settings = _require_oidc_settings()
    oidc_configuration = await fetch_oidc_configuration()
    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.post(
            oidc_configuration["token_endpoint"],
            data={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": settings.oidc_redirect_uri,
                "client_id": settings.oidc_client_id,
                "client_secret": settings.oidc_client_secret,
            },
        )
        response.raise_for_status()
        return response.json()


async def fetch_userinfo(
    *,
    access_token: str,
    oidc_configuration: dict[str, Any],
    token_response: dict[str, Any],
) -> dict[str, Any]:
    userinfo_endpoint = oidc_configuration.get("userinfo_endpoint")
    if not userinfo_endpoint:
        raise RuntimeError("OIDC provider does not expose userinfo_endpoint")

    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.get(
            userinfo_endpoint,
            headers={"Authorization": f"Bearer {access_token}"},
        )
        response.raise_for_status()
        return response.json()


def _claim_values(claims: dict[str, Any], claim_name: str) -> list[str]:
    value: Any = claims
    for segment in claim_name.split("."):
        if not isinstance(value, dict):
            value = None
            break
        value = value.get(segment)

    if value is None and claim_name == "roles":
        realm_access = claims.get("realm_access")
        if isinstance(realm_access, dict):
            value = realm_access.get("roles")

    if isinstance(value, str):
        return [item.strip() for item in value.split(",") if item.strip()]
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    return []


def resolve_local_roles(claims: dict[str, Any]) -> list[str]:
    settings = get_auth_settings()
    local_roles: list[str] = []
    for external_role in _claim_values(claims, settings.oidc_role_claim):
        mapped = settings.oidc_role_map.get(external_role)
        if mapped and mapped in ROLE_DESCRIPTIONS and mapped not in local_roles:
            local_roles.append(mapped)
    if not local_roles and settings.default_role in ROLE_DESCRIPTIONS:
        local_roles.append(settings.default_role)
    return sorted(local_roles)


def verify_local_admin_credentials(*, username: str, password: str) -> bool:
    settings = get_auth_settings()
    if not settings.password_login_enabled:
        return False

    candidate_username = username.strip()
    if not candidate_username:
        return False

    return (
        secrets.compare_digest(candidate_username, settings.local_admin_username)
        and secrets.compare_digest(password, settings.local_admin_password)
    )


async def ensure_authorization_seed_data(session: AsyncSession) -> None:
    permission_names = {
        item[0]
        for item in (await session.execute(select(Permission.name))).all()
    }
    for permission_name, description in PERMISSION_DESCRIPTIONS.items():
        if permission_name not in permission_names:
            session.add(Permission(name=permission_name, description=description))

    role_names = {
        item[0] for item in (await session.execute(select(Role.name))).all()
    }
    for role_name, description in ROLE_DESCRIPTIONS.items():
        if role_name not in role_names:
            session.add(Role(name=role_name, description=description))

    await session.flush()

    result = await session.execute(
        select(Role).options(selectinload(Role.permissions)).order_by(Role.name)
    )
    roles = {role.name: role for role in result.scalars().unique().all()}

    permission_result = await session.execute(select(Permission).order_by(Permission.name))
    permissions = {
        permission.name: permission
        for permission in permission_result.scalars().all()
    }

    for role_name, permission_names_for_role in ROLE_PERMISSIONS.items():
        role = roles.get(role_name)
        if role is None:
            continue
        role.permissions = [
            permissions[permission_name]
            for permission_name in sorted(permission_names_for_role)
            if permission_name in permissions
        ]


async def get_user_by_id(user_id: str, *, session: AsyncSession | None = None) -> User | None:
    owns_session = session is None
    if session is None:
        session = AsyncSessionLocal()
    try:
        result = await session.execute(
            select(User)
            .options(selectinload(User.roles).selectinload(Role.permissions))
            .where(User.id == user_id)
        )
        return result.scalar_one_or_none()
    finally:
        if owns_session:
            await session.close()


async def get_user_by_subject(
    subject: str,
    *,
    session: AsyncSession | None = None,
) -> User | None:
    owns_session = session is None
    if session is None:
        session = AsyncSessionLocal()
    try:
        result = await session.execute(
            select(User)
            .options(selectinload(User.roles).selectinload(Role.permissions))
            .where(User.subject == subject)
        )
        return result.scalar_one_or_none()
    finally:
        if owns_session:
            await session.close()


async def sync_user_from_claims(
    claims: dict[str, Any],
    *,
    session: AsyncSession | None = None,
) -> User:
    subject = str(claims.get("sub") or "").strip()
    if not subject:
        raise ValueError("OIDC userinfo is missing 'sub'")

    owns_session = session is None
    if session is None:
        session = AsyncSessionLocal()

    try:
        await ensure_authorization_seed_data(session)

        user = await get_user_by_subject(subject, session=session)
        if user is None:
            user = User(subject=subject)
            session.add(user)
            await session.flush()
            user = await get_user_by_id(user.id, session=session)
            if user is None:
                raise RuntimeError("Failed to create local user")

        user.email = str(claims.get("email") or "").strip() or None
        user.display_name = (
            str(claims.get("name") or claims.get("preferred_username") or "").strip()
            or None
        )
        user.is_active = True
        user.last_login_at = _utcnow()

        local_roles = resolve_local_roles(claims)
        role_result = await session.execute(select(Role).order_by(Role.name))
        roles_by_name = {role.name: role for role in role_result.scalars().all()}
        user.roles = [
            roles_by_name[role_name]
            for role_name in local_roles
            if role_name in roles_by_name
        ]
        await session.flush()

        if owns_session:
            await session.commit()

        refreshed_user = await get_user_by_id(user.id, session=session)
        if refreshed_user is None:
            raise RuntimeError("Failed to refresh local user")
        return refreshed_user
    finally:
        if owns_session:
            await session.close()


async def sync_local_admin_user(*, session: AsyncSession | None = None) -> User:
    settings = get_auth_settings()
    owns_session = session is None
    if session is None:
        session = AsyncSessionLocal()

    try:
        await ensure_authorization_seed_data(session)

        user = await get_user_by_subject(LOCAL_ADMIN_SUBJECT, session=session)
        if user is None:
            user = User(subject=LOCAL_ADMIN_SUBJECT)
            session.add(user)
            await session.flush()
            user = await get_user_by_id(user.id, session=session)
            if user is None:
                raise RuntimeError("Failed to create local admin user")

        user.email = None
        user.display_name = settings.local_admin_display_name
        user.is_active = True
        user.last_login_at = _utcnow()

        role_result = await session.execute(select(Role).order_by(Role.name))
        roles_by_name = {role.name: role for role in role_result.scalars().all()}
        admin_role = roles_by_name.get("admin")
        if admin_role is None:
            raise RuntimeError("Missing admin role seed data")
        user.roles = [admin_role]
        await session.flush()

        if owns_session:
            await session.commit()

        refreshed_user = await get_user_by_id(user.id, session=session)
        if refreshed_user is None:
            raise RuntimeError("Failed to refresh local admin user")
        return refreshed_user
    finally:
        if owns_session:
            await session.close()
