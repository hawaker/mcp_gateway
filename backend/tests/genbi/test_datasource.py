import pytest
from sqlalchemy import select

from app.core.base_schema import AuthSchema
from app.modules.genbi.datasource.model import GenbiDatasourceModel
from app.utils.crypto_util import CryptoUtil
from tests.mcp_gateway.test_runtime import _add, _system  # 若路径不同则用现有 biz system fixture


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


async def test_create_datasource_encrypts_password_and_links_system(db) -> None:
    from app.modules.genbi.datasource.service import GenbiDatasourceService

    system = await _system(db, "oa_genbi", base_url="https://oa.example.com")
    svc = GenbiDatasourceService(AuthSchema(), db)
    row = await svc.create(
        system_id=system.id,
        name="OA 数仓",
        wren_type="POSTGRES",
        host="127.0.0.1",
        port=5432,
        username="bi",
        password="secret-pass",
        database="oa",
        db_schema="public",
    )
    assert row.id is not None
    assert row.system_id == system.id
    assert row.password_encrypted
    assert row.password_encrypted != "secret-pass"
    assert CryptoUtil.decrypt(row.password_encrypted) == "secret-pass"
    out = await svc.get(row.id)
    assert "password" not in (out.model_dump() if hasattr(out, "model_dump") else {})
    # schema 出参：无 password 明文字段
    from app.modules.genbi.datasource.schema import GenbiDatasourceOut
    dumped = GenbiDatasourceOut.model_validate(row).model_dump()
    assert "password" not in dumped
    assert "password_encrypted" not in dumped


async def test_reject_unknown_wren_type(db) -> None:
    from app.core.exceptions import CustomException
    from app.modules.genbi.datasource.service import GenbiDatasourceService

    system = await _system(db, "oa_genbi2", base_url="https://oa.example.com")
    svc = GenbiDatasourceService(AuthSchema(), db)
    with pytest.raises(CustomException) as ei:
        await svc.create(
            system_id=system.id,
            name="坏类型",
            wren_type="NOT_A_DB",
            host="127.0.0.1",
            port=5432,
            username="u",
            password="p",
            database="d",
        )
    assert "类型" in str(ei.value.msg) or "wren" in str(ei.value.msg).lower()
