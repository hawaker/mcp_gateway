"""管理员 MCP 调试接口。业务用户不能调用。"""

from typing import Annotated

from fastapi import APIRouter, Body, Depends, Security
from fastapi.responses import JSONResponse
from redis.asyncio.client import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.response import ResponseSchema, SuccessResponse
from app.core.base_schema import AuthSchema
from app.core.dependencies import AuthPermission, db_getter, redis_getter
from app.core.router_class import OperationLogRoute

from .debug import (
    DebugCallSchema,
    DebugService,
    DebugSessionResultSchema,
    DebugTargetSchema,
    DebugToolsCallResultSchema,
    DebugToolsListResultSchema,
)

McpDebugRouter = APIRouter(route_class=OperationLogRoute, prefix="/debug", tags=["MCP 调试"])


@McpDebugRouter.post(
    "/session",
    summary="连接并 initialize",
    response_model=ResponseSchema[DebugSessionResultSchema],
)
async def debug_session_controller(
    auth: Annotated[AuthSchema, Security(AuthPermission(["module_mcp_gateway:debug:session"]))],
    db: Annotated[AsyncSession, Depends(db_getter)],
    redis: Annotated[Redis, Depends(redis_getter)],
    data: Annotated[DebugTargetSchema, Body(description="调试目标")],
) -> JSONResponse:
    result = await DebugService(auth, db, redis).session(
        target=data.target,
        group_id=data.group_id,
        user_id=data.user_id,
        transport=data.transport,
        upstream_id=data.upstream_id,
        url=data.url,
        headers=data.headers,
        reveal=data.reveal,
    )
    return SuccessResponse(data=result, msg="连接调试目标成功")


@McpDebugRouter.post(
    "/tools/list",
    summary="调试 tools/list",
    response_model=ResponseSchema[DebugToolsListResultSchema],
)
async def debug_tools_list_controller(
    auth: Annotated[AuthSchema, Security(AuthPermission(["module_mcp_gateway:debug:tools-list"]))],
    db: Annotated[AsyncSession, Depends(db_getter)],
    redis: Annotated[Redis, Depends(redis_getter)],
    data: Annotated[DebugTargetSchema, Body(description="调试目标")],
) -> JSONResponse:
    result = await DebugService(auth, db, redis).tools_list(
        target=data.target,
        group_id=data.group_id,
        user_id=data.user_id,
        transport=data.transport,
        upstream_id=data.upstream_id,
        url=data.url,
        headers=data.headers,
        reveal=data.reveal,
    )
    return SuccessResponse(data=result, msg="列出调试工具成功")


@McpDebugRouter.post(
    "/tools/call",
    summary="调试 tools/call",
    response_model=ResponseSchema[DebugToolsCallResultSchema],
)
async def debug_tools_call_controller(
    auth: Annotated[AuthSchema, Security(AuthPermission(["module_mcp_gateway:debug:tools-call"]))],
    db: Annotated[AsyncSession, Depends(db_getter)],
    redis: Annotated[Redis, Depends(redis_getter)],
    data: Annotated[DebugCallSchema, Body(description="调试调用")],
) -> JSONResponse:
    result = await DebugService(auth, db, redis).tools_call(
        target=data.target,
        group_id=data.group_id,
        user_id=data.user_id,
        transport=data.transport,
        upstream_id=data.upstream_id,
        url=data.url,
        headers=data.headers,
        reveal=data.reveal,
        name=data.name,
        arguments=data.arguments,
    )
    return SuccessResponse(data=result, msg="调试调用工具成功")
