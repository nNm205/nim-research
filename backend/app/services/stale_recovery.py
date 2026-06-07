from __future__ import annotations
from datetime import datetime, timedelta, timezone
from sqlalchemy import update
from app.database.session import AsyncSessionLocal
from app.models.analysis import DocumentAnalysis
from app.models.report import Report
from app.models.research import ResearchSession
from app.utils.constants import (
    AnalysisStatus,
    QAStatus,
    ResearchStatus,
    SynthesisStatus,
)
from app.utils.logger import logger


_GRACE_WINDOW = timedelta(minutes=1)

_RECOVERY_NOTE = (
    "Backend đã khởi động lại trong khi tác vụ đang chạy — "
    "phiên đã bị đánh dấu thất bại để giải phóng UI."
)


async def recover_stale_sessions() -> None:
    cutoff = datetime.now(timezone.utc) - _GRACE_WINDOW
    now = datetime.now(timezone.utc)

    try:
        async with AsyncSessionLocal() as db:
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

            syn_stmt = (
                update(Report)
                .where(
                    Report.synthesis_status.in_(
                        [
                            SynthesisStatus.PENDING.value,
                            SynthesisStatus.RUNNING.value,
                        ]
                    )
                )
                .where(Report.synthesis_started_at < cutoff)
                .values(
                    synthesis_status=SynthesisStatus.FAILED.value,
                    synthesis_error=_RECOVERY_NOTE,
                    synthesis_completed_at=now,
                )
            )
            syn_result = await db.execute(syn_stmt)

            qa_stmt = (
                update(Report)
                .where(
                    Report.qa_status.in_(
                        [
                            QAStatus.PENDING.value,
                            QAStatus.RUNNING.value,
                        ]
                    )
                )
                .where(Report.qa_started_at < cutoff)
                .values(
                    qa_status=QAStatus.FAILED.value,
                    qa_error=_RECOVERY_NOTE,
                    qa_completed_at=now,
                )
            )
            qa_result = await db.execute(qa_stmt)

            await db.commit()

            res_count = res_result.rowcount or 0
            ana_count = ana_result.rowcount or 0
            syn_count = syn_result.rowcount or 0
            qa_count = qa_result.rowcount or 0
            if res_count or ana_count or syn_count or qa_count:
                logger.warning(
                    f"Stale-recovery: marked {res_count} research session(s), "
                    f"{ana_count} analysis row(s), "
                    f"{syn_count} report synthesis run(s), and "
                    f"{qa_count} report QA run(s) as FAILED "
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
