import { useState } from "react";
import {
  Wand2,
  ShieldCheck,
  Zap,
  Loader,
  CheckCircle2,
  AlertCircle,
  ArrowDownToLine,
  ChevronRight,
} from "lucide-react";
import PipelineProgressPanel from "./PipelineProgressPanel";
import { synthesisService } from "../../services/synthesisService";
import { qaService } from "../../services/qaService";

/**
 * AIEnhancementPanel — drives Synthesis + QA on a Report.
 *
 * Shows three primary actions:
 *
 *   1. "Tổng hợp bằng AI"  → SynthesisAgent rewrites Report.content as
 *                            a cross-document narrative with [n] cites.
 *                            Original template is snapshotted for rollback.
 *   2. "Kiểm chất lượng"   → QualityAssuranceAgent scores the current
 *                            content (whether template or synthesised)
 *                            and writes Report.qa_report.
 *   3. "Chạy đầy đủ"       → Synthesis followed by QA, in one click.
 *
 * Live progress (pipelined polling done by ``useReportEnhancement``) is
 * passed in by the parent so polling state can be shared with other
 * components on the page (e.g. the preview should refresh when synthesis
 * completes).
 */
const AIEnhancementPanel = ({
  reportId,
  synthesis,
  qa,
  onRefresh,
  onOpenQAReport,
  onAfterSynthesis,
}) => {
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");
  const [info, setInfo] = useState("");

  const synStatus = synthesis?.synthesis_status || null;
  const qaStatus = qa?.qa_status || null;
  const synBusy = synStatus === "pending" || synStatus === "running";
  const qaBusy = qaStatus === "pending" || qaStatus === "running";
  const anyBusy = synBusy || qaBusy || !!busy;

  const flash = (text) => {
    setInfo(text);
    setTimeout(() => setInfo(""), 3000);
  };

  const handleStartSynthesis = async () => {
    setBusy("synthesis");
    setError("");
    try {
      await synthesisService.start(reportId);
      flash("Đã bắt đầu tổng hợp bằng AI");
      await onRefresh?.();
    } catch (err) {
      setError(err.response?.data?.detail || "Không thể bắt đầu Synthesis");
    } finally {
      setBusy("");
    }
  };

  const handleStartQA = async () => {
    setBusy("qa");
    setError("");
    try {
      await qaService.start(reportId);
      flash("Đã bắt đầu kiểm chất lượng");
      await onRefresh?.();
    } catch (err) {
      setError(err.response?.data?.detail || "Không thể bắt đầu QA");
    } finally {
      setBusy("");
    }
  };

  const handleStartFullPipeline = async () => {
    setBusy("full");
    setError("");
    try {
      await synthesisService.runFullPipeline(reportId);
      flash("Đã bắt đầu Synthesis + QA");
      await onRefresh?.();
    } catch (err) {
      setError(
        err.response?.data?.detail || "Không thể bắt đầu pipeline đầy đủ"
      );
    } finally {
      setBusy("");
    }
  };

  const handleRollback = async () => {
    if (
      !window.confirm(
        "Khôi phục báo cáo về phiên bản trước khi tổng hợp AI? " +
          "Phiên bản tổng hợp hiện tại sẽ bị xóa."
      )
    )
      return;
    setBusy("rollback");
    setError("");
    try {
      await synthesisService.rollback(reportId);
      flash("Đã khôi phục bản gốc");
      // Trigger full reload of the report via the parent so the preview
      // flips back to the template-rendered HTML.
      await onAfterSynthesis?.();
      await onRefresh?.();
    } catch (err) {
      setError(err.response?.data?.detail || "Không thể khôi phục");
    } finally {
      setBusy("");
    }
  };

  const synProgress = synthesis?.synthesis_progress;
  const qaProgress = qa?.qa_progress;

  // QA stub from /qa/status only carries qa_progress. Score is on the
  // detail endpoint via /qa/report — we surface the score from
  // ``qa.qa_report?.overall_score`` if the parent passes the full report.
  const qaScore = qa?.qa_report?.overall_score;
  const qaVerdict = qa?.qa_report?.verdict;

  return (
    <div className="bg-white rounded-2xl border border-slate-200 p-6 shadow-sm space-y-5">
      <div className="flex items-start gap-3">
        <div className="p-2 rounded-xl bg-gradient-to-br from-violet-500 to-fuchsia-500 flex-shrink-0">
          <Wand2 className="w-4 h-4 text-white" />
        </div>
        <div>
          <h3 className="text-sm font-bold text-slate-900">AI Enhancement</h3>
          <p className="text-xs text-slate-500 mt-0.5 leading-snug">
            Tổng hợp lại narrative bằng LLM hoặc kiểm chất lượng báo cáo
          </p>
        </div>
      </div>

      {error && (
        <div className="flex items-start gap-2 bg-red-50 border border-red-200 text-red-700 px-3 py-2.5 rounded-lg text-xs">
          <AlertCircle className="w-3.5 h-3.5 flex-shrink-0 mt-0.5" />
          <span className="flex-1">{error}</span>
        </div>
      )}

      {info && (
        <div className="flex items-start gap-2 bg-emerald-50 border border-emerald-200 text-emerald-700 px-3 py-2.5 rounded-lg text-xs">
          <CheckCircle2 className="w-3.5 h-3.5 flex-shrink-0 mt-0.5" />
          <span>{info}</span>
        </div>
      )}

      {/* ── Synthesis row ─────────────────────────────────────────── */}
      <ActionRow
        icon={Wand2}
        iconTone="violet"
        title="Tổng hợp bằng AI"
        subtitle={synthesisSubtitle(synStatus, synthesis)}
        statusPill={statusPillFor(synStatus)}
        primaryLabel={
          synBusy
            ? "Đang chạy..."
            : synStatus === "completed"
            ? "Tổng hợp lại"
            : "Chạy Synthesis"
        }
        onPrimary={handleStartSynthesis}
        primaryDisabled={anyBusy}
        primaryBusy={busy === "synthesis"}
        secondary={
          synStatus === "completed" &&
          synthesis?.synthesis_metadata?.original_template_md
            ? {
                label: "Khôi phục bản gốc",
                icon: ArrowDownToLine,
                onClick: handleRollback,
                busy: busy === "rollback",
              }
            : null
        }
      />

      {/* ── QA row ────────────────────────────────────────────────── */}
      <ActionRow
        icon={ShieldCheck}
        iconTone="emerald"
        title="Kiểm chất lượng"
        subtitle={qaSubtitle(qaStatus, qaScore, qaVerdict)}
        statusPill={statusPillFor(qaStatus, { score: qaScore, verdict: qaVerdict })}
        primaryLabel={
          qaBusy
            ? "Đang chạy..."
            : qaStatus === "completed"
            ? "Chạy lại QA"
            : "Chạy QA"
        }
        onPrimary={handleStartQA}
        primaryDisabled={anyBusy}
        primaryBusy={busy === "qa"}
        secondary={
          qaStatus === "completed" && qa?.qa_report
            ? {
                label: "Xem báo cáo QA",
                icon: ChevronRight,
                onClick: () => onOpenQAReport?.(qa.qa_report),
                primary: true,
              }
            : null
        }
      />

      {/* ── Full pipeline ─────────────────────────────────────────── */}
      <button
        type="button"
        onClick={handleStartFullPipeline}
        disabled={anyBusy}
        className="w-full inline-flex items-center justify-center gap-2 px-4 py-3 bg-gradient-to-r from-violet-600 via-fuchsia-600 to-pink-600 hover:from-violet-700 hover:via-fuchsia-700 hover:to-pink-700 text-white rounded-xl font-bold text-sm shadow-md hover:shadow-lg transition-all disabled:opacity-50 disabled:cursor-not-allowed"
      >
        {busy === "full" ? (
          <Loader className="w-4 h-4 animate-spin" />
        ) : (
          <Zap className="w-4 h-4" />
        )}
        Chạy đầy đủ (Synthesis + QA)
      </button>

      {/* ── Live progress panels (only when actually running) ─────── */}
      {synBusy && (
        <PipelineProgressPanel
          title="Tổng hợp"
          status={synStatus}
          errorMessage={synthesis?.synthesis_error}
          progress={synProgress}
          accent="violet"
          defaultSteps={DEFAULT_SYNTHESIS_STEPS}
        />
      )}
      {qaBusy && (
        <PipelineProgressPanel
          title="Kiểm chất lượng"
          status={qaStatus}
          errorMessage={qa?.qa_error}
          progress={qaProgress}
          accent="emerald"
          defaultSteps={DEFAULT_QA_STEPS}
        />
      )}

      {/* Show failure detail even after the agent stops */}
      {synStatus === "failed" && !synBusy && synthesis?.synthesis_error && (
        <FailureBox
          title="Synthesis thất bại"
          message={synthesis.synthesis_error}
        />
      )}
      {qaStatus === "failed" && !qaBusy && qa?.qa_error && (
        <FailureBox title="QA thất bại" message={qa.qa_error} />
      )}
    </div>
  );
};

