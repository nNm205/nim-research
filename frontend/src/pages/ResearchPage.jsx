import { useState, useEffect, useRef, useCallback } from "react";
import { useParams, useNavigate } from "react-router-dom";
import DashboardLayout from "../components/layout/DashboardLayout";
import { researchService } from "../services/researchService";
import { projectService } from "../services/projectService";
import IngestSearchResultModal from "../components/research/IngestSearchResultModal";
import {
  ArrowLeft,
  Search,
  Loader2,
  CheckCircle2,
  AlertCircle,
  Clock,
  ExternalLink,
  BookOpen,
  Globe,
  GraduationCap,
  ChevronRight,
  FolderPlus,
  History,
  RefreshCw,
} from "lucide-react";

// ─── Constants ────────────────────────────────────────────────────────────────

const SOURCE_LABELS = {
  arxiv:            { label: "arXiv",            icon: BookOpen,     color: "text-red-600 bg-red-50 border-red-200" },
  google_scholar:   { label: "Google Scholar",   icon: GraduationCap, color: "text-blue-600 bg-blue-50 border-blue-200" },
  semantic_scholar: { label: "Semantic Scholar", icon: GraduationCap, color: "text-purple-600 bg-purple-50 border-purple-200" },
  web:              { label: "Web",              icon: Globe,         color: "text-teal-600 bg-teal-50 border-teal-200" },
};

const STATUS_CONFIG = {
  pending:   { label: "Đang chờ",      color: "text-amber-600 bg-amber-50 border-amber-200",   icon: Clock },
  running:   { label: "Đang tìm kiếm", color: "text-blue-600 bg-blue-50 border-blue-200",      icon: Loader2 },
  completed: { label: "Hoàn thành",    color: "text-emerald-600 bg-emerald-50 border-emerald-200", icon: CheckCircle2 },
  failed:    { label: "Thất bại",      color: "text-red-600 bg-red-50 border-red-200",          icon: AlertCircle },
};

const POLL_INTERVAL_MS = 2500;

// ─── Main Page ────────────────────────────────────────────────────────────────

