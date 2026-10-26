"""业务 token 按用户和业务系统分键存在 Redis。不访问 OA，不登录。"""

import asyncio
import json
import time
from datetime import UTC, datetime, timedelta
from typing import Any
from unittest.mock import AsyncMock

import pytest
from fastapi.routing import APIRoute

from app.api.v1.routers import DOMAIN_CONTROLLERS
from app.core.dependencies import AuthPermission
from app.modules.mcp_gateway.auth.extract import TokenBundle
from app.modules.mcp_gateway.auth.refresh import run_under_token_lock
from app.modules.mcp_gateway.token_cache.controller import BizTokenCacheRouter, list_biz_token_cache_controller
from app.modules.mcp_gateway.token_cache.store import _RELEASE_LOCK_SCRIPT, _RENEW_LOCK_SCRIPT, TokenCache

_PAIRS = ((1, 10), (1, 20), (2, 10), (2, 20), (9, 9))


def bundle(access_token: str, expires_at: datetime | None = None, **extra: str) -> TokenBundle:
    vars_ = {"access_token": access_token, **extra}
    return TokenBundle(
        vars=vars_,
        expires_at=expires_at or (datetime.now(UTC) + timedelta(hours=1)),
    )


def _as_text(value: Any) -> str:
    if isinstance(value, bytes):
        return value.decode()
    return str(value)


class ExpiringRedis:
    """会过期的内存 Redis。锁的释放和续期走与生产相同的脚本，并且是一次完成的。"""

    def __init__(self) -> None:
        self._data: dict[str, tuple[str, float | None]] = {}
        self.set = AsyncMock(side_effect=self._set)
        self.get = AsyncMock(side_effect=self._get)
        self.delete = AsyncMock(side_effect=self._delete)
        self.keys = AsyncMock(side_effect=self._keys)
        self.eval = AsyncMock(side_effect=self._eval)

    def force_expire(self, name: Any) -> None:
        self._data.pop(_as_text(name), None)

    def expiry(self, name: Any) -> float | None:
        key = _as_text(name)
        self._drop_if_expired(key)
        item = self._data.get(key)
        if item is None:
            return None
        return item[1]

    def _drop_if_expired(self, key: str) -> None:
        item = self._data.get(key)
        if item is None:
            return
        expires_at = item[1]
        if expires_at is not None and time.monotonic() >= expires_at:
            self._data.pop(key, None)

    def _purge(self) -> None:
        now = time.monotonic()
        expired = [key for key, (_, expires_at) in self._data.items() if expires_at is not None and now >= expires_at]
        for key in expired:
            self._data.pop(key, None)

    async def _set(self, name: Any, value: Any, ex: float | None = None, px: float | None = None, nx: bool = False) -> bool | None:
        key = _as_text(name)
        self._drop_if_expired(key)
        if nx and key in self._data:
            return None
        expires_at = None
        if ex is not None:
            expires_at = time.monotonic() + float(ex)
        if px is not None:
            expires_at = time.monotonic() + float(px) / 1000
        self._data[key] = (_as_text(value), expires_at)
        return True

    async def _get(self, name: Any) -> str | None:
        key = _as_text(name)
        self._drop_if_expired(key)
        item = self._data.get(key)
        if item is None:
            return None
        return item[0]

    async def _delete(self, *names: Any) -> int:
        count = 0
        for name in names:
            if self._data.pop(_as_text(name), None) is not None:
                count += 1
        return count

    async def _keys(self, pattern: Any = None) -> list[str]:
        self._purge()
        if pattern is None or pattern in {"*", b"*"}:
            return list(self._data)
        text = _as_text(pattern)
        if text.endswith("*"):
            prefix = text[:-1]
            return [key for key in self._data if key.startswith(prefix)]
        return [key for key in self._data if key == text]

    async def _eval(self, script: str, numkeys: int, *keys_and_args: Any) -> int:
        """生产用 Lua 一次比较再删除或续期。这里按同一对脚本做同样的事。"""
        if numkeys != 1:
            raise AssertionError("lock scripts use one key")
        key = _as_text(keys_and_args[0])
        token = _as_text(keys_and_args[1])
        self._drop_if_expired(key)
        current = self._data.get(key)
        owned = current is not None and current[0] == token
        if script == _RENEW_LOCK_SCRIPT:
            if not owned or current is None:
                return 0
            ttl_ms = int(keys_and_args[2])
            self._data[key] = (current[0], time.monotonic() + ttl_ms / 1000)
            return 1
        if script == _RELEASE_LOCK_SCRIPT:
            if not owned:
                return 0
            self._data.pop(key, None)
            return 1
        raise AssertionError("unexpected redis script")


