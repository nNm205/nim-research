"""GrammarCheckerTool — single LLM call to surface grammar / clarity issues.

We send a line-numbered version of the report body so the LLM can return
``line_hint`` values the FE can scroll to. The body is trimmed to a hard
character cap to bound LLM cost.

Robustness contract: ``check()`` ALWAYS returns a usable result. If the
LLM doesn't follow the schema we (1) try to coerce a list payload, (2)
retry once with a minimal prompt, (3) fall back to a neutral score so
the QA verdict isn't dragged down by an upstream parser issue.
"""

from __future__ import annotations

import re
from typing import Any

from app.agents.tools.analysis.json_utils import parse_llm_json
from app.prompts.qa import GRAMMAR_SYSTEM_PROMPT, GRAMMAR_USER_PROMPT
from app.utils.logger import logger


# Hard caps. Reports can be tens of KB; sending the whole thing to a
# free-tier model risks OOM-ish behaviour and burns tokens.
_MAX_BODY_CHARS = 12_000
_MAX_BODY_CHARS_RETRY = 6_000  # tighter to free up output tokens
_MAX_ISSUES = 25

# Keys we accept when the LLM uses a synonym instead of "issues" — small
# models in particular tend to drift to "errors" / "results" / "items".
_ISSUE_LIST_KEYS = ("issues", "errors", "results", "findings", "items")


