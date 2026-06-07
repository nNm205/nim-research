from __future__ import annotations
import asyncio
from datetime import datetime, timezone
from typing import Any, TypedDict
from uuid import UUID
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.exc import StaleDataError
from app.agents.tools.analysis import (
    ChunkLoaderTool,
    ChunkRecord,
    CrossSectionSynthesizerTool,
    MappedSection,
    OutlineBuilderTool,
    SectionInsightTool,
    SectionMapperTool,
    parse_llm_json,  
)
from app.agents.tools.analysis.progress_tracker import (
    ProgressTracker,
    STEP_ANALYSE_SECTIONS,
    STEP_BUILD_OUTLINE,
    STEP_LOAD_CHUNKS,
    STEP_MAP_SECTIONS,
    STEP_PERSIST,
    STEP_SYNTHESIZE,
)
from app.config import settings
from app.models.analysis import DocumentAnalysis
from app.models.document import Document
from app.models.document_chunk import DocumentChunk
from app.models.llm_providers.base import LLMProvider
from app.models.llm_providers.factory import LLMFactory
from app.models.llm_providers.types import ProviderType
from app.utils.constants import AnalysisStatus
from app.utils.logger import logger

__all__ = ["AnalysisAgent", "parse_llm_json"]


_MAX_SECTIONS_TO_ANALYSE = 16
_SECTION_CONCURRENCY = 2
_SKIP_SECTION_TYPES = frozenset({
    "references",
    "acknowledgments",
})
_MIN_CHARS_FOR_LLM = 500

class AnalysisState(TypedDict, total=False):
    analysis_id: UUID
    document: Document
    db: AsyncSession
    llm: LLMProvider
    progress: "ProgressTracker"
    chunks: list[ChunkRecord]
    sections: list[MappedSection]
    outline: dict
    section_insights: list[dict]
    narrative_synthesis: dict
    summary: str | None
    legacy_rollup: dict
    error: str | None

async def _node_load_chunks(state: AnalysisState) -> AnalysisState:
    db: AsyncSession = state["db"]
    document: Document = state["document"]
    progress: ProgressTracker | None = state.get("progress")

    if progress:
        await progress.start_step(STEP_LOAD_CHUNKS)

    loader = ChunkLoaderTool()
    chunks = await loader.load(db, document.id)

    if not chunks and document.content:
        chunks = [
            ChunkRecord(
                id=document.id,  
                chunk_index=0,
                content=document.content,
                metadata={},
                has_embedding=False,
            )
        ]
        logger.info(
            "AnalysisAgent: no DocumentChunks found, using document.content as a "
            "single synthetic chunk"
        )

    if not chunks:
        msg = "Document has no content to analyse"
        if progress:
            await progress.fail_step(STEP_LOAD_CHUNKS, msg)
        return {**state, "error": msg}

    logger.info(f"AnalysisAgent: loaded {len(chunks)} chunks for analysis")
    if progress:
        await progress.finish_step(STEP_LOAD_CHUNKS, f"{len(chunks)} chunks")
    return {**state, "chunks": chunks}


async def _node_map_sections(state: AnalysisState) -> AnalysisState:
    if state.get("error"):
        return state

    progress: ProgressTracker | None = state.get("progress")
    if progress:
        await progress.start_step(STEP_MAP_SECTIONS)

    mapper = SectionMapperTool()
    sections = mapper.map(state["chunks"])

    if len(sections) > _MAX_SECTIONS_TO_ANALYSE:
        logger.info(
            f"AnalysisAgent: capping section analysis to "
            f"{_MAX_SECTIONS_TO_ANALYSE} of {len(sections)} sections"
        )
        sections = sections[:_MAX_SECTIONS_TO_ANALYSE]

    if progress:
        await progress.finish_step(
            STEP_MAP_SECTIONS, f"{len(sections)} sections"
        )
    return {**state, "sections": sections}


async def _node_build_outline(state: AnalysisState) -> AnalysisState:
    if state.get("error"):
        return state

    progress: ProgressTracker | None = state.get("progress")
    if progress:
        await progress.start_step(STEP_BUILD_OUTLINE)

    builder = OutlineBuilderTool()
    document: Document = state["document"]
    outline = await builder.build(
        document_title=document.title or "Untitled",
        sections=state["sections"],
        llm=state["llm"],
    )
    if progress:
        doc_type = (outline or {}).get("document_type") or "other"
        await progress.finish_step(
            STEP_BUILD_OUTLINE, f"document_type={doc_type}"
        )
    return {**state, "outline": outline or {}}


