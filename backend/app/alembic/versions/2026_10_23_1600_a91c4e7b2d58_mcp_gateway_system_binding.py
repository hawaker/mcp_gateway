"""mcp gateway system and binding

Revision ID: a91c4e7b2d58
Revises: c4e8a1b07d36
Create Date: 2026-10-23 16:00:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a91c4e7b2d58"
down_revision: str | None = "c4e8a1b07d36"
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
        "mcp_biz_system",
        sa.Column("name", sa.String(length=64), nullable=False, comment="名称"),
        sa.Column("code", sa.String(length=64), nullable=False, comment="系统编码"),
        sa.Column("base_url", sa.String(length=512), nullable=False, comment="基础地址"),
        sa.Column("enabled", sa.Boolean(), nullable=False, comment="是否启用"),
        sa.Column("params", sa.JSON(), nullable=False, comment="扩展参数"),
        sa.Column("uid_field", sa.String(length=64), nullable=False, comment="用户标识字段"),
        sa.Column("attr_fields", sa.JSON(), nullable=False, comment="允许的绑定属性"),
        *_mixin_columns(),
        sa.PrimaryKeyConstraint("id", name="pk_mcp_biz_system"),
        comment="业务系统表",
    )
    op.create_index("ix_mcp_biz_system_name", "mcp_biz_system", ["name"], unique=False)
    op.create_index("ix_mcp_biz_system_code", "mcp_biz_system", ["code"], unique=True)
    op.create_index("ix_mcp_biz_system_id", "mcp_biz_system", ["id"], unique=False)
    op.create_index("ix_mcp_biz_system_uuid", "mcp_biz_system", ["uuid"], unique=True)
    op.create_index("ix_mcp_biz_system_is_deleted", "mcp_biz_system", ["is_deleted"], unique=False)
    op.create_index("ix_mcp_biz_system_created_time", "mcp_biz_system", ["created_time"], unique=False)

    op.create_table(
        "mcp_biz_binding",
        sa.Column("user_id", sa.Integer(), nullable=False, comment="业务用户ID"),
        sa.Column("system_id", sa.Integer(), nullable=False, comment="业务系统ID"),
        sa.Column("uid_value", sa.String(length=128), nullable=False, comment="业务系统用户标识"),
        sa.Column("attrs", sa.JSON(), nullable=False, comment="绑定属性"),
        sa.Column("enabled", sa.Boolean(), nullable=False, comment="是否启用"),
        *_mixin_columns(),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["mcp_biz_user.id"],
            name="fk_mcp_biz_binding_user_id_mcp_biz_user",
            ondelete="CASCADE",
            onupdate="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["system_id"],
            ["mcp_biz_system.id"],
            name="fk_mcp_biz_binding_system_id_mcp_biz_system",
            ondelete="CASCADE",
            onupdate="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_mcp_biz_binding"),
        sa.UniqueConstraint("user_id", "system_id", name="uq_mcp_biz_binding_user_system"),
        comment="业务系统绑定表",
    )
    op.create_index("ix_mcp_biz_binding_user_id", "mcp_biz_binding", ["user_id"], unique=False)
    op.create_index("ix_mcp_biz_binding_system_id", "mcp_biz_binding", ["system_id"], unique=False)
    op.create_index("ix_mcp_biz_binding_id", "mcp_biz_binding", ["id"], unique=False)
    op.create_index("ix_mcp_biz_binding_uuid", "mcp_biz_binding", ["uuid"], unique=True)
    op.create_index("ix_mcp_biz_binding_is_deleted", "mcp_biz_binding", ["is_deleted"], unique=False)
    op.create_index("ix_mcp_biz_binding_created_time", "mcp_biz_binding", ["created_time"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_mcp_biz_binding_created_time", table_name="mcp_biz_binding")
    op.drop_index("ix_mcp_biz_binding_is_deleted", table_name="mcp_biz_binding")
    op.drop_index("ix_mcp_biz_binding_uuid", table_name="mcp_biz_binding")
    op.drop_index("ix_mcp_biz_binding_id", table_name="mcp_biz_binding")
    op.drop_index("ix_mcp_biz_binding_system_id", table_name="mcp_biz_binding")
    op.drop_index("ix_mcp_biz_binding_user_id", table_name="mcp_biz_binding")
    op.drop_table("mcp_biz_binding")
    op.drop_index("ix_mcp_biz_system_created_time", table_name="mcp_biz_system")
    op.drop_index("ix_mcp_biz_system_is_deleted", table_name="mcp_biz_system")
    op.drop_index("ix_mcp_biz_system_uuid", table_name="mcp_biz_system")
    op.drop_index("ix_mcp_biz_system_id", table_name="mcp_biz_system")
    op.drop_index("ix_mcp_biz_system_code", table_name="mcp_biz_system")
    op.drop_index("ix_mcp_biz_system_name", table_name="mcp_biz_system")
    op.drop_table("mcp_biz_system")
