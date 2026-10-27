"""组×源关联与共享 ACL：同组两源独立；无成员表/字段。"""

from __future__ import annotations

import pytest
from sqlalchemy import inspect

from app.core.base_schema import AuthSchema
from app.core.exceptions import CustomException
from app.modules.mcp_gateway.mcp_group.schema import McpGroupCreateSchema, McpGroupToolCreateSchema
from app.modules.mcp_gateway.mcp_group.service import McpGroupService
from tests.mcp_gateway.test_runtime import _system


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


async def _datasource(db, *, system_id: int, name: str):
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


async def _mcp_group(db, name: str = "问数组"):
    created = await McpGroupService(AuthSchema(), db).create(
        McpGroupCreateSchema(name=name, enabled=True)
    )
    return created


async def test_two_datasources_on_same_group_have_independent_acl(db) -> None:
    from app.modules.genbi.acl.schema import (
        GenbiGroupDatasourceAclSave,
        GenbiAclColumnPolicyIn,
        GenbiAclRowPolicyIn,
    )
    from app.modules.genbi.acl.service import GenbiGroupDatasourceService

    system = await _system(db, "oa_gd_acl", base_url="https://oa.example.com")
    ds_a = await _datasource(db, system_id=system.id, name="源 A")
    ds_b = await _datasource(db, system_id=system.id, name="源 B")
    group = await _mcp_group(db)
    svc = GenbiGroupDatasourceService(AuthSchema(), db)

    link_a = await svc.attach(
        group_id=group.id,
        datasource_id=ds_a.id,
        external_name="oa_a_ask_bi",
        enabled=True,
    )
    link_b = await svc.attach(
        group_id=group.id,
        datasource_id=ds_b.id,
        external_name="oa_b_ask_bi",
        enabled=True,
    )

    await svc.save_acl(
        link_a.id,
        GenbiGroupDatasourceAclSave(
            row_policies=[
                GenbiAclRowPolicyIn(
                    model_id=1,
                    column_id=10,
                    operator="eq",
                    values=["dept-a"],
                )
            ],
            column_policies=[
                GenbiAclColumnPolicyIn(
                    model_id=1,
                    column_id=11,
                    action="mask",
                    mask_template="keep_first_3",
                )
            ],
        ),
    )
    await svc.save_acl(
        link_b.id,
        GenbiGroupDatasourceAclSave(
            row_policies=[
                GenbiAclRowPolicyIn(
                    model_id=2,
                    column_id=20,
                    operator="in",
                    values=["x", "y"],
                )
            ],
            column_policies=[
                GenbiAclColumnPolicyIn(
                    model_id=2,
                    column_id=21,
                    action="deny",
                )
            ],
        ),
    )

    acl_a = await svc.get_acl(link_a.id)
    acl_b = await svc.get_acl(link_b.id)

    assert len(acl_a.row_policies) == 1
    assert acl_a.row_policies[0].values == ["dept-a"]
    assert acl_a.column_policies[0].action == "mask"
    assert len(acl_b.row_policies) == 1
    assert acl_b.row_policies[0].values == ["x", "y"]
    assert acl_b.column_policies[0].action == "deny"
    # 互不覆盖
    assert acl_a.row_policies[0].model_id != acl_b.row_policies[0].model_id


async def test_acl_models_have_no_member_fields(db) -> None:
    """无 ACL 成员表；规则表不含 user/member 字段。"""
    from app.modules.genbi.acl import model as acl_model

    assert not hasattr(acl_model, "GenbiAclMemberModel")
    assert not hasattr(acl_model, "GenbiGroupDatasourceAclMemberModel")

    for cls_name in (
        "GenbiGroupDatasourceModel",
        "GenbiGroupDatasourceAclRowModel",
        "GenbiGroupDatasourceAclColumnModel",
    ):
        cls = getattr(acl_model, cls_name)
        columns = {c.key for c in inspect(cls).mapper.column_attrs}
        for forbidden in ("user_id", "member_id", "principal_id", "principal_type"):
            assert forbidden not in columns, f"{cls_name} must not have {forbidden}"


