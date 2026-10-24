from typing import Annotated

from fastapi import APIRouter, Body, Depends, Path, Query, Security
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.response import ResponseSchema, SuccessResponse
from app.core.base_schema import AuthSchema, PageResultSchema, PaginationQueryParam
from app.core.dependencies import AuthPermission, db_getter
from app.core.router_class import OperationLogRoute

from .schema import SmtpConfigCreateSchema, SmtpConfigOutSchema, SmtpConfigQueryParam, SmtpConfigUpdateSchema, SmtpTestSchema
from .service import SmtpConfigService

SmtpRouter = APIRouter(route_class=OperationLogRoute, prefix="/smtp", tags=["SMTP 配置"])


@SmtpRouter.get("/list", summary="分页查询 SMTP 配置", response_model=ResponseSchema[PageResultSchema[SmtpConfigOutSchema]])
async def list_smtp_controller(
    auth: Annotated[AuthSchema, Security(AuthPermission(["module_mcp_gateway:smtp:query"]))],
    db: Annotated[AsyncSession, Depends(db_getter)],
    page: Annotated[PaginationQueryParam, Depends()],
    search: Annotated[SmtpConfigQueryParam, Query()],
) -> JSONResponse:
    result = await SmtpConfigService(auth, db).page(
        page_no=page.page_no,
        page_size=page.page_size,
        search=search,
        order_by=page.order_by,
    )
    return SuccessResponse(data=result, msg="查询 SMTP 配置成功")


@SmtpRouter.get("/detail/{id}", summary="获取 SMTP 配置详情", response_model=ResponseSchema[SmtpConfigOutSchema])
async def detail_smtp_controller(
    auth: Annotated[AuthSchema, Security(AuthPermission(["module_mcp_gateway:smtp:query"]))],
    db: Annotated[AsyncSession, Depends(db_getter)],
    id: Annotated[int, Path(description="SMTP 配置ID", ge=1)],
) -> JSONResponse:
    result = await SmtpConfigService(auth, db).detail(config_id=id)
    return SuccessResponse(data=result, msg="获取 SMTP 配置详情成功")


@SmtpRouter.post("/create", summary="创建 SMTP 配置", response_model=ResponseSchema[SmtpConfigOutSchema])
async def create_smtp_controller(
    auth: Annotated[AuthSchema, Security(AuthPermission(["module_mcp_gateway:smtp:create"]))],
    db: Annotated[AsyncSession, Depends(db_getter)],
    data: Annotated[SmtpConfigCreateSchema, Body(description="创建 SMTP 配置")],
) -> JSONResponse:
    result = await SmtpConfigService(auth, db).create(data=data)
    return SuccessResponse(data=result, msg="创建 SMTP 配置成功")


@SmtpRouter.put("/update/{id}", summary="修改 SMTP 配置", response_model=ResponseSchema[SmtpConfigOutSchema])
async def update_smtp_controller(
    auth: Annotated[AuthSchema, Security(AuthPermission(["module_mcp_gateway:smtp:update"]))],
    db: Annotated[AsyncSession, Depends(db_getter)],
    id: Annotated[int, Path(description="SMTP 配置ID", ge=1)],
    data: Annotated[SmtpConfigUpdateSchema, Body(description="修改 SMTP 配置")],
) -> JSONResponse:
    result = await SmtpConfigService(auth, db).update(config_id=id, data=data)
    return SuccessResponse(data=result, msg="修改 SMTP 配置成功")


@SmtpRouter.post("/test", summary="发送 SMTP 测试邮件", response_model=ResponseSchema[dict])
async def test_smtp_controller(
    auth: Annotated[AuthSchema, Security(AuthPermission(["module_mcp_gateway:smtp:test"]))],
    db: Annotated[AsyncSession, Depends(db_getter)],
    data: Annotated[SmtpTestSchema, Body(description="测试收件人")],
) -> JSONResponse:
    await SmtpConfigService(auth, db).send_test(to_address=data.to_address)
    return SuccessResponse(data={"to_address": data.to_address}, msg="测试邮件已发送")
