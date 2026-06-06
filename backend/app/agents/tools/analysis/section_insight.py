"""SectionInsightTool — extract structured insights for a single section.

Cost model: ONE LLM call per section. Long sections are truncated rather
than map-reduced because map-reduce burns N+1 LLM calls per section, which
quickly exhausts free-tier quota (Gemini: 5 RPM, Groq: 30 RPM). Modern LLMs
handle 16 K characters easily, and section_insight prompts only need the
"shape" of the content — the head + tail of a long section is enough for the
LLM to extract claims, methods, data, tables, formulas. Truncation strategy:
keep the first ~10 K chars and the last ~6 K chars, skipping the middle.

The output schema is documented in app/prompts/analysis.py
(``SECTION_INSIGHT_SYSTEM_PROMPT``).

Robustness contract: ``analyse()`` ALWAYS returns a section insight dict
even when the LLM fails. When the LLM returns nothing parseable, we fall
back to a heuristic summary derived from the raw section text so the UI
never shows a fully empty card with no signal at all.
"""

from __future__ import annotations

import re
from typing import Any

from app.agents.tools.analysis.chunk_loader import ChunkRecord  # noqa: F401  used in type hints
from app.agents.tools.analysis.json_utils import parse_llm_json
from app.agents.tools.analysis.section_mapper import MappedSection
from app.prompts.analysis import (
    SECTION_INSIGHT_SYSTEM_PROMPT,
    SECTION_INSIGHT_USER_PROMPT,
)
from app.utils.logger import logger


# Hard cap on the section text we send in a single LLM call. Modern LLMs
# accept much more (Gemini 1M, Claude 200K) but we keep this conservative
# so we don't blow up the output token budget on the response side.
_SINGLE_CALL_MAX_CHARS = 16_000

# When a section is longer than the cap, we keep this many chars at the
# head and the rest at the tail (with a [...] elision marker in the middle).
# Rationale: in academic writing the opening usually states the claim and
# the methods, while the closing usually states the results and limitations.
# Mid-section examples / derivations contribute less per char to the insight.
_HEAD_BUDGET = 10_000


# Empty insight skeleton — used as a safe fallback or to fill missing keys
_EMPTY_INSIGHT: dict[str, Any] = {
    "summary": None,
    "purpose": None,
    "key_points": [],
    "claims": [],
    "methods_or_techniques": [],
    "data_or_experiments": [],
    "tables": [],
    "formulas": [],
    "notable_terms": [],
    "connections": [],
    "critique": {"strengths": [], "weaknesses": [], "assumptions": []},
    "open_questions": [],
    "notable_quotes": [],
}


