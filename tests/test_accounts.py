"""S1-01 tests: Agency/User constraints and atomic registration.

Uses an in-memory SQLite database so nothing touches the real app database.
"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models import Agency, User
from app.services.accounts import (
    AccountError,
    normalize_email,
    register_agency_with_owner,
    slugify,
)

HASH = "$argon2id$placeholder"  # S1-02 adds real hashing; these tests never verify it


@pytest.fixture()
def db():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    yield session
    session.close()
    engine.dispose()


def register(db, **over):
    args = dict(agency_name="Acme SEO", email="owner@acme.com", display_name="Olivia", password_hash=HASH)
    args.update(over)
    return register_agency_with_owner(db, **args)


@pytest.mark.parametrize(
    "raw, expected",
    [("Bob@X.com", "bob@x.com"), ("  bob@x.com \n", "bob@x.com"), ("BOB@X.COM", "bob@x.com")],
)
def test_normalize_email(raw, expected):
    assert normalize_email(raw) == expected


@pytest.mark.parametrize("raw", ["", None, "no-at-sign", "a@b", "a b@c.com", "@c.com"])
def test_normalize_email_rejects_bad(raw):
    with pytest.raises(AccountError):
        normalize_email(raw)


@pytest.mark.parametrize(
    "name, slug",
    [("Acme SEO Agency!", "acme-seo-agency"), ("  Café  Ünïcode ", "cafe-unicode"), ("a--b", "a-b")],
)
def test_slugify(name, slug):
    assert slugify(name) == slug


def test_slugify_rejects_empty():
    with pytest.raises(AccountError):
        slugify("!!!")


def test_registration_creates_agency_and_owner(db):
    user = register(db)
    assert user.platform_role == "customer"
    assert user.agency_role == "owner"
    assert user.is_active and user.email_verified_at is None
    assert user.agency.slug == "acme-seo" and user.agency.is_active
    assert db.query(Agency).count() == 1 and db.query(User).count() == 1


def test_duplicate_email_is_rejected_after_normalizing(db):
    register(db)
    with pytest.raises(AccountError):
        register(db, agency_name="Other", email="  OWNER@Acme.com ")
    assert db.query(Agency).count() == 1  # no orphan agency left behind


def test_duplicate_agency_slug_is_rejected(db):
    register(db)
    with pytest.raises(AccountError):
        register(db, email="second@acme.com", agency_name="ACME  seo")
    assert db.query(User).count() == 1


def test_registration_has_no_way_to_choose_a_role(db):
    with pytest.raises(TypeError):
        register(db, platform_role="platform_admin")
    with pytest.raises(TypeError):
        register(db, agency_role="member")


def test_blank_fields_are_rejected(db):
    for bad in ({"agency_name": " "}, {"display_name": ""}, {"password_hash": ""}):
        with pytest.raises(AccountError):
            register(db, **bad)
    assert db.query(Agency).count() == 0


def test_deactivated_user_flag_persists(db):
    user = register(db)
    user.is_active = False
    db.commit()
    assert db.get(User, user.id).is_active is False


# --- the database itself refuses bad rows, even if the service is bypassed ---

def test_db_rejects_uppercase_email(db):
    agency = Agency(name="A", slug="a")
    db.add(User(agency=agency, email="Bob@X.com", display_name="B", password_hash=HASH, agency_role="owner"))
    with pytest.raises(IntegrityError):
        db.commit()


def test_db_rejects_unknown_platform_role(db):
    agency = Agency(name="A", slug="a")
    db.add(User(agency=agency, email="b@x.com", display_name="B", password_hash=HASH,
                platform_role="superuser", agency_role="owner"))
    with pytest.raises(IntegrityError):
        db.commit()


def test_db_rejects_customer_without_agency(db):
    db.add(User(email="b@x.com", display_name="B", password_hash=HASH))
    with pytest.raises(IntegrityError):
        db.commit()


def test_platform_admin_needs_no_agency(db):
    db.add(User(email="staff@x.com", display_name="S", password_hash=HASH, platform_role="platform_admin"))
    db.commit()
    assert db.query(User).one().agency_id is None
