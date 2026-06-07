"""PDFParser — extract text, tables, and mathematical formulas from a PDF.

Strategy:
  1. **docling** does the heavy lifting: layout analysis, reading-order
     reconstruction, heading detection, table structure extraction. Its
     output is markdown that already has section headers (``## 1
     Introduction``), table blocks, and placeholder markers for content
     it couldn't decode (e.g. ``<!-- formula-not-decoded -->``).
  2. **PyMuPDF fallback** decodes the formulas docling left as
     placeholders. We pull the bbox of each formula item from the
     docling result and read the raw text under that rectangle from the
     PDF — that recovers Unicode math like ``softmax(QKᵀ/√dₖ)V`` that
     would otherwise be lost.
  3. **Heuristic post-processing** turns each decoded formula into a
     ``[Equation]\\n```formula\\n...```` block consistent with the rest
     of the parser, so chunkers + LLMs see formulas as structured units.

We keep ``LegacyPDFParser`` (the previous PyMuPDF + pdfplumber pipeline)
as a fallback in case docling fails on a particular document. The
``DocumentIngestionService`` automatically falls back to it on errors.
"""

from __future__ import annotations

import asyncio
import io
import re
from dataclasses import dataclass
from pathlib import Path

import fitz

from app.tools.document.parsers.base import BaseParser
from app.tools.document.schemas.parsed_document import (
    ParsedDocument,
    ParsedFormula,
    ParsedTable,
)
from app.utils.logger import logger


# Marker docling emits when it identifies a formula but can't decode
# its content. We replace this in-place with our own ``[Equation]``
# block backed by a PyMuPDF text extraction over the formula bbox.
_DOCLING_FORMULA_MARKER = "<!-- formula-not-decoded -->"

# Caption regex used when a formula bbox sits next to an "Equation N" or
# "(N)" label in surrounding text. Used to attach a label to the
# decoded formula.
_TRAILING_EQ_LABEL_RE = re.compile(r"\(([\dA-Z]+(?:\.\d+)?)\)\s*$")
_LEADING_EQ_LABEL_RE = re.compile(r"^\s*Equation\s+([\dA-Z]+(?:\.\d+)?)\b", re.I)


# ─── Decoded-formula record (internal to this module) ───────────────────────


@dataclass
class _DoclingFormula:
    """Internal placeholder for a docling-detected formula.

    ``page`` is 1-based. ``bbox`` is in PDF coordinate units (points)
    with origin at BOTTOM-LEFT; we convert to top-left when extracting
    the bbox text via PyMuPDF.
    """

    page: int
    bbox_bottom_left: tuple[float, float, float, float]  # l, t, r, b
    decoded_text: str | None = None
    label: str | None = None


# ─── Public PDF parser ──────────────────────────────────────────────────────


