"""GenBI 项目与 MDL 元数据表（对齐 tiga genbi，按数据源归属）。"""

from datetime import datetime
from typing import Any

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.base_model import JSONType, ModelMixin

# Soft-delete 友好：仅未删除行参与唯一约束（PostgreSQL / SQLite 部分唯一索引）。
_ACTIVE_ROW = text("is_deleted = false")


class GenbiProjectModel(ModelMixin):
    """GenBI 项目。与数据源 1:1；可选冗余 system_id。"""

    __tablename__: str = "genbi_project"
    __table_args__ = (
        Index(
            "uq_genbi_project_datasource_id",
            "datasource_id",
            unique=True,
            postgresql_where=_ACTIVE_ROW,
            sqlite_where=_ACTIVE_ROW,
        ),
        {"comment": "GenBI 项目表"},
    )

    datasource_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("genbi_datasource.id", ondelete="CASCADE", onupdate="CASCADE"),
        nullable=False,
        index=True,
        comment="数据源ID（一源一项目）",
    )
    system_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("mcp_biz_system.id", ondelete="SET NULL", onupdate="CASCADE"),
        nullable=True,
        index=True,
        comment="业务系统ID（可自数据源冗余）",
    )
    display_name: Mapped[str] = mapped_column(String(255), nullable=False, comment="显示名称")
    onboarding_status: Mapped[str] = mapped_column(
        String(64), nullable=False, default="not_started", comment="入驻状态"
    )
    language: Mapped[str] = mapped_column(String(16), nullable=False, default="zh-CN", comment="语言")
    agent_profile: Mapped[dict] = mapped_column(
        JSONType, nullable=False, default=dict, comment="Agent 配置"
    )

    models = relationship(
        "GenbiModelModel",
        back_populates="project",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    relationships = relationship(
        "GenbiRelationshipModel",
        back_populates="project",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    views = relationship(
        "GenbiViewModel",
        back_populates="project",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    metrics = relationship(
        "GenbiMetricModel",
        back_populates="project",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    deploy_logs = relationship(
        "GenbiDeployLogModel",
        back_populates="project",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    instructions = relationship(
        "GenbiInstructionModel",
        back_populates="project",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    metric_docs = relationship(
        "GenbiMetricDocModel",
        back_populates="project",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    sql_pairs = relationship(
        "GenbiSqlPairModel",
        back_populates="project",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class GenbiModelModel(ModelMixin):
    """MDL 模型（表）。"""

    __tablename__: str = "genbi_model"
    __table_args__: dict[str, str] = {"comment": "GenBI MDL 模型表"}

    project_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("genbi_project.id", ondelete="CASCADE", onupdate="CASCADE"),
        nullable=False,
        index=True,
        comment="项目ID",
    )
    display_name: Mapped[str] = mapped_column(String(255), nullable=False, comment="显示名称")
    source_table_name: Mapped[str] = mapped_column(String(512), nullable=False, comment="源表名")
    reference_name: Mapped[str] = mapped_column(String(255), nullable=False, comment="引用名")
    ref_sql: Mapped[str | None] = mapped_column(Text, nullable=True, comment="引用 SQL")
    cached: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, comment="是否缓存")
    refresh_time: Mapped[str | None] = mapped_column(String(64), nullable=True, comment="刷新时间")
    properties: Mapped[dict | None] = mapped_column(JSONType, nullable=True, comment="扩展属性")

    project = relationship("GenbiProjectModel", back_populates="models")
    columns = relationship(
        "GenbiModelColumnModel",
        back_populates="model",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class GenbiModelColumnModel(ModelMixin):
    """MDL 模型列。"""

    __tablename__: str = "genbi_model_column"
    __table_args__: dict[str, str] = {"comment": "GenBI MDL 模型列表"}

    model_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("genbi_model.id", ondelete="CASCADE", onupdate="CASCADE"),
        nullable=False,
        index=True,
        comment="模型ID",
    )
    display_name: Mapped[str] = mapped_column(String(255), nullable=False, comment="显示名称")
    source_column_name: Mapped[str] = mapped_column(String(512), nullable=False, comment="源列名")
    column_type: Mapped[str | None] = mapped_column(String(128), nullable=True, comment="列类型")
    is_calculated: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False, comment="是否计算列"
    )
    expression: Mapped[str | None] = mapped_column(Text, nullable=True, comment="计算表达式")
    properties: Mapped[dict | None] = mapped_column(JSONType, nullable=True, comment="扩展属性")

    model = relationship("GenbiModelModel", back_populates="columns")


class GenbiRelationshipModel(ModelMixin):
    """MDL 模型关系。"""

    __tablename__: str = "genbi_relationship"
    __table_args__: dict[str, str] = {"comment": "GenBI MDL 关系表"}

    project_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("genbi_project.id", ondelete="CASCADE", onupdate="CASCADE"),
        nullable=False,
        index=True,
        comment="项目ID",
    )
    from_model_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("genbi_model.id", ondelete="CASCADE", onupdate="CASCADE"),
        nullable=False,
        comment="源模型ID",
    )
    to_model_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("genbi_model.id", ondelete="CASCADE", onupdate="CASCADE"),
        nullable=False,
        comment="目标模型ID",
    )
    join_type: Mapped[str | None] = mapped_column(String(32), nullable=True, comment="连接类型")
    condition: Mapped[str | None] = mapped_column(Text, nullable=True, comment="连接条件")
    properties: Mapped[dict | None] = mapped_column(JSONType, nullable=True, comment="扩展属性")

    project = relationship("GenbiProjectModel", back_populates="relationships")


class GenbiViewModel(ModelMixin):
    """MDL 视图。"""

    __tablename__: str = "genbi_view"
    __table_args__ = (
        Index(
            "uq_genbi_view_project_id_name",
            "project_id",
            "name",
            unique=True,
            postgresql_where=_ACTIVE_ROW,
            sqlite_where=_ACTIVE_ROW,
        ),
        {"comment": "GenBI MDL 视图表"},
    )

    project_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("genbi_project.id", ondelete="CASCADE", onupdate="CASCADE"),
        nullable=False,
        index=True,
        comment="项目ID",
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False, comment="视图名")
    statement: Mapped[str] = mapped_column(Text, nullable=False, comment="视图 SQL")
    properties: Mapped[dict | None] = mapped_column(JSONType, nullable=True, comment="扩展属性")

    project = relationship("GenbiProjectModel", back_populates="views")


class GenbiMetricModel(ModelMixin):
    """MDL 指标。"""

    __tablename__: str = "genbi_metric"
    __table_args__ = (
        Index(
            "uq_genbi_metric_project_id_name",
            "project_id",
            "name",
            unique=True,
            postgresql_where=_ACTIVE_ROW,
            sqlite_where=_ACTIVE_ROW,
        ),
        {"comment": "GenBI MDL 指标表"},
    )

    project_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("genbi_project.id", ondelete="CASCADE", onupdate="CASCADE"),
        nullable=False,
        index=True,
        comment="项目ID",
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False, comment="指标名")
    base_model_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("genbi_model.id", ondelete="CASCADE", onupdate="CASCADE"),
        nullable=False,
        index=True,
        comment="基础模型ID",
    )
    properties: Mapped[dict | None] = mapped_column(JSONType, nullable=True, comment="扩展属性")

    project = relationship("GenbiProjectModel", back_populates="metrics")
    measures = relationship(
        "GenbiMetricMeasureModel",
        back_populates="metric",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class GenbiMetricMeasureModel(ModelMixin):
    """MDL 指标度量。"""

    __tablename__: str = "genbi_metric_measure"
    __table_args__: dict[str, str] = {"comment": "GenBI MDL 指标度量表"}

    metric_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("genbi_metric.id", ondelete="CASCADE", onupdate="CASCADE"),
        nullable=False,
        index=True,
        comment="指标ID",
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False, comment="度量名")
    kind: Mapped[str] = mapped_column(String(16), nullable=False, default="measure", comment="种类")
    column_type: Mapped[str | None] = mapped_column(String(128), nullable=True, comment="列类型")
    expression: Mapped[str | None] = mapped_column(Text, nullable=True, comment="表达式")

    metric = relationship("GenbiMetricModel", back_populates="measures")


