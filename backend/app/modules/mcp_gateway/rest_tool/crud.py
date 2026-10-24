from sqlalchemy.ext.asyncio import AsyncSession

from app.core.base_crud import CRUDBase
from app.core.base_schema import AuthSchema

from .model import RestToolModel
from .schema import RestToolCreateSchema, RestToolUpdateSchema


class RestToolCRUD(CRUDBase[RestToolModel, RestToolCreateSchema, RestToolUpdateSchema]):
    """REST 工具数据层。"""

    def __init__(self, auth: AuthSchema, db: AsyncSession) -> None:
        super().__init__(model=RestToolModel, auth=auth, db=db)
