"""GenBI AI runtime pool — one embedded wren-ai container (platform tenant)."""

from __future__ import annotations

import logging
import threading
from collections import OrderedDict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from app.config.setting import settings
from app.modules.genbi.ai.container import build_embedded_container, resolve_genbi_ai_config_path
from app.modules.genbi.ai.errors import GenbiAiNotReadyError
from app.modules.genbi.ai.tenant_context import PLATFORM_TENANT_KEY

logger = logging.getLogger(__name__)


@dataclass
class GenbiAiRuntime:
    tenant_key: str = PLATFORM_TENANT_KEY
    is_ready: bool = False
    config_path: Optional[str] = None
    container: Any = None
    service_metadata: Any = None
    pipe_components: Any = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def shutdown(self) -> None:
        self.is_ready = False
        self.container = None
        self.service_metadata = None
        self.pipe_components = None
        self.metadata.clear()


class GenbiAiRuntimePool:
    def __init__(self, max_tenants: int) -> None:
        self._max_tenants = max(1, max_tenants)
        self._config_path: Optional[Path] = None
        self._runtimes: OrderedDict[str, GenbiAiRuntime] = OrderedDict()
        self._lock = threading.Lock()
        self.metadata: dict[str, Any] = {"mode": "idle"}

    def _touch(self, tenant_key: str) -> GenbiAiRuntime:
        runtime = self._runtimes[tenant_key]
        self._runtimes.move_to_end(tenant_key)
        return runtime

    def _build_runtime(self, tenant_key: str) -> GenbiAiRuntime:
        container, service_metadata, pipe_components = build_embedded_container(
            self._config_path or Path("built-in")
        )
        return GenbiAiRuntime(
            tenant_key=tenant_key,
            is_ready=True,
            config_path=str(self._config_path) if self._config_path else "built-in",
            container=container,
            service_metadata=service_metadata,
            pipe_components=pipe_components,
            metadata={"mode": "embedded", "tenant_key": tenant_key},
        )

    async def startup(self) -> None:
        self._config_path = resolve_genbi_ai_config_path()
        await self.ensure_runtime(PLATFORM_TENANT_KEY)
        self.metadata = {
            "mode": "pool",
            "config_path": str(self._config_path) if self._config_path else "built-in",
            "max_tenants": self._max_tenants,
            "active_tenants": list(self._runtimes.keys()),
        }
        logger.info(
            "GenBI AI runtime pool ok config=%s max_tenants=%s",
            self.metadata["config_path"],
            self._max_tenants,
        )

    async def shutdown(self) -> None:
        for runtime in self._runtimes.values():
            runtime.shutdown()
        self._runtimes.clear()
        self.metadata = {"mode": "shutdown"}

    async def ensure_runtime(self, tenant_key: str) -> GenbiAiRuntime:
        key = (tenant_key or "").strip() or PLATFORM_TENANT_KEY
        if key in self._runtimes:
            return self._touch(key)
        with self._lock:
            if key in self._runtimes:
                return self._touch(key)
            while len(self._runtimes) >= self._max_tenants:
                evicted_key, evicted = self._runtimes.popitem(last=False)
                evicted.shutdown()
                logger.info("GenBI evicted tenant runtime %s", evicted_key)
            runtime = self._build_runtime(key)
            self._runtimes[key] = runtime
            self.metadata["active_tenants"] = list(self._runtimes.keys())
            logger.info("GenBI started tenant runtime %s", key)
            return runtime

    def get_runtime(self, tenant_key: str) -> GenbiAiRuntime:
        key = (tenant_key or "").strip() or PLATFORM_TENANT_KEY
        runtime = self._runtimes.get(key)
        if runtime is None or not runtime.is_ready or runtime.container is None:
            raise GenbiAiNotReadyError(f"GenBI AI runtime not ready for tenant {key}")
        return self._touch(key)


_pool: Optional[GenbiAiRuntimePool] = None


def get_genbi_ai_runtime_pool() -> GenbiAiRuntimePool:
    global _pool
    if _pool is None:
        max_tenants = int(getattr(settings, "GENBI_AI_MAX_TENANT_RUNTIMES", 16) or 16)
        _pool = GenbiAiRuntimePool(max_tenants=max_tenants)
    return _pool


async def ensure_platform_runtime() -> GenbiAiRuntime:
    pool = get_genbi_ai_runtime_pool()
    return await pool.ensure_runtime(PLATFORM_TENANT_KEY)


async def init_genbi_ai_runtime() -> GenbiAiRuntimePool:
    pool = get_genbi_ai_runtime_pool()
    await pool.startup()
    return pool


async def shutdown_genbi_ai_runtime() -> None:
    await get_genbi_ai_runtime_pool().shutdown()
