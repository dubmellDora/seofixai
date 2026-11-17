"""Tests for app/host_routing.py (S0-04).

These pin down the security-relevant behaviour of host classification:
exact matches only, deny by default.
"""

import pytest

from app.host_routing import (
    HostConfig,
    HostKind,
    classify_host,
    host_guard_decision,
    normalize_host,
)

CONFIG = HostConfig(
    public_host="app.seofixai.com",
    admin_host="admin.seofixai.com",
    legacy_hosts=("seofixai.com",),
)


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("App.SeoFixAI.com:8000", "app.seofixai.com"),  # case + port
        ("seofixai.com.", "seofixai.com"),              # trailing dot
        ("  admin.seofixai.com ", "admin.seofixai.com"),  # stray spaces
        ("[::1]:8000", "[::1]"),                        # IPv6 keeps its colons
        ("127.0.0.1:8000", "127.0.0.1"),
        ("", ""),
        (None, ""),
    ],
)
def test_normalize_host(raw, expected):
    assert normalize_host(raw) == expected


@pytest.mark.parametrize(
    "raw, expected",
    [
        # --- trusted hosts, in different spellings ---
        ("app.seofixai.com", HostKind.PUBLIC),
        ("APP.SeoFixAI.com", HostKind.PUBLIC),
        ("app.seofixai.com:443", HostKind.PUBLIC),
        ("admin.seofixai.com", HostKind.ADMIN),
        ("seofixai.com", HostKind.LEGACY),
        ("seofixai.com.", HostKind.LEGACY),
        # --- look-alikes that an endswith/startswith check would wrongly accept ---
        ("evilseofixai.com", HostKind.UNKNOWN),
        ("app.seofixai.com.evil.com", HostKind.UNKNOWN),
        ("evil.com/app.seofixai.com", HostKind.UNKNOWN),
        ("app.seofixai.com@evil.com", HostKind.UNKNOWN),
        ("xadmin.seofixai.com", HostKind.UNKNOWN),
        # --- subdomains we never listed ---
        ("sub.app.seofixai.com", HostKind.UNKNOWN),
        ("www.seofixai.com", HostKind.UNKNOWN),
        # --- missing or junk ---
        ("", HostKind.UNKNOWN),
        (None, HostKind.UNKNOWN),
        ("   ", HostKind.UNKNOWN),
        ("127.0.0.1:8000", HostKind.UNKNOWN),
        ("localhost", HostKind.UNKNOWN),
    ],
)
def test_classify_host(raw, expected):
    assert classify_host(raw, CONFIG) == expected


def test_no_legacy_hosts_means_apex_is_unknown():
    config = HostConfig(public_host="app.seofixai.com", admin_host="admin.seofixai.com")
    assert classify_host("seofixai.com", config) == HostKind.UNKNOWN


def test_config_cannot_be_changed_after_creation():
    with pytest.raises(Exception):
        CONFIG.public_host = "evil.com"


@pytest.mark.parametrize(
    "kind, path, expected",
    [
        # unknown host: always 421, even for /health
        (HostKind.UNKNOWN, "/", 421),
        (HostKind.UNKNOWN, "/health", 421),
        (HostKind.UNKNOWN, "/admin/login", 421),
        # public host: customer pages pass, admin paths are hidden
        (HostKind.PUBLIC, "/", None),
        (HostKind.PUBLIC, "/projects/1", None),
        (HostKind.PUBLIC, "/admin", 404),
        (HostKind.PUBLIC, "/admin/login", 404),
        (HostKind.PUBLIC, "/administrator-notes", None),  # not under /admin/
        # admin host: only /admin... is served
        (HostKind.ADMIN, "/admin", None),
        (HostKind.ADMIN, "/admin/login", None),
        (HostKind.ADMIN, "/", 404),
        (HostKind.ADMIN, "/projects/1", 404),
        (HostKind.ADMIN, "/administrator-notes", 404),
        # legacy host behaves like public
        (HostKind.LEGACY, "/", None),
        (HostKind.LEGACY, "/admin/login", 404),
        # /health is allowed on every known host
        (HostKind.PUBLIC, "/health", None),
        (HostKind.ADMIN, "/health", None),
        (HostKind.LEGACY, "/health", None),
    ],
)
def test_host_guard_decision(kind, path, expected):
    assert host_guard_decision(kind, path) == expected
