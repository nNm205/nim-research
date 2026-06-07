from __future__ import annotations
import re
from typing import Any
from app.agents.tools.analysis.json_utils import parse_llm_json
from app.prompts.qa import GRAMMAR_SYSTEM_PROMPT, GRAMMAR_USER_PROMPT
from app.utils.logger import logger

_MAX_BODY_CHARS = 12_000
_MAX_BODY_CHARS_RETRY = 6_000  
_MAX_ISSUES = 25
_ISSUE_LIST_KEYS = ("issues", "errors", "results", "findings", "items")

class GrammarCheckerTool:
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
            return await self._minimal_retry(body, report_title, llm)

        return self._build_result(raw_issues)

    def _extract_issue_list(
        self, response: str | None, *, log_label: str
    ) -> list | None:
        parsed = parse_llm_json(response)

        if isinstance(parsed, list):
            return parsed

        if isinstance(parsed, dict):
            for key in _ISSUE_LIST_KEYS:
                value = parsed.get(key)
                if isinstance(value, list):
                    return value
            
            list_values = [v for v in parsed.values() if isinstance(v, list)]
            if len(list_values) == 1:
                return list_values[0]
            
            if not parsed:
                return []
            
            preview = (response or "")[:300].replace("\n", " ")
            logger.warning(
                f"GrammarChecker[{log_label}]: dict missing issues array. "
                f"keys={list(parsed.keys())[:6]} preview={preview!r}"
            )
            return None

        preview = (response or "")[:300].replace("\n", " ")
        logger.warning(
            f"GrammarChecker[{log_label}]: non-JSON response. "
            f"preview={preview!r}"
        )
        return None

    async def _minimal_retry(
        self, body: str, report_title: str, llm: Any
    ) -> dict[str, Any]:
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

        weights = {"low": 4, "medium": 8, "high": 14}
        score = 100
        for it in issues:
            score -= weights.get(it["severity"], 4)
        score = max(0, min(100, score))

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

def _strip_noise(markdown: str) -> str:
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
