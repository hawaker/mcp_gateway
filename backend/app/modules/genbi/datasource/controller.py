from typing import Annotated

from fastapi import APIRouter, Body, Depends, Path, Query, Security
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.response import ResponseSchema, SuccessResponse
from app.core.base_schema import AuthSchema, PageResultSchema, PaginationQueryParam
from app.core.dependencies import AuthPermission, db_getter
from app.core.router_class import OperationLogRoute

from .schema import (
    GenbiDatasourceCreate,
    GenbiDatasourceOut,
    GenbiDatasourceQueryParam,
    GenbiDatasourceTest,
    GenbiDatasourceUpdate,
)
from .service import GenbiDatasourceService

GenbiDatasourceRouter = APIRouter(
    route_class=OperationLogRoute,
    prefix="/data-sources",
    tags=["GenBI 数据源"],
)


@GenbiDatasourceRouter.get(
    "/list",
    summary="分页查询 GenBI 数据源",
    response_model=ResponseSchema[PageResultSchema[GenbiDatasourceOut]],
)
async def list_genbi_datasource_controller(
    auth: Annotated[AuthSchema, Security(AuthPermission(["module_genbi:datasource:query"]))],
    db: Annotated[AsyncSession, Depends(db_getter)],
    page: Annotated[PaginationQueryParam, Depends()],
    search: Annotated[GenbiDatasourceQueryParam, Query()],
) -> JSONResponse:
    result = await GenbiDatasourceService(auth, db).list(
        page_no=page.page_no,
        page_size=page.page_size,
        search=search,
        order_by=page.order_by,
    )
    return SuccessResponse(data=result, msg="查询数据源成功")


@GenbiDatasourceRouter.get(
    "/detail/{id}",
    summary="获取 GenBI 数据源详情",
    response_model=ResponseSchema[GenbiDatasourceOut],
)
async def detail_genbi_datasource_controller(
    auth: Annotated[AuthSchema, Security(AuthPermission(["module_genbi:datasource:query"]))],
    db: Annotated[AsyncSession, Depends(db_getter)],
    id: Annotated[int, Path(description="数据源ID", ge=1)],
) -> JSONResponse:
    result = await GenbiDatasourceService(auth, db).get(datasource_id=id)
    return SuccessResponse(data=result, msg="获取数据源详情成功")


@GenbiDatasourceRouter.post(
    "/create",
    summary="创建 GenBI 数据源",
    response_model=ResponseSchema[GenbiDatasourceOut],
)
async def create_genbi_datasource_controller(
    auth: Annotated[AuthSchema, Security(AuthPermission(["module_genbi:datasource:create"]))],
    db: Annotated[AsyncSession, Depends(db_getter)],
    data: Annotated[GenbiDatasourceCreate, Body(description="创建数据源")],
) -> JSONResponse:
    row = await GenbiDatasourceService(auth, db).create(**data.model_dump())
    return SuccessResponse(data=GenbiDatasourceOut.model_validate(row), msg="创建数据源成功")


@GenbiDatasourceRouter.put(
    "/update/{id}",
    summary="修改 GenBI 数据源",
    response_model=ResponseSchema[GenbiDatasourceOut],
)
async def update_genbi_datasource_controller(
    auth: Annotated[AuthSchema, Security(AuthPermission(["module_genbi:datasource:update"]))],
    db: Annotated[AsyncSession, Depends(db_getter)],
    id: Annotated[int, Path(description="数据源ID", ge=1)],
    data: Annotated[GenbiDatasourceUpdate, Body(description="修改数据源")],
) -> JSONResponse:
    result = await GenbiDatasourceService(auth, db).update(datasource_id=id, data=data)
    return SuccessResponse(data=result, msg="修改数据源成功")


@GenbiDatasourceRouter.delete(
    "/delete",
    summary="删除 GenBI 数据源",
    response_model=ResponseSchema[None],
)
async def delete_genbi_datasource_controller(
    auth: Annotated[AuthSchema, Security(AuthPermission(["module_genbi:datasource:delete"]))],
    db: Annotated[AsyncSession, Depends(db_getter)],
    ids: Annotated[list[int], Body(description="数据源ID列表")],
) -> JSONResponse:
    await GenbiDatasourceService(auth, db).delete(ids=ids)
    return SuccessResponse(msg="删除数据源成功")


@GenbiDatasourceRouter.post(
    "/test",
    summary="按填写中的凭据测试连接（不落库）",
    response_model=ResponseSchema[None],
)
async def test_genbi_datasource_config_controller(
    auth: Annotated[AuthSchema, Security(AuthPermission(["module_genbi:datasource:update"]))],
    db: Annotated[AsyncSession, Depends(db_getter)],
    data: Annotated[GenbiDatasourceTest, Body(description="测连参数")],
) -> JSONResponse:
    await GenbiDatasourceService(auth, db).test_connection(data)
    return SuccessResponse(msg="连接成功")


@GenbiDatasourceRouter.post(
    "/{id}/test",
    summary="测试已保存的 GenBI 数据源连接",
    response_model=ResponseSchema[None],
)
async def test_genbi_datasource_by_id_controller(
    auth: Annotated[AuthSchema, Security(AuthPermission(["module_genbi:datasource:query"]))],
    db: Annotated[AsyncSession, Depends(db_getter)],
    id: Annotated[int, Path(description="数据源ID", ge=1)],
) -> JSONResponse:
    await GenbiDatasourceService(auth, db).test_by_id(datasource_id=id)
    return SuccessResponse(msg="连接成功")
