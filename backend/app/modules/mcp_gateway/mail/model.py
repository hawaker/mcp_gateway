from datetime import UTC, datetime

from sqlalchemy import Boolean, DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.base_model import MappedBase


class MailLogModel(MappedBase):
    """一封连接信息邮件的结果。没有 token，也没有 SMTP 密码。"""

    __tablename__: str = "mcp_mail_log"
    __table_args__: dict[str, str] = {"comment": "MCP 发信记录表"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, comment="主键ID")
    user_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True, comment="业务用户ID")
    group_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True, comment="MCP 组ID")
    channel: Mapped[str] = mapped_column(String(16), nullable=False, index=True, comment="途径")
    ok: Mapped[bool] = mapped_column(Boolean, nullable=False, index=True, comment="是否成功")
    reason: Mapped[str | None] = mapped_column(String(255), nullable=True, comment="失败原因")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
        index=True,
        comment="创建时间",
    )
