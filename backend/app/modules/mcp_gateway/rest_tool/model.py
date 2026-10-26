from sqlalchemy import JSON, Boolean, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.base_model import ModelMixin


class RestToolModel(ModelMixin):
    """挂在业务系统上的一条 REST 工具。"""

    __tablename__: str = "mcp_rest_tool"
    __table_args__: dict[str, str] = {"comment": "REST 工具表"}

    name: Mapped[str] = mapped_column(String(128), nullable=False, index=True, comment="名称")
    display_name: Mapped[str] = mapped_column(String(128), nullable=False, comment="显示名")
    url: Mapped[str] = mapped_column(String(2048), nullable=False, comment="接口地址")
    description: Mapped[str | None] = mapped_column(String(1024), nullable=True, comment="描述")
    request_type: Mapped[str] = mapped_column(String(16), nullable=False, default="GET", comment="请求方法")
    headers: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict, comment="请求头")
    input_schema: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict, comment="入参结构")
    output_schema: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict, comment="出参结构")
    jsonpath_filter: Mapped[str | None] = mapped_column(String(512), nullable=True, comment="Json Path Filter")
    query_mapping: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict, comment="Query 映射")
    header_mapping: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict, comment="Header 映射")
    timeout_ms: Mapped[int | None] = mapped_column(Integer, nullable=True, comment="超时毫秒")
    token_in: Mapped[str] = mapped_column(String(16), nullable=False, default="header", comment="token 位置")
    token_name: Mapped[str | None] = mapped_column(String(128), nullable=True, comment="token 字段名")
    token_var: Mapped[str | None] = mapped_column(String(128), nullable=True, comment="注入的 auth 变量名")
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, comment="是否启用")
    system_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("mcp_biz_system.id", ondelete="CASCADE", onupdate="CASCADE"),
        nullable=False,
        index=True,
        comment="业务系统ID",
    )
