"""Haystack DocumentStore backed by GenBI pgvector (PostgreSQL)."""

from __future__ import annotations

import logging
import os
from typing import Any, Dict, List, Optional

from haystack import Document, component
from haystack.document_stores.types import DuplicatePolicy

from src.core.provider import DocumentStoreProvider
from src.providers.loader import provider

logger = logging.getLogger("wren-ai-service")


def _cred_from_env():
    from app.config.setting import settings
    from app.modules.genbi.ai.llm_context import ResolvedEmbedding

    dims = int(getattr(settings, "GENBI_EMBEDDING_DIMENSIONS", 1024) or 1024)
    return ResolvedEmbedding(
        api_key=(
            getattr(settings, "GENBI_EMBED_API_KEY", "")
            or settings.OPENAI_API_KEY
            or ""
        ).strip(),
        base_url=(
            getattr(settings, "GENBI_EMBED_API_BASE", "")
            or settings.OPENAI_BASE_URL
            or ""
        ).strip()
        or None,
        model_id=(getattr(settings, "GENBI_EMBEDDING_MODEL_ID", "") or "").strip(),
        source="env",
        dimensions=dims,
    )


def _resolve_embedding_cred():
    """Prefer scoped embedding credentials; env only as last resort."""
    from app.modules.genbi.ai.llm_context import ResolvedEmbedding, current_credentials

    creds = current_credentials()
    if creds is not None and hasattr(creds, "to_resolved_embedding"):
        return creds.to_resolved_embedding()
    if isinstance(creds, ResolvedEmbedding):
        return creds
    return _cred_from_env()


class AsyncPgvectorDocumentStore:
    """Async Haystack document store backed by GenBI pgvector."""

    def __init__(
        self,
        *,
        index: str = "Document",
        embedding_dim: int = 1024,
        progress_bar: bool = True,
        recreate_index: bool = False,
    ):
        self.index = index
        self.embedding_dim = embedding_dim
        self.progress_bar = progress_bar
        self.recreate_index = recreate_index

    def _store(self):
        from app.modules.genbi.ai.vector.store import GenbiPgvectorStore

        return GenbiPgvectorStore(_resolve_embedding_cred(), collection=self.index)

    def to_dict(self) -> Dict[str, Any]:
        """Haystack DocumentCleaner logs store name via init_parameters.index."""
        return {
            "type": "AsyncPgvectorDocumentStore",
            "init_parameters": {
                "index": self.index,
                "embedding_dim": self.embedding_dim,
                "progress_bar": self.progress_bar,
                "recreate_index": self.recreate_index,
            },
        }

    async def write_documents(
        self,
        documents: List[Document],
        policy: DuplicatePolicy = DuplicatePolicy.FAIL,
    ) -> int:
        del policy  # upsert semantics
        if not documents:
            logger.warning("AsyncPgvectorDocumentStore.write_documents() with empty list")
            return 0
        by_project: Dict[str, List[Dict[str, Any]]] = {}
        for doc in documents:
            if not isinstance(doc, Document):
                raise ValueError(f"Expected Document, got {type(doc)}")
            flat = doc.to_dict(flatten=True)
            embedding = flat.pop("embedding", None)
            if embedding is None:
                continue
            meta = {k: v for k, v in flat.items() if k not in ("content", "id")}
            project_id = str(meta.get("project_id") or "").strip()
            if not project_id:
                logger.warning("pgvector write skipped doc without project_id id=%s", doc.id)
                continue
            by_project.setdefault(project_id, []).append(
                {
                    "doc_id": str(doc.id),
                    "embedding": embedding,
                    "meta": meta,
                    "content": flat.get("content") or doc.content or "",
                }
            )
        store = self._store()
        total = 0
        for project_id, batch in by_project.items():
            total += await store.upsert_documents(project_id=project_id, documents=batch)
        return total

    async def delete_documents(self, filters: Optional[Dict[str, Any]] = None) -> None:
        await self._store().delete_documents(filters)

    async def count_documents(self, filters: Optional[Dict[str, Any]] = None) -> int:
        return await self._store().count_documents(filters)

    async def _query_by_embedding(
        self,
        query_embedding: List[float],
        filters: Optional[Dict[str, Any]] = None,
        top_k: int = 10,
        scale_score: bool = True,
        return_embedding: bool = False,
    ) -> List[Document]:
        del return_embedding
        project_id = None
        if filters and filters.get("operator") == "AND":
            for cond in filters.get("conditions") or []:
                if cond.get("field") == "project_id" and cond.get("operator") == "==":
                    project_id = str(cond.get("value") or "")
        hits = await self._store().search_by_embedding(
            query_embedding=query_embedding,
            project_id=project_id or None,
            top_k=top_k,
            filters=filters,
        )
        docs: List[Document] = []
        for hit in hits:
            score = float(hit.get("score") or 0.0)
            if scale_score:
                score = (score + 1) / 2
            docs.append(
                Document(
                    id=hit["id"],
                    content=hit.get("content") or "",
                    meta=hit.get("meta") or {},
                    score=score,
                )
            )
        return docs

    async def _query_by_filters(
        self,
        filters: Optional[Dict[str, Any]] = None,
        top_k: Optional[int] = None,
    ) -> List[Document]:
        limit = top_k if top_k is not None else 500
        hits = await self._store().list_documents(filters=filters, limit=limit)
        return [
            Document(
                id=hit["id"],
                content=hit.get("content") or "",
                meta=hit.get("meta") or {},
            )
            for hit in hits
        ]


