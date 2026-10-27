"""Per-request MDL + ibis connection for wren-engine / ibis dry-run."""

from __future__ import annotations

import base64
import json
from contextlib import contextmanager
from contextvars import ContextVar, Token
from dataclasses import dataclass
from typing import Any, Iterator, Optional

from app.modules.genbi.datasource.model import GenbiDatasourceModel
from app.modules.genbi.ibis.connection import ibis_connector_slug, to_ibis_connection_info

_var: ContextVar[Optional["GenbiEngineContext"]] = ContextVar("genbi_engine_context", default=None)


@dataclass(frozen=True)
class GenbiEngineContext:
    engine_manifest_b64: str
    ibis_manifest_b64: str
    connection_info: dict[str, Any]
    ibis_source: str


def encode_mdl_manifest_b64(manifest: dict[str, Any]) -> str:
    payload = json.dumps(manifest, separators=(",", ":"), ensure_ascii=False).encode()
    return base64.b64encode(payload).decode()


def build_engine_context(
    manifest: dict[str, Any],
    data_source: GenbiDatasourceModel,
) -> GenbiEngineContext:
    manifest_b64 = encode_mdl_manifest_b64(manifest)
    wren_type = (data_source.wren_type or "").strip().upper()
    ibis_source = ibis_connector_slug(wren_type) or ""
    return GenbiEngineContext(
        engine_manifest_b64=manifest_b64,
        ibis_manifest_b64=manifest_b64,
        connection_info=to_ibis_connection_info(data_source) or {},
        ibis_source=ibis_source,
    )


def current_engine_context() -> Optional[GenbiEngineContext]:
    return _var.get()


def current_engine_manifest_b64() -> Optional[str]:
    ctx = _var.get()
    return ctx.engine_manifest_b64 if ctx else None


@contextmanager
def use_genbi_engine_context(ctx: Optional[GenbiEngineContext]) -> Iterator[None]:
    if ctx is None:
        yield
        return
    token: Token = _var.set(ctx)
    try:
        yield
    finally:
        _var.reset(token)
