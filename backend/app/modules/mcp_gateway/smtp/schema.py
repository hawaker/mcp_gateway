from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.base_schema import BaseQueryParam, BaseSchema

Encryption = Literal["none", "starttls", "ssl"]


def _required(value: str, label: str) -> str:
    value = value.strip()
    if not value:
        raise ValueError(f"{label}不能为空")
    return value


def _optional(value: str | None) -> str | None:
    if value is None:
        return None
    value = value.strip()
    return value or None


class SmtpConfigCreateSchema(BaseModel):
    """创建唯一的 SMTP 配置。password 只在写入时出现。"""

    enabled: bool = Field(default=False, description="是否启用")
    host: str = Field(..., min_length=1, max_length=255, description="SMTP 主机")
    port: int = Field(..., ge=1, le=65535, description="端口")
    username: str | None = Field(default=None, max_length=128, description="账号")
    password: str = Field(default="", max_length=512, description="密码")
    from_address: str = Field(..., min_length=1, max_length=255, description="发件人地址")
    from_name: str | None = Field(default=None, max_length=128, description="发件人名称")
    encryption: Encryption = Field(..., description="加密方式")

    @field_validator("host")
    @classmethod
    def _validate_host(cls, value: str) -> str:
        return _required(value, "SMTP 主机")

    @field_validator("from_address")
    @classmethod
    def _validate_from_address(cls, value: str) -> str:
        return _required(value, "发件人地址")

    @field_validator("username", "from_name")
    @classmethod
    def _validate_optional(cls, value: str | None) -> str | None:
        return _optional(value)


class SmtpConfigUpdateSchema(BaseModel):
    """更新 SMTP 配置。密码留空则保持原密文。"""

    enabled: bool | None = Field(default=None, description="是否启用")
    host: str | None = Field(default=None, min_length=1, max_length=255, description="SMTP 主机")
    port: int | None = Field(default=None, ge=1, le=65535, description="端口")
    username: str | None = Field(default=None, max_length=128, description="账号")
    password: str | None = Field(default=None, max_length=512, description="密码")
    from_address: str | None = Field(default=None, min_length=1, max_length=255, description="发件人地址")
    from_name: str | None = Field(default=None, max_length=128, description="发件人名称")
    encryption: Encryption | None = Field(default=None, description="加密方式")

    @field_validator("host")
    @classmethod
    def _validate_host(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return _required(value, "SMTP 主机")

    @field_validator("from_address")
    @classmethod
    def _validate_from_address(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return _required(value, "发件人地址")

    @field_validator("username", "from_name")
    @classmethod
    def _validate_optional(cls, value: str | None) -> str | None:
        return _optional(value)


class SmtpConfigOutSchema(BaseSchema):
    """列表和详情。没有明文密码，也没有密文。"""

    model_config = ConfigDict(from_attributes=True)

    enabled: bool = Field(description="是否启用")
    host: str = Field(description="SMTP 主机")
    port: int = Field(description="端口")
    username: str | None = Field(default=None, description="账号")
    from_address: str = Field(description="发件人地址")
    from_name: str | None = Field(default=None, description="发件人名称")
    encryption: Encryption = Field(description="加密方式")


class SmtpConfigQueryParam(BaseQueryParam):
    """SMTP 配置查询。只有一行，仍走分页。"""

    enabled: bool | None = Field(None, description="是否启用", json_schema_extra={"q": "eq"})
    host: str | None = Field(None, description="SMTP 主机", json_schema_extra={"q": "like"})


class SmtpTestSchema(BaseModel):
    """测试信收件人。不写发信记录。"""

    to_address: str = Field(..., min_length=1, max_length=255, description="收件人")

    @field_validator("to_address")
    @classmethod
    def _validate_to_address(cls, value: str) -> str:
        return _required(value, "收件人")
