"""Host routing: decide which "portal" a request belongs to, from its Host header.

This module only answers "which door did the request come through?".
It never answers "who is the user?" - that is authentication (Sprint 1).
"""

import os
from dataclasses import dataclass
from enum import Enum
from typing import Mapping
from urllib.parse import urlparse

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, RedirectResponse


class HostKind(str, Enum):
    """The possible answers when we classify a hostname."""

    PUBLIC = "public"    # app.seofixai.com   - customers
    ADMIN = "admin"      # admin.seofixai.com - staff
    LEGACY = "legacy"    # seofixai.com       - old URL, kept open during the move
    UNKNOWN = "unknown"  # anything else      - will be rejected


@dataclass(frozen=True)
class HostConfig:
    """The list of hostnames we trust. Built once from settings, never from a request.

    Every value must already be normalized (lowercase, no port), because
    classify_host() compares them with ==.
    """

    public_host: str                    # e.g. "app.seofixai.com"
    admin_host: str                     # e.g. "admin.seofixai.com"
    legacy_hosts: tuple[str, ...] = ()  # e.g. ("seofixai.com",) during the move
    enforce: bool = False               # False = guard is installed but lets everything through


def normalize_host(raw: str | None) -> str:
    """Clean a raw Host header so two spellings of the same host compare equal.

    "App.SeoFixAI.com:8000" -> "app.seofixai.com"
    "seofixai.com."         -> "seofixai.com"
    None or ""              -> ""   (an empty host will classify as UNKNOWN)
    """
    if not raw:
        return ""

    host = raw.strip().lower()

    if host.startswith("["):
        # IPv6 literal such as "[::1]:8000": the colons are part of the
        # address, so keep everything up to the closing bracket.
        end = host.find("]")
        if end != -1:
            host = host[: end + 1]
    else:
        # Normal host: drop ":port" if there is one.
        host = host.split(":", 1)[0]

    # A trailing dot ("seofixai.com.") is a valid way to write the same name.
    return host.rstrip(".")


def classify_host(raw_host: str | None, config: HostConfig) -> HostKind:
    """Decide which portal a Host header belongs to.

    Uses EXACT matches only: the whole host must equal a trusted name. Never
    endswith/startswith or a substring test: those would let
    "evilseofixai.com" or "app.seofixai.com.evil.com" through.
    Anything we do not recognise, including a missing host, is UNKNOWN.
    """
    host = normalize_host(raw_host)

    if not host:
        return HostKind.UNKNOWN
    if host == config.public_host:
        return HostKind.PUBLIC
    if host == config.admin_host:
        return HostKind.ADMIN
    if host in config.legacy_hosts:
        return HostKind.LEGACY
    return HostKind.UNKNOWN


ADMIN_PATH_PREFIX = "/admin"
# Reachable on any trusted host: the liveness check, plus login/logout so staff can
# sign in on admin. and customers on app. (each portal has its own login, S1-05).
ALWAYS_ALLOWED_PATHS = ("/health", "/login", "/logout")


def _is_admin_path(path: str) -> bool:
    # Match "/admin" itself or anything under "/admin/". A plain
    # startswith("/admin") would also catch "/administrator-notes".
    return path == ADMIN_PATH_PREFIX or path.startswith(ADMIN_PATH_PREFIX + "/")


def host_guard_decision(kind: HostKind, path: str) -> int | None:
    """Return an HTTP status to reject the request with, or None to let it through.

    421 = "this server does not serve that hostname" (unknown host)
    404 = known host, but that path does not exist there. We use 404, not 403,
          so we do not confirm that an admin area exists.

    This only picks the right portal. It says nothing about who the user is.
    """
    if kind is HostKind.UNKNOWN:
        return 421
    if path in ALWAYS_ALLOWED_PATHS:
        return None

    on_admin_path = _is_admin_path(path)
    if kind is HostKind.ADMIN and not on_admin_path:
        return 404
    if kind in (HostKind.PUBLIC, HostKind.LEGACY) and on_admin_path:
        return 404
    return None


def host_from_origin(value: str) -> str:
    """Turn "https://app.seofixai.com:8000/" (or a bare "app.seofixai.com") into
    the normalized host "app.seofixai.com"."""
    value = value.strip()
    if "://" not in value:
        value = "//" + value  # so urlparse treats it as a host, not a path
    return normalize_host(urlparse(value).hostname or "")


def load_host_config(env: Mapping[str, str] | None = None) -> HostConfig:
    """Build the trusted-host list from environment variables.

    PUBLIC_APP_ORIGIN   customer app origin   (default http://app.localhost:8000)
    ADMIN_APP_ORIGIN    admin origin          (default http://admin.localhost:8000)
    LEGACY_APP_HOSTS    comma-separated hosts that keep serving the old app
    HOST_ENFORCEMENT    1/true/yes/on to turn the guard on; anything else = off

    Hostnames are configuration, not constants in route code (plan S0-04).
    """
    env = os.environ if env is None else env
    legacy = tuple(
        host
        for host in (host_from_origin(h) for h in env.get("LEGACY_APP_HOSTS", "").split(","))
        if host
    )
    return HostConfig(
        public_host=host_from_origin(env.get("PUBLIC_APP_ORIGIN", "http://app.localhost:8000")),
        admin_host=host_from_origin(env.get("ADMIN_APP_ORIGIN", "http://admin.localhost:8000")),
        legacy_hosts=legacy,
        enforce=env.get("HOST_ENFORCEMENT", "").strip().lower() in ("1", "true", "yes", "on"),
    )


_REJECTION_BODIES = {421: "Misdirected Request", 404: "Not Found"}


def install_host_guard(app: FastAPI, config: HostConfig) -> None:
    """Attach the host guard to `app` as middleware.

    The config lives on app.state so tests can swap it. It is read on every
    request, and the guard does nothing at all while config.enforce is False.
    """
    app.state.host_config = config

    @app.middleware("http")
    async def host_guard(request: Request, call_next):
        cfg: HostConfig = app.state.host_config
        if cfg.enforce:
            kind = classify_host(request.headers.get("host"), cfg)
            if kind is HostKind.ADMIN and request.url.path == "/":
                # Friendly landing: the admin host's front door is /admin (which asks for login).
                return RedirectResponse("/admin", status_code=303)
            status = host_guard_decision(kind, request.url.path)
            if status is not None:
                return JSONResponse({"detail": _REJECTION_BODIES[status]}, status_code=status)
        return await call_next(request)
