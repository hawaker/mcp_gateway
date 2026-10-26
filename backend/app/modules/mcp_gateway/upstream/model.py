from sqlalchemy import JSON, Boolean, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.base_model import ModelMixin


class UpstreamMcpModel(ModelMixin):
    """MCP 代理：独立编码，不挂业务系统。调用用保存的一份静态凭证。"""

    __tablename__: str = "mcp_upstream_mcp"
    __table_args__: dict[str, str] = {"comment": "MCP 代理表"}

    name: Mapped[str] = mapped_column(String(128), nullable=False, index=True, comment="名称")
    code: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True, comment="英文编码")
    url: Mapped[str] = mapped_column(String(2048), nullable=False, comment="上游地址")
    credential_header: Mapped[str] = mapped_column(String(128), nullable=False, comment="凭证请求头")
    credential_value_encrypted: Mapped[str] = mapped_column(Text, nullable=False, comment="凭证密文")


class UpstreamToolModel(ModelMixin):
    """MCP 代理暴露的一个工具。selected 只由管理员显式修改。"""

    __tablename__: str = "mcp_upstream_tool"
    __table_args__ = (
        UniqueConstraint(
            "upstream_id",
            "remote_name",
            name="uq_mcp_upstream_tool_upstream_id_remote_name",
        ),
        {"comment": "MCP 代理工具表"},
    )

    upstream_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("mcp_upstream_mcp.id", ondelete="CASCADE", onupdate="CASCADE"),
        nullable=False,
        index=True,
        comment="MCP 代理 ID",
    )
    remote_name: Mapped[str] = mapped_column(String(512), nullable=False, index=True, comment="远端工具名")
    external_name: Mapped[str] = mapped_column(String(512), nullable=False, index=True, comment="外部名称")
    input_schema: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict, comment="入参结构")
    selected: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, comment="是否选用")
