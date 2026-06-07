"""ReportComposerTool — combine outline + narrative + summary + citations.

Pure deterministic composition. Produces ``(markdown, html)`` in the same
shape as the existing ``app.services.report_generator`` so the FE renders
both report flavours identically.

We reuse the report_generator's ``styles.wrap_html`` for consistent CSS.
"""

from __future__ import annotations

import html as _html
import re
from datetime import datetime
from typing import Iterable

from app.agents.tools.synthesis.context_loader import SynthesisContext
from app.services.report_generator.styles import wrap_html


# Inline citation regex matching `[n]` / `[n, m]`. We linkify these in the
# rendered HTML to anchors pointing at the references list.
_CITATION_RE = re.compile(r"\[(\d+(?:\s*,\s*\d+)*)\]")


def _esc(value: str | None) -> str:
    if value is None:
        return ""
    return _html.escape(str(value), quote=True)


def _topic_chips_html(topic_string: str | None) -> str:
    """Render a comma-separated topic string as a violet chip row matching
    the ProjectCard chip pattern. Returns empty string when no chips."""
    if not topic_string:
        return ""
    chips = [t.strip() for t in topic_string.split(",") if t.strip()]
    if not chips:
        return ""
    pills = "".join(
        f'<span class="report-tag">{_esc(t)}</span>' for t in chips
    )
    return f'<div class="report-tag-row cover-topics">{pills}</div>'


def _format_date_vi(value: datetime) -> str:
    return value.strftime("%d/%m/%Y %H:%M")


def _linkify_citations_html(body_html: str, valid_indices: set[int]) -> str:
    """Replace every `[n]` with a small superscript anchor."""
    def repl(m: re.Match) -> str:
        nums = [s.strip() for s in m.group(1).split(",")]
        anchors: list[str] = []
        for n in nums:
            try:
                n_int = int(n)
            except ValueError:
                continue
            if n_int not in valid_indices:
                continue
            anchors.append(
                f'<a href="#ref-{n_int}" class="report-citation">[{n_int}]</a>'
            )
        return "".join(anchors) if anchors else m.group(0)
    return _CITATION_RE.sub(repl, body_html)


def _paragraphs_html(body: str) -> str:
    """Convert plain prose with blank-line paragraphs to <p>...</p>."""
    parts = [p.strip() for p in re.split(r"\n\s*\n", body) if p.strip()]
    return "\n".join(f"<p>{_esc(p)}</p>" for p in parts)


def _paragraphs_html_keep_brackets(body: str) -> str:
    """Same as _paragraphs_html but escapes everything except `[n]` markers
    which we'll later linkify into <a> anchors."""
    parts = [p.strip() for p in re.split(r"\n\s*\n", body) if p.strip()]
    safe_parts: list[str] = []
    for p in parts:
        # Replace each [n] with a unique placeholder before HTML-escaping
        placeholders: list[str] = []
        def stash(m: re.Match) -> str:
            placeholders.append(m.group(0))
            return f"\x00CIT{len(placeholders) - 1}\x00"
        replaced = _CITATION_RE.sub(stash, p)
        escaped = _html.escape(replaced, quote=True)
        # Restore citations
        for idx, original in enumerate(placeholders):
            escaped = escaped.replace(f"\x00CIT{idx}\x00", original)
        safe_parts.append(f"<p>{escaped}</p>")
    return "\n".join(safe_parts)


