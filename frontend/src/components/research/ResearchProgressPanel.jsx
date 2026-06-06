import { useMemo, useState } from "react";
import {
  Loader,
  CheckCircle2,
  Circle,
  AlertCircle,
  ChevronDown,
  ChevronUp,
  Wand2,
  Search,
} from "lucide-react";
import AnalysisProgressInline from "../analysis/AnalysisProgressInline";

/**
 * Live-progress panel for a research session (ordinary or auto-research).
 *
 * The backend's ``ResearchProgressTracker`` writes a JSONB blob to
 * ``research_sessions.progress`` with this shape:
 *
 *   {
 *     mode: "simple" | "auto",
 *     stages: [{ key, label }, ...],
 *     current_stage: "search" | "ingest" | "analyse" | "save" | null,
 *     current_stage_label: string,
 *     current_detail: string | null,
 *     completed_stages: ["search", ...],
 *     item_progress: { done, total, current_title } | null,
 *     events: [{ ts, level, message }],
 *     started_at: ISO,
 *   }
 *
 * Rendered as: header status pill → big progress bar → horizontal stage
 * stepper → current detail line → optional activity log (collapsed).
 *
 * Same visual language as ``RunningProgressPanel`` (analysis pipeline),
 * which lives next door, so users learn the pattern once.
 */
const ResearchProgressPanel = ({
  status,
  progress,
  errorMessage,
  query,
  projectId,
}) => {
  const [logOpen, setLogOpen] = useState(false);

  const stages = progress?.stages?.length
    ? progress.stages
    : DEFAULT_SIMPLE_STAGES;
  const completedSet = useMemo(
    () => new Set(progress?.completed_stages || []),
    [progress?.completed_stages]
  );
  const currentStage = progress?.current_stage || null;
  const isAuto = progress?.mode === "auto";

  // Compute global percent. Each stage contributes 1/N. The ingest /
  // analyse stages can report fractional progress via item_progress so
  // the bar moves while a long-running batch grinds through papers.
  const percent = useMemo(() => {
    if (status === "completed") return 100;
    const total = stages.length;
    if (!total) return 0;

    let acc = 0;
    for (const s of stages) {
      if (completedSet.has(s.key)) {
        acc += 1;
      } else if (s.key === currentStage) {
        const ip = progress?.item_progress;
        if (ip && ip.total > 0) {
          acc += Math.min(1, ip.done / ip.total);
        } else {
          acc += 0.4; // mid-stage heuristic so the bar moves while the agent works
        }
        break;
      }
    }
    return Math.min(100, Math.round((acc / total) * 100));
  }, [status, stages, completedSet, currentStage, progress?.item_progress]);

  const isFailed = status === "failed";
  const isRunning = status === "running";
  const isPending = status === "pending";

  const headerColor = isFailed
    ? "border-red-200 bg-red-50/40"
    : isAuto
    ? "border-violet-200 bg-violet-50/30"
    : "border-blue-200 bg-blue-50/40";

  const barColor = isFailed
    ? "from-red-500 to-red-400"
    : isAuto
    ? "from-violet-600 via-fuchsia-500 to-pink-500"
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
            <p className="text-sm font-bold text-slate-900 flex items-center gap-2">
              {isFailed
                ? "Phiên nghiên cứu thất bại"
                : isPending
                ? "Đang chờ xử lý"
                : isAuto
                ? "Nghiên cứu tự động"
                : "Đang tìm kiếm tài liệu"}
              {isAuto && (
                <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wide bg-violet-100 text-violet-700">
                  <Wand2 className="w-3 h-3" />
                  AUTO
                </span>
              )}
            </p>
            {query && (
              <p className="text-xs text-slate-500 mt-0.5 flex items-center gap-1.5 truncate">
                <Search className="w-3 h-3 flex-shrink-0" />
                <span className="italic truncate">{query}</span>
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

      {/* Stage stepper */}
      <div className="flex items-stretch gap-1.5 mb-4 overflow-x-auto pb-1">
        {stages.map((s, idx) => {
          const done = completedSet.has(s.key);
          const active = currentStage === s.key && !done;
          const failed = isFailed && active;
          return (
            <StageChip
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
      {(progress?.current_detail || progress?.current_stage_label) &&
        !isFailed && (
          <div className="flex items-center gap-2 px-4 py-3 bg-white rounded-xl border border-slate-200 mb-3">
            <Loader className="w-4 h-4 text-blue-600 animate-spin flex-shrink-0" />
            <p className="text-sm text-slate-700 leading-snug">
              <span className="font-semibold">
                {progress.current_stage_label || "Đang xử lý"}:
              </span>{" "}
              <span className="text-slate-600">
                {progress.current_detail || "..."}
              </span>
            </p>
          </div>
        )}

      {/* Item-level progress (e.g. "Tài liệu 2/3: Foo Paper") */}
      {progress?.item_progress &&
        progress.item_progress.total > 0 &&
        !isFailed && (
          <ItemProgressRow ip={progress.item_progress} />
        )}

      {/* When the auto-research pipeline is mid-analyse, embed the
          AnalysisAgent's own per-step progress so the user has one
          unified view rather than chasing the live panel from page to
          page. We only render this nested view in auto mode. */}
      {isAuto && progress?.item_progress?.current_analysis_id && !isFailed && (
        <AnalysisProgressInline
          analysisId={progress.item_progress.current_analysis_id}
          projectId={projectId}
          embedded
        />
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

const StageChip = ({ index, label, done, active, failed }) => {
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
      className={`flex flex-col items-center gap-1.5 px-3 py-2 rounded-xl border min-w-[120px] flex-1 transition-all ${cls}`}
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

const ItemProgressRow = ({ ip }) => {
  const pct = Math.min(100, Math.round((ip.done / ip.total) * 100));
  return (
    <div className="px-4 py-3 bg-white rounded-xl border border-slate-200 mb-3">
      <div className="flex items-center justify-between gap-3 mb-2">
        <span className="text-xs font-semibold text-slate-700">
          Tài liệu{" "}
          <span className="tabular-nums">
            {Math.min(ip.done + (ip.current_title ? 1 : 0), ip.total)}
          </span>
          /<span className="tabular-nums">{ip.total}</span>
        </span>
        <span className="text-xs font-bold text-slate-900 tabular-nums">
          {pct}%
        </span>
      </div>
      <div className="w-full h-1.5 bg-slate-200/60 rounded-full overflow-hidden">
        <div
          className="h-full bg-gradient-to-r from-blue-500 to-teal-500 transition-all duration-500 rounded-full"
          style={{ width: `${pct}%` }}
        />
      </div>
      {ip.current_title && (
        <p className="text-xs text-slate-600 mt-2 truncate" title={ip.current_title}>
          {ip.current_title}
        </p>
      )}
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

const DEFAULT_SIMPLE_STAGES = [
  { key: "search", label: "Tìm kiếm tài liệu" },
  { key: "save",   label: "Lưu kết quả" },
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

export default ResearchProgressPanel;