const ResearchPage = () => {
  const { projectId } = useParams();
  const navigate = useNavigate();

  // Page state
  const [project, setProject]       = useState(null);
  const [pageLoading, setPageLoading] = useState(true);
  const [pageError, setPageError]   = useState("");

  // History sidebar
  const [sessions, setSessions]         = useState([]);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [activeSessionId, setActiveSessionId] = useState(null);

  // Current search
  const [query, setQuery]         = useState("");
  const [maxResults, setMaxResults] = useState(10);
  const [session, setSession]     = useState(null);
  const [results, setResults]     = useState([]);
  const [status, setStatus]       = useState(null);
  const [loading, setLoading]     = useState(false);
  const [searchError, setSearchError] = useState("");
  const [addedResultIds, setAddedResultIds] = useState(new Set());

  const pollRef = useRef(null);

  // ── Load project + history on mount
  useEffect(() => {
    const init = async () => {
      try {
        const [proj, hist] = await Promise.all([
          projectService.getProject(projectId),
          researchService.getSessions(projectId),
        ]);
        setProject(proj);
        setSessions(hist || []);
      } catch {
        setPageError("Không thể tải thông tin dự án");
      } finally {
        setPageLoading(false);
      }
    };
    init();
    return () => clearInterval(pollRef.current);
  }, [projectId]);

  // ── Refresh history list
  const refreshHistory = useCallback(async () => {
    setHistoryLoading(true);
    try {
      const hist = await researchService.getSessions(projectId);
      setSessions(hist || []);
    } catch {
      // silent
    } finally {
      setHistoryLoading(false);
    }
  }, [projectId]);

  // ── Load a past session's results
  const loadSession = async (sess) => {
    clearInterval(pollRef.current);
    setActiveSessionId(sess.id);
    setSession(sess);
    setStatus(sess.status);
    setResults([]);
    setSearchError("");
    setAddedResultIds(new Set());
    setQuery(sess.query);

    if (sess.status === "completed") {
      try {
        const data = await researchService.getResults(sess.id);
        setResults(data.results || []);
      } catch {
        setSearchError("Không thể tải kết quả phiên này");
      }
    } else if (sess.status === "pending" || sess.status === "running") {
      startPolling(sess.id);
    } else if (sess.status === "failed") {
      setSearchError(sess.error_message || "Phiên tìm kiếm thất bại");
    }
  };

  // ── Polling
  const startPolling = (taskId) => {
    clearInterval(pollRef.current);
    pollRef.current = setInterval(async () => {
      try {
        const statusData = await researchService.getStatus(projectId, taskId);
        setStatus(statusData.status);
        setSession((prev) => ({ ...prev, ...statusData }));

        // Update status in sidebar too
        setSessions((prev) =>
          prev.map((s) => (s.id === taskId ? { ...s, ...statusData } : s))
        );

        if (statusData.status === "completed") {
          clearInterval(pollRef.current);
          const resultData = await researchService.getResults(taskId);
          setResults(resultData.results || []);
        } else if (statusData.status === "failed") {
          clearInterval(pollRef.current);
          setSearchError(statusData.error_message || "Tìm kiếm thất bại");
        }
      } catch {
        clearInterval(pollRef.current);
        setSearchError("Mất kết nối khi theo dõi tiến trình");
      }
    }, POLL_INTERVAL_MS);
  };

  // ── Start new search
  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!query.trim()) return;

    clearInterval(pollRef.current);
    setLoading(true);
    setSearchError("");
    setResults([]);
    setSession(null);
    setStatus(null);
    setActiveSessionId(null);
    setAddedResultIds(new Set());

    try {
      const newSession = await researchService.startResearch(
        projectId,
        query.trim(),
        maxResults
      );
      setSession(newSession);
      setStatus(newSession.status);
      setActiveSessionId(newSession.id);

      // Prepend to sidebar immediately
      setSessions((prev) => [newSession, ...prev]);

      startPolling(newSession.id);
    } catch (err) {
      setSearchError(err.response?.data?.detail || "Không thể bắt đầu tìm kiếm");
    } finally {
      setLoading(false);
    }
  };

  // ─────────────────────────────────────────────────────────────────────────────

  if (pageLoading) {
    return (
      <DashboardLayout>
        <div className="flex items-center justify-center h-96">
          <div className="text-center">
            <div className="w-12 h-12 border-4 border-teal-200 border-t-teal-600 rounded-full animate-spin mx-auto mb-4" />
            <p className="text-slate-600 font-medium">Đang tải...</p>
          </div>
        </div>
      </DashboardLayout>
    );
  }

  const statusCfg = status ? STATUS_CONFIG[status] : null;
  const StatusIcon = statusCfg?.icon;
  const isRunning = status === "pending" || status === "running";

  return (
    <DashboardLayout>
      <div className="space-y-6">
        {/* Breadcrumb */}
        <div className="flex items-center gap-3 text-sm">
          <button
            onClick={() => navigate("/projects")}
            className="flex items-center gap-2 text-teal-600 hover:text-teal-700 font-semibold transition-colors group"
          >
            <ArrowLeft className="w-4 h-4 group-hover:-translate-x-1 transition-transform" />
            Dự án
          </button>
          <span className="text-slate-400">/</span>
          <button
            onClick={() => navigate(`/projects/${projectId}`)}
            className="text-teal-600 hover:text-teal-700 font-semibold transition-colors"
          >
            {project?.name || "..."}
          </button>
          <span className="text-slate-400">/</span>
          <span className="text-slate-900 font-semibold">Tìm kiếm</span>
        </div>

        {pageError && (
          <div className="flex items-center gap-3 bg-red-50 border border-red-200 text-red-700 px-5 py-3 rounded-xl text-sm font-medium">
            <AlertCircle className="w-4 h-4 flex-shrink-0" />
            {pageError}
          </div>
        )}

        {/* ── 2-column layout ── */}
        <div className="flex gap-6 items-start">

          {/* ── LEFT: History Sidebar ── */}
          <aside className="w-72 flex-shrink-0 bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden">
            {/* Sidebar header */}
            <div className="flex items-center justify-between px-5 py-4 border-b border-slate-200">
              <div className="flex items-center gap-2">
                <History className="w-4 h-4 text-slate-500" />
                <span className="text-sm font-bold text-slate-900">Lịch sử tìm kiếm</span>
              </div>
              <button
                onClick={refreshHistory}
                disabled={historyLoading}
                className="text-slate-400 hover:text-teal-600 transition-colors disabled:opacity-50"
                title="Làm mới"
              >
                <RefreshCw className={`w-3.5 h-3.5 ${historyLoading ? "animate-spin" : ""}`} />
              </button>
            </div>

            {/* Session list */}
            <div className="overflow-y-auto max-h-[calc(100vh-280px)]">
              {sessions.length === 0 ? (
                <div className="text-center py-10 px-4">
                  <Search className="w-8 h-8 text-slate-300 mx-auto mb-2" />
                  <p className="text-slate-400 text-xs">Chưa có phiên tìm kiếm nào</p>
                </div>
              ) : (
                <div className="divide-y divide-slate-100">
                  {sessions.map((sess) => (
                    <SessionItem
                      key={sess.id}
                      sess={sess}
                      isActive={activeSessionId === sess.id}
                      onClick={() => loadSession(sess)}
                    />
                  ))}
                </div>
              )}
            </div>
          </aside>

          {/* ── RIGHT: Main Area ── */}
          <div className="flex-1 min-w-0 space-y-6">
            {/* Header */}
            <div>
              <h1 className="text-2xl font-bold text-slate-900 mb-1">Tìm kiếm tài liệu</h1>
              <p className="text-slate-500 text-sm">
                Tìm kiếm đồng thời trên arXiv, Google Scholar, Semantic Scholar và Web
              </p>
            </div>

            {/* Search Form */}
            <div className="bg-white rounded-2xl border border-slate-200 p-6 shadow-sm">
              <form onSubmit={handleSubmit} className="space-y-4">
                <div>
                  <label className="block text-sm font-semibold text-slate-900 mb-2">
                    Câu truy vấn <span className="text-red-500">*</span>
                  </label>
                  <textarea
                    rows={2}
                    value={query}
                    onChange={(e) => setQuery(e.target.value)}
                    placeholder="Ví dụ: transformer architecture for natural language processing"
                    disabled={isRunning}
                    className="w-full px-4 py-3 border border-slate-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-teal-500 focus:border-transparent transition-all resize-none disabled:bg-slate-50 disabled:text-slate-400 text-sm"
                  />
                </div>

                <div className="flex items-center gap-4">
                  <div>
                    <label className="block text-xs font-semibold text-slate-700 mb-1.5">
                      Số kết quả
                    </label>
                    <select
                      value={maxResults}
                      onChange={(e) => setMaxResults(Number(e.target.value))}
                      disabled={isRunning}
                      className="px-3 py-2 text-sm border border-slate-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-teal-500 focus:border-transparent transition-all disabled:bg-slate-50"
                    >
                      {[5, 10, 20, 30, 50].map((n) => (
                        <option key={n} value={n}>{n} kết quả</option>
                      ))}
                    </select>
                  </div>

                  <div className="flex-1 flex justify-end">
                    <button
                      type="submit"
                      disabled={loading || isRunning || !query.trim()}
                      className="flex items-center gap-2 px-6 py-2.5 bg-gradient-to-r from-teal-600 to-teal-700 hover:from-teal-700 hover:to-teal-800 disabled:opacity-60 text-white rounded-xl font-semibold text-sm transition-all shadow-md hover:shadow-lg"
                    >
                      {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Search className="w-4 h-4" />}
                      {loading ? "Đang khởi động..." : "Tìm kiếm mới"}
                    </button>
                  </div>
                </div>
              </form>
            </div>

            {/* Search error */}
            {searchError && (
              <div className="flex items-start gap-3 bg-red-50 border border-red-200 text-red-700 px-5 py-3 rounded-xl text-sm font-medium">
                <AlertCircle className="w-4 h-4 flex-shrink-0 mt-0.5" />
                {searchError}
              </div>
            )}

            {/* Compact status pill — replaces the full progress panel
                that used to live here. The unified live-progress view
                now lives on the ProjectDetailPage so the user has a
                single place to watch all running pipelines. Here we
                only show a small status indicator so the page is not
                empty while a session is in flight. */}
            {statusCfg && status !== "failed" && (
              <div
                className={`flex items-center gap-3 px-5 py-3 rounded-xl border text-sm ${statusCfg.color}`}
              >
                <StatusIcon
                  className={`w-4 h-4 flex-shrink-0 ${
                    status === "running" || status === "pending"
                      ? "animate-spin"
                      : ""
                  }`}
                />
                <div className="flex-1">
                  <span className="font-semibold">{statusCfg.label}</span>
                  {session?.query && (
                    <span className="ml-2 opacity-75">
                      — "{session.query}"
                    </span>
                  )}
                </div>
                {status === "completed" && (
                  <span className="font-semibold">
                    {results.length} kết quả
                  </span>
                )}
                {(status === "running" || status === "pending") && (
                  <a
                    href={`/projects/${projectId}`}
                    className="text-xs font-semibold underline hover:opacity-80"
                  >
                    Xem tiến trình →
                  </a>
                )}
              </div>
            )}

            {/* Failed sessions still show their error inline so the user
                can see what went wrong without leaving the page. */}
            {status === "failed" && (
              <div className="flex items-start gap-3 bg-red-50 border border-red-200 text-red-700 px-5 py-3 rounded-xl text-sm font-medium">
                <AlertCircle className="w-4 h-4 flex-shrink-0 mt-0.5" />
                <div className="flex-1">
                  <p className="font-semibold mb-1">Phiên tìm kiếm thất bại</p>
                  {session?.error_message && (
                    <p className="text-xs text-red-600 break-words">
                      {session.error_message}
                    </p>
                  )}
                </div>
              </div>
            )}

            {/* Results */}
            {results.length > 0 && (
              <div className="space-y-3">
                <h2 className="text-base font-bold text-slate-900">
                  Kết quả
                  <span className="ml-2 font-normal text-slate-400">({results.length} tài liệu)</span>
                </h2>
                {results.map((result, idx) => (
                  <ResultCard
                    key={result.id || idx}
                    result={result}
                    projectId={projectId}
                    isAdded={addedResultIds.has(result.id || idx)}
                    onAdded={() =>
                      setAddedResultIds((prev) => new Set([...prev, result.id || idx]))
                    }
                  />
                ))}
              </div>
            )}

            {/* Empty state */}
            {status === "completed" && results.length === 0 && (
              <div className="text-center py-14 bg-white rounded-2xl border border-slate-200">
                <Search className="w-10 h-10 text-slate-300 mx-auto mb-3" />
                <p className="text-slate-600 font-medium">Không tìm thấy kết quả nào</p>
                <p className="text-slate-400 text-sm mt-1">Thử thay đổi câu truy vấn</p>
              </div>
            )}

            {/* Idle state — no session selected yet */}
            {!session && !loading && (
              <div className="text-center py-14 bg-white rounded-2xl border border-dashed border-slate-200">
                <Search className="w-10 h-10 text-slate-300 mx-auto mb-3" />
                <p className="text-slate-500 font-medium">Nhập câu truy vấn để bắt đầu tìm kiếm</p>
                <p className="text-slate-400 text-sm mt-1">
                  Hoặc chọn một phiên cũ từ lịch sử bên trái
                </p>
              </div>
            )}
          </div>
        </div>
      </div>
    </DashboardLayout>
  );
};

