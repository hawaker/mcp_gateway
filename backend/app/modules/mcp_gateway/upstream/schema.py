from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.base_schema import BaseQueryParam, BaseSchema


def _strip_required(value: str, label: str) -> str:
    value = value.strip()
    if not value:
        raise ValueError(f"{label}不能为空")
    return value


def _http_url(value: str) -> str:
    value = _strip_required(value, "上游地址")
    lowered = value.lower()
    if not (lowered.startswith("http://") or lowered.startswith("https://")):
        raise ValueError("上游地址必须以 http:// 或 https:// 开头")
    return value


class UpstreamMcpCreateSchema(BaseModel):
    """创建 MCP 代理。credential_value 只在请求里出现，不会原样入库。code 创建后不可改。"""

    name: str = Field(..., min_length=1, max_length=128, description="名称")
    code: str = Field(..., min_length=1, max_length=64, description="英文编码")
    url: str = Field(..., min_length=1, max_length=2048, description="上游地址")
    credential_header: str = Field(..., min_length=1, max_length=128, description="凭证请求头")
    credential_value: str = Field(..., min_length=1, max_length=8192, description="凭证")

    @field_validator("name")
    @classmethod
    def _validate_name(cls, value: str) -> str:
        return _strip_required(value, "名称")

    @field_validator("code")
    @classmethod
    def _validate_code(cls, value: str) -> str:
        return _strip_required(value, "英文编码")

    @field_validator("url")
    @classmethod
    def _validate_url(cls, value: str) -> str:
        return _http_url(value)

    @field_validator("credential_header")
    @classmethod
    def _validate_header(cls, value: str) -> str:
        return _strip_required(value, "凭证请求头")

    @field_validator("credential_value")
    @classmethod
    def _validate_credential(cls, value: str) -> str:
        return _strip_required(value, "凭证")


class UpstreamMcpUpdateSchema(BaseModel):
    """更新 MCP 代理。不能改 code。省略凭证或传空字符串时保留原密文。"""

    name: str | None = Field(default=None, min_length=1, max_length=128, description="名称")
    url: str | None = Field(default=None, min_length=1, max_length=2048, description="上游地址")
    credential_header: str | None = Field(default=None, min_length=1, max_length=128, description="凭证请求头")
    credential_value: str | None = Field(default=None, max_length=8192, description="凭证")

    @field_validator("name")
    @classmethod
    def _validate_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return _strip_required(value, "名称")

    @field_validator("url")
    @classmethod
    def _validate_url(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return _http_url(value)

    @field_validator("credential_header")
    @classmethod
    def _validate_header(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return _strip_required(value, "凭证请求头")

    @field_validator("credential_value")
    @classmethod
    def _validate_credential(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        return value or None


class UpstreamMcpOutSchema(BaseSchema):
    """MCP 代理响应。不含凭证明文，也不回传密文。"""

    model_config = ConfigDict(from_attributes=True)

    name: str = Field(..., description="名称")
    code: str = Field(..., description="英文编码")
    url: str = Field(..., description="上游地址")
    credential_header: str = Field(..., description="凭证请求头")


class UpstreamMcpQueryParam(BaseQueryParam):
    """MCP 代理查询参数。"""

    name: str | None = Field(None, description="名称", json_schema_extra={"q": "like"})
    code: str | None = Field(None, description="英文编码", json_schema_extra={"q": "like"})
    url: str | None = Field(None, description="上游地址", json_schema_extra={"q": "like"})
    credential_header: str | None = Field(None, description="凭证请求头", json_schema_extra={"q": "like"})


class UpstreamToolOutSchema(BaseSchema):
    """MCP 代理工具响应。"""

    model_config = ConfigDict(from_attributes=True)

    upstream_id: int = Field(..., description="MCP 代理 ID")
    remote_name: str = Field(..., description="远端工具名")
    external_name: str = Field(..., description="外部名称")
    input_schema: dict[str, Any] = Field(default_factory=dict, description="入参结构")
    selected: bool = Field(..., description="是否选用")


class UpstreamToolUpdateSchema(BaseModel):
    """管理员显式选用或取消选用。"""

    selected: bool = Field(..., description="是否选用")


class UpstreamToolQueryParam(BaseQueryParam):
    """MCP 代理工具查询参数。"""

    upstream_id: int | None = Field(None, description="MCP 代理 ID", json_schema_extra={"q": "eq"})
    remote_name: str | None = Field(None, description="远端工具名", json_schema_extra={"q": "like"})
    external_name: str | None = Field(None, description="外部名称", json_schema_extra={"q": "like"})
    selected: bool | None = Field(None, description="是否选用", json_schema_extra={"q": "eq"})


class ToolSnapshot(BaseModel):
    """一次 tools/list 合并后的工具快照。"""

    remote_name: str
    external_name: str
    input_schema: dict[str, Any] = Field(default_factory=dict)
    selected: bool = False


class UpstreamResult(BaseModel):
    """一次上游 JSON-RPC 调用的 HTTP 结果。401 也落在这里，不再登录。"""

    status: int | None = None
    body: Any = None
