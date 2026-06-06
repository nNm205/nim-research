"""Report renderers — pure functions over a ``ReportContext``.

Each :func:`render_<type>` returns a ``(markdown, body_html)`` pair. The
caller wraps ``body_html`` in the shared theme via ``styles.wrap_html``.

Style guidelines:
- Markdown is CommonMark-only (no extensions). It must round-trip cleanly
  through every Markdown renderer.
- HTML is fully escaped on every interpolation. We never render
  user-provided strings as raw HTML.
- Sections degrade gracefully: when a field is empty we emit either
  nothing at all (preferred) or a localized ``"Chưa có dữ liệu"`` placeholder.
- All user-facing strings are Vietnamese to match the FE.
"""

from __future__ import annotations

import html as _html
from datetime import datetime
from typing import Iterable

from app.services.report_generator.aggregator import (
    DocumentBlock,
    ReportContext,
)
from app.utils.constants import ReportType


# ── Helpers ──────────────────────────────────────────────────────────────────


def _esc(value: str | None) -> str:
    """HTML-escape, treating ``None`` as empty."""
    if value is None:
        return ""
    return _html.escape(str(value), quote=True)


def _md_paragraph(text: str | None) -> str:
    if not text:
        return ""
    # Tighten internal newlines — analysis summaries occasionally contain
    # hard line breaks that screw with Markdown rendering.
    return " ".join(line.strip() for line in text.splitlines() if line.strip())


def _format_date_vi(value: datetime) -> str:
    return value.strftime("%d/%m/%Y %H:%M")


def _list_md(items: Iterable[str], *, ordered: bool = False) -> str:
    items = [i for i in items if i and i.strip()]
    if not items:
        return ""
    if ordered:
        return "\n".join(f"{idx}. {item}" for idx, item in enumerate(items, 1))
    return "\n".join(f"- {item}" for item in items)


def _list_html(items: Iterable[str], *, ordered: bool = False) -> str:
    items = [i for i in items if i and i.strip()]
    if not items:
        return ""
    tag = "ol" if ordered else "ul"
    rows = "\n".join(f"  <li>{_esc(i)}</li>" for i in items)
    return f"<{tag}>\n{rows}\n</{tag}>"


# Inline SVG icons — the report HTML is self-contained so we can't pull
# from lucide-react. These are the same shapes Lucide renders, written
# as SVG strings with currentColor so CSS can theme them.
_TAG_ICON_SVG = (
    '<svg class="tag-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" '
    'stroke-width="2" stroke-linecap="round" stroke-linejoin="round" '
    'aria-hidden="true">'
    '<path d="M12.586 2.586A2 2 0 0 0 11.172 2H4a2 2 0 0 0-2 2v7.172a2 2 0 0 0 .586 1.414l8.704 8.704a2.426 2.426 0 0 0 3.42 0l6.58-6.58a2.426 2.426 0 0 0 0-3.42z"/>'
    '<circle cx="7.5" cy="7.5" r=".5" fill="currentColor"/>'
    '</svg>'
)

_LINK_ICON_SVG = (
    '<svg class="src-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" '
    'stroke-width="2" stroke-linecap="round" stroke-linejoin="round" '
    'aria-hidden="true">'
    '<path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71"/>'
    '<path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71"/>'
    '</svg>'
)

_ARROW_OUT_ICON_SVG = (
    '<svg class="src-arrow" viewBox="0 0 24 24" fill="none" stroke="currentColor" '
    'stroke-width="2" stroke-linecap="round" stroke-linejoin="round" '
    'aria-hidden="true">'
    '<path d="M7 7h10v10"/><path d="M7 17 17 7"/>'
    '</svg>'
)


def _tag_row_html(items: Iterable[str]) -> str:
    items = [i for i in items if i and i.strip()]
    if not items:
        return ""
    pills = "".join(
        f'<span class="report-tag">{_TAG_ICON_SVG}{_esc(i)}</span>'
        for i in items
    )
    return f'<div class="report-tag-row">{pills}</div>'


