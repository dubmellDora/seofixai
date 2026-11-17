"""Session cookie helpers (S1-03b).

The cookie carries only the random session token from services/sessions.py.
Every attribute below closes one specific attack:

  HttpOnly    JavaScript cannot read the cookie, so an XSS bug cannot steal it.
  Secure      the browser sends it over HTTPS only (default ON; see below).
  SameSite    the browser withholds it on cross-site requests (CSRF defence in
              depth; the CSRF token in S1-03c is the real control).
                app   -> Lax    (still arrives when a user clicks a link to us)
                admin -> Strict (never sent from another site, even via a link)
  Path=/      required by the __Host- prefix below.
  no Domain   "host-only": app.seofixai.com's cookie is never sent to
              admin.seofixai.com or to seofixai.com. Setting Domain=.seofixai.com
              would share it with every subdomain, so this module never does.
  __Host-     a name prefix that makes the browser REFUSE the cookie unless it is
              Secure, Path=/ and has no Domain. Even a bug here cannot widen it.
"""

import os

from fastapi import Request, Response

from ..host_routing import HostKind
from .sessions import LIFETIMES

_SAMESITE = {"app": "lax", "admin": "strict"}


def session_kind_for(kind: HostKind) -> str:
    """HostKind (from classify_host) -> 'app' | 'admin'. UNKNOWN has no sessions."""
    if kind in (HostKind.PUBLIC, HostKind.LEGACY):
        return "app"
    if kind is HostKind.ADMIN:
        return "admin"
    raise ValueError("no session cookie for an unknown host")


def cookies_are_secure() -> bool:
    """Secure is ON unless COOKIE_SECURE is explicitly 0/false/no/off.

    Deny by default: forgetting to set anything gives the safe behaviour. Only
    local development over plain http:// needs COOKIE_SECURE=0.
    """
    return os.environ.get("COOKIE_SECURE", "").strip().lower() not in ("0", "false", "no", "off")


def cookie_name(host_kind: str) -> str:
    base = f"sfx_{host_kind}"
    return f"__Host-{base}" if cookies_are_secure() else base


def set_session_cookie(response: Response, token: str, host_kind: str) -> None:
    absolute, _idle = LIFETIMES[host_kind]
    response.set_cookie(
        key=cookie_name(host_kind),
        value=token,
        max_age=int(absolute.total_seconds()),
        path="/",
        domain=None,  # host-only, on purpose
        secure=cookies_are_secure(),
        httponly=True,
        samesite=_SAMESITE[host_kind],
    )


def clear_session_cookie(response: Response, host_kind: str) -> None:
    """Tell the browser to delete the cookie (same name/path/flags, expired)."""
    response.delete_cookie(
        key=cookie_name(host_kind),
        path="/",
        domain=None,
        secure=cookies_are_secure(),
        httponly=True,
        samesite=_SAMESITE[host_kind],
    )


def read_session_cookie(request: Request, host_kind: str) -> str | None:
    return request.cookies.get(cookie_name(host_kind))
