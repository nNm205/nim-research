"""AutoResearchService — chain search → ingest → analyse in one shot.

The "Nghiên cứu tự động" feature: user enters a topic, picks how many
papers to ingest and which LLM to analyse with, then walks away. The
service orchestrates three existing agents in sequence:

  1. ResearchAgent — query arXiv / Google Scholar / Semantic Scholar
     and persist SearchResult rows.
  2. DocumentIngestionService.ingest_from_search_result — for the top-N
     results, locate a PDF (Unpaywall / arXiv-derived / scrape) and
     ingest it (or fall back to HTML) into the project as a Document.
  3. AnalysisAgent — for each newly-ingested Document, run the
     section-grounded analysis pipeline.

State is tracked using existing tables:
  - The ResearchSession row records the search stage (status / error)
  - Each Document record marks an ingest success
  - Each DocumentAnalysis row marks an analysis stage

The HTTP endpoint returns the ResearchSession ID immediately so the FE
can open the research history tab and watch progress unfold. Errors at
any stage are logged but never abort the rest of the pipeline — a single
failed PDF download does not stop the other documents from being
analysed.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import update
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession  # noqa: F401  used for type hints

from app.agents.analysis_agent import AnalysisAgent
from app.agents.qa_agent import QualityAssuranceAgent
from app.agents.research_agent import ResearchAgent
from app.agents.synthesis_agent import SynthesisAgent
from app.agents.tools.research.progress_tracker import (
    ResearchProgressTracker,
    STAGE_ANALYSE,
    STAGE_INGEST,
    STAGE_QA,
    STAGE_REPORT,
    STAGE_SAVE,
    STAGE_SYNTHESIZE,
    build_auto_stages,
)
from app.database.session import AsyncSessionLocal
from app.models.analysis import DocumentAnalysis
from app.models.document import Document  # noqa: F401  imported for ORM resolution
from app.models.project import Project
from app.models.report import Report
from app.models.research import ResearchSession, SearchResult
from app.schemas.report import ReportCreate
from app.services.document_ingestion_service import (
    DocumentIngestionService,
    IngestSkipped,
    NoAcademicPdfError,
    NonAcademicSourceError,
    PdfIngestError,
)
from app.services.report_service import create_report
from app.utils.constants import AnalysisStatus, ReportType, ResearchStatus
from app.utils.logger import logger


# Hard caps to keep cost predictable. Free-tier LLM quota is the binding
# constraint for analysis fan-out.
_MAX_DOCS_TO_INGEST = 5
_MAX_DOCS_TO_ANALYSE = 5


# Strong refs to fire-and-forget tasks. asyncio's event loop only keeps
# weak references to tasks; without this set the GC can collect and
# cancel the coroutine mid-run, which leaves the session stuck at
# status='running' forever — the exact symptom of "thanh tiến trình vẫn
# hiển thị sau khi phiên đã kết thúc". See
# https://docs.python.org/3/library/asyncio-task.html#asyncio.create_task
_BACKGROUND_TASKS: set[asyncio.Task] = set()


def _track(task: asyncio.Task) -> asyncio.Task:
    """Hold a strong reference to ``task`` until it completes."""
    _BACKGROUND_TASKS.add(task)
    task.add_done_callback(_BACKGROUND_TASKS.discard)
    return task


class AutoResearchService:
    """Orchestrate search → ingest → analyse for a single user request."""

    async def dispatch(
        self,
        research_session_id: UUID,
        max_documents: int,
        embedding_provider: str | None,
        embedding_model: str | None,
        llm_provider: str | None,
        llm_model: str | None,
        *,
        auto_report: bool = False,
        auto_synthesize: bool = False,
        auto_qa: bool = False,
        report_type: str | None = None,
    ) -> None:
        """Schedule the orchestration as an asyncio background task.

        Returns immediately so the route handler can respond to the FE.
        """
        _track(
            asyncio.create_task(
                self._run_in_background(
                    research_session_id=research_session_id,
                    max_documents=max_documents,
                    embedding_provider=embedding_provider,
                    embedding_model=embedding_model,
                    llm_provider=llm_provider,
                    llm_model=llm_model,
                    auto_report=auto_report,
                    auto_synthesize=auto_synthesize,
                    auto_qa=auto_qa,
                    report_type=report_type,
                )
            )
        )
        logger.info(
            f"AutoResearch: dispatched session={research_session_id} "
            f"max_documents={max_documents} llm={llm_provider}/{llm_model} "
            f"report={auto_report} synthesize={auto_synthesize} qa={auto_qa}"
        )

    async def _run_in_background(
        self,
        *,
        research_session_id: UUID,
        max_documents: int,
        embedding_provider: str | None,
        embedding_model: str | None,
        llm_provider: str | None,
        llm_model: str | None,
        auto_report: bool = False,
        auto_synthesize: bool = False,
        auto_qa: bool = False,
        report_type: str | None = None,
    ) -> None:
        max_documents = max(1, min(max_documents, _MAX_DOCS_TO_INGEST))

        # Synthesis and QA implicitly require a Report — silently drop
        # them if the user disabled report creation. Avoids running
        # downstream agents against a non-existent target.
        if not auto_report:
            auto_synthesize = False
            auto_qa = False

        # The tracker writes to ``research_sessions.progress`` — needs a
        # dedicated session because it persists state across stages while
        # the actual stage code uses fresh sessions per call. Holding one
        # connection open just for the tracker is fine because Supavisor
        # is fine with idle connections inside transaction-mode pooling
        # as long as we don't keep an open transaction open between
        # writes (the tracker commits on every flush).
        tracker_db = AsyncSessionLocal()
        try:
            try:
                await self._run_pipeline(
                    tracker_db=tracker_db,
                    research_session_id=research_session_id,
                    max_documents=max_documents,
                    embedding_provider=embedding_provider,
                    embedding_model=embedding_model,
                    llm_provider=llm_provider,
                    llm_model=llm_model,
                    auto_report=auto_report,
                    auto_synthesize=auto_synthesize,
                    auto_qa=auto_qa,
                    report_type=report_type,
                )
            except BaseException as e:
                # Catch BaseException (not just Exception) so even a
                # CancelledError from a GC race or shutdown gets a
                # chance to flip the session into a terminal state.
                # Without this, an unexpected crash would leave the
                # session stuck at status='running' forever and the FE
                # progress bar would never go away.
                logger.exception(
                    f"AutoResearch: pipeline crashed unexpectedly for "
                    f"{research_session_id}: {e!r}"
                )
                try:
                    await self._mark_session_terminal(
                        research_session_id, "failed",
                        error=f"Pipeline crashed: {type(e).__name__}",
                    )
                except Exception as mark_err:
                    logger.error(
                        f"AutoResearch: also failed to mark session "
                        f"{research_session_id} as failed after crash: "
                        f"{mark_err}"
                    )
                # Re-raise hard interrupts (Ctrl+C / SystemExit) so the
                # process can shut down cleanly. Cancellation from the
                # event-loop side is allowed to swallow because we've
                # already recorded the failure on the row.
                import asyncio as _asyncio
                if isinstance(e, (KeyboardInterrupt, SystemExit)):
                    raise
                if not isinstance(e, (Exception, _asyncio.CancelledError)):
                    raise
        finally:
            try:
                await tracker_db.close()
            except Exception:
                pass

    async def _run_pipeline(
        self,
        *,
        tracker_db,
        research_session_id: UUID,
        max_documents: int,
        embedding_provider: str | None,
        embedding_model: str | None,
        llm_provider: str | None,
        llm_model: str | None,
        auto_report: bool = False,
        auto_synthesize: bool = False,
        auto_qa: bool = False,
        report_type: str | None = None,
    ) -> None:
        """The pipeline body itself — extracted so the caller can wrap it
        in a top-level safety net that always lands the session in a
        terminal state."""
        # Build the stage list dynamically so the FE stepper renders the
        # exact sequence we're about to run.
        stages = build_auto_stages(
            with_report=auto_report,
            with_synthesis=auto_synthesize,
            with_qa=auto_qa,
        )
        tracker = ResearchProgressTracker(
            tracker_db, research_session_id, mode="auto", stages=stages,
        )
        # Pull the query for the init message.
        session_row = await tracker_db.scalar(
            select(ResearchSession).where(
                ResearchSession.id == research_session_id
            )
        )
        await tracker.init(query=session_row.query if session_row else None)

        project_id = session_row.project_id if session_row else None

        # ── Stage 1: search ───────────────────────────────────────────
        try:
            await self._stage_search(
                research_session_id=research_session_id,
                tracker=tracker,
            )
        except Exception as e:
            logger.error(
                f"AutoResearch: search stage failed for "
                f"{research_session_id}: {e}"
            )
            await tracker.finalize("failed", f"Tìm kiếm thất bại: {e}")
            await self._mark_session_terminal(
                research_session_id, "failed",
                error=f"Tìm kiếm thất bại: {e}",
            )
            return

        # ── Stage 2: ingest top-N results ─────────────────────────────
        try:
            await tracker.start_stage(
                STAGE_INGEST,
                detail=f"Nạp top {max_documents} tài liệu",
            )
            document_ids = await self._stage_ingest(
                research_session_id=research_session_id,
                project_id=project_id,
                max_documents=max_documents,
                embedding_provider=embedding_provider,
                embedding_model=embedding_model,
                tracker=tracker,
            )
            await tracker.finish_stage(
                STAGE_INGEST,
                message=f"{len(document_ids)} tài liệu thành công",
            )
        except Exception as e:
            logger.error(
                f"AutoResearch: ingest stage failed for "
                f"{research_session_id}: {e}"
            )
            await tracker.fail_stage(STAGE_INGEST, str(e))
            await tracker.finalize("failed", f"Nạp tài liệu thất bại: {e}")
            await self._mark_session_terminal(
                research_session_id, "failed",
                error=f"Nạp tài liệu thất bại: {e}",
            )
            return

        if not document_ids:
            logger.warning(
                f"AutoResearch: no documents ingested for "
                f"{research_session_id}; skipping analysis"
            )
            await tracker.finalize(
                "completed",
                "Không có tài liệu nào ingest thành công — bỏ qua phân tích",
            )
            # Still mark COMPLETED — the search stage finished and
            # the user has search results, just nothing to analyse.
            await self._mark_session_terminal(
                research_session_id, "completed"
            )
            return

        # ── Stage 3: analyse each ingested document ───────────────────
        try:
            await tracker.start_stage(
                STAGE_ANALYSE,
                detail=f"Phân tích {len(document_ids)} tài liệu",
            )
            await self._stage_analyse(
                document_ids=document_ids,
                llm_provider=llm_provider,
                llm_model=llm_model,
                tracker=tracker,
            )
            await tracker.finish_stage(STAGE_ANALYSE)
        except Exception as e:
            logger.error(
                f"AutoResearch: analysis stage failed for "
                f"{research_session_id}: {e}"
            )
            await tracker.fail_stage(STAGE_ANALYSE, str(e))
            await tracker.finalize("failed", f"Phân tích thất bại: {e}")
            await self._mark_session_terminal(
                research_session_id, "failed",
                error=f"Phân tích thất bại: {e}",
            )
            return

        # ── Stage 4 (optional): create Report ─────────────────────────
        report_id: UUID | None = None
        if auto_report and project_id is not None:
            try:
                await tracker.start_stage(
                    STAGE_REPORT,
                    detail="Tạo báo cáo từ Documents + Analysis",
                )
                report_id = await self._stage_report(
                    project_id=project_id,
                    research_query=session_row.query if session_row else None,
                    report_type=report_type,
                    document_ids=document_ids,
                )
                await tracker.finish_stage(
                    STAGE_REPORT,
                    message=f"Báo cáo được tạo (id={str(report_id)[:8]}...)",
                )
            except Exception as e:
                # Don't abort the whole pipeline — log and skip the
                # remaining add-ons. The user still has Documents +
                # Analyses; they can create a report manually later.
                logger.error(
                    f"AutoResearch: report stage failed for "
                    f"{research_session_id}: {e}"
                )
                await tracker.fail_stage(STAGE_REPORT, str(e))
                report_id = None

        # ── Stage 5 (optional): synthesise the report with LLM ────────
        if auto_synthesize and report_id is not None:
            try:
                await tracker.start_stage(
                    STAGE_SYNTHESIZE,
                    detail="LLM viết lại narrative xuyên tài liệu",
                )
                await self._stage_synthesize(
                    report_id=report_id,
                    llm_provider=llm_provider,
                    llm_model=llm_model,
                )
                await tracker.finish_stage(STAGE_SYNTHESIZE)
            except Exception as e:
                logger.error(
                    f"AutoResearch: synthesis stage failed for "
                    f"{research_session_id}: {e}"
                )
                await tracker.fail_stage(STAGE_SYNTHESIZE, str(e))
                # Synthesis failed but the template Report still exists
                # — let the pipeline continue to QA on the template body.

        # ── Stage 6 (optional): QA the report ─────────────────────────
        if auto_qa and report_id is not None:
            try:
                await tracker.start_stage(
                    STAGE_QA,
                    detail="Kiểm format / citation / fact / grammar",
                )
                qa_score = await self._stage_qa(
                    report_id=report_id,
                    llm_provider=llm_provider,
                    llm_model=llm_model,
                )
                msg = (
                    f"QA điểm {qa_score}/100"
                    if qa_score is not None
                    else "QA hoàn tất"
                )
                await tracker.finish_stage(STAGE_QA, message=msg)
            except Exception as e:
                logger.error(
                    f"AutoResearch: qa stage failed for "
                    f"{research_session_id}: {e}"
                )
                await tracker.fail_stage(STAGE_QA, str(e))

        # ── Stage 7: done ─────────────────────────────────────────────
        await tracker.start_stage(
            STAGE_SAVE,
            detail="Hoàn tất pipeline",
        )
        await tracker.finish_stage(STAGE_SAVE)
        completion_msg = f"{len(document_ids)} tài liệu được phân tích"
        if report_id is not None:
            completion_msg += " + báo cáo đã sinh"
        await tracker.finalize("completed", completion_msg)
        await self._mark_session_terminal(
            research_session_id, "completed"
        )

    async def _mark_session_terminal(
        self,
        research_session_id: UUID,
        status: str,  # "completed" | "failed"
        error: str | None = None,
    ) -> None:
        """Flip the ResearchSession row's status to a terminal state.

        ResearchAgent only marks COMPLETED for standalone search; in
        auto-research mode it leaves the row as RUNNING because more
        stages (ingest + analyse) are still pending. This method is
        the orchestrator's chance to write the final status, including
        when an intermediate stage failed.

        Notifications are written here too — every terminal path goes
        through this method, so the user gets exactly one bell alert
        per pipeline run regardless of which stage finished it.
        """
        target = (
            ResearchStatus.COMPLETED.value
            if status == "completed"
            else ResearchStatus.FAILED.value
        )
        project_id = None
        query: str | None = None
        try:
            async with AsyncSessionLocal() as db:
                # We need ``project_id`` + ``query`` for the notification.
                # Fetch them BEFORE the update so we don't have to read
                # back from the row we're about to update.
                row = await db.scalar(
                    select(ResearchSession).where(
                        ResearchSession.id == research_session_id
                    )
                )
                if row is not None:
                    project_id = row.project_id
                    query = row.query

                stmt = (
                    update(ResearchSession)
                    .where(ResearchSession.id == research_session_id)
                    .values(
                        status=target,
                        completed_at=datetime.now(timezone.utc),
                        **({"error_message": error[:1000]} if error else {}),
                    )
                )
                await db.execute(stmt)
                await db.commit()
        except Exception as e:
            logger.warning(
                f"AutoResearch: failed to flip ResearchSession "
                f"{research_session_id} status → {status}: {e}"
            )
            return

        # Best-effort notification. Errors are swallowed inside
        # ``create_notification_async`` so we don't need a try/except.
        await self._notify_done(
            research_session_id=research_session_id,
            project_id=project_id,
            query=query,
            success=(status == "completed"),
            error=error,
        )

    async def _notify_done(
        self,
        *,
        research_session_id: UUID,
        project_id: UUID | None,
        query: str | None,
        success: bool,
        error: str | None,
    ) -> None:
        from app.models.project import Project
        from app.services.notification_service import (
            CATEGORY_AUTO_RESEARCH,
            TYPE_ERROR,
            TYPE_SUCCESS,
            create_notification_async,
        )

        if project_id is None:
            return
        try:
            async with AsyncSessionLocal() as db:
                user_id = await db.scalar(
                    select(Project.user_id).where(
                        Project.id == project_id
                    )
                )
            if user_id is None:
                return

            q = (query or "")[:120]
            if success:
                title = "Nghiên cứu tự động hoàn thành"
                message = (
                    f"'{q}' — pipeline (tìm kiếm + nạp + phân tích) đã chạy xong."
                    if q
                    else "Pipeline (tìm kiếm + nạp + phân tích) đã chạy xong."
                )
                ntype = TYPE_SUCCESS
            else:
                title = "Nghiên cứu tự động thất bại"
                message = (
                    f"'{q}': {(error or 'lỗi không xác định')[:200]}"
                    if q
                    else (error or "lỗi không xác định")[:200]
                )
                ntype = TYPE_ERROR

            await create_notification_async(
                user_id=user_id,
                title=title,
                message=message,
                notification_type=ntype,
                category=CATEGORY_AUTO_RESEARCH,
                entity_id=research_session_id,
                entity_kind="research",
                project_id=project_id,
            )
        except Exception as e:
            logger.warning(
                f"AutoResearch: failed to write notification for "
                f"{research_session_id}: {e}"
            )

    # ── Stage 1: search ─────────────────────────────────────────────────────

    async def _stage_search(
        self,
        research_session_id: UUID,
        *,
        tracker: ResearchProgressTracker,
    ) -> None:
        # ResearchAgent will run STAGE_SEARCH + STAGE_SAVE inside its own
        # session. We pass our auto-mode tracker so its stage events show
        # up in the same progress feed.
        async with AsyncSessionLocal() as db:
            agent = ResearchAgent(db, tracker=tracker)
            await agent.run(research_session_id)

    # ── Stage 2: ingest top-N results ───────────────────────────────────────

    async def _stage_ingest(
        self,
        *,
        research_session_id: UUID,
        project_id: UUID | None,
        max_documents: int,
        embedding_provider: str | None,
        embedding_model: str | None,
        tracker: ResearchProgressTracker,
    ) -> list[UUID]:
        """Ingest the top-ranked academic search results.

        Pulls more results than ``max_documents`` from the DB so we can
        skip non-academic ones and missing-PDF ones without dropping
        below the user's requested document count. Stops as soon as we
        have ``max_documents`` successful ingests OR exhaust the search
        results.
        """
        # Over-fetch: assume up to 50% of search results may be skipped
        # (non-academic source or no PDF). Capped at 3× to avoid wasting
        # work on a query that's mostly low-quality.
        candidate_limit = min(max_documents * 3, _MAX_DOCS_TO_INGEST * 3)
        async with AsyncSessionLocal() as db:
            stmt = (
                select(SearchResult)
                .where(SearchResult.research_session_id == research_session_id)
                .where(SearchResult.document_id.is_(None))
                .order_by(SearchResult.rank.asc().nulls_last())
                .limit(candidate_limit)
            )
            results = list((await db.execute(stmt)).scalars().all())

        if not results or project_id is None:
            logger.info(
                f"AutoResearch: research session {research_session_id} "
                f"yielded zero ingestable results"
            )
            return []

        logger.info(
            f"AutoResearch: scanning up to {len(results)} candidates for "
            f"top {max_documents} academic-PDF ingests "
            f"(session {research_session_id})"
        )

        document_ids: list[UUID] = []
        skipped_count = 0
        seen_ids = 0

        for result in results:
            if len(document_ids) >= max_documents:
                break
            seen_ids += 1
            # Show "x/N" against the goal, not the candidate pool, so
            # the user sees progress toward the target they configured.
            await tracker.update_item_progress(
                done=len(document_ids),
                total=max_documents,
                current_title=result.title,
            )
            async with AsyncSessionLocal() as db:
                sr = await db.scalar(
                    select(SearchResult).where(SearchResult.id == result.id)
                )
                if sr is None or sr.document_id is not None:
                    continue
                service = DocumentIngestionService(
                    db,
                    embedding_provider=embedding_provider,
                    embedding_model=embedding_model,
                )
                try:
                    document = await service.ingest_from_search_result(
                        project_id=project_id,
                        search_result=sr,
                    )
                    sr.document_id = document.id
                    await db.commit()
                    document_ids.append(document.id)
                    await tracker.log(
                        f"✓ Đã nạp PDF: {result.title[:80]}",
                        level="done",
                    )
                except NonAcademicSourceError:
                    # Common — silent skip with low-noise log.
                    skipped_count += 1
                    await db.rollback()
                    await tracker.log(
                        f"⏭ Bỏ qua (nguồn không học thuật): "
                        f"{result.title[:80]}",
                        level="info",
                    )
                except NoAcademicPdfError:
                    skipped_count += 1
                    await db.rollback()
                    await tracker.log(
                        f"⏭ Bỏ qua (không có PDF): {result.title[:80]}",
                        level="info",
                    )
                except (PdfIngestError, IngestSkipped) as e:
                    skipped_count += 1
                    await db.rollback()
                    await tracker.log(
                        f"⚠ Bỏ qua (lỗi PDF): {result.title[:80]} ({e})",
                        level="error",
                    )
                except Exception as e:
                    # Unknown failure — log loudly but keep going.
                    logger.warning(
                        f"AutoResearch: unexpected ingest failure for "
                        f"search_result={result.id}: {e}"
                    )
                    skipped_count += 1
                    await db.rollback()
                    await tracker.log(
                        f"⚠ Lỗi không xác định: {result.title[:80]}",
                        level="error",
                    )

        # Final progress update — show "done/goal" cleanly.
        await tracker.update_item_progress(
            done=len(document_ids),
            total=max_documents,
            current_title=None,
        )
        if skipped_count:
            await tracker.log(
                f"Tổng kết: {len(document_ids)}/{max_documents} tài liệu "
                f"thành công, bỏ qua {skipped_count} kết quả "
                f"(không phải nguồn học thuật hoặc không có PDF)",
                level="info",
            )
        return document_ids

    # ── Stage 3: analyse each ingested document ─────────────────────────────

    async def _stage_analyse(
        self,
        *,
        document_ids: list[UUID],
        llm_provider: str | None,
        llm_model: str | None,
        tracker: ResearchProgressTracker,
    ) -> None:
        if not document_ids:
            return

        document_ids = document_ids[:_MAX_DOCS_TO_ANALYSE]
        logger.info(
            f"AutoResearch: starting analysis for {len(document_ids)} document(s)"
        )

        total = len(document_ids)
        for idx, doc_id in enumerate(document_ids):
            # Get the doc title for the per-item label.
            async with AsyncSessionLocal() as db:
                doc = await db.scalar(
                    select(Document).where(Document.id == doc_id)
                )
                doc_title = doc.title if doc else None

            await tracker.update_item_progress(
                done=idx,
                total=total,
                current_title=doc_title,
            )

            async with AsyncSessionLocal() as db:
                existing = await db.scalar(
                    select(DocumentAnalysis.id).where(
                        DocumentAnalysis.document_id == doc_id
                    )
                )
                if existing is not None:
                    logger.info(
                        f"AutoResearch: analysis already exists for "
                        f"document {doc_id}; skipping"
                    )
                    await tracker.log(
                        f"⏭ Đã có phân tích cho '{doc_title or doc_id}'",
                        level="info",
                    )
                    continue
                analysis = DocumentAnalysis(
                    document_id=doc_id,
                    status=AnalysisStatus.PENDING.value,
                )
                db.add(analysis)
                await db.commit()
                await db.refresh(analysis)
                analysis_id = analysis.id

            # Re-publish the item progress with the freshly-created
            # analysis id so the FE can drill in and render the
            # AnalysisAgent's own per-step progress inline.
            await tracker.update_item_progress(
                done=idx,
                total=total,
                current_title=doc_title,
                current_analysis_id=str(analysis_id),
            )

            try:
                async with AsyncSessionLocal() as db:
                    agent = AnalysisAgent(
                        db,
                        llm_provider=llm_provider,
                        llm_model=llm_model,
                    )
                    await agent.run(analysis_id)
                logger.info(
                    f"AutoResearch: analysis completed for document {doc_id}"
                )
                await tracker.log(
                    f"✓ Đã phân tích: {doc_title or doc_id}",
                    level="done",
                )
            except Exception as e:
                logger.error(
                    f"AutoResearch: analysis failed for document "
                    f"{doc_id}: {e}"
                )
                await tracker.log(
                    f"⚠ Phân tích thất bại: {doc_title or doc_id} ({e})",
                    level="error",
                )
                continue

        await tracker.update_item_progress(
            done=total, total=total, current_title=None
        )

    # ── Stage 4 (optional): create Report ───────────────────────────────────

    async def _stage_report(
        self,
        *,
        project_id: UUID,
        research_query: str | None,
        report_type: str | None,
        document_ids: list[UUID],
    ) -> UUID:
        """Create a deterministic Report attached to the project.

        Title is derived from the search query so the user sees the same
        topic on the report list as in the research history. The report
        includes only the documents we actually ingested in this auto-
        research run — not every document the project ever held.
        """
        # Validate / fall back the report type.
        rtype = report_type
        if rtype not in {t.value for t in ReportType}:
            rtype = ReportType.RESEARCH_SUMMARY.value

        title = _derive_report_title(research_query)
        # ``create_report`` is sync (operates on a sync ``Session``).
        # We wrap it in ``asyncio.to_thread`` so the orchestrator stays
        # async-friendly and doesn't block the event loop while the
        # generator runs.
        from app.database.session import SessionLocal

        def _create_sync() -> UUID:
            with SessionLocal() as db:
                report = create_report(
                    db=db,
                    project_id=project_id,
                    report_data=ReportCreate(
                        title=title,
                        report_type=ReportType(rtype),
                        included_documents=list(document_ids) or None,
                    ),
                )
                # Detach: pull the id before the session closes.
                return report.id

        return await asyncio.to_thread(_create_sync)

    # ── Stage 5 (optional): SynthesisAgent ──────────────────────────────────

    async def _stage_synthesize(
        self,
        *,
        report_id: UUID,
        llm_provider: str | None,
        llm_model: str | None,
    ) -> None:
        """Run SynthesisAgent INLINE (not via dispatch) so this stage
        blocks the auto-research pipeline until synthesis completes.

        The agent persists progress into ``reports.synthesis_progress``
        so a separate "report detail" tab can still show its own steps —
        but the auto-research stepper only flips when this method
        returns.
        """
        async with AsyncSessionLocal() as db:
            agent = SynthesisAgent(
                db,
                llm_provider=llm_provider,
                llm_model=llm_model,
            )
            await agent.run(report_id)

    # ── Stage 6 (optional): QualityAssuranceAgent ───────────────────────────

    async def _stage_qa(
        self,
        *,
        report_id: UUID,
        llm_provider: str | None,
        llm_model: str | None,
    ) -> int | None:
        """Run QualityAssuranceAgent INLINE and return the overall score
        so the auto-research progress can advertise it on completion."""
        async with AsyncSessionLocal() as db:
            agent = QualityAssuranceAgent(
                db,
                llm_provider=llm_provider,
                llm_model=llm_model,
            )
            await agent.run(report_id)

        # Read back the score for the stage finish message.
        try:
            async with AsyncSessionLocal() as db:
                report = await db.scalar(
                    select(Report).where(Report.id == report_id)
                )
                if report and isinstance(report.qa_report, dict):
                    score = report.qa_report.get("overall_score")
                    if isinstance(score, (int, float)):
                        return int(score)
        except Exception:
            pass
        return None


# ── Module-level convenience ──────────────────────────────────────────────

_service = AutoResearchService()


def dispatch_auto_research(
    *,
    research_session_id: UUID,
    max_documents: int,
    embedding_provider: str | None = None,
    embedding_model: str | None = None,
    llm_provider: str | None = None,
    llm_model: str | None = None,
    auto_report: bool = False,
    auto_synthesize: bool = False,
    auto_qa: bool = False,
    report_type: str | None = None,
) -> None:
    """Fire-and-forget convenience wrapper used by the route handler.

    ``_service.dispatch`` already creates the background task and holds
    a strong ref via ``_track``; we just need to schedule the call so
    the route handler doesn't await it. Wrapping ``dispatch`` itself in
    an extra ``create_task`` would create a task-of-task pair where the
    outer task isn't held anywhere — exactly the GC-collection bug we
    just fixed.
    """
    _track(
        asyncio.create_task(
            _service.dispatch(
                research_session_id=research_session_id,
                max_documents=max_documents,
                embedding_provider=embedding_provider,
                embedding_model=embedding_model,
                llm_provider=llm_provider,
                llm_model=llm_model,
                auto_report=auto_report,
                auto_synthesize=auto_synthesize,
                auto_qa=auto_qa,
                report_type=report_type,
            )
        )
    )


def _derive_report_title(query: str | None) -> str:
    """Build a Report.title from the research query.

    Truncated + capitalised so the report list reads cleanly. Falls
    back to a generic title when the query is empty (defensive — the
    pipeline should never have got this far without a query).
    """
    base = (query or "").strip()
    if not base:
        return "Báo cáo nghiên cứu tự động"
    # Drop common imperative prefixes the user types when querying.
    for prefix in ("tìm hiểu về ", "nghiên cứu về ", "tổng quan về "):
        if base.lower().startswith(prefix):
            base = base[len(prefix):]
            break
    if len(base) > 120:
        base = base[:117].rstrip() + "..."
    return f"Báo cáo: {base[0].upper()}{base[1:]}" if base else "Báo cáo"
