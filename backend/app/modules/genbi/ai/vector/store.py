"""Simplified GenBI pgvector store (TEXT project_id; fixed table per embedding dim)."""

from __future__ import annotations

import asyncio
import json
import logging
import re
from typing import Any, Dict, List, Optional, Sequence, Tuple

from pgvector.asyncpg import register_vector

from app.modules.genbi.ai.llm_context import ResolvedEmbedding
from app.modules.genbi.ai.vector.engine import get_genbi_vector_pool

logger = logging.getLogger(__name__)

_TABLE_PREFIX = "genbi_wren_vectors"
_IDENT_RE = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*$")
_ensured_tables: set[str] = set()
_ensure_locks: dict[str, asyncio.Lock] = {}
_ensure_locks_guard = asyncio.Lock()


def _table_for_dims(dimensions: int) -> str:
    name = f"{_TABLE_PREFIX}_d{int(dimensions)}"
    if not _IDENT_RE.match(name):
        raise ValueError(f"invalid pgvector table name: {name!r}")
    return name


async def _lock_for_table(table: str) -> asyncio.Lock:
    async with _ensure_locks_guard:
        lock = _ensure_locks.get(table)
        if lock is None:
            lock = asyncio.Lock()
            _ensure_locks[table] = lock
        return lock


async def ensure_vector_space(cred: ResolvedEmbedding) -> str:
    dims = int(getattr(cred, "dimensions", 0) or 0)
    if dims <= 0:
        from app.config.setting import settings

        dims = int(getattr(settings, "GENBI_EMBEDDING_DIMENSIONS", 1024) or 1024)
    table = _table_for_dims(dims)
    if table in _ensured_tables:
        return table

    lock = await _lock_for_table(table)
    async with lock:
        if table in _ensured_tables:
            return table
        pool = await get_genbi_vector_pool()
        async with pool.acquire() as conn:
            await register_vector(conn)
            await conn.execute("CREATE EXTENSION IF NOT EXISTS vector")
            await conn.execute(
                f"""
                CREATE TABLE IF NOT EXISTS {table} (
                    id BIGSERIAL PRIMARY KEY,
                    collection VARCHAR(64) NOT NULL,
                    project_id TEXT NOT NULL,
                    doc_id VARCHAR(255) NOT NULL,
                    embedding vector({int(dims)}) NOT NULL,
                    payload JSONB NOT NULL DEFAULT '{{}}'::jsonb,
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                    UNIQUE (collection, project_id, doc_id)
                )
                """
            )
            await conn.execute(
                f"CREATE INDEX IF NOT EXISTS idx_{table}_proj ON {table} (collection, project_id)"
            )
            await conn.execute(
                f"""
                CREATE INDEX IF NOT EXISTS idx_{table}_hnsw
                ON {table} USING hnsw (embedding vector_cosine_ops)
                """
            )
        _ensured_tables.add(table)
        logger.info("GenBI pgvector space ensured table=%s dimensions=%s", table, dims)
        return table


def _flatten_meta(document_meta: Dict[str, Any]) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    for key, val in document_meta.items():
        if isinstance(val, (str, int, float, bool)) or val is None:
            out[key] = val
        else:
            out[key] = str(val)
    return out


def _filter_to_sql(
    filters: Optional[Dict[str, Any]],
    *,
    collection: str,
) -> Tuple[str, List[Any]]:
    params: List[Any] = [collection]

    def expr(node: Optional[Dict[str, Any]]) -> str:
        if not node:
            return "TRUE"
        op = node.get("operator")
        if op in ("AND", "OR"):
            parts = [expr(c) for c in (node.get("conditions") or [])]
            parts = [p for p in parts if p and p != "TRUE"]
            if not parts:
                return "TRUE"
            join = " AND " if op == "AND" else " OR "
            if len(parts) == 1:
                return parts[0]
            return "(" + join.join(parts) + ")"
        field = str(node.get("field") or "")
        oper = node.get("operator")
        value = node.get("value")
        if not field or not oper:
            return "TRUE"
        if field == "project_id" and oper == "==":
            params.append(str(value))
            return f"project_id = ${len(params)}"
        if oper == "==":
            if isinstance(value, bool):
                params.append(value)
                return f"(payload->>'{field}')::boolean = ${len(params)}"
            params.append(str(value))
            return f"payload->>'{field}' = ${len(params)}"
        if oper == "in" and isinstance(value, list):
            params.append([str(v) for v in value])
            return f"payload->>'{field}' = ANY(${len(params)}::text[])"
        return "TRUE"

    filter_sql = expr(filters)
    if filter_sql == "TRUE":
        return "collection = $1", params
    return f"collection = $1 AND ({filter_sql})", params


