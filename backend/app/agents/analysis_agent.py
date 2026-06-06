"""AnalysisAgent — section-grounded LLM analysis pipeline (LangGraph).

Pipeline:
  START
    → load_chunks            (load DocumentChunks + embeddings, no truncation)
    → map_sections           (group chunks into sections by metadata or headings)
    → build_outline          (deterministic, 0 LLM calls)
    → analyse_sections       (parallel SectionInsightTool over each section)
    → synthesize             (1 LLM call, returns narrative + executive_summary)
    → rollup_legacy_fields   (rule-based: derive key_findings / methodology /
                              limitations / future_work / keywords / RQs /
                              critical_assessment from section insights)
    → persist                (write to document_analyses)
  END

Total LLM calls per document = N_sections + 1 (synthesis), where short or
"trivial" sections (references, acknowledgments, very short) are skipped to
save more quota. For a typical 7-section paper that means ~6 calls total
versus the 10+ the original pipeline made.

The agent uses chunk-grounded retrieval: SectionInsightTool sees full chunks
labelled with [chunk N] so it can cite quotes back to specific chunk indices,
and the SemanticRetrieverTool is available for future aspect-based deep dives.
"""

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
# Conservative — Gemini free tier is 5 RPM. Most other providers tolerate 4-8.
# Override at runtime via env if you have a paid tier.
_SECTION_CONCURRENCY = 2

# Cost guard. Sections of these types are pure boilerplate; analysing them
# burns LLM quota for no insight gain. They get a heuristic-only insight.
_SKIP_SECTION_TYPES = frozenset({
    "references",
    "acknowledgments",
})

# Sections shorter than this get a heuristic insight (no LLM call). 500 chars
# ≈ 100 tokens of substantive text — anything below that is too small to
# extract claims/methods/data from anyway.
_MIN_CHARS_FOR_LLM = 500


# ---------------------------------------------------------------------------
# LangGraph state
# ---------------------------------------------------------------------------
class AnalysisState(TypedDict, total=False):
    # Input
    analysis_id: UUID
    document: Document
    db: AsyncSession
    llm: LLMProvider
    progress: "ProgressTracker"

    # Loaded
    chunks: list[ChunkRecord]
    sections: list[MappedSection]

    # Produced
    outline: dict
    section_insights: list[dict]
    narrative_synthesis: dict
    summary: str | None
    legacy_rollup: dict

    # Control
    error: str | None

