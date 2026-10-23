from sqlalchemy import Boolean, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.base_model import ModelMixin


class SmtpConfigModel(ModelMixin):
    """唯一一条 SMTP 配置。密码只存密文。"""

    __tablename__: str = "mcp_smtp_config"
    __table_args__: dict[str, str] = {"comment": "SMTP 配置表"}

    enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, comment="是否启用")
    host: Mapped[str] = mapped_column(String(255), nullable=False, comment="SMTP 主机")
    port: Mapped[int] = mapped_column(Integer, nullable=False, comment="端口")
    username: Mapped[str | None] = mapped_column(String(128), nullable=True, comment="账号")
    password_encrypted: Mapped[str] = mapped_column(Text, nullable=False, comment="密码密文")
    from_address: Mapped[str] = mapped_column(String(255), nullable=False, comment="发件人地址")
    from_name: Mapped[str | None] = mapped_column(String(128), nullable=True, comment="发件人名称")
    encryption: Mapped[str] = mapped_column(String(16), nullable=False, comment="加密方式")
