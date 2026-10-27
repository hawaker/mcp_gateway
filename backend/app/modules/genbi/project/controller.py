from typing import Annotated

from fastapi import APIRouter, Body, Depends, Path, Query, Security
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.response import ResponseSchema, SuccessResponse
from app.core.base_schema import AuthSchema, PageResultSchema, PaginationQueryParam
from app.core.dependencies import AuthPermission, db_getter
from app.core.router_class import OperationLogRoute

from .schema import GenbiProjectCreate, GenbiProjectOut, GenbiProjectQueryParam
from .service import GenbiProjectService

GenbiProjectRouter = APIRouter(
    route_class=OperationLogRoute,
    prefix="/projects",
    tags=["GenBI 项目"],
)


@GenbiProjectRouter.get(
    "/list",
    summary="分页查询 GenBI 项目",
    response_model=ResponseSchema[PageResultSchema[GenbiProjectOut]],
)
async def list_genbi_project_controller(
    auth: Annotated[AuthSchema, Security(AuthPermission(["module_genbi:project:query"]))],
    db: Annotated[AsyncSession, Depends(db_getter)],
    page: Annotated[PaginationQueryParam, Depends()],
    search: Annotated[GenbiProjectQueryParam, Query()],
) -> JSONResponse:
    result = await GenbiProjectService(auth, db).list(
        page_no=page.page_no,
        page_size=page.page_size,
        search=search,
        order_by=page.order_by,
    )
    return SuccessResponse(data=result, msg="查询项目成功")


@GenbiProjectRouter.get(
    "/detail/{id}",
    summary="获取 GenBI 项目详情",
    response_model=ResponseSchema[GenbiProjectOut],
)
async def detail_genbi_project_controller(
    auth: Annotated[AuthSchema, Security(AuthPermission(["module_genbi:project:query"]))],
    db: Annotated[AsyncSession, Depends(db_getter)],
    id: Annotated[int, Path(description="项目ID", ge=1)],
) -> JSONResponse:
    result = await GenbiProjectService(auth, db).get(project_id=id)
    return SuccessResponse(data=result, msg="获取项目详情成功")


@GenbiProjectRouter.post(
    "/create",
    summary="创建 GenBI 项目（每数据源一个）",
    response_model=ResponseSchema[GenbiProjectOut],
)
async def create_genbi_project_controller(
    auth: Annotated[AuthSchema, Security(AuthPermission(["module_genbi:project:create"]))],
    db: Annotated[AsyncSession, Depends(db_getter)],
    data: Annotated[GenbiProjectCreate, Body(description="创建项目")],
) -> JSONResponse:
    row = await GenbiProjectService(auth, db).create(**data.model_dump())
    return SuccessResponse(data=GenbiProjectOut.model_validate(row), msg="创建项目成功")
