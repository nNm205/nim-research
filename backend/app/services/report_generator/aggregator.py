from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Iterable
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models.analysis import DocumentAnalysis
from app.models.document import Document
from app.models.project import Project
from app.utils.constants import AnalysisStatus


@dataclass
class DocumentBlock:
    id: UUID
    title: str
    source_url: str | None
    source_type: str | None
    summary: str | None
    key_findings: list[str]
    methodology: str | None
    keywords: list[str]
    research_questions: list[str]
    research_contribution: str | None
    limitations: list[str]
    future_work: list[str]
    critical_assessment: dict[str, Any]
    section_count: int
    document_type: str | None
    main_topics: list[str]
    main_thesis: str | None
    novelty_vs_prior_work: str | None
    has_analysis: bool

    @property
    def display_title(self) -> str:
        return self.title or "Untitled document"

@dataclass
class ReportContext:
    project_name: str
    project_topic: str | None
    project_description: str | None
    project_research_scope: str | None
    report_title: str
    report_type: str
    documents: list[DocumentBlock]
    generated_at: datetime
    included_documents_filter: list[UUID] | None = field(default=None)
    aggregate_keywords: list[str] = field(default_factory=list)
    aggregate_findings: list[str] = field(default_factory=list)
    aggregate_research_questions: list[str] = field(default_factory=list)
    aggregate_methodologies: list[str] = field(default_factory=list)
    aggregate_limitations: list[str] = field(default_factory=list)
    aggregate_future_work: list[str] = field(default_factory=list)

    @property
    def documents_with_analysis(self) -> list[DocumentBlock]:
        return [d for d in self.documents if d.has_analysis]

    @property
    def total_documents(self) -> int:
        return len(self.documents)

def _ensure_str_list(value: Any, *, max_len: int = 100) -> list[str]:
    if not value:
        return []
    out: list[str] = []
    seen: set[str] = set()
    iterable: Iterable[Any]
    if isinstance(value, str):
        iterable = [value]
    elif isinstance(value, dict):
        iterable = value.values()
    else:
        try:
            iterable = list(value)
        except TypeError:
            return []
    for item in iterable:
        text: str | None = None
        if isinstance(item, str):
            text = item.strip()
        elif isinstance(item, dict):
            for key in ("claim", "text", "description", "value", "name", "title"):
                v = item.get(key)
                if isinstance(v, str) and v.strip():
                    text = v.strip()
                    break
        if not text:
            continue
        norm = text.lower()
        if norm in seen:
            continue
        seen.add(norm)
        out.append(text)
        if len(out) >= max_len:
            break
    return out


def _build_document_block(
    document: Document, analysis: DocumentAnalysis | None
) -> DocumentBlock:
    has_analysis = (
        analysis is not None
        and analysis.status == AnalysisStatus.COMPLETED.value
    )

    if not has_analysis or analysis is None:
        return DocumentBlock(
            id=document.id,
            title=document.title or "Untitled",
            source_url=document.source_url,
            source_type=document.source_type,
            summary=None,
            key_findings=[],
            methodology=None,
            keywords=[],
            research_questions=[],
            research_contribution=None,
            limitations=[],
            future_work=[],
            critical_assessment={},
            section_count=0,
            document_type=None,
            main_topics=[],
            main_thesis=None,
            novelty_vs_prior_work=None,
            has_analysis=False,
        )

    outline = analysis.document_outline or {}
    synthesis = analysis.narrative_synthesis or {}
    section_insights = analysis.section_insights or []

    return DocumentBlock(
        id=document.id,
        title=document.title or "Untitled",
        source_url=document.source_url,
        source_type=document.source_type,
        summary=analysis.summary,
        key_findings=_ensure_str_list(analysis.key_findings, max_len=8),
        methodology=analysis.methodology,
        keywords=_ensure_str_list(analysis.keywords, max_len=12),
        research_questions=_ensure_str_list(
            analysis.research_questions, max_len=6
        ),
        research_contribution=analysis.research_contribution
        or synthesis.get("novelty_vs_prior_work"),
        limitations=_ensure_str_list(analysis.limitations, max_len=8),
        future_work=_ensure_str_list(analysis.future_work, max_len=8),
        critical_assessment=analysis.critical_assessment or {},
        section_count=len(section_insights),
        document_type=outline.get("document_type"),
        main_topics=_ensure_str_list(outline.get("main_topics"), max_len=8),
        main_thesis=synthesis.get("main_thesis"),
        novelty_vs_prior_work=synthesis.get("novelty_vs_prior_work"),
        has_analysis=True,
    )


def _aggregate_across_documents(
    blocks: list[DocumentBlock],
) -> dict[str, list[str]]:
    def _flatten(attr: str, cap: int) -> list[str]:
        seen: set[str] = set()
        out: list[str] = []
        for b in blocks:
            for item in getattr(b, attr, []):
                norm = (item or "").strip().lower()
                if not norm or norm in seen:
                    continue
                seen.add(norm)
                out.append(item)
                if len(out) >= cap:
                    return out
        return out

    methodologies: list[str] = []
    seen_method: set[str] = set()
    for b in blocks:
        if b.methodology:
            norm = b.methodology.strip().lower()
            if norm not in seen_method:
                seen_method.add(norm)
                methodologies.append(f"{b.display_title}: {b.methodology}")

    return {
        "aggregate_keywords": _flatten("keywords", 30),
        "aggregate_findings": _flatten("key_findings", 15),
        "aggregate_research_questions": _flatten(
            "research_questions", 10
        ),
        "aggregate_limitations": _flatten("limitations", 10),
        "aggregate_future_work": _flatten("future_work", 10),
        "aggregate_methodologies": methodologies[:10],
    }


def build_report_context(
    db: Session,
    project: Project,
    *,
    report_title: str,
    report_type: str,
    included_documents: list[UUID] | None,
) -> ReportContext:
    stmt = (
        select(Document)
        .where(Document.project_id == project.id)
        .options(selectinload(Document.analysis))
        .order_by(Document.created_at.asc())
    )
    if included_documents:
        stmt = stmt.where(Document.id.in_(included_documents))

    documents: list[Document] = list(db.execute(stmt).scalars().all())
    blocks = [_build_document_block(d, d.analysis) for d in documents]
    rollups = _aggregate_across_documents(blocks)

    return ReportContext(
        project_name=project.name,
        project_topic=project.topic,
        project_description=project.description,
        project_research_scope=project.research_scope,
        report_title=report_title,
        report_type=report_type,
        documents=blocks,
        generated_at=datetime.now(timezone.utc),
        included_documents_filter=list(included_documents)
        if included_documents
        else None,
        **rollups,
    )
