"""Load vendored wren-ai and build in-process ServiceContainer."""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any, Optional, Tuple

from app.config.setting import settings as app_settings
from app.modules.genbi.ai._bootstrap import ensure_wren_src_path
from app.modules.genbi.ai.litellm_model import llm_generation_kwargs_for, to_litellm_model

logger = logging.getLogger(__name__)

_VENDOR_PYPROJECT = Path(__file__).resolve().parent / "vendor" / "pyproject.toml"


def resolve_genbi_ai_config_path() -> Optional[Path]:
    raw = (getattr(app_settings, "GENBI_AI_CONFIG_PATH", "") or "").strip()
    if raw:
        path = Path(raw)
        if path.is_file():
            return path
    return None


def _apply_env_defaults() -> None:
    if app_settings.GENBI_WREN_ENGINE_ENDPOINT:
        os.environ.setdefault("WREN_ENGINE_ENDPOINT", app_settings.GENBI_WREN_ENGINE_ENDPOINT)
    if app_settings.GENBI_IBIS_ENDPOINT:
        os.environ.setdefault("WREN_IBIS_ENDPOINT", app_settings.GENBI_IBIS_ENDPOINT)
    if app_settings.OPENAI_API_KEY:
        os.environ.setdefault("OPENAI_API_KEY", app_settings.OPENAI_API_KEY)
    if app_settings.OPENAI_BASE_URL:
        os.environ.setdefault("OPENAI_API_BASE", app_settings.OPENAI_BASE_URL)
        os.environ.setdefault("OPENAI_BASE_URL", app_settings.OPENAI_BASE_URL)
    embed_key = (getattr(app_settings, "GENBI_EMBED_API_KEY", "") or app_settings.OPENAI_API_KEY or "").strip()
    if embed_key:
        os.environ.setdefault("EMBED_API_KEY", embed_key)
    embed_base = (
        getattr(app_settings, "GENBI_EMBED_API_BASE", "") or app_settings.OPENAI_BASE_URL or ""
    ).strip()
    if embed_base:
        os.environ.setdefault("EMBED_API_BASE", embed_base)


def _g(name: str, default: Any = None) -> Any:
    return getattr(app_settings, name, default)


