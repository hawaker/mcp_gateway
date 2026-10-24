"""v1 验收：OA 待办。

张三经「办公」MCP 组调用 list_todos，运行时与调试页都能拿到待办，调用日志不含正文和 token。
"""

import json

import httpx
import pytest
from sqlalchemy import select

from app.modules.mcp_gateway.auth.model import AuthConfigModel
from app.modules.mcp_gateway.binding.model import BizBindingModel
from app.modules.mcp_gateway.call_log.model import CallLogModel
from app.modules.mcp_gateway.rest_tool.model import RestToolModel
from app.modules.mcp_gateway.system.model import BizSystemModel
from tests.mcp_gateway.test_runtime import (
    _OA_TOKEN,
    _TODOS,
    _TOKEN_RULE,
    _add,
    _client,
    _Gateway,
    _headers,
    _initialize,
    _mcp_group,
    _member,
    _publish_rest,
    _rpc,
    _user,
    _visible_text,
)
from tests.mcp_gateway.test_token_cache import ExpiringRedis

_TODO_JSON = list(_TODOS)


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


def _auth_schema():
    from app.core.base_schema import AuthSchema

    return AuthSchema()


def _debug_service(db, redis, transport: httpx.AsyncBaseTransport):
    from app.modules.mcp_gateway.runtime.debug import DebugService

    return DebugService(_auth_schema(), db, redis, transport=transport)


async def _rows(db) -> list[CallLogModel]:
    result = await db.execute(select(CallLogModel).order_by(CallLogModel.id.asc()))
    return list(result.scalars().all())


def _row_blob(row: CallLogModel) -> str:
    payload = {column.name: getattr(row, column.name) for column in row.__table__.columns}
    return json.dumps(payload, ensure_ascii=False, default=str)


async def _office_setup(db):
    """OA code=oa、uid_field=user_id，张三绑定 zhangsan，固定鉴权，list_todos +「办公」组。"""
    user = await _user(db, "张三")
    system = await _add(
        db,
        BizSystemModel(
            name="OA",
            code="oa",
            base_url="https://oa.example.com",
            enabled=True,
            params={},
            uid_field="user_id",
            attr_fields=[],
        ),
    )
    await _add(
        db,
        AuthConfigModel(
            system_id=system.id,
            method="fixed",
            enabled=True,
            url="/login",
            rule=dict(_TOKEN_RULE),
        ),
    )
    await _add(
        db,
        BizBindingModel(
            user_id=user.id,
            system_id=system.id,
            uid_value="zhangsan",
            attrs={},
            enabled=True,
        ),
    )
    tool = await _add(
        db,
        RestToolModel(
            name="list_todos",
            display_name="待办列表",
            url="/todos",
            description="OA 待办",
            request_type="GET",
            headers={},
            input_schema={"type": "object", "properties": {}},
            output_schema={},
            jsonpath_filter="$.todos",
            query_mapping={},
            header_mapping={},
            token_in="header",
            enabled=True,
            system_id=system.id,
        ),
    )
    group = await _mcp_group(db, "办公")
    # 调试 Connect 不再签发凭证，须事先发给张三
    token = await _member(db, group.id, user.id)
    await _publish_rest(db, group.id, tool.id, "list_todos")
    return user, system, group, token


def _assert_call_log_safe(rows: list[CallLogModel], *, mcp_token: str) -> None:
    assert rows
    for row in rows:
        blob = _row_blob(row)
        assert _OA_TOKEN not in blob
        assert mcp_token not in blob
        # 待办正文（title / 请假）不得入表；tool_name=list_todos 本身可出现
        assert "请假" not in blob
        assert "title" not in blob


async def test_oa_todo_acceptance_through_mcp_group(db) -> None:
    """张三经「办公」组拿待办：运行时、调试页、调用日志三线验收。"""
    user, system, group, token = await _office_setup(db)
    gateway = _Gateway()
    redis = ExpiringRedis()
    transport = httpx.MockTransport(gateway.handler)

    # 1) 运行时：POST /mcp/{group_id} + Bearer → tools/call list_todos
    async with _client(group.id, db, redis, transport) as client:
        await _initialize(client, group.id, token)
        called = await client.post(
            f"/mcp/{group.id}",
            headers=_headers(token),
            json=_rpc("tools/call", {"name": "list_todos", "arguments": {}}),
        )

    assert called.status_code == 200
    assert json.loads(_visible_text(called)) == _TODO_JSON
    assert _OA_TOKEN not in _visible_text(called)
    assert token not in called.text

    logins = gateway.hits("oa.example.com", "/login")
    business = gateway.hits("oa.example.com", "/todos")
    assert len(logins) == 1
    assert len(business) == 1
    assert json.loads(logins[0].content) == {"user_id": "zhangsan"}
    assert business[0].headers["authorization"] == f"Bearer {_OA_TOKEN}"

    runtime_rows = await _rows(db)
    assert len(runtime_rows) == 1
    assert runtime_rows[0].user_id == user.id
    assert runtime_rows[0].group_id == group.id
    assert runtime_rows[0].tool_name == "list_todos"
    assert runtime_rows[0].system_id == system.id
    assert runtime_rows[0].ok is True
    assert runtime_rows[0].http_status == 200
    _assert_call_log_safe(runtime_rows, mcp_token=token)

    # 2) 调试页：以张三连接「办公」→ tools/list 含 list_todos → tools/call 同一待办
    # 业务 token 已缓存，调试调用不应再打登录
    service = _debug_service(db, redis, transport)
    session = await service.session(
        target="group",
        group_id=group.id,
        user_id=user.id,
        transport="streamable_http",
    )
    assert session.server_info["name"] == "mcp-gateway"

    listed = await service.tools_list(
        target="group",
        group_id=group.id,
        user_id=user.id,
        transport="streamable_http",
    )
    assert "list_todos" in [item["name"] for item in listed.tools]

    debug_called = await service.tools_call(
        target="group",
        group_id=group.id,
        user_id=user.id,
        transport="streamable_http",
        name="list_todos",
        arguments={},
    )
    assert json.loads(debug_called.result_text) == _TODO_JSON

    # 3) 调用日志有行，且不含待办正文与 token
    all_rows = await _rows(db)
    assert len(all_rows) >= 1
    _assert_call_log_safe(all_rows, mcp_token=token)
    assert all(row.tool_name == "list_todos" for row in all_rows)
