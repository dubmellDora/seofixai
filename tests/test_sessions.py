"""S1-03a tests: server-side session lifecycle."""

from datetime import timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models import UserSession
from app.services import sessions as S
from app.services.accounts import register_agency_with_owner

HASH = "$argon2id$placeholder"


@pytest.fixture()
def db():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    s = sessionmaker(bind=engine)()
    yield s
    s.close()
    engine.dispose()


@pytest.fixture()
def user(db):
    return register_agency_with_owner(
        db, agency_name="Acme", email="o@acme.com", display_name="O", password_hash=HASH
    )


def test_token_is_random_and_only_hash_is_stored(db, user):
    t1, r1 = S.create_session(db, user, "app")
    t2, _ = S.create_session(db, user, "app")
    assert t1 != t2
    assert r1.token_hash == S.hash_token(t1) and t1 not in r1.token_hash


def test_valid_cookie_returns_session(db, user):
    token, row = S.create_session(db, user, "app")
    assert S.get_valid_session(db, token, "app").id == row.id


@pytest.mark.parametrize("bad", [None, "", "garbage", "x" * 500])
def test_unknown_or_tampered_token_is_logged_out(db, user, bad):
    S.create_session(db, user, "app")
    assert S.get_valid_session(db, bad, "app") is None


def test_one_changed_character_fails(db, user):
    token, _ = S.create_session(db, user, "app")
    tampered = token[:-1] + ("A" if token[-1] != "A" else "B")
    assert S.get_valid_session(db, tampered, "app") is None


def test_absolute_expiry(db, user):
    token, row = S.create_session(db, user, "admin")
    row.expires_at = S._now() - timedelta(seconds=1)
    db.commit()
    assert S.get_valid_session(db, token, "admin") is None


def test_idle_expiry(db, user):
    token, row = S.create_session(db, user, "admin")
    row.last_seen_at = S._now() - timedelta(minutes=31)
    db.commit()
    assert S.get_valid_session(db, token, "admin") is None


def test_activity_slides_idle_but_not_absolute_limit(db, user):
    token, row = S.create_session(db, user, "app")
    limit = row.expires_at
    row.last_seen_at = S._now() - timedelta(hours=2)
    db.commit()
    assert S.get_valid_session(db, token, "app") is not None
    db.refresh(row)
    assert row.last_seen_at > S._now() - timedelta(minutes=1)
    assert row.expires_at == limit


def test_cookie_from_one_host_kind_is_useless_on_the_other(db, user):
    token, _ = S.create_session(db, user, "app")
    assert S.get_valid_session(db, token, "admin") is None


def test_logout_revokes(db, user):
    token, row = S.create_session(db, user, "app")
    S.revoke_session(db, row)
    assert S.get_valid_session(db, token, "app") is None


def test_deactivated_user_session_stops_working(db, user):
    token, _ = S.create_session(db, user, "app")
    user.is_active = False
    db.commit()
    assert S.get_valid_session(db, token, "app") is None


def test_rotation_kills_old_token_and_issues_new(db, user):
    old_token, old = S.create_session(db, user, "app")
    new_token, new = S.rotate_session(db, old)
    assert new_token != old_token and new.id != old.id
    assert S.get_valid_session(db, old_token, "app") is None
    assert S.get_valid_session(db, new_token, "app") is not None


def test_revoke_all_for_user_models_password_reset(db, user):
    tokens = [S.create_session(db, user, "app")[0] for _ in range(3)]
    assert S.revoke_all_for_user(db, user.id) == 3
    assert all(S.get_valid_session(db, t, "app") is None for t in tokens)


def test_cleanup_removes_expired_keeps_live(db, user):
    live_token, _ = S.create_session(db, user, "app")
    _, dead = S.create_session(db, user, "app")
    dead.expires_at = S._now() - timedelta(days=1)
    db.commit()
    assert S.delete_expired(db) == 1
    assert db.query(UserSession).count() == 1
    assert S.get_valid_session(db, live_token, "app") is not None