class PDFParser(BaseParser):
    """docling-backed PDF parser with PyMuPDF formula fallback."""

    async def parse(self, file_path: Path) -> ParsedDocument:
        """Convert ``file_path`` to ``ParsedDocument``.

        docling's converter is synchronous and CPU-heavy (layout + OCR
        models), so we run it on a worker thread to keep the agent's
        event loop responsive.
        """
        path = Path(file_path)
        return await asyncio.to_thread(self._parse_sync, path)

    # ── Heavy lifting ───────────────────────────────────────────────────

    def _parse_sync(self, path: Path) -> ParsedDocument:
        # Lazy import — docling pulls in heavy ML dependencies. Keeping
        # the import local lets the rest of the app start even when
        # docling isn't installed (the ingestion service will fall back
        # to ``LegacyPDFParser``).
        from docling.document_converter import DocumentConverter

        try:
            converter = DocumentConverter()
            result = converter.convert(path)
        except Exception as e:
            logger.warning(
                f"PDFParser(docling): conversion failed for {path}: {e}; "
                f"falling back to legacy parser"
            )
            from app.tools.document.parsers.pdf_parser_legacy import (
                LegacyPDFParser,
            )
            # Run the legacy sync entry point to avoid spawning another
            # thread within this thread.
            return _run_legacy_sync(path)

        doc = result.document

        # 1. Markdown export — docling already does heading detection,
        # multi-column reading order, and table structure. We just need
        # to wire formulas in afterwards.
        markdown = doc.export_to_markdown() or ""

        # 2. Locate every FORMULA item in the doc. We need the page +
        # bbox to read the underlying glyph text out of the PDF.
        formula_items = _collect_formula_items(doc)

        # 3. Decode each formula with PyMuPDF. Formulas docling already
        # decoded (rare at default settings) keep their text; the rest
        # get the bbox-text we extract here.
        if formula_items:
            _decode_formulas_with_pymupdf(path, formula_items)

        # 4. Build ``ParsedFormula`` list (the Document schema) and
        # splice each one into the markdown in place of its placeholder.
        parsed_formulas: list[ParsedFormula] = []
        rendered_markdown = _splice_formulas_into_markdown(
            markdown, formula_items, parsed_formulas
        )

        # 4b. Strip markdown ATX heading prefixes (``## 1 Introduction``
        # → ``1 Introduction``). The downstream ``SectionAwareChunker``
        # detects sections via regexes that anchor on plain-text heading
        # shapes — when docling's ``##`` prefix is left in place every
        # regex misses every heading and the whole paper collapses into
        # one giant section. See ``_demarkdown_headings`` for details.
        rendered_markdown = _demarkdown_headings(rendered_markdown)

        # 5. Tables — docling already inlined them as markdown tables in
        # the export. We additionally collect them as structured records
        # so the AnalysisAgent can render them as proper tables in the
        # report. Failure to extract structured tables is non-fatal —
        # the markdown already has the table.
        parsed_tables = _collect_tables(doc)

        # 6. Pull metadata from the PDF (title / author) using PyMuPDF —
        # docling does not currently expose this. ``page_count`` comes
        # from docling's ``num_pages`` when available, else PyMuPDF.
        meta = _read_pdf_metadata(path)
        page_count = _safe_page_count(doc, meta.get("page_count"))

        return ParsedDocument(
            text=rendered_markdown.strip(),
            page_count=page_count,
            title=(doc.name or meta.get("title")),
            author=meta.get("author"),
            metadata=meta.get("raw") or {},
            tables=parsed_tables,
            formulas=parsed_formulas,
        )


def _run_legacy_sync(path: Path) -> ParsedDocument:
    """Invoke the legacy PyMuPDF + pdfplumber pipeline synchronously."""
    from app.tools.document.parsers.pdf_parser_legacy import LegacyPDFParser

    return asyncio.run(LegacyPDFParser().parse(path))


# Markdown ATX heading lines emitted by docling. We strip the leading
# ``#`` characters before sending text to the chunker so its plain-text
# heading regexes (``1 Introduction``, ``III. Methodology``, ``A. Setup``)
# actually match. Without this strip, docling's ``## 1 Introduction``
# never matches the chunker's regexes and the whole paper degenerates
# into a single un-sectioned span — which is the bug the user observed.
_ATX_HEADING_RE = re.compile(r"(?m)^(#{1,6})[ \t]+(.+?)[ \t]*$")


def _demarkdown_headings(markdown: str) -> str:
    """Convert ``## N. Title`` lines back to plain ``N. Title`` form.

    The chunker we ship (``SectionAwareChunker``) was tuned for raw PDF
    text where headings sit on their own line as plain prose. Markdown
    ATX headings (``##`` prefix) make those lines start with a hash,
    which never matches the chunker's regexes — so docling-produced
    output silently lost ALL section structure. The fix is the smallest
    one possible: strip the hash prefix and surround the line with
    blank lines so ``_has_isolation_before`` still passes.

    We always insert a blank line BEFORE the heading; the trailing
    blank line is added unconditionally too. Multiple heading lines in
    a row stay collapsed because the chunker's ``_has_isolation_before``
    treats consecutive headings as still isolated.
    """
    if not markdown or "#" not in markdown:
        return markdown

    def _strip(match: re.Match) -> str:
        title = match.group(2).strip()
        if not title:
            return match.group(0)
        return f"\n{title}\n"

    out = _ATX_HEADING_RE.sub(_strip, markdown)
    # Collapse triple+ blank lines so the chunker doesn't emit empty chunks.
    return re.sub(r"\n{3,}", "\n\n", out)


