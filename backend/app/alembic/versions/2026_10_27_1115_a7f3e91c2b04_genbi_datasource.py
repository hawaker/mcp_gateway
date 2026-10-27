"""genbi datasource

Revision ID: a7f3e91c2b04
Revises: a1b2c3d4e5f6
Create Date: 2026-10-27 11:15:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "a7f3e91c2b04"
down_revision: str | None = "a1b2c3d4e5f6"
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
        "genbi_datasource",
        sa.Column("system_id", sa.Integer(), nullable=False, comment="业务系统ID"),
        sa.Column("name", sa.String(length=128), nullable=False, comment="名称"),
        sa.Column("wren_type", sa.String(length=32), nullable=False, comment="Wren 数据源类型"),
        sa.Column("host", sa.String(length=255), nullable=True, comment="主机"),
        sa.Column("port", sa.Integer(), nullable=True, comment="端口"),
        sa.Column("username", sa.String(length=128), nullable=True, comment="用户名"),
        sa.Column("password_encrypted", sa.Text(), nullable=True, comment="密码密文"),
        sa.Column("database", sa.String(length=128), nullable=True, comment="数据库名"),
        sa.Column("db_schema", sa.String(length=128), nullable=True, comment="Schema"),
        sa.Column("url", sa.String(length=1024), nullable=True, comment="连接 URL"),
        sa.Column("api_key_encrypted", sa.Text(), nullable=True, comment="API Key 密文"),
        sa.Column("private_key_encrypted", sa.Text(), nullable=True, comment="私钥密文"),
        sa.Column("token_encrypted", sa.Text(), nullable=True, comment="Token 密文"),
        sa.Column("config", sa.JSON(), nullable=False, comment="扩展配置"),
        sa.Column("description", sa.String(length=512), nullable=True, comment="描述"),
        sa.Column("enabled", sa.Boolean(), nullable=False, comment="是否启用"),
        *_mixin_columns(),
        sa.ForeignKeyConstraint(
            ["system_id"],
            ["mcp_biz_system.id"],
            name="fk_genbi_datasource_system_id_mcp_biz_system",
            ondelete="CASCADE",
            onupdate="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_genbi_datasource"),
        comment="GenBI 数据源表",
    )
    op.create_index("ix_genbi_datasource_system_id", "genbi_datasource", ["system_id"], unique=False)
    op.create_index("ix_genbi_datasource_name", "genbi_datasource", ["name"], unique=False)
    op.create_index("ix_genbi_datasource_id", "genbi_datasource", ["id"], unique=False)
    op.create_index("ix_genbi_datasource_uuid", "genbi_datasource", ["uuid"], unique=True)
    op.create_index("ix_genbi_datasource_is_deleted", "genbi_datasource", ["is_deleted"], unique=False)
    op.create_index("ix_genbi_datasource_created_time", "genbi_datasource", ["created_time"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_genbi_datasource_created_time", table_name="genbi_datasource")
    op.drop_index("ix_genbi_datasource_is_deleted", table_name="genbi_datasource")
    op.drop_index("ix_genbi_datasource_uuid", table_name="genbi_datasource")
    op.drop_index("ix_genbi_datasource_id", table_name="genbi_datasource")
    op.drop_index("ix_genbi_datasource_name", table_name="genbi_datasource")
    op.drop_index("ix_genbi_datasource_system_id", table_name="genbi_datasource")
    op.drop_table("genbi_datasource")
