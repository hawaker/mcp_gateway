"""短期验证链接。nonce 只记下用户和系统，十分钟后失效。

不向业务系统登录，也不把业务 token 放进这条 Redis 记录。
"""

import json
import secrets
from typing import Any

from redis.asyncio.client import Redis
from sqlalchemy import select

from app.modules.mcp_gateway.auth.model import AuthConfigModel

# 打开链接的人要在这段时间内完成验证。共享的测试 Redis 不会按这个值过期，调用方要看 set 的 ex。
LINK_TTL_SECONDS = 10 * 60
_LINK_KEY = "mcp:auth-link:{nonce}"
_LINK_PATH = "/mcp-gateway/auth/interactive/{nonce}"


def _text(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, bytes):
        return value.decode()
    return str(value)


class InteractiveAuth:
    """签发和读取只属于一个用户、一个业务系统的验证链接。"""

    def __init__(self, redis: Redis) -> None:
        self.redis = redis

    async def start(self, user_id: int, system_id: int) -> str:
        """返回测试客户端和浏览器都能直接 GET 的路径。"""
        nonce = secrets.token_urlsafe(32)
        payload = json.dumps({"user_id": user_id, "system_id": system_id})
        await self.redis.set(_LINK_KEY.format(nonce=nonce), payload, ex=LINK_TTL_SECONDS)
        return _LINK_PATH.format(nonce=nonce)

    async def read(self, nonce: str) -> tuple[int, int] | None:
        """链接过期或不存在时返回 None。调用方这时不能写缓存。"""
        raw = _text(await self.redis.get(_LINK_KEY.format(nonce=nonce)))
        if not raw:
            return None
        data = json.loads(raw)
        return int(data["user_id"]), int(data["system_id"])

    async def consume(self, nonce: str) -> None:
        """验证成功后删掉 nonce，同一条链接不能再写一次缓存。"""
        await self.redis.delete(_LINK_KEY.format(nonce=nonce))


async def load_enabled_interactive_config(system_id: int) -> AuthConfigModel | None:
    """该系统当前启用的交互式鉴权。没有、未启用或不是 interactive 时返回 None。"""
    from app.core.database import async_db_session

    stmt = (
        select(AuthConfigModel)
        .where(
            AuthConfigModel.system_id == system_id,
            AuthConfigModel.enabled.is_(True),
            AuthConfigModel.method == "interactive",
            AuthConfigModel.is_deleted.is_(False),
        )
        .limit(1)
    )
    async with async_db_session() as session, session.begin():
        result = await session.execute(stmt)
        row = result.scalar_one_or_none()
        if row is None:
            return None
        # 离开会话后再读字段会碰到已过期的实例。这里抄出回调真正要用的值。
        return AuthConfigModel(
            id=row.id,
            system_id=row.system_id,
            method=row.method,
            enabled=row.enabled,
            url=row.url,
            rule=dict(row.rule or {}),
        )