class GenbiDeployLogModel(ModelMixin):
    """MDL 部署日志。"""

    __tablename__: str = "genbi_deploy_log"
    __table_args__: dict[str, str] = {"comment": "GenBI MDL 部署日志表"}

    project_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("genbi_project.id", ondelete="CASCADE", onupdate="CASCADE"),
        nullable=False,
        index=True,
        comment="项目ID",
    )
    mdl_hash: Mapped[str | None] = mapped_column(
        String(128), nullable=True, index=True, comment="MDL 哈希"
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending", comment="状态")
    stage: Mapped[str | None] = mapped_column(String(32), nullable=True, comment="阶段")
    smoke_report: Mapped[dict | None] = mapped_column(JSONType, nullable=True, comment="冒烟报告")
    error: Mapped[str | None] = mapped_column(Text, nullable=True, comment="错误信息")
    deployed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, comment="部署时间"
    )

    project = relationship("GenbiProjectModel", back_populates="deploy_logs")


class GenbiInstructionModel(ModelMixin):
    """问数指令（知识库）。字段名对齐 tiga genbi_instructions。"""

    __tablename__: str = "genbi_instruction"
    __table_args__: dict[str, str] = {"comment": "GenBI 问数指令表"}

    project_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("genbi_project.id", ondelete="CASCADE", onupdate="CASCADE"),
        nullable=False,
        index=True,
        comment="项目ID",
    )
    instruction: Mapped[str] = mapped_column(Text, nullable=False, comment="指令正文")
    questions: Mapped[list[Any] | None] = mapped_column(JSONType, nullable=True, comment="关联问题列表")
    is_default: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, comment="是否默认")

    project = relationship("GenbiProjectModel", back_populates="instructions")


class GenbiMetricDocModel(ModelMixin):
    """指标文档（知识库）。字段名对齐 tiga genbi_metric_docs。"""

    __tablename__: str = "genbi_metric_doc"
    __table_args__: dict[str, str] = {"comment": "GenBI 指标文档表"}

    project_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("genbi_project.id", ondelete="CASCADE", onupdate="CASCADE"),
        nullable=False,
        index=True,
        comment="项目ID",
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False, comment="文档名")
    content: Mapped[str] = mapped_column(Text, nullable=False, comment="文档内容")
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, comment="是否启用")

    project = relationship("GenbiProjectModel", back_populates="metric_docs")


class GenbiSqlPairModel(ModelMixin):
    """SQL 问答对（知识库）。字段名对齐 tiga genbi_sql_pairs。"""

    __tablename__: str = "genbi_sql_pair"
    __table_args__: dict[str, str] = {"comment": "GenBI SQL 问答对表"}

    project_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("genbi_project.id", ondelete="CASCADE", onupdate="CASCADE"),
        nullable=False,
        index=True,
        comment="项目ID",
    )
    question: Mapped[str] = mapped_column(Text, nullable=False, comment="问题")
    sql: Mapped[str] = mapped_column(Text, nullable=False, comment="SQL")
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, comment="是否启用")

    project = relationship("GenbiProjectModel", back_populates="sql_pairs")
