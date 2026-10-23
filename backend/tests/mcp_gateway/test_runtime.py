"""MCP 组的 Streamable HTTP 与 SSE。

测试驱动 build_mcp_app，走真实的 invoke 和上游转发。业务 HTTP 停在 MockTransport，不访问真实 OA。
"""

import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import httpx
import pytest
from fastapi import FastAPI
from sqlalchemy import func, select

from app.core.base_schema import AuthSchema
from app.modules.mcp_gateway.auth.client import AuthClient
from app.modules.mcp_gateway.auth.model import AuthConfigModel
from app.modules.mcp_gateway.binding.model import BizBindingModel
from app.modules.mcp_gateway.mcp_group.model import McpCredentialModel, McpGroupModel
from app.modules.mcp_gateway.mcp_group.schema import (
    McpGroupCreateSchema,
    McpGroupMemberCreateSchema,
    McpGroupToolCreateSchema,
    McpGroupUpdateSchema,
)
from app.modules.mcp_gateway.mcp_group.service import McpCredentialService, McpGroupService
from app.modules.mcp_gateway.rest_tool.model import RestToolModel
from app.modules.mcp_gateway.runtime.app import build_mcp_app
from app.modules.mcp_gateway.system.model import BizSystemModel
from app.modules.mcp_gateway.upstream.model import UpstreamMcpModel, UpstreamToolModel
from app.modules.mcp_gateway.user.model import BizUserGroupMemberModel, BizUserGroupModel, BizUserModel
from app.utils.crypto_util import CryptoUtil
from tests.mcp_gateway.test_token_cache import ExpiringRedis

_TOKEN_RULE = {
    "token_from": "json",
    "token_name": "token",
    "expires_from": "json",
    "expires_name": "expires_in",
    "expires_unit": "seconds",
}
_OA_TOKEN = "oa-token-zhangsan"
_TODOS = [{"title": "请假"}]


@pytest.fixture
async def db():
    from app.core.base_model import MappedBase
    from app.core.database import async_db_session, async_engine

    async with async_engine.begin() as conn:
        await conn.run_sync(MappedBase.metadata.create_all)

    async with async_db_session() as session:
        transaction = await session.begin()
        try:
            yield session
        finally:
            if transaction.is_active:
                await transaction.rollback()


def _auth() -> AuthSchema:
    return AuthSchema()


