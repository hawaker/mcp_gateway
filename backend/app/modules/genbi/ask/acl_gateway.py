"""问数 SQL 行/列权限改写（对标 chatBI semantic_gateway，谓词已是最终 SQL 字面量）。"""
from __future__ import annotations

import sqlglot
from sqlglot import exp


class ColumnDenied(ValueError):
    """查询投影命中 deny 列。"""


class AclRewriteError(ValueError):
    """解析失败、非只读、或改写不确定时 fail-closed。"""


# 写操作/DDL 节点黑名单：exp.DML 覆盖 Insert/Update/Delete/Merge/Copy（含数据修改 CTE）；
# Create/Alter/Drop/Truncate/Grant 在本 sqlglot 版本不挂在 DML/DDL 基类下，逐个列出。
# exp.Into：SELECT ... INTO t 解析为 Select 根节点但重序列化为 CREATE TABLE AS，是写操作。
_FORBIDDEN_NODES = tuple(c for c in (
    exp.DML, exp.Create, exp.Alter, exp.Drop, exp.Into,
    getattr(exp, "TruncateTable", None), getattr(exp, "Grant", None),
    getattr(exp, "SetItem", None),
) if c is not None)


def _reject_write_nodes(tree: exp.Expression) -> None:
    for node in tree.walk():
        if isinstance(node, _FORBIDDEN_NODES):
            raise AclRewriteError(
                f"只允许只读查询：检测到 {type(node).__name__} 节点，按 fail-closed 拒绝"
            )


def rewrite_sql(
    sql: str,
    policies: dict,
    schema: dict[str, list[str]] | None = None,
    view_sql: dict[str, str] | None = None,
) -> str:
    """对生成的 SQL 做行/列权限改写。fail closed：不确定就抛异常。

    view_sql 将 Wren 视图名替换为底层 SELECT 子查询，再套行/列策略。
    """
    try:
        tree = sqlglot.parse_one(sql)
    except Exception as e:
        raise AclRewriteError(f"SQL 解析失败，按 fail-closed 拒绝：{e}") from e
    if not isinstance(tree, (exp.Select, exp.Union, exp.Subquery)):
        raise AclRewriteError(f"只允许只读查询（SELECT），实际为 {type(tree).__name__}")
    # 写操作可藏在数据修改 CTE 里（WITH d AS (DELETE ... RETURNING *) SELECT * FROM d
    # 根节点仍是 Select），必须全树扫描。
    _reject_write_nodes(tree)

    row_policies = policies.get("row") or {}
    col_policies = policies.get("column") or {}

    if view_sql:
        _expand_views(tree, view_sql, row_policies, col_policies)
        # 视图展开后 statement 可能含 DML，需再次扫描。
        _reject_write_nodes(tree)

    for table in list(tree.find_all(exp.Table)):
        templates = row_policies.get(table.name)
        if not templates:
            continue
        select = table.find_ancestor(exp.Select)
        if select is None:
            raise AclRewriteError(f"表 {table.name} 不在 SELECT 内，按 fail-closed 拒绝")
        for tpl in templates:
            try:
                cond = sqlglot.parse_one(tpl)
            except Exception as e:
                raise AclRewriteError(f"行谓词解析失败，按 fail-closed 拒绝：{e}") from e
            select.where(cond, copy=False)

    if col_policies:
        if not isinstance(tree, exp.Select):
            raise AclRewriteError("含列权限策略时仅支持单 SELECT（UNION 等按 fail-closed 拒绝）")
        _expand_outer_stars(tree, schema)
        for select in tree.find_all(exp.Select):
            _apply_column_policies(select, col_policies)

    return tree.sql()


def _expand_views(
    tree: exp.Expression,
    view_sql: dict[str, str],
    row_policies: dict,
    col_policies: dict,
) -> None:
    """把 view_sql 中的表名替换为解析后的子查询（保留 alias）。

    固定点展开直到树中不再出现 view_sql 名称；检测环并 fail-closed。
    解析失败时有行/列策略则 fail-closed。
    """
    has_exceptions = bool(row_policies) or bool(col_policies)

    def _replace_table(table: exp.Table, chain: tuple[str, ...]) -> None:
        name = table.name
        statement = view_sql.get(name)
        if statement is None:
            return
        if name in chain:
            raise AclRewriteError(
                f"视图展开检测到环：{' → '.join([*chain, name])}，按 fail-closed 拒绝"
            )
        try:
            view_tree = sqlglot.parse_one(statement)
        except Exception as e:
            if has_exceptions:
                raise AclRewriteError(f"视图 SQL 解析失败，按 fail-closed 拒绝：{e}") from e
            return
        _reject_write_nodes(view_tree)
        if not isinstance(view_tree, (exp.Select, exp.Union, exp.Subquery)):
            if has_exceptions:
                raise AclRewriteError(
                    f"视图 SQL 解析失败，按 fail-closed 拒绝：非只读查询 {type(view_tree).__name__}"
                )
            return
        # 先展开视图体内的嵌套视图，再替换外层引用。
        nested_chain = (*chain, name)
        for inner in list(view_tree.find_all(exp.Table)):
            if inner.name in view_sql:
                _replace_table(inner, nested_chain)
        table.replace(view_tree.subquery(alias=table.alias or name))

    # 固定点：反复扫描直到本轮无替换。
    max_rounds = max(1, len(view_sql) + 1)
    for _ in range(max_rounds):
        replaced = False
        for table in list(tree.find_all(exp.Table)):
            if table.name not in view_sql:
                continue
            _replace_table(table, ())
            replaced = True
        if not replaced:
            break
    else:
        remaining = sorted({t.name for t in tree.find_all(exp.Table) if t.name in view_sql})
        if remaining and has_exceptions:
            raise AclRewriteError(
                f"视图未能完全展开（仍含 {remaining}），按 fail-closed 拒绝"
            )

    # 策略非空时，展开后仍残留 view 名 → fail-closed（防御固定点遗漏）。
    if has_exceptions:
        leftover = sorted({t.name for t in tree.find_all(exp.Table) if t.name in view_sql})
        if leftover:
            raise AclRewriteError(
                f"视图未能完全展开（仍含 {leftover}），按 fail-closed 拒绝"
            )


