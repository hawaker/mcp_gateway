from sqlalchemy.ext.asyncio import AsyncSession

from app.core.base_schema import AuthSchema, PageResultSchema
from app.core.exceptions import CustomException
from app.utils.common_util import search_to_dict

from .crud import BizSystemCRUD
from .schema import BizSystemCreateSchema, BizSystemOutSchema, BizSystemQueryParam, BizSystemUpdateSchema


class BizSystemService:
    """业务系统服务。"""

    def __init__(self, auth: AuthSchema, db: AsyncSession) -> None:
        self.auth = auth
        self.db = db

    async def page(
        self,
        page_no: int,
        page_size: int,
        search: BizSystemQueryParam | None = None,
        order_by: list[dict[str, str]] | None = None,
    ) -> PageResultSchema[BizSystemOutSchema]:
        offset = (page_no - 1) * page_size
        return await BizSystemCRUD(self.auth, self.db).page(
            offset=offset,
            limit=page_size,
            order_by=order_by or [{"id": "asc"}],
            search=search_to_dict(search, {}),
            out_schema=BizSystemOutSchema,
        )

    async def detail(self, system_id: int) -> BizSystemOutSchema:
        return await BizSystemCRUD(self.auth, self.db).get_or_404(id=system_id, msg="业务系统不存在", out_schema=BizSystemOutSchema)

    async def create(self, data: BizSystemCreateSchema) -> BizSystemOutSchema:
        if await BizSystemCRUD(self.auth, self.db).exists(code=data.code):
            raise CustomException(msg="业务系统编码已存在")
        obj = await BizSystemCRUD(self.auth, self.db).create(data=data)
        return BizSystemOutSchema.model_validate(obj)

    async def update(self, system_id: int, data: BizSystemUpdateSchema) -> BizSystemOutSchema:
        """已存在的系统拒绝修改 code。传入相同 code 或省略 code 都保留原值。"""
        current = await BizSystemCRUD(self.auth, self.db).get(id=system_id)
        if current is None:
            raise CustomException(msg="业务系统不存在")
        submitted = data.model_dump(exclude_unset=True)
        new_code = submitted.get("code")
        if new_code is not None and new_code != current.code:
            raise CustomException(msg="业务系统编码不可修改")
        obj = await BizSystemCRUD(self.auth, self.db).update(id=system_id, data=data)
        return BizSystemOutSchema.model_validate(obj)
