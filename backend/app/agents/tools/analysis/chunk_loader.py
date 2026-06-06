"""ChunkLoaderTool — load DocumentChunks (and their embeddings) for analysis.

Unlike the legacy AnalysisAgent, which concatenated all chunk content into a
single string and truncated at 12K chars, this tool returns chunks as-is so
downstream tools can analyse them per-section, retrieve them semantically,
and cite them by index.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.chunk_embedding import ChunkEmbedding
from app.models.document_chunk import DocumentChunk


@dataclass
class ChunkRecord:
    """Lightweight in-memory view of a DocumentChunk for the agent."""

    id: UUID
    chunk_index: int
    content: str
    metadata: dict[str, Any] = field(default_factory=dict)
    has_embedding: bool = False
    embedding_model: str | None = None
    # We do NOT carry the embedding vector in memory by default — it's large
    # and the SemanticRetriever queries the DB directly via pgvector.


class ChunkLoaderTool:
    """Load DocumentChunks for a document, ordered by chunk_index."""

    async def load(
        self, db: AsyncSession, document_id: UUID
    ) -> list[ChunkRecord]:
        stmt = (
            select(DocumentChunk)
            .options(selectinload(DocumentChunk.embedding))
            .where(DocumentChunk.document_id == document_id)
            .order_by(DocumentChunk.chunk_index)
        )
        result = await db.execute(stmt)
        rows = result.scalars().all()

        records: list[ChunkRecord] = []
        for row in rows:
            embedding: ChunkEmbedding | None = row.embedding
            records.append(
                ChunkRecord(
                    id=row.id,
                    chunk_index=row.chunk_index,
                    content=row.content or "",
                    metadata=row.chunk_metadata or {},
                    has_embedding=embedding is not None,
                    embedding_model=(
                        embedding.embedding_model if embedding is not None else None
                    ),
                )
            )

        return records
