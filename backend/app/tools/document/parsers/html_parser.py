"""HTMLParser — extract main-content text, tables, and formulas from HTML.

Both tables and formulas are converted to markdown blocks and replaced inline
with markers, so the resulting text preserves document order and downstream
chunkers see structured content as coherent blocks.

Formulas are detected from common math markup conventions:
  - <math> elements (MathML, used by Wikipedia and arxiv-vanity)
  - .katex / .MathJax / .math / .equation containers (KaTeX, MathJax, Sphinx)
  - Inline `\\(...\\)` and display `\\[...\\]` / `$$...$$` LaTeX fences in plain text
"""

from __future__ import annotations

import re
from pathlib import Path

from bs4 import BeautifulSoup

from app.tools.document.parsers.base import BaseParser
from app.tools.document.schemas.parsed_document import (
    ParsedDocument,
    ParsedFormula,
    ParsedTable,
)
from app.utils.logger import logger


_CAPTION_TAGS = ("caption", "figcaption")

_MATH_CLASS_HINTS = (
    "katex",
    "katex-display",
    "mathjax",
    "math",
    "equation",
    "MathJax",
    "MathJax_Display",
    "MathJax_Preview",
)


class HTMLParser(BaseParser):
    async def parse(self, file_path: Path) -> ParsedDocument:
        html = file_path.read_text(encoding="utf-8", errors="replace")
        soup = BeautifulSoup(html, "html.parser")

        title = None
        if soup.title and soup.title.string:
            title = soup.title.string.strip()

        # Strip noise elements
        for tag in soup(
            [
                "script",
                "style",
                "nav",
                "footer",
                "header",
                "aside",
                "form",
                "noscript",
                "iframe",
            ]
        ):
            tag.decompose()

        # Strip ad/nav by class/id hints
        for tag in soup.find_all(True):
            cls = " ".join(tag.get("class", []))
            id_ = tag.get("id", "")
            if any(
                kw in cls.lower() or kw in id_.lower()
                for kw in (
                    "nav",
                    "menu",
                    "sidebar",
                    "footer",
                    "header",
                    "ad",
                    "banner",
                    "cookie",
                    "popup",
                )
            ):
                tag.decompose()

        # Find main content container
        main = (
            soup.find("main")
            or soup.find("article")
            or soup.find(id="content")
            or soup.find(id="main")
            or soup.find(class_="content")
            or soup.body
        )
        if main is None:
            main = soup

        # 1. Extract structured tables BEFORE turning the DOM into text
        tables = self._extract_tables(main)

        # 2. Extract math formulas BEFORE turning the DOM into text
        formulas = self._extract_formulas(main)

        # 3. Replace each <table> in the DOM with a placeholder
        for idx, table_tag in enumerate(main.find_all("table")):
            if idx < len(tables):
                marker = f"\n\n__TABLE_PLACEHOLDER_{idx}__\n\n"
                table_tag.replace_with(marker)

        # 4. Now flatten DOM to text
        text = main.get_text(separator="\n", strip=True)

        # 5. Substitute table markers
        for idx, table in enumerate(tables):
            marker = f"__TABLE_PLACEHOLDER_{idx}__"
            text = text.replace(marker, table.to_markdown(), 1)

        # 6. Detect inline LaTeX fences in the flattened text and add to
        # `formulas`. We do this AFTER DOM flattening because some pages put
        # `\\(...\\)` directly in text nodes without any <math> tag.
        text, plain_text_formulas = self._extract_inline_latex(text)
        formulas.extend(plain_text_formulas)

        # Collapse excessive blank lines
        text = re.sub(r"\n{3,}", "\n\n", text).strip()

        if formulas:
            sample = ", ".join(
                f"({f.label})" if f.label else "<unlabelled>"
                for f in formulas[:5]
            )
            logger.info(
                f"HTMLParser: detected {len(formulas)} formula(s) (first 5: {sample})"
            )

        return ParsedDocument(
            text=text,
            page_count=1,
            title=title,
            tables=tables,
            formulas=formulas,
        )

    # ── Table extraction ─────────────────────────────────────────────────────

    def _extract_tables(self, root) -> list[ParsedTable]:
        tables: list[ParsedTable] = []
        for table_tag in root.find_all("table"):
            try:
                parsed = self._parse_table(table_tag)
            except Exception as e:
                logger.warning(f"HTMLParser: table extraction failed: {e}")
                continue
            if parsed.is_empty:
                continue
            tables.append(parsed)
        if tables:
            logger.info(
                f"HTMLParser: extracted {len(tables)} table(s) "
                f"({[t.title or 'untitled' for t in tables[:3]]})"
            )
        return tables

    def _parse_table(self, table_tag) -> ParsedTable:
        title: str | None = None
        for cap_tag in _CAPTION_TAGS:
            cap = table_tag.find(cap_tag)
            if cap and cap.get_text(strip=True):
                title = cap.get_text(strip=True)
                break
        if not title:
            parent = table_tag.find_parent("figure")
            if parent:
                cap = parent.find("figcaption")
                if cap and cap.get_text(strip=True):
                    title = cap.get_text(strip=True)

        headers: list[str] = []
        thead = table_tag.find("thead")
        if thead:
            first_row = thead.find("tr")
            if first_row:
                headers = [
                    th.get_text(strip=True)
                    for th in first_row.find_all(["th", "td"])
                ]

        body_rows = []
        tbody = table_tag.find("tbody")
        row_source = tbody.find_all("tr") if tbody else table_tag.find_all("tr")

        first_row_used_as_header = False
        for tr in row_source:
            cells = [c.get_text(strip=True) for c in tr.find_all(["th", "td"])]
            if not any(cells):
                continue
            if not headers and not first_row_used_as_header:
                ths = tr.find_all("th")
                if ths and len(ths) == len(cells):
                    headers = cells
                    first_row_used_as_header = True
                    continue
            body_rows.append(cells)

        if len(body_rows) < 1 and not headers:
            return ParsedTable()

        if not headers and body_rows:
            headers = body_rows[0]
            body_rows = body_rows[1:]

        return ParsedTable(headers=headers, rows=body_rows, title=title)

    # ── Formula extraction ───────────────────────────────────────────────────

    def _extract_formulas(self, root) -> list[ParsedFormula]:
        """Find math elements and replace them with formula-block markers.

        The order matters: we process MathML first (the most semantic), then
        class-based math containers (KaTeX/MathJax). Each formula tag is
        replaced in-place with a marker that we render later in `parse()`.
        """
        formulas: list[ParsedFormula] = []

        # 1. <math> (MathML)
        for math_tag in list(root.find_all("math")):
            text = math_tag.get_text(separator=" ", strip=True)
            label = self._guess_label_from_attr(math_tag)
            kind = (
                "display"
                if math_tag.get("display", "").lower() == "block"
                else "inline"
            )
            if not text:
                continue
            f = ParsedFormula(text=text, label=label, kind=kind)
            formulas.append(f)
            math_tag.replace_with(f"\n\n{f.to_markdown()}\n\n")

        # 2. KaTeX / MathJax / generic .math containers
        for tag in list(root.find_all(True)):
            if tag.name in ("math",):  # already handled
                continue
            cls_list = tag.get("class") or []
            cls_lower = " ".join(c.lower() for c in cls_list)
            if not cls_lower:
                continue
            if not any(hint.lower() in cls_lower for hint in _MATH_CLASS_HINTS):
                continue
            text = tag.get_text(separator=" ", strip=True)
            if not text or len(text) < 3:
                continue
            label = self._guess_label_from_attr(tag)
            kind = (
                "display"
                if any(k in cls_lower for k in ("display", "block", "equation"))
                else "inline"
            )
            f = ParsedFormula(text=text, label=label, kind=kind)
            formulas.append(f)
            tag.replace_with(f"\n\n{f.to_markdown()}\n\n")

        return formulas

    def _guess_label_from_attr(self, tag) -> str | None:
        for attr in ("data-label", "data-equation", "id", "aria-label"):
            v = tag.get(attr)
            if not v:
                continue
            v = str(v).strip()
            # Pull the trailing number out of common patterns ("eq3", "equation:7")
            m = re.search(r"(\d+(?:\.\d+)?)$", v)
            if m:
                return m.group(1)
        return None

    # ── Inline LaTeX fences in plain text ───────────────────────────────────

    _LATEX_FENCE_RE = re.compile(
        r"\\\[(.+?)\\\]"      # \[ ... \]
        r"|\$\$(.+?)\$\$"      # $$ ... $$
        r"|\\\((.+?)\\\)",     # \( ... \)
        re.DOTALL,
    )

    def _extract_inline_latex(self, text: str) -> tuple[str, list[ParsedFormula]]:
        formulas: list[ParsedFormula] = []

        def _repl(match: re.Match) -> str:
            body = next(g for g in match.groups() if g is not None).strip()
            if not body:
                return match.group(0)
            kind = "display" if match.group(0).startswith(("\\[", "$$")) else "inline"
            f = ParsedFormula(text=body, label=None, kind=kind)
            formulas.append(f)
            return f"\n\n{f.to_markdown()}\n\n"

        replaced = self._LATEX_FENCE_RE.sub(_repl, text)
        return replaced, formulas
