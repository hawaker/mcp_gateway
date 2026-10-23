"""mcp gateway auth config

Revision ID: b8e1d4c07f25
Revises: a91c4e7b2d58
Create Date: 2026-10-23 17:00:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b8e1d4c07f25"
down_revision: str | None = "a91c4e7b2d58"
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
        "mcp_biz_auth_config",
        sa.Column("system_id", sa.Integer(), nullable=False, comment="业务系统ID"),
        sa.Column("method", sa.String(length=32), nullable=False, comment="鉴权方法"),
        sa.Column("enabled", sa.Boolean(), nullable=False, comment="是否启用"),
        sa.Column("url", sa.String(length=512), nullable=False, comment="鉴权地址"),
        sa.Column("rule", sa.JSON(), nullable=False, comment="取值规则"),
        sa.Column("http_method", sa.String(length=16), nullable=True, comment="HTTP 方法"),
        sa.Column("username", sa.String(length=128), nullable=True, comment="Basic 用户名"),
        sa.Column("password", sa.String(length=512), nullable=True, comment="Basic 密码"),
        *_mixin_columns(),
        sa.ForeignKeyConstraint(
            ["system_id"],
            ["mcp_biz_system.id"],
            name="fk_mcp_biz_auth_config_system_id_mcp_biz_system",
            ondelete="CASCADE",
            onupdate="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_mcp_biz_auth_config"),
        comment="业务鉴权配置表",
    )
    op.create_index("ix_mcp_biz_auth_config_system_id", "mcp_biz_auth_config", ["system_id"], unique=False)
    op.create_index("ix_mcp_biz_auth_config_id", "mcp_biz_auth_config", ["id"], unique=False)
    op.create_index("ix_mcp_biz_auth_config_uuid", "mcp_biz_auth_config", ["uuid"], unique=True)
    op.create_index("ix_mcp_biz_auth_config_is_deleted", "mcp_biz_auth_config", ["is_deleted"], unique=False)
    op.create_index("ix_mcp_biz_auth_config_created_time", "mcp_biz_auth_config", ["created_time"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_mcp_biz_auth_config_created_time", table_name="mcp_biz_auth_config")
    op.drop_index("ix_mcp_biz_auth_config_is_deleted", table_name="mcp_biz_auth_config")
    op.drop_index("ix_mcp_biz_auth_config_uuid", table_name="mcp_biz_auth_config")
    op.drop_index("ix_mcp_biz_auth_config_id", table_name="mcp_biz_auth_config")
    op.drop_index("ix_mcp_biz_auth_config_system_id", table_name="mcp_biz_auth_config")
    op.drop_table("mcp_biz_auth_config")
