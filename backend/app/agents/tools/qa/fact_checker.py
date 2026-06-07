from __future__ import annotations
import json
import re
from dataclasses import dataclass
from typing import Any
from app.agents.tools.analysis.json_utils import parse_llm_json
from app.agents.tools.synthesis.context_loader import SynthesisContext
from app.prompts.qa import FACT_CHECK_SYSTEM_PROMPT, FACT_CHECK_USER_PROMPT
from app.utils.logger import logger

_MAX_CLAIMS_TO_CHECK = 12
_MIN_CLAIM_CHARS = 30
_MAX_CLAIM_CHARS = 400
_MAX_EVIDENCE_CHARS_PER_DOC = 1500
_MAX_EVIDENCE_TOTAL_CHARS = 12_000


_INLINE_CITATION_RE = re.compile(r"\[(\d+(?:\s*,\s*\d+)*)\]")
_SENTENCE_SPLIT_RE = re.compile(
    r"(?<=[\.\?!])\s+(?=[A-ZĐĂÂÊÔƠƯ])"
    r"|\n[ \t]*\n+"
    r"|\n+(?=\s*(?:\d+[.)]\s+|[-*•]\s+|#{1,6}\s+))"
)


@dataclass
class _Candidate:
    index: int
    text: str
    cited_docs: list[int]