class AsyncPgvectorEmbeddingRetriever:
    def __init__(
        self,
        document_store: AsyncPgvectorDocumentStore,
        filters: Optional[Dict[str, Any]] = None,
        top_k: int = 10,
        scale_score: bool = True,
        return_embedding: bool = False,
    ):
        self._document_store = document_store
        self._filters = filters
        self._top_k = top_k
        self._scale_score = scale_score
        self._return_embedding = return_embedding

    @component.output_types(documents=List[Document])
    async def run(
        self,
        query_embedding: List[float],
        filters: Optional[Dict[str, Any]] = None,
        top_k: Optional[int] = None,
        scale_score: Optional[bool] = None,
        return_embedding: Optional[bool] = None,
    ):
        del return_embedding
        if query_embedding:
            docs = await self._document_store._query_by_embedding(
                query_embedding=query_embedding,
                filters=filters or self._filters,
                top_k=top_k or self._top_k,
                scale_score=scale_score if scale_score is not None else self._scale_score,
            )
        else:
            docs = await self._document_store._query_by_filters(filters=filters)
        return {"documents": docs}


@provider("pgvector")
class PgvectorProvider(DocumentStoreProvider):
    def __init__(
        self,
        embedding_model_dim: int = 0,
        recreate_index: bool = False,
        **_,
    ):
        from app.core.config import settings

        dim = int(embedding_model_dim or 0)
        if dim <= 0:
            dim = int(settings.SESSION_FILE_EMBEDDING_DIMENSIONS or 0)
        if dim <= 0:
            raise ValueError(
                "pgvector document_store requires embedding_model_dim or SESSION_FILE_EMBEDDING_DIMENSIONS"
            )
        self._embedding_model_dim = dim
        self._recreate_index = bool(
            recreate_index or (os.getenv("SHOULD_FORCE_DEPLOY") or "").lower() in ("1", "true")
        )
        self._reset_document_store(self._recreate_index)

    def _reset_document_store(self, recreate_index: bool) -> None:
        for name in (
            "Document",
            "table_descriptions",
            "view_questions",
            "sql_pairs",
            "instructions",
            "project_meta",
        ):
            self.get_store(dataset_name=name, recreate_index=recreate_index)

    def get_store(
        self,
        dataset_name: Optional[str] = None,
        recreate_index: bool = False,
    ) -> AsyncPgvectorDocumentStore:
        del recreate_index
        return AsyncPgvectorDocumentStore(
            index=dataset_name or "Document",
            embedding_dim=self._embedding_model_dim,
            recreate_index=self._recreate_index,
        )

    def get_retriever(
        self,
        document_store: AsyncPgvectorDocumentStore,
        top_k: int = 10,
    ):
        return AsyncPgvectorEmbeddingRetriever(
            document_store=document_store,
            top_k=top_k,
        )
