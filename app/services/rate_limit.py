"""Login throttling (S1-03d).

Rules (failures counted inside the sliding WINDOW):
  - 5 failures for one email  -> that email is blocked
  - 20 failures from one IP   -> that IP is blocked
The check runs BEFORE the password is verified, and it keys on the email the
caller typed, whether or not an account exists. So the response for "blocked"
is identical for real and fake emails (no account-existence leak).

Trade-off, stated honestly: an attacker can deliberately lock a victim's email
for 15 minutes by failing 5 times. We accept that (it is temporary and the
victim keeps their data); permanent lockout would be worse. The per-IP limit
and Cloudflare's own rate limit are the outer layers.

Callers must pass the real client IP. Behind Cloudflare/a proxy that comes from
a trusted header, never from a header the browser can set freely (S1-05 wires
this; see the reverse-proxy contract in docs/Hostname_Matrix.md).
"""

import hashlib
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from ..models import LoginAttempt

WINDOW = timedelta(minutes=15)
MAX_FAILURES_PER_EMAIL = 5
MAX_FAILURES_PER_IP = 20


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def email_key(email: str | None) -> str:
    return hashlib.sha256((email or "").strip().lower().encode()).hexdigest()


def is_blocked(db: Session, email: str | None, ip: str) -> bool:
    since = _now() - WINDOW
    q = db.query(LoginAttempt).filter(LoginAttempt.created_at >= since)
    if q.filter(LoginAttempt.email_hash == email_key(email)).count() >= MAX_FAILURES_PER_EMAIL:
        return True
    return q.filter(LoginAttempt.ip == ip).count() >= MAX_FAILURES_PER_IP


def record_failure(db: Session, email: str | None, ip: str) -> None:
    db.add(LoginAttempt(email_hash=email_key(email), ip=ip[:64]))
    db.commit()


def clear_email(db: Session, email: str | None) -> None:
    """After a successful login, forget that email's earlier failures."""
    db.query(LoginAttempt).filter(LoginAttempt.email_hash == email_key(email)).delete()
    db.commit()


def delete_old(db: Session) -> int:
    """Cleanup job: drop rows older than the window."""
    n = db.query(LoginAttempt).filter(LoginAttempt.created_at < _now() - WINDOW).delete()
    db.commit()
    return n