async def _wipe(redis: ExpiringRedis) -> None:
    keys: list[str] = []
    for user_id, system_id in _PAIRS:
        keys.append(f"mcp:biz-token:{user_id}:{system_id}")
        keys.append(f"mcp:biz-token-lock:{user_id}:{system_id}")
    await redis.delete(*keys)


@pytest.fixture
async def cache() -> Any:
    """用户 1、系统 10 和 20 只是缓存键，不要求数据库里有这些行。"""
    redis = ExpiringRedis()
    await _wipe(redis)
    yield TokenCache(redis)
    await _wipe(redis)


def _token_ex(cache: TokenCache, key: str) -> int:
    """同一把键可能被前面的用例写过。看这次 put 传给 set 的 ex，也就是最后一次。"""
    found: int | None = None
    for call in cache.redis.set.await_args_list:
        name = call.kwargs.get("name", call.args[0] if call.args else None)
        if name == key and call.kwargs.get("nx") is not True and "ex" in call.kwargs:
            found = int(call.kwargs["ex"])
    if found is None:
        raise AssertionError(f"没有看到 {key} 的 set ex")
    return found


def _permission_names(route: APIRoute) -> set[str]:
    found: set[str] = set()
    seen: set[int] = set()

    def walk(dep: object) -> None:
        ident = id(dep)
        if ident in seen:
            return
        seen.add(ident)
        call = getattr(dep, "call", None)
        if isinstance(call, AuthPermission):
            found.update(call.permissions)
        for sub in list(getattr(dep, "dependencies", []) or []):
            walk(sub)

    walk(route.dependant)
    for dep in route.dependencies:
        walk(dep)
    return found


async def test_oa_and_mes_tokens_are_separate(cache: TokenCache) -> None:
    await cache.put(1, 10, bundle("oa-token"))
    await cache.put(1, 20, bundle("mes-token"))
    assert (await cache.get(1, 10)).access_token == "oa-token"
    assert (await cache.get(1, 20)).access_token == "mes-token"


async def test_get_missing_returns_none(cache: TokenCache) -> None:
    assert await cache.get(1, 10) is None


async def test_delete_removes_only_that_pair(cache: TokenCache) -> None:
    await cache.put(1, 10, bundle("oa-token"))
    await cache.put(1, 20, bundle("mes-token"))
    await cache.delete(1, 10)
    assert await cache.get(1, 10) is None
    assert (await cache.get(1, 20)).access_token == "mes-token"


async def test_put_sets_ttl_until_expires_at(cache: TokenCache) -> None:
    expires_at = datetime.now(UTC) + timedelta(seconds=120)
    await cache.put(1, 10, bundle("oa-token", expires_at))
    ex = _token_ex(cache, "mcp:biz-token:1:10")
    assert 118 <= ex <= 121
    loaded = await cache.get(1, 10)
    assert loaded is not None
    assert loaded.token_type == "Bearer"
    assert abs((loaded.expires_at - expires_at).total_seconds()) < 1


async def test_put_get_roundtrip_vars(cache: TokenCache) -> None:
    packed = TokenBundle(
        vars={"access_token": "t1", "tenant_id": "9"},
        expires_at=datetime.now(UTC) + timedelta(minutes=5),
    )
    await cache.put(1, 2, packed)
    got = await cache.get(1, 2)
    assert got is not None
    assert got.vars == {"access_token": "t1", "tenant_id": "9"}


