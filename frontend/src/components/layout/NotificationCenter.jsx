import { useState, useEffect, useRef, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import {
  Bell,
  Check,
  CheckCircle2,
  AlertCircle,
  Info,
  X,
  Trash2,
  ClipboardList,
  BarChart3,
  Search,
  Wand2,
  FileText,
  Loader,
} from "lucide-react";
import { notificationService } from "../../services/notificationService";

/**
 * NotificationCenter — header bell + dropdown panel.
 *
 * Polls the backend every 15s for new notifications, renders the
 * unread badge, and lets the user open a dropdown to read / dismiss.
 *
 * Design choices:
 *   - Polling instead of websockets: the rest of the app is HTTP, and
 *     the backend persists notifications anyway, so a 15 s polling
 *     window is plenty responsive for "task done" alerts.
 *   - Click on a row navigates to the source entity (analysis / report
 *     / research session) and marks it read in one shot.
 *   - "Mark all read" + "Clear all" live in the panel footer for bulk
 *     hygiene.
 *
 * The dropdown is positioned absolutely below the bell. Scroll inside
 * the panel rather than the page so the rest of the layout stays put.
 */

const POLL_INTERVAL_MS = 15_000;
const MAX_DISPLAY = 30;

// Per-category visual + nav config. ``deepLink`` returns a path the
// navigator should send the user to when a row is clicked.
const CATEGORY_META = {
  analysis: {
    label: "Phân tích",
    icon: BarChart3,
    accent: "text-violet-600 bg-violet-50",
    deepLink: (n) => (n.entity_id ? `/analysis/${n.entity_id}` : null),
  },
  research: {
    label: "Tìm kiếm",
    icon: Search,
    accent: "text-blue-600 bg-blue-50",
    deepLink: (n) =>
      n.project_id ? `/projects/${n.project_id}/research` : null,
  },
  auto_research: {
    label: "Nghiên cứu tự động",
    icon: Wand2,
    accent: "text-fuchsia-600 bg-fuchsia-50",
    deepLink: (n) =>
      n.project_id ? `/projects/${n.project_id}` : null,
  },
  report: {
    label: "Báo cáo",
    icon: ClipboardList,
    accent: "text-teal-600 bg-teal-50",
    deepLink: (n) => (n.entity_id ? `/reports/${n.entity_id}` : null),
  },
  document: {
    label: "Tài liệu",
    icon: FileText,
    accent: "text-amber-600 bg-amber-50",
    deepLink: (n) =>
      n.entity_id && n.project_id
        ? `/projects/${n.project_id}/documents/${n.entity_id}`
        : n.project_id
        ? `/projects/${n.project_id}`
        : null,
  },
  general: {
    label: "Khác",
    icon: Info,
    accent: "text-slate-600 bg-slate-50",
    deepLink: () => null,
  },
};

const TYPE_BORDER = {
  success: "border-l-emerald-400",
  error: "border-l-red-400",
  info: "border-l-slate-300",
};

const TYPE_ICON = {
  success: CheckCircle2,
  error: AlertCircle,
  info: Info,
};

const TYPE_ICON_TONE = {
  success: "text-emerald-600",
  error: "text-red-600",
  info: "text-slate-500",
};

// ── Time formatter — "vừa xong / 5 phút trước / 2 giờ trước / ngày DD/MM"
function formatRelative(iso) {
  if (!iso) return "";
  const now = new Date();
  const d = new Date(iso);
  const diffMs = now - d;
  const diffSec = Math.floor(diffMs / 1000);
  if (diffSec < 30) return "vừa xong";
  if (diffSec < 60) return `${diffSec} giây trước`;
  const diffMin = Math.floor(diffSec / 60);
  if (diffMin < 60) return `${diffMin} phút trước`;
  const diffHour = Math.floor(diffMin / 60);
  if (diffHour < 24) return `${diffHour} giờ trước`;
  const diffDay = Math.floor(diffHour / 24);
  if (diffDay < 7) return `${diffDay} ngày trước`;
  return d.toLocaleDateString("vi-VN", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
  });
}

