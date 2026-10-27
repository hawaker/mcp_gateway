"""MCP catalog + execute entry for `{code}_ask_bi`."""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.base_schema import AuthSchema
from app.modules.genbi.ask.service import AskService
from app.modules.genbi.acl.crud import GenbiGroupDatasourceCRUD
from app.modules.genbi.datasource.crud import GenbiDatasourceCRUD
from app.modules.mcp_gateway.system.crud import BizSystemCRUD

ASK_BI_DESCRIPTION = "自然语言问数：根据问题生成并执行 SQL，返回表格结果。"

ASK_BI_INPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "question": {
            "type": "string",
            "description": "自然语言数据问题",
        }
    },
    "required": ["question"],
}


def default_ask_bi_name(system_code: str) -> str:
    code = (system_code or "").strip() or "system"
    return f"{code}_ask_bi"


async def list_enabled_ask_bi_tools(
    auth: AuthSchema,
    db: AsyncSession,
    group_id: int,
) -> list[dict[str, Any]]:
    """Enabled group datasources as published MCP tools (source=genbi)."""
    links = await GenbiGroupDatasourceCRUD(auth, db).get_list(
        search={"group_id": group_id, "enabled": True},
        order_by=[{"id": "asc"}],
    )
    out: list[dict[str, Any]] = []
    for link in links:
        ds = await GenbiDatasourceCRUD(auth, db).get(id=link.datasource_id)
        if ds is None or not ds.enabled:
            continue
        out.append(
            {
                "name": link.external_name,
                "description": ASK_BI_DESCRIPTION,
                "input_schema": dict(ASK_BI_INPUT_SCHEMA),
                "source": "genbi",
                "source_id": link.id,
                "datasource_id": link.datasource_id,
                "system_id": ds.system_id,
            }
        )
    return out


async def resolve_ask_bi_system_id(auth: AuthSchema, db: AsyncSession, datasource_id: int) -> int | None:
    ds = await GenbiDatasourceCRUD(auth, db).get(id=datasource_id)
    return ds.system_id if ds is not None else None


async def execute_ask_bi(
    auth: AuthSchema,
    db: AsyncSession,
    *,
    group_id: int,
    datasource_id: int,
    arguments: dict[str, Any],
) -> tuple[str, bool, int | None]:
    """Run ask; return (text, is_error, http_status for call_log).

    Response text may include sql/rows for the MCP client; call_log stores
    only metadata (no SQL / result body).
    """
    question = arguments.get("question")
    if not isinstance(question, str):
        question = ""
    payload = await AskService(auth, db).run(
        group_id=group_id,
        datasource_id=datasource_id,
        question=question,
    )
    is_error = bool(payload.get("error") or payload.get("code") in {
        "DEPLOY_REQUIRED",
        "ACL_COLUMN_DENIED",
        "ACL_REWRITE_FAILED",
        "ASK_FAILED",
        "QUESTION_REQUIRED",
        "NO_DATA_SOURCE",
        "PROJECT_NOT_FOUND",
        "EXECUTE_FAILED",
    })
    text = json.dumps(payload, ensure_ascii=False, default=str)
    http_status = None if is_error else 200
    return text, is_error, http_status


async def suggest_external_name(auth: AuthSchema, db: AsyncSession, datasource_id: int) -> str:
    ds = await GenbiDatasourceCRUD(auth, db).get(id=datasource_id)
    if ds is None:
        return "ask_bi"
    system = await BizSystemCRUD(auth, db).get(id=ds.system_id)
    if system is not None and system.code:
        return default_ask_bi_name(system.code)
    return default_ask_bi_name(ds.name)
