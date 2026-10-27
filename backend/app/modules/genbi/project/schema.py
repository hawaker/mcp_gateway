from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.base_schema import BaseQueryParam, BaseSchema


def _strip_required(value: str, label: str) -> str:
    value = value.strip()
    if not value:
        raise ValueError(f"{label}不能为空")
    return value


class GenbiProjectCreate(BaseModel):
    """创建项目。每数据源仅一条。"""

    datasource_id: int = Field(..., ge=1, description="数据源ID")
    display_name: str = Field(..., min_length=1, max_length=255, description="显示名称")
    system_id: int | None = Field(default=None, ge=1, description="业务系统ID（可选，默认取自数据源）")
    onboarding_status: str = Field(default="not_started", max_length=64, description="入驻状态")
    language: str = Field(default="zh-CN", max_length=16, description="语言")
    agent_profile: dict[str, Any] = Field(default_factory=dict, description="Agent 配置")

    @field_validator("display_name")
    @classmethod
    def _validate_display_name(cls, value: str) -> str:
        return _strip_required(value, "显示名称")


class GenbiProjectUpdate(BaseModel):
    """更新项目（本任务最小 CRUD 未暴露，预留给后续）。"""

    display_name: str | None = Field(default=None, min_length=1, max_length=255, description="显示名称")
    onboarding_status: str | None = Field(default=None, max_length=64, description="入驻状态")
    language: str | None = Field(default=None, max_length=16, description="语言")
    agent_profile: dict[str, Any] | None = Field(default=None, description="Agent 配置")


class GenbiProjectOut(BaseSchema):
    """列表与详情。"""

    model_config = ConfigDict(from_attributes=True)

    datasource_id: int = Field(description="数据源ID")
    system_id: int | None = Field(default=None, description="业务系统ID")
    display_name: str = Field(description="显示名称")
    onboarding_status: str = Field(description="入驻状态")
    language: str = Field(description="语言")
    agent_profile: dict[str, Any] = Field(default_factory=dict, description="Agent 配置")


class GenbiProjectQueryParam(BaseQueryParam):
    """项目查询参数。"""

    datasource_id: int | None = Field(None, description="数据源ID", json_schema_extra={"q": "eq"})
    system_id: int | None = Field(None, description="业务系统ID", json_schema_extra={"q": "eq"})
    display_name: str | None = Field(None, description="显示名称", json_schema_extra={"q": "like"})
    onboarding_status: str | None = Field(None, description="入驻状态", json_schema_extra={"q": "eq"})