# ─── Formula handling ───────────────────────────────────────────────────────


def _collect_formula_items(docling_doc) -> list[_DoclingFormula]:
    """Walk the docling Document tree and pull out every FORMULA item.

    Each item carries ``prov[0]`` with a ``page_no`` and a ``bbox``
    (BOTTOMLEFT origin). Items without a usable provenance are skipped
    — without a bbox we can't decode the formula content.
    """
    formulas: list[_DoclingFormula] = []
    try:
        from docling_core.types.doc.labels import DocItemLabel
    except Exception:
        DocItemLabel = None  # noqa: N806

    for item, _level in docling_doc.iterate_items():
        label = getattr(item, "label", None)
        # ``label`` is an enum; compare via string for robustness across
        # docling versions.
        label_str = (
            label.value if hasattr(label, "value") else str(label or "")
        ).lower()
        if label_str != "formula":
            continue

        prov = getattr(item, "prov", None) or []
        if not prov:
            continue
        bbox = getattr(prov[0], "bbox", None)
        page_no = getattr(prov[0], "page_no", None)
        if bbox is None or page_no is None:
            continue

        formulas.append(
            _DoclingFormula(
                page=int(page_no),
                bbox_bottom_left=(
                    float(bbox.l),
                    float(bbox.t),
                    float(bbox.r),
                    float(bbox.b),
                ),
                decoded_text=(
                    item.text.strip()
                    if isinstance(getattr(item, "text", None), str)
                    and item.text.strip()
                    else None
                ),
            )
        )
    return formulas


def _decode_formulas_with_pymupdf(
    path: Path, formulas: list[_DoclingFormula]
) -> None:
    """Read the raw text under each formula bbox.

    Docling stores bboxes with ``coord_origin=BOTTOMLEFT`` (PDF
    convention). PyMuPDF's ``page.get_textbox`` expects rect coordinates
    in TOP-LEFT origin, so we convert via ``page_height - y``.

    Mutates ``formulas`` in place — sets ``decoded_text`` and ``label``
    when text was successfully read. Errors are logged and swallowed:
    a formula we can't decode just stays as ``[Equation]`` with no body.
    """
    if not formulas:
        return

    try:
        pdf = fitz.open(path)
    except Exception as e:
        logger.warning(f"PDFParser: PyMuPDF open failed for {path}: {e}")
        return

    try:
        # Group formulas by page so we open each page once.
        by_page: dict[int, list[_DoclingFormula]] = {}
        for f in formulas:
            by_page.setdefault(f.page, []).append(f)

        for page_no, items in by_page.items():
            # docling pages are 1-based; PyMuPDF uses 0-based.
            page_idx = page_no - 1
            if not (0 <= page_idx < len(pdf)):
                continue
            page = pdf[page_idx]
            page_height = page.rect.height

            for f in items:
                if f.decoded_text:
                    # docling already decoded this one (rare at default
                    # settings, but if formula_enrichment was enabled
                    # in a future config it's possible). Skip.
                    continue

                l, t_bottom, r, b_bottom = f.bbox_bottom_left
                # Convert BOTTOMLEFT → TOPLEFT.
                # In BOTTOMLEFT, ``t`` is the higher y-value (top of
                # the box) and ``b`` is the lower y-value. PyMuPDF
                # rects use TOPLEFT where y increases downward, so the
                # top of the box gets the smaller y-coordinate after
                # flipping.
                top = page_height - max(t_bottom, b_bottom)
                bottom = page_height - min(t_bottom, b_bottom)
                # Padding so we catch superscripts / subscripts that
                # extend a bit past the docling bbox.
                rect = fitz.Rect(l - 1, top - 1, r + 1, bottom + 1)

                try:
                    text = page.get_text("text", clip=rect)
                except Exception as e:
                    logger.warning(
                        f"PDFParser: get_text failed for formula on "
                        f"page {page_no}: {e}"
                    )
                    continue

                cleaned = _clean_formula_text(text or "")
                if not cleaned:
                    continue

                # Pull a label out of the body if it ended with "(N)".
                label = None
                m = _TRAILING_EQ_LABEL_RE.search(cleaned)
                if m:
                    label = m.group(1)
                    cleaned = _TRAILING_EQ_LABEL_RE.sub("", cleaned).rstrip()
                m = _LEADING_EQ_LABEL_RE.search(cleaned)
                if not label and m:
                    label = m.group(1)
                    cleaned = _LEADING_EQ_LABEL_RE.sub("", cleaned).strip()

                f.decoded_text = cleaned
                f.label = label
    finally:
        pdf.close()


