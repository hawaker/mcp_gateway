from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.base_schema import BaseQueryParam, BaseSchema


def _strip_required(value: str, label: str) -> str:
    value = value.strip()
    if not value:
        raise ValueError(f"{label}不能为空")
    return value


def _optional_str(value: str | None) -> str | None:
    if value is None:
        return None
    value = value.strip()
    return value or None


class GenbiDatasourceCreate(BaseModel):
    """创建数据源。明文密钥只在入参出现。"""

    system_id: int = Field(..., ge=1, description="业务系统ID")
    name: str = Field(..., min_length=1, max_length=128, description="名称")
    wren_type: str = Field(..., min_length=1, max_length=32, description="Wren 数据源类型")
    host: str | None = Field(default=None, max_length=255, description="主机")
    port: int | None = Field(default=None, ge=0, le=65535, description="端口")
    username: str | None = Field(default=None, max_length=128, description="用户名")
    password: str | None = Field(default=None, max_length=2048, description="密码")
    database: str | None = Field(default=None, max_length=128, description="数据库名")
    db_schema: str | None = Field(default=None, max_length=128, description="Schema")
    url: str | None = Field(default=None, max_length=1024, description="连接 URL")
    api_key: str | None = Field(default=None, max_length=4096, description="API Key")
    private_key: str | None = Field(default=None, max_length=16384, description="私钥")
    token: str | None = Field(default=None, max_length=4096, description="Token")
    config: dict[str, Any] = Field(default_factory=dict, description="扩展配置")
    description: str | None = Field(default=None, max_length=512, description="描述")
    enabled: bool = Field(default=True, description="是否启用")

    @field_validator("name", "wren_type")
    @classmethod
    def _validate_required(cls, value: str, info) -> str:
        return _strip_required(value, "名称" if info.field_name == "name" else "数据源类型")

    @field_validator("host", "username", "database", "db_schema", "url", "description")
    @classmethod
    def _validate_optional(cls, value: str | None) -> str | None:
        return _optional_str(value)


class GenbiDatasourceUpdate(BaseModel):
    """更新数据源。密钥留空则保持原密文。"""

    name: str | None = Field(default=None, min_length=1, max_length=128, description="名称")
    wren_type: str | None = Field(default=None, min_length=1, max_length=32, description="Wren 数据源类型")
    host: str | None = Field(default=None, max_length=255, description="主机")
    port: int | None = Field(default=None, ge=0, le=65535, description="端口")
    username: str | None = Field(default=None, max_length=128, description="用户名")
    password: str | None = Field(default=None, max_length=2048, description="密码")
    database: str | None = Field(default=None, max_length=128, description="数据库名")
    db_schema: str | None = Field(default=None, max_length=128, description="Schema")
    url: str | None = Field(default=None, max_length=1024, description="连接 URL")
    api_key: str | None = Field(default=None, max_length=4096, description="API Key")
    private_key: str | None = Field(default=None, max_length=16384, description="私钥")
    token: str | None = Field(default=None, max_length=4096, description="Token")
    config: dict[str, Any] | None = Field(default=None, description="扩展配置")
    description: str | None = Field(default=None, max_length=512, description="描述")
    enabled: bool | None = Field(default=None, description="是否启用")

    @field_validator("name", "wren_type")
    @classmethod
    def _validate_required(cls, value: str | None, info) -> str | None:
        if value is None:
            return None
        return _strip_required(value, "名称" if info.field_name == "name" else "数据源类型")

    @field_validator("host", "username", "database", "db_schema", "url", "description")
    @classmethod
    def _validate_optional(cls, value: str | None) -> str | None:
        return _optional_str(value)


class GenbiDatasourceOut(BaseSchema):
    """列表与详情。不含明文密钥与密文字段。"""

    model_config = ConfigDict(from_attributes=True)

    system_id: int = Field(description="业务系统ID")
    name: str = Field(description="名称")
    wren_type: str = Field(description="Wren 数据源类型")
    host: str | None = Field(default=None, description="主机")
    port: int | None = Field(default=None, description="端口")
    username: str | None = Field(default=None, description="用户名")
    database: str | None = Field(default=None, description="数据库名")
    db_schema: str | None = Field(default=None, description="Schema")
    url: str | None = Field(default=None, description="连接 URL")
    config: dict[str, Any] = Field(default_factory=dict, description="扩展配置")
    description: str | None = Field(default=None, description="描述")
    enabled: bool = Field(description="是否启用")


class GenbiDatasourceQueryParam(BaseQueryParam):
    """数据源查询参数。"""

    system_id: int | None = Field(None, description="业务系统ID", json_schema_extra={"q": "eq"})
    name: str | None = Field(None, description="名称", json_schema_extra={"q": "like"})
    wren_type: str | None = Field(None, description="Wren 类型", json_schema_extra={"q": "eq"})
    enabled: bool | None = Field(None, description="是否启用", json_schema_extra={"q": "eq"})
