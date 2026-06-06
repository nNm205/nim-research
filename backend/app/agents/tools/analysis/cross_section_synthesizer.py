"""CrossSectionSynthesizerTool — synthesize a narrative across section insights.

Single LLM call that consumes a compact JSON digest of every section's
insight (summary, purpose, top claims, top critique points, top quotes) and
returns:

  - the cross-section synthesis (narrative, main_thesis, argument_flow,
    overall_strengths/weaknesses, internal_conflicts, knowledge_gaps,
    confidence)
  - the executive summary that gets written into ``document_analyses.summary``

Producing both in one shot saves one LLM round-trip per analysis. The
``final_summary()`` helper is kept for callers that still expect a separate
method, but it now returns the cached value from ``synthesize()`` instead
of triggering a second call.
"""

from __future__ import annotations

from typing import Any

from app.agents.tools.analysis.json_utils import parse_llm_json
from app.prompts.analysis import (
    CROSS_SYNTHESIS_SYSTEM_PROMPT,
    CROSS_SYNTHESIS_USER_PROMPT,
)
from app.utils.logger import logger


# How much of each section we keep in the synthesis digest
_DIGEST_KEY_POINTS = 4
_DIGEST_CLAIMS = 3
_DIGEST_QUOTES = 2
_DIGEST_CRITIQUE_ITEMS = 3
# Hard char cap on the full digest blob
_MAX_DIGEST_CHARS = 14_000