class ReportComposerTool:
    """Compose markdown + HTML for a synthesised report."""

    def compose(
        self,
        context: SynthesisContext,
        outline: dict,
        narrative: dict,
        summary: dict,
        citations: dict,
        *,
        provider: str | None = None,
        model: str | None = None,
    ) -> tuple[str, str]:
        generated_at = datetime.utcnow()

        sections = outline.get("sections") or []
        narrative_sections = (narrative or {}).get("sections") or {}

        # Markdown
        md_lines: list[str] = []
        md_lines.append(f"# {outline.get('title') or context.report_title}")
        md_lines.append("")
        md_lines.append(self._meta_md(context, generated_at, provider, model))
        md_lines.append("")

        if summary.get("executive_summary"):
            md_lines.append("## Tóm tắt")
            md_lines.append(summary["executive_summary"])
            md_lines.append("")
            if summary.get("key_takeaways"):
                md_lines.append("**Điểm nổi bật:**")
                for t in summary["key_takeaways"]:
                    md_lines.append(f"- {t}")
                md_lines.append("")

        if outline.get("thesis"):
            md_lines.append("## Luận điểm chính")
            md_lines.append(outline["thesis"])
            md_lines.append("")

        for s in sections:
            md_lines.append(f"## {s['title']}")
            entry = narrative_sections.get(s["key"])
            body = (entry or {}).get("body") or ""
            if body:
                md_lines.append(body)
            else:
                md_lines.append("_Phần này hiện chưa có nội dung._")
            md_lines.append("")

        if citations.get("entries"):
            md_lines.append("## Tài liệu tham khảo")
            md_lines.append(citations["apa_text"])
            md_lines.append("")
            md_lines.append("### BibTeX")
            md_lines.append("```bibtex")
            md_lines.append(citations["bibtex_text"])
            md_lines.append("```")
            md_lines.append("")

        markdown = "\n".join(md_lines).strip() + "\n"

        # HTML
        html_parts: list[str] = []
        html_parts.append(self._cover_html(context, outline, generated_at, provider, model))

        toc_titles = [s["title"] for s in sections]
        if summary.get("executive_summary"):
            toc_titles = ["Tóm tắt"] + toc_titles
        if citations.get("entries"):
            toc_titles = toc_titles + ["Tài liệu tham khảo"]
        if toc_titles:
            items = "\n".join(f"  <li>{_esc(t)}</li>" for t in toc_titles)
            html_parts.append(
                '<nav class="report-toc">'
                "<h3>Mục lục</h3>"
                f"<ol>\n{items}\n</ol>"
                "</nav>"
            )

        if summary.get("executive_summary"):
            html_parts.append('<section class="report-section">')
            html_parts.append("<h2>Tóm tắt</h2>")
            html_parts.append(
                f'<div class="report-callout">'
                f"<p>{_esc(summary['executive_summary'])}</p>"
                "</div>"
            )
            if summary.get("key_takeaways"):
                html_parts.append("<h3>Điểm nổi bật</h3>")
                items = "\n".join(
                    f"  <li>{_esc(t)}</li>" for t in summary["key_takeaways"]
                )
                html_parts.append(f"<ul>\n{items}\n</ul>")
            html_parts.append("</section>")

        if outline.get("thesis"):
            html_parts.append(
                '<section class="report-section">'
                "<h2>Luận điểm chính</h2>"
                f"<p>{_esc(outline['thesis'])}</p>"
                "</section>"
            )

        valid_indices = {d.index for d in context.documents}

        for s in sections:
            entry = narrative_sections.get(s["key"]) or {}
            body = entry.get("body") or ""
            html_parts.append('<section class="report-section">')
            html_parts.append(f"<h2>{_esc(s['title'])}</h2>")
            if s.get("purpose"):
                html_parts.append(
                    f'<p class="report-section-purpose">'
                    f"<em>{_esc(s['purpose'])}</em></p>"
                )
            if body:
                body_html = _paragraphs_html_keep_brackets(body)
                body_html = _linkify_citations_html(body_html, valid_indices)
                html_parts.append(body_html)
            else:
                html_parts.append(
                    '<p class="report-empty">Phần này hiện chưa có nội dung.</p>'
                )
            html_parts.append("</section>")

        if citations.get("entries"):
            html_parts.append('<section class="report-section">')
            html_parts.append("<h2>Tài liệu tham khảo</h2>")
            html_parts.append('<ol class="report-references">')
            for e in citations["entries"]:
                url_html = ""
                if e.get("doi"):
                    url_html = (
                        f' <a href="https://doi.org/{_esc(e["doi"])}" '
                        f'target="_blank" rel="noopener noreferrer">'
                        f'[doi]</a>'
                    )
                elif e.get("url"):
                    url_html = (
                        f' <a href="{_esc(e["url"])}" '
                        f'target="_blank" rel="noopener noreferrer">'
                        f'[link]</a>'
                    )
                html_parts.append(
                    f'<li id="ref-{e["index"]}" value="{e["index"]}">'
                    f"{_esc(e['apa'])}{url_html}"
                    "</li>"
                )
            html_parts.append("</ol>")

            html_parts.append("<h3>BibTeX</h3>")
            html_parts.append(
                f'<pre class="report-bibtex"><code>'
                f"{_esc(citations['bibtex_text'])}"
                "</code></pre>"
            )
            html_parts.append("</section>")

        body_html = "\n".join(html_parts)
        full_html = wrap_html(
            outline.get("title") or context.report_title or "Báo cáo",
            body_html,
        )
        # Inject extra CSS the synthesis-only renderers need (citation
        # superscript + reference list). We prepend a <style> tag inside
        # the existing wrapper.
        full_html = full_html.replace(
            "</style>", _EXTRA_CSS + "\n</style>", 1
        )
        return markdown, full_html

    # ── Helpers ──────────────────────────────────────────────────────────

    def _meta_md(
        self,
        context: SynthesisContext,
        generated_at: datetime,
        provider: str | None,
        model: str | None,
    ) -> str:
        n_total = len(context.documents)
        n_analyzed = len(context.documents_with_analysis)
        lines = [
            f"**Dự án**: {context.project_name}",
            f"**Tài liệu**: {n_analyzed}/{n_total} đã phân tích",
            f"**Tạo lúc**: {_format_date_vi(generated_at)}",
        ]
        if provider:
            lines.append(f"**LLM**: {provider}:{model or '?'}")
        return "  \n".join(lines)

    def _cover_html(
        self,
        context: SynthesisContext,
        outline: dict,
        generated_at: datetime,
        provider: str | None,
        model: str | None,
    ) -> str:
        n_total = len(context.documents)
        n_analyzed = len(context.documents_with_analysis)
        title = outline.get("title") or context.report_title or "Báo cáo"

        # Cover subtitle: prefer the LLM-generated thesis (it's a single
        # narrative sentence), fall back to the project topic which lives
        # as a comma-joined string and is rendered as chips matching the
        # ProjectCard pattern. Description is prose, so it stays as <p>.
        thesis = outline.get("thesis")
        if thesis:
            subtitle_html = f'<p class="subtitle">{_esc(thesis)}</p>'
        elif context.project_topic:
            subtitle_html = _topic_chips_html(context.project_topic)
        elif context.project_description:
            subtitle_html = (
                f'<p class="subtitle">{_esc(context.project_description)}</p>'
            )
        else:
            subtitle_html = ""

        provider_html = ""
        if provider:
            provider_html = (
                '<div class="meta-item">'
                f'<span class="label">LLM</span>'
                f'<span class="value">{_esc(provider)}:{_esc(model or "?")}</span>'
                "</div>"
            )
        return f"""
<header class="report-cover">
  <span class="eyebrow">Báo cáo tổng hợp</span>
  <h1>{_esc(title)}</h1>
  {subtitle_html}
  <div class="meta">
    <div class="meta-item">
      <span class="label">Dự án</span>
      <span class="value">{_esc(context.project_name)}</span>
    </div>
    <div class="meta-item">
      <span class="label">Tài liệu</span>
      <span class="value">{n_analyzed}/{n_total} đã phân tích</span>
    </div>
    <div class="meta-item">
      <span class="label">Tạo lúc</span>
      <span class="value">{_format_date_vi(generated_at)}</span>
    </div>
    {provider_html}
  </div>
</header>
""".strip()


