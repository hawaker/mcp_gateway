from typing import Annotated

from fastapi import APIRouter, Body, Depends, Path, Query, Security
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.response import ResponseSchema, SuccessResponse
from app.core.base_schema import AuthSchema, PageResultSchema, PaginationQueryParam
from app.core.dependencies import AuthPermission, db_getter
from app.core.router_class import OperationLogRoute

from .schema import BizSystemCreateSchema, BizSystemOutSchema, BizSystemQueryParam, BizSystemUpdateSchema
from .service import BizSystemService

BizSystemRouter = APIRouter(route_class=OperationLogRoute, prefix="/biz-system", tags=["业务系统"])


@BizSystemRouter.get("/list", summary="分页查询业务系统", response_model=ResponseSchema[PageResultSchema[BizSystemOutSchema]])
async def list_biz_system_controller(
    auth: Annotated[AuthSchema, Security(AuthPermission(["module_mcp_gateway:biz-system:query"]))],
    db: Annotated[AsyncSession, Depends(db_getter)],
    page: Annotated[PaginationQueryParam, Depends()],
    search: Annotated[BizSystemQueryParam, Query()],
) -> JSONResponse:
    result = await BizSystemService(auth, db).page(
        page_no=page.page_no,
        page_size=page.page_size,
        search=search,
        order_by=page.order_by,
    )
    return SuccessResponse(data=result, msg="查询业务系统成功")


@BizSystemRouter.get("/detail/{id}", summary="获取业务系统详情", response_model=ResponseSchema[BizSystemOutSchema])
async def detail_biz_system_controller(
    auth: Annotated[AuthSchema, Security(AuthPermission(["module_mcp_gateway:biz-system:query"]))],
    db: Annotated[AsyncSession, Depends(db_getter)],
    id: Annotated[int, Path(description="业务系统ID", ge=1)],
) -> JSONResponse:
    result = await BizSystemService(auth, db).detail(system_id=id)
    return SuccessResponse(data=result, msg="获取业务系统详情成功")


@BizSystemRouter.post("/create", summary="创建业务系统", response_model=ResponseSchema[BizSystemOutSchema])
async def create_biz_system_controller(
    auth: Annotated[AuthSchema, Security(AuthPermission(["module_mcp_gateway:biz-system:create"]))],
    db: Annotated[AsyncSession, Depends(db_getter)],
    data: Annotated[BizSystemCreateSchema, Body(description="创建业务系统")],
) -> JSONResponse:
    result = await BizSystemService(auth, db).create(data=data)
    return SuccessResponse(data=result, msg="创建业务系统成功")


@BizSystemRouter.put("/update/{id}", summary="修改业务系统", response_model=ResponseSchema[BizSystemOutSchema])
async def update_biz_system_controller(
    auth: Annotated[AuthSchema, Security(AuthPermission(["module_mcp_gateway:biz-system:update"]))],
    db: Annotated[AsyncSession, Depends(db_getter)],
    id: Annotated[int, Path(description="业务系统ID", ge=1)],
    data: Annotated[BizSystemUpdateSchema, Body(description="修改业务系统")],
) -> JSONResponse:
    result = await BizSystemService(auth, db).update(system_id=id, data=data)
    return SuccessResponse(data=result, msg="修改业务系统成功")