class GrammarCheckerTool:
    """Detect grammar / spelling / clarity issues."""

    async def check(
        self,
        markdown: str,
        report_title: str,
        llm: Any,
    ) -> dict[str, Any]:
        body = _strip_noise(markdown)
        if not body.strip():
            return self._neutral("báo cáo rỗng", score=100)

        if len(body) > _MAX_BODY_CHARS:
            body = body[:_MAX_BODY_CHARS] + "\n... [body truncated]"

        body_numbered = _line_number(body)

        # ── Main call ───────────────────────────────────────────────
        try:
            response = await llm.generate(
                prompt=GRAMMAR_USER_PROMPT.format(
                    report_title=report_title or "Báo cáo",
                    body_numbered=body_numbered,
                ),
                system_prompt=GRAMMAR_SYSTEM_PROMPT,
                temperature=0.1,
                max_tokens=2000,
                response_format="json",
            )
        except Exception as e:
            logger.warning(f"GrammarChecker LLM call failed: {e}")
            return await self._minimal_retry(body, report_title, llm)

        raw_issues = self._extract_issue_list(response, log_label="main")
        if raw_issues is None:
            # Parsable JSON shape but couldn't find an issue list. Try a
            # minimal-prompt retry; that one explicitly asks for an array.
            return await self._minimal_retry(body, report_title, llm)

        return self._build_result(raw_issues)

    # ── Coercion ────────────────────────────────────────────────────────

    def _extract_issue_list(
        self, response: str | None, *, log_label: str
    ) -> list | None:
        """Pull the issues array out of an LLM response.

        Accepts the documented shape (``{"issues": [...]}``) plus a few
        common drift cases:
          - JSON array at the top level: ``[{...}, {...}]``
          - dict with a synonym key: ``{"errors": [...]}``
          - dict with a single value that's a list

        Returns ``None`` only when nothing useful could be extracted.
        Empty list is a valid "no issues" answer and returns ``[]``.
        """
        parsed = parse_llm_json(response)

        if isinstance(parsed, list):
            # LLM returned the array directly — most common drift on
            # smaller / free-tier models.
            return parsed

        if isinstance(parsed, dict):
            for key in _ISSUE_LIST_KEYS:
                value = parsed.get(key)
                if isinstance(value, list):
                    return value
            # Sometimes the LLM wraps the array under a custom key but
            # there's only one value in the dict. Fall back to that.
            list_values = [v for v in parsed.values() if isinstance(v, list)]
            if len(list_values) == 1:
                return list_values[0]
            # An empty object is a perfectly valid "nothing to flag" answer.
            if not parsed:
                return []
            # A dict shape we don't understand — log a preview and bail.
            preview = (response or "")[:300].replace("\n", " ")
            logger.warning(
                f"GrammarChecker[{log_label}]: dict missing issues array. "
                f"keys={list(parsed.keys())[:6]} preview={preview!r}"
            )
            return None

        # Not parsable as JSON at all.
        preview = (response or "")[:300].replace("\n", " ")
        logger.warning(
            f"GrammarChecker[{log_label}]: non-JSON response. "
            f"preview={preview!r}"
        )
        return None

    async def _minimal_retry(
        self, body: str, report_title: str, llm: Any
    ) -> dict[str, Any]:
        """One last attempt with a stripped-down prompt that explicitly
        asks for a JSON array. Several free-tier models honour the
        simpler schema even when they drift on the documented one."""
        snippet = body[:_MAX_BODY_CHARS_RETRY]
        prompt = (
            "Đọc đoạn văn bản tiếng Việt/tiếng Anh dưới đây. Trả về JSON "
            "dạng MẢNG (array) chứa tối đa 15 vấn đề về ngữ pháp, chính "
            "tả, hoặc câu khó hiểu. Mỗi phần tử có cấu trúc:\n"
            '{ "snippet": "...", "type": "grammar|spelling|clarity|consistency", '
            '"severity": "low|medium|high", "suggestion": "..." }\n\n'
            "Nếu không có vấn đề nào, trả về [].\n\n"
            f"Tiêu đề: {report_title or 'Báo cáo'}\n\n"
            f"Văn bản:\n{snippet}\n\n"
            "JSON ARRAY only. No markdown, no preamble."
        )
        try:
            response = await llm.generate(
                prompt=prompt,
                system_prompt=(
                    "You are a bilingual editor. Return a strict JSON "
                    "array. No surrounding object, no commentary."
                ),
                temperature=0.1,
                max_tokens=1400,
                response_format="json",
            )
        except Exception as e:
            logger.warning(
                f"GrammarChecker minimal-retry LLM call failed: {e}"
            )
            return self._neutral("LLM lỗi", score=80)

        raw_issues = self._extract_issue_list(response, log_label="retry")
        if raw_issues is None:
            return self._neutral(
                "LLM không trả về JSON đúng schema sau khi thử lại",
                score=80,
            )
        return self._build_result(raw_issues)

    # ── Result building ─────────────────────────────────────────────────

    def _build_result(self, raw_issues: list) -> dict[str, Any]:
        issues: list[dict[str, Any]] = []
        for it in raw_issues:
            if not isinstance(it, dict):
                continue
            snippet = (it.get("snippet") or "").strip()
            suggestion = (it.get("suggestion") or "").strip()
            if not snippet:
                continue
            severity = it.get("severity")
            if severity not in {"low", "medium", "high"}:
                severity = "low"
            type_ = it.get("type")
            if type_ not in {"grammar", "spelling", "clarity", "consistency"}:
                type_ = "clarity"
            try:
                line_hint = int(it.get("line_hint") or 0)
            except (TypeError, ValueError):
                line_hint = 0
            issues.append({
                "type": type_,
                "severity": severity,
                "snippet": snippet[:200],
                "suggestion": suggestion[:300],
                "line_hint": max(0, line_hint),
            })

        issues = issues[:_MAX_ISSUES]

        # Score: 100 - (4 per low, 8 per medium, 14 per high)
        weights = {"low": 4, "medium": 8, "high": 14}
        score = 100
        for it in issues:
            score -= weights.get(it["severity"], 4)
        score = max(0, min(100, score))

        # Roll up a single aggregate issue for the QA panel summary.
        agg_issues: list[dict[str, Any]] = []
        if issues:
            high = sum(1 for i in issues if i["severity"] == "high")
            med = sum(1 for i in issues if i["severity"] == "medium")
            low = len(issues) - high - med
            sev = "high" if high else ("medium" if med >= 3 else "low")
            agg_issues.append({
                "type": "grammar_issues",
                "severity": sev,
                "message": (
                    f"Phát hiện {len(issues)} vấn đề "
                    f"(high={high}, medium={med}, low={low})"
                ),
            })

        return {
            "score": score,
            "issues": agg_issues,
            "details": issues,
            "stats": {"issues_count": len(issues)},
        }

    def _neutral(self, message: str, *, score: int) -> dict[str, Any]:
        """Score-only result with no detail rows.

        Used when we genuinely couldn't run the check (LLM failure,
        empty body, unparseable response after retry). The aggregate
        issue acts as a soft warning so the QA modal renders something
        meaningful instead of an empty card.
        """
        return {
            "score": score,
            "issues": [{
                "type": "grammar_skipped",
                "severity": "low",
                "message": message,
            }] if score < 100 else [],
            "details": [],
            "stats": {"issues_count": 0},
        }


# ── Static helpers ──────────────────────────────────────────────────────


def _strip_noise(markdown: str) -> str:
    """Drop code fences and trailing reference list — they aren't useful
    for grammar checking and they confuse line numbering."""
    text = re.sub(r"```.*?```", "", markdown, flags=re.DOTALL)
    text = re.split(
        r"\n##\s+(?:Tài liệu tham khảo|References|BibTeX)\s*\n",
        text,
        maxsplit=1,
    )[0]
    return text.strip()


def _line_number(text: str) -> str:
    lines = text.split("\n")
    return "\n".join(f"{i + 1:4d}: {line}" for i, line in enumerate(lines))
