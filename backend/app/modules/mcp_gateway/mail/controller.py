from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query, Security
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.response import ResponseSchema, SuccessResponse
from app.core.base_schema import AuthSchema, PageResultSchema, PaginationQueryParam
from app.core.dependencies import AuthPermission, db_getter
from app.core.router_class import OperationLogRoute

from .schema import MailLogOutSchema, MailLogQueryParam
from .service import MailService

MailRouter = APIRouter(route_class=OperationLogRoute, prefix="/mail", tags=["发信记录"])


@MailRouter.post("/group/{group_id}", summary="按 MCP 组发送连接信息", response_model=ResponseSchema[list[MailLogOutSchema]])
async def send_mail_for_group_controller(
    auth: Annotated[AuthSchema, Security(AuthPermission(["module_mcp_gateway:smtp:update"]))],
    db: Annotated[AsyncSession, Depends(db_getter)],
    group_id: Annotated[int, Path(description="MCP 组ID", ge=1)],
) -> JSONResponse:
    result = await MailService(auth, db).send_for_group(group_id)
    return SuccessResponse(data=result, msg="按 MCP 组发送完成")


@MailRouter.post(
    "/user-group/{user_group_id}",
    summary="按用户组发送连接信息",
    response_model=ResponseSchema[list[MailLogOutSchema]],
)
async def send_mail_for_user_group_controller(
    auth: Annotated[AuthSchema, Security(AuthPermission(["module_mcp_gateway:smtp:update"]))],
    db: Annotated[AsyncSession, Depends(db_getter)],
    user_group_id: Annotated[int, Path(description="业务用户组ID", ge=1)],
) -> JSONResponse:
    result = await MailService(auth, db).send_for_user_group(user_group_id)
    return SuccessResponse(data=result, msg="按用户组发送完成")


@MailRouter.post("/user/{user_id}", summary="按用户发送连接信息", response_model=ResponseSchema[list[MailLogOutSchema]])
async def send_mail_for_user_controller(
    auth: Annotated[AuthSchema, Security(AuthPermission(["module_mcp_gateway:smtp:update"]))],
    db: Annotated[AsyncSession, Depends(db_getter)],
    user_id: Annotated[int, Path(description="业务用户ID", ge=1)],
) -> JSONResponse:
    result = await MailService(auth, db).send_for_user(user_id)
    return SuccessResponse(data=result, msg="按用户发送完成")


@MailRouter.get("/log/list", summary="分页查询发信记录", response_model=ResponseSchema[PageResultSchema[MailLogOutSchema]])
async def list_mail_log_controller(
    auth: Annotated[AuthSchema, Security(AuthPermission(["module_mcp_gateway:mail-log:query"]))],
    db: Annotated[AsyncSession, Depends(db_getter)],
    page: Annotated[PaginationQueryParam, Depends()],
    search: Annotated[MailLogQueryParam, Query()],
) -> JSONResponse:
    result = await MailService(auth, db).page(
        page_no=page.page_no,
        page_size=page.page_size,
        search=search,
        order_by=page.order_by,
    )
    return SuccessResponse(data=result, msg="查询发信记录成功")
