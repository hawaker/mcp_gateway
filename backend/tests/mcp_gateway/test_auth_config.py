"""一个业务系统同时只有一条启用中的鉴权配置。Basic 密码只写不读。"""

import pytest
from fastapi.testclient import TestClient

from app.core.base_schema import AuthSchema
from app.modules.mcp_gateway.auth.model import AuthConfigModel
from app.modules.mcp_gateway.auth.schema import AuthConfigCreateSchema, AuthConfigOutSchema, AuthConfigUpdateSchema
from app.modules.mcp_gateway.auth.service import AuthConfigService
from app.modules.mcp_gateway.system.model import BizSystemModel
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


async def _system(db, code: str = "oa-auth") -> BizSystemModel:
    row = BizSystemModel(
        name=code,
        code=code,
        base_url="https://oa.example.com",
        enabled=True,
        params={},
        uid_field="user_id",
        attr_fields=[],
    )
    db.add(row)
    await db.flush()
    return row


async def test_basic_password_is_write_only_and_encrypted(db) -> None:
    system = await _system(db, "oa-basic-secret")
    service = AuthConfigService(_auth(), db)
    created = await service.create(
        AuthConfigCreateSchema(
            system_id=system.id,
            method="basic",
            enabled=True,
            url="https://oa.example.com/login",
            rule={},
            http_method="POST",
            username="svc",
            password="super-secret-password",
        )
    )
    assert isinstance(created, AuthConfigOutSchema)
    assert "password" not in created.model_dump()
    assert created.username == "svc"

    detail = await service.detail(created.id)
    assert "password" not in detail.model_dump()

    row = await db.get(AuthConfigModel, created.id)
    assert row is not None
    assert row.password_encrypted
    assert row.password_encrypted != "super-secret-password"
    assert CryptoUtil.decrypt(row.password_encrypted) == "super-secret-password"
    assert "super-secret-password" not in detail.model_dump_json()

    updated = await service.update(created.id, AuthConfigUpdateSchema(username="svc2"))
    assert "password" not in updated.model_dump()
    await db.refresh(row)
    assert CryptoUtil.decrypt(row.password_encrypted) == "super-secret-password"


def test_only_one_enabled_auth_config_per_system(test_client: TestClient, auth_headers: dict[str, str]) -> None:
    system = test_client.post(
        "/mcp-gateway/biz-system/create",
        json={
            "name": "OA",
            "code": "oa-auth",
            "base_url": "https://oa.example.com",
            "enabled": True,
            "params": {},
            "uid_field": "user_id",
            "attr_fields": [],
        },
        headers=auth_headers,
    )
    assert system.status_code == 200, system.text
    system_id = system.json()["data"]["id"]

    def create(url: str) -> dict:
        created = test_client.post(
            "/mcp-gateway/biz-auth/create",
            json={
                "system_id": system_id,
                "method": "fixed",
                "enabled": True,
                "url": url,
                "rule": {},
            },
            headers=auth_headers,
        )
        assert created.status_code == 200, created.text
        return created.json()["data"]

    create("https://oa.example.com/login")
    second = create("https://oa.example.com/token")
    listed = test_client.get(
        "/mcp-gateway/biz-auth/list",
        params={"page_no": 1, "page_size": 20, "system_id": system_id},
        headers=auth_headers,
    )
    assert listed.status_code == 200, listed.text
    items = listed.json()["data"]["items"]
    enabled = [item for item in items if item["enabled"]]
    assert len(items) == 2
    assert len(enabled) == 1
    assert enabled[0]["id"] == second["id"]
    for item in items:
        assert "password" not in item
        assert "password_encrypted" not in item
