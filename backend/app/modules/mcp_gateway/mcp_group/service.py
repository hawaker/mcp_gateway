"""MCP 组：发布哪些工具、哪些人能用，以及每人每组一个稳定 token。"""

import hashlib
import secrets

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.base_schema import AuthSchema, PageResultSchema
from app.core.exceptions import CustomException
from app.modules.mcp_gateway.rest_tool.crud import RestToolCRUD
from app.modules.mcp_gateway.upstream.crud import UpstreamMcpCRUD, UpstreamToolCRUD
from app.modules.mcp_gateway.user.crud import BizUserCRUD, BizUserGroupCRUD
from app.modules.mcp_gateway.user.service import BizUserGroupService
from app.utils.common_util import search_to_dict
from app.utils.crypto_util import CryptoUtil

from .crud import McpCredentialCRUD, McpGroupCRUD, McpGroupMemberCRUD, McpGroupToolCRUD
from .schema import (
    ConnectionInfoSchema,
    McpCredentialOutSchema,
    McpCredentialQueryParam,
    McpGroupCreateSchema,
    McpGroupMemberCreateSchema,
    McpGroupMemberOutSchema,
    McpGroupMemberQueryParam,
    McpGroupMemberUpdateSchema,
    McpGroupOutSchema,
    McpGroupQueryParam,
    McpGroupToolCreateSchema,
    McpGroupToolOutSchema,
    McpGroupToolQueryParam,
    McpGroupToolUpdateSchema,
    McpGroupUpdateSchema,
    PublishedToolSchema,
)


class NotFound(Exception):
    """成员没有删除接口。调用 remove_member 时抛出，且不会删除任何行。"""


def token_hash(raw: str) -> str:
    """可查询的令牌摘要。随机盐的口令哈希无法按明文找回这一行。"""
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


class McpCredentialService:
    """签发、校验和重新签发。明文只从 issue、reissue 以及 connection_info 给出。"""

    def __init__(self, auth: AuthSchema, db: AsyncSession) -> None:
        self.auth = auth
        self.db = db

    async def page(
        self,
        page_no: int,
        page_size: int,
        search: McpCredentialQueryParam | None = None,
        order_by: list[dict[str, str]] | None = None,
    ) -> PageResultSchema[McpCredentialOutSchema]:
        offset = (page_no - 1) * page_size
        return await McpCredentialCRUD(self.auth, self.db).page(
            offset=offset,
            limit=page_size,
            order_by=order_by or [{"id": "asc"}],
            search=search_to_dict(search, {}),
            out_schema=McpCredentialOutSchema,
        )

    async def issue(self, user_id: int, group_id: int) -> str:
        """已有凭证时原样返回，不轮换。"""
        await self._require_user(user_id)
        await self._require_group(group_id)
        existing = await McpCredentialCRUD(self.auth, self.db).get(user_id=user_id, group_id=group_id)
        if existing is not None:
            return CryptoUtil.decrypt(existing.token_encrypted)
        raw = secrets.token_urlsafe(32)
        await McpCredentialCRUD(self.auth, self.db).create(
            data={
                "user_id": user_id,
                "group_id": group_id,
                "token_hash": token_hash(raw),
                "token_encrypted": CryptoUtil.encrypt(raw),
            }
        )
        return raw

    async def verify(self, raw: str) -> tuple[int, int]:
        """只核对 token。成员停用或离开业务用户组都不影响结果。"""
        row = await McpCredentialCRUD(self.auth, self.db).get(token_hash=token_hash(raw))
        if row is None:
            raise CustomException(msg="凭证无效")
        return row.user_id, row.group_id

    async def reissue(self, user_id: int, group_id: int) -> str:
        """替换哈希和密文。旧明文立刻无法 verify。"""
        existing = await McpCredentialCRUD(self.auth, self.db).get(user_id=user_id, group_id=group_id)
        if existing is None or existing.id is None:
            raise CustomException(msg="凭证不存在")
        raw = secrets.token_urlsafe(32)
        await McpCredentialCRUD(self.auth, self.db).update(
            id=existing.id,
            data={"token_hash": token_hash(raw), "token_encrypted": CryptoUtil.encrypt(raw)},
        )
        return raw

    async def connection_info(self, user_id: int, group_id: int) -> ConnectionInfoSchema:
        """解密已保存的副本。不会创建凭证，也不启动传输。"""
        existing = await McpCredentialCRUD(self.auth, self.db).get(user_id=user_id, group_id=group_id)
        if existing is None:
            raise CustomException(msg="凭证不存在")
        raw = CryptoUtil.decrypt(existing.token_encrypted)
        return ConnectionInfoSchema(
            streamable_http_url=f"/mcp/{group_id}",
            sse_url=f"/mcp/{group_id}/sse",
            messages_url=f"/mcp/{group_id}/messages",
            authorization=f"Authorization: Bearer {raw}",
        )

    async def _require_user(self, user_id: int) -> None:
        user = await BizUserCRUD(self.auth, self.db).get(id=user_id)
        if user is None:
            raise CustomException(msg="业务用户不存在")

    async def _require_group(self, group_id: int) -> None:
        group = await McpGroupCRUD(self.auth, self.db).get(id=group_id)
        if group is None:
            raise CustomException(msg="MCP 组不存在")


