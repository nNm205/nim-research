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
 * Visual language is intentionally identical to ``StartAnalysisModal`` and
 * ``CreateDocumentModal`` so the three creation flows feel like one product:
 *
 *   - backdrop: ``bg-black/20`` (no blur — page stays visible)
 *   - frame:    ``rounded-2xl`` + ``shadow-2xl`` + ``overflow-hidden``
 *   - header:   sticky, ``px-8 py-5`` with title + one-line subtitle
 *   - body:     ``p-8 space-y-6`` with plain ``<label>`` fields
 *   - footer:   inline at the bottom of the form, ``border-t pt-4``
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

  // Reset selected docs whenever the user picks a different project. Done
  // in the change handler (not an effect) to avoid a render cascade — see
  // ``react-hooks/set-state-in-effect``.
  const handleProjectChange = (newProjectId) => {
    if (newProjectId === projectId) return;
    setProjectId(newProjectId);
    setSelectedDocIds(new Set());
    setDocuments([]);
    setDocFilter("");
  };

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
    <div className="fixed inset-0 bg-black/20 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-2xl max-w-2xl w-full max-h-[90vh] overflow-y-auto no-scrollbar shadow-2xl">
        {/* ── Sticky header ─────────────────────────────────────────── */}
        <div className="sticky top-0 bg-white border-b border-slate-200 px-8 py-5 flex items-center justify-between z-10">
          <div>
            <h2 className="text-2xl font-bold text-slate-900">
              Tạo báo cáo mới
            </h2>
            <p className="text-sm text-slate-600 mt-1">
              Hệ thống tự dựng nội dung từ Documents + Analysis của dự án
            </p>
          </div>
          <button
            onClick={onClose}
            className="text-slate-400 hover:text-slate-600 transition-colors p-1 hover:bg-slate-100 rounded-lg"
            aria-label="Đóng"
          >
            <X className="w-6 h-6" />
          </button>
        </div>

        {/* ── Body ──────────────────────────────────────────────────── */}
        <form onSubmit={handleSubmit} className="p-8 space-y-6">
          {error && (
            <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-xl text-sm font-medium flex items-start gap-3">
              <AlertCircle className="w-4 h-4 flex-shrink-0 mt-0.5" />
              <span>{error}</span>
            </div>
          )}

          {/* 1 — Project picker (only shown in cross-project mode) */}
          {!lockedProject && (
            <div>
              <label className="block text-sm font-semibold text-slate-900 mb-2">
                Dự án <span className="text-red-500">*</span>
              </label>
              <select
                value={projectId}
                onChange={(e) => handleProjectChange(e.target.value)}
                required
                className="w-full px-4 py-3 border border-slate-300 rounded-xl focus:outline-none focus:ring-2 focus:ring-teal-500 focus:border-transparent transition-all text-slate-900 bg-white text-sm font-medium"
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
                <p className="text-xs text-slate-500 mt-2">
                  Chủ đề: {selectedProject.topic}
                </p>
              )}
            </div>
          )}

          {/* 2 — Title */}
          <div>
            <label className="block text-sm font-semibold text-slate-900 mb-2">
              Tiêu đề báo cáo <span className="text-red-500">*</span>
            </label>
            <input
              type="text"
              required
              minLength={3}
              maxLength={500}
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="Ví dụ: Tổng quan nghiên cứu Vision Transformer 2024-2026"
              className="w-full px-4 py-3 border border-slate-300 rounded-xl focus:outline-none focus:ring-2 focus:ring-teal-500 focus:border-transparent transition-all text-slate-900 text-sm"
            />
          </div>

          {/* 3 — Report type */}
          <div>
            <label className="block text-sm font-semibold text-slate-900 mb-2 flex items-center gap-2">
              <Sparkles className="w-4 h-4 text-teal-600" />
              Loại báo cáo <span className="text-red-500">*</span>
            </label>
            <p className="text-xs text-slate-500 mb-4">
              Chọn mẫu phù hợp với mục đích trình bày
            </p>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
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
                        ? "border-teal-500 bg-teal-50"
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
                        <Icon className="w-4 h-4" />
                      </div>
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center justify-between gap-2 mb-1">
                          <span className="font-semibold text-slate-900 text-sm">
                            {type.label}
                          </span>
                          {active && (
                            <CheckCircle2 className="w-4 h-4 text-teal-600 flex-shrink-0" />
                          )}
                        </div>
                        <p className="text-xs text-slate-600 leading-snug mb-1.5">
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
          </div>

          {/* 4 — Document scope */}
          <div>
            <label className="block text-sm font-semibold text-slate-900 mb-2 flex items-center gap-2">
              <ClipboardList className="w-4 h-4 text-teal-600" />
              Phạm vi tài liệu
            </label>
            <p className="text-xs text-slate-500 mb-4">
              Quyết định những tài liệu nào sẽ được tổng hợp vào báo cáo
            </p>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
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
              <div className="border border-slate-200 rounded-xl bg-slate-50 overflow-hidden mt-3">
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
                <div className="max-h-72 overflow-y-auto no-scrollbar">
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
          </div>

          {/* Info hint box (mirrors StartAnalysisModal / CreateDocumentModal) */}
          <div className="bg-teal-50 border border-teal-200 rounded-xl p-5">
            <div className="flex items-start gap-3">
              <Sparkles className="w-5 h-5 text-teal-600 flex-shrink-0 mt-0.5" />
              <div className="text-sm text-teal-900">
                <p className="font-semibold mb-2">Báo cáo sẽ bao gồm:</p>
                <ul className="space-y-1.5 text-xs">
                  <li>· Trang bìa với tên dự án, loại báo cáo, ngày tạo</li>
                  <li>· Mục lục và tóm tắt tổng quan dự án</li>
                  <li>· Phát hiện nổi bật + từ khóa tổng hợp xuyên tài liệu</li>
                  <li>· Chi tiết từng tài liệu (đóng góp, phương pháp, giới hạn)</li>
                </ul>
                <p className="text-xs text-teal-700 mt-3 leading-snug">
                  Sau khi tạo, bạn có thể chạy{" "}
                  <strong>Synthesis</strong> để LLM viết lại narrative xuyên
                  tài liệu, hoặc <strong>QA</strong> để kiểm chất lượng.
                </p>
              </div>
            </div>
          </div>

          {/* Actions — inline at bottom of form, mirrors StartAnalysisModal */}
          <div className="flex items-center justify-end gap-3 pt-4 border-t border-slate-200">
            <button
              type="button"
              onClick={onClose}
              disabled={loading}
              className="px-6 py-3 border border-slate-200 rounded-xl text-slate-700 hover:bg-slate-50 font-semibold transition-colors disabled:opacity-50"
            >
              Hủy
            </button>
            <button
              type="submit"
              disabled={loading || !projectId || !title.trim()}
              className="flex items-center gap-2 px-6 py-3 bg-gradient-to-r from-teal-600 to-teal-700 hover:from-teal-700 hover:to-teal-800 disabled:opacity-60 disabled:cursor-not-allowed text-white rounded-xl font-semibold transition-all shadow-lg hover:shadow-xl disabled:shadow-none"
            >
              {loading ? (
                <>
                  <Loader className="w-5 h-5 animate-spin" />
                  <span>Đang tạo...</span>
                </>
              ) : (
                <>
                  <ClipboardList className="w-5 h-5" />
                  <span>Tạo báo cáo</span>
                </>
              )}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};

const ScopeOption = ({ active, onClick, title, description }) => (
  <button
    type="button"
    onClick={onClick}
    className={`text-left rounded-xl border-2 p-4 transition-all ${
      active
        ? "border-teal-500 bg-teal-50"
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
