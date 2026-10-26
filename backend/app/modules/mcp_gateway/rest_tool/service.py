"""保存 REST 工具，并按同一套请求组装调试未保存的表单。

调试不插入工具，也不写调用日志。上游 HTTP 走 AuthClient.call。
"""

import copy
import json
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any
from urllib.parse import parse_qsl, quote, unquote, urlencode, urlsplit, urlunsplit

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.base_schema import AuthSchema, PageResultSchema
from app.core.exceptions import CustomException
from app.modules.mcp_gateway.auth.client import AuthClient, InteractiveAuthRequired
from app.modules.mcp_gateway.auth.crud import AuthConfigCRUD
from app.modules.mcp_gateway.auth.model import AuthConfigModel
from app.modules.mcp_gateway.binding.crud import BizBindingCRUD
from app.modules.mcp_gateway.binding.model import BizBindingModel
from app.modules.mcp_gateway.system.crud import BizSystemCRUD
from app.modules.mcp_gateway.system.model import BizSystemModel
from app.modules.mcp_gateway.token_cache.store import TokenCache
from app.utils.common_util import search_to_dict

from .assemble import MissingUrlParameter, prepare_call
from .crud import RestToolCRUD
from .filter import apply_jsonpath
from .model import RestToolModel
from .schema import (
    RestToolCreateSchema,
    RestToolDebugResultSchema,
    RestToolOutSchema,
    RestToolQueryParam,
    RestToolUpdateSchema,
    UpstreamResult,
)

_TOOL_FIELDS = (
    "name",
    "display_name",
    "url",
    "description",
    "request_type",
    "headers",
    "input_schema",
    "output_schema",
    "jsonpath_filter",
    "query_mapping",
    "header_mapping",
    "timeout_ms",
    "token_in",
    "token_name",
    "token_var",
    "enabled",
    "system_id",
)
_MASK = "******"


@dataclass(frozen=True, slots=True)
class _Call:
    status: int
    text: str
    request: httpx.Request
    secrets: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class _PreparedInvoke:
    """数据库已经读完。后面的 HTTP 只用这些副本。"""

    tool: dict[str, Any]
    system: BizSystemModel
    binding: BizBindingModel | None
    auth_config: AuthConfigModel
    cache: TokenCache


