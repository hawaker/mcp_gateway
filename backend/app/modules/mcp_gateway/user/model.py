from sqlalchemy import Boolean, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.base_model import MappedBase, ModelMixin


class BizUserModel(ModelMixin):
    """MCP 网关业务用户，与 sys_user 分离。"""

    __tablename__: str = "mcp_biz_user"
    __table_args__: dict[str, str] = {"comment": "业务用户表"}

    name: Mapped[str] = mapped_column(String(64), nullable=False, index=True, comment="姓名")
    email: Mapped[str | None] = mapped_column(String(128), nullable=True, comment="邮箱")
    mobile: Mapped[str | None] = mapped_column(String(20), nullable=True, comment="手机号")
    nickname: Mapped[str | None] = mapped_column(String(64), nullable=True, comment="昵称")
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, comment="是否启用")


class BizUserGroupModel(ModelMixin):
    """MCP 网关业务用户组。"""

    __tablename__: str = "mcp_biz_user_group"
    __table_args__: dict[str, str] = {"comment": "业务用户组表"}

    name: Mapped[str] = mapped_column(String(64), nullable=False, index=True, comment="组名")
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, comment="是否启用")


class BizUserGroupMemberModel(MappedBase):
    """业务用户与用户组的多对多关系。同一用户可属于多个组。"""

    __tablename__: str = "mcp_biz_user_group_member"
    __table_args__: dict[str, str] = {"comment": "业务用户组成员表"}

    user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("mcp_biz_user.id", ondelete="CASCADE", onupdate="CASCADE"),
        primary_key=True,
        comment="业务用户ID",
    )
    group_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("mcp_biz_user_group.id", ondelete="CASCADE", onupdate="CASCADE"),
        primary_key=True,
        comment="用户组ID",
    )
