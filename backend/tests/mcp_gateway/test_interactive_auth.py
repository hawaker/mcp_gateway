"""交互式验证链接只属于一个用户。不启动完整应用，不要求用户或系统行在数据库里。"""

import json
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
import pytest
from fastapi import APIRouter, FastAPI
from fastapi.routing import APIRoute

from app.api.v1.routers import DOMAIN_CONTROLLERS
from app.core.dependencies import AuthPermission
from app.modules.mcp_gateway.auth.client import AuthClient, BindingUnavailable, InteractiveAuthRequired
from app.modules.mcp_gateway.auth.extract import TokenBundle
from app.modules.mcp_gateway.auth.interactive import LINK_TTL_SECONDS, InteractiveAuth
from app.modules.mcp_gateway.auth.interactive_controller import InteractiveAuthRouter
from app.modules.mcp_gateway.auth.model import AuthConfigModel
from app.modules.mcp_gateway.binding.model import BizBindingModel
from app.modules.mcp_gateway.system.model import BizSystemModel
from app.modules.mcp_gateway.token_cache.store import TokenCache

_LINK_PREFIX = "/mcp-gateway/auth/interactive/"
_HEADER_RULE = {
    "token_from": "header",
    "token_name": "X-Token",
    "expires_from": "header",
    "expires_name": "X-Expires-In",
    "expires_unit": "seconds",
    "token_type": "Bearer",
}
_FORM_RULE = {
    "token_from": "form",
    "token_name": "access_token",
    "expires_from": "form",
    "expires_name": "expires_in",
    "expires_unit": "seconds",
}
_state: dict[str, Any] = {}


class RecordingRedis:
    """记下 set 的 ex。键不会自己过期，和共享的 Redis mock 一样。"""

    def __init__(self) -> None:
        self.values: dict[str, str] = {}
        self.sets: list[dict[str, Any]] = []

    async def set(self, name: Any, value: Any, ex: int | None = None, **kwargs: Any) -> bool:
        text = value.decode() if isinstance(value, bytes) else str(value)
        self.sets.append({"name": str(name), "value": text, "ex": ex, **kwargs})
        self.values[str(name)] = text
        return True

    async def get(self, name: Any) -> str | None:
        return self.values.get(str(name))

    async def delete(self, *names: Any) -> int:
        count = 0
        for name in names:
            if self.values.pop(str(name), None) is not None:
                count += 1
        return count


def _config(*, system_id: int = 10, method: str = "interactive", enabled: bool = True, rule: dict[str, Any] | None = None) -> AuthConfigModel:
    return AuthConfigModel(
        id=5,
        system_id=system_id,
        method=method,
        enabled=enabled,
        url="https://oa.example.com/verify",
        rule=dict(rule or _HEADER_RULE),
    )


def _system() -> BizSystemModel:
    return BizSystemModel(
        id=10,
        name="OA",
        code="oa",
        base_url="https://oa.example.com/app",
        enabled=True,
        params={"client_id": "oa-app"},
        uid_field="employee_no",
        attr_fields=["dept"],
    )


def _binding(*, enabled: bool = True) -> BizBindingModel:
    return BizBindingModel(id=3, user_id=1, system_id=10, uid_value="zhangsan", attrs={"dept": "rd"}, enabled=enabled)


@pytest.fixture
async def cache() -> Any:
    """用户 1、2 和系统 10 只写在 nonce 上，不查这两张表。"""
    redis = RecordingRedis()
    _state["redis"] = redis
    _state["configs"] = {10: _config()}
    yield TokenCache(redis)  # type: ignore[arg-type]
    _state.clear()


@pytest.fixture
async def client(cache: TokenCache) -> Any:
    app = FastAPI()
    parent = APIRouter(prefix="/mcp-gateway")
    parent.include_router(InteractiveAuthRouter)
    app.include_router(parent)
    app.state.redis = cache.redis
    app.state.interactive_configs = _state["configs"]
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://interactive.test") as http:
        yield http


async def start_for(*, user_id: int, system_id: int) -> str:
    """给样本测试用。nonce 记在和 cache 同一份 Redis 上。"""
    return await InteractiveAuth(_state["redis"]).start(user_id, system_id)


def _link_writes(cache: TokenCache) -> list[dict[str, Any]]:
    return [item for item in cache.redis.sets if str(item["name"]).startswith("mcp:auth-link:")]


def _nonce(link: str) -> str:
    assert link.startswith(_LINK_PREFIX)
    nonce = link.removeprefix(_LINK_PREFIX)
    assert nonce and "/" not in nonce and nonce != "callback"
    return nonce


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


async def test_link_is_bound_to_one_user(client, cache):
    link = await start_for(user_id=1, system_id=10)
    stolen = await client.get(link, headers={"X-Test-User": "2"})
    assert stolen.status_code == 403
    assert await cache.get(1, 10) is None


