"""S1-04 / S1-05 tests: guard, login, logout, registration, portals.

Uses a small FastAPI app wired like app.main (guard + auth router) on an
in-memory database. Hosts are app.localhost and admin.localhost.
"""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import auth, host_routing
from app.database import Base, get_db
from app.routes import auth as auth_routes
from app.services.accounts import create_platform_staff, register_agency_with_owner
from app.services.passwords import hash_password

PW = "correct horse battery"
HOSTS_ENFORCED = host_routing.HostConfig(public_host="app.localhost", admin_host="admin.localhost", enforce=True)
HOSTS_OFF = host_routing.HostConfig(public_host="app.localhost", admin_host="admin.localhost", enforce=False)


@pytest.fixture()
def env(monkeypatch):
    monkeypatch.setenv("COOKIE_SECURE", "0")
    monkeypatch.setenv("AUTH_ENFORCEMENT", "1")
    monkeypatch.setenv("REGISTRATION_ENABLED", "1")
    monkeypatch.setenv("ALLOW_ADMIN_BOOTSTRAP", "1")
    monkeypatch.delenv("APP_ENV", raising=False)


@pytest.fixture()
def factory():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    yield sessionmaker(bind=engine)
    engine.dispose()


@pytest.fixture()
def app(env, factory):
    app = FastAPI()
    # Same order as app.main: auth first, host guard LAST so it runs FIRST (outermost).
    auth.install_auth_guard(app, session_factory=factory)
    host_routing.install_host_guard(app, HOSTS_ENFORCED)
    app.include_router(auth_routes.router)

    @app.get("/")
    def home():
        return {"page": "projects"}

    @app.get("/health")
    def health():
        return {"status": "ok"}

    def _db():
        db = factory()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = _db
    return app


@pytest.fixture()
def db(factory):
    s = factory()
    yield s
    s.close()


@pytest.fixture()
def customer(db):
    return register_agency_with_owner(
        db, agency_name="Acme", email="owner@acme.com", display_name="Olivia", password_hash=hash_password(PW)
    )


@pytest.fixture()
def staff(db):
    return create_platform_staff(db, email="boss@vtechys.com", display_name="Boss", password=PW)


def web(app):
    return TestClient(app, base_url="http://app.localhost", follow_redirects=False)


def admin(app):
    return TestClient(app, base_url="http://admin.localhost", follow_redirects=False)


def login(client, email, password=PW, **extra):
    return client.post("/login", data={"email": email, "password": password, **extra})


# --- guard: deny by default -------------------------------------------------

def test_anonymous_browser_is_redirected_to_login_with_next(app):
    r = web(app).get("/")
    assert r.status_code == 303 and r.headers["location"] == "/login?next=%2F"


def test_anonymous_htmx_gets_401_and_hx_redirect(app):
    r = web(app).get("/", headers={"HX-Request": "true"})
    assert r.status_code == 401 and r.headers["HX-Redirect"] == "/login"


def test_anonymous_api_client_gets_401_json(app):
    r = web(app).get("/", headers={"Accept": "application/json"})
    assert r.status_code == 401


def test_health_and_login_page_stay_public(app):
    c = web(app)
    assert c.get("/health").status_code == 200
    assert c.get("/login").status_code == 200


def test_guard_off_means_old_behaviour(app, monkeypatch):
    monkeypatch.setenv("AUTH_ENFORCEMENT", "0")
    assert web(app).get("/").status_code == 200


def test_tampered_cookie_is_logged_out(app, customer):
    c = web(app)
    login(c, "owner@acme.com")
    assert c.get("/").status_code == 200
    c.cookies.clear()  # drop the real cookie so only the forged one is sent
    c.cookies.set("sfx_app", "forged-token")
    assert c.get("/").status_code == 303


# --- login ------------------------------------------------------------------

def test_customer_login_then_access(app, customer):
    c = web(app)
    r = login(c, "owner@acme.com")
    assert r.status_code == 303 and r.headers["location"] == "/"
    assert "HttpOnly" in r.headers["set-cookie"]
    assert c.get("/").status_code == 200


def test_login_normalizes_email(app, customer):
    assert login(web(app), "  OWNER@Acme.com ").status_code == 303


def test_wrong_password_and_unknown_email_look_identical(app, customer):
    a = login(web(app), "owner@acme.com", "wrong password!!")
    b = login(web(app), "nobody@acme.com")
    assert a.status_code == b.status_code == 401
    assert "Invalid email or password." in a.text and "Invalid email or password." in b.text


def test_next_is_honoured_when_same_site_and_ignored_when_external(app, customer):
    assert login(web(app), "owner@acme.com", next="/keywords").headers["location"] == "/keywords"
    for bad in ["//evil.com", "https://evil.com", "/\\evil.com", "javascript:alert(1)"]:
        assert login(web(app), "owner@acme.com", next=bad).headers["location"] == "/"


@pytest.mark.parametrize("value,expected", [("/x?a=1", "/x?a=1"), ("//e.com", None), ("x", None), ("", None), (None, None)])
def test_safe_next(value, expected):
    assert auth.safe_next(value) == expected


