"""Compile group×datasource ACL policies into SQL predicates (tiga port)."""

from __future__ import annotations


class CompileError(ValueError):
    pass


def sql_literal(value: str) -> str:
    return "'" + str(value).replace("'", "''") + "'"


def _ident(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def _col(model_ref: str, column_name: str) -> str:
    return f"{_ident(model_ref)}.{_ident(column_name)}"


def compile_row_predicate(
    *, model_ref: str, column_name: str, operator: str, values: list[str]
) -> str:
    vals = [v for v in values if v is not None and str(v) != ""]
    if not vals:
        return "1 = 0"
    col = _col(model_ref, column_name)
    if operator == "eq":
        return f"{col} = {sql_literal(vals[0])}"
    if operator == "ne":
        return f"{col} <> {sql_literal(vals[0])}"
    if operator == "gt":
        return f"{col} > {sql_literal(vals[0])}"
    if operator == "gte":
        return f"{col} >= {sql_literal(vals[0])}"
    if operator == "lt":
        return f"{col} < {sql_literal(vals[0])}"
    if operator == "lte":
        return f"{col} <= {sql_literal(vals[0])}"
    if operator == "in":
        return f"{col} IN ({', '.join(sql_literal(v) for v in vals)})"
    if operator == "not_in":
        return f"{col} NOT IN ({', '.join(sql_literal(v) for v in vals)})"
    if operator == "contains":
        parts = [f"{col} LIKE {sql_literal('%' + v + '%')}" for v in vals]
        return "(" + " OR ".join(parts) + ")" if len(parts) > 1 else parts[0]
    if operator == "not_contains":
        parts = [f"{col} NOT LIKE {sql_literal('%' + v + '%')}" for v in vals]
        return "(" + " AND ".join(parts) + ")" if len(parts) > 1 else parts[0]
    raise CompileError(f"unknown operator: {operator}")


def compile_mask_expr(column_name: str, template: str) -> str:
    col = _ident(column_name)
    if template == "all_stars":
        return "'****'"
    if template == "keep_first_1":
        return f"CONCAT(LEFT({col}, 1), '****')"
    if template == "keep_first_3":
        return f"CONCAT(LEFT({col}, 3), '****')"
    raise CompileError(f"unknown mask template: {template}")
