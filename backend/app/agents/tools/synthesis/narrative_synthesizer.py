from __future__ import annotations
import json
import re
from typing import Any
from app.agents.tools.analysis.json_utils import parse_llm_json
from app.agents.tools.synthesis.context_loader import SynthesisContext
from app.prompts.synthesis import (
    NARRATIVE_SYSTEM_PROMPT,
    NARRATIVE_USER_PROMPT,
)
from app.utils.logger import logger

_MAX_DIGEST_CHARS = 18_000
_CITATION_RE = re.compile(r"\[(\d+(?:\s*,\s*\d+)*)\]")

class NarrativeSynthesizerTool:
    async def synthesize(
        self,
        context: SynthesisContext,
        outline: dict,
        llm: Any,
    ) -> dict:
        if not outline or not outline.get("sections"):
            return {"sections": {}}

        digest = context.documents_digest_json
        if len(digest) > _MAX_DIGEST_CHARS:
            digest = digest[:_MAX_DIGEST_CHARS] + "\n... [digest truncated]"

        outline_payload = {
            "title": outline.get("title"),
            "thesis": outline.get("thesis"),
            "audience": outline.get("audience"),
            "sections": [
                {
                    "key": s["key"],
                    "title": s["title"],
                    "purpose": s.get("purpose"),
                    "key_questions": s.get("key_questions") or [],
                    "documents_to_use": s.get("documents_to_use") or [],
                    "expected_length": s.get("expected_length") or "medium",
                }
                for s in outline["sections"]
            ],
        }

        prompt = NARRATIVE_USER_PROMPT.format(
            outline_json=json.dumps(
                outline_payload, ensure_ascii=False, indent=2
            ),
            documents_digest=digest,
        )

        try:
            response = await llm.generate(
                prompt=prompt,
                system_prompt=NARRATIVE_SYSTEM_PROMPT,
                temperature=0.4,
                max_tokens=3500,
                response_format="json",
            )
        except Exception as e:
            logger.warning(f"NarrativeSynthesizer LLM call failed: {e}")
            return self._fallback(context, outline)

        parsed = parse_llm_json(response)
        if not isinstance(parsed, dict):
            preview = (response or "")[:300].replace("\n", " ")
            logger.warning(
                f"NarrativeSynthesizer: non-JSON response. Preview: {preview!r}"
            )
            return self._fallback(context, outline)

        return self._normalise(parsed, context, outline)

    def _normalise(
        self, parsed: dict, context: SynthesisContext, outline: dict
    ) -> dict:
        sections_raw = parsed.get("sections") or {}
        if not isinstance(sections_raw, dict):
            return self._fallback(context, outline)

        valid_indices = {d.index for d in context.documents}
        out_sections: dict[str, dict] = {}

        for s in outline["sections"]:
            key = s["key"]
            entry = sections_raw.get(key)
            if not isinstance(entry, dict):
                out_sections[key] = self._fallback_section(s, context)
                continue

            body = entry.get("body")
            if not isinstance(body, str) or not body.strip():
                out_sections[key] = self._fallback_section(s, context)
                continue

            body = body.strip()
            cited = _extract_cited_indices(body, valid_indices)

            out_sections[key] = {
                "body": body,
                "documents_cited": cited,
            }

        return {"sections": out_sections}

    def _fallback(
        self, context: SynthesisContext, outline: dict
    ) -> dict:
        return {
            "sections": {
                s["key"]: self._fallback_section(s, context)
                for s in outline.get("sections", [])
            }
        }

    def _fallback_section(
        self, section: dict, context: SynthesisContext
    ) -> dict:
        doc_indices = section.get("documents_to_use") or [
            d.index for d in context.documents_with_analysis
        ]
        doc_indices = doc_indices[:5]
        if not doc_indices:
            return {
                "body": (
                    "Phần này hiện chưa có dữ liệu từ tài liệu nào trong dự án. "
                    "Hãy thêm tài liệu hoặc chạy phân tích để bổ sung nội dung."
                ),
                "documents_cited": [],
            }
        doc_map = {d.index: d for d in context.documents}
        sentences: list[str] = []
        for n in doc_indices:
            d = doc_map.get(n)
            if not d or not d.summary:
                continue
            text = d.summary.strip()
            if len(text) > 240:
                text = text[:240].rsplit(".", 1)[0] + "."
            sentences.append(f"{text} [{n}]")
        body = " ".join(sentences) if sentences else (
            "Tổng hợp tài liệu được trích dẫn dưới đây."
        )
        return {"body": body, "documents_cited": doc_indices}


def _extract_cited_indices(body: str, valid: set[int]) -> list[int]:
    seen: set[int] = set()
    out: list[int] = []
    for m in _CITATION_RE.finditer(body):
        for raw in m.group(1).split(","):
            try:
                n = int(raw.strip())
            except ValueError:
                continue
            if n in valid and n not in seen:
                seen.add(n)
                out.append(n)
    return out
