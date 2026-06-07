import asyncio
from uuid import UUID
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.agents.qa_agent import QualityAssuranceAgent
from app.database.session import AsyncSessionLocal
from app.models.report import Report
from app.utils.constants import QAStatus
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


async def mark_report_qa_pending(
    db: AsyncSession, report: Report
) -> Report:
    report.qa_status = QAStatus.PENDING.value
    report.qa_error = None
    report.qa_completed_at = None
    await db.commit()
    await db.refresh(report)
    return report

async def _run_agent_in_background(
    report_id: UUID,
    llm_provider: str | None = None,
    llm_model: str | None = None,
    *,
    run_synthesis_first: bool = False,
) -> None:
    try:
        async with AsyncSessionLocal() as db:
            if run_synthesis_first:
                from app.agents.synthesis_agent import SynthesisAgent
                synthesis = SynthesisAgent(
                    db,
                    llm_provider=llm_provider,
                    llm_model=llm_model,
                )
                try:
                    await synthesis.run(report_id)
                except Exception as e:
                    logger.warning(
                        f"Pre-QA synthesis failed for {report_id}: {e} — "
                        f"continuing to QA on existing content"
                    )
            agent = QualityAssuranceAgent(
                db,
                llm_provider=llm_provider,
                llm_model=llm_model,
            )
            await agent.run(report_id)
    except Exception as e:
        logger.error(f"Background QA task failed for {report_id}: {e}")


_BACKGROUND_TASKS: set[asyncio.Task] = set()

def dispatch_qa_agent(
    report_id: UUID,
    llm_provider: str | None = None,
    llm_model: str | None = None,
    *,
    run_synthesis_first: bool = False,
) -> None:
    try:
        task = asyncio.create_task(
            _run_agent_in_background(
                report_id,
                llm_provider=llm_provider,
                llm_model=llm_model,
                run_synthesis_first=run_synthesis_first,
            )
        )
        _BACKGROUND_TASKS.add(task)
        task.add_done_callback(_BACKGROUND_TASKS.discard)
    except Exception as e:
        logger.error(f"Failed to dispatch QA agent for {report_id}: {e}")
