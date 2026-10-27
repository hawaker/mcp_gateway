"""genbi project and MDL metadata tables

Revision ID: b8c4d2e91a05
Revises: a7f3e91c2b04
Create Date: 2026-10-27 11:26:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "b8c4d2e91a05"
down_revision: str | None = "a7f3e91c2b04"
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
        "genbi_project",
        sa.Column("datasource_id", sa.Integer(), nullable=False, comment="数据源ID（一源一项目）"),
        sa.Column("system_id", sa.Integer(), nullable=True, comment="业务系统ID（可自数据源冗余）"),
        sa.Column("display_name", sa.String(length=255), nullable=False, comment="显示名称"),
        sa.Column("onboarding_status", sa.String(length=64), nullable=False, comment="入驻状态"),
        sa.Column("language", sa.String(length=16), nullable=False, comment="语言"),
        sa.Column("agent_profile", sa.JSON(), nullable=False, comment="Agent 配置"),
        *_mixin_columns(),
        sa.ForeignKeyConstraint(
            ["datasource_id"],
            ["genbi_datasource.id"],
            name="fk_genbi_project_datasource_id_genbi_datasource",
            ondelete="CASCADE",
            onupdate="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["system_id"],
            ["mcp_biz_system.id"],
            name="fk_genbi_project_system_id_mcp_biz_system",
            ondelete="SET NULL",
            onupdate="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_genbi_project"),
        sa.UniqueConstraint("datasource_id", name="uq_genbi_project_datasource_id"),
        comment="GenBI 项目表",
    )
    op.create_index("ix_genbi_project_datasource_id", "genbi_project", ["datasource_id"], unique=False)
    op.create_index("ix_genbi_project_system_id", "genbi_project", ["system_id"], unique=False)
    _mixin_indexes("genbi_project")

    op.create_table(
        "genbi_model",
        sa.Column("project_id", sa.Integer(), nullable=False, comment="项目ID"),
        sa.Column("display_name", sa.String(length=255), nullable=False, comment="显示名称"),
        sa.Column("source_table_name", sa.String(length=512), nullable=False, comment="源表名"),
        sa.Column("reference_name", sa.String(length=255), nullable=False, comment="引用名"),
        sa.Column("ref_sql", sa.Text(), nullable=True, comment="引用 SQL"),
        sa.Column("cached", sa.Boolean(), nullable=False, comment="是否缓存"),
        sa.Column("refresh_time", sa.String(length=64), nullable=True, comment="刷新时间"),
        sa.Column("properties", sa.JSON(), nullable=True, comment="扩展属性"),
        *_mixin_columns(),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["genbi_project.id"],
            name="fk_genbi_model_project_id_genbi_project",
            ondelete="CASCADE",
            onupdate="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_genbi_model"),
        comment="GenBI MDL 模型表",
    )
    op.create_index("ix_genbi_model_project_id", "genbi_model", ["project_id"], unique=False)
    _mixin_indexes("genbi_model")

    op.create_table(
        "genbi_model_column",
        sa.Column("model_id", sa.Integer(), nullable=False, comment="模型ID"),
        sa.Column("display_name", sa.String(length=255), nullable=False, comment="显示名称"),
        sa.Column("source_column_name", sa.String(length=512), nullable=False, comment="源列名"),
        sa.Column("column_type", sa.String(length=128), nullable=True, comment="列类型"),
        sa.Column("is_calculated", sa.Boolean(), nullable=False, comment="是否计算列"),
        sa.Column("expression", sa.Text(), nullable=True, comment="计算表达式"),
        sa.Column("properties", sa.JSON(), nullable=True, comment="扩展属性"),
        *_mixin_columns(),
        sa.ForeignKeyConstraint(
            ["model_id"],
            ["genbi_model.id"],
            name="fk_genbi_model_column_model_id_genbi_model",
            ondelete="CASCADE",
            onupdate="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_genbi_model_column"),
        comment="GenBI MDL 模型列表",
    )
    op.create_index("ix_genbi_model_column_model_id", "genbi_model_column", ["model_id"], unique=False)
    _mixin_indexes("genbi_model_column")

    op.create_table(
        "genbi_relationship",
        sa.Column("project_id", sa.Integer(), nullable=False, comment="项目ID"),
        sa.Column("from_model_id", sa.Integer(), nullable=False, comment="源模型ID"),
        sa.Column("to_model_id", sa.Integer(), nullable=False, comment="目标模型ID"),
        sa.Column("join_type", sa.String(length=32), nullable=True, comment="连接类型"),
        sa.Column("condition", sa.Text(), nullable=True, comment="连接条件"),
        sa.Column("properties", sa.JSON(), nullable=True, comment="扩展属性"),
        *_mixin_columns(),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["genbi_project.id"],
            name="fk_genbi_relationship_project_id_genbi_project",
            ondelete="CASCADE",
            onupdate="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["from_model_id"],
            ["genbi_model.id"],
            name="fk_genbi_relationship_from_model_id_genbi_model",
            ondelete="CASCADE",
            onupdate="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["to_model_id"],
            ["genbi_model.id"],
            name="fk_genbi_relationship_to_model_id_genbi_model",
            ondelete="CASCADE",
            onupdate="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_genbi_relationship"),
        comment="GenBI MDL 关系表",
    )
    op.create_index("ix_genbi_relationship_project_id", "genbi_relationship", ["project_id"], unique=False)
    _mixin_indexes("genbi_relationship")

    op.create_table(
        "genbi_view",
        sa.Column("project_id", sa.Integer(), nullable=False, comment="项目ID"),
        sa.Column("name", sa.String(length=255), nullable=False, comment="视图名"),
        sa.Column("statement", sa.Text(), nullable=False, comment="视图 SQL"),
        sa.Column("properties", sa.JSON(), nullable=True, comment="扩展属性"),
        *_mixin_columns(),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["genbi_project.id"],
            name="fk_genbi_view_project_id_genbi_project",
            ondelete="CASCADE",
            onupdate="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_genbi_view"),
        sa.UniqueConstraint("project_id", "name", name="uq_genbi_view_project_id_name"),
        comment="GenBI MDL 视图表",
    )
    op.create_index("ix_genbi_view_project_id", "genbi_view", ["project_id"], unique=False)
    _mixin_indexes("genbi_view")

    op.create_table(
        "genbi_metric",
        sa.Column("project_id", sa.Integer(), nullable=False, comment="项目ID"),
        sa.Column("name", sa.String(length=255), nullable=False, comment="指标名"),
        sa.Column("base_model_id", sa.Integer(), nullable=False, comment="基础模型ID"),
        sa.Column("properties", sa.JSON(), nullable=True, comment="扩展属性"),
        *_mixin_columns(),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["genbi_project.id"],
            name="fk_genbi_metric_project_id_genbi_project",
            ondelete="CASCADE",
            onupdate="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["base_model_id"],
            ["genbi_model.id"],
            name="fk_genbi_metric_base_model_id_genbi_model",
            ondelete="CASCADE",
            onupdate="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_genbi_metric"),
        sa.UniqueConstraint("project_id", "name", name="uq_genbi_metric_project_id_name"),
        comment="GenBI MDL 指标表",
    )
    op.create_index("ix_genbi_metric_project_id", "genbi_metric", ["project_id"], unique=False)
    op.create_index("ix_genbi_metric_base_model_id", "genbi_metric", ["base_model_id"], unique=False)
    _mixin_indexes("genbi_metric")

    op.create_table(
        "genbi_metric_measure",
        sa.Column("metric_id", sa.Integer(), nullable=False, comment="指标ID"),
        sa.Column("name", sa.String(length=255), nullable=False, comment="度量名"),
        sa.Column("kind", sa.String(length=16), nullable=False, comment="种类"),
        sa.Column("column_type", sa.String(length=128), nullable=True, comment="列类型"),
        sa.Column("expression", sa.Text(), nullable=True, comment="表达式"),
        *_mixin_columns(),
        sa.ForeignKeyConstraint(
            ["metric_id"],
            ["genbi_metric.id"],
            name="fk_genbi_metric_measure_metric_id_genbi_metric",
            ondelete="CASCADE",
            onupdate="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_genbi_metric_measure"),
        comment="GenBI MDL 指标度量表",
    )
    op.create_index("ix_genbi_metric_measure_metric_id", "genbi_metric_measure", ["metric_id"], unique=False)
    _mixin_indexes("genbi_metric_measure")

    op.create_table(
        "genbi_deploy_log",
        sa.Column("project_id", sa.Integer(), nullable=False, comment="项目ID"),
        sa.Column("mdl_hash", sa.String(length=128), nullable=True, comment="MDL 哈希"),
        sa.Column("status", sa.String(length=32), nullable=False, comment="状态"),
        sa.Column("stage", sa.String(length=32), nullable=True, comment="阶段"),
        sa.Column("smoke_report", sa.JSON(), nullable=True, comment="冒烟报告"),
        sa.Column("error", sa.Text(), nullable=True, comment="错误信息"),
        sa.Column("deployed_at", sa.DateTime(timezone=True), nullable=True, comment="部署时间"),
        *_mixin_columns(),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["genbi_project.id"],
            name="fk_genbi_deploy_log_project_id_genbi_project",
            ondelete="CASCADE",
            onupdate="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_genbi_deploy_log"),
        comment="GenBI MDL 部署日志表",
    )
    op.create_index("ix_genbi_deploy_log_project_id", "genbi_deploy_log", ["project_id"], unique=False)
    op.create_index("ix_genbi_deploy_log_mdl_hash", "genbi_deploy_log", ["mdl_hash"], unique=False)
    _mixin_indexes("genbi_deploy_log")


def downgrade() -> None:
    for table in (
        "genbi_deploy_log",
        "genbi_metric_measure",
        "genbi_metric",
        "genbi_view",
        "genbi_relationship",
        "genbi_model_column",
        "genbi_model",
        "genbi_project",
    ):
        if table == "genbi_deploy_log":
            op.drop_index("ix_genbi_deploy_log_mdl_hash", table_name=table)
            op.drop_index("ix_genbi_deploy_log_project_id", table_name=table)
        elif table == "genbi_metric_measure":
            op.drop_index("ix_genbi_metric_measure_metric_id", table_name=table)
        elif table == "genbi_metric":
            op.drop_index("ix_genbi_metric_base_model_id", table_name=table)
            op.drop_index("ix_genbi_metric_project_id", table_name=table)
        elif table == "genbi_view":
            op.drop_index("ix_genbi_view_project_id", table_name=table)
        elif table == "genbi_relationship":
            op.drop_index("ix_genbi_relationship_project_id", table_name=table)
        elif table == "genbi_model_column":
            op.drop_index("ix_genbi_model_column_model_id", table_name=table)
        elif table == "genbi_model":
            op.drop_index("ix_genbi_model_project_id", table_name=table)
        elif table == "genbi_project":
            op.drop_index("ix_genbi_project_system_id", table_name=table)
            op.drop_index("ix_genbi_project_datasource_id", table_name=table)
        _drop_mixin_indexes(table)
        op.drop_table(table)
