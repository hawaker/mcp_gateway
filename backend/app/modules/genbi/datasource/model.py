from sqlalchemy import Boolean, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.base_model import JSONType, ModelMixin


class GenbiDatasourceModel(ModelMixin):
    """GenBI 数据源。归属业务系统；密钥只存密文。"""

    __tablename__: str = "genbi_datasource"
    __table_args__: dict[str, str] = {"comment": "GenBI 数据源表"}

    system_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("mcp_biz_system.id", ondelete="CASCADE", onupdate="CASCADE"),
        nullable=False,
        index=True,
        comment="业务系统ID",
    )
    name: Mapped[str] = mapped_column(String(128), nullable=False, index=True, comment="名称")
    wren_type: Mapped[str] = mapped_column(String(32), nullable=False, comment="Wren 数据源类型")
    host: Mapped[str | None] = mapped_column(String(255), nullable=True, comment="主机")
    port: Mapped[int | None] = mapped_column(Integer, nullable=True, comment="端口")
    username: Mapped[str | None] = mapped_column(String(128), nullable=True, comment="用户名")
    password_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True, comment="密码密文")
    database: Mapped[str | None] = mapped_column(String(128), nullable=True, comment="数据库名")
    db_schema: Mapped[str | None] = mapped_column(String(128), nullable=True, comment="Schema")
    url: Mapped[str | None] = mapped_column(String(1024), nullable=True, comment="连接 URL")
    api_key_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True, comment="API Key 密文")
    private_key_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True, comment="私钥密文")
    token_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True, comment="Token 密文")
    config: Mapped[dict] = mapped_column(JSONType, nullable=False, default=dict, comment="扩展配置")
    description: Mapped[str | None] = mapped_column(String(512), nullable=True, comment="描述")
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, comment="是否启用")
