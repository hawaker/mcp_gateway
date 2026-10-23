"""按 MCP 组、用户组、用户发送各自的连接信息，并记下成败。"""

import smtplib

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.base_schema import AuthSchema, PageResultSchema
from app.core.exceptions import CustomException
from app.modules.mcp_gateway.mcp_group.crud import McpCredentialCRUD, McpGroupCRUD, McpGroupMemberCRUD
from app.modules.mcp_gateway.smtp.model import SmtpConfigModel
from app.modules.mcp_gateway.smtp.service import SmtpConfigService
from app.modules.mcp_gateway.user.crud import BizUserCRUD, BizUserGroupCRUD
from app.modules.mcp_gateway.user.model import BizUserGroupMemberModel
from app.modules.mcp_gateway.user.service import BizUserGroupService
from app.utils.common_util import search_to_dict
from app.utils.crypto_util import CryptoUtil

from .crud import MailLogCRUD
from .schema import Channel, MailLogOutSchema, MailLogQueryParam


def connection_body(group_id: int, token: str) -> str:
    """一封信只放这个用户在这个组上的地址和 token。"""
    return "\n".join(
        [
            f"/mcp/{group_id}",
            f"/mcp/{group_id}/sse",
            f"/mcp/{group_id}/messages",
            f"Authorization: Bearer {token}",
        ]
    )