// ─── Session Item (sidebar) ───────────────────────────────────────────────────

// React's purity lint flags `Date.now()` inside render. Pre-compute on
// module init; the list is short enough that "as of page load" precision
// is fine.
const _PAGE_LOAD_MS = Date.now();

const formatTimeAgo = (dateStr) => {
  const diff = _PAGE_LOAD_MS - new Date(dateStr).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return "vừa xong";
  if (mins < 60) return `${mins} phút trước`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs} giờ trước`;
  return `${Math.floor(hrs / 24)} ngày trước`;
};

const SessionItem = ({ sess, isActive, onClick }) => {
  const cfg = STATUS_CONFIG[sess.status] || STATUS_CONFIG.pending;
  const Icon = cfg.icon;
  const isRunning = sess.status === "pending" || sess.status === "running";

  return (
    <button
      onClick={onClick}
      className={`w-full text-left px-4 py-3.5 transition-colors hover:bg-slate-50 ${
        isActive ? "bg-teal-50 border-l-2 border-teal-500" : "border-l-2 border-transparent"
      }`}
    >
      {/* Query text */}
      <p className={`text-sm font-semibold truncate mb-1.5 ${isActive ? "text-teal-700" : "text-slate-800"}`}>
        {sess.query}
      </p>

      {/* Status + time */}
      <div className="flex items-center justify-between gap-2">
        <span className={`inline-flex items-center gap-1 text-xs font-medium px-2 py-0.5 rounded-md border ${cfg.color}`}>
          <Icon className={`w-3 h-3 ${isRunning ? "animate-spin" : ""}`} />
          {cfg.label}
        </span>
        <span className="text-xs text-slate-400 flex-shrink-0">
          {formatTimeAgo(sess.started_at)}
        </span>
      </div>

      {/* Result count */}
      {sess.status === "completed" && (
        <p className="text-xs text-slate-400 mt-1">{sess.results_count} kết quả</p>
      )}
    </button>
  );
};

// ─── Result Card ──────────────────────────────────────────────────────────────

const ResultCard = ({ result, projectId, isAdded, onAdded }) => {
  const sourceCfg = SOURCE_LABELS[result.source] || SOURCE_LABELS.web;
  const SourceIcon = sourceCfg.icon;
  const [showIngest, setShowIngest] = useState(false);

  // A result is "already added" if either the prop says so (live add this
  // session) or the backend returned ``document_id != null`` from a previous
  // session.
  const alreadyAdded = isAdded || !!result.document_id;

  return (
    <div className="bg-white rounded-xl border border-slate-200 p-5 shadow-sm hover:shadow-md transition-shadow">
      <div className="flex items-start justify-between gap-4">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-2 flex-wrap">
            <span className={`inline-flex items-center gap-1 text-xs font-semibold px-2 py-0.5 rounded-lg border ${sourceCfg.color}`}>
              <SourceIcon className="w-3 h-3" />
              {sourceCfg.label}
            </span>
            {result.rank && (
              <span className="text-xs text-slate-400">#{result.rank}</span>
            )}
          </div>

          <h3 className="text-sm font-bold text-slate-900 mb-1.5 leading-snug">{result.title}</h3>

          {result.authors?.length > 0 && (
            <p className="text-xs text-slate-500 mb-1.5">
              {result.authors.slice(0, 3).join(", ")}
              {result.authors.length > 3 && " et al."}
            </p>
          )}

          {result.snippet && (
            <p className="text-xs text-slate-600 leading-relaxed line-clamp-2">{result.snippet}</p>
          )}

          <div className="flex items-center gap-3 mt-2 text-xs text-slate-400">
            {result.published_at && <span>{new Date(result.published_at).getFullYear()}</span>}
            {result.doi && <span className="font-mono">DOI: {result.doi}</span>}
            {result.relevance_score != null && (
              <span>
                Liên quan:{" "}
                <span className="font-semibold text-teal-600">
                  {(result.relevance_score * 100).toFixed(0)}%
                </span>
              </span>
            )}
          </div>
        </div>

        <div className="flex flex-col items-end gap-2 flex-shrink-0">
          <a
            href={result.url}
            target="_blank"
            rel="noopener noreferrer"
            className="text-slate-400 hover:text-teal-600 transition-colors"
            title="Mở trang nguồn"
          >
            <ExternalLink className="w-4 h-4" />
          </a>
          {alreadyAdded ? (
            <span className="inline-flex items-center gap-1 text-xs font-semibold text-emerald-600 bg-emerald-50 border border-emerald-200 px-2.5 py-1 rounded-lg">
              <CheckCircle2 className="w-3 h-3" /> Đã thêm
            </span>
          ) : (
            <button
              onClick={() => setShowIngest(true)}
              className="inline-flex items-center gap-1 text-xs font-semibold text-teal-600 bg-teal-50 hover:bg-teal-100 border border-teal-200 hover:border-teal-300 px-2.5 py-1 rounded-lg transition-colors"
            >
              <FolderPlus className="w-3 h-3" /> Thêm vào dự án
            </button>
          )}
        </div>
      </div>

      {result.pdf_url && (
        <div className="mt-3 pt-3 border-t border-slate-100">
          <a
            href={result.pdf_url}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-1.5 text-xs text-red-600 hover:text-red-700 font-semibold transition-colors"
          >
            <BookOpen className="w-3.5 h-3.5" />
            Xem PDF
            <ChevronRight className="w-3 h-3" />
          </a>
        </div>
      )}

      {showIngest && (
        <IngestSearchResultModal
          result={result}
          projectId={projectId}
          onClose={() => setShowIngest(false)}
          onIngested={() => {
            setShowIngest(false);
            onAdded();
          }}
        />
      )}
    </div>
  );
};

export default ResearchPage;