def _clean_formula_text(text: str) -> str:
    """Light cleanup of glyph-extracted formula text.

    PDF glyph extraction returns characters in spatial reading order but
    can introduce double spaces, hard line breaks, and stray markers
    (page numbers etc.). We collapse whitespace and strip lone digits
    that look like an equation label was already detected as a separate
    line by docling.
    """
    if not text:
        return ""
    # Normalise unicode whitespace
    text = (
        text.replace("\u00a0", " ")
        .replace("\u202f", " ")
        .replace("\u200b", "")
        .replace("\ufeff", "")
        .strip()
    )
    # Collapse runs of internal whitespace; preserve newlines that
    # separate display-formula lines.
    lines = [
        re.sub(r"\s+", " ", ln).strip()
        for ln in text.split("\n")
        if ln.strip()
    ]
    return "\n".join(lines)


def _splice_formulas_into_markdown(
    markdown: str,
    formulas: list[_DoclingFormula],
    out_parsed: list[ParsedFormula],
) -> str:
    """Replace every ``<!-- formula-not-decoded -->`` placeholder with a
    rendered formula block from the matching ``_DoclingFormula``.

    Docling emits the placeholders in document order, so we walk both
    lists in parallel. If a formula's bbox text couldn't be decoded, we
    drop in a graceful ``[Equation - không trích xuất được]`` placeholder
    so the user knows there was math here.
    """
    if not markdown:
        return markdown

    # Quick-exit when there are no markers at all.
    if _DOCLING_FORMULA_MARKER not in markdown:
        # Some docling versions may decode formulas into the markdown
        # directly. Surface them as ParsedFormula records anyway.
        for f in formulas:
            if f.decoded_text:
                out_parsed.append(
                    ParsedFormula(
                        text=f.decoded_text,
                        label=f.label,
                        kind="display",
                        page=f.page,
                    )
                )
        return markdown

    pieces = markdown.split(_DOCLING_FORMULA_MARKER)
    if len(pieces) - 1 != len(formulas):
        logger.info(
            f"PDFParser: marker count ({len(pieces) - 1}) doesn't match "
            f"formula items ({len(formulas)}); will pad/truncate"
        )

    out: list[str] = [pieces[0]]
    for idx, segment in enumerate(pieces[1:]):
        formula_render: str
        if idx < len(formulas):
            f = formulas[idx]
            if f.decoded_text:
                pf = ParsedFormula(
                    text=f.decoded_text,
                    label=f.label,
                    kind="display",
                    page=f.page,
                )
                out_parsed.append(pf)
                formula_render = pf.to_markdown()
            else:
                # Decoded text empty — keep a graceful placeholder so the
                # reader still knows there was math here. Don't add to
                # ``out_parsed`` because there's nothing to send to the
                # LLM.
                formula_render = (
                    f"[Equation page {f.page}]\n```formula\n"
                    "(không trích xuất được nội dung công thức)\n```"
                )
        else:
            # More markers than formulas — leave the original marker so
            # the caller can investigate.
            formula_render = _DOCLING_FORMULA_MARKER
        out.append(formula_render)
        out.append(segment)

    return "".join(out)


