from sqlalchemy import JSON, Boolean, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.base_model import ModelMixin


class BizSystemModel(ModelMixin):
    """MCP 网关业务系统。code 创建后不可修改。"""

    __tablename__: str = "mcp_biz_system"
    __table_args__: dict[str, str] = {"comment": "业务系统表"}

    name: Mapped[str] = mapped_column(String(64), nullable=False, index=True, comment="名称")
    code: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True, comment="系统编码")
    base_url: Mapped[str] = mapped_column(String(512), nullable=False, comment="基础地址")
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, comment="是否启用")
    params: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict, comment="扩展参数")
    uid_field: Mapped[str] = mapped_column(String(64), nullable=False, comment="用户标识字段")
    attr_fields: Mapped[list] = mapped_column(JSON, nullable=False, default=list, comment="允许的绑定属性")
