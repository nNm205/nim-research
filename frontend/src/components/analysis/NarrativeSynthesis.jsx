import {
  Sparkles,
  GitBranch,
  ShieldCheck,
  ShieldAlert,
  AlertOctagon,
  HelpCircle,
} from "lucide-react";

const confidenceBadge = (level) => {
  if (level === "high") return "bg-emerald-100 text-emerald-700 border-emerald-200";
  if (level === "medium") return "bg-amber-100 text-amber-700 border-amber-200";
  if (level === "low") return "bg-red-100 text-red-700 border-red-200";
  return "bg-slate-100 text-slate-600 border-slate-200";
};

const confidenceLabel = (level) =>
  level === "high" ? "Cao" : level === "medium" ? "Trung bình" : level === "low" ? "Thấp" : "—";

/**
 * Render the narrative_synthesis JSON object.
 * Shape:
 *   {
 *     narrative, main_thesis, novelty_vs_prior_work,
 *     argument_flow: [], internal_conflicts: [{between, description}],
 *     knowledge_gaps: [], overall_strengths: [], overall_weaknesses: [],
 *     confidence_in_conclusions, confidence_justification
 *   }
 */
const NarrativeSynthesis = ({ synthesis }) => {
  if (!synthesis || !Object.keys(synthesis).length) {
    return (
      <div className="bg-amber-50 border border-amber-100 rounded-xl px-4 py-3 text-sm text-amber-800">
        Tổng hợp xuyên phần chưa được sinh. LLM có thể đã trả về JSON không
        hợp lệ — kiểm tra log backend hoặc chạy lại phân tích.
      </div>
    );
  }

  const isEmpty =
    !synthesis.narrative &&
    !synthesis.main_thesis &&
    !synthesis.novelty_vs_prior_work &&
    !(synthesis.argument_flow || []).length &&
    !(synthesis.internal_conflicts || []).length &&
    !(synthesis.knowledge_gaps || []).length &&
    !(synthesis.overall_strengths || []).length &&
    !(synthesis.overall_weaknesses || []).length &&
    !synthesis.confidence_in_conclusions;

  if (isEmpty) {
    return (
      <div className="bg-amber-50 border border-amber-100 rounded-xl px-4 py-3 text-sm text-amber-800">
        Synthesis trống. Có thể do các section_insights phía dưới không có
        nội dung — chạy lại phân tích sau khi sửa lỗi sẽ giúp.
      </div>
    );
  }

  return (
    <div className="space-y-5">
      {/* Main thesis */}
      {synthesis.main_thesis && (
        <div className="bg-gradient-to-br from-teal-50 to-emerald-50 border border-teal-100 rounded-xl p-5">
          <div className="flex items-center gap-2 mb-2">
            <Sparkles className="w-4 h-4 text-teal-600" />
            <p className="text-xs font-bold text-teal-700 uppercase tracking-wide">
              Luận điểm chính
            </p>
          </div>
          <p className="text-slate-800 font-semibold leading-relaxed">
            {synthesis.main_thesis}
          </p>
        </div>
      )}

      {/* Narrative */}
      {synthesis.narrative && (
        <div>
          <p className="text-xs font-bold text-slate-500 uppercase tracking-wide mb-2">
            Mạch lập luận
          </p>
          <p className="text-slate-700 leading-relaxed whitespace-pre-wrap">
            {synthesis.narrative}
          </p>
        </div>
      )}

      {/* Novelty */}
      {synthesis.novelty_vs_prior_work && (
        <div>
          <p className="text-xs font-bold text-slate-500 uppercase tracking-wide mb-2">
            Đóng góp mới so với tiền nhiệm
          </p>
          <p className="text-slate-700 leading-relaxed bg-violet-50 border border-violet-100 rounded-xl p-4">
            {synthesis.novelty_vs_prior_work}
          </p>
        </div>
      )}

      {/* Argument flow */}
      {synthesis.argument_flow?.length > 0 && (
        <div>
          <div className="flex items-center gap-2 mb-2">
            <GitBranch className="w-4 h-4 text-slate-500" />
            <p className="text-xs font-bold text-slate-500 uppercase tracking-wide">
              Luồng lập luận giữa các phần
            </p>
          </div>
          <ol className="space-y-2">
            {synthesis.argument_flow.map((step, idx) => (
              <li
                key={idx}
                className="flex items-start gap-3 bg-white rounded-xl border border-slate-200 p-3"
              >
                <span className="flex-shrink-0 w-6 h-6 rounded-full bg-slate-100 text-slate-600 text-xs font-bold flex items-center justify-center mt-0.5">
                  {idx + 1}
                </span>
                <p className="text-sm text-slate-700 leading-relaxed">{step}</p>
              </li>
            ))}
          </ol>
        </div>
      )}

      {/* Strengths + weaknesses */}
      {(synthesis.overall_strengths?.length > 0 ||
        synthesis.overall_weaknesses?.length > 0) && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {synthesis.overall_strengths?.length > 0 && (
            <div className="bg-emerald-50 rounded-xl border border-emerald-100 p-4">
              <div className="flex items-center gap-2 mb-3">
                <ShieldCheck className="w-4 h-4 text-emerald-600" />
                <p className="text-xs font-bold text-emerald-700 uppercase tracking-wide">
                  Điểm mạnh tổng thể
                </p>
              </div>
              <ul className="space-y-2">
                {synthesis.overall_strengths.map((s, i) => (
                  <li
                    key={i}
                    className="text-sm text-slate-700 flex items-start gap-2"
                  >
                    <span className="text-emerald-500 mt-0.5 flex-shrink-0">•</span>
                    {s}
                  </li>
                ))}
              </ul>
            </div>
          )}
          {synthesis.overall_weaknesses?.length > 0 && (
            <div className="bg-red-50 rounded-xl border border-red-100 p-4">
              <div className="flex items-center gap-2 mb-3">
                <ShieldAlert className="w-4 h-4 text-red-600" />
                <p className="text-xs font-bold text-red-700 uppercase tracking-wide">
                  Điểm yếu tổng thể
                </p>
              </div>
              <ul className="space-y-2">
                {synthesis.overall_weaknesses.map((w, i) => (
                  <li
                    key={i}
                    className="text-sm text-slate-700 flex items-start gap-2"
                  >
                    <span className="text-red-400 mt-0.5 flex-shrink-0">•</span>
                    {w}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}

      {/* Internal conflicts */}
      {synthesis.internal_conflicts?.length > 0 && (
        <div>
          <div className="flex items-center gap-2 mb-2">
            <AlertOctagon className="w-4 h-4 text-amber-600" />
            <p className="text-xs font-bold text-amber-700 uppercase tracking-wide">
              Mâu thuẫn nội tại
            </p>
          </div>
          <div className="space-y-2">
            {synthesis.internal_conflicts.map((c, i) => (
              <div
                key={i}
                className="bg-amber-50 rounded-xl border border-amber-100 p-3"
              >
                {Array.isArray(c.between) && c.between.length > 0 && (
                  <p className="text-xs font-semibold text-amber-700 mb-1">
                    Giữa: {c.between.join(" ↔ ")}
                  </p>
                )}
                {c.description && (
                  <p className="text-sm text-slate-700">{c.description}</p>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Knowledge gaps */}
      {synthesis.knowledge_gaps?.length > 0 && (
        <div>
          <div className="flex items-center gap-2 mb-2">
            <HelpCircle className="w-4 h-4 text-indigo-600" />
            <p className="text-xs font-bold text-indigo-700 uppercase tracking-wide">
              Khoảng trống kiến thức
            </p>
          </div>
          <ul className="space-y-2">
            {synthesis.knowledge_gaps.map((gap, i) => (
              <li
                key={i}
                className="flex items-start gap-3 bg-indigo-50 rounded-xl border border-indigo-100 p-3"
              >
                <span className="flex-shrink-0 w-5 h-5 rounded-full bg-indigo-200 text-indigo-700 text-xs font-bold flex items-center justify-center mt-0.5">
                  ?
                </span>
                <p className="text-sm text-slate-700">{gap}</p>
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Confidence */}
      {synthesis.confidence_in_conclusions && (
        <div className="border-t border-slate-100 pt-4">
          <div className="flex items-center gap-2 mb-2">
            <p className="text-sm font-semibold text-slate-700">Mức độ tin cậy:</p>
            <span
              className={`px-2.5 py-0.5 rounded-lg text-xs font-bold border ${confidenceBadge(
                synthesis.confidence_in_conclusions
              )}`}
            >
              {confidenceLabel(synthesis.confidence_in_conclusions)}
            </span>
          </div>
          {synthesis.confidence_justification && (
            <p className="text-sm text-slate-600 italic">
              {synthesis.confidence_justification}
            </p>
          )}
        </div>
      )}
    </div>
  );
};

export default NarrativeSynthesis;
