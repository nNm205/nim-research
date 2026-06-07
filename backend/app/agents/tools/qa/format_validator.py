from __future__ import annotations
import re
from typing import Any

_HEADING_RE = re.compile(r"^(#{1,6})\s+(.*?)\s*$", re.MULTILINE)
_TABLE_ROW_RE = re.compile(r"^\|.*\|\s*$", re.MULTILINE)
_TABLE_SEPARATOR_RE = re.compile(r"^\|[\s:\-|]+\|\s*$")


class FormatValidatorTool:
    def validate(self, markdown: str) -> dict[str, Any]:
        if not markdown or not markdown.strip():
            return {
                "score": 0,
                "issues": [
                    {
                        "type": "empty_report",
                        "severity": "high",
                        "message": "Báo cáo không có nội dung",
                    }
                ],
                "stats": {},
            }

        issues: list[dict[str, Any]] = []
        stats: dict[str, Any] = {}

        headings = list(_HEADING_RE.finditer(markdown))
        stats["heading_count"] = len(headings)

        if not any(m.group(1) == "#" for m in headings):
            issues.append({
                "type": "missing_title",
                "severity": "medium",
                "message": "Báo cáo không có tiêu đề (H1)",
            })

        prev_level = 0
        h2_titles: list[str] = []
        for m in headings:
            level = len(m.group(1))
            title = (m.group(2) or "").strip()
            if level == 2:
                h2_titles.append(title)
            if prev_level and level - prev_level > 1:
                issues.append({
                    "type": "heading_gap",
                    "severity": "low",
                    "message": (
                        f"Heading '{title[:60]}' nhảy từ H{prev_level} "
                        f"sang H{level} mà không có cấp trung gian"
                    ),
                })
            prev_level = level

        seen_h2: set[str] = set()
        for t in h2_titles:
            tl = t.lower().strip()
            if tl in seen_h2:
                issues.append({
                    "type": "duplicate_heading",
                    "severity": "low",
                    "message": f"Phần '{t}' bị lặp lại",
                })
            seen_h2.add(tl)

        sections = _split_sections(markdown, headings)
        stats["section_count"] = len(sections)
        for title, body, level in sections:
            text = _measure_prose(body)
            if not text:
                if level == 2:
                    issues.append({
                        "type": "empty_section",
                        "severity": "high",
                        "message": f"Phần '{title}' không có nội dung",
                    })
            elif level == 2 and len(text) < 80:
                issues.append({
                    "type": "tiny_section",
                    "severity": "low",
                    "message": (
                        f"Phần '{title}' rất ngắn ({len(text)} ký tự)"
                    ),
                })

        paragraphs = re.split(r"\n\s*\n", markdown)
        long_para_count = 0
        for p in paragraphs:
            p_text = p.strip()
            if p_text.startswith(("```", "|", "#")):
                continue
            if len(p_text) > 2000:
                long_para_count += 1
        if long_para_count > 0:
            issues.append({
                "type": "long_paragraph",
                "severity": "low",
                "message": (
                    f"{long_para_count} đoạn văn dài hơn 2000 ký tự — "
                    f"khó đọc, cân nhắc tách nhỏ"
                ),
            })

        table_rows = _TABLE_ROW_RE.findall(markdown)
        if table_rows:
            uneven = _check_uneven_tables(table_rows)
            if uneven:
                issues.append({
                    "type": "malformed_table",
                    "severity": "medium",
                    "message": (
                        f"Phát hiện {uneven} hàng bảng có số cột không khớp"
                    ),
                })

        words = re.findall(r"\b\w+\b", markdown)
        stats["word_count"] = len(words)
        stats["char_count"] = len(markdown)
        stats["paragraph_count"] = sum(
            1
            for p in paragraphs
            if p.strip() and not p.strip().startswith(("```", "|"))
        )

        score = self._score(issues, stats)

        return {"score": score, "issues": issues, "stats": stats}

    def _score(
        self, issues: list[dict[str, Any]], stats: dict[str, Any]
    ) -> int:
        score = 100
        weights = {"high": 20, "medium": 8, "low": 2}
        for it in issues:
            score -= weights.get(it.get("severity", "low"), 2)

        wc = stats.get("word_count", 0)
        if wc < 100:
            score -= 15
        elif wc < 250:
            score -= 5

        return max(0, min(100, score))

def _split_sections(
    markdown: str, headings: list[re.Match]
) -> list[tuple[str, str, int]]:
    if not headings:
        return []
    relevant = [m for m in headings if len(m.group(1)) in (2, 3)]
    if not relevant:
        return []

    out: list[tuple[str, str, int]] = []
    for i, m in enumerate(relevant):
        title = (m.group(2) or "").strip() or "(không tiêu đề)"
        level = len(m.group(1))
        start = m.end()
        end = len(markdown)
        for next_m in relevant[i + 1 :]:
            next_level = len(next_m.group(1))
            if next_level <= level:
                end = next_m.start()
                break
        body = markdown[start:end]
        out.append((title, body, level))
    return out


def _measure_prose(body: str) -> str:
    lines: list[str] = []
    for raw in body.splitlines():
        stripped = raw.strip()
        if not stripped:
            continue
        if stripped.startswith("#"):
            continue
        if _TABLE_SEPARATOR_RE.match(stripped):
            continue
        lines.append(stripped)
    return "\n".join(lines)


def _check_uneven_tables(rows: list[str]) -> int:
    uneven = 0
    current_cols: int | None = None
    in_table = False
    prev = ""
    for raw in rows:
        cols = raw.count("|") - 1
        if cols < 1:
            continue
        
        if _TABLE_SEPARATOR_RE.match(raw):
            continue
        if not in_table or _TABLE_SEPARATOR_RE.match(prev):
            current_cols = cols
            in_table = True
        elif current_cols is not None and cols != current_cols:
            uneven += 1
        prev = raw
    return uneven
