from typing import Annotated

from fastapi import APIRouter, Depends, Security
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.response import ResponseSchema, SuccessResponse
from app.core.base_schema import AuthSchema
from app.core.dependencies import AuthPermission, db_getter
from app.core.router_class import OperationLogRoute

from .schema import CallLogAggregateSchema
from .service import CallLogService

CallLogRouter = APIRouter(route_class=OperationLogRoute, prefix="/call-log", tags=["调用日志"])


@CallLogRouter.get(
    "/aggregate",
    summary="按用户和工具汇总调用次数",
    response_model=ResponseSchema[list[CallLogAggregateSchema]],
)
async def aggregate_call_log_controller(
    auth: Annotated[AuthSchema, Security(AuthPermission(["module_mcp_gateway:call-log:query"]))],
    db: Annotated[AsyncSession, Depends(db_getter)],
) -> JSONResponse:
    result = await CallLogService(auth, db).aggregate()
    return SuccessResponse(data=result, msg="查询调用日志成功")
