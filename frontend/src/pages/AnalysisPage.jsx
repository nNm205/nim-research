import { useState, useEffect, useMemo } from "react";
import { useNavigate } from "react-router-dom";
import DashboardLayout from "../components/layout/DashboardLayout";
import { projectService } from "../services/projectService";
import { analysisService } from "../services/analysisService";
import AnalysisCard from "../components/analysis/AnalysisCard";
import {
  Search,
  BarChart3,
  CheckCircle2,
  AlertCircle,
  Loader,
  Folder,
} from "lucide-react";

/**
 * Analysis page — aggregator only.
 *
 * Lists every analysis the user has run across every project. Triggering
 * a new analysis happens inside ProjectDetailPage where the project + the
 * available documents are already in scope.
 */
const AnalysisPage = () => {
  const navigate = useNavigate();
  const [projects, setProjects] = useState([]);
  const [analyses, setAnalyses] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [projectFilter, setProjectFilter] = useState("all");
  const [statusFilter, setStatusFilter] = useState("all");
  const [searchTerm, setSearchTerm] = useState("");

  useEffect(() => {
    async function loadAll() {
      try {
        setLoading(true);
        const [projectsData, analysesData] = await Promise.all([
          projectService.getProjects(),
          analysisService.getAllAnalyses(),
        ]);
        setProjects(projectsData.filter((p) => !p.is_archived));
        setAnalyses(analysesData);
        setError("");
      } catch (err) {
        setError("Không thể tải dữ liệu phân tích");
        console.error(err);
      } finally {
        setLoading(false);
      }
    }
    loadAll();
  }, []);

  // We don't have project_id directly on AnalysisListItemResponse, but
  // analyses include `document` shim with project_id when the backend
  // attaches it via selectinload. Read defensively: prefer document.project_id.
  const projectIdOf = (a) =>
    a.project_id || a.document?.project_id || null;

  const projectsById = useMemo(() => {
    const out = new Map();
    projects.forEach((p) => out.set(p.id, p));
    return out;
  }, [projects]);

  const stats = useMemo(
    () => ({
      total: analyses.length,
      completed: analyses.filter((a) => a.status === "completed").length,
      running: analyses.filter((a) => a.status === "running").length,
      failed: analyses.filter((a) => a.status === "failed").length,
    }),
    [analyses]
  );

  const filteredAnalyses = useMemo(() => {
    const q = searchTerm.trim().toLowerCase();
    return analyses.filter((a) => {
      const pid = projectIdOf(a);
      if (projectFilter !== "all" && pid !== projectFilter) return false;
      if (statusFilter !== "all" && a.status !== statusFilter) return false;
      if (q) {
        const hay = [a.document_title, a.id].join(" ").toLowerCase();
        if (!hay.includes(q)) return false;
      }
      return true;
    });
  }, [analyses, projectFilter, statusFilter, searchTerm]);

  return (
    <DashboardLayout>
      <div className="space-y-8">
        {/* Header */}
        <div>
          <h1 className="text-3xl font-bold text-slate-900">Phân tích tài liệu</h1>
          <p className="text-slate-600 mt-2">
            Tổng hợp toàn bộ phân tích AI bạn đã thực hiện. Để chạy phân
            tích mới, mở dự án tương ứng.
          </p>
        </div>

        {/* Stats */}
        <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
          <StatCard label="Tổng cộng" value={stats.total}     icon={BarChart3}    color="teal" />
          <StatCard label="Hoàn thành" value={stats.completed} icon={CheckCircle2} color="emerald" />
          <StatCard label="Đang chạy"  value={stats.running}   icon={Loader}       color="blue" />
          <StatCard label="Thất bại"   value={stats.failed}    icon={AlertCircle}  color="red" />
        </div>

        {/* Error */}
        {error && (
          <div className="flex items-start gap-3 bg-red-50 border border-red-200 text-red-700 px-6 py-4 rounded-xl">
            <AlertCircle className="w-5 h-5 flex-shrink-0 mt-0.5" />
            <span className="text-sm font-medium">{error}</span>
          </div>
        )}

        {/* No projects */}
        {!loading && projects.length === 0 && (
          <div className="text-center py-16 bg-white rounded-2xl border border-slate-200 shadow-sm">
            <BarChart3 className="w-16 h-16 text-slate-300 mx-auto mb-4" />
            <h3 className="text-xl font-bold text-slate-900 mb-2">
              Chưa có dự án nào
            </h3>
            <p className="text-slate-600 mb-8">
              Tạo dự án và thêm tài liệu trước khi chạy phân tích.
            </p>
            <button
              onClick={() => navigate("/projects")}
              className="inline-flex items-center gap-2 px-6 py-3 bg-gradient-to-r from-teal-600 to-teal-700 hover:from-teal-700 hover:to-teal-800 text-white rounded-xl font-semibold transition-all shadow-lg hover:shadow-xl"
            >
              Mở trang Dự án
            </button>
          </div>
        )}

        {/* Filters — visible whenever there are projects to filter by,
            even if no analyses have been run yet. */}
        {!loading && projects.length > 0 && (
          <div className="space-y-4">
            <div className="relative">
              <Search className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-slate-400" />
              <input
                type="text"
                placeholder="Tìm kiếm phân tích..."
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
                count={analyses.length}
              />
              {projects.map((p) => {
                const c = analyses.filter(
                  (a) => projectIdOf(a) === p.id
                ).length;
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
                active={statusFilter === "completed"}
                onClick={() => setStatusFilter("completed")}
                label="Hoàn thành"
                count={stats.completed}
              />
              <FilterChip
                active={statusFilter === "running"}
                onClick={() => setStatusFilter("running")}
                label="Đang chạy"
                count={stats.running}
              />
              <FilterChip
                active={statusFilter === "failed"}
                onClick={() => setStatusFilter("failed")}
                label="Thất bại"
                count={stats.failed}
              />
            </div>
          </div>
        )}

        {/* Loading */}
        {loading && (
          <div className="text-center py-16">
            <div className="w-12 h-12 border-4 border-teal-200 border-t-teal-600 rounded-full animate-spin mx-auto mb-4" />
            <p className="text-slate-600 font-medium">
              Đang tải dữ liệu phân tích...
            </p>
          </div>
        )}

        {/* List */}
        {!loading && filteredAnalyses.length > 0 && (
          <div className="space-y-4">
            {filteredAnalyses.map((analysis) => {
              const pid = projectIdOf(analysis);
              const projectName = pid ? projectsById.get(pid)?.name : null;
              return (
                <AnalysisCard
                  key={analysis.id}
                  analysis={analysis}
                  projectName={projectName}
                  onClick={() => navigate(`/analysis/${analysis.id}`)}
                />
              );
            })}
          </div>
        )}

        {/* Empty after filter */}
        {!loading &&
          analyses.length > 0 &&
          filteredAnalyses.length === 0 && (
            <div className="text-center py-12 bg-slate-50 rounded-xl border border-slate-200">
              <Search className="w-12 h-12 text-slate-300 mx-auto mb-3" />
              <p className="text-slate-600">
                Không có phân tích nào khớp bộ lọc
              </p>
            </div>
          )}

        {/* Empty when no analyses at all */}
        {!loading && projects.length > 0 && analyses.length === 0 && (
          <div className="text-center py-16 bg-white rounded-2xl border border-slate-200 shadow-sm">
            <BarChart3 className="w-16 h-16 text-slate-300 mx-auto mb-4" />
            <h3 className="text-xl font-bold text-slate-900 mb-2">
              Chưa có phân tích nào
            </h3>
            <p className="text-slate-600 mb-8">
              Mở một dự án có tài liệu để bắt đầu phân tích đầu tiên.
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

const StatCard = ({ label, value, icon: Icon, color }) => {
  const colorClasses = {
    teal: "from-teal-50 to-teal-100",
    emerald: "from-emerald-50 to-emerald-100",
    blue: "from-blue-50 to-blue-100",
    red: "from-red-50 to-red-100",
  };
  const iconColorClasses = {
    teal: "text-teal-600",
    emerald: "text-emerald-600",
    blue: "text-blue-600",
    red: "text-red-600",
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

export default AnalysisPage;
