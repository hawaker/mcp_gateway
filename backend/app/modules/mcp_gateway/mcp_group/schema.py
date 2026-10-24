from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.base_schema import BaseQueryParam, BaseSchema

Source = Literal["rest", "upstream"]
PrincipalType = Literal["user", "group"]


def _strip_required(value: str, label: str) -> str:
    value = value.strip()
    if not value:
        raise ValueError(f"{label}不能为空")
    return value


def _empty_to_none(value: str | None) -> str | None:
    if value is None:
        return None
    value = value.strip()
    return value or None


class McpGroupCreateSchema(BaseModel):
    """创建一个 MCP 组。"""

    name: str = Field(..., min_length=1, max_length=128, description="名称")
    enabled: bool = Field(default=True, description="是否启用")

    @field_validator("name")
    @classmethod
    def _validate_name(cls, value: str) -> str:
        return _strip_required(value, "名称")


class McpGroupUpdateSchema(BaseModel):
    """修改 MCP 组。只提交需要变更的字段。"""

    name: str | None = Field(default=None, min_length=1, max_length=128, description="名称")
    enabled: bool | None = Field(default=None, description="是否启用")

    @field_validator("name")
    @classmethod
    def _validate_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return _strip_required(value, "名称")


class McpGroupOutSchema(McpGroupCreateSchema, BaseSchema):
    """MCP 组响应。"""

    model_config = ConfigDict(from_attributes=True)


class McpGroupQueryParam(BaseQueryParam):
    """MCP 组查询参数。"""

    name: str | None = Field(None, description="名称", json_schema_extra={"q": "like"})
    enabled: bool | None = Field(None, description="是否启用", json_schema_extra={"q": "eq"})


class McpGroupToolCreateSchema(BaseModel):
    """把一条 REST 或上游工具放进组。external_name 是该组对外的别名。"""

    source: Source = Field(..., description="来源")
    source_id: int = Field(..., ge=1, description="来源工具ID")
    external_name: str | None = Field(default=None, max_length=512, description="外部名称")
    enabled: bool = Field(default=True, description="是否启用")

    @field_validator("external_name")
    @classmethod
    def _validate_external_name(cls, value: str | None) -> str | None:
        return _empty_to_none(value)


class McpGroupToolUpdateSchema(BaseModel):
    """修改组内工具的别名或启用状态。不能删除。"""

    external_name: str | None = Field(default=None, max_length=512, description="外部名称")
    enabled: bool | None = Field(default=None, description="是否启用")

    @field_validator("external_name")
    @classmethod
    def _validate_external_name(cls, value: str | None) -> str | None:
        return _empty_to_none(value)


class McpGroupToolOutSchema(BaseSchema):
    """组内工具响应。"""

    model_config = ConfigDict(from_attributes=True)

    group_id: int = Field(..., description="MCP 组ID")
    source: Source = Field(..., description="来源")
    source_id: int = Field(..., description="来源工具ID")
    external_name: str = Field(..., description="外部名称")
    enabled: bool = Field(..., description="是否启用")


class McpGroupToolQueryParam(BaseQueryParam):
    """组内工具查询参数。"""

    group_id: int | None = Field(None, description="MCP 组ID", json_schema_extra={"q": "eq"})
    source: str | None = Field(None, description="来源", json_schema_extra={"q": "eq"})
    external_name: str | None = Field(None, description="外部名称", json_schema_extra={"q": "like"})
    enabled: bool | None = Field(None, description="是否启用", json_schema_extra={"q": "eq"})


class McpGroupMemberCreateSchema(BaseModel):
    """勾选一个业务用户或业务用户组。"""

    principal_type: PrincipalType = Field(..., description="主体类型")
    principal_id: int = Field(..., ge=1, description="主体ID")
    enabled: bool = Field(default=True, description="是否启用")


class McpGroupMemberUpdateSchema(BaseModel):
    """启用或停用成员。不能删除。"""

    enabled: bool | None = Field(default=None, description="是否启用")


class McpGroupMemberOutSchema(BaseSchema):
    """成员响应。不含 token。"""

    model_config = ConfigDict(from_attributes=True)

    group_id: int = Field(..., description="MCP 组ID")
    principal_type: PrincipalType = Field(..., description="主体类型")
    principal_id: int = Field(..., description="主体ID")
    enabled: bool = Field(..., description="是否启用")


class McpGroupMemberQueryParam(BaseQueryParam):
    """成员查询参数。"""

    group_id: int | None = Field(None, description="MCP 组ID", json_schema_extra={"q": "eq"})
    principal_type: str | None = Field(None, description="主体类型", json_schema_extra={"q": "eq"})
    principal_id: int | None = Field(None, description="主体ID", json_schema_extra={"q": "eq"})
    enabled: bool | None = Field(None, description="是否启用", json_schema_extra={"q": "eq"})


class McpCredentialOutSchema(BaseSchema):
    """凭证列表项。不含明文、哈希和密文。"""

    model_config = ConfigDict(from_attributes=True)

    user_id: int = Field(..., description="业务用户ID")
    group_id: int = Field(..., description="MCP 组ID")


class McpCredentialQueryParam(BaseQueryParam):
    """凭证查询参数。"""

    user_id: int | None = Field(None, description="业务用户ID", json_schema_extra={"q": "eq"})
    group_id: int | None = Field(None, description="MCP 组ID", json_schema_extra={"q": "eq"})


class ConnectionInfoSchema(BaseModel):
    """管理员查看的连接信息。明文只出现在 authorization 里。"""

    streamable_http_url: str = Field(..., description="Streamable HTTP 地址")
    sse_url: str = Field(..., description="SSE 地址")
    messages_url: str = Field(..., description="SSE 消息地址")
    authorization: str = Field(..., description="Authorization 请求头")


class PublishedToolSchema(BaseModel):
    """tools_for 交给下一任务作为 tools/list 的一条工具。"""

    name: str
    description: str = ""
    input_schema: dict[str, Any] = Field(default_factory=dict)
    source: Source
    source_id: int


class McpCredentialReissueSchema(BaseModel):
    """重新签发某个人在某个组上的 token。"""

    user_id: int = Field(..., ge=1, description="业务用户ID")
    group_id: int = Field(..., ge=1, description="MCP 组ID")
