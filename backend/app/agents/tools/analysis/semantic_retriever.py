"""SemanticRetrieverTool — pgvector-backed top-k chunk retrieval.

Used for aspect-based deep dives ("retrieve chunks relevant to evidence
quality", "retrieve chunks discussing limitations") without sending the
whole document to the LLM. The agent decides which queries to run.

This tool wraps:
  - EmbeddingFactory + ProviderEmbeddingGenerator: produce a query vector
  - PGVectorStore.similarity_search: cosine-distance top-k from chunk_embeddings

The retriever filters results to the current document_id so it never crosses
document boundaries.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.tools.analysis.chunk_loader import ChunkRecord
from app.config import settings
from app.models.chunk_embedding import ChunkEmbedding
from app.models.document_chunk import DocumentChunk
from app.models.embedding_providers.factory import EmbeddingFactory
from app.models.embedding_providers.types import EmbeddingProviderType
from app.utils.logger import logger


class SemanticRetrieverTool:
    """Top-k chunk retrieval scoped to a single document."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self._embedder = None  # lazy

    async def retrieve(
        self,
        document_id: UUID,
        query: str,
        top_k: int = 5,
    ) -> list[ChunkRecord]:
        """Embed `query`, return top-k ChunkRecords from this document only."""
        if not query.strip():
            return []

        try:
            embedder = self._get_embedder()
            vectors = await embedder.embed_batch([query])
        except Exception as e:
            logger.warning(f"SemanticRetriever: embedding failed: {e}")
            return []

        if not vectors:
            return []

        query_vector = vectors[0]

        # Direct query — we need to filter by document_id, which the generic
        # PGVectorStore.similarity_search does not support. Run an inline
        # query with the same cosine_distance ordering.
        stmt = (
            select(DocumentChunk, ChunkEmbedding)
            .join(ChunkEmbedding, ChunkEmbedding.chunk_id == DocumentChunk.id)
            .where(DocumentChunk.document_id == document_id)
            .order_by(ChunkEmbedding.embedding.cosine_distance(query_vector))
            .limit(top_k)
        )
        try:
            result = await self.db.execute(stmt)
        except Exception as e:
            logger.warning(f"SemanticRetriever: pgvector query failed: {e}")
            return []

        records: list[ChunkRecord] = []
        for chunk, embedding in result.all():
            records.append(
                ChunkRecord(
                    id=chunk.id,
                    chunk_index=chunk.chunk_index,
                    content=chunk.content or "",
                    metadata=chunk.chunk_metadata or {},
                    has_embedding=True,
                    embedding_model=embedding.embedding_model,
                )
            )
        return records

    # ── Helpers ──────────────────────────────────────────────────────────────

    def _get_embedder(self):
        if self._embedder is not None:
            return self._embedder
        provider_type = EmbeddingProviderType(settings.EMBEDDING_PROVIDER)
        self._embedder = EmbeddingFactory.create_provider(
            provider_type,
            model=settings.EMBEDDING_MODEL or None,
        )
        return self._embedder
