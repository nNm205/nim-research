import { useState, useEffect, useMemo, useCallback } from "react";
import { useParams, useNavigate } from "react-router-dom";
import DashboardLayout from "../components/layout/DashboardLayout";
import { projectService } from "../services/projectService";
import { documentService } from "../services/documentService";
import { analysisService } from "../services/analysisService";
import { researchService } from "../services/researchService";
import CreateDocumentModal from "../components/documents/CreateDocumentModal";
import StartAnalysisModal from "../components/analysis/StartAnalysisModal";
import AutoResearchModal from "../components/projects/AutoResearchModal";
import TopicChipInput, { TopicChipList } from "../components/projects/TopicChipInput";
import AnalysisCard from "../components/analysis/AnalysisCard";
import AnalysisProgressInline from "../components/analysis/AnalysisProgressInline";
import ResearchProgressPanel from "../components/research/ResearchProgressPanel";
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
  BarChart3,
  ClipboardList,
  Search,
  Plus,
  Sparkles,
  Wand2,
  X,
} from "lucide-react";

const ProjectDetailsPage = () => {
  const { projectId } = useParams();
  const navigate = useNavigate();

  const [project, setProject] = useState(null);
  const [documents, setDocuments] = useState([]);
  const [analyses, setAnalyses] = useState([]);
  // Research sessions (search + auto-research). The active progress
  // panels are derived from this list — any session whose status is
  // pending or running is shown live with its tracker state.
  const [researchSessions, setResearchSessions] = useState([]);
  const [loading, setLoading] = useState(true);
  const [isEditing, setIsEditing] = useState(false);
  const [formData, setFormData] = useState(null);
  const [apiLoading, setApiLoading] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState({ type: "", text: "" });
  // Live draft for the topic chip editor in edit mode. Confirmed chips
  // are stored inside ``formData.topic`` as a comma-joined string.
  const [editTopicDraft, setEditTopicDraft] = useState("");

  const [showCreateDocModal, setShowCreateDocModal] = useState(false);
  const [showAnalyzeModal, setShowAnalyzeModal] = useState(false);
  const [showAutoResearchModal, setShowAutoResearchModal] = useState(false);

  // Reload all project-scoped data. Stable callback so it can be used
  // both by the initial-mount effect and by the AutoResearchModal
  // completion handler that polls a few seconds after launch to show
  // the first wave of ingested documents.
  const loadAll = useCallback(async () => {
    try {
      setLoading(true);
      const [data, docs, analysesData, sessions] = await Promise.all([
        projectService.getProject(projectId),
        documentService.getProjectDocuments(projectId),
        analysisService.getProjectAnalyses(projectId),
        researchService.getSessions(projectId).catch(() => []),
      ]);
      setProject(data);
      setDocuments(docs || []);
      setAnalyses(analysesData || []);
      setResearchSessions(sessions || []);
      setFormData({
        name: data.name,
        description: data.description || "",
        topic: data.topic || "",
        research_scope: data.research_scope || "",
        status: data.status,
      });
      setError("");
    } catch (err) {
      setError("Không thể tải thông tin dự án");
      console.error(err);
    } finally {
      setLoading(false);
    }
  }, [projectId]);

  // Defer the initial load to a microtask so React can flush its
  // mount-time effects without the lint plugin flagging
  // "setState during effect body" — loadAll itself updates state
  // asynchronously via Promise.all callbacks.
  useEffect(() => {
    let cancelled = false;
    Promise.resolve().then(() => {
      if (!cancelled) loadAll();
    });
    return () => {
      cancelled = true;
    };
  }, [loadAll]);

  // Active research sessions (pending / running) — these are what we
  // poll for live progress updates. Memo'd by id list so we don't
  // restart the poll on every re-render.
  const activeResearchIds = useMemo(
    () =>
      researchSessions
        .filter((s) => s.status === "pending" || s.status === "running")
        .map((s) => s.id),
    [researchSessions]
  );

  // Active analyses (pending / running) — same idea. We poll so the
  // top-level state knows when an analysis terminates and the
  // AnalysisProgressInline panel can be removed from the page.
  const activeAnalysisIds = useMemo(
    () =>
      analyses
        .filter((a) => a.status === "pending" || a.status === "running")
        .map((a) => a.id),
    [analyses]
  );

  // Poll progress for any active research session every 3 s. We hit
  // the same status endpoint the ResearchPage uses; the response
  // includes the full ``progress`` JSON.
  useEffect(() => {
    if (activeResearchIds.length === 0) return undefined;

    const tick = async () => {
      const updates = await Promise.all(
        activeResearchIds.map((id) =>
          researchService.getStatus(projectId, id).catch(() => null)
        )
      );

      let anyTerminal = false;
      // Detect whether at least one updated session is in auto mode and
      // currently in the analyse stage. If so we refresh documents +
      // analyses on every tick so newly-ingested docs and newly-spawned
      // analyses appear in the lower cards while the pipeline runs.
      let autoActive = false;
      setResearchSessions((prev) =>
        prev.map((s) => {
          const u = updates.find((x) => x && x.id === s.id);
          if (!u) return s;
          if (
            (u.status === "completed" || u.status === "failed") &&
            (s.status === "pending" || s.status === "running")
          ) {
            anyTerminal = true;
          }
          if (
            u.status === "running" &&
            u.progress?.mode === "auto" &&
            ["ingest", "analyse"].includes(u.progress?.current_stage)
          ) {
            autoActive = true;
          }
          return { ...s, ...u };
        })
      );
      if (anyTerminal || autoActive) {
        Promise.all([
          documentService.getProjectDocuments(projectId).catch(() => null),
          analysisService.getProjectAnalyses(projectId).catch(() => null),
        ]).then(([docs, an]) => {
          if (docs) setDocuments(docs);
          if (an) setAnalyses(an);
        });
      }
    };

    tick();
    const handle = setInterval(tick, 3000);
    return () => clearInterval(handle);
  }, [activeResearchIds, projectId]);

  // Poll any running standalone analyses. When one terminates we update
  // the local list so the inline progress panel disappears and the
  // analyses card list shows the final status.
  useEffect(() => {
    if (activeAnalysisIds.length === 0) return undefined;

    const tick = async () => {
      const updates = await Promise.all(
        activeAnalysisIds.map((id) =>
          analysisService
            .getAnalysisStatus(projectId, id)
            .catch(() => null),
        ),
      );

      let anyTerminal = false;
      setAnalyses((prev) =>
        prev.map((a) => {
          const u = updates.find((x) => x && x.id === a.id);
          if (!u) return a;
          if (
            (u.status === "completed" || u.status === "failed") &&
            (a.status === "pending" || a.status === "running")
          ) {
            anyTerminal = true;
          }
          // Merge — but the status endpoint doesn't include
          // ``document_title`` (it only has the ``document`` shim), so
          // we preserve the existing title we already had.
          return { ...a, status: u.status, error_message: u.error_message };
        }),
      );
      if (anyTerminal) {
        // Refresh the full list from the project endpoint to pick up
        // the completion timestamp + any other fields we don't poll.
        analysisService
          .getProjectAnalyses(projectId)
          .then((fresh) => setAnalyses(fresh || []))
          .catch(() => {});
      }
    };

    tick();
    const handle = setInterval(tick, 3000);
    return () => clearInterval(handle);
  }, [activeAnalysisIds, projectId]);

  const handleCreateDocument = async (documentDataOrDoc) => {
    if (documentDataOrDoc?.id) {
      setDocuments([documentDataOrDoc, ...documents]);
      setShowCreateDocModal(false);
      setMessage({ type: "success", text: "Đã thêm tài liệu thành công." });
      setTimeout(() => setMessage({ type: "", text: "" }), 3000);
      return;
    }
    
    const newDoc = await documentService.createDocument(
      projectId,
      documentDataOrDoc
    );
    setDocuments([newDoc, ...documents]);
    setShowCreateDocModal(false);
    setMessage({ type: "success", text: "Đã thêm tài liệu thành công." });
    setTimeout(() => setMessage({ type: "", text: "" }), 3000);
  };

  const handleStartAnalysis = async (documentId, llmProvider, llmModel) => {
    const result = await analysisService.startAnalysis(
      projectId,
      documentId,
      llmProvider,
      llmModel
    );
    setAnalyses([result, ...analyses]);
    setShowAnalyzeModal(false);
    setMessage({
      type: "success",
      text: "Đã bắt đầu phân tích. Mở thẻ để theo dõi tiến trình.",
    });
    setTimeout(() => setMessage({ type: "", text: "" }), 3000);
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setApiLoading(true);
    setError("");
    try {
      // If user typed a chip in the editor without confirming with Enter,
      // accept it on submit so the value isn't silently lost.
      let topicValue = formData.topic;
      if (editTopicDraft.trim()) {
        const existing = (formData.topic || "")
          .split(",")
          .map((t) => t.trim())
          .filter(Boolean);
        const draft = editTopicDraft.trim();
        if (
          !existing.some((t) => t.toLowerCase() === draft.toLowerCase())
        ) {
          existing.push(draft);
        }
        topicValue = existing.join(", ");
      }

      const updated = await projectService.updateProject(projectId, {
        ...formData,
        topic: topicValue,
      });
      setProject(updated);
      setFormData({
        name: updated.name,
        description: updated.description || "",
        topic: updated.topic || "",
        research_scope: updated.research_scope || "",
        status: updated.status,
      });
      setEditTopicDraft("");
      setIsEditing(false);
      setMessage({ type: "success", text: "Cập nhật dự án thành công!" });
      setTimeout(() => setMessage({ type: "", text: "" }), 3000);
    } catch (err) {
      setError(err.response?.data?.detail || "Không thể cập nhật dự án");
    } finally {
      setApiLoading(false);
    }
  };

  const handleChange = (e) =>
    setFormData({ ...formData, [e.target.name]: e.target.value });

  const handleArchive = async () => {
    setApiLoading(true);
    try {
      const updated = await projectService.updateProject(projectId, {
        is_archived: !project.is_archived,
      });
      setProject(updated);
      setMessage({
        type: "success",
        text: project.is_archived
          ? "Bỏ lưu trữ dự án thành công!"
          : "Lưu trữ dự án thành công!",
      });
      setTimeout(() => setMessage({ type: "", text: "" }), 3000);
    } catch (err) {
      setError(err.response?.data?.detail || "Không thể cập nhật trạng thái");
    } finally {
      setApiLoading(false);
    }
  };

  const handleDelete = async () => {
    if (
      !window.confirm(
        "Bạn có chắc muốn xóa dự án này? Hành động này không thể hoàn tác."
      )
    )
      return;
    setApiLoading(true);
    try {
      await projectService.deleteProject(projectId);
      navigate("/projects");
    } catch (err) {
      setError(err.response?.data?.detail || "Không thể xóa dự án");
    } finally {
      setApiLoading(false);
    }
  };

  const formatDate = (dateString) =>
    new Date(dateString).toLocaleString("vi-VN", {
      day: "2-digit",
      month: "2-digit",
      year: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });

  const statusOptions = [
    { value: "active", label: "Đang hoạt động" },
    { value: "completed", label: "Hoàn thành" },
    { value: "on_hold", label: "Tạm dừng" },
    { value: "cancelled", label: "Đã hủy" },
  ];

  const statusColors = {
    active:    { bg: "bg-emerald-50", text: "text-emerald-700" },
    completed: { bg: "bg-blue-50",    text: "text-blue-700" },
    on_hold:   { bg: "bg-amber-50",   text: "text-amber-700" },
    cancelled: { bg: "bg-red-50",     text: "text-red-700" },
  };

  const docHasAnalysis = useMemo(() => {
    const set = new Set(analyses.map((a) => a.document_id));
    return (docId) => set.has(docId);
  }, [analyses]);

  const stats = useMemo(
    () => ({
      docs: documents.length,
      analyses: analyses.length,
      processed: documents.filter((d) => d.processed).length,
      analysed: documents.filter((d) => docHasAnalysis(d.id)).length,
    }),
    [documents, analyses, docHasAnalysis]
  );

  if (loading) {
    return (
      <DashboardLayout>
        <div className="flex items-center justify-center h-96">
          <div className="text-center">
            <div className="w-12 h-12 border-4 border-teal-200 border-t-teal-600 rounded-full animate-spin mx-auto mb-4" />
            <p className="text-slate-600 font-medium">Đang tải dự án...</p>
          </div>
        </div>
      </DashboardLayout>
    );
  }

  if (!project) {
    return (
      <DashboardLayout>
        <div className="text-center py-16">
          <AlertCircle className="w-16 h-16 text-red-400 mx-auto mb-4" />
          <h2 className="text-2xl font-bold text-slate-900 mb-2">
            Không tìm thấy dự án
          </h2>
          <p className="text-slate-600 mb-8">
            Dự án bạn tìm không tồn tại hoặc đã bị xóa
          </p>
          <button
            onClick={() => navigate("/projects")}
            className="px-6 py-3 bg-gradient-to-r from-teal-600 to-teal-700 hover:from-teal-700 hover:to-teal-800 text-white rounded-xl font-semibold transition-all shadow-lg hover:shadow-xl"
          >
            Quay lại Dự án
          </button>
        </div>
      </DashboardLayout>
    );
  }

  const statusConfig = statusColors[project.status] || statusColors.active;

  return (
    <DashboardLayout>
      <div className="space-y-8">
        <div className="flex items-center gap-3 text-sm">
          <button
            onClick={() => navigate("/projects")}
            className="flex items-center gap-2 text-teal-600 hover:text-teal-700 font-semibold transition-colors group"
          >
            <ArrowLeft className="w-4 h-4 group-hover:-translate-x-1 transition-transform" />
            Dự án
          </button>
          <span className="text-slate-400">/</span>
          <span className="text-slate-900 font-semibold">{project.name}</span>
        </div>

        {error && (
          <div className="flex items-start gap-3 bg-red-50 border border-red-200 text-red-700 px-6 py-4 rounded-xl">
            <AlertCircle className="w-5 h-5 flex-shrink-0 mt-0.5" />
            <span className="text-sm font-medium flex-1">{error}</span>
            <button
              onClick={() => setError("")}
              className="text-red-500 hover:text-red-700"
              aria-label="Đóng"
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

        {!isEditing ? (
          <div className="space-y-8">
            <div className="flex items-start justify-between gap-4">
              <div className="flex-1 min-w-0">
                <h1 className="text-4xl font-bold text-slate-900 mb-3">
                  {project.name}
                </h1>
                {project.topic && (
                  <TopicChipList
                    topics={project.topic
                      .split(",")
                      .map((t) => t.trim())
                      .filter(Boolean)}
                  />
                )}
              </div>
              {project.is_archived && (
                <span className="flex-shrink-0 bg-slate-100 text-slate-600 text-xs px-3 py-1 rounded-lg font-medium">
                  📦 Đã lưu trữ
                </span>
              )}
            </div>

            <div className="flex flex-wrap items-center gap-3">
              <button
                onClick={() => setShowAutoResearchModal(true)}
                disabled={project.is_archived}
                title="Tự động tìm tài liệu, thêm vào dự án và phân tích trong 1 lần"
                className="inline-flex items-center gap-2 px-5 py-3 bg-gradient-to-r from-violet-600 to-fuchsia-600 hover:from-violet-700 hover:to-fuchsia-700 disabled:opacity-50 disabled:cursor-not-allowed text-white rounded-xl font-semibold transition-all shadow-lg hover:shadow-xl"
              >
                <Wand2 className="w-5 h-5" />
                Nghiên cứu tự động
              </button>

              <button
                onClick={() => setShowCreateDocModal(true)}
                disabled={project.is_archived}
                className="inline-flex items-center gap-2 px-5 py-3 bg-gradient-to-r from-teal-600 to-teal-700 hover:from-teal-700 hover:to-teal-800 disabled:opacity-50 disabled:cursor-not-allowed text-white rounded-xl font-semibold transition-all shadow-lg hover:shadow-xl"
              >
                <Plus className="w-5 h-5" />
                Thêm tài liệu
              </button>

              <button
                onClick={() => setShowAnalyzeModal(true)}
                disabled={project.is_archived || documents.length === 0}
                title={
                  documents.length === 0
                    ? "Thêm tài liệu trước khi phân tích"
                    : "Mở dialog phân tích"
                }
                className="inline-flex items-center gap-2 px-5 py-3 bg-white border border-violet-200 text-violet-700 hover:bg-violet-50 hover:border-violet-300 disabled:opacity-50 disabled:cursor-not-allowed rounded-xl font-semibold transition-all shadow-sm"
              >
                <Sparkles className="w-5 h-5" />
                Phân tích tài liệu
              </button>

              <button
                onClick={() => navigate(`/projects/${projectId}/research`)}
                className="inline-flex items-center gap-2 px-5 py-3 bg-white border border-slate-200 text-slate-700 hover:bg-slate-50 hover:border-slate-300 rounded-xl font-semibold transition-all shadow-sm"
              >
                <Search className="w-5 h-5" />
                Tìm kiếm tài liệu
              </button>
            </div>

            {/* Live progress for any active research / auto-research
                session — top-of-page placement so the user sees pipeline
                state immediately after launching from the action bar. */}
            {researchSessions
              .filter(
                (s) => s.status === "pending" || s.status === "running"
              )
              .map((sess) => (
                <ResearchProgressPanel
                  key={sess.id}
                  status={sess.status}
                  progress={sess.progress}
                  errorMessage={sess.error_message}
                  query={sess.query}
                  projectId={projectId}
                />
              ))}

            {/* Live progress for standalone analyses (kicked off via
                "Phân tích tài liệu", not auto-research). We skip
                analyses that are already shown nested inside a running
                auto-research panel to avoid duplicating the same
                progress in two places. */}
            {(() => {
              const nestedIds = new Set(
                researchSessions
                  .filter(
                    (s) =>
                      s.status === "running" &&
                      s.progress?.item_progress?.current_analysis_id
                  )
                  .map((s) =>
                    String(s.progress.item_progress.current_analysis_id)
                  )
              );
              return analyses
                .filter(
                  (a) =>
                    (a.status === "pending" || a.status === "running") &&
                    !nestedIds.has(String(a.id))
                )
                .map((a) => (
                  <AnalysisProgressInline
                    key={a.id}
                    projectId={projectId}
                    analysisId={a.id}
                    documentTitle={a.document_title}
                  />
                ));
            })()}

            {/* Surface recently-failed sessions briefly too — the user
                may have been on another tab when the error happened and
                will appreciate seeing it without having to dig into the
                research history. We only render the most recent failed
                session to keep the page tidy. */}
            {(() => {
              const lastFailed = researchSessions.find(
                (s) => s.status === "failed"
              );
              if (!lastFailed) return null;
              // Hide the panel once the user has launched a fresh
              // session that has progressed past pending.
              const hasNewer = researchSessions.some(
                (s) =>
                  s.status === "running" || s.status === "completed"
              );
              if (hasNewer) return null;
              return (
                <ResearchProgressPanel
                  key={lastFailed.id}
                  status={lastFailed.status}
                  progress={lastFailed.progress}
                  errorMessage={lastFailed.error_message}
                  query={lastFailed.query}
                  projectId={projectId}
                />
              );
            })()}

            <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
              <div className="lg:col-span-2 space-y-8">
                {project.description && (
                  <Panel title="Mô tả">
                    <p className="text-slate-700 whitespace-pre-wrap leading-relaxed">
                      {project.description}
                    </p>
                  </Panel>
                )}

                {project.research_scope && (
                  <Panel title="Phạm vi nghiên cứu">
                    <p className="text-slate-700 whitespace-pre-wrap leading-relaxed">
                      {project.research_scope}
                    </p>
                  </Panel>
                )}

                <div className="grid grid-cols-4 gap-4 bg-white rounded-2xl border border-slate-200 p-6 shadow-sm">
                  <StatItem icon={FileText}      value={stats.docs}      label="Tài liệu" />
                  <StatItem icon={CheckCircle2}  value={stats.processed} label="Đã xử lý" />
                  <StatItem icon={BarChart3}     value={stats.analyses}  label="Phân tích" />
                  <StatItem icon={ClipboardList} value={project.report_count ?? 0} label="Báo cáo" />
                </div>

                <Panel
                  id="documents"
                  title={`Tài liệu (${documents.length})`}
                  action={
                    documents.length > 0 && (
                      <button
                        onClick={() =>
                          navigate(`/documents`)
                        }
                        className="text-sm text-teal-600 hover:text-teal-700 font-semibold transition-colors"
                      >
                        Tất cả tài liệu →
                      </button>
                    )
                  }
                >
                  {documents.length === 0 ? (
                    <div className="text-center py-10">
                      <FileText className="w-10 h-10 text-slate-300 mx-auto mb-3" />
                      <p className="text-slate-500 font-medium mb-4">
                        Chưa có tài liệu nào trong dự án này
                      </p>
                      <button
                        onClick={() => setShowCreateDocModal(true)}
                        disabled={project.is_archived}
                        className="inline-flex items-center gap-2 px-5 py-2.5 bg-gradient-to-r from-teal-600 to-teal-700 hover:from-teal-700 hover:to-teal-800 disabled:opacity-50 text-white rounded-xl font-semibold transition-all shadow-md"
                      >
                        <Plus className="w-4 h-4" />
                        Thêm tài liệu đầu tiên
                      </button>
                    </div>
                  ) : (
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                      {documents.slice(0, 6).map((doc) => (
                        <DocumentRowCompact
                          key={doc.id}
                          doc={doc}
                          hasAnalysis={docHasAnalysis(doc.id)}
                          onClick={() =>
                            navigate(
                              `/projects/${projectId}/documents/${doc.id}`
                            )
                          }
                        />
                      ))}
                      {documents.length > 6 && (
                        <button
                          onClick={() =>
                            navigate(`/projects/${projectId}/documents`)
                          }
                          className="md:col-span-2 w-full py-3 text-sm text-teal-600 hover:text-teal-700 font-semibold transition-colors border border-dashed border-slate-200 rounded-xl hover:border-teal-300"
                        >
                          Xem thêm {documents.length - 6} tài liệu
                        </button>
                      )}
                    </div>
                  )}
                </Panel>

                <Panel
                  id="analyses"
                  title={`Phân tích (${analyses.length})`}
                  action={
                    analyses.length > 0 && (
                      <button
                        onClick={() => navigate(`/analysis`)}
                        className="text-sm text-teal-600 hover:text-teal-700 font-semibold transition-colors"
                      >
                        Tất cả phân tích →
                      </button>
                    )
                  }
                >
                  {analyses.length === 0 ? (
                    <div className="text-center py-10">
                      <BarChart3 className="w-10 h-10 text-slate-300 mx-auto mb-3" />
                      <p className="text-slate-500 font-medium mb-4">
                        {documents.length === 0
                          ? "Thêm tài liệu trước khi phân tích"
                          : "Chưa có phân tích nào cho dự án này"}
                      </p>
                      {documents.length > 0 && (
                        <button
                          onClick={() => setShowAnalyzeModal(true)}
                          disabled={project.is_archived}
                          className="inline-flex items-center gap-2 px-5 py-2.5 bg-white border border-violet-200 text-violet-700 hover:bg-violet-50 disabled:opacity-50 rounded-xl font-semibold transition-all shadow-sm"
                        >
                          <Sparkles className="w-4 h-4" />
                          Bắt đầu phân tích đầu tiên
                        </button>
                      )}
                    </div>
                  ) : (
                    <div className="space-y-3">
                      {analyses.slice(0, 5).map((a) => (
                        <AnalysisCard
                          key={a.id}
                          analysis={a}
                          onClick={() => navigate(`/analysis/${a.id}`)}
                        />
                      ))}
                      {analyses.length > 5 && (
                        <button
                          onClick={() => navigate(`/analysis`)}
                          className="w-full py-3 text-sm text-teal-600 hover:text-teal-700 font-semibold transition-colors border border-dashed border-slate-200 rounded-xl hover:border-teal-300"
                        >
                          Xem thêm {analyses.length - 5} phân tích
                        </button>
                      )}
                    </div>
                  )}
                </Panel>
              </div>

              <div className="space-y-6">
                <Panel title="Thông tin">
                  <div className="space-y-4">
                    <div>
                      <p className="text-xs font-semibold text-slate-600 mb-2">
                        Trạng thái
                      </p>
                      <span
                        className={`inline-block text-sm font-bold px-4 py-2 rounded-lg ${statusConfig.bg} ${statusConfig.text}`}
                      >
                        {statusOptions.find((s) => s.value === project.status)?.label}
                      </span>
                    </div>
                    <div className="border-t border-slate-200 pt-4">
                      <p className="text-xs font-semibold text-slate-600 mb-2 flex items-center gap-2">
                        <Calendar className="w-4 h-4" />
                        Ngày tạo
                      </p>
                      <p className="text-sm text-slate-700 font-medium">
                        {formatDate(project.created_at)}
                      </p>
                    </div>
                    <div className="border-t border-slate-200 pt-4">
                      <p className="text-xs font-semibold text-slate-600 mb-2 flex items-center gap-2">
                        <CheckCircle2 className="w-4 h-4" />
                        Cập nhật lần cuối
                      </p>
                      <p className="text-sm text-slate-700 font-medium">
                        {formatDate(project.updated_at)}
                      </p>
                    </div>
                  </div>
                </Panel>

                <Panel title="Quản lý">
                  <div className="space-y-3">
                    <button
                      onClick={() => setIsEditing(true)}
                      className="w-full flex items-center justify-center gap-2 px-6 py-3 border border-slate-200 rounded-xl text-slate-700 hover:bg-slate-50 font-semibold transition-colors"
                    >
                      <Edit2 className="w-4 h-4" />
                      Chỉnh sửa
                    </button>
                    <button
                      onClick={handleArchive}
                      disabled={apiLoading}
                      className="w-full flex items-center justify-center gap-2 px-6 py-3 border border-slate-200 rounded-xl text-slate-700 hover:bg-slate-50 font-semibold transition-colors disabled:opacity-50"
                    >
                      {project.is_archived ? (
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
                      onClick={handleDelete}
                      disabled={apiLoading}
                      className="w-full flex items-center justify-center gap-2 px-6 py-3 border border-red-300 text-red-600 hover:bg-red-50 font-semibold transition-colors rounded-xl disabled:opacity-50"
                    >
                      <Trash2 className="w-4 h-4" />
                      Xóa dự án
                    </button>
                  </div>
                </Panel>
              </div>
            </div>
          </div>
        ) : (
          <Panel title="Chỉnh sửa dự án">
            <form onSubmit={handleSubmit} className="space-y-6">
              <div>
                <label className="block text-sm font-semibold text-slate-900 mb-2">
                  Tên dự án <span className="text-red-500">*</span>
                </label>
                <input
                  type="text"
                  name="name"
                  required
                  minLength={3}
                  maxLength={255}
                  value={formData.name}
                  onChange={handleChange}
                  className="w-full px-4 py-3 border border-slate-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-teal-500 focus:ring-offset-2 focus:border-transparent transition-all"
                />
              </div>
              <div>
                <label className="block text-sm font-semibold text-slate-900 mb-2">
                  Chủ đề
                </label>
                <TopicChipInput
                  topics={(formData.topic || "")
                    .split(",")
                    .map((t) => t.trim())
                    .filter(Boolean)}
                  draft={editTopicDraft}
                  onTopicsChange={(arr) =>
                    setFormData({ ...formData, topic: arr.join(", ") })
                  }
                  onDraftChange={setEditTopicDraft}
                />
              </div>
              <div>
                <label className="block text-sm font-semibold text-slate-900 mb-2">
                  Trạng thái
                </label>
                <select
                  name="status"
                  value={formData.status}
                  onChange={handleChange}
                  className="w-full px-4 py-3 border border-slate-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-teal-500 focus:ring-offset-2 focus:border-transparent transition-all"
                >
                  {statusOptions.map((o) => (
                    <option key={o.value} value={o.value}>
                      {o.label}
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block text-sm font-semibold text-slate-900 mb-2">
                  Mô tả
                </label>
                <textarea
                  name="description"
                  rows={5}
                  value={formData.description}
                  onChange={handleChange}
                  className="w-full px-4 py-3 border border-slate-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-teal-500 focus:ring-offset-2 focus:border-transparent transition-all resize-none"
                />
              </div>
              <div>
                <label className="block text-sm font-semibold text-slate-900 mb-2">
                  Phạm vi nghiên cứu
                </label>
                <textarea
                  name="research_scope"
                  rows={5}
                  value={formData.research_scope}
                  onChange={handleChange}
                  className="w-full px-4 py-3 border border-slate-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-teal-500 focus:ring-offset-2 focus:border-transparent transition-all resize-none"
                />
              </div>
              <div className="flex items-center justify-end gap-3 pt-6 border-t border-slate-200">
                <button
                  type="button"
                  onClick={() => setIsEditing(false)}
                  className="px-6 py-3 border border-slate-200 rounded-xl text-slate-700 hover:bg-slate-50 font-semibold transition-colors"
                >
                  Hủy
                </button>
                <button
                  type="submit"
                  disabled={apiLoading}
                  className="px-6 py-3 bg-gradient-to-r from-teal-600 to-teal-700 hover:from-teal-700 hover:to-teal-800 disabled:opacity-60 text-white rounded-xl font-semibold transition-all shadow-lg hover:shadow-xl"
                >
                  {apiLoading ? "Đang lưu..." : "Lưu thay đổi"}
                </button>
              </div>
            </form>
          </Panel>
        )}
      </div>

      {showCreateDocModal && (
        <CreateDocumentModal
          projectId={projectId}
          onClose={() => setShowCreateDocModal(false)}
          onCreate={handleCreateDocument}
        />
      )}

      {showAnalyzeModal && (
        <StartAnalysisModal
          documents={documents}
          onClose={() => setShowAnalyzeModal(false)}
          onStart={handleStartAnalysis}
        />
      )}

      {showAutoResearchModal && (
        <AutoResearchModal
          projectId={projectId}
          onClose={() => setShowAutoResearchModal(false)}
          onLaunched={(session) => {
            // Inject the new session into the running list so the
            // progress panel shows immediately. The polling loop
            // already started above will pick up its progress on the
            // very next tick.
            if (session) {
              setResearchSessions((prev) => [session, ...prev]);
            }
            setMessage({
              type: "success",
              text:
                "Nghiên cứu tự động đã khởi động. Theo dõi tiến trình " +
                "ngay phía trên — tài liệu và phân tích sẽ xuất hiện dần.",
            });
            setTimeout(() => setMessage({ type: "", text: "" }), 6000);
          }}
        />
      )}
    </DashboardLayout>
  );
};

const Panel = ({ title, children, action, id }) => (
  <section
    id={id}
    className="bg-white rounded-2xl border border-slate-200 p-6 md:p-8 shadow-sm"
  >
    <div className="flex items-center justify-between mb-5">
      <h2 className="text-lg md:text-xl font-bold text-slate-900 flex items-center gap-2">
        <span className="w-1 h-5 rounded-full bg-teal-600" />
        {title}
      </h2>
      {action}
    </div>
    {children}
  </section>
);

const StatItem = ({ icon: Icon, value, label }) => (
  <div className="text-center p-3 bg-slate-50 rounded-lg border border-slate-200">
    <Icon className="w-5 h-5 text-teal-600 mx-auto mb-2" />
    <div className="text-2xl font-bold text-slate-900 mb-0.5">{value}</div>
    <div className="text-xs font-medium text-slate-600">{label}</div>
  </div>
);

const DocumentRowCompact = ({ doc, hasAnalysis, onClick }) => {
  const sourceTypeColors = {
    pdf:      "text-rose-600 bg-rose-50 border-rose-200",
    web:      "text-blue-600 bg-blue-50 border-blue-200",
    academic: "text-violet-600 bg-violet-50 border-violet-200",
    uploaded: "text-amber-600 bg-amber-50 border-amber-200",
  };
  const colorClass = sourceTypeColors[doc.source_type] || sourceTypeColors.uploaded;

  return (
    <div
      onClick={onClick}
      className="flex items-center gap-3 p-3 rounded-xl border border-slate-200 hover:border-teal-300 hover:bg-teal-50/30 cursor-pointer transition-all group"
    >
      <div className={`flex-shrink-0 p-2 rounded-lg border ${colorClass}`}>
        <FileText className="w-4 h-4" />
      </div>
      <div className="flex-1 min-w-0">
        <p className="text-sm font-semibold text-slate-900 truncate group-hover:text-teal-700 transition-colors">
          {doc.title}
        </p>
        <div className="flex items-center gap-2 mt-0.5 flex-wrap">
          {doc.processed && (
            <span className="text-[10px] uppercase tracking-wide font-bold text-emerald-600 flex items-center gap-1">
              <CheckCircle2 className="w-3 h-3" />
              Đã xử lý
            </span>
          )}
          {hasAnalysis && (
            <span className="text-[10px] uppercase tracking-wide font-bold text-violet-600 flex items-center gap-1">
              <Sparkles className="w-3 h-3" />
              Đã phân tích
            </span>
          )}
        </div>
      </div>
    </div>
  );
};

export default ProjectDetailsPage;
