"""向业务系统同步登录，并在业务接口 401 时重新登录一次。

interactive 不在这里登录。有未过期缓存就用；没有，或业务接口返回 401，就返回新的验证链接。
不登记 REST 工具。
"""

import re
from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any

import httpx

from app.modules.mcp_gateway.auth.extract import TokenBundle, extract_captures, extract_token, resolve_url
from app.modules.mcp_gateway.auth.interactive import InteractiveAuth
from app.modules.mcp_gateway.auth.migrate_rule import lift_custom_request_from_rule
from app.modules.mcp_gateway.auth.model import AuthConfigModel
from app.modules.mcp_gateway.auth.refresh import run_under_token_lock
from app.modules.mcp_gateway.binding.model import BizBindingModel
from app.modules.mcp_gateway.system.model import BizSystemModel
from app.modules.mcp_gateway.token_cache.store import TokenCache
from app.utils.crypto_util import CryptoUtil

# system / user / auth。调用参数里的同名值不参与替换。不再识别 {{token}}。
_PLACEHOLDER = re.compile(
    r"\{\{(?:system\.(?P<system>[A-Za-z0-9_]+)|user\.uid|user\.attr\.(?P<attr>[A-Za-z0-9_]+)|auth\.(?P<auth>[A-Za-z0-9_]+))\}\}"
)


class CallerLiteral:
    """调用方传入的原值。业务请求先渲染工具模板，再把这些值并进去，且不再渲染。"""

    __slots__ = ("value",)

    def __init__(self, value: Any) -> None:
        self.value = value


class BindingUnavailable(Exception):
    """没有可用绑定。这次不会向业务系统发请求。"""


class InteractiveAuthRequired(Exception):
    """交互式验证不在这里登录。link 是给当前用户打开的短期地址。"""

    def __init__(self, link: str) -> None:
        self.link = link
        super().__init__(link)


class _BorrowedTransport(httpx.AsyncBaseTransport):
    """转发请求。关闭这一层时不关闭注入的 transport。"""

    def __init__(self, transport: httpx.AsyncBaseTransport) -> None:
        self._transport = transport

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        return await self._transport.handle_async_request(request)

    async def aclose(self) -> None:
        """连接池属于调用方。这里不调用注入 transport 的 aclose。"""