def _source_host(url: str) -> str:
    """Extract a compact display label from a URL.

    Prefers the host (without ``www.``) so the chip stays narrow and
    scannable. Falls back to the full URL if parsing fails.
    """
    try:
        from urllib.parse import urlparse

        parsed = urlparse(url)
        host = (parsed.netloc or url).lower()
        if host.startswith("www."):
            host = host[4:]
        path = parsed.path or ""
        # Tack on a path hint when the host is too generic to identify
        # the source (e.g. github.com/user/repo, arxiv.org/abs/2401.0001).
        if host in {"arxiv.org", "github.com", "doi.org"} and path:
            return f"{host}{path[:32]}"
        return host or url
    except Exception:
        return url


def _source_link_html(url: str, *, label: str | None = None) -> str:
    """Render a styled "Mở nguồn" anchor — link icon + host + arrow."""
    if not url:
        return ""
    text = label or _source_host(url)
    return (
        f'<a class="report-source-link" href="{_esc(url)}" '
        f'target="_blank" rel="noopener noreferrer" '
        f'title="{_esc(url)}">'
        f"{_LINK_ICON_SVG}"
        f'<span class="src-host">{_esc(text)}</span>'
        f"{_ARROW_OUT_ICON_SVG}"
        "</a>"
    )


def _empty_md(label: str = "Chưa có dữ liệu") -> str:
    return f"_{label}_"


def _empty_html(label: str = "Chưa có dữ liệu") -> str:
    return f'<p class="report-empty">{_esc(label)}</p>'


def _doc_meta_html(doc: DocumentBlock) -> str:
    parts: list[str] = []
    if doc.source_type:
        parts.append(f'<span class="report-pill">{_esc(doc.source_type)}</span>')
    if doc.document_type:
        parts.append(
            f'<span class="report-pill accent">{_esc(doc.document_type)}</span>'
        )
    if not doc.has_analysis:
        parts.append(
            '<span class="report-pill warn">Chưa có phân tích</span>'
        )
    if doc.source_url:
        parts.append(_source_link_html(doc.source_url))
    if not parts:
        return ""
    # Each item lives in its own flex slot — no manual " · " separator
    # because the `.doc-meta` flex rule provides the spacing, and the
    # source-link chip already has its own visual border.
    return f'<div class="doc-meta">{"".join(parts)}</div>'


# ── Cover & TOC ──────────────────────────────────────────────────────────────


_REPORT_TYPE_LABEL_VI = {
    ReportType.RESEARCH_SUMMARY.value: "Tóm tắt nghiên cứu",
    ReportType.LITERATURE_REVIEW.value: "Tổng quan tài liệu",
    ReportType.DATA_ANALYSIS.value: "Phân tích dữ liệu",
    ReportType.CUSTOM.value: "Báo cáo tùy chỉnh",
}


def _cover_md(ctx: ReportContext) -> str:
    label = _REPORT_TYPE_LABEL_VI.get(ctx.report_type, ctx.report_type)
    n_total = ctx.total_documents
    n_analyzed = len(ctx.documents_with_analysis)

    lines = [f"# {ctx.report_title}", ""]
    lines.append(f"**Loại báo cáo**: {label}")
    if ctx.project_name:
        lines.append(f"**Dự án**: {ctx.project_name}")
    if ctx.project_topic:
        lines.append(f"**Chủ đề**: {ctx.project_topic}")
    lines.append(
        f"**Tài liệu tham gia**: {n_analyzed}/{n_total} đã phân tích"
    )
    lines.append(f"**Tạo lúc**: {_format_date_vi(ctx.generated_at)}")
    lines.append("")
    return "\n".join(lines)


