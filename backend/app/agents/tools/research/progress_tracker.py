"""ResearchProgressTracker — write live pipeline progress to ``research_sessions.progress``.

This module mirrors ``app/agents/tools/analysis/progress_tracker.py`` for the
research pipeline. The same JSONB schema is used so the FE can render the
two pipelines with one shared progress panel component.

Two pipeline modes share the tracker:

  - **simple**  — ordinary research session: 2 stages (search → save).
  - **auto**    — auto-research session: 4 stages (search → ingest → analyse → save).

The mode is fixed at ``init()`` and cannot change mid-run. The FE picks
the mode key out of the JSON state to know how many stage chips to render.
"""

from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.research import ResearchSession
from app.utils.logger import logger


# ── Canonical stage keys ─────────────────────────────────────────────────────

STAGE_SEARCH = "search"
STAGE_INGEST = "ingest"
STAGE_ANALYSE = "analyse"
STAGE_REPORT = "report"
STAGE_SYNTHESIZE = "synthesize"
STAGE_QA = "qa"
STAGE_SAVE = "save"


CANONICAL_STAGES_SIMPLE: list[dict[str, str]] = [
    {"key": STAGE_SEARCH, "label": "Tìm kiếm tài liệu"},
    {"key": STAGE_SAVE,   "label": "Lưu kết quả"},
]

# The "auto" stage list is now BUILT dynamically because the user can
# toggle the report / synthesis / qa add-on stages independently in the
# auto-research modal. ``build_auto_stages`` returns the right shape
# given the toggles. ``CANONICAL_STAGES_AUTO`` is kept as the default
# (no add-ons) for backward compatibility with callers that don't pass
# explicit toggles.
CANONICAL_STAGES_AUTO: list[dict[str, str]] = [
    {"key": STAGE_SEARCH,  "label": "Tìm kiếm tài liệu"},
    {"key": STAGE_INGEST,  "label": "Nạp tài liệu vào dự án"},
    {"key": STAGE_ANALYSE, "label": "Phân tích từng tài liệu"},
    {"key": STAGE_SAVE,    "label": "Hoàn tất"},
]


def build_auto_stages(
    *,
    with_report: bool = False,
    with_synthesis: bool = False,
    with_qa: bool = False,
) -> list[dict[str, str]]:
    """Return the auto-research stage list with the requested add-ons.

    Stages always appear in the same order:
        search → ingest → analyse → [report] → [synthesize] → [qa] → save

    Synthesis and QA only make sense when there's a Report to operate on,
    so when ``with_report=False`` the ``with_synthesis`` and ``with_qa``
    toggles are silently dropped from the stage list. The orchestrator
    enforces the same invariant before dispatching the agents.
    """
    stages: list[dict[str, str]] = [
        {"key": STAGE_SEARCH,  "label": "Tìm kiếm tài liệu"},
        {"key": STAGE_INGEST,  "label": "Nạp tài liệu vào dự án"},
        {"key": STAGE_ANALYSE, "label": "Phân tích từng tài liệu"},
    ]
    if with_report:
        stages.append({"key": STAGE_REPORT, "label": "Tạo báo cáo dự án"})
        if with_synthesis:
            stages.append(
                {"key": STAGE_SYNTHESIZE, "label": "Tổng hợp báo cáo bằng AI"}
            )
        if with_qa:
            stages.append(
                {"key": STAGE_QA, "label": "Kiểm chất lượng báo cáo"}
            )
    stages.append({"key": STAGE_SAVE, "label": "Hoàn tất"})
    return stages

_MAX_EVENTS = 40


# ─────────────────────────────────────────────────────────────────────────────


