from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.base_schema import AuthSchema, PageResultSchema
from app.core.exceptions import CustomException
from app.modules.genbi.datasource.crud import GenbiDatasourceCRUD
from app.modules.genbi.datasource.model import GenbiDatasourceModel
from app.utils.common_util import search_to_dict

from .crud import GenbiProjectCRUD
from .mdl_builder import build_mdl_manifest, create_mdl_hash
from .model import (
    GenbiDeployLogModel,
    GenbiInstructionModel,
    GenbiMetricDocModel,
    GenbiModelColumnModel,
    GenbiModelModel,
    GenbiProjectModel,
    GenbiRelationshipModel,
    GenbiSqlPairModel,
)
from .schema import (
    GenbiAgentProfileOut,
    GenbiAgentProfileUpdate,
    GenbiInstructionCreate,
    GenbiInstructionOut,
    GenbiInstructionUpdate,
    GenbiMetricDocCreate,
    GenbiMetricDocOut,
    GenbiMetricDocUpdate,
    GenbiModelIn,
    GenbiModelOut,
    GenbiProjectOut,
    GenbiProjectQueryParam,
    GenbiProjectUpdate,
    GenbiRelationshipIn,
    GenbiRelationshipOut,
    GenbiSqlPairCreate,
    GenbiSqlPairOut,
    GenbiSqlPairUpdate,
)
from .wren_client import WrenClient, get_wren_client


