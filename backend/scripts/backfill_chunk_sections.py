"""Re-tag DocumentChunk.chunk_metadata with section info using the latest
SectionAwareChunker heading regex.

When the heading regex changes (e.g. tightening false-positive matches), any
documents already ingested keep their stale `section_title` / `section_type`
in chunk_metadata. This script scans every document, rebuilds the heading
spans from `document.content`, and updates each chunk's metadata in place.

Usage:
    venv\\Scripts\\python.exe -m scripts.backfill_chunk_sections             # all docs
    venv\\Scripts\\python.exe -m scripts.backfill_chunk_sections --doc <uuid> # one doc

Safety: existing keys other than `section_title`/`section_type`/`char_offset`
are preserved.
"""

from __future__ import annotations

import argparse
import asyncio
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.session import AsyncSessionLocal
from app.models.document import Document
from app.models.document_chunk import DocumentChunk
from app.tools.document.chunkers.section_aware_chunker import (
    _detect_sections,
    _find_section_for_offset,
    _normalize_text,
)
from app.utils.logger import logger


_PRESERVE_KEYS = {"page", "page_number", "source_url", "language"}


async def _backfill_one(db: AsyncSession, document: Document) -> int:
    """Return number of chunks updated."""
    if not document.content:
        logger.warning(f"  doc {document.id}: no document.content, skipping")
        return 0

    chunks_result = await db.execute(
        select(DocumentChunk)
        .where(DocumentChunk.document_id == document.id)
        .order_by(DocumentChunk.chunk_index)
    )
    chunks = list(chunks_result.scalars().all())
    if not chunks:
        return 0

    spans = _detect_sections(_normalize_text(document.content))
    if spans:
        logger.info(
            f"  doc {document.id}: detected {len(spans)} sections "
            f"(first 3: {[s.title for s in spans[:3]]})"
        )
    else:
        logger.info(f"  doc {document.id}: no headings detected")

    text = document.content
    cursor = 0
    updates = 0
    for chunk in chunks:
        offset = text.find(chunk.content or "", cursor)
        if offset < 0:
            offset = text.find(chunk.content or "")
        if offset < 0:
            offset = cursor
        end = offset + len(chunk.content or "")
        cursor = max(cursor, end - 50)  # small overlap-tolerance window

        midpoint = (offset + end) // 2
        section = _find_section_for_offset(spans, midpoint)

        existing = dict(chunk.chunk_metadata or {})
        # Strip stale section tags first
        for k in ("section_title", "section_type"):
            existing.pop(k, None)
        existing["char_offset"] = offset
        if section is not None:
            existing["section_title"] = section.title
            existing["section_type"] = section.section_type

        chunk.chunk_metadata = existing
        updates += 1

    await db.commit()
    return updates


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--doc", help="Single document UUID to backfill")
    args = parser.parse_args()

    async with AsyncSessionLocal() as db:
        if args.doc:
            doc_id = UUID(args.doc)
            result = await db.execute(select(Document).where(Document.id == doc_id))
            documents = [result.scalar_one()]
        else:
            result = await db.execute(select(Document))
            documents = list(result.scalars().all())

        logger.info(f"Backfilling {len(documents)} document(s)")
        total = 0
        for doc in documents:
            try:
                count = await _backfill_one(db, doc)
                total += count
                logger.success(
                    f"  doc {doc.id} ({doc.title[:60]!r}): {count} chunks updated"
                )
            except Exception as e:
                logger.error(f"  doc {doc.id}: failed: {e}")
                await db.rollback()

        logger.success(f"Done. {total} chunk metadata rows updated.")


if __name__ == "__main__":
    asyncio.run(main())
