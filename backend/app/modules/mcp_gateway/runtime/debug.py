"""管理员调试 MCP 组或上游。组走 build_mcp_app，上游用保存的凭证。"""

from __future__ import annotations

import asyncio
import json
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any
from urllib.parse import quote

import httpx
from pydantic import BaseModel, Field, model_validator
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.base_schema import AuthSchema
from app.core.exceptions import CustomException
from app.modules.mcp_gateway.mcp_group.service import McpCredentialService
from app.modules.mcp_gateway.token_cache.store import TokenCache
from app.modules.mcp_gateway.upstream.client import require_http_url
from app.modules.mcp_gateway.upstream.crud import UpstreamMcpCRUD
from app.modules.mcp_gateway.upstream.model import UpstreamMcpModel
from app.utils.crypto_util import CryptoUtil

from .app import build_mcp_app

_MASK = "***"
_PROTOCOL = "2025-03-26"
_TRANSPORTS = frozenset({"streamable_http", "sse"})


class DebugTargetSchema(BaseModel):
    """连接目标。组要带用户和传输；上游只带 upstream_id。"""

    target: str = Field(description="group、upstream 或 custom")
    group_id: int | None = Field(default=None, description="MCP 组 ID")
    user_id: int | None = Field(default=None, description="业务用户 ID")
    transport: str | None = Field(default=None, description="streamable_http 或 sse")
    upstream_id: int | None = Field(default=None, description="上游 MCP ID")
    url: str | None = Field(default=None, description="自定义 MCP URL")
    headers: dict[str, str] = Field(default_factory=dict, description="自定义请求头")
    reveal: bool = Field(default=False, description="为真时不遮住 token")

    @model_validator(mode="after")
    def _check(self) -> DebugTargetSchema:
        if self.target == "group":
            if self.group_id is None or self.user_id is None:
                raise ValueError("调试 MCP 组需要 group_id 和 user_id")
            if self.transport not in _TRANSPORTS:
                raise ValueError("传输只能是 streamable_http 或 sse")
            return self
        if self.target == "upstream":
            if self.upstream_id is None:
                raise ValueError("调试上游需要 upstream_id")
            return self
        if self.target == "custom":
            if not self.url:
                raise ValueError("调试自定义目标需要 url")
            try:
                require_http_url(self.url)
            except CustomException as exc:
                raise ValueError(exc.msg) from exc
            if self.transport not in _TRANSPORTS:
                raise ValueError("传输只能是 streamable_http 或 sse")
            return self
        raise ValueError("target 只能是 group、upstream 或 custom")


_SECRET_HEADER_MARKERS = ("token", "secret", "key", "password")


def _custom_header_secrets(headers: Mapping[str, str]) -> tuple[str, ...]:
    secrets: list[str] = []
    for name, value in headers.items():
        if not value:
            continue
        lowered = name.lower()
        if lowered == "authorization" or any(marker in lowered for marker in _SECRET_HEADER_MARKERS):
            secrets.append(value)
    return tuple(dict.fromkeys(secrets))


def _merge_custom_headers(
    user: Mapping[str, str],
    *,
    for_sse_get: bool = False,
) -> dict[str, str]:
    merged = {str(k): str(v) for k, v in user.items() if k}
    if for_sse_get:
        merged.setdefault("Accept", "text/event-stream")
    else:
        merged.setdefault("Content-Type", "application/json")
        merged.setdefault("Accept", "application/json, text/event-stream")
    return merged


class DebugCallSchema(DebugTargetSchema):
    name: str = Field(description="工具名称")
    arguments: dict[str, Any] = Field(default_factory=dict, description="工具参数")


class ProtocolViewSchema(BaseModel):
    request: str
    response: str


class NetworkViewSchema(BaseModel):
    status: int
    request_headers: str
    response_body: str


class DebugSessionResultSchema(BaseModel):
    server_info: dict[str, Any]
    protocol: ProtocolViewSchema
    network: NetworkViewSchema


