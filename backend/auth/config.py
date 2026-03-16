from dataclasses import dataclass
from functools import lru_cache
import os


TRUE_VALUES = {"1", "true", "yes", "on"}
DEFAULT_ROLE_MAP = {
    "viewer": "viewer",
    "operator": "operator",
    "admin": "admin",
}


def _env_flag(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in TRUE_VALUES


def _parse_role_map(raw: str | None) -> dict[str, str]:
    if not raw or not raw.strip():
        return DEFAULT_ROLE_MAP.copy()

    mapping: dict[str, str] = {}
    for item in raw.split(","):
        candidate = item.strip()
        if not candidate or "=" not in candidate:
            continue
        external_role, local_role = candidate.split("=", 1)
        external_role = external_role.strip()
        local_role = local_role.strip()
        if external_role and local_role:
            mapping[external_role] = local_role
    return mapping or DEFAULT_ROLE_MAP.copy()


@dataclass(frozen=True)
class AuthSettings:
    enabled: bool
    oidc_issuer_url: str
    oidc_client_id: str
    oidc_client_secret: str
    oidc_redirect_uri: str
    oidc_scope: str
    oidc_role_claim: str
    oidc_role_map: dict[str, str]
    default_role: str
    local_auth_enabled: bool
    local_admin_username: str
    local_admin_password: str
    local_admin_display_name: str
    session_secret: str
    session_cookie_name: str
    session_cookie_same_site: str
    session_cookie_secure: bool

    @property
    def oidc_login_enabled(self) -> bool:
        return self.enabled and all(
            (
                self.oidc_issuer_url,
                self.oidc_client_id,
                self.oidc_client_secret,
                self.oidc_redirect_uri,
            )
        )

    @property
    def password_login_enabled(self) -> bool:
        return (
            self.enabled
            and self.local_auth_enabled
            and bool(self.local_admin_username)
            and bool(self.local_admin_password)
        )

    @property
    def login_methods(self) -> list[str]:
        methods: list[str] = []
        if self.oidc_login_enabled:
            methods.append("oidc")
        if self.password_login_enabled:
            methods.append("password")
        return methods


@lru_cache
def get_auth_settings() -> AuthSettings:
    return AuthSettings(
        enabled=_env_flag("AUTH_ENABLED", False),
        oidc_issuer_url=os.getenv("OIDC_ISSUER_URL", "").strip(),
        oidc_client_id=os.getenv("OIDC_CLIENT_ID", "").strip(),
        oidc_client_secret=os.getenv("OIDC_CLIENT_SECRET", "").strip(),
        oidc_redirect_uri=os.getenv("OIDC_REDIRECT_URI", "").strip(),
        oidc_scope=os.getenv("OIDC_SCOPE", "openid profile email").strip(),
        oidc_role_claim=os.getenv("OIDC_ROLE_CLAIM", "roles").strip() or "roles",
        oidc_role_map=_parse_role_map(os.getenv("OIDC_ROLE_MAP")),
        default_role=os.getenv("AUTH_DEFAULT_ROLE", "viewer").strip() or "viewer",
        local_auth_enabled=_env_flag("LOCAL_AUTH_ENABLED", False),
        local_admin_username=os.getenv("LOCAL_ADMIN_USERNAME", "").strip(),
        local_admin_password=os.getenv("LOCAL_ADMIN_PASSWORD", ""),
        local_admin_display_name=(
            os.getenv("LOCAL_ADMIN_DISPLAY_NAME", "Local Admin").strip()
            or "Local Admin"
        ),
        session_secret=os.getenv("SESSION_SECRET", "agentweave-session-secret"),
        session_cookie_name=os.getenv("SESSION_COOKIE_NAME", "agentweave_session"),
        session_cookie_same_site=(
            os.getenv("SESSION_COOKIE_SAMESITE", "lax").strip().lower() or "lax"
        ),
        session_cookie_secure=_env_flag("SESSION_COOKIE_SECURE", False),
    )