async def _node_analyse_sections(state: AnalysisState) -> AnalysisState:
    if state.get("error"):
        return state

    document: Document = state["document"]
    sections: list[MappedSection] = state["sections"]
    outline: dict = state.get("outline") or {}
    document_type = outline.get("document_type") or "other"
    llm: LLMProvider = state["llm"]
    progress: ProgressTracker | None = state.get("progress")
    sections_for_llm: list[MappedSection] = []
    sections_skipped: list[MappedSection] = []
    for s in sections:
        if s.section_type in _SKIP_SECTION_TYPES:
            sections_skipped.append(s)
        elif s.total_chars < _MIN_CHARS_FOR_LLM:
            sections_skipped.append(s)
        else:
            sections_for_llm.append(s)

    total = len(sections_for_llm)
    if progress:
        await progress.start_step(
            STEP_ANALYSE_SECTIONS,
            f"{total} sections to analyse"
            + (f" (skipping {len(sections_skipped)} short/boilerplate)"
               if sections_skipped else ""),
        )
        if total > 0:
            await progress.update_section_progress(
                done=0, total=total,
                current_title=sections_for_llm[0].title,
            )

    tool = SectionInsightTool()
    semaphore = asyncio.Semaphore(_SECTION_CONCURRENCY)
    done_counter = 0
    counter_lock = asyncio.Lock()

    async def analyse_one(section: MappedSection) -> dict:
        nonlocal done_counter
        async with semaphore:
            result = await tool.analyse(
                section=section,
                document_title=document.title or "Untitled",
                document_type=document_type,
                total_sections=total,
                llm=llm,
            )
        if progress:
            async with counter_lock:
                done_counter += 1
                await progress.update_section_progress(
                    done=done_counter, total=total,
                    current_title=section.title,
                )
        return result

    insights_llm = await asyncio.gather(
        *[analyse_one(s) for s in sections_for_llm]
    )
    insights_skipped = [
        tool._wrap_section(s, tool._heuristic_fallback(s))
        for s in sections_skipped
    ]

    by_index: dict[int, dict] = {}
    for ins in insights_llm + insights_skipped:
        idx = ins.get("section_index")
        if isinstance(idx, int):
            by_index[idx] = ins
    insights = [by_index[i] for i in sorted(by_index)]

    if progress:
        msg = f"{total} sections analysed"
        if sections_skipped:
            msg += f" + {len(sections_skipped)} via heuristic"
        await progress.finish_step(STEP_ANALYSE_SECTIONS, msg)
    return {**state, "section_insights": insights}


async def _node_synthesize(state: AnalysisState) -> AnalysisState:
    if state.get("error"):
        return state

    document: Document = state["document"]
    outline: dict = state.get("outline") or {}
    insights: list[dict] = state.get("section_insights") or []
    progress: ProgressTracker | None = state.get("progress")

    if progress:
        await progress.start_step(STEP_SYNTHESIZE)

    tool = CrossSectionSynthesizerTool()
    synthesis = await tool.synthesize(
        document_title=document.title or "Untitled",
        document_type=outline.get("document_type") or "other",
        main_topics=outline.get("main_topics") or [],
        section_insights=insights,
        llm=state["llm"],
    )

    summary = (synthesis or {}).get("executive_summary")

    if progress:
        thesis = (synthesis or {}).get("main_thesis") or ""
        msg = (
            f"Main thesis: {thesis[:80]}..."
            if len(thesis) > 80
            else (thesis or "synthesis complete")
        )
        await progress.finish_step(STEP_SYNTHESIZE, msg)
    return {**state, "narrative_synthesis": synthesis, "summary": summary}


async def _node_rollup_legacy(state: AnalysisState) -> AnalysisState:
    if state.get("error"):
        return state

    insights: list[dict] = state.get("section_insights") or []
    synthesis: dict = state.get("narrative_synthesis") or {}

    rollup = _aggregate_legacy(insights, synthesis)
    return {**state, "legacy_rollup": rollup}

