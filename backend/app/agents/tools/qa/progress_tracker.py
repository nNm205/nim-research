from __future__ import annotations
import time
from datetime import datetime, timezone
from typing import Any
from uuid import UUID
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.report import Report
from app.utils.logger import logger

STEP_LOAD = "load_report"
STEP_FORMAT = "check_format"
STEP_CITATIONS = "check_citations"
STEP_FACTS = "check_facts"
STEP_GRAMMAR = "check_grammar"
STEP_SCORE = "compute_score"
STEP_PERSIST = "persist"

CANONICAL_STEPS: list[dict[str, str]] = [
    {"key": STEP_LOAD,      "label": "Tải báo cáo và nguồn"},
    {"key": STEP_FORMAT,    "label": "Kiểm tra định dạng"},
    {"key": STEP_CITATIONS, "label": "Kiểm tra trích dẫn"},
    {"key": STEP_FACTS,     "label": "Kiểm tra độ chính xác"},
    {"key": STEP_GRAMMAR,   "label": "Kiểm tra văn phong"},
    {"key": STEP_SCORE,     "label": "Tính điểm tổng hợp"},
    {"key": STEP_PERSIST,   "label": "Lưu kết quả"},
]

_MAX_EVENTS = 30


class QAProgressTracker:
    def __init__(self, db: AsyncSession, report_id: UUID) -> None:
        self.db = db
        self.report_id = report_id
        self._step_started_at: dict[str, float] = {}
        self._state: dict[str, Any] = {
            "current_step": None,
            "current_step_label": None,
            "current_detail": None,
            "completed_steps": [],
            "steps": list(CANONICAL_STEPS),
            "events": [],
            "started_at": _now_iso(),
            "provider": None,
            "model": None,
        }

    async def init(
        self, provider: str | None = None, model: str | None = None
    ) -> None:
        self._state["provider"] = provider
        self._state["model"] = model
        self._state["events"] = []
        self._state["completed_steps"] = []
        self._state["current_step"] = None
        self._state["current_step_label"] = None
        self._state["current_detail"] = None
        self._state["started_at"] = _now_iso()
        msg = f"Bắt đầu kiểm chất lượng bằng {provider}:{model}" if provider else "Bắt đầu kiểm chất lượng"
        self._append_event(msg, level="info")
        await self._flush()

    async def start_step(self, key: str, detail: str | None = None) -> None:
        label = self._label_for(key)
        self._step_started_at[key] = time.monotonic()
        self._state["current_step"] = key
        self._state["current_step_label"] = label
        self._state["current_detail"] = detail
        self._append_event(
            f"Đang {label.lower()}" + (f": {detail}" if detail else ""),
            level="running",
        )
        await self._flush()

    async def finish_step(self, key: str, message: str | None = None) -> None:
        label = self._label_for(key)
        started = self._step_started_at.pop(key, None)
        duration_ms = (
            int((time.monotonic() - started) * 1000)
            if started is not None else None
        )
        if key not in self._state["completed_steps"]:
            self._state["completed_steps"].append(key)
        if self._state.get("current_step") == key:
            self._state["current_step"] = None
            self._state["current_detail"] = None
        suffix = f" ({duration_ms} ms)" if duration_ms is not None else ""
        self._append_event(
            f"✓ {label}{(' — ' + message) if message else ''}{suffix}",
            level="done",
        )
        await self._flush()

    async def fail_step(self, key: str, error_message: str) -> None:
        label = self._label_for(key)
        self._state["current_step"] = key
        self._state["current_step_label"] = label
        self._state["current_detail"] = f"Lỗi: {error_message[:200]}"
        self._append_event(
            f"✗ {label} thất bại: {error_message[:200]}",
            level="error",
        )
        await self._flush()

    async def finalize(self, status: str, message: str | None = None) -> None:
        self._state["current_step"] = None
        self._state["current_detail"] = None
        if status == "completed":
            self._append_event(
                f"🎉 Hoàn thành{(' — ' + message) if message else ''}",
                level="done",
            )
        else:
            self._append_event(
                f"Pipeline dừng: {message or status}",
                level="error",
            )
        await self._flush()

    def _label_for(self, key: str) -> str:
        for s in CANONICAL_STEPS:
            if s["key"] == key:
                return s["label"]
        return key

    def _append_event(self, message: str, level: str) -> None:
        events = self._state.setdefault("events", [])
        events.append(
            {"ts": _now_iso(), "level": level, "message": message}
        )
        if len(events) > _MAX_EVENTS:
            del events[: len(events) - _MAX_EVENTS]

    async def _flush(self) -> None:
        try:
            stmt = (
                update(Report)
                .where(Report.id == self.report_id)
                .values(qa_progress=dict(self._state))
            )
            await self.db.execute(stmt)
            await self.db.commit()
        except Exception as e:
            logger.warning(
                f"QAProgressTracker: failed to persist progress for "
                f"{self.report_id}: {e}"
            )
            try:
                await self.db.rollback()
            except Exception:
                pass


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
