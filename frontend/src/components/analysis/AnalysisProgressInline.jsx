import { useEffect, useState } from "react";
import { Loader, CheckCircle2, Circle, AlertCircle, Cpu } from "lucide-react";
import { analysisService } from "../../services/analysisService";

/**
 * Compact inline progress view for a single DocumentAnalysis.
 *
 * Used in two places:
 *   1. Standalone — at the top of ProjectDetailPage when the user kicks
 *      off "Phân tích tài liệu" (single document, no auto-research).
 *   2. Nested — inside ResearchProgressPanel's auto-mode body, showing
 *      the inner pipeline of the document the orchestrator is currently
 *      analysing.
 *
 * Polls the AnalysisAgent's status endpoint every 3 s and renders a
 * 6-step horizontal stepper plus a one-line current-detail label. We
 * deliberately keep this much smaller than the section-by-section
 * RunningProgressPanel that lives on the analysis results page — at
 * the project level the user only needs a high-level "where is it
 * now?" indicator.
 */
const ANALYSIS_STEPS = [
  { key: "load_chunks",      label: "Tải chunks" },
  { key: "map_sections",     label: "Chia phần" },
  { key: "build_outline",    label: "Outline" },
  { key: "analyse_sections", label: "Phân tích phần" },
  { key: "synthesize",       label: "Tổng hợp & tóm tắt" },
  { key: "persist",          label: "Lưu" },
];

const AnalysisProgressInline = ({
  projectId,
  analysisId,
  // When ``embedded`` is true we render with reduced padding/border so
  // the panel slots cleanly inside another card. When false we render
  // as a standalone card with our own border/shadow.
  embedded = false,
  documentTitle,
}) => {
  const [analysis, setAnalysis] = useState(null);

  useEffect(() => {
    if (!analysisId || !projectId) return undefined;
    let cancelled = false;

    const tick = async () => {
      try {
        const data = await analysisService.getAnalysisStatus(
          projectId,
          analysisId,
        );
        if (!cancelled) setAnalysis(data);
      } catch {
        // silent — retry on next tick
      }
    };
    tick();
    const handle = setInterval(tick, 3000);
    return () => {
      cancelled = true;
      clearInterval(handle);
    };
  }, [analysisId, projectId]);

  if (!analysis) {
    return (
      <div
        className={
          embedded
            ? "px-4 py-3 bg-white rounded-xl border border-slate-200 mb-3 text-xs text-slate-500 flex items-center gap-2"
            : "rounded-2xl border border-slate-200 bg-white p-6 shadow-sm text-sm text-slate-500 flex items-center gap-2"
        }
      >
        <Loader className="w-4 h-4 animate-spin" />
        Đang tải tiến trình phân tích...
      </div>
    );
  }

  const progress = analysis.progress || {};
  const completedSet = new Set(progress.completed_steps || []);
  const currentStep = progress.current_step || null;
  const failed = analysis.status === "failed";
  const running = analysis.status === "running";
  const total = ANALYSIS_STEPS.length;
  const completed = ANALYSIS_STEPS.filter((s) =>
    completedSet.has(s.key),
  ).length;
  const percent =
    analysis.status === "completed"
      ? 100
      : Math.round((completed / total) * 100);

  // Standalone outer wrapper or embedded inline wrapper.
  const Wrapper = embedded ? "div" : "section";
  const wrapperClass = embedded
    ? "px-4 py-3 bg-white rounded-xl border border-slate-200 mb-3"
    : "rounded-2xl border border-blue-200 bg-blue-50/30 p-6 shadow-sm";

  return (
    <Wrapper className={wrapperClass}>
      {!embedded && (
        <div className="flex items-start justify-between gap-3 mb-4 flex-wrap">
          <div className="flex items-center gap-3 min-w-0">
            {running ? (
              <Loader className="w-5 h-5 text-blue-600 animate-spin flex-shrink-0" />
            ) : failed ? (
              <AlertCircle className="w-5 h-5 text-red-600 flex-shrink-0" />
            ) : (
              <Loader className="w-5 h-5 text-slate-400 animate-spin flex-shrink-0" />
            )}
            <div className="min-w-0">
              <p className="text-sm font-bold text-slate-900">
                {failed
                  ? "Phân tích thất bại"
                  : running
                  ? "Đang phân tích tài liệu"
                  : "Đang chờ phân tích"}
              </p>
              {documentTitle && (
                <p className="text-xs text-slate-500 mt-0.5 truncate">
                  {documentTitle}
                </p>
              )}
              {progress.provider && (
                <p className="text-[11px] text-slate-500 mt-0.5 flex items-center gap-1.5">
                  <Cpu className="w-3 h-3" />
                  <span className="font-mono">
                    {progress.provider}:{progress.model || ""}
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
      )}

      {!embedded && (
        <div className="w-full h-1.5 bg-slate-200/60 rounded-full overflow-hidden mb-4">
          <div
            className={`h-full bg-gradient-to-r ${
              failed
                ? "from-red-500 to-red-400"
                : "from-blue-600 via-teal-500 to-emerald-500"
            } transition-all duration-500 rounded-full`}
            style={{ width: `${percent}%` }}
          />
        </div>
      )}

      {embedded && (
        <div className="flex items-center justify-between gap-3 mb-2.5">
          <p className="text-xs font-bold text-slate-700 uppercase tracking-wide">
            Pipeline phân tích
          </p>
          {running && (
            <span className="inline-flex items-center gap-1 text-[10px] font-bold uppercase tracking-wide text-blue-600">
              <Loader className="w-3 h-3 animate-spin" />
              đang chạy
            </span>
          )}
          {failed && (
            <span className="inline-flex items-center gap-1 text-[10px] font-bold uppercase tracking-wide text-red-600">
              <AlertCircle className="w-3 h-3" />
              lỗi
            </span>
          )}
        </div>
      )}

      <div className="flex items-stretch gap-1 mb-2 overflow-x-auto pb-1">
        {ANALYSIS_STEPS.map((s, idx) => {
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
            />
          );
        })}
      </div>

      {progress.current_detail && !failed && (
        <p className="text-xs text-slate-600 mt-1 leading-snug">
          <span className="font-semibold">
            {progress.current_step_label || "Đang xử lý"}:
          </span>{" "}
          {progress.current_detail}
        </p>
      )}

      {failed && analysis.error_message && (
        <p className="text-xs text-red-600 mt-1 leading-snug break-words">
          {analysis.error_message}
        </p>
      )}
    </Wrapper>
  );
};

const SubStepChip = ({ index, label, done, active, failed }) => {
  const cls = failed
    ? "border-red-300 bg-red-50 text-red-700"
    : done
    ? "border-emerald-300 bg-emerald-50 text-emerald-700"
    : active
    ? "border-blue-400 bg-blue-50 text-blue-700"
    : "border-slate-200 bg-slate-50 text-slate-500";

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
      <span className="text-[10px] font-semibold leading-tight text-center line-clamp-1">
        {label}
      </span>
    </div>
  );
};

export default AnalysisProgressInline;
