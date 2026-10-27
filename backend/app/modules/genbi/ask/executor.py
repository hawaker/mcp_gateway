"""SQL preview executor (mockable; ibis later)."""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from app.modules.genbi.datasource.model import GenbiDatasourceModel


@runtime_checkable
class SqlExecutor(Protocol):
    async def execute_preview(
        self,
        *,
        datasource: GenbiDatasourceModel,
        sql: str,
        limit: int = 50,
    ) -> dict[str, Any]:
        """Return ``{"columns": [...], "rows": [...]}``."""
        ...


class StubSqlExecutor:
    """In-process stub for tests."""

    def __init__(
        self,
        *,
        columns: list[str] | None = None,
        rows: list[Any] | None = None,
    ) -> None:
        self.columns = columns or ["value"]
        self.rows = rows if rows is not None else [{"value": 1}]
        self.execute_calls = 0
        self.last_sql: str | None = None

    async def execute_preview(
        self,
        *,
        datasource: GenbiDatasourceModel,
        sql: str,
        limit: int = 50,
    ) -> dict[str, Any]:
        self.execute_calls += 1
        self.last_sql = sql
        _ = datasource, limit
        return {"columns": list(self.columns), "rows": list(self.rows)}


class SettingsSqlExecutor:
    """Production plug-in point for ibis / Wren engine preview."""

    async def execute_preview(
        self,
        *,
        datasource: GenbiDatasourceModel,
        sql: str,
        limit: int = 50,
    ) -> dict[str, Any]:
        from app.config.setting import settings

        _ = settings.GENBI_IBIS_ENDPOINT, datasource, sql, limit
        raise RuntimeError("SQL 预览执行器尚未配置")


def get_sql_executor() -> SqlExecutor:
    return SettingsSqlExecutor()
