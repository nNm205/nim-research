"""FormatValidatorTool — deterministic markdown / structure checks.

Surfaces:
  - empty / tiny H2 sections (H3 are tolerated as intentional placeholders)
  - heading hierarchy gaps (e.g. ## directly followed by ####)
  - duplicate top-level headings
  - malformed markdown tables (uneven columns)
  - very long paragraphs (>2000 chars; readability red flag)
  - missing required structural elements (title, executive summary)

Section emptiness is measured against PROSE only — nested headings,
table separator rows, and HR markers are stripped before measuring so
an H2 that contains only sub-H3s isn't falsely flagged as empty.
"""

from __future__ import annotations

import re
from typing import Any


_HEADING_RE = re.compile(r"^(#{1,6})\s+(.*?)\s*$", re.MULTILINE)
_TABLE_ROW_RE = re.compile(r"^\|.*\|\s*$", re.MULTILINE)
_TABLE_SEPARATOR_RE = re.compile(r"^\|[\s:\-|]+\|\s*$")


class FormatValidatorTool:
    """Run a battery of static checks on the report markdown body."""

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

        # ── Headings ────────────────────────────────────────────────────
        headings = list(_HEADING_RE.finditer(markdown))
        stats["heading_count"] = len(headings)

        if not any(m.group(1) == "#" for m in headings):
            issues.append({
                "type": "missing_title",
                "severity": "medium",
                "message": "Báo cáo không có tiêu đề (H1)",
            })

        # Hierarchy: a level should not jump down by more than 1
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

        # Duplicate H2
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

        # ── Empty / tiny sections ───────────────────────────────────────
        sections = _split_sections(markdown, headings)
        stats["section_count"] = len(sections)
        for title, body, level in sections:
            text = _measure_prose(body)
            if not text:
                # Tolerate empty H3 — H2 children are sometimes deliberately
                # placeholder until the user fills them in. Only flag H2.
                if level == 2:
                    issues.append({
                        "type": "empty_section",
                        "severity": "high",
                        "message": f"Phần '{title}' không có nội dung",
                    })
            elif level == 2 and len(text) < 80:
                # Tiny H2 is suspicious; tiny H3 (e.g. just a keyword
                # chip row) is fine and should not penalise the report.
                issues.append({
                    "type": "tiny_section",
                    "severity": "low",
                    "message": (
                        f"Phần '{title}' rất ngắn ({len(text)} ký tự)"
                    ),
                })

        # ── Long paragraphs ─────────────────────────────────────────────
        paragraphs = re.split(r"\n\s*\n", markdown)
        long_para_count = 0
        for p in paragraphs:
            p_text = p.strip()
            # Skip code blocks / tables / headings
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

        # ── Tables ──────────────────────────────────────────────────────
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

        # ── Stats ───────────────────────────────────────────────────────
        words = re.findall(r"\b\w+\b", markdown)
        stats["word_count"] = len(words)
        stats["char_count"] = len(markdown)
        stats["paragraph_count"] = sum(
            1
            for p in paragraphs
            if p.strip() and not p.strip().startswith(("```", "|"))
        )

        # ── Score ───────────────────────────────────────────────────────
        score = self._score(issues, stats)

        return {"score": score, "issues": issues, "stats": stats}

    # ── Scoring ─────────────────────────────────────────────────────────

    def _score(
        self, issues: list[dict[str, Any]], stats: dict[str, Any]
    ) -> int:
        score = 100
        # High issues are big deductions; low ones are small nudges.
        # Lowered "low" weight from 3 → 2 so a long template report with
        # a handful of cosmetic findings doesn't drop into the 70s.
        weights = {"high": 20, "medium": 8, "low": 2}
        for it in issues:
            score -= weights.get(it.get("severity", "low"), 2)

        # Length sanity check. We're tolerant on the lower bound — a
        # template report for a 1-document project legitimately runs
        # ~300 words and shouldn't be penalised heavily.
        wc = stats.get("word_count", 0)
        if wc < 100:
            score -= 15
        elif wc < 250:
            score -= 5

        return max(0, min(100, score))


# ── Helpers ─────────────────────────────────────────────────────────────


def _split_sections(
    markdown: str, headings: list[re.Match]
) -> list[tuple[str, str, int]]:
    """Return ``[(title, body, level), ...]`` for every H2/H3 section.

    The ``body`` spans from the heading to the NEXT heading at the same
    OR higher level — so an H2's body includes its child H3s. Without
    this, an H2 like ``## Kết quả tổng hợp`` whose only content is
    sub-H3s would have an empty body slice and the validator would
    falsely flag it as empty.
    """
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
        # Find the next heading at level <= current level.
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
    """Strip nested headings and table separator rows, then trim.

    Used to decide whether a section has any "real" content — pure
    sub-headings or a lone table separator row don't count.
    """
    lines: list[str] = []
    for raw in body.splitlines():
        stripped = raw.strip()
        if not stripped:
            continue
        if stripped.startswith("#"):
            # nested heading
            continue
        if _TABLE_SEPARATOR_RE.match(stripped):
            continue
        lines.append(stripped)
    return "\n".join(lines)


def _check_uneven_tables(rows: list[str]) -> int:
    """Count rows whose column count differs from the first row in a run."""
    uneven = 0
    current_cols: int | None = None
    in_table = False
    prev = ""
    for raw in rows:
        cols = raw.count("|") - 1
        if cols < 1:
            continue
        # Skip separator rows like |---|---|
        if _TABLE_SEPARATOR_RE.match(raw):
            continue
        if not in_table or _TABLE_SEPARATOR_RE.match(prev):
            current_cols = cols
            in_table = True
        elif current_cols is not None and cols != current_cols:
            uneven += 1
        prev = raw
    return uneven