async def test_load_legacy_access_token_json(cache: TokenCache) -> None:
    await cache.redis.set(
        "mcp:biz-token:3:4",
        '{"access_token":"legacy","expires_at":"2099-01-01T00:00:00+00:00","token_type":"Bearer"}',
    )
    got = await cache.get(3, 4)
    assert got is not None
    assert got.vars == {"access_token": "legacy"}


async def test_same_pair_locks_exclude_each_other(cache: TokenCache) -> None:
    started = asyncio.Event()
    release = asyncio.Event()
    order: list[str] = []

    async def first() -> None:
        async with cache.lock(1, 10):
            order.append("first-enter")
            started.set()
            await release.wait()
            order.append("first-exit")

    async def second() -> None:
        await started.wait()
        async with cache.lock(1, 10):
            order.append("second-enter")

    holder = asyncio.create_task(first())
    await started.wait()
    waiter = asyncio.create_task(second())
    await asyncio.sleep(0.05)
    assert order == ["first-enter"]
    nx_calls = [call for call in cache.redis.set.await_args_list if call.kwargs.get("nx") is True and (call.args[0] if call.args else call.kwargs.get("name")) == "mcp:biz-token-lock:1:10"]
    assert nx_calls
    release.set()
    await asyncio.wait_for(asyncio.gather(holder, waiter), timeout=2)
    assert order == ["first-enter", "first-exit", "second-enter"]


async def test_different_pairs_do_not_exclude(cache: TokenCache) -> None:
    both = asyncio.Event()
    entered: list[int] = []

    async def hold(system_id: int) -> None:
        async with cache.lock(1, system_id):
            entered.append(system_id)
            if len(entered) == 2:
                both.set()
            await asyncio.wait_for(both.wait(), timeout=1)

    await asyncio.wait_for(asyncio.gather(hold(10), hold(20)), timeout=1)
    assert set(entered) == {10, 20}


async def test_lock_outlives_ttl_until_holder_exits(cache: TokenCache, monkeypatch: pytest.MonkeyPatch) -> None:
    """临界区长过最初的 TTL 时，同一用户同一系统的后来者仍要等到前者退出。"""
    monkeypatch.setattr("app.modules.mcp_gateway.token_cache.store._LOCK_TTL_SECONDS", 0.4)
    monkeypatch.setattr("app.modules.mcp_gateway.token_cache.store._LOCK_RENEW_SECONDS", 0.05)
    key = "mcp:biz-token-lock:1:10"
    started = asyncio.Event()
    release = asyncio.Event()
    order: list[str] = []

    async def first() -> None:
        async with cache.lock(1, 10):
            order.append("first-enter")
            original_expiry = cache.redis.expiry(key)
            assert original_expiry is not None
            started.set()
            await release.wait()
            assert cache.redis.expiry(key) is not None
            assert cache.redis.expiry(key) > original_expiry
            order.append("first-exit")

    async def second() -> None:
        await started.wait()
        async with cache.lock(1, 10):
            order.append("second-enter")

    holder = asyncio.create_task(first())
    await started.wait()
    waiter = asyncio.create_task(second())
    opened = time.monotonic()
    await asyncio.sleep(0.7)
    assert time.monotonic() - opened > 0.4
    assert order == ["first-enter"]
    assert await cache.redis.get(key) is not None
    release.set()
    await asyncio.wait_for(asyncio.gather(holder, waiter), timeout=2)
    assert order == ["first-enter", "first-exit", "second-enter"]


async def test_expired_owner_cannot_delete_new_owner(cache: TokenCache) -> None:
    """原持有者的键已经过期并被别人写下之后，退出不得删掉新键。"""
    key = "mcp:biz-token-lock:1:10"
    first_in = asyncio.Event()
    first_release = asyncio.Event()
    second_in = asyncio.Event()
    second_release = asyncio.Event()

    async def first() -> None:
        async with cache.lock(1, 10):
            first_in.set()
            await first_release.wait()

    async def second() -> None:
        async with cache.lock(1, 10):
            second_in.set()
            await second_release.wait()

    holder = asyncio.create_task(first())
    await first_in.wait()
    cache.redis.force_expire(key)
    newcomer = asyncio.create_task(second())
    await asyncio.wait_for(second_in.wait(), timeout=2)
    new_token = await cache.redis.get(key)
    assert new_token not in (None, "")
    first_release.set()
    await asyncio.wait_for(holder, timeout=2)
    assert await cache.redis.get(key) == new_token
    second_release.set()
    await asyncio.wait_for(newcomer, timeout=2)
    assert await cache.redis.get(key) is None


