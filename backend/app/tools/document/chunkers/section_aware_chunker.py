"""SectionAwareChunker — recursive char chunking that tags every chunk with
the section it falls into.

Detection strategy (in priority order):

  1. Pre-stitch broken numbered headings ("3\\nIntroduction" →
     "3 Introduction") and normalise line endings.
  2. ``_NUMBERED_HEADING_RE`` — generic numbered-heading pattern. Catches
     any line of the form ``N[.M[.K]]<space>TitleText`` regardless of what
     the title actually says. This is the primary detector and it
     generalises to papers with custom section names like
     "3 TimeGazer Model" or "4.2 Data Collection".
  3. ``_NAMED_HEADING_RE`` — curated whitelist of canonical section names
     (Abstract, Introduction, References, Tóm tắt, ...). Acts as a fallback
     for papers that don't number their sections, and as a redundant safety
     net for the numbered detector.
  4. ``_looks_like_heading_title`` — post-filter that rejects sentences,
     figure/table captions, and oversized titles.
  5. ``_has_isolation_before`` — visual isolation check (blank line / prior
     paragraph ending in punctuation / prior line is itself a heading).
     Drops list items that happen to start with a digit.
  6. Build ``_SectionSpan`` list. Numbered "N" → top-level. "N.M" / "N.M.K"
     → subsection of the most recent parent. Leading content (paper
     title, authors, affiliations) is absorbed into the FIRST detected
     top-level section so we never emit a "Front Matter" pseudo-section.

The previous version of this module hard-whitelisted section names, which
silently dropped sections with custom titles. The new pipeline only
requires the title to follow a numbered-heading shape, which generalises
to any paper that numbers its sections.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from langchain_text_splitters import RecursiveCharacterTextSplitter

from app.tools.document.chunkers.base import BaseChunker
from app.tools.document.schemas.chunk import DocumentChunk
from app.utils.logger import logger


# ─── Whitelist of commonly-named unnumbered headings ────────────────────────
# Used as a fallback when a paper doesn't number its sections, OR to catch
# unnumbered front-matter ("Abstract", "References") on numbered papers.

_NAMED_HEADING_WORDS: list[str] = [
    # English — front matter & body
    r"Abstract", r"Introduction", r"Background", r"Preliminaries", r"Notation",
    r"Related\s+Works?", r"Prior\s+Works?", r"Literature\s+Review",
    r"Motivation", r"Problem\s+Statement",
    r"Methodology", r"Methods?", r"Materials?\s+and\s+Methods?",
    r"Approach",
    r"Proposed\s+(?:Method|Approach|Model|Algorithm|Framework|Architecture)",
    r"Model\s+Architecture", r"Architecture", r"Framework",
    r"System(?:\s+Design)?", r"Implementation",
    r"Experiments?", r"Experimental\s+(?:Setup|Results?)", r"Setup",
    r"Training(?:\s+(?:Setup|Details))?", r"Datasets?", r"Evaluation",
    r"Results?", r"Findings?", r"Analysis", r"Discussion",
    r"Ablation(?:\s+Stud(?:y|ies))?",
    r"Conclusions?(?:\s+and\s+Future\s+Work)?", r"Concluding\s+Remarks",
    r"Summary", r"Future\s+(?:Work|Directions?)", r"Limitations?",
    # English — back matter
    r"References", r"Bibliography", r"Appendix(?:\s+[A-Z])?", r"Appendices",
    r"Supplementary(?:\s+(?:Material|Information))?",
    r"Acknowledg(?:e?ments?)",
    # Vietnamese
    r"Tóm\s+tắt", r"Giới\s+thiệu", r"Tổng\s+quan",
    r"Cơ\s+sở\s+lý\s+thuyết",
    r"Phương\s+pháp(?:\s+(?:nghiên\s+cứu|đề\s+xuất))?",
    r"Mô\s+hình(?:\s+đề\s+xuất)?", r"Kiến\s+trúc",
    r"Thí\s+nghiệm", r"Đánh\s+giá",
    r"Kết\s+quả(?:\s+(?:thí\s+nghiệm|nghiên\s+cứu))?",
    r"Phân\s+tích", r"Thảo\s+luận", r"Kết\s+luận",
    r"Hướng\s+(?:phát\s+triển|nghiên\s+cứu(?:\s+tiếp\s+theo)?)",
    r"Hạn\s+chế", r"Tài\s+liệu\s+tham\s+khảo",
    r"Phụ\s+lục", r"Lời\s+cảm\s+ơn",
]


# ─── Heading detection regexes ─────────────────────────────────────────────
#
# Numbered: "N", "N.M", "N.M.K" + space + Title-case text.


def _capitalize_first(pattern: str) -> str:
    """Capitalize only the first letter, preserving the rest verbatim.

    Used to build a Vietnamese-friendly variant of named-heading
    patterns. ``"Tóm\\s+tắt".title()`` would produce ``"Tóm\\s+Tắt"`` —
    every word capitalised — which doesn't match how Vietnamese papers
    actually print headings ("Tóm tắt", "Tài liệu tham khảo"). The
    correct casing is "first letter of the heading capitalised, rest
    lowercase", which is what this helper produces.
    """
    if not pattern:
        return pattern
    return pattern[0].upper() + pattern[1:].lower()
#   Number: max 2 digits per component, max 3 components deep
#   Title:  starts with capital letter (or ``&`` for "& Connections" style),
#           3-100 chars, no newline.
#   Anchored to start AND end of line (multiline).

_NUMBERED_HEADING_RE = re.compile(
    r"(?m)^[ \t]*"
    r"(?P<num>\d{1,2}(?:\.\d{1,2}){0,2})"
    r"\.?[ \t]+"
    r"(?P<title>[A-Z&][^\n]{2,99})"
    r"[ \t]*:?[ \t]*$"
)

# Roman-numeral headings (IEEE-style top-level sections).
#   "I. INTRODUCTION" / "II. RELATED WORK" / "III. METHODOLOGY"
#
# We require the dot+space separator and a 1-99 chars title that starts
# with a capital letter so common false positives — variable names ("V"),
# inline references ("Eq. I"), and figure captions starting with "I" —
# don't match. The list of valid roman numerals is upper-cased here so
# the regex stays case-sensitive (papers don't write "i. introduction"
# as a section heading; they use prose).
_ROMAN_NUMERAL = (
    r"(?:I{1,3}V?|IV|V|VI{1,3}|IX|X|XI{1,3}|XIV|XV|XVI{1,3}|XIX|XX|"
    r"XXI{1,3}|XXIV|XXV)"
)
_ROMAN_HEADING_RE = re.compile(
    r"(?m)^[ \t]*"
    rf"(?P<roman>{_ROMAN_NUMERAL})"
    r"\.[ \t]+"
    r"(?P<title>[A-Z&][^\n]{2,99})"
    r"[ \t]*:?[ \t]*$"
)

# Letter-prefixed sub-headings (IEEE / ACM style under a Roman section).
#   "A. Setup" / "B. Datasets" / "C. Evaluation Metrics"
#
# These are always SUBSECTIONS of the most-recent Roman or numbered
# parent. We require dot+space + capital-leading title for the same
# reasons as ``_ROMAN_HEADING_RE``. To distinguish a real "B. Setup"
# heading from a stray bullet "B. " that appears inside running text,
# the heading_collector still applies ``_has_isolation_before`` on
# each match.
_LETTER_HEADING_RE = re.compile(
    r"(?m)^[ \t]*"
    r"(?P<letter>[A-Z])"
    r"\.[ \t]+"
    r"(?P<title>[A-Z&][^\n]{2,99})"
    r"[ \t]*:?[ \t]*$"
)

# Named: a whitelisted heading word, optionally with leading numbering.
# Case-insensitive (some papers write "INTRODUCTION", others "Introduction").
#
# Note: assembling the alternation as a single big pattern with IGNORECASE
# was catastrophically slow at compile time (~20 s) due to interaction
# between `re.IGNORECASE` and 60+ alternations. We avoid IGNORECASE here
# and instead bake the casing variants into ``_NAMED_HEADING_VARIANTS``.

_NAMED_HEADING_VARIANTS = "|".join(
    pat.upper() + "|" + pat.lower() + "|" + pat.title() + "|" + _capitalize_first(pat)
    for pat in _NAMED_HEADING_WORDS
)

_NAMED_HEADING_RE = re.compile(
    r"(?m)^[ \t]*"
    r"(?:(?P<num>\d{1,2}(?:\.\d{1,2}){0,2})\.?[ \t]+)?"
    r"(?P<title>" + _NAMED_HEADING_VARIANTS + r")"
    r"[ \t]*:?[ \t]*$"
)


# Public re-export — ``section_mapper`` imports this for its legacy regex
# fallback (when chunk metadata is missing). Combines both regexes via the
# module's own iteration logic, exposed as a regex for compatibility but
# implemented as a wrapper.

class _CombinedHeadingRE:
    """Drop-in replacement that ``section_mapper._map_from_headings``
    treats as a regex. Yields matches whose ``group(1)`` returns the
    raw heading title (with leading numbering preserved).
    """

    def finditer(self, text: str):
        # Order matters: numbered first (most specific), then roman, then
        # letter, then named. Each loop dedupes by start-offset against
        # earlier loops so a position never gets matched twice.
        seen: set[int] = set()

        for m in _NUMBERED_HEADING_RE.finditer(text):
            if m.start() in seen:
                continue
            seen.add(m.start())
            title_with_num = f"{m.group('num')} {m.group('title').strip()}"
            yield _FakeMatch(start=m.start(), group1=title_with_num)

        for m in _ROMAN_HEADING_RE.finditer(text):
            if m.start() in seen:
                continue
            seen.add(m.start())
            yield _FakeMatch(
                start=m.start(),
                group1=f"{m.group('roman')} {m.group('title').strip()}",
            )

        for m in _LETTER_HEADING_RE.finditer(text):
            if m.start() in seen:
                continue
            seen.add(m.start())
            yield _FakeMatch(
                start=m.start(),
                group1=f"{m.group('letter')} {m.group('title').strip()}",
            )

        for m in _NAMED_HEADING_RE.finditer(text):
            if m.start() in seen:
                continue
            seen.add(m.start())
            title = m.group("title").strip()
            num = m.group("num")
            yield _FakeMatch(
                start=m.start(),
                group1=f"{num} {title}" if num else title,
            )


class _FakeMatch:
    def __init__(self, start: int, group1: str) -> None:
        self._start = start
        self._g1 = group1

    def start(self) -> int:
        return self._start

    def group(self, n: int = 0) -> str:
        return self._g1


_HEADING_RE = _CombinedHeadingRE()

# Pre-stitch broken numbered headings: PDF extractors sometimes split
# "3 Introduction" or "III. Introduction" across two lines. We restitch
# both forms so the heading regexes below match the rejoined line.
_SPLIT_NUMBERED_HEADING_RE = re.compile(
    r"(?m)^[ \t]*(\d{1,2}(?:\.\d{1,2}){0,2}\.?)[ \t]*\n[ \t]*"
    r"([A-Z][A-Za-z].{2,118})$"
)
_SPLIT_ROMAN_HEADING_RE = re.compile(
    rf"(?m)^[ \t]*({_ROMAN_NUMERAL}\.)[ \t]*\n[ \t]*"
    r"([A-Z][A-Za-z].{2,118})$"
)
_SPLIT_LETTER_HEADING_RE = re.compile(
    r"(?m)^[ \t]*([A-Z]\.)[ \t]*\n[ \t]*"
    r"([A-Z][A-Za-z].{2,118})$"
)


def _normalize_text(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = _SPLIT_NUMBERED_HEADING_RE.sub(r"\1 \2", text)
    text = _SPLIT_ROMAN_HEADING_RE.sub(r"\1 \2", text)
    # Letter-prefix re-stitch is conservative: only run it when the
    # previous line is a Roman heading. Without that guard we'd
    # accidentally glue ordinary single-letter list items ("A.\nlist
    # item content") to their bodies. We skip it here and rely on the
    # in-place ``_LETTER_HEADING_RE`` to match A./B./C. that already sit
    # on a single line — which is the overwhelmingly common case.
    return text


# ─── Heading filtering ──────────────────────────────────────────────────────

# Caption-like prefixes that often start title-case lines but aren't headings.
_CAPTION_PREFIXES = (
    "figure", "fig.", "fig ", "table", "tab.", "tab ",
    "equation", "eq.", "eq ", "lemma", "theorem",
    "proposition", "corollary", "definition", "algorithm",
    "proof",
)


def _looks_like_heading_title(title: str) -> bool:
    """Reject candidates that look more like prose, captions, or list items.

    Rules:
      - 3-120 chars total
      - At most 14 words
      - Doesn't end in sentence punctuation ('.', '!', '?')
      - Doesn't start with a caption marker ("Figure", "Table", "Eq.", ...)
    """
    t = title.strip().rstrip(":")
    if not t:
        return False
    if len(t) < 3 or len(t) > 120:
        return False
    if t[-1] in ".!?":
        return False

    lower = t.lower()
    for prefix in _CAPTION_PREFIXES:
        if lower.startswith(prefix + " ") or lower == prefix.rstrip():
            return False

    if len(t.split()) > 14:
        return False

    return True


# Backward-compat alias used by section_mapper.
def _is_noise_heading(title: str) -> bool:
    return not _looks_like_heading_title(title)


def _has_isolation_before(text: str, pos: int) -> bool:
    """A heading line should be visually isolated.

    Accepts any of:
      - At very start of text
      - Preceded by a blank line (``\\n\\n`` or two ``\\n`` chars in a row)
      - Preceded by a line that ends in sentence punctuation (the body
        paragraph just ended)
      - Preceded by a line that itself parses as a heading (consecutive
        section headings, e.g. "3 Methods\\n4 Results")
    """
    if pos <= 1:
        return True
    # Strict: blank line directly before (char two positions back is also \n)
    if pos >= 2 and text[pos - 2] == "\n":
        return True

    # Find the start of the previous line.
    line_end = pos - 1   # this is the \n preceding our line
    line_start = line_end
    while line_start > 0 and text[line_start - 1] != "\n":
        line_start -= 1
    prev_line = text[line_start:line_end].rstrip()

    if not prev_line:
        return True
    if prev_line[-1] in ".!?":
        return True

    # Consecutive headings: previous line itself looks like a heading.
    if (
        _NUMBERED_HEADING_RE.match(prev_line)
        or _NAMED_HEADING_RE.match(prev_line)
        or _ROMAN_HEADING_RE.match(prev_line)
        or _LETTER_HEADING_RE.match(prev_line)
    ):
        return True

    return False


# ─── Section type classification ───────────────────────────────────────────

_RULE_KEYWORDS: list[tuple[str, list[str]]] = [
    ("abstract",       ["abstract", "synopsis", "tóm tắt"]),
    ("introduction",   ["introduction", "intro", "giới thiệu", "tổng quan"]),
    ("background",     ["background", "preliminaries", "notation",
                        "motivation", "problem statement",
                        "cơ sở lý thuyết"]),
    ("related_work",   ["related work", "prior work", "literature review"]),
    ("methodology",    ["methodology", "method", "methods",
                        "materials and method", "approach", "framework",
                        "design", "architecture", "system design",
                        "implementation", "proposed",
                        "phương pháp", "mô hình", "kiến trúc"]),
    ("results",        ["result", "finding", "outcome", "evaluation",
                        "kết quả", "đánh giá"]),
    ("experiments",    ["experiment", "experimental setup",
                        "experimental result", "setup", "training",
                        "datasets", "ablation", "thí nghiệm"]),
    ("discussion",     ["discussion", "analysis", "interpretation",
                        "thảo luận", "phân tích"]),
    ("conclusion",     ["conclusion", "concluding", "summary", "kết luận"]),
    ("future_work",    ["future work", "future direction", "open problem",
                        "hướng phát triển", "hướng nghiên cứu"]),
    ("limitations",    ["limitation", "threat to validity", "hạn chế"]),
    ("references",     ["reference", "bibliography", "tài liệu tham khảo"]),
    ("appendix",       ["appendix", "appendices", "supplementary",
                        "supplement", "phụ lục"]),
    ("acknowledgments", ["acknowledgment", "acknowledgement", "lời cảm ơn"]),
]


def _classify_title(title: str) -> str:
    t = title.lower().strip()
    for stype, keywords in _RULE_KEYWORDS:
        if any(kw in t for kw in keywords):
            return stype
    return "other"


def _normalize_section_title(title: str) -> str:
    """Make whitelisted section titles consistent regardless of source casing."""
    t = title.strip()
    if not t:
        return t
    # Vietnamese / non-ASCII — leave the casing the author wrote.
    if any(ord(c) > 127 for c in t):
        return t
    # ASCII — title-case ("RELATED WORKS" → "Related Works", etc.)
    return t.title()


def _is_section_keyword_only(title: str) -> bool:
    """True iff the entire title is just a *named* heading word like 'Methods'.

    Used to drop noisy subsection regex matches that simply repeat a
    parent's name (e.g. "3.1 Methods" inside section "3 Methods"). Only
    rejects exact matches of the canonical heading words listed in
    ``_NAMED_HEADING_WORDS``; subsection titles like "Architecture" or
    "Setup" that happen to appear in ``_RULE_KEYWORDS`` are NOT treated
    as boilerplate — they often carry useful context.
    """
    flat = re.sub(r"\s+", " ", title.strip().lower())
    # Match against exact lowercase variants of named heading words.
    canonical = {
        "abstract", "introduction", "background", "methods", "method",
        "methodology", "results", "result", "discussion", "conclusion",
        "conclusions", "references", "bibliography", "appendix",
    }
    return flat in canonical


def _is_redundant_subsection(title: str, parent) -> bool:
    """True iff the subsection title exactly repeats its parent's name.

    A previous version of this check rejected ANY subsection whose
    title was a canonical section keyword — that wrongly dropped
    legitimate sub-headings like "B. Results" under "IV. Experiments"
    in IEEE-style papers, where "Results" is a perfectly valid name
    for a sub-section presenting experimental results.

    The redundancy test now requires the subsection name to actually
    match the parent's name (case-insensitive, whitespace-collapsed)
    before we drop it. Examples:

      - parent="Methods",  sub="3.1 Methods"  → True   (drop)
      - parent="Experiments", sub="B. Results" → False  (keep)
      - parent="Results", sub="3.1 Results"   → True   (drop)
    """
    if parent is None:
        return False
    parent_name = (parent.title or "").strip()
    # Strip a leading numbering prefix from the parent's display title
    # so "3 Methods" / "III. Methods" both match against "Methods".
    parent_name = re.sub(
        r"^(?:\d+(?:\.\d+){0,2}|[IVX]+)\.?\s+", "", parent_name
    )
    norm_parent = re.sub(r"\s+", " ", parent_name.strip().lower())
    norm_sub = re.sub(r"\s+", " ", (title or "").strip().lower())
    if not norm_parent or not norm_sub:
        return False
    return norm_parent == norm_sub


# ─── Section span data ─────────────────────────────────────────────────────

@dataclass
class _Subsection:
    """A numbered subsection like '3.1 Encoder and Decoder Stacks'."""

    number: str
    title: str
    char_offset: int


@dataclass
class _SectionSpan:
    start: int
    end: int
    title: str
    section_type: str
    number: str | None = None
    subsections: list[_Subsection] | None = None


def _heading_depth(num: str | None) -> int:
    """0 = unnumbered, 1 = top-level (N), 2 = subsection (N.M), 3 = sub-sub."""
    if not num:
        return 0
    return num.count(".") + 1


# Lookup table for Roman numerals up to 25. Reads off-grammar but is the
# clearest implementation; covers every realistic paper section count.
_ROMAN_VALUES: dict[str, int] = {
    "I": 1, "II": 2, "III": 3, "IV": 4, "V": 5,
    "VI": 6, "VII": 7, "VIII": 8, "IX": 9, "X": 10,
    "XI": 11, "XII": 12, "XIII": 13, "XIV": 14, "XV": 15,
    "XVI": 16, "XVII": 17, "XVIII": 18, "XIX": 19, "XX": 20,
    "XXI": 21, "XXII": 22, "XXIII": 23, "XXIV": 24, "XXV": 25,
}


def _roman_to_int(roman: str) -> int | None:
    """Convert a Roman numeral string to an integer, or None on miss.

    We use the explicit lookup table rather than the algorithmic
    decomposition because the regex above already enforces that the
    matched string is one of the canonical 25 forms — no point
    duplicating that validation in two places.
    """
    return _ROMAN_VALUES.get(roman.upper())


def _letter_to_int(letter: str) -> int | None:
    """``A`` → 1, ``B`` → 2, ..., ``Z`` → 26. ``None`` for non-letters."""
    if not letter or len(letter) != 1:
        return None
    code = ord(letter.upper()) - ord("A")
    if 0 <= code <= 25:
        return code + 1
    return None


def _last_before(items: list[dict], position: int) -> dict | None:
    """Return the last item (by ``start``) whose ``start`` is < ``position``.

    Used to bind a letter-sub-heading to the most recent Roman /
    numbered parent. We sort defensively because the caller's list may
    not be ordered.
    """
    best = None
    for item in items:
        s = item.get("start", -1)
        if s < position and (best is None or s > best.get("start", -1)):
            best = item
    return best


# ─── Main detection ────────────────────────────────────────────────────────


# Front- and back-matter section types that are commonly *unnumbered* even
# in heavily-numbered papers. When the document is in "numbered mode"
# (≥ 2 valid top-level numbered headings) we still keep these because
# they're never confused with body subsections.
_ALWAYS_KEEP_NAMED_TYPES = frozenset({
    "abstract",
    "references",
    "bibliography",
    "appendix",
    "acknowledgments",
    "supplementary",
})


def _is_front_or_back_matter(title: str) -> bool:
    """True iff the title is one of the always-keep named-only headings."""
    flat = re.sub(r"\s+", " ", title.strip().lower())
    keep = {
        "abstract", "tóm tắt",
        "references", "bibliography", "tài liệu tham khảo",
        "appendix", "appendices", "phụ lục",
        "acknowledgments", "acknowledgements", "lời cảm ơn",
        "supplementary material", "supplementary information",
        "supplementary",
    }
    if flat in keep:
        return True
    # "Appendix A", "Appendix B" — keep
    if flat.startswith("appendix "):
        return True
    return False


def _detect_sections(text: str) -> list[_SectionSpan]:
    """Return ordered, contiguous _SectionSpan list.

    Rules:

    1. **Sequence validation for numbered headings.** A numbered heading
       only counts as a real section if its top-level number is one of:
         - the next sequential number after the previous top-level
           (e.g. "1 Introduction" → "2 Background" → "3 Method")
         - the same top-level (re-rendering of the heading text — rare)
         - 1 (always allowed for the first heading)
       This prevents list items like "1. First metric, 2. Second metric"
       inside subsection 6.1 from being interpreted as new sections.

    2. **Numbered mode silences named-only matches in the body.** If we
       detected ≥ 2 valid top-level numbered sections, the document is
       treated as "numbered mode": named-only matches like "Limitations"
       (with no number prefix) are dropped UNLESS they are front- or
       back-matter (Abstract, References, Appendix, Acknowledgments,
       Supplementary). This prevents an unnumbered paragraph titled
       "Limitations" inside section "7 Discussion" from being split out
       as a top-level section.

    3. Subsections (depth ≥ 2) only count if they share the same top-level
       prefix as the current parent. This rejects "1.", "2.", "3." labels
       (depth 1 list-style numbering) at offsets where a depth-1 parent
       is already active.
    """
    # ── 1. Collect raw matches ─────────────────────────────────────────────
    numbered_raw: list[dict] = []
    named_raw: list[dict] = []

    for m in _NUMBERED_HEADING_RE.finditer(text):
        title = m.group("title").strip()
        if not _looks_like_heading_title(title):
            continue
        if not _has_isolation_before(text, m.start()):
            continue
        numbered_raw.append({
            "start": m.start(),
            "number": m.group("num"),
            "title": title,
            "is_named": False,
            # ``display_number`` keeps the raw heading prefix the paper
            # actually uses (Roman / letter / Arabic). The pipeline below
            # normalises ``number`` to Arabic for sequence checks but
            # uses ``display_number`` when rendering the section title.
            "display_number": m.group("num"),
        })

    # Roman top-level headings — converted to Arabic numbers so the
    # sequence-validation pipeline below can treat them uniformly with
    # ordinary "1.", "2.", ... headings. The ORIGINAL roman is kept in
    # ``display_number`` for rendering.
    roman_parents: list[dict] = []  # used to bind letter sub-headings below
    for m in _ROMAN_HEADING_RE.finditer(text):
        title = m.group("title").strip()
        if not _looks_like_heading_title(title):
            continue
        if not _has_isolation_before(text, m.start()):
            continue
        roman = m.group("roman")
        num = _roman_to_int(roman)
        if num is None:
            continue
        entry = {
            "start": m.start(),
            "number": str(num),
            "title": title,
            "is_named": False,
            "display_number": f"{roman}.",
        }
        numbered_raw.append(entry)
        roman_parents.append(entry)

    # Letter sub-headings — only kept when there's a Roman parent above
    # them (otherwise an "A. Foo" line is more likely to be a list item
    # or an enumeration inside a paragraph than a real subsection).
    # We attach them tentatively as depth-2 of the most recent Roman
    # parent and let the sequence validator drop spurious ones.
    letter_candidates: list[dict] = []
    for m in _LETTER_HEADING_RE.finditer(text):
        title = m.group("title").strip()
        if not _looks_like_heading_title(title):
            continue
        if not _has_isolation_before(text, m.start()):
            continue
        letter = m.group("letter")
        sub_idx = _letter_to_int(letter)
        if sub_idx is None:
            continue
        letter_candidates.append({
            "start": m.start(),
            "letter": letter,
            "sub_idx": sub_idx,
            "title": title,
        })

    # Bind each letter candidate to the most recent ROMAN top-level
    # heading. Pure-Arabic numbered docs don't use "A./B./C." sub-
    # headings (they use "3.1/3.2"), so we deliberately skip letters
    # when no Roman parent has been seen — that avoids confusing
    # bullet points with subsection markers.
    if letter_candidates and roman_parents:
        for cand in letter_candidates:
            parent = _last_before(roman_parents, cand["start"])
            if parent is None:
                continue
            top_arabic = parent["number"]
            numbered_raw.append({
                "start": cand["start"],
                "number": f"{top_arabic}.{cand['sub_idx']}",
                "title": cand["title"],
                "is_named": False,
                "display_number": f"{cand['letter']}.",
            })

    for m in _NAMED_HEADING_RE.finditer(text):
        title = m.group("title").strip()
        if not _looks_like_heading_title(title):
            continue
        if not _has_isolation_before(text, m.start()):
            continue
        named_raw.append({
            "start": m.start(),
            "number": m.group("num"),
            "title": title,
            "is_named": True,
            "display_number": m.group("num"),
        })

    # ── 2. Validate the numbered sequence ──────────────────────────────────
    # Walk numbered headings in document order. Accept only those whose
    # top-level number forms a non-decreasing sequence starting near 1.
    # Subsections (depth ≥ 2) and "next" depth-1 numbers extend the
    # current run.
    valid_numbered: list[dict] = []
    last_top: int | None = None
    last_subnums: dict[int, list[int]] = {}  # parent_top → [last seen subnum at each depth]

    for h in sorted(numbered_raw, key=lambda x: x["start"]):
        parts = h["number"].split(".")
        depth = len(parts)
        try:
            top = int(parts[0])
        except ValueError:
            continue

        if depth == 1:
            # First top-level: must start at 1 (almost always) or 2
            # (papers that begin sectioning at "Introduction" without an
            # "Abstract" number).
            if last_top is None:
                if top not in (1, 2):
                    continue
            else:
                # Allow same top (re-print) or next integer.
                if top != last_top and top != last_top + 1:
                    continue
            last_top = top
            last_subnums.setdefault(top, [])
            valid_numbered.append(h)
            continue

        # depth ≥ 2 — must hang off the current parent (same top).
        if last_top is None or top != last_top:
            continue

        # The subsection chain must be sequential too:
        #   "6.1" after "6"     ✓
        #   "6.2" after "6.1"   ✓
        #   "6.1.1" after "6.1" ✓
        #   "6.1" then "1." inside it → "1." has depth=1 with top=1, not
        #     last_top, so already filtered above.
        try:
            sub_chain = [int(p) for p in parts[1:]]
        except ValueError:
            continue

        prev_chain = last_subnums.get(top, [])
        if not _valid_subsection_chain(prev_chain, sub_chain):
            continue
        last_subnums[top] = sub_chain
        valid_numbered.append(h)

    # ── 3. Decide on "numbered mode" ───────────────────────────────────────
    # If we have ≥ 2 valid depth-1 numbered headings, the doc is numbered
    # and we filter named-only matches down to front/back matter only.
    top_level_count = sum(1 for h in valid_numbered if "." not in h["number"])
    numbered_mode = top_level_count >= 2

    if numbered_mode:
        named_filtered = [
            h for h in named_raw if _is_front_or_back_matter(h["title"])
        ]
    else:
        named_filtered = list(named_raw)

    # ── 4. Merge + dedupe ──────────────────────────────────────────────────
    raw_matches = valid_numbered + named_filtered
    # Sort by position; tie-break favours numbered (is_named=False).
    raw_matches.sort(key=lambda x: (x["start"], 1 if x["is_named"] else 0))
    deduped: list[dict] = []
    for h in raw_matches:
        if deduped and h["start"] == deduped[-1]["start"]:
            continue
        deduped.append(h)

    if not deduped:
        return []

    # ── 5. Build contiguous spans ──────────────────────────────────────────
    # - depth 0 (unnumbered named) → top-level section
    # - depth 1 (e.g. "3") → top-level section
    # - depth 2/3 (e.g. "3.1", "3.1.2") → subsection of most recent parent
    spans: list[_SectionSpan] = []
    current: _SectionSpan | None = None

    for h in deduped:
        depth = _heading_depth(h["number"])

        if depth >= 2:
            if current is None:
                continue
            # Skip subsections that just repeat the *current parent's*
            # canonical name (e.g. "3.1 Methods" inside section "3
            # Methods"). We compare against the parent specifically so
            # legitimate IEEE-style sub-headings like "B. Results"
            # under "IV. Experiments" aren't dropped — they only
            # collide if Results sits inside a section also called
            # Results, which is genuinely redundant.
            if _is_redundant_subsection(h["title"], current):
                continue
            if current.subsections is None:
                current.subsections = []
            current.subsections.append(_Subsection(
                number=h.get("display_number") or h["number"],
                title=h["title"],
                char_offset=h["start"] - current.start,
            ))
            continue

        # Top-level (depth 0 or 1).
        if current is not None:
            current.end = h["start"]
            spans.append(current)
            start_pos = h["start"]
        else:
            # First top-level absorbs leading content (paper title, authors,
            # affiliations) so we never emit a "Front Matter" pseudo-section.
            start_pos = 0

        display_number = h.get("display_number") or h["number"]
        display_title = (
            f"{display_number} {_normalize_section_title(h['title'])}"
            if display_number else _normalize_section_title(h["title"])
        )
        current = _SectionSpan(
            start=start_pos,
            end=len(text),  # placeholder, updated when next heading is found
            title=display_title,
            section_type=_classify_title(h["title"]),
            number=display_number,
            subsections=[],
        )

    if current is not None:
        current.end = len(text)
        spans.append(current)

    return spans


def _valid_subsection_chain(
    prev: list[int], current: list[int]
) -> bool:
    """True iff ``current`` is a plausible next subsection after ``prev``.

    Examples (parent = "6"):
      prev=[],     current=[1]      → True   (first subsection 6.1)
      prev=[1],    current=[2]      → True   (6.2 after 6.1)
      prev=[2],    current=[1]      → False  (going back is not legal)
      prev=[1],    current=[1, 1]   → True   (6.1.1 after 6.1)
      prev=[1, 1], current=[1, 2]   → True   (6.1.2 after 6.1.1)
      prev=[2],    current=[1, 1]   → False  (6.1.1 must follow 6.1, not 6.2)
      prev=[1],    current=[3]      → False  (skipping 6.2)
      prev=[2, 1], current=[3]      → False  (6.3 after 6.2.1 needs 6.2 → 6.3? no
                                              the natural step is 6.2.2 or 6.3.1)
      prev=[1, 1], current=[2, 1]   → False  (need 6.2 before 6.2.1)
      prev=[1, 1], current=[2]      → True   (popping back up to 6.2 after 6.1.1)
    """
    if not current:
        return False
    if not prev:
        # First subsection must start at "1" (e.g. 6.1, not 6.2).
        return current[0] == 1 and all(c == 1 for c in current[1:])

    # The depth of ``current`` must be ≤ depth(prev)+1 — we can deepen by
    # at most one level at a time. Going from "6.1" to "6.1.1.1" jumps
    # two levels and is rejected.
    if len(current) > len(prev) + 1:
        return False

    # Walk down both chains together. At the first depth where they
    # differ, ``current[d]`` must equal ``prev[d] + 1`` AND ``current``
    # must end at this depth (no deeper components yet — those would
    # reset to a fresh sub-tree, but only if depth(current) > depth(prev)).
    for d, cur_v in enumerate(current):
        if d >= len(prev):
            # current is exactly one level deeper than prev's last common
            # depth. The new component must be 1 (the first child).
            return cur_v == 1
        prev_v = prev[d]
        if cur_v == prev_v:
            continue
        if cur_v == prev_v + 1:
            # Advancing at this depth. ``current`` must end here — any
            # deeper components would be a forward jump into uncharted
            # territory (we'd need a fresh sub-tree for the new node first).
            return d == len(current) - 1
        return False
    # current is a prefix of prev (e.g. prev=[1,1], current=[1]) — not a
    # forward step, so reject.
    return False


def _find_section_for_offset(
    spans: list[_SectionSpan], offset: int
) -> _SectionSpan | None:
    """Pick the span containing ``offset``.

    Uses the start of the chunk (not its midpoint) so a chunk that *begins*
    inside a section is correctly attributed to that section, even when
    the chunk's body is shorter than expected and its midpoint would
    land in the previous span. This matters most for short test texts
    and tightly-packed back-matter.
    """
    if not spans:
        return None
    for span in spans:
        if span.start <= offset < span.end:
            return span
    return spans[-1]


# ─── Public Chunker ────────────────────────────────────────────────────────

class SectionAwareChunker(BaseChunker):
    """Recursive char chunker that tags each chunk with section metadata."""

    def __init__(
        self,
        chunk_size: int = 1000,
        chunk_overlap: int = 200,
    ) -> None:
        self.splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
        )

    async def chunk(self, text: str) -> list[DocumentChunk]:
        if not text:
            return []

        text = _normalize_text(text)

        spans = _detect_sections(text)
        if spans:
            logger.info(
                f"SectionAwareChunker: detected {len(spans)} sections "
                f"({[s.title for s in spans[:5]]}{'...' if len(spans) > 5 else ''})"
            )
        else:
            logger.info("SectionAwareChunker: no headings detected, single section")

        # Strategy: split text at section boundaries first, then chunk
        # within each section. This guarantees that no chunk straddles a
        # section boundary, so every detected section gets at least one
        # chunk attributed to it (even tiny sections like a 1-paragraph
        # "Conclusion") regardless of ``chunk_size`` setting.
        out: list[DocumentChunk] = []
        chunk_id = 0

        if spans:
            for span in spans:
                section_text = text[span.start:span.end]
                section_chunks = self.splitter.split_text(section_text) or [""]
                cursor_in_section = 0
                for raw in section_chunks:
                    if not raw.strip():
                        continue
                    rel = section_text.find(raw, cursor_in_section)
                    if rel < 0:
                        rel = section_text.find(raw)
                    if rel < 0:
                        rel = cursor_in_section
                    abs_start = span.start + rel
                    abs_end = abs_start + len(raw)
                    cursor_in_section = max(
                        cursor_in_section,
                        rel + len(raw) - max(0, self.splitter._chunk_overlap),
                    )

                    metadata: dict = {
                        "char_offset": abs_start,
                        "section_title": span.title,
                        "section_type": span.section_type,
                    }
                    if span.number:
                        metadata["section_number"] = span.number
                    if span.subsections:
                        metadata["section_subsections"] = [
                            {"number": s.number, "title": s.title}
                            for s in span.subsections
                        ]

                    out.append(
                        DocumentChunk(
                            chunk_id=chunk_id,
                            text=raw,
                            start_char=abs_start,
                            end_char=abs_end,
                            metadata=metadata,
                        )
                    )
                    chunk_id += 1
            return out

        # Fallback: no sections detected — chunk the whole document and
        # tag each chunk only with ``char_offset``. SectionMapper will
        # collapse these into a single "Document" section.
        raw_chunks = self.splitter.split_text(text)
        cursor = 0
        for raw in raw_chunks:
            start = text.find(raw, cursor)
            if start < 0:
                start = text.find(raw)
            if start < 0:
                start = cursor
            end = start + len(raw)
            cursor = max(cursor, end - max(0, self.splitter._chunk_overlap))
            out.append(
                DocumentChunk(
                    chunk_id=chunk_id,
                    text=raw,
                    start_char=start,
                    end_char=end,
                    metadata={"char_offset": start},
                )
            )
            chunk_id += 1
        return out
