import { useState, useEffect, useMemo } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "../hooks/useAuth";
import DashboardLayout from "../components/layout/DashboardLayout";
import { projectService } from "../services/projectService";
import { notificationService } from "../services/notificationService";
import {
  FileText,
  BarChart3,
  ClipboardList,
  Plus,
  Wand2,
  Search,
  Folder,
  Clock,
  CheckCircle2,
  AlertCircle,
  ArrowRight,
  Loader,
  Info,
  Sparkles,
  TrendingUp,
} from "lucide-react";

/**
 * DashboardPage — landing screen.
 *
 * Performance:
 *
 *   The previous implementation made N+1 round-trips: one
 *   ``GET /projects``, then for the first three projects it called
 *   ``/documents``, ``/analyses``, ``/reports`` — all sequentially
 *   inside a ``for`` loop. That meant up to 10 sequential network
 *   round-trips before the page could render, and totals were wrong
 *   (only counted top three projects).
 *
 *   The fix:
 *
 *   1. ``GET /api/v1/projects/`` already returns ``document_count``,
 *      ``research_session_count``, ``analysis_count``, ``report_count``
 *      for every project (via ``_annotate_counts``). We derive every
 *      dashboard stat from that single response — no per-project
 *      fan-out.
 *   2. ``GET /api/v1/notifications`` gives us the real recent-activity
 *      feed (task completed / failed events) with deep links, so we
 *      drop the synthesised "X tài liệu gần đây" placeholder rows.
 *   3. The two requests run in parallel via ``Promise.all``.
 *
 *   Result: 2 parallel requests instead of 10 sequential, and the
 *   numbers are correct across every project.
 */

