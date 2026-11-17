"""Request-level tests for the host guard (S0-04).

Most tests use a tiny throwaway FastAPI app so they never touch the database.
The last tests check the real app is wired up and defaults to "off".
"""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.host_routing import HostConfig, host_from_origin, install_host_guard, load_host_config

ENFORCING = HostConfig(
    public_host="app.seofixai.com",
    admin_host="admin.seofixai.com",
    legacy_hosts=("seofixai.com",),
    enforce=True,
)


def make_client(config: HostConfig) -> TestClient:
    app = FastAPI()
    install_host_guard(app, config)

    @app.get("/")
    def home():
        return {"page": "home"}

    @app.get("/health")
    def health():
        return {"status": "ok"}

    @app.get("/admin/login")
    def admin_login():
        return {"page": "admin-login"}

    return TestClient(app)


@pytest.mark.parametrize(
    "host, path, expected_status",
    [
        ("app.seofixai.com", "/", 200),
        ("app.seofixai.com", "/admin/login", 404),   # admin path hidden on public host
        ("admin.seofixai.com", "/admin/login", 200),
        ("admin.seofixai.com", "/", 404),            # customer path hidden on admin host
        ("seofixai.com", "/", 200),                  # legacy host still works
        ("seofixai.com", "/admin/login", 404),
        ("evil.com", "/", 421),                      # unknown host
        ("evilseofixai.com", "/", 421),              # look-alike
        ("app.seofixai.com.evil.com", "/", 421),     # look-alike
        ("evil.com", "/health", 421),                # unknown host cannot probe /health
        ("app.seofixai.com", "/health", 200),
        ("admin.seofixai.com", "/health", 200),
        ("APP.SeoFixAI.com:8000", "/", 200),         # case and port are normalized
    ],
)
def test_guard_when_enforcing(host, path, expected_status):
    client = make_client(ENFORCING)
    assert client.get(path, headers={"host": host}).status_code == expected_status


def test_rejection_bodies_are_generic():
    client = make_client(ENFORCING)
    assert client.get("/", headers={"host": "evil.com"}).json() == {"detail": "Misdirected Request"}
    assert client.get("/admin/login", headers={"host": "app.seofixai.com"}).json() == {"detail": "Not Found"}


def test_guard_does_nothing_when_not_enforcing():
    off = HostConfig("app.seofixai.com", "admin.seofixai.com", enforce=False)
    client = make_client(off)
    for host in ("evil.com", "app.seofixai.com", "admin.seofixai.com"):
        assert client.get("/", headers={"host": host}).status_code == 200
        assert client.get("/admin/login", headers={"host": host}).status_code == 200


# ---- configuration loading -------------------------------------------------

def test_host_from_origin():
    assert host_from_origin("https://app.seofixai.com") == "app.seofixai.com"
    assert host_from_origin("http://App.Localhost:8000/") == "app.localhost"
    assert host_from_origin("seofixai.com") == "seofixai.com"  # bare host
    assert host_from_origin("") == ""


def test_load_host_config_defaults_to_off_and_local_names():
    cfg = load_host_config({})
    assert cfg.enforce is False
    assert cfg.public_host == "app.localhost"
    assert cfg.admin_host == "admin.localhost"
    assert cfg.legacy_hosts == ()


def test_load_host_config_from_env():
    cfg = load_host_config(
        {
            "PUBLIC_APP_ORIGIN": "https://app.seofixai.com",
            "ADMIN_APP_ORIGIN": "https://admin.seofixai.com",
            "LEGACY_APP_HOSTS": "seofixai.com, Old.Example.com:8080 ,",
            "HOST_ENFORCEMENT": "true",
        }
    )
    assert cfg == HostConfig(
        public_host="app.seofixai.com",
        admin_host="admin.seofixai.com",
        legacy_hosts=("seofixai.com", "old.example.com"),
        enforce=True,
    )


@pytest.mark.parametrize("value", ["", "0", "false", "off", "no", "garbage"])
def test_enforcement_is_off_unless_clearly_enabled(value):
    assert load_host_config({"HOST_ENFORCEMENT": value}).enforce is False


# ---- the real app ----------------------------------------------------------

def test_real_app_health_endpoint_works():
    from app.main import app

    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_real_app_guard_is_installed_and_can_be_switched_on():
    from app.main import app

    original = app.state.host_config
    try:
        app.state.host_config = ENFORCING
        client = TestClient(app)
        assert client.get("/health", headers={"host": "evil.com"}).status_code == 421
        assert client.get("/health", headers={"host": "app.seofixai.com"}).status_code == 200
    finally:
        app.state.host_config = original
