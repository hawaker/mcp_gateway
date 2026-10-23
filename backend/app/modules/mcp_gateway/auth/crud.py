from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.base_crud import CRUDBase
from app.core.base_schema import AuthSchema

from .model import AuthConfigModel
from .schema import AuthConfigCreateSchema, AuthConfigUpdateSchema


class AuthConfigCRUD(CRUDBase[AuthConfigModel, AuthConfigCreateSchema, AuthConfigUpdateSchema]):
    """业务鉴权配置数据层。"""

    def __init__(self, auth: AuthSchema, db: AsyncSession) -> None:
        super().__init__(model=AuthConfigModel, auth=auth, db=db)

    async def lock_system_rows(self, system_id: int) -> None:
        """锁住该系统已有的鉴权行，避免两次保存同时提交 enabled=True。"""
        await self.db.execute(select(AuthConfigModel.id).where(AuthConfigModel.system_id == system_id).order_by(AuthConfigModel.id).with_for_update())
