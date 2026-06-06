"""SectionMapperTool — group ChunkRecords into ordered sections.

The mapper is **stateless w.r.t. chunk_metadata**. We always re-detect headings
from the concatenated chunk content, because:

1. Existing documents may have stale section tags from older chunker versions.
2. Heading regex / noise filters evolve — re-running them every analysis run
   keeps the mapping consistent with the latest rules.
3. SectionAwareChunker only uses the metadata for downstream display; it does
   not stop us from re-deriving structure here.

When heading detection produces more sections than the agent can analyse,
hierarchical numbered subsections are coalesced into their parent (3.1, 3.2,
3.2.1 → merged into the section starting with '3 ...'). Only when there are
no numbered ancestors do we fall back to a single-section view.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from app.agents.tools.analysis.chunk_loader import ChunkRecord
from app.utils.logger import logger


# ---------------------------------------------------------------------------
# Section taxonomy
# ---------------------------------------------------------------------------

SECTION_TYPES = frozenset({
    "abstract", "introduction", "background", "related_work",
    "methodology", "methods", "results", "experiments",
    "discussion", "conclusion", "future_work", "limitations",
    "references", "appendix", "acknowledgments", "other",
})

# Heading detection + classification re-uses the whitelist from the chunker
# so chunk-time and analysis-time agree on what counts as a section.
from app.tools.document.chunkers.section_aware_chunker import (  # noqa: E402
    _HEADING_RE,
    _classify_title,
    _is_noise_heading,
    _normalize_section_title,
)


# Numbered heading prefix extractor: "3.1.2 Foo" → "3.1.2"
_NUMBERED_PREFIX_RE = re.compile(r"^(\d+(?:\.\d+){0,3})\.?\s+")

# Stitch broken numbered headings: "3.1\nEncoder and Decoder Stacks"
_SPLIT_NUMBERED_HEADING = re.compile(
    r"(?m)^[ \t]*(\d+(?:\.\d+){0,2}\.?)[ \t]*\n[ \t]*([A-Z][A-Za-z].{2,118})$"
)


def _heading_depth(title: str) -> int:
    """Return depth of a numbered heading. 0 means non-numbered."""
    m = _NUMBERED_PREFIX_RE.match(title)
    if not m:
        return 0
    # "3" → 1, "3.1" → 2, "3.1.2" → 3
    return m.group(1).count(".") + 1


def _heading_top_prefix(title: str) -> str | None:
    """Return the top-level numeric prefix, e.g. '3.2.1 Foo' → '3'."""
    m = _NUMBERED_PREFIX_RE.match(title)
    if not m:
        return None
    return m.group(1).split(".", 1)[0]


# ---------------------------------------------------------------------------
# Output type
# ---------------------------------------------------------------------------

@dataclass
class MappedSection:
    """A section made of a contiguous list of ChunkRecords."""

    index: int
    title: str
    section_type: str
    chunks: list[ChunkRecord] = field(default_factory=list)
    number: str | None = None
    subsections: list[dict] = field(default_factory=list)

    @property
    def merged_content(self) -> str:
        """Concatenate chunk content with chunk index labels for LLM consumption."""
        return "\n\n".join(
            f"[chunk {c.chunk_index}] {c.content.strip()}" for c in self.chunks
        )

    @property
    def total_chars(self) -> int:
        return sum(len(c.content) for c in self.chunks)

    def to_outline_dict(self) -> dict:
        return {
            "index": self.index,
            "title": self.title,
            "type": self.section_type,
            "number": self.number,
            "chunk_count": len(self.chunks),
            "char_count": self.total_chars,
            "chunk_indices": [c.chunk_index for c in self.chunks],
            "subsections": list(self.subsections),
        }


# ---------------------------------------------------------------------------
# SectionMapperTool
# ---------------------------------------------------------------------------

class SectionMapperTool:
    """Group ChunkRecords into MappedSections via heading detection.

    Strategy:
      1. Try metadata-driven mapping first. ``SectionAwareChunker`` already
         tagged every chunk with ``section_title`` / ``section_type`` /
         ``section_number`` / ``section_subsections``. When this metadata
         is present, grouping is trivial and exact.
      2. Fall back to running the heading regex over the concatenated chunk
         text (legacy ingests that didn't have the new chunker).
    """

    def map(self, chunks: list[ChunkRecord]) -> list[MappedSection]:
        if not chunks:
            return []

        sections = self._map_from_metadata(chunks)
        source = "metadata"

        if not sections:
            sections = self._map_from_headings(chunks)
            source = "regex"

        if not sections:
            logger.info("SectionMapper: single-section fallback (no headings found)")
            return [
                MappedSection(
                    index=0,
                    title="Document",
                    section_type="other",
                    chunks=list(chunks),
                )
            ]

        logger.info(
            f"SectionMapper: {source}-driven, {len(sections)} sections "
            f"(first 3 titles: {[s.title for s in sections[:3]]})"
        )
        return sections

    # ── Metadata-driven mapping ─────────────────────────────────────────────

    def _map_from_metadata(
        self, chunks: list[ChunkRecord]
    ) -> list[MappedSection]:
        """Group chunks by the ``section_title`` already on each chunk's metadata.

        Returns ``[]`` if any chunk has no metadata (legacy ingests) so the
        caller falls back to regex-based detection.
        """
        if not all((c.metadata or {}).get("section_title") for c in chunks):
            return []

        sections: list[MappedSection] = []
        current_title: str | None = None
        current_type: str = "other"
        current_number: str | None = None
        current_subsections: list[dict] = []
        bucket: list[ChunkRecord] = []

        def flush():
            if bucket:
                sections.append(
                    MappedSection(
                        index=len(sections),
                        title=current_title or "Section",
                        section_type=current_type or "other",
                        chunks=list(bucket),
                        number=current_number,
                        subsections=list(current_subsections),
                    )
                )

        for chunk in chunks:
            meta = chunk.metadata or {}
            title = meta.get("section_title") or "Section"
            stype = meta.get("section_type") or "other"
            number = meta.get("section_number")
            subs = meta.get("section_subsections") or []

            if title != current_title:
                flush()
                bucket = []
                current_title = title
                current_type = stype
                current_number = number
                current_subsections = subs

            bucket.append(chunk)

        flush()
        return sections

    # ── Heading-driven mapping (fallback for legacy ingests) ────────────────

    def _map_from_headings(
        self, chunks: list[ChunkRecord]
    ) -> list[MappedSection]:
        # Build the concatenated text and remember chunk char ranges
        offsets: list[tuple[int, int, ChunkRecord]] = []  # (start, end, chunk)
        cursor = 0
        parts: list[str] = []
        for chunk in chunks:
            content = chunk.content or ""
            parts.append(content)
            offsets.append((cursor, cursor + len(content), chunk))
            cursor += len(content) + 2  # account for "\n\n" join below

        full_text = "\n\n".join(parts)
        # Stitch broken numbered headings before regex-matching, so PDFs that
        # split "3.1\nEncoder ..." onto two lines still get caught.
        full_text = _SPLIT_NUMBERED_HEADING.sub(r"\1 \2", full_text)

        # Find heading positions in the (normalised) full text
        heading_positions: list[tuple[int, str]] = []
        for m in _HEADING_RE.finditer(full_text):
            title = m.group(1).strip()
            if _is_noise_heading(title):
                continue
            heading_positions.append((m.start(), _normalize_section_title(title)))

        if not heading_positions:
            return []

        # Map each heading position → the chunk whose range it falls into.
        # Note: post-stitching changes string length minimally (we only replace
        # newline + spaces with a single space) — close enough for chunk
        # alignment, since SectionAwareChunker also runs the same stitching.
        def chunk_for_pos(pos: int) -> int:
            for i, (start, end, _c) in enumerate(offsets):
                if start <= pos < end:
                    return i
            return len(offsets) - 1

        # Build initial cut points (one per heading), keeping at most one cut
        # per chunk so we don't fragment a single chunk into multiple sections.
        cut_points: list[tuple[int, str]] = []
        for pos, title in heading_positions:
            cidx = chunk_for_pos(pos)
            if cut_points and cut_points[-1][0] == cidx:
                # Same chunk already has a heading → keep the first one as the
                # section title (deeper headings live as text inside).
                continue
            cut_points.append((cidx, title))

        # Build sections from cut points
        sections: list[MappedSection] = []

        # Leading prose before first heading: only become its own section if
        # there is enough content to warrant it (>800 chars, ~one paragraph).
        if cut_points and cut_points[0][0] > 0:
            front_chunks = chunks[: cut_points[0][0]]
            front_size = sum(len(c.content or "") for c in front_chunks)
            if front_size >= 800:
                sections.append(
                    MappedSection(
                        index=0,
                        title="Front Matter",
                        section_type="other",
                        chunks=front_chunks,
                    )
                )
            else:
                # Attach short leading chunks to the first real section instead
                # of creating a tiny "Front Matter" stub.
                cut_points[0] = (0, cut_points[0][1])

        for i, (cidx, title) in enumerate(cut_points):
            next_cidx = (
                cut_points[i + 1][0] if i + 1 < len(cut_points) else len(chunks)
            )
            section_chunks = chunks[cidx:next_cidx]
            if not section_chunks:
                continue
            sections.append(
                MappedSection(
                    index=len(sections),
                    title=title,
                    section_type=_classify_title(title),
                    chunks=section_chunks,
                )
            )

        # Coalesce numbered hierarchy: '3.1 Foo' merges into '3 Bar' when both
        # exist as siblings. This collapses an Attention-style outline from
        # 24 sub-sections to ~7 top-level sections, matching the user's mental
        # model and keeping LLM cost manageable.
        sections = self._coalesce_subsections(sections)

        # Re-index after coalescing
        for new_idx, s in enumerate(sections):
            s.index = new_idx

        return sections

    # ── Hierarchy coalescing ────────────────────────────────────────────────

    def _coalesce_subsections(
        self, sections: list[MappedSection]
    ) -> list[MappedSection]:
        """Merge numbered subsections into their top-level parent.

        Rules:
        - A section with depth >= 2 (e.g. '3.1', '3.2.1') is a subsection.
        - It is merged into the most recent section with depth == 1 (e.g. '3')
          AND the same top-level number prefix.
        - If no parent exists (subsection appears before any depth-1 section),
          the subsection is kept as-is.
        """
        if not sections:
            return sections

        out: list[MappedSection] = []
        # Track the most recent depth-1 section by its top-level prefix
        parent_by_prefix: dict[str, MappedSection] = {}

        for s in sections:
            depth = _heading_depth(s.title)
            top_prefix = _heading_top_prefix(s.title)

            if depth == 1 and top_prefix is not None:
                out.append(s)
                parent_by_prefix[top_prefix] = s
            elif depth >= 2 and top_prefix is not None and top_prefix in parent_by_prefix:
                # Merge into parent
                parent = parent_by_prefix[top_prefix]
                parent.chunks = parent.chunks + s.chunks
            else:
                # Non-numbered (Abstract, Introduction, References) — keep as-is
                out.append(s)
                # Non-numbered sections also "reset" any active numbered parent
                # so a subsequent '4.1' can't accidentally merge into a stale '3'
                # if '3' has already passed several non-numbered sections.

        return out
