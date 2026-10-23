from sqlalchemy.ext.asyncio import AsyncSession

from app.core.base_crud import CRUDBase
from app.core.base_schema import AuthSchema

from .model import McpCredentialModel, McpGroupMemberModel, McpGroupModel, McpGroupToolModel
from .schema import (
    McpCredentialOutSchema,
    McpGroupCreateSchema,
    McpGroupMemberCreateSchema,
    McpGroupMemberUpdateSchema,
    McpGroupToolCreateSchema,
    McpGroupToolUpdateSchema,
    McpGroupUpdateSchema,
)


class McpGroupCRUD(CRUDBase[McpGroupModel, McpGroupCreateSchema, McpGroupUpdateSchema]):
    """MCP 组数据层。"""

    def __init__(self, auth: AuthSchema, db: AsyncSession) -> None:
        super().__init__(model=McpGroupModel, auth=auth, db=db)


class McpGroupToolCRUD(CRUDBase[McpGroupToolModel, McpGroupToolCreateSchema, McpGroupToolUpdateSchema]):
    """组内工具数据层。不提供删除。"""

    def __init__(self, auth: AuthSchema, db: AsyncSession) -> None:
        super().__init__(model=McpGroupToolModel, auth=auth, db=db)


class McpGroupMemberCRUD(CRUDBase[McpGroupMemberModel, McpGroupMemberCreateSchema, McpGroupMemberUpdateSchema]):
    """组成员数据层。不提供删除。"""

    def __init__(self, auth: AuthSchema, db: AsyncSession) -> None:
        super().__init__(model=McpGroupMemberModel, auth=auth, db=db)


class McpCredentialCRUD(CRUDBase[McpCredentialModel, McpCredentialOutSchema, McpCredentialOutSchema]):
    """凭证数据层。一行对应一个 (user_id, group_id)。"""

    def __init__(self, auth: AuthSchema, db: AsyncSession) -> None:
        super().__init__(model=McpCredentialModel, auth=auth, db=db)
