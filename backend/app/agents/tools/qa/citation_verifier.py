"""CitationVerifierTool — deterministic citation cross-checks.

For a given report we check:
  - Every `[n]` in the body resolves to a known reference entry.
  - Every reference entry has a usable URL (well-formed http(s)) or DOI.
  - No reference entry is unreferenced (cited zero times in the body).
  - No duplicate entries (same DOI / title).

Citations come from ``Report.synthesis_metadata.citation_entries`` when the
report was synthesised. For deterministic-template reports we fall back to
the project documents (still useful — confirms each linked source has a URL).
"""

from __future__ import annotations

import re
from typing import Any
from urllib.parse import urlparse


_INLINE_CITATION_RE = re.compile(r"\[(\d+(?:\s*,\s*\d+)*)\]")


class CitationVerifierTool:
    """Validate citations against the report's reference list."""

    def verify(
        self,
        markdown: str,
        citation_entries: list[dict] | None,
        *,
        expects_inline_citations: bool = False,
    ) -> dict[str, Any]:
        """Validate citations.

        Args:
            markdown: report body text.
            citation_entries: reference list (each must have at least
                ``index``, plus ``url`` / ``doi`` / ``title``).
            expects_inline_citations: when ``True`` (synthesised report),
                the verifier flags references that aren't cited inline.
                When ``False`` (template-rendered report from the
                deterministic generator, which doesn't emit ``[n]``
                markers), unreferenced entries are accepted silently —
                the reference list still serves as a "see also" surface.
        """
        issues: list[dict[str, Any]] = []
        entries = citation_entries or []
        entry_indices = {
            int(e.get("index"))
            for e in entries
            if isinstance(e.get("index"), int)
        }

        # ── Inline citations ────────────────────────────────────────────
        cited_indices: set[int] = set()
        unknown_refs: set[int] = set()
        for m in _INLINE_CITATION_RE.finditer(markdown or ""):
            for raw in m.group(1).split(","):
                try:
                    n = int(raw.strip())
                except ValueError:
                    continue
                cited_indices.add(n)
                if entry_indices and n not in entry_indices:
                    unknown_refs.add(n)

        for n in sorted(unknown_refs):
            issues.append({
                "type": "missing_reference",
                "severity": "high",
                "message": f"Trích dẫn [{n}] xuất hiện trong báo cáo nhưng không có entry tương ứng",
            })

        # ── Reference list checks ───────────────────────────────────────
        seen_dois: dict[str, int] = {}
        seen_titles: dict[str, int] = {}
        broken_urls: list[int] = []
        missing_url: list[int] = []
        unreferenced: list[int] = []

        for e in entries:
            try:
                idx = int(e.get("index"))
            except (TypeError, ValueError):
                continue

            url = e.get("url")
            doi = e.get("doi")
            title = (e.get("title") or "").strip().lower()

            if not _is_valid_url(url) and not doi:
                missing_url.append(idx)
            if url and not _is_valid_url(url):
                broken_urls.append(idx)

            if doi:
                doi_key = doi.lower().strip()
                if doi_key in seen_dois:
                    issues.append({
                        "type": "duplicate_reference",
                        "severity": "medium",
                        "message": (
                            f"Reference [{idx}] và [{seen_dois[doi_key]}] có cùng DOI ({doi})"
                        ),
                    })
                else:
                    seen_dois[doi_key] = idx

            if title:
                if title in seen_titles:
                    issues.append({
                        "type": "duplicate_reference",
                        "severity": "low",
                        "message": (
                            f"Reference [{idx}] và [{seen_titles[title]}] có cùng tiêu đề"
                        ),
                    })
                else:
                    seen_titles[title] = idx

            if entry_indices and idx not in cited_indices:
                unreferenced.append(idx)

        for idx in missing_url:
            issues.append({
                "type": "missing_url",
                "severity": "medium",
                "message": f"Reference [{idx}] không có URL hoặc DOI",
            })
        for idx in broken_urls:
            issues.append({
                "type": "broken_url",
                "severity": "medium",
                "message": f"Reference [{idx}] có URL không hợp lệ",
            })
        if unreferenced and entries and expects_inline_citations:
            # Only warn at low severity — sometimes the user explicitly
            # wants to include a reference list of related work that
            # isn't directly cited inline. Skip entirely for template
            # reports which have no inline `[n]` markers by design.
            issues.append({
                "type": "unreferenced_entries",
                "severity": "low",
                "message": (
                    f"{len(unreferenced)} reference không được trích dẫn inline: "
                    f"{', '.join(f'[{i}]' for i in unreferenced[:8])}"
                    + ("..." if len(unreferenced) > 8 else "")
                ),
            })

        # ── Stats / score ───────────────────────────────────────────────
        stats = {
            "inline_citations": len(cited_indices),
            "reference_count": len(entries),
            "unknown_references": len(unknown_refs),
            "unreferenced_entries": len(unreferenced),
            "broken_urls": len(broken_urls),
            "missing_url": len(missing_url),
        }

        score = self._score(
            issues, entries, cited_indices, expects_inline_citations
        )

        return {
            "score": score,
            "issues": issues,
            "stats": stats,
            "cited_indices": sorted(cited_indices),
        }

    # ── Scoring ─────────────────────────────────────────────────────────

    def _score(
        self,
        issues: list[dict[str, Any]],
        entries: list[dict],
        cited_indices: set[int],
        expects_inline_citations: bool = True,
    ) -> int:
        score = 100
        weights = {"high": 25, "medium": 10, "low": 3}
        for it in issues:
            score -= weights.get(it.get("severity", "low"), 3)

        # No citations at all in a SYNTHESISED report (which is supposed
        # to have inline [n] markers) is a red flag — drop another 20
        # points. Template reports never carry inline markers; don't
        # penalise them here.
        if expects_inline_citations and entries and not cited_indices:
            score -= 20

        return max(0, min(100, score))


# ── Helpers ─────────────────────────────────────────────────────────────


def _is_valid_url(url: Any) -> bool:
    if not isinstance(url, str) or not url.strip():
        return False
    try:
        parsed = urlparse(url.strip())
    except Exception:
        return False
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)
