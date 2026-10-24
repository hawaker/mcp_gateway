"""管理员 MCP 调试：走运行时同一入口，遮住 token，上游调试不写调用日志。"""

import json
from typing import Any

import httpx
import pytest
from sqlalchemy import select

from app.core.base_schema import AuthSchema
from app.modules.mcp_gateway.call_log.model import CallLogModel
from app.modules.mcp_gateway.upstream.model import UpstreamMcpModel, UpstreamToolModel
from app.utils.crypto_util import CryptoUtil
from tests.mcp_gateway.test_runtime import (
    _OA_TOKEN,
    _TODOS,
    _add,
    _auth_config,
    _binding,
    _Gateway,
    _mcp_group,
    _member,
    _publish_rest,
    _rest,
    _system,
    _user,
)
from tests.mcp_gateway.test_token_cache import ExpiringRedis

_UPSTREAM_SECRET = "upstream-debug-secret"
_MASK = "***"


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


def _auth_schema() -> AuthSchema:
    return AuthSchema()


async def _rows(db) -> list[CallLogModel]:
    result = await db.execute(select(CallLogModel).order_by(CallLogModel.id.asc()))
    return list(result.scalars().all())


def _service(db, redis, transport: httpx.AsyncBaseTransport):
    from app.modules.mcp_gateway.runtime.debug import DebugService

    return DebugService(_auth_schema(), db, redis, transport=transport)


def _blob(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, default=str)


async def _office_group(db):
    """张三 + OA list_todos +「办公」组。"""
    user = await _user(db, "张三")
    system = await _system(db, "oa", base_url="https://oa.example.com")
    await _auth_config(db, system.id)
    await _binding(db, user.id, system.id)
    tool = await _rest(db, system.id, "list_todos")
    group = await _mcp_group(db, "办公")
    token = await _member(db, group.id, user.id)
    await _publish_rest(db, group.id, tool.id, "list_todos")
    return user, system, group, token


async def _upstream_row(db, system_id: int) -> UpstreamMcpModel:
    return await _add(
        db,
        UpstreamMcpModel(
            system_id=system_id,
            url="https://upstream.example.com/mcp",
            credential_header="X-Api-Key",
            credential_value_encrypted=CryptoUtil.encrypt(_UPSTREAM_SECRET),
            is_deleted=False,
        ),
    )


def test_debug_router_is_admin_only() -> None:
    from app.api.v1.routers import DOMAIN_CONTROLLERS
    from app.core.dependencies import AuthPermission
    from app.config.path_conf import BASE_DIR
    from app.modules.mcp_gateway.runtime.debug_controller import McpDebugRouter

    assert McpDebugRouter in DOMAIN_CONTROLLERS["/mcp-gateway"]
    actions: set[str] = set()
    for route in McpDebugRouter.routes:
        path = getattr(route, "path", "")
        assert path.startswith("/debug")
        dependant = getattr(route, "dependant", None)
        if dependant is None:
            continue
        for dep in dependant.dependencies:
            call = getattr(dep, "call", None)
            if isinstance(call, AuthPermission):
                for permission in call.permissions:
                    assert permission.startswith("module_mcp_gateway:debug:")
                    actions.add(permission.rsplit(":", 1)[-1])
    assert "session" in actions or "query" in actions or "debug" in actions
    source = (BASE_DIR / "app/modules/mcp_gateway/runtime/debug_controller.py").read_text(encoding="utf-8")
    assert "status_code=" not in source


async def test_group_debug_lists_and_calls_through_runtime_with_call_log(db) -> None:
    """张三调试「办公」组：tools/list 含 list_todos，tools/call 返回待办并写日志。"""
    user, system, group, token = await _office_group(db)
    gateway = _Gateway()
    redis = ExpiringRedis()
    service = _service(db, redis, httpx.MockTransport(gateway.handler))

    session = await service.session(
        target="group",
        group_id=group.id,
        user_id=user.id,
        transport="streamable_http",
    )
    assert session.server_info["name"] == "mcp-gateway"
    assert token not in _blob(session.protocol)
    assert token not in _blob(session.network)
    assert _MASK in _blob(session.network)

    listed = await service.tools_list(
        target="group",
        group_id=group.id,
        user_id=user.id,
        transport="streamable_http",
    )
    assert [item["name"] for item in listed.tools] == ["list_todos"]
    assert await _rows(db) == []

    called = await service.tools_call(
        target="group",
        group_id=group.id,
        user_id=user.id,
        transport="streamable_http",
        name="list_todos",
        arguments={},
    )
    assert json.loads(called.result_text) == _TODOS
    assert len(gateway.hits("oa.example.com", "/login")) == 1
    assert len(gateway.hits("oa.example.com", "/todos")) == 1
    rows = await _rows(db)
    assert len(rows) == 1
    assert rows[0].user_id == user.id
    assert rows[0].group_id == group.id
    assert rows[0].tool_name == "list_todos"
    assert rows[0].system_id == system.id
    assert rows[0].ok is True
    assert token not in _blob(called.protocol)
    assert token not in _blob(called.network)
    assert _OA_TOKEN not in _blob(called.protocol)
    assert _OA_TOKEN not in _blob(called.network)
    assert _MASK in _blob(called.network)


