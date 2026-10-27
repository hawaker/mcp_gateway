from typing import Annotated

from fastapi import APIRouter, Body, Depends, Path, Query, Security
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.response import ResponseSchema, SuccessResponse
from app.core.base_schema import AuthSchema, PageResultSchema, PaginationQueryParam
from app.core.dependencies import AuthPermission, db_getter
from app.core.router_class import OperationLogRoute

from .schema import (
    ConnectionInfoSchema,
    McpCredentialOutSchema,
    McpCredentialQueryParam,
    McpCredentialReissueSchema,
    McpGroupCreateSchema,
    McpGroupMemberCreateSchema,
    McpGroupMemberOutSchema,
    McpGroupMemberQueryParam,
    McpGroupMemberUpdateSchema,
    McpGroupOutSchema,
    McpGroupQueryParam,
    McpGroupToolCreateSchema,
    McpGroupToolOutSchema,
    McpGroupToolQueryParam,
    McpGroupToolUpdateSchema,
    McpGroupUpdateSchema,
    PublishedToolSchema,
)
from .service import McpCredentialService, McpGroupService

McpGroupRouter = APIRouter(route_class=OperationLogRoute, prefix="/mcp-group", tags=["MCP 组"])


@McpGroupRouter.get(
    "/list",
    summary="分页查询 MCP 组",
    response_model=ResponseSchema[PageResultSchema[McpGroupOutSchema]],
)
async def list_mcp_group_controller(
    auth: Annotated[AuthSchema, Security(AuthPermission(["module_mcp_gateway:mcp-group:query"]))],
    db: Annotated[AsyncSession, Depends(db_getter)],
    page: Annotated[PaginationQueryParam, Depends()],
    search: Annotated[McpGroupQueryParam, Query()],
) -> JSONResponse:
    result = await McpGroupService(auth, db).page(
        page_no=page.page_no,
        page_size=page.page_size,
        search=search,
        order_by=page.order_by,
    )
    return SuccessResponse(data=result, msg="查询 MCP 组成功")


@McpGroupRouter.get(
    "/detail/{id}",
    summary="获取 MCP 组详情",
    response_model=ResponseSchema[McpGroupOutSchema],
)
async def detail_mcp_group_controller(
    auth: Annotated[AuthSchema, Security(AuthPermission(["module_mcp_gateway:mcp-group:query"]))],
    db: Annotated[AsyncSession, Depends(db_getter)],
    id: Annotated[int, Path(description="MCP 组ID", ge=1)],
) -> JSONResponse:
    result = await McpGroupService(auth, db).detail(group_id=id)
    return SuccessResponse(data=result, msg="获取 MCP 组详情成功")


@McpGroupRouter.post("/create", summary="创建 MCP 组", response_model=ResponseSchema[McpGroupOutSchema])
async def create_mcp_group_controller(
    auth: Annotated[AuthSchema, Security(AuthPermission(["module_mcp_gateway:mcp-group:create"]))],
    db: Annotated[AsyncSession, Depends(db_getter)],
    data: Annotated[McpGroupCreateSchema, Body(description="创建 MCP 组")],
) -> JSONResponse:
    result = await McpGroupService(auth, db).create(data=data)
    return SuccessResponse(data=result, msg="创建 MCP 组成功")


@McpGroupRouter.put(
    "/update/{id}",
    summary="修改 MCP 组",
    response_model=ResponseSchema[McpGroupOutSchema],
)
async def update_mcp_group_controller(
    auth: Annotated[AuthSchema, Security(AuthPermission(["module_mcp_gateway:mcp-group:update"]))],
    db: Annotated[AsyncSession, Depends(db_getter)],
    id: Annotated[int, Path(description="MCP 组ID", ge=1)],
    data: Annotated[McpGroupUpdateSchema, Body(description="修改 MCP 组")],
) -> JSONResponse:
    result = await McpGroupService(auth, db).update(group_id=id, data=data)
    return SuccessResponse(data=result, msg="修改 MCP 组成功")


