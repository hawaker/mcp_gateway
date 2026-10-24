"""tools/call 写入调用日志。断言读的是表里的行，调试未保存表单不写。"""

import json

import httpx
import pytest
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import func, select

from app.config.path_conf import BASE_DIR
from app.core.base_model import MappedBase, ModelMixin
from app.modules.mcp_gateway.call_log.controller import CallLogRouter, aggregate_call_log_controller
from app.modules.mcp_gateway.call_log.model import CallLogModel
from app.modules.mcp_gateway.mcp_group.schema import McpGroupToolCreateSchema
from app.modules.mcp_gateway.mcp_group.service import McpGroupService
from app.modules.mcp_gateway.upstream.model import UpstreamMcpModel, UpstreamToolModel
from app.utils.crypto_util import CryptoUtil
from tests.mcp_gateway.test_rest_tool import _binding, _draft, _service
from tests.mcp_gateway.test_runtime import (
    _OA_TOKEN,
    _TODOS,
    _add,
    _auth,
    _auth_config,
    _client,
    _Gateway,
    _headers,
    _initialize,
    _mcp_group,
    _member,
    _publish_rest,
    _rest,
    _rpc,
    _system,
    _user,
    _visible_text,
)
from tests.mcp_gateway.test_runtime import (
    _binding as _bind_user,
)
from tests.mcp_gateway.test_token_cache import ExpiringRedis

_COLUMNS = {
    "id",
    "user_id",
    "group_id",
    "tool_name",
    "system_id",
    "elapsed_ms",
    "ok",
    "http_status",
    "created_at",
}
_REVISION = "c8d4f1a07e53"


@pytest.fixture
async def db():
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


def test_call_log_table_has_no_body_or_mixin_columns() -> None:
    assert issubclass(CallLogModel, MappedBase)
    assert not issubclass(CallLogModel, ModelMixin)
    assert set(CallLogModel.__table__.columns.keys()) == _COLUMNS
    assert CallLogModel.system_id.nullable
    assert CallLogModel.http_status.nullable


def test_revision_follows_mcp_group() -> None:
    script = ScriptDirectory.from_config(Config(str(BASE_DIR / "alembic.ini")))
    revision = script.get_revision(_REVISION)
    assert revision is not None
    assert revision.down_revision == "a7c3e9b14d62"


def test_router_is_query_only() -> None:
    from app.api.v1.routers import DOMAIN_CONTROLLERS
    from app.core.dependencies import AuthPermission

    assert CallLogRouter in DOMAIN_CONTROLLERS["/mcp-gateway"]
    actions: set[str] = set()
    for route in CallLogRouter.routes:
        path = getattr(route, "path", "")
        assert path.startswith("/call-log")
        dependant = getattr(route, "dependant", None)
        if dependant is None:
            continue
        for dep in dependant.dependencies:
            call = getattr(dep, "call", None)
            if isinstance(call, AuthPermission):
                assert call.permissions == ["module_mcp_gateway:call-log:query"]
                actions.add("query")
    assert actions == {"query"}
    source = (BASE_DIR / "app/modules/mcp_gateway/call_log/controller.py").read_text(encoding="utf-8")
    assert "status_code=" not in source


async def _rows(db) -> list[CallLogModel]:
    result = await db.execute(select(CallLogModel).order_by(CallLogModel.id.asc()))
    return list(result.scalars().all())


def _blob(row: CallLogModel) -> str:
    payload = {column.name: getattr(row, column.name) for column in row.__table__.columns}
    return json.dumps(payload, ensure_ascii=False, default=str)


async def _call(db, group_id: int, token: str, name: str, arguments: dict | None = None, *, rpc_id: int = 1):
    gateway = _Gateway()
    redis = ExpiringRedis()
    async with _client(group_id, db, redis, httpx.MockTransport(gateway.handler)) as client:
        await _initialize(client, group_id, token)
        response = await client.post(
            f"/mcp/{group_id}",
            headers=_headers(token),
            json=_rpc("tools/call", {"name": name, "arguments": arguments or {}}, rpc_id=rpc_id),
        )
    return response, gateway


