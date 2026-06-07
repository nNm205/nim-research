"""ExecutiveSummaryGeneratorTool — single LLM call for the cover summary."""

from __future__ import annotations

from typing import Any

from app.agents.tools.analysis.json_utils import parse_llm_json
from app.prompts.synthesis import (
    EXECUTIVE_SUMMARY_SYSTEM_PROMPT,
    EXECUTIVE_SUMMARY_USER_PROMPT,
)
from app.utils.logger import logger


_MAX_NARRATIVE_CHARS = 14_000


class ExecutiveSummaryGeneratorTool:
    """Produce a short executive summary + 4-6 bullet takeaways."""

    async def generate(
        self,
        report_title: str,
        thesis: str,
        narrative_text: str,
        llm: Any,
    ) -> dict:
        if not narrative_text.strip():
            return {"executive_summary": None, "key_takeaways": []}

        if len(narrative_text) > _MAX_NARRATIVE_CHARS:
            narrative_text = (
                narrative_text[:_MAX_NARRATIVE_CHARS]
                + "\n... [narrative truncated]"
            )

        prompt = EXECUTIVE_SUMMARY_USER_PROMPT.format(
            report_title=report_title or "Báo cáo",
            thesis=thesis or "(không xác định)",
            narrative_text=narrative_text,
        )

        try:
            response = await llm.generate(
                prompt=prompt,
                system_prompt=EXECUTIVE_SUMMARY_SYSTEM_PROMPT,
                temperature=0.3,
                max_tokens=900,
                response_format="json",
            )
        except Exception as e:
            logger.warning(f"ExecutiveSummary LLM call failed: {e}")
            return self._fallback(narrative_text)

        parsed = parse_llm_json(response)
        if not isinstance(parsed, dict):
            preview = (response or "")[:300].replace("\n", " ")
            logger.warning(
                f"ExecutiveSummary: non-JSON response. Preview: {preview!r}"
            )
            return self._fallback(narrative_text)

        return self._normalise(parsed, narrative_text)

    # ── Helpers ──────────────────────────────────────────────────────────

    def _normalise(self, parsed: dict, narrative_text: str) -> dict:
        summary = parsed.get("executive_summary")
        if not isinstance(summary, str) or not summary.strip():
            return self._fallback(narrative_text)
        takeaways_raw = parsed.get("key_takeaways") or []
        takeaways: list[str] = []
        if isinstance(takeaways_raw, list):
            for t in takeaways_raw:
                if isinstance(t, str) and t.strip():
                    takeaways.append(t.strip())
        return {
            "executive_summary": summary.strip(),
            "key_takeaways": takeaways[:8],
        }

    def _fallback(self, narrative_text: str) -> dict:
        # Crude fallback — first 3 sentences of the narrative.
        text = narrative_text.replace("\n", " ").strip()
        chunks = []
        for piece in text.split(". "):
            piece = piece.strip()
            if piece:
                chunks.append(piece)
            if len(chunks) >= 3:
                break
        if not chunks:
            return {"executive_summary": None, "key_takeaways": []}
        summary = ". ".join(chunks)
        if not summary.endswith("."):
            summary += "."
        return {"executive_summary": summary[:1200], "key_takeaways": []}