# ─── Tables ─────────────────────────────────────────────────────────────────


def _collect_tables(docling_doc) -> list[ParsedTable]:
    """Convert docling TableItems to our ``ParsedTable`` records.

    docling already inlines table markdown in ``export_to_markdown``;
    this list is the parallel structured representation that the
    AnalysisAgent picks up to render the tables in the final report.
    """
    parsed: list[ParsedTable] = []
    try:
        for item, _level in docling_doc.iterate_items():
            label = getattr(item, "label", None)
            label_str = (
                label.value if hasattr(label, "value") else str(label or "")
            ).lower()
            if label_str != "table":
                continue
            data = getattr(item, "data", None)
            if data is None:
                continue
            try:
                grid = data.grid  # list[list[TableCell]]
            except Exception:
                continue

            # Convert the grid into headers + rows. docling marks header
            # cells with ``column_header=True`` / ``row_header=True``;
            # we treat the FIRST row that contains any header cells as
            # the header row.
            if not grid:
                continue
            headers: list[str] = []
            rows: list[list[str]] = []
            header_row_idx: int | None = None
            for r_idx, row in enumerate(grid):
                if any(
                    getattr(cell, "column_header", False) for cell in row
                ):
                    headers = [_cell_text(cell) for cell in row]
                    header_row_idx = r_idx
                    break

            for r_idx, row in enumerate(grid):
                if r_idx == header_row_idx:
                    continue
                rows.append([_cell_text(cell) for cell in row])

            if not headers and rows:
                # No explicit headers — promote the first row.
                headers = rows[0]
                rows = rows[1:]

            page = None
            prov = getattr(item, "prov", None) or []
            if prov:
                page = getattr(prov[0], "page_no", None)

            title = None
            captions = getattr(item, "captions", None) or []
            if captions:
                first = captions[0]
                # ``captions`` carries TextItem refs in some versions or
                # plain strings in others. Resolve safely.
                if isinstance(first, str):
                    title = first
                else:
                    cap_text = getattr(first, "text", None)
                    if isinstance(cap_text, str):
                        title = cap_text

            tbl = ParsedTable(
                headers=headers, rows=rows, page=page, title=title
            )
            if not tbl.is_empty:
                parsed.append(tbl)
    except Exception as e:
        logger.warning(f"PDFParser: table collection failed: {e}")
    return parsed


def _cell_text(cell) -> str:
    text = getattr(cell, "text", None)
    if isinstance(text, str):
        return text.strip()
    return ""


# ─── Metadata + page count ──────────────────────────────────────────────────


def _read_pdf_metadata(path: Path) -> dict:
    """Pull title / author / page_count from the PDF info dict via PyMuPDF.

    docling does not currently expose this metadata. The original
    ingestion service relies on it for the document title fallback, so
    we read it here via PyMuPDF — the same library we already use for
    formula bbox extraction.
    """
    out: dict = {"title": None, "author": None, "page_count": None}
    try:
        with fitz.open(path) as doc:
            md = doc.metadata or {}
            title = (md.get("title") or "").strip() or None
            author = (md.get("author") or "").strip() or None
            out["title"] = title
            out["author"] = author
            out["page_count"] = doc.page_count
            out["raw"] = dict(md)
    except Exception as e:
        logger.warning(f"PDFParser: metadata read failed for {path}: {e}")
    return out


def _safe_page_count(docling_doc, fallback: int | None) -> int:
    n = getattr(docling_doc, "num_pages", None)
    try:
        if callable(n):
            n = n()
        n = int(n)
        if n > 0:
            return n
    except Exception:
        pass
    return fallback or 0
