from __future__ import annotations
import re
from typing import Any
from urllib.parse import urlparse

_INLINE_CITATION_RE = re.compile(r"\[(\d+(?:\s*,\s*\d+)*)\]")

class CitationVerifierTool:
    def verify(
        self,
        markdown: str,
        citation_entries: list[dict] | None,
        *,
        expects_inline_citations: bool = False,
    ) -> dict[str, Any]:
        issues: list[dict[str, Any]] = []
        entries = citation_entries or []
        entry_indices = {
            int(e.get("index"))
            for e in entries
            if isinstance(e.get("index"), int)
        }

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
            issues.append({
                "type": "unreferenced_entries",
                "severity": "low",
                "message": (
                    f"{len(unreferenced)} reference không được trích dẫn inline: "
                    f"{', '.join(f'[{i}]' for i in unreferenced[:8])}"
                    + ("..." if len(unreferenced) > 8 else "")
                ),
            })

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

        if expects_inline_citations and entries and not cited_indices:
            score -= 20

        return max(0, min(100, score))

def _is_valid_url(url: Any) -> bool:
    if not isinstance(url, str) or not url.strip():
        return False
    try:
        parsed = urlparse(url.strip())
    except Exception:
        return False
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)
