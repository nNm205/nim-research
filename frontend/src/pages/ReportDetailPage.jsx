import { useState, useEffect, useRef } from "react";
import { useParams, useNavigate } from "react-router-dom";
import DashboardLayout from "../components/layout/DashboardLayout";
import { reportService } from "../services/reportService";
import { qaService } from "../services/qaService";
import AIEnhancementPanel from "../components/reports/AIEnhancementPanel";
import QAReportModal from "../components/reports/QAReportModal";
import { useReportEnhancement } from "../hooks/useReportEnhancement";
import {
  ArrowLeft,
  Trash2,
  Archive,
  ArchiveRestore,
  Edit2,
  Calendar,
  CheckCircle2,
  AlertCircle,
  FileText,
  BookOpen,
  BarChart3,
  Sparkles,
  ClipboardList,
  Tag,
  Download,
  RefreshCw,
  ChevronDown,
  Loader,
  Clock,
  X,
  PenLine,
  Upload,
  Hash,
} from "lucide-react";

// ── Static config ──────────────────────────────────────────────────────────

const TYPE_CONFIG = {
  research_summary: {
    label: "Tóm tắt nghiên cứu",
    icon: FileText,
    accent: { bg: "bg-teal-50", text: "text-teal-700", border: "border-teal-200" },
  },
  literature_review: {
    label: "Tổng quan tài liệu",
    icon: BookOpen,
    accent: { bg: "bg-violet-50", text: "text-violet-700", border: "border-violet-200" },
  },
  data_analysis: {
    label: "Phân tích dữ liệu",
    icon: BarChart3,
    accent: { bg: "bg-blue-50", text: "text-blue-700", border: "border-blue-200" },
  },
  custom: {
    label: "Tùy chỉnh",
    icon: Sparkles,
    accent: { bg: "bg-fuchsia-50", text: "text-fuchsia-700", border: "border-fuchsia-200" },
  },
};

const STATUS_CONFIG = {
  draft: {
    label: "Nháp",
    icon: PenLine,
    bg: "bg-amber-50",
    text: "text-amber-700",
    border: "border-amber-200",
    badge: "bg-amber-100 text-amber-700",
  },
  published: {
    label: "Đã xuất bản",
    icon: CheckCircle2,
    bg: "bg-emerald-50",
    text: "text-emerald-700",
    border: "border-emerald-200",
    badge: "bg-emerald-100 text-emerald-700",
  },
  archived: {
    label: "Lưu trữ",
    icon: Archive,
    bg: "bg-slate-50",
    text: "text-slate-700",
    border: "border-slate-200",
    badge: "bg-slate-100 text-slate-700",
  },
};

const DOWNLOAD_FORMATS = [
  {
    value: "html",
    label: "HTML (.html)",
    description: "Trang web độc lập, mở trong trình duyệt",
  },
  {
    value: "docx",
    label: "Word (.docx)",
    description: "Mở bằng Microsoft Word hoặc LibreOffice",
  },
  {
    value: "md",
    label: "Markdown (.md)",
    description: "Văn bản thuần, phù hợp để chỉnh sửa",
  },
];

// ── Page ──────────────────────────────────────────────────────────────────

