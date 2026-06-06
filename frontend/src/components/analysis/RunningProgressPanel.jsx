import { useMemo, useState } from "react";
import {
  Loader,
  CheckCircle2,
  Circle,
  AlertCircle,
  Cpu,
  ChevronDown,
  ChevronUp,
} from "lucide-react";

/**
 * Compact progress panel for an analysis that is still pending or running.
 * Layout:
 *   ┌──────────────────────────────────────────────────────────┐
 *   │ Header: status pill + provider:model                      │
 *   │ Big progress bar with % + current step label              │
 *   │ Horizontal stepper of N chips (✓ / ◐ / ○)                 │
 *   │ Detail line for the current step (e.g. "Section 3/7")     │
 *   │ ▾ Activity log (collapsible, default closed)              │
 *   └──────────────────────────────────────────────────────────┘
 *
 * This is the "full" analysis-results-page version. The smaller
 * ``AnalysisProgressInline`` is for the project-detail page where
 * multiple progress panels share screen space.
 */
const RunningProgressPanel = ({ status, progress, errorMessage }) => {
  const [logOpen, setLogOpen] = useState(false);

  const steps = progress?.steps?.length ? progress.steps : DEFAULT_STEPS;
  const completedSet = useMemo(
    () => new Set(progress?.completed_steps || []),
    [progress?.completed_steps]
  );
  const currentStep = progress?.current_step || null;

  const percent = useMemo(() => {
    if (status === "completed") return 100;
    const total = steps.length;
    if (!total) return 0;

    let acc = 0;
    for (const s of steps) {
      if (completedSet.has(s.key)) {
        acc += 1;
      } else if (s.key === currentStep) {
        if (s.key === "analyse_sections" && progress?.section_progress) {
          const { done = 0, total: secTotal = 1 } = progress.section_progress;
          acc += secTotal > 0 ? done / secTotal : 0;
        } else {
          acc += 0.4;
        }
        break;
      }
    }
    return Math.min(100, Math.round((acc / total) * 100));
  }, [status, steps, completedSet, currentStep, progress?.section_progress]);

  const isFailed = status === "failed";
  const isRunning = status === "running";
  const isPending = status === "pending";

  const headerColor = isFailed
    ? "border-red-200 bg-red-50/40"
    : isRunning
    ? "border-blue-200 bg-blue-50/40"
    : "border-slate-200 bg-slate-50/40";

  const barColor = isFailed
    ? "from-red-500 to-red-400"
    : "from-blue-600 via-teal-500 to-emerald-500";

  return (
    <div className={`rounded-2xl border ${headerColor} p-6 shadow-sm`}>
      {/* Header */}
      <div className="flex items-start justify-between gap-3 mb-5 flex-wrap">
        <div className="flex items-center gap-3 min-w-0">
          {isRunning ? (
            <Loader className="w-6 h-6 text-blue-600 animate-spin flex-shrink-0" />
          ) : isFailed ? (
            <AlertCircle className="w-6 h-6 text-red-600 flex-shrink-0" />
          ) : (
            <Loader className="w-6 h-6 text-slate-400 animate-spin flex-shrink-0" />
          )}
          <div className="min-w-0">
            <p className="text-sm font-bold text-slate-900">
              {isFailed
                ? "Phân tích thất bại"
                : isPending
                ? "Đang chờ xử lý"
                : "Đang phân tích tài liệu"}
            </p>
            {progress?.provider && (
              <p className="text-xs text-slate-500 mt-0.5 flex items-center gap-1.5 truncate">
                <Cpu className="w-3 h-3 flex-shrink-0" />
                <span className="font-mono truncate">
                  {progress.provider}:{progress.model || ""}
                </span>
              </p>
            )}
          </div>
        </div>

        <div className="text-right">
          <div className="text-2xl font-bold text-slate-900 tabular-nums">
            {percent}%
          </div>
          <div className="text-[11px] text-slate-500 uppercase tracking-wide">
            tiến độ
          </div>
        </div>
      </div>

      {/* Progress bar */}
      <div className="w-full h-2 bg-slate-200/60 rounded-full overflow-hidden mb-5">
        <div
          className={`h-full bg-gradient-to-r ${barColor} transition-all duration-500 rounded-full`}
          style={{ width: `${percent}%` }}
        />
      </div>

      {/* Stepper */}
      <div className="flex items-stretch gap-1.5 mb-4 overflow-x-auto pb-1">
        {steps.map((s, idx) => {
          const done = completedSet.has(s.key);
          const active = currentStep === s.key && !done;
          const failed = isFailed && active;
          return (
            <StepChip
              key={s.key}
              index={idx + 1}
              label={s.label}
              done={done}
              active={active}
              failed={failed}
            />
          );
        })}
      </div>

      {/* Current detail */}
      {(progress?.current_detail || progress?.current_step_label) && !isFailed && (
        <div className="flex items-center gap-2 px-4 py-3 bg-white rounded-xl border border-slate-200 mb-3">
          <Loader className="w-4 h-4 text-blue-600 animate-spin flex-shrink-0" />
          <p className="text-sm text-slate-700 leading-snug">
            <span className="font-semibold">
              {progress.current_step_label || "Đang xử lý"}:
            </span>{" "}
            <span className="text-slate-600">
              {progress.current_detail || "..."}
            </span>
          </p>
        </div>
      )}

      {/* Failed detail */}
      {isFailed && errorMessage && (
        <div className="px-4 py-3 bg-red-50 border border-red-200 rounded-xl text-sm text-red-700 mb-3">
          <p className="font-semibold mb-1">Chi tiết lỗi</p>
          <p className="text-red-600 break-words">{errorMessage}</p>
        </div>
      )}

      {/* Activity log */}
      {(progress?.events?.length || 0) > 0 && (
        <button
          type="button"
          onClick={() => setLogOpen((v) => !v)}
          className="w-full flex items-center justify-between px-3 py-2 text-xs font-semibold text-slate-600 hover:text-slate-900 hover:bg-slate-100/60 rounded-lg transition-colors"
        >
          <span className="flex items-center gap-2">
            <span>Lịch sử hoạt động</span>
            <span className="px-1.5 py-0.5 rounded bg-slate-200 text-slate-700 text-[10px] font-bold">
              {progress.events.length}
            </span>
          </span>
          {logOpen ? (
            <ChevronUp className="w-4 h-4" />
          ) : (
            <ChevronDown className="w-4 h-4" />
          )}
        </button>
      )}

      {logOpen && progress?.events?.length > 0 && (
        <div className="mt-2 max-h-56 overflow-y-auto no-scrollbar bg-white rounded-xl border border-slate-200 divide-y divide-slate-100">
          {[...progress.events].reverse().map((ev, idx) => (
            <EventRow key={`${ev.ts}-${idx}`} event={ev} />
          ))}
        </div>
      )}
    </div>
  );
};

