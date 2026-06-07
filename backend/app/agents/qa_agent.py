from __future__ import annotations
from datetime import datetime, timezone
from typing import Any
from uuid import UUID
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.exc import StaleDataError
from app.agents.tools.qa import (
    CitationVerifierTool,
    FactCheckerTool,
    FormatValidatorTool,
    GrammarCheckerTool,
    QualityScorerTool,
)
from app.agents.tools.qa.progress_tracker import (
    STEP_CITATIONS,
    STEP_FACTS,
    STEP_FORMAT,
    STEP_GRAMMAR,
    STEP_LOAD,
    STEP_PERSIST,
    STEP_SCORE,
    QAProgressTracker,
)
from app.agents.tools.synthesis.context_loader import SynthesisContextLoaderTool
from app.config import settings
from app.models.llm_providers.base import LLMProvider
from app.models.llm_providers.factory import LLMFactory
from app.models.llm_providers.types import ProviderType
from app.models.project import Project
from app.models.report import Report
from app.utils.constants import QAStatus
from app.utils.logger import logger

__all__ = ["QualityAssuranceAgent"]

class QualityAssuranceAgent:
    def __init__(
        self,
        db: AsyncSession,
        llm_provider: str | None = None,
        llm_model: str | None = None,
    ) -> None:
        self.db = db
        self.llm_provider = (llm_provider or settings.PROVIDER).lower()
        self.llm_model = llm_model or settings.MODEL_NAME

    async def run(self, report_id: UUID) -> Report:
        report = await self._get_report(report_id)
        progress = QAProgressTracker(self.db, report_id)

        try:
            try:
                await self._mark_running(report)
            except RuntimeError:
                return report

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
                f"QualityAssuranceAgent: using provider={self.llm_provider} "
                f"model={llm.get_model_name()} for report {report.id}"
            )

            await progress.init(
                provider=self.llm_provider,
                model=llm.get_model_name(),
            )

            await progress.start_step(STEP_LOAD)
            project = await self._get_project(report.project_id)
            included = None
            if report.included_documents:
                try:
                    included = [UUID(str(x)) for x in report.included_documents]
                except Exception:
                    included = None
            loader = SynthesisContextLoaderTool()
            context = await loader.load(
                db=self.db,
                project=project,
                report_title=report.title,
                report_type=report.report_type,
                included_documents=included,
            )
            markdown = report.content or ""
            await progress.finish_step(
                STEP_LOAD,
                f"{len(context.documents)} tài liệu, {len(markdown)} ký tự",
            )

            await progress.start_step(STEP_FORMAT)
            format_tool = FormatValidatorTool()
            format_result = format_tool.validate(markdown)
            await progress.finish_step(
                STEP_FORMAT,
                f"score={format_result['score']}, "
                f"{len(format_result.get('issues') or [])} issue",
            )

            await progress.start_step(STEP_CITATIONS)
            citation_entries = self._citation_entries_from_report(
                report, context
            )
            expects_inline = bool(
                (report.synthesis_metadata or {}).get("citation_entries")
            )
            citation_tool = CitationVerifierTool()
            citations_result = citation_tool.verify(
                markdown,
                citation_entries,
                expects_inline_citations=expects_inline,
            )
            await progress.finish_step(
                STEP_CITATIONS,
                f"score={citations_result['score']}, "
                f"{len(citations_result.get('issues') or [])} issue",
            )

            await progress.start_step(STEP_FACTS)
            fact_tool = FactCheckerTool()
            facts_result = await fact_tool.check(
                markdown=markdown,
                report_title=report.title,
                context=context,
                llm=llm,
            )
            await progress.finish_step(
                STEP_FACTS,
                f"score={facts_result['score']}, "
                f"checked {(facts_result.get('stats') or {}).get('claims_checked', 0)} claim",
            )

            await progress.start_step(STEP_GRAMMAR)
            grammar_tool = GrammarCheckerTool()
            grammar_result = await grammar_tool.check(
                markdown=markdown,
                report_title=report.title,
                llm=llm,
            )
            await progress.finish_step(
                STEP_GRAMMAR,
                f"score={grammar_result['score']}, "
                f"{(grammar_result.get('stats') or {}).get('issues_count', 0)} issue",
            )

            await progress.start_step(STEP_SCORE)
            scorer = QualityScorerTool()
            qa_report = scorer.score(
                format_result=format_result,
                citations_result=citations_result,
                facts_result=facts_result,
                grammar_result=grammar_result,
            )
            qa_report["provider"] = self.llm_provider
            qa_report["model"] = llm.get_model_name()
            qa_report["generated_at"] = datetime.now(timezone.utc).isoformat()
            await progress.finish_step(
                STEP_SCORE,
                f"overall={qa_report['overall_score']} ({qa_report['verdict']})",
            )

            try:
                await progress.start_step(STEP_PERSIST)
                await self._persist_result(report, qa_report)
                await progress.finish_step(STEP_PERSIST, "đã ghi vào CSDL")
                await progress.finalize(
                    "completed",
                    message=f"score={qa_report['overall_score']}",
                )
            except StaleDataError:
                await self.db.rollback()
                logger.warning(
                    f"QualityAssuranceAgent: report {report_id} disappeared "
                    f"during run; result discarded."
                )
                return report

            logger.success(
                f"QualityAssuranceAgent: completed report {report.id} "
                f"score={qa_report['overall_score']}"
            )
            await self._notify(report, qa_report=qa_report, success=True)

        except StaleDataError:
            await self.db.rollback()
            logger.warning(
                f"QualityAssuranceAgent: report {report_id} was deleted during "
                f"run; aborting cleanly."
            )
        except Exception as e:
            await self.db.rollback()
            logger.error(
                f"QualityAssuranceAgent: failed for report {report_id}: {e}"
            )
            try:
                await progress.finalize("failed", str(e))
            except Exception:
                pass
            await self._mark_failed(report_id, str(e))
            await self._notify(report, qa_report=None, success=False, error=str(e))
            raise

        return report

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
        if report.qa_status == QAStatus.RUNNING.value:
            logger.info(
                f"QualityAssuranceAgent: skipping duplicate run for report "
                f"{report.id}"
            )
            raise RuntimeError("QA already running")

        report.qa_status = QAStatus.RUNNING.value
        report.qa_started_at = datetime.now(timezone.utc)
        report.qa_completed_at = None
        report.qa_error = None
        await self.db.commit()
        await self.db.refresh(report)
        logger.info(
            f"QualityAssuranceAgent: report {report.id} qa_status → RUNNING"
        )

    async def _mark_failed(
        self, report_id: UUID, error_message: str
    ) -> None:
        try:
            stmt = (
                update(Report)
                .where(Report.id == report_id)
                .values(
                    qa_status=QAStatus.FAILED.value,
                    qa_error=(error_message or "")[:1000],
                    qa_completed_at=datetime.now(timezone.utc),
                )
            )
            await self.db.execute(stmt)
            await self.db.commit()
        except Exception as e:
            await self.db.rollback()
            logger.error(
                f"QualityAssuranceAgent: failed to record FAILED status for "
                f"{report_id}: {e}"
            )

    async def _persist_result(
        self,
        report: Report,
        qa_report: dict[str, Any],
    ) -> None:
        report.qa_report = qa_report
        report.qa_status = QAStatus.COMPLETED.value
        report.qa_completed_at = datetime.now(timezone.utc)
        report.qa_error = None
        await self.db.commit()
        await self.db.refresh(report)

    def _citation_entries_from_report(
        self,
        report: Report,
        context: Any,
    ) -> list[dict]:
        meta = report.synthesis_metadata or {}
        entries = meta.get("citation_entries") if isinstance(meta, dict) else None
        if isinstance(entries, list) and entries:
            return entries

        out: list[dict] = []
        for d in context.documents:
            out.append({
                "index": d.index,
                "doc_id": str(d.id),
                "title": d.title,
                "url": d.source_url,
                "doi": d.doi,
                "authors": d.authors,
            })
        return out

    async def _notify(
        self,
        report: Report,
        *,
        qa_report: dict[str, Any] | None,
        success: bool,
        error: str | None = None,
    ) -> None:
        from app.database.session import AsyncSessionLocal as _Session
        from app.services.notification_service import (
            CATEGORY_QA,
            TYPE_ERROR,
            TYPE_INFO,
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

            report_title = (report.title or "")[:120] or "Báo cáo"
            if success and qa_report is not None:
                score = qa_report.get("overall_score", "?")
                verdict = qa_report.get("verdict", "?")
                title = f"QA hoàn thành — điểm {score}"
                message = (
                    f"'{report_title}' nhận điểm {score}/100 "
                    f"({_verdict_vi(verdict)})."
                )
                ntype = TYPE_SUCCESS if score >= 75 else TYPE_INFO
            else:
                title = "QA báo cáo thất bại"
                message = (
                    f"'{report_title}': {(error or 'lỗi không xác định')[:200]}"
                )
                ntype = TYPE_ERROR

            await create_notification_async(
                user_id=user_id,
                title=title,
                message=message,
                notification_type=ntype,
                category=CATEGORY_QA,
                entity_id=report.id,
                entity_kind="report",
                project_id=report.project_id,
            )
        except Exception as e:
            logger.warning(
                f"QualityAssuranceAgent: failed to write notification for "
                f"{report.id}: {e}"
            )


def _verdict_vi(verdict: str) -> str:
    return {
        "excellent": "Xuất sắc",
        "good": "Tốt",
        "needs_review": "Cần xem lại",
        "poor": "Kém",
    }.get(verdict, verdict)
