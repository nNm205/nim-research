import {
  FileText,
  BarChart3,
  ClipboardList,
  ArrowRight,
  Trash2,
  Search,
} from "lucide-react";

/**
 * ProjectCard — list-view card.
 *
 * Stats row reflects what the user actually cares about:
 *   - document_count           (tài liệu đã upload / ingest)
 *   - research_session_count   (số phiên tìm kiếm tài liệu)
 *   - analysis_count           (số phân tích AI đã chạy)
 *   - report_count             (số báo cáo đã sinh)
 *
 * The topic field, when present, is rendered as comma-separated chips
 * matching the keyword chips style used elsewhere in the app, so users
 * see a consistent visual language for "tags".
 */
const ProjectCard = ({ project, onClick, onDelete }) => {
  const formatDate = (dateString) => {
    const date = new Date(dateString);
    return date.toLocaleDateString("vi-VN", {
      day: "2-digit",
      month: "2-digit",
      year: "numeric",
    });
  };

  const statusColors = {
    active:    { bg: "bg-emerald-50", border: "border-emerald-200", text: "text-emerald-700", label: "Đang hoạt động" },
    completed: { bg: "bg-blue-50",    border: "border-blue-200",    text: "text-blue-700",    label: "Hoàn thành" },
    on_hold:   { bg: "bg-amber-50",   border: "border-amber-200",   text: "text-amber-700",   label: "Tạm dừng" },
    cancelled: { bg: "bg-red-50",     border: "border-red-200",     text: "text-red-700",     label: "Đã hủy" },
  };
  const statusConfig = statusColors[project.status] || statusColors.active;

  // Split the comma-joined topic string into individual chips. Strip empty
  // entries that come from trailing commas in user input.
  const topicChips = (project.topic || "")
    .split(",")
    .map((t) => t.trim())
    .filter(Boolean);

  return (
    <div className="bg-white rounded-2xl border border-slate-200 p-6 shadow-sm hover:shadow-md hover:border-teal-300 transition-all group flex flex-col">
      {/* Header */}
      <div className="flex items-start justify-between mb-3">
        <button
          onClick={onClick}
          className="flex-1 text-left min-w-0"
        >
          <h3 className="text-lg font-bold text-slate-900 group-hover:text-teal-600 transition-colors mb-1 truncate">
            {project.name}
          </h3>
        </button>
        {project.is_archived && (
          <span className="flex-shrink-0 bg-slate-100 text-slate-600 text-xs px-3 py-1 rounded-lg font-medium ml-2">
            📦 Lưu trữ
          </span>
        )}
      </div>

      {/* Topic chips — keep tight (small, ring-1) so the card layout
          stays compact even with several tags. */}
      {topicChips.length > 0 && (
        <div className="flex flex-wrap gap-1.5 mb-3">
          {topicChips.slice(0, 5).map((t, idx) => (
            <span
              key={`${t}-${idx}`}
              className="inline-flex items-center gap-1 px-2 py-0.5 bg-violet-50 ring-1 ring-violet-200 text-violet-700 rounded text-[11px] font-medium"
            >
              {t}
            </span>
          ))}
          {topicChips.length > 5 && (
            <span className="inline-flex items-center px-2 py-0.5 bg-slate-50 ring-1 ring-slate-200 text-slate-500 rounded text-[11px] font-medium">
              +{topicChips.length - 5}
            </span>
          )}
        </div>
      )}

      {/* Description */}
      {project.description && (
        <button
          onClick={onClick}
          className="w-full text-left text-sm text-slate-600 mb-4 line-clamp-2 hover:text-teal-600 transition-colors"
        >
          {project.description}
        </button>
      )}

      {/* Research Scope Preview */}
      {project.research_scope && (
        <button
          onClick={onClick}
          className="w-full text-left mb-4 p-3 bg-slate-50 rounded-lg border border-slate-200 hover:bg-teal-50 hover:border-teal-300 transition-colors"
        >
          <p className="text-xs font-semibold text-slate-700 mb-1">Phạm vi nghiên cứu:</p>
          <p className="text-sm text-slate-600 line-clamp-2">{project.research_scope}</p>
        </button>
      )}

      {/* Spacer to push footer down */}
      <div className="flex-1" />

      {/* Stats — pulled from the per-project counts the API already exposes */}
      <button
        onClick={onClick}
        className="grid grid-cols-4 gap-2 mb-3 mt-1"
      >
        <StatCell
          icon={FileText}
          label="Tài liệu"
          value={project.document_count ?? 0}
          color="text-teal-600"
        />
        <StatCell
          icon={Search}
          label="Tìm kiếm"
          value={project.research_session_count ?? 0}
          color="text-blue-600"
        />
        <StatCell
          icon={BarChart3}
          label="Phân tích"
          value={project.analysis_count ?? 0}
          color="text-violet-600"
        />
        <StatCell
          icon={ClipboardList}
          label="Báo cáo"
          value={project.report_count ?? 0}
          color="text-amber-600"
        />
      </button>

      {/* Footer */}
      <div className="flex items-center justify-between pt-3 border-t border-slate-100">
        <span
          className={`${statusConfig.bg} border ${statusConfig.border} text-xs px-3 py-1 rounded-lg font-semibold ${statusConfig.text}`}
        >
          {statusConfig.label}
        </span>
        <div className="flex items-center gap-2">
          <span className="text-xs text-slate-500">{formatDate(project.updated_at)}</span>
          <button
            onClick={onClick}
            className="text-teal-600 hover:text-teal-700 transition-colors p-1 hover:bg-teal-50 rounded-lg"
            title="Xem chi tiết"
          >
            <ArrowRight className="w-4 h-4" />
          </button>
          {onDelete && (
            <button
              onClick={(e) => {
                e.stopPropagation();
                onDelete(project.id);
              }}
              className="text-red-600 hover:text-red-700 transition-colors p-1 hover:bg-red-50 rounded-lg"
              title="Xóa"
            >
              <Trash2 className="w-4 h-4" />
            </button>
          )}
        </div>
      </div>
    </div>
  );
};

const StatCell = ({ icon: Icon, label, value, color }) => (
  <div
    className="flex flex-col items-center justify-center p-2 rounded-lg bg-slate-50 hover:bg-slate-100 transition-colors"
    title={label}
  >
    <Icon className={`w-4 h-4 mb-0.5 ${color}`} />
    <span className="text-base font-bold text-slate-900 leading-tight">{value}</span>
    <span className="text-[10px] text-slate-500 font-medium">{label}</span>
  </div>
);

export default ProjectCard;
