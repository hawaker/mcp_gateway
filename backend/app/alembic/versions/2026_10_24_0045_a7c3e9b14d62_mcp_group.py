"""mcp group

Revision ID: a7c3e9b14d62
Revises: b6e2d8a14c90
Create Date: 2026-10-24 00:45:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a7c3e9b14d62"
down_revision: str | None = "b6e2d8a14c90"
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
        "mcp_group",
        sa.Column("name", sa.String(length=128), nullable=False, comment="名称"),
        sa.Column("enabled", sa.Boolean(), nullable=False, comment="是否启用"),
        *_mixin_columns(),
        sa.PrimaryKeyConstraint("id", name="pk_mcp_group"),
        comment="MCP 组表",
    )
    op.create_index("ix_mcp_group_name", "mcp_group", ["name"], unique=False)
    op.create_index("ix_mcp_group_id", "mcp_group", ["id"], unique=False)
    op.create_index("ix_mcp_group_uuid", "mcp_group", ["uuid"], unique=True)
    op.create_index("ix_mcp_group_is_deleted", "mcp_group", ["is_deleted"], unique=False)
    op.create_index("ix_mcp_group_created_time", "mcp_group", ["created_time"], unique=False)

    op.create_table(
        "mcp_group_tool",
        sa.Column("group_id", sa.Integer(), nullable=False, comment="MCP 组ID"),
        sa.Column("source", sa.String(length=16), nullable=False, comment="来源"),
        sa.Column("source_id", sa.Integer(), nullable=False, comment="来源工具ID"),
        sa.Column("external_name", sa.String(length=512), nullable=False, comment="外部名称"),
        sa.Column("enabled", sa.Boolean(), nullable=False, comment="是否启用"),
        *_mixin_columns(),
        sa.ForeignKeyConstraint(
            ["group_id"],
            ["mcp_group.id"],
            name="fk_mcp_group_tool_group_id_mcp_group",
            ondelete="CASCADE",
            onupdate="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_mcp_group_tool"),
        sa.UniqueConstraint("group_id", "external_name", name="uq_mcp_group_tool_group_id_external_name"),
        comment="MCP 组工具表",
    )
    op.create_index("ix_mcp_group_tool_group_id", "mcp_group_tool", ["group_id"], unique=False)
    op.create_index("ix_mcp_group_tool_source_id", "mcp_group_tool", ["source_id"], unique=False)
    op.create_index("ix_mcp_group_tool_external_name", "mcp_group_tool", ["external_name"], unique=False)
    op.create_index("ix_mcp_group_tool_id", "mcp_group_tool", ["id"], unique=False)
    op.create_index("ix_mcp_group_tool_uuid", "mcp_group_tool", ["uuid"], unique=True)
    op.create_index("ix_mcp_group_tool_is_deleted", "mcp_group_tool", ["is_deleted"], unique=False)
    op.create_index("ix_mcp_group_tool_created_time", "mcp_group_tool", ["created_time"], unique=False)

    op.create_table(
        "mcp_group_member",
        sa.Column("group_id", sa.Integer(), nullable=False, comment="MCP 组ID"),
        sa.Column("principal_type", sa.String(length=16), nullable=False, comment="主体类型"),
        sa.Column("principal_id", sa.Integer(), nullable=False, comment="主体ID"),
        sa.Column("enabled", sa.Boolean(), nullable=False, comment="是否启用"),
        *_mixin_columns(),
        sa.ForeignKeyConstraint(
            ["group_id"],
            ["mcp_group.id"],
            name="fk_mcp_group_member_group_id_mcp_group",
            ondelete="CASCADE",
            onupdate="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_mcp_group_member"),
        sa.UniqueConstraint("group_id", "principal_type", "principal_id", name="uq_mcp_group_member_group_principal"),
        comment="MCP 组成员表",
    )
    op.create_index("ix_mcp_group_member_group_id", "mcp_group_member", ["group_id"], unique=False)
    op.create_index("ix_mcp_group_member_principal_id", "mcp_group_member", ["principal_id"], unique=False)
    op.create_index("ix_mcp_group_member_id", "mcp_group_member", ["id"], unique=False)
    op.create_index("ix_mcp_group_member_uuid", "mcp_group_member", ["uuid"], unique=True)
    op.create_index("ix_mcp_group_member_is_deleted", "mcp_group_member", ["is_deleted"], unique=False)
    op.create_index("ix_mcp_group_member_created_time", "mcp_group_member", ["created_time"], unique=False)

    op.create_table(
        "mcp_credential",
        sa.Column("user_id", sa.Integer(), nullable=False, comment="业务用户ID"),
        sa.Column("group_id", sa.Integer(), nullable=False, comment="MCP 组ID"),
        sa.Column("token_hash", sa.String(length=64), nullable=False, comment="令牌哈希"),
        sa.Column("token_encrypted", sa.Text(), nullable=False, comment="令牌密文"),
        *_mixin_columns(),
        sa.ForeignKeyConstraint(
            ["group_id"],
            ["mcp_group.id"],
            name="fk_mcp_credential_group_id_mcp_group",
            ondelete="CASCADE",
            onupdate="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["mcp_biz_user.id"],
            name="fk_mcp_credential_user_id_mcp_biz_user",
            ondelete="CASCADE",
            onupdate="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_mcp_credential"),
        sa.UniqueConstraint("user_id", "group_id", name="uq_mcp_credential_user_id_group_id"),
        comment="MCP 凭证表",
    )
    op.create_index("ix_mcp_credential_user_id", "mcp_credential", ["user_id"], unique=False)
    op.create_index("ix_mcp_credential_group_id", "mcp_credential", ["group_id"], unique=False)
    op.create_index("ix_mcp_credential_token_hash", "mcp_credential", ["token_hash"], unique=True)
    op.create_index("ix_mcp_credential_id", "mcp_credential", ["id"], unique=False)
    op.create_index("ix_mcp_credential_uuid", "mcp_credential", ["uuid"], unique=True)
    op.create_index("ix_mcp_credential_is_deleted", "mcp_credential", ["is_deleted"], unique=False)
    op.create_index("ix_mcp_credential_created_time", "mcp_credential", ["created_time"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_mcp_credential_created_time", table_name="mcp_credential")
    op.drop_index("ix_mcp_credential_is_deleted", table_name="mcp_credential")
    op.drop_index("ix_mcp_credential_uuid", table_name="mcp_credential")
    op.drop_index("ix_mcp_credential_id", table_name="mcp_credential")
    op.drop_index("ix_mcp_credential_token_hash", table_name="mcp_credential")
    op.drop_index("ix_mcp_credential_group_id", table_name="mcp_credential")
    op.drop_index("ix_mcp_credential_user_id", table_name="mcp_credential")
    op.drop_table("mcp_credential")
    op.drop_index("ix_mcp_group_member_created_time", table_name="mcp_group_member")
    op.drop_index("ix_mcp_group_member_is_deleted", table_name="mcp_group_member")
    op.drop_index("ix_mcp_group_member_uuid", table_name="mcp_group_member")
    op.drop_index("ix_mcp_group_member_id", table_name="mcp_group_member")
    op.drop_index("ix_mcp_group_member_principal_id", table_name="mcp_group_member")
    op.drop_index("ix_mcp_group_member_group_id", table_name="mcp_group_member")
    op.drop_table("mcp_group_member")
    op.drop_index("ix_mcp_group_tool_created_time", table_name="mcp_group_tool")
    op.drop_index("ix_mcp_group_tool_is_deleted", table_name="mcp_group_tool")
    op.drop_index("ix_mcp_group_tool_uuid", table_name="mcp_group_tool")
    op.drop_index("ix_mcp_group_tool_id", table_name="mcp_group_tool")
    op.drop_index("ix_mcp_group_tool_external_name", table_name="mcp_group_tool")
    op.drop_index("ix_mcp_group_tool_source_id", table_name="mcp_group_tool")
    op.drop_index("ix_mcp_group_tool_group_id", table_name="mcp_group_tool")
    op.drop_table("mcp_group_tool")
    op.drop_index("ix_mcp_group_created_time", table_name="mcp_group")
    op.drop_index("ix_mcp_group_is_deleted", table_name="mcp_group")
    op.drop_index("ix_mcp_group_uuid", table_name="mcp_group")
    op.drop_index("ix_mcp_group_id", table_name="mcp_group")
    op.drop_index("ix_mcp_group_name", table_name="mcp_group")
    op.drop_table("mcp_group")
