"""把 REST 工具和调用参数收成一次上游请求。调试和正式调用共用这里。

URL 里的 {参数} 先替换。GET 的其余参数进 query，其他方法进 body。
query_mapping、header_mapping 把指名的参数放到对应位置。
工具 URL、配置的 header、token 槽位仍是模板。调用参数的值原样上送，不再渲染。
"""

import re
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any
from urllib.parse import quote

from app.modules.mcp_gateway.auth.client import CallerLiteral
from app.modules.mcp_gateway.auth.extract import resolve_url

_DOUBLE = re.compile(r"\{\{(?:system\.[A-Za-z0-9_]+|user\.uid|user\.attr\.[A-Za-z0-9_]+|token)\}\}")
_SINGLE = re.compile(r"\{([A-Za-z0-9_]+)\}")


class MissingUrlParameter(Exception):
    """URL 模板里的 {参数} 没有出现在这次调用参数中。此时不发业务请求。"""

    def __init__(self, name: str) -> None:
        self.name = name
        super().__init__(name)


@dataclass(frozen=True, slots=True)
class PreparedCall:
    method: str
    url: str
    headers: dict[str, Any]
    params: dict[str, Any] | None
    json_body: dict[str, Any] | None
    timeout: float | None


def prepare_call(base_url: str, tool: Mapping[str, Any], arguments: Mapping[str, Any] | None) -> PreparedCall:
    args = dict(arguments or {})
    url = _substitute_url(resolve_url(base_url, str(tool.get("url") or "")), args)
    method = str(tool.get("request_type") or "GET").upper()
    headers = _string_map(tool.get("headers"))
    params: dict[str, Any] = {}
    body: dict[str, Any] = {}
    query_mapping = _string_map(tool.get("query_mapping"))
    header_mapping = _string_map(tool.get("header_mapping"))

    if query_mapping:
        for source, target in query_mapping.items():
            if source in args:
                params[target] = CallerLiteral(args.pop(source))
    if header_mapping:
        for source, target in header_mapping.items():
            if source in args:
                headers[target] = CallerLiteral(_as_text(args.pop(source)))

    if method == "GET":
        for key, value in args.items():
            params[str(key)] = CallerLiteral(value)
    else:
        for key, value in args.items():
            body[str(key)] = CallerLiteral(value)

    _place_token(tool, headers, params, body)
    return PreparedCall(
        method=method,
        url=url,
        headers=headers,
        params=params or None,
        json_body=body or None,
        timeout=_timeout_seconds(tool.get("timeout_ms")),
    )


def _substitute_url(url: str, arguments: dict[str, Any]) -> str:
    held: list[str] = []

    def hold(match: re.Match[str]) -> str:
        held.append(match.group(0))
        return f"\x00{len(held) - 1}\x00"

    protected = _DOUBLE.sub(hold, url)

    def replace(match: re.Match[str]) -> str:
        key = match.group(1)
        if key not in arguments:
            raise MissingUrlParameter(key)
        return quote(_as_text(arguments.pop(key)), safe="")

    replaced = _SINGLE.sub(replace, protected)
    for index, text in enumerate(held):
        replaced = replaced.replace(f"\x00{index}\x00", text)
    return replaced


def _place_token(tool: Mapping[str, Any], headers: dict[str, Any], params: dict[str, Any], body: dict[str, Any]) -> None:
    token_in = str(tool.get("token_in") or "header")
    raw_name = tool.get("token_name")
    name = str(raw_name).strip() if raw_name else ""
    if token_in == "query":
        params[name or "token"] = "{{token}}"
        return
    if token_in == "body":
        body[name or "token"] = "{{token}}"
        return
    header_name = name or "Authorization"
    if header_name.lower() == "authorization":
        headers["Authorization"] = "Bearer {{token}}"
        return
    headers[header_name] = "{{token}}"


def _string_map(value: Any) -> dict[str, str]:
    if not isinstance(value, Mapping):
        return {}
    return {str(key): _as_text(item) for key, item in value.items()}


def _timeout_seconds(value: Any) -> float | None:
    if value is None or value == "":
        return None
    return float(value) / 1000.0


def _as_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value)