@McpGroupRouter.post(
    "/validate-selection/{id}",
    summary="校验组已配置 REST/上游/数据源至少一类",
    response_model=ResponseSchema[None],
)
async def validate_mcp_group_selection_controller(
    auth: Annotated[AuthSchema, Security(AuthPermission(["module_mcp_gateway:mcp-group:query"]))],
    db: Annotated[AsyncSession, Depends(db_getter)],
    id: Annotated[int, Path(description="MCP 组ID", ge=1)],
) -> JSONResponse:
    await McpGroupService(auth, db).validate_selection(group_id=id)
    return SuccessResponse(data=None, msg="组工具选择有效")


@McpGroupRouter.get(
    "/tool/list",
    summary="分页查询组内工具",
    response_model=ResponseSchema[PageResultSchema[McpGroupToolOutSchema]],
)
async def list_mcp_group_tool_controller(
    auth: Annotated[AuthSchema, Security(AuthPermission(["module_mcp_gateway:mcp-group:query"]))],
    db: Annotated[AsyncSession, Depends(db_getter)],
    page: Annotated[PaginationQueryParam, Depends()],
    search: Annotated[McpGroupToolQueryParam, Query()],
) -> JSONResponse:
    result = await McpGroupService(auth, db).page_tools(
        page_no=page.page_no,
        page_size=page.page_size,
        search=search,
        order_by=page.order_by,
    )
    return SuccessResponse(data=result, msg="查询组内工具成功")


@McpGroupRouter.post("/tool/create", summary="添加工具到 MCP 组", response_model=ResponseSchema[McpGroupToolOutSchema])
async def create_mcp_group_tool_controller(
    auth: Annotated[AuthSchema, Security(AuthPermission(["module_mcp_gateway:mcp-group:create"]))],
    db: Annotated[AsyncSession, Depends(db_getter)],
    group_id: Annotated[int, Query(description="MCP 组ID", ge=1)],
    data: Annotated[McpGroupToolCreateSchema, Body(description="组内工具")],
) -> JSONResponse:
    result = await McpGroupService(auth, db).add_tool(group_id=group_id, data=data)
    return SuccessResponse(data=result, msg="添加组内工具成功")


@McpGroupRouter.put(
    "/tool/update/{id}",
    summary="修改组内工具",
    response_model=ResponseSchema[McpGroupToolOutSchema],
)
async def update_mcp_group_tool_controller(
    auth: Annotated[AuthSchema, Security(AuthPermission(["module_mcp_gateway:mcp-group:update"]))],
    db: Annotated[AsyncSession, Depends(db_getter)],
    id: Annotated[int, Path(description="组内工具ID", ge=1)],
    data: Annotated[McpGroupToolUpdateSchema, Body(description="修改组内工具")],
) -> JSONResponse:
    result = await McpGroupService(auth, db).update_tool(tool_id=id, data=data)
    return SuccessResponse(data=result, msg="修改组内工具成功")


@McpGroupRouter.get(
    "/tool/catalog/{id}",
    summary="查看组将对外发布的工具目录",
    response_model=ResponseSchema[list[PublishedToolSchema]],
)
async def catalog_mcp_group_tool_controller(
    auth: Annotated[AuthSchema, Security(AuthPermission(["module_mcp_gateway:mcp-group:query"]))],
    db: Annotated[AsyncSession, Depends(db_getter)],
    id: Annotated[int, Path(description="MCP 组ID", ge=1)],
) -> JSONResponse:
    result = await McpGroupService(auth, db).tools_for(group_id=id)
    return SuccessResponse(data=result, msg="查询工具目录成功")


@McpGroupRouter.get(
    "/member/list",
    summary="分页查询 MCP 组成员",
    response_model=ResponseSchema[PageResultSchema[McpGroupMemberOutSchema]],
)
async def list_mcp_group_member_controller(
    auth: Annotated[AuthSchema, Security(AuthPermission(["module_mcp_gateway:mcp-group:query"]))],
    db: Annotated[AsyncSession, Depends(db_getter)],
    page: Annotated[PaginationQueryParam, Depends()],
    search: Annotated[McpGroupMemberQueryParam, Query()],
) -> JSONResponse:
    result = await McpGroupService(auth, db).page_members(
        page_no=page.page_no,
        page_size=page.page_size,
        search=search,
        order_by=page.order_by,
    )
    return SuccessResponse(data=result, msg="查询组成员成功")


