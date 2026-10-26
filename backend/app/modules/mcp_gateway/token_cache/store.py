"""按业务用户和业务系统把 TokenBundle 放进 Redis。不访问 OA。"""

import asyncio
import contextlib
import json
import math
import re
import time
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from redis.asyncio.client import Redis

from app.modules.mcp_gateway.auth.extract import TokenBundle

_TOKEN_KEY = "mcp:biz-token:{user_id}:{system_id}"
_LOCK_KEY = "mcp:biz-token-lock:{user_id}:{system_id}"
_TOKEN_KEY_RE = re.compile(r"^mcp:biz-token:(?P<user_id>\d+):(?P<system_id>\d+)$")
_LOCK_TTL_SECONDS = 30
_LOCK_RENEW_SECONDS = 10
_LOCK_WAIT_SECONDS = 10
_LOCK_POLL_SECONDS = 0.02

# 只在值仍是本次 token 时删除。GET 再 DELETE 会在中间被别人 SET 掉。
_RELEASE_LOCK_SCRIPT = """
local token = redis.call('get', KEYS[1])
if not token or token ~= ARGV[1] then
    return 0
end
redis.call('del', KEYS[1])
return 1
"""

# 只给仍属于本次 token 的锁续期，避免把后来者的 TTL 拨长。
_RENEW_LOCK_SCRIPT = """
local token = redis.call('get', KEYS[1])
if not token or token ~= ARGV[1] then
    return 0
end
return redis.call('pexpire', KEYS[1], ARGV[2])
"""


@dataclass(frozen=True, slots=True)
class CachedBizToken:
    """Redis 里的一条业务变量包，外加是否已过期。"""

    user_id: int
    system_id: int
    vars: dict[str, str]
    expires_at: datetime
    expired: bool

    @property
    def access_token(self) -> str:
        return self.vars.get("access_token") or ""

    @property
    def token_type(self) -> str:
        return "Bearer"


def _token_key(user_id: int, system_id: int) -> str:
    return _TOKEN_KEY.format(user_id=user_id, system_id=system_id)


def _lock_key(user_id: int, system_id: int) -> str:
    return _LOCK_KEY.format(user_id=user_id, system_id=system_id)


def _lock_ttl_ms() -> int:
    """PX / PEXPIRE 用毫秒。至少 1，避免 Redis 拒绝 0。"""
    return max(1, int(_LOCK_TTL_SECONDS * 1000))


def _lock_renew_seconds() -> float:
    """续期间隔短于锁寿命，这样上下文还在时键不会先消失。"""
    return min(float(_LOCK_RENEW_SECONDS), float(_LOCK_TTL_SECONDS) / 3)


def _text(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, bytes):
        return value.decode()
    return str(value)


def _aware(moment: datetime) -> datetime:
    if moment.tzinfo is None:
        return moment.replace(tzinfo=UTC)
    return moment.astimezone(UTC)


def _ttl_seconds(expires_at: datetime) -> int:
    """键在 expires_at 到期。Redis 的 EX 至少是 1 秒。"""
    remaining = (_aware(expires_at) - datetime.now(UTC)).total_seconds()
    if remaining <= 0:
        return 1
    return max(1, math.ceil(remaining))


def _dump(bundle: TokenBundle) -> str:
    payload = {
        "vars": dict(bundle.vars),
        "expires_at": _aware(bundle.expires_at).isoformat(),
    }
    return json.dumps(payload, ensure_ascii=False)


def _load(raw: str) -> TokenBundle:
    data = json.loads(raw)
    expires_at = _aware(datetime.fromisoformat(str(data["expires_at"])))
    raw_vars = data.get("vars")
    if isinstance(raw_vars, dict):
        vars_ = {str(key): "" if value is None else str(value) for key, value in raw_vars.items()}
        return TokenBundle(vars=vars_, expires_at=expires_at)
    # 旧格式：只有 access_token / token_type
    token = data.get("access_token")
    if token is None:
        raise ValueError("cached token missing vars")
    return TokenBundle(vars={"access_token": str(token)}, expires_at=expires_at)