class MailService:
    """不调用 issue 或 reissue。没有凭证就记失败，不新造 token。"""

    def __init__(
        self,
        auth: AuthSchema,
        db: AsyncSession,
        *,
        smtp_cls: type = smtplib.SMTP,
        smtp_ssl_cls: type = smtplib.SMTP_SSL,
    ) -> None:
        self.auth = auth
        self.db = db
        self.smtp = SmtpConfigService(auth, db, smtp_cls=smtp_cls, smtp_ssl_cls=smtp_ssl_cls)

    async def send_for_group(self, group_id: int) -> list[MailLogOutSchema]:
        config = await self.smtp.load_for_connection_mail()
        group = await McpGroupCRUD(self.auth, self.db).get(id=group_id)
        if group is None:
            raise CustomException(msg="MCP 组不存在")
        user_ids = await self._users_for_group(group_id)
        return await self._send_each(config, user_ids, group_id, "group")

    async def send_for_user_group(self, user_group_id: int) -> list[MailLogOutSchema]:
        config = await self.smtp.load_for_connection_mail()
        biz_group = await BizUserGroupCRUD(self.auth, self.db).get(id=user_group_id)
        if biz_group is None:
            raise CustomException(msg="用户组不存在")
        if not biz_group.enabled:
            return []
        links = await McpGroupMemberCRUD(self.auth, self.db).get_list(
            search={"principal_type": "group", "principal_id": user_group_id, "enabled": True},
        )
        user_ids = await BizUserGroupService(self.auth, self.db).list_member_user_ids(user_group_id)
        rows: list[MailLogOutSchema] = []
        for link in links:
            rows.extend(await self._send_each(config, user_ids, link.group_id, "user_group"))
        return rows

    async def send_for_user(self, user_id: int) -> list[MailLogOutSchema]:
        config = await self.smtp.load_for_connection_mail()
        user = await BizUserCRUD(self.auth, self.db).get(id=user_id)
        if user is None:
            raise CustomException(msg="业务用户不存在")
        if not user.enabled:
            return []
        rows: list[MailLogOutSchema] = []
        for group_id in await self._allowed_group_ids(user_id):
            rows.extend(await self._send_each(config, [user_id], group_id, "user"))
        return rows

    async def page(
        self,
        page_no: int,
        page_size: int,
        search: MailLogQueryParam | None = None,
        order_by: list[dict[str, str]] | None = None,
    ) -> PageResultSchema[MailLogOutSchema]:
        payload = search_to_dict(search, {}) or {}
        user_group_id = payload.pop("user_group_id", None)
        if user_group_id is not None:
            ids = await BizUserGroupService(self.auth, self.db).list_member_user_ids(int(user_group_id))
            if "user_id" in payload:
                wanted = payload["user_id"][1] if isinstance(payload["user_id"], tuple) else payload["user_id"]
                ids = [item for item in ids if item == wanted]
            payload["user_id"] = ("in", ids)
        offset = (page_no - 1) * page_size
        return await MailLogCRUD(self.auth, self.db).page(
            offset=offset,
            limit=page_size,
            order_by=order_by or [{"id": "asc"}],
            search=payload,
            out_schema=MailLogOutSchema,
        )

    async def _users_for_group(self, group_id: int) -> list[int]:
        members = await McpGroupMemberCRUD(self.auth, self.db).get_list(search={"group_id": group_id})
        seen: dict[int, None] = {}
        for member in members:
            if not member.enabled:
                continue
            if member.principal_type == "user":
                seen.setdefault(member.principal_id, None)
                continue
            if member.principal_type != "group":
                continue
            biz_group = await BizUserGroupCRUD(self.auth, self.db).get(id=member.principal_id)
            if biz_group is None or not biz_group.enabled:
                continue
            for user_id in await BizUserGroupService(self.auth, self.db).list_member_user_ids(member.principal_id):
                seen.setdefault(user_id, None)
        return list(seen)

    async def _allowed_group_ids(self, user_id: int) -> list[int]:
        """组已启用，并且本人是启用成员，或仍在某个已启用且被勾选的业务用户组里。"""
        seen: dict[int, None] = {}
        direct = await McpGroupMemberCRUD(self.auth, self.db).get_list(
            search={"principal_type": "user", "principal_id": user_id, "enabled": True},
        )
        for member in direct:
            group = await McpGroupCRUD(self.auth, self.db).get(id=member.group_id)
            if group is not None and group.enabled:
                seen.setdefault(member.group_id, None)
        result = await self.db.execute(select(BizUserGroupMemberModel.group_id).where(BizUserGroupMemberModel.user_id == user_id))
        for biz_group_id in result.scalars().all():
            biz_group = await BizUserGroupCRUD(self.auth, self.db).get(id=biz_group_id)
            if biz_group is None or not biz_group.enabled:
                continue
            links = await McpGroupMemberCRUD(self.auth, self.db).get_list(
                search={"principal_type": "group", "principal_id": biz_group_id, "enabled": True},
            )
            for link in links:
                group = await McpGroupCRUD(self.auth, self.db).get(id=link.group_id)
                if group is not None and group.enabled:
                    seen.setdefault(link.group_id, None)
        return list(seen)

    async def _send_each(
        self,
        config: SmtpConfigModel,
        user_ids: list[int],
        group_id: int,
        channel: Channel,
    ) -> list[MailLogOutSchema]:
        rows: list[MailLogOutSchema] = []
        for user_id in user_ids:
            user = await BizUserCRUD(self.auth, self.db).get(id=user_id)
            if user is None or not user.enabled:
                continue
            email = (user.email or "").strip()
            if not email:
                rows.append(await self._log(user_id, group_id, channel, False, "没有邮箱"))
                continue
            credential = await McpCredentialCRUD(self.auth, self.db).get(user_id=user_id, group_id=group_id)
            if credential is None or not credential.token_encrypted:
                rows.append(await self._log(user_id, group_id, channel, False, "凭证不存在"))
                continue
            try:
                token = CryptoUtil.decrypt(credential.token_encrypted)
                self.smtp.deliver_message(config, email, "MCP 连接信息", connection_body(group_id, token))
            except Exception:
                rows.append(await self._log(user_id, group_id, channel, False, "发信失败"))
                continue
            rows.append(await self._log(user_id, group_id, channel, True, None))
        return rows

    async def _log(
        self,
        user_id: int,
        group_id: int,
        channel: Channel,
        ok: bool,
        reason: str | None,
    ) -> MailLogOutSchema:
        obj = await MailLogCRUD(self.auth, self.db).create(
            data={
                "user_id": user_id,
                "group_id": group_id,
                "channel": channel,
                "ok": ok,
                "reason": reason,
            }
        )
        return MailLogOutSchema.model_validate(obj)