class CrossSectionSynthesizerTool:
    """Produce narrative_synthesis (JSON) + executive summary in ONE LLM call."""

    async def synthesize(
        self,
        document_title: str,
        document_type: str,
        main_topics: list[str],
        section_insights: list[dict],
        llm: Any,
    ) -> dict:
        """Returns a dict with all narrative_synthesis fields PLUS an
        ``executive_summary`` key. The caller writes ``executive_summary``
        into the analysis row's ``summary`` field.
        """
        if not section_insights:
            return self._empty_synthesis()

        digest = self._build_digest(section_insights)

        try:
            response = await llm.generate(
                prompt=CROSS_SYNTHESIS_USER_PROMPT.format(
                    document_title=document_title or "Untitled",
                    document_type=document_type or "other",
                    main_topics=", ".join(main_topics) if main_topics else "(unknown)",
                    section_digests=digest,
                ),
                system_prompt=CROSS_SYNTHESIS_SYSTEM_PROMPT,
                temperature=0.3,
                # Bumped to fit narrative + executive_summary in one response.
                max_tokens=2000,
                response_format="json",
            )
        except Exception as e:
            logger.warning(f"CrossSectionSynthesizer LLM call failed: {e}")
            return self._fallback_synthesis(section_insights)

        parsed = parse_llm_json(response)
        if not isinstance(parsed, dict):
            preview = (response or "")[:400].replace("\n", " ")
            logger.warning(
                f"CrossSectionSynthesizer: LLM did not return JSON object. Preview: {preview!r}"
            )
            return self._fallback_synthesis(section_insights)

        return self._normalise(parsed, section_insights)

    async def final_summary(
        self,
        document_title: str,
        document_type: str,
        narrative_synthesis: dict,
        section_insights: list[dict],
        llm: Any,  # noqa: ARG002 — kept for API compatibility, no longer used
    ) -> str | None:
        """Return the executive summary baked into the synthesis result.

        Kept for backwards compatibility — does NOT make an extra LLM call.
        The agent should pull the summary from
        ``narrative_synthesis["executive_summary"]`` directly when possible.
        """
        if not isinstance(narrative_synthesis, dict):
            return None
        text = narrative_synthesis.get("executive_summary")
        if isinstance(text, str) and text.strip():
            return text.strip()

        # Heuristic fallback if the LLM didn't include the key (rare).
        narrative = (narrative_synthesis.get("narrative") or "").strip()
        if narrative:
            return narrative

        return self._heuristic_summary(section_insights)

    # ── Helpers ──────────────────────────────────────────────────────────────

    def _build_digest(self, section_insights: list[dict]) -> str:
        import json

        digests: list[dict] = []
        for s in section_insights:
            critique = s.get("critique") or {}
            digests.append(
                {
                    "index": s.get("section_index"),
                    "title": s.get("title"),
                    "type": s.get("section_type"),
                    "summary": s.get("summary"),
                    "purpose": s.get("purpose"),
                    "key_points": (s.get("key_points") or [])[:_DIGEST_KEY_POINTS],
                    "claims": [
                        {
                            "claim": c.get("claim"),
                            "evidence_type": c.get("evidence_type"),
                            "confidence": c.get("confidence"),
                        }
                        for c in (s.get("claims") or [])[:_DIGEST_CLAIMS]
                        if isinstance(c, dict)
                    ],
                    "strengths": (critique.get("strengths") or [])[:_DIGEST_CRITIQUE_ITEMS],
                    "weaknesses": (critique.get("weaknesses") or [])[:_DIGEST_CRITIQUE_ITEMS],
                    "open_questions": (s.get("open_questions") or [])[:_DIGEST_CRITIQUE_ITEMS],
                    "quotes": [
                        q.get("quote")
                        for q in (s.get("notable_quotes") or [])[:_DIGEST_QUOTES]
                        if isinstance(q, dict)
                    ],
                }
            )

        text = json.dumps(digests, ensure_ascii=False, indent=2)
        if len(text) > _MAX_DIGEST_CHARS:
            text = text[:_MAX_DIGEST_CHARS] + "\n... [digest truncated]"
        return text

    def _heuristic_summary(self, section_insights: list[dict]) -> str | None:
        """Concatenate the first 3 section summaries when the LLM gives us
        nothing usable. Always produces *some* readable text instead of None.
        """
        parts: list[str] = []
        for s in section_insights[:3]:
            summary = (s.get("summary") or "").strip()
            if summary:
                parts.append(summary)
        text = " ".join(parts).strip()
        return text or None

    def _normalise(
        self, parsed: dict, section_insights: list[dict]
    ) -> dict:
        def _str(key: str) -> str | None:
            v = parsed.get(key)
            return v.strip() if isinstance(v, str) and v.strip() else None

        def _list(key: str) -> list:
            v = parsed.get(key)
            return v if isinstance(v, list) else []

        confidence = parsed.get("confidence_in_conclusions")
        if confidence not in {"high", "medium", "low"}:
            confidence = None

        # Normalise internal_conflicts to consistent shape
        conflicts: list[dict] = []
        for c in _list("internal_conflicts"):
            if not isinstance(c, dict):
                continue
            between = c.get("between")
            description = c.get("description")
            if not isinstance(between, list):
                between = [str(between)] if between else []
            if isinstance(description, str) and description.strip():
                conflicts.append(
                    {
                        "between": [str(b) for b in between],
                        "description": description.strip(),
                    }
                )

        # If the LLM forgot the executive_summary, fall back to the narrative
        # field. If even that is missing, derive from section summaries so
        # downstream code never sees a fully empty summary.
        executive_summary = _str("executive_summary") or _str("narrative")
        if not executive_summary:
            executive_summary = self._heuristic_summary(section_insights)

        return {
            "executive_summary": executive_summary,
            "narrative": _str("narrative"),
            "main_thesis": _str("main_thesis"),
            "argument_flow": [s for s in _list("argument_flow") if isinstance(s, str)],
            "novelty_vs_prior_work": _str("novelty_vs_prior_work"),
            "internal_conflicts": conflicts,
            "knowledge_gaps": [s for s in _list("knowledge_gaps") if isinstance(s, str)],
            "overall_strengths": [s for s in _list("overall_strengths") if isinstance(s, str)],
            "overall_weaknesses": [s for s in _list("overall_weaknesses") if isinstance(s, str)],
            "confidence_in_conclusions": confidence,
            "confidence_justification": _str("confidence_justification"),
        }

    def _empty_synthesis(self) -> dict:
        return {
            "executive_summary": None,
            "narrative": None,
            "main_thesis": None,
            "argument_flow": [],
            "novelty_vs_prior_work": None,
            "internal_conflicts": [],
            "knowledge_gaps": [],
            "overall_strengths": [],
            "overall_weaknesses": [],
            "confidence_in_conclusions": None,
            "confidence_justification": None,
        }

    def _fallback_synthesis(self, section_insights: list[dict]) -> dict:
        out = self._empty_synthesis()
        out["executive_summary"] = self._heuristic_summary(section_insights)
        return out
