"""Robust JSON parsing for LLM output.

LLMs frequently wrap JSON in code fences, prepend commentary, append a
trailing period or comma, or output near-JSON with single quotes / Python
`True/False/None`. We try strict parsing first, then progressively looser
fallbacks. We never raise — failures return None so callers can degrade
gracefully.
"""

from __future__ import annotations

import json
import re

from app.utils.logger import logger


_TRAILING_COMMA_RE = re.compile(r",(\s*[\]}])")


def parse_llm_json(raw_response: str) -> dict | list | None:
    """Parse JSON from an LLM response with several fallback strategies."""
    if not raw_response:
        return None

    text = raw_response.strip()

    # Strategy 1: strict JSON
    parsed = _try_loads(text)
    if parsed is not None:
        return parsed

    # Strategy 2: extract from a code fence (```json ... ``` or ``` ... ```)
    fence = re.search(r"```(?:json|JSON)?\s*([\s\S]*?)```", text)
    if fence:
        parsed = _try_loads(fence.group(1).strip())
        if parsed is not None:
            return parsed

    # Strategy 3: cut to the first {...} or [...] block, balancing braces
    block = _extract_balanced_json(text)
    if block is not None:
        parsed = _try_loads(block)
        if parsed is not None:
            return parsed

    # Strategy 4: clean common artifacts and retry on whatever survived
    cleaned = _sanitize(text)
    parsed = _try_loads(cleaned)
    if parsed is not None:
        return parsed

    block = _extract_balanced_json(cleaned)
    if block is not None:
        parsed = _try_loads(block)
        if parsed is not None:
            return parsed

    snippet = (raw_response or "")[:300].replace("\n", " ")
    logger.warning(
        f"parse_llm_json: failed (len={len(raw_response)}) snippet={snippet!r}"
    )
    return None


def _try_loads(s: str) -> dict | list | None:
    if not s:
        return None
    try:
        result = json.loads(s)
    except Exception:
        return None
    if isinstance(result, (dict, list)):
        return result
    return None


def _sanitize(s: str) -> str:
    """Strip noise that LLMs commonly emit alongside JSON."""
    # Strip Python literals → JSON literals
    s = re.sub(r"\bTrue\b", "true", s)
    s = re.sub(r"\bFalse\b", "false", s)
    s = re.sub(r"\bNone\b", "null", s)
    # Drop trailing commas inside arrays/objects: `,]` → `]`
    s = _TRAILING_COMMA_RE.sub(r"\1", s)
    return s.strip()


def _extract_balanced_json(s: str) -> str | None:
    """Find the first balanced {...} or [...] substring, ignoring quoted strings.

    Handles nested braces correctly, unlike a naive `re.search(r"\\{.*\\}")`.
    """
    if not s:
        return None
    # Find the earliest opening bracket
    open_pos = -1
    open_ch = ""
    for i, c in enumerate(s):
        if c in "{[":
            open_pos = i
            open_ch = c
            break
    if open_pos < 0:
        return None

    close_ch = "}" if open_ch == "{" else "]"
    depth = 0
    in_str = False
    str_quote = ""
    escape = False

    for i in range(open_pos, len(s)):
        c = s[i]
        if in_str:
            if escape:
                escape = False
            elif c == "\\":
                escape = True
            elif c == str_quote:
                in_str = False
        else:
            if c in ('"', "'"):
                in_str = True
                str_quote = c
            elif c == open_ch:
                depth += 1
            elif c == close_ch:
                depth -= 1
                if depth == 0:
                    return s[open_pos : i + 1]

    return None
