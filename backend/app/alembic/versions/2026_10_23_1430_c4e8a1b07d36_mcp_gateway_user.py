"""mcp gateway user

Revision ID: c4e8a1b07d36
Revises:
Create Date: 2026-10-23 14:30:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c4e8a1b07d36"
down_revision: str | None = None
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
        "mcp_biz_user",
        sa.Column("name", sa.String(length=64), nullable=False, comment="姓名"),
        sa.Column("email", sa.String(length=128), nullable=True, comment="邮箱"),
        sa.Column("mobile", sa.String(length=20), nullable=True, comment="手机号"),
        sa.Column("nickname", sa.String(length=64), nullable=True, comment="昵称"),
        sa.Column("enabled", sa.Boolean(), nullable=False, comment="是否启用"),
        *_mixin_columns(),
        sa.PrimaryKeyConstraint("id", name="pk_mcp_biz_user"),
        comment="业务用户表",
    )
    op.create_index("ix_mcp_biz_user_name", "mcp_biz_user", ["name"], unique=False)
    op.create_index("ix_mcp_biz_user_id", "mcp_biz_user", ["id"], unique=False)
    op.create_index("ix_mcp_biz_user_uuid", "mcp_biz_user", ["uuid"], unique=True)
    op.create_index("ix_mcp_biz_user_is_deleted", "mcp_biz_user", ["is_deleted"], unique=False)
    op.create_index("ix_mcp_biz_user_created_time", "mcp_biz_user", ["created_time"], unique=False)

    op.create_table(
        "mcp_biz_user_group",
        sa.Column("name", sa.String(length=64), nullable=False, comment="组名"),
        sa.Column("enabled", sa.Boolean(), nullable=False, comment="是否启用"),
        *_mixin_columns(),
        sa.PrimaryKeyConstraint("id", name="pk_mcp_biz_user_group"),
        comment="业务用户组表",
    )
    op.create_index("ix_mcp_biz_user_group_name", "mcp_biz_user_group", ["name"], unique=False)
    op.create_index("ix_mcp_biz_user_group_id", "mcp_biz_user_group", ["id"], unique=False)
    op.create_index("ix_mcp_biz_user_group_uuid", "mcp_biz_user_group", ["uuid"], unique=True)
    op.create_index("ix_mcp_biz_user_group_is_deleted", "mcp_biz_user_group", ["is_deleted"], unique=False)
    op.create_index("ix_mcp_biz_user_group_created_time", "mcp_biz_user_group", ["created_time"], unique=False)

    op.create_table(
        "mcp_biz_user_group_member",
        sa.Column("user_id", sa.Integer(), nullable=False, comment="业务用户ID"),
        sa.Column("group_id", sa.Integer(), nullable=False, comment="用户组ID"),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["mcp_biz_user.id"],
            name="fk_mcp_biz_user_group_member_user_id_mcp_biz_user",
            ondelete="CASCADE",
            onupdate="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["group_id"],
            ["mcp_biz_user_group.id"],
            name="fk_mcp_biz_user_group_member_group_id_mcp_biz_user_group",
            ondelete="CASCADE",
            onupdate="CASCADE",
        ),
        sa.PrimaryKeyConstraint("user_id", "group_id", name="pk_mcp_biz_user_group_member"),
        comment="业务用户组成员表",
    )


def downgrade() -> None:
    op.drop_table("mcp_biz_user_group_member")
    op.drop_index("ix_mcp_biz_user_group_created_time", table_name="mcp_biz_user_group")
    op.drop_index("ix_mcp_biz_user_group_is_deleted", table_name="mcp_biz_user_group")
    op.drop_index("ix_mcp_biz_user_group_uuid", table_name="mcp_biz_user_group")
    op.drop_index("ix_mcp_biz_user_group_id", table_name="mcp_biz_user_group")
    op.drop_index("ix_mcp_biz_user_group_name", table_name="mcp_biz_user_group")
    op.drop_table("mcp_biz_user_group")
    op.drop_index("ix_mcp_biz_user_created_time", table_name="mcp_biz_user")
    op.drop_index("ix_mcp_biz_user_is_deleted", table_name="mcp_biz_user")
    op.drop_index("ix_mcp_biz_user_uuid", table_name="mcp_biz_user")
    op.drop_index("ix_mcp_biz_user_id", table_name="mcp_biz_user")
    op.drop_index("ix_mcp_biz_user_name", table_name="mcp_biz_user")
    op.drop_table("mcp_biz_user")
