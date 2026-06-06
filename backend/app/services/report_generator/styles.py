"""HTML / CSS theme for generated reports.

Single shared stylesheet so every report — regardless of report_type — looks
like part of the same product. Tuned to match the FE's slate / teal palette
so the in-browser preview blends with the rest of the app.

The HTML is fully self-contained (inline CSS) so it stays presentable when
exported / downloaded / emailed without any external assets.
"""

REPORT_CSS = """
:root {
    --color-text: #0f172a;
    --color-text-muted: #475569;
    --color-text-soft: #64748b;
    --color-border: #e2e8f0;
    --color-border-soft: #f1f5f9;
    --color-bg: #ffffff;
    --color-bg-soft: #f8fafc;
    --color-bg-muted: #f1f5f9;
    --color-accent: #0d9488;
    --color-accent-dark: #0f766e;
    --color-accent-soft: #ccfbf1;
    --color-success: #059669;
    --color-warn: #b45309;
    --color-danger: #b91c1c;
}

* { box-sizing: border-box; }

.report-root {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto,
                 "Helvetica Neue", Arial, sans-serif;
    color: var(--color-text);
    line-height: 1.7;
    font-size: 15px;
    background: var(--color-bg);
    max-width: 920px;
    margin: 0 auto;
    padding: 32px 40px 56px;
}

.report-root h1,
.report-root h2,
.report-root h3,
.report-root h4 {
    color: var(--color-text);
    line-height: 1.3;
    font-weight: 700;
    margin-top: 1.6em;
    margin-bottom: 0.6em;
}

.report-root h1 { font-size: 32px; margin-top: 0; }
.report-root h2 {
    font-size: 22px;
    padding-bottom: 8px;
    border-bottom: 2px solid var(--color-border);
}
.report-root h3 { font-size: 18px; color: var(--color-accent-dark); }
.report-root h4 { font-size: 16px; color: var(--color-text-muted); }

.report-root p { margin: 0 0 14px; }
.report-root ul, .report-root ol { margin: 0 0 14px; padding-left: 24px; }
.report-root li { margin-bottom: 6px; }

.report-root strong { color: var(--color-text); font-weight: 600; }
.report-root em { color: var(--color-text-muted); }

.report-cover {
    border-radius: 16px;
    padding: 36px 36px 30px;
    background: linear-gradient(135deg, #f8fafc 0%, #ecfeff 60%, #f0fdfa 100%);
    border: 1px solid var(--color-border);
    margin-bottom: 32px;
}
.report-cover .eyebrow {
    display: inline-block;
    font-size: 12px;
    font-weight: 700;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    color: var(--color-accent-dark);
    background: var(--color-accent-soft);
    padding: 4px 12px;
    border-radius: 999px;
    margin-bottom: 16px;
}
.report-cover h1 { font-size: 34px; margin: 0 0 14px; }
.report-cover .subtitle {
    color: var(--color-text-muted);
    font-size: 16px;
    margin: 0;
}
.report-cover .meta {
    display: flex;
    flex-wrap: wrap;
    gap: 18px;
    margin-top: 22px;
    padding-top: 18px;
    border-top: 1px solid var(--color-border);
}
.report-cover .meta-item { font-size: 13px; }
.report-cover .meta-item .label {
    display: block;
    font-size: 11px;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    color: var(--color-text-soft);
    margin-bottom: 2px;
}
.report-cover .meta-item .value {
    color: var(--color-text);
    font-weight: 600;
}

.report-section {
    margin: 28px 0;
}

.report-callout {
    border-left: 4px solid var(--color-accent);
    background: var(--color-bg-soft);
    padding: 16px 20px;
    border-radius: 0 10px 10px 0;
    margin: 18px 0;
    color: var(--color-text-muted);
}
.report-callout p:last-child { margin-bottom: 0; }

.report-finding-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
    gap: 14px;
    margin: 18px 0;
}
.report-finding {
    border: 1px solid var(--color-border);
    background: var(--color-bg);
    border-radius: 12px;
    padding: 16px 18px;
}
.report-finding .finding-num {
    display: inline-block;
    width: 26px;
    height: 26px;
    border-radius: 50%;
    background: var(--color-accent);
    color: #fff;
    text-align: center;
    line-height: 26px;
    font-size: 13px;
    font-weight: 700;
    margin-right: 10px;
}
.report-finding p { margin: 0; }

.report-doc-list {
    list-style: none;
    padding: 0;
    margin: 0;
}
.report-doc-list li {
    border: 1px solid var(--color-border);
    border-radius: 10px;
    padding: 14px 16px;
    margin-bottom: 10px;
    background: var(--color-bg);
}
.report-doc-list .doc-title {
    font-weight: 600;
    color: var(--color-text);
    margin-bottom: 4px;
}
.report-doc-list .doc-meta {
    color: var(--color-text-soft);
    font-size: 13px;
    /* Override the generic flex rule below — inside the literature
       review's doc list cards we want a plain inline flow with " · "
       separators between items. */
    display: block;
    margin: 0;
    gap: 0;
}
.report-doc-list .doc-summary {
    margin-top: 8px;
    color: var(--color-text-muted);
}

/* Inline meta row (loại tài liệu, source pill, link chip) shown under
   each section h3. Flex so chips wrap nicely on narrow screens. */
.doc-meta {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 6px;
    color: var(--color-text-soft);
    font-size: 13px;
    margin: 4px 0 14px;
}

.report-tag-row {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
    margin: 8px 0 16px;
}
.report-tag {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 5px 12px 5px 10px;
    border-radius: 10px;
    background: #fff;
    color: #6d28d9;
    border: 1px solid #ddd6fe;
    font-size: 13px;
    font-weight: 500;
    line-height: 1.3;
    transition: background-color 0.15s ease;
}
.report-tag:hover {
    background: #f5f3ff;
}
.report-tag .tag-icon {
    width: 12px;
    height: 12px;
    flex-shrink: 0;
    color: #8b5cf6;
}

.report-table {
    width: 100%;
    border-collapse: collapse;
    margin: 14px 0 18px;
    font-size: 14px;
    border: 1px solid var(--color-border);
    border-radius: 10px;
    overflow: hidden;
}
.report-table th,
.report-table td {
    padding: 10px 14px;
    text-align: left;
    border-bottom: 1px solid var(--color-border);
}
.report-table th {
    background: var(--color-bg-muted);
    color: var(--color-text);
    font-weight: 600;
    font-size: 13px;
    text-transform: uppercase;
    letter-spacing: 0.04em;
}
.report-table tr:last-child td { border-bottom: 0; }
.report-table tr:nth-child(even) td { background: var(--color-bg-soft); }

.report-pill {
    display: inline-block;
    padding: 2px 10px;
    border-radius: 999px;
    font-size: 12px;
    font-weight: 600;
    background: var(--color-bg-muted);
    color: var(--color-text-muted);
}
.report-pill.success { background: #d1fae5; color: var(--color-success); }
.report-pill.warn    { background: #fef3c7; color: var(--color-warn); }
.report-pill.danger  { background: #fee2e2; color: var(--color-danger); }
.report-pill.accent  { background: var(--color-accent-soft); color: var(--color-accent-dark); }

/* Source link chip — for "[link icon] Mở nguồn" affordance on doc cards
   and meta rows. Visually a pill with an icon + truncated URL host so
   the user can see at a glance where the document came from without
   the chip dominating the layout. */
.report-source-link {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 4px 10px 4px 8px;
    border-radius: 8px;
    background: #f0fdfa;
    color: #0f766e;
    border: 1px solid #99f6e4;
    font-size: 12px;
    font-weight: 600;
    line-height: 1.3;
    text-decoration: none;
    max-width: 100%;
    transition: background-color 0.15s ease, border-color 0.15s ease;
}
.report-source-link:hover {
    background: #ccfbf1;
    border-color: #5eead4;
}
.report-source-link .src-icon {
    width: 12px;
    height: 12px;
    flex-shrink: 0;
}
.report-source-link .src-host {
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    max-width: 240px;
}
.report-source-link .src-arrow {
    width: 11px;
    height: 11px;
    flex-shrink: 0;
    opacity: 0.7;
}

.report-toc {
    background: var(--color-bg-soft);
    border: 1px solid var(--color-border);
    border-radius: 12px;
    padding: 16px 22px;
    margin: 0 0 26px;
}
.report-toc h3 {
    margin: 0 0 8px;
    font-size: 14px;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    color: var(--color-text-soft);
}
.report-toc ol { margin: 0; padding-left: 22px; }
.report-toc li {
    color: var(--color-text-muted);
    margin-bottom: 4px;
}

.report-footer {
    margin-top: 48px;
    padding-top: 18px;
    border-top: 1px solid var(--color-border);
    color: var(--color-text-soft);
    font-size: 12px;
    text-align: center;
}

.report-empty {
    color: var(--color-text-soft);
    font-style: italic;
}
""".strip()


def wrap_html(title: str, body: str) -> str:
    """Wrap rendered body HTML in a self-contained document with inline CSS."""
    safe_title = (title or "Report").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    return f"""<!doctype html>
<html lang="vi">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width,initial-scale=1" />
<title>{safe_title}</title>
<style>{REPORT_CSS}</style>
</head>
<body>
<article class="report-root">
{body}
</article>
</body>
</html>
"""