async def test_successful_tools_call_stores_upstream_status_without_bodies(db) -> None:
    """登录和业务请求各一次，调用日志只有一行，状态码是业务响应。"""
    user = await _user(db)
    system = await _system(db, "oa_log_ok", base_url="https://oa.example.com")
    await _auth_config(db, system.id)
    await _bind_user(db, user.id, system.id)
    tool = await _rest(db, system.id, "todos")
    group = await _mcp_group(db, "日志成功")
    token = await _member(db, group.id, user.id)
    await _publish_rest(db, group.id, tool.id, "todos")

    response, gateway = await _call(db, group.id, token, "todos", {"q": "今天"})

    assert json.loads(_visible_text(response)) == _TODOS
    assert len(gateway.hits("oa.example.com", "/login")) == 1
    assert len(gateway.hits("oa.example.com", "/todos")) == 1
    rows = await _rows(db)
    assert len(rows) == 1
    row = rows[0]
    assert row.user_id == user.id
    assert row.group_id == group.id
    assert row.tool_name == "todos"
    assert row.system_id == system.id
    assert row.http_status == 200
    assert row.ok is True
    assert isinstance(row.elapsed_ms, int) and row.elapsed_ms >= 0
    assert row.created_at is not None
    blob = _blob(row)
    assert _OA_TOKEN not in blob
    assert token not in blob
    assert "今天" not in blob
    assert "title" not in blob


async def test_initialize_and_tools_list_write_nothing(db) -> None:
    user = await _user(db)
    system = await _system(db, "oa_log_list", base_url="https://oa.example.com")
    await _auth_config(db, system.id)
    await _bind_user(db, user.id, system.id)
    tool = await _rest(db, system.id, "search", jsonpath_filter=None)
    group = await _mcp_group(db, "日志目录")
    token = await _member(db, group.id, user.id)
    await _publish_rest(db, group.id, tool.id, "search")
    gateway = _Gateway()
    redis = ExpiringRedis()

    async with _client(group.id, db, redis, httpx.MockTransport(gateway.handler)) as client:
        await _initialize(client, group.id, token)
        listed = await client.post(f"/mcp/{group.id}", headers=_headers(token), json=_rpc("tools/list"))

    assert listed.status_code == 200
    assert await _rows(db) == []


async def test_disabled_group_tool_stores_failure_without_http_status(db) -> None:
    user = await _user(db)
    system = await _system(db, "oa_log_disabled", base_url="https://oa.example.com")
    await _auth_config(db, system.id)
    await _bind_user(db, user.id, system.id)
    tool = await _rest(db, system.id, "hidden")
    group = await _mcp_group(db, "日志禁用工具")
    token = await _member(db, group.id, user.id)
    await _publish_rest(db, group.id, tool.id, "hidden", enabled=False)

    response, gateway = await _call(db, group.id, token, "hidden", {"q": "隐藏参数"})

    assert _visible_text(response) == "无权限"
    assert gateway.hits("oa.example.com") == []
    rows = await _rows(db)
    assert len(rows) == 1
    row = rows[0]
    assert row.user_id == user.id
    assert row.group_id == group.id
    assert row.tool_name == "hidden"
    assert row.system_id == system.id
    assert row.ok is False
    assert row.http_status is None
    blob = _blob(row)
    assert "无权限" not in blob
    assert "隐藏参数" not in blob
    assert token not in blob