class DebugToolsListResultSchema(BaseModel):
    tools: list[dict[str, Any]]
    protocol: ProtocolViewSchema
    network: NetworkViewSchema


class DebugToolsCallResultSchema(BaseModel):
    result_text: str
    protocol: ProtocolViewSchema
    network: NetworkViewSchema


@dataclass(frozen=True, slots=True)
class _Exchange:
    status: int
    request_headers: dict[str, str]
    request_body: dict[str, Any]
    response_body: Any
    secrets: tuple[str, ...]


class DebugService:
    """以管理员身份代发 initialize / tools/list / tools/call。"""

    def __init__(
        self,
        auth: AuthSchema,
        db: AsyncSession,
        redis: Any,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.auth = auth
        self.db = db
        self.redis = redis
        self.transport = transport

    async def session(
        self,
        *,
        target: str,
        group_id: int | None = None,
        user_id: int | None = None,
        transport: str | None = None,
        upstream_id: int | None = None,
        url: str | None = None,
        headers: Mapping[str, str] | None = None,
        reveal: bool = False,
    ) -> DebugSessionResultSchema:
        data = DebugTargetSchema(
            target=target,
            group_id=group_id,
            user_id=user_id,
            transport=transport,
            upstream_id=upstream_id,
            url=url,
            headers=dict(headers or {}),
            reveal=reveal,
        )
        exchange = await self._rpc(
            data,
            "initialize",
            {
                "protocolVersion": _PROTOCOL,
                "capabilities": {},
                "clientInfo": {"name": "mcp-gateway-debug", "version": "1.0.0"},
            },
        )
        result = _as_dict(exchange.response_body).get("result")
        server_info = _as_dict(result).get("serverInfo") if isinstance(result, dict) else None
        if not isinstance(server_info, dict):
            server_info = {}
        protocol, network = _views(exchange, reveal=data.reveal)
        return DebugSessionResultSchema(server_info=server_info, protocol=protocol, network=network)

    async def tools_list(
        self,
        *,
        target: str,
        group_id: int | None = None,
        user_id: int | None = None,
        transport: str | None = None,
        upstream_id: int | None = None,
        url: str | None = None,
        headers: Mapping[str, str] | None = None,
        reveal: bool = False,
    ) -> DebugToolsListResultSchema:
        data = DebugTargetSchema(
            target=target,
            group_id=group_id,
            user_id=user_id,
            transport=transport,
            upstream_id=upstream_id,
            url=url,
            headers=dict(headers or {}),
            reveal=reveal,
        )
        exchange = await self._rpc(data, "tools/list", {})
        result = _as_dict(exchange.response_body).get("result")
        tools = result.get("tools") if isinstance(result, dict) else None
        if not isinstance(tools, list):
            tools = []
        protocol, network = _views(exchange, reveal=data.reveal)
        return DebugToolsListResultSchema(tools=tools, protocol=protocol, network=network)

    async def tools_call(
        self,
        *,
        target: str,
        name: str,
        arguments: Mapping[str, Any] | None = None,
        group_id: int | None = None,
        user_id: int | None = None,
        transport: str | None = None,
        upstream_id: int | None = None,
        url: str | None = None,
        headers: Mapping[str, str] | None = None,
        reveal: bool = False,
    ) -> DebugToolsCallResultSchema:
        data = DebugCallSchema(
            target=target,
            group_id=group_id,
            user_id=user_id,
            transport=transport,
            upstream_id=upstream_id,
            url=url,
            headers=dict(headers or {}),
            reveal=reveal,
            name=name,
            arguments=dict(arguments or {}),
        )
        exchange = await self._rpc(data, "tools/call", {"name": data.name, "arguments": data.arguments})
        protocol, network = _views(exchange, reveal=data.reveal)
        return DebugToolsCallResultSchema(
            result_text=_result_text(exchange.response_body),
            protocol=protocol,
            network=network,
        )

    async def _rpc(self, data: DebugTargetSchema, method: str, params: dict[str, Any]) -> _Exchange:
        if data.target == "group":
            assert data.group_id is not None and data.user_id is not None and data.transport is not None
            return await self._group_rpc(data.group_id, data.user_id, data.transport, method, params)
        if data.target == "upstream":
            assert data.upstream_id is not None
            return await self._upstream_rpc(data.upstream_id, method, params)
        assert data.url is not None and data.transport is not None
        return await self._custom_rpc(data.url, data.headers, data.transport, method, params)

    async def _custom_rpc(
        self,
        url: str,
        headers: Mapping[str, str],
        transport: str,
        method: str,
        params: dict[str, Any],
    ) -> _Exchange:
        target_url = require_http_url(url)
        payload = {"jsonrpc": "2.0", "id": 1, "method": method, "params": params}
        if transport == "streamable_http":
            exchange = await self._custom_streamable(target_url, headers, payload)
        elif transport == "sse":
            exchange = await self._custom_sse(target_url, headers, payload)
        else:
            raise CustomException(msg="传输只能是 streamable_http 或 sse")
        secrets = _custom_header_secrets(headers)
        return _Exchange(
            status=exchange.status,
            request_headers=exchange.request_headers,
            request_body=exchange.request_body,
            response_body=exchange.response_body,
            secrets=secrets,
        )

    async def _custom_streamable(
        self,
        url: str,
        headers: Mapping[str, str],
        payload: dict[str, Any],
    ) -> _Exchange:
        sent = _merge_custom_headers(headers)
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        client = httpx.AsyncClient(transport=_borrow(self.transport), timeout=30.0)
        try:
            response = await client.post(url, content=body, headers=sent)
            return _Exchange(
                status=response.status_code,
                request_headers=dict(sent),
                request_body=payload,
                response_body=_decode_response(response),
                secrets=(),
            )
        finally:
            await client.aclose()

    async def _custom_sse(
        self,
        url: str,
        headers: Mapping[str, str],
        payload: dict[str, Any],
    ) -> _Exchange:
        raise CustomException(msg="自定义 SSE 尚未实现")  # Task 2 替换

    async def _group_rpc(
        self,
        group_id: int,
        user_id: int,
        transport: str,
        method: str,
        params: dict[str, Any],
    ) -> _Exchange:
        info = await McpCredentialService(self.auth, self.db).connection_info(
            user_id=user_id, group_id=group_id
        )
        token = info.authorization.removeprefix("Authorization: Bearer ")
        app = build_mcp_app(
            group_id,
            db=self.db,
            redis=self.redis,
            pubsub_redis=self.redis,
            transport=self.transport,
        )
        payload = {"jsonrpc": "2.0", "id": 1, "method": method, "params": params}
        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/json, text/event-stream",
            "Content-Type": "application/json",
        }
        if transport == "streamable_http":
            exchange = await self._streamable(app, group_id, headers, payload)
        elif transport == "sse":
            exchange = await self._sse(app, group_id, token, headers, payload)
        else:
            raise CustomException(msg="传输只能是 streamable_http 或 sse")
        secrets = await self._group_secrets(user_id, token)
        return _Exchange(
            status=exchange.status,
            request_headers=exchange.request_headers,
            request_body=exchange.request_body,
            response_body=exchange.response_body,
            secrets=secrets,
        )

    async def _streamable(
        self,
        app: Any,
        group_id: int,
        headers: dict[str, str],
        payload: dict[str, Any],
    ) -> _Exchange:
        asgi = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=asgi, base_url="http://mcp.debug") as client:
            response = await client.post(f"/mcp/{group_id}", headers=headers, json=payload)
        return _Exchange(
            status=response.status_code,
            request_headers=dict(headers),
            request_body=payload,
            response_body=_decode_response(response),
            secrets=(),
        )

    async def _sse(
        self,
        app: Any,
        group_id: int,
        token: str,
        headers: dict[str, str],
        payload: dict[str, Any],
    ) -> _Exchange:
        stream = _OpenSse(app, f"/mcp/{group_id}/sse", token)
        try:
            await stream.wait_started()
            if stream.status != 200:
                body = {"error": f"SSE 连接失败: {stream.status}"}
                return _Exchange(stream.status, dict(headers), payload, body, ())
            event, endpoint = await stream.next_event()
            if event != "endpoint" or not endpoint:
                raise CustomException(msg="SSE 未返回 endpoint")
            asgi = httpx.ASGITransport(app=app)
            async with httpx.AsyncClient(transport=asgi, base_url="http://mcp.debug") as client:
                posted = await client.post(endpoint, headers=headers, json=payload)
            if posted.status_code not in {200, 202}:
                return _Exchange(
                    posted.status_code,
                    dict(headers),
                    payload,
                    _decode_response(posted),
                    (),
                )
            message_event, message = await stream.next_event()
            if message_event != "message":
                raise CustomException(msg="SSE 未返回 message")
            try:
                body: Any = json.loads(message)
            except json.JSONDecodeError:
                body = message
            return _Exchange(posted.status_code, dict(headers), payload, body, ())
        finally:
            await stream.aclose()

    async def _upstream_rpc(self, upstream_id: int, method: str, params: dict[str, Any]) -> _Exchange:
        upstream = await UpstreamMcpCRUD(self.auth, self.db).get(id=upstream_id)
        if upstream is None:
            raise CustomException(msg="上游 MCP 不存在")
        credential = CryptoUtil.decrypt(upstream.credential_value_encrypted)
        payload = {"jsonrpc": "2.0", "id": 1, "method": method, "params": params}
        status, content, sent_headers = await _upstream_post(upstream, credential, payload, self.transport)
        return _Exchange(status, sent_headers, payload, _decode_bytes(content), (credential,))

    async def _group_secrets(self, user_id: int, mcp_token: str) -> tuple[str, ...]:
        secrets = [mcp_token]
        try:
            rows = await TokenCache(self.redis).list_entries(user_id=user_id)
        except Exception:
            rows = []
        for row in rows:
            if row.access_token:
                secrets.append(row.access_token)
        return tuple(dict.fromkeys(item for item in secrets if item))


