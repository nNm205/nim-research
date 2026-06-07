"""SynthesisAgent — LLM-driven cross-document report writer.

Pipeline (LangGraph):

  START
    → load_context        (deterministic — gather Project + Documents + Analyses)
    → build_outline       (1 LLM call — design cross-document outline)
    → synthesize_narrative (1 LLM call — write per-section narrative with [n] cites)
    → generate_summary    (1 LLM call — executive summary + key takeaways)
    → build_citations     (deterministic — APA + BibTeX)
    → render_report       (deterministic — compose markdown + HTML)
    → persist             (write to Report.content / html_content / synthesis_metadata)
  END

Total LLM calls per report ≈ 3.

The agent OVERWRITES ``Report.content`` and ``Report.html_content`` with the
synthesised version. The previous deterministic content is preserved in
``Report.synthesis_metadata.original_template_md`` so an FE rollback button
can restore it.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, TypedDict
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.exc import StaleDataError

from app.agents.tools.synthesis import (
    CitationManagerTool,
    ExecutiveSummaryGeneratorTool,
    NarrativeSynthesizerTool,
    OutlineBuilderTool,
    ReportComposerTool,
    SynthesisContext,
    SynthesisContextLoaderTool,
)
from app.agents.tools.synthesis.report_composer import collect_narrative_text
from app.agents.tools.synthesis.progress_tracker import (
    STEP_BUILD_CITATIONS,
    STEP_BUILD_OUTLINE,
    STEP_GENERATE_SUMMARY,
    STEP_LOAD_CONTEXT,
    STEP_PERSIST,
    STEP_RENDER_REPORT,
    STEP_SYNTHESIZE_NARRATIVE,
    SynthesisProgressTracker,
)
from app.config import settings
from app.models.llm_providers.base import LLMProvider
from app.models.llm_providers.factory import LLMFactory
from app.models.llm_providers.types import ProviderType
from app.models.project import Project
from app.models.report import Report
from app.utils.constants import SynthesisStatus
from app.utils.logger import logger


__all__ = ["SynthesisAgent"]


# ---------------------------------------------------------------------------
# LangGraph state
# ---------------------------------------------------------------------------
class SynthesisState(TypedDict, total=False):
    report_id: UUID
    report: Report
    project: Project
    db: AsyncSession
    llm: LLMProvider
    progress: SynthesisProgressTracker

    context: SynthesisContext
    outline: dict
    narrative: dict
    summary: dict
    citations: dict
    markdown: str
    html: str

    error: str | None


# ---------------------------------------------------------------------------
# Pipeline nodes
# ---------------------------------------------------------------------------

async def _node_load_context(state: SynthesisState) -> SynthesisState:
    progress = state["progress"]
    await progress.start_step(STEP_LOAD_CONTEXT)

    report: Report = state["report"]
    project: Project = state["project"]

    included = None
    if report.included_documents:
        try:
            included = [UUID(str(x)) for x in report.included_documents]
        except Exception:
            included = None

    loader = SynthesisContextLoaderTool()
    context = await loader.load(
        db=state["db"],
        project=project,
        report_title=report.title,
        report_type=report.report_type,
        included_documents=included,
    )

    if not context.documents:
        msg = "Project has no documents to synthesise"
        await progress.fail_step(STEP_LOAD_CONTEXT, msg)
        return {**state, "error": msg}

    n_with_analysis = len(context.documents_with_analysis)
    await progress.finish_step(
        STEP_LOAD_CONTEXT,
        f"{len(context.documents)} tài liệu, {n_with_analysis} đã phân tích",
    )
    return {**state, "context": context}


async def _node_build_outline(state: SynthesisState) -> SynthesisState:
    if state.get("error"):
        return state

    progress = state["progress"]
    await progress.start_step(STEP_BUILD_OUTLINE)

    builder = OutlineBuilderTool()
    outline = await builder.build(state["context"], state["llm"])

    n_sections = len(outline.get("sections") or [])
    await progress.finish_step(
        STEP_BUILD_OUTLINE,
        f"{n_sections} phần",
    )
    return {**state, "outline": outline}


async def _node_synthesize_narrative(
    state: SynthesisState,
) -> SynthesisState:
    if state.get("error"):
        return state

    progress = state["progress"]
    await progress.start_step(STEP_SYNTHESIZE_NARRATIVE)

    tool = NarrativeSynthesizerTool()
    narrative = await tool.synthesize(
        context=state["context"],
        outline=state["outline"],
        llm=state["llm"],
    )

    n_written = sum(
        1
        for s in (narrative.get("sections") or {}).values()
        if isinstance(s, dict) and (s.get("body") or "").strip()
    )
    await progress.finish_step(
        STEP_SYNTHESIZE_NARRATIVE,
        f"{n_written} phần đã viết",
    )
    return {**state, "narrative": narrative}


async def _node_generate_summary(state: SynthesisState) -> SynthesisState:
    if state.get("error"):
        return state

    progress = state["progress"]
    await progress.start_step(STEP_GENERATE_SUMMARY)

    outline = state["outline"]
    narrative_text = collect_narrative_text(
        state["narrative"], outline.get("sections") or []
    )

    tool = ExecutiveSummaryGeneratorTool()
    summary = await tool.generate(
        report_title=outline.get("title") or state["report"].title,
        thesis=outline.get("thesis") or "",
        narrative_text=narrative_text,
        llm=state["llm"],
    )

    msg = "tóm tắt đã sinh" if summary.get("executive_summary") else "không có tóm tắt"
    await progress.finish_step(STEP_GENERATE_SUMMARY, msg)
    return {**state, "summary": summary}


async def _node_build_citations(state: SynthesisState) -> SynthesisState:
    if state.get("error"):
        return state

    progress = state["progress"]
    await progress.start_step(STEP_BUILD_CITATIONS)

    # Collect every cited index across all sections.
    cited: set[int] = set()
    sections_map = (state.get("narrative") or {}).get("sections") or {}
    for entry in sections_map.values():
        if isinstance(entry, dict):
            for n in entry.get("documents_cited") or []:
                if isinstance(n, int):
                    cited.add(n)

    tool = CitationManagerTool()
    citations = tool.build(state["context"], cited)

    await progress.finish_step(
        STEP_BUILD_CITATIONS,
        f"{len(citations.get('entries') or [])} trích dẫn",
    )
    return {**state, "citations": citations}


async def _node_render_report(state: SynthesisState) -> SynthesisState:
    if state.get("error"):
        return state

    progress = state["progress"]
    await progress.start_step(STEP_RENDER_REPORT)

    composer = ReportComposerTool()
    provider = (state.get("progress")._state if state.get("progress") else {}).get("provider")
    model = (state.get("progress")._state if state.get("progress") else {}).get("model")
    markdown, html = composer.compose(
        context=state["context"],
        outline=state["outline"],
        narrative=state["narrative"],
        summary=state["summary"],
        citations=state["citations"],
        provider=provider,
        model=model,
    )

    await progress.finish_step(
        STEP_RENDER_REPORT,
        f"md={len(markdown)} chars, html={len(html)} chars",
    )
    return {**state, "markdown": markdown, "html": html}


# ---------------------------------------------------------------------------
# Build LangGraph
# ---------------------------------------------------------------------------

def _build_graph():
    from langgraph.graph import END, StateGraph

    graph = StateGraph(SynthesisState)
    graph.add_node("load_context", _node_load_context)
    graph.add_node("build_outline", _node_build_outline)
    graph.add_node("synthesize_narrative", _node_synthesize_narrative)
    graph.add_node("generate_summary", _node_generate_summary)
    graph.add_node("build_citations", _node_build_citations)
    graph.add_node("render_report", _node_render_report)

    graph.set_entry_point("load_context")
    graph.add_edge("load_context", "build_outline")
    graph.add_edge("build_outline", "synthesize_narrative")
    graph.add_edge("synthesize_narrative", "generate_summary")
    graph.add_edge("generate_summary", "build_citations")
    graph.add_edge("build_citations", "render_report")
    graph.add_edge("render_report", END)

    return graph.compile()


_GRAPH = _build_graph()


# ---------------------------------------------------------------------------
# SynthesisAgent
# ---------------------------------------------------------------------------

class SynthesisAgent:
    """Run the cross-document synthesis pipeline for a single Report."""

    def __init__(
        self,
        db: AsyncSession,
        llm_provider: str | None = None,
        llm_model: str | None = None,
    ) -> None:
        self.db = db
        self.llm_provider = (llm_provider or settings.PROVIDER).lower()
        self.llm_model = llm_model or settings.MODEL_NAME

    # ── Public entry point ──────────────────────────────────────────────

    async def run(self, report_id: UUID) -> Report:
        report = await self._get_report(report_id)
        progress = SynthesisProgressTracker(self.db, report_id)

        try:
            try:
                await self._mark_running(report)
            except RuntimeError:
                # Already running — caller skip silently
                return report

            project = await self._get_project(report.project_id)

            try:
                provider_type = ProviderType[self.llm_provider.upper()]
            except KeyError:
                raise ValueError(
                    f"Unknown LLM provider {self.llm_provider!r}. "
                    f"Valid: {[p.value for p in ProviderType]}"
                )
            llm = LLMFactory.create_provider(
                provider_type, model=self.llm_model
            )
            logger.info(
                f"SynthesisAgent: using provider={self.llm_provider} "
                f"model={llm.get_model_name()} for report {report.id}"
            )

            await progress.init(
                provider=self.llm_provider,
                model=llm.get_model_name(),
            )

            initial_state: SynthesisState = {
                "report_id": report_id,
                "report": report,
                "project": project,
                "db": self.db,
                "llm": llm,
                "progress": progress,
            }

            final_state: SynthesisState = await _GRAPH.ainvoke(initial_state)

            if final_state.get("error"):
                await progress.finalize("failed", final_state["error"])
                await self._mark_failed(report_id, final_state["error"])
                await self._notify(report, success=False, error=final_state["error"])
                return report

            try:
                await progress.start_step(STEP_PERSIST)
                await self._persist_result(report, final_state, llm)
                await progress.finish_step(STEP_PERSIST, "đã ghi vào CSDL")
                await progress.finalize("completed")
            except StaleDataError:
                await self.db.rollback()
                logger.warning(
                    f"SynthesisAgent: report {report_id} disappeared during run; "
                    f"result discarded."
                )
                return report

            logger.success(
                f"SynthesisAgent: completed report {report.id}"
            )
            await self._notify(report, success=True)

        except StaleDataError:
            await self.db.rollback()
            logger.warning(
                f"SynthesisAgent: report {report_id} was deleted during run; "
                f"aborting cleanly."
            )
        except Exception as e:
            await self.db.rollback()
            logger.error(f"SynthesisAgent: failed for report {report_id}: {e}")
            try:
                await progress.finalize("failed", str(e))
            except Exception:
                pass
            await self._mark_failed(report_id, str(e))
            await self._notify(report, success=False, error=str(e))
            raise

        return report

    # ── DB helpers ──────────────────────────────────────────────────────

    async def _get_report(self, report_id: UUID) -> Report:
        result = await self.db.execute(
            select(Report).where(Report.id == report_id)
        )
        report = result.scalar_one_or_none()
        if report is None:
            raise ValueError(f"Report not found: {report_id}")
        return report

    async def _get_project(self, project_id: UUID) -> Project:
        result = await self.db.execute(
            select(Project).where(Project.id == project_id)
        )
        project = result.scalar_one_or_none()
        if project is None:
            raise ValueError(f"Project not found: {project_id}")
        return project

    async def _mark_running(self, report: Report) -> None:
        if report.synthesis_status == SynthesisStatus.RUNNING.value:
            logger.info(
                f"SynthesisAgent: skipping duplicate run for report {report.id}"
            )
            raise RuntimeError("Synthesis already running")

        report.synthesis_status = SynthesisStatus.RUNNING.value
        report.synthesis_started_at = datetime.now(timezone.utc)
        report.synthesis_completed_at = None
        report.synthesis_error = None
        await self.db.commit()
        await self.db.refresh(report)
        logger.info(
            f"SynthesisAgent: report {report.id} synthesis_status → RUNNING"
        )

    async def _mark_failed(
        self, report_id: UUID, error_message: str
    ) -> None:
        try:
            stmt = (
                update(Report)
                .where(Report.id == report_id)
                .values(
                    synthesis_status=SynthesisStatus.FAILED.value,
                    synthesis_error=(error_message or "")[:1000],
                    synthesis_completed_at=datetime.now(timezone.utc),
                )
            )
            await self.db.execute(stmt)
            await self.db.commit()
        except Exception as e:
            await self.db.rollback()
            logger.error(
                f"SynthesisAgent: failed to record FAILED status for "
                f"{report_id}: {e}"
            )

    async def _persist_result(
        self,
        report: Report,
        state: SynthesisState,
        llm: LLMProvider,
    ) -> None:
        outline = state.get("outline") or {}
        narrative = state.get("narrative") or {}
        summary = state.get("summary") or {}
        citations = state.get("citations") or {}
        markdown = state.get("markdown") or ""
        html = state.get("html") or ""

        # Preserve the existing template-rendered content for rollback.
        original_md = report.content
        original_html = report.html_content

        # Overwrite report content with the synthesised version.
        report.content = markdown
        report.html_content = html

        report.synthesis_status = SynthesisStatus.COMPLETED.value
        report.synthesis_completed_at = datetime.now(timezone.utc)
        report.synthesis_error = None

        # Compact metadata snapshot — full narrative + outline + citations
        # so the FE / regen flow has everything it needs.
        report.synthesis_metadata = {
            "provider": self.llm_provider,
            "model": llm.get_model_name(),
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "outline": outline,
            "narrative": narrative,
            "summary": summary,
            "citations_apa": citations.get("apa_text"),
            "citations_bibtex": citations.get("bibtex_text"),
            "citation_entries": citations.get("entries"),
            "original_template_md": original_md,
            "original_template_html": original_html,
        }

        await self.db.commit()
        await self.db.refresh(report)

    # ── Notifications ───────────────────────────────────────────────────

    async def _notify(
        self,
        report: Report,
        *,
        success: bool,
        error: str | None = None,
    ) -> None:
        from app.database.session import AsyncSessionLocal as _Session
        from app.services.notification_service import (
            CATEGORY_SYNTHESIS,
            TYPE_ERROR,
            TYPE_SUCCESS,
            create_notification_async,
        )

        try:
            async with _Session() as s:
                user_id = await s.scalar(
                    select(Project.user_id).where(
                        Project.id == report.project_id
                    )
                )
            if user_id is None:
                return

            title = (
                "Synthesis báo cáo hoàn thành"
                if success
                else "Synthesis báo cáo thất bại"
            )
            report_title = (report.title or "")[:120] or "Báo cáo"
            if success:
                message = f"'{report_title}' đã được tổng hợp xong bằng LLM."
                ntype = TYPE_SUCCESS
            else:
                message = (
                    f"'{report_title}': {(error or 'lỗi không xác định')[:200]}"
                )
                ntype = TYPE_ERROR

            await create_notification_async(
                user_id=user_id,
                title=title,
                message=message,
                notification_type=ntype,
                category=CATEGORY_SYNTHESIS,
                entity_id=report.id,
                entity_kind="report",
                project_id=report.project_id,
            )
        except Exception as e:
            logger.warning(
                f"SynthesisAgent: failed to write notification for "
                f"{report.id}: {e}"
            )
