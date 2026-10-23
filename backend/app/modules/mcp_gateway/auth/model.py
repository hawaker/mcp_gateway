from sqlalchemy import JSON, Boolean, ForeignKey, Index, Integer, String, text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.base_model import ModelMixin


class AuthConfigModel(ModelMixin):
    """业务系统鉴权配置。同一系统同时只有一条启用记录。"""

    __tablename__: str = "mcp_biz_auth_config"
    __table_args__ = (
        Index(
            "uq_mcp_biz_auth_config_one_enabled",
            "system_id",
            unique=True,
            sqlite_where=text("enabled = 1"),
            postgresql_where=text("enabled IS TRUE"),
        ),
        {"comment": "业务鉴权配置表"},
    )

    system_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("mcp_biz_system.id", ondelete="CASCADE", onupdate="CASCADE"),
        nullable=False,
        index=True,
        comment="业务系统ID",
    )
    method: Mapped[str] = mapped_column(String(32), nullable=False, comment="鉴权方法")
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, comment="是否启用")
    url: Mapped[str] = mapped_column(String(512), nullable=False, comment="鉴权地址")
    rule: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict, comment="取值规则")
    http_method: Mapped[str | None] = mapped_column(String(16), nullable=True, comment="HTTP 方法")
    username: Mapped[str | None] = mapped_column(String(128), nullable=True, comment="Basic 用户名")
    password: Mapped[str | None] = mapped_column(String(512), nullable=True, comment="Basic 密码")