async def _upstream_post(
    upstream: UpstreamMcpModel,
    credential: str,
    payload: dict[str, Any],
    transport: httpx.AsyncBaseTransport | None,
) -> tuple[int, bytes, dict[str, str]]:
    url = require_http_url(upstream.url)
    headers = {
        upstream.credential_header: credential,
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    client = httpx.AsyncClient(transport=_borrow(transport), timeout=30.0)
    try:
        response = await client.post(url, content=body, headers=headers)
        return response.status_code, response.content, headers
    finally:
        await client.aclose()


def _borrow(transport: httpx.AsyncBaseTransport | None) -> httpx.AsyncBaseTransport:
    if transport is None:
        return httpx.AsyncHTTPTransport()

    class _Borrowed(httpx.AsyncBaseTransport):
        async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
            return await transport.handle_async_request(request)

        async def aclose(self) -> None:
            return None

    return _Borrowed()


def _views(exchange: _Exchange, *, reveal: bool) -> tuple[ProtocolViewSchema, NetworkViewSchema]:
    protocol = ProtocolViewSchema(
        request=_pretty(exchange.request_body),
        response=_pretty(exchange.response_body),
    )
    network = NetworkViewSchema(
        status=exchange.status,
        request_headers=_pretty(exchange.request_headers),
        response_body=_pretty(exchange.response_body),
    )
    if reveal:
        return protocol, network
    secrets = [item for item in exchange.secrets if item]
    return (
        ProtocolViewSchema(
            request=_mask_text(protocol.request, secrets),
            response=_mask_text(protocol.response, secrets),
        ),
        NetworkViewSchema(
            status=network.status,
            request_headers=_mask_text(network.request_headers, secrets),
            response_body=_mask_text(network.response_body, secrets),
        ),
    )


def _mask_text(text: str, secrets: list[str]) -> str:
    masked = text
    for secret in sorted(secrets, key=len, reverse=True):
        if not secret:
            continue
        masked = masked.replace(secret, _MASK)
        encoded = quote(secret, safe="")
        if encoded and encoded != secret:
            masked = masked.replace(encoded, _MASK)
    return masked


def _pretty(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2, default=str)


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _result_text(body: Any) -> str:
    result = _as_dict(body).get("result")
    if not isinstance(result, dict):
        return _pretty(body)
    content = result.get("content")
    if isinstance(content, list) and content:
        first = content[0]
        if isinstance(first, dict) and "text" in first:
            return str(first.get("text") or "")
    return _pretty(result)


def _decode_response(response: httpx.Response) -> Any:
    try:
        return response.json()
    except json.JSONDecodeError:
        return response.text


def _decode_bytes(content: bytes) -> Any:
    if not content:
        return None
    text = content.decode("utf-8", errors="replace")
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return text


class _OpenSse:
    """按块读 SSE。ASGI 传输会攒齐整段 body，长连接不能用普通 httpx。"""

    def __init__(self, app: Any, path: str, token: str) -> None:
        self.app = app
        self.path = path
        self.token = token
        self.status = 0
        self._started = asyncio.Event()
        self._disconnect = asyncio.Event()
        self._saw_request = False
        self._chunks: asyncio.Queue[bytes | None] = asyncio.Queue()
        self._buffer = ""
        self._task = asyncio.create_task(self._run())

    async def wait_started(self) -> None:
        await asyncio.wait_for(self._started.wait(), timeout=5)
        if self._task.done():
            error = self._task.exception()
            if error is not None:
                raise error

    async def next_event(self) -> tuple[str, str]:
        while "\n\n" not in self._buffer:
            chunk = await asyncio.wait_for(self._chunks.get(), timeout=5)
            if chunk is None:
                raise CustomException(msg="SSE 流已关闭")
            self._buffer += chunk.decode()
        raw, self._buffer = self._buffer.split("\n\n", 1)
        event = "message"
        data: list[str] = []
        for line in raw.split("\n"):
            if line.startswith("event:"):
                event = line.split(":", 1)[1].strip()
            elif line.startswith("data:"):
                data.append(line.split(":", 1)[1].lstrip())
        return event, "\n".join(data)

    async def aclose(self) -> None:
        self._disconnect.set()
        self._task.cancel()
        try:
            await self._task
        except asyncio.CancelledError:
            pass
        except Exception:
            pass

    async def _run(self) -> None:
        scope = {
            "type": "http",
            "asgi": {"version": "3.0", "spec_version": "2.3"},
            "http_version": "1.1",
            "method": "GET",
            "scheme": "http",
            "path": self.path,
            "raw_path": self.path.encode(),
            "query_string": b"",
            "headers": [
                (b"authorization", f"Bearer {self.token}".encode()),
                (b"accept", b"text/event-stream"),
                (b"host", b"mcp.debug"),
            ],
            "client": ("127.0.0.1", 50000),
            "server": ("mcp.debug", 80),
            "root_path": "",
        }
        await self.app(scope, self._receive, self._send)

    async def _receive(self) -> dict[str, Any]:
        if not self._saw_request:
            self._saw_request = True
            return {"type": "http.request", "body": b"", "more_body": False}
        await self._disconnect.wait()
        return {"type": "http.disconnect"}

    async def _send(self, message: dict[str, Any]) -> None:
        if message["type"] == "http.response.start":
            self.status = int(message["status"])
            self._started.set()
            return
        if message["type"] != "http.response.body":
            return
        body = message.get("body", b"")
        if body:
            await self._chunks.put(body)
        if not message.get("more_body", False):
            await self._chunks.put(None)
