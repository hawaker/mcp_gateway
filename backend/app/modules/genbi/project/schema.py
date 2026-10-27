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


class GenbiModelColumnIn(BaseModel):
    """同步 MDL 列。"""

    display_name: str = Field(..., min_length=1, max_length=255, description="显示名称")
    source_column_name: str = Field(..., min_length=1, max_length=512, description="源列名")
    column_type: str | None = Field(default="varchar", max_length=128, description="列类型")
    is_calculated: bool = Field(default=False, description="是否计算列")
    expression: str | None = Field(default=None, description="计算表达式")
    properties: dict[str, Any] | None = Field(default=None, description="扩展属性")


class GenbiModelIn(BaseModel):
    """同步 MDL 模型（表）。"""

    display_name: str = Field(..., min_length=1, max_length=255, description="显示名称")
    source_table_name: str = Field(..., min_length=1, max_length=512, description="源表名")
    reference_name: str = Field(..., min_length=1, max_length=255, description="引用名")
    ref_sql: str | None = Field(default=None, description="引用 SQL")
    cached: bool = Field(default=False, description="是否缓存")
    refresh_time: str | None = Field(default=None, max_length=64, description="刷新时间")
    properties: dict[str, Any] | None = Field(default=None, description="扩展属性")
    columns: list[GenbiModelColumnIn] = Field(default_factory=list, description="列")


class GenbiModelSyncRequest(BaseModel):
    """批量替换项目下的 MDL 模型。"""

    models: list[GenbiModelIn] = Field(..., min_length=1, description="模型列表")


class GenbiModelColumnOut(BaseSchema):
    model_config = ConfigDict(from_attributes=True)

    display_name: str = Field(description="显示名称")
    source_column_name: str = Field(description="源列名")
    column_type: str | None = Field(default=None, description="列类型")
    is_calculated: bool = Field(description="是否计算列")
    expression: str | None = Field(default=None, description="计算表达式")
    properties: dict[str, Any] | None = Field(default=None, description="扩展属性")


class GenbiModelOut(BaseSchema):
    model_config = ConfigDict(from_attributes=True)

    project_id: int = Field(description="项目ID")
    display_name: str = Field(description="显示名称")
    source_table_name: str = Field(description="源表名")
    reference_name: str = Field(description="引用名")
    ref_sql: str | None = Field(default=None, description="引用 SQL")
    cached: bool = Field(description="是否缓存")
    refresh_time: str | None = Field(default=None, description="刷新时间")
    properties: dict[str, Any] | None = Field(default=None, description="扩展属性")
    columns: list[GenbiModelColumnOut] = Field(default_factory=list, description="列")


class GenbiDeployOut(BaseSchema):
    model_config = ConfigDict(from_attributes=True)

    project_id: int = Field(description="项目ID")
    mdl_hash: str | None = Field(default=None, description="MDL 哈希")
    status: str = Field(description="状态")
    stage: str | None = Field(default=None, description="阶段")
    error: str | None = Field(default=None, description="错误信息")
    deployed_at: Any = Field(default=None, description="部署时间")