def _build_wren_config_blocks() -> list[dict]:
    s = app_settings
    llm_timeout = int(_g("GENBI_LLM_TIMEOUT", 120) or 120)
    embed_timeout = int(_g("GENBI_EMBED_TIMEOUT", 600) or 600)
    embed_dim = int(_g("GENBI_EMBEDDING_DIMENSIONS", 1024) or 1024)

    llm_block = {
        "type": "llm",
        "provider": "litellm_llm",
        "timeout": llm_timeout,
        "models": [
            {
                "alias": "default",
                "model": "gpt-4o-mini",
                "context_window_size": 128000,
                "kwargs": {"max_tokens": 4096, "n": 1, "seed": 0, "temperature": 0},
            }
        ],
    }
    embedder_block = {
        "type": "embedder",
        "provider": "litellm_embedder",
        "models": [
            {
                "model": _g("GENBI_EMBEDDING_MODEL_ID", "") or "text-embedding-3-small",
                "alias": "default",
                "api_key_name": "EMBED_API_KEY",
                "timeout": embed_timeout,
            }
        ],
    }
    engine_ibis_block = {
        "type": "engine",
        "provider": "wren_ibis",
        "endpoint": s.GENBI_IBIS_ENDPOINT,
        "manifest": "",
        "connection_info": "",
    }
    engine_wren_block = {
        "type": "engine",
        "provider": "wren_engine",
        "endpoint": s.GENBI_WREN_ENGINE_ENDPOINT,
        "manifest": "",
    }
    ds_block = {
        "type": "document_store",
        "provider": "pgvector",
        "embedding_model_dim": embed_dim,
        "recreate_index": bool(_g("GENBI_VECTOR_RECREATE_INDEX", False)),
    }
    pipeline_block = {
        "type": "pipeline",
        "pipes": [
            {"name": "db_schema_indexing", "embedder": "litellm_embedder.default", "document_store": "pgvector"},
            {"name": "historical_question_indexing", "embedder": "litellm_embedder.default", "document_store": "pgvector"},
            {"name": "table_description_indexing", "embedder": "litellm_embedder.default", "document_store": "pgvector"},
            {"name": "db_schema_retrieval", "llm": "litellm_llm.default", "embedder": "litellm_embedder.default", "document_store": "pgvector"},
            {"name": "historical_question_retrieval", "embedder": "litellm_embedder.default", "document_store": "pgvector"},
            {"name": "sql_generation", "llm": "litellm_llm.default", "engine": "wren_ibis", "document_store": "pgvector"},
            {"name": "sql_correction", "llm": "litellm_llm.default", "engine": "wren_ibis", "document_store": "pgvector"},
            {"name": "followup_sql_generation", "llm": "litellm_llm.default", "engine": "wren_ibis", "document_store": "pgvector"},
            {"name": "sql_answer", "llm": "litellm_llm.default"},
            {"name": "semantics_description", "llm": "litellm_llm.default"},
            {"name": "relationship_recommendation", "llm": "litellm_llm.default"},
            {"name": "question_recommendation", "llm": "litellm_llm.default"},
            {"name": "question_recommendation_sql_generation", "llm": "litellm_llm.default", "engine": "wren_ibis", "document_store": "pgvector"},
            {"name": "chart_generation", "llm": "litellm_llm.default"},
            {"name": "chart_adjustment", "llm": "litellm_llm.default"},
            {"name": "intent_classification", "llm": "litellm_llm.default", "embedder": "litellm_embedder.default", "document_store": "pgvector"},
            {"name": "misleading_assistance", "llm": "litellm_llm.default"},
            {"name": "data_assistance", "llm": "litellm_llm.default"},
            {"name": "sql_pairs_indexing", "document_store": "pgvector", "embedder": "litellm_embedder.default"},
            {"name": "sql_pairs_retrieval", "document_store": "pgvector", "embedder": "litellm_embedder.default", "llm": "litellm_llm.default"},
            {"name": "preprocess_sql_data", "llm": "litellm_llm.default"},
            {"name": "sql_executor", "engine": "wren_ibis"},
            {"name": "user_guide_assistance", "llm": "litellm_llm.default"},
            {"name": "sql_question_generation", "llm": "litellm_llm.default"},
            {"name": "sql_generation_reasoning", "llm": "litellm_llm.default"},
            {"name": "followup_sql_generation_reasoning", "llm": "litellm_llm.default"},
            {"name": "sql_regeneration", "llm": "litellm_llm.default", "engine": "wren_ibis"},
            {"name": "evaluation", "llm": "litellm_llm.default"},
            {"name": "instructions_indexing", "embedder": "litellm_embedder.default", "document_store": "pgvector"},
            {"name": "instructions_retrieval", "embedder": "litellm_embedder.default", "document_store": "pgvector"},
            {"name": "sql_functions_retrieval", "engine": "wren_ibis", "document_store": "pgvector"},
            {"name": "project_meta_indexing", "document_store": "pgvector"},
            {"name": "sql_tables_extraction", "llm": "litellm_llm.default"},
            {"name": "sql_diagnosis", "llm": "litellm_llm.default"},
            {"name": "sql_knowledge_retrieval", "engine": "wren_ibis", "document_store": "pgvector"},
        ],
    }
    settings_block = {
        "settings": {
            "host": "127.0.0.1",
            "port": 5556,
            "doc_endpoint": "https://docs.getwren.ai",
            "is_oss": True,
            "engine_timeout": float(_g("GENBI_ENGINE_TIMEOUT", 300.0) or 300.0),
            "column_indexing_batch_size": int(_g("GENBI_COLUMN_INDEX_BATCH_SIZE", 50) or 50),
            "table_retrieval_size": int(_g("GENBI_TABLE_RETRIEVAL_SIZE", 10) or 10),
            "table_column_retrieval_size": int(_g("GENBI_TABLE_COLUMN_RETRIEVAL_SIZE", 100) or 100),
            "allow_intent_classification": bool(_g("GENBI_ALLOW_INTENT_CLASSIFICATION", True)),
            "allow_sql_generation_reasoning": bool(_g("GENBI_ALLOW_SQL_GENERATION_REASONING", True)),
            "allow_sql_functions_retrieval": bool(_g("GENBI_ALLOW_SQL_FUNCTIONS_RETRIEVAL", False)),
            "enable_column_pruning": bool(_g("GENBI_ENABLE_COLUMN_PRUNING", False)),
            "max_sql_correction_retries": int(_g("GENBI_MAX_SQL_CORRECTION_RETRIES", 3) or 3),
            "query_cache_maxsize": int(_g("GENBI_QUERY_CACHE_MAXSIZE", 1000) or 1000),
            "query_cache_ttl": int(_g("GENBI_QUERY_CACHE_TTL", 3600) or 3600),
            "langfuse_host": "",
            "langfuse_enable": False,
            "logging_level": _g("GENBI_LOG_LEVEL", "INFO") or "INFO",
            "development": bool(_g("GENBI_DEV_MODE", False)),
            "historical_question_retrieval_similarity_threshold": float(
                _g("GENBI_HIST_QUESTION_THRESHOLD", 0.9) or 0.9
            ),
            "sql_pairs_similarity_threshold": float(_g("GENBI_SQL_PAIRS_THRESHOLD", 0.7) or 0.7),
            "sql_pairs_retrieval_max_size": int(_g("GENBI_SQL_PAIRS_MAX_SIZE", 10) or 10),
            "instructions_similarity_threshold": float(_g("GENBI_INSTRUCTIONS_THRESHOLD", 0.7) or 0.7),
            "instructions_top_k": int(_g("GENBI_INSTRUCTIONS_TOP_K", 10) or 10),
        }
    }
    return [
        llm_block,
        embedder_block,
        engine_ibis_block,
        engine_wren_block,
        ds_block,
        pipeline_block,
        settings_block,
    ]