def _row(user_id: int, system_id: int, bundle: TokenBundle) -> CachedBizToken:
    expires_at = _aware(bundle.expires_at)
    return CachedBizToken(
        user_id=user_id,
        system_id=system_id,
        vars=dict(bundle.vars),
        expires_at=expires_at,
        expired=expires_at <= datetime.now(UTC),
    )


class TokenCache:
    """一个业务用户在一个业务系统上只保留一条 token。"""

    def __init__(self, redis: Redis) -> None:
        self.redis = redis

    async def get(self, user_id: int, system_id: int) -> TokenBundle | None:
        raw = _text(await self.redis.get(_token_key(user_id, system_id)))
        if raw is None:
            return None
        return _load(raw)

    async def put(self, user_id: int, system_id: int, bundle: TokenBundle) -> None:
        await self.redis.set(
            _token_key(user_id, system_id),
            _dump(bundle),
            ex=_ttl_seconds(bundle.expires_at),
        )

    async def delete(self, user_id: int, system_id: int) -> None:
        await self.redis.delete(_token_key(user_id, system_id))

    @asynccontextmanager
    async def lock(self, user_id: int, system_id: int) -> AsyncIterator[None]:
        """同一用户同一系统互斥。持有期间续期，退出时只删除仍属于本次的锁。"""
        key = _lock_key(user_id, system_id)
        token = uuid.uuid4().hex
        deadline = time.monotonic() + _LOCK_WAIT_SECONDS
        acquired = False
        renew_task: asyncio.Task[None] | None = None
        try:
            while True:
                held = await self.redis.set(key, token, nx=True, px=_lock_ttl_ms())
                if held:
                    acquired = True
                    break
                if time.monotonic() >= deadline:
                    raise TimeoutError("等待业务 token 锁超时")
                await asyncio.sleep(_LOCK_POLL_SECONDS)
            renew_task = asyncio.create_task(self._renew_lock(key, token))
            yield
        finally:
            try:
                if renew_task is not None:
                    renew_task.cancel()
                    with contextlib.suppress(asyncio.CancelledError):
                        await renew_task
            finally:
                if acquired:
                    await self.redis.eval(_RELEASE_LOCK_SCRIPT, 1, key, token)

    async def _renew_lock(self, key: str, token: str) -> None:
        """在 TTL 耗尽前把本次持有者的锁拨回完整寿命。丢失所有权后不再改键。"""
        while True:
            await asyncio.sleep(_lock_renew_seconds())
            await self.redis.eval(_RENEW_LOCK_SCRIPT, 1, key, token, _lock_ttl_ms())

    async def list_entries(self, user_id: int | None = None, system_id: int | None = None) -> list[CachedBizToken]:
        """列出 mcp:biz-token:*。两个 id 都给出时只读那一把键。没有则空列表。"""
        if user_id is not None and system_id is not None:
            bundle = await self.get(user_id, system_id)
            if bundle is None:
                return []
            return [_row(user_id, system_id, bundle)]

        pattern = f"mcp:biz-token:{user_id}:*" if user_id is not None else "mcp:biz-token:*"
        rows: list[CachedBizToken] = []
        for key in await self._keys(pattern):
            matched = _TOKEN_KEY_RE.fullmatch(key)
            if matched is None:
                continue
            found_user = int(matched.group("user_id"))
            found_system = int(matched.group("system_id"))
            if system_id is not None and found_system != system_id:
                continue
            bundle = await self.get(found_user, found_system)
            if bundle is None:
                continue
            rows.append(_row(found_user, found_system, bundle))
        rows.sort(key=lambda item: (item.user_id, item.system_id))
        return rows

    async def _keys(self, pattern: str) -> list[str]:
        found = await self.redis.keys(pattern)
        texts: list[str] = []
        for key in found or []:
            text = _text(key)
            if text is not None:
                texts.append(text)
        return texts
