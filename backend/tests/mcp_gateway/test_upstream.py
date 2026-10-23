"""上游 MCP：一份加密凭证、JSON-RPC 转发、未选用的工具不发出请求。

测试用 MockTransport，不访问真实 MCP，也不启动 FastAPI。
"""

import json
from typing import Any

import httpx
import pytest
from pydantic import ValidationError

from app.core.exceptions import CustomException
from app.modules.mcp_gateway.auth.client import AuthClient
from app.utils.crypto_util import CryptoUtil

UPSTREAM_ID = 7
SYSTEM_ID = 10
SYSTEM_CODE = "oa"
REMOTE_NAME = "search_docs"
EXTERNAL_NAME = "oa_search_docs"
PLAIN_CREDENTIAL = "upstream-secret"
BUSINESS_TOKEN = "biz-access-token"
BINDING_UID = "zhangsan"
BASE_URL = "https://oa.example.com/app"
UPSTREAM_URL = "https://mcp.example.com/rpc"
HEADER_NAME = "X-Api-Key"


def _cipher(plain: str = PLAIN_CREDENTIAL) -> str:
    return CryptoUtil.encrypt(plain)


def _upstream(**overrides: Any):
    from app.modules.mcp_gateway.upstream.model import UpstreamMcpModel

    data: dict[str, Any] = {
        "id": UPSTREAM_ID,
        "system_id": SYSTEM_ID,
        "url": UPSTREAM_URL,
        "credential_header": HEADER_NAME,
        "credential_value_encrypted": _cipher(),
        "is_deleted": False,
    }
    data.update(overrides)
    return UpstreamMcpModel(**data)


def _tool(*, remote_name: str = REMOTE_NAME, selected: bool = False, input_schema: dict | None = None, tool_id: int | None = 1):
    from app.modules.mcp_gateway.upstream.model import UpstreamToolModel

    return UpstreamToolModel(
        id=tool_id,
        upstream_id=UPSTREAM_ID,
        remote_name=remote_name,
        external_name=f"{SYSTEM_CODE}_{remote_name}",
        input_schema=input_schema if input_schema is not None else {"type": "object", "properties": {"q": {"type": "string"}}},
        selected=selected,
        is_deleted=False,
    )


def _client(transport: httpx.BaseTransport, tools: list, upstream=None):
    from app.modules.mcp_gateway.upstream.client import UpstreamClient

    return UpstreamClient(
        upstream=upstream or _upstream(),
        system_code=SYSTEM_CODE,
        tools=tools,
        transport=transport,
    )


def _rpc_tools(*names: str, schemas: dict[str, dict] | None = None) -> dict[str, Any]:
    schemas = schemas or {}
    return {
        "jsonrpc": "2.0",
        "id": 1,
        "result": {
            "tools": [
                {
                    "name": name,
                    "inputSchema": schemas.get(name, {"type": "object"}),
                }
                for name in names
            ]
        },
    }


def test_external_name_is_system_code_and_remote_name() -> None:
    """外部名是 {code}_{remote_name}，不再改写大小写、空格或连字符。"""
    from app.modules.mcp_gateway.upstream.client import external_name

    assert external_name("oa", "search_docs") == "oa_search_docs"
    assert external_name("oa", "Get-User") == "oa_Get-User"
    assert external_name("hr_core", "list users") == "hr_core_list users"


async def test_list_tools_inserts_unselected_and_relist_keeps_selection() -> None:
    """首次出现的工具 selected=False。再次拉取只更新 input_schema，保留 selected，不删除远端已消失的行。"""
    seen: list[httpx.Request] = []
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        calls["n"] += 1
        if calls["n"] == 1:
            return httpx.Response(200, json=_rpc_tools("search_docs", "old_tool"))
        return httpx.Response(
            200,
            json=_rpc_tools(
                "search_docs",
                "fresh_tool",
                schemas={
                    "search_docs": {"type": "object", "properties": {"q": {"type": "string"}}},
                    "fresh_tool": {"type": "object", "properties": {"limit": {"type": "integer"}}},
                },
            ),
        )

    tools: list = []
    client = _client(httpx.MockTransport(handler), tools)
    first = await client.list_tools(UPSTREAM_ID)

    assert len(seen) == 1
    assert seen[0].method == "POST"
    assert str(seen[0].url) == UPSTREAM_URL
    listed = json.loads(seen[0].content)
    assert listed["jsonrpc"] == "2.0"
    assert listed["method"] == "tools/list"
    assert {item.remote_name: item.selected for item in first} == {"search_docs": False, "old_tool": False}
    assert {item.external_name for item in first} == {"oa_search_docs", "oa_old_tool"}

    kept = next(item for item in tools if item.remote_name == "search_docs")
    stale = next(item for item in tools if item.remote_name == "old_tool")
    kept.selected = True
    stale.selected = True
    kept_external = kept.external_name

    second = await client.list_tools(UPSTREAM_ID)

    assert len(seen) == 2
    by_name = {item.remote_name: item for item in tools}
    assert set(by_name) == {"search_docs", "old_tool", "fresh_tool"}
    assert by_name["search_docs"].selected is True
    assert by_name["search_docs"].external_name == kept_external
    assert by_name["search_docs"].input_schema == {"type": "object", "properties": {"q": {"type": "string"}}}
    assert by_name["old_tool"].selected is True
    assert by_name["fresh_tool"].selected is False
    assert by_name["fresh_tool"].external_name == "oa_fresh_tool"
    assert {item.remote_name: item.selected for item in second} == {"search_docs": True, "fresh_tool": False}