class ResearchProgressTracker:
    """Persist live progress of a research / auto-research pipeline.

    All writes go to the ``research_sessions.progress`` JSONB column via
    explicit UPDATE statements so we never clobber concurrent updates the
    main pipeline writes (``status``, ``results_count``, etc.).

    DB errors are caught and logged but never raised — progress writes
    must NEVER kill the pipeline.
    """

    def __init__(
        self,
        db: AsyncSession,
        research_session_id: UUID,
        *,
        mode: str = "simple",  # "simple" | "auto"
        stages: list[dict[str, str]] | None = None,
    ) -> None:
        self.db = db
        self.research_session_id = research_session_id
        self.mode = mode
        self._stage_started_at: dict[str, float] = {}

        # Caller can override the canonical stage list — used by
        # AutoResearchService to add optional report / synthesise / qa
        # stages without baking the full cross-product into the tracker.
        if stages is not None:
            stage_list = list(stages)
        elif mode == "auto":
            stage_list = list(CANONICAL_STAGES_AUTO)
        else:
            stage_list = list(CANONICAL_STAGES_SIMPLE)
        self._state: dict[str, Any] = {
            "mode": mode,
            "stages": stage_list,
            "current_stage": None,
            "current_stage_label": None,
            "current_detail": None,
            "completed_stages": [],
            # Inner counter for stages that loop over a list (ingest /
            # analyse). FE renders this as "Tài liệu 2/3: Foo".
            "item_progress": None,
            "events": [],
            "started_at": _now_iso(),
        }

    # ── Public lifecycle ────────────────────────────────────────────────────

    async def init(self, query: str | None = None) -> None:
        """Reset the tracker state. Call once at pipeline start."""
        self._state["events"] = []
        self._state["completed_stages"] = []
        self._state["current_stage"] = None
        self._state["current_stage_label"] = None
        self._state["current_detail"] = None
        self._state["item_progress"] = None
        self._state["started_at"] = _now_iso()
        msg = "Khởi động pipeline nghiên cứu"
        if query:
            msg += f": '{query[:120]}'"
        self._append_event(msg, level="info")
        await self._flush()

    async def start_stage(
        self, key: str, detail: str | None = None
    ) -> None:
        label = self._label_for(key)
        self._stage_started_at[key] = time.monotonic()
        self._state["current_stage"] = key
        self._state["current_stage_label"] = label
        self._state["current_detail"] = detail
        # New stage clears the inner counter from the previous stage so
        # the FE doesn't show "2/3" left over from ingest while analyse
        # is just getting started.
        self._state["item_progress"] = None
        self._append_event(
            f"Đang {label.lower()}" + (f": {detail}" if detail else ""),
            level="running",
        )
        await self._flush()

    async def finish_stage(
        self, key: str, message: str | None = None
    ) -> None:
        label = self._label_for(key)
        started = self._stage_started_at.pop(key, None)
        duration_ms = (
            int((time.monotonic() - started) * 1000)
            if started is not None
            else None
        )
        if key not in self._state["completed_stages"]:
            self._state["completed_stages"].append(key)
        if self._state.get("current_stage") == key:
            self._state["current_stage"] = None
            self._state["current_detail"] = None
            self._state["item_progress"] = None
        suffix = f" ({duration_ms} ms)" if duration_ms is not None else ""
        self._append_event(
            f"✓ {label}{(' — ' + message) if message else ''}{suffix}",
            level="done",
        )
        await self._flush()

    async def update_item_progress(
        self,
        done: int,
        total: int,
        current_title: str | None = None,
        current_analysis_id: str | None = None,
    ) -> None:
        """Update the per-item counter inside a long-running stage.

        ``current_analysis_id`` is recorded so the frontend can poll the
        analysis-level progress endpoint and render its sub-steps inside
        the research progress panel — giving the user a unified view of
        the entire pipeline in one place.
        """
        self._state["item_progress"] = {
            "done": done,
            "total": total,
            "current_title": current_title,
            "current_analysis_id": current_analysis_id,
        }
        if current_title:
            self._state["current_detail"] = (
                f"Tài liệu {min(done + 1, total)}/{total}: {current_title}"
            )
        await self._flush()

    async def fail_stage(self, key: str, error_message: str) -> None:
        label = self._label_for(key)
        self._state["current_stage"] = key
        self._state["current_stage_label"] = label
        self._state["current_detail"] = f"Lỗi: {error_message[:200]}"
        self._append_event(
            f"✗ {label} thất bại: {error_message[:200]}",
            level="error",
        )
        await self._flush()

    async def log(self, message: str, level: str = "info") -> None:
        """Add a free-form activity-log entry without changing stage state."""
        self._append_event(message, level=level)
        await self._flush()

    async def finalize(
        self, status: str, message: str | None = None
    ) -> None:
        self._state["current_stage"] = None
        self._state["current_detail"] = None
        self._state["item_progress"] = None
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

    # ── Internals ───────────────────────────────────────────────────────────

    def _label_for(self, key: str) -> str:
        for s in self._state["stages"]:
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
                update(ResearchSession)
                .where(ResearchSession.id == self.research_session_id)
                .values(progress=dict(self._state))
            )
            await self.db.execute(stmt)
            await self.db.commit()
        except Exception as e:
            logger.warning(
                f"ResearchProgressTracker: failed to persist progress for "
                f"{self.research_session_id}: {e}"
            )
            try:
                await self.db.rollback()
            except Exception:
                pass


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