# ---------------------------------------------------------------------------
# Nodes
# ---------------------------------------------------------------------------
async def _node_load_chunks(state: AnalysisState) -> AnalysisState:
    db: AsyncSession = state["db"]
    document: Document = state["document"]
    progress: ProgressTracker | None = state.get("progress")

    if progress:
        await progress.start_step(STEP_LOAD_CHUNKS)

    loader = ChunkLoaderTool()
    chunks = await loader.load(db, document.id)

    if not chunks and document.content:
        # Fallback for legacy documents that only have document.content but
        # no DocumentChunks. Wrap the full content as a single synthetic chunk
        # so the rest of the pipeline can still operate.
        chunks = [
            ChunkRecord(
                id=document.id,  # not a real chunk id; never persisted
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

    # Cost guard: skip sections that won't yield useful insights.
    # - References / Acknowledgments are pure boilerplate.
    # - Very short sections (< _MIN_CHARS_FOR_LLM) get a heuristic-only insight
    #   without spending an LLM call.
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

    # Heuristic-only insights for skipped sections — no LLM cost. The
    # SectionInsightTool's heuristic_fallback path already handles this when
    # we pass it a stub LLM, so we just call its public API with a sentinel
    # provider that always raises; the tool then falls through to fallback.
    insights_llm = await asyncio.gather(
        *[analyse_one(s) for s in sections_for_llm]
    )
    insights_skipped = [
        tool._wrap_section(s, tool._heuristic_fallback(s))
        for s in sections_skipped
    ]

    # Re-merge in original section order so the FE renders sections sequentially
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
    """Single LLM call that returns BOTH the narrative synthesis AND the
    executive summary. Caches the summary into state['summary']."""
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
    """Derive legacy fields (key_findings, methodology, ...) from the
    structured section insights. This is rule-based — no extra LLM calls —
    and keeps the old API surface alive for the frontend.
    """
    if state.get("error"):
        return state

    insights: list[dict] = state.get("section_insights") or []
    synthesis: dict = state.get("narrative_synthesis") or {}

    rollup = _aggregate_legacy(insights, synthesis)
    return {**state, "legacy_rollup": rollup}


# ---------------------------------------------------------------------------
# Legacy field aggregation (rule-based)
# ---------------------------------------------------------------------------

def _aggregate_legacy(
    insights: list[dict], synthesis: dict
) -> dict[str, Any]:
    """Collapse per-section insights into the flat fields exposed by the API.

    Strategy is deliberately simple:
      - key_findings: top claims across sections (cap 10)
      - methodology: summary of the methodology section, if any
      - limitations: weaknesses + open_questions of the limitations section
                     plus overall_weaknesses from synthesis
      - future_work: open_questions of future_work section + knowledge_gaps
      - keywords: notable_terms (term names) across all sections (cap 20)
      - research_questions: union of section open_questions tagged as RQs
                            plus knowledge_gaps from synthesis (cap 7)
      - research_contribution: synthesis.novelty_vs_prior_work
      - critical_assessment: synthesis-level overall strengths/weaknesses
                             plus confidence
    """
    by_type: dict[str, list[dict]] = {}
    for s in insights:
        by_type.setdefault(s.get("section_type") or "other", []).append(s)

    # ── key_findings ─────────────────────────────────────────────────────────
    key_findings: list[str] = []
    for s in insights:
        for c in s.get("claims") or []:
            if not isinstance(c, dict):
                continue
            claim = (c.get("claim") or "").strip()
            if claim and claim not in key_findings:
                key_findings.append(claim)
    key_findings = key_findings[:10]

    # ── methodology ──────────────────────────────────────────────────────────
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

    # ── limitations ──────────────────────────────────────────────────────────
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

    # ── future_work ──────────────────────────────────────────────────────────
    future_work: list[str] = []
    for s in by_type.get("future_work", []):
        for q in s.get("open_questions") or []:
            if isinstance(q, str) and q not in future_work:
                future_work.append(q)
    for g in synthesis.get("knowledge_gaps") or []:
        if isinstance(g, str) and g not in future_work:
            future_work.append(g)
    future_work = future_work[:10]

    # ── keywords ─────────────────────────────────────────────────────────────
    keywords: list[str] = []
    for s in insights:
        for term in s.get("notable_terms") or []:
            if isinstance(term, dict):
                name = (term.get("term") or "").strip()
                if name and name.lower() not in {k.lower() for k in keywords}:
                    keywords.append(name)
    keywords = keywords[:20]

    # ── research_questions ───────────────────────────────────────────────────
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

    # ── critical_assessment ──────────────────────────────────────────────────
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


# ---------------------------------------------------------------------------
# Build LangGraph
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# AnalysisAgent
# ---------------------------------------------------------------------------

class AnalysisAgent:
    """Run the section-grounded analysis pipeline for a single document."""

    def __init__(
        self,
        db: AsyncSession,
        llm_provider: str | None = None,
        llm_model: str | None = None,
    ) -> None:
        self.db = db
        # Caller can pin a provider/model per-analysis. Falls back to
        # settings.PROVIDER / settings.MODEL_NAME when omitted.
        self.llm_provider = (llm_provider or settings.PROVIDER).lower()
        self.llm_model = llm_model or settings.MODEL_NAME

    # ── Public entry point ───────────────────────────────────────────────────

    async def run(self, analysis_id: UUID) -> DocumentAnalysis:
        analysis = await self._get_analysis(analysis_id)
        progress = ProgressTracker(self.db, analysis_id)

        try:
            try:
                await self._mark_running(analysis)
            except RuntimeError:
                # Already running or completed — let the caller skip silently
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
                return analysis

            try:
                await progress.start_step(STEP_PERSIST)
                await self._persist_result(analysis, final_state, llm)
                await progress.finish_step(STEP_PERSIST, "saved to DB")
                await progress.finalize("completed")
            except StaleDataError:
                # The analysis row was deleted (or its document was deleted
                # → cascade) while the pipeline was running. Drop the result
                # silently — the user already explicitly discarded it.
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

        except StaleDataError:
            await self.db.rollback()
            logger.warning(
                f"AnalysisAgent: analysis {analysis_id} was deleted during "
                f"run; aborting cleanly."
            )
        except Exception as e:
            # Any other failure: rollback FIRST so we can write the failure
            # marker without dragging a poisoned session along.
            await self.db.rollback()
            logger.error(f"AnalysisAgent: failed for analysis {analysis_id}: {e}")
            try:
                await progress.finalize("failed", str(e))
            except Exception:
                pass
            await self._mark_failed(analysis_id, str(e))
            raise

        return analysis

    # ── DB helpers ───────────────────────────────────────────────────────────

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
        """Mark an analysis as failed via a direct UPDATE.

        We use an explicit UPDATE statement (rather than mutating the ORM
        object and committing) for two reasons:

        1. The ORM object may be stale — the row could have been deleted by
           the user while the pipeline was running. SQLAlchemy raises
           ``StaleDataError`` on commit when a versioned UPDATE matches 0
           rows. Direct UPDATE simply does nothing in that case.
        2. Coming from an except branch, the session may be in a
           pending-rollback state. UPDATE on a fresh statement after rollback
           is the safest path — see https://sqlalche.me/e/20/7s2a.
        """
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
                # Row was deleted between status=RUNNING and now.
                logger.warning(
                    f"AnalysisAgent: tried to mark analysis {analysis_id} "
                    f"as FAILED but row was already gone."
                )
        except Exception as e:
            # Don't shadow the original exception with a write-failure.
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

        # Section-level fields (new pipeline)
        analysis.document_outline = outline or None
        analysis.section_insights = section_insights or None
        analysis.narrative_synthesis = synthesis or None

        # Executive summary
        analysis.summary = state.get("summary")

        # Legacy fields derived from section insights (backward compatibility)
        analysis.key_findings = rollup.get("key_findings") or None
        analysis.methodology = rollup.get("methodology")
        analysis.limitations = rollup.get("limitations") or None
        analysis.future_work = rollup.get("future_work") or None
        analysis.keywords = rollup.get("keywords") or None
        analysis.research_questions = rollup.get("research_questions") or None
        analysis.research_contribution = rollup.get("research_contribution")
        analysis.critical_assessment = rollup.get("critical_assessment")

        # Structural fields kept for the API but built from the outline so the
        # response stays consistent with section_insights.
        analysis.sections = [
            {
                "index": s.get("section_index"),
                "title": s.get("title"),
                "type": s.get("section_type"),
                "summary": s.get("summary"),
            }
            for s in section_insights
        ] or None

        # Legacy fields no longer populated by the new pipeline — set to None
        # so stale data from a prior run does not leak through.
        analysis.extracted_entities = None
        analysis.extracted_tables = None
        analysis.relationships = None
        analysis.metrics = None
        analysis.sentiment = None
        analysis.evidence_quality = None
        analysis.citation_context = None

        # Status
        analysis.status = AnalysisStatus.COMPLETED.value
        analysis.completed_at = datetime.now(timezone.utc)
        analysis.processed_by = f"{self.llm_provider}:{llm.get_model_name()}"

        await self.db.commit()
        await self.db.refresh(analysis)
