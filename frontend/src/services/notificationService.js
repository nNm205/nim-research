import api from "./api";

/**
 * Notification API client.
 *
 * Talks to the backend's ``/api/v1/notifications`` endpoints.
 * The bell dropdown polls ``list`` every 15s while the user is
 * signed in (see DashboardLayout).
 */
export const notificationService = {
  /**
   * Fetch latest notifications + global unread count.
   * Returns ``{ notifications: [...], unread_count: number }``.
   */
  list: async ({ limit = 30, onlyUnread = false } = {}) => {
    const res = await api.get("/api/v1/notifications", {
      params: { limit, only_unread: onlyUnread },
    });
    return res.data;
  },

  /**
   * Mark one or more notifications as read. Pass ``ids`` to mark
   * specific rows; omit it to mark every unread row.
   * Returns the number of rows that were flipped.
   */
  markRead: async (ids = null) => {
    const res = await api.post("/api/v1/notifications/mark-read", {
      ids: ids || null,
    });
    return res.data.marked_read || 0;
  },

  /** Hard-delete one notification. */
  delete: async (id) => {
    await api.delete(`/api/v1/notifications/${id}`);
  },

  /** Hard-delete every notification belonging to the user. */
  clearAll: async () => {
    const res = await api.delete("/api/v1/notifications");
    return res.data.deleted || 0;
  },
};
