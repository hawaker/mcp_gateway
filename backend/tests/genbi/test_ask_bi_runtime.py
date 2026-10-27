"""ask_bi MCP：tools/list 名称；call mock Wren；未部署失败；ACL deny；call_log 无 SQL 明文。"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import httpx
import pytest
from sqlalchemy import select

from app.core.base_schema import AuthSchema
from app.modules.mcp_gateway.call_log.model import CallLogModel
from app.modules.mcp_gateway.mcp_group.schema import McpGroupCreateSchema, McpGroupMemberCreateSchema
from app.modules.mcp_gateway.mcp_group.service import McpCredentialService, McpGroupService
from app.modules.mcp_gateway.runtime.app import build_mcp_app
from tests.mcp_gateway.test_runtime import (
    _headers,
    _rpc,
    _system,
    _tool_names,
    _user,
    _visible_text,
)
from tests.mcp_gateway.test_token_cache import ExpiringRedis


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


async def _datasource(db, *, system_id: int, name: str = "OA 数仓"):
    from app.modules.genbi.datasource.service import GenbiDatasourceService

    return await GenbiDatasourceService(AuthSchema(), db).create(
        system_id=system_id,
        name=name,
        wren_type="POSTGRES",
        host="127.0.0.1",
        port=5432,
        username="bi",
        password="secret",
        database="oa",
        db_schema="public",
    )


async def _project_with_models(db, *, system_id: int, deploy: bool = True):
    from app.modules.genbi.project.service import GenbiProjectService
    from app.modules.genbi.project.wren_client import StubWrenClient

    ds = await _datasource(db, system_id=system_id)
    svc = GenbiProjectService(AuthSchema(), db)
    project = await svc.create(datasource_id=ds.id, display_name="问数项目")
    models = await svc.sync_models(
        project_id=project.id,
        models=[
            {
                "display_name": "用户",
                "source_table_name": "users",
                "reference_name": "users",
                "properties": {"schema": "public", "table": "users"},
                "columns": [
                    {
                        "display_name": "ID",
                        "source_column_name": "id",
                        "column_type": "integer",
                        "properties": {"isPk": True},
                    },
                    {
                        "display_name": "姓名",
                        "source_column_name": "name",
                        "column_type": "varchar",
                    },
                ],
            }
        ],
    )
    if deploy:
        await svc.deploy(project_id=project.id, wren_client=StubWrenClient())
    return ds, project, models


async def _mcp_group(db, name: str = "问数组"):
    return await McpGroupService(AuthSchema(), db).create(
        McpGroupCreateSchema(name=name, enabled=True)
    )


async def _member_token(db, group_id: int, user_id: int) -> str:
    await McpGroupService(AuthSchema(), db).add_member(
        group_id,
        McpGroupMemberCreateSchema(principal_type="user", principal_id=user_id),
    )
    return await McpCredentialService(AuthSchema(), db).issue(user_id=user_id, group_id=group_id)


async def _attach_ask_bi(db, *, group_id: int, datasource_id: int, external_name: str):
    from app.modules.genbi.acl.service import GenbiGroupDatasourceService

    return await GenbiGroupDatasourceService(AuthSchema(), db).attach(
        group_id=group_id,
        datasource_id=datasource_id,
        external_name=external_name,
        enabled=True,
    )


@asynccontextmanager
async def _client(group_id: int, db, redis) -> AsyncIterator[httpx.AsyncClient]:
    app = build_mcp_app(
        group_id,
        db=db,
        redis=redis,
        transport=httpx.MockTransport(lambda r: httpx.Response(500)),
    )
    asgi = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=asgi, base_url="http://mcp.test") as client:
        yield client


@pytest.mark.asyncio
async def test_tools_list_includes_ask_bi_external_name(db) -> None:
    from app.modules.mcp_gateway.mcp_group.service import McpGroupService as Svc

    user = await _user(db)
    system = await _system(db, "oa_ask_list", base_url="https://oa.example.com")
    ds, _, _ = await _project_with_models(db, system_id=system.id, deploy=True)
    group = await _mcp_group(db)
    token = await _member_token(db, group.id, user.id)
    tool_name = f"{system.code}_ask_bi"
    await _attach_ask_bi(db, group_id=group.id, datasource_id=ds.id, external_name=tool_name)

    catalog = await Svc(AuthSchema(), db).tools_for(group.id)
    names = [t.name for t in catalog]
    assert tool_name in names
    ask = next(t for t in catalog if t.name == tool_name)
    assert ask.source == "genbi"
    assert ask.input_schema.get("properties", {}).get("question")

    redis = ExpiringRedis()
    async with _client(group.id, db, redis) as client:
        listed = await client.post(
            f"/mcp/{group.id}", headers=_headers(token), json=_rpc("tools/list")
        )
    assert tool_name in _tool_names(listed)


@pytest.mark.asyncio
async def test_tools_call_ask_bi_with_mocked_wren(db, monkeypatch: pytest.MonkeyPatch) -> None:
    from app.modules.genbi.ask.executor import StubSqlExecutor
    from app.modules.genbi.ask.wren_ask import StubWrenAskClient
    import app.modules.genbi.ask.service as ask_mod

    user = await _user(db)
    system = await _system(db, "oa_ask_call", base_url="https://oa.example.com")
    ds, _, _ = await _project_with_models(db, system_id=system.id, deploy=True)
    group = await _mcp_group(db)
    token = await _member_token(db, group.id, user.id)
    tool_name = f"{system.code}_ask_bi"
    await _attach_ask_bi(db, group_id=group.id, datasource_id=ds.id, external_name=tool_name)

    stub_wren = StubWrenAskClient(sql='SELECT "users"."name" FROM "users"')
    stub_exec = StubSqlExecutor(
        columns=["name"],
        rows=[{"name": "张三"}],
    )
    monkeypatch.setattr(ask_mod, "get_wren_ask_client", lambda: stub_wren)
    monkeypatch.setattr(ask_mod, "get_sql_executor", lambda: stub_exec)

    redis = ExpiringRedis()
    async with _client(group.id, db, redis) as client:
        called = await client.post(
            f"/mcp/{group.id}",
            headers=_headers(token),
            json=_rpc("tools/call", {"name": tool_name, "arguments": {"question": "有哪些用户"}}),
        )
    assert called.status_code == 200
    text = _visible_text(called)
    payload = json.loads(text)
    assert payload.get("error") is None
    assert payload.get("sql")
    assert payload.get("columns") == ["name"]
    assert payload.get("rows")
    assert stub_wren.ask_calls == 1
    assert stub_exec.execute_calls == 1

    logs = (
        await db.execute(
            select(CallLogModel).where(
                CallLogModel.user_id == user.id,
                CallLogModel.group_id == group.id,
                CallLogModel.tool_name == tool_name,
            )
        )
    ).scalars().all()
    assert len(logs) == 1
    assert logs[0].ok is True
    assert logs[0].system_id == system.id
    dumped = json.dumps({c.key: getattr(logs[0], c.key) for c in logs[0].__table__.columns}, default=str)
    assert "SELECT" not in dumped
    assert "张三" not in dumped


@pytest.mark.asyncio
async def test_ask_bi_undeployed_fails(db, monkeypatch: pytest.MonkeyPatch) -> None:
    import app.modules.genbi.ask.service as ask_mod
    from app.modules.genbi.ask.wren_ask import StubWrenAskClient
    from app.modules.genbi.ask.executor import StubSqlExecutor

    user = await _user(db)
    system = await _system(db, "oa_ask_undeployed", base_url="https://oa.example.com")
    ds, _, _ = await _project_with_models(db, system_id=system.id, deploy=False)
    group = await _mcp_group(db)
    token = await _member_token(db, group.id, user.id)
    tool_name = f"{system.code}_ask_bi"
    await _attach_ask_bi(db, group_id=group.id, datasource_id=ds.id, external_name=tool_name)

    monkeypatch.setattr(ask_mod, "get_wren_ask_client", lambda: StubWrenAskClient())
    monkeypatch.setattr(ask_mod, "get_sql_executor", lambda: StubSqlExecutor())

    redis = ExpiringRedis()
    async with _client(group.id, db, redis) as client:
        called = await client.post(
            f"/mcp/{group.id}",
            headers=_headers(token),
            json=_rpc("tools/call", {"name": tool_name, "arguments": {"question": "有哪些用户"}}),
        )
    payload = json.loads(_visible_text(called))
    assert payload.get("code") == "DEPLOY_REQUIRED"
    assert payload.get("error")
    assert called.json()["result"].get("isError") is True


@pytest.mark.asyncio
async def test_ask_bi_acl_column_deny(db, monkeypatch: pytest.MonkeyPatch) -> None:
    from app.modules.genbi.acl.schema import GenbiAclColumnPolicyIn, GenbiGroupDatasourceAclSave
    from app.modules.genbi.acl.service import GenbiGroupDatasourceService
    from app.modules.genbi.ask.executor import StubSqlExecutor
    from app.modules.genbi.ask.wren_ask import StubWrenAskClient
    import app.modules.genbi.ask.service as ask_mod

    user = await _user(db)
    system = await _system(db, "oa_ask_acl", base_url="https://oa.example.com")
    ds, _, models = await _project_with_models(db, system_id=system.id, deploy=True)
    group = await _mcp_group(db)
    token = await _member_token(db, group.id, user.id)
    tool_name = f"{system.code}_ask_bi"
    link = await _attach_ask_bi(db, group_id=group.id, datasource_id=ds.id, external_name=tool_name)

    model = models[0]
    name_col = next(c for c in model.columns if c.source_column_name == "name")
    await GenbiGroupDatasourceService(AuthSchema(), db).save_acl(
        link.id,
        GenbiGroupDatasourceAclSave(
            row_policies=[],
            column_policies=[
                GenbiAclColumnPolicyIn(
                    model_id=model.id,
                    column_id=name_col.id,
                    action="deny",
                )
            ],
        ),
    )

    monkeypatch.setattr(
        ask_mod,
        "get_wren_ask_client",
        lambda: StubWrenAskClient(sql='SELECT "users"."name" FROM "users"'),
    )
    monkeypatch.setattr(ask_mod, "get_sql_executor", lambda: StubSqlExecutor())

    redis = ExpiringRedis()
    async with _client(group.id, db, redis) as client:
        called = await client.post(
            f"/mcp/{group.id}",
            headers=_headers(token),
            json=_rpc("tools/call", {"name": tool_name, "arguments": {"question": "查姓名"}}),
        )
    payload = json.loads(_visible_text(called))
    assert payload.get("code") == "ACL_COLUMN_DENIED"
    assert payload.get("error")
