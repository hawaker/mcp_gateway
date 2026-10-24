from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

Channel = Literal["group", "user_group", "user"]


class MailLogOutSchema(BaseModel):
    """发信记录。只有用户、MCP 组、途径、成败、时间和原因。"""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description="主键ID")
    user_id: int = Field(description="业务用户ID")
    group_id: int = Field(description="MCP 组ID")
    channel: Channel = Field(description="途径")
    ok: bool = Field(description="是否成功")
    reason: str | None = Field(default=None, description="失败原因")
    created_at: datetime = Field(description="创建时间")


class MailLogQueryParam(BaseModel):
    """按用户、MCP 组、用户组、途径、成败和时间筛选。"""

    user_id: int | None = Field(None, description="业务用户ID", json_schema_extra={"q": "eq"})
    group_id: int | None = Field(None, description="MCP 组ID", json_schema_extra={"q": "eq"})
    user_group_id: int | None = Field(None, description="业务用户组ID")
    channel: Channel | None = Field(None, description="途径", json_schema_extra={"q": "eq"})
    ok: bool | None = Field(None, description="是否成功", json_schema_extra={"q": "eq"})
    created_at_start: datetime | None = Field(None, description="创建时间起")
    created_at_end: datetime | None = Field(None, description="创建时间止")