const DashboardPage = () => {
  const { user } = useAuth();
  const navigate = useNavigate();

  const [projects, setProjects] = useState([]);
  const [activities, setActivities] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        setLoading(true);
        const [projectsData, notifData] = await Promise.all([
          projectService.getProjects(),
          notificationService
            .list({ limit: 6 })
            .catch(() => ({ notifications: [] })),
        ]);
        if (cancelled) return;
        setProjects(projectsData || []);
        setActivities(notifData.notifications || []);
        setError("");
      } catch (err) {
        if (!cancelled) {
          setError("Không thể tải dữ liệu dashboard");
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

  // Aggregate stats across every (active) project. Counts come straight
  // off ``ProjectResponse`` so this is an O(N) reduce on a list usually
  // shorter than 50.
  const stats = useMemo(() => {
    const active = projects.filter((p) => !p.is_archived);
    return {
      projects: active.length,
      archived: projects.length - active.length,
      documents: active.reduce(
        (sum, p) => sum + (p.document_count || 0),
        0
      ),
      analyses: active.reduce(
        (sum, p) => sum + (p.analysis_count || 0),
        0
      ),
      reports: active.reduce(
        (sum, p) => sum + (p.report_count || 0),
        0
      ),
      research: active.reduce(
        (sum, p) => sum + (p.research_session_count || 0),
        0
      ),
    };
  }, [projects]);

  // Most recently updated active projects — best proxy for "what was I
  // working on?" without an extra endpoint.
  const recentProjects = useMemo(() => {
    return projects
      .filter((p) => !p.is_archived)
      .slice()
      .sort(
        (a, b) =>
          new Date(b.updated_at || b.created_at) -
          new Date(a.updated_at || a.created_at)
      )
      .slice(0, 4);
  }, [projects]);

  return (
    <DashboardLayout>
      <div className="space-y-8">
        {/* ── Welcome banner ────────────────────────────────────────── */}
        <div className="relative overflow-hidden rounded-2xl bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900 p-8 text-white shadow-lg">
          <div className="absolute right-0 top-0 -mr-32 -mt-32 h-64 w-64 rounded-full bg-teal-500 opacity-10 blur-3xl"></div>
          <div className="relative z-10">
            <h1 className="text-3xl md:text-4xl font-bold mb-3">
              Chào mừng, {user?.full_name || "User"}
            </h1>
            <p className="text-slate-300 text-base md:text-lg">
              {stats.projects > 0
                ? `Bạn đang có ${stats.projects} dự án — tiếp tục nghiên cứu nhé.`
                : "Tạo dự án đầu tiên để bắt đầu nghiên cứu."}
            </p>
          </div>
        </div>

        {/* Error banner */}
        {error && (
          <div className="flex items-start gap-3 bg-red-50 border border-red-200 text-red-700 px-6 py-4 rounded-xl">
            <AlertCircle className="w-5 h-5 flex-shrink-0 mt-0.5" />
            <span className="text-sm font-medium">{error}</span>
          </div>
        )}

        {/* ── Stats grid ────────────────────────────────────────────── */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 md:gap-6">
          <StatCard
            title="Dự án"
            value={stats.projects}
            sub={
              stats.archived > 0
                ? `+ ${stats.archived} đã lưu trữ`
                : "đang hoạt động"
            }
            icon={Folder}
            color="teal"
            href="/projects"
            loading={loading}
          />
          <StatCard
            title="Tài liệu"
            value={stats.documents}
            sub="trên toàn bộ dự án"
            icon={FileText}
            color="blue"
            href="/documents"
            loading={loading}
          />
          <StatCard
            title="Phân tích"
            value={stats.analyses}
            sub="đã chạy"
            icon={BarChart3}
            color="violet"
            href="/analysis"
            loading={loading}
          />
          <StatCard
            title="Báo cáo"
            value={stats.reports}
            sub="đã tạo"
            icon={ClipboardList}
            color="emerald"
            href="/reports"
            loading={loading}
          />
        </div>

        {/* ── Main grid ─────────────────────────────────────────────── */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 md:gap-8">
          {/* Left — quick actions + recent projects */}
          <div className="lg:col-span-2 space-y-6 md:space-y-8">
            {/* Quick actions */}
            <Panel title="Thao tác nhanh" icon={Sparkles}>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <QuickActionCard
                  icon={Plus}
                  title="Dự án mới"
                  description="Bắt đầu một dự án nghiên cứu"
                  onClick={() => navigate("/projects")}
                  accent="teal"
                />
                <QuickActionCard
                  icon={Wand2}
                  title="Nghiên cứu tự động"
                  description="Tìm + nạp + phân tích trong 1 lần"
                  onClick={() => navigate("/projects")}
                  accent="violet"
                />
              </div>
            </Panel>

            {/* Recent projects */}
            <Panel
              title="Dự án gần đây"
              icon={Folder}
              action={
                projects.length > 0 && (
                  <Link
                    to="/projects"
                    className="text-sm font-semibold text-teal-600 hover:text-teal-700 inline-flex items-center gap-1.5 transition-colors group"
                  >
                    Xem tất cả
                    <ArrowRight className="w-4 h-4 group-hover:translate-x-1 transition-transform" />
                  </Link>
                )
              }
            >
              {loading ? (
                <SkeletonGrid count={4} />
              ) : recentProjects.length === 0 ? (
                <div className="text-center py-12">
                  <Folder className="w-12 h-12 text-slate-300 mx-auto mb-3" />
                  <p className="text-slate-600 mb-4 font-medium">
                    Chưa có dự án nào
                  </p>
                  <button
                    onClick={() => navigate("/projects")}
                    className="inline-flex items-center gap-2 px-5 py-2.5 bg-gradient-to-r from-teal-600 to-teal-700 hover:from-teal-700 hover:to-teal-800 text-white rounded-xl font-semibold transition-all shadow-md"
                  >
                    <Plus className="w-4 h-4" />
                    Tạo dự án đầu tiên
                  </button>
                </div>
              ) : (
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  {recentProjects.map((p) => (
                    <ProjectMiniCard key={p.id} project={p} />
                  ))}
                </div>
              )}
            </Panel>
          </div>

          {/* Right — recent activity feed (notifications) */}
          <Panel
            title="Hoạt động gần đây"
            icon={Clock}
            className="h-fit lg:sticky lg:top-24"
          >
            {loading ? (
              <SkeletonList count={4} />
            ) : activities.length === 0 ? (
              <div className="text-center py-10">
                <Info className="w-10 h-10 text-slate-300 mx-auto mb-3" />
                <p className="text-sm text-slate-500">
                  Chưa có hoạt động nào.
                </p>
                <p className="text-xs text-slate-400 mt-1">
                  Thông báo sẽ xuất hiện khi tác vụ hoàn thành.
                </p>
              </div>
            ) : (
              <ul className="space-y-3">
                {activities.map((a) => (
                  <ActivityRow key={a.id} notification={a} />
                ))}
              </ul>
            )}
          </Panel>
        </div>
      </div>
    </DashboardLayout>
  );
};

// ── Sub-components ────────────────────────────────────────────────────────

const Panel = ({ title, icon: Icon, action, className = "", children }) => (
  <section
    className={`bg-white rounded-2xl border border-slate-200 p-6 md:p-8 shadow-sm hover:shadow-md transition-shadow ${className}`}
  >
    <div className="flex items-center justify-between mb-5">
      <div className="flex items-center gap-2">
        {Icon && <Icon className="w-5 h-5 text-teal-600" />}
        <h2 className="text-lg md:text-xl font-bold text-slate-900">{title}</h2>
      </div>
      {action}
    </div>
    {children}
  </section>
);

const COLOR_MAP = {
  teal: {
    icon: "text-teal-600",
    bg: "from-teal-50 to-teal-100",
    hoverBg: "group-hover:from-teal-100 group-hover:to-teal-200",
  },
  blue: {
    icon: "text-blue-600",
    bg: "from-blue-50 to-blue-100",
    hoverBg: "group-hover:from-blue-100 group-hover:to-blue-200",
  },
  violet: {
    icon: "text-violet-600",
    bg: "from-violet-50 to-violet-100",
    hoverBg: "group-hover:from-violet-100 group-hover:to-violet-200",
  },
  emerald: {
    icon: "text-emerald-600",
    bg: "from-emerald-50 to-emerald-100",
    hoverBg: "group-hover:from-emerald-100 group-hover:to-emerald-200",
  },
  amber: {
    icon: "text-amber-600",
    bg: "from-amber-50 to-amber-100",
    hoverBg: "group-hover:from-amber-100 group-hover:to-amber-200",
  },
};

const StatCard = ({ title, value, sub, icon: Icon, color, href, loading }) => {
  const c = COLOR_MAP[color] || COLOR_MAP.teal;
  const inner = (
    <div className="bg-white rounded-2xl border border-slate-200 p-5 md:p-6 shadow-sm hover:shadow-md hover:border-slate-300 transition-all group cursor-pointer h-full">
      <div className="flex items-center justify-between mb-4">
        <div
          className={`w-12 h-12 md:w-14 md:h-14 rounded-xl bg-gradient-to-br ${c.bg} ${c.hoverBg} flex items-center justify-center transition-all`}
        >
          <Icon className={`w-6 h-6 md:w-7 md:h-7 ${c.icon}`} />
        </div>
      </div>
      <div className="space-y-1.5">
        <p className="text-xs md:text-sm font-semibold text-slate-600">
          {title}
        </p>
        {loading ? (
          <div className="h-9 w-16 bg-slate-100 rounded animate-pulse" />
        ) : (
          <p className="text-2xl md:text-3xl font-bold text-slate-900 tabular-nums">
            {value}
          </p>
        )}
        <p className="text-xs text-slate-500">{sub}</p>
      </div>
    </div>
  );
  return href ? (
    <Link to={href} className="block h-full">
      {inner}
    </Link>
  ) : (
    inner
  );
};

const QuickActionCard = ({ icon: Icon, title, description, onClick, accent }) => {
  const c = COLOR_MAP[accent] || COLOR_MAP.teal;
  return (
    <button
      onClick={onClick}
      className="text-left p-5 border-2 border-slate-200 rounded-xl hover:border-teal-300 hover:bg-teal-50/40 transition-all group focus:outline-none focus:ring-2 focus:ring-teal-500 focus:ring-offset-2"
    >
      <div
        className={`w-11 h-11 rounded-lg bg-gradient-to-br ${c.bg} flex items-center justify-center mb-3 ${c.hoverBg} transition-all`}
      >
        <Icon className={`w-5 h-5 ${c.icon}`} />
      </div>
      <h3 className="font-semibold text-slate-900 mb-1 group-hover:text-teal-700 transition-colors">
        {title}
      </h3>
      <p className="text-sm text-slate-600 leading-snug">{description}</p>
    </button>
  );
};

const ProjectMiniCard = ({ project }) => {
  const docs = project.document_count || 0;
  const ana = project.analysis_count || 0;
  const reps = project.report_count || 0;
  const formatDate = (dateString) => {
    if (!dateString) return "—";
    const d = new Date(dateString);
    const today = new Date();
    const yesterday = new Date(today);
    yesterday.setDate(yesterday.getDate() - 1);
    if (d.toDateString() === today.toDateString()) return "Hôm nay";
    if (d.toDateString() === yesterday.toDateString()) return "Hôm qua";
    return d.toLocaleDateString("vi-VN", {
      day: "2-digit",
      month: "2-digit",
      year: "numeric",
    });
  };

  return (
    <Link
      to={`/projects/${project.id}`}
      className="block border border-slate-200 rounded-xl p-5 hover:border-teal-300 hover:shadow-md hover:bg-teal-50/30 transition-all group"
    >
      <div className="flex items-start justify-between gap-3 mb-3">
        <h3 className="font-semibold text-slate-900 group-hover:text-teal-700 transition-colors line-clamp-1 flex-1 min-w-0">
          {project.name}
        </h3>
        {project.status === "completed" && (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-bold bg-emerald-100 text-emerald-700 flex-shrink-0">
            <CheckCircle2 className="w-3 h-3" />
            Hoàn thành
          </span>
        )}
      </div>

      <p className="text-sm text-slate-600 line-clamp-2 min-h-[2.5rem] mb-4">
        {project.description || project.topic || "Không có mô tả"}
      </p>

      {/* Real counts instead of fake "progress" */}
      <div className="flex items-center gap-3 mb-3 flex-wrap">
        <CountChip icon={FileText} value={docs} label="tài liệu" />
        <CountChip
          icon={BarChart3}
          value={ana}
          label="phân tích"
          tone="violet"
        />
        <CountChip
          icon={ClipboardList}
          value={reps}
          label="báo cáo"
          tone="emerald"
        />
      </div>

      <div className="flex items-center justify-between pt-3 border-t border-slate-100">
        <p className="text-[11px] text-slate-500 inline-flex items-center gap-1">
          <Clock className="w-3 h-3" />
          Cập nhật: {formatDate(project.updated_at || project.created_at)}
        </p>
        <ArrowRight className="w-4 h-4 text-slate-400 group-hover:text-teal-600 group-hover:translate-x-1 transition-all" />
      </div>
    </Link>
  );
};

const CHIP_TONE = {
  slate: "bg-slate-50 text-slate-600 border-slate-200",
  violet: "bg-violet-50 text-violet-600 border-violet-200",
  emerald: "bg-emerald-50 text-emerald-600 border-emerald-200",
};

const CountChip = ({ icon: Icon, value, label, tone = "slate" }) => (
  <span
    className={`inline-flex items-center gap-1 px-2 py-1 rounded-md border text-[11px] font-semibold ${CHIP_TONE[tone]}`}
  >
    <Icon className="w-3 h-3" />
    <span className="tabular-nums">{value}</span>
    <span className="font-normal text-slate-500 hidden sm:inline">
      {label}
    </span>
  </span>
);

// ── Activity row (driven by real notifications) ──────────────────────────

const ACTIVITY_META = {
  analysis: {
    icon: BarChart3,
    href: (n) => (n.entity_id ? `/analysis/${n.entity_id}` : null),
    accent: "text-violet-600 bg-violet-50",
  },
  research: {
    icon: Search,
    href: (n) =>
      n.project_id ? `/projects/${n.project_id}/research` : null,
    accent: "text-blue-600 bg-blue-50",
  },
  auto_research: {
    icon: Wand2,
    href: (n) => (n.project_id ? `/projects/${n.project_id}` : null),
    accent: "text-fuchsia-600 bg-fuchsia-50",
  },
  report: {
    icon: ClipboardList,
    href: (n) => (n.entity_id ? `/reports/${n.entity_id}` : null),
    accent: "text-teal-600 bg-teal-50",
  },
  document: {
    icon: FileText,
    href: (n) =>
      n.entity_id && n.project_id
        ? `/projects/${n.project_id}/documents/${n.entity_id}`
        : null,
    accent: "text-amber-600 bg-amber-50",
  },
  general: {
    icon: Info,
    href: () => null,
    accent: "text-slate-600 bg-slate-50",
  },
};

const STATUS_PILL = {
  success: { bg: "bg-emerald-50", text: "text-emerald-700", icon: CheckCircle2 },
  error: { bg: "bg-red-50", text: "text-red-700", icon: AlertCircle },
  info: { bg: "bg-slate-100", text: "text-slate-600", icon: Info },
};

const formatRelative = (iso) => {
  if (!iso) return "";
  const now = new Date();
  const d = new Date(iso);
  const diffSec = Math.floor((now - d) / 1000);
  if (diffSec < 60) return "vừa xong";
  const diffMin = Math.floor(diffSec / 60);
  if (diffMin < 60) return `${diffMin} phút trước`;
  const diffHour = Math.floor(diffMin / 60);
  if (diffHour < 24) return `${diffHour} giờ trước`;
  const diffDay = Math.floor(diffHour / 24);
  if (diffDay < 7) return `${diffDay} ngày trước`;
  return d.toLocaleDateString("vi-VN", {
    day: "2-digit",
    month: "2-digit",
  });
};

const ActivityRow = ({ notification: n }) => {
  const navigate = useNavigate();
  const meta = ACTIVITY_META[n.category] || ACTIVITY_META.general;
  const TypeIcon = meta.icon;
  const status = STATUS_PILL[n.notification_type] || STATUS_PILL.info;
  const StatusIcon = status.icon;
  const href = meta.href(n);

  return (
    <li>
      <button
        onClick={() => href && navigate(href)}
        disabled={!href}
        className={`w-full flex gap-3 p-3 rounded-lg text-left transition-colors ${
          href
            ? "hover:bg-slate-50 cursor-pointer"
            : "cursor-default"
        } ${!n.is_read ? "bg-teal-50/40" : ""}`}
      >
        <div
          className={`flex-shrink-0 w-9 h-9 rounded-lg ${meta.accent} flex items-center justify-center`}
        >
          <TypeIcon className="w-4 h-4" />
        </div>
        <div className="flex-1 min-w-0">
          <p className="text-sm font-semibold text-slate-900 line-clamp-1">
            {n.title}
          </p>
          {n.message && (
            <p className="text-xs text-slate-500 mt-0.5 line-clamp-2">
              {n.message}
            </p>
          )}
          <p className="text-[11px] text-slate-400 mt-1">
            {formatRelative(n.created_at)}
          </p>
        </div>
        <div
          className={`flex-shrink-0 self-start px-2 py-1 rounded-md flex items-center gap-1 ${status.bg}`}
        >
          <StatusIcon className={`w-3 h-3 ${status.text}`} />
        </div>
      </button>
    </li>
  );
};

// ── Skeletons ────────────────────────────────────────────────────────────

const SkeletonGrid = ({ count = 4 }) => (
  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
    {Array.from({ length: count }).map((_, i) => (
      <div
        key={i}
        className="border border-slate-200 rounded-xl p-5 animate-pulse"
      >
        <div className="h-5 w-2/3 bg-slate-100 rounded mb-3" />
        <div className="h-3 w-full bg-slate-100 rounded mb-2" />
        <div className="h-3 w-3/4 bg-slate-100 rounded mb-4" />
        <div className="flex gap-2">
          <div className="h-5 w-16 bg-slate-100 rounded" />
          <div className="h-5 w-16 bg-slate-100 rounded" />
          <div className="h-5 w-16 bg-slate-100 rounded" />
        </div>
      </div>
    ))}
  </div>
);

const SkeletonList = ({ count = 4 }) => (
  <ul className="space-y-3">
    {Array.from({ length: count }).map((_, i) => (
      <li
        key={i}
        className="flex gap-3 p-3 rounded-lg animate-pulse"
      >
        <div className="w-9 h-9 rounded-lg bg-slate-100 flex-shrink-0" />
        <div className="flex-1 space-y-2">
          <div className="h-3 w-3/4 bg-slate-100 rounded" />
          <div className="h-3 w-1/2 bg-slate-100 rounded" />
        </div>
      </li>
    ))}
  </ul>
);

export default DashboardPage;