class SectionInsightTool:
    """Produce one structured insight object per section."""

    async def analyse(
        self,
        section: MappedSection,
        document_title: str,
        document_type: str,
        total_sections: int,
        llm: Any,
    ) -> dict:
        """Return a SectionInsight dict (always returns; never raises).

        Always uses a single LLM call. Long sections are truncated head+tail
        — see module docstring for the rationale.
        """
        if not section.chunks:
            return self._wrap_section(section, dict(_EMPTY_INSIGHT))

        insight = await self._single_call(
            section, document_title, document_type, total_sections, llm
        )

        # Last-resort fallback: if the structured pipeline returned nothing
        # the user could see (no summary, no key_points, no claims, ...),
        # synthesise a heuristic summary from the raw section text so the
        # card never renders as a fully empty placeholder.
        if not self._has_meaningful_content(insight):
            heuristic = self._heuristic_fallback(section)
            # Preserve any structured items the pipeline did manage to
            # extract — only fill the empty slots.
            for key, value in heuristic.items():
                if not insight.get(key):
                    insight[key] = value

        return self._wrap_section(section, insight)

    # ── Single-call strategy ────────────────────────────────────────────────

    async def _single_call(
        self,
        section: MappedSection,
        document_title: str,
        document_type: str,
        total_sections: int,
        llm: Any,
    ) -> dict:
        section_text = self._truncate_for_llm(section.merged_content)
        try:
            response = await llm.generate(
                prompt=SECTION_INSIGHT_USER_PROMPT.format(
                    document_title=document_title or "Untitled",
                    document_type=document_type or "other",
                    section_title=section.title,
                    section_type=section.section_type,
                    section_index=section.index,
                    total_sections=total_sections,
                    section_text=section_text,
                ),
                system_prompt=SECTION_INSIGHT_SYSTEM_PROMPT,
                temperature=0.2,
                max_tokens=4000,
                response_format="json",
            )
        except Exception as e:
            logger.warning(
                f"SectionInsightTool single-call failed for "
                f"section[{section.index}] '{section.title}': {e}"
            )
            return await self._minimal_retry(section, llm)

        parsed = parse_llm_json(response)
        if not isinstance(parsed, dict):
            preview = (response or "")[:400].replace("\n", " ")
            logger.warning(
                f"SectionInsightTool: non-JSON response for section[{section.index}] "
                f"'{section.title}'. Preview: {preview!r}"
            )
            return await self._minimal_retry(section, llm)

        normalised = self._normalise(parsed, section)

        # If the LLM produced syntactically valid JSON but the body has no
        # meaningful content (every field empty), retry once with the
        # minimal prompt before giving up.
        if not self._has_meaningful_content(normalised):
            logger.info(
                f"SectionInsightTool: empty insight from main prompt for "
                f"section[{section.index}] '{section.title}', retrying with "
                f"minimal prompt"
            )
            retry = await self._minimal_retry(section, llm)
            if self._has_meaningful_content(retry):
                return retry
        return normalised

    @staticmethod
    def _truncate_for_llm(text: str) -> str:
        """Smart head+tail truncation that preserves the [chunk N] labels.

        For sections that fit under the cap, return as-is. Otherwise keep
        the first ``_HEAD_BUDGET`` chars (head) and the last
        ``_SINGLE_CALL_MAX_CHARS - _HEAD_BUDGET`` chars (tail), separated
        by a clearly marked elision so the LLM doesn't think we ran out of
        text.
        """
        if len(text) <= _SINGLE_CALL_MAX_CHARS:
            return text

        head = text[:_HEAD_BUDGET]
        tail_budget = _SINGLE_CALL_MAX_CHARS - _HEAD_BUDGET - 64
        tail = text[-tail_budget:] if tail_budget > 0 else ""
        return (
            head
            + "\n\n[... section truncated for LLM context window — "
            + f"omitting middle {len(text) - _HEAD_BUDGET - tail_budget} chars ...]\n\n"
            + tail
        )

    # ── Helpers ─────────────────────────────────────────────────────────────

    def _normalise(self, insight: dict, section: MappedSection) -> dict:
        """Coerce LLM output into the canonical schema, filling missing keys."""
        out = dict(_EMPTY_INSIGHT)
        # Deep-copy critique so callers can mutate safely
        out["critique"] = {"strengths": [], "weaknesses": [], "assumptions": []}

        if not isinstance(insight, dict):
            return out

        for key in ("summary", "purpose"):
            v = insight.get(key)
            if isinstance(v, str) and v.strip():
                out[key] = v.strip()

        for key in (
            "key_points",
            "claims",
            "methods_or_techniques",
            "data_or_experiments",
            "tables",
            "formulas",
            "notable_terms",
            "connections",
            "open_questions",
            "notable_quotes",
        ):
            v = insight.get(key)
            if isinstance(v, list):
                out[key] = v

        critique = insight.get("critique")
        if isinstance(critique, dict):
            for sub in ("strengths", "weaknesses", "assumptions"):
                v = critique.get(sub)
                if isinstance(v, list):
                    out["critique"][sub] = [s for s in v if isinstance(s, str)]

        # Validate notable_quotes chunk_index against this section
        valid_chunk_indices = {c.chunk_index for c in section.chunks}
        cleaned_quotes: list[dict] = []
        for q in out["notable_quotes"]:
            if not isinstance(q, dict):
                continue
            quote = q.get("quote")
            cidx = q.get("chunk_index")
            if not isinstance(quote, str) or not quote.strip():
                continue
            # Coerce chunk_index to int and validate
            try:
                cidx_int = int(cidx)
            except (TypeError, ValueError):
                cidx_int = section.chunks[0].chunk_index
            if cidx_int not in valid_chunk_indices:
                cidx_int = section.chunks[0].chunk_index
            cleaned_quotes.append(
                {"quote": quote.strip(), "chunk_index": cidx_int}
            )
        out["notable_quotes"] = cleaned_quotes

        # Validate tables: drop empty rows, coerce chunk_index, ensure
        # headers / rows are list[str] / list[list[str]]
        cleaned_tables: list[dict] = []
        for t in out["tables"]:
            if not isinstance(t, dict):
                continue
            headers = t.get("headers") or []
            rows = t.get("rows") or []
            if not isinstance(headers, list):
                continue
            if not isinstance(rows, list):
                continue

            headers = [str(h) for h in headers]
            cleaned_rows: list[list[str]] = []
            for r in rows:
                if not isinstance(r, list):
                    continue
                cells = [str(c) for c in r]
                if any(c.strip() for c in cells):
                    cleaned_rows.append(cells)

            # Drop tables that have neither headers nor rows
            if not headers and not cleaned_rows:
                continue

            cidx = t.get("chunk_index")
            try:
                cidx_int = int(cidx) if cidx is not None else section.chunks[0].chunk_index
            except (TypeError, ValueError):
                cidx_int = section.chunks[0].chunk_index
            if cidx_int not in valid_chunk_indices:
                cidx_int = section.chunks[0].chunk_index

            cleaned_tables.append({
                "title": (t.get("title") or "").strip() or None,
                "summary": (t.get("summary") or "").strip() or None,
                "headers": headers,
                "rows": cleaned_rows,
                "key_finding": (t.get("key_finding") or "").strip() or None,
                "chunk_index": cidx_int,
            })
        out["tables"] = cleaned_tables

        # Validate formulas: drop empty expression, coerce chunk_index, accept
        # variables list of {symbol, meaning}.
        cleaned_formulas: list[dict] = []
        for f in out["formulas"]:
            if not isinstance(f, dict):
                continue
            expression = (f.get("expression") or "").strip()
            if not expression:
                continue
            label = (f.get("label") or "").strip() or None
            latex = (f.get("latex") or "").strip() or None
            explanation = (f.get("explanation") or "").strip() or None

            cidx = f.get("chunk_index")
            try:
                cidx_int = int(cidx) if cidx is not None else section.chunks[0].chunk_index
            except (TypeError, ValueError):
                cidx_int = section.chunks[0].chunk_index
            if cidx_int not in valid_chunk_indices:
                cidx_int = section.chunks[0].chunk_index

            raw_vars = f.get("variables")
            cleaned_vars: list[dict] = []
            if isinstance(raw_vars, list):
                for v in raw_vars:
                    if not isinstance(v, dict):
                        continue
                    symbol = (v.get("symbol") or "").strip()
                    meaning = (v.get("meaning") or "").strip()
                    if not symbol:
                        continue
                    cleaned_vars.append({
                        "symbol": symbol,
                        "meaning": meaning or None,
                    })

            cleaned_formulas.append({
                "label": label,
                "expression": expression,
                "latex": latex,
                "explanation": explanation,
                "variables": cleaned_vars,
                "chunk_index": cidx_int,
            })
        out["formulas"] = cleaned_formulas

        return out

    def _wrap_section(self, section: MappedSection, insight: dict) -> dict:
        """Wrap a normalised insight with section identity fields."""
        return {
            "section_index": section.index,
            "section_type": section.section_type,
            "title": section.title,
            "number": section.number,
            "subsections": list(section.subsections or []),
            "chunk_indices": [c.chunk_index for c in section.chunks],
            "chunk_ids": [str(c.id) for c in section.chunks],
            **insight,
        }

    # ── Retry + fallback helpers ────────────────────────────────────────────

    def _has_meaningful_content(self, insight: dict) -> bool:
        """True iff the insight has anything the user could actually read.

        We require at least one of: a summary, a non-trivial key_points list,
        a claim, or a method/data/table/formula entry. The "shape" fields
        (notable_terms / quotes alone) don't count — they're not enough to
        carry a card on their own.
        """
        if (insight.get("summary") or "").strip():
            return True
        if insight.get("key_points"):
            return True
        for key in ("claims", "methods_or_techniques", "data_or_experiments",
                    "tables", "formulas"):
            if insight.get(key):
                return True
        return False

    async def _minimal_retry(
        self, section: MappedSection, llm: Any
    ) -> dict:
        """Last-chance LLM call asking only for ``summary`` + ``key_points``.

        Used when the main prompt fails (network error, JSON parse error,
        or "valid JSON but every field empty"). The minimal schema is far
        less likely to trigger truncation, safety-filter blocks, or token
        limits, which means we usually get *something* back.
        """
        section_text = section.merged_content[:8000]
        prompt = (
            "Read this section of a research document and return a JSON "
            "object with exactly two keys:\n"
            '{ "summary": <2-4 sentence prose summary>, '
            '"key_points": [<3-5 strings>] }\n\n'
            f"Section title: {section.title}\n"
            f"Section type: {section.section_type}\n\n"
            f"Section text:\n{section_text}\n\n"
            "JSON only. No markdown."
        )
        try:
            response = await llm.generate(
                prompt=prompt,
                system_prompt=(
                    "You are a research analyst. Output strict JSON. "
                    "If the section is too short to summarise, still produce "
                    "a one-sentence summary and an empty key_points array."
                ),
                temperature=0.2,
                max_tokens=900,
                response_format="json",
            )
        except Exception as e:
            logger.warning(
                f"SectionInsightTool minimal retry failed for "
                f"section[{section.index}] '{section.title}': {e}"
            )
            return dict(_EMPTY_INSIGHT)

        parsed = parse_llm_json(response)
        if not isinstance(parsed, dict):
            return dict(_EMPTY_INSIGHT)

        out = dict(_EMPTY_INSIGHT)
        out["critique"] = {"strengths": [], "weaknesses": [], "assumptions": []}
        summary = parsed.get("summary")
        if isinstance(summary, str) and summary.strip():
            out["summary"] = summary.strip()
        kp = parsed.get("key_points")
        if isinstance(kp, list):
            out["key_points"] = [s for s in kp if isinstance(s, str) and s.strip()]
        return out

    def _heuristic_fallback(self, section: MappedSection) -> dict:
        """Build a minimal insight from raw text when every LLM call failed.

        Picks the first 2-3 substantive sentences as a summary and a few
        more as bullet ``key_points`` so the user at least sees the source
        text instead of an empty card.
        """
        out = dict(_EMPTY_INSIGHT)
        out["critique"] = {"strengths": [], "weaknesses": [], "assumptions": []}

        # Strip [chunk N] prefixes the merged_content adds for the LLM
        text = re.sub(r"\[chunk \d+\]\s*", "", section.merged_content)
        # Crude sentence split — good enough for English + Vietnamese papers
        sentences = [
            s.strip()
            for s in re.split(r"(?<=[\.\?!])\s+(?=[A-ZĐĂÂÊÔƠƯ])", text)
            if len(s.strip()) >= 30
        ]
        if not sentences:
            return out

        out["summary"] = " ".join(sentences[:3])[:600]
        if len(sentences) > 3:
            out["key_points"] = [
                s[:240] for s in sentences[3:8] if s
            ]
        return out
