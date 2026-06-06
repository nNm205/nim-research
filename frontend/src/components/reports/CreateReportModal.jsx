import { useEffect, useState, useMemo } from "react";
import {
  X,
  FileText,
  BookOpen,
  BarChart3,
  Sparkles,
  ClipboardList,
  Loader,
  AlertCircle,
  Folder,
  CheckCircle2,
  Search,
} from "lucide-react";
import { documentService } from "../../services/documentService";

/**
 * CreateReportModal — usable from two places:
 *
 *   1. Global Reports page (cross-project): pass ``projects`` so the user
 *      picks the project from a dropdown inside the modal.
 *   2. ProjectDetailPage (project-scoped): pass ``lockedProject`` so the
 *      project picker is hidden and the report is auto-attached to the
 *      current project.
 *
 * Visual language matches StartAnalysisModal / AutoResearchModal:
 *   - rounded-2xl frame with sticky top header
 *   - section headings with small icon
 *   - radio cards with active state in teal
 *   - footer with Cancel + primary CTA
 */

const REPORT_TYPES = [
  {
    value: "research_summary",
    label: "Tóm tắt nghiên cứu",
    icon: FileText,
    description:
      "Báo cáo executive: tóm tắt nhanh từng tài liệu, phát hiện nổi bật, từ khóa quan trọng",
    bestFor: "Khi muốn nắm tổng quan dự án trong vài phút",
  },
  {
    value: "literature_review",
    label: "Tổng quan tài liệu",
    icon: BookOpen,
    description:
      "So sánh đóng góp, phương pháp và khoảng trống nghiên cứu giữa các tài liệu",
    bestFor: "Khi viết phần Related Work hoặc literature review học thuật",
  },
  {
    value: "data_analysis",
    label: "Phân tích dữ liệu",
    icon: BarChart3,
    description:
      "Bảng tổng quan + phát hiện chính, phù hợp với dự án có nhiều dữ liệu thực nghiệm",
    bestFor: "Khi cần báo cáo kết quả phân tích định lượng",
  },
  {
    value: "custom",
    label: "Tùy chỉnh",
    icon: Sparkles,
    description: "Khung báo cáo trống — bạn tự biên soạn nội dung",
    bestFor: "Khi cần định dạng riêng không khớp với 3 mẫu trên",
  },
];

