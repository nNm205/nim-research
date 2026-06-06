"""Deterministic report generator.

Aggregates data from Documents + DocumentAnalysis (already produced by the
AnalysisAgent pipeline) into a polished, professional report. NO LLM calls
are made here — everything is rule-based composition over the structured
fields the analysis pipeline already extracted (executive_summary, claims,
methodology, key_findings, narrative_synthesis, ...).

Why deterministic:

- It's free — the AnalysisAgent already paid the LLM cost upstream.
- It's reproducible — regenerating a report twice yields the same output.
- It's fast — a typical project with 5-10 analyses generates in < 100 ms.

The generator produces both Markdown (for storage / .md export) and
styled HTML (for in-browser viewing and .html / .docx export). HTML
rendering uses a shared professional theme defined in ``styles.py``.

Public entry point: :func:`generate_report_content`.
"""

from app.services.report_generator.generator import generate_report_content

__all__ = ["generate_report_content"]
