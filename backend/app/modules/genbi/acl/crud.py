from sqlalchemy.ext.asyncio import AsyncSession

from app.core.base_crud import CRUDBase
from app.core.base_schema import AuthSchema

from .model import (
    GenbiGroupDatasourceAclColumnModel,
    GenbiGroupDatasourceAclRowModel,
    GenbiGroupDatasourceModel,
)
from .schema import GenbiGroupDatasourceAttach, GenbiGroupDatasourceUpdate


class GenbiGroupDatasourceCRUD(
    CRUDBase[GenbiGroupDatasourceModel, GenbiGroupDatasourceAttach, GenbiGroupDatasourceUpdate]
):
    def __init__(self, auth: AuthSchema, db: AsyncSession) -> None:
        super().__init__(model=GenbiGroupDatasourceModel, auth=auth, db=db)


class GenbiGroupDatasourceAclRowCRUD(
    CRUDBase[GenbiGroupDatasourceAclRowModel, GenbiGroupDatasourceAttach, GenbiGroupDatasourceUpdate]
):
    def __init__(self, auth: AuthSchema, db: AsyncSession) -> None:
        super().__init__(model=GenbiGroupDatasourceAclRowModel, auth=auth, db=db)


class GenbiGroupDatasourceAclColumnCRUD(
    CRUDBase[GenbiGroupDatasourceAclColumnModel, GenbiGroupDatasourceAttach, GenbiGroupDatasourceUpdate]
):
    def __init__(self, auth: AuthSchema, db: AsyncSession) -> None:
        super().__init__(model=GenbiGroupDatasourceAclColumnModel, auth=auth, db=db)
