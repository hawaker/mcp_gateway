from datetime import UTC, datetime

from sqlalchemy import Boolean, DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.base_model import MappedBase


class CallLogModel(MappedBase):
    """一次 tools/call 的结果。没有请求体、响应体和 token。"""

    __tablename__: str = "mcp_call_log"
    __table_args__: dict[str, str] = {"comment": "MCP 调用日志表"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, comment="主键ID")
    user_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True, comment="业务用户ID")
    group_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True, comment="MCP 组ID")
    tool_name: Mapped[str] = mapped_column(String(512), nullable=False, index=True, comment="工具名称")
    system_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True, comment="业务系统ID")
    elapsed_ms: Mapped[int] = mapped_column(Integer, nullable=False, comment="耗时毫秒")
    ok: Mapped[bool] = mapped_column(Boolean, nullable=False, comment="是否成功")
    http_status: Mapped[int | None] = mapped_column(Integer, nullable=True, comment="上游 HTTP 状态码")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
        index=True,
        comment="创建时间",
    )
