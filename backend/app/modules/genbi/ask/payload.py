"""tiga-aligned ask_bi tool payload (sql/columns/rows/summary/error/code)."""

from __future__ import annotations

from typing import Any


def _cell_value(raw: Any) -> Any:
    if isinstance(raw, (int, float)) and not isinstance(raw, bool):
        return float(raw) if not isinstance(raw, int) else raw
    if raw is None:
        return None
    if isinstance(raw, str):
        try:
            return float(raw.replace(",", ""))
        except ValueError:
            return raw
    return raw


def format_ask_tool_payload(
    *,
    sql: str | None = None,
    preview: dict[str, Any] | None = None,
    truncated: bool = False,
    error: str | None = None,
    code: str | None = None,
    summary: str | None = None,
) -> dict[str, Any]:
    columns: list[str] = []
    rows: list[list[Any]] = []
    built_summary = ""
    if preview:
        columns = list(preview.get("columns") or [])
        for row in preview.get("rows") or []:
            if isinstance(row, dict):
                rows.append([_cell_value(row.get(c)) for c in columns])
            elif isinstance(row, (list, tuple)):
                rows.append([_cell_value(v) for v in row])
        if columns and rows:
            header = "| " + " | ".join(columns) + " |"
            sep = "| " + " | ".join(["---"] * len(columns)) + " |"
            body = "\n".join(
                "| " + " | ".join(str(v) if v is not None else "" for v in r) + " |" for r in rows
            )
            built_summary = f"{header}\n{sep}\n{body}"
    return {
        "sql": sql,
        "summary": (summary or built_summary) or None,
        "columns": columns,
        "rows": rows,
        "truncated": truncated,
        "error": error,
        "code": code,
    }
