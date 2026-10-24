from sqlalchemy.ext.asyncio import AsyncSession

from app.core.base_crud import CRUDBase
from app.core.base_schema import AuthSchema

from .model import BizUserGroupModel, BizUserModel
from .schema import BizUserCreateSchema, BizUserGroupCreateSchema


class BizUserCRUD(CRUDBase[BizUserModel, BizUserCreateSchema, BizUserCreateSchema]):
    """业务用户数据层。"""

    def __init__(self, auth: AuthSchema, db: AsyncSession) -> None:
        super().__init__(model=BizUserModel, auth=auth, db=db)


class BizUserGroupCRUD(CRUDBase[BizUserGroupModel, BizUserGroupCreateSchema, BizUserGroupCreateSchema]):
    """业务用户组数据层。"""

    def __init__(self, auth: AuthSchema, db: AsyncSession) -> None:
        super().__init__(model=BizUserGroupModel, auth=auth, db=db)