class McpGroupService:
    """组、组内工具和成员。删除成员的入口固定拒绝。"""

    def __init__(self, auth: AuthSchema, db: AsyncSession) -> None:
        self.auth = auth
        self.db = db

    async def page(
        self,
        page_no: int,
        page_size: int,
        search: McpGroupQueryParam | None = None,
        order_by: list[dict[str, str]] | None = None,
    ) -> PageResultSchema[McpGroupOutSchema]:
        offset = (page_no - 1) * page_size
        return await McpGroupCRUD(self.auth, self.db).page(
            offset=offset,
            limit=page_size,
            order_by=order_by or [{"id": "asc"}],
            search=search_to_dict(search, {}),
            out_schema=McpGroupOutSchema,
        )

    async def detail(self, group_id: int) -> McpGroupOutSchema:
        return await McpGroupCRUD(self.auth, self.db).get_or_404(id=group_id, msg="MCP 组不存在", out_schema=McpGroupOutSchema)

    async def create(self, data: McpGroupCreateSchema) -> McpGroupOutSchema:
        obj = await McpGroupCRUD(self.auth, self.db).create(data=data)
        return McpGroupOutSchema.model_validate(obj)

    async def update(self, group_id: int, data: McpGroupUpdateSchema) -> McpGroupOutSchema:
        current = await McpGroupCRUD(self.auth, self.db).get(id=group_id)
        if current is None:
            raise CustomException(msg="MCP 组不存在")
        payload = data.model_dump(exclude_unset=True)
        if not payload:
            return McpGroupOutSchema.model_validate(current)
        obj = await McpGroupCRUD(self.auth, self.db).update(id=group_id, data=payload)
        return McpGroupOutSchema.model_validate(obj)

    async def page_tools(
        self,
        page_no: int,
        page_size: int,
        search: McpGroupToolQueryParam | None = None,
        order_by: list[dict[str, str]] | None = None,
    ) -> PageResultSchema[McpGroupToolOutSchema]:
        offset = (page_no - 1) * page_size
        return await McpGroupToolCRUD(self.auth, self.db).page(
            offset=offset,
            limit=page_size,
            order_by=order_by or [{"id": "asc"}],
            search=search_to_dict(search, {}),
            out_schema=McpGroupToolOutSchema,
        )

    async def add_tool(self, group_id: int, data: McpGroupToolCreateSchema) -> McpGroupToolOutSchema:
        await self._require_group(group_id)
        external_name = await self._resolve_external_name(data)
        await self._require_unique_external_name(group_id, external_name)
        obj = await McpGroupToolCRUD(self.auth, self.db).create(
            data={
                "group_id": group_id,
                "source": data.source,
                "source_id": data.source_id,
                "external_name": external_name,
                "enabled": data.enabled,
            }
        )
        return McpGroupToolOutSchema.model_validate(obj)

    async def update_tool(self, tool_id: int, data: McpGroupToolUpdateSchema) -> McpGroupToolOutSchema:
        current = await McpGroupToolCRUD(self.auth, self.db).get(id=tool_id)
        if current is None:
            raise CustomException(msg="组内工具不存在")
        payload = data.model_dump(exclude_unset=True)
        external_name = payload.get("external_name")
        if external_name:
            await self._require_unique_external_name(current.group_id, external_name, exclude_id=current.id)
        if not payload:
            return McpGroupToolOutSchema.model_validate(current)
        obj = await McpGroupToolCRUD(self.auth, self.db).update(id=tool_id, data=payload)
        return McpGroupToolOutSchema.model_validate(obj)

    async def update_tool_enabled(self, tool_id: int, enabled: bool) -> McpGroupToolOutSchema:
        return await self.update_tool(tool_id, McpGroupToolUpdateSchema(enabled=enabled))

    async def tools_for(self, group_id: int) -> list[PublishedToolSchema]:
        """下一任务将把这份目录暴露为 tools/list。这里不做 JSON-RPC。"""
        await self._require_group(group_id)
        rows = await McpGroupToolCRUD(self.auth, self.db).get_list(
            search={"group_id": group_id, "enabled": True},
            order_by=[{"id": "asc"}],
        )
        catalog: list[PublishedToolSchema] = []
        for row in rows:
            item = await self._publish(row.source, row.source_id, row.external_name)
            if item is not None:
                catalog.append(item)
        return catalog

    async def page_members(
        self,
        page_no: int,
        page_size: int,
        search: McpGroupMemberQueryParam | None = None,
        order_by: list[dict[str, str]] | None = None,
    ) -> PageResultSchema[McpGroupMemberOutSchema]:
        offset = (page_no - 1) * page_size
        return await McpGroupMemberCRUD(self.auth, self.db).page(
            offset=offset,
            limit=page_size,
            order_by=order_by or [{"id": "asc"}],
            search=search_to_dict(search, {}),
            out_schema=McpGroupMemberOutSchema,
        )

    async def add_member(self, group_id: int, data: McpGroupMemberCreateSchema) -> McpGroupMemberOutSchema:
        await self._require_group(group_id)
        await self._require_principal(data.principal_type, data.principal_id)
        existing = await McpGroupMemberCRUD(self.auth, self.db).get(
            group_id=group_id,
            principal_type=data.principal_type,
            principal_id=data.principal_id,
        )
        if existing is None:
            existing = await McpGroupMemberCRUD(self.auth, self.db).create(
                data={
                    "group_id": group_id,
                    "principal_type": data.principal_type,
                    "principal_id": data.principal_id,
                    "enabled": data.enabled,
                }
            )
        elif existing.enabled != data.enabled:
            # 再次添加时采用本次提交的 enabled，避免悄悄留下停用行。
            existing = await McpGroupMemberCRUD(self.auth, self.db).update(
                id=existing.id,
                data={"enabled": data.enabled},
            )
        if existing.enabled:
            await self._issue_principal(group_id, existing.principal_type, existing.principal_id)
        return McpGroupMemberOutSchema.model_validate(existing)

    async def update_member(self, member_id: int, data: McpGroupMemberUpdateSchema) -> McpGroupMemberOutSchema:
        current = await McpGroupMemberCRUD(self.auth, self.db).get(id=member_id)
        if current is None:
            raise CustomException(msg="成员不存在")
        payload = data.model_dump(exclude_unset=True)
        if not payload:
            return McpGroupMemberOutSchema.model_validate(current)
        obj = await McpGroupMemberCRUD(self.auth, self.db).update(id=member_id, data=payload)
        if obj.enabled:
            await self._issue_principal(obj.group_id, obj.principal_type, obj.principal_id)
        return McpGroupMemberOutSchema.model_validate(obj)

    async def disable_member(self, group_id: int, principal_type: str, principal_id: int) -> None:
        """停用成员，保留已签发的凭证。"""
        member = await McpGroupMemberCRUD(self.auth, self.db).get(
            group_id=group_id,
            principal_type=principal_type,
            principal_id=principal_id,
        )
        if member is None:
            raise CustomException(msg="成员不存在")
        member.enabled = False
        await self.db.flush()

    async def remove_member(self, group_id: int, principal_type: str, principal_id: int) -> None:
        """始终拒绝。不读取、不删除成员或凭证。"""
        raise NotFound("成员不能删除")

    async def validate_selection(self, group_id: int) -> None:
        """组保存校验：REST ∪ 上游 ∪ 数据源至少一类。"""
        await self._require_group(group_id)
        tools = await McpGroupToolCRUD(self.auth, self.db).get_list(search={"group_id": group_id})
        if tools:
            return
        from app.modules.genbi.acl.service import GenbiGroupDatasourceService

        ds_count = await GenbiGroupDatasourceService(self.auth, self.db).count_for_group(group_id)
        if ds_count > 0:
            return
        raise CustomException(msg="至少需要配置一类：REST、上游或数据源")

    async def _require_group(self, group_id: int) -> None:
        group = await McpGroupCRUD(self.auth, self.db).get(id=group_id)
        if group is None:
            raise CustomException(msg="MCP 组不存在")

    async def _require_principal(self, principal_type: str, principal_id: int) -> None:
        if principal_type == "user":
            user = await BizUserCRUD(self.auth, self.db).get(id=principal_id)
            if user is None:
                raise CustomException(msg="业务用户不存在")
            return
        group = await BizUserGroupCRUD(self.auth, self.db).get(id=principal_id)
        if group is None:
            raise CustomException(msg="用户组不存在")

    async def _issue_principal(self, group_id: int, principal_type: str, principal_id: int) -> None:
        credentials = McpCredentialService(self.auth, self.db)
        if principal_type == "user":
            await credentials.issue(principal_id, group_id)
            return
        user_ids = await BizUserGroupService(self.auth, self.db).list_member_user_ids(principal_id)
        for user_id in user_ids:
            await credentials.issue(user_id, group_id)

    async def _resolve_external_name(self, data: McpGroupToolCreateSchema) -> str:
        if data.source == "rest":
            tool = await RestToolCRUD(self.auth, self.db).get(id=data.source_id)
            if tool is None:
                raise CustomException(msg="REST 工具不存在")
            return data.external_name or tool.name
        upstream_tool = await self._selected_upstream_tool(data.source_id)
        return data.external_name or upstream_tool.external_name

    async def _selected_upstream_tool(self, source_id: int):
        tool = await UpstreamToolCRUD(self.auth, self.db).get(id=source_id)
        if tool is None or not tool.selected:
            raise CustomException(msg="未选用的上游工具不能加入")
        upstream = await UpstreamMcpCRUD(self.auth, self.db).get(id=tool.upstream_id)
        if upstream is None:
            raise CustomException(msg="未选用的上游工具不能加入")
        return tool

    async def _require_unique_external_name(self, group_id: int, external_name: str, *, exclude_id: int | None = None) -> None:
        rows = await McpGroupToolCRUD(self.auth, self.db).get_list(
            search={"group_id": group_id, "external_name": external_name},
        )
        for row in rows:
            if exclude_id is not None and row.id == exclude_id:
                continue
            raise CustomException(msg="外部名称已存在")

    async def _publish(self, source: str, source_id: int, external_name: str) -> PublishedToolSchema | None:
        if source == "rest":
            tool = await RestToolCRUD(self.auth, self.db).get(id=source_id)
            if tool is None or not tool.enabled:
                return None
            if tool.id is None:
                return None
            return PublishedToolSchema(
                name=external_name,
                description=tool.description or "",
                input_schema=dict(tool.input_schema or {}),
                source="rest",
                source_id=tool.id,
            )
        if source != "upstream":
            return None
        tool = await UpstreamToolCRUD(self.auth, self.db).get(id=source_id)
        if tool is None or not tool.selected or tool.id is None:
            return None
        upstream = await UpstreamMcpCRUD(self.auth, self.db).get(id=tool.upstream_id)
        if upstream is None:
            return None
        return PublishedToolSchema(
            name=external_name,
            description="",
            input_schema=dict(tool.input_schema or {}),
            source="upstream",
            source_id=tool.id,
        )