const CreateReportModal = ({
  projects = [],
  lockedProject = null,
  onClose,
  onCreate,
}) => {
  // When ``lockedProject`` is provided we operate in single-project mode
  // and hide the picker entirely. Otherwise fall back to the cross-project
  // picker fed by ``projects``.
  const projectList = lockedProject ? [lockedProject] : projects;
  const [projectId, setProjectId] = useState(
    lockedProject?.id || projects[0]?.id || ""
  );
  const [reportType, setReportType] = useState("research_summary");
  const [title, setTitle] = useState("");

  const [includeAll, setIncludeAll] = useState(true);
  const [selectedDocIds, setSelectedDocIds] = useState(new Set());

  const [documents, setDocuments] = useState([]);
  const [docsLoading, setDocsLoading] = useState(false);
  const [docFilter, setDocFilter] = useState("");

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  // Reset selected docs when project changes — different project, different
  // document pool.
  useEffect(() => {
    setSelectedDocIds(new Set());
    setDocuments([]);
    setDocFilter("");
  }, [projectId]);

  // Lazy-load documents for the picked project. Only fetch when the user
  // actually wants to narrow them down.
  useEffect(() => {
    if (!projectId || includeAll) return undefined;
    let cancelled = false;
    (async () => {
      try {
        setDocsLoading(true);
        const data = await documentService.getProjectDocuments(projectId);
        if (!cancelled) setDocuments(Array.isArray(data) ? data : []);
      } catch (err) {
        console.error("Failed to load project documents", err);
      } finally {
        if (!cancelled) setDocsLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [projectId, includeAll]);

  const filteredDocs = useMemo(() => {
    const q = docFilter.trim().toLowerCase();
    if (!q) return documents;
    return documents.filter((d) => (d.title || "").toLowerCase().includes(q));
  }, [documents, docFilter]);

  const toggleDoc = (docId) => {
    setSelectedDocIds((prev) => {
      const next = new Set(prev);
      if (next.has(docId)) next.delete(docId);
      else next.add(docId);
      return next;
    });
  };

  const toggleAllVisible = () => {
    setSelectedDocIds((prev) => {
      const allVisibleSelected = filteredDocs.every((d) => prev.has(d.id));
      const next = new Set(prev);
      if (allVisibleSelected) {
        filteredDocs.forEach((d) => next.delete(d.id));
      } else {
        filteredDocs.forEach((d) => next.add(d.id));
      }
      return next;
    });
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError("");

    if (!projectId) {
      setError("Vui lòng chọn dự án");
      return;
    }
    if (!title.trim() || title.trim().length < 3) {
      setError("Tiêu đề phải có ít nhất 3 ký tự");
      return;
    }
    if (!includeAll && selectedDocIds.size === 0) {
      setError("Hãy chọn ít nhất một tài liệu hoặc đổi sang 'Toàn bộ tài liệu'");
      return;
    }

    setLoading(true);
    try {
      const payload = {
        title: title.trim(),
        report_type: reportType,
      };
      if (!includeAll) {
        payload.included_documents = Array.from(selectedDocIds);
      }
      await onCreate(projectId, payload);
    } catch (err) {
      setError(err.response?.data?.detail || "Không thể tạo báo cáo");
    } finally {
      setLoading(false);
    }
  };

  const selectedProject = projectList.find((p) => p.id === projectId);

  return (
    <div className="fixed inset-0 bg-black/30 backdrop-blur-sm flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-2xl max-w-3xl w-full max-h-[90vh] flex flex-col shadow-2xl overflow-hidden">
        {/* ── Sticky header ─────────────────────────────────────────── */}
        <div className="border-b border-slate-200 px-8 py-5 flex items-center justify-between flex-shrink-0">
          <div className="flex items-center gap-3 min-w-0">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-teal-500 to-teal-600 flex items-center justify-center flex-shrink-0">
              <ClipboardList className="w-5 h-5 text-white" />
            </div>
            <div className="min-w-0">
              <h2 className="text-xl font-bold text-slate-900">
                Tạo báo cáo mới
              </h2>
              <p className="text-xs text-slate-500 mt-0.5">
                Hệ thống sẽ tự dựng nội dung từ Documents + Analysis của dự án
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="text-slate-400 hover:text-slate-600 transition-colors p-1 hover:bg-slate-100 rounded-lg flex-shrink-0 ml-3"
            aria-label="Đóng"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* ── Body ──────────────────────────────────────────────────── */}
        <form
          onSubmit={handleSubmit}
          className="flex-1 overflow-y-auto no-scrollbar p-6 space-y-6"
        >
          {error && (
            <div className="flex items-start gap-3 bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-xl text-sm">
              <AlertCircle className="w-4 h-4 flex-shrink-0 mt-0.5" />
              <span>{error}</span>
            </div>
          )}

          {/* 1 — Project picker (only shown in cross-project mode) */}
          {!lockedProject && (
            <>
              <SectionLabel icon={Folder} title="Dự án" required />
              <select
                value={projectId}
                onChange={(e) => setProjectId(e.target.value)}
                required
                className="w-full px-4 py-3 border border-slate-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-teal-500 focus:ring-offset-2 focus:border-transparent transition-all text-slate-900 bg-white font-medium"
              >
                <option value="" disabled>
                  Chọn dự án...
                </option>
                {projects.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.name}
                  </option>
                ))}
              </select>
              {selectedProject?.topic && (
                <p className="text-xs text-slate-500 -mt-3 ml-1 italic">
                  Chủ đề: {selectedProject.topic}
                </p>
              )}
            </>
          )}

          {/* 2 — Title */}
          <SectionLabel icon={FileText} title="Tiêu đề báo cáo" required />
          <input
            type="text"
            required
            minLength={3}
            maxLength={500}
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            placeholder="Ví dụ: Tổng quan nghiên cứu Vision Transformer 2024-2026"
            className="w-full px-4 py-3 border border-slate-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-teal-500 focus:ring-offset-2 focus:border-transparent transition-all text-slate-900"
          />

          {/* 3 — Report type */}
          <SectionLabel icon={Sparkles} title="Loại báo cáo" required />
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {REPORT_TYPES.map((type) => {
              const Icon = type.icon;
              const active = reportType === type.value;
              return (
                <button
                  key={type.value}
                  type="button"
                  onClick={() => setReportType(type.value)}
                  className={`text-left rounded-xl border-2 p-4 transition-all ${
                    active
                      ? "border-teal-500 bg-teal-50 ring-2 ring-teal-100"
                      : "border-slate-200 hover:border-slate-300 hover:bg-slate-50"
                  }`}
                >
                  <div className="flex items-start gap-3">
                    <div
                      className={`p-2 rounded-lg flex-shrink-0 ${
                        active
                          ? "bg-teal-100 text-teal-700"
                          : "bg-slate-100 text-slate-500"
                      }`}
                    >
                      <Icon className="w-5 h-5" />
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center justify-between gap-2 mb-1">
                        <span className="font-bold text-slate-900 text-sm">
                          {type.label}
                        </span>
                        {active && (
                          <CheckCircle2 className="w-4 h-4 text-teal-600 flex-shrink-0" />
                        )}
                      </div>
                      <p className="text-xs text-slate-600 leading-snug mb-2">
                        {type.description}
                      </p>
                      <p className="text-[11px] text-slate-500 italic leading-snug">
                        {type.bestFor}
                      </p>
                    </div>
                  </div>
                </button>
              );
            })}
          </div>

          {/* 4 — Document scope */}
          <SectionLabel icon={ClipboardList} title="Phạm vi tài liệu" />
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            <ScopeOption
              active={includeAll}
              onClick={() => setIncludeAll(true)}
              title="Toàn bộ tài liệu"
              description="Tổng hợp tất cả tài liệu trong dự án (kèm phân tích nếu có)"
            />
            <ScopeOption
              active={!includeAll}
              onClick={() => setIncludeAll(false)}
              title="Chọn tài liệu cụ thể"
              description="Chỉ tổng hợp các tài liệu bạn chọn"
            />
          </div>

          {!includeAll && (
            <div className="border border-slate-200 rounded-xl bg-slate-50 overflow-hidden">
              {/* Doc list controls */}
              <div className="border-b border-slate-200 bg-white p-3 flex items-center gap-3 flex-wrap">
                <div className="relative flex-1 min-w-[200px]">
                  <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
                  <input
                    type="text"
                    value={docFilter}
                    onChange={(e) => setDocFilter(e.target.value)}
                    placeholder="Lọc tài liệu..."
                    className="w-full pl-9 pr-3 py-2 text-sm border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-teal-500 focus:border-transparent"
                  />
                </div>
                <button
                  type="button"
                  onClick={toggleAllVisible}
                  disabled={filteredDocs.length === 0}
                  className="text-xs font-semibold text-teal-600 hover:text-teal-700 disabled:opacity-40 disabled:cursor-not-allowed"
                >
                  {filteredDocs.every((d) => selectedDocIds.has(d.id)) &&
                  filteredDocs.length > 0
                    ? "Bỏ chọn tất cả hiển thị"
                    : "Chọn tất cả hiển thị"}
                </button>
              </div>

              {/* Doc list */}
              <div className="max-h-72 overflow-y-auto">
                {docsLoading ? (
                  <div className="flex items-center justify-center py-10 text-slate-500 gap-2">
                    <Loader className="w-4 h-4 animate-spin" />
                    Đang tải danh sách tài liệu...
                  </div>
                ) : filteredDocs.length === 0 ? (
                  <div className="py-10 text-center text-slate-500 text-sm">
                    {documents.length === 0
                      ? "Dự án này chưa có tài liệu nào"
                      : "Không có tài liệu nào khớp bộ lọc"}
                  </div>
                ) : (
                  <ul className="divide-y divide-slate-200 bg-white">
                    {filteredDocs.map((doc) => {
                      const checked = selectedDocIds.has(doc.id);
                      return (
                        <li key={doc.id}>
                          <label
                            className={`flex items-start gap-3 p-3 cursor-pointer transition-colors ${
                              checked ? "bg-teal-50" : "hover:bg-slate-50"
                            }`}
                          >
                            <input
                              type="checkbox"
                              checked={checked}
                              onChange={() => toggleDoc(doc.id)}
                              className="w-4 h-4 mt-1 text-teal-600 rounded"
                            />
                            <FileText className="w-4 h-4 text-slate-400 mt-0.5 flex-shrink-0" />
                            <div className="flex-1 min-w-0">
                              <p className="text-sm font-medium text-slate-900 truncate">
                                {doc.title || "Untitled"}
                              </p>
                              <div className="flex items-center gap-2 text-[11px] text-slate-500 mt-0.5">
                                <span className="uppercase tracking-wide font-semibold">
                                  {doc.source_type || "—"}
                                </span>
                                {doc.processed && (
                                  <>
                                    <span className="text-slate-300">·</span>
                                    <span className="text-emerald-600 font-medium">
                                      đã xử lý
                                    </span>
                                  </>
                                )}
                              </div>
                            </div>
                          </label>
                        </li>
                      );
                    })}
                  </ul>
                )}
              </div>

              <div className="px-4 py-2.5 text-xs text-slate-600 border-t border-slate-200 bg-white flex items-center justify-between">
                <span>
                  Đã chọn:{" "}
                  <strong className="text-slate-900">
                    {selectedDocIds.size}
                  </strong>
                  /{documents.length}
                </span>
                {selectedDocIds.size > 0 && (
                  <button
                    type="button"
                    onClick={() => setSelectedDocIds(new Set())}
                    className="text-xs font-semibold text-slate-500 hover:text-slate-700"
                  >
                    Xóa lựa chọn
                  </button>
                )}
              </div>
            </div>
          )}
        </form>

        {/* ── Sticky footer ─────────────────────────────────────────── */}
        <div className="border-t border-slate-200 px-6 py-4 flex items-center justify-end gap-3 bg-white flex-shrink-0">
          <button
            type="button"
            onClick={onClose}
            disabled={loading}
            className="px-5 py-2.5 border border-slate-200 rounded-xl text-slate-700 hover:bg-slate-50 font-semibold transition-colors disabled:opacity-50"
          >
            Hủy
          </button>
          <button
            type="submit"
            onClick={handleSubmit}
            disabled={loading || !projectId || !title.trim()}
            className="inline-flex items-center gap-2 px-5 py-2.5 bg-gradient-to-r from-teal-600 to-teal-700 hover:from-teal-700 hover:to-teal-800 disabled:opacity-60 disabled:cursor-not-allowed text-white rounded-xl font-semibold transition-all shadow-lg"
          >
            {loading ? (
              <>
                <Loader className="w-4 h-4 animate-spin" />
                Đang tạo...
              </>
            ) : (
              <>
                <ClipboardList className="w-4 h-4" />
                Tạo báo cáo
              </>
            )}
          </button>
        </div>
      </div>
    </div>
  );
};

