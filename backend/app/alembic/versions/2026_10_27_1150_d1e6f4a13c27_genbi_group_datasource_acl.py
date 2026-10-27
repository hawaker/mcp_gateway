"""genbi group datasource links and shared ACL

Revision ID: d1e6f4a13c27
Revises: c9d5e3f02b16
Create Date: 2026-10-27 11:50:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "d1e6f4a13c27"
down_revision: str | None = "c9d5e3f02b16"
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


def _mixin_indexes(table: str) -> None:
    op.create_index(f"ix_{table}_id", table, ["id"], unique=False)
    op.create_index(f"ix_{table}_uuid", table, ["uuid"], unique=True)
    op.create_index(f"ix_{table}_is_deleted", table, ["is_deleted"], unique=False)
    op.create_index(f"ix_{table}_created_time", table, ["created_time"], unique=False)


def _drop_mixin_indexes(table: str) -> None:
    op.drop_index(f"ix_{table}_created_time", table_name=table)
    op.drop_index(f"ix_{table}_is_deleted", table_name=table)
    op.drop_index(f"ix_{table}_uuid", table_name=table)
    op.drop_index(f"ix_{table}_id", table_name=table)


def upgrade() -> None:
    op.create_table(
        "genbi_group_datasource",
        sa.Column("group_id", sa.Integer(), nullable=False, comment="MCP 组ID"),
        sa.Column("datasource_id", sa.Integer(), nullable=False, comment="数据源ID"),
        sa.Column("external_name", sa.String(length=512), nullable=False, comment="对外工具名（别名）"),
        sa.Column("enabled", sa.Boolean(), nullable=False, comment="是否启用"),
        *_mixin_columns(),
        sa.ForeignKeyConstraint(
            ["group_id"],
            ["mcp_group.id"],
            name="fk_genbi_group_datasource_group_id_mcp_group",
            ondelete="CASCADE",
            onupdate="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["datasource_id"],
            ["genbi_datasource.id"],
            name="fk_genbi_group_datasource_datasource_id_genbi_datasource",
            ondelete="CASCADE",
            onupdate="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_genbi_group_datasource"),
        sa.UniqueConstraint(
            "group_id",
            "datasource_id",
            name="uq_genbi_group_datasource_group_datasource",
        ),
        sa.UniqueConstraint(
            "group_id",
            "external_name",
            name="uq_genbi_group_datasource_group_external_name",
        ),
        comment="MCP 组–GenBI 数据源关联",
    )
    _mixin_indexes("genbi_group_datasource")
    op.create_index(
        "ix_genbi_group_datasource_group_id", "genbi_group_datasource", ["group_id"], unique=False
    )
    op.create_index(
        "ix_genbi_group_datasource_datasource_id",
        "genbi_group_datasource",
        ["datasource_id"],
        unique=False,
    )
    op.create_index(
        "ix_genbi_group_datasource_external_name",
        "genbi_group_datasource",
        ["external_name"],
        unique=False,
    )

    op.create_table(
        "genbi_group_datasource_acl_row",
        sa.Column("group_datasource_id", sa.Integer(), nullable=False, comment="组–数据源关联ID"),
        sa.Column("model_id", sa.Integer(), nullable=False, comment="MDL 模型ID"),
        sa.Column("column_id", sa.Integer(), nullable=False, comment="MDL 列ID"),
        sa.Column("operator", sa.String(length=32), nullable=False, comment="运算符"),
        sa.Column("values", sa.JSON(), nullable=False, comment="比较值列表"),
        sa.Column("propagate", sa.Boolean(), nullable=False, comment="是否传播"),
        sa.Column("propagate_to_model_ids", sa.JSON(), nullable=False, comment="传播目标模型ID"),
        *_mixin_columns(),
        sa.ForeignKeyConstraint(
            ["group_datasource_id"],
            ["genbi_group_datasource.id"],
            name="fk_genbi_gds_acl_row_group_datasource_id_genbi_group_datasource",
            ondelete="CASCADE",
            onupdate="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_genbi_group_datasource_acl_row"),
        comment="组×源行级 ACL",
    )
    _mixin_indexes("genbi_group_datasource_acl_row")
    op.create_index(
        "ix_genbi_group_datasource_acl_row_group_datasource_id",
        "genbi_group_datasource_acl_row",
        ["group_datasource_id"],
        unique=False,
    )
    op.create_index(
        "ix_genbi_group_datasource_acl_row_model_id",
        "genbi_group_datasource_acl_row",
        ["model_id"],
        unique=False,
    )
    op.create_index(
        "ix_genbi_group_datasource_acl_row_column_id",
        "genbi_group_datasource_acl_row",
        ["column_id"],
        unique=False,
    )

    op.create_table(
        "genbi_group_datasource_acl_column",
        sa.Column("group_datasource_id", sa.Integer(), nullable=False, comment="组–数据源关联ID"),
        sa.Column("model_id", sa.Integer(), nullable=False, comment="MDL 模型ID"),
        sa.Column("column_id", sa.Integer(), nullable=False, comment="MDL 列ID"),
        sa.Column("action", sa.String(length=32), nullable=False, comment="动作 mask/deny"),
        sa.Column("mask_template", sa.String(length=64), nullable=True, comment="掩码模板"),
        *_mixin_columns(),
        sa.ForeignKeyConstraint(
            ["group_datasource_id"],
            ["genbi_group_datasource.id"],
            name="fk_genbi_gds_acl_col_group_datasource_id_genbi_group_datasource",
            ondelete="CASCADE",
            onupdate="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_genbi_group_datasource_acl_column"),
        sa.UniqueConstraint(
            "group_datasource_id",
            "model_id",
            "column_id",
            name="uq_genbi_gds_acl_column_link_model_column",
        ),
        comment="组×源列级 ACL",
    )
    _mixin_indexes("genbi_group_datasource_acl_column")
    op.create_index(
        "ix_genbi_group_datasource_acl_column_group_datasource_id",
        "genbi_group_datasource_acl_column",
        ["group_datasource_id"],
        unique=False,
    )
    op.create_index(
        "ix_genbi_group_datasource_acl_column_model_id",
        "genbi_group_datasource_acl_column",
        ["model_id"],
        unique=False,
    )
    op.create_index(
        "ix_genbi_group_datasource_acl_column_column_id",
        "genbi_group_datasource_acl_column",
        ["column_id"],
        unique=False,
    )


def downgrade() -> None:
    for table in (
        "genbi_group_datasource_acl_column",
        "genbi_group_datasource_acl_row",
        "genbi_group_datasource",
    ):
        if table == "genbi_group_datasource_acl_column":
            op.drop_index(
                "ix_genbi_group_datasource_acl_column_column_id",
                table_name=table,
            )
            op.drop_index(
                "ix_genbi_group_datasource_acl_column_model_id",
                table_name=table,
            )
            op.drop_index(
                "ix_genbi_group_datasource_acl_column_group_datasource_id",
                table_name=table,
            )
        elif table == "genbi_group_datasource_acl_row":
            op.drop_index(
                "ix_genbi_group_datasource_acl_row_column_id",
                table_name=table,
            )
            op.drop_index(
                "ix_genbi_group_datasource_acl_row_model_id",
                table_name=table,
            )
            op.drop_index(
                "ix_genbi_group_datasource_acl_row_group_datasource_id",
                table_name=table,
            )
        else:
            op.drop_index("ix_genbi_group_datasource_external_name", table_name=table)
            op.drop_index("ix_genbi_group_datasource_datasource_id", table_name=table)
            op.drop_index("ix_genbi_group_datasource_group_id", table_name=table)
        _drop_mixin_indexes(table)
        op.drop_table(table)
