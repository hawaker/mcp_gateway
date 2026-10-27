"""GenBI 知识库：instructions / metric_docs / sql_pairs + agent_profile。"""

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


async def _project(db):
    from app.modules.genbi.datasource.service import GenbiDatasourceService
    from app.modules.genbi.project.service import GenbiProjectService

    system = await _system(db, "oa_genbi_know", base_url="https://oa.example.com")
    ds = await GenbiDatasourceService(AuthSchema(), db).create(
        system_id=system.id,
        name="知识源",
        wren_type="POSTGRES",
        host="127.0.0.1",
        port=5432,
        username="bi",
        password="secret",
        database="oa",
        db_schema="public",
    )
    return await GenbiProjectService(AuthSchema(), db).create(
        datasource_id=ds.id, display_name="知识项目"
    )


async def test_instruction_sql_pair_metric_doc_crud(db) -> None:
    from app.modules.genbi.project.schema import (
        GenbiInstructionCreate,
        GenbiInstructionUpdate,
        GenbiMetricDocCreate,
        GenbiSqlPairCreate,
    )
    from app.modules.genbi.project.service import GenbiProjectService

    project = await _project(db)
    svc = GenbiProjectService(AuthSchema(), db)

    inst = await svc.create_instruction(
        project.id,
        GenbiInstructionCreate(instruction="只查本部门数据", questions=["我的订单"], is_default=True),
    )
    assert inst.id is not None
    listed = await svc.list_instructions(project.id)
    assert any(item.id == inst.id for item in listed)

    updated = await svc.update_instruction(
        project.id,
        inst.id,
        GenbiInstructionUpdate(instruction="只查本部门已完成订单"),
    )
    assert updated.instruction == "只查本部门已完成订单"

    doc = await svc.create_metric_doc(
        project.id,
        GenbiMetricDocCreate(name="GMV", content="成交总额", enabled=True),
    )
    assert doc.name == "GMV"
    assert len(await svc.list_metric_docs(project.id)) == 1

    pair = await svc.create_sql_pair(
        project.id,
        GenbiSqlPairCreate(question="订单数", sql="select count(*) from orders", enabled=True),
    )
    assert pair.id is not None
    assert len(await svc.list_sql_pairs(project.id)) == 1

    await svc.delete_instruction(project.id, inst.id)
    assert all(item.id != inst.id for item in await svc.list_instructions(project.id))


async def test_agent_profile_patch(db) -> None:
    from app.modules.genbi.project.schema import GenbiAgentProfileUpdate
    from app.modules.genbi.project.service import GenbiProjectService

    project = await _project(db)
    svc = GenbiProjectService(AuthSchema(), db)

    profile = await svc.patch_agent_profile(
        project.id,
        GenbiAgentProfileUpdate(
            instructions=["be concise"],
            tools_config=[{"name": "ask_bi"}],
            virtual_agent_id="va-1",
        ),
    )
    assert profile.instructions == ["be concise"]
    assert profile.virtual_agent_id == "va-1"
    got = await svc.get_agent_profile(project.id)
    assert got.tools_config == [{"name": "ask_bi"}]


async def test_relationship_sync_requires_models(db) -> None:
    from app.modules.genbi.project.schema import GenbiModelIn, GenbiRelationshipIn
    from app.modules.genbi.project.service import GenbiProjectService

    project = await _project(db)
    svc = GenbiProjectService(AuthSchema(), db)

    with pytest.raises(CustomException):
        await svc.sync_relationships(
            project_id=project.id,
            relationships=[
                GenbiRelationshipIn(from_model_id=1, to_model_id=2, join_type="MANY_TO_ONE")
            ],
        )

    models = await svc.sync_models(
        project_id=project.id,
        models=[
            GenbiModelIn(
                display_name="订单",
                source_table_name="orders",
                reference_name="orders",
                columns=[],
            ),
            GenbiModelIn(
                display_name="用户",
                source_table_name="users",
                reference_name="users",
                columns=[],
            ),
        ],
    )
    rels = await svc.sync_relationships(
        project_id=project.id,
        relationships=[
            GenbiRelationshipIn(
                from_model_id=models[0].id,
                to_model_id=models[1].id,
                join_type="MANY_TO_ONE",
                condition="orders.user_id = users.id",
            )
        ],
    )
    assert len(rels) == 1
    assert len(await svc.list_relationships(project.id)) == 1