async def test_link_ttl_is_ten_minutes_and_stores_only_the_two_ids(cache: TokenCache) -> None:
    link = await start_for(user_id=1, system_id=10)
    nonce = _nonce(link)
    writes = _link_writes(cache)
    assert len(writes) == 1
    saved = writes[0]
    assert saved["name"] == f"mcp:auth-link:{nonce}"
    assert saved["ex"] == LINK_TTL_SECONDS == 600
    assert json.loads(saved["value"]) == {"user_id": 1, "system_id": 10}
    assert not link.startswith("/api/v1")


async def test_missing_or_other_user_cannot_open_or_fill_the_cache(client: httpx.AsyncClient, cache: TokenCache) -> None:
    link = await start_for(user_id=1, system_id=10)

    missing = await client.get(link)
    assert missing.status_code == 403
    mismatch = await client.get(link, headers={"X-Test-User": "abc"})
    assert mismatch.status_code == 403
    owner = await client.get(link, headers={"X-Test-User": "1"})
    assert owner.status_code == 200
    assert "https://oa.example.com/verify" in owner.text
    assert await cache.get(1, 10) is None
    assert f"mcp:auth-link:{_nonce(link)}" in cache.redis.values


async def test_callback_route_is_not_captured_as_a_nonce(client: httpx.AsyncClient, cache: TokenCache) -> None:
    cache.redis.values["mcp:auth-link:callback"] = json.dumps({"user_id": 1, "system_id": 10})
    response = await client.get("/mcp-gateway/auth/interactive/callback", headers={"X-Test-User": "2"})
    assert response.status_code != 403
    assert await cache.get(1, 10) is None


def test_routes_are_public_and_callback_is_declared_first() -> None:
    assert InteractiveAuthRouter in DOMAIN_CONTROLLERS["/mcp-gateway"]
    routes = [route for route in InteractiveAuthRouter.routes if isinstance(route, APIRoute)]
    by_path = {route.path: route for route in routes}
    callback = by_path["/auth/interactive/callback"]
    page = by_path["/auth/interactive/{nonce}"]
    assert routes.index(callback) < routes.index(page)
    assert callback.methods is not None and "GET" in callback.methods
    assert page.methods is not None and "GET" in page.methods
    assert _permission_names(callback) == set()
    assert _permission_names(page) == set()
    assert all("/api/v1" not in route.path for route in routes)


async def test_callback_stores_header_token_for_the_nonce_user(client: httpx.AsyncClient, cache: TokenCache) -> None:
    _state["configs"][11] = _config(system_id=11)
    link = await start_for(user_id=1, system_id=11)
    nonce = _nonce(link)
    before = datetime.now(UTC)

    response = await client.get(
        "/mcp-gateway/auth/interactive/callback",
        params={"nonce": nonce},
        headers={"X-Test-User": "1", "X-Token": "Bearer biz-secret", "X-Expires-In": "120"},
    )

    after = datetime.now(UTC)
    assert response.status_code == 200
    assert "biz-secret" not in response.text
    for value in response.headers.values():
        assert "biz-secret" not in value
    assert await cache.get(1, 10) is None
    bundle = await cache.get(1, 11)
    assert bundle is not None
    assert bundle.access_token == "biz-secret"
    assert bundle.token_type == "Bearer"
    assert before + timedelta(seconds=120) <= bundle.expires_at <= after + timedelta(seconds=120)
    assert f"mcp:auth-link:{nonce}" not in cache.redis.values


async def test_callback_reads_form_token_from_the_query(client: httpx.AsyncClient, cache: TokenCache) -> None:
    _state["configs"][10] = _config(rule=_FORM_RULE)
    link = await start_for(user_id=1, system_id=10)
    response = await client.get(
        "/mcp-gateway/auth/interactive/callback",
        params={"nonce": _nonce(link), "access_token": "query-secret", "expires_in": "30"},
        headers={"X-Test-User": "1"},
    )
    assert response.status_code == 200
    assert "query-secret" not in response.text
    bundle = await cache.get(1, 10)
    assert bundle is not None and bundle.access_token == "query-secret"


async def test_callback_rejects_the_wrong_user_and_a_missing_nonce(client: httpx.AsyncClient, cache: TokenCache) -> None:
    link = await start_for(user_id=1, system_id=10)
    nonce = _nonce(link)
    stolen = await client.get(
        "/mcp-gateway/auth/interactive/callback",
        params={"nonce": nonce},
        headers={"X-Test-User": "2", "X-Token": "Bearer stolen-token", "X-Expires-In": "120"},
    )
    assert stolen.status_code == 403
    assert "stolen-token" not in stolen.text
    assert await cache.get(1, 10) is None

    absent = await client.get(
        "/mcp-gateway/auth/interactive/callback",
        params={"nonce": "missing-nonce"},
        headers={"X-Test-User": "1", "X-Token": "Bearer absent-token", "X-Expires-In": "120"},
    )
    assert absent.status_code == 404
    assert "absent-token" not in absent.text
    assert await cache.get(1, 10) is None
    assert f"mcp:auth-link:{nonce}" in cache.redis.values


