from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.tools.research.progress_tracker import (
    ResearchProgressTracker,
    STAGE_SAVE,
    STAGE_SEARCH,
)
from app.models.research import ResearchSession, SearchResult
from app.services.search_service import SearchService
from app.tools.search.schemas.search_result import SearchDocument
from app.utils.constants import ResearchStatus
from app.utils.logger import logger


class ResearchAgent:
    """Run a research session end-to-end.

    Stages (with progress published into ``research_sessions.progress``):

      1. Mark session as RUNNING
      2. STAGE_SEARCH   — call SearchService (parallel multi-source + rerank)
      3. STAGE_SAVE     — persist SearchResult rows
      4. Mark session as COMPLETED (or FAILED on error)

    A caller (e.g. ``AutoResearchService``) can pass its own ``tracker`` to
    chain extra stages (ingest, analyse) into the same session's progress
    feed. When no tracker is passed we create one in ``simple`` mode so
    standalone research sessions still get a live stepper on the FE.
    """

    def __init__(
        self,
        db: AsyncSession,
        *,
        tracker: Optional[ResearchProgressTracker] = None,
    ):
        self.db = db
        self.search_service = SearchService()
        self._tracker = tracker
        # Whether this agent owns the tracker lifecycle (init + finalize).
        # If a caller passed in a pre-existing tracker, they're responsible
        # for finalising it after their own additional stages run.
        self._owns_tracker = tracker is None

    # ── Public entry point ──────────────────────────────────────────────────

    async def run(self, research_session_id: UUID) -> ResearchSession:
        session = await self._get_session(research_session_id)

        if self._tracker is None:
            self._tracker = ResearchProgressTracker(
                self.db, research_session_id, mode="simple"
            )
            await self._tracker.init(query=session.query)

        try:
            await self._mark_running(session)

            await self._tracker.start_stage(
                STAGE_SEARCH,
                detail=f"Tìm tối đa {session.max_results} tài liệu",
            )
            documents = await self.search_service.search(
                query=session.query,
                max_results=session.max_results,
            )
            await self._tracker.finish_stage(
                STAGE_SEARCH,
                message=f"{len(documents)} kết quả",
            )

            # The "save" stage only fits ordinary search sessions: in the
            # simple-mode tracker it's the final terminal step. The auto
            # mode's stage list reserves "save" for the very end of the
            # whole pipeline (after ingest + analyse), so when we're
            # nested inside auto-research we must NOT publish a save
            # stage event here — the orchestrator handles it.
            if self._owns_tracker:
                await self._tracker.start_stage(
                    STAGE_SAVE,
                    detail="Ghi kết quả vào CSDL",
                )
                await self._save_results(session, documents)
                await self._tracker.finish_stage(STAGE_SAVE)
            else:
                # Still persist the results — just do it without the
                # stage event (auto mode logs this implicitly via the
                # SEARCH stage's "X kết quả" message).
                await self._save_results(session, documents)

            # Only mark the session COMPLETED when we own the tracker
            # — ie when this is a standalone search. When the agent is
            # invoked as the first stage of auto-research, the
            # orchestrator above us still has more work to do (ingest +
            # analyse) and will flip the status itself at the end.
            if self._owns_tracker:
                await self._mark_completed(session, results_count=len(documents))
                await self._tracker.finalize(
                    "completed",
                    message=f"{len(documents)} kết quả",
                )
                await self._notify_done(
                    session, success=True, count=len(documents)
                )
            else:
                # Still record results_count so the FE list shows the
                # right number even before the parent orchestrator
                # finishes.
                session.results_count = len(documents)
                await self.db.commit()
                await self.db.refresh(session)

            logger.success(
                f"ResearchAgent completed session {session.id} "
                f"with {len(documents)} results"
            )

        except Exception as e:
            logger.error(f"ResearchAgent failed for session {session.id}: {e}")
            try:
                await self._tracker.fail_stage(
                    self._tracker._state.get("current_stage") or STAGE_SEARCH,
                    str(e),
                )
                if self._owns_tracker:
                    await self._tracker.finalize("failed", str(e))
            except Exception:
                pass
            await self._mark_failed(session, error_message=str(e))
            if self._owns_tracker:
                await self._notify_done(session, success=False, error=str(e))
            raise

        return session

    # ── DB helpers ──────────────────────────────────────────────────────────

    async def _get_session(self, research_session_id: UUID) -> ResearchSession:
        result = await self.db.execute(
            select(ResearchSession).where(
                ResearchSession.id == research_session_id
            )
        )
        session = result.scalar_one_or_none()
        if not session:
            raise ValueError(f"ResearchSession not found: {research_session_id}")
        return session

    async def _mark_running(self, session: ResearchSession) -> None:
        session.status = ResearchStatus.RUNNING.value
        await self.db.commit()
        await self.db.refresh(session)
        logger.info(f"ResearchAgent: session {session.id} → RUNNING")

    async def _mark_completed(
        self, session: ResearchSession, results_count: int
    ) -> None:
        session.status = ResearchStatus.COMPLETED.value
        session.results_count = results_count
        session.completed_at = datetime.now(timezone.utc)
        await self.db.commit()
        await self.db.refresh(session)

    async def _mark_failed(
        self, session: ResearchSession, error_message: str
    ) -> None:
        session.status = ResearchStatus.FAILED.value
        session.error_message = error_message
        session.completed_at = datetime.now(timezone.utc)
        await self.db.commit()
        await self.db.refresh(session)

    async def _save_results(
        self,
        session: ResearchSession,
        documents: list[SearchDocument],
    ) -> None:
        """Bulk-insert all SearchResult rows in a single transaction."""
        rows = [
            SearchResult(
                research_session_id=session.id,
                title=doc.title,
                url=doc.url,
                snippet=doc.snippet,
                content_preview=doc.content_preview,
                source=doc.source,
                search_type=doc.search_type,
                authors=doc.authors,
                published_at=doc.published_at,
                doi=doc.doi,
                pdf_url=doc.pdf_url,
                source_id=doc.source_id,
                retrieval_score=doc.retrieval_score,
                relevance_score=doc.relevance_score,
                rank=rank,
                search_query=session.query,
                raw_metadata=doc.raw_metadata,
            )
            for rank, doc in enumerate(documents, start=1)
        ]
        self.db.add_all(rows)
        await self.db.commit()

        logger.info(
            f"ResearchAgent: saved {len(rows)} search results "
            f"for session {session.id}"
        )


    # ── Notifications ───────────────────────────────────────────────────────

    async def _notify_done(
        self,
        session: ResearchSession,
        *,
        success: bool,
        count: int = 0,
        error: str | None = None,
    ) -> None:
        """Push a "tìm kiếm xong" notification to the project owner.

        Only called for standalone search sessions. Auto-research mode
        defers the alert to ``AutoResearchService`` which fires at the
        end of the full pipeline (search + ingest + analyse).
        """
        from app.database.session import AsyncSessionLocal as _Session
        from app.models.project import Project
        from app.services.notification_service import (
            CATEGORY_RESEARCH,
            TYPE_ERROR,
            TYPE_SUCCESS,
            create_notification_async,
        )

        try:
            async with _Session() as s:
                user_id = await s.scalar(
                    select(Project.user_id).where(
                        Project.id == session.project_id
                    )
                )
            if user_id is None:
                return

            query = (session.query or "")[:120]
            if success:
                title = "Tìm kiếm tài liệu hoàn thành"
                message = (
                    f"'{query}' — {count} kết quả đã được lưu."
                    if query
                    else f"{count} kết quả đã được lưu."
                )
                ntype = TYPE_SUCCESS
            else:
                title = "Tìm kiếm tài liệu thất bại"
                message = (
                    f"'{query}': {(error or 'lỗi không xác định')[:200]}"
                    if query
                    else (error or "lỗi không xác định")[:200]
                )
                ntype = TYPE_ERROR

            await create_notification_async(
                user_id=user_id,
                title=title,
                message=message,
                notification_type=ntype,
                category=CATEGORY_RESEARCH,
                entity_id=session.id,
                entity_kind="research",
                project_id=session.project_id,
            )
        except Exception as e:
            logger.warning(
                f"ResearchAgent: failed to write notification for "
                f"{session.id}: {e}"
            )