async def test_missing_binding_stores_failure_without_http_status(db) -> None:
    user = await _user(db)
    oa = await _system(db, "oa_log_bound", base_url="https://oa.example.com")
    mes = await _system(db, "mes_log_unbound", base_url="https://mes.example.com")
    await _auth_config(db, oa.id)
    await _auth_config(db, mes.id)
    await _bind_user(db, user.id, oa.id)
    tool = await _rest(db, mes.id, "jobs", url="/jobs", jsonpath_filter=None)
    group = await _mcp_group(db, "日志缺绑定")
    token = await _member(db, group.id, user.id)
    await _publish_rest(db, group.id, tool.id, "mes_jobs")

    response, gateway = await _call(db, group.id, token, "mes_jobs")

    assert _visible_text(response) == "无权限"
    assert gateway.requests == []
    rows = await _rows(db)
    assert len(rows) == 1
    row = rows[0]
    assert row.tool_name == "mes_jobs"
    assert row.system_id == mes.id
    assert row.ok is False
    assert row.http_status is None
    assert token not in _blob(row)


async def test_disabled_member_stores_failure_without_http_status(db) -> None:
    user = await _user(db)
    system = await _system(db, "oa_log_member", base_url="https://oa.example.com")
    await _auth_config(db, system.id)
    await _bind_user(db, user.id, system.id)
    tool = await _rest(db, system.id, "todos")
    group = await _mcp_group(db, "日志成员")
    token = await _member(db, group.id, user.id)
    await _publish_rest(db, group.id, tool.id, "todos")
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
        await McpGroupService(_auth(), db).disable_member(group.id, "user", user.id)
        denied = await client.post(
            f"/mcp/{group.id}",
            headers=_headers(token),
            json=_rpc("tools/call", {"name": "todos", "arguments": {"q": "停用后"}}, rpc_id=2),
        )
        listed = await client.post(f"/mcp/{group.id}", headers=_headers(token), json=_rpc("tools/list", rpc_id=3))

    assert _visible_text(denied) == "无权限"
    assert _visible_text(listed) == "无权限"
    rows = await _rows(db)
    assert len(rows) == 2
    assert rows[0].ok is True
    assert rows[0].http_status == 200
    assert rows[1].user_id == user.id
    assert rows[1].group_id == group.id
    assert rows[1].tool_name == "todos"
    assert rows[1].system_id == system.id
    assert rows[1].ok is False
    assert rows[1].http_status is None
    assert "停用后" not in _blob(rows[1])
    assert token not in _blob(rows[1])


async def test_unknown_tool_stores_null_system_id(db) -> None:
    user = await _user(db)
    system = await _system(db, "oa_log_unknown", base_url="https://oa.example.com")
    await _auth_config(db, system.id)
    await _bind_user(db, user.id, system.id)
    tool = await _rest(db, system.id, "todos")
    group = await _mcp_group(db, "日志未知")
    token = await _member(db, group.id, user.id)
    await _publish_rest(db, group.id, tool.id, "todos")

    response, gateway = await _call(db, group.id, token, "missing", {"secret": "not-stored"})

    assert _visible_text(response) == "无权限"
    assert gateway.requests == []
    rows = await _rows(db)
    assert len(rows) == 1
    row = rows[0]
    assert row.tool_name == "missing"
    assert row.system_id is None
    assert row.ok is False
    assert row.http_status is None
    assert "not-stored" not in _blob(row)


async def test_non_2xx_rest_response_stores_status_and_ok_false(db) -> None:
    user = await _user(db)
    system = await _system(db, "oa_log_500", base_url="https://oa.example.com")
    await _auth_config(db, system.id)
    await _bind_user(db, user.id, system.id)
    tool = await _rest(db, system.id, "missing", url="/missing", jsonpath_filter=None)
    group = await _mcp_group(db, "日志500")
    token = await _member(db, group.id, user.id)
    await _publish_rest(db, group.id, tool.id, "missing_api")

    _response, gateway = await _call(db, group.id, token, "missing_api")

    assert len(gateway.hits("oa.example.com", "/login")) == 1
    assert len(gateway.hits("oa.example.com", "/missing")) == 1
    rows = await _rows(db)
    assert len(rows) == 1
    row = rows[0]
    assert row.system_id == system.id
    assert row.tool_name == "missing_api"
    assert row.http_status == 500
    assert row.ok is False
    assert "unexpected" not in _blob(row)
    assert _OA_TOKEN not in _blob(row)