def _patch_wren_config(raw: list) -> list:
    llm_model = (app_settings.OPENAI_MODEL or "").strip() or "gpt-4o-mini"
    llm_base = (app_settings.OPENAI_BASE_URL or "").strip().rstrip("/")
    embed_model = (getattr(app_settings, "GENBI_EMBEDDING_MODEL_ID", "") or "").strip()
    embed_base = (
        getattr(app_settings, "GENBI_EMBED_API_BASE", "") or app_settings.OPENAI_BASE_URL or ""
    ).strip().rstrip("/")
    embed_dim = int(getattr(app_settings, "GENBI_EMBEDDING_DIMENSIONS", 1024) or 1024)

    for block in raw:
        if not block or block.get("type") != "llm":
            continue
        block["api_key_name"] = "OPENAI_API_KEY"
        if llm_base:
            block["api_base"] = llm_base
        if llm_model:
            litellm_model = to_litellm_model(llm_model, llm_base or None)
            models = block.get("models") or []
            if models:
                models[0]["model"] = litellm_model
                models[0]["kwargs"] = llm_generation_kwargs_for(litellm_model)
        break

    for block in raw:
        if not block or block.get("type") != "embedder":
            continue
        for model in block.get("models") or []:
            if embed_model:
                model["model"] = to_litellm_model(embed_model, embed_base or None)
            if embed_base:
                model["api_base"] = embed_base
            model["api_key_name"] = "EMBED_API_KEY"
        break

    for block in raw:
        if block and block.get("type") == "document_store":
            block["provider"] = "pgvector"
            block["embedding_model_dim"] = embed_dim
            block.pop("location", None)
            block.pop("timeout", None)
            break

    for block in raw:
        if not block or block.get("type") != "pipeline":
            continue
        for pipe in block.get("pipes") or []:
            if pipe.get("document_store"):
                pipe["document_store"] = "pgvector"

    return raw


def _reload_wren_settings(config_path: Path):
    import src.config as wren_config

    s = wren_config.settings
    raw = _patch_wren_config(_build_wren_config_blocks())
    s.override(raw)
    s._components = [c for c in raw if c and "settings" not in c]
    s.langfuse_enable = False
    return s


def build_embedded_container(config_path: Path) -> Tuple[Any, Any, Any]:
    vendor_root = ensure_wren_src_path()
    _apply_env_defaults()
    wren_settings = _reload_wren_settings(config_path)

    from src.globals import ServiceMetadata, create_service_container, create_service_metadata
    from src.providers import generate_components
    from src.utils import init_langfuse, setup_custom_logger

    init_langfuse(wren_settings)
    setup_custom_logger(
        "genbi-wren",
        level_str=wren_settings.logging_level,
        is_dev=wren_settings.development,
    )

    prev_cwd = os.getcwd()
    os.chdir(vendor_root)
    try:
        pipe_components = generate_components(wren_settings.components)
        container = create_service_container(pipe_components, wren_settings)
        try:
            metadata = create_service_metadata(
                pipe_components, pyproject_path=str(_VENDOR_PYPROJECT)
            )
        except Exception as exc:
            logger.warning("GenBI wren metadata fallback: %s", exc)
            metadata = ServiceMetadata(pipes_metadata={}, service_version="embedded")
    finally:
        os.chdir(prev_cwd)

    return container, metadata, pipe_components