def _aggregate_legacy(
    insights: list[dict], synthesis: dict
) -> dict[str, Any]:
    by_type: dict[str, list[dict]] = {}
    for s in insights:
        by_type.setdefault(s.get("section_type") or "other", []).append(s)

    key_findings: list[str] = []
    for s in insights:
        for c in s.get("claims") or []:
            if not isinstance(c, dict):
                continue
            claim = (c.get("claim") or "").strip()
            if claim and claim not in key_findings:
                key_findings.append(claim)
    key_findings = key_findings[:10]

    method_section = (
        by_type.get("methodology")
        or by_type.get("methods")
        or by_type.get("experiments")
        or []
    )
    methodology: str | None = None
    if method_section:
        first = method_section[0]
        methodology = first.get("summary") or first.get("purpose")

    limitations: list[str] = []
    for s in by_type.get("limitations", []):
        critique = s.get("critique") or {}
        for w in critique.get("weaknesses") or []:
            if isinstance(w, str) and w not in limitations:
                limitations.append(w)
        for q in s.get("open_questions") or []:
            if isinstance(q, str) and q not in limitations:
                limitations.append(q)
    for w in synthesis.get("overall_weaknesses") or []:
        if isinstance(w, str) and w not in limitations:
            limitations.append(w)
    limitations = limitations[:10]

    future_work: list[str] = []
    for s in by_type.get("future_work", []):
        for q in s.get("open_questions") or []:
            if isinstance(q, str) and q not in future_work:
                future_work.append(q)
    for g in synthesis.get("knowledge_gaps") or []:
        if isinstance(g, str) and g not in future_work:
            future_work.append(g)
    future_work = future_work[:10]

    keywords: list[str] = []
    for s in insights:
        for term in s.get("notable_terms") or []:
            if isinstance(term, dict):
                name = (term.get("term") or "").strip()
                if name and name.lower() not in {k.lower() for k in keywords}:
                    keywords.append(name)
    keywords = keywords[:20]

    research_questions: list[str] = []
    intro_like = (
        by_type.get("introduction", [])
        + by_type.get("abstract", [])
    )
    for s in intro_like:
        for q in s.get("open_questions") or []:
            if isinstance(q, str) and q not in research_questions:
                research_questions.append(q)
    for g in synthesis.get("knowledge_gaps") or []:
        if isinstance(g, str) and g not in research_questions:
            research_questions.append(g)
    research_questions = research_questions[:7]

    critical_assessment: dict[str, Any] = {
        "strengths": list(synthesis.get("overall_strengths") or [])[:5],
        "weaknesses": list(synthesis.get("overall_weaknesses") or [])[:5],
        "confidence_in_conclusions": synthesis.get("confidence_in_conclusions"),
        "confidence_justification": synthesis.get("confidence_justification"),
        "internal_conflicts": list(synthesis.get("internal_conflicts") or [])[:5],
    }
    if not any(critical_assessment.values()):
        critical_assessment = {}

    return {
        "key_findings": key_findings,
        "methodology": methodology,
        "limitations": limitations,
        "future_work": future_work,
        "keywords": keywords,
        "research_questions": research_questions,
        "research_contribution": synthesis.get("novelty_vs_prior_work"),
        "critical_assessment": critical_assessment or None,
    }

def _build_graph():
    from langgraph.graph import END, StateGraph

    graph = StateGraph(AnalysisState)
    graph.add_node("load_chunks", _node_load_chunks)
    graph.add_node("map_sections", _node_map_sections)
    graph.add_node("build_outline", _node_build_outline)
    graph.add_node("analyse_sections", _node_analyse_sections)
    graph.add_node("synthesize", _node_synthesize)
    graph.add_node("rollup_legacy", _node_rollup_legacy)

    graph.set_entry_point("load_chunks")
    graph.add_edge("load_chunks", "map_sections")
    graph.add_edge("map_sections", "build_outline")
    graph.add_edge("build_outline", "analyse_sections")
    graph.add_edge("analyse_sections", "synthesize")
    graph.add_edge("synthesize", "rollup_legacy")
    graph.add_edge("rollup_legacy", END)

    return graph.compile()

_GRAPH = _build_graph()

