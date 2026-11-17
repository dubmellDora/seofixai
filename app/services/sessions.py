"""Server-side sessions (S1-03a).

Lifecycle
  create   : login makes a NEW random token every time (never reuses one).
  validate : cookie token -> sha256 -> row. Rejected if unknown, revoked,
             past its absolute expiry, idle too long, or the user is
             deactivated. Anything wrong returns None ("treated as logged out").
  rotate   : on privilege change, revoke the old session and issue a new token
             (stops "session fixation": an attacker keeping an old id alive).
  revoke   : logout kills one session; revoke_all_for_user kills every session
             (password reset, deactivation).
  cleanup  : delete_expired() removes dead rows; run it from the scheduler.
"""

import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy import or_
from sqlalchemy.orm import Session

from ..models import User, UserSession

# host_kind -> (absolute lifetime, idle timeout). Admin is stricter on purpose.
LIFETIMES = {
    "app": (timedelta(days=14), timedelta(hours=24)),
    "admin": (timedelta(hours=8), timedelta(minutes=30)),
}
TOUCH_EVERY = timedelta(minutes=1)  # don't write to the DB on every request


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)  # models store naive UTC


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def create_session(db: Session, user: User, host_kind: str) -> tuple[str, UserSession]:
    """Return (raw_token, row). Put raw_token in the cookie; it is never stored."""
    if host_kind not in LIFETIMES:
        raise ValueError("host_kind must be 'app' or 'admin'")
    absolute, _idle = LIFETIMES[host_kind]
    token = secrets.token_urlsafe(32)  # 256 bits from the OS random source
    now = _now()
    row = UserSession(
        user_id=user.id,
        token_hash=hash_token(token),
        csrf_token=secrets.token_urlsafe(32),
        host_kind=host_kind,
        created_at=now,
        last_seen_at=now,
        expires_at=now + absolute,
    )
    db.add(row)
    db.commit()
    return token, row


def get_valid_session(db: Session, token: str | None, host_kind: str) -> UserSession | None:
    """The live session for this cookie token on this host, else None."""
    if not token or len(token) > 200:
        return None
    row = db.query(UserSession).filter(UserSession.token_hash == hash_token(token)).first()
    if row is None or row.revoked_at is not None:
        return None
    # An admin-host cookie must never work on the app host and vice versa.
    if not hmac.compare_digest(row.host_kind, host_kind):
        return None
    now = _now()
    _absolute, idle = LIFETIMES[row.host_kind]
    if now >= row.expires_at or now - row.last_seen_at >= idle:
        return None
    if not row.user.is_active:
        return None
    if now - row.last_seen_at >= TOUCH_EVERY:
        row.last_seen_at = now
        db.commit()
    return row


def rotate_session(db: Session, old: UserSession) -> tuple[str, UserSession]:
    """Replace a session with a fresh one (use after privilege changes)."""
    old.revoked_at = _now()
    db.commit()
    return create_session(db, old.user, old.host_kind)


def revoke_session(db: Session, row: UserSession) -> None:
    if row.revoked_at is None:
        row.revoked_at = _now()
        db.commit()


def revoke_all_for_user(db: Session, user_id) -> int:
    """Kill every live session of a user. Returns how many were revoked."""
    n = (
        db.query(UserSession)
        .filter(UserSession.user_id == user_id, UserSession.revoked_at.is_(None))
        .update({UserSession.revoked_at: _now()})
    )
    db.commit()
    return n


def delete_expired(db: Session) -> int:
    """Remove rows that are expired or revoked for over a day (cleanup job)."""
    now = _now()
    n = (
        db.query(UserSession)
        .filter(
            or_(
                UserSession.expires_at < now,
                UserSession.revoked_at < now - timedelta(days=1),
            )
        )
        .delete(synchronize_session=False)
    )
    db.commit()
    return n