const StepChip = ({ index, label, done, active, failed }) => {
  const cls = failed
    ? "border-red-300 bg-red-50 text-red-700"
    : done
    ? "border-emerald-300 bg-emerald-50 text-emerald-700"
    : active
    ? "border-blue-400 bg-blue-50 text-blue-700 ring-2 ring-blue-200"
    : "border-slate-200 bg-white text-slate-500";

  const Icon = failed
    ? AlertCircle
    : done
    ? CheckCircle2
    : active
    ? Loader
    : Circle;

  return (
    <div
      className={`flex flex-col items-center gap-1.5 px-3 py-2 rounded-xl border min-w-[110px] flex-1 transition-all ${cls}`}
    >
      <div className="flex items-center gap-1.5">
        <Icon
          className={`w-3.5 h-3.5 ${active && !failed ? "animate-spin" : ""}`}
        />
        <span className="text-[10px] font-mono opacity-60">#{index}</span>
      </div>
      <span className="text-[11px] font-semibold leading-tight text-center">
        {label}
      </span>
    </div>
  );
};

const EventRow = ({ event }) => {
  const level = event.level || "info";
  const tone =
    level === "done"
      ? "text-emerald-700"
      : level === "running"
      ? "text-blue-700"
      : level === "error"
      ? "text-red-700"
      : "text-slate-700";
  return (
    <div className="px-3 py-2 flex items-start gap-3 text-xs">
      <span className="text-[10px] text-slate-400 font-mono whitespace-nowrap min-w-[58px]">
        {formatTime(event.ts)}
      </span>
      <span className={`flex-1 ${tone}`}>{event.message}</span>
    </div>
  );
};

const DEFAULT_STEPS = [
  { key: "load_chunks",      label: "Tải chunks" },
  { key: "map_sections",     label: "Chia phần" },
  { key: "build_outline",    label: "Outline" },
  { key: "analyse_sections", label: "Phân tích phần" },
  { key: "synthesize",       label: "Tổng hợp & tóm tắt" },
  { key: "persist",          label: "Lưu kết quả" },
];

const formatTime = (iso) => {
  if (!iso) return "";
  try {
    const d = new Date(iso);
    return d.toLocaleTimeString("vi-VN", {
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
    });
  } catch {
    return "";
  }
};

export default RunningProgressPanel;
