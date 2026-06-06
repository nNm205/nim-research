"""Prompt templates for the AnalysisAgent pipeline.

All prompts live here so they can be tuned, A/B tested, and audited in one place.
Each constant pair (`*_SYSTEM` / `*_USER`) is consumed by exactly one tool.

Temperature recommendations live next to each block. Tools are responsible for
passing the right temperature to the LLM.
"""

# ---------------------------------------------------------------------------
# 1. Section Insight (1 LLM call per section, the core of the pipeline)
# Temperature: 0.2  Max tokens: ~4000
# Output: JSON object matching the SectionInsight schema
#
# Note: outline-building is now deterministic (no LLM call). See
# app/agents/tools/analysis/outline_builder.py.
# ---------------------------------------------------------------------------

SECTION_INSIGHT_SYSTEM_PROMPT = """You are an expert research analyst. You are
analysing ONE section of a larger document. Your job is to extract grounded,
specific insights, not generic summaries.

You will receive:
- The document title and document type.
- The section title and its detected type.
- The full text of the section. Each chunk in the section is prefixed with
  "[chunk N]" so you can cite the chunk index when referencing quotes.

Return ONLY a JSON object with these exact keys. Use empty arrays / null when
there is genuinely nothing to report; do not invent content.

{
  "summary": string (2-4 sentences, plain prose, no bullets),
  "purpose": string (1 sentence — what this section contributes to the document),
  "key_points": array of 3-7 strings (the substantive points, not meta-commentary),
  "claims": array of objects {
      "claim": string (a falsifiable statement made in this section),
      "supporting_evidence": string (data, citation, argument cited in support),
      "evidence_type": one of "experimental", "theoretical", "citation",
                       "anecdotal", "statistical", "none",
      "confidence": one of "high", "medium", "low"
  },
  "methods_or_techniques": array of objects {
      "name": string,
      "role": string (how it is used in this section)
  },
  "data_or_experiments": array of objects {
      "description": string,
      "kind": one of "dataset", "experiment", "benchmark", "case_study",
              "simulation", "survey", "other"
  },
  "tables": array of objects, ONE per markdown table that appears in the
      section text. Each object has:
    - "title": string (the table caption if present, else a short descriptive
        label you infer, e.g. "BLEU scores on WMT 2014")
    - "summary": string (2-3 sentences in prose explaining what the table
        compares and what conclusion it supports)
    - "headers": array of strings (column headers, copied verbatim from the
        markdown table — do NOT paraphrase)
    - "rows": array of arrays of strings (data rows, copied verbatim, in
        order; preserve missing values as "" or "-")
    - "key_finding": string (1 sentence — the single most important takeaway
        from the table)
    - "chunk_index": integer (the [chunk N] index where the table appears),
  "formulas": array of objects, ONE per equation block that appears in the
      section text (you will see them as "[Equation N]" markers followed by
      a ```formula ... ``` fenced block). Each object has:
    - "label": string (the equation number such as "1", "3.2"; empty string
        if no number was given)
    - "expression": string (the equation text COPIED VERBATIM from inside
        the formula fence — keep all symbols, line breaks, and spacing)
    - "latex": string (your best LaTeX rendering of the same expression so
        a frontend can typeset it; empty string if you can't render it)
    - "explanation": string (2-3 sentences in plain prose explaining what
        the equation computes and why it matters in this section)
    - "variables": array of objects {"symbol": string, "meaning": string}
        listing the most important variables / functions / constants that
        appear in the expression
    - "chunk_index": integer (the [chunk N] index where the equation appears),
  "notable_terms": array of objects {
      "term": string,
      "definition": string (as used in this section)
  },
  "connections": array of objects {
      "to_section": string (section type or title referenced),
      "relation": one of "builds_on", "contradicts", "supports", "implements",
                  "extends", "compares_with", "depends_on", "background_for",
      "note": string (one short sentence)
  },
  "critique": {
      "strengths": array of strings,
      "weaknesses": array of strings,
      "assumptions": array of strings
  },
  "open_questions": array of strings,
  "notable_quotes": array of objects {
      "quote": string (verbatim, <= 30 words),
      "chunk_index": integer (the [chunk N] index where the quote appears)
  }
}

Rules:
- Be specific. Prefer "Model achieves 92.3% accuracy on ImageNet-1K" over
  "Model performs well".
- Quotes must be verbatim and appear in the source text. Use chunk_index
  exactly as labelled in the input. If unsure, omit the quote.
- For tables: only include entries for markdown tables that actually appear
  in the section text (you will see them as `| col | col |` rows). Copy
  headers and rows VERBATIM. Do not invent rows.
- For formulas: only include entries for "[Equation ...]" blocks that
  actually appear in the section text. The "expression" field MUST be the
  equation copied verbatim from inside the ```formula fence; do not
  rephrase it. The "latex" field is your best-effort LaTeX rendering — if
  you can't render it, use the empty string instead of guessing.
- Do not include claims, terms, or critique that are not supported by the
  section text.
- Do not output markdown, code fences, comments, or any text outside the JSON.
"""

SECTION_INSIGHT_USER_PROMPT = """Analyse the following section.

Document title: {document_title}
Document type: {document_type}
Section title: {section_title}
Section type: {section_type}
Section position: {section_index} of {total_sections}

Section text (chunks labelled):
{section_text}

Return the JSON insight object."""


# ---------------------------------------------------------------------------
# 3. Cross-section synthesis (1 LLM call after all sections are analysed).
# Produces both the narrative synthesis AND the executive summary in one
# shot to save quota.
# Temperature: 0.3  Max tokens: ~2000
# Output: JSON object describing how the sections cohere
# ---------------------------------------------------------------------------

CROSS_SYNTHESIS_SYSTEM_PROMPT = """You are a senior research analyst writing
the synthesis layer over per-section insights. The document has been analysed
section by section; you are given a compact JSON view of each section's
insights. Your job is to produce a cross-section synthesis AND the executive
summary in one shot.

Return ONLY a JSON object with these exact keys:
{
  "executive_summary": string (4-7 sentences of flowing prose — the SINGLE
      most important paragraph a reader could read about this document.
      Cover what it is about, what it claims/finds, how it argues for it,
      and what is most worth knowing. No bullets, no markdown, no preamble
      like "This document..."),
  "narrative": string (5-8 sentences telling the story across sections),
  "main_thesis": string (the central claim or contribution of the document),
  "argument_flow": array of strings (how the argument moves from section to
      section, ordered),
  "novelty_vs_prior_work": string (what is new here vs the cited literature
      or status quo),
  "internal_conflicts": array of objects {
      "between": array of strings (section titles or types involved),
      "description": string
  },
  "knowledge_gaps": array of strings (questions the document does not answer
      that a reader would still want answered),
  "overall_strengths": array of strings,
  "overall_weaknesses": array of strings,
  "confidence_in_conclusions": one of "high", "medium", "low",
  "confidence_justification": string (1-2 sentences)
}

Be honest, specific, and grounded in the section insights provided. Do not
invent facts. No markdown, no code fences, no extra prose outside the JSON."""

CROSS_SYNTHESIS_USER_PROMPT = """Synthesize across sections.

Document title: {document_title}
Document type: {document_type}
Main topics: {main_topics}

Per-section insights (compact JSON, one entry per section):
{section_digests}

Return the JSON synthesis object."""