const NotificationCenter = () => {
  const navigate = useNavigate();
  const [open, setOpen] = useState(false);
  const [notifications, setNotifications] = useState([]);
  const [unreadCount, setUnreadCount] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const wrapperRef = useRef(null);

  // Track ``open`` via a ref so the polling effect stays stable across
  // toggle cycles (otherwise ``refresh`` would change identity and the
  // 15 s interval would tear down + restart on every open/close).
  const openRef = useRef(open);
  useEffect(() => {
    openRef.current = open;
  }, [open]);

  // ── Polling ──────────────────────────────────────────────────────────
  const refresh = useCallback(async ({ silent = false } = {}) => {
    try {
      if (!silent) setLoading(true);
      const data = await notificationService.list({ limit: MAX_DISPLAY });
      setNotifications(data.notifications || []);
      setUnreadCount(data.unread_count || 0);
      setError("");
    } catch (err) {
      // Don't spam errors during polling — the user might briefly be
      // offline or unauthenticated. Only surface inside the panel when
      // it's open so they have somewhere to look.
      if (openRef.current) setError("Không tải được thông báo");
      console.error(err);
    } finally {
      if (!silent) setLoading(false);
    }
  }, []);

  useEffect(() => {
    refresh();
    const handle = setInterval(() => refresh({ silent: true }), POLL_INTERVAL_MS);
    return () => clearInterval(handle);
  }, [refresh]);

  // ── Outside click / Escape ──────────────────────────────────────────
  useEffect(() => {
    if (!open) return undefined;
    const onClick = (e) => {
      if (wrapperRef.current && !wrapperRef.current.contains(e.target)) {
        setOpen(false);
      }
    };
    const onKey = (e) => {
      if (e.key === "Escape") setOpen(false);
    };
    document.addEventListener("mousedown", onClick);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onClick);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  // ── Handlers ────────────────────────────────────────────────────────
  const handleOpen = () => {
    setOpen((v) => !v);
    if (!open) {
      // Refresh on open so the user sees the latest state without
      // waiting for the next polling tick.
      refresh({ silent: true });
    }
  };

  const handleRowClick = async (n) => {
    const meta = CATEGORY_META[n.category] || CATEGORY_META.general;
    const link = meta.deepLink(n);

    // Optimistic mark-as-read so the badge updates immediately.
    if (!n.is_read) {
      setNotifications((prev) =>
        prev.map((row) =>
          row.id === n.id ? { ...row, is_read: true } : row
        )
      );
      setUnreadCount((c) => Math.max(0, c - 1));
      notificationService.markRead([n.id]).catch(() => {
        // Revert on failure.
        setNotifications((prev) =>
          prev.map((row) =>
            row.id === n.id ? { ...row, is_read: false } : row
          )
        );
        setUnreadCount((c) => c + 1);
      });
    }

    setOpen(false);
    if (link) navigate(link);
  };

  const handleMarkAllRead = async () => {
    if (unreadCount === 0) return;
    setNotifications((prev) =>
      prev.map((row) => ({ ...row, is_read: true }))
    );
    setUnreadCount(0);
    try {
      await notificationService.markRead();
    } catch (err) {
      console.error(err);
      // Refresh to recover the server-side truth.
      refresh({ silent: true });
    }
  };

  const handleClearAll = async () => {
    if (notifications.length === 0) return;
    if (
      !window.confirm("Xóa toàn bộ thông báo? Hành động này không thể hoàn tác.")
    ) {
      return;
    }
    setNotifications([]);
    setUnreadCount(0);
    try {
      await notificationService.clearAll();
    } catch (err) {
      console.error(err);
      refresh({ silent: true });
    }
  };

  const handleDelete = async (e, n) => {
    e.stopPropagation();
    setNotifications((prev) => prev.filter((row) => row.id !== n.id));
    if (!n.is_read) setUnreadCount((c) => Math.max(0, c - 1));
    try {
      await notificationService.delete(n.id);
    } catch (err) {
      console.error(err);
      refresh({ silent: true });
    }
  };

  const badgeText = unreadCount > 9 ? "9+" : String(unreadCount);
  const hasUnread = unreadCount > 0;

  return (
    <div className="relative" ref={wrapperRef}>
      {/* Bell button */}
      <button
        onClick={handleOpen}
        className={`relative p-2.5 rounded-lg transition-colors group ${
          open
            ? "bg-slate-100 text-slate-900"
            : "text-slate-600 hover:text-slate-900 hover:bg-slate-100"
        }`}
        aria-label="Thông báo"
      >
        <Bell className="w-5 h-5" />
        {hasUnread && (
          <span className="absolute -top-0.5 -right-0.5 min-w-[18px] h-[18px] px-1 bg-red-500 text-white text-[10px] font-bold rounded-full flex items-center justify-center shadow-sm border-2 border-white">
            {badgeText}
          </span>
        )}
      </button>

      {/* Dropdown panel */}
      {open && (
        <div className="absolute right-0 mt-3 w-[420px] max-w-[95vw] bg-white rounded-2xl shadow-xl border border-slate-200 z-50 overflow-hidden">
          {/* Header */}
          <div className="px-5 py-4 border-b border-slate-200 flex items-center justify-between gap-3">
            <div>
              <h3 className="text-sm font-bold text-slate-900">Thông báo</h3>
              {hasUnread ? (
                <p className="text-xs text-slate-500">
                  {unreadCount} chưa đọc
                </p>
              ) : (
                <p className="text-xs text-slate-400">Bạn đã đọc hết</p>
              )}
            </div>
            <div className="flex items-center gap-2">
              {hasUnread && (
                <button
                  onClick={handleMarkAllRead}
                  title="Đánh dấu tất cả đã đọc"
                  className="inline-flex items-center gap-1 px-2 py-1 text-xs font-semibold text-teal-600 hover:bg-teal-50 rounded-md transition-colors"
                >
                  <Check className="w-3.5 h-3.5" />
                  Đọc hết
                </button>
              )}
              {notifications.length > 0 && (
                <button
                  onClick={handleClearAll}
                  title="Xóa toàn bộ"
                  className="inline-flex items-center gap-1 px-2 py-1 text-xs font-semibold text-slate-500 hover:text-red-600 hover:bg-red-50 rounded-md transition-colors"
                >
                  <Trash2 className="w-3.5 h-3.5" />
                </button>
              )}
            </div>
          </div>

          {/* Body */}
          <div className="max-h-[480px] overflow-y-auto">
            {loading && notifications.length === 0 ? (
              <div className="flex items-center justify-center py-12 text-slate-500 gap-2 text-sm">
                <Loader className="w-4 h-4 animate-spin" />
                Đang tải...
              </div>
            ) : error ? (
              <div className="flex items-start gap-3 px-5 py-4 text-sm text-red-700 bg-red-50">
                <AlertCircle className="w-4 h-4 flex-shrink-0 mt-0.5" />
                <span>{error}</span>
              </div>
            ) : notifications.length === 0 ? (
              <div className="px-5 py-12 text-center">
                <Bell className="w-10 h-10 text-slate-300 mx-auto mb-3" />
                <p className="text-sm font-semibold text-slate-700 mb-1">
                  Chưa có thông báo
                </p>
                <p className="text-xs text-slate-500">
                  Thông báo sẽ xuất hiện khi tác vụ hoàn thành hoặc thất bại.
                </p>
              </div>
            ) : (
              <ul className="divide-y divide-slate-100">
                {notifications.map((n) => (
                  <NotificationRow
                    key={n.id}
                    notification={n}
                    onClick={() => handleRowClick(n)}
                    onDelete={(e) => handleDelete(e, n)}
                  />
                ))}
              </ul>
            )}
          </div>

          {/* Footer hint */}
          <div className="px-5 py-2.5 bg-slate-50 border-t border-slate-200 text-[11px] text-slate-500">
            Tự cập nhật mỗi {Math.round(POLL_INTERVAL_MS / 1000)}s
          </div>
        </div>
      )}
    </div>
  );
};

// ── Single notification row ──────────────────────────────────────────────

const NotificationRow = ({ notification: n, onClick, onDelete }) => {
  const meta = CATEGORY_META[n.category] || CATEGORY_META.general;
  const CategoryIcon = meta.icon;
  const TypeIcon = TYPE_ICON[n.notification_type] || Info;
  const typeTone = TYPE_ICON_TONE[n.notification_type] || "text-slate-500";
  const borderTone =
    TYPE_BORDER[n.notification_type] || TYPE_BORDER.info;

  return (
    <li>
      <button
        onClick={onClick}
        className={`group w-full flex items-start gap-3 px-4 py-3 text-left border-l-4 transition-colors ${borderTone} ${
          n.is_read ? "bg-white hover:bg-slate-50" : "bg-teal-50/40 hover:bg-teal-50"
        }`}
      >
        {/* Category icon block */}
        <div
          className={`p-2 rounded-lg flex-shrink-0 ${meta.accent}`}
          aria-hidden="true"
        >
          <CategoryIcon className="w-4 h-4" />
        </div>

        {/* Body */}
        <div className="flex-1 min-w-0">
          <div className="flex items-start justify-between gap-2">
            <div className="flex items-center gap-1.5 min-w-0">
              <TypeIcon className={`w-3.5 h-3.5 flex-shrink-0 ${typeTone}`} />
              <p
                className={`text-sm truncate ${
                  n.is_read
                    ? "text-slate-700 font-medium"
                    : "text-slate-900 font-bold"
                }`}
                title={n.title}
              >
                {n.title}
              </p>
            </div>
            {!n.is_read && (
              <span className="w-2 h-2 rounded-full bg-teal-500 flex-shrink-0 mt-1.5" />
            )}
          </div>
          {n.message && (
            <p className="text-xs text-slate-600 mt-1 line-clamp-2 break-words">
              {n.message}
            </p>
          )}
          <div className="flex items-center justify-between gap-2 mt-1.5">
            <div className="flex items-center gap-2 text-[11px] text-slate-400">
              <span className="font-semibold uppercase tracking-wide">
                {meta.label}
              </span>
              <span>·</span>
              <span>{formatRelative(n.created_at)}</span>
            </div>
            <span
              onClick={onDelete}
              role="button"
              tabIndex={0}
              onKeyDown={(e) => {
                if (e.key === "Enter" || e.key === " ") {
                  e.preventDefault();
                  e.stopPropagation();
                  onDelete(e);
                }
              }}
              className="opacity-0 group-hover:opacity-100 text-slate-400 hover:text-red-600 hover:bg-red-50 transition-all p-1 rounded cursor-pointer"
              title="Xóa thông báo"
            >
              <X className="w-3.5 h-3.5" />
            </span>
          </div>
        </div>
      </button>
    </li>
  );
};

export default NotificationCenter;
