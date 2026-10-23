"""在刷新业务 token 期间持有 TokenCache.lock。这里不发登录请求。"""

from collections.abc import Awaitable

from app.modules.mcp_gateway.token_cache.store import TokenCache


async def run_under_token_lock[T](
    cache: TokenCache,
    user_id: int,
    system_id: int,
    operation: Awaitable[T],
) -> T:
    """先锁住该用户该系统，再执行调用方给出的协程，结束后放锁。"""
    async with cache.lock(user_id, system_id):
        return await operation
