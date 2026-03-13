import importlib
import sys
import types
from urllib.parse import parse_qs, urlparse

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.middleware.sessions import SessionMiddleware

from api.routers import conversations as conversations_router

from auth.config import get_auth_settings
from auth import dependencies as auth_dependencies
from auth import service as auth_service
from models import User


def build_test_app(
    session_factory,
    *,
    include_auth_router: bool = False,
    include_conversations_router: bool = False,
    include_chat_router: bool = False,
    monkeypatch: pytest.MonkeyPatch | None = None,
) -> FastAPI:
    get_auth_settings.cache_clear()
    settings = get_auth_settings()

    auth_dependencies.AsyncSessionLocal = session_factory
    auth_service.AsyncSessionLocal = session_factory
    conversations_router.AsyncSessionLocal = session_factory

    app = FastAPI()
    app.add_middleware(
        SessionMiddleware,
        secret_key=settings.session_secret,
        session_cookie=settings.session_cookie_name,
        same_site=settings.session_cookie_same_site,
        https_only=settings.session_cookie_secure,
    )

    if include_auth_router:
        from api.routers import auth as auth_router

        app.include_router(auth_router.router)

    if include_conversations_router:
        app.include_router(conversations_router.router)

    if include_chat_router:
        assert monkeypatch is not None
        stub_agent = types.ModuleType("agent")
        stub_agent.resolve_default_agent = lambda: "orchestrator"

        async def _run_agent(*args, **kwargs):
            return None

        stub_agent.run_agent = _run_agent
        monkeypatch.setitem(sys.modules, "agent", stub_agent)
        sys.modules.pop("api.ws.chat", None)
        chat_router = importlib.import_module("api.ws.chat")
        app.include_router(chat_router.router)

    return app


@pytest.fixture(autouse=True)
def clear_auth_settings_cache():
    get_auth_settings.cache_clear()
    yield
    get_auth_settings.cache_clear()


async def get_user_by_subject(session_factory, subject: str) -> User | None:
    async with session_factory() as session:
        return await auth_service.get_user_by_subject(subject, session=session)


def login_with_claims(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    *,
    subject: str,
    email: str,
    name: str,
    roles: list[str],
    next_path: str = "/",
):
    async def fake_fetch_oidc_configuration():
        return {
            "authorization_endpoint": "https://sso.example.com/auth",
            "token_endpoint": "https://sso.example.com/token",
            "userinfo_endpoint": "https://sso.example.com/userinfo",
            "end_session_endpoint": "https://sso.example.com/logout",
        }

    async def fake_exchange_authorization_code(*, code: str):
        assert code == "test-code"
        return {
            "access_token": "access-token",
            "id_token": "id-token",
            "token_type": "Bearer",
        }

    async def fake_fetch_userinfo(*, access_token: str, oidc_configuration: dict, token_response: dict):
        assert access_token == "access-token"
        assert oidc_configuration["userinfo_endpoint"].endswith("/userinfo")
        assert token_response["id_token"] == "id-token"
        return {
            "sub": subject,
            "email": email,
            "name": name,
            "roles": roles,
        }

    monkeypatch.setattr(auth_service, "fetch_oidc_configuration", fake_fetch_oidc_configuration)
    monkeypatch.setattr(auth_service, "exchange_authorization_code", fake_exchange_authorization_code)
    monkeypatch.setattr(auth_service, "fetch_userinfo", fake_fetch_userinfo)

    login_response = client.get(
        f"/api/auth/login?next={next_path}",
        follow_redirects=False,
    )
    assert login_response.status_code == 307

    redirect_location = login_response.headers["location"]
    parsed = urlparse(redirect_location)
    state = parse_qs(parsed.query)["state"][0]

    callback_response = client.get(
        f"/api/auth/callback?code=test-code&state={state}",
        follow_redirects=False,
    )
    assert callback_response.status_code == 307
    assert callback_response.headers["location"] == next_path


def test_conversations_route_remains_accessible_when_auth_disabled(
    session_factory,
    seeded_conversation,
    monkeypatch,
):
    monkeypatch.setenv("AUTH_ENABLED", "false")
    monkeypatch.setenv("SESSION_SECRET", "test-session-secret")
    app = build_test_app(
        session_factory,
        include_conversations_router=True,
    )
    client = TestClient(app)

    response = client.get("/api/conversations")

    assert response.status_code == 200
    assert response.json()[0]["id"] == seeded_conversation.id


def test_websocket_chat_connects_when_auth_disabled(session_factory, monkeypatch):
    monkeypatch.setenv("AUTH_ENABLED", "false")
    monkeypatch.setenv("SESSION_SECRET", "test-session-secret")
    app = build_test_app(
        session_factory,
        include_chat_router=True,
        monkeypatch=monkeypatch,
    )
    client = TestClient(app)

    with client.websocket_connect("/ws/chat"):
        pass


