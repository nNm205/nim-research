import { useState, useEffect, useMemo } from "react";
import { useNavigate } from "react-router-dom";
import DashboardLayout from "../components/layout/DashboardLayout";
import { projectService } from "../services/projectService";
import { reportService } from "../services/reportService";
import ReportCard from "../components/reports/ReportCard";
import {
  ClipboardList,
  PenLine,
  CheckCircle2,
  Archive,
  AlertCircle,
  Search,
  Folder,
} from "lucide-react";

/**
 * ReportsPage — list every report the user owns, across every project.
 *
 * Pure aggregator (matches DocumentsPage / AnalysisPage). Creating new
 * reports happens inside ProjectDetailPage where the project context is
 * already known — same pattern as documents and analyses.
 *
 * Visual structure:
 *
 *   1. Header (title + subtitle)
 *   2. Stat cards (total / draft / published / archived)
 *   3. Search input
 *   4. Filter chips (project, status, type)
 *   5. Content grid (or empty state)
 */
const ReportsPage = () => {
  const navigate = useNavigate();

  const [projects, setProjects] = useState([]);
  const [reports, setReports] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  // Filters
  const [searchTerm, setSearchTerm] = useState("");
  const [projectFilter, setProjectFilter] = useState("all");
  const [statusFilter, setStatusFilter] = useState("all");
  const [typeFilter, setTypeFilter] = useState("all");

  // ── Initial load: projects + every report across them ───────────────────
  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        setLoading(true);
        const projectsData = await projectService.getProjects();
        const activeProjects = projectsData.filter((p) => !p.is_archived);
        if (cancelled) return;
        setProjects(activeProjects);

        // Fan out per-project. The backend doesn't yet expose a
        // cross-project /reports endpoint, so we aggregate client-side.
        // Each call only fetches metadata (deferred content/html) so
        // the cost scales linearly with project count, not report size.
        const all = await Promise.all(
          activeProjects.map((p) =>
            reportService
              .getProjectReports(p.id)
              .then((rs) =>
                rs.map((r) => ({ ...r, _project_id: p.id, _project_name: p.name }))
              )
              .catch(() => [])
          )
        );
        if (cancelled) return;
        setReports(all.flat());
        setError("");
      } catch (err) {
        if (!cancelled) {
          setError("Không thể tải danh sách báo cáo");
          console.error(err);
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const stats = useMemo(
    () => ({
      total: reports.length,
      draft: reports.filter((r) => r.status === "draft").length,
      published: reports.filter((r) => r.status === "published").length,
      archived: reports.filter((r) => r.status === "archived").length,
    }),
    [reports]
  );

  const filteredReports = useMemo(() => {
    const q = searchTerm.trim().toLowerCase();
    return reports
      .filter((r) => {
        if (projectFilter !== "all" && r._project_id !== projectFilter)
          return false;
        if (statusFilter !== "all" && r.status !== statusFilter) return false;
        if (typeFilter !== "all" && r.report_type !== typeFilter) return false;
        if (q && !(r.title || "").toLowerCase().includes(q)) return false;
        return true;
      })
      .sort(
        (a, b) =>
          new Date(b.updated_at || b.created_at) -
          new Date(a.updated_at || a.created_at)
      );
  }, [reports, projectFilter, statusFilter, typeFilter, searchTerm]);

  const handleDeleteReport = async (reportId) => {
    if (!window.confirm("Bạn có chắc muốn xóa báo cáo này?")) return;
    try {
      await reportService.deleteReport(reportId);
      setReports((prev) => prev.filter((r) => r.id !== reportId));
    } catch (err) {
      console.error(err);
      setError("Không thể xóa báo cáo");
    }
  };

  return (
    <DashboardLayout>
      <div className="space-y-8">
        {/* ── Header ─────────────────────────────────────────────────── */}
        <div>
          <h1 className="text-3xl font-bold text-slate-900">Báo cáo</h1>
          <p className="text-slate-600 mt-2">
            Tổng hợp toàn bộ báo cáo nghiên cứu của bạn. Để tạo báo cáo
            mới, mở dự án tương ứng.
          </p>
        </div>

        {/* ── Stats ──────────────────────────────────────────────────── */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-6">
          <StatCard label="Tổng số" value={stats.total} icon={ClipboardList} color="teal" />
          <StatCard label="Nháp" value={stats.draft} icon={PenLine} color="amber" />
          <StatCard label="Đã xuất bản" value={stats.published} icon={CheckCircle2} color="emerald" />
          <StatCard label="Lưu trữ" value={stats.archived} icon={Archive} color="slate" />
        </div>

        {/* ── Error banner ───────────────────────────────────────────── */}
        {error && (
          <div className="flex items-start gap-3 bg-red-50 border border-red-200 text-red-700 px-6 py-4 rounded-xl">
            <AlertCircle className="w-5 h-5 flex-shrink-0 mt-0.5" />
            <span className="text-sm font-medium">{error}</span>
          </div>
        )}

        {/* ── No projects yet — onboarding state ──────────────────────── */}
        {!loading && projects.length === 0 && (
          <div className="text-center py-16 bg-white rounded-2xl border border-slate-200 shadow-sm">
            <Folder className="w-16 h-16 text-slate-300 mx-auto mb-4" />
            <h3 className="text-xl font-bold text-slate-900 mb-2">
              Chưa có dự án nào
            </h3>
            <p className="text-slate-600 mb-8">
              Tạo dự án và thêm tài liệu trước khi viết báo cáo.
            </p>
            <button
              onClick={() => navigate("/projects")}
              className="inline-flex items-center gap-2 px-6 py-3 bg-gradient-to-r from-teal-600 to-teal-700 hover:from-teal-700 hover:to-teal-800 text-white rounded-xl font-semibold transition-all shadow-lg hover:shadow-xl"
            >
              Mở trang Dự án
            </button>
          </div>
        )}

        {/* ── Filters ────────────────────────────────────────────────── */}
        {!loading && projects.length > 0 && (
          <div className="space-y-4">
            <div className="relative">
              <Search className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-slate-400" />
              <input
                type="text"
                placeholder="Tìm kiếm theo tiêu đề báo cáo..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                className="w-full pl-12 pr-4 py-3 border border-slate-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-teal-500 focus:ring-offset-2 focus:border-transparent transition-all text-slate-900 placeholder-slate-500"
              />
            </div>

            <div className="flex flex-wrap items-center gap-3">
              <span className="text-xs font-bold uppercase tracking-wider text-slate-500">
                Dự án:
              </span>
              <FilterChip
                active={projectFilter === "all"}
                onClick={() => setProjectFilter("all")}
                label="Tất cả"
                count={reports.length}
              />
              {projects.map((p) => {
                const c = reports.filter((r) => r._project_id === p.id).length;
                return (
                  <FilterChip
                    key={p.id}
                    active={projectFilter === p.id}
                    onClick={() => setProjectFilter(p.id)}
                    label={p.name}
                    count={c}
                  />
                );
              })}
            </div>

            <div className="flex flex-wrap items-center gap-3">
              <span className="text-xs font-bold uppercase tracking-wider text-slate-500">
                Trạng thái:
              </span>
              <FilterChip
                active={statusFilter === "all"}
                onClick={() => setStatusFilter("all")}
                label="Tất cả"
              />
              <FilterChip
                active={statusFilter === "draft"}
                onClick={() => setStatusFilter("draft")}
                label="Nháp"
                count={stats.draft}
              />
              <FilterChip
                active={statusFilter === "published"}
                onClick={() => setStatusFilter("published")}
                label="Đã xuất bản"
                count={stats.published}
              />
              <FilterChip
                active={statusFilter === "archived"}
                onClick={() => setStatusFilter("archived")}
                label="Lưu trữ"
                count={stats.archived}
              />
            </div>

            <div className="flex flex-wrap items-center gap-3">
              <span className="text-xs font-bold uppercase tracking-wider text-slate-500">
                Loại:
              </span>
              <FilterChip
                active={typeFilter === "all"}
                onClick={() => setTypeFilter("all")}
                label="Tất cả"
              />
              <FilterChip
                active={typeFilter === "research_summary"}
                onClick={() => setTypeFilter("research_summary")}
                label="Tóm tắt nghiên cứu"
                count={reports.filter((r) => r.report_type === "research_summary").length}
              />
              <FilterChip
                active={typeFilter === "literature_review"}
                onClick={() => setTypeFilter("literature_review")}
                label="Tổng quan tài liệu"
                count={reports.filter((r) => r.report_type === "literature_review").length}
              />
              <FilterChip
                active={typeFilter === "data_analysis"}
                onClick={() => setTypeFilter("data_analysis")}
                label="Phân tích dữ liệu"
                count={reports.filter((r) => r.report_type === "data_analysis").length}
              />
              <FilterChip
                active={typeFilter === "custom"}
                onClick={() => setTypeFilter("custom")}
                label="Tùy chỉnh"
                count={reports.filter((r) => r.report_type === "custom").length}
              />
            </div>
          </div>
        )}

        {/* ── Loading ────────────────────────────────────────────────── */}
        {loading && (
          <div className="text-center py-16">
            <div className="w-12 h-12 border-4 border-teal-200 border-t-teal-600 rounded-full animate-spin mx-auto mb-4" />
            <p className="text-slate-600 font-medium">Đang tải báo cáo...</p>
          </div>
        )}

        {/* ── Grid ───────────────────────────────────────────────────── */}
        {!loading && filteredReports.length > 0 && (
          <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-6">
            {filteredReports.map((report) => (
              <ReportCard
                key={report.id}
                report={report}
                projectName={report._project_name}
                onClick={() => navigate(`/reports/${report.id}`)}
                onDelete={handleDeleteReport}
              />
            ))}
          </div>
        )}

        {/* ── Empty after filter ─────────────────────────────────────── */}
        {!loading &&
          reports.length > 0 &&
          filteredReports.length === 0 && (
            <div className="text-center py-12 bg-slate-50 rounded-xl border border-slate-200">
              <Search className="w-12 h-12 text-slate-300 mx-auto mb-3" />
              <p className="text-slate-600">Không có báo cáo nào khớp bộ lọc</p>
            </div>
          )}

        {/* ── Empty when no reports at all ───────────────────────────── */}
        {!loading && projects.length > 0 && reports.length === 0 && (
          <div className="text-center py-16 bg-white rounded-2xl border border-slate-200 shadow-sm">
            <ClipboardList className="w-16 h-16 text-slate-300 mx-auto mb-4" />
            <h3 className="text-xl font-bold text-slate-900 mb-2">
              Chưa có báo cáo nào
            </h3>
            <p className="text-slate-600 mb-8">
              Mở một dự án có tài liệu để tạo báo cáo đầu tiên — hệ thống
              sẽ tự dựng nội dung từ Documents và Analysis của dự án.
            </p>
            <button
              onClick={() => navigate("/projects")}
              className="inline-flex items-center gap-2 px-6 py-3 bg-gradient-to-r from-teal-600 to-teal-700 hover:from-teal-700 hover:to-teal-800 text-white rounded-xl font-semibold transition-all shadow-lg hover:shadow-xl"
            >
              <Folder className="w-5 h-5" />
              Mở trang Dự án
            </button>
          </div>
        )}
      </div>
    </DashboardLayout>
  );
};

// ── Stat card (matches AnalysisPage) ──────────────────────────────────────

const StatCard = ({ label, value, icon: Icon, color }) => {
  const colorClasses = {
    teal: "from-teal-50 to-teal-100",
    emerald: "from-emerald-50 to-emerald-100",
    amber: "from-amber-50 to-amber-100",
    slate: "from-slate-50 to-slate-100",
  };
  const iconColorClasses = {
    teal: "text-teal-600",
    emerald: "text-emerald-600",
    amber: "text-amber-600",
    slate: "text-slate-600",
  };
  return (
    <div className="bg-white rounded-2xl border border-slate-200 p-6 shadow-sm hover:shadow-md hover:border-slate-300 transition-all group">
      <div className="flex items-center justify-between">
        <div>
          <p className="text-sm font-semibold text-slate-600 mb-2">{label}</p>
          <p className="text-3xl font-bold text-slate-900">{value}</p>
        </div>
        <div
          className={`w-16 h-16 rounded-xl bg-gradient-to-br ${colorClasses[color]} flex items-center justify-center group-hover:shadow-md transition-all`}
        >
          <Icon className={`w-8 h-8 ${iconColorClasses[color]}`} />
        </div>
      </div>
    </div>
  );
};

const FilterChip = ({ active, onClick, label, count }) => (
  <button
    onClick={onClick}
    className={`inline-flex items-center gap-1.5 px-3.5 py-1.5 rounded-full text-sm font-semibold transition-all border ${
      active
        ? "bg-teal-600 text-white border-teal-600 shadow-sm"
        : "bg-white text-slate-700 border-slate-200 hover:border-slate-300 hover:bg-slate-50"
    }`}
  >
    {label}
    {count !== undefined && (
      <span
        className={`text-[11px] font-bold px-1.5 py-0.5 rounded ${
          active ? "bg-white/20 text-white" : "bg-slate-100 text-slate-500"
        }`}
      >
        {count}
      </span>
    )}
  </button>
);

export default ReportsPage;
