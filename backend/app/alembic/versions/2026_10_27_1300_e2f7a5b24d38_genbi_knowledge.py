"""genbi knowledge tables: instruction / metric_doc / sql_pair

Revision ID: e2f7a5b24d38
Revises: d1e6f4a13c27
Create Date: 2026-10-27 13:00:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "e2f7a5b24d38"
down_revision: str | None = "d1e6f4a13c27"
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
        "genbi_instruction",
        sa.Column("project_id", sa.Integer(), nullable=False, comment="项目ID"),
        sa.Column("instruction", sa.Text(), nullable=False, comment="指令正文"),
        sa.Column("questions", sa.JSON(), nullable=True, comment="关联问题列表"),
        sa.Column("is_default", sa.Boolean(), nullable=False, comment="是否默认"),
        *_mixin_columns(),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["genbi_project.id"],
            name="fk_genbi_instruction_project_id_genbi_project",
            ondelete="CASCADE",
            onupdate="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_genbi_instruction"),
        comment="GenBI 问数指令表",
    )
    op.create_index("ix_genbi_instruction_project_id", "genbi_instruction", ["project_id"], unique=False)
    _mixin_indexes("genbi_instruction")

    op.create_table(
        "genbi_metric_doc",
        sa.Column("project_id", sa.Integer(), nullable=False, comment="项目ID"),
        sa.Column("name", sa.String(length=255), nullable=False, comment="文档名"),
        sa.Column("content", sa.Text(), nullable=False, comment="文档内容"),
        sa.Column("enabled", sa.Boolean(), nullable=False, comment="是否启用"),
        *_mixin_columns(),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["genbi_project.id"],
            name="fk_genbi_metric_doc_project_id_genbi_project",
            ondelete="CASCADE",
            onupdate="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_genbi_metric_doc"),
        comment="GenBI 指标文档表",
    )
    op.create_index("ix_genbi_metric_doc_project_id", "genbi_metric_doc", ["project_id"], unique=False)
    _mixin_indexes("genbi_metric_doc")

    op.create_table(
        "genbi_sql_pair",
        sa.Column("project_id", sa.Integer(), nullable=False, comment="项目ID"),
        sa.Column("question", sa.Text(), nullable=False, comment="问题"),
        sa.Column("sql", sa.Text(), nullable=False, comment="SQL"),
        sa.Column("enabled", sa.Boolean(), nullable=False, comment="是否启用"),
        *_mixin_columns(),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["genbi_project.id"],
            name="fk_genbi_sql_pair_project_id_genbi_project",
            ondelete="CASCADE",
            onupdate="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_genbi_sql_pair"),
        comment="GenBI SQL 问答对表",
    )
    op.create_index("ix_genbi_sql_pair_project_id", "genbi_sql_pair", ["project_id"], unique=False)
    _mixin_indexes("genbi_sql_pair")


def downgrade() -> None:
    _drop_mixin_indexes("genbi_sql_pair")
    op.drop_index("ix_genbi_sql_pair_project_id", table_name="genbi_sql_pair")
    op.drop_table("genbi_sql_pair")

    _drop_mixin_indexes("genbi_metric_doc")
    op.drop_index("ix_genbi_metric_doc_project_id", table_name="genbi_metric_doc")
    op.drop_table("genbi_metric_doc")

    _drop_mixin_indexes("genbi_instruction")
    op.drop_index("ix_genbi_instruction_project_id", table_name="genbi_instruction")
    op.drop_table("genbi_instruction")
