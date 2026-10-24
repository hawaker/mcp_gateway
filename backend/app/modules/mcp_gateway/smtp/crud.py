from sqlalchemy.ext.asyncio import AsyncSession

from app.core.base_crud import CRUDBase
from app.core.base_schema import AuthSchema

from .model import SmtpConfigModel
from .schema import SmtpConfigCreateSchema, SmtpConfigUpdateSchema


class SmtpConfigCRUD(CRUDBase[SmtpConfigModel, SmtpConfigCreateSchema, SmtpConfigUpdateSchema]):
    """SMTP 配置。全表只有一行。"""

    def __init__(self, auth: AuthSchema, db: AsyncSession) -> None:
        super().__init__(model=SmtpConfigModel, auth=auth, db=db)