async def test_update_rejects_empty_external_name(db) -> None:
    """更新不得把 required external_name 清成 null/空串。"""
    from app.modules.genbi.acl.schema import GenbiGroupDatasourceUpdate
    from app.modules.genbi.acl.service import GenbiGroupDatasourceService

    system = await _system(db, "oa_name_guard", base_url="https://oa.example.com")
    ds = await _datasource(db, system_id=system.id, name="命名源")
    group = await _mcp_group(db, name="命名组")
    svc = GenbiGroupDatasourceService(AuthSchema(), db)
    link = await svc.attach(
        group_id=group.id,
        datasource_id=ds.id,
        external_name="keep_me_ask_bi",
    )

    with pytest.raises(CustomException) as ei:
        await svc.update(link.id, GenbiGroupDatasourceUpdate(external_name=None))
    assert "不能为空" in str(ei.value.msg)

    with pytest.raises(CustomException) as ei2:
        await svc.update(link.id, GenbiGroupDatasourceUpdate(external_name="   "))
    assert "不能为空" in str(ei2.value.msg)

    from app.modules.genbi.acl.crud import GenbiGroupDatasourceCRUD

    row = await GenbiGroupDatasourceCRUD(AuthSchema(), db).get(id=link.id)
    assert row is not None
    assert row.external_name == "keep_me_ask_bi"


async def test_group_selection_requires_rest_or_upstream_or_datasource(db) -> None:
    """组保存校验：REST ∪ 上游 ∪ 数据源 至少一类。"""
    from app.modules.genbi.acl.service import GenbiGroupDatasourceService
    from app.modules.mcp_gateway.rest_tool.model import RestToolModel

    system = await _system(db, "oa_sel", base_url="https://oa.example.com")
    group = await _mcp_group(db, name="空组")
    svc = McpGroupService(AuthSchema(), db)

    with pytest.raises(CustomException) as ei:
        await svc.validate_selection(group.id)
    assert "至少" in str(ei.value.msg)

    # 仅数据源即可通过
    ds = await _datasource(db, system_id=system.id, name="唯一源")
    await GenbiGroupDatasourceService(AuthSchema(), db).attach(
        group_id=group.id,
        datasource_id=ds.id,
        external_name="only_ds_ask_bi",
    )
    await svc.validate_selection(group.id)

    # 仅 REST 也可
    group2 = await _mcp_group(db, name="REST组")
    rest = RestToolModel(
        name="search",
        display_name="search",
        url="https://oa.example.com/search",
        description="d",
        input_schema={"type": "object"},
        enabled=True,
        system_id=system.id,
    )
    db.add(rest)
    await db.flush()
    await svc.add_tool(
        group2.id,
        McpGroupToolCreateSchema(source="rest", source_id=rest.id, external_name="search"),
    )
    await svc.validate_selection(group2.id)


async def test_cross_catalog_external_name_uniqueness(db) -> None:
    """同组内 GenBI 与 REST/上游 external_name 互斥，冲突抛中文 CustomException。"""
    from app.modules.genbi.acl.service import GenbiGroupDatasourceService
    from app.modules.mcp_gateway.rest_tool.model import RestToolModel

    system = await _system(db, "oa_xcat", base_url="https://oa.example.com")
    group = await _mcp_group(db, name="跨目录组")
    rest = RestToolModel(
        name="portal_search",
        display_name="portal_search",
        url="https://oa.example.com/search",
        description="d",
        input_schema={"type": "object"},
        enabled=True,
        system_id=system.id,
    )
    db.add(rest)
    await db.flush()
    rest2 = RestToolModel(
        name="portal_lookup",
        display_name="portal_lookup",
        url="https://oa.example.com/lookup",
        description="d",
        input_schema={"type": "object"},
        enabled=True,
        system_id=system.id,
    )
    db.add(rest2)
    await db.flush()

    group_svc = McpGroupService(AuthSchema(), db)
    ds_svc = GenbiGroupDatasourceService(AuthSchema(), db)
    ds = await _datasource(db, system_id=system.id, name="跨目录源")

    await group_svc.add_tool(
        group.id,
        McpGroupToolCreateSchema(source="rest", source_id=rest.id, external_name="shared_name"),
    )

    with pytest.raises(CustomException) as ei_attach:
        await ds_svc.attach(
            group_id=group.id,
            datasource_id=ds.id,
            external_name="shared_name",
        )
    assert ei_attach.value.status_code == 400
    assert "外部名称" in str(ei_attach.value.msg)

    await ds_svc.attach(
        group_id=group.id,
        datasource_id=ds.id,
        external_name="genbi_only_name",
    )

    with pytest.raises(CustomException) as ei_add:
        await group_svc.add_tool(
            group.id,
            McpGroupToolCreateSchema(source="rest", source_id=rest2.id, external_name="genbi_only_name"),
        )
    assert ei_add.value.status_code == 400
    assert "外部名称" in str(ei_add.value.msg)