def collect_narrative_text(narrative: dict, sections: Iterable[dict]) -> str:
    """Concatenate every section body for the executive-summary call."""
    parts: list[str] = []
    sections_map = (narrative or {}).get("sections") or {}
    for s in sections:
        entry = sections_map.get(s["key"]) or {}
        body = entry.get("body")
        if isinstance(body, str) and body.strip():
            parts.append(body.strip())
    return "\n\n".join(parts)


_EXTRA_CSS = """
.report-citation {
    color: var(--color-accent-dark);
    text-decoration: none;
    font-weight: 600;
    font-size: 0.85em;
    vertical-align: super;
    line-height: 1;
    padding: 0 1px;
}
.report-citation:hover { text-decoration: underline; }

.report-section-purpose {
    color: var(--color-text-soft);
    font-size: 13px;
    margin-top: -8px;
    margin-bottom: 14px;
}

.report-references {
    padding-left: 24px;
    margin: 12px 0;
}
.report-references li {
    margin-bottom: 8px;
    color: var(--color-text-muted);
    font-size: 14px;
}
.report-references li a {
    color: var(--color-accent-dark);
    text-decoration: none;
    margin-left: 4px;
}
.report-references li a:hover { text-decoration: underline; }

.report-bibtex {
    background: var(--color-bg-soft);
    border: 1px solid var(--color-border);
    border-radius: 8px;
    padding: 12px 14px;
    overflow-x: auto;
    font-size: 12.5px;
    line-height: 1.5;
    color: var(--color-text);
}
"""
