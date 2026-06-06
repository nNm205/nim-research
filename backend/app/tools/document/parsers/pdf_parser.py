"""PDFParser — extract text, tables, and mathematical formulas from a PDF.

Strategy:
  - PyMuPDF (`fitz`) for fast page text.
  - pdfplumber for structured tables.
  - Line-based heuristic for mathematical formulas (math-symbol density,
    equation labels like "(1)" / "Eq. 3", and visual cues like indentation).

Tables and formulas are converted to markdown blocks and spliced back into
the page text so chunkers see them as coherent blocks.
"""

from __future__ import annotations

import io
import re
from pathlib import Path

import fitz
import pdfplumber

from app.tools.document.parsers.base import BaseParser
from app.tools.document.schemas.parsed_document import (
    ParsedDocument,
    ParsedFormula,
    ParsedTable,
)
from app.utils.logger import logger


# Caption regex used for table titles.
_CAPTION_RE = re.compile(
    r"\bTable\s+(\d+(?:\.\d+)?)\s*[\.\:\-—]?\s*([^\n]{0,160})?",
    re.IGNORECASE,
)

# ── Formula detection ──────────────────────────────────────────────────────

# Unicode math characters frequently seen in PDF text streams of academic
# papers. We keep this small on purpose — large character classes catch too
# many false positives in figure captions.
_MATH_CHARS = (
    "∑∏∫∮∂∇∞±∓×÷·≠≈≡≤≥≪≫"
    "αβγδεζηθικλμνξοπρστυφχψω"
    "ΓΔΘΛΞΠΣΦΨΩ"
    "→←↔⇒⇐⇔↦"
    "∈∉⊂⊃⊆⊇∩∪∅"
    "ℝℕℤℚℂ"
    "√"
)
_MATH_CHAR_SET = set(_MATH_CHARS)

# Equation label at end of line: "(1)", "(3.2)", "(A.1)"
_EQUATION_LABEL_RE = re.compile(r"\(([\dA-Z]+(?:\.\d+)?)\)\s*$")

# Strong LaTeX cues — when present, line is almost certainly a formula
_LATEX_CUES_RE = re.compile(
    r"\\(?:frac|sqrt|sum|int|prod|partial|nabla|alpha|beta|gamma|theta|"
    r"sigma|mathbf|mathbb|mathcal|operatorname|text|begin\{equation\}"
    r"|begin\{align\})"
)

# Non-formula prose markers we should reject (citations, footnotes, etc.)
_REFERENCE_LIKE_RE = re.compile(r"^\s*\[\d+\]\s+[A-Z]")  # "[12] Vaswani et al."

# Lines containing both a typical sentence ending AND lowercase prose are
# probably text, not formulas.
_PROSE_END_RE = re.compile(r"[a-z]{3,}[\.!?]\s*$")


# ── Page text extraction (blocks + font-size heading detection) ─────────────


def _normalize_whitespace(text: str) -> str:
    """Replace non-breaking space, narrow-NBSP, etc. with regular ASCII space."""
    if not text:
        return text
    return (
        text.replace("\u00a0", " ")
        .replace("\u202f", " ")
        .replace("\u200b", "")
        .replace("\ufeff", "")
    )


