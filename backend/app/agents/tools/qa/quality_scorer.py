"""QualityScorerTool — combine sub-scores into a single overall verdict.

Inputs are the per-check result dicts produced by the format / citation /
fact / grammar tools (each having ``score``, ``issues``, optionally
``stats`` and ``details``). Output:

  {
    "overall_score": int,
    "verdict": "excellent" | "good" | "needs_review" | "poor",
    "format": {...},
    "citations": {...},
    "facts": {...},
    "grammar": {...},
    "recommendations": [str, ...]
  }

Weights are biased toward facts + citations (a report's accuracy matters
more than its prose), then format, then grammar. Tweakable here in one
place.
"""

from __future__ import annotations

from typing import Any

from app.utils.constants import QAVerdict


# Weights must sum to 1.0
_WEIGHTS = {
    "format": 0.15,
    "citations": 0.30,
    "facts": 0.35,
    "grammar": 0.20,
}


class QualityScorerTool:
    """Compose a single QA verdict + recommendations from sub-checks."""

    def score(
        self,
        format_result: dict[str, Any],
        citations_result: dict[str, Any],
        facts_result: dict[str, Any],
        grammar_result: dict[str, Any],
    ) -> dict[str, Any]:
        format_score = _safe_score(format_result)
        citations_score = _safe_score(citations_result)
        facts_score = _safe_score(facts_result)
        grammar_score = _safe_score(grammar_result)

        overall = int(round(
            format_score * _WEIGHTS["format"]
            + citations_score * _WEIGHTS["citations"]
            + facts_score * _WEIGHTS["facts"]
            + grammar_score * _WEIGHTS["grammar"]
        ))
        overall = max(0, min(100, overall))

        verdict = _verdict_for(overall).value

        recommendations = _build_recommendations(
            format_result, citations_result, facts_result, grammar_result
        )

        return {
            "overall_score": overall,
            "verdict": verdict,
            "weights": dict(_WEIGHTS),
            "format": format_result,
            "citations": citations_result,
            "facts": facts_result,
            "grammar": grammar_result,
            "recommendations": recommendations,
        }


# ── Helpers ─────────────────────────────────────────────────────────────


def _safe_score(result: dict[str, Any] | None) -> int:
    if not isinstance(result, dict):
        return 70
    score = result.get("score")
    if not isinstance(score, (int, float)):
        return 70
    return max(0, min(100, int(score)))


def _verdict_for(score: int) -> QAVerdict:
    if score >= 90:
        return QAVerdict.EXCELLENT
    if score >= 75:
        return QAVerdict.GOOD
    if score >= 60:
        return QAVerdict.NEEDS_REVIEW
    return QAVerdict.POOR


def _build_recommendations(
    format_result: dict[str, Any],
    citations_result: dict[str, Any],
    facts_result: dict[str, Any],
    grammar_result: dict[str, Any],
) -> list[str]:
    recs: list[str] = []

    # Highest-priority recommendations come from "high" severity issues.
    for area_name, area in (
        ("Định dạng", format_result),
        ("Trích dẫn", citations_result),
        ("Độ chính xác", facts_result),
        ("Văn phong", grammar_result),
    ):
        issues = (area or {}).get("issues") or []
        for it in issues:
            if it.get("severity") == "high":
                msg = (it.get("message") or "").strip()
                if msg:
                    recs.append(f"[{area_name}] {msg}")

    # If nothing high-severity, still surface 1-2 medium issues so the user
    # has actionable feedback even on a "good" report.
    if len(recs) < 2:
        for area_name, area in (
            ("Trích dẫn", citations_result),
            ("Độ chính xác", facts_result),
            ("Định dạng", format_result),
            ("Văn phong", grammar_result),
        ):
            for it in (area or {}).get("issues") or []:
                if it.get("severity") == "medium":
                    msg = (it.get("message") or "").strip()
                    if msg and f"[{area_name}] {msg}" not in recs:
                        recs.append(f"[{area_name}] {msg}")
                        if len(recs) >= 4:
                            break
            if len(recs) >= 4:
                break

    # Heuristic suggestion when the fact-check produced nothing useful
    # (template report with no inline citations). Steer the user toward
    # running Synthesis so the next QA pass actually has something to
    # verify against.
    facts_stats = (facts_result or {}).get("stats") or {}
    checked = facts_stats.get("claims_checked", 0)
    supported = facts_stats.get("supported", 0)
    if checked > 0 and supported == 0:
        recs.append(
            "[Gợi ý] Chạy 'Tổng hợp bằng AI' để báo cáo có inline "
            "citations [n] — QA sẽ verify được claim chính xác hơn."
        )

    if not recs:
        recs.append("Báo cáo đạt chuẩn — không có khuyến nghị cải thiện cấp bách.")

    return recs[:8]
