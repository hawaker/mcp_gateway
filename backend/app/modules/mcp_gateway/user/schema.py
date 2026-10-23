from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.base_schema import BaseQueryParam, BaseSchema


class BizUserCreateSchema(BaseModel):
    """业务用户创建参数。"""

    name: str = Field(..., min_length=1, max_length=64, description="姓名")
    email: str | None = Field(default=None, max_length=128, description="邮箱")
    mobile: str | None = Field(default=None, max_length=20, description="手机号")
    nickname: str | None = Field(default=None, max_length=64, description="昵称")
    enabled: bool = Field(default=True, description="是否启用")

    @field_validator("name")
    @classmethod
    def _validate_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("姓名不能为空")
        return value


class BizUserOutSchema(BizUserCreateSchema, BaseSchema):
    """业务用户响应。"""

    model_config = ConfigDict(from_attributes=True)


class BizUserQueryParam(BaseQueryParam):
    """业务用户查询参数。"""

    name: str | None = Field(None, description="姓名", json_schema_extra={"q": "like"})
    enabled: bool | None = Field(None, description="是否启用", json_schema_extra={"q": "eq"})


class BizUserGroupCreateSchema(BaseModel):
    """业务用户组创建参数。"""

    name: str = Field(..., min_length=1, max_length=64, description="组名")
    enabled: bool = Field(default=True, description="是否启用")

    @field_validator("name")
    @classmethod
    def _validate_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("组名不能为空")
        return value


class BizUserGroupOutSchema(BizUserGroupCreateSchema, BaseSchema):
    """业务用户组响应。"""

    model_config = ConfigDict(from_attributes=True)


class BizUserGroupQueryParam(BaseQueryParam):
    """业务用户组查询参数。"""

    name: str | None = Field(None, description="组名", json_schema_extra={"q": "like"})
    enabled: bool | None = Field(None, description="是否启用", json_schema_extra={"q": "eq"})


class BizUserGroupMemberCreateSchema(BaseModel):
    """向用户组添加成员。只追加，不替换该用户已加入的其他组。"""

    user_ids: list[int] = Field(..., min_length=1, description="业务用户ID列表")


class BizUserGroupMemberOutSchema(BaseModel):
    """添加成员的响应。id 为用户组 ID。"""

    id: int = Field(description="用户组ID")
    user_ids: list[int] = Field(description="本次请求的业务用户ID")
