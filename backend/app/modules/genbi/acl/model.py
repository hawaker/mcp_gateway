"""组–数据源关联与行/列 ACL。规则挂在关联上，组内全体成员共用；无成员表。"""

from sqlalchemy import Boolean, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.base_model import JSONType, ModelMixin


class GenbiGroupDatasourceModel(ModelMixin):
    """MCP 组勾选的一个 GenBI 数据源。对外名组内唯一。"""

    __tablename__: str = "genbi_group_datasource"
    __table_args__ = (
        UniqueConstraint(
            "group_id",
            "datasource_id",
            name="uq_genbi_group_datasource_group_datasource",
        ),
        UniqueConstraint(
            "group_id",
            "external_name",
            name="uq_genbi_group_datasource_group_external_name",
        ),
        {"comment": "MCP 组–GenBI 数据源关联"},
    )

    group_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("mcp_group.id", ondelete="CASCADE", onupdate="CASCADE"),
        nullable=False,
        index=True,
        comment="MCP 组ID",
    )
    datasource_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("genbi_datasource.id", ondelete="CASCADE", onupdate="CASCADE"),
        nullable=False,
        index=True,
        comment="数据源ID",
    )
    external_name: Mapped[str] = mapped_column(
        String(512), nullable=False, index=True, comment="对外工具名（别名）"
    )
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, comment="是否启用")

    row_policies = relationship(
        "GenbiGroupDatasourceAclRowModel",
        back_populates="group_datasource",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    column_policies = relationship(
        "GenbiGroupDatasourceAclColumnModel",
        back_populates="group_datasource",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class GenbiGroupDatasourceAclRowModel(ModelMixin):
    """组×源行级 ACL。字段形态对齐 tiga GenbiAclRowPolicy；无成员。"""

    __tablename__: str = "genbi_group_datasource_acl_row"
    __table_args__: dict[str, str] = {"comment": "组×源行级 ACL"}

    group_datasource_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("genbi_group_datasource.id", ondelete="CASCADE", onupdate="CASCADE"),
        nullable=False,
        index=True,
        comment="组–数据源关联ID",
    )
    model_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True, comment="MDL 模型ID")
    column_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True, comment="MDL 列ID")
    operator: Mapped[str] = mapped_column(String(32), nullable=False, comment="运算符")
    values: Mapped[list] = mapped_column(JSONType, nullable=False, comment="比较值列表")
    propagate: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, comment="是否传播")
    propagate_to_model_ids: Mapped[list] = mapped_column(
        JSONType, nullable=False, default=list, comment="传播目标模型ID"
    )

    group_datasource = relationship("GenbiGroupDatasourceModel", back_populates="row_policies")


class GenbiGroupDatasourceAclColumnModel(ModelMixin):
    """组×源列级 ACL。mask/deny；无成员。"""

    __tablename__: str = "genbi_group_datasource_acl_column"
    __table_args__ = (
        UniqueConstraint(
            "group_datasource_id",
            "model_id",
            "column_id",
            name="uq_genbi_gds_acl_column_link_model_column",
        ),
        {"comment": "组×源列级 ACL"},
    )

    group_datasource_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("genbi_group_datasource.id", ondelete="CASCADE", onupdate="CASCADE"),
        nullable=False,
        index=True,
        comment="组–数据源关联ID",
    )
    model_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True, comment="MDL 模型ID")
    column_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True, comment="MDL 列ID")
    action: Mapped[str] = mapped_column(String(32), nullable=False, comment="动作 mask/deny")
    mask_template: Mapped[str | None] = mapped_column(String(64), nullable=True, comment="掩码模板")

    group_datasource = relationship("GenbiGroupDatasourceModel", back_populates="column_policies")
