"""mcp call log

Revision ID: c8d4f1a07e53
Revises: a7c3e9b14d62
Create Date: 2026-10-24 02:50:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c8d4f1a07e53"
down_revision: str | None = "a7c3e9b14d62"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "mcp_call_log",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False, comment="主键ID"),
        sa.Column("user_id", sa.Integer(), nullable=False, comment="业务用户ID"),
        sa.Column("group_id", sa.Integer(), nullable=False, comment="MCP 组ID"),
        sa.Column("tool_name", sa.String(length=512), nullable=False, comment="工具名称"),
        sa.Column("system_id", sa.Integer(), nullable=True, comment="业务系统ID"),
        sa.Column("elapsed_ms", sa.Integer(), nullable=False, comment="耗时毫秒"),
        sa.Column("ok", sa.Boolean(), nullable=False, comment="是否成功"),
        sa.Column("http_status", sa.Integer(), nullable=True, comment="上游 HTTP 状态码"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, comment="创建时间"),
        sa.PrimaryKeyConstraint("id", name="pk_mcp_call_log"),
        comment="MCP 调用日志表",
    )
    op.create_index("ix_mcp_call_log_user_id", "mcp_call_log", ["user_id"], unique=False)
    op.create_index("ix_mcp_call_log_group_id", "mcp_call_log", ["group_id"], unique=False)
    op.create_index("ix_mcp_call_log_tool_name", "mcp_call_log", ["tool_name"], unique=False)
    op.create_index("ix_mcp_call_log_system_id", "mcp_call_log", ["system_id"], unique=False)
    op.create_index("ix_mcp_call_log_created_at", "mcp_call_log", ["created_at"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_mcp_call_log_created_at", table_name="mcp_call_log")
    op.drop_index("ix_mcp_call_log_system_id", table_name="mcp_call_log")
    op.drop_index("ix_mcp_call_log_tool_name", table_name="mcp_call_log")
    op.drop_index("ix_mcp_call_log_group_id", table_name="mcp_call_log")
    op.drop_index("ix_mcp_call_log_user_id", table_name="mcp_call_log")
    op.drop_table("mcp_call_log")
