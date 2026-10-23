"""REST 工具占位符与未保存表单的调试。占位符测试不启动应用。调试用 MockTransport，不访问真实 OA。"""

import importlib.util
import json
from pathlib import Path
from typing import Any

import httpx
import pytest

from app.modules.mcp_gateway.auth.client import BindingUnavailable
from app.modules.mcp_gateway.auth.model import AuthConfigModel
from app.modules.mcp_gateway.binding.model import BizBindingModel
from app.modules.mcp_gateway.system.model import BizSystemModel
from app.modules.mcp_gateway.token_cache.store import TokenCache

USER_ID = 1
SYSTEM_ID = 10
_BUSINESS_TOKEN = "secret-token"


def test_reserved_placeholders_ignore_call_arguments():
    from app.modules.mcp_gateway.rest_tool.render import build_context

    ctx = build_context(
        system_params={"host": "oa"},
        uid="zhangsan",
        attrs={"dept": "rd"},
        token="secret",
        arguments={"token": "from-client", "page": 1},
    )
    assert ctx["token"] == "secret"
    assert ctx["args"]["page"] == 1


def _load_expiring_redis() -> type:
    path = Path(__file__).with_name("test_token_cache.py")
    spec = importlib.util.spec_from_file_location("mcp_gateway_task7_token_cache", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("task 4 redis fake is missing")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.ExpiringRedis


def _system() -> BizSystemModel:
    return BizSystemModel(
        id=SYSTEM_ID,
        name="OA",
        code="oa",
        base_url="https://oa.example.com/app",
        enabled=True,
        params={"host": "oa"},
        uid_field="employee_no",
        attr_fields=["dept"],
    )


def _binding(*, enabled: bool = True) -> BizBindingModel:
    return BizBindingModel(
        id=3,
        user_id=USER_ID,
        system_id=SYSTEM_ID,
        uid_value="zhangsan",
        attrs={"dept": "rd"},
        enabled=enabled,
    )


def _auth() -> AuthConfigModel:
    return AuthConfigModel(
        id=5,
        system_id=SYSTEM_ID,
        method="fixed",
        enabled=True,
        url="/login",
        rule={
            "token_from": "json",
            "token_name": "token",
            "expires_from": "json",
            "expires_name": "expires_in",
            "expires_unit": "seconds",
        },
        http_method=None,
        username=None,
        password=None,
    )


def _draft() -> dict[str, Any]:
    """还没保存的表单。没有 id，调试不能把它插进工具表。"""
    return {
        "name": "todos",
        "display_name": "待办",
        "url": "/todos/{page}",
        "description": "未保存",
        "request_type": "GET",
        "headers": {"X-Uid": "{{user.uid}}"},
        "input_schema": {"type": "object"},
        "output_schema": {},
        "jsonpath_filter": None,
        "query_mapping": {},
        "header_mapping": {},
        "timeout_ms": 5000,
        "token_in": "header",
        "token_name": "Authorization",
        "enabled": True,
        "system_id": SYSTEM_ID,
    }


def _service(transport: httpx.BaseTransport, redis: Any, logs: list, saved: list, *, binding: BizBindingModel | None):
    from app.modules.mcp_gateway.rest_tool.service import RestToolService

    return RestToolService(
        system=_system(),
        binding=binding,
        auth_config=_auth(),
        cache=TokenCache(redis),
        transport=transport,
        logs=logs,
        saved=saved,
    )


async def test_debug_unsaved_form_skips_log_and_unbound_user() -> None:
    """已绑定用户调试未保存表单。Mock OA 返回 200。不写调用日志，也不插入工具。未绑定用户不会打到 OA。"""
    from app.modules.mcp_gateway.rest_tool.service import RestToolService

    ExpiringRedis = _load_expiring_redis()
    redis = ExpiringRedis()
    logs: list[dict[str, Any]] = []
    saved: list[dict[str, Any]] = []
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        if request.url.path.rstrip("/").endswith("/login"):
            return httpx.Response(200, json={"token": _BUSINESS_TOKEN, "expires_in": 60})
        return httpx.Response(200, json={"ok": True})

    service: RestToolService = _service(httpx.MockTransport(handler), redis, logs, saved, binding=_binding())
    result = await service.debug(_draft(), USER_ID, {"page": 1, "token": "from-client", "q": "open"})

    business = [request for request in seen if not request.url.path.rstrip("/").endswith("/login")]
    assert len(business) == 1
    assert business[0].url.path == "/app/todos/1"
    assert business[0].headers["authorization"] == f"Bearer {_BUSINESS_TOKEN}"
    assert business[0].url.params["q"] == "open"
    assert business[0].url.params["token"] == "from-client"
    assert result.status == 200
    assert result.response == {"ok": True}
    rendered = json.dumps({"request": result.request, "response": result.response}, ensure_ascii=False)
    assert _BUSINESS_TOKEN not in rendered
    assert "Bearer ******" in rendered
    assert logs == []
    assert saved == []
    assert not hasattr(service, "write_log")

    unbound_seen: list[httpx.Request] = []

    def unbound_handler(request: httpx.Request) -> httpx.Response:
        unbound_seen.append(request)
        return httpx.Response(200, json={"ok": True})

    unbound = _service(httpx.MockTransport(unbound_handler), ExpiringRedis(), logs, saved, binding=None)
    with pytest.raises(BindingUnavailable):
        await unbound.debug(_draft(), USER_ID, {"page": 1, "token": "from-client"})
    assert unbound_seen == []
