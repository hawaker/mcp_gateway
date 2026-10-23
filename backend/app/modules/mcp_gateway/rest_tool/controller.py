from typing import Annotated

from fastapi import APIRouter, Body, Depends, Path, Query, Security
from fastapi.responses import JSONResponse
from redis.asyncio.client import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.response import ResponseSchema, SuccessResponse
from app.core.base_schema import AuthSchema, PageResultSchema, PaginationQueryParam
from app.core.dependencies import AuthPermission, db_getter, redis_getter
from app.core.exceptions import CustomException
from app.core.router_class import OperationLogRoute
from app.modules.mcp_gateway.auth.client import BindingUnavailable

from .schema import (
    RestToolCreateSchema,
    RestToolDebugResultSchema,
    RestToolDebugSchema,
    RestToolOutSchema,
    RestToolQueryParam,
    RestToolUpdateSchema,
)
from .service import RestToolService

RestToolRouter = APIRouter(route_class=OperationLogRoute, prefix="/rest-tool", tags=["REST 工具"])


@RestToolRouter.get("/list", summary="分页查询 REST 工具", response_model=ResponseSchema[PageResultSchema[RestToolOutSchema]])
async def list_rest_tool_controller(
    auth: Annotated[AuthSchema, Security(AuthPermission(["module_mcp_gateway:rest-tool:query"]))],
    db: Annotated[AsyncSession, Depends(db_getter)],
    page: Annotated[PaginationQueryParam, Depends()],
    search: Annotated[RestToolQueryParam, Query()],
) -> JSONResponse:
    result = await RestToolService(auth, db).page(
        page_no=page.page_no,
        page_size=page.page_size,
        search=search,
        order_by=page.order_by,
    )
    return SuccessResponse(data=result, msg="查询 REST 工具成功")


@RestToolRouter.get("/detail/{id}", summary="获取 REST 工具详情", response_model=ResponseSchema[RestToolOutSchema])
async def detail_rest_tool_controller(
    auth: Annotated[AuthSchema, Security(AuthPermission(["module_mcp_gateway:rest-tool:query"]))],
    db: Annotated[AsyncSession, Depends(db_getter)],
    id: Annotated[int, Path(description="REST 工具ID", ge=1)],
) -> JSONResponse:
    result = await RestToolService(auth, db).detail(tool_id=id)
    return SuccessResponse(data=result, msg="获取 REST 工具详情成功")


@RestToolRouter.post("/create", summary="创建 REST 工具", response_model=ResponseSchema[RestToolOutSchema])
async def create_rest_tool_controller(
    auth: Annotated[AuthSchema, Security(AuthPermission(["module_mcp_gateway:rest-tool:create"]))],
    db: Annotated[AsyncSession, Depends(db_getter)],
    data: Annotated[RestToolCreateSchema, Body(description="创建 REST 工具")],
) -> JSONResponse:
    result = await RestToolService(auth, db).create(data=data)
    return SuccessResponse(data=result, msg="创建 REST 工具成功")


@RestToolRouter.put("/update/{id}", summary="修改 REST 工具", response_model=ResponseSchema[RestToolOutSchema])
async def update_rest_tool_controller(
    auth: Annotated[AuthSchema, Security(AuthPermission(["module_mcp_gateway:rest-tool:update"]))],
    db: Annotated[AsyncSession, Depends(db_getter)],
    id: Annotated[int, Path(description="REST 工具ID", ge=1)],
    data: Annotated[RestToolUpdateSchema, Body(description="修改 REST 工具")],
) -> JSONResponse:
    result = await RestToolService(auth, db).update(tool_id=id, data=data)
    return SuccessResponse(data=result, msg="修改 REST 工具成功")


@RestToolRouter.post("/debug", summary="调试未保存的 REST 工具", response_model=ResponseSchema[RestToolDebugResultSchema])
async def debug_rest_tool_controller(
    auth: Annotated[AuthSchema, Security(AuthPermission(["module_mcp_gateway:rest-tool:debug"]))],
    db: Annotated[AsyncSession, Depends(db_getter)],
    redis: Annotated[Redis, Depends(redis_getter)],
    data: Annotated[RestToolDebugSchema, Body(description="未保存的表单")],
) -> JSONResponse:
    try:
        result = await RestToolService(auth, db, redis).debug(
            draft=data.draft,
            user_id=data.user_id,
            arguments=data.arguments,
            reveal=data.reveal,
        )
    except BindingUnavailable:
        raise CustomException(msg="没有可用的业务绑定") from None
    return SuccessResponse(data=result, msg="调试 REST 工具成功")
