from typing import Annotated

from fastapi import APIRouter, Body, Depends, Path, Query, Security
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.response import ResponseSchema, SuccessResponse
from app.core.base_schema import AuthSchema, PageResultSchema, PaginationQueryParam
from app.core.dependencies import AuthPermission, db_getter
from app.core.router_class import OperationLogRoute

from .schema import BizBindingCreateSchema, BizBindingOutSchema, BizBindingQueryParam, BizBindingUpdateSchema
from .service import BizBindingService

BizBindingRouter = APIRouter(route_class=OperationLogRoute, prefix="/biz-binding", tags=["业务系统绑定"])


@BizBindingRouter.get("/list", summary="分页查询业务系统绑定", response_model=ResponseSchema[PageResultSchema[BizBindingOutSchema]])
async def list_biz_binding_controller(
    auth: Annotated[AuthSchema, Security(AuthPermission(["module_mcp_gateway:biz-binding:query"]))],
    db: Annotated[AsyncSession, Depends(db_getter)],
    page: Annotated[PaginationQueryParam, Depends()],
    search: Annotated[BizBindingQueryParam, Query()],
) -> JSONResponse:
    result = await BizBindingService(auth, db).page(
        page_no=page.page_no,
        page_size=page.page_size,
        search=search,
        order_by=page.order_by,
    )
    return SuccessResponse(data=result, msg="查询业务系统绑定成功")


@BizBindingRouter.get("/detail/{id}", summary="获取业务系统绑定详情", response_model=ResponseSchema[BizBindingOutSchema])
async def detail_biz_binding_controller(
    auth: Annotated[AuthSchema, Security(AuthPermission(["module_mcp_gateway:biz-binding:query"]))],
    db: Annotated[AsyncSession, Depends(db_getter)],
    id: Annotated[int, Path(description="绑定ID", ge=1)],
) -> JSONResponse:
    result = await BizBindingService(auth, db).detail(binding_id=id)
    return SuccessResponse(data=result, msg="获取业务系统绑定详情成功")


@BizBindingRouter.post("/create", summary="创建业务系统绑定", response_model=ResponseSchema[BizBindingOutSchema])
async def create_biz_binding_controller(
    auth: Annotated[AuthSchema, Security(AuthPermission(["module_mcp_gateway:biz-binding:create"]))],
    db: Annotated[AsyncSession, Depends(db_getter)],
    data: Annotated[BizBindingCreateSchema, Body(description="创建业务系统绑定")],
) -> JSONResponse:
    result = await BizBindingService(auth, db).upsert(data=data)
    return SuccessResponse(data=result, msg="创建业务系统绑定成功")


@BizBindingRouter.put("/update/{id}", summary="修改业务系统绑定", response_model=ResponseSchema[BizBindingOutSchema])
async def update_biz_binding_controller(
    auth: Annotated[AuthSchema, Security(AuthPermission(["module_mcp_gateway:biz-binding:update"]))],
    db: Annotated[AsyncSession, Depends(db_getter)],
    id: Annotated[int, Path(description="绑定ID", ge=1)],
    data: Annotated[BizBindingUpdateSchema, Body(description="修改业务系统绑定")],
) -> JSONResponse:
    result = await BizBindingService(auth, db).update(binding_id=id, data=data)
    return SuccessResponse(data=result, msg="修改业务系统绑定成功")
