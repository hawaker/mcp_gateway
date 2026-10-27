"""GenBI 建模同步与部署门禁：无 MDL 失败；mock Wren 成功写 deploy_log。"""

from __future__ import annotations

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


async def _project(db, *, system_id: int):
    from app.modules.genbi.project.service import GenbiProjectService

    ds = await _datasource(db, system_id=system_id)
    return await GenbiProjectService(AuthSchema(), db).create(
        datasource_id=ds.id,
        display_name="部署测试项目",
    )


async def test_deploy_without_mdl_fails(db) -> None:
    from app.modules.genbi.project.service import GenbiProjectService

    system = await _system(db, "oa_genbi_deploy_empty", base_url="https://oa.example.com")
    project = await _project(db, system_id=system.id)
    svc = GenbiProjectService(AuthSchema(), db)

    with pytest.raises(CustomException) as ei:
        await svc.deploy(project_id=project.id)
    assert "MDL" in str(ei.value.msg) or "模型" in str(ei.value.msg)


async def test_sync_models_then_deploy_with_mock_wren_writes_deploy_log(db) -> None:
    from app.modules.genbi.project.model import GenbiDeployLogModel
    from app.modules.genbi.project.service import GenbiProjectService
    from app.modules.genbi.project.wren_client import StubWrenClient
    from sqlalchemy import select

    system = await _system(db, "oa_genbi_deploy_ok", base_url="https://oa.example.com")
    project = await _project(db, system_id=system.id)
    svc = GenbiProjectService(AuthSchema(), db)

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
    assert len(models) == 1
    assert models[0].reference_name == "users"
    assert len(models[0].columns) == 2

    stub = StubWrenClient(mdl_hash_suffix="abc")
    log = await svc.deploy(project_id=project.id, wren_client=stub)
    assert log.status == "success"
    assert log.mdl_hash
    assert stub.deploy_calls == 1

    rows = (
        await db.execute(
            select(GenbiDeployLogModel).where(GenbiDeployLogModel.project_id == project.id)
        )
    ).scalars().all()
    assert len(rows) == 1
    assert rows[0].status == "success"
    assert rows[0].mdl_hash == log.mdl_hash

    refreshed = await svc.get(project.id)
    assert refreshed.onboarding_status == "deployed"
