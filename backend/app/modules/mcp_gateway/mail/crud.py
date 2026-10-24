from sqlalchemy.ext.asyncio import AsyncSession

from app.core.base_crud import CRUDBase
from app.core.base_schema import AuthSchema

from .model import MailLogModel
from .schema import MailLogOutSchema


class MailLogCRUD(CRUDBase[MailLogModel, MailLogOutSchema, MailLogOutSchema]):
    """发信记录只追加。"""

    def __init__(self, auth: AuthSchema, db: AsyncSession) -> None:
        super().__init__(model=MailLogModel, auth=auth, db=db)
