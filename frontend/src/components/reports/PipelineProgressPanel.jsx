import {
  Loader,
  CheckCircle2,
  Circle,
  AlertCircle,
  Cpu,
} from "lucide-react";

/**
 * Generic compact pipeline progress card — renders a status header, a
 * progress bar, a horizontal step stepper, and the current detail line.
 *
 * Used identically by ``SynthesisProgressPanel`` and ``QAProgressPanel``;
 * the only difference between them is the ``steps`` array, the ``label``,
 * and the accent color, which the parent passes in. Keeping the shared
 * shell here lets us match the visual language of
 * ``AnalysisProgressInline`` and ``ResearchProgressPanel`` without the
 * copy-paste risk.
 *
 * Backend tracker JSONB shape (synthesis_progress / qa_progress):
 *   {
 *     current_step: string | null,
 *     current_step_label: string,
 *     current_detail: string | null,
 *     completed_steps: string[],
 *     steps: { key, label }[],   // canonical order from backend
 *     events: { ts, level, message }[],
 *     provider: string,
 *     model:    string,
 *   }
 */
const PipelineProgressPanel = ({
  title,
  status,
  errorMessage,
  progress,
  defaultSteps,
  accent = "blue", // "blue" | "violet" | "emerald" | "rose"
}) => {
  const steps = progress?.steps?.length ? progress.steps : defaultSteps || [];
  const completedSet = new Set(progress?.completed_steps || []);
  const currentStep = progress?.current_step || null;
  const failed = status === "failed";
  const running = status === "running";
  const total = steps.length;
  const completedCount = steps.filter((s) =>
    completedSet.has(s.key)
  ).length;
  const percent =
    status === "completed"
      ? 100
      : total === 0
      ? 0
      : Math.min(
          100,
          Math.round(
            ((completedCount + (currentStep ? 0.4 : 0)) / total) * 100
          )
        );

  const tones = ACCENT_TONES[failed ? "rose" : accent] || ACCENT_TONES.blue;

  return (
    <div className={`rounded-2xl border ${tones.border} ${tones.bg} p-5 shadow-sm`}>
      {/* Header */}
      <div className="flex items-start justify-between gap-3 mb-4 flex-wrap">
        <div className="flex items-center gap-3 min-w-0">
          {running ? (
            <Loader className={`w-5 h-5 ${tones.icon} animate-spin flex-shrink-0`} />
          ) : failed ? (
            <AlertCircle className="w-5 h-5 text-rose-600 flex-shrink-0" />
          ) : (
            <Loader className="w-5 h-5 text-slate-400 animate-spin flex-shrink-0" />
          )}
          <div className="min-w-0">
            <p className="text-sm font-bold text-slate-900">
              {failed
                ? `${title} thất bại`
                : running
                ? `Đang ${title.toLowerCase()}`
                : `Đang chờ ${title.toLowerCase()}`}
            </p>
            {progress?.provider && (
              <p className="text-[11px] text-slate-500 mt-0.5 flex items-center gap-1.5">
                <Cpu className="w-3 h-3" />
                <span className="font-mono">
                  {progress.provider}:{progress.model || "?"}
                </span>
              </p>
            )}
          </div>
        </div>

        <div className="text-right">
          <div className="text-xl font-bold text-slate-900 tabular-nums">
            {percent}%
          </div>
          <div className="text-[10px] text-slate-500 uppercase tracking-wide">
            tiến độ
          </div>
        </div>
      </div>

      {/* Progress bar */}
      <div className="w-full h-1.5 bg-slate-200/60 rounded-full overflow-hidden mb-4">
        <div
          className={`h-full bg-gradient-to-r ${tones.bar} transition-all duration-500 rounded-full`}
          style={{ width: `${percent}%` }}
        />
      </div>

      {/* Stepper */}
      <div className="flex items-stretch gap-1 mb-2 overflow-x-auto pb-1">
        {steps.map((s, idx) => {
          const done = completedSet.has(s.key);
          const active = currentStep === s.key && !done;
          const stepFailed = failed && active;
          return (
            <SubStepChip
              key={s.key}
              index={idx + 1}
              label={s.label}
              done={done}
              active={active}
              failed={stepFailed}
              accent={accent}
            />
          );
        })}
      </div>

      {progress?.current_detail && !failed && (
        <p className="text-xs text-slate-600 mt-2 leading-snug">
          <span className="font-semibold">
            {progress.current_step_label || "Đang xử lý"}:
          </span>{" "}
          {progress.current_detail}
        </p>
      )}

      {failed && errorMessage && (
        <p className="text-xs text-rose-700 mt-2 leading-snug break-words">
          {errorMessage}
        </p>
      )}
    </div>
  );
};

const ACCENT_TONES = {
  blue: {
    border: "border-blue-200",
    bg: "bg-blue-50/30",
    icon: "text-blue-600",
    bar: "from-blue-600 via-teal-500 to-emerald-500",
  },
  violet: {
    border: "border-violet-200",
    bg: "bg-violet-50/30",
    icon: "text-violet-600",
    bar: "from-violet-600 via-fuchsia-500 to-pink-500",
  },
  emerald: {
    border: "border-emerald-200",
    bg: "bg-emerald-50/30",
    icon: "text-emerald-600",
    bar: "from-emerald-500 to-teal-500",
  },
  rose: {
    border: "border-rose-200",
    bg: "bg-rose-50/30",
    icon: "text-rose-600",
    bar: "from-rose-500 to-red-500",
  },
};

const SubStepChip = ({ index, label, done, active, failed, accent }) => {
  const activeRing =
    accent === "violet"
      ? "border-violet-400 bg-violet-50 text-violet-700"
      : accent === "emerald"
      ? "border-emerald-400 bg-emerald-50 text-emerald-700"
      : "border-blue-400 bg-blue-50 text-blue-700";

  const cls = failed
    ? "border-rose-300 bg-rose-50 text-rose-700"
    : done
    ? "border-emerald-300 bg-emerald-50 text-emerald-700"
    : active
    ? activeRing
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
      className={`flex flex-col items-center gap-0.5 px-2 py-1.5 rounded-lg border min-w-[80px] flex-1 transition-all ${cls}`}
      title={label}
    >
      <div className="flex items-center gap-1">
        <Icon
          className={`w-3 h-3 ${active && !failed ? "animate-spin" : ""}`}
        />
        <span className="text-[9px] font-mono opacity-60">#{index}</span>
      </div>
      <span className="text-[10px] font-semibold leading-tight text-center line-clamp-2">
        {label}
      </span>
    </div>
  );
};

export default PipelineProgressPanel;
