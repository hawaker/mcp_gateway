"""把已选用的上游工具转发成一次 JSON-RPC。

只带保存的那一份凭证。不读业务绑定，不读业务 token，也不在 401 时重新登录。
"""

import json
from typing import Any

import httpx

from app.core.exceptions import CustomException
from app.utils.crypto_util import CryptoUtil

from .model import UpstreamMcpModel, UpstreamToolModel
from .schema import ToolSnapshot, UpstreamResult


def external_name(code: str, remote_name: str) -> str:
    """外部名称就是系统编码、下划线、远端工具名，按原样拼接。"""
    return f"{code}_{remote_name}"


def require_http_url(url: str) -> str:
    text = (url or "").strip()
    lowered = text.lower()
    if not (lowered.startswith("http://") or lowered.startswith("https://")):
        raise CustomException(msg="上游地址必须以 http:// 或 https:// 开头")
    return text


class _BorrowedTransport(httpx.AsyncBaseTransport):
    """转发请求。关闭这一层时不关闭注入的 transport。"""

    def __init__(self, transport: httpx.AsyncBaseTransport) -> None:
        self._transport = transport

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        return await self._transport.handle_async_request(request)

    async def aclose(self) -> None:
        return None


class UpstreamClient:
    """对一个上游 MCP 发 tools/list 或 tools/call。"""

    def __init__(
        self,
        *,
        upstream: UpstreamMcpModel,
        system_code: str,
        tools: list[UpstreamToolModel],
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.upstream = upstream
        self.system_code = system_code
        self.tools = tools
        self.transport = transport

    async def list_tools(self, upstream_id: int) -> list[ToolSnapshot]:
        """POST 一次 tools/list，并按 remote_name 合并到本地工具。不删除远端已消失的行。"""
        self._require_upstream(upstream_id)
        status, content = await self._post({"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}})
        if status < 200 or status >= 300:
            raise CustomException(msg="拉取上游工具失败")
        return self._merge(upstream_id, _remote_tools(_decode(content)))

    async def call(self, upstream_id: int, name: str, arguments: dict[str, Any] | None = None) -> UpstreamResult:
        """未选用的工具直接拒绝。选用后 POST 一次 tools/call，params.name 用远端名。"""
        self._require_upstream(upstream_id)
        tool = self._find(upstream_id, name)
        if tool is None or not tool.selected:
            raise CustomException(msg="未选择的上游工具不能调用")
        status, content = await self._post(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/call",
                "params": {"name": tool.remote_name, "arguments": dict(arguments or {})},
            }
        )
        return UpstreamResult(status=status, body=_decode(content))

    def _require_upstream(self, upstream_id: int) -> None:
        if self.upstream.id != upstream_id:
            raise CustomException(msg="上游 MCP 不存在")

    def _find(self, upstream_id: int, name: str) -> UpstreamToolModel | None:
        for tool in self.tools:
            if tool.upstream_id == upstream_id and tool.external_name == name and not tool.is_deleted:
                return tool
        return None

    def _merge(self, upstream_id: int, remote_tools: list[dict[str, Any]]) -> list[ToolSnapshot]:
        by_name = {
            tool.remote_name: tool
            for tool in self.tools
            if tool.upstream_id == upstream_id and not tool.is_deleted
        }
        snapshots: list[ToolSnapshot] = []
        for item in remote_tools:
            remote = str(item["name"])
            schema = item.get("inputSchema")
            if not isinstance(schema, dict):
                schema = {}
            current = by_name.get(remote)
            if current is None:
                current = UpstreamToolModel(
                    upstream_id=upstream_id,
                    remote_name=remote,
                    external_name=external_name(self.system_code, remote),
                    input_schema=dict(schema),
                    selected=False,
                    is_deleted=False,
                )
                self.tools.append(current)
                by_name[remote] = current
            else:
                current.input_schema = dict(schema)
            snapshots.append(
                ToolSnapshot(
                    remote_name=current.remote_name,
                    external_name=current.external_name,
                    input_schema=dict(current.input_schema or {}),
                    selected=bool(current.selected),
                )
            )
        return snapshots

    async def _post(self, payload: dict[str, Any]) -> tuple[int, bytes]:
        url = require_http_url(self.upstream.url)
        headers = {
            self.upstream.credential_header: CryptoUtil.decrypt(self.upstream.credential_value_encrypted),
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        client = httpx.AsyncClient(transport=self._open_transport(), timeout=30.0)
        try:
            response = await client.post(url, content=body, headers=headers)
            return response.status_code, response.content
        finally:
            await client.aclose()

    def _open_transport(self) -> httpx.AsyncBaseTransport:
        if self.transport is not None:
            return _BorrowedTransport(self.transport)
        return httpx.AsyncHTTPTransport()


def _remote_tools(body: Any) -> list[dict[str, Any]]:
    if not isinstance(body, dict):
        raise CustomException(msg="上游工具列表不是 JSON-RPC 对象")
    result = body.get("result")
    tools = result.get("tools") if isinstance(result, dict) else None
    if not isinstance(tools, list):
        raise CustomException(msg="上游工具列表缺少 result.tools")
    parsed: list[dict[str, Any]] = []
    for item in tools:
        if not isinstance(item, dict) or not isinstance(item.get("name"), str) or not item["name"]:
            raise CustomException(msg="上游工具缺少名称")
        parsed.append(item)
    return parsed


def _decode(content: bytes) -> Any:
    if not content:
        return None
    text = content.decode("utf-8", errors="replace")
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return text
