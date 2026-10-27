"""SQL preview executor (ibis / Wren engine)."""

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
        manifest: dict[str, Any] | None = None,
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
        self.last_manifest: dict[str, Any] | None = None

    async def execute_preview(
        self,
        *,
        datasource: GenbiDatasourceModel,
        sql: str,
        limit: int = 50,
        manifest: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        self.execute_calls += 1
        self.last_sql = sql
        self.last_manifest = manifest
        _ = datasource, limit
        return {"columns": list(self.columns), "rows": list(self.rows)}


class SettingsSqlExecutor:
    """Production plug-in: ibis HTTP preview (``run_mdl_sql_preview``)."""

    async def execute_preview(
        self,
        *,
        datasource: GenbiDatasourceModel,
        sql: str,
        limit: int = 50,
        manifest: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        from app.config.setting import settings
        from app.modules.genbi.ibis.preview import run_mdl_sql_preview

        if not (settings.GENBI_IBIS_ENDPOINT or "").strip():
            raise RuntimeError("GENBI_IBIS_ENDPOINT is not configured")
        if not manifest or not manifest.get("models"):
            raise RuntimeError("MDL manifest is required for ibis SQL preview")
        return await run_mdl_sql_preview(
            datasource,
            sql,
            manifest,
            limit=limit,
        )


def get_sql_executor() -> SqlExecutor:
    return SettingsSqlExecutor()
