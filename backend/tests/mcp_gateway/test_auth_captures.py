"""custom 多变量 captures 抽取。"""

from datetime import UTC, datetime

import pytest

from app.modules.mcp_gateway.auth.extract import (
    TokenExtractError,
    extract_captures,
    normalize_captures,
)


def test_normalize_legacy_token_fields_to_captures():
    assert normalize_captures({"token_from": "json", "token_name": "data.token"}) == [
        {"name": "access_token", "from": "json", "path": "data.token"}
    ]


def test_normalize_prefers_explicit_captures():
    rule = {
        "captures": [{"name": "session", "from": "json", "path": "sid"}],
        "token_from": "json",
        "token_name": "ignored",
    }
    assert normalize_captures(rule) == [{"name": "session", "from": "json", "path": "sid"}]


def test_extract_captures_multiple_without_access_token():
    body = '{"a": "1", "b": "2"}'
    bundle = extract_captures(
        body=body,
        headers={},
        rule={
            "captures": [
                {"name": "tenant_id", "from": "json", "path": "a"},
                {"name": "session", "from": "json", "path": "b"},
            ],
            "expires_seconds": 60,
        },
    )
    assert bundle.vars == {"tenant_id": "1", "session": "2"}
    assert bundle.access_token == ""
    assert bundle.token_type == "Bearer"
    assert bundle.expires_at > datetime.now(UTC)


def test_extract_captures_requires_at_least_one():
    with pytest.raises(TokenExtractError):
        extract_captures(body="{}", headers={}, rule={"captures": [], "expires_seconds": 30})


def test_extract_captures_rejects_duplicate_names():
    with pytest.raises(TokenExtractError):
        extract_captures(
            body='{"a":"1"}',
            headers={},
            rule={
                "captures": [
                    {"name": "x", "from": "json", "path": "a"},
                    {"name": "x", "from": "json", "path": "a"},
                ],
                "expires_seconds": 30,
            },
        )
