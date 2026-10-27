"""Per-request tenant key → isolated wren-ai runtime instance."""

from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar, Token
from typing import Iterator, Optional

from app.modules.genbi.ai.errors import GenbiTenantNotBoundError

PLATFORM_TENANT_KEY = "__platform__"

_tenant_var: ContextVar[Optional[str]] = ContextVar("genbi_ai_tenant", default=None)


def runtime_tenant_key(*_args: object, **_kwargs: object) -> str:
    """FastapiAdmin GenBI is single-tenant (platform) for Wren AI runtimes."""
    return PLATFORM_TENANT_KEY


def current_tenant_key() -> str:
    key = _tenant_var.get()
    if not key:
        # Default to platform so Settings* can call facade without explicit scope.
        return PLATFORM_TENANT_KEY
    return key


@contextmanager
def use_genbi_tenant(tenant_key: str) -> Iterator[None]:
    token: Token = _tenant_var.set(tenant_key or PLATFORM_TENANT_KEY)
    try:
        yield
    finally:
        _tenant_var.reset(token)
