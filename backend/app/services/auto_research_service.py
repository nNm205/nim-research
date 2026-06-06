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
from app.agents.research_agent import ResearchAgent
from app.agents.tools.research.progress_tracker import (
    ResearchProgressTracker,
    STAGE_ANALYSE,
    STAGE_INGEST,
    STAGE_SAVE,
)
from app.database.session import AsyncSessionLocal
from app.models.analysis import DocumentAnalysis
from app.models.document import Document  # noqa: F401  imported for ORM resolution
from app.models.research import ResearchSession, SearchResult
from app.services.document_ingestion_service import DocumentIngestionService
from app.utils.constants import AnalysisStatus, ResearchStatus
from app.utils.logger import logger


# Hard caps to keep cost predictable. Free-tier LLM quota is the binding
# constraint for analysis fan-out.
_MAX_DOCS_TO_INGEST = 5
_MAX_DOCS_TO_ANALYSE = 5


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
    ) -> None:
        """Schedule the orchestration as an asyncio background task.

        Returns immediately so the route handler can respond to the FE.
        """
        asyncio.create_task(
            self._run_in_background(
                research_session_id=research_session_id,
                max_documents=max_documents,
                embedding_provider=embedding_provider,
                embedding_model=embedding_model,
                llm_provider=llm_provider,
                llm_model=llm_model,
            )
        )
        logger.info(
            f"AutoResearch: dispatched session={research_session_id} "
            f"max_documents={max_documents} llm={llm_provider}/{llm_model}"
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
    ) -> None:
        max_documents = max(1, min(max_documents, _MAX_DOCS_TO_INGEST))

        # The tracker writes to ``research_sessions.progress`` — needs a
        # dedicated session because it persists state across stages while
        # the actual stage code uses fresh sessions per call. Holding one
        # connection open just for the tracker is fine because Supavisor
        # is fine with idle connections inside transaction-mode pooling
        # as long as we don't keep an open transaction open between
        # writes (the tracker commits on every flush).
        tracker_db = AsyncSessionLocal()
        try:
            tracker = ResearchProgressTracker(
                tracker_db, research_session_id, mode="auto"
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

            # ── Stage 4: done ─────────────────────────────────────────────
            await tracker.start_stage(
                STAGE_SAVE,
                detail="Hoàn tất pipeline",
            )
            await tracker.finish_stage(STAGE_SAVE)
            await tracker.finalize(
                "completed",
                f"{len(document_ids)} tài liệu được phân tích",
            )
            await self._mark_session_terminal(
                research_session_id, "completed"
            )
        finally:
            try:
                await tracker_db.close()
            except Exception:
                pass

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
        """
        target = (
            ResearchStatus.COMPLETED.value
            if status == "completed"
            else ResearchStatus.FAILED.value
        )
        try:
            async with AsyncSessionLocal() as db:
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
        async with AsyncSessionLocal() as db:
            stmt = (
                select(SearchResult)
                .where(SearchResult.research_session_id == research_session_id)
                .where(SearchResult.document_id.is_(None))
                .order_by(SearchResult.rank.asc().nulls_last())
                .limit(max_documents)
            )
            results = list((await db.execute(stmt)).scalars().all())

        if not results or project_id is None:
            logger.info(
                f"AutoResearch: research session {research_session_id} "
                f"yielded zero ingestable results"
            )
            return []

        logger.info(
            f"AutoResearch: ingesting top {len(results)} results "
            f"for session {research_session_id}"
        )

        # Run ingests sequentially so we can publish accurate per-item
        # progress to the tracker. PDF download + parse is dominated by
        # network I/O so the 2× speedup from concurrency=2 isn't worth
        # the loss of clean per-item progress reporting.
        document_ids: list[UUID] = []
        total = len(results)
        for idx, result in enumerate(results):
            await tracker.update_item_progress(
                done=idx,
                total=total,
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
                        f"✓ Đã nạp: {result.title[:80]}",
                        level="done",
                    )
                except Exception as e:
                    logger.warning(
                        f"AutoResearch: ingest failed for "
                        f"search_result={result.id} ({e})"
                    )
                    await db.rollback()
                    await tracker.log(
                        f"⚠ Bỏ qua (lỗi ingest): {result.title[:80]}",
                        level="error",
                    )

        # Final progress update — show "done/total" instead of leaving
        # the counter on the last in-flight item.
        await tracker.update_item_progress(
            done=total,
            total=total,
            current_title=None,
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
) -> None:
    """Fire-and-forget convenience wrapper used by the route handler."""
    asyncio.create_task(
        _service.dispatch(
            research_session_id=research_session_id,
            max_documents=max_documents,
            embedding_provider=embedding_provider,
            embedding_model=embedding_model,
            llm_provider=llm_provider,
            llm_model=llm_model,
        )
    )
