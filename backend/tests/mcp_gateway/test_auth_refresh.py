"""同步登录后调用业务接口。上游 401 只重新登录一次。不启动应用，不访问真实 OA。"""

import importlib.util
import json
from base64 import b64encode
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs

import httpx
import pytest

from app.modules.mcp_gateway.auth.client import AuthClient, BindingUnavailable
from app.modules.mcp_gateway.auth.extract import TokenBundle
from app.modules.mcp_gateway.auth.model import AuthConfigModel
from app.modules.mcp_gateway.binding.model import BizBindingModel
from app.modules.mcp_gateway.system.model import BizSystemModel
from app.modules.mcp_gateway.token_cache.store import TokenCache

USER_ID = 1
SYSTEM_ID = 10
_TOKEN_RULE = {
    "token_from": "json",
    "token_name": "token",
    "expires_from": "json",
    "expires_name": "expires_in",
    "expires_unit": "seconds",
}
_LOGIN_BODY = {"token": "new", "expires_in": 60}
_LOCK_KEY = f"mcp:biz-token-lock:{USER_ID}:{SYSTEM_ID}"
_TOKEN_KEY = f"mcp:biz-token:{USER_ID}:{SYSTEM_ID}"


def _load_expiring_redis() -> type:
    path = Path(__file__).with_name("test_token_cache.py")
    spec = importlib.util.spec_from_file_location("mcp_gateway_task4_token_cache", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("task 4 redis fake is missing")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.ExpiringRedis


ExpiringRedis = _load_expiring_redis()


def _system() -> BizSystemModel:
    return BizSystemModel(
        id=SYSTEM_ID,
        name="OA",
        code="oa",
        base_url="https://oa.example.com/app",
        enabled=True,
        params={"client_id": "oa-app"},
        uid_field="employee_no",
        attr_fields=["dept"],
    )


def _binding(*, enabled: bool = True, user_id: int = USER_ID, system_id: int = SYSTEM_ID) -> BizBindingModel:
    return BizBindingModel(
        id=3,
        user_id=user_id,
        system_id=system_id,
        uid_value="zhangsan",
        attrs={"dept": "rd", "secret": "hidden"},
        enabled=enabled,
    )


def _auth(
    *,
    method: str = "fixed",
    url: str = "/login",
    http_method: str | None = None,
    username: str | None = None,
    password: str | None = None,
    rule: dict[str, Any] | None = None,
) -> AuthConfigModel:
    return AuthConfigModel(
        id=5,
        system_id=SYSTEM_ID,
        method=method,
        enabled=True,
        url=url,
        rule=dict(rule or _TOKEN_RULE),
        http_method=http_method,
        username=username,
        password_encrypted=password,
    )


def _business_call() -> dict[str, Any]:
    return {
        "method": "GET",
        "url": "https://oa.example.com/app/todos",
        "headers": {
            "Authorization": "Bearer {{token}}",
            "X-Uid": "{{user.uid}}",
            "X-Dept": "{{user.attr.dept}}",
            "X-App": "{{system.client_id}}",
            "X-Secret": "{{user.attr.secret}}",
        },
        "params": {"access_token": "{{token}}"},
        "arguments": {
            "token": "from-caller",
            "uid": "from-caller",
            "username": "from-caller",
            "password": "from-caller",
            "access_token": "from-caller",
            "employee_no": "from-caller",
            "user": {"uid": "from-caller", "attr": {"dept": "from-caller", "secret": "from-caller"}},
            "system": {"client_id": "from-caller"},
        },
    }


class _Upstream:
    """登录固定返回 brief 里的 JSON。业务接口按给定状态码依次响应。"""

    def __init__(self, redis: Any, statuses: list[int]) -> None:
        self.redis = redis
        self.statuses = statuses
        self.logins: list[httpx.Request] = []
        self.business: list[httpx.Request] = []
        self.lock_held: list[bool] = []

    def handler(self, request: httpx.Request) -> httpx.Response:
        leaf = request.url.path.rstrip("/").rsplit("/", 1)[-1]
        if leaf == "todos":
            self.business.append(request)
            index = len(self.business)
            status = self.statuses[index - 1]
            return httpx.Response(status, text=f"biz-{index}")
        self.logins.append(request)
        self.lock_held.append(_LOCK_KEY in self.redis._data)
        return httpx.Response(200, json=_LOGIN_BODY)


def _client(
    transport: httpx.BaseTransport,
    redis: Any,
    *,
    binding: BizBindingModel | None = None,
    omit_binding: bool = False,
    auth: AuthConfigModel | None = None,
) -> tuple[AuthClient, TokenCache]:
    cache = TokenCache(redis)
    chosen = None if omit_binding else _binding() if binding is None else binding
    client = AuthClient(cache=cache, system=_system(), binding=chosen, auth=auth or _auth(), transport=transport)
    return client, cache


def _assert_business_identity(request: httpx.Request) -> None:
    assert request.headers["Authorization"] == "Bearer new"
    assert request.url.params["access_token"] == "new"
    assert request.headers["X-Uid"] == "zhangsan"
    assert request.headers["X-Dept"] == "rd"
    assert request.headers["X-App"] == "oa-app"
    assert request.headers["X-Secret"] == "{{user.attr.secret}}"
    assert "from-caller" not in str(request.url)
    for value in request.headers.values():
        assert "from-caller" not in value


def _assert_fixed_login(request: httpx.Request) -> None:
    assert request.method == "POST"
    assert request.url.host == "oa.example.com"
    assert request.url.path == "/app/login"
    assert dict(request.url.params) == {}
    assert json.loads(request.content) == {"employee_no": "zhangsan"}
    assert request.headers.get("authorization") is None
    assert "new" not in request.content.decode()
    assert "from-caller" not in request.content.decode()


async def test_business_call_retries_once_after_401_and_third_request_does_not_login() -> None:
    redis = ExpiringRedis()
    upstream = _Upstream(redis, [401, 200, 200])
    client, cache = _client(httpx.MockTransport(upstream.handler), redis, auth=_auth(http_method="DELETE", username="not-the-user", password="not-the-password"))
    before = datetime.now(UTC)

    first = await client.call(USER_ID, SYSTEM_ID, **_business_call())
    third = await client.call(USER_ID, SYSTEM_ID, **_business_call())
    cached = await client.ensure_token(USER_ID, SYSTEM_ID)

    after = datetime.now(UTC)
    assert first.status_code == 200
    assert first.text == "biz-2"
    assert third.status_code == 200
    assert third.text == "biz-3"
    assert len(upstream.logins) == 2
    assert len(upstream.business) == 3
    assert upstream.lock_held == [True, True]
    for request in upstream.logins:
        _assert_fixed_login(request)
    for request in upstream.business:
        _assert_business_identity(request)
    assert cached.access_token == "new"
    assert cached.token_type == "Bearer"
    assert before + timedelta(seconds=58) <= cached.expires_at <= after + timedelta(seconds=62)
    stored = await cache.get(USER_ID, SYSTEM_ID)
    assert stored is not None and stored.access_token == "new"
    assert await cache.get(USER_ID, 20) is None

    await client.ensure_token(USER_ID, SYSTEM_ID, force=True)
    assert len(upstream.logins) == 3
    assert upstream.lock_held == [True, True, True]
    _assert_fixed_login(upstream.logins[2])


async def test_second_401_is_returned_without_a_third_login() -> None:
    redis = ExpiringRedis()
    upstream = _Upstream(redis, [401, 401])
    client, cache = _client(httpx.MockTransport(upstream.handler), redis)

    response = await client.call(USER_ID, SYSTEM_ID, **_business_call())

    assert response.status_code == 401
    assert response.text == "biz-2"
    assert len(upstream.logins) == 2
    assert len(upstream.business) == 2
    stored = await cache.get(USER_ID, SYSTEM_ID)
    assert stored is not None and stored.access_token == "new"
    await client.ensure_token(USER_ID, SYSTEM_ID)
    assert len(upstream.logins) == 2


async def test_retry_login_sees_deleted_cache_and_holds_the_lock() -> None:
    redis = ExpiringRedis()
    seen_token_key: list[bool] = []

    def handler(request: httpx.Request) -> httpx.Response:
        leaf = request.url.path.rstrip("/").rsplit("/", 1)[-1]
        if leaf == "login":
            seen_token_key.append(_TOKEN_KEY in redis._data)
            assert _LOCK_KEY in redis._data
            return httpx.Response(200, json=_LOGIN_BODY)
        return httpx.Response(401, text="denied")

    client, _cache = _client(httpx.MockTransport(handler), redis)
    response = await client.call(USER_ID, SYSTEM_ID, **_business_call())

    assert response.status_code == 401
    assert response.text == "denied"
    assert seen_token_key == [False, False]


_PLACES = {
    "query": "GET",
    "json": "POST",
    "form": "PUT",
}
_TEMPLATE = {
    "uid": "{{user.uid}}",
    "app": "{{system.client_id}}",
    "dept": "{{user.attr.dept}}",
    "echo": "{{token}}",
    "hidden": "{{user.attr.secret}}",
    "missing": "{{system.missing}}",
}
_RENDERED = {
    "uid": "zhangsan",
    "app": "oa-app",
    "dept": "rd",
    "echo": "{{token}}",
    "hidden": "{{user.attr.secret}}",
    "missing": "{{system.missing}}",
}


def _placed(request: httpx.Request, place: str) -> dict[str, str]:
    if place == "query":
        assert request.content == b""
        return dict(request.url.params)
    if place == "json":
        return json.loads(request.content)
    parsed = parse_qs(request.content.decode(), keep_blank_values=True)
    return {key: values[0] for key, values in parsed.items()}


@pytest.mark.parametrize("place", ["query", "json", "form"])
async def test_custom_login_puts_placeholders_where_the_config_says(place: str) -> None:
    redis = ExpiringRedis()
    upstream = _Upstream(redis, [200])
    rule = dict(_TOKEN_RULE)
    rule[place] = dict(_TEMPLATE)
    client, _cache = _client(
        httpx.MockTransport(upstream.handler),
        redis,
        auth=_auth(method="custom", url="https://auth.example.com/login", http_method=_PLACES[place], rule=rule),
    )

    response = await client.call(USER_ID, SYSTEM_ID, **_business_call())

    assert response.status_code == 200
    assert len(upstream.logins) == 1
    assert len(upstream.business) == 1
    login = upstream.logins[0]
    assert login.method == _PLACES[place]
    assert login.url.host == "auth.example.com"
    assert login.url.path == "/login"
    assert _placed(login, place) == _RENDERED
    assert "new" not in login.content.decode()
    assert "from-caller" not in login.content.decode()
    assert "from-caller" not in str(login.url)
    _assert_business_identity(upstream.business[0])
    assert upstream.lock_held == [True]


async def test_basic_login_uses_the_system_account_not_the_person() -> None:
    redis = ExpiringRedis()
    upstream = _Upstream(redis, [200])
    rule = dict(_TOKEN_RULE)
    rule["json"] = {"uid": "{{user.uid}}", "echo": "{{token}}"}
    client, _cache = _client(
        httpx.MockTransport(upstream.handler),
        redis,
        auth=_auth(
            method="basic",
            url="/session",
            http_method="PATCH",
            username="svc-account",
            password="svc-pass",
            rule=rule,
        ),
    )

    response = await client.call(USER_ID, SYSTEM_ID, **_business_call())

    assert response.status_code == 200
    assert len(upstream.logins) == 1
    login = upstream.logins[0]
    assert login.method == "PATCH"
    assert login.url.host == "oa.example.com"
    assert login.url.path == "/app/session"
    assert login.headers["authorization"] == "Basic " + b64encode(b"svc-account:svc-pass").decode()
    assert json.loads(login.content) == {"uid": "zhangsan", "echo": "{{token}}"}
    assert "from-caller" not in login.content.decode()
    assert b"zhangsan:".decode() not in login.headers["authorization"]
    _assert_business_identity(upstream.business[0])


async def test_missing_or_disabled_binding_does_not_send_the_business_request() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json=_LOGIN_BODY)

    transport = httpx.MockTransport(handler)
    redis = ExpiringRedis()
    missing, _cache = _client(transport, redis, omit_binding=True)
    disabled, _cache = _client(transport, redis, binding=_binding(enabled=False))

    with pytest.raises(BindingUnavailable):
        await missing.call(USER_ID, SYSTEM_ID, **_business_call())
    with pytest.raises(BindingUnavailable):
        await disabled.call(USER_ID, SYSTEM_ID, **_business_call())

    assert seen == []


