"""Settings* paths: ibis HTTP selected (not stub); Wren HTTP ask/deploy when configured."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock

import httpx
import pytest

from app.modules.genbi.ask.executor import SettingsSqlExecutor, StubSqlExecutor, get_sql_executor
from app.modules.genbi.ask.wren_ask import SettingsWrenAskClient, StubWrenAskClient, get_wren_ask_client
from app.modules.genbi.datasource.model import GenbiDatasourceModel
from app.modules.genbi.project.wren_client import SettingsWrenClient, StubWrenClient, get_wren_client


def _datasource(**overrides: Any) -> GenbiDatasourceModel:
    row = GenbiDatasourceModel()
    row.id = 1
    row.system_id = 1
    row.name = "ds"
    row.wren_type = "POSTGRES"
    row.host = "127.0.0.1"
    row.port = 5432
    row.username = "bi"
    row.password_encrypted = None
    row.database = "oa"
    row.db_schema = "public"
    row.url = None
    row.config = {}
    row.enabled = True
    for key, value in overrides.items():
        setattr(row, key, value)
    return row


@pytest.mark.asyncio
async def test_get_sql_executor_is_settings_not_stub() -> None:
    assert isinstance(get_sql_executor(), SettingsSqlExecutor)
    assert not isinstance(get_sql_executor(), StubSqlExecutor)


@pytest.mark.asyncio
async def test_get_wren_clients_are_settings_not_stub() -> None:
    assert isinstance(get_wren_client(), SettingsWrenClient)
    assert isinstance(get_wren_ask_client(), SettingsWrenAskClient)
    assert not isinstance(get_wren_client(), StubWrenClient)
    assert not isinstance(get_wren_ask_client(), StubWrenAskClient)


@pytest.mark.asyncio
async def test_settings_sql_executor_posts_ibis_query(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.config.setting import settings

    monkeypatch.setattr(settings, "GENBI_IBIS_ENDPOINT", "http://ibis.test:18000")

    captured: dict[str, Any] = {}

    class FakeResponse:
        status_code = 200
        content = b'{"columns":["id"],"data":[[1]]}'

        def json(self) -> dict[str, Any]:
            return {"columns": ["id"], "data": [[1]]}

    class FakeClient:
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            pass

        async def post(self, url: str, json: dict[str, Any] | None = None) -> FakeResponse:
            captured["url"] = url
            captured["body"] = json
            return FakeResponse()

        async def aclose(self) -> None:
            return None

    monkeypatch.setattr(httpx, "AsyncClient", FakeClient)

    manifest = {
        "catalog": "wren",
        "schema": "public",
        "models": [{"name": "users", "columns": [{"name": "id", "type": "integer"}]}],
    }
    result = await SettingsSqlExecutor().execute_preview(
        datasource=_datasource(),
        sql="SELECT id FROM users LIMIT 10",
        limit=50,
        manifest=manifest,
    )
    assert "postgres" in captured["url"]
    assert "/v3/connector/" in captured["url"]
    assert "manifestStr" in (captured.get("body") or {})
    assert "connectionInfo" in (captured.get("body") or {})
    assert result["columns"] == ["id"]
    assert result["rows"] == [{"id": 1}]


@pytest.mark.asyncio
async def test_settings_wren_ask_uses_http_when_endpoint_set(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.config.setting import settings
    import app.modules.genbi.ai.http_client as http_mod

    monkeypatch.setattr(settings, "GENBI_WREN_AI_ENDPOINT", "http://wren-ai.test:5555")

    async def fake_http_ask(**kwargs: Any) -> dict[str, Any]:
        assert kwargs["question"] == "有多少用户"
        assert kwargs["mdl_hash"] == "abc"
        return {
            "status": "finished",
            "response": [{"sql": "SELECT COUNT(*) FROM users"}],
        }

    monkeypatch.setattr(http_mod, "http_ask", AsyncMock(side_effect=fake_http_ask))

    result = await SettingsWrenAskClient().ask(
        question="有多少用户",
        mdl_hash="abc",
        project_id=7,
    )
    assert result.status == "finished"
    assert result.sql == "SELECT COUNT(*) FROM users"


@pytest.mark.asyncio
async def test_settings_wren_deploy_uses_http_when_endpoint_set(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.config.setting import settings
    import app.modules.genbi.ai.http_client as http_mod

    monkeypatch.setattr(settings, "GENBI_WREN_AI_ENDPOINT", "http://wren-ai.test:5555")

    called: dict[str, Any] = {}

    async def fake_prepare(**kwargs: Any) -> dict[str, Any]:
        called.update(kwargs)
        return {"status": "finished"}

    monkeypatch.setattr(http_mod, "http_prepare_semantics", AsyncMock(side_effect=fake_prepare))

    result = await SettingsWrenClient().deploy_semantics(
        project_id=3,
        mdl_hash="hash1",
        manifest={"models": [{"name": "users"}]},
    )
    assert result.status == "finished"
    assert result.mdl_hash == "hash1"
    assert called.get("mdl_hash") == "hash1"
