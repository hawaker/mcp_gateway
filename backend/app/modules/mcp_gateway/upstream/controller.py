from typing import Annotated

from fastapi import APIRouter, Body, Depends, Path, Query, Security
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.response import ResponseSchema, SuccessResponse
from app.core.base_schema import AuthSchema, PageResultSchema, PaginationQueryParam
from app.core.dependencies import AuthPermission, db_getter
from app.core.router_class import OperationLogRoute

from .schema import (
    ToolSnapshot,
    UpstreamMcpCreateSchema,
    UpstreamMcpOutSchema,
    UpstreamMcpQueryParam,
    UpstreamMcpUpdateSchema,
    UpstreamToolOutSchema,
    UpstreamToolQueryParam,
    UpstreamToolUpdateSchema,
)
from .service import UpstreamService

UpstreamRouter = APIRouter(route_class=OperationLogRoute, prefix="/upstream", tags=["MCP 代理"])


@UpstreamRouter.get(
    "/list",
    summary="分页查询MCP 代理",
    response_model=ResponseSchema[PageResultSchema[UpstreamMcpOutSchema]],
)
async def list_upstream_controller(
    auth: Annotated[AuthSchema, Security(AuthPermission(["module_mcp_gateway:upstream:query"]))],
    db: Annotated[AsyncSession, Depends(db_getter)],
    page: Annotated[PaginationQueryParam, Depends()],
    search: Annotated[UpstreamMcpQueryParam, Query()],
) -> JSONResponse:
    result = await UpstreamService(auth, db).page(
        page_no=page.page_no,
        page_size=page.page_size,
        search=search,
        order_by=page.order_by,
    )
    return SuccessResponse(data=result, msg="查询MCP 代理 成功")


@UpstreamRouter.get(
    "/detail/{id}",
    summary="获取MCP 代理 详情",
    response_model=ResponseSchema[UpstreamMcpOutSchema],
)
async def detail_upstream_controller(
    auth: Annotated[AuthSchema, Security(AuthPermission(["module_mcp_gateway:upstream:query"]))],
    db: Annotated[AsyncSession, Depends(db_getter)],
    id: Annotated[int, Path(description="MCP 代理 ID", ge=1)],
) -> JSONResponse:
    result = await UpstreamService(auth, db).detail(upstream_id=id)
    return SuccessResponse(data=result, msg="获取MCP 代理 详情成功")


@UpstreamRouter.post("/create", summary="创建MCP 代理", response_model=ResponseSchema[UpstreamMcpOutSchema])
async def create_upstream_controller(
    auth: Annotated[AuthSchema, Security(AuthPermission(["module_mcp_gateway:upstream:create"]))],
    db: Annotated[AsyncSession, Depends(db_getter)],
    data: Annotated[UpstreamMcpCreateSchema, Body(description="创建MCP 代理")],
) -> JSONResponse:
    result = await UpstreamService(auth, db).create(data=data)
    return SuccessResponse(data=result, msg="创建MCP 代理 成功")


@UpstreamRouter.put(
    "/update/{id}",
    summary="修改MCP 代理",
    response_model=ResponseSchema[UpstreamMcpOutSchema],
)
async def update_upstream_controller(
    auth: Annotated[AuthSchema, Security(AuthPermission(["module_mcp_gateway:upstream:update"]))],
    db: Annotated[AsyncSession, Depends(db_getter)],
    id: Annotated[int, Path(description="MCP 代理 ID", ge=1)],
    data: Annotated[UpstreamMcpUpdateSchema, Body(description="修改MCP 代理")],
) -> JSONResponse:
    result = await UpstreamService(auth, db).update(upstream_id=id, data=data)
    return SuccessResponse(data=result, msg="修改MCP 代理 成功")


@UpstreamRouter.delete("/delete", summary="删除MCP 代理", response_model=ResponseSchema[None])
async def delete_upstream_controller(
    auth: Annotated[AuthSchema, Security(AuthPermission(["module_mcp_gateway:upstream:delete"]))],
    db: Annotated[AsyncSession, Depends(db_getter)],
    ids: Annotated[list[int], Body(description="MCP 代理 ID列表")],
) -> JSONResponse:
    await UpstreamService(auth, db).delete(ids=ids)
    return SuccessResponse(msg="删除MCP 代理 成功")


@UpstreamRouter.get(
    "/tool/list",
    summary="分页查询代理工具",
    response_model=ResponseSchema[PageResultSchema[UpstreamToolOutSchema]],
)
async def list_upstream_tool_controller(
    auth: Annotated[AuthSchema, Security(AuthPermission(["module_mcp_gateway:upstream:query"]))],
    db: Annotated[AsyncSession, Depends(db_getter)],
    page: Annotated[PaginationQueryParam, Depends()],
    search: Annotated[UpstreamToolQueryParam, Query()],
) -> JSONResponse:
    result = await UpstreamService(auth, db).page_tools(
        page_no=page.page_no,
        page_size=page.page_size,
        search=search,
        order_by=page.order_by,
    )
    return SuccessResponse(data=result, msg="查询代理工具成功")


@UpstreamRouter.put(
    "/tool/update/{id}",
    summary="选用代理工具",
    response_model=ResponseSchema[UpstreamToolOutSchema],
)
async def update_upstream_tool_controller(
    auth: Annotated[AuthSchema, Security(AuthPermission(["module_mcp_gateway:upstream:update"]))],
    db: Annotated[AsyncSession, Depends(db_getter)],
    id: Annotated[int, Path(description="代理工具 ID", ge=1)],
    data: Annotated[UpstreamToolUpdateSchema, Body(description="是否选用")],
) -> JSONResponse:
    result = await UpstreamService(auth, db).update_tool(tool_id=id, data=data)
    return SuccessResponse(data=result, msg="修改代理工具成功")


@UpstreamRouter.post(
    "/tool/refresh/{id}",
    summary="拉取代理工具列表",
    response_model=ResponseSchema[list[ToolSnapshot]],
)
async def refresh_upstream_tool_controller(
    auth: Annotated[AuthSchema, Security(AuthPermission(["module_mcp_gateway:upstream:update"]))],
    db: Annotated[AsyncSession, Depends(db_getter)],
    id: Annotated[int, Path(description="MCP 代理 ID", ge=1)],
) -> JSONResponse:
    result = await UpstreamService(auth, db).refresh(upstream_id=id)
    return SuccessResponse(data=result, msg="拉取代理工具成功")