class GenbiPgvectorStore:
    def __init__(self, cred: ResolvedEmbedding, *, collection: str):
        self._cred = cred
        self._collection = collection

    async def _table(self) -> str:
        return await ensure_vector_space(self._cred)

    async def upsert_documents(
        self,
        *,
        project_id: str,
        documents: Sequence[Dict[str, Any]],
    ) -> int:
        if not documents:
            return 0
        table = await self._table()
        pool = await get_genbi_vector_pool()
        count = 0
        async with pool.acquire() as conn:
            await register_vector(conn)
            for doc in documents:
                doc_id = str(doc.get("doc_id") or doc.get("id") or "").strip()
                embedding = doc.get("embedding")
                if not doc_id or not embedding:
                    continue
                meta = _flatten_meta(dict(doc.get("meta") or {}))
                if doc.get("content") is not None:
                    meta.setdefault("content", doc["content"])
                meta.setdefault("project_id", project_id)
                await conn.execute(
                    f"""
                    INSERT INTO {table} (collection, project_id, doc_id, embedding, payload, updated_at)
                    VALUES ($1, $2, $3, $4, $5::jsonb, now())
                    ON CONFLICT (collection, project_id, doc_id)
                    DO UPDATE SET embedding = EXCLUDED.embedding,
                                  payload = EXCLUDED.payload,
                                  updated_at = now()
                    """,
                    self._collection,
                    str(project_id),
                    doc_id,
                    list(embedding),
                    json.dumps(meta, ensure_ascii=False),
                )
                count += 1
        return count

    async def list_documents(
        self,
        *,
        filters: Optional[Dict[str, Any]] = None,
        limit: int = 500,
    ) -> List[Dict[str, Any]]:
        table = await self._table()
        where, params = _filter_to_sql(filters, collection=self._collection)
        params.append(limit)
        limit_idx = len(params)
        pool = await get_genbi_vector_pool()
        async with pool.acquire() as conn:
            await register_vector(conn)
            rows = await conn.fetch(
                f"""
                SELECT doc_id, payload
                FROM {table}
                WHERE {where}
                LIMIT ${limit_idx}
                """,
                *params,
            )
        out: List[Dict[str, Any]] = []
        for row in rows:
            payload = row["payload"]
            if isinstance(payload, str):
                payload = json.loads(payload)
            meta = dict(payload or {})
            content = meta.pop("content", "") or ""
            out.append({"id": row["doc_id"], "content": content, "meta": meta})
        return out

    async def search_by_embedding(
        self,
        *,
        query_embedding: List[float],
        project_id: Optional[str] = None,
        top_k: int = 10,
        filters: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        table = await self._table()
        where, params = _filter_to_sql(filters, collection=self._collection)
        if project_id:
            params.append(str(project_id))
            where += f" AND project_id = ${len(params)}"
        params.append(list(query_embedding))
        emb_idx = len(params)
        params.append(top_k)
        limit_idx = len(params)
        pool = await get_genbi_vector_pool()
        async with pool.acquire() as conn:
            await register_vector(conn)
            rows = await conn.fetch(
                f"""
                SELECT doc_id, payload,
                       1 - (embedding <=> ${emb_idx}::vector) AS score
                FROM {table}
                WHERE {where}
                ORDER BY embedding <=> ${emb_idx}::vector
                LIMIT ${limit_idx}
                """,
                *params,
            )
        out: List[Dict[str, Any]] = []
        for row in rows:
            payload = row["payload"]
            if isinstance(payload, str):
                payload = json.loads(payload)
            meta = dict(payload or {})
            content = meta.pop("content", "") or ""
            out.append(
                {
                    "id": row["doc_id"],
                    "content": content,
                    "meta": meta,
                    "score": float(row["score"] or 0.0),
                }
            )
        return out

    async def delete_documents(self, filters: Optional[Dict[str, Any]] = None) -> None:
        table = await self._table()
        where, params = _filter_to_sql(filters, collection=self._collection)
        pool = await get_genbi_vector_pool()
        async with pool.acquire() as conn:
            await register_vector(conn)
            await conn.execute(f"DELETE FROM {table} WHERE {where}", *params)

    async def count_documents(self, filters: Optional[Dict[str, Any]] = None) -> int:
        table = await self._table()
        where, params = _filter_to_sql(filters, collection=self._collection)
        pool = await get_genbi_vector_pool()
        async with pool.acquire() as conn:
            await register_vector(conn)
            row = await conn.fetchrow(f"SELECT COUNT(*) AS c FROM {table} WHERE {where}", *params)
        return int(row["c"] if row else 0)

    async def purge_project(self, project_id: str) -> None:
        table = await self._table()
        pool = await get_genbi_vector_pool()
        async with pool.acquire() as conn:
            await register_vector(conn)
            await conn.execute(
                f"DELETE FROM {table} WHERE collection = $1 AND project_id = $2",
                self._collection,
                str(project_id),
            )
