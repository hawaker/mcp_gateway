"""GenBI 项目：一源一项目；重复创建拒绝。"""

import pytest

from app.core.base_schema import AuthSchema
from app.core.exceptions import CustomException
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


async def test_create_project_one_per_datasource_and_list_get(db) -> None:
    from app.modules.genbi.project.service import GenbiProjectService

    system = await _system(db, "oa_genbi_proj", base_url="https://oa.example.com")
    ds = await _datasource(db, system_id=system.id)
    svc = GenbiProjectService(AuthSchema(), db)

    row = await svc.create(datasource_id=ds.id, display_name="OA 问数项目")
    assert row.id is not None
    assert row.datasource_id == ds.id
    assert row.system_id == system.id
    assert row.display_name == "OA 问数项目"
    assert row.onboarding_status == "not_started"
    assert row.language == "zh-CN"

    got = await svc.get(row.id)
    assert got.id == row.id
    assert got.datasource_id == ds.id

    page = await svc.list(page_no=1, page_size=10)
    assert page.total >= 1
    assert any(item.id == row.id for item in page.items)


async def test_reject_duplicate_project_for_same_datasource(db) -> None:
    from app.modules.genbi.project.service import GenbiProjectService

    system = await _system(db, "oa_genbi_proj2", base_url="https://oa.example.com")
    ds = await _datasource(db, system_id=system.id, name="源 A")
    svc = GenbiProjectService(AuthSchema(), db)

    await svc.create(datasource_id=ds.id, display_name="项目一")
    with pytest.raises(CustomException) as ei:
        await svc.create(datasource_id=ds.id, display_name="项目二")
    assert "已存在" in str(ei.value.msg) or "重复" in str(ei.value.msg)


async def test_recreate_project_after_soft_delete_same_datasource(db) -> None:
    """软删除后同一 datasource 应可再创建（依赖 is_deleted=false 部分唯一索引）。"""
    from app.modules.genbi.project.crud import GenbiProjectCRUD
    from app.modules.genbi.project.service import GenbiProjectService

    system = await _system(db, "oa_genbi_proj3", base_url="https://oa.example.com")
    ds = await _datasource(db, system_id=system.id, name="源 B")
    auth = AuthSchema()
    svc = GenbiProjectService(auth, db)

    row = await svc.create(datasource_id=ds.id, display_name="将删项目")
    await GenbiProjectCRUD(auth, db).set([row.id], is_deleted=True)

    recreated = await svc.create(datasource_id=ds.id, display_name="重建项目")
    assert recreated.id != row.id
    assert recreated.datasource_id == ds.id
    assert recreated.display_name == "重建项目"