def test_deactivated_user_cannot_login_or_keep_session(app, customer, db):
    c = web(app)
    login(c, "owner@acme.com")
    customer.is_active = False
    db.commit()
    assert c.get("/").status_code == 303
    assert login(web(app), "owner@acme.com").status_code == 401


def test_suspended_agency_gets_403_everywhere(app, customer, db):
    c = web(app)
    login(c, "owner@acme.com")
    customer.agency.is_active = False
    db.commit()
    assert c.get("/").status_code == 403
    assert login(web(app), "owner@acme.com").status_code == 403


# --- logout -----------------------------------------------------------------

def test_logout_revokes_the_session_even_if_cookie_is_replayed(app, customer):
    c = web(app)
    login(c, "owner@acme.com")
    stolen = c.cookies.get("sfx_app")
    r = c.post("/logout")
    assert r.status_code == 303 and r.headers["location"] == "/login"
    replay = web(app)
    replay.cookies.set("sfx_app", stolen)
    assert replay.get("/").status_code == 303


# --- portals ----------------------------------------------------------------

def test_staff_login_on_admin_host_reaches_admin_page(app, staff):
    c = admin(app)
    r = login(c, "boss@vtechys.com")
    assert r.status_code == 303 and r.headers["location"] == "/admin"
    page = c.get("/admin")
    assert page.status_code == 200 and "Boss" in page.text


def test_customer_cannot_log_in_on_admin_host(app, customer):
    assert login(admin(app), "owner@acme.com").status_code == 401


def test_staff_cannot_log_in_on_app_host(app, staff):
    assert login(web(app), "boss@vtechys.com").status_code == 401


def test_customer_cookie_is_useless_on_admin_host(app, customer):
    c = web(app)
    login(c, "owner@acme.com")
    cookie = c.cookies.get("sfx_app")
    a = admin(app)
    a.cookies.set("sfx_app", cookie)
    a.cookies.set("sfx_admin", cookie)  # even under the admin cookie name the host_kind check fails
    assert a.get("/admin").status_code == 303


def test_customer_requesting_admin_page_on_app_host_is_refused(app, customer):
    app.state.host_config = HOSTS_OFF  # host guard off: the role check alone must refuse
    c = web(app)
    login(c, "owner@acme.com")
    assert c.get("/admin").status_code == 403


def test_host_guard_runs_before_login_redirect(app):
    assert web(app).get("/admin").status_code == 404  # not a login redirect: admin area is invisible on app.
    r = TestClient(app, base_url="http://evil.com", follow_redirects=False).get("/")
    assert r.status_code == 421


def test_admin_host_front_door_leads_to_admin_then_login(app):
    r = admin(app).get("/")
    assert r.status_code == 303 and r.headers["location"] == "/admin"
    assert admin(app).get("/admin").headers["location"] == "/login?next=%2Fadmin"


def test_login_page_reachable_on_both_hosts_with_host_guard_on(app):
    assert web(app).get("/login").status_code == 200
    assert admin(app).get("/login").status_code == 200


# --- registration -----------------------------------------------------------

REG = dict(agency_name="New Agency", display_name="Nia", email="nia@new.com", password=PW, password2=PW)


def test_registration_creates_owner_and_logs_in(app, db):
    c = web(app)
    r = c.post("/register", data=REG)
    assert r.status_code == 303 and r.headers["location"] == "/"
    assert c.get("/").status_code == 200
    from app.models import User
    u = db.query(User).filter_by(email="nia@new.com").one()
    assert u.platform_role == "customer" and u.agency_role == "owner"


def test_registration_ignores_a_smuggled_admin_role(app, db):
    c = web(app)
    c.post("/register", data={**REG, "platform_role": "platform_admin", "agency_role": "member"})
    from app.models import User
    u = db.query(User).filter_by(email="nia@new.com").one()
    assert u.platform_role == "customer" and u.agency_role == "owner"


def test_registration_closed_by_default(app, monkeypatch):
    monkeypatch.setenv("REGISTRATION_ENABLED", "0")
    assert web(app).get("/register").status_code == 404
    assert web(app).post("/register", data=REG).status_code == 404


def test_registration_not_available_on_admin_host(app):
    assert admin(app).post("/register", data=REG).status_code == 404


def test_registration_errors(app, customer):
    assert web(app).post("/register", data={**REG, "password2": "different password"}).status_code == 400
    assert web(app).post("/register", data={**REG, "password": "short", "password2": "short"}).status_code == 400
    dup = web(app).post("/register", data={**REG, "email": "OWNER@acme.com"})
    assert dup.status_code == 400 and "already exists" in dup.text


def test_admin_dependency_checks_role_even_without_the_middleware(app, customer, monkeypatch):
    monkeypatch.setenv("AUTH_ENFORCEMENT", "0")  # guard off: the dependency must still refuse
    app.state.host_config = HOSTS_OFF
    c = web(app)
    assert c.get("/admin").status_code == 401
    login(c, "owner@acme.com")
    assert c.get("/admin").status_code == 403
