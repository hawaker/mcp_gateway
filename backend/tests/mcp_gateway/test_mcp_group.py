"""MCP 组、成员与每人每组一个稳定 token。

行为通过 service 写入真实会话，不启动 FastAPI，也不挂载 /mcp/{group_id}。
"""

import hashlib

import pytest
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import delete, func, select

from app.config.path_conf import BASE_DIR
from app.core.base_schema import AuthSchema
from app.core.exceptions import CustomException
from app.modules.mcp_gateway.mcp_group.controller import McpGroupRouter
from app.modules.mcp_gateway.mcp_group.model import (
    McpCredentialModel,
    McpGroupMemberModel,
    McpGroupModel,
    McpGroupToolModel,
)
from app.modules.mcp_gateway.mcp_group.schema import (
    McpCredentialOutSchema,
    McpGroupCreateSchema,
    McpGroupMemberCreateSchema,
    McpGroupToolCreateSchema,
)
from app.modules.mcp_gateway.mcp_group.service import McpCredentialService, McpGroupService, NotFound
from app.modules.mcp_gateway.rest_tool.model import RestToolModel
from app.modules.mcp_gateway.system.model import BizSystemModel
from app.modules.mcp_gateway.upstream.model import UpstreamMcpModel, UpstreamToolModel
from app.modules.mcp_gateway.user.model import BizUserGroupMemberModel, BizUserGroupModel, BizUserModel
from app.utils.crypto_util import CryptoUtil


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


