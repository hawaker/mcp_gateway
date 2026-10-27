"""GenBI 数据源测连：mock 底层探测，合法 POSTGRES 成功、错误密码失败。"""

from __future__ import annotations

import pytest

from app.core.base_schema import AuthSchema
from app.core.exceptions import CustomException
from app.utils.crypto_util import CryptoUtil
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


_GOOD_POSTGRES = {
    "wren_type": "POSTGRES",
    "host": "127.0.0.1",
    "port": 5432,
    "username": "bi",
    "password": "secret-pass",
    "database": "oa",
}


async def test_probe_postgres_valid_params_succeed(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.modules.genbi.datasource import probe as probe_mod

    calls: list[str] = []

    async def fake_probe_url(url: str) -> None:
        calls.append(url)

    monkeypatch.setattr(probe_mod, "_probe_url", fake_probe_url)

    await probe_mod.probe_connection(dict(_GOOD_POSTGRES))

    assert len(calls) == 1
    assert calls[0].startswith("postgresql+asyncpg://")
    assert "bi" in calls[0]
    assert "127.0.0.1:5432" in calls[0]
    assert "/oa" in calls[0]


async def test_probe_postgres_bad_password_raises_custom_exception(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.modules.genbi.datasource import probe as probe_mod

    async def fake_probe_url(url: str) -> None:
        raise RuntimeError("password authentication failed for user \"bi\"")

    monkeypatch.setattr(probe_mod, "_probe_url", fake_probe_url)

    with pytest.raises(CustomException) as ei:
        await probe_mod.probe_connection({**_GOOD_POSTGRES, "password": "wrong-pass"})

    assert "连接失败" in ei.value.msg or "失败" in ei.value.msg


async def test_service_test_by_id_decrypts_and_probes(
    db, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.modules.genbi.datasource import service as service_mod
    from app.modules.genbi.datasource.service import GenbiDatasourceService

    seen: list[dict] = []

    async def fake_probe(params: dict) -> None:
        seen.append(dict(params))

    monkeypatch.setattr(service_mod, "probe_connection", fake_probe)

    system = await _system(db, "oa_probe", base_url="https://oa.example.com")
    svc = GenbiDatasourceService(AuthSchema(), db)
    row = await svc.create(
        system_id=system.id,
        name="测连源",
        wren_type="POSTGRES",
        host="db.internal",
        port=5432,
        username="bi",
        password="stored-secret",
        database="oa",
    )
    assert row.password_encrypted != "stored-secret"
    assert CryptoUtil.decrypt(row.password_encrypted) == "stored-secret"

    await svc.test_by_id(row.id)

    assert len(seen) == 1
    assert seen[0]["wren_type"] == "POSTGRES"
    assert seen[0]["host"] == "db.internal"
    assert seen[0]["password"] == "stored-secret"
