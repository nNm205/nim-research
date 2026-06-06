import {
  FileText,
  ClipboardList,
  BookOpen,
  BarChart3,
  Sparkles,
  Folder,
  Calendar,
  CheckCircle2,
  Archive,
  PenLine,
  Trash2,
  ArrowRight,
} from "lucide-react";

/**
 * ReportCard — list view tile for a single report.
 *
 * Visual language matches AnalysisCard / DocumentCard:
 *   - subtle border with status-tinted hover (teal accent on hover)
 *   - icon block on the left in a colored badge
 *   - title + meta on the right
 *   - status pill in the top-right corner
 *   - optional inline destructive action (trash) only when ``onDelete``
 *     is provided
 *
 * The card is fully clickable; the delete button stops propagation so
 * it doesn't bubble up to the row click.
 */

// Per report-type icon + accent color. Using one icon per type makes the
// list scannable at a glance — research_summary papers vs literature
// reviews vs data analysis pop visually.
const TYPE_CONFIG = {
  research_summary: {
    label: "Tóm tắt nghiên cứu",
    icon: FileText,
    accent: {
      bg: "bg-teal-50",
      text: "text-teal-600",
      border: "border-teal-200",
    },
  },
  literature_review: {
    label: "Tổng quan tài liệu",
    icon: BookOpen,
    accent: {
      bg: "bg-violet-50",
      text: "text-violet-600",
      border: "border-violet-200",
    },
  },
  data_analysis: {
    label: "Phân tích dữ liệu",
    icon: BarChart3,
    accent: {
      bg: "bg-blue-50",
      text: "text-blue-600",
      border: "border-blue-200",
    },
  },
  custom: {
    label: "Tùy chỉnh",
    icon: Sparkles,
    accent: {
      bg: "bg-fuchsia-50",
      text: "text-fuchsia-600",
      border: "border-fuchsia-200",
    },
  },
};

const STATUS_CONFIG = {
  draft: {
    label: "Nháp",
    badge: "bg-amber-100 text-amber-700",
    icon: PenLine,
  },
  published: {
    label: "Đã xuất bản",
    badge: "bg-emerald-100 text-emerald-700",
    icon: CheckCircle2,
  },
  archived: {
    label: "Lưu trữ",
    badge: "bg-slate-100 text-slate-600",
    icon: Archive,
  },
};

const ReportCard = ({ report, onClick, onDelete, projectName }) => {
  const type = TYPE_CONFIG[report.report_type] || TYPE_CONFIG.custom;
  const status = STATUS_CONFIG[report.status] || STATUS_CONFIG.draft;
  const TypeIcon = type.icon;
  const StatusIcon = status.icon;

  const formatDate = (dateString) => {
    if (!dateString) return "—";
    const date = new Date(dateString);
    return date.toLocaleDateString("vi-VN", {
      day: "2-digit",
      month: "2-digit",
      year: "numeric",
    });
  };

  const docCount = Array.isArray(report.included_documents)
    ? report.included_documents.length
    : 0;

  return (
    <div
      onClick={onClick}
      className="group bg-white rounded-2xl border border-slate-200 p-6 shadow-sm hover:shadow-md hover:border-teal-300 transition-all cursor-pointer"
    >
      <div className="flex items-start gap-4">
        {/* Type icon block */}
        <div
          className={`p-3 rounded-xl ${type.accent.bg} border ${type.accent.border} flex-shrink-0`}
        >
          <TypeIcon className={`w-6 h-6 ${type.accent.text}`} />
        </div>

        {/* Content */}
        <div className="flex-1 min-w-0">
          <div className="flex items-start justify-between gap-3 mb-2">
            <div className="min-w-0 flex-1">
              <h3 className="text-lg font-bold text-slate-900 group-hover:text-teal-600 transition-colors mb-1 truncate">
                {report.title}
              </h3>
              <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">
                {type.label}
              </p>
            </div>
            <span
              className={`inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-bold ${status.badge} whitespace-nowrap`}
            >
              <StatusIcon className="w-3 h-3" />
              {status.label}
            </span>
          </div>

          {/* Meta row */}
          <div className="flex items-center gap-3 text-xs text-slate-500 flex-wrap mt-3">
            {projectName && (
              <span className="inline-flex items-center gap-1 font-medium">
                <Folder className="w-3 h-3" />
                {projectName}
              </span>
            )}
            <span className="inline-flex items-center gap-1">
              <Calendar className="w-3 h-3" />
              {formatDate(report.updated_at || report.created_at)}
            </span>
            {docCount > 0 && (
              <span className="inline-flex items-center gap-1">
                <ClipboardList className="w-3 h-3" />
                {docCount} tài liệu
              </span>
            )}
          </div>

          {/* Footer actions */}
          <div className="flex items-center justify-between pt-4 mt-4 border-t border-slate-100">
            <button
              onClick={(e) => {
                e.stopPropagation();
                onClick?.();
              }}
              className="text-xs font-semibold text-teal-600 hover:text-teal-700 inline-flex items-center gap-1 transition-colors"
            >
              Xem chi tiết
              <ArrowRight className="w-3 h-3 group-hover:translate-x-0.5 transition-transform" />
            </button>
            {onDelete && (
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  onDelete(report.id);
                }}
                title="Xóa báo cáo"
                className="text-slate-400 hover:text-red-600 hover:bg-red-50 transition-colors p-1.5 rounded-lg"
              >
                <Trash2 className="w-4 h-4" />
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};

export default ReportCard;
