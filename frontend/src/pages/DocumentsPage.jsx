import { useState, useEffect, useMemo } from "react";
import { useNavigate } from "react-router-dom";
import {
  FileText,
  CheckCircle2,
  Clock,
  AlertCircle,
  Folder,
  Search,
} from "lucide-react";
import DashboardLayout from "../components/layout/DashboardLayout";
import { projectService } from "../services/projectService";
import { documentService } from "../services/documentService";
import DocumentCard from "../components/documents/DocumentCard";

/**
 * Documents page — aggregator only.
 *
 * Fetches every document the user owns across every project in a single
 * request to ``/api/v1/documents`` and lets the user filter / search
 * client-side. Adding a document happens inside ProjectDetailPage where
 * the project context is already known.
 */
const DocumentsPage = () => {
  const navigate = useNavigate();

  const [projects, setProjects] = useState([]);
  const [documents, setDocuments] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [projectFilter, setProjectFilter] = useState("all"); // "all" | projectId
  const [searchTerm, setSearchTerm] = useState("");
  const [statusFilter, setStatusFilter] = useState("all"); // "all" | "processed" | "unprocessed"

  useEffect(() => {
    async function loadAll() {
      try {
        setLoading(true);
        const [projectsData, documentsData] = await Promise.all([
          projectService.getProjects(),
          documentService.getAllDocuments(),
        ]);
        setProjects(projectsData.filter((p) => !p.is_archived));
        setDocuments(documentsData);
        setError("");
      } catch (err) {
        setError("Không thể tải danh sách tài liệu");
        console.error(err);
      } finally {
        setLoading(false);
      }
    }
    loadAll();
  }, []);

  // Map projectId → project for fast lookup when rendering meta on each card.
  const projectsById = useMemo(() => {
    const out = new Map();
    projects.forEach((p) => out.set(p.id, p));
    return out;
  }, [projects]);

  const filteredDocuments = useMemo(() => {
    const q = searchTerm.trim().toLowerCase();
    return documents.filter((d) => {
      if (projectFilter !== "all" && d.project_id !== projectFilter)
        return false;
      if (statusFilter === "processed" && !d.processed) return false;
      if (statusFilter === "unprocessed" && d.processed) return false;
      if (q && !d.title?.toLowerCase().includes(q)) return false;
      return true;
    });
  }, [documents, projectFilter, statusFilter, searchTerm]);

  const stats = useMemo(
    () => ({
      total: documents.length,
      processed: documents.filter((d) => d.processed).length,
      unprocessed: documents.filter((d) => !d.processed).length,
      visible: filteredDocuments.length,
    }),
    [documents, filteredDocuments]
  );

  return (
    <DashboardLayout>
      <div className="space-y-8">
        {/* Header */}
        <div>
          <h1 className="text-3xl font-bold text-slate-900">Tài liệu</h1>
          <p className="text-slate-600 mt-2">
            Tổng hợp toàn bộ tài liệu bạn đã upload. Để thêm tài liệu mới,
            mở dự án tương ứng.
          </p>
        </div>

        {/* Stats */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          <StatCard
            label="Tổng tài liệu"
            value={stats.total}
            icon={FileText}
            color="teal"
          />
          <StatCard
            label="Đã xử lý"
            value={stats.processed}
            icon={CheckCircle2}
            color="emerald"
          />
          <StatCard
            label="Chưa xử lý"
            value={stats.unprocessed}
            icon={Clock}
            color="amber"
          />
        </div>

        {/* Error banner */}
        {error && (
          <div className="flex items-start gap-3 bg-red-50 border border-red-200 text-red-700 px-6 py-4 rounded-xl">
            <AlertCircle className="w-5 h-5 flex-shrink-0 mt-0.5" />
            <span className="text-sm font-medium">{error}</span>
          </div>
        )}

        {/* No projects */}
        {!loading && projects.length === 0 && (
          <div className="text-center py-16 bg-white rounded-2xl border border-slate-200 shadow-sm">
            <Folder className="w-16 h-16 text-slate-300 mx-auto mb-4" />
            <h3 className="text-xl font-bold text-slate-900 mb-2">
              Chưa có dự án nào
            </h3>
            <p className="text-slate-600 mb-8">
              Tạo dự án rồi thêm tài liệu bên trong dự án đó.
            </p>
            <button
              onClick={() => navigate("/projects")}
              className="inline-flex items-center gap-2 px-6 py-3 bg-gradient-to-r from-teal-600 to-teal-700 hover:from-teal-700 hover:to-teal-800 text-white rounded-xl font-semibold transition-all shadow-lg hover:shadow-xl"
            >
              Mở trang Dự án
            </button>
          </div>
        )}

        {/* Filters: search + project chips + status chips */}
        {!loading && projects.length > 0 && (
          <div className="space-y-4">
            <div className="relative">
              <Search className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-slate-400" />
              <input
                type="text"
                placeholder="Tìm kiếm theo tiêu đề..."
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
                count={documents.length}
              />
              {projects.map((p) => (
                <FilterChip
                  key={p.id}
                  active={projectFilter === p.id}
                  onClick={() => setProjectFilter(p.id)}
                  label={p.name}
                  count={documents.filter((d) => d.project_id === p.id).length}
                />
              ))}
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
                active={statusFilter === "processed"}
                onClick={() => setStatusFilter("processed")}
                label="Đã xử lý"
                count={stats.processed}
              />
              <FilterChip
                active={statusFilter === "unprocessed"}
                onClick={() => setStatusFilter("unprocessed")}
                label="Chưa xử lý"
                count={stats.unprocessed}
              />
            </div>
          </div>
        )}

        {/* Loading */}
        {loading && (
          <div className="text-center py-16">
            <div className="w-12 h-12 border-4 border-teal-200 border-t-teal-600 rounded-full animate-spin mx-auto mb-4" />
            <p className="text-slate-600 font-medium">Đang tải tài liệu...</p>
          </div>
        )}

        {/* Grid */}
        {!loading && filteredDocuments.length > 0 && (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {filteredDocuments.map((doc) => (
              <DocumentCard
                key={doc.id}
                document={doc}
                projectName={projectsById.get(doc.project_id)?.name}
                onClick={() =>
                  navigate(`/projects/${doc.project_id}/documents/${doc.id}`)
                }
              />
            ))}
          </div>
        )}

        {/* Empty after filter */}
        {!loading &&
          documents.length > 0 &&
          filteredDocuments.length === 0 && (
            <div className="text-center py-12 bg-slate-50 rounded-xl border border-slate-200">
              <Search className="w-12 h-12 text-slate-300 mx-auto mb-3" />
              <p className="text-slate-600">
                Không có tài liệu nào khớp bộ lọc
              </p>
            </div>
          )}

        {/* Empty when no documents at all */}
        {!loading && documents.length === 0 && projects.length > 0 && (
          <div className="text-center py-16 bg-white rounded-2xl border border-slate-200 shadow-sm">
            <FileText className="w-16 h-16 text-slate-300 mx-auto mb-4" />
            <h3 className="text-xl font-bold text-slate-900 mb-2">
              Chưa có tài liệu nào
            </h3>
            <p className="text-slate-600 mb-8">
              Mở một dự án để upload tài liệu đầu tiên.
            </p>
            <button
              onClick={() => navigate("/projects")}
              className="inline-flex items-center gap-2 px-6 py-3 bg-gradient-to-r from-teal-600 to-teal-700 hover:from-teal-700 hover:to-teal-800 text-white rounded-xl font-semibold transition-all shadow-lg hover:shadow-xl"
            >
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
    amber: "from-amber-50 to-amber-100",
  };
  const iconColorClasses = {
    teal: "text-teal-600",
    emerald: "text-emerald-600",
    amber: "text-amber-600",
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

export default DocumentsPage;