def _cover_html(ctx: ReportContext) -> str:
    label = _REPORT_TYPE_LABEL_VI.get(ctx.report_type, ctx.report_type)
    n_total = ctx.total_documents
    n_analyzed = len(ctx.documents_with_analysis)

    subtitle_bits: list[str] = []
    if ctx.project_topic:
        subtitle_bits.append(_esc(ctx.project_topic))
    elif ctx.project_description:
        subtitle_bits.append(_esc(ctx.project_description))
    subtitle = (
        f'<p class="subtitle">{subtitle_bits[0]}</p>' if subtitle_bits else ""
    )

    return f"""
<header class="report-cover">
  <span class="eyebrow">{_esc(label)}</span>
  <h1>{_esc(ctx.report_title)}</h1>
  {subtitle}
  <div class="meta">
    <div class="meta-item">
      <span class="label">Dự án</span>
      <span class="value">{_esc(ctx.project_name)}</span>
    </div>
    <div class="meta-item">
      <span class="label">Tài liệu</span>
      <span class="value">{n_analyzed}/{n_total} đã phân tích</span>
    </div>
    <div class="meta-item">
      <span class="label">Tạo lúc</span>
      <span class="value">{_format_date_vi(ctx.generated_at)}</span>
    </div>
  </div>
</header>
""".strip()


def _toc_html(headings: list[str]) -> str:
    if not headings:
        return ""
    items = "\n".join(f"  <li>{_esc(h)}</li>" for h in headings)
    return f"""
<nav class="report-toc">
  <h3>Mục lục</h3>
  <ol>
{items}
  </ol>
</nav>
""".strip()


# ── Document block renderers ────────────────────────────────────────────────


def _render_doc_block_md(doc: DocumentBlock, *, depth: int = 3) -> str:
    """Produce a per-document section in Markdown."""
    h = "#" * depth
    out: list[str] = [f"{h} {doc.display_title}"]
    if doc.source_url:
        out.append(f"_Nguồn_: <{doc.source_url}>")
    if doc.document_type:
        out.append(f"_Loại tài liệu_: {doc.document_type}")
    out.append("")

    if not doc.has_analysis:
        out.append("> _Tài liệu này chưa có phân tích đầy đủ._")
        out.append("")
        return "\n".join(out)

    if doc.summary:
        out.append(_md_paragraph(doc.summary))
        out.append("")

    if doc.main_thesis:
        out.append(f"**Luận điểm chính**: {_md_paragraph(doc.main_thesis)}")
        out.append("")

    if doc.research_contribution:
        out.append(
            f"**Đóng góp**: {_md_paragraph(doc.research_contribution)}"
        )
        out.append("")

    if doc.key_findings:
        out.append("**Phát hiện chính**:")
        out.append(_list_md(doc.key_findings))
        out.append("")

    if doc.methodology:
        out.append("**Phương pháp**:")
        out.append(_md_paragraph(doc.methodology))
        out.append("")

    if doc.limitations:
        out.append("**Giới hạn**:")
        out.append(_list_md(doc.limitations))
        out.append("")

    if doc.keywords:
        out.append(f"**Từ khóa**: {', '.join(doc.keywords)}")
        out.append("")

    return "\n".join(out)


def _render_doc_block_html(doc: DocumentBlock) -> str:
    parts: list[str] = []
    parts.append(f"<h3>{_esc(doc.display_title)}</h3>")
    meta = _doc_meta_html(doc)
    if meta:
        parts.append(meta)

    if not doc.has_analysis:
        parts.append(
            '<p class="report-empty">'
            "Tài liệu này chưa có phân tích đầy đủ — hãy chạy "
            "<em>Analysis</em> để bổ sung dữ liệu vào báo cáo."
            "</p>"
        )
        return "\n".join(parts)

    if doc.summary:
        parts.append(f'<div class="report-callout"><p>{_esc(doc.summary)}</p></div>')

    if doc.main_thesis:
        parts.append(
            "<p><strong>Luận điểm chính:</strong> "
            f"{_esc(doc.main_thesis)}</p>"
        )

    if doc.research_contribution:
        parts.append(
            "<p><strong>Đóng góp:</strong> "
            f"{_esc(doc.research_contribution)}</p>"
        )

    if doc.key_findings:
        parts.append("<h4>Phát hiện chính</h4>")
        parts.append(_list_html(doc.key_findings))

    if doc.methodology:
        parts.append("<h4>Phương pháp</h4>")
        parts.append(f"<p>{_esc(doc.methodology)}</p>")

    if doc.limitations:
        parts.append("<h4>Giới hạn</h4>")
        parts.append(_list_html(doc.limitations))

    if doc.keywords:
        parts.append("<h4>Từ khóa</h4>")
        parts.append(_tag_row_html(doc.keywords))

    return "\n".join(parts)


