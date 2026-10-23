from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.base_schema import BaseQueryParam, BaseSchema


def _strip_required(value: str, label: str) -> str:
    value = value.strip()
    if not value:
        raise ValueError(f"{label}不能为空")
    return value


class BizSystemCreateSchema(BaseModel):
    """业务系统创建参数。"""

    name: str = Field(..., min_length=1, max_length=64, description="名称")
    code: str = Field(..., min_length=1, max_length=64, description="系统编码")
    base_url: str = Field(..., min_length=1, max_length=512, description="基础地址")
    enabled: bool = Field(default=True, description="是否启用")
    params: dict[str, Any] = Field(default_factory=dict, description="扩展参数")
    uid_field: str = Field(..., min_length=1, max_length=64, description="用户标识字段")
    attr_fields: list[str] = Field(default_factory=list, description="允许的绑定属性")

    @field_validator("name")
    @classmethod
    def _validate_name(cls, value: str) -> str:
        return _strip_required(value, "名称")

    @field_validator("code")
    @classmethod
    def _validate_code(cls, value: str) -> str:
        return _strip_required(value, "系统编码")

    @field_validator("base_url")
    @classmethod
    def _validate_base_url(cls, value: str) -> str:
        return _strip_required(value, "基础地址")

    @field_validator("uid_field")
    @classmethod
    def _validate_uid_field(cls, value: str) -> str:
        return _strip_required(value, "用户标识字段")

    @field_validator("attr_fields")
    @classmethod
    def _validate_attr_fields(cls, value: list[str]) -> list[str]:
        cleaned: list[str] = []
        for item in value:
            text = item.strip()
            if not text:
                raise ValueError("绑定属性名不能为空")
            if text not in cleaned:
                cleaned.append(text)
        return cleaned


class BizSystemUpdateSchema(BaseModel):
    """业务系统更新参数。省略 code 则保持原值；传入相同 code 不算修改。"""

    name: str | None = Field(default=None, min_length=1, max_length=64, description="名称")
    code: str | None = Field(default=None, min_length=1, max_length=64, description="系统编码")
    base_url: str | None = Field(default=None, min_length=1, max_length=512, description="基础地址")
    enabled: bool | None = Field(default=None, description="是否启用")
    params: dict[str, Any] | None = Field(default=None, description="扩展参数")
    uid_field: str | None = Field(default=None, min_length=1, max_length=64, description="用户标识字段")
    attr_fields: list[str] | None = Field(default=None, description="允许的绑定属性")

    @field_validator("name")
    @classmethod
    def _validate_name(cls, value: str | None) -> str | None:
        if value is None:
            return value
        return _strip_required(value, "名称")

    @field_validator("code")
    @classmethod
    def _validate_code(cls, value: str | None) -> str | None:
        if value is None:
            return value
        return _strip_required(value, "系统编码")

    @field_validator("base_url")
    @classmethod
    def _validate_base_url(cls, value: str | None) -> str | None:
        if value is None:
            return value
        return _strip_required(value, "基础地址")

    @field_validator("uid_field")
    @classmethod
    def _validate_uid_field(cls, value: str | None) -> str | None:
        if value is None:
            return value
        return _strip_required(value, "用户标识字段")

    @field_validator("attr_fields")
    @classmethod
    def _validate_attr_fields(cls, value: list[str] | None) -> list[str] | None:
        if value is None:
            return value
        return BizSystemCreateSchema._validate_attr_fields(value)


class BizSystemOutSchema(BizSystemCreateSchema, BaseSchema):
    """业务系统响应。"""

    model_config = ConfigDict(from_attributes=True)


class BizSystemQueryParam(BaseQueryParam):
    """业务系统查询参数。"""

    name: str | None = Field(None, description="名称", json_schema_extra={"q": "like"})
    code: str | None = Field(None, description="系统编码", json_schema_extra={"q": "like"})
    enabled: bool | None = Field(None, description="是否启用", json_schema_extra={"q": "eq"})
