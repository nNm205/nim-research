import api from "./api";

export const reportService = {
  // List
  getProjectReports: async (projectId) => {
    const res = await api.get(`/api/v1/projects/${projectId}/reports`);
    return res.data.reports;
  },

  // Detail
  getReport: async (reportId) => {
    const res = await api.get(`/api/v1/reports/${reportId}`);
    return res.data;
  },

  // Create — backend auto-generates content + html_content
  createReport: async (projectId, reportData) => {
    const res = await api.post(`/api/v1/projects/${projectId}/reports`, reportData);
    return res.data;
  },

  // Update — backend auto-regenerates when title/type/included_documents change
  updateReport: async (reportId, updateData) => {
    const res = await api.put(`/api/v1/reports/${reportId}`, updateData);
    return res.data;
  },

  deleteReport: async (reportId) => {
    await api.delete(`/api/v1/reports/${reportId}`);
  },

  // Re-run the deterministic generator over the latest project data
  regenerateReport: async (reportId) => {
    const res = await api.post(`/api/v1/reports/${reportId}/regenerate`);
    return res.data;
  },

  // Download triggers a browser save. Format ∈ {"md", "html", "docx"}.
  // We request the file as a blob, then build a temporary <a download> link
  // so the filename suggested by the backend's Content-Disposition header is
  // preserved.
  downloadReport: async (reportId, format) => {
    const res = await api.get(
      `/api/v1/reports/${reportId}/download/${format}`,
      { responseType: "blob" }
    );

    // Pull the filename from Content-Disposition if provided by the backend
    const cd = res.headers["content-disposition"] || "";
    const match = cd.match(/filename="([^"]+)"/i);
    const filename = match ? match[1] : `report.${format}`;

    const url = window.URL.createObjectURL(new Blob([res.data]));
    const link = document.createElement("a");
    link.href = url;
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    link.remove();
    window.URL.revokeObjectURL(url);
  },
};
