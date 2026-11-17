"""S1-03b tests: session cookie attributes."""

import pytest
from fastapi import FastAPI, Request, Response
from fastapi.testclient import TestClient

from app.host_routing import HostKind
from app.services import session_cookies as C


def header(host_kind="app", token="tok123"):
    r = Response()
    C.set_session_cookie(r, token, host_kind)
    return r.headers["set-cookie"]


def test_secure_is_default_when_env_unset(monkeypatch):
    monkeypatch.delenv("COOKIE_SECURE", raising=False)
    assert C.cookies_are_secure() is True


@pytest.mark.parametrize("val", ["0", "false", "No", "OFF"])
def test_secure_can_only_be_disabled_explicitly(monkeypatch, val):
    monkeypatch.setenv("COOKIE_SECURE", val)
    assert C.cookies_are_secure() is False


@pytest.mark.parametrize("val", ["1", "true", "garbage", ""])
def test_any_other_value_stays_secure(monkeypatch, val):
    monkeypatch.setenv("COOKIE_SECURE", val)
    assert C.cookies_are_secure() is True


def test_production_cookie_has_every_protection(monkeypatch):
    monkeypatch.delenv("COOKIE_SECURE", raising=False)
    h = header("app")
    assert h.startswith("__Host-sfx_app=tok123")
    assert "HttpOnly" in h and "Secure" in h
    assert "Path=/" in h
    assert "samesite=lax" in h.lower()
    assert "domain" not in h.lower()  # host-only


def test_admin_cookie_is_strict_and_has_its_own_name(monkeypatch):
    monkeypatch.delenv("COOKIE_SECURE", raising=False)
    h = header("admin")
    assert h.startswith("__Host-sfx_admin=")
    assert "samesite=strict" in h.lower()


def test_local_http_cookie_drops_secure_and_prefix(monkeypatch):
    monkeypatch.setenv("COOKIE_SECURE", "0")
    h = header("app")
    assert h.startswith("sfx_app=") and "Secure" not in h
    assert "HttpOnly" in h and "domain" not in h.lower()  # still protected


def test_max_age_matches_absolute_lifetime(monkeypatch):
    assert "Max-Age=1209600" in header("app")   # 14 days
    assert "Max-Age=28800" in header("admin")   # 8 hours


def test_clear_cookie_expires_it(monkeypatch):
    monkeypatch.delenv("COOKIE_SECURE", raising=False)
    r = Response()
    C.clear_session_cookie(r, "app")
    h = r.headers["set-cookie"]
    assert h.startswith("__Host-sfx_app=;") or '__Host-sfx_app=""' in h
    assert "Max-Age=0" in h


def test_unknown_host_has_no_session_kind():
    assert C.session_kind_for(HostKind.PUBLIC) == "app"
    assert C.session_kind_for(HostKind.LEGACY) == "app"
    assert C.session_kind_for(HostKind.ADMIN) == "admin"
    with pytest.raises(ValueError):
        C.session_kind_for(HostKind.UNKNOWN)


def test_cookie_round_trip_and_cross_kind_isolation(monkeypatch):
    monkeypatch.setenv("COOKIE_SECURE", "0")
    app = FastAPI()

    @app.get("/set")
    def _set():
        r = Response()
        C.set_session_cookie(r, "abc", "app")
        return r

    @app.get("/read/{kind}")
    def _read(kind: str, request: Request):
        return {"token": C.read_session_cookie(request, kind)}

    client = TestClient(app)
    client.get("/set")
    assert client.get("/read/app").json() == {"token": "abc"}
    assert client.get("/read/admin").json() == {"token": None}  # admin never sees the app cookie
