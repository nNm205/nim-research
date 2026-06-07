import asyncio
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.synthesis_agent import SynthesisAgent
from app.database.session import AsyncSessionLocal
from app.models.report import Report
from app.utils.constants import SynthesisStatus
from app.utils.logger import logger


async def get_report_async(
    db: AsyncSession, report_id: UUID
) -> Report:
    report = await db.scalar(select(Report).where(Report.id == report_id))
    if report is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Report not found"
        )
    return report


async def mark_report_synthesis_pending(
    db: AsyncSession, report: Report
) -> Report:
    report.synthesis_status = SynthesisStatus.PENDING.value
    report.synthesis_error = None
    report.synthesis_completed_at = None
    await db.commit()
    await db.refresh(report)
    return report

async def _run_agent_in_background(
    report_id: UUID,
    llm_provider: str | None = None,
    llm_model: str | None = None,
) -> None:
    try:
        async with AsyncSessionLocal() as db:
            agent = SynthesisAgent(
                db,
                llm_provider=llm_provider,
                llm_model=llm_model,
            )
            await agent.run(report_id)
    except Exception as e:
        logger.error(f"Background synthesis task failed for {report_id}: {e}")


_BACKGROUND_TASKS: set[asyncio.Task] = set()


def dispatch_synthesis_agent(
    report_id: UUID,
    llm_provider: str | None = None,
    llm_model: str | None = None,
) -> None:
    try:
        task = asyncio.create_task(
            _run_agent_in_background(
                report_id,
                llm_provider=llm_provider,
                llm_model=llm_model,
            )
        )
        _BACKGROUND_TASKS.add(task)
        task.add_done_callback(_BACKGROUND_TASKS.discard)
    except Exception as e:
        logger.error(
            f"Failed to dispatch synthesis agent for {report_id}: {e}"
        )
