"""Authentication guard and dependencies (S1-04).

One middleware protects every route at once (deny by default) instead of editing
~100 routes one by one. Turn it on with AUTH_ENFORCEMENT=1. While it is off the
app behaves exactly as before, but request.state.user is still filled in when a
valid session cookie is present, so pages can show "signed in as ...".

What each situation gets (the response matrix from docs/Threat_Model.md):
  not logged in               -> redirect to /login (HTMX: 401 + HX-Redirect, API: 401 JSON)
  wrong portal for the role   -> 403   (a customer on admin., staff on app.)
  agency suspended            -> 403
  bad / expired / revoked     -> treated as not logged in
Ownership of individual projects (agency A vs agency B) comes with the tenancy
migration in S2-02; until then every customer sees all projects.
"""

import os
from dataclasses import dataclass
from urllib.parse import quote

from fastapi import Depends, HTTPException, Request
from fastapi.responses import JSONResponse, RedirectResponse
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from .database import SessionLocal, get_db
from .host_routing import HostKind, classify_host
from .services import session_cookies, sessions

PUBLIC_PATHS = frozenset({"/login", "/register", "/logout", "/health", "/version"})
STAFF_ROLES = ("platform_admin", "support_admin")
_TRUE = ("1", "true", "yes", "on")


def auth_enforced() -> bool:
    return os.environ.get("AUTH_ENFORCEMENT", "").strip().lower() in _TRUE


def registration_enabled() -> bool:
    """Public sign-up is OFF unless REGISTRATION_ENABLED=1 (invitation-only by default)."""
    return os.environ.get("REGISTRATION_ENABLED", "").strip().lower() in _TRUE


@dataclass(frozen=True)
class AuthUser:
    """Plain copy of what the guard needs, so it stays valid after the DB session closes."""

    id: str
    email: str
    display_name: str
    platform_role: str
    agency_id: str | None
    agency_name: str | None
    agency_active: bool
    csrf_token: str


def host_session_kind(request: Request) -> str:
    """'admin' for the admin host, otherwise 'app' (public, legacy and local hosts)."""
    cfg = getattr(request.app.state, "host_config", None)
    if cfg is not None and classify_host(request.headers.get("host"), cfg) is HostKind.ADMIN:
        return "admin"
    return "app"


def portal_allows(platform_role: str, kind: str) -> bool:
    """Staff belong on the admin portal, customers on the app portal. Nothing else."""
    if kind == "admin":
        return platform_role in STAFF_ROLES
    return platform_role == "customer"


def load_auth_user(db: Session, request: Request) -> AuthUser | None:
    kind = host_session_kind(request)
    token = session_cookies.read_session_cookie(request, kind)
    row = sessions.get_valid_session(db, token, kind)
    if row is None:
        return None
    u = row.user
    return AuthUser(
        id=str(u.id),
        email=u.email,
        display_name=u.display_name,
        platform_role=u.platform_role,
        agency_id=str(u.agency_id) if u.agency_id else None,
        agency_name=u.agency.name if u.agency else None,
        agency_active=u.agency.is_active if u.agency else True,
        csrf_token=row.csrf_token,
    )


def guard_decision(path: str, user: AuthUser | None, kind: str) -> str | None:
    """None = let through, else 'login' | 'forbidden' | 'suspended'. Deny by default."""
    if path in PUBLIC_PATHS:
        return None
    if user is None:
        return "login"
    if not portal_allows(user.platform_role, kind):
        return "forbidden"
    if user.agency_id and not user.agency_active:
        return "suspended"
    return None


def safe_next(value: str | None) -> str | None:
    """Only same-site relative paths. Blocks open redirects like //evil.com or https://evil.com."""
    if not value or not value.startswith("/") or value.startswith("//") or "\\" in value:
        return None
    return value


def _reject(request: Request, decision: str):
    if decision == "forbidden":
        return JSONResponse({"detail": "Forbidden"}, status_code=403)
    if decision == "suspended":
        return JSONResponse({"detail": "This account is suspended."}, status_code=403)
    # decision == "login"
    if request.headers.get("hx-request"):
        return JSONResponse({"detail": "Login required"}, status_code=401, headers={"HX-Redirect": "/login"})
    if "application/json" in request.headers.get("accept", "") and "text/html" not in request.headers.get("accept", ""):
        return JSONResponse({"detail": "Login required"}, status_code=401)
    target = request.url.path + (f"?{request.url.query}" if request.url.query else "")
    return RedirectResponse(f"/login?next={quote(target, safe='')}", status_code=303)


def install_auth_guard(app, session_factory=SessionLocal) -> None:
    app.state.auth_session_factory = session_factory

    @app.middleware("http")
    async def auth_guard(request: Request, call_next):
        request.state.user = None
        kind = host_session_kind(request)
        has_cookie = session_cookies.read_session_cookie(request, kind) is not None
        if has_cookie or auth_enforced():
            def _lookup():
                db = app.state.auth_session_factory()
                try:
                    return load_auth_user(db, request)
                finally:
                    db.close()

            request.state.user = await run_in_threadpool(_lookup) if has_cookie else None
        if auth_enforced():
            decision = guard_decision(request.url.path, request.state.user, kind)
            if decision is not None:
                return _reject(request, decision)
        return await call_next(request)


# ---- dependencies for routes that need the user object ---------------------

def require_user(request: Request, db: Session = Depends(get_db)) -> AuthUser:
    user = getattr(request.state, "user", None) or load_auth_user(db, request)
    if user is None:
        raise HTTPException(status_code=401, detail="Login required")
    if not portal_allows(user.platform_role, host_session_kind(request)):
        raise HTTPException(status_code=403, detail="Forbidden")
    if user.agency_id and not user.agency_active:
        raise HTTPException(status_code=403, detail="This account is suspended.")
    return user


def require_platform_admin(user: AuthUser = Depends(require_user)) -> AuthUser:
    """Checks the role on the server, whatever host the request claims to come from."""
    if user.platform_role not in STAFF_ROLES:
        raise HTTPException(status_code=403, detail="Forbidden")
    return user