class RestToolService:
    """REST 工具的保存、调试和正式调用。"""

    def __init__(
        self,
        auth: AuthSchema | None = None,
        db: AsyncSession | None = None,
        redis: Any | None = None,
        *,
        system: BizSystemModel | None = None,
        binding: BizBindingModel | None = None,
        auth_config: AuthConfigModel | None = None,
        cache: TokenCache | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
        logs: list[Any] | None = None,
        saved: list[Any] | None = None,
    ) -> None:
        self.auth = auth
        self.db = db
        self.redis = redis
        self.system = system
        self.binding = binding
        self.auth_config = auth_config
        self.cache = cache
        self.transport = transport
        self._direct = system is not None
        self._track_saved = saved is not None
        self.logs = logs if logs is not None else []
        self.saved = saved if saved is not None else []

    async def page(
        self,
        page_no: int,
        page_size: int,
        search: RestToolQueryParam | None = None,
        order_by: list[dict[str, str]] | None = None,
    ) -> PageResultSchema[RestToolOutSchema]:
        offset = (page_no - 1) * page_size
        return await self._crud().page(
            offset=offset,
            limit=page_size,
            order_by=order_by or [{"id": "asc"}],
            search=search_to_dict(search, {}),
            out_schema=RestToolOutSchema,
        )

    async def detail(self, tool_id: int) -> RestToolOutSchema:
        return await self._crud().get_or_404(id=tool_id, msg="REST 工具不存在", out_schema=RestToolOutSchema)

    async def create(self, data: RestToolCreateSchema) -> RestToolOutSchema:
        if self._track_saved:
            self.saved.append(data.model_dump())
        await self._require_system(data.system_id)
        obj = await self._crud().create(data=data)
        return RestToolOutSchema.model_validate(obj)

    async def update(self, tool_id: int, data: RestToolUpdateSchema) -> RestToolOutSchema:
        current = await self._crud().get(id=tool_id)
        if current is None:
            raise CustomException(msg="REST 工具不存在")
        submitted = data.model_dump(exclude_unset=True)
        if "system_id" in submitted and submitted["system_id"] != current.system_id:
            await self._require_system(submitted["system_id"])
        obj = await self._crud().update(id=tool_id, data=data)
        return RestToolOutSchema.model_validate(obj)

    async def debug(
        self,
        draft: Mapping[str, Any] | RestToolCreateSchema | RestToolModel,
        user_id: int,
        arguments: Mapping[str, Any] | None = None,
        reveal: bool = False,
    ) -> RestToolDebugResultSchema:
        """按未保存的表单发一次业务请求。不插入工具，不写调用日志。

        reveal=true 时 HTTP 响应可含明文；操作日志仍应遮住密钥（见 OperationLogRoute）。
        """
        data = _tool_dict(draft)
        try:
            called = await self._execute(data, user_id, arguments or {})
        except InteractiveAuthRequired as exc:
            return RestToolDebugResultSchema(link=exc.link)
        body = apply_jsonpath(_decode_body(called.text), _optional_text(data.get("jsonpath_filter")))
        request_view = _request_view(called.request)
        if not reveal:
            for secret in called.secrets:
                request_view = mask_secret(request_view, secret)
                body = mask_secret(body, secret)
        return RestToolDebugResultSchema(status=called.status, request=request_view, response=body)

    async def invoke(self, tool_id: int, user_id: int, arguments: Mapping[str, Any] | None = None) -> UpstreamResult:
        """正式调用已保存的工具。请求组装与调试相同。这里不写调用日志。

        工具、系统和鉴权先读完并复制出来。出站 HTTP 不再占用这次数据库事务。
        """
        prepared = await self._prepare_invoke(tool_id, user_id)
        direct = RestToolService(
            system=prepared.system,
            binding=prepared.binding,
            auth_config=prepared.auth_config,
            cache=prepared.cache,
            transport=self.transport,
        )
        try:
            called = await direct._execute(prepared.tool, user_id, arguments or {})
        except InteractiveAuthRequired as exc:
            return UpstreamResult(link=exc.link)
        body = apply_jsonpath(_decode_body(called.text), prepared.tool.get("jsonpath_filter"))
        return UpstreamResult(status=called.status, body=body)

    async def _prepare_invoke(self, tool_id: int, user_id: int) -> _PreparedInvoke:
        if self.db is not None:
            return await self._load_invoke(tool_id, user_id)
        from app.core.database import async_db_session

        async with async_db_session() as session, session.begin():
            loader = RestToolService(self.auth, session, self.redis, transport=self.transport)
            return await loader._load_invoke(tool_id, user_id)

    async def _load_invoke(self, tool_id: int, user_id: int) -> _PreparedInvoke:
        tool = await self._crud().get(id=tool_id)
        if tool is None or not tool.enabled:
            raise CustomException(msg="REST 工具不存在或已停用")
        data = _tool_dict(tool)
        system, binding, auth_config, cache = await self._context(data, user_id)
        return _PreparedInvoke(
            tool=data,
            system=_snapshot(system),
            binding=_snapshot(binding) if binding is not None else None,
            auth_config=_snapshot(auth_config),
            cache=cache,
        )

    async def _execute(self, tool: Mapping[str, Any] | RestToolModel, user_id: int, arguments: Mapping[str, Any]) -> _Call:
        data = _tool_dict(tool)
        system, binding, auth_config, cache = await self._context(data, user_id)
        if not system.enabled:
            raise CustomException(msg="业务系统已停用")
        try:
            prepared = prepare_call(system.base_url, data, arguments)
        except MissingUrlParameter as exc:
            raise CustomException(msg=f"缺少 URL 参数 {exc.name}") from exc
        transport, owns_transport = self._open_transport()
        client = AuthClient(cache=cache, system=system, binding=binding, auth=auth_config, transport=transport)
        try:
            response = await client.call(
                user_id,
                system.id,
                method=prepared.method,
                url=prepared.url,
                headers=prepared.headers,
                params=prepared.params,
                json_body=prepared.json_body,
                timeout=prepared.timeout,
            )
            upstream_status = response.status_code
            text = response.text
            upstream_request = response.request
        finally:
            await client.aclose()
            if owns_transport:
                await transport.aclose()
        bundle = await cache.get(user_id, system.id)
        secrets: list[str] = []
        # 始终遮住缓存里的鉴权变量值。
        if bundle is not None:
            for value in bundle.vars.values():
                if value:
                    secrets.append(value)
        bearer = _bearer(upstream_request)
        if bearer and bearer not in secrets:
            secrets.append(bearer)
        return _Call(status=upstream_status, text=text, request=upstream_request, secrets=tuple(secrets))

    async def _context(
        self,
        data: Mapping[str, Any],
        user_id: int,
    ) -> tuple[BizSystemModel, BizBindingModel | None, AuthConfigModel, TokenCache]:
        if self._direct:
            if self.system is None or self.auth_config is None or self.cache is None:
                raise CustomException(msg="调试运行时不完整")
            return self.system, self.binding, self.auth_config, self.cache
        if self.auth is None or self.db is None or self.redis is None:
            raise CustomException(msg="调试运行时不完整")
        system_id = int(data["system_id"])
        system = await BizSystemCRUD(self.auth, self.db).get(id=system_id)
        if system is None:
            raise CustomException(msg="业务系统不存在")
        binding = await BizBindingCRUD(self.auth, self.db).get(user_id=user_id, system_id=system_id)
        rows = await AuthConfigCRUD(self.auth, self.db).get_list(search={"system_id": system_id, "enabled": True})
        if not rows:
            raise CustomException(msg="业务系统没有启用的鉴权配置")
        return system, binding, rows[0], TokenCache(self.redis)

    def _open_transport(self) -> tuple[httpx.AsyncBaseTransport, bool]:
        if self.transport is not None:
            return self.transport, False
        return httpx.AsyncHTTPTransport(), True

    async def _require_system(self, system_id: int) -> None:
        if self.auth is None or self.db is None:
            raise CustomException(msg="无法保存 REST 工具")
        system = await BizSystemCRUD(self.auth, self.db).get(id=system_id)
        if system is None:
            raise CustomException(msg="业务系统不存在")

    def _crud(self) -> RestToolCRUD:
        if self.auth is None or self.db is None:
            raise CustomException(msg="无法保存 REST 工具")
        return RestToolCRUD(self.auth, self.db)