async def test_group_debug_reveal_returns_raw_tokens(db) -> None:
    user, _system_row, group, token = await _office_group(db)
    gateway = _Gateway()
    redis = ExpiringRedis()
    service = _service(db, redis, httpx.MockTransport(gateway.handler))

    masked = await service.session(
        target="group",
        group_id=group.id,
        user_id=user.id,
        transport="streamable_http",
        reveal=False,
    )
    revealed = await service.session(
        target="group",
        group_id=group.id,
        user_id=user.id,
        transport="streamable_http",
        reveal=True,
    )
    assert token not in _blob(masked.network)
    assert _MASK in _blob(masked.network)
    assert token in _blob(revealed.network)

    masked_call = await service.tools_call(
        target="group",
        group_id=group.id,
        user_id=user.id,
        transport="streamable_http",
        name="list_todos",
        arguments={},
        reveal=False,
    )
    raw_call = await service.tools_call(
        target="group",
        group_id=group.id,
        user_id=user.id,
        transport="streamable_http",
        name="list_todos",
        arguments={},
        reveal=True,
    )
    assert _OA_TOKEN not in _blob(masked_call.protocol)
    assert _OA_TOKEN not in _blob(masked_call.network)
    assert token not in _blob(masked_call.network)
    assert token in _blob(raw_call.network)
    # 业务 token 若出现在 Protocol/Network 文本里也必须被遮住；此处确认遮罩后不泄露
    assert _MASK in _blob(masked_call.network)


async def test_upstream_debug_uses_credential_without_call_log(db) -> None:
    user = await _user(db, "张三")
    system = await _system(db, "oa_up_debug", base_url="https://oa.example.com")
    upstream = await _upstream_row(db, system.id)
    await _add(
        db,
        UpstreamToolModel(
            upstream_id=upstream.id,
            remote_name="search_docs",
            external_name="oa_up_debug_search_docs",
            input_schema={"type": "object"},
            selected=True,
            is_deleted=False,
        ),
    )
    del user

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers.get("x-api-key") == _UPSTREAM_SECRET
        body = json.loads(request.content.decode())
        method = body.get("method")
        if method == "initialize":
            return httpx.Response(
                200,
                json={
                    "jsonrpc": "2.0",
                    "id": body.get("id"),
                    "result": {
                        "protocolVersion": "2025-03-26",
                        "capabilities": {"tools": {}},
                        "serverInfo": {"name": "remote-mcp", "version": "0.1"},
                    },
                },
            )
        if method == "tools/list":
            return httpx.Response(
                200,
                json={
                    "jsonrpc": "2.0",
                    "id": body.get("id"),
                    "result": {"tools": [{"name": "search_docs", "inputSchema": {"type": "object"}}]},
                },
            )
        if method == "tools/call":
            return httpx.Response(
                200,
                json={
                    "jsonrpc": "2.0",
                    "id": body.get("id"),
                    "result": {"content": [{"type": "text", "text": "{\"ok\":true}"}]},
                },
            )
        return httpx.Response(500, text=f"unexpected {method}")

    redis = ExpiringRedis()
    service = _service(db, redis, httpx.MockTransport(handler))

    session = await service.session(target="upstream", upstream_id=upstream.id)
    assert session.server_info["name"] == "remote-mcp"
    assert _UPSTREAM_SECRET not in _blob(session.network)
    assert _MASK in _blob(session.network)

    listed = await service.tools_list(target="upstream", upstream_id=upstream.id)
    assert [item["name"] for item in listed.tools] == ["search_docs"]

    called = await service.tools_call(
        target="upstream",
        upstream_id=upstream.id,
        name="search_docs",
        arguments={"q": "x"},
    )
    assert called.result_text == '{"ok":true}'
    assert await _rows(db) == []
    assert _UPSTREAM_SECRET not in _blob(called.network)

    revealed = await service.tools_list(target="upstream", upstream_id=upstream.id, reveal=True)
    assert _UPSTREAM_SECRET in _blob(revealed.network)


async def test_group_debug_sse_lists_tools(db) -> None:
    user, _system_row, group, token = await _office_group(db)
    gateway = _Gateway()
    redis = ExpiringRedis()
    # SSE 需要 publish/subscribe
    from tests.mcp_gateway.test_runtime import StreamingRedis

    redis = StreamingRedis()
    service = _service(db, redis, httpx.MockTransport(gateway.handler))

    listed = await service.tools_list(
        target="group",
        group_id=group.id,
        user_id=user.id,
        transport="sse",
    )
    assert [item["name"] for item in listed.tools] == ["list_todos"]
    assert token not in _blob(listed.network)
    assert await _rows(db) == []
