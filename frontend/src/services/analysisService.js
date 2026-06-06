import api from "./api";

export const analysisService = {
  // Start analysis for a document — sends document_id + optional llm provider/model
  startAnalysis: async (projectId, documentId, llmProvider, llmModel) => {
    const res = await api.post(`/api/v1/projects/${projectId}/analyze`, {
      document_id: documentId,
      ...(llmProvider && { llm_provider: llmProvider }),
      ...(llmModel && { llm_model: llmModel }),
    });
    return res.data;
  },

  // Get available LLM providers and models for analysis
  getLLMProviders: async () => {
    const res = await api.get("/api/v1/llm/providers");
    return res.data;
  },

  // Get project analyses
  getProjectAnalyses: async (projectId) => {
    const res = await api.get(`/api/v1/projects/${projectId}/analyses`);
    return res.data;
  },

  // Get all analyses owned by the current user, across every project.
  // Used by the Analysis page (no project scope).
  getAllAnalyses: async () => {
    const res = await api.get(`/api/v1/analyses`);
    return res.data;
  },

  // Get a single analysis by ID (full results — includes section_insights,
  // narrative_synthesis, document_outline, plus all legacy fields)
  getAnalysis: async (analysisId) => {
    const res = await api.get(`/api/v1/analysis/${analysisId}/results`);
    return res.data;
  },

  // Get analysis status
  getAnalysisStatus: async (projectId, taskId) => {
    const res = await api.get(`/api/v1/projects/${projectId}/analysis/${taskId}`);
    return res.data;
  },

  // Get analysis results (alias kept for backward compat)
  getAnalysisResults: async (taskId) => {
    const res = await api.get(`/api/v1/analysis/${taskId}/results`);
    return res.data;
  },

  // Get document summary
  getDocumentSummary: async (documentId) => {
    const res = await api.get(`/api/v1/documents/${documentId}/summary`);
    return res.data;
  },

  // Get all section insights for a document (with outline)
  getDocumentSections: async (documentId) => {
    const res = await api.get(`/api/v1/documents/${documentId}/sections`);
    return res.data;
  },

  // Get a single section insight by index
  getDocumentSection: async (documentId, sectionIndex) => {
    const res = await api.get(
      `/api/v1/documents/${documentId}/sections/${sectionIndex}`
    );
    return res.data;
  },

  // Get cross-section narrative synthesis
  getDocumentSynthesis: async (documentId) => {
    const res = await api.get(`/api/v1/documents/${documentId}/synthesis`);
    return res.data;
  },

  // Delete an analysis by ID
  deleteAnalysis: async (analysisId) => {
    await api.delete(`/api/v1/analysis/${analysisId}`);
  },
};
