from typing import Annotated

from fastapi import APIRouter, Body, Depends, Path, Query, Security
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.response import ResponseSchema, SuccessResponse
from app.core.base_schema import AuthSchema, PageResultSchema, PaginationQueryParam
from app.core.dependencies import AuthPermission, db_getter
from app.core.router_class import OperationLogRoute

from .schema import (
    GenbiAgentProfileOut,
    GenbiAgentProfileUpdate,
    GenbiDeployOut,
    GenbiInstructionCreate,
    GenbiInstructionOut,
    GenbiInstructionUpdate,
    GenbiMetricDocCreate,
    GenbiMetricDocOut,
    GenbiMetricDocUpdate,
    GenbiModelOut,
    GenbiModelSyncRequest,
    GenbiProjectCreate,
    GenbiProjectOut,
    GenbiProjectQueryParam,
    GenbiProjectUpdate,
    GenbiRelationshipOut,
    GenbiRelationshipSyncRequest,
    GenbiSqlPairCreate,
    GenbiSqlPairOut,
    GenbiSqlPairUpdate,
)
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


@GenbiProjectRouter.put(
    "/update/{id}",
    summary="更新 GenBI 项目",
    response_model=ResponseSchema[GenbiProjectOut],
)
async def update_genbi_project_controller(
    auth: Annotated[AuthSchema, Security(AuthPermission(["module_genbi:project:update"]))],
    db: Annotated[AsyncSession, Depends(db_getter)],
    id: Annotated[int, Path(description="项目ID", ge=1)],
    data: Annotated[GenbiProjectUpdate, Body(description="更新项目")],
) -> JSONResponse:
    result = await GenbiProjectService(auth, db).update(project_id=id, data=data)
    return SuccessResponse(data=result, msg="更新项目成功")


@GenbiProjectRouter.get(
    "/{id}/models",
    summary="列出项目 MDL 模型",
    response_model=ResponseSchema[list[GenbiModelOut]],
)
async def list_genbi_project_models_controller(
    auth: Annotated[AuthSchema, Security(AuthPermission(["module_genbi:project:query"]))],
    db: Annotated[AsyncSession, Depends(db_getter)],
    id: Annotated[int, Path(description="项目ID", ge=1)],
) -> JSONResponse:
    result = await GenbiProjectService(auth, db).list_models(project_id=id)
    return SuccessResponse(data=result, msg="查询模型成功")


@GenbiProjectRouter.put(
    "/{id}/models",
    summary="同步/保存项目 MDL 模型与列（整表替换）",
    response_model=ResponseSchema[list[GenbiModelOut]],
)
async def sync_genbi_project_models_controller(
    auth: Annotated[AuthSchema, Security(AuthPermission(["module_genbi:project:update"]))],
    db: Annotated[AsyncSession, Depends(db_getter)],
    id: Annotated[int, Path(description="项目ID", ge=1)],
    data: Annotated[GenbiModelSyncRequest, Body(description="MDL 模型")],
) -> JSONResponse:
    rows = await GenbiProjectService(auth, db).sync_models(project_id=id, models=data.models)
    out = [GenbiModelOut.model_validate(r) for r in rows]
    return SuccessResponse(data=out, msg="保存模型成功")


@GenbiProjectRouter.get(
    "/{id}/relationships",
    summary="列出项目 MDL 关系",
    response_model=ResponseSchema[list[GenbiRelationshipOut]],
)
async def list_genbi_project_relationships_controller(
    auth: Annotated[AuthSchema, Security(AuthPermission(["module_genbi:project:query"]))],
    db: Annotated[AsyncSession, Depends(db_getter)],
    id: Annotated[int, Path(description="项目ID", ge=1)],
) -> JSONResponse:
    result = await GenbiProjectService(auth, db).list_relationships(project_id=id)
    return SuccessResponse(data=result, msg="查询关系成功")


