"""保存上游 MCP，并把 tools/list 的结果合并进本地工具表。"""

from typing import Any

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.base_schema import AuthSchema, PageResultSchema
from app.core.exceptions import CustomException
from app.modules.mcp_gateway.system.crud import BizSystemCRUD
from app.utils.common_util import search_to_dict
from app.utils.crypto_util import CryptoUtil

from .client import UpstreamClient
from .crud import UpstreamMcpCRUD, UpstreamToolCRUD
from .model import UpstreamToolModel
from .schema import (
    ToolSnapshot,
    UpstreamMcpCreateSchema,
    UpstreamMcpOutSchema,
    UpstreamMcpQueryParam,
    UpstreamMcpUpdateSchema,
    UpstreamResult,
    UpstreamToolOutSchema,
    UpstreamToolQueryParam,
    UpstreamToolUpdateSchema,
)


def upstream_create_payload(data: UpstreamMcpCreateSchema) -> dict[str, Any]:
    """明文凭证换成密文。返回值里不再保留 credential_value。"""
    return {
        "system_id": data.system_id,
        "url": data.url,
        "credential_header": data.credential_header,
        "credential_value_encrypted": CryptoUtil.encrypt(data.credential_value),
    }


def upstream_update_payload(data: UpstreamMcpUpdateSchema) -> dict[str, Any]:
    """只收集提交过的字段。没有新凭证时不写密文列。"""
    submitted = data.model_dump(exclude_unset=True)
    payload: dict[str, Any] = {}
    for key in ("system_id", "url", "credential_header"):
        if key in submitted and submitted[key] is not None:
            payload[key] = submitted[key]
    credential = submitted.get("credential_value")
    if credential:
        payload["credential_value_encrypted"] = CryptoUtil.encrypt(credential)
    return payload


class UpstreamService:
    """上游 MCP 与其工具的管理，以及一次不带业务 token 的调用。"""

    def __init__(
        self,
        auth: AuthSchema,
        db: AsyncSession,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.auth = auth
        self.db = db
        self.transport = transport

    async def page(
        self,
        page_no: int,
        page_size: int,
        search: UpstreamMcpQueryParam | None = None,
        order_by: list[dict[str, str]] | None = None,
    ) -> PageResultSchema[UpstreamMcpOutSchema]:
        offset = (page_no - 1) * page_size
        return await self._mcp_crud().page(
            offset=offset,
            limit=page_size,
            order_by=order_by or [{"id": "asc"}],
            search=search_to_dict(search, {}),
            out_schema=UpstreamMcpOutSchema,
        )

    async def detail(self, upstream_id: int) -> UpstreamMcpOutSchema:
        return await self._mcp_crud().get_or_404(id=upstream_id, msg="上游 MCP 不存在", out_schema=UpstreamMcpOutSchema)

    async def create(self, data: UpstreamMcpCreateSchema) -> UpstreamMcpOutSchema:
        await self._require_system(data.system_id)
        obj = await self._mcp_crud().create(data=upstream_create_payload(data))
        return UpstreamMcpOutSchema.model_validate(obj)

    async def update(self, upstream_id: int, data: UpstreamMcpUpdateSchema) -> UpstreamMcpOutSchema:
        current = await self._mcp_crud().get(id=upstream_id)
        if current is None:
            raise CustomException(msg="上游 MCP 不存在")
        payload = upstream_update_payload(data)
        if "system_id" in payload and payload["system_id"] != current.system_id:
            await self._require_system(payload["system_id"])
        if not payload:
            return UpstreamMcpOutSchema.model_validate(current)
        obj = await self._mcp_crud().update(id=upstream_id, data=payload)
        return UpstreamMcpOutSchema.model_validate(obj)

    async def page_tools(
        self,
        page_no: int,
        page_size: int,
        search: UpstreamToolQueryParam | None = None,
        order_by: list[dict[str, str]] | None = None,
    ) -> PageResultSchema[UpstreamToolOutSchema]:
        offset = (page_no - 1) * page_size
        return await self._tool_crud().page(
            offset=offset,
            limit=page_size,
            order_by=order_by or [{"id": "asc"}],
            search=search_to_dict(search, {}),
            out_schema=UpstreamToolOutSchema,
        )

    async def update_tool(self, tool_id: int, data: UpstreamToolUpdateSchema) -> UpstreamToolOutSchema:
        current = await self._tool_crud().get(id=tool_id)
        if current is None:
            raise CustomException(msg="上游工具不存在")
        obj = await self._tool_crud().update(id=tool_id, data=data)
        return UpstreamToolOutSchema.model_validate(obj)

    async def refresh(self, upstream_id: int) -> list[ToolSnapshot]:
        """向该上游要一次工具列表。已有 remote_name 只更新 input_schema。"""
        upstream, system_code, tools = await self._catalog(upstream_id)
        client = UpstreamClient(
            upstream=upstream,
            system_code=system_code,
            tools=tools,
            transport=self.transport,
        )
        snapshots = await client.list_tools(upstream_id)
        for tool in tools:
            if tool.id is None:
                self.db.add(tool)
        await self.db.flush()
        return snapshots

    async def call(self, upstream_id: int, name: str, arguments: dict[str, Any] | None = None) -> UpstreamResult:
        """正式转发。未选用的工具不会发出请求。"""
        upstream, system_code, tools = await self._catalog(upstream_id)
        client = UpstreamClient(
            upstream=upstream,
            system_code=system_code,
            tools=tools,
            transport=self.transport,
        )
        return await client.call(upstream_id, name, arguments)

    async def _catalog(self, upstream_id: int):
        upstream = await self._mcp_crud().get(id=upstream_id)
        if upstream is None:
            raise CustomException(msg="上游 MCP 不存在")
        system = await BizSystemCRUD(self.auth, self.db).get(id=upstream.system_id)
        if system is None:
            raise CustomException(msg="业务系统不存在")
        rows = await self._tool_crud().get_list(search={"upstream_id": upstream_id}, order_by=[{"id": "asc"}])
        tools: list[UpstreamToolModel] = list(rows)
        return upstream, system.code, tools

    async def _require_system(self, system_id: int) -> None:
        system = await BizSystemCRUD(self.auth, self.db).get(id=system_id)
        if system is None:
            raise CustomException(msg="业务系统不存在")

    def _mcp_crud(self) -> UpstreamMcpCRUD:
        return UpstreamMcpCRUD(self.auth, self.db)

    def _tool_crud(self) -> UpstreamToolCRUD:
        return UpstreamToolCRUD(self.auth, self.db)
