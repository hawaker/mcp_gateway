import asyncio
import base64
import logging
import os
from typing import Any, Dict, Optional, Tuple

import aiohttp
import orjson

from src.config import settings
from src.core.engine import Engine, remove_limit_statement
from src.providers.loader import provider

logger = logging.getLogger("wren-ai-service")


def _engine_manifest_b64(fallback: str) -> str:
    try:
        from src.genbi_engine_context import current_engine_manifest_b64

        ctx = current_engine_manifest_b64()
        if ctx:
            return ctx
    except Exception:
        pass
    return fallback or ""


def _manifest_dict(manifest_b64: str) -> dict:
    if manifest_b64:
        return orjson.loads(base64.b64decode(manifest_b64))
    return {}


def _ibis_runtime(
    fallback_manifest: str,
    fallback_connection: dict,
    fallback_source: str,
) -> tuple[str, dict, str]:
    try:
        from src.genbi_engine_context import current_engine_context

        ctx = current_engine_context()
        if ctx:
            return ctx.ibis_manifest_b64, ctx.connection_info, ctx.ibis_source
    except Exception:
        pass
    return fallback_manifest, fallback_connection, fallback_source


@provider("wren_ibis")
class WrenIbis(Engine):
    def __init__(
        self,
        endpoint: str = os.getenv("WREN_IBIS_ENDPOINT"),
        source: str = os.getenv("WREN_IBIS_SOURCE"),
        manifest: str = os.getenv("WREN_IBIS_MANIFEST"),
        connection_info: str = os.getenv("WREN_IBIS_CONNECTION_INFO"),
        **_,
    ):
        self._endpoint = endpoint
        self._source = source
        self._manifest = manifest
        self._connection_info = (
            orjson.loads(base64.b64decode(connection_info)) if connection_info else {}
        )

    async def execute_sql(
        self,
        sql: str,
        session: aiohttp.ClientSession,
        dry_run: bool = True,
        timeout: float = settings.engine_timeout,
        limit: int = 500,
        **kwargs,
    ) -> Tuple[bool, Optional[Dict[str, Any]]]:
        api_endpoint = f"{self._endpoint}/v3/connector/{self._source}/query"
        if dry_run:
            api_endpoint += "?dryRun=true&limit=1"
        else:
            api_endpoint += f"?limit={limit}"

        manifest_b64, connection_info, source = _ibis_runtime(
            self._manifest, self._connection_info, self._source
        )
        if source:
            api_endpoint = f"{self._endpoint}/v3/connector/{source}/query"
            if dry_run:
                api_endpoint += "?dryRun=true&limit=1"
            else:
                api_endpoint += f"?limit={limit}"

        try:
            async with session.post(
                api_endpoint,
                json={
                    "sql": remove_limit_statement(sql),
                    "manifestStr": manifest_b64,
                    "connectionInfo": connection_info,
                },
                timeout=aiohttp.ClientTimeout(total=timeout),
            ) as response:
                if dry_run:
                    res = await response.text()
                else:
                    res = await response.json()

                if response.status == 200 or response.status == 204:
                    return (
                        True,
                        res,
                        {
                            "correlation_id": "",
                        },
                    )

                return (
                    False,
                    None,
                    {
                        "error_message": res,
                        "correlation_id": "",
                    },
                )
        except asyncio.TimeoutError:
            return False, None, f"Request timed out: {timeout} seconds"

    async def dry_plan(
        self,
        session: aiohttp.ClientSession,
        sql: str,
        data_source: str,
        timeout: float = settings.engine_timeout,
        allow_fallback: bool = True,
        **kwargs,
    ) -> Tuple[bool, str]:
        api_endpoint = f"{self._endpoint}/v3/connector/{data_source}/dry-plan"
        manifest_b64, _, _ = _ibis_runtime(
            self._manifest, self._connection_info, self._source
        )
        try:
            async with session.post(
                api_endpoint,
                headers={
                    "x-wren-fallback_disable": "false" if allow_fallback else "true",
                },
                json={
                    "sql": sql,
                    "manifestStr": manifest_b64,
                },
                timeout=aiohttp.ClientTimeout(total=timeout),
            ) as response:
                res = await response.text()

                if response.status != 200:
                    raise Exception(f"Request failed with message: {res}")

                return True, ""
        except asyncio.TimeoutError:
            logger.error(f"Request timed out: {timeout} seconds")
            return False, f"Request timed out: {timeout} seconds"
        except Exception as e:
            logger.exception(f"Unexpected error during dry_plan: {str(e)}")
            return False, f"Unexpected error during dry_plan: {str(e)}"

    async def get_func_list(
        self,
        session: aiohttp.ClientSession,
        data_source: str,
        timeout: float = settings.engine_timeout,
    ) -> list[str]:
        api_endpoint = f"{self._endpoint}/v3/connector/{data_source}/functions"
        try:
            async with session.get(api_endpoint, timeout=timeout) as response:
                res = await response.json()

                if response.status != 200:
                    raise Exception(f"Request failed with message: {res}")

                return res
        except asyncio.TimeoutError:
            logger.error(f"Request timed out: {timeout} seconds")
            return []
        except Exception as e:
            logger.exception(f"Unexpected error during get_func_list: {str(e)}")
            return []

    async def get_sql_knowledge(
        self,
        session: aiohttp.ClientSession,
        data_source: str,
        timeout: float = settings.engine_timeout,
    ) -> Optional[Dict[str, Any]]:
        api_endpoint = f"{self._endpoint}/v3/connector/{data_source}/knowledge"
        try:
            async with session.get(api_endpoint, timeout=timeout) as response:
                res = await response.json()

                if response.status != 200:
                    raise Exception(f"Request failed with message: {res}")

                return res
        except asyncio.TimeoutError:
            logger.error(f"Request timed out: {timeout} seconds")
            return None
        except Exception as e:
            logger.exception(f"Unexpected error during get_sql_knowledge: {str(e)}")
            return None


@provider("wren_engine")
class WrenEngine(Engine):
    def __init__(
        self,
        endpoint: str = os.getenv("WREN_ENGINE_ENDPOINT"),
        manifest: str = os.getenv("WREN_ENGINE_MANIFEST"),
        **_,
    ):
        self._endpoint = endpoint
        self._manifest = manifest

    async def execute_sql(
        self,
        sql: str,
        session: aiohttp.ClientSession,
        dry_run: bool = True,
        timeout: float = settings.engine_timeout,
        limit: int = 500,
        **kwargs,
    ) -> Tuple[bool, Optional[Dict[str, Any]], Optional[str]]:
        api_endpoint = (
            f"{self._endpoint}/v1/mdl/dry-run"
            if dry_run
            else f"{self._endpoint}/v1/mdl/preview"
        )

        manifest_b64 = _engine_manifest_b64(self._manifest or "")
        try:
            async with session.get(
                api_endpoint,
                json={
                    "manifest": _manifest_dict(manifest_b64),
                    "sql": remove_limit_statement(sql),
                    "limit": 1 if dry_run else limit,
                },
                timeout=aiohttp.ClientTimeout(total=timeout),
            ) as response:
                if dry_run:
                    res = await response.text()
                else:
                    res = await response.json()

                if response.status == 200:
                    return (
                        True,
                        res,
                        {
                            "correlation_id": "",
                        },
                    )

                logger.warning("wren_engine dry-run failed: %s", res)
                return (
                    False,
                    None,
                    {
                        "error_message": res,
                        "correlation_id": "",
                    },
                )
        except asyncio.TimeoutError:
            return False, None, f"Request timed out: {timeout} seconds"
