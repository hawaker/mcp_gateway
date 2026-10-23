from sqlalchemy import JSON, Boolean, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.base_model import ModelMixin


class BizBindingModel(ModelMixin):
    """业务用户在某个业务系统上的一条绑定。同一用户同一系统只有一条。"""

    __tablename__: str = "mcp_biz_binding"
    __table_args__ = (
        UniqueConstraint("user_id", "system_id", name="uq_mcp_biz_binding_user_system"),
        {"comment": "业务系统绑定表"},
    )

    user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("mcp_biz_user.id", ondelete="CASCADE", onupdate="CASCADE"),
        nullable=False,
        index=True,
        comment="业务用户ID",
    )
    system_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("mcp_biz_system.id", ondelete="CASCADE", onupdate="CASCADE"),
        nullable=False,
        index=True,
        comment="业务系统ID",
    )
    uid_value: Mapped[str] = mapped_column(String(128), nullable=False, comment="业务系统用户标识")
    attrs: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict, comment="绑定属性")
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, comment="是否启用")