const SectionLabel = ({ icon: Icon, title, required }) => (
  <div className="flex items-center gap-2 -mb-3">
    <Icon className="w-4 h-4 text-teal-600" />
    <span className="text-sm font-semibold text-slate-900">
      {title}
      {required && <span className="text-red-500 ml-1">*</span>}
    </span>
  </div>
);

const ScopeOption = ({ active, onClick, title, description }) => (
  <button
    type="button"
    onClick={onClick}
    className={`text-left rounded-xl border-2 p-4 transition-all ${
      active
        ? "border-teal-500 bg-teal-50 ring-2 ring-teal-100"
        : "border-slate-200 hover:border-slate-300 hover:bg-slate-50"
    }`}
  >
    <div className="flex items-start gap-3">
      <div
        className={`w-5 h-5 mt-0.5 rounded-full border-2 flex-shrink-0 flex items-center justify-center ${
          active ? "border-teal-600 bg-teal-600" : "border-slate-300"
        }`}
      >
        {active && <div className="w-1.5 h-1.5 rounded-full bg-white" />}
      </div>
      <div>
        <p className="font-semibold text-slate-900 text-sm mb-1">{title}</p>
        <p className="text-xs text-slate-600 leading-snug">{description}</p>
      </div>
    </div>
  </button>
);

export default CreateReportModal;
