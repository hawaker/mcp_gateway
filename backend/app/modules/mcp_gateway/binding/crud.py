from sqlalchemy.ext.asyncio import AsyncSession

from app.core.base_crud import CRUDBase
from app.core.base_schema import AuthSchema

from .model import BizBindingModel
from .schema import BizBindingCreateSchema, BizBindingUpdateSchema


class BizBindingCRUD(CRUDBase[BizBindingModel, BizBindingCreateSchema, BizBindingUpdateSchema]):
    """业务系统绑定数据层。"""

    def __init__(self, auth: AuthSchema, db: AsyncSession) -> None:
        super().__init__(model=BizBindingModel, auth=auth, db=db)