@McpGroupRouter.post("/member/create", summary="添加 MCP 组成员", response_model=ResponseSchema[McpGroupMemberOutSchema])
async def create_mcp_group_member_controller(
    auth: Annotated[AuthSchema, Security(AuthPermission(["module_mcp_gateway:mcp-group:create"]))],
    db: Annotated[AsyncSession, Depends(db_getter)],
    group_id: Annotated[int, Query(description="MCP 组ID", ge=1)],
    data: Annotated[McpGroupMemberCreateSchema, Body(description="成员")],
) -> JSONResponse:
    result = await McpGroupService(auth, db).add_member(group_id=group_id, data=data)
    return SuccessResponse(data=result, msg="添加组成员成功")


@McpGroupRouter.put(
    "/member/update/{id}",
    summary="启用或停用 MCP 组成员",
    response_model=ResponseSchema[McpGroupMemberOutSchema],
)
async def update_mcp_group_member_controller(
    auth: Annotated[AuthSchema, Security(AuthPermission(["module_mcp_gateway:mcp-group:update"]))],
    db: Annotated[AsyncSession, Depends(db_getter)],
    id: Annotated[int, Path(description="成员ID", ge=1)],
    data: Annotated[McpGroupMemberUpdateSchema, Body(description="启用状态")],
) -> JSONResponse:
    result = await McpGroupService(auth, db).update_member(member_id=id, data=data)
    return SuccessResponse(data=result, msg="修改组成员成功")


@McpGroupRouter.get(
    "/credential/list",
    summary="分页查询 MCP 凭证",
    response_model=ResponseSchema[PageResultSchema[McpCredentialOutSchema]],
)
async def list_mcp_credential_controller(
    auth: Annotated[AuthSchema, Security(AuthPermission(["module_mcp_gateway:mcp-group:query"]))],
    db: Annotated[AsyncSession, Depends(db_getter)],
    page: Annotated[PaginationQueryParam, Depends()],
    search: Annotated[McpCredentialQueryParam, Query()],
) -> JSONResponse:
    result = await McpCredentialService(auth, db).page(
        page_no=page.page_no,
        page_size=page.page_size,
        search=search,
        order_by=page.order_by,
    )
    return SuccessResponse(data=result, msg="查询凭证成功")


@McpGroupRouter.get(
    "/connection/{user_id}/{group_id}",
    summary="查看 MCP 连接信息",
    response_model=ResponseSchema[ConnectionInfoSchema],
)
async def connection_mcp_group_controller(
    auth: Annotated[AuthSchema, Security(AuthPermission(["module_mcp_gateway:mcp-group:query"]))],
    db: Annotated[AsyncSession, Depends(db_getter)],
    user_id: Annotated[int, Path(description="业务用户ID", ge=1)],
    group_id: Annotated[int, Path(description="MCP 组ID", ge=1)],
) -> JSONResponse:
    result = await McpCredentialService(auth, db).connection_info(user_id=user_id, group_id=group_id)
    return SuccessResponse(data=result, msg="获取连接信息成功")


@McpGroupRouter.post(
    "/credential/reissue",
    summary="重新签发 MCP 凭证",
    response_model=ResponseSchema[ConnectionInfoSchema],
)
async def reissue_mcp_credential_controller(
    auth: Annotated[AuthSchema, Security(AuthPermission(["module_mcp_gateway:mcp-group:update"]))],
    db: Annotated[AsyncSession, Depends(db_getter)],
    data: Annotated[McpCredentialReissueSchema, Body(description="重新签发")],
) -> JSONResponse:
    service = McpCredentialService(auth, db)
    await service.reissue(user_id=data.user_id, group_id=data.group_id)
    result = await service.connection_info(user_id=data.user_id, group_id=data.group_id)
    return SuccessResponse(data=result, msg="重新签发成功")
