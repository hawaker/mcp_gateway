from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.base_schema import AuthSchema, PageResultSchema
from app.core.exceptions import CustomException
from app.modules.genbi.datasource.crud import GenbiDatasourceCRUD
from app.utils.common_util import search_to_dict

from .crud import GenbiProjectCRUD
from .model import GenbiProjectModel
from .schema import GenbiProjectOut, GenbiProjectQueryParam


class GenbiProjectService:
    """GenBI 项目管理。一数据源一项目。"""

    def __init__(self, auth: AuthSchema, db: AsyncSession) -> None:
        self.auth = auth
        self.db = db

    async def list(
        self,
        page_no: int,
        page_size: int,
        search: GenbiProjectQueryParam | None = None,
        order_by: list[dict[str, str]] | None = None,
    ) -> PageResultSchema[GenbiProjectOut]:
        offset = (page_no - 1) * page_size
        return await GenbiProjectCRUD(self.auth, self.db).page(
            offset=offset,
            limit=page_size,
            order_by=order_by or [{"id": "asc"}],
            search=search_to_dict(search, {}),
            out_schema=GenbiProjectOut,
        )

    async def get(self, project_id: int) -> GenbiProjectOut:
        return await GenbiProjectCRUD(self.auth, self.db).get_or_404(
            id=project_id,
            msg="项目不存在",
            out_schema=GenbiProjectOut,
        )

    async def create(
        self,
        *,
        datasource_id: int,
        display_name: str,
        system_id: int | None = None,
        onboarding_status: str = "not_started",
        language: str = "zh-CN",
        agent_profile: dict[str, Any] | None = None,
    ) -> GenbiProjectModel:
        ds = await GenbiDatasourceCRUD(self.auth, self.db).get(id=datasource_id)
        if ds is None:
            raise CustomException(msg="数据源不存在")

        if await GenbiProjectCRUD(self.auth, self.db).exists(datasource_id=datasource_id):
            raise CustomException(msg="该数据源已存在项目，不可重复创建")

        payload: dict[str, Any] = {
            "datasource_id": datasource_id,
            "system_id": system_id if system_id is not None else ds.system_id,
            "display_name": display_name.strip(),
            "onboarding_status": onboarding_status or "not_started",
            "language": language or "zh-CN",
            "agent_profile": agent_profile if isinstance(agent_profile, dict) else {},
        }
        return await GenbiProjectCRUD(self.auth, self.db).create(data=payload)
