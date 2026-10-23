from sqlalchemy.ext.asyncio import AsyncSession

from app.core.base_schema import AuthSchema, PageResultSchema
from app.core.exceptions import CustomException
from app.modules.mcp_gateway.system.crud import BizSystemCRUD
from app.utils.common_util import search_to_dict

from .crud import AuthConfigCRUD
from .schema import (
    AuthConfigCreateSchema,
    AuthConfigOutSchema,
    AuthConfigQueryParam,
    AuthConfigUpdateSchema,
    ensure_method_fields,
)


class AuthConfigService:
    """业务系统鉴权配置。一个系统同时只有一条启用中的配置。"""

    def __init__(self, auth: AuthSchema, db: AsyncSession) -> None:
        self.auth = auth
        self.db = db

    async def page(
        self,
        page_no: int,
        page_size: int,
        search: AuthConfigQueryParam | None = None,
        order_by: list[dict[str, str]] | None = None,
    ) -> PageResultSchema[AuthConfigOutSchema]:
        offset = (page_no - 1) * page_size
        return await AuthConfigCRUD(self.auth, self.db).page(
            offset=offset,
            limit=page_size,
            order_by=order_by or [{"id": "asc"}],
            search=search_to_dict(search, {}),
            out_schema=AuthConfigOutSchema,
        )

    async def detail(self, config_id: int) -> AuthConfigOutSchema:
        return await AuthConfigCRUD(self.auth, self.db).get_or_404(id=config_id, msg="鉴权配置不存在", out_schema=AuthConfigOutSchema)

    async def create(self, data: AuthConfigCreateSchema) -> AuthConfigOutSchema:
        await self._require_system(data.system_id)
        self._validate_method_fields(data.method, data.http_method, data.username, data.password)
        await self._lock_systems(data.system_id)
        if data.enabled:
            await self._disable_others(data.system_id, keep_id=None)
        obj = await AuthConfigCRUD(self.auth, self.db).create(data=data)
        return AuthConfigOutSchema.model_validate(obj)

    async def update(self, config_id: int, data: AuthConfigUpdateSchema) -> AuthConfigOutSchema:
        current = await AuthConfigCRUD(self.auth, self.db).get(id=config_id)
        if current is None:
            raise CustomException(msg="鉴权配置不存在")
        submitted = data.model_dump(exclude_unset=True)
        system_id = submitted.get("system_id", current.system_id)
        if system_id != current.system_id:
            await self._require_system(system_id)
        method = submitted.get("method", current.method)
        http_method = submitted.get("http_method", current.http_method)
        username = submitted.get("username", current.username)
        password = submitted.get("password", current.password)
        self._validate_method_fields(method, http_method, username, password)
        enabled = submitted.get("enabled", current.enabled)
        await self._lock_systems(current.system_id, system_id)
        if enabled:
            await self._disable_others(system_id, keep_id=config_id)
        obj = await AuthConfigCRUD(self.auth, self.db).update(id=config_id, data=data)
        return AuthConfigOutSchema.model_validate(obj)

    async def _require_system(self, system_id: int) -> None:
        system = await BizSystemCRUD(self.auth, self.db).get(id=system_id)
        if system is None:
            raise CustomException(msg="业务系统不存在")

    async def _lock_systems(self, *system_ids: int) -> None:
        """按系统 ID 顺序锁鉴权行，两次并发保存会排成一队。"""
        crud = AuthConfigCRUD(self.auth, self.db)
        for system_id in sorted(set(system_ids)):
            await crud.lock_system_rows(system_id)

    async def _disable_others(self, system_id: int, keep_id: int | None) -> None:
        """保存一条启用配置时，把该系统其他配置改成未启用。"""
        rows = await AuthConfigCRUD(self.auth, self.db).get_list(search={"system_id": system_id, "enabled": True})
        changed = False
        for row in rows:
            if keep_id is not None and row.id == keep_id:
                continue
            row.enabled = False
            changed = True
        if changed:
            await self.db.flush()

    @staticmethod
    def _validate_method_fields(
        method: str,
        http_method: str | None,
        username: str | None,
        password: str | None,
    ) -> None:
        try:
            ensure_method_fields(method, http_method, username, password)
        except ValueError as exc:
            raise CustomException(msg=str(exc)) from exc
