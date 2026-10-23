"""把 MCP 组暴露成 Streamable HTTP 和 SSE。不写调用日志，也不签发 token。"""

import copy
import json
import secrets
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Any

import httpx
from fastapi import FastAPI
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse, Response, StreamingResponse
from starlette.routing import Route

from app.core.base_schema import AuthSchema
from app.modules.mcp_gateway.auth.client import BindingUnavailable
from app.modules.mcp_gateway.mcp_group.service import McpGroupService
from app.modules.mcp_gateway.rest_tool.crud import RestToolCRUD
from app.modules.mcp_gateway.rest_tool.service import RestToolService
from app.modules.mcp_gateway.system.crud import BizSystemCRUD
from app.modules.mcp_gateway.upstream.client import UpstreamClient
from app.modules.mcp_gateway.upstream.crud import UpstreamMcpCRUD, UpstreamToolCRUD

from .auth import CredentialRejected, allowed, verify_bearer
from .session import message_channel, publish_result, read_session, refresh_session, write_session

_PROTOCOL = "2025-03-26"
_DENIED = "无权限"
_SSE_HEADERS = {"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}


@dataclass(frozen=True, slots=True)
class _Ready:
    payload: dict[str, Any]


@dataclass(frozen=True, slots=True)
class _RestCall:
    tool_id: int
    user_id: int
    arguments: dict[str, Any]


@dataclass(frozen=True, slots=True)
class _UpstreamCall:
    upstream: Any
    system_code: str
    tools: list[Any]
    external_name: str
    arguments: dict[str, Any]


def build_mcp_app(
    group_id: int,
    *,
    db: Any | None = None,
    redis: Any | None = None,
    pubsub_redis: Any | None = None,
    transport: httpx.AsyncBaseTransport | None = None,
) -> Starlette:
    """测试用的独立应用。路由只服务这一个组。"""
    runtime = McpRuntime(
        db=db,
        redis=redis,
        pubsub_redis=pubsub_redis,
        transport=transport,
        bound_group_id=group_id,
    )
    return Starlette(
        routes=[
            Route(f"/mcp/{group_id}", runtime.streamable, methods=["GET", "POST"]),
            Route(f"/mcp/{group_id}/sse", runtime.sse, methods=["GET"]),
            Route(f"/mcp/{group_id}/messages", runtime.messages, methods=["POST"]),
        ],
    )


def mount_mcp_runtime(app: FastAPI) -> None:
    """挂到主应用根路径。凭证是 MCP token，不走管理员会话。"""
    runtime = McpRuntime()
    app.add_api_route("/mcp/{group_id}", runtime.streamable, methods=["GET", "POST"], include_in_schema=False)
    app.add_api_route("/mcp/{group_id}/sse", runtime.sse, methods=["GET"], include_in_schema=False)
    app.add_api_route("/mcp/{group_id}/messages", runtime.messages, methods=["POST"], include_in_schema=False)


class McpRuntime:
    """一次 JSON-RPC。权限不过时直接回无权限，不向业务系统或上游发请求。"""

    def __init__(
        self,
        *,
        db: Any | None = None,
        redis: Any | None = None,
        pubsub_redis: Any | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
        bound_group_id: int | None = None,
    ) -> None:
        self.db = db
        self.redis = redis
        self.pubsub_redis = pubsub_redis
        self.transport = transport
        self.bound_group_id = bound_group_id

    async def streamable(self, request: Request) -> Response:
        if request.method == "GET":
            group_id = self._group_id(request)
            try:
                async with self._db() as db:
                    await self._authenticate(db, request, group_id)
            except CredentialRejected as exc:
                return _unauthorized(exc)
            return _event_stream(": ok\n\n")
        return await self._jsonrpc(request)

    async def sse(self, request: Request) -> Response:
        group_id = self._group_id(request)
        try:
            async with self._db() as db:
                user_id = await self._authenticate(db, request, group_id)
                if not await allowed(db, user_id, group_id):
                    return _json({"error": _DENIED}, 200)
        except CredentialRejected as exc:
            return _unauthorized(exc)
        session_id = secrets.token_urlsafe(24)
        return StreamingResponse(
            self._sse_events(self._redis(request), self._pubsub_redis(request), session_id, group_id),
            media_type="text/event-stream",
            headers=_SSE_HEADERS,
        )

    async def _sse_events(self, redis: Any, pubsub_redis: Any, session_id: str, group_id: int) -> AsyncIterator[str]:
        await write_session(redis, session_id, group_id)
        pubsub = pubsub_redis.pubsub()
        try:
            await pubsub.subscribe(message_channel(session_id))
            endpoint = f"/mcp/{group_id}/messages?session_id={session_id}"
            yield f"event: endpoint\ndata: {endpoint}\n\n"
            while True:
                await refresh_session(redis, session_id)
                incoming = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
                if not incoming or incoming.get("type") != "message":
                    continue
                data = incoming.get("data")
                if isinstance(data, bytes):
                    data = data.decode()
                elif data is None:
                    continue
                else:
                    data = str(data)
                yield f"event: message\ndata: {data}\n\n"
        finally:
            await pubsub.aclose()

    async def messages(self, request: Request) -> Response:
        group_id = self._group_id(request)
        session_id = request.query_params.get("session_id") or request.query_params.get("sessionId") or ""
        redis = self._redis(request)
        found = await read_session(redis, session_id) if session_id else None
        if found is None or found != group_id:
            return _json({"error": "会话不存在"}, 404)
        outcome = await self._handle(request)
        if isinstance(outcome, Response):
            return outcome
        await publish_result(redis, session_id, outcome)
        return _empty(202)

    async def _jsonrpc(self, request: Request) -> Response:
        outcome = await self._handle(request)
        if isinstance(outcome, Response):
            return outcome
        return _json(outcome, 200)

    async def _handle(self, request: Request) -> Response | dict[str, Any]:
        group_id = self._group_id(request)
        try:
            message = await request.json()
        except (json.JSONDecodeError, UnicodeDecodeError):
            return _json({"error": "无效的 JSON"}, 400)
        if not isinstance(message, dict):
            return _json({"error": "无效的 JSON"}, 400)
        method = message.get("method")
        rpc_id = message.get("id")
        params = message.get("params")
        if not isinstance(params, dict):
            params = {}
        try:
            async with self._db() as db:
                user_id = await self._authenticate(db, request, group_id)
                if isinstance(method, str) and method.startswith("notifications/"):
                    return _empty(202)
                plan = await self._plan(db, user_id, group_id, method, rpc_id, params)
        except CredentialRejected as exc:
            return _unauthorized(exc)
        if isinstance(plan, _Ready):
            return plan.payload
        text = await self._perform(request, plan)
        return _text_result(rpc_id, text, is_error=text == _DENIED)

    async def _plan(
        self,
        db: Any,
        user_id: int,
        group_id: int,
        method: Any,
        rpc_id: Any,
        params: dict[str, Any],
    ) -> _Ready | _RestCall | _UpstreamCall:
        if method == "initialize":
            return _Ready(
                {
                    "jsonrpc": "2.0",
                    "id": rpc_id,
                    "result": {
                        "protocolVersion": _PROTOCOL,
                        "capabilities": {"tools": {"listChanged": False}},
                        "serverInfo": {"name": "mcp-gateway", "version": "1.0.0"},
                    },
                }
            )
        if method == "tools/list":
            if not await allowed(db, user_id, group_id):
                return _Ready(_denied(rpc_id))
            catalog = await McpGroupService(AuthSchema(), db).tools_for(group_id)
            return _Ready(
                {
                    "jsonrpc": "2.0",
                    "id": rpc_id,
                    "result": {
                        "tools": [
                            {
                                "name": item.name,
                                "description": item.description,
                                "inputSchema": item.input_schema,
                            }
                            for item in catalog
                        ]
                    },
                }
            )
        if method == "tools/call":
            if not await allowed(db, user_id, group_id):
                return _Ready(_denied(rpc_id))
            name = str(params.get("name") or "")
            arguments = params.get("arguments")
            if not isinstance(arguments, dict):
                arguments = {}
            return await self._plan_call(db, user_id, group_id, rpc_id, name, arguments)
        return _Ready({"jsonrpc": "2.0", "id": rpc_id, "error": {"code": -32601, "message": "Method not found"}})

    async def _plan_call(
        self,
        db: Any,
        user_id: int,
        group_id: int,
        rpc_id: Any,
        name: str,
        arguments: dict[str, Any],
    ) -> _Ready | _RestCall | _UpstreamCall:
        catalog = await McpGroupService(AuthSchema(), db).tools_for(group_id)
        match = next((item for item in catalog if item.name == name), None)
        if match is None:
            return _Ready(_text_result(rpc_id, _DENIED, is_error=True))
        if match.source == "rest":
            tool = await RestToolCRUD(AuthSchema(), db).get(id=match.source_id)
            if tool is None or not tool.enabled:
                return _Ready(_text_result(rpc_id, _DENIED, is_error=True))
            return _RestCall(tool_id=tool.id, user_id=user_id, arguments=arguments)
        if match.source == "upstream":
            loaded = await self._load_upstream(db, match.source_id, arguments)
            if loaded is None:
                return _Ready(_text_result(rpc_id, _DENIED, is_error=True))
            return loaded
        return _Ready(_text_result(rpc_id, _DENIED, is_error=True))

    async def _load_upstream(self, db: Any, source_id: int, arguments: dict[str, Any]) -> _UpstreamCall | None:
        auth = AuthSchema()
        tool = await UpstreamToolCRUD(auth, db).get(id=source_id)
        if tool is None or not tool.selected:
            return None
        upstream = await UpstreamMcpCRUD(auth, db).get(id=tool.upstream_id)
        if upstream is None:
            return None
        system = await BizSystemCRUD(auth, db).get(id=upstream.system_id)
        if system is None:
            return None
        rows = await UpstreamToolCRUD(auth, db).get_list(search={"upstream_id": upstream.id})
        return _UpstreamCall(
            upstream=_snapshot(upstream),
            system_code=system.code,
            tools=[_snapshot(row) for row in rows],
            external_name=tool.external_name,
            arguments=arguments,
        )

    async def _perform(self, request: Request, plan: _RestCall | _UpstreamCall) -> str:
        if isinstance(plan, _RestCall):
            service = RestToolService(AuthSchema(), self.db, self._redis(request), transport=self.transport)
            try:
                result = await service.invoke(plan.tool_id, plan.user_id, plan.arguments)
            except BindingUnavailable:
                return _DENIED
            if result.link:
                return result.link
            return _render_body(result.body)
        client = UpstreamClient(
            upstream=plan.upstream,
            system_code=plan.system_code,
            tools=list(plan.tools),
            transport=self.transport,
        )
        result = await client.call(plan.upstream.id, plan.external_name, dict(plan.arguments))
        return json.dumps({"status": result.status, "body": result.body}, ensure_ascii=False)

    async def _authenticate(self, db: Any, request: Request, group_id: int) -> int:
        user_id, token_group_id = await verify_bearer(db, request.headers.get("authorization"))
        if token_group_id != group_id:
            raise CredentialRejected()
        return user_id

    def _group_id(self, request: Request) -> int:
        if self.bound_group_id is not None:
            return self.bound_group_id
        return int(request.path_params["group_id"])

    def _redis(self, request: Request) -> Any:
        if self.redis is not None:
            return self.redis
        return request.app.state.redis

    def _pubsub_redis(self, request: Request) -> Any:
        """订阅用的客户端。和短命令不是同一个连接池。"""
        if self.pubsub_redis is not None:
            return self.pubsub_redis
        return request.app.state.redis_pubsub

    @asynccontextmanager
    async def _db(self) -> AsyncIterator[Any]:
        if self.db is not None:
            yield self.db
            return
        from app.core.database import async_db_session

        async with async_db_session() as session, session.begin():
            yield session


def _unauthorized(exc: CredentialRejected) -> JSONResponse:
    return _json({"error": exc.message or "凭证无效"}, 401)


def _json(content: dict[str, Any], status: int) -> JSONResponse:
    """第二参是 HTTP 状态，按位置传入。"""
    return JSONResponse(content, status)


def _empty(status: int) -> Response:
    return Response(None, status)


def _denied(rpc_id: Any) -> dict[str, Any]:
    return _text_result(rpc_id, _DENIED, is_error=True)


def _text_result(rpc_id: Any, text: str, *, is_error: bool) -> dict[str, Any]:
    result: dict[str, Any] = {"content": [{"type": "text", "text": text}]}
    if is_error:
        result["isError"] = True
    return {"jsonrpc": "2.0", "id": rpc_id, "result": result}


def _render_body(body: Any) -> str:
    if isinstance(body, str):
        return body
    return json.dumps(body, ensure_ascii=False)


def _snapshot(row: Any) -> Any:
    """事务结束前把行复制出来，出站 HTTP 不再碰这个会话。"""
    values: dict[str, Any] = {}
    for column in row.__table__.columns:
        value = getattr(row, column.key)
        if isinstance(value, dict | list):
            value = copy.deepcopy(value)
        values[column.key] = value
    return type(row)(**values)


def _event_stream(body: str) -> Response:
    return Response(body, media_type="text/event-stream")
