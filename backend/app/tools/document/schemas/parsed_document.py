from dataclasses import dataclass, field
from typing import Optional


@dataclass
class ParsedTable:
    """Structured representation of a table extracted from a document."""

    headers: list[str] = field(default_factory=list)
    rows: list[list[str]] = field(default_factory=list)
    page: Optional[int] = None
    title: Optional[str] = None  # caption inferred from surrounding text

    @property
    def is_empty(self) -> bool:
        return not self.headers and not self.rows

    def to_markdown(self) -> str:
        if self.is_empty:
            return ""
        cols = max(len(self.headers), max((len(r) for r in self.rows), default=0))
        if cols == 0:
            return ""

        def _norm(cells: list[str]) -> list[str]:
            cleaned = [(c or "").replace("\n", " ").replace("|", "\\|").strip() for c in cells]
            cleaned += [""] * (cols - len(cleaned))
            return cleaned

        header_cells = _norm(self.headers) if self.headers else _norm([""] * cols)
        sep = ["---"] * cols
        body = [_norm(r) for r in self.rows]

        lines: list[str] = []
        if self.title:
            lines.append(f"**{self.title}**")
        lines.append("| " + " | ".join(header_cells) + " |")
        lines.append("| " + " | ".join(sep) + " |")
        for row in body:
            lines.append("| " + " | ".join(row) + " |")
        return "\n".join(lines)

    def to_dict(self) -> dict:
        return {
            "headers": list(self.headers),
            "rows": [list(r) for r in self.rows],
            "page": self.page,
            "title": self.title,
        }


@dataclass
class ParsedFormula:
    """A mathematical expression extracted from a document.

    `text` is the raw extracted form (may contain unicode math symbols, may
    even be LaTeX if the source had it). `label` is the equation number or
    name when available. `kind` says whether the formula stood on its own
    line (``"display"``) or was embedded in prose (``"inline"``).
    """

    text: str
    label: Optional[str] = None
    kind: str = "display"  # "display" | "inline"
    page: Optional[int] = None

    @property
    def is_empty(self) -> bool:
        return not (self.text or "").strip()

    def to_markdown(self) -> str:
        if self.is_empty:
            return ""
        # We tag formulas so the chunker and the LLM can recognise them as a
        # distinct block. The fence is plain text — most LLMs handle this
        # better than $$..$$ when the source already mixes Unicode math.
        body = (self.text or "").strip()
        label = (self.label or "").strip()
        header = f"[Equation {label}]" if label else "[Equation]"
        return f"{header}\n```formula\n{body}\n```"

    def to_dict(self) -> dict:
        return {
            "text": self.text,
            "label": self.label,
            "kind": self.kind,
            "page": self.page,
        }


@dataclass
class ParsedDocument:
    text: str
    page_count: int
    title: Optional[str] = None
    author: Optional[str] = None
    metadata: Optional[dict] = None
    tables: list[ParsedTable] = field(default_factory=list)
    formulas: list[ParsedFormula] = field(default_factory=list)
