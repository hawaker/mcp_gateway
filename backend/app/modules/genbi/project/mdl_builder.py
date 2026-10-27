"""Build a Wren-compatible MDL manifest (minimal subset for deploy gate)."""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any

from app.modules.genbi.datasource.model import GenbiDatasourceModel

from .model import (
    GenbiModelColumnModel,
    GenbiModelModel,
    GenbiProjectModel,
    GenbiRelationshipModel,
)

WREN_MDL_CATALOG = "wren"
WREN_MDL_SCHEMA = "public"


def _slug_ref(name: str) -> str:
    ref = re.sub(r"[^\w]", "_", (name or "").strip())
    return ref or "field"


def _column_name(column: GenbiModelColumnModel) -> str:
    if column.is_calculated:
        return _slug_ref(column.display_name or column.source_column_name or "field")
    src = (column.source_column_name or "").strip()
    return src if src else _slug_ref(column.display_name or "field")


def _table_reference(model: GenbiModelModel, datasource: GenbiDatasourceModel | None) -> dict[str, str] | None:
    props = model.properties if isinstance(model.properties, dict) else {}
    raw_table = props.get("table") or model.source_table_name
    if not raw_table:
        return None
    schema = (props.get("schema") or (datasource.db_schema if datasource else None) or WREN_MDL_SCHEMA).strip()
    name = str(raw_table).strip()
    if schema and name.startswith(f"{schema}."):
        name = name[len(schema) + 1 :]
    elif "." in name:
        head, tail = name.split(".", 1)
        if head and tail:
            schema, name = head, tail
    return {"schema": schema or WREN_MDL_SCHEMA, "table": name}


def build_mdl_manifest(
    *,
    project: GenbiProjectModel,
    datasource: GenbiDatasourceModel | None,
    models: list[GenbiModelModel],
    relationships: list[GenbiRelationshipModel] | None = None,
) -> dict[str, Any]:
    """Minimal Wren MDL: catalog/schema/models(+columns)/relationships."""
    models_sorted = sorted(models, key=lambda m: m.id or 0)
    model_by_id = {m.id: m for m in models_sorted}
    wren_type = (datasource.wren_type if datasource else "POSTGRES") or "POSTGRES"

    manifest: dict[str, Any] = {
        "dataSource": wren_type.lower() if wren_type != "POSTGRES" else "postgres",
        "catalog": WREN_MDL_CATALOG,
        "schema": WREN_MDL_SCHEMA,
        "models": [],
        "relationships": [],
    }

    for model in models_sorted:
        props = model.properties if isinstance(model.properties, dict) else {}
        table_ref = _table_reference(model, datasource)
        entry: dict[str, Any] = {
            "name": model.reference_name,
            "columns": [],
            "tableReference": table_ref,
            "refSql": None if table_ref else model.ref_sql,
            "cached": bool(model.cached),
            "refreshTime": model.refresh_time,
            "properties": {
                "displayName": model.display_name,
                "description": props.get("description"),
                "sourceKind": props.get("sourceKind"),
            },
            "primaryKey": "",
        }
        for column in sorted(model.columns or [], key=lambda c: c.id or 0):
            col_props = column.properties if isinstance(column.properties, dict) else {}
            col_props = {**col_props, "displayName": column.display_name}
            col_entry: dict[str, Any] = {
                "name": _column_name(column),
                "type": column.column_type or "varchar",
                "isCalculated": bool(column.is_calculated),
                "notNull": False,
                "properties": col_props,
            }
            if column.is_calculated and column.expression:
                col_entry["expression"] = column.expression
            if col_props.get("isPk") and not column.is_calculated:
                entry["primaryKey"] = col_entry["name"]
            entry["columns"].append(col_entry)
        manifest["models"].append(entry)

    for rel in sorted(relationships or [], key=lambda r: r.id or 0):
        from_model = model_by_id.get(rel.from_model_id)
        to_model = model_by_id.get(rel.to_model_id)
        if not from_model or not to_model:
            continue
        rel_props = rel.properties if isinstance(rel.properties, dict) else {}
        from_ref = from_model.reference_name
        to_ref = to_model.reference_name
        name = rel_props.get("name") or f"{from_ref}_{to_ref}"
        condition = rel.condition or f'"{from_ref}"."id" = "{to_ref}"."id"'
        manifest["relationships"].append(
            {
                "name": name,
                "models": [from_ref, to_ref],
                "joinType": rel.join_type or "MANY_TO_ONE",
                "condition": condition,
                "properties": rel_props,
            }
        )

    return manifest


def create_mdl_hash(manifest: dict[str, Any], project_id: int | str) -> str:
    manifest_str = json.dumps(manifest, sort_keys=True, separators=(",", ":"))
    content = f"{project_id} {manifest_str}"
    return hashlib.sha1(content.encode("utf-8")).hexdigest()