async def test_call_posts_remote_name_with_only_the_stored_credential() -> None:
    """tools/call 的 params.name 是远端名。请求地址就是保存的 url。请求头只有这份凭证，外加 JSON 所需的 Content-Type 和 Accept。"""
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json={"jsonrpc": "2.0", "id": 1, "result": {"content": [{"type": "text", "text": "ok"}]}})

    tools = [_tool(selected=True)]
    client = _client(httpx.MockTransport(handler), tools)
    result = await client.call(UPSTREAM_ID, EXTERNAL_NAME, {"q": "hello", "token": BUSINESS_TOKEN})

    assert len(seen) == 1
    request = seen[0]
    assert request.method == "POST"
    assert str(request.url) == UPSTREAM_URL
    assert BASE_URL not in str(request.url)
    body = json.loads(request.content)
    assert body["jsonrpc"] == "2.0"
    assert body["method"] == "tools/call"
    assert body["params"]["name"] == REMOTE_NAME
    assert body["params"]["arguments"] == {"q": "hello", "token": BUSINESS_TOKEN}
    assert request.headers[HEADER_NAME] == PLAIN_CREDENTIAL
    assert request.headers["content-type"].startswith("application/json")
    assert request.headers["accept"] == "application/json"
    header_blob = json.dumps(dict(request.headers), ensure_ascii=False)
    assert BUSINESS_TOKEN not in header_blob
    assert BINDING_UID not in header_blob
    assert "oa.example.com" not in header_blob
    assert result.status == 200
    assert result.body["result"]["content"][0]["text"] == "ok"
    stored = client.upstream.credential_value_encrypted
    assert stored != PLAIN_CREDENTIAL
    assert PLAIN_CREDENTIAL not in stored
    assert CryptoUtil.decrypt(stored) == PLAIN_CREDENTIAL


async def test_unselected_tool_is_rejected_before_any_request() -> None:
    """未选用的工具在发出 HTTP 之前就被拒绝。"""
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json={"jsonrpc": "2.0", "id": 1, "result": {}})

    client = _client(httpx.MockTransport(handler), [_tool(selected=False)])
    with pytest.raises(CustomException):
        await client.call(UPSTREAM_ID, EXTERNAL_NAME, {"q": "hello"})
    assert seen == []


async def test_upstream_401_is_returned_without_ensure_token(monkeypatch: pytest.MonkeyPatch) -> None:
    """上游 401 原样返回。不会调用 AuthClient.ensure_token，也不会再登录一次。"""
    ensure_calls: list[Any] = []

    async def _ensure(self, *args: Any, **kwargs: Any):
        ensure_calls.append((args, kwargs))
        raise AssertionError("ensure_token must not run")

    monkeypatch.setattr(AuthClient, "ensure_token", _ensure)
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(401, json={"error": "unauthorized"})

    client = _client(httpx.MockTransport(handler), [_tool(selected=True)])
    result = await client.call(UPSTREAM_ID, EXTERNAL_NAME, {"q": "hello"})

    assert len(seen) == 1
    assert result.status == 401
    assert result.body == {"error": "unauthorized"}
    assert ensure_calls == []


async def test_non_http_url_is_rejected_before_any_request() -> None:
    """保存的地址必须是 http:// 或 https://，并且原样作为请求 URL，不拼到业务系统 base_url 上。"""
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json={"jsonrpc": "2.0", "id": 1, "result": {"tools": []}})

    client = _client(
        httpx.MockTransport(handler),
        [_tool(selected=True)],
        upstream=_upstream(url="ftp://mcp.example.com/rpc"),
    )
    with pytest.raises(CustomException):
        await client.call(UPSTREAM_ID, EXTERNAL_NAME, {"q": "hello"})
    assert seen == []