def _sha256(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


async def _add(db, row):
    db.add(row)
    await db.flush()
    return row


async def _user(db, name: str = "张三") -> BizUserModel:
    return await _add(db, BizUserModel(name=name, enabled=True))


async def _biz_group(db, name: str) -> BizUserGroupModel:
    return await _add(db, BizUserGroupModel(name=name, enabled=True))


async def _join(db, user_id: int, group_id: int) -> None:
    await _add(db, BizUserGroupMemberModel(user_id=user_id, group_id=group_id))


async def _system(db, code: str) -> BizSystemModel:
    return await _add(
        db,
        BizSystemModel(
            name=code,
            code=code,
            base_url="https://oa.example.com",
            enabled=True,
            uid_field="uid",
        ),
    )


async def _rest(db, system_id: int, name: str = "search") -> RestToolModel:
    return await _add(
        db,
        RestToolModel(
            name=name,
            display_name=name,
            url=f"https://oa.example.com/{name}",
            description="查找文档",
            input_schema={"type": "object", "properties": {"q": {"type": "string"}}},
            enabled=True,
            system_id=system_id,
        ),
    )


async def _upstream(db, system_id: int = 0, *, code: str | None = None) -> UpstreamMcpModel:
    import secrets

    return await _add(
        db,
        UpstreamMcpModel(
            name="Proxy",
            code=code or f"up{secrets.token_hex(4)}",
            url="https://mcp.example.com/rpc",
            credential_header="X-Api-Key",
            credential_value_encrypted=CryptoUtil.encrypt("upstream-secret"),
        ),
    )


async def _upstream_tool(db, upstream_id: int, *, selected: bool = True, remote_name: str = "search_docs") -> UpstreamToolModel:
    return await _add(
        db,
        UpstreamToolModel(
            upstream_id=upstream_id,
            remote_name=remote_name,
            external_name=f"oa_{remote_name}",
            input_schema={"type": "object", "properties": {"q": {"type": "string"}}},
            selected=selected,
        ),
    )


async def _mcp_group(db, name: str = "门户") -> McpGroupModel:
    created = await McpGroupService(_auth(), db).create(McpGroupCreateSchema(name=name, enabled=True))
    row = await db.get(McpGroupModel, created.id)
    assert row is not None
    assert row.name == name
    assert row.enabled is True
    return row


async def _credential_row(db, user_id: int, group_id: int) -> McpCredentialModel:
    row = (
        await db.execute(
            select(McpCredentialModel)
            .where(
                McpCredentialModel.user_id == user_id,
                McpCredentialModel.group_id == group_id,
            )
            .execution_options(populate_existing=True)
        )
    ).scalar_one()
    return row


async def _credential_count(db, user_id: int, group_id: int) -> int:
    return (await db.execute(select(func.count()).select_from(McpCredentialModel).where(McpCredentialModel.user_id == user_id, McpCredentialModel.group_id == group_id))).scalar_one()


async def test_membership_disable_keeps_token(db) -> None:
    """停用成员后原 token 仍能 verify。remove_member 始终抛 NotFound，且不删行。"""
    user = await _user(db)
    group = await _mcp_group(db)
    groups = McpGroupService(_auth(), db)
    credentials = McpCredentialService(_auth(), db)
    await groups.add_member(
        group.id,
        McpGroupMemberCreateSchema(principal_type="user", principal_id=user.id),
    )
    raw = await credentials.issue(user_id=user.id, group_id=group.id)
    stored = await _credential_row(db, user.id, group.id)
    assert stored.token_hash == _sha256(raw)
    assert CryptoUtil.decrypt(stored.token_encrypted) == raw
    assert raw not in stored.token_encrypted

    await groups.disable_member(group_id=group.id, principal_type="user", principal_id=user.id)
    assert await credentials.verify(raw) == (user.id, group.id)

    with pytest.raises(NotFound):
        await groups.remove_member(group_id=group.id, principal_type="user", principal_id=user.id)

    member = (
        await db.execute(
            select(McpGroupMemberModel).where(
                McpGroupMemberModel.group_id == group.id,
                McpGroupMemberModel.principal_type == "user",
                McpGroupMemberModel.principal_id == user.id,
            )
        )
    ).scalar_one()
    assert member.enabled is False
    assert await _credential_count(db, user.id, group.id) == 1
    assert (await _credential_row(db, user.id, group.id)).token_hash == _sha256(raw)


async def test_duplicate_external_name_is_400_and_alias_is_stored(db) -> None:
    """同一组外部名重复则 CustomException 对应 HTTP 400。换一个别名后写入该组的 external_name。"""
    system = await _system(db, "oa_alias")
    rest = await _rest(db, system.id, name="search")
    other = await _rest(db, system.id, name="lookup")
    upstream = await _upstream(db, system.id)
    selected = await _upstream_tool(db, upstream.id, selected=True, remote_name="lookup_docs")
    group = await _mcp_group(db, name="别名组")
    other_group = await _mcp_group(db, name="另一组")
    service = McpGroupService(_auth(), db)

    first = await service.add_tool(
        group.id,
        McpGroupToolCreateSchema(source="rest", source_id=rest.id, external_name="search"),
    )
    assert first.external_name == "search"

    with pytest.raises(CustomException) as exc_info:
        await service.add_tool(
            group.id,
            McpGroupToolCreateSchema(source="upstream", source_id=selected.id, external_name="search"),
        )
    assert exc_info.value.status_code == 400
    assert "外部名称" in exc_info.value.msg

    aliased = await service.add_tool(
        group.id,
        McpGroupToolCreateSchema(source="upstream", source_id=selected.id, external_name="search_alias"),
    )
    stored = (await db.execute(select(McpGroupToolModel).where(McpGroupToolModel.id == aliased.id).execution_options(populate_existing=True))).scalar_one()
    assert stored is not None
    assert stored.external_name == "search_alias"
    assert stored.source == "upstream"
    assert stored.source_id == selected.id

    same_name_elsewhere = await service.add_tool(
        other_group.id,
        McpGroupToolCreateSchema(source="rest", source_id=other.id, external_name="search"),
    )
    assert same_name_elsewhere.external_name == "search"


async def test_unselected_upstream_tool_cannot_be_added(db) -> None:
    system = await _system(db, "oa_unselected")
    upstream = await _upstream(db, system.id)
    tool = await _upstream_tool(db, upstream.id, selected=False)
    group = await _mcp_group(db, name="未选用")
    service = McpGroupService(_auth(), db)

    with pytest.raises(CustomException) as exc_info:
        await service.add_tool(
            group.id,
            McpGroupToolCreateSchema(source="upstream", source_id=tool.id),
        )
    assert exc_info.value.status_code == 400
    count = (await db.execute(select(func.count()).select_from(McpGroupToolModel).where(McpGroupToolModel.group_id == group.id))).scalar_one()
    assert count == 0


async def test_tools_for_omits_disabled_or_deleted_sources(db) -> None:
    """tools_for 是下一任务的 tools/list 目录。定义停用、删除，或上游未选用/上游被删，都不再出现。"""
    system = await _system(db, "oa_catalog")
    live_rest = await _rest(db, system.id, name="live_rest")
    disabled_rest = await _rest(db, system.id, name="disabled_rest")
    paused_rest = await _rest(db, system.id, name="paused_rest")
    deleted_rest = await _rest(db, system.id, name="deleted_rest")
    upstream = await _upstream(db, system.id)
    deleted_upstream = await _upstream(db, system.id)
    live_tool = await _upstream_tool(db, upstream.id, selected=True, remote_name="live_tool")
    unselected_later = await _upstream_tool(db, upstream.id, selected=True, remote_name="later_off")
    deleted_tool = await _upstream_tool(db, upstream.id, selected=True, remote_name="deleted_tool")
    orphan_tool = await _upstream_tool(db, deleted_upstream.id, selected=True, remote_name="orphan_tool")
    group = await _mcp_group(db, name="目录")
    service = McpGroupService(_auth(), db)

    await service.add_tool(group.id, McpGroupToolCreateSchema(source="rest", source_id=live_rest.id, external_name="live_rest"))
    await service.add_tool(
        group.id,
        McpGroupToolCreateSchema(source="rest", source_id=disabled_rest.id, external_name="disabled_rest"),
    )
    paused_link = await service.add_tool(
        group.id,
        McpGroupToolCreateSchema(source="rest", source_id=paused_rest.id, external_name="paused_rest"),
    )
    await service.add_tool(group.id, McpGroupToolCreateSchema(source="rest", source_id=deleted_rest.id, external_name="deleted_rest"))
    await service.add_tool(group.id, McpGroupToolCreateSchema(source="upstream", source_id=live_tool.id, external_name="live_tool"))
    await service.add_tool(
        group.id,
        McpGroupToolCreateSchema(source="upstream", source_id=unselected_later.id, external_name="later_off"),
    )
    await service.add_tool(
        group.id,
        McpGroupToolCreateSchema(source="upstream", source_id=deleted_tool.id, external_name="deleted_tool"),
    )
    await service.add_tool(
        group.id,
        McpGroupToolCreateSchema(source="upstream", source_id=orphan_tool.id, external_name="orphan_tool"),
    )
    await service.update_tool_enabled(paused_link.id, enabled=False)
    disabled_rest.enabled = False
    deleted_rest.is_deleted = True
    unselected_later.selected = False
    deleted_tool.is_deleted = True
    deleted_upstream.is_deleted = True
    await db.flush()

    catalog = await service.tools_for(group.id)
    assert [item.name for item in catalog] == ["live_rest", "live_tool"]
    rest_item = catalog[0]
    assert rest_item.description == "查找文档"
    assert rest_item.input_schema["properties"]["q"]["type"] == "string"
    assert rest_item.source == "rest"
    assert rest_item.source_id == live_rest.id
    assert catalog[1].source == "upstream"
    assert catalog[1].source_id == live_tool.id
    assert catalog[1].name == "live_tool"


async def test_two_biz_groups_issue_one_stable_credential(db) -> None:
    """同一个人被两个业务用户组勾进同一 MCP 组，只生成一行凭证，且不轮换。"""
    user = await _user(db, name="李四")
    first_group = await _biz_group(db, "甲")
    second_group = await _biz_group(db, "乙")
    await _join(db, user.id, first_group.id)
    await _join(db, user.id, second_group.id)
    mcp_group = await _mcp_group(db, name="双组")
    groups = McpGroupService(_auth(), db)
    credentials = McpCredentialService(_auth(), db)

    await groups.add_member(
        mcp_group.id,
        McpGroupMemberCreateSchema(principal_type="group", principal_id=first_group.id),
    )
    raw = await credentials.issue(user_id=user.id, group_id=mcp_group.id)
    before = (await _credential_row(db, user.id, mcp_group.id)).token_hash

    await groups.add_member(
        mcp_group.id,
        McpGroupMemberCreateSchema(principal_type="group", principal_id=second_group.id),
    )
    after = await _credential_row(db, user.id, mcp_group.id)
    assert await _credential_count(db, user.id, mcp_group.id) == 1
    assert after.token_hash == before
    assert after.token_hash == _sha256(raw)
    assert await credentials.issue(user_id=user.id, group_id=mcp_group.id) == raw
    assert await credentials.verify(raw) == (user.id, mcp_group.id)


async def test_leave_biz_group_and_rejoin_keeps_token(db) -> None:
    """离开业务用户组再加回，只动成员表那一行。原 token 仍然 verify。"""
    user = await _user(db, name="王五")
    biz_group = await _biz_group(db, "临时组")
    await _join(db, user.id, biz_group.id)
    mcp_group = await _mcp_group(db, name="稳定组")
    groups = McpGroupService(_auth(), db)
    credentials = McpCredentialService(_auth(), db)
    await groups.add_member(
        mcp_group.id,
        McpGroupMemberCreateSchema(principal_type="group", principal_id=biz_group.id),
    )
    raw = await credentials.issue(user_id=user.id, group_id=mcp_group.id)

    await db.execute(
        delete(BizUserGroupMemberModel).where(
            BizUserGroupMemberModel.user_id == user.id,
            BizUserGroupMemberModel.group_id == biz_group.id,
        )
    )
    await db.flush()
    await _join(db, user.id, biz_group.id)

    assert await credentials.verify(raw) == (user.id, mcp_group.id)
    stored = await _credential_row(db, user.id, mcp_group.id)
    assert stored.token_hash == _sha256(raw)
    assert CryptoUtil.decrypt(stored.token_encrypted) == raw


async def test_reissue_replaces_hash_and_old_token_fails(db) -> None:
    user = await _user(db, name="赵六")
    group = await _mcp_group(db, name="轮换")
    credentials = McpCredentialService(_auth(), db)
    raw = await credentials.issue(user_id=user.id, group_id=group.id)
    renewed = await credentials.reissue(user_id=user.id, group_id=group.id)

    assert renewed != raw
    assert await _credential_count(db, user.id, group.id) == 1
    stored = await _credential_row(db, user.id, group.id)
    assert stored.token_hash == _sha256(renewed)
    assert stored.token_hash != _sha256(raw)
    assert CryptoUtil.decrypt(stored.token_encrypted) == renewed
    with pytest.raises(CustomException):
        await credentials.verify(raw)
    assert await credentials.verify(renewed) == (user.id, group.id)


async def test_connection_info_reveals_urls_without_rotating(db) -> None:
    user = await _user(db, name="钱七")
    group = await _mcp_group(db, name="连接")
    credentials = McpCredentialService(_auth(), db)
    with pytest.raises(CustomException):
        await credentials.connection_info(user_id=user.id, group_id=group.id)
    assert await _credential_count(db, user.id, group.id) == 0

    raw = await credentials.issue(user_id=user.id, group_id=group.id)
    info = await credentials.connection_info(user_id=user.id, group_id=group.id)
    assert info.streamable_http_url == f"/mcp/{group.id}"
    assert info.sse_url == f"/mcp/{group.id}/sse"
    assert info.messages_url == f"/mcp/{group.id}/messages"
    assert info.authorization == f"Authorization: Bearer {raw}"
    again = await credentials.connection_info(user_id=user.id, group_id=group.id)
    assert again.authorization == info.authorization
    assert (await _credential_row(db, user.id, group.id)).token_hash == _sha256(raw)


async def test_credential_list_omits_raw_token(db) -> None:
    user = await _user(db, name="孙八")
    group = await _mcp_group(db, name="列表")
    credentials = McpCredentialService(_auth(), db)
    raw = await credentials.issue(user_id=user.id, group_id=group.id)
    stored = await _credential_row(db, user.id, group.id)
    page = await credentials.page(page_no=1, page_size=10)
    payload = page.model_dump_json()
    assert raw not in payload
    assert stored.token_hash not in payload
    assert stored.token_encrypted not in payload
    visible = McpCredentialOutSchema.model_validate(stored).model_dump()
    assert visible["user_id"] == user.id
    assert visible["group_id"] == group.id
    assert "token_hash" not in visible
    assert "token_encrypted" not in visible
    assert "token" not in visible


def test_router_has_no_remove_or_transport() -> None:
    from app.api.v1.routers import DOMAIN_CONTROLLERS
    from app.core.dependencies import AuthPermission

    assert McpGroupRouter in DOMAIN_CONTROLLERS["/mcp-gateway"]
    actions: set[str] = set()
    for route in McpGroupRouter.routes:
        path = getattr(route, "path", "")
        assert path.startswith("/mcp-group")
        assert not path.startswith("/mcp/")
        assert "delete" not in path
        dependant = getattr(route, "dependant", None)
        if dependant is None:
            continue
        for dep in dependant.dependencies:
            call = getattr(dep, "call", None)
            if isinstance(call, AuthPermission):
                assert call.permissions
                for permission in call.permissions:
                    prefix, action = permission.rsplit(":", 1)
                    assert prefix == "module_mcp_gateway:mcp-group"
                    assert action in {"query", "create", "update"}
                    actions.add(action)
    assert actions == {"query", "create", "update"}

    source = (BASE_DIR / "app/modules/mcp_gateway/mcp_group/controller.py").read_text(encoding="utf-8")
    assert "status_code=" not in source
    assert "RET.DATAEXIST" not in source
    assert "HTTP_201" not in source


def test_revision_follows_upstream_tool_unique() -> None:
    script = ScriptDirectory.from_config(Config(str(BASE_DIR / "alembic.ini")))
    revision = script.get_revision("a7c3e9b14d62")
    assert revision is not None
    assert revision.down_revision == "b6e2d8a14c90"
    assert revision.revision != "b6e2d8a14c90"


async def test_add_member_again_re_enables_disabled_row(db) -> None:
    """再次添加已停用成员时，采用本次提交的 enabled，并重新签发凭证。"""
    user = await _user(db, name="再启用")
    group = await _mcp_group(db, name="再启用组")
    groups = McpGroupService(_auth(), db)
    credentials = McpCredentialService(_auth(), db)
    first = await groups.add_member(
        group.id,
        McpGroupMemberCreateSchema(principal_type="user", principal_id=user.id, enabled=True),
    )
    await credentials.issue(user_id=user.id, group_id=group.id)
    await groups.disable_member(group_id=group.id, principal_type="user", principal_id=user.id)
    again = await groups.add_member(
        group.id,
        McpGroupMemberCreateSchema(principal_type="user", principal_id=user.id, enabled=True),
    )
    assert again.id == first.id
    assert again.enabled is True
    member = (
        await db.execute(
            select(McpGroupMemberModel).where(McpGroupMemberModel.id == first.id)
        )
    ).scalar_one()
    assert member.enabled is True
    assert await _credential_count(db, user.id, group.id) == 1


async def test_late_biz_group_joiner_gets_credential(db) -> None:
    """业务用户组已是启用 MCP 成员后，后来通过服务加入的用户会拿到凭证。"""
    from app.modules.mcp_gateway.user.service import BizUserService

    early = await _user(db, name="先到")
    late = await _user(db, name="后到")
    biz_group = await _biz_group(db, "后加入")
    await _join(db, early.id, biz_group.id)
    mcp_group = await _mcp_group(db, name="联动签发")
    groups = McpGroupService(_auth(), db)
    credentials = McpCredentialService(_auth(), db)
    await groups.add_member(
        mcp_group.id,
        McpGroupMemberCreateSchema(principal_type="group", principal_id=biz_group.id),
    )
    early_token = await credentials.issue(user_id=early.id, group_id=mcp_group.id)
    assert await _credential_count(db, late.id, mcp_group.id) == 0

    await BizUserService(_auth(), db).add_to_groups(late.id, [biz_group.id])
    assert await _credential_count(db, late.id, mcp_group.id) == 1
    late_row = await _credential_row(db, late.id, mcp_group.id)
    late_raw = CryptoUtil.decrypt(late_row.token_encrypted)
    assert await credentials.verify(late_raw) == (late.id, mcp_group.id)
    assert await credentials.verify(early_token) == (early.id, mcp_group.id)
