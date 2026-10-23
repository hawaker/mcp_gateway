from typing import Any, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.core.base_schema import BaseQueryParam, BaseSchema

AuthMethod = Literal["fixed", "custom", "basic", "interactive"]
HttpMethod = Literal["GET", "POST", "PUT", "PATCH", "DELETE"]


def _clean_url(value: str) -> str:
    value = value.strip()
    if not value:
        raise ValueError("鉴权地址不能为空")
    return value


def _clean_username(value: str | None) -> str | None:
    if value is None:
        return None
    value = value.strip()
    return value or None


class AuthConfigCreateSchema(BaseModel):
    """创建一条业务系统鉴权。Basic 的账号密码属于系统，不放在用户上。"""

    system_id: int = Field(..., ge=1, description="业务系统ID")
    method: AuthMethod = Field(..., description="鉴权方法")
    enabled: bool = Field(default=True, description="是否启用")
    url: str = Field(..., min_length=1, max_length=512, description="鉴权地址")
    rule: dict[str, Any] = Field(default_factory=dict, description="取值规则")
    http_method: HttpMethod | None = Field(default=None, description="HTTP 方法")
    username: str | None = Field(default=None, max_length=128, description="Basic 用户名")
    password: str | None = Field(default=None, max_length=512, description="Basic 密码")

    @field_validator("url")
    @classmethod
    def _validate_url(cls, value: str) -> str:
        return _clean_url(value)

    @field_validator("username")
    @classmethod
    def _validate_username(cls, value: str | None) -> str | None:
        return _clean_username(value)

    @model_validator(mode="after")
    def _validate_method_fields(self) -> Self:
        ensure_method_fields(self.method, self.http_method, self.username, self.password)
        return self


class AuthConfigUpdateSchema(BaseModel):
    """更新一条鉴权。未提交的字段保持原值。"""

    system_id: int | None = Field(default=None, ge=1, description="业务系统ID")
    method: AuthMethod | None = Field(default=None, description="鉴权方法")
    enabled: bool | None = Field(default=None, description="是否启用")
    url: str | None = Field(default=None, min_length=1, max_length=512, description="鉴权地址")
    rule: dict[str, Any] | None = Field(default=None, description="取值规则")
    http_method: HttpMethod | None = Field(default=None, description="HTTP 方法")
    username: str | None = Field(default=None, max_length=128, description="Basic 用户名")
    password: str | None = Field(default=None, max_length=512, description="Basic 密码")

    @field_validator("url")
    @classmethod
    def _validate_url(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return _clean_url(value)

    @field_validator("username")
    @classmethod
    def _validate_username(cls, value: str | None) -> str | None:
        return _clean_username(value)


class AuthConfigOutSchema(AuthConfigCreateSchema, BaseSchema):
    """鉴权配置响应。"""

    model_config = ConfigDict(from_attributes=True)


class AuthConfigQueryParam(BaseQueryParam):
    """鉴权配置查询参数。"""

    system_id: int | None = Field(None, description="业务系统ID", json_schema_extra={"q": "eq"})
    method: str | None = Field(None, description="鉴权方法", json_schema_extra={"q": "eq"})
    enabled: bool | None = Field(None, description="是否启用", json_schema_extra={"q": "eq"})
    url: str | None = Field(None, description="鉴权地址", json_schema_extra={"q": "like"})


def ensure_method_fields(
    method: str,
    http_method: str | None,
    username: str | None,
    password: str | None,
) -> None:
    """custom 和 basic 要有 HTTP 方法；basic 的账号密码在这条配置上。"""
    if method in {"custom", "basic"} and not http_method:
        raise ValueError("自定义和 Basic 鉴权需要 HTTP 方法")
    if method == "basic" and (not username or not password):
        raise ValueError("Basic 鉴权需要系统账号和密码")