# ── Per-report-type renderers ───────────────────────────────────────────────


def render_research_summary(ctx: ReportContext) -> tuple[str, str]:
    """Concise executive view of every analyzed document."""
    md: list[str] = [_cover_md(ctx)]
    html: list[str] = [_cover_html(ctx)]

    headings = ["Tóm tắt tổng quan", "Phát hiện nổi bật", "Tài liệu chi tiết"]
    if ctx.aggregate_research_questions:
        headings.insert(2, "Câu hỏi nghiên cứu")
    html.append(_toc_html(headings))

    # ── Tóm tắt tổng quan ─────────────────────────────────────────────────
    md.append("## Tóm tắt tổng quan")
    html.append('<section class="report-section"><h2>Tóm tắt tổng quan</h2>')

    if ctx.project_description or ctx.project_research_scope or ctx.project_topic:
        intro_md_parts: list[str] = []
        intro_html_parts: list[str] = []
        if ctx.project_topic:
            intro_md_parts.append(f"**Chủ đề**: {ctx.project_topic}")
            intro_html_parts.append(
                f"<p><strong>Chủ đề:</strong> {_esc(ctx.project_topic)}</p>"
            )
        if ctx.project_description:
            intro_md_parts.append(_md_paragraph(ctx.project_description))
            intro_html_parts.append(
                f"<p>{_esc(ctx.project_description)}</p>"
            )
        if ctx.project_research_scope:
            intro_md_parts.append(
                f"**Phạm vi nghiên cứu**: {_md_paragraph(ctx.project_research_scope)}"
            )
            intro_html_parts.append(
                "<p><strong>Phạm vi nghiên cứu:</strong> "
                f"{_esc(ctx.project_research_scope)}</p>"
            )
        md.append("\n\n".join(intro_md_parts))
        html.append("\n".join(intro_html_parts))

    n_analyzed = len(ctx.documents_with_analysis)
    n_total = ctx.total_documents
    summary_line = (
        f"Báo cáo tổng hợp dữ liệu từ **{n_analyzed} tài liệu đã phân tích** "
        f"trên tổng số {n_total} tài liệu thuộc dự án."
    )
    md.append(summary_line)
    html.append(
        f"<p>{summary_line.replace('**', '')}</p>".replace(
            f"{n_analyzed} tài liệu đã phân tích",
            f"<strong>{n_analyzed} tài liệu đã phân tích</strong>",
        )
    )

    if ctx.aggregate_keywords:
        md.append(f"\n**Từ khóa nổi bật**: {', '.join(ctx.aggregate_keywords[:15])}")
        html.append("<h3>Từ khóa nổi bật</h3>")
        html.append(_tag_row_html(ctx.aggregate_keywords[:15]))

    md.append("")
    html.append("</section>")

    # ── Phát hiện nổi bật ─────────────────────────────────────────────────
    md.append("## Phát hiện nổi bật")
    html.append('<section class="report-section"><h2>Phát hiện nổi bật</h2>')

    if ctx.aggregate_findings:
        md.append(_list_md(ctx.aggregate_findings, ordered=True))
        # HTML: render as a numbered grid for visual appeal
        finding_cards = "\n".join(
            f'<div class="report-finding">'
            f'<span class="finding-num">{idx}</span>'
            f"<p>{_esc(item)}</p></div>"
            for idx, item in enumerate(ctx.aggregate_findings, 1)
        )
        html.append(f'<div class="report-finding-grid">{finding_cards}</div>')
    else:
        md.append(_empty_md("Chưa có phát hiện nào được tổng hợp."))
        html.append(_empty_html("Chưa có phát hiện nào được tổng hợp."))
    md.append("")
    html.append("</section>")

    # ── Câu hỏi nghiên cứu ────────────────────────────────────────────────
    if ctx.aggregate_research_questions:
        md.append("## Câu hỏi nghiên cứu")
        md.append(_list_md(ctx.aggregate_research_questions))
        md.append("")
        html.append(
            '<section class="report-section">'
            "<h2>Câu hỏi nghiên cứu</h2>"
            f"{_list_html(ctx.aggregate_research_questions)}"
            "</section>"
        )

    # ── Tài liệu chi tiết ─────────────────────────────────────────────────
    md.append("## Tài liệu chi tiết")
    html.append('<section class="report-section"><h2>Tài liệu chi tiết</h2>')
    if ctx.documents:
        for doc in ctx.documents:
            md.append(_render_doc_block_md(doc, depth=3))
            html.append(_render_doc_block_html(doc))
    else:
        md.append(_empty_md("Dự án chưa có tài liệu nào."))
        html.append(_empty_html("Dự án chưa có tài liệu nào."))
    html.append("</section>")

    return "\n".join(md), "\n".join(html)