class AnalysisAgent:
    def __init__(
        self,
        db: AsyncSession,
        llm_provider: str | None = None,
        llm_model: str | None = None,
    ) -> None:
        self.db = db
        self.llm_provider = (llm_provider or settings.PROVIDER).lower()
        self.llm_model = llm_model or settings.MODEL_NAME

    async def run(self, analysis_id: UUID) -> DocumentAnalysis:
        analysis = await self._get_analysis(analysis_id)
        progress = ProgressTracker(self.db, analysis_id)

        try:
            try:
                await self._mark_running(analysis)
            except RuntimeError:
                return analysis

            document = await self._get_document(analysis.document_id)

            try:
                provider_type = ProviderType[self.llm_provider.upper()]
            except KeyError:
                raise ValueError(
                    f"Unknown LLM provider {self.llm_provider!r}. "
                    f"Valid: {[p.value for p in ProviderType]}"
                )

            llm = LLMFactory.create_provider(
                provider_type,
                model=self.llm_model,
            )
            logger.info(
                f"AnalysisAgent: using provider={self.llm_provider} "
                f"model={llm.get_model_name()}"
            )

            await progress.init(provider=self.llm_provider, model=llm.get_model_name())

            initial_state: AnalysisState = {
                "analysis_id": analysis_id,
                "document": document,
                "db": self.db,
                "llm": llm,
                "progress": progress,
            }

            final_state: AnalysisState = await _GRAPH.ainvoke(initial_state)

            if final_state.get("error"):
                await progress.finalize("failed", final_state["error"])
                await self._mark_failed(analysis_id, final_state["error"])
                await self._notify_failed(
                    analysis_id, document, final_state["error"]
                )
                return analysis

            try:
                await progress.start_step(STEP_PERSIST)
                await self._persist_result(analysis, final_state, llm)
                await progress.finish_step(STEP_PERSIST, "saved to DB")
                await progress.finalize("completed")
            except StaleDataError:
                await self.db.rollback()
                logger.warning(
                    f"AnalysisAgent: analysis {analysis_id} disappeared "
                    f"during run; result discarded (likely deleted by user)."
                )
                return analysis

            logger.success(
                f"AnalysisAgent: completed analysis {analysis.id} "
                f"for document {document.id}"
            )
            await self._notify_completed(analysis_id, document)

        except StaleDataError:
            await self.db.rollback()
            logger.warning(
                f"AnalysisAgent: analysis {analysis_id} was deleted during "
                f"run; aborting cleanly."
            )
        except Exception as e:
            await self.db.rollback()
            logger.error(f"AnalysisAgent: failed for analysis {analysis_id}: {e}")
            try:
                await progress.finalize("failed", str(e))
            except Exception:
                pass
            await self._mark_failed(analysis_id, str(e))

            doc = locals().get("document")
            await self._notify_failed(analysis_id, doc, str(e))
            raise

        return analysis

    async def _get_analysis(self, analysis_id: UUID) -> DocumentAnalysis:
        result = await self.db.execute(
            select(DocumentAnalysis).where(DocumentAnalysis.id == analysis_id)
        )
        analysis = result.scalar_one_or_none()
        if analysis is None:
            raise ValueError(f"DocumentAnalysis not found: {analysis_id}")
        return analysis

    async def _get_document(self, document_id: UUID) -> Document:
        result = await self.db.execute(
            select(Document).where(Document.id == document_id)
        )
        document = result.scalar_one_or_none()
        if document is None:
            raise ValueError(f"Document not found: {document_id}")
        return document

    async def _mark_running(self, analysis: DocumentAnalysis) -> None:
        if analysis.status != AnalysisStatus.PENDING.value:
            logger.info(
                f"AnalysisAgent: skipping duplicate task for analysis "
                f"{analysis.id} (status={analysis.status})"
            )
            raise RuntimeError("Analysis is not in PENDING state")

        analysis.status = AnalysisStatus.RUNNING.value
        analysis.started_at = datetime.now(timezone.utc)
        await self.db.commit()
        await self.db.refresh(analysis)
        logger.info(f"AnalysisAgent: analysis {analysis.id} → RUNNING")

    async def _mark_failed(
        self, analysis_id: UUID, error_message: str
    ) -> None:
        from sqlalchemy import update

        try:
            stmt = (
                update(DocumentAnalysis)
                .where(DocumentAnalysis.id == analysis_id)
                .values(
                    status=AnalysisStatus.FAILED.value,
                    error_message=(error_message or "")[:1000],
                    completed_at=datetime.now(timezone.utc),
                )
            )
            result = await self.db.execute(stmt)
            await self.db.commit()
            if result.rowcount == 0:
                logger.warning(
                    f"AnalysisAgent: tried to mark analysis {analysis_id} "
                    f"as FAILED but row was already gone."
                )
        except Exception as e:
            await self.db.rollback()
            logger.error(
                f"AnalysisAgent: failed to record FAILED status for "
                f"{analysis_id}: {e}"
            )

    async def _persist_result(
        self,
        analysis: DocumentAnalysis,
        state: AnalysisState,
        llm: LLMProvider,
    ) -> None:
        outline: dict = state.get("outline") or {}
        section_insights: list[dict] = state.get("section_insights") or []
        synthesis: dict = state.get("narrative_synthesis") or {}
        rollup: dict = state.get("legacy_rollup") or {}
        analysis.document_outline = outline or None
        analysis.section_insights = section_insights or None
        analysis.narrative_synthesis = synthesis or None
        analysis.summary = state.get("summary")
        analysis.key_findings = rollup.get("key_findings") or None
        analysis.methodology = rollup.get("methodology")
        analysis.limitations = rollup.get("limitations") or None
        analysis.future_work = rollup.get("future_work") or None
        analysis.keywords = rollup.get("keywords") or None
        analysis.research_questions = rollup.get("research_questions") or None
        analysis.research_contribution = rollup.get("research_contribution")
        analysis.critical_assessment = rollup.get("critical_assessment")
        analysis.sections = [
            {
                "index": s.get("section_index"),
                "title": s.get("title"),
                "type": s.get("section_type"),
                "summary": s.get("summary"),
            }
            for s in section_insights
        ] or None

        analysis.extracted_entities = None
        analysis.extracted_tables = None
        analysis.relationships = None
        analysis.metrics = None
        analysis.sentiment = None
        analysis.evidence_quality = None
        analysis.citation_context = None
        analysis.status = AnalysisStatus.COMPLETED.value
        analysis.completed_at = datetime.now(timezone.utc)
        analysis.processed_by = f"{self.llm_provider}:{llm.get_model_name()}"

        await self.db.commit()
        await self.db.refresh(analysis)

    async def _notify_completed(
        self, analysis_id: UUID, document: Document
    ) -> None:
        await self._notify(
            analysis_id=analysis_id,
            document=document,
            success=True,
            error=None,
        )

    async def _notify_failed(
        self,
        analysis_id: UUID,
        document: Document | None,
        error: str | None,
    ) -> None:
        await self._notify(
            analysis_id=analysis_id,
            document=document,
            success=False,
            error=error,
        )

    async def _notify(
        self,
        *,
        analysis_id: UUID,
        document: Document | None,
        success: bool,
        error: str | None,
    ) -> None:
        from app.database.session import AsyncSessionLocal as _Session
        from app.models.project import Project
        from app.services.notification_service import (
            CATEGORY_ANALYSIS,
            TYPE_ERROR,
            TYPE_SUCCESS,
            create_notification_async,
        )

        try:
            project_id = (
                document.project_id if document is not None else None
            )
            user_id = None
            if project_id is not None:
                async with _Session() as s:
                    user_id = await s.scalar(
                        select(Project.user_id).where(
                            Project.id == project_id
                        )
                    )
            if user_id is None:
                return

            doc_title = (document.title if document else None) or "tài liệu"
            if success:
                title = "Phân tích tài liệu hoàn thành"
                message = f"'{doc_title[:120]}' đã được phân tích xong."
                ntype = TYPE_SUCCESS
            else:
                title = "Phân tích tài liệu thất bại"
                message = (
                    f"'{doc_title[:120]}': {(error or 'lỗi không xác định')[:200]}"
                )
                ntype = TYPE_ERROR

            await create_notification_async(
                user_id=user_id,
                title=title,
                message=message,
                notification_type=ntype,
                category=CATEGORY_ANALYSIS,
                entity_id=analysis_id,
                entity_kind="analysis",
                project_id=project_id,
            )
        except Exception as e:
            logger.warning(
                f"AnalysisAgent: failed to write notification for "
                f"{analysis_id}: {e}"
            )
