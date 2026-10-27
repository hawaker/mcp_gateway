"""HTTP client for external Wren AI service (ask + semantics-preparations)."""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

import httpx

from app.config.setting import settings

logger = logging.getLogger(__name__)

_POLL_INTERVAL = 1.0
_DEPLOY_TIMEOUT = 180.0
_ASK_TIMEOUT = 180.0
_TERMINAL = frozenset({"finished", "failed", "stopped"})


def wren_ai_base_url() -> str:
    return (getattr(settings, "GENBI_WREN_AI_ENDPOINT", "") or "").rstrip("/")


def http_ai_configured() -> bool:
    return bool(wren_ai_base_url())


async def http_prepare_semantics(
    *,
    mdl: str,
    mdl_hash: str,
    project_id: str,
    client: httpx.AsyncClient | None = None,
) -> dict[str, Any]:
    base = wren_ai_base_url()
    if not base:
        raise RuntimeError("GENBI_WREN_AI_ENDPOINT is not configured")

    owns = client is None
    http = client or httpx.AsyncClient(timeout=120.0)
    try:
        resp = await http.post(
            f"{base}/v1/semantics-preparations",
            json={
                "mdl": mdl if isinstance(mdl, str) else json.dumps(mdl, ensure_ascii=False),
                "mdlHash": mdl_hash,
                "projectId": str(project_id),
            },
        )
        if resp.status_code >= 400:
            raise RuntimeError(resp.text)
        elapsed = 0.0
        while elapsed < _DEPLOY_TIMEOUT:
            status_resp = await http.get(f"{base}/v1/semantics-preparations/{mdl_hash}/status")
            if status_resp.status_code >= 400:
                raise RuntimeError(status_resp.text)
            body = status_resp.json() if status_resp.content else {}
            status = (body.get("status") or "").lower()
            if status == "finished":
                return body
            if status == "failed":
                raise RuntimeError(body.get("error") or "semantics preparation failed")
            await asyncio.sleep(_POLL_INTERVAL)
            elapsed += _POLL_INTERVAL
        raise TimeoutError(f"semantics preparation timed out for {mdl_hash}")
    finally:
        if owns:
            await http.aclose()


async def http_ask(
    *,
    question: str,
    mdl_hash: str,
    project_id: str,
    client: httpx.AsyncClient | None = None,
) -> dict[str, Any]:
    base = wren_ai_base_url()
    if not base:
        raise RuntimeError("GENBI_WREN_AI_ENDPOINT is not configured")

    owns = client is None
    http = client or httpx.AsyncClient(timeout=120.0)
    try:
        resp = await http.post(
            f"{base}/v1/asks",
            json={
                "query": question,
                "mdlHash": mdl_hash,
                "projectId": str(project_id),
            },
        )
        if resp.status_code >= 400:
            raise RuntimeError(resp.text)
        body = resp.json() if resp.content else {}
        query_id = body.get("query_id") or body.get("queryId") or body.get("id")
        if not query_id:
            raise RuntimeError(f"ask response missing query_id: {body}")

        elapsed = 0.0
        while elapsed < _ASK_TIMEOUT:
            result_resp = await http.get(f"{base}/v1/asks/{query_id}/result")
            if result_resp.status_code >= 400:
                raise RuntimeError(result_resp.text)
            result = result_resp.json() if result_resp.content else {}
            status = (result.get("status") or "").lower()
            if status in _TERMINAL:
                return result
            await asyncio.sleep(_POLL_INTERVAL)
            elapsed += _POLL_INTERVAL
        raise TimeoutError(f"ask timed out query_id={query_id}")
    finally:
        if owns:
            await http.aclose()
