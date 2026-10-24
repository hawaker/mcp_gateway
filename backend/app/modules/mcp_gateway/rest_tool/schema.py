from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.base_schema import BaseQueryParam, BaseSchema

RequestType = Literal["GET", "POST", "PUT", "PATCH", "DELETE"]
TokenIn = Literal["header", "query", "body"]


def _strip_required(value: str, label: str) -> str:
    value = value.strip()
    if not value:
        raise ValueError(f"{label}不能为空")
    return value


def _json_object(value: Any, label: str) -> dict[str, Any]:
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise ValueError(f"{label}须为 JSON 对象")
    return value


def _empty_to_none(value: str | None) -> str | None:
    if value is None:
        return None
    value = value.strip()
    return value or None


class RestToolCreateSchema(BaseModel):
    """创建一条 REST 工具。调试接口复用这份字段，但不会把它插入表。"""

    name: str = Field(..., min_length=1, max_length=128, description="名称")
    display_name: str = Field(..., min_length=1, max_length=128, description="显示名")
    url: str = Field(..., min_length=1, max_length=2048, description="接口地址")
    description: str | None = Field(default=None, max_length=1024, description="描述")
    request_type: RequestType = Field(default="GET", description="请求方法")
    headers: dict[str, Any] = Field(default_factory=dict, description="请求头")
    input_schema: dict[str, Any] = Field(default_factory=dict, description="入参结构")
    output_schema: dict[str, Any] = Field(default_factory=dict, description="出参结构")
    jsonpath_filter: str | None = Field(default=None, max_length=512, description="Json Path Filter")
    query_mapping: dict[str, Any] = Field(default_factory=dict, description="Query 映射")
    header_mapping: dict[str, Any] = Field(default_factory=dict, description="Header 映射")
    timeout_ms: int | None = Field(default=None, ge=1, description="超时毫秒")
    token_in: TokenIn = Field(default="header", description="token 位置")
    token_name: str | None = Field(default=None, max_length=128, description="token 字段名")
    enabled: bool = Field(default=True, description="是否启用")
    system_id: int = Field(..., ge=1, description="业务系统ID")

    @field_validator("name")
    @classmethod
    def _validate_name(cls, value: str) -> str:
        return _strip_required(value, "名称")

    @field_validator("display_name")
    @classmethod
    def _validate_display_name(cls, value: str) -> str:
        return _strip_required(value, "显示名")

    @field_validator("url")
    @classmethod
    def _validate_url(cls, value: str) -> str:
        return _strip_required(value, "接口地址")

    @field_validator("description", "jsonpath_filter", "token_name")
    @classmethod
    def _validate_optional_text(cls, value: str | None) -> str | None:
        return _empty_to_none(value)

    @field_validator("headers", "input_schema", "output_schema", "query_mapping", "header_mapping")
    @classmethod
    def _validate_objects(cls, value: Any, info) -> dict[str, Any]:
        return _json_object(value, str(info.field_name))

    @field_validator("request_type", mode="before")
    @classmethod
    def _validate_request_type(cls, value: str) -> str:
        if isinstance(value, str):
            return value.strip().upper()
        return value


class RestToolUpdateSchema(BaseModel):
    """更新一条 REST 工具。未提交的字段保持原值。"""

    name: str | None = Field(default=None, min_length=1, max_length=128, description="名称")
    display_name: str | None = Field(default=None, min_length=1, max_length=128, description="显示名")
    url: str | None = Field(default=None, min_length=1, max_length=2048, description="接口地址")
    description: str | None = Field(default=None, max_length=1024, description="描述")
    request_type: RequestType | None = Field(default=None, description="请求方法")
    headers: dict[str, Any] | None = Field(default=None, description="请求头")
    input_schema: dict[str, Any] | None = Field(default=None, description="入参结构")
    output_schema: dict[str, Any] | None = Field(default=None, description="出参结构")
    jsonpath_filter: str | None = Field(default=None, max_length=512, description="Json Path Filter")
    query_mapping: dict[str, Any] | None = Field(default=None, description="Query 映射")
    header_mapping: dict[str, Any] | None = Field(default=None, description="Header 映射")
    timeout_ms: int | None = Field(default=None, ge=1, description="超时毫秒")
    token_in: TokenIn | None = Field(default=None, description="token 位置")
    token_name: str | None = Field(default=None, max_length=128, description="token 字段名")
    enabled: bool | None = Field(default=None, description="是否启用")
    system_id: int | None = Field(default=None, ge=1, description="业务系统ID")

    @field_validator("name")
    @classmethod
    def _validate_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return _strip_required(value, "名称")

    @field_validator("display_name")
    @classmethod
    def _validate_display_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return _strip_required(value, "显示名")

    @field_validator("url")
    @classmethod
    def _validate_url(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return _strip_required(value, "接口地址")

    @field_validator("description", "jsonpath_filter", "token_name")
    @classmethod
    def _validate_optional_text(cls, value: str | None) -> str | None:
        return _empty_to_none(value)

    @field_validator("headers", "input_schema", "output_schema", "query_mapping", "header_mapping")
    @classmethod
    def _validate_objects(cls, value: Any, info) -> dict[str, Any] | None:
        if value is None:
            return None
        return _json_object(value, str(info.field_name))

    @field_validator("request_type", mode="before")
    @classmethod
    def _validate_request_type(cls, value: str | None) -> str | None:
        if isinstance(value, str):
            return value.strip().upper()
        return value


class RestToolOutSchema(RestToolCreateSchema, BaseSchema):
    """REST 工具响应。"""

    model_config = ConfigDict(from_attributes=True)


class RestToolQueryParam(BaseQueryParam):
    """REST 工具查询参数。"""

    name: str | None = Field(None, description="名称", json_schema_extra={"q": "like"})
    system_id: int | None = Field(None, description="业务系统ID", json_schema_extra={"q": "eq"})
    request_type: str | None = Field(None, description="请求方法", json_schema_extra={"q": "eq"})
    enabled: bool | None = Field(None, description="是否启用", json_schema_extra={"q": "eq"})


class RestToolDebugSchema(BaseModel):
    """用当前表单调试。draft 还没保存，这次请求不会插入工具。"""

    draft: RestToolCreateSchema
    user_id: int = Field(..., ge=1, description="业务用户ID")
    arguments: dict[str, Any] = Field(default_factory=dict, description="调用参数")
    reveal: bool = Field(default=False, description="为真时返回未遮住的业务 token")

    @field_validator("arguments")
    @classmethod
    def _validate_arguments(cls, value: Any) -> dict[str, Any]:
        return _json_object(value, "调用参数")


class RestToolDebugResultSchema(BaseModel):
    """调试结果。默认遮住业务 token。不包含调用日志。"""

    status: int | None = Field(default=None, description="上游 HTTP 状态码")
    request: dict[str, Any] | None = Field(default=None, description="发出的请求")
    response: Any = Field(default=None, description="上游响应")
    link: str | None = Field(default=None, description="交互式验证链接")


class UpstreamResult(BaseModel):
    """正式调用的上游结果。有 Json Path Filter 时 body 已过滤。"""

    status: int | None = None
    body: Any = None
    link: str | None = None
