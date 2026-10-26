from typing import Annotated

from fastapi import APIRouter, Depends, Query, Security
from fastapi.responses import JSONResponse
from redis.asyncio.client import Redis

from app.common.response import ResponseSchema, SuccessResponse
from app.core.base_schema import AuthSchema
from app.core.dependencies import AuthPermission, redis_getter
from app.core.router_class import OperationLogRoute

from .schema import BizTokenCacheOutSchema
from .store import TokenCache

BizTokenCacheRouter = APIRouter(route_class=OperationLogRoute, tags=["业务 token 缓存"])


@BizTokenCacheRouter.get(
    "/biz-token-cache",
    summary="查询业务 token 缓存",
    response_model=ResponseSchema[list[BizTokenCacheOutSchema]],
)
async def list_biz_token_cache_controller(
    auth: Annotated[AuthSchema, Security(AuthPermission(["module_mcp_gateway:biz-token-cache:query"]))],
    redis: Annotated[Redis, Depends(redis_getter)],
    user_id: Annotated[int | None, Query(description="业务用户ID")] = None,
    system_id: Annotated[int | None, Query(description="业务系统ID")] = None,
) -> JSONResponse:
    rows = await TokenCache(redis).list_entries(user_id=user_id, system_id=system_id)
    data = [
        {
            "user_id": row.user_id,
            "system_id": row.system_id,
            "vars": row.vars,
            "var_keys": sorted(row.vars.keys()),
            "access_token": row.access_token,
            "expires_at": row.expires_at,
            "token_type": row.token_type,
            "expired": row.expired,
        }
        for row in rows
    ]
    return SuccessResponse(data=data, msg="查询业务 token 缓存成功")
