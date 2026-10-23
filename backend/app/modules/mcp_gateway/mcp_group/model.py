from sqlalchemy import Boolean, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.base_model import ModelMixin


class McpGroupModel(ModelMixin):
    """对外发布的一个 MCP 组。"""

    __tablename__: str = "mcp_group"
    __table_args__: dict[str, str] = {"comment": "MCP 组表"}

    name: Mapped[str] = mapped_column(String(128), nullable=False, index=True, comment="名称")
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, comment="是否启用")


class McpGroupToolModel(ModelMixin):
    """组内的一条 REST 或上游工具。外部名在组内唯一。没有删除接口。"""

    __tablename__: str = "mcp_group_tool"
    __table_args__ = (
        UniqueConstraint(
            "group_id",
            "external_name",
            name="uq_mcp_group_tool_group_id_external_name",
        ),
        {"comment": "MCP 组工具表"},
    )

    group_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("mcp_group.id", ondelete="CASCADE", onupdate="CASCADE"),
        nullable=False,
        index=True,
        comment="MCP 组ID",
    )
    source: Mapped[str] = mapped_column(String(16), nullable=False, comment="来源")
    source_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True, comment="来源工具ID")
    external_name: Mapped[str] = mapped_column(String(512), nullable=False, index=True, comment="外部名称")
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, comment="是否启用")


class McpGroupMemberModel(ModelMixin):
    """组的成员：一个业务用户，或一个业务用户组。没有删除接口。"""

    __tablename__: str = "mcp_group_member"
    __table_args__ = (
        UniqueConstraint(
            "group_id",
            "principal_type",
            "principal_id",
            name="uq_mcp_group_member_group_principal",
        ),
        {"comment": "MCP 组成员表"},
    )

    group_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("mcp_group.id", ondelete="CASCADE", onupdate="CASCADE"),
        nullable=False,
        index=True,
        comment="MCP 组ID",
    )
    principal_type: Mapped[str] = mapped_column(String(16), nullable=False, comment="主体类型")
    principal_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True, comment="主体ID")
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, comment="是否启用")


class McpCredentialModel(ModelMixin):
    """一个业务用户在一个 MCP 组上的唯一凭证。token_hash 可查询，密文可被管理员解密。"""

    __tablename__: str = "mcp_credential"
    __table_args__ = (
        UniqueConstraint("user_id", "group_id", name="uq_mcp_credential_user_id_group_id"),
        {"comment": "MCP 凭证表"},
    )

    user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("mcp_biz_user.id", ondelete="CASCADE", onupdate="CASCADE"),
        nullable=False,
        index=True,
        comment="业务用户ID",
    )
    group_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("mcp_group.id", ondelete="CASCADE", onupdate="CASCADE"),
        nullable=False,
        index=True,
        comment="MCP 组ID",
    )
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True, comment="令牌哈希")
    token_encrypted: Mapped[str] = mapped_column(Text, nullable=False, comment="令牌密文")