def _expand_outer_stars(select: exp.Select, schema: dict[str, list[str]] | None) -> None:
    """展开最外层投影的 * / t.* 为显式列。无法静态解析则 fail closed。"""
    stars = [p for p in select.expressions
             if isinstance(p, exp.Star) or (isinstance(p, exp.Column) and p.name == "*")]
    if not stars:
        return
    if not schema:
        raise AclRewriteError("查询含 SELECT * 且存在列权限策略，但缺少模型列清单，按 fail-closed 拒绝")

    cte_names = {c.alias for c in select.find_all(exp.CTE)}
    from_ = select.args.get("from_")
    raw_sources = (([from_.this] if from_ and from_.this else [])
                   + list(from_.expressions if from_ else [])
                   + [j.this for j in (select.args.get("joins") or [])])
    sources = []
    for s in raw_sources:
        if not isinstance(s, exp.Table) or s.name in cte_names:
            raise AclRewriteError(
                f"SELECT * 的来源 {s.sql()} 不是基底模型（子查询/CTE 无法静态展开），"
                "按 fail-closed 拒绝"
            )
        sources.append((s.alias_or_name, s.name))
    if not sources:
        raise AclRewriteError("SELECT * 无 FROM 来源（无列可展开），按 fail-closed 拒绝")

    new_exprs = []
    for p in select.expressions:
        if isinstance(p, exp.Star):
            targets = sources
        elif isinstance(p, exp.Column) and p.name == "*":
            targets = [(ref, m) for ref, m in sources if ref == p.table or m == p.table]
            if not targets:
                raise AclRewriteError(f"无法解析 {p.sql()} 的来源表，按 fail-closed 拒绝")
        else:
            new_exprs.append(p)
            continue
        for ref, model in targets:
            model_cols = schema.get(model)
            if not model_cols:
                raise AclRewriteError(f"模型 {model} 无列清单（未建模？），SELECT * 按 fail-closed 拒绝")
            new_exprs.extend(exp.column(c, table=ref, quoted=True) for c in model_cols)
    select.set("expressions", new_exprs)


def _parse_mask_expr(mask_expr: str, *, model: str, col: str) -> exp.Expression:
    """Parse mask_expr; empty/invalid → AclRewriteError (never let ParseError escape)."""
    if not (mask_expr or "").strip():
        raise AclRewriteError(
            f"列 {col}（模型 {model}）为 mask 但缺少 mask_expr，按 fail-closed 拒绝"
        )
    try:
        return sqlglot.parse_one(mask_expr)
    except Exception as e:
        raise AclRewriteError(
            f"列 {col}（模型 {model}）的 mask_expr 解析失败，按 fail-closed 拒绝：{e}"
        ) from e


def _apply_column_policies(select: exp.Select, col_policies: dict) -> None:
    tables_in_query = {t.name for t in select.find_all(exp.Table)}
    group = select.args.get("group")
    grouped_cols = ({c.name.lower() for c in group.find_all(exp.Column)}
                    if group else None)
    for projection in select.expressions:
        out_name = (projection.alias_or_name or "").lower()
        for (model, col), rule in col_policies.items():
            if model not in tables_in_query:
                continue
            hit = any(c.name.lower() == col.lower()
                      and (not c.table or c.table == model or model in tables_in_query)
                      for c in projection.find_all(exp.Column))
            if not hit and out_name != col.lower():
                continue
            action = rule.get("action")
            if action == "deny":
                raise ColumnDenied(f"无权限访问字段：{col}（模型 {model}）")
            if action != "mask":
                raise AclRewriteError(
                    f"列 {col}（模型 {model}）未知动作 {action!r}，按 fail-closed 拒绝"
                )
            mask_ast = _parse_mask_expr(rule.get("mask_expr") or "", model=model, col=col)
            if grouped_cols is not None:
                refs = {c.name.lower() for c in mask_ast.find_all(exp.Column)}
                missing = refs - grouped_cols - {col.lower()}
                if missing:
                    raise AclRewriteError(
                        f"脱敏表达式引用的列 {sorted(missing)} 不在 GROUP BY 中，"
                        "该聚合查询无法应用条件脱敏；请把相关维度加入分组，或改为非聚合查询。")
            if isinstance(projection, exp.Column) and projection.name.lower() == col.lower():
                projection.replace(exp.alias_(mask_ast.copy(), projection.name))
                break
            for c in list(projection.find_all(exp.Column)):
                if c.name.lower() == col.lower():
                    c.replace(mask_ast.copy())
