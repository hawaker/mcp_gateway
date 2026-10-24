from sqlalchemy.ext.asyncio import AsyncSession

from app.core.base_crud import CRUDBase
from app.core.base_schema import AuthSchema

from .model import BizSystemModel
from .schema import BizSystemCreateSchema, BizSystemUpdateSchema


class BizSystemCRUD(CRUDBase[BizSystemModel, BizSystemCreateSchema, BizSystemUpdateSchema]):
    """业务系统数据层。"""

    def __init__(self, auth: AuthSchema, db: AsyncSession) -> None:
        super().__init__(model=BizSystemModel, auth=auth, db=db)