const ReportDetailPage = () => {
  const { reportId } = useParams();
  const navigate = useNavigate();

  const [report, setReport] = useState(null);
  const [loading, setLoading] = useState(true);
  const [isEditing, setIsEditing] = useState(false);
  const [formData, setFormData] = useState(null);
  const [apiLoading, setApiLoading] = useState(false);
  const [regenerating, setRegenerating] = useState(false);
  const [downloading, setDownloading] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState({ type: "", text: "" });
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);

  const [showDownloadMenu, setShowDownloadMenu] = useState(false);
  const downloadMenuRef = useRef(null);

  // ── AI Enhancement (Synthesis + QA) ────────────────────────────────
  // Polls /synthesis/status and /qa/status every 3 s while either
  // pipeline is in flight, then stops automatically. The hook also
  // exposes ``refresh()`` which we call after dispatching a pipeline so
  // we don't have to wait for the next tick to see "pending".
  const enhancement = useReportEnhancement(reportId);
  const [qaModalReport, setQaModalReport] = useState(null);

  // When QA finishes we want to surface the score on the panel. The
  // status endpoint only returns ``qa_progress`` (light) — the full
  // ``qa_report`` lives on the detail endpoint. Pull it once after
  // completion so the panel can show the score badge.
  const [qaFullReport, setQaFullReport] = useState(null);
  useEffect(() => {
    let cancelled = false;
    const status = enhancement.qa?.qa_status;
    if (status !== "completed") {
      if (qaFullReport) setQaFullReport(null);
      return undefined;
    }
    (async () => {
      try {
        const data = await qaService.getReport(reportId);
        if (!cancelled) setQaFullReport(data?.qa_report || null);
      } catch (err) {
        console.error("Failed to fetch QA report", err);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [enhancement.qa?.qa_status, enhancement.qa?.qa_completed_at, reportId, qaFullReport]);

  // After Synthesis completes the cached HTML/Markdown body changes —
  // pull the full report so the preview pane reflects the new content.
  const [lastSynCompletedAt, setLastSynCompletedAt] = useState(null);
  useEffect(() => {
    const completedAt = enhancement.synthesis?.synthesis_completed_at;
    const status = enhancement.synthesis?.synthesis_status;
    if (status !== "completed" || !completedAt) return;
    if (completedAt === lastSynCompletedAt) return;
    setLastSynCompletedAt(completedAt);
    // Refetch report; ignore errors silently.
    (async () => {
      try {
        const data = await reportService.getReport(reportId);
        setReport(data);
        setFormData({
          title: data.title,
          report_type: data.report_type,
          content: data.content || "",
          status: data.status,
        });
      } catch (err) {
        console.error("Failed to refresh report after synthesis", err);
      }
    })();
  }, [
    enhancement.synthesis?.synthesis_status,
    enhancement.synthesis?.synthesis_completed_at,
    lastSynCompletedAt,
    reportId,
  ]);

  useEffect(() => {
    loadReport();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [reportId]);

  // Close download menu on outside click
  useEffect(() => {
    if (!showDownloadMenu) return undefined;
    const onClick = (e) => {
      if (
        downloadMenuRef.current &&
        !downloadMenuRef.current.contains(e.target)
      ) {
        setShowDownloadMenu(false);
      }
    };
    document.addEventListener("mousedown", onClick);
    return () => document.removeEventListener("mousedown", onClick);
  }, [showDownloadMenu]);

  const flashSuccess = (text) => {
    setMessage({ type: "success", text });
    setTimeout(() => setMessage({ type: "", text: "" }), 3000);
  };

  const loadReport = async () => {
    try {
      setLoading(true);
      const data = await reportService.getReport(reportId);
      setReport(data);
      setFormData({
        title: data.title,
        report_type: data.report_type,
        content: data.content || "",
        status: data.status,
      });
      setError("");
    } catch (err) {
      setError("Không thể tải thông tin báo cáo");
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setApiLoading(true);
    setError("");

    // Only send fields the user actually changed. Sending the full
    // formData on every save makes the backend think the user wants to
    // pin the body to the current text — which then suppresses auto-
    // regeneration when only title or type changed, and leaves the
    // cached HTML preview stale because the markdown body never moves.
    // The diff-only patch keeps the backend's three branches (regen
    // from data / re-render from edited markdown / metadata-only)
    // distinguishable.
    const patch = {};
    if (formData.title !== report.title) patch.title = formData.title;
    if (formData.report_type !== report.report_type) {
      patch.report_type = formData.report_type;
    }
    if (formData.status !== report.status) patch.status = formData.status;
    if ((formData.content || "") !== (report.content || "")) {
      patch.content = formData.content;
    }

    if (Object.keys(patch).length === 0) {
      flashSuccess("Không có thay đổi nào để lưu");
      setIsEditing(false);
      setApiLoading(false);
      return;
    }

    try {
      const updated = await reportService.updateReport(reportId, patch);
      flashSuccess("Cập nhật báo cáo thành công");
      setReport(updated);
      setFormData({
        title: updated.title,
        report_type: updated.report_type,
        content: updated.content || "",
        status: updated.status,
      });
      setIsEditing(false);
    } catch (err) {
      setError(err.response?.data?.detail || "Không thể cập nhật báo cáo");
      console.error(err);
    } finally {
      setApiLoading(false);
    }
  };

  const handleChange = (e) =>
    setFormData({ ...formData, [e.target.name]: e.target.value });

  const handleArchive = async () => {
    setApiLoading(true);
    try {
      const newStatus = report.status === "archived" ? "draft" : "archived";
      const updated = await reportService.updateReport(reportId, {
        status: newStatus,
      });
      setReport(updated);
      flashSuccess(
        report.status === "archived" ? "Đã bỏ lưu trữ" : "Đã lưu trữ báo cáo"
      );
    } catch (err) {
      setError("Không thể cập nhật trạng thái");
      console.error(err);
    } finally {
      setApiLoading(false);
    }
  };

  const handlePublish = async () => {
    setApiLoading(true);
    try {
      const updated = await reportService.updateReport(reportId, {
        status: "published",
      });
      setReport(updated);
      flashSuccess("Đã xuất bản báo cáo");
    } catch (err) {
      setError("Không thể xuất bản báo cáo");
      console.error(err);
    } finally {
      setApiLoading(false);
    }
  };

  const handleDelete = async () => {
    setApiLoading(true);
    try {
      await reportService.deleteReport(reportId);
      navigate("/reports");
    } catch (err) {
      setError("Không thể xóa báo cáo");
      setShowDeleteConfirm(false);
      console.error(err);
    } finally {
      setApiLoading(false);
    }
  };

  const handleRegenerate = async () => {
    if (
      !window.confirm(
        "Tạo lại nội dung báo cáo từ dữ liệu Documents và Analysis hiện tại? " +
          "Nội dung hiện tại sẽ bị ghi đè."
      )
    )
      return;

    setRegenerating(true);
    setError("");
    try {
      const updated = await reportService.regenerateReport(reportId);
      setReport(updated);
      setFormData((prev) => ({
        ...(prev || {}),
        content: updated.content || "",
      }));
      flashSuccess("Đã tạo lại nội dung từ dữ liệu mới nhất");
    } catch (err) {
      setError(err.response?.data?.detail || "Không thể tạo lại nội dung");
      console.error(err);
    } finally {
      setRegenerating(false);
    }
  };

  const handleDownload = async (format) => {
    setShowDownloadMenu(false);
    setDownloading(true);
    setError("");
    try {
      await reportService.downloadReport(reportId, format);
      flashSuccess(`Đã tải xuống bản ${format.toUpperCase()}`);
    } catch (err) {
      setError(
        err.response?.data?.detail ||
          `Không thể tải xuống bản ${format.toUpperCase()}`
      );
      console.error(err);
    } finally {
      setDownloading(false);
    }
  };

  const formatDate = (dateString) => {
    if (!dateString) return "—";
    const date = new Date(dateString);
    return date.toLocaleString("vi-VN", {
      day: "2-digit",
      month: "2-digit",
      year: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  };

  // ── Loading ──────────────────────────────────────────────────────────────
  if (loading) {
    return (
      <DashboardLayout>
        <div className="flex items-center justify-center h-96">
          <div className="text-center">
            <div className="w-12 h-12 border-4 border-teal-200 border-t-teal-600 rounded-full animate-spin mx-auto mb-4" />
            <p className="text-slate-600 font-medium">Đang tải báo cáo...</p>
          </div>
        </div>
      </DashboardLayout>
    );
  }

  // ── Not found ────────────────────────────────────────────────────────────
  if (!report) {
    return (
      <DashboardLayout>
        <div className="text-center py-16">
          <AlertCircle className="w-16 h-16 text-red-400 mx-auto mb-4" />
          <h2 className="text-2xl font-bold text-slate-900 mb-2">
            Không tìm thấy báo cáo
          </h2>
          <p className="text-slate-600 mb-8">
            Báo cáo bạn tìm không tồn tại hoặc đã bị xóa
          </p>
          <button
            onClick={() => navigate("/reports")}
            className="inline-flex items-center gap-2 px-6 py-3 bg-gradient-to-r from-teal-600 to-teal-700 hover:from-teal-700 hover:to-teal-800 text-white rounded-xl font-semibold transition-all shadow-lg hover:shadow-xl"
          >
            <ArrowLeft className="w-5 h-5" />
            Quay lại Báo cáo
          </button>
        </div>
      </DashboardLayout>
    );
  }

  const type = TYPE_CONFIG[report.report_type] || TYPE_CONFIG.custom;
  const status = STATUS_CONFIG[report.status] || STATUS_CONFIG.draft;
  const TypeIcon = type.icon;
  const StatusIcon = status.icon;
  const docCount = Array.isArray(report.included_documents)
    ? report.included_documents.length
    : 0;

  return (
    <DashboardLayout>
      <div className="space-y-8">
        {/* ── Breadcrumb ─────────────────────────────────────────────── */}
        <div className="flex items-center gap-3 text-sm">
          <button
            onClick={() => navigate("/reports")}
            className="flex items-center gap-2 text-teal-600 hover:text-teal-700 font-semibold transition-colors group"
          >
            <ArrowLeft className="w-4 h-4 group-hover:-translate-x-1 transition-transform" />
            Báo cáo
          </button>
          <span className="text-slate-400">/</span>
          <span className="text-slate-900 font-semibold truncate max-w-md">
            {report.title}
          </span>
        </div>

        {/* ── Banners ────────────────────────────────────────────────── */}
        {error && (
          <div className="flex items-start gap-3 bg-red-50 border border-red-200 text-red-700 px-6 py-4 rounded-xl">
            <AlertCircle className="w-5 h-5 flex-shrink-0 mt-0.5" />
            <span className="text-sm font-medium flex-1">{error}</span>
            <button
              onClick={() => setError("")}
              className="text-red-500 hover:text-red-700"
            >
              <X className="w-4 h-4" />
            </button>
          </div>
        )}

        {message.text && (
          <div
            className={`border rounded-xl px-6 py-4 flex items-start gap-3 ${
              message.type === "success"
                ? "bg-emerald-50 border-emerald-200 text-emerald-700"
                : "bg-red-50 border-red-200 text-red-700"
            }`}
          >
            {message.type === "success" ? (
              <CheckCircle2 className="w-5 h-5 flex-shrink-0 mt-0.5" />
            ) : (
              <AlertCircle className="w-5 h-5 flex-shrink-0 mt-0.5" />
            )}
            <span className="text-sm font-medium">{message.text}</span>
          </div>
        )}

        {/* ── Page header card (matches AnalysisResultsPage) ───────── */}
        {!isEditing && (
          <div className="bg-white rounded-2xl border border-slate-200 p-8 shadow-sm">
            <div className="flex items-start gap-5">
              <div
                className={`p-4 rounded-2xl ${type.accent.bg} border ${type.accent.border} flex-shrink-0`}
              >
                <TypeIcon className={`w-8 h-8 ${type.accent.text}`} />
              </div>
              <div className="flex-1 min-w-0">
                <div className="flex items-start justify-between gap-4 flex-wrap">
                  <div className="min-w-0">
                    <h1 className="text-2xl font-bold text-slate-900 mb-1 break-words">
                      {report.title}
                    </h1>
                    <div className="flex items-center gap-3 flex-wrap text-sm text-slate-500">
                      <span className="inline-flex items-center gap-1.5">
                        <Tag className="w-3.5 h-3.5" />
                        {type.label}
                      </span>
                      <span className="text-slate-300">·</span>
                      <span className="inline-flex items-center gap-1.5 font-mono text-xs">
                        <Hash className="w-3 h-3" />
                        {report.id?.slice(0, 8)}
                      </span>
                    </div>
                  </div>

                  <div className="flex items-center gap-2 flex-wrap">
                    <span
                      className={`inline-flex items-center gap-1.5 px-4 py-1.5 rounded-xl text-sm font-bold ${status.badge}`}
                    >
                      <StatusIcon className="w-3.5 h-3.5" />
                      {status.label}
                    </span>
                  </div>
                </div>

                {/* Quick action bar */}
                <div className="flex items-center gap-2 mt-5 pt-5 border-t border-slate-100 flex-wrap">
                  <button
                    onClick={handleRegenerate}
                    disabled={regenerating || apiLoading}
                    className="inline-flex items-center gap-2 px-4 py-2 border border-slate-200 hover:bg-slate-50 hover:border-slate-300 text-slate-700 rounded-xl font-semibold text-sm transition-colors disabled:opacity-50"
                    title="Tạo lại nội dung từ dữ liệu Document + Analysis hiện tại"
                  >
                    <RefreshCw
                      className={`w-4 h-4 ${regenerating ? "animate-spin" : ""}`}
                    />
                    {regenerating ? "Đang tạo lại..." : "Tạo lại nội dung"}
                  </button>

                  <div className="relative" ref={downloadMenuRef}>
                    <button
                      onClick={() => setShowDownloadMenu((v) => !v)}
                      disabled={downloading}
                      className="inline-flex items-center gap-2 px-4 py-2 bg-gradient-to-r from-teal-600 to-teal-700 hover:from-teal-700 hover:to-teal-800 text-white rounded-xl font-semibold text-sm transition-all shadow-md hover:shadow-lg disabled:opacity-50"
                    >
                      <Download className="w-4 h-4" />
                      {downloading ? "Đang tải..." : "Tải xuống"}
                      <ChevronDown className="w-4 h-4" />
                    </button>
                    {showDownloadMenu && (
                      <div className="absolute right-0 mt-2 w-72 bg-white border border-slate-200 rounded-xl shadow-xl z-20 overflow-hidden">
                        {DOWNLOAD_FORMATS.map((fmt) => (
                          <button
                            key={fmt.value}
                            onClick={() => handleDownload(fmt.value)}
                            className="w-full text-left px-4 py-3 hover:bg-teal-50 transition-colors border-b border-slate-100 last:border-b-0"
                          >
                            <div className="font-semibold text-slate-900 text-sm">
                              {fmt.label}
                            </div>
                            <div className="text-xs text-slate-500 mt-0.5">
                              {fmt.description}
                            </div>
                          </button>
                        ))}
                      </div>
                    )}
                  </div>

                  <button
                    onClick={() => setIsEditing(true)}
                    className="inline-flex items-center gap-2 px-4 py-2 border border-slate-200 hover:bg-slate-50 hover:border-slate-300 text-slate-700 rounded-xl font-semibold text-sm transition-colors"
                  >
                    <Edit2 className="w-4 h-4" />
                    Chỉnh sửa
                  </button>

                  {report.status !== "published" && (
                    <button
                      onClick={handlePublish}
                      disabled={apiLoading}
                      className="inline-flex items-center gap-2 px-4 py-2 border border-emerald-200 text-emerald-700 hover:bg-emerald-50 rounded-xl font-semibold text-sm transition-colors disabled:opacity-50"
                    >
                      <Upload className="w-4 h-4" />
                      Xuất bản
                    </button>
                  )}

                  <div className="ml-auto" />

                  <button
                    onClick={() => setShowDeleteConfirm(true)}
                    disabled={apiLoading}
                    className="inline-flex items-center gap-2 px-4 py-2 border border-red-200 text-red-600 hover:bg-red-50 rounded-xl font-semibold text-sm transition-colors disabled:opacity-50"
                  >
                    <Trash2 className="w-4 h-4" />
                    Xóa
                  </button>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* ── Body ──────────────────────────────────────────────────── */}
        {!isEditing ? (
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            {/* Left — rendered HTML report */}
            <div className="lg:col-span-2 space-y-4">
              {report.html_content ? (
                <div className="bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden">
                  <ReportHtmlPreview html={report.html_content} />
                </div>
              ) : report.content ? (
                <div className="bg-white rounded-2xl border border-slate-200 p-8 shadow-sm">
                  <h2 className="text-xl font-bold text-slate-900 mb-6 flex items-center gap-2">
                    <span className="w-1 h-6 rounded-full bg-teal-600" />
                    Nội dung báo cáo
                  </h2>
                  <pre className="whitespace-pre-wrap font-sans text-slate-700 leading-relaxed text-base">
                    {report.content}
                  </pre>
                </div>
              ) : (
                <div className="bg-white rounded-2xl border border-slate-200 p-12 shadow-sm text-center">
                  <ClipboardList className="w-12 h-12 text-slate-300 mx-auto mb-4" />
                  <p className="text-slate-600 mb-2 font-semibold">
                    Báo cáo chưa có nội dung
                  </p>
                  <p className="text-slate-500 text-sm mb-6 max-w-md mx-auto">
                    Hệ thống tự dựng báo cáo từ Documents và Analysis của dự án.
                    Bấm nút bên dưới để tạo nội dung.
                  </p>
                  <button
                    onClick={handleRegenerate}
                    disabled={regenerating}
                    className="inline-flex items-center gap-2 px-6 py-3 bg-gradient-to-r from-teal-600 to-teal-700 hover:from-teal-700 hover:to-teal-800 text-white rounded-xl font-semibold transition-all shadow-lg hover:shadow-xl disabled:opacity-50"
                  >
                    <RefreshCw
                      className={`w-4 h-4 ${regenerating ? "animate-spin" : ""}`}
                    />
                    {regenerating ? "Đang tạo..." : "Tạo nội dung báo cáo"}
                  </button>
                </div>
              )}
            </div>

            {/* Right — sidebar */}
            <div className="space-y-6">
              {/* AI Enhancement card — Synthesis + QA */}
              <AIEnhancementPanel
                reportId={reportId}
                synthesis={enhancement.synthesis}
                qa={{
                  ...(enhancement.qa || {}),
                  qa_report: qaFullReport,
                }}
                onRefresh={enhancement.refresh}
                onOpenQAReport={(qr) => setQaModalReport(qr)}
                onAfterSynthesis={loadReport}
              />

              {/* Metadata card */}
              <div className="bg-white rounded-2xl border border-slate-200 p-6 shadow-sm">
                <h3 className="text-sm font-semibold text-slate-600 mb-5 uppercase tracking-wide">
                  Thông tin
                </h3>
                <div className="space-y-4">
                  <SidebarRow
                    icon={Tag}
                    label="Loại báo cáo"
                    value={
                      <span
                        className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-xs font-bold ${type.accent.bg} ${type.accent.text}`}
                      >
                        <TypeIcon className="w-3 h-3" />
                        {type.label}
                      </span>
                    }
                  />
                  <SidebarRow
                    icon={StatusIcon}
                    label="Trạng thái"
                    value={
                      <span
                        className={`inline-flex items-center gap-1 px-2.5 py-1 rounded-lg text-xs font-bold ${status.badge}`}
                      >
                        {status.label}
                      </span>
                    }
                    divider
                  />
                  <SidebarRow
                    icon={Calendar}
                    label="Ngày tạo"
                    value={formatDate(report.created_at)}
                    divider
                  />
                  <SidebarRow
                    icon={Clock}
                    label="Cập nhật lần cuối"
                    value={formatDate(report.updated_at)}
                    divider
                  />
                  {docCount > 0 && (
                    <SidebarRow
                      icon={ClipboardList}
                      label="Tài liệu đính kèm"
                      value={`${docCount} tài liệu`}
                      divider
                    />
                  )}
                  <div className="border-t border-slate-200 pt-4">
                    <p className="text-xs font-semibold text-slate-600 mb-2">
                      Report ID
                    </p>
                    <p className="text-xs font-mono text-slate-500 bg-slate-50 p-2 rounded-lg border border-slate-200 break-all">
                      {report.id}
                    </p>
                  </div>
                </div>
              </div>

              {/* Quick actions card */}
              <div className="bg-white rounded-2xl border border-slate-200 p-6 shadow-sm space-y-3">
                <h3 className="text-sm font-semibold text-slate-600 mb-2 uppercase tracking-wide">
                  Hành động
                </h3>
                <button
                  onClick={handleArchive}
                  disabled={apiLoading}
                  className="w-full flex items-center justify-center gap-2 px-4 py-2.5 border border-slate-200 rounded-xl text-slate-700 hover:bg-slate-50 font-semibold text-sm transition-colors disabled:opacity-50"
                >
                  {report.status === "archived" ? (
                    <>
                      <ArchiveRestore className="w-4 h-4" />
                      Bỏ lưu trữ
                    </>
                  ) : (
                    <>
                      <Archive className="w-4 h-4" />
                      Lưu trữ
                    </>
                  )}
                </button>
                <button
                  onClick={() => navigate("/reports")}
                  className="w-full flex items-center justify-center gap-2 px-4 py-2.5 border border-slate-200 rounded-xl text-slate-700 hover:bg-slate-50 font-semibold text-sm transition-colors"
                >
                  <ArrowLeft className="w-4 h-4" />
                  Quay lại danh sách
                </button>
              </div>
            </div>
          </div>
        ) : (
          // ── Edit mode ─────────────────────────────────────────────
          <div className="bg-white rounded-2xl border border-slate-200 p-8 shadow-sm">
            <div className="flex items-start justify-between gap-3 mb-6 pb-6 border-b border-slate-200">
              <div>
                <h2 className="text-xl font-bold text-slate-900">
                  Chỉnh sửa báo cáo
                </h2>
                <p className="text-sm text-slate-500 mt-1">
                  Khi đổi tiêu đề hoặc loại báo cáo, hệ thống sẽ tự dựng lại
                  nội dung từ dữ liệu Document + Analysis.
                </p>
              </div>
              <button
                onClick={() => setIsEditing(false)}
                className="text-slate-400 hover:text-slate-600 p-1 hover:bg-slate-100 rounded-lg"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <form onSubmit={handleSubmit} className="space-y-5">
              <div>
                <label className="block text-sm font-semibold text-slate-900 mb-2">
                  Tiêu đề báo cáo <span className="text-red-500">*</span>
                </label>
                <input
                  type="text"
                  name="title"
                  required
                  minLength={3}
                  maxLength={500}
                  value={formData.title}
                  onChange={handleChange}
                  className="w-full px-4 py-3 border border-slate-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-teal-500 focus:ring-offset-2 focus:border-transparent transition-all"
                />
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-semibold text-slate-900 mb-2">
                    Loại báo cáo
                  </label>
                  <select
                    name="report_type"
                    value={formData.report_type}
                    onChange={handleChange}
                    className="w-full px-4 py-3 border border-slate-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-teal-500 focus:ring-offset-2 focus:border-transparent transition-all bg-white"
                  >
                    <option value="research_summary">Tóm tắt nghiên cứu</option>
                    <option value="literature_review">Tổng quan tài liệu</option>
                    <option value="data_analysis">Phân tích dữ liệu</option>
                    <option value="custom">Tùy chỉnh</option>
                  </select>
                </div>

                <div>
                  <label className="block text-sm font-semibold text-slate-900 mb-2">
                    Trạng thái
                  </label>
                  <select
                    name="status"
                    value={formData.status}
                    onChange={handleChange}
                    className="w-full px-4 py-3 border border-slate-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-teal-500 focus:ring-offset-2 focus:border-transparent transition-all bg-white"
                  >
                    <option value="draft">Nháp</option>
                    <option value="published">Đã xuất bản</option>
                    <option value="archived">Lưu trữ</option>
                  </select>
                </div>
              </div>

              <div>
                <label className="block text-sm font-semibold text-slate-900 mb-2">
                  Nội dung Markdown
                  <span className="text-slate-400 font-normal ml-1.5">
                    (cao cấp — bỏ trống để dùng nội dung tự sinh)
                  </span>
                </label>
                <textarea
                  name="content"
                  rows={14}
                  value={formData.content}
                  onChange={handleChange}
                  className="w-full px-4 py-3 border border-slate-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-teal-500 focus:ring-offset-2 focus:border-transparent transition-all resize-y font-mono text-sm bg-slate-50/50"
                  placeholder="# Tiêu đề&#10;&#10;Nội dung Markdown..."
                />
              </div>

              <div className="flex items-center justify-end gap-3 pt-6 border-t border-slate-200">
                <button
                  type="button"
                  onClick={() => setIsEditing(false)}
                  className="px-5 py-2.5 border border-slate-200 rounded-xl text-slate-700 hover:bg-slate-50 font-semibold transition-colors"
                >
                  Hủy
                </button>
                <button
                  type="submit"
                  disabled={apiLoading}
                  className="inline-flex items-center gap-2 px-5 py-2.5 bg-gradient-to-r from-teal-600 to-teal-700 hover:from-teal-700 hover:to-teal-800 disabled:opacity-60 text-white rounded-xl font-semibold transition-all shadow-lg hover:shadow-xl"
                >
                  {apiLoading ? (
                    <>
                      <Loader className="w-4 h-4 animate-spin" />
                      Đang lưu...
                    </>
                  ) : (
                    <>
                      <CheckCircle2 className="w-4 h-4" />
                      Lưu thay đổi
                    </>
                  )}
                </button>
              </div>
            </form>
          </div>
        )}
      </div>

      {/* ── QA Report Modal (full-screen, mounted at page root) ───── */}
      {qaModalReport && (
        <QAReportModal
          qaReport={qaModalReport}
          reportTitle={report?.title}
          onClose={() => setQaModalReport(null)}
        />
      )}

      {/* ── Delete confirmation ──────────────────────────────────── */}
      {showDeleteConfirm && (
        <div className="fixed inset-0 bg-black/40 backdrop-blur-sm flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-2xl shadow-2xl max-w-md w-full p-8">
            <div className="flex items-start gap-4 mb-6">
              <div className="w-12 h-12 rounded-xl bg-red-100 flex items-center justify-center flex-shrink-0">
                <Trash2 className="w-6 h-6 text-red-600" />
              </div>
              <div>
                <h3 className="text-lg font-bold text-slate-900 mb-1">
                  Xóa báo cáo?
                </h3>
                <p className="text-sm text-slate-600">
                  Hành động này không thể hoàn tác. Báo cáo{" "}
                  <span className="font-semibold text-slate-800">
                    {report.title}
                  </span>{" "}
                  sẽ bị xóa vĩnh viễn.
                </p>
              </div>
            </div>
            <div className="flex items-center justify-end gap-3">
              <button
                onClick={() => setShowDeleteConfirm(false)}
                disabled={apiLoading}
                className="flex items-center gap-2 px-5 py-2.5 border border-slate-200 rounded-xl text-slate-700 hover:bg-slate-50 font-semibold transition-colors disabled:opacity-50"
              >
                <X className="w-4 h-4" />
                Hủy
              </button>
              <button
                onClick={handleDelete}
                disabled={apiLoading}
                className="flex items-center gap-2 px-5 py-2.5 bg-red-600 hover:bg-red-700 disabled:opacity-60 text-white rounded-xl font-semibold transition-colors shadow-sm"
              >
                {apiLoading ? (
                  <>
                    <Loader className="w-4 h-4 animate-spin" />
                    Đang xóa...
                  </>
                ) : (
                  <>
                    <Trash2 className="w-4 h-4" />
                    Xóa báo cáo
                  </>
                )}
              </button>
            </div>
          </div>
        </div>
      )}
    </DashboardLayout>
  );
};

// ── Sub-components ────────────────────────────────────────────────────────

const SidebarRow = ({ icon: Icon, label, value, divider }) => (
  <div className={divider ? "border-t border-slate-200 pt-4" : ""}>
    <p className="text-xs font-semibold text-slate-600 mb-2 flex items-center gap-2">
      <Icon className="w-3.5 h-3.5" />
      {label}
    </p>
    <div className="text-sm text-slate-700 font-medium">
      {typeof value === "string" ? value : value}
    </div>
  </div>
);

/**
 * Render the report's full HTML inside an iframe so its embedded
 * <style> rules don't leak into the host page.
 *
 * The backend always returns a self-contained HTML document, so we use
 * srcDoc and let the browser do the rest. We auto-size the iframe to
 * its content via a ResizeObserver to avoid an awkward inner scrollbar.
 */
const ReportHtmlPreview = ({ html }) => {
  const iframeRef = useRef(null);
  const [height, setHeight] = useState(800);

  useEffect(() => {
    const iframe = iframeRef.current;
    if (!iframe) return;

    const measure = () => {
      try {
        const doc = iframe.contentDocument || iframe.contentWindow?.document;
        if (!doc) return;
        const newHeight = Math.max(
          doc.documentElement.scrollHeight,
          doc.body?.scrollHeight || 0
        );
        if (newHeight && Math.abs(newHeight - height) > 4) {
          setHeight(newHeight);
        }
      } catch {
        // cross-origin or not yet loaded — ignore.
      }
    };

    const onLoad = () => {
      measure();
      try {
        const doc = iframe.contentDocument;
        if (doc?.fonts?.ready) doc.fonts.ready.then(measure);
        if (doc?.body && "ResizeObserver" in window) {
          const ro = new ResizeObserver(measure);
          ro.observe(doc.body);
          iframe._ro = ro;
        }
      } catch {
        // ignore
      }
    };
    iframe.addEventListener("load", onLoad);
    return () => {
      iframe.removeEventListener("load", onLoad);
      if (iframe._ro) iframe._ro.disconnect();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [html]);

  return (
    <iframe
      ref={iframeRef}
      title="Báo cáo"
      srcDoc={html}
      sandbox="allow-same-origin allow-popups"
      style={{
        width: "100%",
        height: `${height}px`,
        border: "0",
        display: "block",
      }}
    />
  );
};

export default ReportDetailPage;