// ── Action row ─────────────────────────────────────────────────────────────

const ActionRow = ({
  icon: Icon,
  iconTone,
  title,
  subtitle,
  statusPill,
  primaryLabel,
  onPrimary,
  primaryDisabled,
  primaryBusy,
  secondary,
}) => {
  const iconBg =
    iconTone === "violet"
      ? "bg-violet-100 text-violet-600"
      : "bg-emerald-100 text-emerald-600";
  return (
    <div className="rounded-xl border border-slate-200 p-4">
      <div className="flex items-start gap-3">
        <div className={`p-1.5 rounded-lg ${iconBg} flex-shrink-0`}>
          <Icon className="w-3.5 h-3.5" />
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap mb-1">
            <span className="text-sm font-bold text-slate-900">{title}</span>
            {statusPill}
          </div>
          <p className="text-xs text-slate-500 leading-snug mb-3 line-clamp-2">
            {subtitle}
          </p>
          <div className="flex items-center gap-2 flex-wrap">
            <button
              type="button"
              onClick={onPrimary}
              disabled={primaryDisabled}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 border border-slate-200 hover:bg-slate-50 hover:border-slate-300 disabled:opacity-50 text-slate-700 rounded-lg font-semibold text-xs transition-colors"
            >
              {primaryBusy && <Loader className="w-3 h-3 animate-spin" />}
              {primaryLabel}
            </button>
            {secondary && (
              <button
                type="button"
                onClick={secondary.onClick}
                disabled={secondary.busy}
                className={`inline-flex items-center gap-1 px-3 py-1.5 rounded-lg font-semibold text-xs transition-colors ${
                  secondary.primary
                    ? "bg-emerald-600 hover:bg-emerald-700 text-white"
                    : "border border-slate-200 hover:bg-slate-50 text-slate-700"
                } disabled:opacity-50`}
              >
                {secondary.busy ? (
                  <Loader className="w-3 h-3 animate-spin" />
                ) : (
                  <secondary.icon className="w-3 h-3" />
                )}
                {secondary.label}
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};

// ── Status pills + subtitle helpers ────────────────────────────────────────

const statusPillFor = (status, extra) => {
  if (!status) return null;
  if (status === "running" || status === "pending") {
    return (
      <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-bold uppercase tracking-wide bg-blue-100 text-blue-700">
        <Loader className="w-2.5 h-2.5 animate-spin" />
        {status === "pending" ? "đang chờ" : "đang chạy"}
      </span>
    );
  }
  if (status === "completed") {
    if (extra?.score != null) {
      const v = extra.verdict || "good";
      const tone =
        v === "excellent"
          ? "bg-emerald-100 text-emerald-700"
          : v === "good"
          ? "bg-teal-100 text-teal-700"
          : v === "needs_review"
          ? "bg-amber-100 text-amber-700"
          : "bg-rose-100 text-rose-700";
      return (
        <span
          className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-bold uppercase tracking-wide ${tone}`}
        >
          <CheckCircle2 className="w-2.5 h-2.5" />
          {extra.score}/100
        </span>
      );
    }
    return (
      <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-bold uppercase tracking-wide bg-emerald-100 text-emerald-700">
        <CheckCircle2 className="w-2.5 h-2.5" />
        hoàn tất
      </span>
    );
  }
  if (status === "failed") {
    return (
      <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-bold uppercase tracking-wide bg-rose-100 text-rose-700">
        <AlertCircle className="w-2.5 h-2.5" />
        thất bại
      </span>
    );
  }
  return null;
};

const synthesisSubtitle = (status, synthesis) => {
  if (status === "completed") {
    const ts = synthesis?.synthesis_completed_at;
    return ts
      ? `Đã tổng hợp lúc ${new Date(ts).toLocaleString("vi-VN")}`
      : "Báo cáo đã được LLM viết lại với citations [n]";
  }
  if (status === "running") return "LLM đang viết narrative xuyên tài liệu...";
  if (status === "pending") return "Đang chờ trong queue...";
  if (status === "failed")
    return synthesis?.synthesis_error || "Pipeline gặp lỗi";
  return "Dùng LLM để tạo narrative liên kết các tài liệu, có citations và executive summary.";
};

const qaSubtitle = (status, score, verdict) => {
  if (status === "completed") {
    if (score != null) {
      return `Điểm ${score}/100 — ${VERDICT_LABEL[verdict] || verdict}`;
    }
    return "Đã có báo cáo QA";
  }
  if (status === "running") return "Đang kiểm format, citation, fact, grammar...";
  if (status === "pending") return "Đang chờ trong queue...";
  if (status === "failed") return "Pipeline gặp lỗi";
  return "Kiểm 4 nhóm tiêu chí: định dạng, trích dẫn, độ chính xác, văn phong.";
};

const FailureBox = ({ title, message }) => (
  <div className="flex items-start gap-2 bg-rose-50 border border-rose-200 text-rose-700 px-3 py-2.5 rounded-lg text-xs">
    <AlertCircle className="w-3.5 h-3.5 flex-shrink-0 mt-0.5" />
    <div className="flex-1 min-w-0">
      <p className="font-semibold">{title}</p>
      <p className="break-words leading-snug mt-0.5">{message}</p>
    </div>
  </div>
);

const VERDICT_LABEL = {
  excellent: "Xuất sắc",
  good: "Tốt",
  needs_review: "Cần xem lại",
  poor: "Kém",
};

const DEFAULT_SYNTHESIS_STEPS = [
  { key: "load_context", label: "Tải dữ liệu" },
  { key: "build_outline", label: "Outline" },
  { key: "synthesize_narrative", label: "Narrative" },
  { key: "generate_summary", label: "Tóm tắt" },
  { key: "build_citations", label: "Trích dẫn" },
  { key: "render_report", label: "Render" },
  { key: "persist", label: "Lưu" },
];

const DEFAULT_QA_STEPS = [
  { key: "load_report", label: "Tải" },
  { key: "check_format", label: "Format" },
  { key: "check_citations", label: "Trích dẫn" },
  { key: "check_facts", label: "Facts" },
  { key: "check_grammar", label: "Văn phong" },
  { key: "compute_score", label: "Tính điểm" },
  { key: "persist", label: "Lưu" },
];

export default AIEnhancementPanel;
