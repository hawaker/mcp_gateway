from sqlalchemy.ext.asyncio import AsyncSession

from app.core.base_crud import CRUDBase
from app.core.base_schema import AuthSchema

from .model import AuthConfigModel
from .schema import AuthConfigCreateSchema, AuthConfigUpdateSchema


class AuthConfigCRUD(CRUDBase[AuthConfigModel, AuthConfigCreateSchema, AuthConfigUpdateSchema]):
    """业务鉴权配置数据层。"""

    def __init__(self, auth: AuthSchema, db: AsyncSession) -> None:
        super().__init__(model=AuthConfigModel, auth=auth, db=db)
