from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.base_schema import AuthSchema, PageResultSchema
from app.core.exceptions import CustomException
from app.modules.mcp_gateway.system.crud import BizSystemCRUD
from app.utils.common_util import search_to_dict
from app.utils.crypto_util import CryptoUtil

from .crud import GenbiDatasourceCRUD
from .model import GenbiDatasourceModel
from .schema import GenbiDatasourceOut, GenbiDatasourceQueryParam, GenbiDatasourceUpdate
from .types import WREN_TYPES

_SECRET_FIELDS = ("password", "api_key", "private_key", "token")


class GenbiDatasourceService:
    """GenBI 数据源管理。密钥入参明文，落库密文；出参永不回传密钥。"""

    def __init__(self, auth: AuthSchema, db: AsyncSession) -> None:
        self.auth = auth
        self.db = db

    async def list(
        self,
        page_no: int,
        page_size: int,
        search: GenbiDatasourceQueryParam | None = None,
        order_by: list[dict[str, str]] | None = None,
    ) -> PageResultSchema[GenbiDatasourceOut]:
        offset = (page_no - 1) * page_size
        return await GenbiDatasourceCRUD(self.auth, self.db).page(
            offset=offset,
            limit=page_size,
            order_by=order_by or [{"id": "asc"}],
            search=search_to_dict(search, {}),
            out_schema=GenbiDatasourceOut,
        )

    async def get(self, datasource_id: int) -> GenbiDatasourceOut:
        return await GenbiDatasourceCRUD(self.auth, self.db).get_or_404(
            id=datasource_id,
            msg="数据源不存在",
            out_schema=GenbiDatasourceOut,
        )

    async def create(
        self,
        *,
        system_id: int,
        name: str,
        wren_type: str,
        host: str | None = None,
        port: int | None = None,
        username: str | None = None,
        password: str | None = None,
        database: str | None = None,
        db_schema: str | None = None,
        url: str | None = None,
        api_key: str | None = None,
        private_key: str | None = None,
        token: str | None = None,
        config: dict[str, Any] | None = None,
        description: str | None = None,
        enabled: bool = True,
    ) -> GenbiDatasourceModel:
        wren_type = self._normalize_wren_type(wren_type)
        if not await BizSystemCRUD(self.auth, self.db).exists(id=system_id):
            raise CustomException(msg="业务系统不存在")
        payload: dict[str, Any] = {
            "system_id": system_id,
            "name": name.strip(),
            "wren_type": wren_type,
            "host": host,
            "port": port,
            "username": username,
            "database": database,
            "db_schema": db_schema,
            "url": url,
            "config": config if isinstance(config, dict) else {},
            "description": description,
            "enabled": enabled,
            **self._encrypt_secrets(
                password=password,
                api_key=api_key,
                private_key=private_key,
                token=token,
            ),
        }
        return await GenbiDatasourceCRUD(self.auth, self.db).create(data=payload)

    async def update(self, datasource_id: int, data: GenbiDatasourceUpdate) -> GenbiDatasourceOut:
        current = await GenbiDatasourceCRUD(self.auth, self.db).get(id=datasource_id)
        if current is None:
            raise CustomException(msg="数据源不存在")
        payload = data.model_dump(exclude_unset=True)
        if "wren_type" in payload and payload["wren_type"] is not None:
            payload["wren_type"] = self._normalize_wren_type(payload["wren_type"])
        secrets = {key: payload.pop(key) for key in list(payload) if key in _SECRET_FIELDS}
        payload.update(self._encrypt_secrets(**secrets, only_present=True))
        if not payload:
            return GenbiDatasourceOut.model_validate(current)
        obj = await GenbiDatasourceCRUD(self.auth, self.db).update(id=datasource_id, data=payload)
        return GenbiDatasourceOut.model_validate(obj)

    async def delete(self, ids: list[int]) -> None:
        if not ids:
            raise CustomException(msg="删除失败，删除对象不能为空")
        crud = GenbiDatasourceCRUD(self.auth, self.db)
        rows = await crud.get_list(search={"id": ("in", ids)})
        found = {row.id for row in rows}
        for datasource_id in ids:
            if datasource_id not in found:
                raise CustomException(msg="数据源不存在")
        await crud.delete(ids=ids)

    @staticmethod
    def _normalize_wren_type(wren_type: str) -> str:
        key = (wren_type or "").strip().upper()
        if key not in WREN_TYPES:
            raise CustomException(msg="不支持的数据源类型")
        return key

    @staticmethod
    def _encrypt_secrets(
        *,
        password: str | None = None,
        api_key: str | None = None,
        private_key: str | None = None,
        token: str | None = None,
        only_present: bool = False,
    ) -> dict[str, str | None]:
        raw = {
            "password_encrypted": password,
            "api_key_encrypted": api_key,
            "private_key_encrypted": private_key,
            "token_encrypted": token,
        }
        out: dict[str, str | None] = {}
        for field, value in raw.items():
            if value is None:
                if not only_present:
                    out[field] = None
                continue
            text = value.strip() if isinstance(value, str) else ""
            if not text:
                if only_present:
                    continue
                out[field] = None
                continue
            out[field] = CryptoUtil.encrypt(text)
        return out