def test_conversations_route_requires_login_when_auth_enabled(session_factory, monkeypatch):
    monkeypatch.setenv("AUTH_ENABLED", "true")
    monkeypatch.setenv("SESSION_SECRET", "test-session-secret")
    app = build_test_app(
        session_factory,
        include_conversations_router=True,
    )
    client = TestClient(app)

    response = client.get("/api/conversations")

    assert response.status_code == 401
    assert response.json()["detail"] == "Authentication required"


def test_auth_login_callback_and_me_payload(session_factory, monkeypatch):
    monkeypatch.setenv("AUTH_ENABLED", "true")
    monkeypatch.setenv("SESSION_SECRET", "test-session-secret")
    monkeypatch.setenv("OIDC_ISSUER_URL", "https://sso.example.com/realms/agentweave")
    monkeypatch.setenv("OIDC_CLIENT_ID", "agentweave-web")
    monkeypatch.setenv("OIDC_CLIENT_SECRET", "secret-value")
    monkeypatch.setenv("OIDC_REDIRECT_URI", "http://testserver/api/auth/callback")
    app = build_test_app(
        session_factory,
        include_auth_router=True,
        monkeypatch=monkeypatch,
    )
    client = TestClient(app)

    login_with_claims(
        client,
        monkeypatch,
        subject="user-operator",
        email="operator@example.com",
        name="Operator User",
        roles=["operator"],
        next_path="/workspace",
    )

    response = client.get("/api/auth/me")

    assert response.status_code == 200
    payload = response.json()
    assert payload["auth_enabled"] is True
    assert payload["authenticated"] is True
    assert payload["oidc_login_enabled"] is True
    assert payload["password_login_enabled"] is False
    assert payload["login_methods"] == ["oidc"]
    assert payload["login_url"] == "/api/auth/login"
    assert payload["logout_url"] == "/api/auth/logout"
    assert payload["user"]["subject"] == "user-operator"
    assert payload["user"]["email"] == "operator@example.com"
    assert payload["user"]["roles"] == ["operator"]
    assert "conversations:write" in payload["permissions"]
    assert "cloud_credentials:write" not in payload["permissions"]


@pytest.mark.asyncio
async def test_callback_creates_local_user_record(session_factory, monkeypatch):
    monkeypatch.setenv("AUTH_ENABLED", "true")
    monkeypatch.setenv("SESSION_SECRET", "test-session-secret")
    monkeypatch.setenv("OIDC_ISSUER_URL", "https://sso.example.com/realms/agentweave")
    monkeypatch.setenv("OIDC_CLIENT_ID", "agentweave-web")
    monkeypatch.setenv("OIDC_CLIENT_SECRET", "secret-value")
    monkeypatch.setenv("OIDC_REDIRECT_URI", "http://testserver/api/auth/callback")
    app = build_test_app(
        session_factory,
        include_auth_router=True,
        monkeypatch=monkeypatch,
    )
    client = TestClient(app)

    login_with_claims(
        client,
        monkeypatch,
        subject="user-viewer",
        email="viewer@example.com",
        name="Viewer User",
        roles=["viewer"],
    )

    user = await get_user_by_subject(session_factory, "user-viewer")

    assert user is not None
    assert user.email == "viewer@example.com"


def test_auth_me_reports_password_and_oidc_login_methods(session_factory, monkeypatch):
    monkeypatch.setenv("AUTH_ENABLED", "true")
    monkeypatch.setenv("SESSION_SECRET", "test-session-secret")
    monkeypatch.setenv("OIDC_ISSUER_URL", "https://sso.example.com/realms/agentweave")
    monkeypatch.setenv("OIDC_CLIENT_ID", "agentweave-web")
    monkeypatch.setenv("OIDC_CLIENT_SECRET", "secret-value")
    monkeypatch.setenv("OIDC_REDIRECT_URI", "http://testserver/api/auth/callback")
    monkeypatch.setenv("LOCAL_AUTH_ENABLED", "true")
    monkeypatch.setenv("LOCAL_ADMIN_USERNAME", "admin")
    monkeypatch.setenv("LOCAL_ADMIN_PASSWORD", "password-123")
    app = build_test_app(
        session_factory,
        include_auth_router=True,
        monkeypatch=monkeypatch,
    )
    client = TestClient(app)

    response = client.get("/api/auth/me")

    assert response.status_code == 200
    payload = response.json()
    assert payload["authenticated"] is False
    assert payload["oidc_login_enabled"] is True
    assert payload["password_login_enabled"] is True
    assert payload["login_methods"] == ["oidc", "password"]


