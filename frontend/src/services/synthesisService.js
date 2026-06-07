import api from "./api";

/**
 * SynthesisAgent endpoints — runs an LLM-driven cross-document synthesis on
 * a Report. Overwrites Report.content / html_content with the LLM-rewritten
 * version; the original template version is snapshotted in
 * ``Report.synthesis_metadata.original_template_md`` for rollback.
 *
 * Returns shapes are documented in ``backend/app/schemas/synthesis.py``.
 */
export const synthesisService = {
  // Dispatch SynthesisAgent. Optional llm_provider / llm_model override
  // settings.PROVIDER / settings.MODEL_NAME. Returns the report row with
  // synthesis_status flipped to "pending".
  start: async (reportId, { llmProvider, llmModel } = {}) => {
    const res = await api.post(`/api/v1/reports/${reportId}/synthesize`, {
      ...(llmProvider && { llm_provider: llmProvider }),
      ...(llmModel && { llm_model: llmModel }),
    });
    return res.data;
  },

  // Polling endpoint — returns light-weight row with synthesis_progress.
  getStatus: async (reportId) => {
    const res = await api.get(
      `/api/v1/reports/${reportId}/synthesis/status`
    );
    return res.data;
  },

  // Full result — includes synthesis_metadata (outline, narrative,
  // citations, original_template_*).
  getResult: async (reportId) => {
    const res = await api.get(`/api/v1/reports/${reportId}/synthesis`);
    return res.data;
  },

  // Restore the report's content/html_content from the template snapshot.
  rollback: async (reportId) => {
    const res = await api.post(
      `/api/v1/reports/${reportId}/synthesis/rollback`
    );
    return res.data;
  },

  // Synthesis + QA chained. Returns the report with synthesis_status =
  // "pending" — FE polls synthesis status first, then QA status when
  // synthesis is done.
  runFullPipeline: async (reportId, { llmProvider, llmModel } = {}) => {
    const res = await api.post(
      `/api/v1/reports/${reportId}/full-pipeline`,
      {
        ...(llmProvider && { llm_provider: llmProvider }),
        ...(llmModel && { llm_model: llmModel }),
      }
    );
    return res.data;
  },
};
