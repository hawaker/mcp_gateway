"""GenBI 数据源测连：成功静默，失败抛 CustomException。"""

from __future__ import annotations

import asyncio
from typing import Any, Mapping
from urllib.parse import quote_plus

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from app.core.exceptions import CustomException

from .types import WREN_TYPES

_CONNECT_TIMEOUT = 10

# wren_type → (SQLAlchemy async driver prefix, default port)
_SQL_DRIVERS: dict[str, tuple[str, int]] = {
    "POSTGRES": ("postgresql+asyncpg", 5432),
    "MYSQL": ("mysql+aiomysql", 3306),
    "REDSHIFT": ("postgresql+asyncpg", 5439),
}


def _normalize_wren_type(wren_type: str | None) -> str:
    key = (wren_type or "").strip().upper()
    if key not in WREN_TYPES:
        raise CustomException(msg="不支持的数据源类型")
    return key


def _build_sqlalchemy_url(wren_type: str, params: Mapping[str, Any]) -> str:
    driver, default_port = _SQL_DRIVERS[wren_type]
    host = (params.get("host") or "").strip()
    if not host:
        raise CustomException(msg="连接失败: host 不能为空")
    port = params.get("port")
    if port is None:
        port = default_port
    username = params.get("username") or ""
    password = params.get("password") or ""
    database = params.get("database") or ""
    auth = f"{quote_plus(str(username))}:{quote_plus(str(password))}"
    db_part = f"/{quote_plus(str(database))}" if database else "/"
    return f"{driver}://{auth}@{host}:{int(port)}{db_part}"


async def _probe_url(url: str) -> None:
    """对给定 SQLAlchemy 异步 URL 执行 SELECT 1。失败抛原始异常（由 probe_connection 包装）。"""
    engine = create_async_engine(url, pool_pre_ping=True, pool_size=1, max_overflow=0)
    try:
        async with engine.connect() as conn:
            await asyncio.wait_for(conn.execute(text("SELECT 1")), timeout=_CONNECT_TIMEOUT)
    finally:
        await engine.dispose()


async def _probe_duckdb(params: Mapping[str, Any]) -> None:
    """DuckDB：校验 initSql 存在即可（与 tiga 行为对齐）。"""
    config = params.get("config") if isinstance(params.get("config"), dict) else {}
    init_sql = config.get("initSql") or config.get("init_sql") or params.get("initSql")
    if not str(init_sql or "").strip():
        raise CustomException(msg="连接失败: DuckDB 需要 initSql")


def _wrap_failure(exc: BaseException) -> CustomException:
    if isinstance(exc, CustomException):
        return exc
    if isinstance(exc, TimeoutError):
        return CustomException(msg=f"连接超时（>{_CONNECT_TIMEOUT}s）")
    reason = str(exc).strip().splitlines()[0][:200] if str(exc).strip() else type(exc).__name__
    return CustomException(msg=f"连接失败: {reason}")


async def probe_connection(params: Mapping[str, Any]) -> None:
    """探测数据源连通性。成功则静默返回；失败抛 CustomException。

    至少 POSTGRES（及 MYSQL/REDSHIFT）走 sqlalchemy async 探活；
    其他 wren_type 经同一入口（DUCKDB 校验 initSql；其余暂不支持本地驱动）。
    """
    wren_type = _normalize_wren_type(params.get("wren_type") if isinstance(params.get("wren_type"), str) else None)
    try:
        if wren_type in _SQL_DRIVERS:
            url = _build_sqlalchemy_url(wren_type, params)
            await _probe_url(url)
            return
        if wren_type == "DUCKDB":
            await _probe_duckdb(params)
            return
        raise CustomException(msg=f"暂不支持直接测连: {wren_type}")
    except CustomException:
        raise
    except Exception as exc:
        raise _wrap_failure(exc) from exc
