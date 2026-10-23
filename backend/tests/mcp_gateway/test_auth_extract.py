"""从上游响应取值，并把相对地址接到业务系统 base_url 上。不访问 OA，不写 Redis。"""

from datetime import UTC, datetime, timedelta

import pytest

from app.modules.mcp_gateway.auth.extract import (
    REGEX_MATCH_TIMEOUT_SECONDS,
    REGEX_MAX_INPUT_LENGTH,
    TokenExtractError,
    extract_token,
    resolve_url,
)


def _around(seconds: float, moment: datetime) -> tuple[datetime, datetime]:
    slack = timedelta(seconds=2)
    delta = timedelta(seconds=seconds)
    return moment - slack + delta, moment + slack + delta


def test_extract_token_from_header_and_join_relative_url():
    bundle = extract_token(
        body="",
        headers={"X-Token": "Bearer abc", "X-Expires-In": "3600"},
        rule={
            "token_from": "header",
            "token_name": "X-Token",
            "expires_from": "header",
            "expires_name": "X-Expires-In",
            "expires_unit": "seconds",
        },
    )
    assert bundle.access_token == "abc"
    assert bundle.token_type == "Bearer"
    low, high = _around(3600, datetime.now(UTC))
    assert low <= bundle.expires_at <= high
    assert bundle.expires_at.tzinfo is not None
    assert resolve_url("https://oa.example.com", "/login") == "https://oa.example.com/login"
    assert resolve_url("https://oa.example.com", "https://auth.example.com/login") == "https://auth.example.com/login"
    assert resolve_url("https://oa.example.com", "http://auth.example.com/login") == "http://auth.example.com/login"


def test_extract_token_from_set_cookie_by_cookie_name():
    bundle = extract_token(
        body="",
        headers={"Set-Cookie": "sid=Bearer abc; Path=/; HttpOnly"},
        rule={
            "token_from": "header",
            "token_name": "Set-Cookie",
            "cookie_name": "sid",
            "expires_seconds": 60,
        },
    )
    assert bundle.access_token == "abc"


def test_extract_token_from_json_path():
    bundle = extract_token(
        body='{"data": {"access_token": "json-tok", "expires_in": 10}}',
        headers={},
        rule={
            "token_from": "json",
            "token_name": "data.access_token",
            "expires_from": "json",
            "expires_name": "data.expires_in",
            "expires_unit": "seconds",
        },
    )
    assert bundle.access_token == "json-tok"
    low, high = _around(10, datetime.now(UTC))
    assert low <= bundle.expires_at <= high


def test_extract_token_from_form_field_with_absolute_expiry():
    bundle = extract_token(
        body="access_token=form-tok&expires_at=2026-12-01T00%3A00%3A00Z",
        headers={},
        rule={
            "token_from": "form",
            "token_name": "access_token",
            "expires_from": "form",
            "expires_name": "expires_at",
            "expires_unit": "absolute",
        },
    )
    assert bundle.access_token == "form-tok"
    assert bundle.expires_at == datetime(2026, 12, 1, tzinfo=UTC)


def test_extract_token_from_whole_text_uses_fixed_seconds_when_expiry_missing():
    before = datetime.now(UTC)
    bundle = extract_token(
        body="plain-token",
        headers={},
        rule={"token_from": "text", "expires_seconds": 90},
    )
    after = datetime.now(UTC)
    assert bundle.access_token == "plain-token"
    assert before + timedelta(seconds=90) <= bundle.expires_at <= after + timedelta(seconds=90)


def test_extract_token_from_regex_first_group_and_input_cap():
    assert isinstance(REGEX_MAX_INPUT_LENGTH, int) and REGEX_MAX_INPUT_LENGTH > 0
    assert isinstance(REGEX_MATCH_TIMEOUT_SECONDS, (int, float)) and REGEX_MATCH_TIMEOUT_SECONDS > 0

    bundle = extract_token(
        body='token="cap-1" tail',
        headers={},
        rule={"token_from": "regex", "token_name": r'token="([^"]+)"', "expires_seconds": 30},
    )
    assert bundle.access_token == "cap-1"

    late = ("x" * REGEX_MAX_INPUT_LENGTH) + "token=late"
    with pytest.raises(TokenExtractError):
        extract_token(
            body=late,
            headers={},
            rule={"token_from": "regex", "token_name": r"token=(\w+)", "expires_seconds": 30},
        )

    within = "token=early&" + ("x" * REGEX_MAX_INPUT_LENGTH)
    kept = extract_token(
        body=within,
        headers={},
        rule={"token_from": "regex", "token_name": r"token=(\w+)", "expires_seconds": 30},
    )
    assert kept.access_token == "early"


def test_regex_match_stops_at_named_timeout(monkeypatch: pytest.MonkeyPatch):
    import time

    import app.modules.mcp_gateway.auth.extract as extract

    monkeypatch.setattr(extract, "REGEX_MATCH_TIMEOUT_SECONDS", 0.05)

    def slow_search(compiled: object, text: str) -> None:  # noqa: ARG001
        time.sleep(0.4)
        return None

    monkeypatch.setattr(extract, "_call_search", slow_search)
    started = time.monotonic()
    with pytest.raises(TokenExtractError):
        extract.extract_token(
            body="hello",
            headers={},
            rule={"token_from": "regex", "token_name": "(hello)", "expires_seconds": 10},
        )
    assert time.monotonic() - started < 0.3
