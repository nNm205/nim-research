"""OutlineBuilderTool — design a cross-document outline (1 LLM call)."""

from __future__ import annotations

from typing import Any

from app.agents.tools.analysis.json_utils import parse_llm_json
from app.agents.tools.synthesis.context_loader import SynthesisContext
from app.prompts.synthesis import OUTLINE_SYSTEM_PROMPT, OUTLINE_USER_PROMPT
from app.utils.logger import logger


_DEFAULT_SECTIONS = [
    {
        "key": "overview",
        "title": "Tổng quan",
        "purpose": "Giới thiệu chủ đề và phạm vi báo cáo",
        "key_questions": [],
        "documents_to_use": [],
        "expected_length": "short",
    },
    {
        "key": "findings",
        "title": "Phát hiện chính",
        "purpose": "Tổng hợp các phát hiện quan trọng nhất",
        "key_questions": [],
        "documents_to_use": [],
        "expected_length": "long",
    },
    {
        "key": "limitations",
        "title": "Giới hạn và hướng tiếp theo",
        "purpose": "Khoảng trống còn tồn tại và đề xuất nghiên cứu tiếp",
        "key_questions": [],
        "documents_to_use": [],
        "expected_length": "medium",
    },
]


class OutlineBuilderTool:
    """Produce a cross-document outline structure."""

    async def build(
        self,
        context: SynthesisContext,
        llm: Any,
    ) -> dict:
        # Edge case: no analyzed docs → fall back to a stub deterministic
        # outline so the rest of the pipeline still produces something
        # useful (it'll mostly degrade to the existing template).
        if not context.documents_with_analysis:
            logger.info(
                "OutlineBuilder: no analyzed documents — using default outline"
            )
            return self._fallback_outline(context)

        prompt = OUTLINE_USER_PROMPT.format(
            project_topic=context.project_topic or "(không xác định)",
            project_description=context.project_description or "(trống)",
            project_scope=context.project_research_scope or "(trống)",
            report_type=context.report_type,
            report_title=context.report_title,
            documents_digest=context.documents_digest_json,
        )

        try:
            response = await llm.generate(
                prompt=prompt,
                system_prompt=OUTLINE_SYSTEM_PROMPT,
                temperature=0.3,
                max_tokens=1200,
                response_format="json",
            )
        except Exception as e:
            logger.warning(f"OutlineBuilder LLM call failed: {e}")
            return self._fallback_outline(context)

        parsed = parse_llm_json(response)
        if not isinstance(parsed, dict):
            preview = (response or "")[:300].replace("\n", " ")
            logger.warning(f"OutlineBuilder: non-JSON response. Preview: {preview!r}")
            return self._fallback_outline(context)

        return self._normalise(parsed, context)

    # ── Helpers ──────────────────────────────────────────────────────────

    def _normalise(
        self, parsed: dict, context: SynthesisContext
    ) -> dict:
        sections_raw = parsed.get("sections")
        if not isinstance(sections_raw, list) or not sections_raw:
            return self._fallback_outline(context)

        valid_indices = {d.index for d in context.documents}
        sections: list[dict] = []
        seen_keys: set[str] = set()

        for s in sections_raw:
            if not isinstance(s, dict):
                continue
            title = (s.get("title") or "").strip()
            if not title:
                continue
            key = (s.get("key") or "").strip().lower() or _slug(title)
            # Make keys unique
            base_key = key
            i = 2
            while key in seen_keys:
                key = f"{base_key}_{i}"
                i += 1
            seen_keys.add(key)

            docs_to_use = s.get("documents_to_use") or []
            if not isinstance(docs_to_use, list):
                docs_to_use = []
            cleaned_docs: list[int] = []
            for n in docs_to_use:
                try:
                    n_int = int(n)
                except (TypeError, ValueError):
                    continue
                if n_int in valid_indices:
                    cleaned_docs.append(n_int)

            key_questions = [
                q.strip()
                for q in (s.get("key_questions") or [])
                if isinstance(q, str) and q.strip()
            ][:5]

            length = s.get("expected_length")
            if length not in {"short", "medium", "long"}:
                length = "medium"

            sections.append(
                {
                    "key": key,
                    "title": title,
                    "purpose": (s.get("purpose") or "").strip(),
                    "key_questions": key_questions,
                    "documents_to_use": cleaned_docs,
                    "expected_length": length,
                }
            )

        if not sections:
            return self._fallback_outline(context)

        return {
            "title": (parsed.get("title") or context.report_title or "").strip()
                     or context.report_title,
            "thesis": (parsed.get("thesis") or "").strip(),
            "audience": (parsed.get("audience") or "").strip(),
            "sections": sections[:10],  # hard cap
        }

    def _fallback_outline(self, context: SynthesisContext) -> dict:
        # Pre-fill documents_to_use across the default findings section so
        # the narrative call still has something to write about.
        sections = [dict(s) for s in _DEFAULT_SECTIONS]
        if context.documents_with_analysis:
            sections[1]["documents_to_use"] = [
                d.index for d in context.documents_with_analysis
            ]
        return {
            "title": context.report_title,
            "thesis": "",
            "audience": "",
            "sections": sections,
        }


def _slug(text: str) -> str:
    """Cheap slug — keep alnum + underscore, lowercase."""
    out: list[str] = []
    for ch in text.lower():
        if ch.isalnum():
            out.append(ch)
        elif ch in " -_":
            out.append("_")
    s = "".join(out).strip("_")
    return s[:32] or "section"