class _Gateway:
    """按主机记下请求。登录、业务接口和上游都走这里，不会出网。"""

    def __init__(self) -> None:
        self.requests: list[httpx.Request] = []

    def handler(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        host = request.url.host
        path = request.url.path
        if host == "oa.example.com" and path.endswith("/login"):
            return httpx.Response(200, json={"token": _OA_TOKEN, "expires_in": 60})
        if host == "oa.example.com" and path.endswith("/todos"):
            return httpx.Response(200, json={"todos": _TODOS, "token": _OA_TOKEN})
        if host == "mes.example.com":
            return httpx.Response(200, json={"jobs": [{"id": 1}]})
        if host == "upstream.example.com":
            return httpx.Response(401, json={"error": "expired"})
        return httpx.Response(500, text=f"unexpected {request.url}")

    def hits(self, host: str, suffix: str | None = None) -> list[httpx.Request]:
        rows = [item for item in self.requests if item.url.host == host]
        if suffix is None:
            return rows
        return [item for item in rows if item.url.path.endswith(suffix)]


async def _add(db, row):
    db.add(row)
    await db.flush()
    return row


async def _user(db, name: str = "张三") -> BizUserModel:
    return await _add(db, BizUserModel(name=name, enabled=True))


async def _biz_group(db, name: str) -> BizUserGroupModel:
    return await _add(db, BizUserGroupModel(name=name, enabled=True))


async def _system(db, code: str, *, base_url: str) -> BizSystemModel:
    return await _add(
        db,
        BizSystemModel(
            name=code,
            code=code,
            base_url=base_url,
            enabled=True,
            params={},
            uid_field="employee_no",
            attr_fields=[],
        ),
    )


async def _auth_config(db, system_id: int, *, method: str = "fixed") -> AuthConfigModel:
    return await _add(
        db,
        AuthConfigModel(
            system_id=system_id,
            method=method,
            enabled=True,
            url="/login",
            rule=dict(_TOKEN_RULE),
        ),
    )


async def _binding(db, user_id: int, system_id: int, *, enabled: bool = True) -> BizBindingModel:
    return await _add(
        db,
        BizBindingModel(
            user_id=user_id,
            system_id=system_id,
            uid_value="zhangsan",
            attrs={},
            enabled=enabled,
        ),
    )


async def _rest(
    db,
    system_id: int,
    name: str,
    *,
    url: str = "/todos",
    jsonpath_filter: str | None = "$.todos",
) -> RestToolModel:
    return await _add(
        db,
        RestToolModel(
            name=name,
            display_name=name,
            url=url,
            description="待办",
            request_type="GET",
            headers={},
            input_schema={"type": "object", "properties": {"q": {"type": "string"}}},
            output_schema={},
            jsonpath_filter=jsonpath_filter,
            query_mapping={},
            header_mapping={},
            token_in="header",
            enabled=True,
            system_id=system_id,
        ),
    )


async def _mcp_group(db, name: str = "门户") -> McpGroupModel:
    created = await McpGroupService(_auth(), db).create(McpGroupCreateSchema(name=name, enabled=True))
    row = await db.get(McpGroupModel, created.id)
    assert row is not None
    return row


async def _member(db, group_id: int, user_id: int) -> str:
    await McpGroupService(_auth(), db).add_member(
        group_id,
        McpGroupMemberCreateSchema(principal_type="user", principal_id=user_id),
    )
    return await McpCredentialService(_auth(), db).issue(user_id=user_id, group_id=group_id)


async def _publish_rest(db, group_id: int, tool_id: int, external_name: str, *, enabled: bool = True):
    return await McpGroupService(_auth(), db).add_tool(
        group_id,
        McpGroupToolCreateSchema(source="rest", source_id=tool_id, external_name=external_name, enabled=enabled),
    )


def _headers(token: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json, text/event-stream",
        "Content-Type": "application/json",
    }


def _rpc(method: str, params: dict | None = None, *, rpc_id: int = 1) -> dict:
    return {"jsonrpc": "2.0", "id": rpc_id, "method": method, "params": params or {}}


def _visible_text(response: httpx.Response) -> str:
    result = response.json().get("result")
    if not isinstance(result, dict):
        return ""
    content = result.get("content")
    if not isinstance(content, list) or not content:
        return ""
    return str(content[0].get("text", ""))


def _tool_names(response: httpx.Response) -> list[str]:
    return [item["name"] for item in response.json()["result"]["tools"]]


@asynccontextmanager
async def _client(group_id: int, db, redis, transport: httpx.BaseTransport) -> AsyncIterator[httpx.AsyncClient]:
    app = build_mcp_app(group_id, db=db, redis=redis, transport=transport)
    asgi = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=asgi, base_url="http://mcp.test") as client:
        yield client


