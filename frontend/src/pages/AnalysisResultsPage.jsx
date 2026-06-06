import { useState, useMemo, useRef } from "react";
import { useParams, useNavigate } from "react-router-dom";
import DashboardLayout from "../components/layout/DashboardLayout";
import { analysisService } from "../services/analysisService";
import { useAnalysisPolling } from "../hooks/useAnalysisPolling";
import DocumentOutline from "../components/analysis/DocumentOutline";
import SectionInsightCard from "../components/analysis/SectionInsightCard";
import NarrativeSynthesis from "../components/analysis/NarrativeSynthesis";
import RunningProgressPanel from "../components/analysis/RunningProgressPanel";
import {
  ArrowLeft,
  CheckCircle2,
  AlertCircle,
  Loader,
  Clock,
  FileText,
  Tag,
  Lightbulb,
  ChevronDown,
  Hash,
  FlaskConical,
  AlertTriangle,
  Telescope,
  BookOpen,
  Trash2,
  X,
  Sparkles,
  ShieldCheck,
  HelpCircle,
  Layers,
} from "lucide-react";

const AnalysisResultsPage = () => {
  const { analysisId } = useParams();
  const navigate = useNavigate();
  const { analysis, loading, error } = useAnalysisPolling(analysisId);
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [deleteError, setDeleteError] = useState("");
  const [expandedSections, setExpandedSections] = useState({
    summary: true,
    outline: true,
    synthesis: true,
    insights: true,
    keywords: false,
    findings: false,
    methodology: false,
    limitations: false,
    future_work: false,
    research_contribution: false,
    research_questions: false,
    critical_assessment: false,
  });
  const [activeSectionIdx, setActiveSectionIdx] = useState(null);
  const sectionRefs = useRef({});

  // ── Helpers ──────────────────────────────────────────────────────────────

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

  const getDuration = () => {
    if (!analysis?.started_at || !analysis?.completed_at) return null;
    const seconds = Math.floor(
      (new Date(analysis.completed_at) - new Date(analysis.started_at)) / 1000
    );
    const minutes = Math.floor(seconds / 60);
    if (minutes > 0) return `${minutes}m ${seconds % 60}s`;
    return `${seconds}s`;
  };

  const toggleSection = (section) => {
    setExpandedSections((prev) => ({ ...prev, [section]: !prev[section] }));
  };

  const handleDelete = async () => {
    setDeleting(true);
    try {
      await analysisService.deleteAnalysis(analysisId);
      navigate("/analysis");
    } catch (err) {
      setDeleteError("Không thể xóa phân tích. Vui lòng thử lại.");
      setShowDeleteConfirm(false);
      console.error(err);
    } finally {
      setDeleting(false);
    }
  };

  // Scroll to a section card from the outline / sidebar
  const scrollToSection = (sectionIndex) => {
    setExpandedSections((prev) => ({ ...prev, insights: true }));
    setActiveSectionIdx(sectionIndex);
    requestAnimationFrame(() => {
      const node = sectionRefs.current[sectionIndex];
      if (node) {
        node.scrollIntoView({ behavior: "smooth", block: "start" });
      }
    });
  };

  // ── Stats ────────────────────────────────────────────────────────────────

  const sectionInsights = useMemo(
    () => analysis?.section_insights || [],
    [analysis]
  );

  const totalClaims = useMemo(
    () =>
      sectionInsights.reduce(
        (sum, s) => sum + (Array.isArray(s.claims) ? s.claims.length : 0),
        0
      ),
    [sectionInsights]
  );

  const totalQuotes = useMemo(
    () =>
      sectionInsights.reduce(
        (sum, s) =>
          sum + (Array.isArray(s.notable_quotes) ? s.notable_quotes.length : 0),
        0
      ),
    [sectionInsights]
  );

  const totalTables = useMemo(
    () =>
      sectionInsights.reduce(
        (sum, s) => sum + (Array.isArray(s.tables) ? s.tables.length : 0),
        0
      ),
    [sectionInsights]
  );

  const totalFormulas = useMemo(
    () =>
      sectionInsights.reduce(
        (sum, s) => sum + (Array.isArray(s.formulas) ? s.formulas.length : 0),
        0
      ),
    [sectionInsights]
  );

  // ── Static config ────────────────────────────────────────────────────────

  const statusConfig = {
    pending:   { label: "Chờ xử lý", icon: Clock,        bg: "bg-slate-50",   text: "text-slate-700",   border: "border-slate-200",   badge: "bg-slate-100 text-slate-700"   },
    running:   { label: "Đang chạy", icon: Loader,       bg: "bg-blue-50",    text: "text-blue-700",    border: "border-blue-200",    badge: "bg-blue-100 text-blue-700"    },
    completed: { label: "Hoàn thành",icon: CheckCircle2, bg: "bg-emerald-50", text: "text-emerald-700", border: "border-emerald-200", badge: "bg-emerald-100 text-emerald-700"},
    failed:    { label: "Thất bại",  icon: AlertCircle,  bg: "bg-red-50",     text: "text-red-700",     border: "border-red-200",     badge: "bg-red-100 text-red-700"     },
  };

  // ── Loading ──────────────────────────────────────────────────────────────
  if (loading) {
    return (
      <DashboardLayout>
        <div className="flex items-center justify-center h-96">
          <div className="text-center">
            <div className="w-12 h-12 border-4 border-teal-200 border-t-teal-600 rounded-full animate-spin mx-auto mb-4"></div>
            <p className="text-slate-600 font-medium">Đang tải kết quả phân tích...</p>
          </div>
        </div>
      </DashboardLayout>
    );
  }

  // ── Error / Not found ────────────────────────────────────────────────────
  if (error || !analysis) {
    return (
      <DashboardLayout>
        <div className="text-center py-16">
          <AlertCircle className="w-16 h-16 text-red-400 mx-auto mb-4" />
          <h2 className="text-2xl font-bold text-slate-900 mb-2">Không tìm thấy phân tích</h2>
          <p className="text-slate-600 mb-8">{error || "Phân tích không tồn tại hoặc đã bị xóa"}</p>
          <button
            onClick={() => navigate("/analysis")}
            className="inline-flex items-center gap-2 px-6 py-3 bg-gradient-to-r from-teal-600 to-teal-700 hover:from-teal-700 hover:to-teal-800 text-white rounded-xl font-semibold transition-all shadow-lg hover:shadow-xl"
          >
            <ArrowLeft className="w-5 h-5" />
            Quay lại phân tích
          </button>
        </div>
      </DashboardLayout>
    );
  }

  const statusInfo = statusConfig[analysis.status] || statusConfig.pending;
  const StatusIcon = statusInfo.icon;
  const outline = analysis.document_outline;
  const synthesis = analysis.narrative_synthesis;

  return (
    <DashboardLayout>
      <div className="space-y-8">
        {/* Delete error banner */}
        {deleteError && (
          <div className="bg-red-50 border border-red-200 rounded-xl p-4 flex items-start gap-3">
            <AlertCircle className="w-5 h-5 text-red-600 flex-shrink-0 mt-0.5" />
            <div className="flex-1">
              <p className="text-sm text-red-700">{deleteError}</p>
            </div>
            <button
              onClick={() => setDeleteError("")}
              className="text-red-500 hover:text-red-700"
              aria-label="Đóng"
            >
              <X className="w-4 h-4" />
            </button>
          </div>
        )}

        {/* Breadcrumb */}
        <div className="flex items-center gap-3 text-sm">
          <button
            onClick={() => navigate("/analysis")}
            className="flex items-center gap-2 text-teal-600 hover:text-teal-700 font-semibold transition-colors group"
          >
            <ArrowLeft className="w-4 h-4 group-hover:-translate-x-1 transition-transform" />
            Phân tích
          </button>
          <span className="text-slate-400">/</span>
          <span className="text-slate-900 font-semibold truncate max-w-xs">
            {analysis.document_title}
          </span>
        </div>

        {/* Page Header */}
        <div className="bg-white rounded-2xl border border-slate-200 p-8 shadow-sm">
          <div className="flex items-start gap-5">
            <div className={`p-4 rounded-2xl ${statusInfo.bg} border ${statusInfo.border} flex-shrink-0`}>
              <StatusIcon className={`w-8 h-8 ${statusInfo.text} ${analysis.status === "running" ? "animate-spin" : ""}`} />
            </div>
            <div className="flex-1 min-w-0">
              <div className="flex items-start justify-between gap-4 flex-wrap">
                <div>
                  <h1 className="text-2xl font-bold text-slate-900 mb-1">
                    {analysis.document_title || `Phân tích ${analysis.id?.slice(0, 8)}`}
                  </h1>
                  <p className="text-sm text-slate-500 font-mono">ID: {analysis.id}</p>
                </div>
                <div className="flex items-center gap-3">
                  <span className={`px-4 py-1.5 rounded-xl text-sm font-bold ${statusInfo.badge}`}>
                    {statusInfo.label}
                  </span>
                  <button
                    onClick={() => setShowDeleteConfirm(true)}
                    className="flex items-center gap-2 px-4 py-1.5 rounded-xl text-sm font-semibold text-red-600 border border-red-200 hover:bg-red-50 transition-colors"
                  >
                    <Trash2 className="w-4 h-4" />
                    Xóa
                  </button>
                </div>
              </div>

              {/* Quick stats row */}
              {analysis.status === "completed" && (
                <div className="flex items-center gap-6 mt-5 pt-5 border-t border-slate-100 flex-wrap">
                  <QuickStat icon={Layers}    label="Phần"      value={sectionInsights.length} color="text-teal-600" />
                  <QuickStat icon={Sparkles}  label="Khẳng định" value={totalClaims}            color="text-violet-600" />
                  <QuickStat icon={Lightbulb} label="Phát hiện"  value={analysis.key_findings?.length || 0} color="text-amber-600" />
                  <QuickStat icon={Tag}       label="Từ khóa"    value={analysis.keywords?.length || 0} color="text-fuchsia-600" />
                  <QuickStat icon={BookOpen}  label="Trích dẫn"  value={totalQuotes} color="text-blue-600" />
                  {totalTables > 0 && (
                    <QuickStat icon={Layers} label="Bảng" value={totalTables} color="text-emerald-600" />
                  )}
                  {totalFormulas > 0 && (
                    <QuickStat icon={Layers} label="Công thức" value={totalFormulas} color="text-indigo-600" />
                  )}
                  {getDuration() && (
                    <QuickStat icon={Clock} label="Thời gian" value={getDuration()} color="text-slate-500" />
                  )}
                </div>
              )}
            </div>
          </div>
        </div>

        {/* Main body */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Left — analysis content */}
          <div className="lg:col-span-2 space-y-4">
            {/* Running / Pending / Failed: full live progress panel
                with stage stepper, current detail, and activity log. */}
            {(analysis.status === "running" ||
              analysis.status === "pending" ||
              analysis.status === "failed") && (
              <RunningProgressPanel
                status={analysis.status}
                progress={analysis.progress}
                errorMessage={analysis.error_message}
              />
            )}

            {/* Completed */}
            {analysis.status === "completed" && (
              <>
                {/* Executive summary */}
                {analysis.summary && (
                  <SectionCard
                    icon={FileText}
                    title="Tóm tắt điều hành"
                    isExpanded={expandedSections.summary}
                    onToggle={() => toggleSection("summary")}
                  >
                    <p className="text-slate-700 leading-relaxed whitespace-pre-wrap">
                      {analysis.summary}
                    </p>
                  </SectionCard>
                )}

                {/* Outline */}
                {outline && (outline.title || outline.sections?.length) && (
                  <SectionCard
                    icon={BookOpen}
                    title="Cấu trúc tài liệu"
                    count={outline.sections?.length}
                    isExpanded={expandedSections.outline}
                    onToggle={() => toggleSection("outline")}
                  >
                    <DocumentOutline outline={outline} onSectionClick={scrollToSection} />
                  </SectionCard>
                )}

                {/* Cross-section synthesis */}
                {synthesis && Object.keys(synthesis).length > 0 && (
                  <SectionCard
                    icon={Sparkles}
                    title="Tổng hợp xuyên phần"
                    isExpanded={expandedSections.synthesis}
                    onToggle={() => toggleSection("synthesis")}
                  >
                    <NarrativeSynthesis synthesis={synthesis} />
                  </SectionCard>
                )}

                {/* Section-by-section deep insights — the headline feature */}
                {sectionInsights.length > 0 && (
                  <SectionCard
                    icon={Layers}
                    title="Phân tích chi tiết theo phần"
                    count={sectionInsights.length}
                    isExpanded={expandedSections.insights}
                    onToggle={() => toggleSection("insights")}
                  >
                    <div className="space-y-3">
                      {sectionInsights.map((sec, idx) => (
                        <div
                          key={sec.section_index}
                          ref={(el) => (sectionRefs.current[sec.section_index] = el)}
                          className={
                            activeSectionIdx === sec.section_index
                              ? "ring-2 ring-teal-300 rounded-2xl"
                              : ""
                          }
                        >
                          <SectionInsightCard
                            section={sec}
                            defaultOpen={
                              activeSectionIdx === sec.section_index || idx === 0
                            }
                          />
                        </div>
                      ))}
                    </div>
                  </SectionCard>
                )}

                {/* ── Tổng hợp nhanh — gom các legacy aggregated views vào ONE card ── */}
                {(analysis.key_findings?.length > 0 ||
                  analysis.keywords?.length > 0 ||
                  analysis.methodology ||
                  analysis.limitations?.length > 0 ||
                  analysis.future_work?.length > 0 ||
                  analysis.research_contribution ||
                  analysis.research_questions?.length > 0 ||
                  (analysis.critical_assessment &&
                    Object.keys(analysis.critical_assessment).length > 0)) && (
                  <SectionCard
                    icon={Sparkles}
                    title="Tổng hợp nhanh"
                    isExpanded={expandedSections.findings}
                    onToggle={() => toggleSection("findings")}
                  >
                    <QuickRollup analysis={analysis} />
                  </SectionCard>
                )}
              </>
            )}
          </div>

          {/* Right — sidebar */}
          <div className="space-y-6">
            {/* Metadata card */}
            <div className="bg-white rounded-2xl border border-slate-200 p-8 shadow-sm">
              <h3 className="text-sm font-semibold text-slate-600 mb-6 uppercase tracking-wide">
                Thông tin phân tích
              </h3>
              <div className="space-y-4">
                <div>
                  <p className="text-xs font-semibold text-slate-600 mb-2">Trạng thái</p>
                  <span
                    className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm font-bold ${statusInfo.badge}`}
                  >
                    <StatusIcon className="w-3.5 h-3.5" />
                    {statusInfo.label}
                  </span>
                </div>

                <div className="border-t border-slate-200 pt-4">
                  <p className="text-xs font-semibold text-slate-600 mb-2 flex items-center gap-2">
                    <Clock className="w-4 h-4" /> Bắt đầu
                  </p>
                  <p className="text-sm text-slate-700 font-medium">{formatDate(analysis.started_at)}</p>
                </div>

                {analysis.completed_at && (
                  <div className="border-t border-slate-200 pt-4">
                    <p className="text-xs font-semibold text-slate-600 mb-2 flex items-center gap-2">
                      <CheckCircle2 className="w-4 h-4" /> Hoàn thành
                    </p>
                    <p className="text-sm text-slate-700 font-medium">
                      {formatDate(analysis.completed_at)}
                    </p>
                  </div>
                )}

                {getDuration() && (
                  <div className="border-t border-slate-200 pt-4">
                    <p className="text-xs font-semibold text-slate-600 mb-2">Thời gian xử lý</p>
                    <p className="text-sm text-slate-700 font-medium">{getDuration()}</p>
                  </div>
                )}

                {analysis.processed_by && (
                  <div className="border-t border-slate-200 pt-4">
                    <p className="text-xs font-semibold text-slate-600 mb-2">Mô hình LLM</p>
                    <p className="text-sm text-slate-700 font-medium font-mono">
                      {analysis.processed_by}
                    </p>
                  </div>
                )}

                <div className="border-t border-slate-200 pt-4">
                  <p className="text-xs font-semibold text-slate-600 mb-2">Analysis ID</p>
                  <p className="text-xs font-mono text-slate-500 bg-slate-50 p-2 rounded-lg border border-slate-200 break-all">
                    {analysis.id}
                  </p>
                </div>
              </div>
            </div>

            {/* Section navigator */}
            {analysis.status === "completed" && sectionInsights.length > 0 && (
              <div className="bg-white rounded-2xl border border-slate-200 p-6 shadow-sm">
                <h3 className="text-sm font-semibold text-slate-600 mb-4 uppercase tracking-wide flex items-center gap-2">
                  <Layers className="w-4 h-4" /> Điều hướng phần
                </h3>
                <ul className="space-y-1.5 max-h-[460px] overflow-y-auto pr-1">
                  {sectionInsights.map((sec) => (
                    <li key={sec.section_index}>
                      <button
                        onClick={() => scrollToSection(sec.section_index)}
                        className={`w-full text-left px-3 py-2 rounded-lg text-sm transition-colors ${
                          activeSectionIdx === sec.section_index
                            ? "bg-teal-50 text-teal-700 border border-teal-200"
                            : "hover:bg-slate-50 text-slate-700 border border-transparent"
                        }`}
                      >
                        <div className="flex items-center gap-2">
                          <span className="flex-shrink-0 w-5 h-5 rounded bg-slate-100 text-slate-600 text-[10px] font-bold flex items-center justify-center">
                            {sec.section_index + 1}
                          </span>
                          <span className="font-semibold truncate flex-1">{sec.title}</span>
                        </div>
                        {sec.section_type && (
                          <span className="ml-7 text-[10px] uppercase font-bold text-slate-400 tracking-wide">
                            {sec.section_type.replace(/_/g, " ")}
                          </span>
                        )}
                      </button>
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {/* Stats card */}
            {analysis.status === "completed" && (
              <div className="bg-white rounded-2xl border border-slate-200 p-8 shadow-sm">
                <h3 className="text-sm font-semibold text-slate-600 mb-6 uppercase tracking-wide">
                  Thống kê
                </h3>
                <div className="space-y-4">
                  <StatLine
                    icon={Layers}
                    label="Số phần được phân tích"
                    value={sectionInsights.length}
                    color="text-teal-600"
                    bg="bg-teal-50"
                  />
                  <StatLine
                    icon={Sparkles}
                    label="Khẳng định trích xuất"
                    value={totalClaims}
                    color="text-violet-600"
                    bg="bg-violet-50"
                  />
                  <StatLine
                    icon={Lightbulb}
                    label="Phát hiện quan trọng"
                    value={analysis.key_findings?.length || 0}
                    color="text-amber-600"
                    bg="bg-amber-50"
                  />
                  <StatLine
                    icon={Tag}
                    label="Từ khóa"
                    value={analysis.keywords?.length || 0}
                    color="text-fuchsia-600"
                    bg="bg-fuchsia-50"
                  />
                  <StatLine
                    icon={BookOpen}
                    label="Trích dẫn đáng chú ý"
                    value={totalQuotes}
                    color="text-blue-600"
                    bg="bg-blue-50"
                  />
                </div>
              </div>
            )}

            {/* Back button */}
            <button
              onClick={() => navigate("/analysis")}
              className="w-full flex items-center justify-center gap-2 px-6 py-3 border border-slate-200 rounded-xl text-slate-700 hover:bg-slate-50 font-semibold transition-colors"
            >
              <ArrowLeft className="w-4 h-4" />
              Quay lại danh sách
            </button>
          </div>
        </div>
      </div>

      {/* Delete Confirm Dialog */}
      {showDeleteConfirm && (
        <div className="fixed inset-0 bg-black/40 backdrop-blur-sm flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-2xl shadow-2xl max-w-md w-full p-8">
            <div className="flex items-start gap-4 mb-6">
              <div className="w-12 h-12 rounded-xl bg-red-100 flex items-center justify-center flex-shrink-0">
                <Trash2 className="w-6 h-6 text-red-600" />
              </div>
              <div>
                <h3 className="text-lg font-bold text-slate-900 mb-1">Xóa phân tích?</h3>
                <p className="text-sm text-slate-600">
                  Hành động này không thể hoàn tác. Toàn bộ kết quả phân tích của tài liệu{" "}
                  <span className="font-semibold text-slate-800">
                    {analysis.document_title || analysis.id?.slice(0, 8)}
                  </span>{" "}
                  sẽ bị xóa vĩnh viễn.
                </p>
              </div>
            </div>
            <div className="flex items-center justify-end gap-3">
              <button
                onClick={() => setShowDeleteConfirm(false)}
                disabled={deleting}
                className="flex items-center gap-2 px-5 py-2.5 border border-slate-200 rounded-xl text-slate-700 hover:bg-slate-50 font-semibold transition-colors disabled:opacity-50"
              >
                <X className="w-4 h-4" />
                Hủy
              </button>
              <button
                onClick={handleDelete}
                disabled={deleting}
                className="flex items-center gap-2 px-5 py-2.5 bg-red-600 hover:bg-red-700 disabled:opacity-60 text-white rounded-xl font-semibold transition-colors shadow-sm"
              >
                {deleting ? (
                  <>
                    <Loader className="w-4 h-4 animate-spin" />
                    Đang xóa...
                  </>
                ) : (
                  <>
                    <Trash2 className="w-4 h-4" />
                    Xóa phân tích
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

// ── Sub-components ───────────────────────────────────────────────────────────

/**
 * Roll-up card that consolidates the legacy aggregated views
 * (key_findings, keywords, methodology, limitations, future_work,
 * research_contribution, research_questions, critical_assessment) into a
 * single tabbed card. Each tab is only listed when its underlying field
 * has content, so the layout stays compact for short documents.
 */
const QuickRollup = ({ analysis }) => {
  const tabs = useMemo(() => {
    const out = [];
    if (analysis.key_findings?.length > 0)
      out.push({ key: "findings", label: "Phát hiện", count: analysis.key_findings.length, icon: Lightbulb });
    if (analysis.research_questions?.length > 0)
      out.push({ key: "rq", label: "Câu hỏi NC", count: analysis.research_questions.length, icon: HelpCircle });
    if (analysis.methodology)
      out.push({ key: "methodology", label: "Phương pháp", icon: FlaskConical });
    if (analysis.limitations?.length > 0)
      out.push({ key: "limitations", label: "Hạn chế", count: analysis.limitations.length, icon: AlertTriangle });
    if (analysis.future_work?.length > 0)
      out.push({ key: "future", label: "Hướng phát triển", count: analysis.future_work.length, icon: Telescope });
    if (analysis.research_contribution)
      out.push({ key: "contribution", label: "Đóng góp", icon: Sparkles });
    if (analysis.critical_assessment && Object.keys(analysis.critical_assessment).length > 0)
      out.push({ key: "assessment", label: "Phản biện", icon: ShieldCheck });
    if (analysis.keywords?.length > 0)
      out.push({ key: "keywords", label: "Từ khóa", count: analysis.keywords.length, icon: Hash });
    return out;
  }, [analysis]);

  const [active, setActive] = useState(tabs[0]?.key);

  if (tabs.length === 0) return null;

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-1 flex-wrap border-b border-slate-100 -mt-1">
        {tabs.map((t) => {
          const Icon = t.icon;
          const isActive = active === t.key;
          return (
            <button
              key={t.key}
              onClick={() => setActive(t.key)}
              className={`relative inline-flex items-center gap-1.5 px-3 py-2 text-sm font-semibold border-b-2 transition-colors ${
                isActive
                  ? "border-teal-600 text-teal-700"
                  : "border-transparent text-slate-500 hover:text-slate-700"
              }`}
            >
              <Icon className="w-4 h-4" />
              {t.label}
              {t.count !== undefined && (
                <span
                  className={`ml-0.5 px-1.5 py-0.5 rounded text-[10px] font-bold ${
                    isActive ? "bg-teal-100 text-teal-700" : "bg-slate-100 text-slate-500"
                  }`}
                >
                  {t.count}
                </span>
              )}
            </button>
          );
        })}
      </div>

      <div>
        {active === "findings" && (
          <ol className="space-y-2">
            {analysis.key_findings.map((f, i) => (
              <NumberedListItem key={i} index={i + 1} color="teal">
                {f}
              </NumberedListItem>
            ))}
          </ol>
        )}

        {active === "rq" && (
          <ol className="space-y-2">
            {analysis.research_questions.map((rq, i) => (
              <NumberedListItem key={i} label={`RQ${i + 1}`} color="indigo" bg="bg-indigo-50" ring="ring-indigo-100">
                {rq}
              </NumberedListItem>
            ))}
          </ol>
        )}

        {active === "methodology" && (
          <p className="text-slate-700 leading-relaxed whitespace-pre-wrap">
            {analysis.methodology}
          </p>
        )}

        {active === "limitations" && (
          <ul className="space-y-2">
            {analysis.limitations.map((item, i) => (
              <NumberedListItem key={i} index={i + 1} color="amber" bg="bg-amber-50" ring="ring-amber-100">
                {item}
              </NumberedListItem>
            ))}
          </ul>
        )}

        {active === "future" && (
          <ul className="space-y-2">
            {analysis.future_work.map((item, i) => (
              <NumberedListItem key={i} index={i + 1} color="blue" bg="bg-blue-50" ring="ring-blue-100">
                {item}
              </NumberedListItem>
            ))}
          </ul>
        )}

        {active === "contribution" && (
          <p className="text-slate-700 leading-relaxed whitespace-pre-wrap">
            {analysis.research_contribution}
          </p>
        )}

        {active === "assessment" && (
          <CriticalAssessmentBlock data={analysis.critical_assessment} />
        )}

        {active === "keywords" && (
          <div className="flex flex-wrap gap-2">
            {analysis.keywords.map((keyword, i) => (
              <span
                key={i}
                className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-white ring-1 ring-violet-200 text-violet-700 rounded-lg text-sm font-medium hover:bg-violet-50 transition-colors"
              >
                <Tag className="w-3 h-3" />
                {keyword}
              </span>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};

/** Compact numbered list item used by QuickRollup tabs. */
const NumberedListItem = ({
  index,
  label,
  color = "slate",
  bg = "bg-white",
  ring = "ring-slate-200",
  children,
}) => {
  const palette = {
    teal:    "bg-teal-100 text-teal-700",
    indigo:  "bg-indigo-200 text-indigo-700",
    amber:   "bg-amber-200 text-amber-700",
    blue:    "bg-blue-200 text-blue-700",
    slate:   "bg-slate-200 text-slate-700",
  };
  return (
    <li className={`flex items-start gap-3 ${bg} rounded-xl ring-1 ${ring} p-3.5`}>
      <span
        className={`flex-shrink-0 ${
          label ? "px-2 h-6 min-w-[1.75rem]" : "w-6 h-6 rounded-full"
        } text-[11px] font-bold flex items-center justify-center mt-0.5 ${
          palette[color] || palette.slate
        } ${label ? "rounded" : ""}`}
      >
        {label || index}
      </span>
      <p className="text-slate-700 text-sm leading-relaxed">{children}</p>
    </li>
  );
};

const SectionCard = ({ icon: Icon, title, children, isExpanded, onToggle, count }) => (
  <div className="bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden hover:shadow-md transition-shadow">
    <button
      onClick={onToggle}
      className="w-full flex items-center justify-between px-6 py-5 hover:bg-slate-50 transition-colors"
    >
      <h3 className="font-bold text-slate-900 flex items-center gap-3">
        <Icon className="w-5 h-5 text-teal-600" />
        {title}
        {count !== undefined && (
          <span className="text-sm font-semibold text-slate-400">({count})</span>
        )}
      </h3>
      <ChevronDown
        className={`w-5 h-5 text-slate-400 transition-transform duration-200 ${isExpanded ? "rotate-180" : ""}`}
      />
    </button>
    {isExpanded && <div className="px-6 py-5 border-t border-slate-100">{children}</div>}
  </div>
);

const QuickStat = ({ icon: Icon, label, value, color }) => (
  <div className="flex items-center gap-2">
    <Icon className={`w-4 h-4 ${color}`} />
    <span className="text-sm text-slate-500">{label}:</span>
    <span className="text-sm font-bold text-slate-900">{value}</span>
  </div>
);

const StatLine = ({ icon: Icon, label, value, color, bg }) => (
  <div className="flex items-center justify-between">
    <div className="flex items-center gap-2">
      <div className={`w-7 h-7 rounded-lg ${bg} flex items-center justify-center`}>
        <Icon className={`w-4 h-4 ${color}`} />
      </div>
      <p className="text-sm text-slate-600">{label}</p>
    </div>
    <p className={`text-lg font-bold ${color}`}>{value}</p>
  </div>
);

/**
 * Render the synthesis-derived `critical_assessment` field that the AnalysisAgent
 * builds during legacy rollup. Shape:
 *   {
 *     strengths, weaknesses, internal_conflicts: [{between, description}],
 *     confidence_in_conclusions, confidence_justification
 *   }
 */
const CriticalAssessmentBlock = ({ data }) => {
  if (!data || typeof data !== "object") return null;
  const conflicts = Array.isArray(data.internal_conflicts) ? data.internal_conflicts : [];
  return (
    <div className="space-y-4">
      {data.confidence_in_conclusions && (
        <div className="flex items-center gap-3 flex-wrap">
          <span className="text-sm font-semibold text-slate-600">Mức độ tin cậy:</span>
          <span
            className={`px-3 py-1 rounded-lg text-sm font-bold border ${
              data.confidence_in_conclusions === "high"
                ? "bg-emerald-100 text-emerald-700 border-emerald-200"
                : data.confidence_in_conclusions === "medium"
                ? "bg-amber-100 text-amber-700 border-amber-200"
                : "bg-red-100 text-red-700 border-red-200"
            }`}
          >
            {data.confidence_in_conclusions === "high"
              ? "Cao"
              : data.confidence_in_conclusions === "medium"
              ? "Trung bình"
              : "Thấp"}
          </span>
          {data.confidence_justification && (
            <span className="text-sm text-slate-600 italic">{data.confidence_justification}</span>
          )}
        </div>
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {data.strengths?.length > 0 && (
          <div className="bg-emerald-50 rounded-xl border border-emerald-100 p-4">
            <p className="text-xs font-bold text-emerald-700 uppercase tracking-wide mb-3">
              ✓ Điểm mạnh
            </p>
            <ul className="space-y-2">
              {data.strengths.map((s, i) => (
                <li key={i} className="text-sm text-slate-700 flex items-start gap-2">
                  <span className="text-emerald-500 mt-0.5 flex-shrink-0">•</span>
                  {s}
                </li>
              ))}
            </ul>
          </div>
        )}
        {data.weaknesses?.length > 0 && (
          <div className="bg-red-50 rounded-xl border border-red-100 p-4">
            <p className="text-xs font-bold text-red-700 uppercase tracking-wide mb-3">
              ✗ Điểm yếu
            </p>
            <ul className="space-y-2">
              {data.weaknesses.map((w, i) => (
                <li key={i} className="text-sm text-slate-700 flex items-start gap-2">
                  <span className="text-red-400 mt-0.5 flex-shrink-0">•</span>
                  {w}
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>

      {conflicts.length > 0 && (
        <div className="bg-amber-50 rounded-xl border border-amber-100 p-4">
          <p className="text-xs font-bold text-amber-700 uppercase tracking-wide mb-3">
            ⚠ Mâu thuẫn nội tại
          </p>
          <ul className="space-y-2">
            {conflicts.map((c, i) => (
              <li key={i} className="text-sm text-slate-700">
                {Array.isArray(c.between) && c.between.length > 0 && (
                  <span className="font-semibold text-amber-700 mr-1">
                    {c.between.join(" ↔ ")}:
                  </span>
                )}
                {c.description}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
};

export default AnalysisResultsPage;
