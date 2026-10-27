"""Bootstrap vendored wren-ai (`import src.*`) + langfuse decorator shim."""

from __future__ import annotations

import logging
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace
from typing import Any

_VENDOR_ROOT = Path(__file__).resolve().parent / "vendor"
_SHIM_INSTALLED = False
_BOOTSTRAPPED = False

logger = logging.getLogger(__name__)


def install_langfuse_shim() -> None:
    """wren vendor expects langfuse.decorators; provide a no-op/OTEL-free shim."""
    global _SHIM_INSTALLED
    if _SHIM_INSTALLED:
        return

    def observe(*args, **kwargs):
        def decorator(fn):
            return fn

        if args and callable(args[0]):
            return decorator(args[0])
        return decorator

    def configure(*, enabled: bool = False, **_: Any) -> None:
        logger.info("GenBI wren-ai Langfuse configure enabled=%s", enabled)

    langfuse_context = SimpleNamespace(
        configure=configure,
        flush=lambda: None,
        get_current_trace_id=lambda: None,
        update_current_trace=lambda **kw: None,
        update_current_observation=lambda **kw: None,
        append_sql_log=lambda *a, **k: None,
    )

    decorators = ModuleType("langfuse.decorators")
    decorators.observe = observe
    decorators.langfuse_context = langfuse_context

    langfuse_pkg = ModuleType("langfuse")
    langfuse_pkg.decorators = decorators

    sys.modules["langfuse"] = langfuse_pkg
    sys.modules["langfuse.decorators"] = decorators
    _SHIM_INSTALLED = True


def _install_context_modules() -> None:
    if "src.genbi_llm_context" not in sys.modules:
        from app.modules.genbi.ai import llm_context

        sys.modules["src.genbi_llm_context"] = llm_context
    if "src.genbi_engine_context" not in sys.modules:
        from app.modules.genbi.ai import engine_context

        sys.modules["src.genbi_engine_context"] = engine_context


def ensure_wren_src_path() -> Path:
    global _BOOTSTRAPPED
    install_langfuse_shim()
    root = str(_VENDOR_ROOT)
    if root not in sys.path:
        sys.path.insert(0, root)
    _install_context_modules()
    _BOOTSTRAPPED = True
    return _VENDOR_ROOT
