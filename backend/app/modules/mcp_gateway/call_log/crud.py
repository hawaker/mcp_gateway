from sqlalchemy.ext.asyncio import AsyncSession

from app.core.base_crud import CRUDBase
from app.core.base_schema import AuthSchema

from .model import CallLogModel
from .schema import CallLogAggregateSchema


class CallLogCRUD(CRUDBase[CallLogModel, CallLogAggregateSchema, CallLogAggregateSchema]):
    """调用日志只追加。"""

    def __init__(self, auth: AuthSchema, db: AsyncSession) -> None:
        super().__init__(model=CallLogModel, auth=auth, db=db)
