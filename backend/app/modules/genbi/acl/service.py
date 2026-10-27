"""MCP 组勾选数据源 + 每源共享 ACL（无成员）。"""

from __future__ import annotations

from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.base_schema import AuthSchema, PageResultSchema
from app.core.exceptions import CustomException
from app.modules.genbi.datasource.crud import GenbiDatasourceCRUD
from app.modules.mcp_gateway.mcp_group.crud import McpGroupCRUD
from app.utils.common_util import search_to_dict

from .crud import (
    GenbiGroupDatasourceAclColumnCRUD,
    GenbiGroupDatasourceAclRowCRUD,
    GenbiGroupDatasourceCRUD,
)
from .model import GenbiGroupDatasourceAclColumnModel, GenbiGroupDatasourceAclRowModel
from .schema import (
    GenbiAclColumnPolicyIn,
    GenbiAclRowPolicyIn,
    GenbiGroupDatasourceAclOut,
    GenbiGroupDatasourceAclSave,
    GenbiGroupDatasourceOut,
    GenbiGroupDatasourceQueryParam,
    GenbiGroupDatasourceUpdate,
)


class GenbiGroupDatasourceService:
    """组–数据源关联与 ACL 读写。"""

    def __init__(self, auth: AuthSchema, db: AsyncSession) -> None:
        self.auth = auth
        self.db = db

    async def page(
        self,
        page_no: int,
        page_size: int,
        search: GenbiGroupDatasourceQueryParam | None = None,
        order_by: list[dict[str, str]] | None = None,
    ) -> PageResultSchema[GenbiGroupDatasourceOut]:
        offset = (page_no - 1) * page_size
        return await GenbiGroupDatasourceCRUD(self.auth, self.db).page(
            offset=offset,
            limit=page_size,
            order_by=order_by or [{"id": "asc"}],
            search=search_to_dict(search, {}),
            out_schema=GenbiGroupDatasourceOut,
        )

    async def attach(
        self,
        *,
        group_id: int,
        datasource_id: int,
        external_name: str | None = None,
        enabled: bool = True,
    ) -> GenbiGroupDatasourceOut:
        await self._require_group(group_id)
        ds = await GenbiDatasourceCRUD(self.auth, self.db).get(id=datasource_id)
        if ds is None:
            raise CustomException(msg="数据源不存在")
        if (external_name or "").strip():
            name = (external_name or "").strip()
        else:
            from app.modules.genbi.runtime_tool import suggest_external_name

            name = await suggest_external_name(self.auth, self.db, datasource_id)
        await self._require_unique_external_name(group_id, name)
        existing = await GenbiGroupDatasourceCRUD(self.auth, self.db).get(
            group_id=group_id, datasource_id=datasource_id
        )
        if existing is not None:
            obj = await GenbiGroupDatasourceCRUD(self.auth, self.db).update(
                id=existing.id,
                data={"external_name": name, "enabled": enabled},
            )
            return GenbiGroupDatasourceOut.model_validate(obj)
        obj = await GenbiGroupDatasourceCRUD(self.auth, self.db).create(
            data={
                "group_id": group_id,
                "datasource_id": datasource_id,
                "external_name": name,
                "enabled": enabled,
            }
        )
        return GenbiGroupDatasourceOut.model_validate(obj)

    async def update(self, link_id: int, data: GenbiGroupDatasourceUpdate) -> GenbiGroupDatasourceOut:
        current = await GenbiGroupDatasourceCRUD(self.auth, self.db).get(id=link_id)
        if current is None:
            raise CustomException(msg="组数据源关联不存在")
        payload = data.model_dump(exclude_unset=True, exclude_none=True)
        if "external_name" in data.model_fields_set:
            name = (data.external_name or "").strip()
            if not name:
                raise CustomException(msg="对外工具名不能为空")
            payload["external_name"] = name
            await self._require_unique_external_name(
                current.group_id, name, exclude_id=current.id
            )
        if not payload:
            return GenbiGroupDatasourceOut.model_validate(current)
        obj = await GenbiGroupDatasourceCRUD(self.auth, self.db).update(id=link_id, data=payload)
        return GenbiGroupDatasourceOut.model_validate(obj)

    async def save_acl(self, link_id: int, data: GenbiGroupDatasourceAclSave) -> GenbiGroupDatasourceAclOut:
        link = await GenbiGroupDatasourceCRUD(self.auth, self.db).get(id=link_id)
        if link is None:
            raise CustomException(msg="组数据源关联不存在")
        await self.db.execute(
            delete(GenbiGroupDatasourceAclRowModel).where(
                GenbiGroupDatasourceAclRowModel.group_datasource_id == link_id
            )
        )
        await self.db.execute(
            delete(GenbiGroupDatasourceAclColumnModel).where(
                GenbiGroupDatasourceAclColumnModel.group_datasource_id == link_id
            )
        )
        row_crud = GenbiGroupDatasourceAclRowCRUD(self.auth, self.db)
        for policy in data.row_policies:
            await row_crud.create(
                data={
                    "group_datasource_id": link_id,
                    "model_id": policy.model_id,
                    "column_id": policy.column_id,
                    "operator": policy.operator,
                    "values": list(policy.values),
                    "propagate": policy.propagate,
                    "propagate_to_model_ids": list(policy.propagate_to_model_ids),
                }
            )
        col_crud = GenbiGroupDatasourceAclColumnCRUD(self.auth, self.db)
        for policy in data.column_policies:
            await col_crud.create(
                data={
                    "group_datasource_id": link_id,
                    "model_id": policy.model_id,
                    "column_id": policy.column_id,
                    "action": policy.action,
                    "mask_template": policy.mask_template,
                }
            )
        return await self.get_acl(link_id)

    async def get_acl(self, link_id: int) -> GenbiGroupDatasourceAclOut:
        link = await GenbiGroupDatasourceCRUD(self.auth, self.db).get(id=link_id)
        if link is None:
            raise CustomException(msg="组数据源关联不存在")
        rows = await GenbiGroupDatasourceAclRowCRUD(self.auth, self.db).get_list(
            search={"group_datasource_id": link_id},
            order_by=[{"id": "asc"}],
        )
        cols = await GenbiGroupDatasourceAclColumnCRUD(self.auth, self.db).get_list(
            search={"group_datasource_id": link_id},
            order_by=[{"id": "asc"}],
        )
        return GenbiGroupDatasourceAclOut(
            group_datasource_id=link_id,
            group_id=link.group_id,
            datasource_id=link.datasource_id,
            row_policies=[
                GenbiAclRowPolicyIn(
                    model_id=r.model_id,
                    column_id=r.column_id,
                    operator=r.operator,  # type: ignore[arg-type]
                    values=list(r.values or []),
                    propagate=bool(r.propagate),
                    propagate_to_model_ids=[int(x) for x in (r.propagate_to_model_ids or [])],
                )
                for r in rows
            ],
            column_policies=[
                GenbiAclColumnPolicyIn(
                    model_id=c.model_id,
                    column_id=c.column_id,
                    action=c.action,  # type: ignore[arg-type]
                    mask_template=c.mask_template,  # type: ignore[arg-type]
                )
                for c in cols
            ],
        )

    async def count_for_group(self, group_id: int) -> int:
        rows = await GenbiGroupDatasourceCRUD(self.auth, self.db).get_list(
            search={"group_id": group_id},
        )
        return len(rows)

    @staticmethod
    def _default_external_name(datasource_name: str) -> str:
        slug = "".join(ch if ch.isalnum() or ch in "_-" else "_" for ch in datasource_name.strip())
        slug = slug.strip("_") or "ds"
        return f"{slug}_ask_bi"

    async def _require_group(self, group_id: int) -> None:
        group = await McpGroupCRUD(self.auth, self.db).get(id=group_id)
        if group is None:
            raise CustomException(msg="MCP 组不存在")

    async def _require_unique_external_name(
        self, group_id: int, external_name: str, *, exclude_id: int | None = None
    ) -> None:
        rows = await GenbiGroupDatasourceCRUD(self.auth, self.db).get_list(
            search={"group_id": group_id, "external_name": external_name},
        )
        for row in rows:
            if exclude_id is not None and row.id == exclude_id:
                continue
            raise CustomException(msg="外部名称已存在")
        from app.modules.mcp_gateway.mcp_group.crud import McpGroupToolCRUD

        tool_rows = await McpGroupToolCRUD(self.auth, self.db).get_list(
            search={"group_id": group_id, "external_name": external_name},
        )
        if tool_rows:
            raise CustomException(msg="外部名称已存在")
