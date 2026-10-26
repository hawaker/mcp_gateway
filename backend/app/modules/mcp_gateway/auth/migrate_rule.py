"""把旧 rule 里的请求外形抬升到独立字段。"""

from typing import Any, Literal

BodyType = Literal["none", "json", "form"]
_REQUEST_KEYS = ("query", "json", "form", "headers")


def _str_map(raw: Any) -> dict[str, str] | None:
    if not isinstance(raw, dict) or not raw:
        return None
    return {str(k): "" if v is None else str(v) for k, v in raw.items() if str(k).strip()}


def lift_custom_request_from_rule(
    rule: dict[str, Any],
) -> tuple[dict[str, str] | None, dict[str, str] | None, BodyType, dict[str, Any] | None, dict[str, Any]]:
    cleaned = {k: v for k, v in rule.items() if k not in _REQUEST_KEYS}
    headers = _str_map(rule.get("headers"))
    query = _str_map(rule.get("query"))
    form = _str_map(rule.get("form"))
    raw_json = rule.get("json")
    if form is not None:
        return headers, query, "form", form, cleaned
    if isinstance(raw_json, dict):
        return headers, query, "json", dict(raw_json), cleaned
    return headers, query, "none", None, cleaned