async def test_upstream_401_stores_status_and_ok_false(db) -> None:
    user = await _user(db)
    system = await _system(db, "oa_log_upstream", base_url="https://oa.example.com")
    await _auth_config(db, system.id)
    await _bind_user(db, user.id, system.id)
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
            input_schema={"type": "object"},
            selected=True,
        ),
    )
    group = await _mcp_group(db, "日志上游")
    token = await _member(db, group.id, user.id)
    await McpGroupService(_auth(), db).add_tool(
        group.id,
        McpGroupToolCreateSchema(source="upstream", source_id=upstream_tool.id, external_name="portal_search"),
    )

    response, gateway = await _call(db, group.id, token, "portal_search", {"q": "请假"})

    assert json.loads(_visible_text(response))["status"] == 401
    assert len(gateway.hits("upstream.example.com")) == 1
    rows = await _rows(db)
    assert len(rows) == 1
    row = rows[0]
    assert row.user_id == user.id
    assert row.group_id == group.id
    assert row.tool_name == "portal_search"
    assert row.system_id == system.id
    assert row.http_status == 401
    assert row.ok is False
    blob = _blob(row)
    assert "expired" not in blob
    assert "upstream-secret" not in blob
    assert "请假" not in blob
    assert "search_docs" not in blob
    assert token not in blob


async def test_debug_unsaved_form_writes_no_call_log(db) -> None:
    """走现有的未保存调试。业务请求发生了，调用日志仍然是 0 行。"""
    before = await db.scalar(select(func.count()).select_from(CallLogModel))
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        if request.url.path.rstrip("/").endswith("/login"):
            return httpx.Response(200, json={"token": "secret-token", "expires_in": 60})
        return httpx.Response(200, json={"ok": True})

    service = _service(httpx.MockTransport(handler), ExpiringRedis(), [], [], binding=_binding())
    result = await service.debug(_draft(), 1, {"page": 1, "q": "open"})

    after = await db.scalar(select(func.count()).select_from(CallLogModel))
    assert result.status == 200
    assert seen
    assert before == 0
    assert after == 0
    assert await _rows(db) == []


async def test_aggregate_groups_counts_by_user_and_tool(db) -> None:
    user = await _user(db)
    other = await _user(db, "李四")
    system = await _system(db, "oa_log_agg", base_url="https://oa.example.com")
    await _auth_config(db, system.id)
    await _bind_user(db, user.id, system.id)
    await _bind_user(db, other.id, system.id)
    todos = await _rest(db, system.id, "todos")
    search = await _rest(db, system.id, "search", url="/todos", jsonpath_filter="$.todos")
    group = await _mcp_group(db, "日志汇总")
    token = await _member(db, group.id, user.id)
    other_token = await _member(db, group.id, other.id)
    await _publish_rest(db, group.id, todos.id, "todos")
    await _publish_rest(db, group.id, search.id, "search")

    await _call(db, group.id, token, "todos")
    await _call(db, group.id, token, "todos")
    await _call(db, group.id, token, "search")
    await _call(db, group.id, other_token, "todos")

    response = await aggregate_call_log_controller(auth=_auth(), db=db)
    assert response.status_code == 200
    payload = json.loads(response.body)
    data = payload["data"]
    assert [item["user_id"] for item in data] == [user.id, user.id, other.id]
    assert [item["tool_name"] for item in data] == ["search", "todos", "todos"]
    assert [item["count"] for item in data] == [1, 2, 1]
    stored = await _rows(db)
    for item in data:
        matched = [row for row in stored if row.user_id == item["user_id"] and row.tool_name == item["tool_name"]]
        assert item["elapsed_ms"] == sum(row.elapsed_ms for row in matched)
        assert item["count"] == len(matched)
        assert set(item) == {"user_id", "tool_name", "count", "elapsed_ms", "created_at"}
        assert "title" not in json.dumps(item, ensure_ascii=False)
