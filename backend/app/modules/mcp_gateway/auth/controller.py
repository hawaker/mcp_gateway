from typing import Annotated

from fastapi import APIRouter, Body, Depends, Path, Query, Security
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.response import ResponseSchema, SuccessResponse
from app.core.base_schema import AuthSchema, PageResultSchema, PaginationQueryParam
from app.core.dependencies import AuthPermission, db_getter
from app.core.router_class import OperationLogRoute

from .schema import AuthConfigCreateSchema, AuthConfigOutSchema, AuthConfigQueryParam, AuthConfigUpdateSchema
from .service import AuthConfigService

BizAuthRouter = APIRouter(route_class=OperationLogRoute, prefix="/biz-auth", tags=["业务鉴权"])


@BizAuthRouter.get("/list", summary="分页查询业务鉴权", response_model=ResponseSchema[PageResultSchema[AuthConfigOutSchema]])
async def list_biz_auth_controller(
    auth: Annotated[AuthSchema, Security(AuthPermission(["module_mcp_gateway:biz-auth:query"]))],
    db: Annotated[AsyncSession, Depends(db_getter)],
    page: Annotated[PaginationQueryParam, Depends()],
    search: Annotated[AuthConfigQueryParam, Query()],
) -> JSONResponse:
    result = await AuthConfigService(auth, db).page(
        page_no=page.page_no,
        page_size=page.page_size,
        search=search,
        order_by=page.order_by,
    )
    return SuccessResponse(data=result, msg="查询业务鉴权成功")


@BizAuthRouter.get("/detail/{id}", summary="获取业务鉴权详情", response_model=ResponseSchema[AuthConfigOutSchema])
async def detail_biz_auth_controller(
    auth: Annotated[AuthSchema, Security(AuthPermission(["module_mcp_gateway:biz-auth:query"]))],
    db: Annotated[AsyncSession, Depends(db_getter)],
    id: Annotated[int, Path(description="鉴权配置ID", ge=1)],
) -> JSONResponse:
    result = await AuthConfigService(auth, db).detail(config_id=id)
    return SuccessResponse(data=result, msg="获取业务鉴权详情成功")


@BizAuthRouter.post("/create", summary="创建业务鉴权", response_model=ResponseSchema[AuthConfigOutSchema])
async def create_biz_auth_controller(
    auth: Annotated[AuthSchema, Security(AuthPermission(["module_mcp_gateway:biz-auth:create"]))],
    db: Annotated[AsyncSession, Depends(db_getter)],
    data: Annotated[AuthConfigCreateSchema, Body(description="创建业务鉴权")],
) -> JSONResponse:
    result = await AuthConfigService(auth, db).create(data=data)
    return SuccessResponse(data=result, msg="创建业务鉴权成功")


@BizAuthRouter.put("/update/{id}", summary="修改业务鉴权", response_model=ResponseSchema[AuthConfigOutSchema])
async def update_biz_auth_controller(
    auth: Annotated[AuthSchema, Security(AuthPermission(["module_mcp_gateway:biz-auth:update"]))],
    db: Annotated[AsyncSession, Depends(db_getter)],
    id: Annotated[int, Path(description="鉴权配置ID", ge=1)],
    data: Annotated[AuthConfigUpdateSchema, Body(description="修改业务鉴权")],
) -> JSONResponse:
    result = await AuthConfigService(auth, db).update(config_id=id, data=data)
    return SuccessResponse(data=result, msg="修改业务鉴权成功")
