"""mcp upstream

Revision ID: c3a9e1d84b72
Revises: f2b7c4e90a18
Create Date: 2026-10-23 21:30:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c3a9e1d84b72"
down_revision: str | None = "f2b7c4e90a18"
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
        "mcp_upstream_mcp",
        sa.Column("system_id", sa.Integer(), nullable=False, comment="业务系统ID"),
        sa.Column("url", sa.String(length=2048), nullable=False, comment="上游地址"),
        sa.Column("credential_header", sa.String(length=128), nullable=False, comment="凭证请求头"),
        sa.Column("credential_value_encrypted", sa.Text(), nullable=False, comment="凭证密文"),
        *_mixin_columns(),
        sa.ForeignKeyConstraint(
            ["system_id"],
            ["mcp_biz_system.id"],
            name="fk_mcp_upstream_mcp_system_id_mcp_biz_system",
            ondelete="CASCADE",
            onupdate="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_mcp_upstream_mcp"),
        comment="上游 MCP 表",
    )
    op.create_index("ix_mcp_upstream_mcp_system_id", "mcp_upstream_mcp", ["system_id"], unique=False)
    op.create_index("ix_mcp_upstream_mcp_id", "mcp_upstream_mcp", ["id"], unique=False)
    op.create_index("ix_mcp_upstream_mcp_uuid", "mcp_upstream_mcp", ["uuid"], unique=True)
    op.create_index("ix_mcp_upstream_mcp_is_deleted", "mcp_upstream_mcp", ["is_deleted"], unique=False)
    op.create_index("ix_mcp_upstream_mcp_created_time", "mcp_upstream_mcp", ["created_time"], unique=False)

    op.create_table(
        "mcp_upstream_tool",
        sa.Column("upstream_id", sa.Integer(), nullable=False, comment="上游 MCP ID"),
        sa.Column("remote_name", sa.String(length=512), nullable=False, comment="远端工具名"),
        sa.Column("external_name", sa.String(length=512), nullable=False, comment="外部名称"),
        sa.Column("input_schema", sa.JSON(), nullable=False, comment="入参结构"),
        sa.Column("selected", sa.Boolean(), nullable=False, comment="是否选用"),
        *_mixin_columns(),
        sa.ForeignKeyConstraint(
            ["upstream_id"],
            ["mcp_upstream_mcp.id"],
            name="fk_mcp_upstream_tool_upstream_id_mcp_upstream_mcp",
            ondelete="CASCADE",
            onupdate="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_mcp_upstream_tool"),
        comment="上游 MCP 工具表",
    )
    op.create_index("ix_mcp_upstream_tool_upstream_id", "mcp_upstream_tool", ["upstream_id"], unique=False)
    op.create_index("ix_mcp_upstream_tool_remote_name", "mcp_upstream_tool", ["remote_name"], unique=False)
    op.create_index("ix_mcp_upstream_tool_external_name", "mcp_upstream_tool", ["external_name"], unique=False)
    op.create_index("ix_mcp_upstream_tool_id", "mcp_upstream_tool", ["id"], unique=False)
    op.create_index("ix_mcp_upstream_tool_uuid", "mcp_upstream_tool", ["uuid"], unique=True)
    op.create_index("ix_mcp_upstream_tool_is_deleted", "mcp_upstream_tool", ["is_deleted"], unique=False)
    op.create_index("ix_mcp_upstream_tool_created_time", "mcp_upstream_tool", ["created_time"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_mcp_upstream_tool_created_time", table_name="mcp_upstream_tool")
    op.drop_index("ix_mcp_upstream_tool_is_deleted", table_name="mcp_upstream_tool")
    op.drop_index("ix_mcp_upstream_tool_uuid", table_name="mcp_upstream_tool")
    op.drop_index("ix_mcp_upstream_tool_id", table_name="mcp_upstream_tool")
    op.drop_index("ix_mcp_upstream_tool_external_name", table_name="mcp_upstream_tool")
    op.drop_index("ix_mcp_upstream_tool_remote_name", table_name="mcp_upstream_tool")
    op.drop_index("ix_mcp_upstream_tool_upstream_id", table_name="mcp_upstream_tool")
    op.drop_table("mcp_upstream_tool")
    op.drop_index("ix_mcp_upstream_mcp_created_time", table_name="mcp_upstream_mcp")
    op.drop_index("ix_mcp_upstream_mcp_is_deleted", table_name="mcp_upstream_mcp")
    op.drop_index("ix_mcp_upstream_mcp_uuid", table_name="mcp_upstream_mcp")
    op.drop_index("ix_mcp_upstream_mcp_id", table_name="mcp_upstream_mcp")
    op.drop_index("ix_mcp_upstream_mcp_system_id", table_name="mcp_upstream_mcp")
    op.drop_table("mcp_upstream_mcp")
