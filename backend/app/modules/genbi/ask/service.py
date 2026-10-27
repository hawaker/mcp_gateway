"""Ask pipeline: deploy gate → Wren NL→SQL → ACL → execute → payload."""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.base_schema import AuthSchema
from app.modules.genbi.datasource.crud import GenbiDatasourceCRUD
from app.modules.genbi.project.mdl_builder import build_mdl_manifest
from app.modules.genbi.project.model import (
    GenbiDeployLogModel,
    GenbiModelModel,
    GenbiProjectModel,
    GenbiRelationshipModel,
)

from .acl import (
    AclRewriteError,
    ColumnDenied,
    CompileError,
    apply_ask_acl,
    format_column_denied_error,
)
from .executor import SqlExecutor, get_sql_executor
from .payload import format_ask_tool_payload
from .wren_ask import WrenAskClient, get_wren_ask_client

logger = logging.getLogger(__name__)

_PREVIEW_LIMIT = 50


class AskService:
    """Shared ask entry for MCP `{code}_ask_bi` (group×datasource ACL)."""

    def __init__(
        self,
        auth: AuthSchema,
        db: AsyncSession,
        *,
        wren_ask: WrenAskClient | None = None,
        sql_executor: SqlExecutor | None = None,
    ) -> None:
        self.auth = auth
        self.db = db
        self.wren_ask = wren_ask
        self.sql_executor = sql_executor

    async def run(
        self,
        *,
        group_id: int,
        datasource_id: int,
        question: str,
    ) -> dict[str, Any]:
        q = (question or "").strip()
        if not q:
            return format_ask_tool_payload(error="问题不能为空", code="QUESTION_REQUIRED")

        ds = await GenbiDatasourceCRUD(self.auth, self.db).get(id=datasource_id)
        if ds is None or not ds.enabled:
            return format_ask_tool_payload(error="数据源不可用", code="NO_DATA_SOURCE")

        project = (
            await self.db.execute(
                select(GenbiProjectModel).where(GenbiProjectModel.datasource_id == datasource_id)
            )
        ).scalar_one_or_none()
        if project is None:
            return format_ask_tool_payload(error="项目不存在", code="PROJECT_NOT_FOUND")

        deploy = await self._latest_successful_deploy(project.id)
        if deploy is None or not deploy.mdl_hash:
            return format_ask_tool_payload(
                error="请先完成建模部署后再问数",
                code="DEPLOY_REQUIRED",
            )

        wren = self.wren_ask or get_wren_ask_client()
        try:
            result = await wren.ask(
                question=q,
                mdl_hash=deploy.mdl_hash,
                project_id=project.id,
            )
        except Exception:
            logger.exception("wren ask failed project=%s", project.id)
            return format_ask_tool_payload(error="问数失败", code="ASK_FAILED")

        if result.status != "finished" or not result.sql:
            return format_ask_tool_payload(
                error=result.error_message or "问数失败",
                code=result.error_code or "ASK_FAILED",
            )

        sql = result.sql
        try:
            sql = await apply_ask_acl(
                self.db,
                project=project,
                group_id=group_id,
                datasource_id=datasource_id,
                sql=sql,
            )
        except ColumnDenied as exc:
            return format_ask_tool_payload(
                error=format_column_denied_error(exc),
                code="ACL_COLUMN_DENIED",
            )
        except (AclRewriteError, CompileError):
            return format_ask_tool_payload(
                error="行列权限改写失败",
                code="ACL_REWRITE_FAILED",
            )

        executor = self.sql_executor or get_sql_executor()
        preview: dict[str, Any] | None = None
        truncated = False
        try:
            manifest = await self._load_manifest(project, ds)
            preview = await executor.execute_preview(
                datasource=ds,
                sql=sql,
                limit=_PREVIEW_LIMIT,
                manifest=manifest,
            )
            truncated = len(preview.get("rows") or []) >= _PREVIEW_LIMIT
        except Exception:
            logger.exception("ask preview failed project=%s", project.id)
            return format_ask_tool_payload(
                sql=sql,
                error="查询执行失败",
                code="EXECUTE_FAILED",
            )

        return format_ask_tool_payload(sql=sql, preview=preview, truncated=truncated)

    async def _load_manifest(
        self,
        project: GenbiProjectModel,
        datasource: Any,
    ) -> dict[str, Any]:
        from sqlalchemy.orm import selectinload

        models = list(
            (
                await self.db.execute(
                    select(GenbiModelModel)
                    .where(
                        GenbiModelModel.project_id == project.id,
                        GenbiModelModel.is_deleted == False,  # noqa: E712
                    )
                    .options(selectinload(GenbiModelModel.columns))
                )
            )
            .scalars()
            .all()
        )
        rels = list(
            (
                await self.db.execute(
                    select(GenbiRelationshipModel).where(
                        GenbiRelationshipModel.project_id == project.id,
                        GenbiRelationshipModel.is_deleted == False,  # noqa: E712
                    )
                )
            )
            .scalars()
            .all()
        )
        return build_mdl_manifest(
            project=project,
            datasource=datasource,
            models=models,
            relationships=rels,
        )

    async def _latest_successful_deploy(self, project_id: int) -> GenbiDeployLogModel | None:
        rows = (
            await self.db.execute(
                select(GenbiDeployLogModel)
                .where(
                    GenbiDeployLogModel.project_id == project_id,
                    GenbiDeployLogModel.status == "success",
                )
                .order_by(GenbiDeployLogModel.id.desc())
                .limit(1)
            )
        ).scalars().all()
        return rows[0] if rows else None


async def run_ask(
    db: AsyncSession,
    *,
    group_id: int,
    datasource_id: int,
    question: str,
    wren_ask: WrenAskClient | None = None,
    sql_executor: SqlExecutor | None = None,
) -> dict[str, Any]:
    return await AskService(
        AuthSchema(),
        db,
        wren_ask=wren_ask,
        sql_executor=sql_executor,
    ).run(group_id=group_id, datasource_id=datasource_id, question=question)


# Re-export for monkeypatch targets used by tests.
__all__ = [
    "AskService",
    "run_ask",
    "get_wren_ask_client",
    "get_sql_executor",
]
