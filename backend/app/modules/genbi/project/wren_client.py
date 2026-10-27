"""Wren / semantics deploy client.

Vector index uses the **existing** application PostgreSQL (pgvector) — see
``settings.genbi_vector_database_url`` / ``GENBI_VECTOR_*`` falling back to
``DATABASE_*``. Do not introduce a second vector DB service.
"""

from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable

logger = logging.getLogger(__name__)

_DEPLOY_POLL_INTERVAL = 2.0
_DEPLOY_POLL_TIMEOUT = 180.0


@dataclass(frozen=True)
class WrenDeployResult:
    """Result of a semantics / vector index deploy."""

    mdl_hash: str
    status: str = "finished"


@runtime_checkable
class WrenClient(Protocol):
    """Deploy MDL semantics / embeddings. Real Wren AI implements this protocol."""

    async def deploy_semantics(
        self,
        *,
        project_id: int,
        mdl_hash: str,
        manifest: dict[str, Any],
    ) -> WrenDeployResult: ...


class StubWrenClient:
    """In-process stub for unit tests and local deploy without Wren services."""

    def __init__(self, *, mdl_hash_suffix: str = "") -> None:
        self.mdl_hash_suffix = mdl_hash_suffix
        self.deploy_calls = 0
        self.last_manifest: dict[str, Any] | None = None

    async def deploy_semantics(
        self,
        *,
        project_id: int,
        mdl_hash: str,
        manifest: dict[str, Any],
    ) -> WrenDeployResult:
        self.deploy_calls += 1
        self.last_manifest = manifest
        final_hash = f"{mdl_hash}{self.mdl_hash_suffix}" if self.mdl_hash_suffix else mdl_hash
        return WrenDeployResult(mdl_hash=final_hash, status="finished")


class SettingsWrenClient:
    """Production client: in-process ``prepare_semantics`` or HTTP Wren AI."""

    async def deploy_semantics(
        self,
        *,
        project_id: int,
        mdl_hash: str,
        manifest: dict[str, Any],
    ) -> WrenDeployResult:
        from app.config.setting import settings

        _ = settings.GENBI_IBIS_ENDPOINT
        _ = settings.GENBI_WREN_ENGINE_ENDPOINT
        _ = settings.genbi_vector_database_url
        if not manifest.get("models"):
            raise ValueError("manifest has no models")

        mdl_json = json.dumps(manifest, ensure_ascii=False)
        project_key = str(project_id)

        from app.modules.genbi.ai.http_client import http_ai_configured, http_prepare_semantics

        if http_ai_configured():
            await http_prepare_semantics(
                mdl=mdl_json,
                mdl_hash=mdl_hash,
                project_id=project_key,
            )
            return WrenDeployResult(mdl_hash=mdl_hash, status="finished")

        try:
            from app.modules.genbi.ai import facade as genbi_ai

            await genbi_ai.prepare_semantics(mdl_json, mdl_hash, project_key)
            ok = await self._wait_semantics_ready(mdl_hash)
            if not ok:
                raise RuntimeError("semantics preparation failed or timed out")
            return WrenDeployResult(mdl_hash=mdl_hash, status="finished")
        except Exception as exc:
            logger.exception("in-process prepare_semantics failed project=%s", project_id)
            raise RuntimeError(
                "Wren 语义部署失败：请配置 GENBI_WREN_AI_ENDPOINT（HTTP）"
                "或安装 GenBI AI 依赖并配置 OPENAI_/GENBI_EMBED_*。"
                f" 原因: {exc}"
            ) from exc

    async def _wait_semantics_ready(self, mdl_hash: str) -> bool:
        from app.modules.genbi.ai import facade as genbi_ai

        elapsed = 0.0
        while elapsed < _DEPLOY_POLL_TIMEOUT:
            status_body = await genbi_ai.get_semantics_status(mdl_hash)
            status = (status_body.get("status") or "").lower()
            if status == "finished":
                return True
            if status == "failed":
                return False
            await asyncio.sleep(_DEPLOY_POLL_INTERVAL)
            elapsed += _DEPLOY_POLL_INTERVAL
        return False


def get_wren_client() -> WrenClient:
    """Default client: SettingsWrenClient (real wiring; Stub* for tests)."""
    return SettingsWrenClient()