class GenbiProjectService:
    """GenBI 项目管理、MDL 同步与部署。一数据源一项目。"""

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

    async def _get_project_row(self, project_id: int) -> GenbiProjectModel:
        row = await GenbiProjectCRUD(self.auth, self.db).get(id=project_id)
        if row is None:
            raise CustomException(msg="项目不存在")
        return row

    async def update(self, project_id: int, data: GenbiProjectUpdate) -> GenbiProjectOut:
        project = await self._get_project_row(project_id)
        payload = data.model_dump(exclude_unset=True)
        if "display_name" in payload and payload["display_name"] is not None:
            payload["display_name"] = str(payload["display_name"]).strip()
        for key, value in payload.items():
            setattr(project, key, value)
        await self.db.flush()
        await self.db.refresh(project)
        return GenbiProjectOut.model_validate(project)

    @staticmethod
    def _profile_from_dict(raw: dict[str, Any] | None) -> GenbiAgentProfileOut:
        data = raw if isinstance(raw, dict) else {}
        return GenbiAgentProfileOut(
            llm_model_id=data.get("llm_model_id"),
            instructions=list(data.get("instructions") or []),
            tools_config=list(data.get("tools_config") or []),
            mcp_config=list(data.get("mcp_config") or []),
            skills_config=dict(data.get("skills_config") or {}),
            knowledge_config=dict(data.get("knowledge_config") or {}),
            virtual_agent_id=str(data.get("virtual_agent_id") or ""),
        )

    async def get_agent_profile(self, project_id: int) -> GenbiAgentProfileOut:
        project = await self._get_project_row(project_id)
        return self._profile_from_dict(project.agent_profile)

    async def patch_agent_profile(
        self, project_id: int, data: GenbiAgentProfileUpdate
    ) -> GenbiAgentProfileOut:
        project = await self._get_project_row(project_id)
        current = dict(project.agent_profile or {})
        patch = data.model_dump(exclude_unset=True)
        current.update(patch)
        project.agent_profile = current
        await self.db.flush()
        await self.db.refresh(project)
        return self._profile_from_dict(project.agent_profile)

    async def list_models(self, project_id: int) -> list[GenbiModelOut]:
        await self._get_project_row(project_id)
        result = await self.db.execute(
            select(GenbiModelModel)
            .where(
                GenbiModelModel.project_id == project_id,
                GenbiModelModel.is_deleted == False,  # noqa: E712
            )
            .options(selectinload(GenbiModelModel.columns))
            .order_by(GenbiModelModel.id)
        )
        rows = list(result.scalars().all())
        return [GenbiModelOut.model_validate(r) for r in rows]

    async def sync_models(
        self,
        *,
        project_id: int,
        models: list[GenbiModelIn] | list[dict[str, Any]],
    ) -> list[GenbiModelModel]:
        """Replace all MDL models/columns for a project (enough to mark deployable)."""
        project = await self._get_project_row(project_id)
        if not models:
            raise CustomException(msg="至少需要一个 MDL 模型")

        parsed: list[GenbiModelIn] = [
            m if isinstance(m, GenbiModelIn) else GenbiModelIn.model_validate(m) for m in models
        ]

        # Hard-replace: cascade deletes columns via FK.
        await self.db.execute(
            delete(GenbiRelationshipModel).where(GenbiRelationshipModel.project_id == project.id)
        )
        await self.db.execute(delete(GenbiModelModel).where(GenbiModelModel.project_id == project.id))
        await self.db.flush()

        created: list[GenbiModelModel] = []
        used_refs: set[str] = set()
        for item in parsed:
            ref = item.reference_name.strip()
            if not ref:
                raise CustomException(msg="模型引用名不能为空")
            if ref in used_refs:
                raise CustomException(msg=f"模型引用名重复: {ref}")
            used_refs.add(ref)
            model = GenbiModelModel(
                project_id=project.id,
                display_name=item.display_name.strip(),
                source_table_name=item.source_table_name.strip(),
                reference_name=ref,
                ref_sql=item.ref_sql,
                cached=bool(item.cached),
                refresh_time=item.refresh_time,
                properties=item.properties,
            )
            self.db.add(model)
            await self.db.flush()
            for col in item.columns:
                self.db.add(
                    GenbiModelColumnModel(
                        model_id=model.id,
                        display_name=col.display_name.strip(),
                        source_column_name=col.source_column_name.strip(),
                        column_type=col.column_type,
                        is_calculated=bool(col.is_calculated),
                        expression=col.expression,
                        properties=col.properties,
                    )
                )
            await self.db.flush()
            await self.db.refresh(model, attribute_names=["columns"])
            created.append(model)

        if project.onboarding_status in ("not_started", "draft", ""):
            project.onboarding_status = "modeling"
            await self.db.flush()

        return created

    async def deploy(
        self,
        *,
        project_id: int,
        force: bool = False,
        wren_client: WrenClient | None = None,
    ) -> GenbiDeployLogModel:
        """Deploy MDL to Wren/pgvector index; require at least one model."""
        project = await self._get_project_row(project_id)
        result = await self.db.execute(
            select(GenbiModelModel)
            .where(
                GenbiModelModel.project_id == project.id,
                GenbiModelModel.is_deleted == False,  # noqa: E712
            )
            .options(selectinload(GenbiModelModel.columns))
        )
        models = list(result.scalars().all())
        if not models:
            raise CustomException(msg="项目尚未配置 MDL 模型，无法部署")

        ds: GenbiDatasourceModel | None = await GenbiDatasourceCRUD(self.auth, self.db).get(
            id=project.datasource_id
        )
        rels = list(
            (
                await self.db.execute(
                    select(GenbiRelationshipModel).where(
                        GenbiRelationshipModel.project_id == project.id,
                        GenbiRelationshipModel.is_deleted == False,  # noqa: E712
                    )
                )
            )
            .scalars()
            .all()
        )
        manifest = build_mdl_manifest(
            project=project,
            datasource=ds,
            models=models,
            relationships=rels,
        )
        mdl_hash = create_mdl_hash(manifest, project.id)

        if not force:
            latest = (
                await self.db.execute(
                    select(GenbiDeployLogModel)
                    .where(GenbiDeployLogModel.project_id == project.id)
                    .order_by(GenbiDeployLogModel.id.desc())
                    .limit(1)
                )
            ).scalars().first()
            if latest and latest.mdl_hash == mdl_hash and latest.status == "success":
                return latest

        client = wren_client or get_wren_client()
        try:
            deploy_result = await client.deploy_semantics(
                project_id=project.id,
                mdl_hash=mdl_hash,
                manifest=manifest,
            )
        except Exception as exc:  # noqa: BLE001 - surface as deploy failure
            log = GenbiDeployLogModel(
                project_id=project.id,
                mdl_hash=mdl_hash,
                status="failed",
                stage="indexing",
                error=str(exc),
            )
            self.db.add(log)
            await self.db.flush()
            await self.db.refresh(log)
            raise CustomException(msg=f"部署失败: {exc}") from exc

        now = datetime.now(UTC)
        log = GenbiDeployLogModel(
            project_id=project.id,
            mdl_hash=deploy_result.mdl_hash or mdl_hash,
            status="success",
            stage="done",
            deployed_at=now,
        )
        self.db.add(log)
        project.onboarding_status = "deployed"
        await self.db.flush()
        await self.db.refresh(log)
        return log

    async def list_deploy_logs(self, project_id: int, *, limit: int = 20) -> list[GenbiDeployLogModel]:
        await self._get_project_row(project_id)
        result = await self.db.execute(
            select(GenbiDeployLogModel)
            .where(
                GenbiDeployLogModel.project_id == project_id,
                GenbiDeployLogModel.is_deleted == False,  # noqa: E712
            )
            .order_by(GenbiDeployLogModel.id.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def list_relationships(self, project_id: int) -> list[GenbiRelationshipOut]:
        await self._get_project_row(project_id)
        result = await self.db.execute(
            select(GenbiRelationshipModel)
            .where(
                GenbiRelationshipModel.project_id == project_id,
                GenbiRelationshipModel.is_deleted == False,  # noqa: E712
            )
            .order_by(GenbiRelationshipModel.id)
        )
        return [GenbiRelationshipOut.model_validate(r) for r in result.scalars().all()]

    async def sync_relationships(
        self,
        *,
        project_id: int,
        relationships: list[GenbiRelationshipIn] | list[dict[str, Any]],
    ) -> list[GenbiRelationshipModel]:
        project = await self._get_project_row(project_id)
        model_ids = {
            m.id
            for m in (
                await self.db.execute(
                    select(GenbiModelModel).where(
                        GenbiModelModel.project_id == project.id,
                        GenbiModelModel.is_deleted == False,  # noqa: E712
                    )
                )
            )
            .scalars()
            .all()
        }
        parsed = [
            r if isinstance(r, GenbiRelationshipIn) else GenbiRelationshipIn.model_validate(r)
            for r in relationships
        ]
        for item in parsed:
            if item.from_model_id not in model_ids or item.to_model_id not in model_ids:
                raise CustomException(msg="关系引用的模型不存在或不属于本项目")

        await self.db.execute(
            delete(GenbiRelationshipModel).where(GenbiRelationshipModel.project_id == project.id)
        )
        await self.db.flush()
        created: list[GenbiRelationshipModel] = []
        for item in parsed:
            row = GenbiRelationshipModel(
                project_id=project.id,
                from_model_id=item.from_model_id,
                to_model_id=item.to_model_id,
                join_type=item.join_type,
                condition=item.condition,
                properties=item.properties,
            )
            self.db.add(row)
            created.append(row)
        await self.db.flush()
        for row in created:
            await self.db.refresh(row)
        return created

    async def list_instructions(self, project_id: int) -> list[GenbiInstructionOut]:
        await self._get_project_row(project_id)
        result = await self.db.execute(
            select(GenbiInstructionModel)
            .where(
                GenbiInstructionModel.project_id == project_id,
                GenbiInstructionModel.is_deleted == False,  # noqa: E712
            )
            .order_by(GenbiInstructionModel.id)
        )
        return [GenbiInstructionOut.model_validate(r) for r in result.scalars().all()]

    async def create_instruction(
        self, project_id: int, data: GenbiInstructionCreate
    ) -> GenbiInstructionModel:
        await self._get_project_row(project_id)
        row = GenbiInstructionModel(
            project_id=project_id,
            instruction=data.instruction,
            questions=data.questions,
            is_default=bool(data.is_default),
        )
        self.db.add(row)
        await self.db.flush()
        await self.db.refresh(row)
        return row

    async def update_instruction(
        self, project_id: int, instruction_id: int, data: GenbiInstructionUpdate
    ) -> GenbiInstructionModel:
        row = await self._get_knowledge_row(GenbiInstructionModel, project_id, instruction_id, "指令")
        for key, value in data.model_dump(exclude_unset=True).items():
            setattr(row, key, value)
        await self.db.flush()
        await self.db.refresh(row)
        return row

    async def delete_instruction(self, project_id: int, instruction_id: int) -> None:
        row = await self._get_knowledge_row(GenbiInstructionModel, project_id, instruction_id, "指令")
        row.is_deleted = True
        row.deleted_time = datetime.now(UTC)
        await self.db.flush()

    async def list_metric_docs(self, project_id: int) -> list[GenbiMetricDocOut]:
        await self._get_project_row(project_id)
        result = await self.db.execute(
            select(GenbiMetricDocModel)
            .where(
                GenbiMetricDocModel.project_id == project_id,
                GenbiMetricDocModel.is_deleted == False,  # noqa: E712
            )
            .order_by(GenbiMetricDocModel.id)
        )
        return [GenbiMetricDocOut.model_validate(r) for r in result.scalars().all()]

    async def create_metric_doc(
        self, project_id: int, data: GenbiMetricDocCreate
    ) -> GenbiMetricDocModel:
        await self._get_project_row(project_id)
        row = GenbiMetricDocModel(
            project_id=project_id,
            name=data.name,
            content=data.content,
            enabled=bool(data.enabled),
        )
        self.db.add(row)
        await self.db.flush()
        await self.db.refresh(row)
        return row

    async def update_metric_doc(
        self, project_id: int, doc_id: int, data: GenbiMetricDocUpdate
    ) -> GenbiMetricDocModel:
        row = await self._get_knowledge_row(GenbiMetricDocModel, project_id, doc_id, "指标文档")
        for key, value in data.model_dump(exclude_unset=True).items():
            setattr(row, key, value)
        await self.db.flush()
        await self.db.refresh(row)
        return row

    async def delete_metric_doc(self, project_id: int, doc_id: int) -> None:
        row = await self._get_knowledge_row(GenbiMetricDocModel, project_id, doc_id, "指标文档")
        row.is_deleted = True
        row.deleted_time = datetime.now(UTC)
        await self.db.flush()

    async def list_sql_pairs(self, project_id: int) -> list[GenbiSqlPairOut]:
        await self._get_project_row(project_id)
        result = await self.db.execute(
            select(GenbiSqlPairModel)
            .where(
                GenbiSqlPairModel.project_id == project_id,
                GenbiSqlPairModel.is_deleted == False,  # noqa: E712
            )
            .order_by(GenbiSqlPairModel.id)
        )
        return [GenbiSqlPairOut.model_validate(r) for r in result.scalars().all()]

    async def create_sql_pair(self, project_id: int, data: GenbiSqlPairCreate) -> GenbiSqlPairModel:
        await self._get_project_row(project_id)
        row = GenbiSqlPairModel(
            project_id=project_id,
            question=data.question,
            sql=data.sql,
            enabled=bool(data.enabled),
        )
        self.db.add(row)
        await self.db.flush()
        await self.db.refresh(row)
        return row

    async def update_sql_pair(
        self, project_id: int, pair_id: int, data: GenbiSqlPairUpdate
    ) -> GenbiSqlPairModel:
        row = await self._get_knowledge_row(GenbiSqlPairModel, project_id, pair_id, "SQL 问答对")
        for key, value in data.model_dump(exclude_unset=True).items():
            setattr(row, key, value)
        await self.db.flush()
        await self.db.refresh(row)
        return row

    async def delete_sql_pair(self, project_id: int, pair_id: int) -> None:
        row = await self._get_knowledge_row(GenbiSqlPairModel, project_id, pair_id, "SQL 问答对")
        row.is_deleted = True
        row.deleted_time = datetime.now(UTC)
        await self.db.flush()

    async def _get_knowledge_row(
        self,
        model: type[Any],
        project_id: int,
        row_id: int,
        label: str,
    ) -> Any:
        await self._get_project_row(project_id)
        row = (
            await self.db.execute(
                select(model).where(
                    model.id == row_id,
                    model.project_id == project_id,
                    model.is_deleted == False,  # noqa: E712
                )
            )
        ).scalars().first()
        if row is None:
            raise CustomException(msg=f"{label}不存在")
        return row
