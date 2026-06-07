"""CitationManagerTool — deterministic BibTeX + APA citation builder.

Builds citation entries from the document metadata already loaded in the
SynthesisContext. No LLM. Two output formats:

  - APA       — used in the rendered references list
  - BibTeX    — exported as a separate ``.bib`` block alongside the report

Only documents that were actually cited in the narrative get an entry; the
``cited_indices`` parameter lets the agent pass in which documents the
narrative referenced. We dedupe on ``(authors, year, title)``.
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Iterable

from app.agents.tools.synthesis.context_loader import (
    DocumentItem,
    SynthesisContext,
)


# ── Public API ───────────────────────────────────────────────────────────


class CitationManagerTool:
    """Produce APA + BibTeX strings for the cited documents."""

    def build(
        self,
        context: SynthesisContext,
        cited_indices: Iterable[int],
    ) -> dict:
        """Return a dict with ``entries`` (per-doc) plus rendered strings.

        Shape:
          {
            "entries": [
              {
                "index": int,
                "doc_id": str,
                "title": str,
                "authors": [str],
                "year": str | None,
                "url": str | None,
                "doi": str | None,
                "apa": str,
                "bibtex": str,
                "bibtex_key": str
              },
              ...
            ],
            "apa_text": "1. Doe, J. (2024). ...\\n2. ...",
            "bibtex_text": "@article{doe2024foo, ...}\\n\\n@misc{...}"
          }
        """
        cited_set = set(cited_indices) if cited_indices else set()
        # If no cited indices were detected, include EVERY analyzed
        # document — the user still wants a references section even if
        # the LLM forgot inline [n] markers.
        if not cited_set:
            cited_set = {d.index for d in context.documents_with_analysis}
        if not cited_set:
            return {"entries": [], "apa_text": "", "bibtex_text": ""}

        items = [d for d in context.documents if d.index in cited_set]
        items.sort(key=lambda d: d.index)

        entries: list[dict] = []
        bibtex_keys: set[str] = set()

        for d in items:
            year = _year_from(d.published_at)
            base_key = _make_bibtex_key(d, year)
            key = base_key
            i = 2
            while key in bibtex_keys:
                key = f"{base_key}{i}"
                i += 1
            bibtex_keys.add(key)

            apa = _format_apa(d, year)
            bibtex = _format_bibtex(d, key, year)

            entries.append(
                {
                    "index": d.index,
                    "doc_id": str(d.id),
                    "title": d.title,
                    "authors": d.authors,
                    "year": year,
                    "url": d.source_url,
                    "doi": d.doi,
                    "apa": apa,
                    "bibtex": bibtex,
                    "bibtex_key": key,
                }
            )

        apa_text = "\n".join(
            f"[{e['index']}] {e['apa']}" for e in entries
        )
        bibtex_text = "\n\n".join(e["bibtex"] for e in entries)

        return {
            "entries": entries,
            "apa_text": apa_text,
            "bibtex_text": bibtex_text,
        }


# ── Formatters ───────────────────────────────────────────────────────────


def _year_from(published_at: str | None) -> str | None:
    if not published_at:
        return None
    m = re.match(r"^(\d{4})", published_at)
    return m.group(1) if m else None


def _format_authors_apa(authors: list[str]) -> str:
    if not authors:
        return ""
    formatted = [_apa_name(a) for a in authors]
    if len(formatted) == 1:
        return formatted[0]
    if len(formatted) == 2:
        return f"{formatted[0]}, & {formatted[1]}"
    if len(formatted) <= 6:
        return ", ".join(formatted[:-1]) + f", & {formatted[-1]}"
    return ", ".join(formatted[:6]) + ", ... " + formatted[-1]


def _apa_name(full_name: str) -> str:
    """`John Doe` → `Doe, J.`. Best-effort; leaves ambiguous names untouched."""
    parts = full_name.strip().split()
    if len(parts) < 2:
        return full_name.strip()
    last = parts[-1]
    initials = " ".join(f"{p[0]}." for p in parts[:-1] if p)
    return f"{last}, {initials}".strip(", ")


def _format_apa(doc: DocumentItem, year: str | None) -> str:
    parts: list[str] = []
    authors_str = _format_authors_apa(doc.authors)
    if authors_str:
        parts.append(authors_str)
    if year:
        parts.append(f"({year})")
    elif not authors_str:
        parts.append("(n.d.)")
    title = doc.title or "Untitled"
    parts.append(f"{title}.")
    if doc.doi:
        parts.append(f"https://doi.org/{doc.doi}")
    elif doc.source_url:
        parts.append(doc.source_url)
    elif doc.source_type:
        parts.append(f"({doc.source_type})")
    return " ".join(parts).strip()


def _format_bibtex(doc: DocumentItem, key: str, year: str | None) -> str:
    """Pick @article when there's a DOI; @misc otherwise."""
    entry_type = "article" if doc.doi else "misc"
    fields: list[tuple[str, str]] = []
    if doc.authors:
        fields.append(("author", " and ".join(_bibtex_escape(a) for a in doc.authors)))
    fields.append(("title", _bibtex_escape(doc.title or "Untitled")))
    if year:
        fields.append(("year", year))
    if doc.doi:
        fields.append(("doi", _bibtex_escape(doc.doi)))
    if doc.source_url:
        fields.append(("url", doc.source_url))
    if doc.source_type:
        fields.append(("note", _bibtex_escape(doc.source_type)))

    body = ",\n  ".join(f"{name} = {{{value}}}" for name, value in fields)
    return f"@{entry_type}{{{key},\n  {body}\n}}"


def _bibtex_escape(s: str) -> str:
    """Escape characters that BibTeX treats specially."""
    if not s:
        return ""
    return (
        s.replace("\\", "")
        .replace("{", "(")
        .replace("}", ")")
        .replace("\n", " ")
    )


def _make_bibtex_key(doc: DocumentItem, year: str | None) -> str:
    """E.g. `doe2024transformer`."""
    last_name = ""
    if doc.authors:
        first_author = doc.authors[0]
        parts = first_author.strip().split()
        if parts:
            last_name = re.sub(r"[^A-Za-z]", "", parts[-1]).lower()
    if not last_name:
        last_name = "doc"

    title_word = ""
    for word in (doc.title or "").split():
        cleaned = re.sub(r"[^A-Za-z]", "", word).lower()
        if len(cleaned) >= 4:
            title_word = cleaned
            break
    if not title_word:
        title_word = "ref"

    yr = year or str(datetime.now().year)
    return f"{last_name}{yr}{title_word[:14]}"