class AuthClient:
    """按 fixed、custom、basic 取 token，并带上 token 调用一次业务接口。

    interactive 只使用未过期缓存。缓存没有，或业务接口返回 401，就给出新的验证链接。
    """

    def __init__(
        self,
        *,
        cache: TokenCache,
        system: BizSystemModel,
        binding: BizBindingModel | None,
        auth: AuthConfigModel,
        transport: httpx.AsyncBaseTransport,
    ) -> None:
        self.cache = cache
        self.system = system
        self.binding = binding
        self.auth = auth
        self.transport = transport
        # 一个客户端用到底。请求结束不能关掉注入的连接池。
        self._http = httpx.AsyncClient(transport=_BorrowedTransport(transport), trust_env=False)

    async def aclose(self) -> None:
        """关闭自己的 AsyncClient。不关闭注入的 transport。"""
        await self._http.aclose()

    async def ensure_token(self, user_id: int, system_id: int, *, force: bool = False) -> TokenBundle:
        """返回未过期缓存。force 为真，或缓存没有可用 token 时，在锁里重新登录。

        interactive 忽略 force：有未过期缓存就返回，没有就给出验证链接，不向业务系统登录。
        """
        if self.auth.method == "interactive":
            return await self._interactive_token(user_id, system_id)
        self._require_sync(user_id, system_id)
        if not force:
            cached = await self._fresh(user_id, system_id)
            if cached is not None:
                return cached
        return await run_under_token_lock(
            self.cache,
            user_id,
            system_id,
            self._login_and_store(user_id, system_id, force=force),
        )

    async def call(
        self,
        user_id: int,
        system_id: int,
        *,
        method: str,
        url: str,
        headers: Mapping[str, Any] | None = None,
        params: Mapping[str, Any] | None = None,
        json_body: Mapping[str, Any] | None = None,
        form: Mapping[str, Any] | None = None,
        arguments: Mapping[str, Any] | None = None,
        timeout: float | None = None,
    ) -> httpx.Response:
        """取 token 后发一次业务请求。401 时删缓存、重新登录一次，再发一次，并返回第二次响应。

        interactive 遇到 401 只删缓存并给出新链接，不调用 ensure_token(force=True)，也不再请求一次。
        timeout 只限制业务请求，不限制登录。
        """
        # arguments 即使带了 token、uid 或系统参数，也不能改占位符的值。
        del arguments
        if self.auth.method == "interactive":
            return await self._call_interactive(
                user_id,
                system_id,
                method=method,
                url=url,
                headers=headers,
                params=params,
                json_body=json_body,
                form=form,
                timeout=timeout,
            )
        self._require_sync(user_id, system_id)
        bundle = await self.ensure_token(user_id, system_id)
        response = await self._send_business(method, url, headers, params, json_body, form, bundle.vars, timeout)
        if response.status_code != 401:
            return response
        await self.cache.delete(user_id, system_id)
        bundle = await self.ensure_token(user_id, system_id, force=True)
        return await self._send_business(method, url, headers, params, json_body, form, bundle.vars, timeout)

    async def _login_and_store(self, user_id: int, system_id: int, *, force: bool) -> TokenBundle:
        if not force:
            cached = await self._fresh(user_id, system_id)
            if cached is not None:
                return cached
        bundle = await self._login()
        await self.cache.put(user_id, system_id, bundle)
        return bundle

    async def _fresh(self, user_id: int, system_id: int) -> TokenBundle | None:
        bundle = await self.cache.get(user_id, system_id)
        if bundle is None:
            return None
        expires_at = bundle.expires_at if bundle.expires_at.tzinfo is not None else bundle.expires_at.replace(tzinfo=UTC)
        if expires_at <= datetime.now(UTC):
            return None
        return bundle

    async def _interactive_token(self, user_id: int, system_id: int) -> TokenBundle:
        """有未过期缓存就用。没有则发链接。这里不能改成 HTTP 登录。"""
        self._require_binding(user_id, system_id)
        cached = await self._fresh(user_id, system_id)
        if cached is not None:
            return cached
        raise await self._link_required(user_id, system_id)

    async def _call_interactive(
        self,
        user_id: int,
        system_id: int,
        *,
        method: str,
        url: str,
        headers: Mapping[str, Any] | None,
        params: Mapping[str, Any] | None,
        json_body: Mapping[str, Any] | None,
        form: Mapping[str, Any] | None,
        timeout: float | None = None,
    ) -> httpx.Response:
        self._require_binding(user_id, system_id)
        cached = await self._fresh(user_id, system_id)
        if cached is None:
            raise await self._link_required(user_id, system_id)
        response = await self._send_business(method, url, headers, params, json_body, form, cached.vars, timeout)
        if response.status_code != 401:
            return response
        await self.cache.delete(user_id, system_id)
        raise await self._link_required(user_id, system_id)

    async def _link_required(self, user_id: int, system_id: int) -> InteractiveAuthRequired:
        link = await InteractiveAuth(self.cache.redis).start(user_id, system_id)
        return InteractiveAuthRequired(link)

    def _require_sync(self, user_id: int, system_id: int) -> None:
        self._require_binding(user_id, system_id)

    def _require_binding(self, user_id: int, system_id: int) -> None:
        binding = self.binding
        if binding is None or not binding.enabled or binding.user_id != user_id or binding.system_id != system_id or self.system.id != system_id:
            raise BindingUnavailable("没有可用的业务绑定")

    async def _login(self) -> TokenBundle:
        method, url, kwargs = self._login_request()
        response = await self._request(method, url, **kwargs)
        rule = self.auth.rule or {}
        if self.auth.method == "custom":
            return extract_captures(body=response.text, headers=dict(response.headers), rule=rule)
        return extract_token(body=response.text, headers=dict(response.headers), rule=rule)

    def _login_request(self) -> tuple[str, str, dict[str, Any]]:
        url = resolve_url(self.system.base_url, self._render_text(self.auth.url, auth_vars=None))
        if self.auth.method == "fixed":
            binding = self._binding()
            return "POST", url, {"json": {self.system.uid_field: binding.uid_value}}

        kwargs: dict[str, Any] = {}
        if self.auth.method == "custom":
            headers, query, body_type, body = self._custom_request_shape()
            if headers:
                kwargs["headers"] = self._render_mapping(headers, auth_vars=None)
            if query:
                kwargs["params"] = self._render_mapping(query, auth_vars=None)
            if body_type == "form" and body is not None:
                kwargs["data"] = self._render_mapping(body, auth_vars=None)
            elif body_type == "json" and body is not None:
                kwargs["json"] = self._render_value(body, auth_vars=None)
        elif self.auth.method == "basic":
            query = self._section("query")
            json_body = self._section("json")
            form = self._section("form")
            if query is not None:
                kwargs["params"] = self._render_mapping(query, auth_vars=None)
            if form is not None:
                kwargs["data"] = self._render_mapping(form, auth_vars=None)
            elif json_body is not None:
                kwargs["json"] = self._render_value(json_body, auth_vars=None)
            kwargs["auth"] = httpx.BasicAuth(
                self.auth.username or "",
                CryptoUtil.decrypt_or_keep(self.auth.password_encrypted),
            )
        http_method = str(self.auth.http_method or "GET").upper()
        return http_method, url, kwargs

    def _custom_request_shape(
        self,
    ) -> tuple[dict[str, Any] | None, dict[str, Any] | None, str, dict[str, Any] | None]:
        headers = self.auth.headers if isinstance(self.auth.headers, dict) else None
        query = self.auth.query if isinstance(self.auth.query, dict) else None
        body_type = self.auth.body_type
        body = self.auth.body if isinstance(self.auth.body, dict) else None
        empty = not headers and not query and body_type is None and body is None
        if empty:
            lifted_headers, lifted_query, lifted_type, lifted_body, _ = lift_custom_request_from_rule(
                self.auth.rule or {}
            )
            return lifted_headers, lifted_query, lifted_type, lifted_body
        return headers, query, body_type or "none", body

    async def _send_business(
        self,
        method: str,
        url: str,
        headers: Mapping[str, Any] | None,
        params: Mapping[str, Any] | None,
        json_body: Mapping[str, Any] | None,
        form: Mapping[str, Any] | None,
        auth_vars: Mapping[str, str],
        timeout: float | None = None,
    ) -> httpx.Response:
        # URL、配置 header、auth 槽位是模板。CallerLiteral 在渲染之后并入，原文上送。
        target = resolve_url(self.system.base_url, self._render_text(url, auth_vars=auth_vars))
        kwargs: dict[str, Any] = {}
        if headers is not None:
            kwargs["headers"] = self._render_then_literals(headers, auth_vars=auth_vars, stringify=True)
        if params is not None:
            kwargs["params"] = self._render_then_literals(params, auth_vars=auth_vars, stringify=True)
        if form is not None:
            kwargs["data"] = self._render_then_literals(form, auth_vars=auth_vars, stringify=True)
        elif json_body is not None:
            kwargs["json"] = self._render_then_literals(json_body, auth_vars=auth_vars, stringify=False)
        if timeout is not None:
            kwargs["timeout"] = timeout
        return await self._request(method, target, **kwargs)

    async def _request(self, method: str, url: str, **kwargs: Any) -> httpx.Response:
        response = await self._http.request(method, url, **kwargs)
        await response.aread()
        # 长生命周期客户端会记住 Set-Cookie。清掉后，登录和业务请求仍然各发各的。
        self._http.cookies.clear()
        return response

    def _section(self, name: str) -> Mapping[str, Any] | None:
        raw = (self.auth.rule or {}).get(name)
        if isinstance(raw, Mapping):
            return raw
        return None

    def _binding(self) -> BizBindingModel:
        if self.binding is None:
            raise BindingUnavailable("没有可用的业务绑定")
        return self.binding

    def _render_then_literals(
        self,
        value: Mapping[str, Any],
        *,
        auth_vars: Mapping[str, str] | None,
        stringify: bool,
    ) -> dict[str, Any]:
        templates: dict[str, Any] = {}
        literals: dict[str, Any] = {}
        for key, item in value.items():
            name = str(key)
            if isinstance(item, CallerLiteral):
                literals[name] = item.value
            else:
                templates[name] = item
        if stringify:
            rendered: dict[str, Any] = self._render_mapping(templates, auth_vars=auth_vars)
        else:
            rendered_value = self._render_value(templates, auth_vars=auth_vars)
            rendered = rendered_value if isinstance(rendered_value, dict) else {}
        for name, item in literals.items():
            if name in rendered:
                continue
            rendered[name] = _as_text(item) if stringify else item
        return rendered

    def _render_mapping(self, value: Mapping[str, Any], *, auth_vars: Mapping[str, str] | None) -> dict[str, str]:
        rendered = self._render_value(dict(value), auth_vars=auth_vars)
        return {str(key): _as_text(item) for key, item in rendered.items()}

    def _render_value(self, value: Any, *, auth_vars: Mapping[str, str] | None) -> Any:
        if isinstance(value, CallerLiteral):
            return value.value
        if isinstance(value, str):
            return self._render_text(value, auth_vars=auth_vars)
        if isinstance(value, Mapping):
            return {str(key): self._render_value(item, auth_vars=auth_vars) for key, item in value.items()}
        if isinstance(value, list):
            return [self._render_value(item, auth_vars=auth_vars) for item in value]
        return value

    def _render_text(self, value: str, *, auth_vars: Mapping[str, str] | None) -> str:
        return _PLACEHOLDER.sub(lambda match: self._replace(match, auth_vars), value)

    def _replace(self, match: re.Match[str], auth_vars: Mapping[str, str] | None) -> str:
        system_key = match.group("system")
        if system_key is not None:
            params = self.system.params or {}
            if system_key not in params:
                return match.group(0)
            return _as_text(params[system_key])
        attr_key = match.group("attr")
        if attr_key is not None:
            allowed = {str(name) for name in (self.system.attr_fields or [])}
            attrs = self.binding.attrs if self.binding is not None else {}
            if attr_key not in allowed or attr_key not in (attrs or {}):
                return match.group(0)
            return _as_text(attrs[attr_key])
        if match.group(0) == "{{user.uid}}":
            if self.binding is None:
                return match.group(0)
            return str(self.binding.uid_value)
        auth_key = match.group("auth")
        if auth_key is not None:
            if auth_vars is None or auth_key not in auth_vars:
                return match.group(0)
            return _as_text(auth_vars[auth_key])
        return match.group(0)


def _as_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value)
