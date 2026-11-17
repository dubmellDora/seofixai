"""Login, logout, registration and the admin landing page (S1-05).

Thin routes: all rules live in app/services/accounts.py, passwords.py, sessions.py
and session_cookies.py. Per D-018 there is no CSRF check and no rate limiting here.
"""

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from ..auth import (
    AuthUser,
    host_session_kind,
    load_auth_user,
    portal_allows,
    registration_enabled,
    require_platform_admin,
    safe_next,
)
from ..database import get_db
from ..services import session_cookies, sessions
from ..services.accounts import AccountError, authenticate, register_agency_with_owner
from ..services.passwords import PasswordError, hash_password

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")

GENERIC_LOGIN_ERROR = "Invalid email or password."


def _home(kind: str) -> str:
    return "/admin" if kind == "admin" else "/"


def _render(request: Request, name: str, status_code: int = 200, **ctx):
    kind = host_session_kind(request)
    ctx.update(portal=kind, registration_enabled=registration_enabled())
    return templates.TemplateResponse(request, name, ctx, status_code=status_code)


def _start_session(db: Session, request: Request, user, next_url: str | None) -> RedirectResponse:
    kind = host_session_kind(request)
    token, _row = sessions.create_session(db, user, kind)  # always a brand-new session id
    response = RedirectResponse(safe_next(next_url) or _home(kind), status_code=303)
    session_cookies.set_session_cookie(response, token, kind)
    return response


@router.get("/login")
def login_page(request: Request, next: str = "", db: Session = Depends(get_db)):
    kind = host_session_kind(request)
    if load_auth_user(db, request) is not None:
        return RedirectResponse(safe_next(next) or _home(kind), status_code=303)
    return _render(request, "auth/login.html", next=safe_next(next) or "")


@router.post("/login")
def login_submit(
    request: Request,
    email: str = Form(""),
    password: str = Form(""),
    next: str = Form(""),
    db: Session = Depends(get_db),
):
    kind = host_session_kind(request)
    user = authenticate(db, email, password)
    # Same message for: unknown email, wrong password, deactivated user, and a
    # real account trying the wrong portal (customer on admin., staff on app.).
    if user is None or not portal_allows(user.platform_role, kind):
        return _render(request, "auth/login.html", 401, error=GENERIC_LOGIN_ERROR, email=email, next=next)
    if user.agency is not None and not user.agency.is_active:
        return _render(request, "auth/login.html", 403, error="This account is suspended.", email=email, next=next)
    return _start_session(db, request, user, next)


@router.post("/logout")
def logout(request: Request, db: Session = Depends(get_db)):
    kind = host_session_kind(request)
    token = session_cookies.read_session_cookie(request, kind)
    row = sessions.get_valid_session(db, token, kind)
    if row is not None:
        sessions.revoke_session(db, row)
    response = RedirectResponse("/login", status_code=303)
    session_cookies.clear_session_cookie(response, kind)
    return response


@router.get("/register")
def register_page(request: Request):
    if not registration_enabled() or host_session_kind(request) == "admin":
        return _render(request, "auth/login.html", 404, error="Registration is closed.")
    return _render(request, "auth/register.html")


@router.post("/register")
def register_submit(
    request: Request,
    agency_name: str = Form(""),
    display_name: str = Form(""),
    email: str = Form(""),
    password: str = Form(""),
    password2: str = Form(""),
    db: Session = Depends(get_db),
):
    if not registration_enabled() or host_session_kind(request) == "admin":
        return _render(request, "auth/login.html", 404, error="Registration is closed.")
    form = dict(agency_name=agency_name, display_name=display_name, email=email)
    if password != password2:
        return _render(request, "auth/register.html", 400, error="The passwords do not match.", **form)
    try:
        user = register_agency_with_owner(
            db,
            agency_name=agency_name,
            email=email,
            display_name=display_name,
            password_hash=hash_password(password),
        )
    except (AccountError, PasswordError) as exc:
        return _render(request, "auth/register.html", 400, error=str(exc), **form)
    return _start_session(db, request, user, None)


@router.get("/admin")
def admin_home(request: Request, user: AuthUser = Depends(require_platform_admin)):
    return _render(request, "auth/admin_home.html", user=user)
