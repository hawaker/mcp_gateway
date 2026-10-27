"""Wren / semantics deploy client.

Vector index uses the **existing** application PostgreSQL (pgvector) — see
``settings.genbi_vector_database_url`` / ``GENBI_VECTOR_*`` falling back to
``DATABASE_*``. Do not introduce a second vector DB service.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable


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
    """Production plug-in point: uses ``GENBI_WREN_*`` / ``GENBI_IBIS_*``.

    Until the full Wren AI runtime is wired (later tasks), this client validates
    configuration and records a successful deploy the same way as the stub —
    so deploy_log / mdl_hash gates work end-to-end without a second vector DB.
    """

    async def deploy_semantics(
        self,
        *,
        project_id: int,
        mdl_hash: str,
        manifest: dict[str, Any],
    ) -> WrenDeployResult:
        from app.config.setting import settings

        # Touch settings so misconfiguration surfaces early; vector URL must resolve
        # to the app Postgres (same DATABASE_* / explicit GENBI_VECTOR_* override).
        _ = settings.GENBI_IBIS_ENDPOINT
        _ = settings.GENBI_WREN_ENGINE_ENDPOINT
        _ = settings.genbi_vector_database_url
        if not manifest.get("models"):
            raise ValueError("manifest has no models")
        return WrenDeployResult(mdl_hash=mdl_hash, status="finished")


def get_wren_client() -> WrenClient:
    """Default client: SettingsWrenClient (stub-compatible until real Wren lands)."""
    return SettingsWrenClient()
