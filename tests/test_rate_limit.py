"""S1-03d tests: login throttling."""

from datetime import timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models import LoginAttempt
from app.services import rate_limit as R


@pytest.fixture()
def db():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    s = sessionmaker(bind=engine)()
    yield s
    s.close()
    engine.dispose()


def fail(db, email, ip, n=1):
    for _ in range(n):
        R.record_failure(db, email, ip)


def test_not_blocked_initially(db):
    assert R.is_blocked(db, "a@x.com", "1.1.1.1") is False


def test_blocked_after_five_failures_for_same_email(db):
    fail(db, "a@x.com", "1.1.1.1", 4)
    assert R.is_blocked(db, "a@x.com", "1.1.1.1") is False
    fail(db, "a@x.com", "2.2.2.2")  # a different IP still counts against the email
    assert R.is_blocked(db, "a@x.com", "9.9.9.9") is True


def test_email_case_and_spaces_do_not_dodge_the_limit(db):
    fail(db, "A@X.com ", "1.1.1.1", 5)
    assert R.is_blocked(db, " a@x.COM", "3.3.3.3") is True


def test_other_email_unaffected(db):
    fail(db, "a@x.com", "1.1.1.1", 5)
    assert R.is_blocked(db, "b@x.com", "3.3.3.3") is False


def test_blocked_for_unknown_email_too_no_existence_leak(db):
    fail(db, "ghost-account@nowhere.test", "1.1.1.1", 5)
    assert R.is_blocked(db, "ghost-account@nowhere.test", "8.8.8.8") is True


def test_ip_blocked_after_twenty_failures_across_emails(db):
    for i in range(20):
        R.record_failure(db, f"user{i}@x.com", "5.5.5.5")
    assert R.is_blocked(db, "brand-new@x.com", "5.5.5.5") is True
    assert R.is_blocked(db, "brand-new@x.com", "6.6.6.6") is False


def test_failures_expire_after_window(db):
    fail(db, "a@x.com", "1.1.1.1", 5)
    old = R._now() - R.WINDOW - timedelta(seconds=1)
    db.query(LoginAttempt).update({LoginAttempt.created_at: old})
    db.commit()
    assert R.is_blocked(db, "a@x.com", "1.1.1.1") is False
    assert R.delete_old(db) == 5


def test_success_clears_that_emails_failures(db):
    fail(db, "a@x.com", "1.1.1.1", 4)
    R.clear_email(db, "a@x.com")
    assert db.query(LoginAttempt).count() == 0


def test_email_is_stored_hashed_not_plain(db):
    fail(db, "secret@x.com", "1.1.1.1")
    row = db.query(LoginAttempt).one()
    assert "secret" not in row.email_hash and len(row.email_hash) == 64
