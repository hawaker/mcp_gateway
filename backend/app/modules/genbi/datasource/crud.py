from sqlalchemy.ext.asyncio import AsyncSession

from app.core.base_crud import CRUDBase
from app.core.base_schema import AuthSchema

from .model import GenbiDatasourceModel
from .schema import GenbiDatasourceCreate, GenbiDatasourceUpdate


class GenbiDatasourceCRUD(CRUDBase[GenbiDatasourceModel, GenbiDatasourceCreate, GenbiDatasourceUpdate]):
    """GenBI 数据源。"""

    def __init__(self, auth: AuthSchema, db: AsyncSession) -> None:
        super().__init__(model=GenbiDatasourceModel, auth=auth, db=db)
