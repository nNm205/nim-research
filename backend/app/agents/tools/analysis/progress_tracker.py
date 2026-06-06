"""ProgressTracker — write live pipeline progress to ``document_analyses.progress``.

The Analysis pipeline is a fixed sequence of named steps. The tracker:
- Knows the canonical step order (so the FE can render a stepper).
- Marks each step start / end and persists via UPDATE statements (no ORM
  object mutation — works even if the analysis row was concurrently
  refreshed elsewhere).
- Tracks per-section progress inside the long-running ``analyse_sections``
  step so the UI can show "Section 3/7: Model Architecture".
- Keeps a small ``events`` list (capped) for an activity log feed.

Each write is its own short transaction so an FE polling loop sees fresh
data within a couple of seconds.
"""

from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.analysis import DocumentAnalysis
from app.utils.logger import logger


# ── Canonical step order (also drives the FE stepper) ──────────────────────

STEP_LOAD_CHUNKS = "load_chunks"
STEP_MAP_SECTIONS = "map_sections"
STEP_BUILD_OUTLINE = "build_outline"
STEP_ANALYSE_SECTIONS = "analyse_sections"
STEP_SYNTHESIZE = "synthesize"
STEP_PERSIST = "persist"

# Kept as an alias for backward compatibility — older code paths may still
# import this. The pipeline no longer has a dedicated final-summary step;
# the executive summary is produced inside STEP_SYNTHESIZE.
STEP_FINAL_SUMMARY = STEP_SYNTHESIZE

CANONICAL_STEPS: list[dict[str, str]] = [
    {"key": STEP_LOAD_CHUNKS,      "label": "Tải chunks tài liệu"},
    {"key": STEP_MAP_SECTIONS,     "label": "Chia tài liệu thành các phần"},
    {"key": STEP_BUILD_OUTLINE,    "label": "Xây outline tài liệu"},
    {"key": STEP_ANALYSE_SECTIONS, "label": "Phân tích từng phần"},
    {"key": STEP_SYNTHESIZE,       "label": "Tổng hợp & viết tóm tắt"},
    {"key": STEP_PERSIST,          "label": "Lưu kết quả"},
]

_STEP_KEYS = [s["key"] for s in CANONICAL_STEPS]
_MAX_EVENTS = 30


# ──────────────────────────────────────────────────────────────────────────


class ProgressTracker:
    """Writes pipeline progress into ``document_analyses.progress`` JSONB."""

    def __init__(self, db: AsyncSession, analysis_id: UUID) -> None:
        self.db = db
        self.analysis_id = analysis_id
        self._step_started_at: dict[str, float] = {}
        # In-memory mirror so we don't have to read-modify-write each tick.
        self._state: dict[str, Any] = {
            "current_step": None,
            "current_step_label": None,
            "current_detail": None,
            "completed_steps": [],
            "steps": list(CANONICAL_STEPS),
            "section_progress": None,
            "events": [],
            "started_at": _now_iso(),
            "provider": None,
            "model": None,
        }

    # ── Public lifecycle ─────────────────────────────────────────────────

    async def init(self, provider: str | None = None, model: str | None = None) -> None:
        """Reset progress for a new run. Call once when the agent starts."""
        self._state["provider"] = provider
        self._state["model"] = model
        self._state["events"] = []
        self._state["completed_steps"] = []
        self._state["current_step"] = None
        self._state["current_step_label"] = None
        self._state["current_detail"] = None
        self._state["section_progress"] = None
        self._state["started_at"] = _now_iso()
        self._append_event(
            f"Bắt đầu phân tích bằng {provider}:{model}" if provider else "Bắt đầu phân tích",
            level="info",
        )
        await self._flush()

    async def start_step(
        self,
        key: str,
        detail: str | None = None,
    ) -> None:
        """Mark the start of a named step."""
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

    async def finish_step(
        self,
        key: str,
        message: str | None = None,
    ) -> None:
        """Mark a step done and record the message + duration."""
        label = self._label_for(key)
        started = self._step_started_at.pop(key, None)
        duration_ms = (
            int((time.monotonic() - started) * 1000) if started is not None else None
        )

        if key not in self._state["completed_steps"]:
            self._state["completed_steps"].append(key)

        # Clear current_step only if the step we're finishing is the current one.
        if self._state.get("current_step") == key:
            self._state["current_step"] = None
            self._state["current_detail"] = None
            self._state["section_progress"] = None

        suffix = f" ({duration_ms} ms)" if duration_ms is not None else ""
        self._append_event(
            f"✓ {label}{(' — ' + message) if message else ''}{suffix}",
            level="done",
        )
        await self._flush()

    async def update_section_progress(
        self, done: int, total: int, current_title: str | None
    ) -> None:
        """Refresh the inner section-loop progress counter."""
        self._state["section_progress"] = {
            "done": done,
            "total": total,
            "current_title": current_title,
        }
        if current_title:
            self._state["current_detail"] = (
                f"Section {done + 1}/{total}: {current_title}"
            )
        await self._flush()

    async def fail_step(
        self,
        key: str,
        error_message: str,
    ) -> None:
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
        """Mark the whole run finished (status = 'completed' | 'failed')."""
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

    # ── Internals ────────────────────────────────────────────────────────

    def _label_for(self, key: str) -> str:
        for s in CANONICAL_STEPS:
            if s["key"] == key:
                return s["label"]
        return key

    def _append_event(self, message: str, level: str) -> None:
        events = self._state.setdefault("events", [])
        events.append(
            {
                "ts": _now_iso(),
                "level": level,
                "message": message,
            }
        )
        if len(events) > _MAX_EVENTS:
            del events[: len(events) - _MAX_EVENTS]

    async def _flush(self) -> None:
        """Persist the current state via a single UPDATE.

        Uses an explicit UPDATE statement so we don't accidentally clobber
        other fields the pipeline is mutating in parallel (e.g. status). Any
        DB error is logged and swallowed — progress writes must NEVER kill
        the analysis pipeline.
        """
        try:
            stmt = (
                update(DocumentAnalysis)
                .where(DocumentAnalysis.id == self.analysis_id)
                .values(progress=dict(self._state))
            )
            await self.db.execute(stmt)
            await self.db.commit()
        except Exception as e:
            logger.warning(
                f"ProgressTracker: failed to persist progress for "
                f"{self.analysis_id}: {e}"
            )
            try:
                await self.db.rollback()
            except Exception:
                pass


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
