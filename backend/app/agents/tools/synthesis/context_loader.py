"""SynthesisContextLoaderTool — gather Project + Documents + Analyses.

Wraps the existing deterministic ``build_report_context`` aggregator so the
SynthesisAgent uses the SAME data layer the deterministic generator already
relies on. We then add a compact LLM-friendly digest derived from the
``DocumentBlock`` objects.

The loader is async-only (the AnalysisAgent / SynthesisAgent run on async
sessions). The underlying aggregator is sync, so we run it inside the
executor only when needed; otherwise we issue equivalent async queries
directly.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.analysis import DocumentAnalysis
from app.models.document import Document
from app.models.project import Project
from app.utils.constants import AnalysisStatus
from app.utils.logger import logger


# How much of each document's insight we keep in the LLM digest. Tight by
# default so multi-document reports don't blow the context window.
_DIGEST_KEY_FINDINGS = 5
_DIGEST_LIMITATIONS = 3
_DIGEST_RQ = 3
_DIGEST_TOPICS = 5
_DIGEST_QUOTES = 2
_MAX_SUMMARY_CHARS = 800


@dataclass
class DocumentItem:
    """A single document + its analysis flattened for the LLM."""

    index: int                      # 1-based citation index
    id: UUID
    title: str
    source_url: str | None
    source_type: str | None
    authors: list[str]
    published_at: str | None        # ISO date string, never raw datetime
    doi: str | None
    summary: str | None
    main_thesis: str | None
    document_type: str | None
    main_topics: list[str]
    key_findings: list[str]
    methodology: str | None
    limitations: list[str]
    research_questions: list[str]
    research_contribution: str | None
    notable_quotes: list[str] = field(default_factory=list)
    has_analysis: bool = False

    def to_digest_dict(self) -> dict[str, Any]:
        """Compact dict shape sent to the LLM (drops irrelevant fields)."""
        out: dict[str, Any] = {
            "n": self.index,
            "title": self.title,
            "type": self.document_type or self.source_type,
        }
        if self.summary:
            out["summary"] = self.summary[:_MAX_SUMMARY_CHARS]
        if self.main_thesis:
            out["thesis"] = self.main_thesis
        if self.research_contribution:
            out["contribution"] = self.research_contribution
        if self.key_findings:
            out["findings"] = self.key_findings[:_DIGEST_KEY_FINDINGS]
        if self.methodology:
            out["methodology"] = self.methodology[:600]
        if self.limitations:
            out["limitations"] = self.limitations[:_DIGEST_LIMITATIONS]
        if self.research_questions:
            out["research_questions"] = (
                self.research_questions[:_DIGEST_RQ]
            )
        if self.main_topics:
            out["topics"] = self.main_topics[:_DIGEST_TOPICS]
        if self.notable_quotes:
            out["quotes"] = self.notable_quotes[:_DIGEST_QUOTES]
        if not self.has_analysis:
            out["analysis_missing"] = True
        return out


@dataclass
class SynthesisContext:
    """Everything the SynthesisAgent needs about the report inputs."""

    project_id: UUID
    project_name: str
    project_topic: str | None
    project_description: str | None
    project_research_scope: str | None
    report_title: str
    report_type: str
    documents: list[DocumentItem] = field(default_factory=list)

    @property
    def documents_with_analysis(self) -> list[DocumentItem]:
        return [d for d in self.documents if d.has_analysis]

    @property
    def documents_digest_json(self) -> str:
        """JSON blob of the digest — sent into LLM prompts."""
        return json.dumps(
            [d.to_digest_dict() for d in self.documents],
            ensure_ascii=False,
            indent=2,
        )


class SynthesisContextLoaderTool:
    """Build a ``SynthesisContext`` for a report row."""

    async def load(
        self,
        db: AsyncSession,
        project: Project,
        report_title: str,
        report_type: str,
        included_documents: list[UUID] | None,
    ) -> SynthesisContext:
        stmt = (
            select(Document)
            .where(Document.project_id == project.id)
            .options(selectinload(Document.analysis))
            .order_by(Document.created_at.asc())
        )
        if included_documents:
            stmt = stmt.where(Document.id.in_(included_documents))

        result = await db.execute(stmt)
        documents: list[Document] = list(result.scalars().all())

        items: list[DocumentItem] = []
        for idx, doc in enumerate(documents, start=1):
            items.append(self._flatten(idx, doc, doc.analysis))

        logger.info(
            f"SynthesisContextLoader: project={project.id} "
            f"docs={len(items)} "
            f"with_analysis={sum(1 for d in items if d.has_analysis)}"
        )

        return SynthesisContext(
            project_id=project.id,
            project_name=project.name,
            project_topic=project.topic,
            project_description=project.description,
            project_research_scope=project.research_scope,
            report_title=report_title,
            report_type=report_type,
            documents=items,
        )

    # ── Helpers ──────────────────────────────────────────────────────────

    def _flatten(
        self,
        index: int,
        document: Document,
        analysis: DocumentAnalysis | None,
    ) -> DocumentItem:
        meta = document.document_metadata or {}
        # Authors from document metadata (ingestion may populate this);
        # fall back to empty list.
        authors = _coerce_authors(meta)
        published = meta.get("published_at") or meta.get("published")
        published_iso: str | None = None
        if isinstance(published, str):
            published_iso = published[:10]

        has_analysis = (
            analysis is not None
            and analysis.status == AnalysisStatus.COMPLETED.value
        )

        if not has_analysis or analysis is None:
            return DocumentItem(
                index=index,
                id=document.id,
                title=document.title or "Untitled",
                source_url=document.source_url,
                source_type=document.source_type,
                authors=authors,
                published_at=published_iso,
                doi=meta.get("doi"),
                summary=None,
                main_thesis=None,
                document_type=None,
                main_topics=[],
                key_findings=[],
                methodology=None,
                limitations=[],
                research_questions=[],
                research_contribution=None,
                notable_quotes=[],
                has_analysis=False,
            )

        outline = analysis.document_outline or {}
        synthesis = analysis.narrative_synthesis or {}

        quotes: list[str] = []
        for s in (analysis.section_insights or [])[:6]:
            if not isinstance(s, dict):
                continue
            for q in (s.get("notable_quotes") or [])[:1]:
                if isinstance(q, dict) and isinstance(q.get("quote"), str):
                    quotes.append(q["quote"].strip())
            if len(quotes) >= _DIGEST_QUOTES:
                break

        return DocumentItem(
            index=index,
            id=document.id,
            title=document.title or "Untitled",
            source_url=document.source_url,
            source_type=document.source_type,
            authors=authors,
            published_at=published_iso,
            doi=meta.get("doi"),
            summary=analysis.summary,
            main_thesis=synthesis.get("main_thesis"),
            document_type=outline.get("document_type"),
            main_topics=_str_list(outline.get("main_topics")),
            key_findings=_str_list(analysis.key_findings),
            methodology=analysis.methodology,
            limitations=_str_list(analysis.limitations),
            research_questions=_str_list(analysis.research_questions),
            research_contribution=(
                analysis.research_contribution
                or synthesis.get("novelty_vs_prior_work")
            ),
            notable_quotes=quotes[:_DIGEST_QUOTES],
            has_analysis=True,
        )


def _coerce_authors(meta: dict[str, Any]) -> list[str]:
    raw = meta.get("authors")
    if not raw:
        return []
    if isinstance(raw, str):
        return [raw.strip()] if raw.strip() else []
    if isinstance(raw, list):
        out: list[str] = []
        for a in raw:
            if isinstance(a, str) and a.strip():
                out.append(a.strip())
            elif isinstance(a, dict):
                name = a.get("name") or a.get("full_name") or a.get("author")
                if isinstance(name, str) and name.strip():
                    out.append(name.strip())
        return out
    return []


def _str_list(value: Any) -> list[str]:
    """Normalise a JSONB list-like value into list[str]."""
    if not value:
        return []
    out: list[str] = []
    if isinstance(value, list):
        for item in value:
            if isinstance(item, str) and item.strip():
                out.append(item.strip())
            elif isinstance(item, dict):
                for k in ("claim", "text", "description", "value", "name"):
                    v = item.get(k)
                    if isinstance(v, str) and v.strip():
                        out.append(v.strip())
                        break
    elif isinstance(value, str):
        out.append(value.strip())
    return out