@GenbiProjectRouter.put(
    "/{id}/relationships",
    summary="同步/保存项目 MDL 关系（整表替换）",
    response_model=ResponseSchema[list[GenbiRelationshipOut]],
)
async def sync_genbi_project_relationships_controller(
    auth: Annotated[AuthSchema, Security(AuthPermission(["module_genbi:project:update"]))],
    db: Annotated[AsyncSession, Depends(db_getter)],
    id: Annotated[int, Path(description="项目ID", ge=1)],
    data: Annotated[GenbiRelationshipSyncRequest, Body(description="MDL 关系")],
) -> JSONResponse:
    rows = await GenbiProjectService(auth, db).sync_relationships(
        project_id=id, relationships=data.relationships
    )
    out = [GenbiRelationshipOut.model_validate(r) for r in rows]
    return SuccessResponse(data=out, msg="保存关系成功")


@GenbiProjectRouter.get(
    "/{id}/agent-profile",
    summary="获取项目 Agent 配置",
    response_model=ResponseSchema[GenbiAgentProfileOut],
)
async def get_genbi_agent_profile_controller(
    auth: Annotated[AuthSchema, Security(AuthPermission(["module_genbi:project:query"]))],
    db: Annotated[AsyncSession, Depends(db_getter)],
    id: Annotated[int, Path(description="项目ID", ge=1)],
) -> JSONResponse:
    result = await GenbiProjectService(auth, db).get_agent_profile(project_id=id)
    return SuccessResponse(data=result, msg="获取 Agent 配置成功")


@GenbiProjectRouter.patch(
    "/{id}/agent-profile",
    summary="更新项目 Agent 配置",
    response_model=ResponseSchema[GenbiAgentProfileOut],
)
async def patch_genbi_agent_profile_controller(
    auth: Annotated[AuthSchema, Security(AuthPermission(["module_genbi:project:update"]))],
    db: Annotated[AsyncSession, Depends(db_getter)],
    id: Annotated[int, Path(description="项目ID", ge=1)],
    data: Annotated[GenbiAgentProfileUpdate, Body(description="Agent 配置")],
) -> JSONResponse:
    result = await GenbiProjectService(auth, db).patch_agent_profile(project_id=id, data=data)
    return SuccessResponse(data=result, msg="保存 Agent 配置成功")


@GenbiProjectRouter.get(
    "/{id}/instructions",
    summary="列出问数指令",
    response_model=ResponseSchema[list[GenbiInstructionOut]],
)
async def list_genbi_instructions_controller(
    auth: Annotated[AuthSchema, Security(AuthPermission(["module_genbi:project:query"]))],
    db: Annotated[AsyncSession, Depends(db_getter)],
    id: Annotated[int, Path(description="项目ID", ge=1)],
) -> JSONResponse:
    result = await GenbiProjectService(auth, db).list_instructions(project_id=id)
    return SuccessResponse(data=result, msg="查询指令成功")


@GenbiProjectRouter.post(
    "/{id}/instructions",
    summary="创建问数指令",
    response_model=ResponseSchema[GenbiInstructionOut],
)
async def create_genbi_instruction_controller(
    auth: Annotated[AuthSchema, Security(AuthPermission(["module_genbi:project:update"]))],
    db: Annotated[AsyncSession, Depends(db_getter)],
    id: Annotated[int, Path(description="项目ID", ge=1)],
    data: Annotated[GenbiInstructionCreate, Body()],
) -> JSONResponse:
    row = await GenbiProjectService(auth, db).create_instruction(project_id=id, data=data)
    return SuccessResponse(data=GenbiInstructionOut.model_validate(row), msg="创建指令成功")


@GenbiProjectRouter.patch(
    "/{id}/instructions/{instruction_id}",
    summary="更新问数指令",
    response_model=ResponseSchema[GenbiInstructionOut],
)
async def update_genbi_instruction_controller(
    auth: Annotated[AuthSchema, Security(AuthPermission(["module_genbi:project:update"]))],
    db: Annotated[AsyncSession, Depends(db_getter)],
    id: Annotated[int, Path(description="项目ID", ge=1)],
    instruction_id: Annotated[int, Path(description="指令ID", ge=1)],
    data: Annotated[GenbiInstructionUpdate, Body()],
) -> JSONResponse:
    row = await GenbiProjectService(auth, db).update_instruction(
        project_id=id, instruction_id=instruction_id, data=data
    )
    return SuccessResponse(data=GenbiInstructionOut.model_validate(row), msg="更新指令成功")


