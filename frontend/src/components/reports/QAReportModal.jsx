import { useMemo, useState } from "react";
import {
  X,
  ShieldCheck,
  AlertTriangle,
  AlertCircle,
  CheckCircle2,
  ListChecks,
  Quote,
  FileText,
  Sparkles,
  Hash,
  ChevronDown,
  ChevronUp,
} from "lucide-react";

/**
 * QAReportModal — full-screen modal that renders a finished QA result.
 *
 * Backend payload shape (from ``Report.qa_report``):
 *   {
 *     overall_score: 0..100,
 *     verdict: "excellent" | "good" | "needs_review" | "poor",
 *     weights: { format, citations, facts, grammar },
 *     format:    { score, issues[], stats }
 *     citations: { score, issues[], stats, cited_indices[] }
 *     facts:     { score, issues[], stats, details[] }
 *     grammar:   { score, issues[], details[], stats }
 *     recommendations: string[]
 *     provider: string,
 *     model: string,
 *     generated_at: ISO,
 *   }
 *
 * Visual language matches the rest of the app — ``rounded-2xl`` frame,
 * sticky header, scrollable body, consistent severity color scale.
 */
const QAReportModal = ({ qaReport, reportTitle, onClose }) => {
  const [openSection, setOpenSection] = useState("recommendations");

  const verdict = qaReport?.verdict || "needs_review";
  const verdictTone = VERDICT_TONES[verdict] || VERDICT_TONES.needs_review;

  const sections = useMemo(
    () => [
      {
        key: "format",
        label: "Định dạng",
        icon: FileText,
        result: qaReport?.format,
        weight: qaReport?.weights?.format,
      },
      {
        key: "citations",
        label: "Trích dẫn",
        icon: Hash,
        result: qaReport?.citations,
        weight: qaReport?.weights?.citations,
      },
      {
        key: "facts",
        label: "Độ chính xác",
        icon: ShieldCheck,
        result: qaReport?.facts,
        weight: qaReport?.weights?.facts,
      },
      {
        key: "grammar",
        label: "Văn phong",
        icon: Quote,
        result: qaReport?.grammar,
        weight: qaReport?.weights?.grammar,
      },
    ],
    [qaReport]
  );

  if (!qaReport) return null;

  return (
    <div className="fixed inset-0 bg-black/30 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-2xl max-w-4xl w-full max-h-[92vh] overflow-y-auto no-scrollbar shadow-2xl">
        {/* ── Sticky header ─────────────────────────────────────────── */}
        <div className="sticky top-0 bg-white border-b border-slate-200 px-8 py-5 flex items-center justify-between z-10">
          <div className="flex items-center gap-3 min-w-0">
            <div className={`p-2 rounded-xl ${verdictTone.bg} ${verdictTone.border} border`}>
              <ShieldCheck className={`w-5 h-5 ${verdictTone.text}`} />
            </div>
            <div className="min-w-0">
              <h2 className="text-xl font-bold text-slate-900 truncate">
                Báo cáo kiểm chất lượng
              </h2>
              <p className="text-xs text-slate-500 truncate mt-0.5">
                {reportTitle || "Báo cáo"}
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="text-slate-400 hover:text-slate-600 transition-colors p-1 hover:bg-slate-100 rounded-lg flex-shrink-0"
            aria-label="Đóng"
          >
            <X className="w-6 h-6" />
          </button>
        </div>

        {/* ── Body ──────────────────────────────────────────────────── */}
        <div className="p-8 space-y-6">
          {/* Overall score banner */}
          <ScoreHero
            score={qaReport.overall_score}
            verdict={verdict}
            verdictTone={verdictTone}
            provider={qaReport.provider}
            model={qaReport.model}
            generatedAt={qaReport.generated_at}
          />

          {/* Sub-scores grid */}
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-3">
            {sections.map(({ key, label, icon, result, weight }) => (
              <SubScoreCard
                key={key}
                label={label}
                icon={icon}
                score={result?.score}
                weight={weight}
                issueCount={(result?.issues || []).length}
              />
            ))}
          </div>

          {/* Recommendations */}
          <CollapsibleSection
            id="recommendations"
            title="Khuyến nghị cải thiện"
            icon={Sparkles}
            badgeCount={(qaReport.recommendations || []).length}
            open={openSection === "recommendations"}
            onToggle={() =>
              setOpenSection(
                openSection === "recommendations" ? "" : "recommendations"
              )
            }
            tone="emerald"
          >
            {(qaReport.recommendations || []).length > 0 ? (
              <ul className="space-y-2">
                {qaReport.recommendations.map((rec, idx) => (
                  <li
                    key={idx}
                    className="flex items-start gap-3 px-4 py-3 bg-slate-50 rounded-xl border border-slate-200"
                  >
                    <span className="w-6 h-6 rounded-full bg-emerald-100 text-emerald-700 text-xs font-bold flex items-center justify-center flex-shrink-0 mt-0.5">
                      {idx + 1}
                    </span>
                    <p className="text-sm text-slate-700 leading-relaxed">
                      {rec}
                    </p>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="text-sm text-slate-500 italic">
                Không có khuyến nghị nào.
              </p>
            )}
          </CollapsibleSection>

          {/* Per-section detail dropdowns */}
          {sections.map(({ key, label, icon, result }) => (
            <CollapsibleSection
              key={key}
              id={key}
              title={label}
              icon={icon}
              badgeCount={(result?.issues || []).length}
              open={openSection === key}
              onToggle={() => setOpenSection(openSection === key ? "" : key)}
            >
              <SectionDetail sectionKey={key} result={result} />
            </CollapsibleSection>
          ))}
        </div>
      </div>
    </div>
  );
};

// ── Score hero ─────────────────────────────────────────────────────────────

const ScoreHero = ({ score, verdict, verdictTone, provider, model, generatedAt }) => {
  const ringColor = verdictTone.ring;
  return (
    <div
      className={`rounded-2xl border-2 ${verdictTone.border} ${verdictTone.bgSoft} p-6`}
    >
      <div className="flex items-center gap-6 flex-wrap">
        {/* Circular score badge */}
        <div className="relative w-28 h-28 flex-shrink-0">
          <svg viewBox="0 0 100 100" className="w-full h-full -rotate-90">
            <circle
              cx="50"
              cy="50"
              r="44"
              fill="none"
              stroke="#e2e8f0"
              strokeWidth="8"
            />
            <circle
              cx="50"
              cy="50"
              r="44"
              fill="none"
              stroke={ringColor}
              strokeWidth="8"
              strokeLinecap="round"
              strokeDasharray={`${2 * Math.PI * 44}`}
              strokeDashoffset={`${
                2 * Math.PI * 44 * (1 - (score ?? 0) / 100)
              }`}
              className="transition-all duration-700"
            />
          </svg>
          <div className="absolute inset-0 flex flex-col items-center justify-center">
            <span className="text-3xl font-bold tabular-nums text-slate-900">
              {score ?? "—"}
            </span>
            <span className="text-[10px] text-slate-500 uppercase tracking-wide">
              / 100
            </span>
          </div>
        </div>

        <div className="flex-1 min-w-0">
          <div
            className={`inline-flex items-center gap-2 px-3 py-1 rounded-full text-xs font-bold uppercase tracking-wide ${verdictTone.pill}`}
          >
            {VERDICT_LABEL[verdict] || verdict}
          </div>
          <p className="text-sm text-slate-700 mt-3 leading-relaxed">
            {VERDICT_BLURB[verdict] ||
              "Báo cáo đã được kiểm chứng qua 4 nhóm tiêu chí."}
          </p>
          {(provider || generatedAt) && (
            <p className="text-[11px] text-slate-500 mt-2 flex items-center gap-3 flex-wrap">
              {provider && (
                <span className="font-mono">
                  LLM: {provider}:{model || "?"}
                </span>
              )}
              {generatedAt && (
                <span>
                  Tạo lúc {new Date(generatedAt).toLocaleString("vi-VN")}
                </span>
              )}
            </p>
          )}
        </div>
      </div>
    </div>
  );
};

// ── Sub-score card ─────────────────────────────────────────────────────────

const SubScoreCard = ({ label, icon: Icon, score, weight, issueCount }) => {
  const tone = scoreTone(score);
  return (
    <div
      className={`rounded-xl border ${tone.border} ${tone.bg} p-4 transition-colors`}
    >
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-2">
          <Icon className={`w-4 h-4 ${tone.icon}`} />
          <span className="text-xs font-bold text-slate-700 uppercase tracking-wide">
            {label}
          </span>
        </div>
        {weight != null && (
          <span className="text-[10px] text-slate-500 font-mono">
            ×{Math.round(weight * 100)}%
          </span>
        )}
      </div>
      <div className="flex items-baseline gap-1.5">
        <span className="text-2xl font-bold tabular-nums text-slate-900">
          {score ?? "—"}
        </span>
        <span className="text-xs text-slate-500">/ 100</span>
      </div>
      {issueCount > 0 ? (
        <p className="text-[11px] text-slate-600 mt-1 flex items-center gap-1">
          <AlertTriangle className="w-3 h-3" />
          {issueCount} vấn đề
        </p>
      ) : (
        <p className="text-[11px] text-emerald-600 mt-1 flex items-center gap-1">
          <CheckCircle2 className="w-3 h-3" />
          Không có vấn đề
        </p>
      )}
    </div>
  );
};

// ── Collapsible section wrapper ────────────────────────────────────────────

const CollapsibleSection = ({
  title,
  icon: Icon,
  badgeCount,
  open,
  onToggle,
  children,
  tone = "slate",
}) => {
  const headerTone =
    tone === "emerald"
      ? "border-emerald-200 bg-emerald-50/40"
      : "border-slate-200 bg-white";
  return (
    <div className={`rounded-2xl border ${headerTone} overflow-hidden`}>
      <button
        type="button"
        onClick={onToggle}
        className="w-full flex items-center justify-between px-5 py-4 hover:bg-slate-50 transition-colors"
      >
        <div className="flex items-center gap-3">
          <Icon className="w-4 h-4 text-slate-600" />
          <h3 className="text-sm font-bold text-slate-900">{title}</h3>
          {badgeCount > 0 && (
            <span className="px-2 py-0.5 rounded bg-slate-200 text-slate-700 text-[10px] font-bold">
              {badgeCount}
            </span>
          )}
        </div>
        {open ? (
          <ChevronUp className="w-4 h-4 text-slate-400" />
        ) : (
          <ChevronDown className="w-4 h-4 text-slate-400" />
        )}
      </button>
      {open && <div className="px-5 pb-5 pt-1">{children}</div>}
    </div>
  );
};

// ── Section detail (issues + section-specific extras) ──────────────────────

const SectionDetail = ({ sectionKey, result }) => {
  if (!result) {
    return <p className="text-sm text-slate-500 italic">Không có dữ liệu.</p>;
  }

  const issues = result.issues || [];

  return (
    <div className="space-y-4">
      {/* Stats row */}
      {result.stats && Object.keys(result.stats).length > 0 && (
        <div className="flex items-center gap-2 flex-wrap">
          {Object.entries(result.stats).map(([k, v]) => (
            <span
              key={k}
              className="inline-flex items-center gap-1 px-2 py-1 rounded-md bg-slate-100 text-slate-700 text-[11px] font-medium"
            >
              <span className="text-slate-500">{k}:</span>
              <span className="font-bold">{String(v)}</span>
            </span>
          ))}
        </div>
      )}

      {/* Top-level issues (one entry per section) */}
      {issues.length > 0 ? (
        <div className="space-y-2">
          {issues.map((issue, idx) => (
            <IssueRow key={idx} issue={issue} />
          ))}
        </div>
      ) : (
        <p className="text-sm text-emerald-700 flex items-center gap-2">
          <CheckCircle2 className="w-4 h-4" />
          Không phát hiện vấn đề nào trong nhóm này.
        </p>
      )}

      {/* Section-specific deep details */}
      {sectionKey === "facts" && Array.isArray(result.details) && result.details.length > 0 && (
        <FactDetails details={result.details} />
      )}

      {sectionKey === "grammar" && Array.isArray(result.details) && result.details.length > 0 && (
        <GrammarDetails details={result.details} />
      )}

      {sectionKey === "citations" && Array.isArray(result.cited_indices) && result.cited_indices.length > 0 && (
        <div className="text-xs text-slate-500">
          Đã trích dẫn:{" "}
          <span className="font-mono">
            {result.cited_indices.map((n) => `[${n}]`).join(" ")}
          </span>
        </div>
      )}
    </div>
  );
};

const IssueRow = ({ issue }) => {
  const tone = SEVERITY_TONES[issue.severity] || SEVERITY_TONES.low;
  return (
    <div
      className={`flex items-start gap-3 px-3 py-2.5 rounded-lg border ${tone.border} ${tone.bg}`}
    >
      <span className={`mt-0.5 ${tone.icon}`}>
        <AlertCircle className="w-3.5 h-3.5" />
      </span>
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 flex-wrap mb-0.5">
          <span
            className={`text-[10px] font-bold uppercase tracking-wide px-1.5 py-0.5 rounded ${tone.pill}`}
          >
            {issue.severity || "low"}
          </span>
          <span className="text-[11px] text-slate-500 font-mono">
            {issue.type}
          </span>
        </div>
        <p className="text-sm text-slate-700 leading-snug break-words">
          {issue.message}
        </p>
      </div>
    </div>
  );
};

// ── Fact-check details ─────────────────────────────────────────────────────

const FactDetails = ({ details }) => (
  <div className="space-y-2">
    <p className="text-xs font-bold text-slate-700 uppercase tracking-wide flex items-center gap-1.5">
      <ListChecks className="w-3.5 h-3.5" />
      Chi tiết kiểm chứng claim
    </p>
    {details.map((d) => {
      const tone = VERDICT_TONES_FACT[d.verdict] || VERDICT_TONES_FACT.partial;
      return (
        <div
          key={d.index}
          className={`rounded-lg border ${tone.border} ${tone.bg} p-3`}
        >
          <div className="flex items-start gap-2 mb-1">
            <span
              className={`text-[10px] font-bold uppercase tracking-wide px-1.5 py-0.5 rounded ${tone.pill}`}
            >
              {VERDICT_LABEL_FACT[d.verdict] || d.verdict}
            </span>
            {Array.isArray(d.cited_docs) && d.cited_docs.length > 0 && (
              <span className="text-[11px] text-slate-500 font-mono">
                {d.cited_docs.map((n) => `[${n}]`).join(" ")}
              </span>
            )}
          </div>
          <p className="text-sm text-slate-700 leading-snug mb-1">
            "{d.claim}"
          </p>
          {d.explanation && (
            <p className="text-xs text-slate-600 leading-snug">
              {d.explanation}
            </p>
          )}
          {d.evidence_excerpt && (
            <p className="text-xs italic text-slate-500 mt-1 border-l-2 border-slate-200 pl-2">
              "{d.evidence_excerpt}"
            </p>
          )}
        </div>
      );
    })}
  </div>
);

// ── Grammar details ────────────────────────────────────────────────────────

const GrammarDetails = ({ details }) => (
  <div className="space-y-2">
    <p className="text-xs font-bold text-slate-700 uppercase tracking-wide flex items-center gap-1.5">
      <Quote className="w-3.5 h-3.5" />
      Chi tiết lỗi văn phong
    </p>
    {details.map((d, idx) => {
      const tone = SEVERITY_TONES[d.severity] || SEVERITY_TONES.low;
      return (
        <div
          key={idx}
          className={`rounded-lg border ${tone.border} ${tone.bg} p-3`}
        >
          <div className="flex items-center gap-2 mb-1 flex-wrap">
            <span
              className={`text-[10px] font-bold uppercase tracking-wide px-1.5 py-0.5 rounded ${tone.pill}`}
            >
              {d.severity || "low"}
            </span>
            <span className="text-[11px] text-slate-500 font-mono">
              {d.type}
            </span>
            {d.line_hint > 0 && (
              <span className="text-[11px] text-slate-500">
                dòng ~{d.line_hint}
              </span>
            )}
          </div>
          <p className="text-sm text-slate-700 mb-1">"{d.snippet}"</p>
          {d.suggestion && (
            <p className="text-xs text-emerald-700">
              <strong>Đề xuất:</strong> {d.suggestion}
            </p>
          )}
        </div>
      );
    })}
  </div>
);

// ── Tone tables ────────────────────────────────────────────────────────────

const VERDICT_TONES = {
  excellent: {
    bg: "bg-emerald-50",
    bgSoft: "bg-emerald-50/40",
    border: "border-emerald-300",
    text: "text-emerald-700",
    pill: "bg-emerald-100 text-emerald-700",
    ring: "#059669",
  },
  good: {
    bg: "bg-teal-50",
    bgSoft: "bg-teal-50/40",
    border: "border-teal-300",
    text: "text-teal-700",
    pill: "bg-teal-100 text-teal-700",
    ring: "#0d9488",
  },
  needs_review: {
    bg: "bg-amber-50",
    bgSoft: "bg-amber-50/40",
    border: "border-amber-300",
    text: "text-amber-700",
    pill: "bg-amber-100 text-amber-700",
    ring: "#d97706",
  },
  poor: {
    bg: "bg-rose-50",
    bgSoft: "bg-rose-50/40",
    border: "border-rose-300",
    text: "text-rose-700",
    pill: "bg-rose-100 text-rose-700",
    ring: "#dc2626",
  },
};

const VERDICT_LABEL = {
  excellent: "Xuất sắc",
  good: "Tốt",
  needs_review: "Cần xem lại",
  poor: "Kém",
};

const VERDICT_BLURB = {
  excellent:
    "Báo cáo đạt chất lượng cao trên tất cả tiêu chí — định dạng, trích dẫn, độ chính xác, và văn phong.",
  good:
    "Báo cáo đạt chuẩn, có thể xuất bản. Một vài điểm có thể cải thiện thêm nhưng không bắt buộc.",
  needs_review:
    "Báo cáo cần được kiểm tra lại trước khi xuất bản. Hãy xem các khuyến nghị bên dưới.",
  poor:
    "Báo cáo có nhiều vấn đề nghiêm trọng. Cần chỉnh sửa hoặc tổng hợp lại trước khi sử dụng.",
};

const SEVERITY_TONES = {
  high: {
    border: "border-rose-200",
    bg: "bg-rose-50",
    pill: "bg-rose-100 text-rose-700",
    icon: "text-rose-600",
  },
  medium: {
    border: "border-amber-200",
    bg: "bg-amber-50",
    pill: "bg-amber-100 text-amber-700",
    icon: "text-amber-600",
  },
  low: {
    border: "border-slate-200",
    bg: "bg-slate-50",
    pill: "bg-slate-200 text-slate-700",
    icon: "text-slate-500",
  },
};

const VERDICT_TONES_FACT = {
  supported: {
    border: "border-emerald-200",
    bg: "bg-emerald-50",
    pill: "bg-emerald-100 text-emerald-700",
  },
  partial: {
    border: "border-amber-200",
    bg: "bg-amber-50",
    pill: "bg-amber-100 text-amber-700",
  },
  unsupported: {
    border: "border-rose-200",
    bg: "bg-rose-50",
    pill: "bg-rose-100 text-rose-700",
  },
};

const VERDICT_LABEL_FACT = {
  supported: "có hỗ trợ",
  partial: "một phần",
  unsupported: "không hỗ trợ",
};

const scoreTone = (score) => {
  if (score == null)
    return {
      border: "border-slate-200",
      bg: "bg-slate-50",
      icon: "text-slate-500",
    };
  if (score >= 90)
    return {
      border: "border-emerald-200",
      bg: "bg-emerald-50",
      icon: "text-emerald-600",
    };
  if (score >= 75)
    return {
      border: "border-teal-200",
      bg: "bg-teal-50",
      icon: "text-teal-600",
    };
  if (score >= 60)
    return {
      border: "border-amber-200",
      bg: "bg-amber-50",
      icon: "text-amber-600",
    };
  return {
    border: "border-rose-200",
    bg: "bg-rose-50",
    icon: "text-rose-600",
  };
};

export default QAReportModal;
