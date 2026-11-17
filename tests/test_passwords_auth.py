"""S1-02 tests: Argon2 hashing, authenticate(), last login, admin bootstrap."""

import pytest
from argon2 import PasswordHasher
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models import User
from app.services.accounts import (
    AccountError,
    authenticate,
    create_platform_staff,
    register_agency_with_owner,
)
from app.services.passwords import PasswordError, hash_password, verify_password

PW = "correct horse battery"


@pytest.fixture()
def db():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    yield session
    session.close()
    engine.dispose()


@pytest.fixture()
def owner(db):
    return register_agency_with_owner(
        db, agency_name="Acme", email="Owner@Acme.com", display_name="Olivia",
        password_hash=hash_password(PW),
    )


# --- hashing ---------------------------------------------------------------

def test_hash_is_argon2id_and_never_plaintext():
    h = hash_password(PW)
    assert h.startswith("$argon2id$")
    assert PW not in h


def test_same_password_gets_different_hashes_salted():
    assert hash_password(PW) != hash_password(PW)


def test_verify_right_and_wrong():
    h = hash_password(PW)
    assert verify_password(h, PW) is True
    assert verify_password(h, "wrong password!!") is False


@pytest.mark.parametrize("bad", [None, "", "short", "x" * 300])
def test_weak_or_huge_password_refused(bad):
    with pytest.raises(PasswordError):
        hash_password(bad)


@pytest.mark.parametrize("stored", [None, "", "not-a-hash"])
def test_verify_never_raises_on_garbage_hash(stored):
    assert verify_password(stored, PW) is False


# --- authenticate ----------------------------------------------------------

def test_login_ok_normalizes_email_and_records_last_login(db, owner):
    assert owner.last_login_at is None
    user = authenticate(db, "  OWNER@acme.com ", PW)
    assert user is not None and user.id == owner.id
    assert user.last_login_at is not None


def test_wrong_password_unknown_email_and_junk_all_return_none(db, owner):
    assert authenticate(db, "owner@acme.com", "nope nope nope") is None
    assert authenticate(db, "nobody@acme.com", PW) is None
    assert authenticate(db, "not-an-email", PW) is None
    assert authenticate(db, None, None) is None
    db.refresh(owner)
    assert owner.last_login_at is None  # failures never touch last login


def test_deactivated_user_cannot_login(db, owner):
    owner.is_active = False
    db.commit()
    assert authenticate(db, "owner@acme.com", PW) is None
    db.refresh(owner)
    assert owner.last_login_at is None


def test_old_weak_hash_is_upgraded_on_login(db, owner):
    weak = PasswordHasher(time_cost=1, memory_cost=8, parallelism=1).hash(PW)
    owner.password_hash = weak
    db.commit()
    assert authenticate(db, "owner@acme.com", PW) is not None
    db.refresh(owner)
    assert owner.password_hash != weak
    assert verify_password(owner.password_hash, PW)


# --- duplicate email normalization ----------------------------------------

def test_duplicate_email_differing_only_in_case_refused(db, owner):
    with pytest.raises(AccountError):
        register_agency_with_owner(
            db, agency_name="Other", email="OWNER@ACME.COM", display_name="X",
            password_hash=hash_password(PW),
        )


# --- admin bootstrap -------------------------------------------------------

def test_bootstrap_disabled_by_default(db, monkeypatch):
    monkeypatch.delenv("ALLOW_ADMIN_BOOTSTRAP", raising=False)
    with pytest.raises(AccountError):
        create_platform_staff(db, email="a@x.com", display_name="A", password=PW)
    assert db.query(User).count() == 0


def test_bootstrap_refused_in_production_even_if_enabled(db, monkeypatch):
    monkeypatch.setenv("ALLOW_ADMIN_BOOTSTRAP", "1")
    monkeypatch.setenv("APP_ENV", "Production")
    with pytest.raises(AccountError):
        create_platform_staff(db, email="a@x.com", display_name="A", password=PW)
    assert db.query(User).count() == 0


def test_bootstrap_creates_agencyless_admin_who_can_login(db, monkeypatch):
    monkeypatch.setenv("ALLOW_ADMIN_BOOTSTRAP", "1")
    monkeypatch.delenv("APP_ENV", raising=False)
    admin = create_platform_staff(db, email="Boss@Vtechys.com", display_name="Boss", password=PW)
    assert admin.platform_role == "platform_admin"
    assert admin.agency_id is None and admin.agency_role is None
    assert authenticate(db, "boss@vtechys.com", PW).id == admin.id


def test_bootstrap_rejects_customer_role(db, monkeypatch):
    monkeypatch.setenv("ALLOW_ADMIN_BOOTSTRAP", "1")
    with pytest.raises(AccountError):
        create_platform_staff(db, email="a@x.com", display_name="A", password=PW, platform_role="customer")


# --- public registration can never create an admin (A11) ------------------

def test_registration_has_no_role_parameter_and_makes_customer(db):
    with pytest.raises(TypeError):
        register_agency_with_owner(
            db, agency_name="Evil", email="e@evil.com", display_name="E",
            password_hash=hash_password(PW), platform_role="platform_admin",
        )
    u = register_agency_with_owner(
        db, agency_name="Good", email="g@good.com", display_name="G", password_hash=hash_password(PW)
    )
    assert u.platform_role == "customer"


def test_no_route_can_reach_bootstrap():
    import pathlib
    for f in pathlib.Path("app").rglob("*.py"):
        if f.name == "accounts.py":
            continue
        assert "create_platform_staff" not in f.read_text(encoding="utf-8"), f
