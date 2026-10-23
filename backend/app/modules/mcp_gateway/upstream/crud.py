from sqlalchemy.ext.asyncio import AsyncSession

from app.core.base_crud import CRUDBase
from app.core.base_schema import AuthSchema

from .model import UpstreamMcpModel, UpstreamToolModel
from .schema import (
    UpstreamMcpCreateSchema,
    UpstreamMcpUpdateSchema,
    UpstreamToolUpdateSchema,
)


class UpstreamMcpCRUD(CRUDBase[UpstreamMcpModel, UpstreamMcpCreateSchema, UpstreamMcpUpdateSchema]):
    """上游 MCP 数据层。"""

    def __init__(self, auth: AuthSchema, db: AsyncSession) -> None:
        super().__init__(model=UpstreamMcpModel, auth=auth, db=db)


class UpstreamToolCRUD(CRUDBase[UpstreamToolModel, UpstreamToolUpdateSchema, UpstreamToolUpdateSchema]):
    """上游工具数据层。"""

    def __init__(self, auth: AuthSchema, db: AsyncSession) -> None:
        super().__init__(model=UpstreamToolModel, auth=auth, db=db)