async def test_lock_is_always_released(cache: TokenCache) -> None:
    async with cache.lock(1, 10):
        assert await cache.redis.get("mcp:biz-token-lock:1:10") is not None
    assert await cache.redis.get("mcp:biz-token-lock:1:10") is None

    with pytest.raises(RuntimeError, match="boom"):
        async with cache.lock(1, 10):
            raise RuntimeError("boom")
    assert await cache.redis.get("mcp:biz-token-lock:1:10") is None


async def test_refresh_helper_runs_coroutine_while_holding_lock(cache: TokenCache) -> None:
    seen: dict[str, object] = {}

    async def operation() -> str:
        seen["lock"] = await cache.redis.get("mcp:biz-token-lock:1:10")
        return "refreshed"

    result = await run_under_token_lock(cache, 1, 10, operation())
    assert result == "refreshed"
    assert seen["lock"] not in (None, "")
    assert await cache.redis.get("mcp:biz-token-lock:1:10") is None


def _body(response: Any) -> dict[str, Any]:
    return json.loads(response.body)


async def test_admin_query_returns_cached_fields_and_empty_list(cache: TokenCache) -> None:
    future = datetime.now(UTC) + timedelta(minutes=5)
    past = datetime.now(UTC) - timedelta(seconds=30)
    await cache.put(1, 10, bundle("oa-token", future))
    await cache.put(1, 20, bundle("mes-token", past))
    await cache.put(2, 10, bundle("other-token", future))

    empty = _body(await list_biz_token_cache_controller(auth=None, redis=cache.redis, user_id=9, system_id=9))  # type: ignore[arg-type]
    assert empty["data"] == []

    by_user = _body(await list_biz_token_cache_controller(auth=None, redis=cache.redis, user_id=1, system_id=None))  # type: ignore[arg-type]
    assert {row["access_token"] for row in by_user["data"]} == {"oa-token", "mes-token"}

    by_system = _body(await list_biz_token_cache_controller(auth=None, redis=cache.redis, user_id=None, system_id=10))  # type: ignore[arg-type]
    assert {row["access_token"] for row in by_system["data"]} == {"oa-token", "other-token"}

    one = _body(await list_biz_token_cache_controller(auth=None, redis=cache.redis, user_id=1, system_id=20))  # type: ignore[arg-type]
    assert len(one["data"]) == 1
    row = one["data"][0]
    assert row["access_token"] == "mes-token"
    assert row["token_type"] == "Bearer"
    assert row["expired"] is True
    assert row["expires_at"]

    everyone = _body(await list_biz_token_cache_controller(auth=None, redis=cache.redis, user_id=None, system_id=None))  # type: ignore[arg-type]
    assert {row["access_token"] for row in everyone["data"]} == {"oa-token", "mes-token", "other-token"}
    assert all({"access_token", "expires_at", "token_type", "expired", "vars", "var_keys"} <= set(item) for item in everyone["data"])
    assert all(isinstance(item["vars"], dict) for item in everyone["data"])


def test_admin_route_lists_cache_for_query_permission() -> None:
    assert BizTokenCacheRouter in DOMAIN_CONTROLLERS["/mcp-gateway"]
    routes = [route for route in BizTokenCacheRouter.routes if isinstance(route, APIRoute) and route.path == "/biz-token-cache"]
    assert len(routes) == 1
    assert "GET" in routes[0].methods
    assert routes[0].methods <= {"GET", "HEAD"}
    assert _permission_names(routes[0]) == {"module_mcp_gateway:biz-token-cache:query"}
