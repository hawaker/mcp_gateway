"""把 MCP 组暴露成 Streamable HTTP 和 SSE。不写调用日志，也不签发 token。"""

import json
import secrets
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

import httpx
from fastapi import FastAPI
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.routing import Route

from app.core.base_schema import AuthSchema
from app.modules.mcp_gateway.auth.client import BindingUnavailable
from app.modules.mcp_gateway.mcp_group.service import McpGroupService
from app.modules.mcp_gateway.rest_tool.service import RestToolService
from app.modules.mcp_gateway.system.crud import BizSystemCRUD
from app.modules.mcp_gateway.upstream.client import UpstreamClient
from app.modules.mcp_gateway.upstream.crud import UpstreamMcpCRUD, UpstreamToolCRUD

from .auth import CredentialRejected, allowed, verify_bearer
from .session import read_session, write_session

_PROTOCOL = "2025-03-26"
_DENIED = "无权限"


def build_mcp_app(
    group_id: int,
    *,
    db: Any | None = None,
    redis: Any | None = None,
    transport: httpx.AsyncBaseTransport | None = None,
) -> Starlette:
    """测试用的独立应用。路由只服务这一个组。"""
    runtime = McpRuntime(db=db, redis=redis, transport=transport, bound_group_id=group_id)
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
        transport: httpx.AsyncBaseTransport | None = None,
        bound_group_id: int | None = None,
    ) -> None:
        self.db = db
        self.redis = redis
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
                await self._authenticate(db, request, group_id)
        except CredentialRejected as exc:
            return _unauthorized(exc)
        session_id = secrets.token_urlsafe(24)
        await write_session(self._redis(request), session_id, group_id)
        endpoint = f"/mcp/{group_id}/messages?session_id={session_id}"
        return _event_stream(f"event: endpoint\ndata: {endpoint}\n\n")

    async def messages(self, request: Request) -> Response:
        group_id = self._group_id(request)
        session_id = request.query_params.get("session_id") or request.query_params.get("sessionId") or ""
        found = await read_session(self._redis(request), session_id) if session_id else None
        if found is None or found != group_id:
            return _json({"error": "会话不存在"}, 404)
        return await self._jsonrpc(request)

    async def _jsonrpc(self, request: Request) -> Response:
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
        async with self._db() as db:
            try:
                user_id = await self._authenticate(db, request, group_id)
                if isinstance(method, str) and method.startswith("notifications/"):
                    return _empty(202)
                payload = await self._dispatch(db, request, user_id, group_id, method, rpc_id, params)
            except CredentialRejected as exc:
                return _unauthorized(exc)
            except BindingUnavailable:
                payload = _denied(rpc_id)
        return _json(payload, 200)

    async def _dispatch(
        self,
        db: Any,
        request: Request,
        user_id: int,
        group_id: int,
        method: Any,
        rpc_id: Any,
        params: dict[str, Any],
    ) -> dict[str, Any]:
        if method == "initialize":
            return {
                "jsonrpc": "2.0",
                "id": rpc_id,
                "result": {
                    "protocolVersion": _PROTOCOL,
                    "capabilities": {"tools": {"listChanged": False}},
                    "serverInfo": {"name": "mcp-gateway", "version": "1.0.0"},
                },
            }
        if method == "tools/list":
            if not await allowed(db, user_id, group_id):
                return _denied(rpc_id)
            catalog = await McpGroupService(AuthSchema(), db).tools_for(group_id)
            return {
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
        if method == "tools/call":
            if not await allowed(db, user_id, group_id):
                return _denied(rpc_id)
            name = str(params.get("name") or "")
            arguments = params.get("arguments")
            if not isinstance(arguments, dict):
                arguments = {}
            text = await self._call(db, request, user_id, group_id, name, arguments)
            return _text_result(rpc_id, text, is_error=text == _DENIED)
        return {"jsonrpc": "2.0", "id": rpc_id, "error": {"code": -32601, "message": "Method not found"}}

    async def _call(
        self,
        db: Any,
        request: Request,
        user_id: int,
        group_id: int,
        name: str,
        arguments: dict[str, Any],
    ) -> str:
        catalog = await McpGroupService(AuthSchema(), db).tools_for(group_id)
        match = next((item for item in catalog if item.name == name), None)
        if match is None:
            return _DENIED
        if match.source == "rest":
            return await self._call_rest(db, request, match.source_id, user_id, arguments)
        if match.source == "upstream":
            return await self._call_upstream(db, match.source_id, arguments)
        return _DENIED

    async def _call_rest(
        self,
        db: Any,
        request: Request,
        tool_id: int,
        user_id: int,
        arguments: dict[str, Any],
    ) -> str:
        service = RestToolService(AuthSchema(), db, self._redis(request), transport=self.transport)
        try:
            result = await service.invoke(tool_id, user_id, arguments)
        except BindingUnavailable:
            return _DENIED
        if result.link:
            return result.link
        return _render_body(result.body)

    async def _call_upstream(self, db: Any, source_id: int, arguments: dict[str, Any]) -> str:
        auth = AuthSchema()
        tool = await UpstreamToolCRUD(auth, db).get(id=source_id)
        if tool is None or not tool.selected:
            return _DENIED
        upstream = await UpstreamMcpCRUD(auth, db).get(id=tool.upstream_id)
        if upstream is None:
            return _DENIED
        system = await BizSystemCRUD(auth, db).get(id=upstream.system_id)
        if system is None:
            return _DENIED
        rows = await UpstreamToolCRUD(auth, db).get_list(search={"upstream_id": upstream.id})
        client = UpstreamClient(
            upstream=upstream,
            system_code=system.code,
            tools=list(rows),
            transport=self.transport,
        )
        result = await client.call(upstream.id, tool.external_name, dict(arguments))
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


def _event_stream(body: str) -> Response:
    return Response(body, media_type="text/event-stream")
