import api from "./api";

export const documentService = {
  // Get all documents for a project
  getProjectDocuments: async (projectId) => {
    const res = await api.get(`/api/v1/projects/${projectId}/documents`);
    return res.data;
  },

  // Get all documents owned by the current user, across every project.
  // Used by the Documents page (no project scope).
  getAllDocuments: async () => {
    const res = await api.get(`/api/v1/documents`);
    return res.data;
  },

  // Get single document
  getDocument: async (projectId, documentId) => {
    const res = await api.get(`/api/v1/projects/${projectId}/documents/${documentId}`);
    return res.data;
  },

  // Create new document (manual)
  createDocument: async (projectId, documentData) => {
    const res = await api.post(`/api/v1/projects/${projectId}/documents`, documentData);
    return res.data;
  },

  // Ingest from URL — fetch, parse, chunk, embed, save in one call
  ingestFromURL: async (projectId, url, sourceType = "web", embeddingProvider = null, embeddingModel = null) => {
    const res = await api.post(
      `/api/v1/projects/${projectId}/documents/ingest-url`,
      {
        url,
        source_type: sourceType,
        ...(embeddingProvider && { embedding_provider: embeddingProvider }),
        ...(embeddingModel && { embedding_model: embeddingModel }),
      }
    );
    return res.data;
  },

  // Upload a local file (PDF or HTML). Same pipeline as ingestFromURL but
  // the file is sent as multipart/form-data.
  uploadFile: async (
    projectId,
    file,
    embeddingProvider = null,
    embeddingModel = null,
    onUploadProgress = null,
  ) => {
    const formData = new FormData();
    formData.append("file", file);
    if (embeddingProvider) formData.append("embedding_provider", embeddingProvider);
    if (embeddingModel) formData.append("embedding_model", embeddingModel);

    const res = await api.post(
      `/api/v1/projects/${projectId}/documents/upload-file`,
      formData,
      {
        headers: { "Content-Type": "multipart/form-data" },
        onUploadProgress,
      }
    );
    return res.data;
  },

  // Ingest a research search result into the project. The server locates a
  // PDF (Unpaywall / arXiv-derived / scraped from landing page) and falls
  // back to ingesting the page HTML if no PDF is found.
  ingestSearchResult: async (
    projectId,
    resultId,
    embeddingProvider = null,
    embeddingModel = null,
  ) => {
    const res = await api.post(
      `/api/v1/projects/${projectId}/documents/ingest-search-result`,
      {
        result_id: resultId,
        ...(embeddingProvider && { embedding_provider: embeddingProvider }),
        ...(embeddingModel && { embedding_model: embeddingModel }),
      },
    );
    return res.data;
  },

  // Get available embedding providers and their models
  getEmbeddingProviders: async () => {
    const res = await api.get("/api/v1/embeddings/providers");
    return res.data;
  },

  // Update document
  updateDocument: async (projectId, documentId, updateData) => {
    const res = await api.patch(`/api/v1/projects/${projectId}/documents/${documentId}`, updateData);
    return res.data;
  },

  // Delete document
  deleteDocument: async (projectId, documentId) => {
    const res = await api.delete(`/api/v1/projects/${projectId}/documents/${documentId}`);
    return res.data;
  },
};
