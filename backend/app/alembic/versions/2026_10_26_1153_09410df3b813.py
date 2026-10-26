"""auth_custom_request_shape

Revision ID: 09410df3b813
Revises: 9a7ebe570526
Create Date: 2026-10-26 11:53:18.338377

"""

import json
from typing import Any, Sequence, Union

import sqlalchemy as sa
from alembic import op

from app.modules.mcp_gateway.auth.migrate_rule import lift_custom_request_from_rule

# revision identifiers, used by Alembic.
revision: str = "09410df3b813"
down_revision: Union[str, None] = "9a7ebe570526"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _parse_rule(raw: Any) -> dict[str, Any]:
    if raw is None:
        return {}
    if isinstance(raw, dict):
        return dict(raw)
    if isinstance(raw, (bytes, bytearray)):
        raw = raw.decode()
    if isinstance(raw, str):
        if not raw.strip():
            return {}
        return dict(json.loads(raw))
    return {}


def _dump_json(value: Any) -> str | None:
    if value is None:
        return None
    return json.dumps(value, ensure_ascii=False)


def upgrade() -> None:
    with op.batch_alter_table("mcp_biz_auth_config", schema=None) as batch_op:
        batch_op.add_column(sa.Column("headers", sa.JSON(), nullable=True, comment="自定义请求头"))
        batch_op.add_column(sa.Column("query", sa.JSON(), nullable=True, comment="自定义 Query"))
        batch_op.add_column(sa.Column("body_type", sa.String(length=16), nullable=True, comment="自定义 Body 类型"))
        batch_op.add_column(sa.Column("body", sa.JSON(), nullable=True, comment="自定义 Body"))

    bind = op.get_bind()
    rows = bind.execute(sa.text("SELECT id, method, rule FROM mcp_biz_auth_config")).mappings().all()
    for row in rows:
        if row["method"] != "custom":
            continue
        headers, query, body_type, body, cleaned = lift_custom_request_from_rule(_parse_rule(row["rule"]))
        bind.execute(
            sa.text(
                "UPDATE mcp_biz_auth_config SET headers = :headers, query = :query, "
                "body_type = :body_type, body = :body, rule = :rule WHERE id = :id"
            ),
            {
                "id": row["id"],
                "headers": _dump_json(headers),
                "query": _dump_json(query),
                "body_type": body_type,
                "body": _dump_json(body),
                "rule": _dump_json(cleaned),
            },
        )


def downgrade() -> None:
    bind = op.get_bind()
    rows = (
        bind.execute(
            sa.text(
                "SELECT id, method, rule, headers, query, body_type, body FROM mcp_biz_auth_config"
            )
        )
        .mappings()
        .all()
    )
    for row in rows:
        if row["method"] != "custom":
            continue
        rule = _parse_rule(row["rule"])
        headers = _parse_rule(row["headers"]) or None
        query = _parse_rule(row["query"]) or None
        body = _parse_rule(row["body"]) or None
        if headers:
            rule["headers"] = headers
        if query:
            rule["query"] = query
        body_type = row["body_type"]
        if body_type == "form" and body is not None:
            rule["form"] = body
        elif body_type == "json" and body is not None:
            rule["json"] = body
        bind.execute(
            sa.text("UPDATE mcp_biz_auth_config SET rule = :rule WHERE id = :id"),
            {"id": row["id"], "rule": _dump_json(rule)},
        )

    with op.batch_alter_table("mcp_biz_auth_config", schema=None) as batch_op:
        batch_op.drop_column("body")
        batch_op.drop_column("body_type")
        batch_op.drop_column("query")
        batch_op.drop_column("headers")
