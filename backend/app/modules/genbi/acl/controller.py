from typing import Annotated

from fastapi import APIRouter, Body, Depends, Path, Query, Security
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.response import ResponseSchema, SuccessResponse
from app.core.base_schema import AuthSchema, PageResultSchema, PaginationQueryParam
from app.core.dependencies import AuthPermission, db_getter
from app.core.router_class import OperationLogRoute

from .schema import (
    GenbiGroupDatasourceAclOut,
    GenbiGroupDatasourceAclSave,
    GenbiGroupDatasourceAttach,
    GenbiGroupDatasourceOut,
    GenbiGroupDatasourceQueryParam,
    GenbiGroupDatasourceUpdate,
)
from .service import GenbiGroupDatasourceService

GenbiGroupDatasourceRouter = APIRouter(
    route_class=OperationLogRoute,
    prefix="/mcp-group/datasource",
    tags=["MCP 组数据源 ACL"],
)


@GenbiGroupDatasourceRouter.get(
    "/list",
    summary="分页查询组内数据源",
    response_model=ResponseSchema[PageResultSchema[GenbiGroupDatasourceOut]],
)
async def list_group_datasource_controller(
    auth: Annotated[AuthSchema, Security(AuthPermission(["module_mcp_gateway:mcp-group:query"]))],
    db: Annotated[AsyncSession, Depends(db_getter)],
    page: Annotated[PaginationQueryParam, Depends()],
    search: Annotated[GenbiGroupDatasourceQueryParam, Query()],
) -> JSONResponse:
    result = await GenbiGroupDatasourceService(auth, db).page(
        page_no=page.page_no,
        page_size=page.page_size,
        search=search,
        order_by=page.order_by,
    )
    return SuccessResponse(data=result, msg="查询组数据源成功")


@GenbiGroupDatasourceRouter.post(
    "/attach",
    summary="将数据源挂到 MCP 组",
    response_model=ResponseSchema[GenbiGroupDatasourceOut],
)
async def attach_group_datasource_controller(
    auth: Annotated[AuthSchema, Security(AuthPermission(["module_mcp_gateway:mcp-group:create"]))],
    db: Annotated[AsyncSession, Depends(db_getter)],
    group_id: Annotated[int, Query(description="MCP 组ID", ge=1)],
    data: Annotated[GenbiGroupDatasourceAttach, Body(description="数据源关联")],
) -> JSONResponse:
    result = await GenbiGroupDatasourceService(auth, db).attach(
        group_id=group_id,
        datasource_id=data.datasource_id,
        external_name=data.external_name,
        enabled=data.enabled,
    )
    return SuccessResponse(data=result, msg="关联数据源成功")


@GenbiGroupDatasourceRouter.put(
    "/update/{id}",
    summary="修改组数据源别名或启用状态",
    response_model=ResponseSchema[GenbiGroupDatasourceOut],
)
async def update_group_datasource_controller(
    auth: Annotated[AuthSchema, Security(AuthPermission(["module_mcp_gateway:mcp-group:update"]))],
    db: Annotated[AsyncSession, Depends(db_getter)],
    id: Annotated[int, Path(description="关联ID", ge=1)],
    data: Annotated[GenbiGroupDatasourceUpdate, Body(description="修改关联")],
) -> JSONResponse:
    result = await GenbiGroupDatasourceService(auth, db).update(link_id=id, data=data)
    return SuccessResponse(data=result, msg="修改组数据源成功")


@GenbiGroupDatasourceRouter.get(
    "/acl/{id}",
    summary="获取组×源共享 ACL",
    response_model=ResponseSchema[GenbiGroupDatasourceAclOut],
)
async def get_group_datasource_acl_controller(
    auth: Annotated[AuthSchema, Security(AuthPermission(["module_mcp_gateway:mcp-group:query"]))],
    db: Annotated[AsyncSession, Depends(db_getter)],
    id: Annotated[int, Path(description="关联ID", ge=1)],
) -> JSONResponse:
    result = await GenbiGroupDatasourceService(auth, db).get_acl(link_id=id)
    return SuccessResponse(data=result, msg="获取 ACL 成功")


@GenbiGroupDatasourceRouter.put(
    "/acl/{id}",
    summary="保存组×源共享 ACL（整包替换）",
    response_model=ResponseSchema[GenbiGroupDatasourceAclOut],
)
async def save_group_datasource_acl_controller(
    auth: Annotated[AuthSchema, Security(AuthPermission(["module_mcp_gateway:mcp-group:update"]))],
    db: Annotated[AsyncSession, Depends(db_getter)],
    id: Annotated[int, Path(description="关联ID", ge=1)],
    data: Annotated[GenbiGroupDatasourceAclSave, Body(description="行列 ACL")],
) -> JSONResponse:
    result = await GenbiGroupDatasourceService(auth, db).save_acl(link_id=id, data=data)
    return SuccessResponse(data=result, msg="保存 ACL 成功")
