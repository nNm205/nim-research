import api from "./api";

export const researchService = {
  // Start a new research session — agent runs in background
  startResearch: async (projectId, query, maxResults = 10) => {
    const response = await api.post(`/api/v1/projects/${projectId}/research`, {
      query,
      max_results: maxResults,
    });
    return response.data;
  },

  // Kick off the auto-research pipeline: search → ingest top-N → analyse.
  // Returns the ResearchSession row immediately; results stream into the
  // project's documents and analyses tables as the pipeline progresses.
  startAutoResearch: async (projectId, payload) => {
    const response = await api.post(
      `/api/v1/projects/${projectId}/auto-research`,
      payload,
    );
    return response.data;
  },

  // Get all past sessions for a project (history)
  getSessions: async (projectId) => {
    const response = await api.get(`/api/v1/projects/${projectId}/research`);
    return response.data;
  },

  // Poll status of a running session
  getStatus: async (projectId, taskId) => {
    const response = await api.get(
      `/api/v1/projects/${projectId}/research/${taskId}`
    );
    return response.data;
  },

  // Fetch final results once COMPLETED
  getResults: async (taskId) => {
    const response = await api.get(`/api/v1/research/${taskId}/results`);
    return response.data;
  },
};
