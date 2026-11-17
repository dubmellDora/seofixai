"""Account creation rules (S1-01).

Public registration goes through register_agency_with_owner() and nothing else.
It takes no role argument on purpose: the only thing a public caller can create
is a customer who owns a brand-new agency. Platform staff are created by a
separate development-only bootstrap (never by a request).
"""

import os
import re
import unicodedata
from datetime import datetime, timezone

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..models import Agency, User
from .passwords import hash_password, needs_rehash, verify_password


class AccountError(ValueError):
    """Registration was refused. The message is safe to show to the user."""


def normalize_email(raw: str | None) -> str:
    """Trim and lowercase so 'Bob@X.com ' and 'bob@x.com' are the same account."""
    email = (raw or "").strip().lower()
    # Deliberately light: real verification is the confirmation email (S1-05).
    if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
        raise AccountError("Enter a valid email address.")
    return email


def slugify(name: str) -> str:
    """'Acme SEO  Agency!' -> 'acme-seo-agency' (lowercase, a-z 0-9 and dashes)."""
    ascii_name = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    slug = re.sub(r"[^a-z0-9]+", "-", ascii_name.lower()).strip("-")
    if not slug:
        raise AccountError("Enter an agency name.")
    return slug


def register_agency_with_owner(
    db: Session,
    *,
    agency_name: str,
    email: str,
    display_name: str,
    password_hash: str,
    slug: str | None = None,
) -> User:
    """Create an Agency and its owner User atomically; return the User.

    Atomic means both rows are saved together or neither is. If the email or
    slug is already taken, the transaction is rolled back and AccountError is
    raised, so a half-created account can never exist.

    `password_hash` must already be an Argon2 hash (S1-02). This function never
    sees a plaintext password.
    """
    agency_name = (agency_name or "").strip()
    display_name = (display_name or "").strip()
    if not agency_name:
        raise AccountError("Enter an agency name.")
    if not display_name:
        raise AccountError("Enter your name.")
    if not password_hash:
        raise AccountError("A password is required.")

    normalized_email = normalize_email(email)
    agency_slug = slugify(slug or agency_name)

    # Pre-checks give friendly messages; the unique constraints in the database
    # are the real guarantee (two simultaneous requests can both pass these).
    if db.query(User.id).filter(User.email == normalized_email).first():
        raise AccountError("An account with this email already exists.")
    if db.query(Agency.id).filter(Agency.slug == agency_slug).first():
        raise AccountError("That agency name is already taken.")

    agency = Agency(name=agency_name, slug=agency_slug)
    user = User(
        agency=agency,
        email=normalized_email,
        display_name=display_name,
        password_hash=password_hash,
        platform_role="customer",  # fixed: public registration can never choose
        agency_role="owner",
    )
    db.add_all([agency, user])
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise AccountError("That email or agency name is already taken.") from None
    return user


def authenticate(db: Session, email: str | None, password: str | None) -> User | None:
    """Return the User for a correct email+password, else None.

    One generic failure for every cause (unknown email, wrong password,
    deactivated user) so a caller cannot tell which accounts exist. A
    deactivated user, or one whose agency is suspended, never authenticates
    here; the agency-suspended 403 is handled by the auth dependency (S1-04)
    because it needs a session to show a message.
    Password is always verified (even for unknown emails) to keep timing equal.
    """
    try:
        normalized = normalize_email(email)
    except AccountError:
        normalized = ""
    user = db.query(User).filter(User.email == normalized).first() if normalized else None
    ok = verify_password(user.password_hash if user else None, password)
    if not (user and ok and user.is_active):
        return None
    now = datetime.now(timezone.utc).replace(tzinfo=None)  # models store naive UTC
    user.last_login_at = now
    if needs_rehash(user.password_hash):
        user.password_hash = hash_password(password)
    db.commit()
    return user


def create_platform_staff(
    db: Session,
    *,
    email: str,
    display_name: str,
    password: str,
    platform_role: str = "platform_admin",
) -> User:
    """Create a platform_admin/support_admin. Development bootstrap ONLY.

    Refuses unless ALLOW_ADMIN_BOOTSTRAP=1 is set in the environment and
    APP_ENV is not "production". No route calls this; it is reached only from
    scripts/bootstrap_admin.py run by a person at a terminal.
    """
    if os.environ.get("ALLOW_ADMIN_BOOTSTRAP") != "1":
        raise AccountError("Admin bootstrap is disabled.")
    if os.environ.get("APP_ENV", "").lower() == "production":
        raise AccountError("Admin bootstrap is disabled in production.")
    if platform_role not in ("platform_admin", "support_admin"):
        raise AccountError("Invalid staff role.")
    display_name = (display_name or "").strip()
    if not display_name:
        raise AccountError("Enter a name.")
    normalized_email = normalize_email(email)
    if db.query(User.id).filter(User.email == normalized_email).first():
        raise AccountError("An account with this email already exists.")
    user = User(
        agency_id=None,
        email=normalized_email,
        display_name=display_name,
        password_hash=hash_password(password),
        platform_role=platform_role,
        agency_role=None,
    )
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise AccountError("An account with this email already exists.") from None
    return user
