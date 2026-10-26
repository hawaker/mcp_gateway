import pytest
from pydantic import ValidationError

from app.modules.mcp_gateway.auth.migrate_rule import lift_custom_request_from_rule
from app.modules.mcp_gateway.auth.schema import AuthConfigCreateSchema


def test_lift_prefers_form_over_json_and_strips_request_keys() -> None:
    rule = {
        "query": {"q": "{{user.uid}}"},
        "json": {"a": "1"},
        "form": {"b": "2"},
        "headers": {"X-App": "{{system.app}}"},
        "token_from": "json",
        "token_name": "token",
    }
    headers, query, body_type, body, cleaned = lift_custom_request_from_rule(rule)
    assert headers == {"X-App": "{{system.app}}"}
    assert query == {"q": "{{user.uid}}"}
    assert body_type == "form"
    assert body == {"b": "2"}
    assert cleaned == {"token_from": "json", "token_name": "token"}
    assert "query" not in cleaned


def test_lift_none_when_no_body_sections() -> None:
    headers, query, body_type, body, cleaned = lift_custom_request_from_rule({"token_from": "text"})
    assert headers is None
    assert query is None
    assert body_type == "none"
    assert body is None
    assert cleaned == {"token_from": "text"}


def test_create_custom_rejects_json_body_type_with_null_body() -> None:
    with pytest.raises((ValidationError, ValueError)):
        AuthConfigCreateSchema(
            system_id=1,
            method="custom",
            url="https://oa.example.com/login",
            rule={"token_from": "json", "token_name": "t"},
            http_method="POST",
            body_type="json",
            body=None,
        )


def test_create_custom_accepts_none_body() -> None:
    data = AuthConfigCreateSchema(
        system_id=1,
        method="custom",
        url="https://oa.example.com/login",
        rule={"token_from": "json", "token_name": "t"},
        http_method="POST",
        body_type="none",
        body=None,
        headers={"X-Key": "{{user.uid}}"},
        query={"id": "{{user.uid}}"},
    )
    assert data.body_type == "none"
    assert data.headers == {"X-Key": "{{user.uid}}"}
