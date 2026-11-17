"""CSRF protection (S1-03c).

The attack: you are logged in to app.seofixai.com. You visit evil.com, whose page
silently submits a form to app.seofixai.com/projects/1/delete. Your browser
attaches your cookie, so without a second check the server would obey.

The defence: every state-changing request must ALSO carry a secret that only our
own pages know: the per-session csrf_token (stored in user_sessions). evil.com
cannot read it, so it cannot forge a valid request. We add an Origin check as a
second layer.

Safe methods (GET/HEAD/OPTIONS) never change state, so they are not checked.
That makes it a rule for every route: a GET must never change anything.
"""

import hmac

from ..host_routing import host_from_origin

SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})
HEADER_NAME = "X-CSRF-Token"   # sent by HTMX / fetch
FORM_FIELD = "csrf_token"      # hidden input in plain HTML forms


def origin_is_allowed(origin: str | None, allowed_hosts: set[str]) -> bool:
    """True if the Origin header is absent, or names one of our own hosts.

    A missing Origin is allowed here because some legitimate clients omit it;
    the token check still applies. A present-but-foreign Origin ("null",
    "https://evil.com") is always refused.
    """
    if origin is None:
        return True
    if origin.strip().lower() == "null":
        return False
    return host_from_origin(origin) in allowed_hosts


def csrf_ok(
    *,
    method: str,
    session_token: str | None,
    header_token: str | None,
    form_token: str | None,
    origin: str | None,
    allowed_hosts: set[str],
) -> bool:
    """Decide whether a request passes the CSRF check. Deny by default."""
    if method.upper() in SAFE_METHODS:
        return True
    if not session_token:  # no session to compare against -> refuse
        return False
    if not origin_is_allowed(origin, allowed_hosts):
        return False
    supplied = header_token or form_token
    if not supplied:
        return False
    # constant-time compare: response time must not reveal how many characters matched
    return hmac.compare_digest(supplied.encode(), session_token.encode())
