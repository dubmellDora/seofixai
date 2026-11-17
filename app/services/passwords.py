"""Password hashing (S1-02). Argon2id only; plaintext never leaves this module.

Nothing here logs, returns or stores the plaintext. Callers keep only the hash.
"""

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

MIN_PASSWORD_LENGTH = 10
MAX_PASSWORD_LENGTH = 256  # stops someone hashing a 10 MB "password" to burn CPU

_hasher = PasswordHasher()  # library defaults: Argon2id with current safe cost

# Verified against when the email does not exist, so "unknown email" and
# "wrong password" cost the same time (no account-existence timing leak).
_DUMMY_HASH = _hasher.hash("not-a-real-password-for-timing")


class PasswordError(ValueError):
    """Password refused. Message is safe to show to the user."""


def validate_password(password: str | None) -> str:
    if not password or len(password) < MIN_PASSWORD_LENGTH:
        raise PasswordError(f"Use at least {MIN_PASSWORD_LENGTH} characters.")
    if len(password) > MAX_PASSWORD_LENGTH:
        raise PasswordError(f"Use at most {MAX_PASSWORD_LENGTH} characters.")
    return password


def hash_password(password: str | None) -> str:
    return _hasher.hash(validate_password(password))


def verify_password(password_hash: str | None, password: str | None) -> bool:
    """True only for a correct password. Never raises on bad input."""
    if not password or len(password) > MAX_PASSWORD_LENGTH:
        return False
    try:
        return _hasher.verify(password_hash or _DUMMY_HASH, password) and bool(password_hash)
    except (VerificationError, InvalidHashError):
        return False


def needs_rehash(password_hash: str) -> bool:
    """True if the stored hash uses older/weaker parameters than current."""
    return _hasher.check_needs_rehash(password_hash)
