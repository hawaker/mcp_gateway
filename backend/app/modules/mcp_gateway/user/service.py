from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.base_schema import AuthSchema, PageResultSchema
from app.core.exceptions import CustomException
from app.utils.common_util import search_to_dict

from .crud import BizUserCRUD, BizUserGroupCRUD
from .model import BizUserGroupMemberModel
from .schema import (
    BizUserCreateSchema,
    BizUserGroupCreateSchema,
    BizUserGroupOutSchema,
    BizUserGroupQueryParam,
    BizUserOutSchema,
    BizUserQueryParam,
)


class BizUserService:
    """业务用户服务。"""

    def __init__(self, auth: AuthSchema, db: AsyncSession) -> None:
        self.auth = auth
        self.db = db

    async def page(
        self,
        page_no: int,
        page_size: int,
        search: BizUserQueryParam | None = None,
        order_by: list[dict[str, str]] | None = None,
    ) -> PageResultSchema[BizUserOutSchema]:
        offset = (page_no - 1) * page_size
        return await BizUserCRUD(self.auth, self.db).page(
            offset=offset,
            limit=page_size,
            order_by=order_by or [{"id": "asc"}],
            search=search_to_dict(search, {}),
            out_schema=BizUserOutSchema,
        )

    async def create(self, data: BizUserCreateSchema) -> BizUserOutSchema:
        obj = await BizUserCRUD(self.auth, self.db).create(data=data)
        return BizUserOutSchema.model_validate(obj)

    async def add_to_groups(self, user_id: int, group_ids: list[int]) -> None:
        """把用户加入若干组。已存在的 (user_id, group_id) 不重复插入，也不移出其他组。"""
        user = await BizUserCRUD(self.auth, self.db).get(id=user_id)
        if not user:
            raise CustomException(msg="业务用户不存在")

        for group_id in dict.fromkeys(group_ids):
            group = await BizUserGroupCRUD(self.auth, self.db).get(id=group_id)
            if not group:
                raise CustomException(msg="用户组不存在")
            existing = await self.db.execute(
                select(BizUserGroupMemberModel).where(
                    BizUserGroupMemberModel.user_id == user_id,
                    BizUserGroupMemberModel.group_id == group_id,
                )
            )
            if existing.scalar_one_or_none() is not None:
                continue
            self.db.add(BizUserGroupMemberModel(user_id=user_id, group_id=group_id))
        await self.db.flush()


class BizUserGroupService:
    """业务用户组服务。"""

    def __init__(self, auth: AuthSchema, db: AsyncSession) -> None:
        self.auth = auth
        self.db = db

    async def page(
        self,
        page_no: int,
        page_size: int,
        search: BizUserGroupQueryParam | None = None,
        order_by: list[dict[str, str]] | None = None,
    ) -> PageResultSchema[BizUserGroupOutSchema]:
        offset = (page_no - 1) * page_size
        return await BizUserGroupCRUD(self.auth, self.db).page(
            offset=offset,
            limit=page_size,
            order_by=order_by or [{"id": "asc"}],
            search=search_to_dict(search, {}),
            out_schema=BizUserGroupOutSchema,
        )

    async def create(self, data: BizUserGroupCreateSchema) -> BizUserGroupOutSchema:
        obj = await BizUserGroupCRUD(self.auth, self.db).create(data=data)
        return BizUserGroupOutSchema.model_validate(obj)

    async def list_member_user_ids(self, group_id: int) -> list[int]:
        """读取该组在成员表中已存储的用户 ID，不回显请求体。"""
        rows = await self.db.execute(
            select(BizUserGroupMemberModel.user_id).where(
                BizUserGroupMemberModel.group_id == group_id,
            )
        )
        return list(rows.scalars().all())
