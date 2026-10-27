from sqlalchemy.ext.asyncio import AsyncSession

from app.core.base_crud import CRUDBase
from app.core.base_schema import AuthSchema

from .model import GenbiProjectModel
from .schema import GenbiProjectCreate, GenbiProjectUpdate


class GenbiProjectCRUD(CRUDBase[GenbiProjectModel, GenbiProjectCreate, GenbiProjectUpdate]):
    """GenBI 项目。"""

    def __init__(self, auth: AuthSchema, db: AsyncSession) -> None:
        super().__init__(model=GenbiProjectModel, auth=auth, db=db)
