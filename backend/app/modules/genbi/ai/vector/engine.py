"""Asyncpg pool for GenBI vector PG (pgvector) — same app DATABASE by default."""

from __future__ import annotations

import asyncio
import logging
import threading
from typing import Dict
from urllib.parse import urlparse

import asyncpg

logger = logging.getLogger(__name__)

_pools: Dict[int, asyncpg.Pool] = {}
_init_lock = threading.Lock()


def _dsn_for_asyncpg(url: str) -> str:
    return (
        url.replace("postgresql+asyncpg://", "postgresql://", 1)
        .replace("postgresql+psycopg://", "postgresql://", 1)
        .replace("postgresql+psycopg2://", "postgresql://", 1)
    )


async def _create_pool() -> asyncpg.Pool:
    from app.config.setting import settings

    dsn = _dsn_for_asyncpg(settings.genbi_vector_database_url)
    parsed = urlparse(dsn)
    logger.info(
        "GenBI vector PG pool host=%s db=%s",
        parsed.hostname,
        (parsed.path or "").lstrip("/"),
    )
    return await asyncpg.create_pool(dsn, min_size=1, max_size=8, command_timeout=120)


async def get_genbi_vector_pool() -> asyncpg.Pool:
    loop_id = id(asyncio.get_running_loop())
    pool = _pools.get(loop_id)
    if pool is not None:
        return pool
    with _init_lock:
        pool = _pools.get(loop_id)
        if pool is not None:
            return pool
        pool = await _create_pool()
        _pools[loop_id] = pool
        return pool
