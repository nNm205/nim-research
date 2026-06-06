"""Recover stale ``running`` rows on app startup.

Background tasks (research, auto-research, analysis) live entirely in
the running process. When the backend crashes or is restarted those
tasks die, but the corresponding ``research_sessions`` /
``document_analyses`` rows remain at status ``running`` forever — the
FE's polling loop then keeps the live progress panel visible
indefinitely, exactly the symptom the user reported.

This module is invoked once at app startup to flip any such rows into
a terminal state. It only touches rows whose ``started_at`` is older
than a small grace window so we never race a freshly-dispatched task
on the same process.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import update

from app.database.session import AsyncSessionLocal
from app.models.analysis import DocumentAnalysis
from app.models.research import ResearchSession
from app.utils.constants import AnalysisStatus, ResearchStatus
from app.utils.logger import logger


# Sessions newer than this are assumed to belong to the *current* run
# and are left alone — there's a small chance a task is still spinning
# up. 1 minute is plenty of margin without leaving zombie panels around
# for very long.
_GRACE_WINDOW = timedelta(minutes=1)

_RECOVERY_NOTE = (
    "Backend đã khởi động lại trong khi tác vụ đang chạy — "
    "phiên đã bị đánh dấu thất bại để giải phóng UI."
)


async def recover_stale_sessions() -> None:
    """Flip any ``running`` rows older than the grace window to ``failed``.

    Logs a single line per recovery so an operator can see the cleanup.
    Errors are swallowed — startup must not be blocked by recovery
    failure (worst case: the FE keeps showing the bar until the user
    clicks the affected session, at which point they can re-run it).
    """
    cutoff = datetime.now(timezone.utc) - _GRACE_WINDOW
    now = datetime.now(timezone.utc)

    try:
        async with AsyncSessionLocal() as db:
            # ── Research / auto-research sessions ─────────────────────
            res_stmt = (
                update(ResearchSession)
                .where(
                    ResearchSession.status.in_(
                        [
                            ResearchStatus.PENDING.value,
                            ResearchStatus.RUNNING.value,
                        ]
                    )
                )
                .where(ResearchSession.started_at < cutoff)
                .values(
                    status=ResearchStatus.FAILED.value,
                    error_message=_RECOVERY_NOTE,
                    completed_at=now,
                )
            )
            res_result = await db.execute(res_stmt)

            # ── Document analyses ─────────────────────────────────────
            ana_stmt = (
                update(DocumentAnalysis)
                .where(
                    DocumentAnalysis.status.in_(
                        [
                            AnalysisStatus.PENDING.value,
                            AnalysisStatus.RUNNING.value,
                        ]
                    )
                )
                .where(DocumentAnalysis.started_at < cutoff)
                .values(
                    status=AnalysisStatus.FAILED.value,
                    error_message=_RECOVERY_NOTE,
                    completed_at=now,
                )
            )
            ana_result = await db.execute(ana_stmt)

            await db.commit()

            res_count = res_result.rowcount or 0
            ana_count = ana_result.rowcount or 0
            if res_count or ana_count:
                logger.warning(
                    f"Stale-recovery: marked {res_count} research session(s) "
                    f"and {ana_count} analysis row(s) as FAILED "
                    f"(left over from a previous run)."
                )
            else:
                logger.info(
                    "Stale-recovery: no leftover running rows to clean up."
                )
    except Exception as e:
        logger.error(
            f"Stale-recovery: failed to clean up running rows on startup: {e}"
        )
