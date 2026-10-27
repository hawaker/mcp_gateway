"""Apply shared group×datasource ACL to Wren SQL (no per-user members)."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.modules.genbi.acl.model import (
    GenbiGroupDatasourceAclColumnModel,
    GenbiGroupDatasourceAclRowModel,
    GenbiGroupDatasourceModel,
)
from app.modules.genbi.project.mdl_builder import _column_name
from app.modules.genbi.project.model import GenbiModelModel, GenbiProjectModel, GenbiViewModel

from .acl_compile import CompileError, compile_mask_expr, compile_row_predicate
from .acl_gateway import AclRewriteError, ColumnDenied, rewrite_sql


def format_column_denied_error(exc: ColumnDenied) -> str:
    column = str(exc)
    prefix = "无权限访问字段："
    if column.startswith(prefix):
        column = column[len(prefix) :].split("（", 1)[0]
    return f"无权限访问字段：{column}"


async def compile_group_datasource_policies(
    db: AsyncSession,
    *,
    project: GenbiProjectModel,
    link_id: int,
) -> dict:
    models_result = await db.execute(
        select(GenbiModelModel)
        .where(GenbiModelModel.project_id == project.id)
        .options(selectinload(GenbiModelModel.columns))
    )
    models = {m.id: m for m in models_result.scalars().all()}
    columns = {c.id: c for m in models.values() for c in (m.columns or [])}

    row: dict[str, list[str]] = {}
    row_result = await db.execute(
        select(GenbiGroupDatasourceAclRowModel).where(
            GenbiGroupDatasourceAclRowModel.group_datasource_id == link_id
        )
    )
    for rp in row_result.scalars().all():
        model = models.get(rp.model_id)
        col = columns.get(rp.column_id)
        if model is None or col is None:
            raise CompileError("row policy references missing model or column")
        model_ref = model.reference_name
        col_name = _column_name(col)
        pred = compile_row_predicate(
            model_ref=model_ref,
            column_name=col_name,
            operator=rp.operator,
            values=[str(v) for v in (rp.values or [])],
        )
        row.setdefault(model_ref, []).append(pred)

    column: dict[tuple[str, str], dict] = {}
    col_result = await db.execute(
        select(GenbiGroupDatasourceAclColumnModel).where(
            GenbiGroupDatasourceAclColumnModel.group_datasource_id == link_id
        )
    )
    for cp in col_result.scalars().all():
        model = models.get(cp.model_id)
        col = columns.get(cp.column_id)
        if model is None or col is None:
            raise CompileError("column policy references missing model or column")
        mdl = _column_name(col)
        mask_expr = None
        if cp.action == "mask":
            if not cp.mask_template:
                raise CompileError("mask policy missing template")
            mask_expr = compile_mask_expr(mdl, cp.mask_template)
        elif cp.action != "deny":
            raise CompileError(f"unknown column action: {cp.action}")
        column[(model.reference_name, mdl)] = {
            "action": cp.action,
            "mask_expr": mask_expr,
        }
    return {"row": row, "column": column}


async def apply_ask_acl(
    db: AsyncSession,
    *,
    project: GenbiProjectModel,
    group_id: int,
    datasource_id: int,
    sql: str,
) -> str:
    """Load shared ACL for group×datasource; empty rules → no rewrite."""
    link = (
        await db.execute(
            select(GenbiGroupDatasourceModel).where(
                GenbiGroupDatasourceModel.group_id == group_id,
                GenbiGroupDatasourceModel.datasource_id == datasource_id,
            )
        )
    ).scalar_one_or_none()
    if link is None:
        return sql

    policies = await compile_group_datasource_policies(db, project=project, link_id=link.id)
    if not policies["row"] and not policies["column"]:
        return sql

    models_result = await db.execute(
        select(GenbiModelModel)
        .where(GenbiModelModel.project_id == project.id)
        .options(selectinload(GenbiModelModel.columns))
    )
    schema = {
        m.reference_name: [_column_name(c) for c in (m.columns or [])]
        for m in models_result.scalars().all()
    }
    views = (
        await db.execute(select(GenbiViewModel).where(GenbiViewModel.project_id == project.id))
    ).scalars().all()
    view_sql = {v.name: v.statement for v in views}
    return rewrite_sql(sql, policies, schema=schema, view_sql=view_sql or None)


__all__ = [
    "AclRewriteError",
    "ColumnDenied",
    "CompileError",
    "apply_ask_acl",
    "format_column_denied_error",
]
