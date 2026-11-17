"""S1-03c tests: CSRF decision rule."""

import pytest

from app.services.csrf import csrf_ok, origin_is_allowed

HOSTS = {"app.seofixai.com"}
TOKEN = "s3cret-token"


def check(**over):
    args = dict(
        method="POST", session_token=TOKEN, header_token=TOKEN, form_token=None,
        origin="https://app.seofixai.com", allowed_hosts=HOSTS,
    )
    args.update(over)
    return csrf_ok(**args)


@pytest.mark.parametrize("m", ["GET", "HEAD", "OPTIONS", "get"])
def test_safe_methods_need_no_token(m):
    assert check(method=m, header_token=None, origin="https://evil.com") is True


@pytest.mark.parametrize("m", ["POST", "PUT", "PATCH", "DELETE", "post"])
def test_state_changing_methods_pass_with_header_token(m):
    assert check(method=m) is True


def test_form_field_token_also_accepted():
    assert check(header_token=None, form_token=TOKEN) is True


def test_missing_token_refused():
    assert check(header_token=None, form_token=None) is False


def test_wrong_token_refused():
    assert check(header_token="nope") is False
    assert check(header_token=TOKEN[:-1]) is False
    assert check(header_token=TOKEN + "x") is False


def test_no_session_refused_even_with_a_token():
    assert check(session_token=None) is False
    assert check(session_token="") is False


def test_foreign_origin_refused_even_with_valid_token():
    assert check(origin="https://evil.com") is False
    assert check(origin="null") is False
    assert check(origin="https://app.seofixai.com.evil.com") is False  # no suffix tricks


def test_missing_origin_falls_back_to_token_only():
    assert check(origin=None) is True
    assert check(origin=None, header_token=None) is False


def test_origin_with_port_and_case_normalised():
    assert origin_is_allowed("HTTPS://App.SeoFixAI.com:443", HOSTS) is True


def test_admin_host_token_from_app_origin_refused():
    # a page on app. must not be able to drive admin. requests
    assert check(origin="https://app.seofixai.com", allowed_hosts={"admin.seofixai.com"}) is False