def _extract_page_text(page) -> str:
    """Return reading-order text for one page using PyMuPDF's dict mode.

    Steps:
      1. ``get_text("dict")`` returns blocks → lines → spans, each carrying
         font, size, bbox.
      2. We compute the page's median body font size (skipping spans
         shorter than 6 chars to avoid biasing on single-character page
         numbers / footnotes).
      3. Sort blocks by reading order. For multi-column pages we cluster
         blocks into columns by x-coordinate first, then read each column
         top-to-bottom.
      4. For each line, concatenate spans. If the line's median font size
         is ≥ 1.4 × body size we treat it as a heading and surround it
         with blank lines so the chunker's regex (which requires line
         isolation) can find it.
    """
    try:
        page_dict = page.get_text("dict")
    except Exception as e:
        logger.warning(f"PDFParser: get_text(dict) failed, falling back: {e}")
        return _normalize_whitespace(page.get_text() or "")

    blocks = [b for b in page_dict.get("blocks", []) if b.get("type", 0) == 0]
    if not blocks:
        return ""

    # Body-text font size baseline (median of "long enough" spans)
    body_font_size = _estimate_body_font_size(blocks)
    heading_threshold = body_font_size * 1.4 if body_font_size else None

    # Sort blocks into reading order. For 2-column layouts, group by
    # rounded x-midpoint into bands, then read top-to-bottom within each
    # band, then left band before right band.
    page_width = page_dict.get("width") or page.rect.width
    columns = _cluster_blocks_into_columns(blocks, page_width)

    rendered_lines: list[str] = []

    for col_blocks in columns:
        for block in col_blocks:
            for line in block.get("lines", []):
                spans = line.get("spans", [])
                if not spans:
                    continue
                line_text_parts = [_normalize_whitespace(s.get("text", "")) for s in spans]
                line_text = "".join(line_text_parts).rstrip()
                if not line_text.strip():
                    continue

                # Median font size of this line — used to flag headings.
                sizes = [
                    float(s.get("size", body_font_size or 0))
                    for s in spans
                    if (s.get("text") or "").strip()
                ]
                line_size = sorted(sizes)[len(sizes) // 2] if sizes else 0

                is_heading_size = (
                    heading_threshold is not None
                    and line_size >= heading_threshold
                )

                if is_heading_size:
                    # Surround with blank lines so the chunker sees the
                    # heading as visually isolated even when the PDF had
                    # no blank line in the original layout.
                    if rendered_lines and rendered_lines[-1] != "":
                        rendered_lines.append("")
                    rendered_lines.append(line_text.strip())
                    rendered_lines.append("")
                else:
                    rendered_lines.append(line_text)

            # Block boundary → blank line.
            if rendered_lines and rendered_lines[-1] != "":
                rendered_lines.append("")

    return "\n".join(rendered_lines).rstrip()


def _estimate_body_font_size(blocks: list[dict]) -> float:
    """Median font size of long-enough text spans on the page."""
    sizes: list[float] = []
    for block in blocks:
        for line in block.get("lines", []):
            for span in line.get("spans", []):
                text = (span.get("text") or "").strip()
                if len(text) < 6:
                    continue
                size = float(span.get("size") or 0)
                if size > 0:
                    sizes.append(size)
    if not sizes:
        return 10.0  # safe default for academic papers
    sizes.sort()
    return sizes[len(sizes) // 2]


def _cluster_blocks_into_columns(
    blocks: list[dict], page_width: float
) -> list[list[dict]]:
    """Group blocks by which column they belong to and return columns
    in left-to-right order with each column's blocks in top-to-bottom order.

    For single-column papers this trivially returns one column with all
    blocks sorted by ``y0``. For two-column papers the gap between the
    rightmost block edge of the left column and the leftmost edge of the
    right column is wide, and clustering by block midpoint x picks them
    apart cleanly.
    """
    if not blocks:
        return []

    # Each block's bbox tuple: (x0, y0, x1, y1)
    enriched = []
    for b in blocks:
        bbox = b.get("bbox", (0, 0, 0, 0))
        enriched.append({
            "block": b,
            "x0": bbox[0],
            "y0": bbox[1],
            "x1": bbox[2],
            "x_mid": (bbox[0] + bbox[2]) / 2.0,
        })

    # Heuristic 2-column detection: split if there's a clear gap around
    # ``page_width / 2``. A block's midpoint < 0.45 × width → left column;
    # > 0.55 × width → right column. Otherwise it spans both columns
    # (figure / table caption) and we treat it as "full-width" — assigned
    # to a synthetic centre stream that interleaves with both columns.
    left_threshold = page_width * 0.45
    right_threshold = page_width * 0.55

    left = [e for e in enriched if e["x_mid"] < left_threshold]
    right = [e for e in enriched if e["x_mid"] > right_threshold]
    full = [
        e
        for e in enriched
        if left_threshold <= e["x_mid"] <= right_threshold
    ]

    # If left or right column is empty, the page is single-column. Just
    # sort everything by y0.
    if not left or not right:
        return [[e["block"] for e in sorted(enriched, key=lambda e: e["y0"])]]

    columns_out: list[list[dict]] = []
    columns_out.append([e["block"] for e in sorted(left, key=lambda e: e["y0"])])
    columns_out.append([e["block"] for e in sorted(right, key=lambda e: e["y0"])])
    if full:
        # Append full-width blocks at the end of the left column (best effort —
        # they're usually figures whose order doesn't strictly matter).
        columns_out[0].extend(
            e["block"] for e in sorted(full, key=lambda e: e["y0"])
        )
    return columns_out


def _looks_like_formula(line: str) -> tuple[bool, str | None]:
    """Heuristic test: return (is_formula, label_if_any).

    Rules of thumb tuned for STEM PDFs:
    - Reject lines under 3 chars or that clearly read as prose.
    - Strong signal: explicit LaTeX cue → formula.
    - Strong signal: ends with "(N)" or "(N.M)" AND has any math content → formula.
    - Density signal: ratio of math symbols + ASCII operators is high (>=0.18).
    """
    raw = line.rstrip()
    stripped = raw.strip()
    if len(stripped) < 3:
        return False, None
    if _REFERENCE_LIKE_RE.match(stripped):
        return False, None
    # Must contain at least one operator-like character to even be considered
    has_op = any(c in _MATH_CHAR_SET or c in "=+−*^/<>" for c in stripped)
    if not has_op:
        return False, None

    # Pull out an equation label first (we still return it on prose-rejected
    # lines so callers can re-attach a number to a multi-line equation).
    label: str | None = None
    m = _EQUATION_LABEL_RE.search(stripped)
    if m:
        label = m.group(1)
        body = stripped[: m.start()].rstrip()
    else:
        body = stripped

    # LaTeX cue → almost certain
    if _LATEX_CUES_RE.search(body):
        return True, label

    # Prose with sentence punctuation → not a formula
    if _PROSE_END_RE.search(body):
        return False, None

    # Density: count math chars + ASCII operators
    body_for_density = body.replace(" ", "")
    if len(body_for_density) < 2:
        return False, None
    math_hits = sum(
        1 for c in body_for_density
        if c in _MATH_CHAR_SET or c in "=+−*^/<>"
    )
    density = math_hits / len(body_for_density)
    has_equals = "=" in body
    unicode_density = sum(1 for c in body_for_density if c in _MATH_CHAR_SET) / len(
        body_for_density
    )

    # Letters: a formula often has a few variable names but not full words
    word_lengths = [len(w) for w in re.findall(r"[A-Za-z]{2,}", body)]
    long_word_count = sum(1 for w in word_lengths if w >= 4)

    # Equation-numbered short line: lower density bar
    if label is not None and (density >= 0.10 or has_equals) and long_word_count <= 6:
        return True, label
    # `=`-anchored line with at least some math operators and few prose words
    if has_equals and density >= 0.08 and long_word_count <= 6:
        return True, label
    # Heavy unicode math (e.g. "y = α x + β + ε" or pure-symbol lines)
    if unicode_density >= 0.30 and long_word_count <= 6:
        return True, label
    return False, None


def _detect_formulas_in_page(
    page_text: str, page_number: int
) -> list[tuple[int, ParsedFormula]]:
    """Return list of (line_index, ParsedFormula) found on a single page."""
    if not page_text:
        return []

    out: list[tuple[int, ParsedFormula]] = []
    lines = page_text.split("\n")
    pending_buffer: list[str] = []
    pending_start_idx: int | None = None

    for idx, line in enumerate(lines):
        is_f, label = _looks_like_formula(line)
        if is_f:
            if pending_start_idx is None:
                pending_start_idx = idx
            pending_buffer.append(line.rstrip())
            # If this line is labelled, finalise the buffered equation
            if label:
                body = "\n".join(pending_buffer).strip()
                # Strip trailing label out of body — we'll show it separately
                body = _EQUATION_LABEL_RE.sub("", body).rstrip()
                if body:
                    out.append(
                        (
                            pending_start_idx,
                            ParsedFormula(
                                text=body,
                                label=label,
                                kind="display",
                                page=page_number,
                            ),
                        )
                    )
                pending_buffer = []
                pending_start_idx = None
            continue

        # Non-formula line ends any pending buffer
        if pending_buffer:
            body = "\n".join(pending_buffer).strip()
            if body and len(body) >= 4:
                out.append(
                    (
                        pending_start_idx or idx,
                        ParsedFormula(
                            text=body,
                            label=None,
                            kind="display",
                            page=page_number,
                        ),
                    )
                )
            pending_buffer = []
            pending_start_idx = None

    # Flush trailing buffer at end of page
    if pending_buffer:
        body = "\n".join(pending_buffer).strip()
        if body and len(body) >= 4:
            out.append(
                (
                    pending_start_idx or len(lines) - 1,
                    ParsedFormula(
                        text=body,
                        label=None,
                        kind="display",
                        page=page_number,
                    ),
                )
            )

    return out


# ──────────────────────────────────────────────────────────────────────────


class PDFParser(BaseParser):
    async def parse(self, file_path: Path) -> ParsedDocument:
        raw_bytes = Path(file_path).read_bytes()

        # 1. Page-level text via PyMuPDF.
        #
        # We use the *blocks* extraction mode and sort by reading order so
        # multi-column papers come out in the correct sequence. The default
        # ``page.get_text()`` is reasonable for single-column documents but
        # routinely scrambles two-column academic PDFs, which causes the
        # heading detector downstream to miss section boundaries.
        #
        # We also detect headings by font size: a line whose median font
        # size is at least 1.4 × the body font size gets a blank-line
        # separator inserted before it, which lets the heading regex on
        # the chunker side find it as an isolated line even when the PDF
        # had no explicit blank line above the heading.
        doc = fitz.open(stream=raw_bytes, filetype="pdf")
        page_texts: list[str] = []
        for page in doc:
            page_texts.append(_extract_page_text(page))
        metadata = doc.metadata or {}
        page_count = len(doc)
        doc.close()

        # 2. Structured tables via pdfplumber
        tables = self._extract_tables(raw_bytes, page_texts)

        # 3. Line-based formula detection on each page
        formulas: list[ParsedFormula] = []
        per_page_formulas: dict[int, list[tuple[int, ParsedFormula]]] = {}
        for page_idx, text in enumerate(page_texts, start=1):
            page_formulas = _detect_formulas_in_page(text, page_idx)
            per_page_formulas[page_idx] = page_formulas
            formulas.extend(f for _, f in page_formulas)

        if formulas:
            sample = ", ".join(
                f"({f.label})" if f.label else "<unlabelled>"
                for f in formulas[:5]
            )
            logger.info(
                f"PDFParser: detected {len(formulas)} formula block(s) (first 5: {sample})"
            )

        # 4. Splice formulas + tables into the page text. Formulas first
        # (line-based, deterministic), tables second (caption-based), so a
        # table caption-search doesn't accidentally land inside a formula.
        rendered_pages = self._render_pages_with_formulas(
            page_texts, per_page_formulas
        )
        full_text = self._splice_tables(rendered_pages, tables)

        return ParsedDocument(
            text=full_text,
            page_count=page_count,
            title=metadata.get("title"),
            author=metadata.get("author"),
            metadata=metadata,
            tables=tables,
            formulas=formulas,
        )

    # ── Table extraction ─────────────────────────────────────────────────────

    def _extract_tables(
        self, raw_bytes: bytes, page_texts: list[str]
    ) -> list[ParsedTable]:
        tables: list[ParsedTable] = []
        try:
            with pdfplumber.open(io.BytesIO(raw_bytes)) as pdf:
                for page_idx, page in enumerate(pdf.pages):
                    page_text = (
                        page_texts[page_idx]
                        if page_idx < len(page_texts)
                        else page.extract_text() or ""
                    )
                    try:
                        page_tables = page.extract_tables() or []
                    except Exception as e:
                        logger.warning(
                            f"PDFParser: pdfplumber.extract_tables failed on "
                            f"page {page_idx + 1}: {e}"
                        )
                        continue

                    for raw_table in page_tables:
                        if not raw_table or len(raw_table) < 2:
                            continue
                        parsed = self._normalise_table(raw_table, page_idx + 1)
                        if parsed.is_empty:
                            continue
                        parsed.title = self._guess_caption(page_text)
                        tables.append(parsed)
        except Exception as e:
            logger.warning(f"PDFParser: pdfplumber failed entirely: {e}")
            return []

        if tables:
            logger.info(
                f"PDFParser: extracted {len(tables)} table(s) "
                f"({[t.title or 'untitled' for t in tables[:3]]})"
            )
        return tables

    def _normalise_table(
        self, raw_table: list[list[str | None]], page: int
    ) -> ParsedTable:
        cleaned: list[list[str]] = []
        for row in raw_table:
            normalised = [(cell or "").strip() for cell in row]
            if any(c for c in normalised):
                cleaned.append(normalised)

        if len(cleaned) < 2:
            return ParsedTable(page=page)

        headers = cleaned[0]
        rows = cleaned[1:]
        total_cells = sum(len(r) for r in rows) + len(headers)
        if total_cells < 4:
            return ParsedTable(page=page)
        return ParsedTable(headers=headers, rows=rows, page=page)

    def _guess_caption(self, page_text: str) -> str | None:
        if not page_text:
            return None
        m = _CAPTION_RE.search(page_text)
        if not m:
            return None
        number = m.group(1).strip()
        title = (m.group(2) or "").strip().rstrip(".:—-").strip()
        if title:
            return f"Table {number}: {title}"
        return f"Table {number}"

    # ── Splicing formulas back into text ────────────────────────────────────

    def _render_pages_with_formulas(
        self,
        page_texts: list[str],
        per_page_formulas: dict[int, list[tuple[int, ParsedFormula]]],
    ) -> list[str]:
        """Return the page texts with each formula replaced by its markdown
        representation (so the LLM sees `[Equation 3]\n```formula\n...```` instead
        of a stream of math symbols mid-paragraph)."""
        rendered: list[str] = []
        for page_idx, text in enumerate(page_texts, start=1):
            formulas = per_page_formulas.get(page_idx) or []
            if not formulas or not text:
                rendered.append(text)
                continue

            lines = text.split("\n")
            # Build a marker per formula and replace the line range it spanned.
            # We sort by line index ascending and process in reverse so indexes
            # don't shift while we splice.
            formulas_sorted = sorted(formulas, key=lambda x: x[0], reverse=True)
            for start_idx, formula in formulas_sorted:
                # Find the contiguous range of formula lines starting at
                # start_idx by re-scanning until the body matches.
                body_lines = formula.text.split("\n")
                end_idx = min(start_idx + len(body_lines), len(lines))
                # Replace the range with the formula's markdown
                replacement = formula.to_markdown()
                lines[start_idx:end_idx] = [replacement]
            rendered.append("\n".join(lines))
        return rendered

    # ── Splicing tables into text ────────────────────────────────────────────

    def _splice_tables(
        self, page_texts: list[str], tables: list[ParsedTable]
    ) -> str:
        if not tables:
            return "\n\n".join(t for t in page_texts if t).strip()

        per_page: dict[int, list[ParsedTable]] = {}
        for t in tables:
            per_page.setdefault(t.page or 1, []).append(t)

        rendered_pages: list[str] = []
        for page_idx, text in enumerate(page_texts, start=1):
            page_text = text or ""
            for t in per_page.get(page_idx, []):
                md = t.to_markdown()
                if not md:
                    continue
                inserted = False
                if t.title:
                    cap_match = re.search(
                        re.escape(t.title.split(":", 1)[0]),
                        page_text,
                        re.IGNORECASE,
                    )
                    if cap_match:
                        end = cap_match.end()
                        nl = page_text.find("\n", end)
                        if nl < 0:
                            nl = len(page_text)
                        page_text = (
                            page_text[:nl]
                            + "\n\n"
                            + md
                            + "\n\n"
                            + page_text[nl:]
                        )
                        inserted = True

                if not inserted:
                    page_text = page_text.rstrip() + "\n\n" + md + "\n\n"
            rendered_pages.append(page_text)

        return "\n\n".join(p for p in rendered_pages if p).strip()
