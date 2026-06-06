import { CheckCircle2, Clock, AlertCircle, Loader, Folder } from "lucide-react";

const AnalysisCard = ({ analysis, onClick, projectName }) => {
  const formatDate = (dateString) => {
    if (!dateString) return "N/A";
    const date = new Date(dateString);
    return date.toLocaleString("vi-VN", {
      day: "2-digit",
      month: "2-digit",
      year: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  };

  const statusConfig = {
    pending: {
      label: "Chờ xử lý",
      bgColor: "bg-slate-50",
      textColor: "text-slate-700",
      borderColor: "border-slate-200",
      icon: Clock,
      badgeClass: "bg-slate-100 text-slate-700",
    },
    running: {
      label: "Đang chạy",
      bgColor: "bg-blue-50",
      textColor: "text-blue-700",
      borderColor: "border-blue-200",
      icon: Loader,
      badgeClass: "bg-blue-100 text-blue-700",
    },
    completed: {
      label: "Hoàn thành",
      bgColor: "bg-emerald-50",
      textColor: "text-emerald-700",
      borderColor: "border-emerald-200",
      icon: CheckCircle2,
      badgeClass: "bg-emerald-100 text-emerald-700",
    },
    failed: {
      label: "Thất bại",
      bgColor: "bg-red-50",
      textColor: "text-red-700",
      borderColor: "border-red-200",
      icon: AlertCircle,
      badgeClass: "bg-red-100 text-red-700",
    },
  };

  const status = statusConfig[analysis.status] || statusConfig.pending;
  const StatusIcon = status.icon;

  const getDuration = () => {
    if (!analysis.started_at || !analysis.completed_at) return null;
    const start = new Date(analysis.started_at);
    const end = new Date(analysis.completed_at);
    const minutes = Math.floor((end - start) / 60000);
    const seconds = Math.floor(((end - start) % 60000) / 1000);
    if (minutes > 0) return `${minutes}m ${seconds}s`;
    return `${seconds}s`;
  };

  return (
    <div
      onClick={onClick}
      className={`bg-white rounded-2xl border ${status.borderColor} p-6 shadow-sm hover:shadow-md hover:border-teal-300 transition-all cursor-pointer group`}
    >
      <div className="flex items-start justify-between">
        {/* Left side - Content */}
        <div className="flex-1">
          <div className="flex items-start gap-4 mb-4">
            <div className={`p-3 rounded-xl ${status.bgColor} flex-shrink-0`}>
              <StatusIcon className={`w-6 h-6 ${status.textColor}`} />
            </div>
            <div className="flex-1 min-w-0">
              <h3 className="text-lg font-bold text-slate-900 group-hover:text-teal-600 transition-colors mb-1 truncate">
                {analysis.document_title || `Phân tích ${analysis.id.slice(0, 8)}`}
              </h3>
              <div className="flex items-center gap-3 flex-wrap">
                {projectName && (
                  <span className="inline-flex items-center gap-1 text-xs text-slate-600 font-medium">
                    <Folder className="w-3 h-3" />
                    {projectName}
                  </span>
                )}
                <p className="text-xs text-slate-500 font-mono truncate">
                  ID: {analysis.id.slice(0, 8)}…
                </p>
              </div>
            </div>
          </div>

          {/* Metadata */}
          <div className="space-y-2 text-sm">
            <div className="flex items-center gap-2 text-slate-600">
              <span className="text-xs font-semibold text-slate-500 uppercase">
                Bắt đầu:
              </span>
              <span className="font-medium text-slate-700">
                {formatDate(analysis.started_at)}
              </span>
            </div>

            {analysis.completed_at && (
              <div className="flex items-center gap-2 text-slate-600">
                <span className="text-xs font-semibold text-slate-500 uppercase">
                  Hoàn thành:
                </span>
                <span className="font-medium text-slate-700">
                  {formatDate(analysis.completed_at)}
                </span>
              </div>
            )}

            {getDuration() && (
              <div className="flex items-center gap-2 text-slate-600">
                <span className="text-xs font-semibold text-slate-500 uppercase">
                  Thời gian:
                </span>
                <span className="font-medium text-slate-700">{getDuration()}</span>
              </div>
            )}

            {analysis.error_message && (
              <div className="flex items-start gap-2 bg-red-50 rounded-lg p-2 border border-red-100 mt-2">
                <AlertCircle className="w-4 h-4 text-red-600 flex-shrink-0 mt-0.5" />
                <span className="text-xs text-red-700">{analysis.error_message}</span>
              </div>
            )}
          </div>
        </div>

        {/* Right side - Status Badge */}
        <div className="flex flex-col items-end gap-2 ml-4 flex-shrink-0">
          <span
            className={`px-3 py-1.5 rounded-full text-xs font-semibold ${status.badgeClass} whitespace-nowrap`}
          >
            {status.label}
          </span>

          {analysis.status === "running" && (
            <div className="w-6 h-6 border-2 border-blue-200 border-t-blue-600 rounded-full animate-spin"></div>
          )}
        </div>
      </div>

      {/* Progress bar for running analyses */}
      {analysis.status === "running" && (
        <div className="mt-4">
          <div className="w-full bg-blue-100 rounded-full h-2 overflow-hidden">
            <div
              className="bg-gradient-to-r from-blue-600 to-blue-500 h-2 rounded-full animate-pulse"
              style={{ width: "65%" }}
            ></div>
          </div>
        </div>
      )}
    </div>
  );
};

export default AnalysisCard;