from __future__ import annotations
import re
from dataclasses import dataclass, field
from app.agents.tools.analysis.chunk_loader import ChunkRecord
from app.utils.logger import logger
from app.tools.document.chunkers.section_aware_chunker import (  
    _HEADING_RE,
    _classify_title,
    _is_noise_heading,
    _normalize_section_title,
)

SECTION_TYPES = frozenset({
    "abstract", "introduction", "background", "related_work",
    "methodology", "methods", "results", "experiments",
    "discussion", "conclusion", "future_work", "limitations",
    "references", "appendix", "acknowledgments", "other",
})
_NUMBERED_PREFIX_RE = re.compile(r"^(\d+(?:\.\d+){0,3})\.?\s+")
_SPLIT_NUMBERED_HEADING = re.compile(
    r"(?m)^[ \t]*(\d+(?:\.\d+){0,2}\.?)[ \t]*\n[ \t]*([A-Z][A-Za-z].{2,118})$"
)

def _heading_depth(title: str) -> int:
    m = _NUMBERED_PREFIX_RE.match(title)
    if not m:
        return 0
    
    return m.group(1).count(".") + 1


def _heading_top_prefix(title: str) -> str | None:
    m = _NUMBERED_PREFIX_RE.match(title)
    if not m:
        return None
    return m.group(1).split(".", 1)[0]

@dataclass
class MappedSection:
    index: int
    title: str
    section_type: str
    chunks: list[ChunkRecord] = field(default_factory=list)
    number: str | None = None
    subsections: list[dict] = field(default_factory=list)

    @property
    def merged_content(self) -> str:
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

class SectionMapperTool:
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

    def _map_from_metadata(
        self, chunks: list[ChunkRecord]
    ) -> list[MappedSection]:
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

    def _map_from_headings(
        self, chunks: list[ChunkRecord]
    ) -> list[MappedSection]:
        offsets: list[tuple[int, int, ChunkRecord]] = [] 
        cursor = 0
        parts: list[str] = []
        for chunk in chunks:
            content = chunk.content or ""
            parts.append(content)
            offsets.append((cursor, cursor + len(content), chunk))
            cursor += len(content) + 2  # account for "\n\n" join below

        full_text = "\n\n".join(parts)
        full_text = _SPLIT_NUMBERED_HEADING.sub(r"\1 \2", full_text)
        heading_positions: list[tuple[int, str]] = []
        for m in _HEADING_RE.finditer(full_text):
            title = m.group(1).strip()
            if _is_noise_heading(title):
                continue
            heading_positions.append((m.start(), _normalize_section_title(title)))

        if not heading_positions:
            return []

        def chunk_for_pos(pos: int) -> int:
            for i, (start, end, _c) in enumerate(offsets):
                if start <= pos < end:
                    return i
            return len(offsets) - 1

        cut_points: list[tuple[int, str]] = []
        for pos, title in heading_positions:
            cidx = chunk_for_pos(pos)
            if cut_points and cut_points[-1][0] == cidx:
                continue
            cut_points.append((cidx, title))

        sections: list[MappedSection] = []

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

        sections = self._coalesce_subsections(sections)
        for new_idx, s in enumerate(sections):
            s.index = new_idx

        return sections

    def _coalesce_subsections(
        self, sections: list[MappedSection]
    ) -> list[MappedSection]:
        if not sections:
            return sections

        out: list[MappedSection] = []
        parent_by_prefix: dict[str, MappedSection] = {}

        for s in sections:
            depth = _heading_depth(s.title)
            top_prefix = _heading_top_prefix(s.title)

            if depth == 1 and top_prefix is not None:
                out.append(s)
                parent_by_prefix[top_prefix] = s
            elif depth >= 2 and top_prefix is not None and top_prefix in parent_by_prefix:
                parent = parent_by_prefix[top_prefix]
                parent.chunks = parent.chunks + s.chunks
            else:
                out.append(s)

        return out