@GenbiProjectRouter.delete(
    "/{id}/instructions/{instruction_id}",
    summary="删除问数指令",
    response_model=ResponseSchema[None],
)
async def delete_genbi_instruction_controller(
    auth: Annotated[AuthSchema, Security(AuthPermission(["module_genbi:project:update"]))],
    db: Annotated[AsyncSession, Depends(db_getter)],
    id: Annotated[int, Path(description="项目ID", ge=1)],
    instruction_id: Annotated[int, Path(description="指令ID", ge=1)],
) -> JSONResponse:
    await GenbiProjectService(auth, db).delete_instruction(
        project_id=id, instruction_id=instruction_id
    )
    return SuccessResponse(data=None, msg="删除指令成功")


@GenbiProjectRouter.get(
    "/{id}/metric-docs",
    summary="列出指标文档",
    response_model=ResponseSchema[list[GenbiMetricDocOut]],
)
async def list_genbi_metric_docs_controller(
    auth: Annotated[AuthSchema, Security(AuthPermission(["module_genbi:project:query"]))],
    db: Annotated[AsyncSession, Depends(db_getter)],
    id: Annotated[int, Path(description="项目ID", ge=1)],
) -> JSONResponse:
    result = await GenbiProjectService(auth, db).list_metric_docs(project_id=id)
    return SuccessResponse(data=result, msg="查询指标文档成功")


@GenbiProjectRouter.post(
    "/{id}/metric-docs",
    summary="创建指标文档",
    response_model=ResponseSchema[GenbiMetricDocOut],
)
async def create_genbi_metric_doc_controller(
    auth: Annotated[AuthSchema, Security(AuthPermission(["module_genbi:project:update"]))],
    db: Annotated[AsyncSession, Depends(db_getter)],
    id: Annotated[int, Path(description="项目ID", ge=1)],
    data: Annotated[GenbiMetricDocCreate, Body()],
) -> JSONResponse:
    row = await GenbiProjectService(auth, db).create_metric_doc(project_id=id, data=data)
    return SuccessResponse(data=GenbiMetricDocOut.model_validate(row), msg="创建指标文档成功")


@GenbiProjectRouter.patch(
    "/{id}/metric-docs/{doc_id}",
    summary="更新指标文档",
    response_model=ResponseSchema[GenbiMetricDocOut],
)
async def update_genbi_metric_doc_controller(
    auth: Annotated[AuthSchema, Security(AuthPermission(["module_genbi:project:update"]))],
    db: Annotated[AsyncSession, Depends(db_getter)],
    id: Annotated[int, Path(description="项目ID", ge=1)],
    doc_id: Annotated[int, Path(description="文档ID", ge=1)],
    data: Annotated[GenbiMetricDocUpdate, Body()],
) -> JSONResponse:
    row = await GenbiProjectService(auth, db).update_metric_doc(
        project_id=id, doc_id=doc_id, data=data
    )
    return SuccessResponse(data=GenbiMetricDocOut.model_validate(row), msg="更新指标文档成功")


@GenbiProjectRouter.delete(
    "/{id}/metric-docs/{doc_id}",
    summary="删除指标文档",
    response_model=ResponseSchema[None],
)
async def delete_genbi_metric_doc_controller(
    auth: Annotated[AuthSchema, Security(AuthPermission(["module_genbi:project:update"]))],
    db: Annotated[AsyncSession, Depends(db_getter)],
    id: Annotated[int, Path(description="项目ID", ge=1)],
    doc_id: Annotated[int, Path(description="文档ID", ge=1)],
) -> JSONResponse:
    await GenbiProjectService(auth, db).delete_metric_doc(project_id=id, doc_id=doc_id)
    return SuccessResponse(data=None, msg="删除指标文档成功")


@GenbiProjectRouter.get(
    "/{id}/sql-pairs",
    summary="列出 SQL 问答对",
    response_model=ResponseSchema[list[GenbiSqlPairOut]],
)
async def list_genbi_sql_pairs_controller(
    auth: Annotated[AuthSchema, Security(AuthPermission(["module_genbi:project:query"]))],
    db: Annotated[AsyncSession, Depends(db_getter)],
    id: Annotated[int, Path(description="项目ID", ge=1)],
) -> JSONResponse:
    result = await GenbiProjectService(auth, db).list_sql_pairs(project_id=id)
    return SuccessResponse(data=result, msg="查询 SQL 问答对成功")


