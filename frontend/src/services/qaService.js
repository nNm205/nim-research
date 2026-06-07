import api from "./api";

/**
 * QualityAssuranceAgent endpoints — runs format / citation / fact /
 * grammar checks on a Report and writes the result to ``Report.qa_report``.
 *
 * Returns shapes are documented in ``backend/app/schemas/qa.py``.
 */
export const qaService = {
  // Dispatch the QA agent. Optional llm_provider / llm_model override the
  // defaults from settings.PROVIDER / settings.MODEL_NAME.
  start: async (reportId, { llmProvider, llmModel } = {}) => {
    const res = await api.post(`/api/v1/reports/${reportId}/qa`, {
      ...(llmProvider && { llm_provider: llmProvider }),
      ...(llmModel && { llm_model: llmModel }),
    });
    return res.data;
  },

  // Light-weight polling endpoint — returns qa_status + qa_progress.
  getStatus: async (reportId) => {
    const res = await api.get(`/api/v1/reports/${reportId}/qa/status`);
    return res.data;
  },

  // Full QA result — includes the qa_report dict with sub-scores +
  // recommendations + per-claim verdicts.
  getReport: async (reportId) => {
    const res = await api.get(`/api/v1/reports/${reportId}/qa/report`);
    return res.data;
  },
};