class FactCheckerTool:
    async def check(
        self,
        markdown: str,
        report_title: str,
        context: SynthesisContext | None,
        llm: Any,
    ) -> dict[str, Any]:
        candidates = _extract_claims(markdown)

        if not candidates:
            return {
                "score": 100,
                "issues": [],
                "stats": {
                    "claims_checked": 0,
                    "supported": 0,
                    "partial": 0,
                    "unsupported": 0,
                },
                "details": [],
                "note": "Không có claim đủ điều kiện để kiểm chứng",
            }

        evidence = self._build_evidence(candidates, context)
        if not evidence and not _any_cited(candidates):
            return {
                "score": 70,
                "issues": [{
                    "type": "no_evidence_available",
                    "severity": "medium",
                    "message": (
                        "Không tìm thấy nguồn dữ liệu để đối chiếu các claim "
                        "trong báo cáo (chưa có tài liệu nào đã phân tích)"
                    ),
                }],
                "stats": {
                    "claims_checked": 0,
                    "supported": 0,
                    "partial": 0,
                    "unsupported": 0,
                },
                "details": [],
            }

        prompt = FACT_CHECK_USER_PROMPT.format(
            report_title=report_title or "Báo cáo",
            claims_json=_format_claims_json(candidates),
            evidence_json=_format_evidence_json(evidence),
        )

        try:
            response = await llm.generate(
                prompt=prompt,
                system_prompt=FACT_CHECK_SYSTEM_PROMPT,
                temperature=0.1,
                max_tokens=2000,
                response_format="json",
            )
        except Exception as e:
            logger.warning(f"FactChecker LLM call failed: {e}")
            return self._fallback(candidates)

        parsed = parse_llm_json(response)
        if not isinstance(parsed, dict):
            preview = (response or "")[:300].replace("\n", " ")
            logger.warning(f"FactChecker: non-JSON response. Preview: {preview!r}")
            return self._fallback(candidates)

        return self._normalise(parsed, candidates)

    def _build_evidence(
        self,
        candidates: list[_Candidate],
        context: SynthesisContext | None,
    ) -> dict[int, dict]:
        if context is None:
            return {}
        cited_set: set[int] = set()
        for c in candidates:
            cited_set.update(c.cited_docs)
        if not cited_set:
            return {}

        docs_by_idx = {d.index: d for d in context.documents}
        evidence: dict[int, dict] = {}
        total_chars = 0
        for n in sorted(cited_set):
            d = docs_by_idx.get(n)
            if not d:
                continue
            digest = d.to_digest_dict()
            digest_str = json.dumps(digest, ensure_ascii=False)
            if len(digest_str) > _MAX_EVIDENCE_CHARS_PER_DOC:
                for k in ("topics", "quotes", "research_questions"):
                    digest.pop(k, None)
                digest_str = json.dumps(digest, ensure_ascii=False)
                if len(digest_str) > _MAX_EVIDENCE_CHARS_PER_DOC:
                    summary = digest.get("summary") or ""
                    digest["summary"] = summary[:600]
            total_chars += len(json.dumps(digest, ensure_ascii=False))
            evidence[n] = digest
            if total_chars > _MAX_EVIDENCE_TOTAL_CHARS:
                break
        return evidence

    def _normalise(
        self, parsed: dict, candidates: list[_Candidate]
    ) -> dict[str, Any]:
        verdicts_raw = parsed.get("verdicts") or []
        if not isinstance(verdicts_raw, list):
            return self._fallback(candidates)

        by_index = {c.index: c for c in candidates}
        details: list[dict] = []
        counts = {"supported": 0, "partial": 0, "unsupported": 0}

        for v in verdicts_raw:
            if not isinstance(v, dict):
                continue
            try:
                idx = int(v.get("index"))
            except (TypeError, ValueError):
                continue
            verdict = v.get("verdict")
            if verdict not in {"supported", "partial", "unsupported"}:
                continue
            cand = by_index.get(idx)
            if not cand:
                continue
            counts[verdict] += 1
            details.append({
                "index": idx,
                "claim": cand.text,
                "cited_docs": cand.cited_docs,
                "verdict": verdict,
                "explanation": (v.get("explanation") or "").strip()[:500],
                "evidence_excerpt": (v.get("evidence_excerpt") or "").strip()[:300],
            })

        verdicted = {d["index"] for d in details}
        for cand in candidates:
            if cand.index not in verdicted:
                counts["partial"] += 1
                details.append({
                    "index": cand.index,
                    "claim": cand.text,
                    "cited_docs": cand.cited_docs,
                    "verdict": "partial",
                    "explanation": "Không có verdict từ LLM",
                    "evidence_excerpt": "",
                })

        rebucketed_unsupported = 0
        for d in details:
            if d["verdict"] == "unsupported" and not d["cited_docs"]:
                d["verdict"] = "partial"
                d["explanation"] = (
                    (d.get("explanation") or "").rstrip(".")
                    + ". Không có nguồn được trích dẫn để xác minh."
                ).strip()
                rebucketed_unsupported += 1
        if rebucketed_unsupported:
            counts["unsupported"] -= rebucketed_unsupported
            counts["partial"] += rebucketed_unsupported

        total = sum(counts.values()) or 1
        ratio = (counts["supported"] + 0.5 * counts["partial"]) / total
        score = int(round(ratio * 100))

        if counts["supported"] == 0 and counts["unsupported"] == 0 and counts["partial"] > 0:
            score = max(score, 70)

        issues: list[dict] = []
        if counts["unsupported"] > 0:
            issues.append({
                "type": "unsupported_claims",
                "severity": "high",
                "message": (
                    f"{counts['unsupported']}/{total} claim không được dữ liệu "
                    f"phân tích hỗ trợ"
                ),
            })
        if counts["partial"] >= max(2, total // 3):
            issues.append({
                "type": "partial_claims",
                "severity": "medium",
                "message": (
                    f"{counts['partial']}/{total} claim chỉ được hỗ trợ một phần"
                ),
            })

        return {
            "score": score,
            "issues": issues,
            "stats": {
                "claims_checked": total,
                "supported": counts["supported"],
                "partial": counts["partial"],
                "unsupported": counts["unsupported"],
            },
            "details": details[:_MAX_CLAIMS_TO_CHECK],
        }

    def _fallback(self, candidates: list[_Candidate]) -> dict[str, Any]:
        return {
            "score": 70,
            "issues": [{
                "type": "fact_check_unavailable",
                "severity": "low",
                "message": "Không thể chạy fact-check (LLM lỗi)",
            }],
            "stats": {
                "claims_checked": 0,
                "supported": 0,
                "partial": 0,
                "unsupported": 0,
            },
            "details": [],
        }

def _extract_claims(markdown: str) -> list[_Candidate]:
    if not markdown:
        return []

    cleaned = _strip_noise(markdown)
    sentences = _SENTENCE_SPLIT_RE.split(cleaned)

    out: list[_Candidate] = []
    for raw in sentences:
        s = raw.strip()
        s = _LIST_PREFIX_RE.sub("", s).strip()
        s = _TRAILING_LIST_NUM_RE.sub("", s).strip()

        if len(s) < _MIN_CLAIM_CHARS or len(s) > _MAX_CLAIM_CHARS:
            continue
        if s.startswith(("|", "#", "-", "*", "_")):
            continue

        cited = _extract_cited(s)
        has_number = bool(_NUMERIC_HINT_RE.search(s))
        if not cited and not has_number:
            continue

        out.append(_Candidate(
            index=len(out) + 1,
            text=s,
            cited_docs=cited,
        ))
        if len(out) >= _MAX_CLAIMS_TO_CHECK:
            break
    return out

_LIST_PREFIX_RE = re.compile(r"^\s*(?:\d+[.)]\s+|[-*•]\s+)")
_TRAILING_LIST_NUM_RE = re.compile(r"\s+\d+\.\s*$")
_NUMERIC_HINT_RE = re.compile(
    r"\b\d{2,}(?:[.,]\d+)?\b"
    r"|\b\d+(?:[.,]\d+)?\s*%"
    r"|(?i:bleu|f1|accuracy|precision|recall|rouge|map|auc|"
    r"top-?\d|n=)\s*\d"
)

def _strip_noise(markdown: str) -> str:
    text = re.sub(r"```.*?```", "", markdown, flags=re.DOTALL)
    text = re.split(r"\n##\s+(?:Tài liệu tham khảo|References|BibTeX)\s*\n",
                    text, maxsplit=1)[0]
    return text


def _extract_cited(text: str) -> list[int]:
    out: list[int] = []
    seen: set[int] = set()
    for m in _INLINE_CITATION_RE.finditer(text):
        for raw in m.group(1).split(","):
            try:
                n = int(raw.strip())
            except ValueError:
                continue
            if n not in seen:
                seen.add(n)
                out.append(n)
    return out


def _any_cited(candidates: list[_Candidate]) -> bool:
    return any(c.cited_docs for c in candidates)


def _format_claims_json(candidates: list[_Candidate]) -> str:
    payload = [
        {"index": c.index, "claim": c.text, "cited_docs": c.cited_docs}
        for c in candidates
    ]
    return json.dumps(payload, ensure_ascii=False, indent=2)


def _format_evidence_json(evidence: dict[int, dict]) -> str:
    if not evidence:
        return "{}"
    return json.dumps(evidence, ensure_ascii=False, indent=2)