def test_create_payload_stores_ciphertext_and_responses_omit_plaintext() -> None:
    """凭证加密后入库。列表和详情的响应模型里没有明文，也没有密文字段。"""
    from app.modules.mcp_gateway.upstream.schema import UpstreamMcpCreateSchema, UpstreamMcpOutSchema
    from app.modules.mcp_gateway.upstream.service import upstream_create_payload

    payload = upstream_create_payload(
        UpstreamMcpCreateSchema(
            system_id=SYSTEM_ID,
            url=UPSTREAM_URL,
            credential_header=HEADER_NAME,
            credential_value=PLAIN_CREDENTIAL,
        )
    )
    assert "credential_value" not in payload
    cipher = payload["credential_value_encrypted"]
    assert cipher != PLAIN_CREDENTIAL
    assert PLAIN_CREDENTIAL not in cipher
    assert CryptoUtil.decrypt(cipher) == PLAIN_CREDENTIAL

    out = UpstreamMcpOutSchema.model_validate(_upstream(credential_value_encrypted=cipher))
    dumped = out.model_dump()
    assert "credential_value" not in dumped
    assert "credential_value_encrypted" not in dumped
    assert PLAIN_CREDENTIAL not in json.dumps(dumped, ensure_ascii=False)


def test_update_without_credential_does_not_replace_ciphertext() -> None:
    from app.modules.mcp_gateway.upstream.schema import UpstreamMcpUpdateSchema
    from app.modules.mcp_gateway.upstream.service import upstream_update_payload

    payload = upstream_update_payload(UpstreamMcpUpdateSchema(url="https://mcp.example.com/v2"))
    assert payload == {"url": "https://mcp.example.com/v2"}
    assert "credential_value" not in payload
    assert "credential_value_encrypted" not in payload


def test_schema_rejects_url_without_http_scheme() -> None:
    from app.modules.mcp_gateway.upstream.schema import UpstreamMcpCreateSchema

    with pytest.raises(ValidationError):
        UpstreamMcpCreateSchema(
            system_id=SYSTEM_ID,
            url="ftp://mcp.example.com/rpc",
            credential_header=HEADER_NAME,
            credential_value=PLAIN_CREDENTIAL,
        )


def test_system_id_is_not_unique() -> None:
    """一个业务系统可以挂多个上游 MCP。"""
    from app.modules.mcp_gateway.upstream.model import UpstreamMcpModel

    table = UpstreamMcpModel.__table__
    for constraint in table.constraints:
        columns = [column.name for column in getattr(constraint, "columns", [])]
        if columns == ["system_id"]:
            assert getattr(constraint, "unique", False) is False
    for index in table.indexes:
        if [column.name for column in index.columns] == ["system_id"]:
            assert index.unique is False


def test_update_schema_has_no_system_id() -> None:
    """创建之后 system_id 不再可写。改系统会让旧外部名停在原来的 code 前缀上。"""
    from app.modules.mcp_gateway.upstream.schema import UpstreamMcpUpdateSchema

    assert "system_id" not in UpstreamMcpUpdateSchema.model_fields


def test_tool_remote_name_is_unique_per_upstream() -> None:
    """同一上游的 remote_name 只有一行，软删除的行也占着这个唯一约束。"""
    from sqlalchemy import UniqueConstraint

    from app.modules.mcp_gateway.upstream.model import UpstreamToolModel

    table = UpstreamToolModel.__table__
    matched = [
        constraint
        for constraint in table.constraints
        if isinstance(constraint, UniqueConstraint)
        and [column.name for column in constraint.columns] == ["upstream_id", "remote_name"]
    ]
    assert len(matched) == 1
    constraint = matched[0]
    assert constraint.name is not None
    assert "upstream_id" in constraint.name
    assert "remote_name" in constraint.name
    for index in table.indexes:
        if index.unique and [column.name for column in index.columns] == ["upstream_id", "remote_name"]:
            where = None
            for dialect_opts in index.dialect_options.values():
                where = where or dialect_opts.get("where")
            assert where is None


async def test_deleted_upstream_and_tools_are_rejected_before_any_request() -> None:
    """上游 MCP 和它的工具被标成已删除后，call 在发出 HTTP 之前拒绝。"""
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json={"jsonrpc": "2.0", "id": 1, "result": {}})

    tool = _tool(selected=True)
    tool.is_deleted = True
    client = _client(
        httpx.MockTransport(handler),
        [tool],
        upstream=_upstream(is_deleted=True),
    )
    with pytest.raises(CustomException):
        await client.call(UPSTREAM_ID, EXTERNAL_NAME, {"q": "hello"})
    assert seen == []
