"""运行时权限。verify 只核对 token，成员现在还能不能用在这里判断。"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.base_schema import AuthSchema
from app.core.exceptions import CustomException
from app.modules.mcp_gateway.mcp_group.crud import McpGroupCRUD, McpGroupMemberCRUD
from app.modules.mcp_gateway.mcp_group.service import McpCredentialService
from app.modules.mcp_gateway.user.crud import BizUserGroupCRUD
from app.modules.mcp_gateway.user.model import BizUserGroupMemberModel


class CredentialRejected(Exception):
    """缺少 bearer，或 token 对不上这个组。响应里不能出现无权限。"""

    def __init__(self, message: str = "凭证无效") -> None:
        self.message = message
        super().__init__(message)


def bearer_token(authorization: str | None) -> str | None:
    if not authorization:
        return None
    scheme, _, raw = authorization.partition(" ")
    if scheme.lower() != "bearer":
        return None
    token = raw.strip()
    return token or None


async def verify_bearer(db: AsyncSession, authorization: str | None) -> tuple[int, int]:
    """核对 Authorization。停用成员不会让这里失败。"""
    raw = bearer_token(authorization)
    if raw is None:
        raise CredentialRejected()
    try:
        return await McpCredentialService(AuthSchema(), db).verify(raw)
    except CustomException as exc:
        raise CredentialRejected(exc.msg) from exc


async def allowed(db: AsyncSession, user_id: int, group_id: int) -> bool:
    """组必须启用。本人是启用的直接成员，或仍在某个已启用且被勾选的业务用户组里。"""
    auth = AuthSchema()
    group = await McpGroupCRUD(auth, db).get(id=group_id)
    if group is None or not group.enabled:
        return False
    direct = await McpGroupMemberCRUD(auth, db).get(
        group_id=group_id,
        principal_type="user",
        principal_id=user_id,
    )
    if direct is not None and direct.enabled:
        return True
    links = await McpGroupMemberCRUD(auth, db).get_list(
        search={"group_id": group_id, "principal_type": "group", "enabled": True},
    )
    for link in links:
        biz_group = await BizUserGroupCRUD(auth, db).get(id=link.principal_id)
        if biz_group is None or not biz_group.enabled:
            continue
        found = await db.execute(
            select(BizUserGroupMemberModel.user_id).where(
                BizUserGroupMemberModel.user_id == user_id,
                BizUserGroupMemberModel.group_id == link.principal_id,
            )
        )
        if found.scalar_one_or_none() is not None:
            return True
    return False
