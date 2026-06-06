"""OutlineBuilderTool — produce a document-level outline with ZERO LLM calls.

Originally this tool sent the section excerpts to the LLM to ask for a title,
document_type, main_topics, and one_line_purpose per section. With free-tier
LLM quota we cannot afford that round-trip, especially since the data we
need is largely deterministic:

- ``title`` is already on the document row
- ``document_type`` can be inferred from the section_type distribution
  (presence of abstract + methods + results → academic_paper, etc.)
- ``main_topics`` are not critical for the UI — we leave them empty here
  and let the cross-section synthesizer fill them in if needed
- ``one_line_purpose`` per section is also optional; the section_type chip
  and one-line preview already give the reader what they need

Saving one LLM call per analysis matters when the user is on Gemini free
tier (5 RPM) or Groq free tier — the synthesis call later uses that quota
to do something the heuristic cannot.
"""

from __future__ import annotations

from typing import Any  # noqa: F401  — kept for backwards compatibility

from app.agents.tools.analysis.section_mapper import MappedSection
from app.utils.logger import logger


class OutlineBuilderTool:
    """Build a structured outline of the document, deterministically."""

    async def build(
        self,
        document_title: str,
        sections: list[MappedSection],
        llm: Any = None,  # noqa: ARG002 — kept for API compat, no longer used
    ) -> dict | None:
        if not sections:
            return None

        document_type = _infer_document_type(sections)
        outline = {
            "title": document_title or "Untitled",
            "document_type": document_type,
            "main_topics": [],
            "primary_audience": "",
            "sections": [
                {
                    "index": s.index,
                    "title": s.title,
                    "number": s.number,
                    "type": s.section_type,
                    # one_line_purpose is now empty by default; the FE
                    # gracefully hides it when missing.
                    "one_line_purpose": "",
                    "chunk_count": len(s.chunks),
                    "char_count": s.total_chars,
                    "subsections": list(s.subsections or []),
                }
                for s in sections
            ],
        }

        logger.info(
            f"OutlineBuilder: deterministic outline (document_type={document_type}, "
            f"{len(sections)} sections, 0 LLM calls)"
        )
        return outline


# ---------------------------------------------------------------------------
# Heuristics
# ---------------------------------------------------------------------------

def _infer_document_type(sections: list[MappedSection]) -> str:
    """Classify the document based on which canonical sections are present.

    The decision tree is intentionally simple. Order matters: more specific
    types are checked before broader fall-throughs.
    """
    types_seen: set[str] = {s.section_type for s in sections}

    # Academic paper: at least 3 of {abstract, introduction, methods, results,
    # discussion, conclusion, references}.
    paper_markers = {
        "abstract", "introduction", "methodology", "methods",
        "results", "experiments", "discussion", "conclusion",
        "references",
    }
    if len(types_seen & paper_markers) >= 3:
        return "academic_paper"

    # Thesis: paper markers + appendix usually means a thesis.
    if "appendix" in types_seen and len(types_seen & paper_markers) >= 4:
        return "thesis"

    # Review article: discussion + related_work + lots of references.
    if {"related_work", "discussion"} <= types_seen:
        return "review_article"

    # Technical report: introduction + methods/results without abstract.
    if "abstract" not in types_seen and (
        types_seen & {"methodology", "methods", "results", "experiments"}
    ):
        return "technical_report"

    # White paper: introduction + conclusion only.
    if {"introduction", "conclusion"} <= types_seen:
        return "white_paper"

    # Book chapter: lots of subsections detected by the chunker.
    total_subs = sum(len(s.subsections or []) for s in sections)
    if total_subs >= 6:
        return "book_chapter"

    return "other"
