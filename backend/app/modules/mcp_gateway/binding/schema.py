from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.base_schema import BaseQueryParam, BaseSchema


class BizBindingCreateSchema(BaseModel):
    """业务系统绑定创建参数。同一用户同一系统只能有一条。"""

    user_id: int = Field(..., ge=1, description="业务用户ID")
    system_id: int = Field(..., ge=1, description="业务系统ID")
    uid_value: str = Field(..., min_length=1, max_length=128, description="业务系统用户标识")
    attrs: dict[str, Any] = Field(default_factory=dict, description="绑定属性")
    enabled: bool = Field(default=True, description="是否启用")

    @field_validator("uid_value")
    @classmethod
    def _validate_uid_value(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("业务系统用户标识不能为空")
        return value


class BizBindingUpdateSchema(BaseModel):
    """更新一条绑定。只改这一行，不影响该用户在其他系统上的绑定。"""

    user_id: int | None = Field(default=None, ge=1, description="业务用户ID")
    system_id: int | None = Field(default=None, ge=1, description="业务系统ID")
    uid_value: str | None = Field(default=None, min_length=1, max_length=128, description="业务系统用户标识")
    attrs: dict[str, Any] | None = Field(default=None, description="绑定属性")
    enabled: bool | None = Field(default=None, description="是否启用")

    @field_validator("uid_value")
    @classmethod
    def _validate_uid_value(cls, value: str | None) -> str | None:
        if value is None:
            return value
        value = value.strip()
        if not value:
            raise ValueError("业务系统用户标识不能为空")
        return value


class BizBindingOutSchema(BizBindingCreateSchema, BaseSchema):
    """业务系统绑定响应。"""

    model_config = ConfigDict(from_attributes=True)


class BizBindingQueryParam(BaseQueryParam):
    """业务系统绑定查询参数。"""

    user_id: int | None = Field(None, description="业务用户ID", json_schema_extra={"q": "eq"})
    system_id: int | None = Field(None, description="业务系统ID", json_schema_extra={"q": "eq"})
    uid_value: str | None = Field(None, description="业务系统用户标识", json_schema_extra={"q": "like"})
    enabled: bool | None = Field(None, description="是否启用", json_schema_extra={"q": "eq"})
