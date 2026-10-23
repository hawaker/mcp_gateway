from datetime import UTC, datetime

from sqlalchemy import false, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.base_crud import CRUDBase
from app.core.base_schema import AuthSchema

from .model import UpstreamMcpModel, UpstreamToolModel
from .schema import (
    UpstreamMcpCreateSchema,
    UpstreamMcpUpdateSchema,
    UpstreamToolUpdateSchema,
)


async def mark_deleted(db: AsyncSession, model: type[UpstreamMcpModel] | type[UpstreamToolModel], ids: list[int]) -> None:
    """把行标成已删除。

    CRUDBase.delete 只在模型同时有 is_deleted、deleted_time、deleted_id 时软删除。
    这两张表没有 deleted_id，直接调用会物理删除，所以这里只写 is_deleted 和 deleted_time。
    """
    if not ids:
        return
    await db.execute(
        update(model)
        .where(model.id.in_(ids))
        .where(model.is_deleted == false())
        .values(is_deleted=True, deleted_time=datetime.now(UTC))
    )
    await db.flush()


class UpstreamMcpCRUD(CRUDBase[UpstreamMcpModel, UpstreamMcpCreateSchema, UpstreamMcpUpdateSchema]):
    """上游 MCP 数据层。"""

    def __init__(self, auth: AuthSchema, db: AsyncSession) -> None:
        super().__init__(model=UpstreamMcpModel, auth=auth, db=db)

    async def delete(self, ids: list[int]) -> None:
        await mark_deleted(self.db, self.model, ids)


class UpstreamToolCRUD(CRUDBase[UpstreamToolModel, UpstreamToolUpdateSchema, UpstreamToolUpdateSchema]):
    """上游工具数据层。"""

    def __init__(self, auth: AuthSchema, db: AsyncSession) -> None:
        super().__init__(model=UpstreamToolModel, auth=auth, db=db)

    async def delete(self, ids: list[int]) -> None:
        await mark_deleted(self.db, self.model, ids)
