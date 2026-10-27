"""In-process GenBI AI facade (vendored wren-ai services)."""

from __future__ import annotations

import uuid
from dataclasses import asdict
from typing import Any, Optional

from app.modules.genbi.ai.errors import GenbiAiNotReadyError
from app.modules.genbi.ai.runtime import ensure_platform_runtime, get_genbi_ai_runtime_pool
from app.modules.genbi.ai.tenant_context import current_tenant_key


def _runtime_parts():
    runtime = get_genbi_ai_runtime_pool().get_runtime(current_tenant_key())
    if not runtime.is_ready or runtime.container is None or runtime.service_metadata is None:
        raise GenbiAiNotReadyError("GenBI AI runtime not initialized")
    return runtime.container, runtime.service_metadata


async def ensure_ready() -> None:
    await ensure_platform_runtime()


async def prepare_semantics(mdl: str, mdl_hash: str, project_id: str) -> None:
    from src.web.v1.services.semantics_preparation import (
        SemanticsPreparationRequest,
        SemanticsPreparationStatusResponse,
    )

    await ensure_ready()
    container, metadata = _runtime_parts()
    req = SemanticsPreparationRequest(
        mdl=mdl,
        mdl_hash=mdl_hash,
        project_id=str(project_id),
        request_from="api",
    )
    container.semantics_preparation_service._prepare_semantics_statuses[mdl_hash] = (
        SemanticsPreparationStatusResponse(status="indexing")
    )
    await container.semantics_preparation_service.prepare_semantics(
        req,
        service_metadata=asdict(metadata),
    )


async def get_semantics_status(mdl_hash: str) -> dict[str, Any]:
    from src.web.v1.services.semantics_preparation import SemanticsPreparationStatusRequest

    await ensure_ready()
    container, _ = _runtime_parts()
    status = container.semantics_preparation_service.get_prepare_semantics_status(
        SemanticsPreparationStatusRequest(mdl_hash=mdl_hash)
    )
    return status.model_dump(by_alias=True)


def _build_ask_request(
    *,
    query_id: str,
    query: str,
    mdl_hash: str,
    project_id: str,
    histories: Optional[list[dict[str, str]]] = None,
    custom_instruction: Optional[str] = None,
    language: str = "Chinese",
):
    from src.web.v1.services import Configuration
    from src.web.v1.services.ask import AskHistory, AskRequest

    history_models = [
        AskHistory(question=h["question"], sql=h["sql"])
        for h in (histories or [])
        if h.get("question") and h.get("sql")
    ]
    req = AskRequest(
        query=query,
        mdl_hash=mdl_hash,
        project_id=str(project_id),
        histories=history_models,
        custom_instruction=custom_instruction,
        configurations=Configuration(language=language),
        request_from="api",
    )
    req.query_id = query_id
    return req


async def bootstrap_ask(
    *,
    query: str,
    mdl_hash: str,
    project_id: str,
    histories: Optional[list[dict[str, str]]] = None,
    custom_instruction: Optional[str] = None,
) -> str:
    from src.web.v1.services.ask import AskResultResponse

    await ensure_ready()
    container, _ = _runtime_parts()
    query_id = str(uuid.uuid4())
    container.ask_service._ask_results[query_id] = AskResultResponse(status="understanding")
    _ = query, histories, custom_instruction
    return query_id


async def run_ask_job(
    *,
    query_id: str,
    query: str,
    mdl_hash: str,
    project_id: str,
    histories: Optional[list[dict[str, str]]] = None,
    custom_instruction: Optional[str] = None,
    language: str = "Chinese",
) -> None:
    await ensure_ready()
    container, metadata = _runtime_parts()
    req = _build_ask_request(
        query_id=query_id,
        query=query,
        mdl_hash=mdl_hash,
        project_id=project_id,
        histories=histories,
        custom_instruction=custom_instruction,
        language=language,
    )
    await container.ask_service.ask(req, service_metadata=asdict(metadata))


async def submit_ask(
    *,
    query: str,
    mdl_hash: str,
    project_id: str,
    histories: Optional[list[dict[str, str]]] = None,
    custom_instruction: Optional[str] = None,
    language: str = "Chinese",
) -> str:
    query_id = await bootstrap_ask(
        query=query,
        mdl_hash=mdl_hash,
        project_id=project_id,
        histories=histories,
        custom_instruction=custom_instruction,
    )
    await run_ask_job(
        query_id=query_id,
        query=query,
        mdl_hash=mdl_hash,
        project_id=project_id,
        histories=histories,
        custom_instruction=custom_instruction,
        language=language,
    )
    return query_id


async def get_ask_result(query_id: str) -> dict[str, Any]:
    from src.web.v1.services.ask import AskResultRequest

    await ensure_ready()
    container, _ = _runtime_parts()
    result = container.ask_service.get_ask_result(AskResultRequest(query_id=query_id))
    return result.model_dump()


def extract_sql_from_ask_result(result: dict[str, Any]) -> str | None:
    candidates = result.get("response") or []
    if candidates and isinstance(candidates, list):
        first = candidates[0]
        if isinstance(first, dict) and first.get("sql"):
            return str(first["sql"])
    return None