def test_password_login_sets_admin_session_and_returns_auth_payload(
    session_factory,
    monkeypatch,
):
    monkeypatch.setenv("AUTH_ENABLED", "true")
    monkeypatch.setenv("SESSION_SECRET", "test-session-secret")
    monkeypatch.setenv("LOCAL_AUTH_ENABLED", "true")
    monkeypatch.setenv("LOCAL_ADMIN_USERNAME", "admin")
    monkeypatch.setenv("LOCAL_ADMIN_PASSWORD", "password-123")
    monkeypatch.setenv("LOCAL_ADMIN_DISPLAY_NAME", "Platform Admin")
    app = build_test_app(
        session_factory,
        include_auth_router=True,
        monkeypatch=monkeypatch,
    )
    client = TestClient(app)

    response = client.post(
        "/api/auth/login/password",
        json={
            "username": "admin",
            "password": "password-123",
            "next": "/workspace",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["authenticated"] is True
    assert payload["redirect_to"] == "/workspace"
    assert payload["user"]["subject"] == "local:admin"
    assert payload["user"]["display_name"] == "Platform Admin"
    assert payload["user"]["roles"] == ["admin"]
    assert "cloud_credentials:write" in payload["permissions"]

    me_response = client.get("/api/auth/me")
    assert me_response.status_code == 200
    assert me_response.json()["user"]["subject"] == "local:admin"


def test_password_login_rejects_invalid_credentials(session_factory, monkeypatch):
    monkeypatch.setenv("AUTH_ENABLED", "true")
    monkeypatch.setenv("SESSION_SECRET", "test-session-secret")
    monkeypatch.setenv("LOCAL_AUTH_ENABLED", "true")
    monkeypatch.setenv("LOCAL_ADMIN_USERNAME", "admin")
    monkeypatch.setenv("LOCAL_ADMIN_PASSWORD", "password-123")
    app = build_test_app(
        session_factory,
        include_auth_router=True,
        monkeypatch=monkeypatch,
    )
    client = TestClient(app)

    response = client.post(
        "/api/auth/login/password",
        json={
            "username": "admin",
            "password": "wrong-password",
        },
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid username or password"


@pytest.mark.asyncio
async def test_password_login_creates_local_admin_user_record(session_factory, monkeypatch):
    monkeypatch.setenv("AUTH_ENABLED", "true")
    monkeypatch.setenv("SESSION_SECRET", "test-session-secret")
    monkeypatch.setenv("LOCAL_AUTH_ENABLED", "true")
    monkeypatch.setenv("LOCAL_ADMIN_USERNAME", "admin")
    monkeypatch.setenv("LOCAL_ADMIN_PASSWORD", "password-123")
    app = build_test_app(
        session_factory,
        include_auth_router=True,
        monkeypatch=monkeypatch,
    )
    client = TestClient(app)

    response = client.post(
        "/api/auth/login/password",
        json={
            "username": "admin",
            "password": "password-123",
        },
    )

    assert response.status_code == 200
    user = await get_user_by_subject(session_factory, "local:admin")
    assert user is not None
    assert user.role_names() == ["admin"]


def test_authenticated_user_without_permission_gets_403(
    session_factory,
    monkeypatch,
):
    monkeypatch.setenv("AUTH_ENABLED", "true")
    monkeypatch.setenv("SESSION_SECRET", "test-session-secret")
    monkeypatch.setenv("OIDC_ISSUER_URL", "https://sso.example.com/realms/agentweave")
    monkeypatch.setenv("OIDC_CLIENT_ID", "agentweave-web")
    monkeypatch.setenv("OIDC_CLIENT_SECRET", "secret-value")
    monkeypatch.setenv("OIDC_REDIRECT_URI", "http://testserver/api/auth/callback")
    app = build_test_app(
        session_factory,
        include_auth_router=True,
        include_conversations_router=True,
        monkeypatch=monkeypatch,
    )
    client = TestClient(app)

    login_with_claims(
        client,
        monkeypatch,
        subject="user-viewer",
        email="viewer@example.com",
        name="Viewer User",
        roles=["viewer"],
    )

    response = client.post("/api/conversations", json={"agent_id": "general"})

    assert response.status_code == 403
    assert response.json()["detail"] == "Missing permission: conversations:write"


def test_websocket_chat_rejects_unauthenticated_client_when_auth_enabled(
    session_factory,
    monkeypatch,
):
    monkeypatch.setenv("AUTH_ENABLED", "true")
    monkeypatch.setenv("SESSION_SECRET", "test-session-secret")
    app = build_test_app(
        session_factory,
        include_chat_router=True,
        monkeypatch=monkeypatch,
    )
    client = TestClient(app)

    with pytest.raises(Exception):
        with client.websocket_connect("/ws/chat"):
            pass