def render_literature_review(ctx: ReportContext) -> tuple[str, str]:
    """Critical synthesis across documents — emphasizes contributions, gaps,
    methodology comparison, and future work."""
    md: list[str] = [_cover_md(ctx)]
    html: list[str] = [_cover_html(ctx)]

    headings = [
        "Bối cảnh",
        "Phương pháp tổng hợp",
        "Tài liệu tham khảo",
        "Đóng góp và phát hiện",
        "So sánh phương pháp",
        "Khoảng trống và hướng tiếp theo",
    ]
    html.append(_toc_html(headings))

    # ── Bối cảnh ──────────────────────────────────────────────────────────
    md.append("## Bối cảnh")
    html.append('<section class="report-section"><h2>Bối cảnh</h2>')
    if ctx.project_topic:
        md.append(f"**Chủ đề**: {ctx.project_topic}")
        html.append(
            f"<p><strong>Chủ đề:</strong> {_esc(ctx.project_topic)}</p>"
        )
    if ctx.project_description:
        md.append(_md_paragraph(ctx.project_description))
        html.append(f"<p>{_esc(ctx.project_description)}</p>")
    if ctx.project_research_scope:
        md.append(
            f"**Phạm vi**: {_md_paragraph(ctx.project_research_scope)}"
        )
        html.append(
            "<p><strong>Phạm vi:</strong> "
            f"{_esc(ctx.project_research_scope)}</p>"
        )
    if not (ctx.project_topic or ctx.project_description):
        md.append(_empty_md("Chưa có mô tả dự án."))
        html.append(_empty_html("Chưa có mô tả dự án."))
    md.append("")
    html.append("</section>")

    # ── Phương pháp tổng hợp ───────────────────────────────────────────────
    md.append("## Phương pháp tổng hợp")
    html.append('<section class="report-section"><h2>Phương pháp tổng hợp</h2>')
    n_total = ctx.total_documents
    n_analyzed = len(ctx.documents_with_analysis)
    methodology_intro = (
        f"Báo cáo tổng hợp dữ liệu từ {n_analyzed}/{n_total} tài liệu "
        f"đã được phân tích bằng pipeline section-grounded của hệ thống. "
        f"Mỗi tài liệu được trích xuất theo các trường: tóm tắt, luận điểm "
        f"chính, phương pháp, đóng góp, giới hạn, và hướng nghiên cứu tiếp theo."
    )
    md.append(methodology_intro)
    html.append(f"<p>{_esc(methodology_intro)}</p>")
    md.append("")
    html.append("</section>")

    # ── Tài liệu tham khảo ────────────────────────────────────────────────
    md.append("## Tài liệu tham khảo")
    html.append('<section class="report-section"><h2>Tài liệu tham khảo</h2>')
    if ctx.documents:
        # Markdown: numbered list with title + URL
        md.append(
            _list_md(
                [
                    f"**{d.display_title}**"
                    + (f" — <{d.source_url}>" if d.source_url else "")
                    + (
                        f" _(loại: {d.document_type})_"
                        if d.document_type
                        else ""
                    )
                    for d in ctx.documents
                ],
                ordered=True,
            )
        )
        # HTML: rich card list
        cards: list[str] = []
        for idx, d in enumerate(ctx.documents, 1):
            inner = [f'<div class="doc-title">{idx}. {_esc(d.display_title)}</div>']
            meta_bits: list[str] = []
            if d.document_type:
                meta_bits.append(f"Loại: {_esc(d.document_type)}")
            if d.source_url:
                meta_bits.append(_source_link_html(d.source_url))
            if not d.has_analysis:
                meta_bits.append(
                    '<span class="report-pill warn">Chưa có phân tích</span>'
                )
            if meta_bits:
                inner.append(
                    f'<div class="doc-meta">{" · ".join(meta_bits)}</div>'
                )
            if d.summary:
                inner.append(f'<div class="doc-summary">{_esc(d.summary)}</div>')
            cards.append("<li>" + "\n".join(inner) + "</li>")
        html.append(f'<ul class="report-doc-list">{"".join(cards)}</ul>')
    else:
        md.append(_empty_md("Chưa có tài liệu nào."))
        html.append(_empty_html("Chưa có tài liệu nào."))
    md.append("")
    html.append("</section>")

    # ── Đóng góp và phát hiện ─────────────────────────────────────────────
    md.append("## Đóng góp và phát hiện")
    html.append(
        '<section class="report-section"><h2>Đóng góp và phát hiện</h2>'
    )
    contributions = [
        (d.display_title, d.research_contribution or d.main_thesis)
        for d in ctx.documents_with_analysis
        if (d.research_contribution or d.main_thesis)
    ]
    if contributions:
        md.append(
            _list_md(
                [f"**{title}**: {contrib}" for title, contrib in contributions]
            )
        )
        rows = "\n".join(
            "<tr>"
            f"<td><strong>{_esc(title)}</strong></td>"
            f"<td>{_esc(contrib)}</td>"
            "</tr>"
            for title, contrib in contributions
        )
        html.append(
            '<table class="report-table">'
            "<thead><tr><th>Tài liệu</th><th>Đóng góp / Luận điểm</th></tr></thead>"
            f"<tbody>{rows}</tbody></table>"
        )
    elif ctx.aggregate_findings:
        md.append(_list_md(ctx.aggregate_findings))
        html.append(_list_html(ctx.aggregate_findings))
    else:
        md.append(_empty_md())
        html.append(_empty_html())
    md.append("")
    html.append("</section>")

    # ── So sánh phương pháp ────────────────────────────────────────────────
    md.append("## So sánh phương pháp")
    html.append('<section class="report-section"><h2>So sánh phương pháp</h2>')
    if ctx.aggregate_methodologies:
        md.append(_list_md(ctx.aggregate_methodologies))
        html.append(_list_html(ctx.aggregate_methodologies))
    else:
        md.append(_empty_md("Các tài liệu chưa có thông tin phương pháp."))
        html.append(_empty_html("Các tài liệu chưa có thông tin phương pháp."))
    md.append("")
    html.append("</section>")

    # ── Khoảng trống và hướng tiếp theo ────────────────────────────────────
    md.append("## Khoảng trống và hướng tiếp theo")
    html.append(
        '<section class="report-section">'
        "<h2>Khoảng trống và hướng tiếp theo</h2>"
    )
    md.append("### Giới hạn quan sát được")
    html.append("<h3>Giới hạn quan sát được</h3>")
    if ctx.aggregate_limitations:
        md.append(_list_md(ctx.aggregate_limitations))
        html.append(_list_html(ctx.aggregate_limitations))
    else:
        md.append(_empty_md())
        html.append(_empty_html())

    md.append("")
    md.append("### Hướng nghiên cứu đề xuất")
    html.append("<h3>Hướng nghiên cứu đề xuất</h3>")
    if ctx.aggregate_future_work:
        md.append(_list_md(ctx.aggregate_future_work))
        html.append(_list_html(ctx.aggregate_future_work))
    else:
        md.append(_empty_md())
        html.append(_empty_html())
    md.append("")
    html.append("</section>")

    return "\n".join(md), "\n".join(html)