@GenbiProjectRouter.post(
    "/{id}/sql-pairs",
    summary="创建 SQL 问答对",
    response_model=ResponseSchema[GenbiSqlPairOut],
)
async def create_genbi_sql_pair_controller(
    auth: Annotated[AuthSchema, Security(AuthPermission(["module_genbi:project:update"]))],
    db: Annotated[AsyncSession, Depends(db_getter)],
    id: Annotated[int, Path(description="项目ID", ge=1)],
    data: Annotated[GenbiSqlPairCreate, Body()],
) -> JSONResponse:
    row = await GenbiProjectService(auth, db).create_sql_pair(project_id=id, data=data)
    return SuccessResponse(data=GenbiSqlPairOut.model_validate(row), msg="创建 SQL 问答对成功")


@GenbiProjectRouter.patch(
    "/{id}/sql-pairs/{pair_id}",
    summary="更新 SQL 问答对",
    response_model=ResponseSchema[GenbiSqlPairOut],
)
async def update_genbi_sql_pair_controller(
    auth: Annotated[AuthSchema, Security(AuthPermission(["module_genbi:project:update"]))],
    db: Annotated[AsyncSession, Depends(db_getter)],
    id: Annotated[int, Path(description="项目ID", ge=1)],
    pair_id: Annotated[int, Path(description="问答对ID", ge=1)],
    data: Annotated[GenbiSqlPairUpdate, Body()],
) -> JSONResponse:
    row = await GenbiProjectService(auth, db).update_sql_pair(
        project_id=id, pair_id=pair_id, data=data
    )
    return SuccessResponse(data=GenbiSqlPairOut.model_validate(row), msg="更新 SQL 问答对成功")


@GenbiProjectRouter.delete(
    "/{id}/sql-pairs/{pair_id}",
    summary="删除 SQL 问答对",
    response_model=ResponseSchema[None],
)
async def delete_genbi_sql_pair_controller(
    auth: Annotated[AuthSchema, Security(AuthPermission(["module_genbi:project:update"]))],
    db: Annotated[AsyncSession, Depends(db_getter)],
    id: Annotated[int, Path(description="项目ID", ge=1)],
    pair_id: Annotated[int, Path(description="问答对ID", ge=1)],
) -> JSONResponse:
    await GenbiProjectService(auth, db).delete_sql_pair(project_id=id, pair_id=pair_id)
    return SuccessResponse(data=None, msg="删除 SQL 问答对成功")


@GenbiProjectRouter.get(
    "/{id}/deploy-logs",
    summary="列出部署日志",
    response_model=ResponseSchema[list[GenbiDeployOut]],
)
async def list_genbi_deploy_logs_controller(
    auth: Annotated[AuthSchema, Security(AuthPermission(["module_genbi:project:query"]))],
    db: Annotated[AsyncSession, Depends(db_getter)],
    id: Annotated[int, Path(description="项目ID", ge=1)],
    limit: Annotated[int, Query(description="条数", ge=1, le=100)] = 20,
) -> JSONResponse:
    rows = await GenbiProjectService(auth, db).list_deploy_logs(project_id=id, limit=limit)
    out = [GenbiDeployOut.model_validate(r) for r in rows]
    return SuccessResponse(data=out, msg="查询部署日志成功")


@GenbiProjectRouter.post(
    "/{id}/deploy",
    summary="部署项目 MDL（Wren + 现有 PG/pgvector）",
    response_model=ResponseSchema[GenbiDeployOut],
)
async def deploy_genbi_project_controller(
    auth: Annotated[AuthSchema, Security(AuthPermission(["module_genbi:project:update"]))],
    db: Annotated[AsyncSession, Depends(db_getter)],
    id: Annotated[int, Path(description="项目ID", ge=1)],
    force: Annotated[bool, Query(description="强制重新部署")] = False,
) -> JSONResponse:
    log = await GenbiProjectService(auth, db).deploy(project_id=id, force=force)
    return SuccessResponse(data=GenbiDeployOut.model_validate(log), msg="部署成功")
