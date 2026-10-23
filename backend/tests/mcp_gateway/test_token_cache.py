"""业务 token 按用户和业务系统分键存在 Redis。不访问 OA，不登录。"""

import asyncio
import json
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from fastapi.routing import APIRoute
from redis.asyncio import Redis

from app.api.v1.routers import DOMAIN_CONTROLLERS
from app.core.dependencies import AuthPermission
from app.modules.mcp_gateway.auth.extract import TokenBundle
from app.modules.mcp_gateway.auth.refresh import run_under_token_lock
from app.modules.mcp_gateway.token_cache.controller import BizTokenCacheRouter, list_biz_token_cache_controller
from app.modules.mcp_gateway.token_cache.store import TokenCache

_PAIRS = ((1, 10), (1, 20), (2, 10), (2, 20), (9, 9))


def bundle(access_token: str, expires_at: datetime | None = None) -> TokenBundle:
    return TokenBundle(
        access_token=access_token,
        expires_at=expires_at or (datetime.now(UTC) + timedelta(hours=1)),
        token_type="Bearer",
    )


async def _wipe(redis: Redis) -> None:
    keys: list[str] = []
    for user_id, system_id in _PAIRS:
        keys.append(f"mcp:biz-token:{user_id}:{system_id}")
        keys.append(f"mcp:biz-token-lock:{user_id}:{system_id}")
    await redis.delete(*keys)


@pytest.fixture
async def cache() -> Any:
    """用户 1、系统 10 和 20 只是缓存键，不要求数据库里有这些行。"""
    redis = Redis.from_url("redis://test")
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
    assert all({"access_token", "expires_at", "token_type", "expired"} <= set(item) for item in everyone["data"])


def test_admin_route_lists_cache_for_query_permission() -> None:
    assert BizTokenCacheRouter in DOMAIN_CONTROLLERS["/mcp-gateway"]
    routes = [route for route in BizTokenCacheRouter.routes if isinstance(route, APIRoute) and route.path == "/biz-token-cache"]
    assert len(routes) == 1
    assert "GET" in routes[0].methods
    assert routes[0].methods <= {"GET", "HEAD"}
    assert _permission_names(routes[0]) == {"module_mcp_gateway:biz-token-cache:query"}