async def _initialize(client: httpx.AsyncClient, group_id: int, token: str) -> httpx.Response:
    response = await client.post(
        f"/mcp/{group_id}", headers=_headers(token), json=_rpc("initialize", {"protocolVersion": "2025-03-26", "capabilities": {}, "clientInfo": {"name": "test", "version": "0"}})
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["jsonrpc"] == "2.0"
    assert payload["result"]["protocolVersion"] == "2025-03-26"
    assert "tools" in payload["result"]["capabilities"]
    return response


async def test_tools_list_returns_only_enabled_group_tools(db) -> None:
    """tools/list 只列出该组未禁用的工具。"""
    user = await _user(db)
    system = await _system(db, "oa_list", base_url="https://oa.example.com")
    await _auth_config(db, system.id)
    await _binding(db, user.id, system.id)
    visible = await _rest(db, system.id, "search")
    hidden = await _rest(db, system.id, "hidden")
    group = await _mcp_group(db, "目录")
    token = await _member(db, group.id, user.id)
    await _publish_rest(db, group.id, visible.id, "search")
    hidden_link = await _publish_rest(db, group.id, hidden.id, "hidden")
    await McpGroupService(_auth(), db).update_tool_enabled(hidden_link.id, False)
    gateway = _Gateway()
    redis = ExpiringRedis()

    async with _client(group.id, db, redis, httpx.MockTransport(gateway.handler)) as client:
        await _initialize(client, group.id, token)
        listed = await client.post(f"/mcp/{group.id}", headers=_headers(token), json=_rpc("tools/list"))

    assert listed.status_code == 200
    assert _tool_names(listed) == ["search"]
    assert listed.json()["result"]["tools"][0]["inputSchema"]["properties"]["q"]["type"] == "string"
    assert gateway.requests == []


async def test_disabled_group_tool_call_is_denied_without_oa_request(db) -> None:
    """组内禁用的工具，tools/call 返回无权限，OA 收到 0 次请求。"""
    user = await _user(db)
    system = await _system(db, "oa_disabled_tool", base_url="https://oa.example.com")
    await _auth_config(db, system.id)
    await _binding(db, user.id, system.id)
    tool = await _rest(db, system.id, "hidden")
    group = await _mcp_group(db, "禁用工具")
    token = await _member(db, group.id, user.id)
    link = await _publish_rest(db, group.id, tool.id, "hidden")
    await McpGroupService(_auth(), db).update_tool_enabled(link.id, False)
    gateway = _Gateway()
    redis = ExpiringRedis()

    async with _client(group.id, db, redis, httpx.MockTransport(gateway.handler)) as client:
        await _initialize(client, group.id, token)
        called = await client.post(
            f"/mcp/{group.id}",
            headers=_headers(token),
            json=_rpc("tools/call", {"name": "hidden", "arguments": {}}),
        )

    assert called.status_code == 200
    assert _visible_text(called) == "无权限"
    assert _OA_TOKEN not in called.text
    assert gateway.hits("oa.example.com") == []


async def test_unbound_system_call_is_denied_without_request(db) -> None:
    """只绑定 OA 时调用 MES 工具，返回无权限，MES 收到 0 次请求。"""
    user = await _user(db)
    oa = await _system(db, "oa_bound", base_url="https://oa.example.com")
    mes = await _system(db, "mes_unbound", base_url="https://mes.example.com")
    await _auth_config(db, oa.id)
    await _auth_config(db, mes.id)
    await _binding(db, user.id, oa.id)
    tool = await _rest(db, mes.id, "jobs", url="/jobs", jsonpath_filter=None)
    group = await _mcp_group(db, "跨系统")
    token = await _member(db, group.id, user.id)
    await _publish_rest(db, group.id, tool.id, "mes_jobs")
    gateway = _Gateway()
    redis = ExpiringRedis()

    async with _client(group.id, db, redis, httpx.MockTransport(gateway.handler)) as client:
        await _initialize(client, group.id, token)
        called = await client.post(
            f"/mcp/{group.id}",
            headers=_headers(token),
            json=_rpc("tools/call", {"name": "mes_jobs", "arguments": {}}),
        )

    assert called.status_code == 200
    assert _visible_text(called) == "无权限"
    assert gateway.hits("mes.example.com") == []
    assert gateway.hits("oa.example.com") == []


async def test_rest_call_logs_in_then_returns_filtered_todos(db) -> None:
    """OA 工具在 token 缺失时先登录再请求。响应体是过滤后的待办 JSON。"""
    user = await _user(db)
    system = await _system(db, "oa_todos", base_url="https://oa.example.com")
    await _auth_config(db, system.id)
    await _binding(db, user.id, system.id)
    tool = await _rest(db, system.id, "todos")
    group = await _mcp_group(db, "待办")
    token = await _member(db, group.id, user.id)
    await _publish_rest(db, group.id, tool.id, "todos")
    gateway = _Gateway()
    redis = ExpiringRedis()

    async with _client(group.id, db, redis, httpx.MockTransport(gateway.handler)) as client:
        await _initialize(client, group.id, token)
        called = await client.post(
            f"/mcp/{group.id}",
            headers=_headers(token),
            json=_rpc("tools/call", {"name": "todos", "arguments": {"q": "今天"}}),
        )

    assert called.status_code == 200
    assert json.loads(_visible_text(called)) == _TODOS
    assert _OA_TOKEN not in _visible_text(called)
    logins = gateway.hits("oa.example.com", "/login")
    business = gateway.hits("oa.example.com", "/todos")
    assert len(logins) == 1
    assert len(business) == 1
    assert gateway.requests.index(logins[0]) < gateway.requests.index(business[0])
    assert business[0].headers["authorization"] == f"Bearer {_OA_TOKEN}"


async def test_interactive_call_returns_link_without_business_request(db) -> None:
    """交互式鉴权且无缓存时，tools/call 的文本里包含验证链接，业务接口收到 0 次请求。"""
    user = await _user(db)
    system = await _system(db, "oa_interactive", base_url="https://oa.example.com")
    await _auth_config(db, system.id, method="interactive")
    await _binding(db, user.id, system.id)
    tool = await _rest(db, system.id, "todos", jsonpath_filter=None)
    group = await _mcp_group(db, "交互")
    token = await _member(db, group.id, user.id)
    await _publish_rest(db, group.id, tool.id, "todos")
    gateway = _Gateway()
    redis = ExpiringRedis()

    async with _client(group.id, db, redis, httpx.MockTransport(gateway.handler)) as client:
        await _initialize(client, group.id, token)
        called = await client.post(
            f"/mcp/{group.id}",
            headers=_headers(token),
            json=_rpc("tools/call", {"name": "todos", "arguments": {}}),
        )

    text = _visible_text(called)
    assert called.status_code == 200
    assert text.startswith("/mcp-gateway/auth/interactive/")
    assert _OA_TOKEN not in text
    assert gateway.hits("oa.example.com") == []


async def test_upstream_call_forwards_without_ensure_token(db, monkeypatch: pytest.MonkeyPatch) -> None:
    """上游工具在用户与 MCP 组都启用时原样转发，不调用 ensure_token。"""
    ensure_calls: list[tuple] = []
    original = AuthClient.ensure_token

    async def tracking(self, user_id: int, system_id: int, *, force: bool = False):
        ensure_calls.append((user_id, system_id, force))
        return await original(self, user_id, system_id, force=force)

    monkeypatch.setattr(AuthClient, "ensure_token", tracking)
    user = await _user(db)
    system = await _system(db, "oa_upstream", base_url="https://oa.example.com")
    await _auth_config(db, system.id)
    await _binding(db, user.id, system.id)
    upstream = await _add(
        db,
        UpstreamMcpModel(
            system_id=system.id,
            url="https://upstream.example.com/rpc",
            credential_header="X-Api-Key",
            credential_value_encrypted=CryptoUtil.encrypt("upstream-secret"),
        ),
    )
    upstream_tool = await _add(
        db,
        UpstreamToolModel(
            upstream_id=upstream.id,
            remote_name="search_docs",
            external_name="oa_search_docs",
            input_schema={"type": "object", "properties": {"q": {"type": "string"}}},
            selected=True,
        ),
    )
    group = await _mcp_group(db, "上游")
    token = await _member(db, group.id, user.id)
    await McpGroupService(_auth(), db).add_tool(
        group.id,
        McpGroupToolCreateSchema(source="upstream", source_id=upstream_tool.id, external_name="portal_search"),
    )
    gateway = _Gateway()
    redis = ExpiringRedis()

    async with _client(group.id, db, redis, httpx.MockTransport(gateway.handler)) as client:
        await _initialize(client, group.id, token)
        called = await client.post(
            f"/mcp/{group.id}",
            headers=_headers(token),
            json=_rpc("tools/call", {"name": "portal_search", "arguments": {"q": "请假"}}),
        )

    assert called.status_code == 200
    assert json.loads(_visible_text(called)) == {"status": 401, "body": {"error": "expired"}}
    assert ensure_calls == []
    forwarded = gateway.hits("upstream.example.com")
    assert len(forwarded) == 1
    sent = json.loads(forwarded[0].content)
    assert sent["method"] == "tools/call"
    assert sent["params"]["name"] == "search_docs"
    assert sent["params"]["arguments"] == {"q": "请假"}
    assert forwarded[0].headers["x-api-key"] == "upstream-secret"
    assert gateway.hits("oa.example.com") == []


async def test_disabled_member_call_is_denied_and_token_stays(db) -> None:
    """成员被禁用后 tools/call 返回无权限，已保存的 token 字符串不变。"""
    user = await _user(db)
    system = await _system(db, "oa_member", base_url="https://oa.example.com")
    await _auth_config(db, system.id)
    await _binding(db, user.id, system.id)
    tool = await _rest(db, system.id, "todos")
    group = await _mcp_group(db, "成员")
    token = await _member(db, group.id, user.id)
    await _publish_rest(db, group.id, tool.id, "todos")
    stored = (
        await db.execute(
            select(McpCredentialModel).where(
                McpCredentialModel.user_id == user.id,
                McpCredentialModel.group_id == group.id,
            )
        )
    ).scalar_one()
    encrypted = stored.token_encrypted
    gateway = _Gateway()
    redis = ExpiringRedis()

    async with _client(group.id, db, redis, httpx.MockTransport(gateway.handler)) as client:
        await _initialize(client, group.id, token)
        allowed = await client.post(
            f"/mcp/{group.id}",
            headers=_headers(token),
            json=_rpc("tools/call", {"name": "todos", "arguments": {}}),
        )
        assert json.loads(_visible_text(allowed)) == _TODOS
        sent_before = len(gateway.requests)
        await McpGroupService(_auth(), db).disable_member(group.id, "user", user.id)
        denied = await client.post(
            f"/mcp/{group.id}",
            headers=_headers(token),
            json=_rpc("tools/call", {"name": "todos", "arguments": {}}),
        )
        listed = await client.post(f"/mcp/{group.id}", headers=_headers(token), json=_rpc("tools/list", rpc_id=2))

    assert denied.status_code == 200
    assert _visible_text(denied) == "无权限"
    assert _OA_TOKEN not in denied.text
    assert token not in denied.text
    assert _visible_text(listed) == "无权限"
    assert len(gateway.requests) == sent_before
    await db.refresh(stored)
    assert stored.token_encrypted == encrypted
    assert CryptoUtil.decrypt(stored.token_encrypted) == token
    assert await McpCredentialService(_auth(), db).verify(token) == (user.id, group.id)


async def test_missing_bearer_is_rejected_before_business_request(db) -> None:
    """没有 bearer 时在业务请求之前拒绝，并且不说无权限。"""
    user = await _user(db)
    system = await _system(db, "oa_anon", base_url="https://oa.example.com")
    await _auth_config(db, system.id)
    await _binding(db, user.id, system.id)
    tool = await _rest(db, system.id, "todos")
    group = await _mcp_group(db, "匿名")
    await _member(db, group.id, user.id)
    await _publish_rest(db, group.id, tool.id, "todos")
    gateway = _Gateway()
    redis = ExpiringRedis()

    async with _client(group.id, db, redis, httpx.MockTransport(gateway.handler)) as client:
        response = await client.post(
            f"/mcp/{group.id}",
            headers={"Accept": "application/json", "Content-Type": "application/json"},
            json=_rpc("tools/call", {"name": "todos", "arguments": {}}),
        )

    assert response.status_code == 401
    assert "无权限" not in json.dumps(response.json(), ensure_ascii=False)
    assert gateway.requests == []


async def test_disabled_group_returns_no_permission_without_request(db) -> None:
    """MCP 组停用后 tools/list 和 tools/call 都返回无权限，且不请求业务系统。"""
    user = await _user(db)
    system = await _system(db, "oa_group_off", base_url="https://oa.example.com")
    await _auth_config(db, system.id)
    await _binding(db, user.id, system.id)
    tool = await _rest(db, system.id, "todos")
    group = await _mcp_group(db, "停用组")
    token = await _member(db, group.id, user.id)
    await _publish_rest(db, group.id, tool.id, "todos")
    await McpGroupService(_auth(), db).update(group.id, McpGroupUpdateSchema(enabled=False))
    gateway = _Gateway()
    redis = ExpiringRedis()

    async with _client(group.id, db, redis, httpx.MockTransport(gateway.handler)) as client:
        await _initialize(client, group.id, token)
        listed = await client.post(f"/mcp/{group.id}", headers=_headers(token), json=_rpc("tools/list"))
        called = await client.post(
            f"/mcp/{group.id}",
            headers=_headers(token),
            json=_rpc("tools/call", {"name": "todos", "arguments": {}}),
        )

    assert _visible_text(listed) == "无权限"
    assert _visible_text(called) == "无权限"
    assert gateway.requests == []


async def test_business_group_member_is_allowed_until_that_group_is_disabled(db) -> None:
    """勾选的业务用户组当前成员可用。之后加入的人不会在运行时拿到 token。"""
    user = await _user(db, "张三")
    late = await _user(db, "李四")
    biz_group = await _biz_group(db, "研发")
    await _add(db, BizUserGroupMemberModel(user_id=user.id, group_id=biz_group.id))
    system = await _system(db, "oa_biz_group", base_url="https://oa.example.com")
    tool = await _rest(db, system.id, "search", jsonpath_filter=None)
    group = await _mcp_group(db, "用户组")
    await McpGroupService(_auth(), db).add_member(
        group.id,
        McpGroupMemberCreateSchema(principal_type="group", principal_id=biz_group.id),
    )
    token = await McpCredentialService(_auth(), db).issue(user_id=user.id, group_id=group.id)
    await _publish_rest(db, group.id, tool.id, "search")
    gateway = _Gateway()
    redis = ExpiringRedis()

    async with _client(group.id, db, redis, httpx.MockTransport(gateway.handler)) as client:
        await _initialize(client, group.id, token)
        listed = await client.post(f"/mcp/{group.id}", headers=_headers(token), json=_rpc("tools/list"))
        assert _tool_names(listed) == ["search"]
        await _add(db, BizUserGroupMemberModel(user_id=late.id, group_id=biz_group.id))
        late_credentials = (await db.execute(select(func.count()).select_from(McpCredentialModel).where(McpCredentialModel.user_id == late.id))).scalar_one()
        assert late_credentials == 0
        biz_group.enabled = False
        await db.flush()
        denied = await client.post(f"/mcp/{group.id}", headers=_headers(token), json=_rpc("tools/list", rpc_id=2))

    assert _visible_text(denied) == "无权限"
    assert gateway.requests == []


async def test_sse_message_post_reads_session_from_redis(db) -> None:
    """GET 把会话写入 Redis。另一边只靠写入 mcp:sse:{session_id} 就能完成 tools/list。"""
    user = await _user(db)
    system = await _system(db, "oa_sse", base_url="https://oa.example.com")
    tool = await _rest(db, system.id, "search", jsonpath_filter=None)
    group = await _mcp_group(db, "SSE")
    token = await _member(db, group.id, user.id)
    await _publish_rest(db, group.id, tool.id, "search")
    gateway = _Gateway()
    redis = ExpiringRedis()

    async with _client(group.id, db, redis, httpx.MockTransport(gateway.handler)) as client:
        opened = await client.get(f"/mcp/{group.id}/sse", headers=_headers(token))
        streamable = await client.get(f"/mcp/{group.id}", headers=_headers(token))

    assert opened.status_code == 200
    assert "text/event-stream" in opened.headers["content-type"]
    marker = f"/mcp/{group.id}/messages?session_id="
    assert marker in opened.text
    opened_id = opened.text.split("session_id=", 1)[1].split()[0].strip()
    stored = await redis.get(f"mcp:sse:{opened_id}")
    assert stored is not None
    assert json.loads(stored)["group_id"] == group.id
    assert streamable.status_code == 200
    assert "text/event-stream" in streamable.headers["content-type"]

    session_id = "from-another-process"
    await redis.set(f"mcp:sse:{session_id}", json.dumps({"group_id": group.id}))
    async with _client(group.id, db, redis, httpx.MockTransport(gateway.handler)) as client:
        listed = await client.post(
            f"/mcp/{group.id}/messages?session_id={session_id}",
            headers=_headers(token),
            json=_rpc("tools/list"),
        )
        missing = await client.post(
            f"/mcp/{group.id}/messages?session_id=missing-session",
            headers=_headers(token),
            json=_rpc("tools/list"),
        )

    assert listed.status_code == 200
    assert _tool_names(listed) == ["search"]
    assert missing.status_code == 404
    assert "tools" not in missing.json()
    assert gateway.requests == []


async def test_runtime_routes_mount_at_app_root_without_admin_auth() -> None:
    """运行时挂在应用根上，不进 api_v1，也不套管理员 AuthPermission。"""
    from app import register_routers

    app = FastAPI()
    register_routers(app)
    found: dict[str, set[str]] = {}
    for route in app.routes:
        path = getattr(route, "path", "")
        if path.startswith("/mcp/"):
            found[path] = set(getattr(route, "methods", set()))
            assert not path.startswith("/api/")
            assert "mcp-gateway" not in path
            assert list(getattr(route, "dependencies", [])) == []
    assert found["/mcp/{group_id}"] >= {"GET", "POST"}
    assert found["/mcp/{group_id}/sse"] >= {"GET"}
    assert found["/mcp/{group_id}/messages"] >= {"POST"}

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://mcp.test") as client:
        response = await client.post(
            "/mcp/1",
            headers={"Content-Type": "application/json"},
            json=_rpc("tools/list"),
        )
    assert response.status_code == 401
    assert "无权限" not in json.dumps(response.json(), ensure_ascii=False)