def render_data_analysis(ctx: ReportContext) -> tuple[str, str]:
    """Dataset / experiment-flavored report — emphasizes findings, methods,
    and a quick coverage table."""
    md: list[str] = [_cover_md(ctx)]
    html: list[str] = [_cover_html(ctx)]

    headings = [
        "Phạm vi phân tích",
        "Bảng tổng quan dữ liệu",
        "Kết quả tổng hợp",
        "Phân tích chi tiết theo tài liệu",
    ]
    html.append(_toc_html(headings))

    # ── Phạm vi phân tích ──────────────────────────────────────────────────
    md.append("## Phạm vi phân tích")
    html.append('<section class="report-section"><h2>Phạm vi phân tích</h2>')
    if ctx.project_research_scope or ctx.project_description:
        scope_text = ctx.project_research_scope or ctx.project_description
        md.append(_md_paragraph(scope_text))
        html.append(f"<p>{_esc(scope_text)}</p>")
    md.append(
        f"- Tổng số tài liệu: **{ctx.total_documents}**\n"
        f"- Số tài liệu đã phân tích: **{len(ctx.documents_with_analysis)}**"
    )
    html.append(
        "<ul>"
        f"<li>Tổng số tài liệu: <strong>{ctx.total_documents}</strong></li>"
        f"<li>Số tài liệu đã phân tích: "
        f"<strong>{len(ctx.documents_with_analysis)}</strong></li>"
        "</ul>"
    )
    md.append("")
    html.append("</section>")

    # ── Bảng tổng quan dữ liệu ────────────────────────────────────────────
    md.append("## Bảng tổng quan dữ liệu")
    html.append(
        '<section class="report-section"><h2>Bảng tổng quan dữ liệu</h2>'
    )
    if ctx.documents:
        # Markdown table
        md.append(
            "| # | Tài liệu | Loại | Số phần | Phát hiện | Trạng thái |"
        )
        md.append("|---|---|---|---|---|---|")
        for idx, d in enumerate(ctx.documents, 1):
            # Markdown tables use ``|`` as a column separator — escape any
            # ``|`` that appears inside a doc title.
            safe_title = (d.display_title or "").replace("|", r"\|")
            doc_type_md = d.document_type or "—"
            section_md = d.section_count or "—"
            findings_md = len(d.key_findings) or "—"
            status_md = "Đã phân tích" if d.has_analysis else "Chưa phân tích"
            md.append(
                f"| {idx} | {safe_title} | {doc_type_md} | "
                f"{section_md} | {findings_md} | {status_md} |"
            )
        # HTML table
        rows = []
        for idx, d in enumerate(ctx.documents, 1):
            status_pill = (
                '<span class="report-pill success">Đã phân tích</span>'
                if d.has_analysis
                else '<span class="report-pill warn">Chưa phân tích</span>'
            )
            rows.append(
                "<tr>"
                f"<td>{idx}</td>"
                f"<td><strong>{_esc(d.display_title)}</strong></td>"
                f"<td>{_esc(d.document_type) or '—'}</td>"
                f"<td>{d.section_count or '—'}</td>"
                f"<td>{len(d.key_findings) or '—'}</td>"
                f"<td>{status_pill}</td>"
                "</tr>"
            )
        html.append(
            '<table class="report-table">'
            "<thead><tr>"
            "<th>#</th><th>Tài liệu</th><th>Loại</th>"
            "<th>Số phần</th><th>Phát hiện</th><th>Trạng thái</th>"
            "</tr></thead>"
            f"<tbody>{''.join(rows)}</tbody>"
            "</table>"
        )
    else:
        md.append(_empty_md())
        html.append(_empty_html())
    md.append("")
    html.append("</section>")

    # ── Kết quả tổng hợp ──────────────────────────────────────────────────
    md.append("## Kết quả tổng hợp")
    html.append('<section class="report-section"><h2>Kết quả tổng hợp</h2>')
    md.append("### Phát hiện chính")
    html.append("<h3>Phát hiện chính</h3>")
    if ctx.aggregate_findings:
        md.append(_list_md(ctx.aggregate_findings, ordered=True))
        html.append(_list_html(ctx.aggregate_findings, ordered=True))
    else:
        md.append(_empty_md())
        html.append(_empty_html())

    if ctx.aggregate_keywords:
        md.append("")
        md.append("### Từ khóa nổi bật")
        md.append(", ".join(ctx.aggregate_keywords[:20]))
        html.append("<h3>Từ khóa nổi bật</h3>")
        html.append(_tag_row_html(ctx.aggregate_keywords[:20]))

    if ctx.aggregate_limitations:
        md.append("")
        md.append("### Cảnh báo về dữ liệu")
        md.append(_list_md(ctx.aggregate_limitations))
        html.append("<h3>Cảnh báo về dữ liệu</h3>")
        html.append(_list_html(ctx.aggregate_limitations))
    md.append("")
    html.append("</section>")

    # ── Phân tích chi tiết ────────────────────────────────────────────────
    md.append("## Phân tích chi tiết theo tài liệu")
    html.append(
        '<section class="report-section">'
        "<h2>Phân tích chi tiết theo tài liệu</h2>"
    )
    if ctx.documents_with_analysis:
        for doc in ctx.documents_with_analysis:
            md.append(_render_doc_block_md(doc, depth=3))
            html.append(_render_doc_block_html(doc))
    else:
        md.append(_empty_md("Chưa có tài liệu nào hoàn tất phân tích."))
        html.append(_empty_html("Chưa có tài liệu nào hoàn tất phân tích."))
    html.append("</section>")

    return "\n".join(md), "\n".join(html)


