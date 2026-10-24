from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.base_schema import AuthSchema, PageResultSchema
from app.core.exceptions import CustomException
from app.modules.mcp_gateway.system.crud import BizSystemCRUD
from app.modules.mcp_gateway.system.model import BizSystemModel
from app.modules.mcp_gateway.user.crud import BizUserCRUD
from app.utils.common_util import search_to_dict

from .crud import BizBindingCRUD
from .schema import BizBindingCreateSchema, BizBindingOutSchema, BizBindingQueryParam, BizBindingUpdateSchema


class BizBindingService:
    """业务用户与业务系统的绑定。一个用户在一个系统上只有一条。"""

    def __init__(self, auth: AuthSchema, db: AsyncSession) -> None:
        self.auth = auth
        self.db = db

    async def page(
        self,
        page_no: int,
        page_size: int,
        search: BizBindingQueryParam | None = None,
        order_by: list[dict[str, str]] | None = None,
    ) -> PageResultSchema[BizBindingOutSchema]:
        offset = (page_no - 1) * page_size
        return await BizBindingCRUD(self.auth, self.db).page(
            offset=offset,
            limit=page_size,
            order_by=order_by or [{"id": "asc"}],
            search=search_to_dict(search, {}),
            out_schema=BizBindingOutSchema,
        )

    async def detail(self, binding_id: int) -> BizBindingOutSchema:
        return await BizBindingCRUD(self.auth, self.db).get_or_404(id=binding_id, msg="绑定不存在", out_schema=BizBindingOutSchema)

    async def upsert(self, data: BizBindingCreateSchema) -> BizBindingOutSchema:
        """创建绑定。同一 (user_id, system_id) 已存在时拒绝，不覆盖、不新增第二条。"""
        await self._require_user(data.user_id)
        system = await self._require_system(data.system_id)
        self._ensure_attr_keys(system.attr_fields, data.attrs)
        if await BizBindingCRUD(self.auth, self.db).exists(user_id=data.user_id, system_id=data.system_id):
            raise CustomException(msg="该用户在此业务系统上已有绑定")
        obj = await BizBindingCRUD(self.auth, self.db).create(data=data)
        return BizBindingOutSchema.model_validate(obj)

    async def update(self, binding_id: int, data: BizBindingUpdateSchema) -> BizBindingOutSchema:
        """只更新这一行。停用时不改该用户在其他系统上的绑定。"""
        current = await BizBindingCRUD(self.auth, self.db).get(id=binding_id)
        if current is None:
            raise CustomException(msg="绑定不存在")
        submitted = data.model_dump(exclude_unset=True)
        if "user_id" in submitted and submitted["user_id"] != current.user_id:
            raise CustomException(msg="不能修改绑定所属用户")
        if "system_id" in submitted and submitted["system_id"] != current.system_id:
            raise CustomException(msg="不能修改绑定所属系统")
        if "attrs" in submitted and submitted["attrs"] is not None:
            system = await self._require_system(current.system_id)
            self._ensure_attr_keys(system.attr_fields, submitted["attrs"])
        obj = await BizBindingCRUD(self.auth, self.db).update(id=binding_id, data=data)
        return BizBindingOutSchema.model_validate(obj)

    async def _require_user(self, user_id: int) -> None:
        user = await BizUserCRUD(self.auth, self.db).get(id=user_id)
        if user is None:
            raise CustomException(msg="业务用户不存在")

    async def _require_system(self, system_id: int) -> BizSystemModel:
        system = await BizSystemCRUD(self.auth, self.db).get(id=system_id)
        if system is None:
            raise CustomException(msg="业务系统不存在")
        return system

    @staticmethod
    def _ensure_attr_keys(attr_fields: list[Any] | None, attrs: dict[str, Any] | None) -> None:
        allowed = {str(item) for item in (attr_fields or [])}
        unknown = sorted(set(attrs or []) - allowed)
        if unknown:
            raise CustomException(msg="绑定属性包含系统未声明的字段")
