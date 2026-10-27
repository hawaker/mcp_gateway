from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.base_schema import BaseQueryParam, BaseSchema

AclOperator = Literal[
    "eq",
    "ne",
    "gt",
    "gte",
    "lt",
    "lte",
    "in",
    "not_in",
    "contains",
    "not_contains",
]
AclColumnAction = Literal["mask", "deny"]
AclMaskTemplate = Literal["all_stars", "keep_first_1", "keep_first_3"]


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


class GenbiGroupDatasourceAttach(BaseModel):
    """把数据源挂到 MCP 组。"""

    datasource_id: int = Field(..., ge=1, description="数据源ID")
    external_name: str | None = Field(default=None, max_length=512, description="对外工具名（别名）")
    enabled: bool = Field(default=True, description="是否启用")

    @field_validator("external_name")
    @classmethod
    def _validate_external_name(cls, value: str | None) -> str | None:
        return _empty_to_none(value)


class GenbiGroupDatasourceUpdate(BaseModel):
    """修改关联的别名或启用状态。"""

    external_name: str | None = Field(default=None, max_length=512, description="对外工具名")
    enabled: bool | None = Field(default=None, description="是否启用")

    @field_validator("external_name")
    @classmethod
    def _validate_external_name(cls, value: str | None) -> str | None:
        return _empty_to_none(value)


class GenbiGroupDatasourceOut(BaseSchema):
    """组–数据源关联响应。"""

    model_config = ConfigDict(from_attributes=True)

    group_id: int = Field(..., description="MCP 组ID")
    datasource_id: int = Field(..., description="数据源ID")
    external_name: str = Field(..., description="对外工具名")
    enabled: bool = Field(..., description="是否启用")


class GenbiGroupDatasourceQueryParam(BaseQueryParam):
    """组–数据源查询。"""

    group_id: int | None = Field(None, description="MCP 组ID", json_schema_extra={"q": "eq"})
    datasource_id: int | None = Field(None, description="数据源ID", json_schema_extra={"q": "eq"})
    enabled: bool | None = Field(None, description="是否启用", json_schema_extra={"q": "eq"})
    external_name: str | None = Field(None, description="对外名", json_schema_extra={"q": "like"})


class GenbiAclRowPolicyIn(BaseModel):
    """行规则（对齐 tiga）。"""

    model_id: int = Field(..., ge=1, description="MDL 模型ID")
    column_id: int = Field(..., ge=1, description="MDL 列ID")
    operator: AclOperator = Field(..., description="运算符")
    values: list[str] = Field(default_factory=list, description="比较值")
    propagate: bool = Field(default=False, description="是否传播")
    propagate_to_model_ids: list[int] = Field(default_factory=list, description="传播目标模型ID")


class GenbiAclColumnPolicyIn(BaseModel):
    """列规则（对齐 tiga）。"""

    model_id: int = Field(..., ge=1, description="MDL 模型ID")
    column_id: int = Field(..., ge=1, description="MDL 列ID")
    action: AclColumnAction = Field(..., description="mask 或 deny")
    mask_template: AclMaskTemplate | None = Field(default=None, description="掩码模板")


class GenbiGroupDatasourceAclSave(BaseModel):
    """整包替换该关联上的行列 ACL。"""

    row_policies: list[GenbiAclRowPolicyIn] = Field(default_factory=list)
    column_policies: list[GenbiAclColumnPolicyIn] = Field(default_factory=list)


class GenbiGroupDatasourceAclOut(BaseModel):
    """组×源 ACL 响应。不含成员。"""

    group_datasource_id: int
    group_id: int
    datasource_id: int
    row_policies: list[GenbiAclRowPolicyIn] = Field(default_factory=list)
    column_policies: list[GenbiAclColumnPolicyIn] = Field(default_factory=list)