def render_custom(ctx: ReportContext) -> tuple[str, str]:
    """Generic / fallback renderer — readable skeleton the user can edit."""
    md: list[str] = [_cover_md(ctx)]
    html: list[str] = [_cover_html(ctx)]

    md.append("## Mở đầu")
    html.append(
        '<section class="report-section"><h2>Mở đầu</h2>'
        "<p>Đây là báo cáo tùy chỉnh được tạo tự động từ dữ liệu dự án. "
        "Bạn có thể chỉnh sửa nội dung dưới đây cho phù hợp với mục đích "
        "trình bày.</p></section>"
    )
    md.append(
        "Đây là báo cáo tùy chỉnh được tạo tự động từ dữ liệu dự án. "
        "Bạn có thể chỉnh sửa nội dung dưới đây cho phù hợp với mục đích "
        "trình bày."
    )
    md.append("")

    if ctx.project_description:
        md.append("## Mô tả dự án")
        md.append(_md_paragraph(ctx.project_description))
        md.append("")
        html.append(
            '<section class="report-section">'
            "<h2>Mô tả dự án</h2>"
            f"<p>{_esc(ctx.project_description)}</p>"
            "</section>"
        )

    md.append("## Tài liệu trong báo cáo")
    html.append(
        '<section class="report-section"><h2>Tài liệu trong báo cáo</h2>'
    )
    if ctx.documents:
        for doc in ctx.documents:
            md.append(_render_doc_block_md(doc, depth=3))
            html.append(_render_doc_block_html(doc))
    else:
        md.append(_empty_md())
        html.append(_empty_html())
    html.append("</section>")

    if ctx.aggregate_findings:
        md.append("## Tổng kết phát hiện")
        md.append(_list_md(ctx.aggregate_findings))
        md.append("")
        html.append(
            '<section class="report-section">'
            "<h2>Tổng kết phát hiện</h2>"
            f"{_list_html(ctx.aggregate_findings)}"
            "</section>"
        )

    return "\n".join(md), "\n".join(html)


# ── Dispatch ────────────────────────────────────────────────────────────────


_RENDERERS = {
    ReportType.RESEARCH_SUMMARY.value: render_research_summary,
    ReportType.LITERATURE_REVIEW.value: render_literature_review,
    ReportType.DATA_ANALYSIS.value: render_data_analysis,
    ReportType.CUSTOM.value: render_custom,
}


def render(ctx: ReportContext) -> tuple[str, str]:
    """Dispatch to the renderer for ``ctx.report_type``.

    Falls back to the custom renderer for unknown report types so the
    pipeline never raises on legacy / future enum values.
    """
    renderer = _RENDERERS.get(ctx.report_type, render_custom)
    body_md, body_html = renderer(ctx)

    # Append a small footer to the HTML body. Markdown stays footer-free
    # so it remains a clean source for further editing.
    body_html += (
        '\n<footer class="report-footer">'
        f"Tạo lúc {_format_date_vi(ctx.generated_at)} bằng hệ thống "
        "Research Assistant"
        "</footer>"
    )
    return body_md, body_html