async def test_interactive_uses_a_cached_token_without_logging_in() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, text="biz-ok")

    redis = ExpiringRedis()
    client, cache = _client(httpx.MockTransport(handler), redis, auth=_auth(method="interactive", url="/verify"))
    await cache.put(
        USER_ID,
        SYSTEM_ID,
        TokenBundle(access_token="kept", expires_at=datetime.now(UTC) + timedelta(minutes=5), token_type="Bearer"),
    )

    token = await client.ensure_token(USER_ID, SYSTEM_ID, force=True)
    response = await client.call(USER_ID, SYSTEM_ID, **_business_call())

    assert token.access_token == "kept"
    assert response.status_code == 200
    assert response.text == "biz-ok"
    assert len(seen) == 1
    assert seen[0].url.path == "/app/todos"
    assert seen[0].headers["Authorization"] == "Bearer kept"
    kept = await cache.get(USER_ID, SYSTEM_ID)
    assert kept is not None and kept.access_token == "kept"


async def test_expired_cache_is_not_reused() -> None:
    redis = ExpiringRedis()
    upstream = _Upstream(redis, [200])
    client, cache = _client(httpx.MockTransport(upstream.handler), redis)
    await cache.put(
        USER_ID,
        SYSTEM_ID,
        TokenBundle(access_token="stale", expires_at=datetime.now(UTC) - timedelta(seconds=30), token_type="Bearer"),
    )

    response = await client.call(USER_ID, SYSTEM_ID, **_business_call())

    assert response.status_code == 200
    assert response.text == "biz-1"
    assert len(upstream.logins) == 1
    assert upstream.business[0].headers["Authorization"] == "Bearer new"
    fresh = await client.ensure_token(USER_ID, SYSTEM_ID)
    assert fresh.access_token == "new"
    assert len(upstream.logins) == 1


class _CloseCountingTransport(httpx.MockTransport):
    """aclose 计数。每次请求都关掉 transport 时，这个数会增加。"""

    def __init__(self, handler: Any) -> None:
        super().__init__(handler)
        self.closes = 0

    async def aclose(self) -> None:
        self.closes += 1


async def test_calls_leave_the_injected_transport_open() -> None:
    redis = ExpiringRedis()
    upstream = _Upstream(redis, [200, 200])
    transport = _CloseCountingTransport(upstream.handler)
    client, _cache = _client(transport, redis)

    first = await client.call(USER_ID, SYSTEM_ID, **_business_call())
    second = await client.call(USER_ID, SYSTEM_ID, **_business_call())

    assert first.status_code == 200
    assert first.text == "biz-1"
    assert second.status_code == 200
    assert second.text == "biz-2"
    assert len(upstream.logins) == 1
    assert len(upstream.business) == 2
    assert transport.closes == 0

    await client.aclose()
    assert transport.closes == 0
