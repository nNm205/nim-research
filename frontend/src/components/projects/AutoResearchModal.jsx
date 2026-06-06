import { useEffect, useState, useMemo } from "react";
import {
  X,
  Sparkles,
  Loader,
  AlertCircle,
  Cpu,
  ChevronDown,
  Wand2,
  Search,
  Download,
  Brain,
} from "lucide-react";
import { researchService } from "../../services/researchService";
import { documentService } from "../../services/documentService";
import { analysisService } from "../../services/analysisService";

/**
 * AutoResearchModal — single entry point for the "Nghiên cứu tự động" feature.
 *
 * The user enters a topic / keywords. The backend then runs three stages
 * in the background:
 *
 *   1. Search arXiv / Google Scholar / Semantic Scholar.
 *   2. Ingest the top N results into this project (PDF or HTML).
 *   3. Analyse each ingested document with the chosen LLM.
 *
 * The modal exposes:
 *   - query input
 *   - "search width" (max search results to pull) — defaults 10
 *   - "ingest depth" (top-N to actually ingest + analyse) — defaults 3
 *   - LLM provider/model picker
 *   - collapsed embedding provider override
 */
const AutoResearchModal = ({ projectId, onClose, onLaunched }) => {
  const [query, setQuery] = useState("");
  const [maxResults, setMaxResults] = useState(10);
  const [maxDocuments, setMaxDocuments] = useState(3);

  // LLM provider/model
  const [llmProviders, setLlmProviders] = useState([]);
  const [llmProvider, setLlmProvider] = useState("");
  const [llmModel, setLlmModel] = useState("");

  // Embedding provider/model
  const [embeddingProviders, setEmbeddingProviders] = useState([]);
  const [selectedEmbeddingProvider, setSelectedEmbeddingProvider] = useState(null);
  const [selectedEmbeddingModel, setSelectedEmbeddingModel] = useState(null);
  const [showEmbedding, setShowEmbedding] = useState(false);

  const [loading, setLoading] = useState(false);
  const [providersLoading, setProvidersLoading] = useState(true);
  const [error, setError] = useState("");

  // ── Load both provider catalogs in parallel on mount ──────────────────
  useEffect(() => {
    let alive = true;
    Promise.all([
      analysisService.getLLMProviders().catch(() => []),
      documentService.getEmbeddingProviders().catch(() => []),
    ]).then(([llms, embs]) => {
      if (!alive) return;
      setLlmProviders(llms);
      setEmbeddingProviders(embs);

      // Pick the recommended LLM (first provider's recommended model).
      const firstLlm = llms[0];
      if (firstLlm) {
        setLlmProvider(firstLlm.value);
        const recommended =
          firstLlm.models.find((m) => m.recommended) || firstLlm.models[0];
        if (recommended) setLlmModel(recommended.value);
      }
      setProvidersLoading(false);
    });
    return () => {
      alive = false;
    };
  }, []);

  const currentLlmProvider = useMemo(
    () => llmProviders.find((p) => p.value === llmProvider),
    [llmProviders, llmProvider]
  );

  const currentEmbeddingModels = useMemo(
    () =>
      embeddingProviders.find((p) => p.value === selectedEmbeddingProvider)
        ?.models || [],
    [embeddingProviders, selectedEmbeddingProvider]
  );

  const handleLlmProviderChange = (value) => {
    setLlmProvider(value);
    const provider = llmProviders.find((p) => p.value === value);
    if (provider) {
      const recommended =
        provider.models.find((m) => m.recommended) || provider.models[0];
      setLlmModel(recommended ? recommended.value : "");
    }
  };

  const handleEmbeddingProviderChange = (value) => {
    setSelectedEmbeddingProvider(value);
    const provider = embeddingProviders.find((p) => p.value === value);
    const recommended = provider?.models.find((m) => m.recommended);
    setSelectedEmbeddingModel(
      recommended?.value || provider?.models[0]?.value || null,
    );
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!query.trim()) {
      setError("Hãy nhập từ khóa hoặc tên tài liệu cần tìm");
      return;
    }
    if (!llmProvider || !llmModel) {
      setError("Vui lòng chọn provider và model LLM");
      return;
    }
    setError("");
    setLoading(true);
    try {
      const session = await researchService.startAutoResearch(projectId, {
        query: query.trim(),
        max_results: maxResults,
        max_documents: maxDocuments,
        llm_provider: llmProvider,
        llm_model: llmModel,
        embedding_provider: selectedEmbeddingProvider,
        embedding_model: selectedEmbeddingModel,
      });
      onLaunched?.(session);
      onClose();
    } catch (err) {
      const detail = err.response?.data?.detail;
      setError(
        typeof detail === "string"
          ? detail
          : "Không thể khởi động nghiên cứu tự động",
      );
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-black/20 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-2xl max-w-2xl w-full max-h-[90vh] flex flex-col shadow-2xl overflow-hidden">
        {/* Header */}
        <div className="border-b border-slate-200 px-8 py-5 flex items-center justify-between flex-shrink-0">
          <div className="flex items-center gap-3 min-w-0">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-violet-500 to-fuchsia-500 flex items-center justify-center flex-shrink-0">
              <Wand2 className="w-5 h-5 text-white" />
            </div>
            <div className="min-w-0">
              <h2 className="text-xl font-bold text-slate-900">
                Nghiên cứu tự động
              </h2>
              <p className="text-xs text-slate-500 mt-0.5">
                Tìm tài liệu → Thêm vào dự án → Phân tích — tất cả trong 1 lần
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="text-slate-400 hover:text-slate-600 transition-colors p-1 hover:bg-slate-100 rounded-lg flex-shrink-0 ml-3"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Body */}
        <form
          onSubmit={handleSubmit}
          className="flex-1 overflow-y-auto no-scrollbar p-6 space-y-5"
        >
          {error && (
            <div className="flex items-start gap-3 bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-xl text-sm">
              <AlertCircle className="w-4 h-4 flex-shrink-0 mt-0.5" />
              <span>{error}</span>
            </div>
          )}

          {/* Query */}
          <div>
            <label className="block text-sm font-semibold text-slate-900 mb-2">
              Chủ đề / từ khóa <span className="text-red-500">*</span>
            </label>
            <textarea
              rows={2}
              required
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Ví dụ: predictive gaze stabilization for AR interaction"
              className="w-full px-4 py-3 border border-slate-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-teal-500 focus:ring-offset-2 focus:border-transparent transition-all resize-none text-sm"
            />
            <p className="text-xs text-slate-500 mt-2">
              Nhập càng cụ thể càng tốt — agent sẽ tìm các paper academic có
              liên quan nhất.
            </p>
          </div>

          {/* Quantities */}
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1.5">
                Số kết quả tìm kiếm
              </label>
              <select
                value={maxResults}
                onChange={(e) => setMaxResults(Number(e.target.value))}
                className="w-full px-3 py-2 text-sm border border-slate-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-teal-500 focus:border-transparent transition-all"
              >
                {[5, 10, 15, 20].map((n) => (
                  <option key={n} value={n}>
                    {n} kết quả
                  </option>
                ))}
              </select>
              <p className="text-[11px] text-slate-500 mt-1.5">
                Tổng số tài liệu agent sẽ duyệt qua.
              </p>
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1.5">
                Số tài liệu phân tích
              </label>
              <select
                value={maxDocuments}
                onChange={(e) => setMaxDocuments(Number(e.target.value))}
                className="w-full px-3 py-2 text-sm border border-slate-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-teal-500 focus:border-transparent transition-all"
              >
                {[1, 2, 3, 4, 5].map((n) => (
                  <option key={n} value={n}>
                    Top {n} tài liệu
                  </option>
                ))}
              </select>
              <p className="text-[11px] text-slate-500 mt-1.5">
                Top-N kết quả sẽ được tải PDF và phân tích.
              </p>
            </div>
          </div>

          {/* LLM picker */}
          <div>
            <label className="block text-sm font-semibold text-slate-900 mb-2 flex items-center gap-2">
              <Sparkles className="w-4 h-4 text-teal-600" />
              Mô hình LLM dùng cho phân tích{" "}
              <span className="text-red-500">*</span>
            </label>

            {providersLoading && (
              <div className="flex items-center gap-2 text-sm text-slate-500 py-3">
                <Loader className="w-4 h-4 animate-spin" />
                Đang tải danh sách provider...
              </div>
            )}

            {!providersLoading && llmProviders.length > 0 && (
              <div className="space-y-3">
                <div className="grid grid-cols-2 md:grid-cols-3 gap-2">
                  {llmProviders.map((p) => {
                    const active = llmProvider === p.value;
                    return (
                      <button
                        type="button"
                        key={p.value}
                        onClick={() => handleLlmProviderChange(p.value)}
                        className={`text-left rounded-xl border-2 px-3 py-2.5 transition-all ${
                          active
                            ? "border-teal-500 bg-teal-50"
                            : "border-slate-200 hover:border-slate-300 hover:bg-slate-50"
                        }`}
                      >
                        <div className="font-semibold text-slate-900 text-sm">
                          {p.label}
                        </div>
                        <div className="text-[11px] text-slate-500 line-clamp-2 mt-0.5">
                          {p.description}
                        </div>
                      </button>
                    );
                  })}
                </div>

                {currentLlmProvider && (
                  <select
                    value={llmModel}
                    onChange={(e) => setLlmModel(e.target.value)}
                    className="w-full px-3 py-2 text-sm border border-slate-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-teal-500 focus:border-transparent transition-all"
                  >
                    {currentLlmProvider.models.map((m) => (
                      <option key={m.value} value={m.value}>
                        {m.label}
                        {m.recommended ? " — khuyên dùng" : ""}
                      </option>
                    ))}
                  </select>
                )}
              </div>
            )}
          </div>

          {/* Embedding provider — collapsible */}
          {embeddingProviders.length > 0 && (
            <div className="border border-slate-200 rounded-xl overflow-hidden">
              <button
                type="button"
                onClick={() => setShowEmbedding(!showEmbedding)}
                className="w-full flex items-center justify-between px-4 py-3 bg-slate-50 hover:bg-slate-100 transition-colors text-sm"
              >
                <div className="flex items-center gap-2 font-semibold text-slate-700">
                  <Cpu className="w-4 h-4 text-teal-600" />
                  Embedding Provider
                  {selectedEmbeddingProvider ? (
                    <span className="text-xs font-normal text-slate-500 ml-1">
                      —{" "}
                      {
                        embeddingProviders.find(
                          (p) => p.value === selectedEmbeddingProvider,
                        )?.label
                      }
                    </span>
                  ) : (
                    <span className="text-xs font-normal text-slate-400 ml-1">
                      (mặc định từ cấu hình)
                    </span>
                  )}
                </div>
                <ChevronDown
                  className={`w-4 h-4 text-slate-400 transition-transform ${
                    showEmbedding ? "rotate-180" : ""
                  }`}
                />
              </button>

              {showEmbedding && (
                <div className="p-4 space-y-3 border-t border-slate-200">
                  <div className="grid grid-cols-3 gap-2">
                    {embeddingProviders.map((p) => (
                      <button
                        key={p.value}
                        type="button"
                        onClick={() => handleEmbeddingProviderChange(p.value)}
                        className={`flex flex-col items-center gap-1 px-3 py-2.5 rounded-xl border-2 text-xs font-semibold transition-all ${
                          selectedEmbeddingProvider === p.value
                            ? "border-teal-500 bg-teal-50 text-teal-700"
                            : "border-slate-200 text-slate-600 hover:border-slate-300"
                        }`}
                      >
                        <span className="font-bold">{p.label}</span>
                        <span className="text-slate-400 font-normal text-center leading-tight">
                          {p.description}
                        </span>
                      </button>
                    ))}
                  </div>

                  {selectedEmbeddingProvider &&
                    currentEmbeddingModels.length > 0 && (
                      <select
                        value={selectedEmbeddingModel || ""}
                        onChange={(e) =>
                          setSelectedEmbeddingModel(e.target.value)
                        }
                        className="w-full px-3 py-2 text-sm border border-slate-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-teal-500 focus:border-transparent transition-all"
                      >
                        {currentEmbeddingModels.map((m) => (
                          <option key={m.value} value={m.value}>
                            {m.label} ({m.dimensions}d)
                            {m.recommended ? " — đề xuất" : ""}
                          </option>
                        ))}
                      </select>
                    )}
                </div>
              )}
            </div>
          )}

          {/* Pipeline preview */}
          <div className="bg-gradient-to-br from-violet-50 to-fuchsia-50 border border-violet-200 rounded-xl p-4">
            <p className="text-xs font-bold text-violet-700 uppercase tracking-wide mb-3">
              Pipeline tự động sẽ chạy
            </p>
            <ol className="space-y-2 text-sm">
              <li className="flex items-start gap-3">
                <span className="flex-shrink-0 w-6 h-6 rounded-full bg-violet-100 text-violet-700 text-xs font-bold flex items-center justify-center">
                  <Search className="w-3.5 h-3.5" />
                </span>
                <div className="flex-1">
                  <p className="font-semibold text-slate-800">
                    Tìm kiếm {maxResults} tài liệu
                  </p>
                  <p className="text-xs text-slate-500">
                    arXiv · Google Scholar · Semantic Scholar (chạy song song)
                  </p>
                </div>
              </li>
              <li className="flex items-start gap-3">
                <span className="flex-shrink-0 w-6 h-6 rounded-full bg-violet-100 text-violet-700 text-xs font-bold flex items-center justify-center">
                  <Download className="w-3.5 h-3.5" />
                </span>
                <div className="flex-1">
                  <p className="font-semibold text-slate-800">
                    Tải về top {maxDocuments} tài liệu
                  </p>
                  <p className="text-xs text-slate-500">
                    Tự tìm PDF (Unpaywall · arXiv) hoặc fallback HTML, chunk +
                    embed
                  </p>
                </div>
              </li>
              <li className="flex items-start gap-3">
                <span className="flex-shrink-0 w-6 h-6 rounded-full bg-violet-100 text-violet-700 text-xs font-bold flex items-center justify-center">
                  <Brain className="w-3.5 h-3.5" />
                </span>
                <div className="flex-1">
                  <p className="font-semibold text-slate-800">
                    Phân tích từng tài liệu
                  </p>
                  <p className="text-xs text-slate-500">
                    Trích xuất sections, claims, bảng, công thức, tổng hợp
                  </p>
                </div>
              </li>
            </ol>
          </div>

          {/* Quota hint */}
          <div className="bg-amber-50 border border-amber-200 rounded-xl p-3">
            <p className="text-xs text-amber-800">
              <span className="font-semibold">⚠ Lưu ý quota:</span> Pipeline
              này dùng nhiều LLM call hơn 1 phân tích đơn (≈ {maxDocuments} ×
              6-7 calls). Free tier Gemini (5 RPM) có thể chậm 5-10 phút; Groq
              (30 RPM) nhanh hơn nhiều.
            </p>
          </div>

          {/* Footer */}
          <div className="flex items-center justify-end gap-3 pt-4 border-t border-slate-200">
            <button
              type="button"
              onClick={onClose}
              disabled={loading}
              className="px-5 py-2.5 border border-slate-200 rounded-xl text-slate-700 hover:bg-slate-50 font-semibold transition-colors disabled:opacity-50"
            >
              Hủy
            </button>
            <button
              type="submit"
              disabled={
                loading || providersLoading || !query.trim() || !llmModel
              }
              className="flex items-center gap-2 px-5 py-2.5 bg-gradient-to-r from-violet-600 to-fuchsia-600 hover:from-violet-700 hover:to-fuchsia-700 disabled:opacity-60 disabled:cursor-not-allowed text-white rounded-xl font-semibold transition-all shadow-lg"
            >
              {loading ? (
                <>
                  <Loader className="w-4 h-4 animate-spin" />
                  Đang khởi động...
                </>
              ) : (
                <>
                  <Wand2 className="w-4 h-4" />
                  Khởi động nghiên cứu
                </>
              )}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};

export default AutoResearchModal;
