from typing import Annotated

from fastapi import APIRouter, Body, Depends, Path, Query, Security, status
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.response import ResponseSchema, SuccessResponse
from app.core.base_schema import AuthSchema, PageResultSchema, PaginationQueryParam
from app.core.dependencies import AuthPermission, db_getter
from app.core.router_class import OperationLogRoute

from .schema import (
    BizUserCreateSchema,
    BizUserGroupCreateSchema,
    BizUserGroupMemberCreateSchema,
    BizUserGroupMemberOutSchema,
    BizUserGroupOutSchema,
    BizUserGroupQueryParam,
    BizUserOutSchema,
    BizUserQueryParam,
)
from .service import BizUserGroupService, BizUserService

BizUserRouter = APIRouter(route_class=OperationLogRoute, prefix="/biz-user", tags=["业务用户"])
BizUserGroupRouter = APIRouter(route_class=OperationLogRoute, prefix="/biz-user-group", tags=["业务用户组"])


@BizUserRouter.get("/list", summary="分页查询业务用户", response_model=ResponseSchema[PageResultSchema[BizUserOutSchema]])
async def list_biz_user_controller(
    auth: Annotated[AuthSchema, Security(AuthPermission(["module_mcp_gateway:biz-user:query"]))],
    db: Annotated[AsyncSession, Depends(db_getter)],
    page: Annotated[PaginationQueryParam, Depends()],
    search: Annotated[BizUserQueryParam, Query()],
) -> JSONResponse:
    result = await BizUserService(auth, db).page(
        page_no=page.page_no,
        page_size=page.page_size,
        search=search,
        order_by=page.order_by,
    )
    return SuccessResponse(data=result, msg="查询业务用户成功")


@BizUserRouter.post("/create", status_code=status.HTTP_201_CREATED, summary="创建业务用户", response_model=ResponseSchema[BizUserOutSchema])
async def create_biz_user_controller(
    auth: Annotated[AuthSchema, Security(AuthPermission(["module_mcp_gateway:biz-user:create"]))],
    db: Annotated[AsyncSession, Depends(db_getter)],
    data: Annotated[BizUserCreateSchema, Body(description="创建业务用户")],
) -> JSONResponse:
    result = await BizUserService(auth, db).create(data=data)
    return SuccessResponse(data=result, msg="创建业务用户成功")


@BizUserGroupRouter.get(
    "/list",
    summary="分页查询业务用户组",
    response_model=ResponseSchema[PageResultSchema[BizUserGroupOutSchema]],
)
async def list_biz_user_group_controller(
    auth: Annotated[AuthSchema, Security(AuthPermission(["module_mcp_gateway:biz-user-group:query"]))],
    db: Annotated[AsyncSession, Depends(db_getter)],
    page: Annotated[PaginationQueryParam, Depends()],
    search: Annotated[BizUserGroupQueryParam, Query()],
) -> JSONResponse:
    result = await BizUserGroupService(auth, db).page(
        page_no=page.page_no,
        page_size=page.page_size,
        search=search,
        order_by=page.order_by,
    )
    return SuccessResponse(data=result, msg="查询业务用户组成功")


@BizUserGroupRouter.post("/create", status_code=status.HTTP_201_CREATED, summary="创建业务用户组", response_model=ResponseSchema[BizUserGroupOutSchema])
async def create_biz_user_group_controller(
    auth: Annotated[AuthSchema, Security(AuthPermission(["module_mcp_gateway:biz-user-group:create"]))],
    db: Annotated[AsyncSession, Depends(db_getter)],
    data: Annotated[BizUserGroupCreateSchema, Body(description="创建业务用户组")],
) -> JSONResponse:
    result = await BizUserGroupService(auth, db).create(data=data)
    return SuccessResponse(data=result, msg="创建业务用户组成功")


@BizUserGroupRouter.get(
    "/{id}/members",
    summary="查询业务用户组成员",
    response_model=ResponseSchema[BizUserGroupMemberOutSchema],
)
async def list_biz_user_group_members_controller(
    auth: Annotated[AuthSchema, Security(AuthPermission(["module_mcp_gateway:biz-user-group:query"]))],
    db: Annotated[AsyncSession, Depends(db_getter)],
    id: Annotated[int, Path(description="用户组ID", ge=1)],
) -> JSONResponse:
    user_ids = await BizUserGroupService(auth, db).list_member_user_ids(group_id=id)
    result = BizUserGroupMemberOutSchema(id=id, user_ids=user_ids)
    return SuccessResponse(data=result, msg="查询组成员成功")


@BizUserGroupRouter.post(
    "/{id}/members",
    summary="添加业务用户组成员",
    response_model=ResponseSchema[BizUserGroupMemberOutSchema],
)
async def add_biz_user_group_members_controller(
    auth: Annotated[AuthSchema, Security(AuthPermission(["module_mcp_gateway:biz-user-group:update"]))],
    db: Annotated[AsyncSession, Depends(db_getter)],
    id: Annotated[int, Path(description="用户组ID", ge=1)],
    data: Annotated[BizUserGroupMemberCreateSchema, Body(description="成员用户ID列表")],
) -> JSONResponse:
    service = BizUserService(auth, db)
    for user_id in data.user_ids:
        await service.add_to_groups(user_id, [id])
    result = BizUserGroupMemberOutSchema(id=id, user_ids=data.user_ids)
    return SuccessResponse(data=result, msg="添加组成员成功")
