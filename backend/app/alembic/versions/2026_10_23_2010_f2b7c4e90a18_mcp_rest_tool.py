"""mcp rest tool

Revision ID: f2b7c4e90a18
Revises: e7c3b9a05d14
Create Date: 2026-10-23 20:10:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f2b7c4e90a18"
down_revision: str | None = "e7c3b9a05d14"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _mixin_columns() -> list[sa.Column]:
    return [
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False, comment="主键ID"),
        sa.Column("uuid", sa.String(length=64), nullable=False, comment="UUID全局唯一标识"),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, comment="是否已删除(0:未删除 1:已删除)"),
        sa.Column("created_time", sa.DateTime(timezone=True), nullable=False, comment="创建时间"),
        sa.Column("updated_time", sa.DateTime(timezone=True), nullable=False, comment="更新时间"),
        sa.Column("deleted_time", sa.DateTime(timezone=True), nullable=True, comment="删除时间"),
    ]


def upgrade() -> None:
    op.create_table(
        "mcp_rest_tool",
        sa.Column("name", sa.String(length=128), nullable=False, comment="名称"),
        sa.Column("display_name", sa.String(length=128), nullable=False, comment="显示名"),
        sa.Column("url", sa.String(length=2048), nullable=False, comment="接口地址"),
        sa.Column("description", sa.String(length=1024), nullable=True, comment="描述"),
        sa.Column("request_type", sa.String(length=16), nullable=False, comment="请求方法"),
        sa.Column("headers", sa.JSON(), nullable=False, comment="请求头"),
        sa.Column("input_schema", sa.JSON(), nullable=False, comment="入参结构"),
        sa.Column("output_schema", sa.JSON(), nullable=False, comment="出参结构"),
        sa.Column("jsonpath_filter", sa.String(length=512), nullable=True, comment="Json Path Filter"),
        sa.Column("query_mapping", sa.JSON(), nullable=False, comment="Query 映射"),
        sa.Column("header_mapping", sa.JSON(), nullable=False, comment="Header 映射"),
        sa.Column("timeout_ms", sa.Integer(), nullable=True, comment="超时毫秒"),
        sa.Column("token_in", sa.String(length=16), nullable=False, comment="token 位置"),
        sa.Column("token_name", sa.String(length=128), nullable=True, comment="token 字段名"),
        sa.Column("enabled", sa.Boolean(), nullable=False, comment="是否启用"),
        sa.Column("system_id", sa.Integer(), nullable=False, comment="业务系统ID"),
        *_mixin_columns(),
        sa.ForeignKeyConstraint(
            ["system_id"],
            ["mcp_biz_system.id"],
            name="fk_mcp_rest_tool_system_id_mcp_biz_system",
            ondelete="CASCADE",
            onupdate="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_mcp_rest_tool"),
        comment="REST 工具表",
    )
    op.create_index("ix_mcp_rest_tool_name", "mcp_rest_tool", ["name"], unique=False)
    op.create_index("ix_mcp_rest_tool_system_id", "mcp_rest_tool", ["system_id"], unique=False)
    op.create_index("ix_mcp_rest_tool_id", "mcp_rest_tool", ["id"], unique=False)
    op.create_index("ix_mcp_rest_tool_uuid", "mcp_rest_tool", ["uuid"], unique=True)
    op.create_index("ix_mcp_rest_tool_is_deleted", "mcp_rest_tool", ["is_deleted"], unique=False)
    op.create_index("ix_mcp_rest_tool_created_time", "mcp_rest_tool", ["created_time"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_mcp_rest_tool_created_time", table_name="mcp_rest_tool")
    op.drop_index("ix_mcp_rest_tool_is_deleted", table_name="mcp_rest_tool")
    op.drop_index("ix_mcp_rest_tool_uuid", table_name="mcp_rest_tool")
    op.drop_index("ix_mcp_rest_tool_id", table_name="mcp_rest_tool")
    op.drop_index("ix_mcp_rest_tool_system_id", table_name="mcp_rest_tool")
    op.drop_index("ix_mcp_rest_tool_name", table_name="mcp_rest_tool")
    op.drop_table("mcp_rest_tool")
