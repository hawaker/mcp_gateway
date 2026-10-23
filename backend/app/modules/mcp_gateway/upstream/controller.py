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

UpstreamRouter = APIRouter(route_class=OperationLogRoute, prefix="/upstream", tags=["上游 MCP"])


@UpstreamRouter.get(
    "/list",
    summary="分页查询上游 MCP",
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
    return SuccessResponse(data=result, msg="查询上游 MCP 成功")


@UpstreamRouter.get(
    "/detail/{id}",
    summary="获取上游 MCP 详情",
    response_model=ResponseSchema[UpstreamMcpOutSchema],
)
async def detail_upstream_controller(
    auth: Annotated[AuthSchema, Security(AuthPermission(["module_mcp_gateway:upstream:query"]))],
    db: Annotated[AsyncSession, Depends(db_getter)],
    id: Annotated[int, Path(description="上游 MCP ID", ge=1)],
) -> JSONResponse:
    result = await UpstreamService(auth, db).detail(upstream_id=id)
    return SuccessResponse(data=result, msg="获取上游 MCP 详情成功")


@UpstreamRouter.post("/create", summary="创建上游 MCP", response_model=ResponseSchema[UpstreamMcpOutSchema])
async def create_upstream_controller(
    auth: Annotated[AuthSchema, Security(AuthPermission(["module_mcp_gateway:upstream:create"]))],
    db: Annotated[AsyncSession, Depends(db_getter)],
    data: Annotated[UpstreamMcpCreateSchema, Body(description="创建上游 MCP")],
) -> JSONResponse:
    result = await UpstreamService(auth, db).create(data=data)
    return SuccessResponse(data=result, msg="创建上游 MCP 成功")


@UpstreamRouter.put(
    "/update/{id}",
    summary="修改上游 MCP",
    response_model=ResponseSchema[UpstreamMcpOutSchema],
)
async def update_upstream_controller(
    auth: Annotated[AuthSchema, Security(AuthPermission(["module_mcp_gateway:upstream:update"]))],
    db: Annotated[AsyncSession, Depends(db_getter)],
    id: Annotated[int, Path(description="上游 MCP ID", ge=1)],
    data: Annotated[UpstreamMcpUpdateSchema, Body(description="修改上游 MCP")],
) -> JSONResponse:
    result = await UpstreamService(auth, db).update(upstream_id=id, data=data)
    return SuccessResponse(data=result, msg="修改上游 MCP 成功")


@UpstreamRouter.get(
    "/tool/list",
    summary="分页查询上游工具",
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
    return SuccessResponse(data=result, msg="查询上游工具成功")


@UpstreamRouter.put(
    "/tool/update/{id}",
    summary="选用上游工具",
    response_model=ResponseSchema[UpstreamToolOutSchema],
)
async def update_upstream_tool_controller(
    auth: Annotated[AuthSchema, Security(AuthPermission(["module_mcp_gateway:upstream:update"]))],
    db: Annotated[AsyncSession, Depends(db_getter)],
    id: Annotated[int, Path(description="上游工具 ID", ge=1)],
    data: Annotated[UpstreamToolUpdateSchema, Body(description="是否选用")],
) -> JSONResponse:
    result = await UpstreamService(auth, db).update_tool(tool_id=id, data=data)
    return SuccessResponse(data=result, msg="修改上游工具成功")


@UpstreamRouter.post(
    "/tool/refresh/{id}",
    summary="拉取上游工具列表",
    response_model=ResponseSchema[list[ToolSnapshot]],
)
async def refresh_upstream_tool_controller(
    auth: Annotated[AuthSchema, Security(AuthPermission(["module_mcp_gateway:upstream:update"]))],
    db: Annotated[AsyncSession, Depends(db_getter)],
    id: Annotated[int, Path(description="上游 MCP ID", ge=1)],
) -> JSONResponse:
    result = await UpstreamService(auth, db).refresh(upstream_id=id)
    return SuccessResponse(data=result, msg="拉取上游工具成功")
