"""Execute Wren semantic SQL through ibis-server (MDL + connectionInfo)."""

from __future__ import annotations

import json
import re
from typing import Any

import httpx

from app.config.setting import settings
from app.modules.genbi.datasource.model import GenbiDatasourceModel
from app.modules.genbi.ai.engine_context import build_engine_context

from .connection import ibis_connector_slug


def _strip_limit(sql: str) -> str:
    return re.sub(r"\s+limit\s+\d+\s*$", "", sql.strip().rstrip(";"), flags=re.IGNORECASE)


def _ibis_rows_to_preview(payload: Any) -> dict[str, Any]:
    if isinstance(payload, list):
        if payload and isinstance(payload[0], dict):
            cols = list(payload[0].keys())
            return {"columns": cols, "rows": payload, "row_count": len(payload)}
        return {"columns": [], "rows": [], "row_count": 0}

    if not isinstance(payload, dict):
        return {"columns": [], "rows": [], "row_count": 0}

    raw_cols = payload.get("columns") or []
    if raw_cols and isinstance(raw_cols[0], dict):
        columns = [str(c.get("name") or c) for c in raw_cols]
    else:
        columns = [str(c) for c in raw_cols]

    data = payload.get("data") or payload.get("rows") or []
    rows: list[Any] = []
    for item in data:
        if isinstance(item, dict):
            rows.append(item)
        elif isinstance(item, (list, tuple)) and columns:
            rows.append(dict(zip(columns, item, strict=False)))
    return {"columns": columns, "rows": rows, "row_count": len(rows)}


async def run_mdl_sql_preview(
    source: GenbiDatasourceModel,
    sql: str,
    manifest: dict[str, Any],
    *,
    limit: int = 100,
    client: httpx.AsyncClient | None = None,
) -> dict[str, Any]:
    """POST semantic SQL to ibis ``/v3/connector/{slug}/query``."""
    wren_type = (source.wren_type or "").strip().upper()
    slug = ibis_connector_slug(wren_type or "")
    if not slug:
        raise ValueError(f"GenBI preview unsupported for data source type: {source.wren_type}")

    base = (settings.GENBI_IBIS_ENDPOINT or "").rstrip("/")
    if not base:
        raise RuntimeError("GENBI_IBIS_ENDPOINT is not configured")

    ctx = build_engine_context(manifest, source)
    connector = ctx.ibis_source or slug
    url = f"{base}/v3/connector/{connector}/query?limit={limit}"
    body = {
        "sql": _strip_limit(sql),
        "manifestStr": ctx.ibis_manifest_b64,
        "connectionInfo": ctx.connection_info,
    }

    owns_client = client is None
    http = client or httpx.AsyncClient(timeout=120.0)
    try:
        resp = await http.post(url, json=body)
        if resp.status_code >= 400:
            text = resp.text
            try:
                parsed = resp.json()
                if isinstance(parsed, dict):
                    text = json.dumps(parsed, ensure_ascii=False)
            except Exception:  # noqa: BLE001
                pass
            raise RuntimeError(text)
        if not resp.content:
            return {"columns": [], "rows": [], "row_count": 0}
        return _ibis_rows_to_preview(resp.json())
    finally:
        if owns_client:
            await http.aclose()