async def test_callback_does_not_cache_when_extraction_or_rule_fails(client: httpx.AsyncClient, cache: TokenCache) -> None:
    link = await start_for(user_id=1, system_id=10)
    nonce = _nonce(link)
    failed = await client.get(
        "/mcp-gateway/auth/interactive/callback",
        params={"nonce": nonce, "access_token": "leaked-token"},
        headers={"X-Test-User": "1"},
    )
    assert failed.status_code == 400
    assert "leaked-token" not in failed.text
    assert await cache.get(1, 10) is None
    assert f"mcp:auth-link:{nonce}" in cache.redis.values

    _state["configs"].clear()
    no_rule = await client.get(
        "/mcp-gateway/auth/interactive/callback",
        params={"nonce": nonce},
        headers={"X-Test-User": "1", "X-Token": "Bearer later-token", "X-Expires-In": "120"},
    )
    assert no_rule.status_code == 400
    assert "later-token" not in no_rule.text
    assert await cache.get(1, 10) is None

    _state["configs"][10] = _config(method="fixed")
    other_method = await client.get(
        "/mcp-gateway/auth/interactive/callback",
        params={"nonce": nonce},
        headers={"X-Test-User": "1", "X-Token": "Bearer fixed-token", "X-Expires-In": "120"},
    )
    assert other_method.status_code == 400
    assert await cache.get(1, 10) is None


def _auth_client(
    transport: httpx.BaseTransport,
    redis: RecordingRedis,
    *,
    binding: BizBindingModel | None = None,
    omit_binding: bool = False,
) -> AuthClient:
    chosen = None if omit_binding else _binding() if binding is None else binding
    return AuthClient(
        cache=TokenCache(redis),  # type: ignore[arg-type]
        system=_system(),
        binding=chosen,
        auth=_config(),
        transport=transport,
    )


async def test_cached_interactive_token_is_used_without_a_new_link() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, text="biz-ok")

    redis = RecordingRedis()
    client = _auth_client(httpx.MockTransport(handler), redis)
    await client.cache.put(
        1,
        10,
        TokenBundle(access_token="kept", expires_at=datetime.now(UTC) + timedelta(minutes=5), token_type="Bearer"),
    )

    token = await client.ensure_token(1, 10, force=True)
    response = await client.call(
        1,
        10,
        method="GET",
        url="https://oa.example.com/app/todos",
        headers={"Authorization": "Bearer {{token}}"},
    )

    assert token.access_token == "kept"
    assert response.status_code == 200
    assert response.text == "biz-ok"
    assert len(seen) == 1
    assert seen[0].url.path == "/app/todos"
    assert seen[0].headers["Authorization"] == "Bearer kept"
    assert _link_writes(client.cache) == []


async def test_missing_interactive_cache_returns_a_link_and_does_not_login() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json={"token": "new", "expires_in": 60})

    redis = RecordingRedis()
    client = _auth_client(httpx.MockTransport(handler), redis)

    with pytest.raises(InteractiveAuthRequired) as caught:
        await client.call(1, 10, method="GET", url="https://oa.example.com/app/todos")

    assert seen == []
    assert caught.value.link.startswith(_LINK_PREFIX)
    assert await client.cache.get(1, 10) is None
    writes = _link_writes(client.cache)
    assert len(writes) == 1
    assert writes[0]["ex"] == 600
    await client.cache.put(
        1,
        10,
        TokenBundle(access_token="stale", expires_at=datetime.now(UTC) - timedelta(seconds=5), token_type="Bearer"),
    )
    with pytest.raises(InteractiveAuthRequired) as expired:
        await client.ensure_token(1, 10)
    assert expired.value.link.startswith(_LINK_PREFIX)
    assert seen == []


async def test_interactive_401_deletes_the_cache_and_does_not_force_login() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(401, text="token=upstream-secret")

    redis = RecordingRedis()
    client = _auth_client(httpx.MockTransport(handler), redis)
    await client.cache.put(
        1,
        10,
        TokenBundle(access_token="kept", expires_at=datetime.now(UTC) + timedelta(minutes=5), token_type="Bearer"),
    )
    force_flags: list[bool] = []
    original = client.ensure_token

    async def spy(user_id: int, system_id: int, *, force: bool = False) -> TokenBundle:
        force_flags.append(force)
        return await original(user_id, system_id, force=force)

    client.ensure_token = spy  # type: ignore[method-assign]

    with pytest.raises(InteractiveAuthRequired) as caught:
        await client.call(
            1,
            10,
            method="GET",
            url="https://oa.example.com/app/todos",
            headers={"Authorization": "Bearer {{token}}"},
        )

    assert len(seen) == 1
    assert seen[0].url.path == "/app/todos"
    assert True not in force_flags
    assert await client.cache.get(1, 10) is None
    assert caught.value.link.startswith(_LINK_PREFIX)
    assert "upstream-secret" not in str(caught.value)
    assert "kept" not in str(caught.value)


async def test_interactive_without_a_binding_does_not_link_or_call() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, text="nope")

    redis = RecordingRedis()
    client = _auth_client(httpx.MockTransport(handler), redis, omit_binding=True)

    with pytest.raises(BindingUnavailable):
        await client.call(1, 10, method="GET", url="https://oa.example.com/app/todos")
    with pytest.raises(BindingUnavailable):
        await client.ensure_token(1, 10)

    assert seen == []
    assert _link_writes(client.cache) == []