def mask_secret(value: Any, secret: str) -> Any:
    if not secret:
        return value
    if isinstance(value, str):
        return _mask_text(value, secret)
    if isinstance(value, dict):
        return {str(key): mask_secret(item, secret) for key, item in value.items()}
    if isinstance(value, list):
        return [mask_secret(item, secret) for item in value]
    return value


def _mask_text(text: str, secret: str) -> str:
    encoded = quote(secret, safe="")
    masked = _mask_url(text, secret, encoded)
    masked = masked.replace(secret, _MASK)
    if encoded != secret:
        masked = masked.replace(encoded, _MASK)
    return masked


def _mask_url(text: str, secret: str, encoded: str) -> str:
    parts = urlsplit(text)
    if not parts.scheme or not parts.netloc:
        return text
    path = _mask_decoded(parts.path, secret, encoded, unquote)
    query = _mask_query(parts.query, secret, encoded)
    if path == parts.path and query == parts.query:
        return text
    return urlunsplit((parts.scheme, parts.netloc, path, query, parts.fragment))


def _mask_decoded(text: str, secret: str, encoded: str, decode) -> str:
    updated = text.replace(encoded, _MASK) if encoded and encoded != secret else text
    decoded = decode(updated)
    if secret not in decoded:
        return updated
    return quote(decoded.replace(secret, _MASK), safe="/*")


def _mask_query(query: str, secret: str, encoded: str) -> str:
    if not query:
        return query
    updated = query.replace(encoded, _MASK) if encoded and encoded != secret else query
    pairs = parse_qsl(updated, keep_blank_values=True)
    if not any(secret in key or secret in value for key, value in pairs):
        return updated
    masked_pairs = [(key.replace(secret, _MASK), value.replace(secret, _MASK)) for key, value in pairs]
    return urlencode(masked_pairs, quote_via=_quote_masked)


def _quote_masked(value: str, safe: str = "", encoding: str | None = None, errors: str | None = None) -> str:
    return quote(value, safe=f"{safe}*", encoding=encoding, errors=errors)


def _snapshot(row: Any) -> Any:
    """复制成不挂在会话上的实例。提交或关闭会话后，出站请求仍能读这些字段。"""
    values: dict[str, Any] = {}
    for column in row.__table__.columns:
        value = getattr(row, column.key)
        if isinstance(value, dict | list):
            value = copy.deepcopy(value)
        values[column.key] = value
    return type(row)(**values)


def _tool_dict(tool: Mapping[str, Any] | RestToolCreateSchema | RestToolModel) -> dict[str, Any]:
    if isinstance(tool, Mapping):
        return dict(tool)
    if isinstance(tool, RestToolCreateSchema):
        return tool.model_dump()
    return {name: getattr(tool, name) for name in _TOOL_FIELDS}


def _request_view(request: httpx.Request) -> dict[str, Any]:
    body: Any = None
    if request.content:
        body = _decode_body(request.content.decode("utf-8", errors="replace"))
    return {
        "method": request.method,
        "url": str(request.url),
        "headers": {str(key): str(value) for key, value in request.headers.items()},
        "body": body,
    }


def _decode_body(text: str) -> Any:
    if text == "":
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return text


def _bearer(request: httpx.Request) -> str:
    header = request.headers.get("authorization", "")
    prefix = "bearer "
    if header.lower().startswith(prefix):
        return header[len(prefix) :].strip()
    return ""


def _optional_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None
