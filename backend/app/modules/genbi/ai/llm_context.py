"""Per-request GenBI LLM creds via ContextVar (simplified for FastapiAdmin)."""

from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar, Token
from dataclasses import dataclass
from typing import Any, Iterator, Optional

_var: ContextVar[Any] = ContextVar("genbi_llm_creds", default=None)


@dataclass(frozen=True)
class ResolvedEmbedding:
    api_key: str = ""
    base_url: str | None = None
    model_id: str = ""
    source: str = "env"
    dimensions: int = 1024


def current_credentials() -> Any:
    return _var.get()


def merge_disable_thinking_kwargs(kwargs: dict[str, Any]) -> dict[str, Any]:
    return dict(kwargs)


def strip_assistant_content(text: str) -> str:
    return (text or "").strip()


def is_response_format_unavailable_error(exc: BaseException) -> bool:
    msg = str(exc).lower()
    return "json_schema" in msg or "response_format" in msg


def downgrade_json_schema_kwargs(model: str, kwargs: dict[str, Any]) -> dict[str, Any]:
    out = dict(kwargs)
    rf = out.get("response_format")
    if not (isinstance(rf, dict) and rf.get("type") == "json_schema"):
        return out
    out["response_format"] = {"type": "json_object"}
    return out


def sanitize_generation_kwargs(model: str, kwargs: dict[str, Any]) -> dict[str, Any]:
    out = dict(kwargs)
    bare = (model or "").split("/", 1)[-1]
    if not bare.startswith("gpt-5"):
        out.pop("reasoning_effort", None)
    return out


@contextmanager
def use_genbi_llm_credentials(creds: Optional[Any]) -> Iterator[None]:
    if creds is None:
        yield
        return
    token: Token = _var.set(creds)
    try:
        yield
    finally:
        _var.reset(token)
