import { useEffect, useState, useMemo } from "react";
import { X, CheckCircle2, Loader, Sparkles, Zap } from "lucide-react";
import { analysisService } from "../../services/analysisService";

const StartAnalysisModal = ({ documents, onClose, onStart }) => {
  const [selectedDocumentId, setSelectedDocumentId] = useState("");
  const [providers, setProviders] = useState([]);
  const [providersLoading, setProvidersLoading] = useState(true);
  const [llmProvider, setLlmProvider] = useState("");
  const [llmModel, setLlmModel] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  // ── Load LLM provider catalog on mount ───────────────────────────────────
  useEffect(() => {
    let alive = true;
    (async () => {
      try {
        const catalog = await analysisService.getLLMProviders();
        if (!alive) return;
        setProviders(catalog);
        // Pick a sensible default: first provider's recommended model.
        const firstProvider = catalog[0];
        if (firstProvider) {
          setLlmProvider(firstProvider.value);
          const recommended =
            firstProvider.models.find((m) => m.recommended) ||
            firstProvider.models[0];
          if (recommended) setLlmModel(recommended.value);
        }
      } catch (err) {
        console.error("Failed to load LLM providers:", err);
        if (alive) setError("Không tải được danh sách LLM provider");
      } finally {
        if (alive) setProvidersLoading(false);
      }
    })();
    return () => {
      alive = false;
    };
  }, []);

  const currentProvider = useMemo(
    () => providers.find((p) => p.value === llmProvider),
    [providers, llmProvider]
  );

  const handleProviderChange = (value) => {
    setLlmProvider(value);
    const provider = providers.find((p) => p.value === value);
    if (provider) {
      const recommended =
        provider.models.find((m) => m.recommended) || provider.models[0];
      setLlmModel(recommended ? recommended.value : "");
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!selectedDocumentId) {
      setError("Vui lòng chọn tài liệu");
      return;
    }
    if (!llmProvider || !llmModel) {
      setError("Vui lòng chọn provider và model LLM");
      return;
    }

    setError("");
    setLoading(true);

    try {
      await onStart(selectedDocumentId, llmProvider, llmModel);
    } catch (err) {
      setError(err.response?.data?.detail || "Không thể bắt đầu phân tích");
    } finally {
      setLoading(false);
    }
  };

  const processedDocs = documents.filter((d) => d.processed);
  const unprocessedDocs = documents.filter((d) => !d.processed);

  return (
    <div className="fixed inset-0 bg-black/20 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-2xl max-w-2xl w-full max-h-[90vh] overflow-y-auto no-scrollbar shadow-2xl">
        {/* Header */}
        <div className="sticky top-0 bg-white border-b border-slate-200 px-8 py-5 flex items-center justify-between z-10">
          <div>
            <h2 className="text-2xl font-bold text-slate-900">Bắt đầu phân tích</h2>
            <p className="text-sm text-slate-600 mt-1">
              Chọn tài liệu và mô hình LLM để phân tích
            </p>
          </div>
          <button
            onClick={onClose}
            className="text-slate-400 hover:text-slate-600 transition-colors p-1 hover:bg-slate-100 rounded-lg"
          >
            <X className="w-6 h-6" />
          </button>
        </div>

        {/* Body */}
        <form onSubmit={handleSubmit} className="p-8 space-y-6">
          {error && (
            <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-xl text-sm font-medium flex items-start gap-3">
              <span className="text-lg">⚠️</span>
              <span>{error}</span>
            </div>
          )}

          {/* ── Document Selection ─────────────────────────────────────── */}
          <div>
            <label className="block text-sm font-semibold text-slate-900 mb-4">
              Chọn tài liệu để phân tích <span className="text-red-500">*</span>
            </label>

            {processedDocs.length === 0 && unprocessedDocs.length === 0 && (
              <div className="text-center py-8 bg-slate-50 rounded-xl border border-slate-200">
                <p className="text-slate-600">Không có tài liệu nào</p>
              </div>
            )}

            {processedDocs.length > 0 && (
              <div className="space-y-2 mb-6">
                <p className="text-xs text-slate-600 font-semibold uppercase tracking-wide">
                  Đã xử lý ({processedDocs.length})
                </p>
                {processedDocs.map((doc) => (
                  <DocumentOption
                    key={doc.id}
                    doc={doc}
                    isSelected={selectedDocumentId === doc.id}
                    onSelect={(id) => setSelectedDocumentId(id)}
                    status="processed"
                  />
                ))}
              </div>
            )}

            {unprocessedDocs.length > 0 && (
              <div className="space-y-2">
                <p className="text-xs text-slate-600 font-semibold uppercase tracking-wide">
                  Chưa xử lý ({unprocessedDocs.length})
                </p>
                {unprocessedDocs.map((doc) => (
                  <DocumentOption
                    key={doc.id}
                    doc={doc}
                    isSelected={selectedDocumentId === doc.id}
                    onSelect={(id) => setSelectedDocumentId(id)}
                    status="unprocessed"
                  />
                ))}
              </div>
            )}
          </div>

          {/* ── LLM Provider Selection ─────────────────────────────────── */}
          <div>
            <label className="block text-sm font-semibold text-slate-900 mb-2 flex items-center gap-2">
              <Sparkles className="w-4 h-4 text-teal-600" />
              Mô hình LLM <span className="text-red-500">*</span>
            </label>
            <p className="text-xs text-slate-500 mb-4">
              Chọn provider và model để cân bằng chất lượng, tốc độ và quota
            </p>

            {providersLoading && (
              <div className="flex items-center gap-2 text-sm text-slate-500 py-3">
                <Loader className="w-4 h-4 animate-spin" />
                Đang tải danh sách provider...
              </div>
            )}

            {!providersLoading && providers.length > 0 && (
              <div className="space-y-4">
                {/* Provider tabs */}
                <div>
                  <p className="text-xs font-semibold text-slate-600 uppercase tracking-wide mb-2">
                    Provider
                  </p>
                  <div className="grid grid-cols-2 md:grid-cols-3 gap-2">
                    {providers.map((p) => {
                      const active = llmProvider === p.value;
                      return (
                        <button
                          type="button"
                          key={p.value}
                          onClick={() => handleProviderChange(p.value)}
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
                </div>

                {/* Model selector */}
                {currentProvider && (
                  <div>
                    <p className="text-xs font-semibold text-slate-600 uppercase tracking-wide mb-2">
                      Model
                    </p>
                    <div className="space-y-2">
                      {currentProvider.models.map((m) => {
                        const active = llmModel === m.value;
                        return (
                          <label
                            key={m.value}
                            className={`flex items-start gap-3 p-3 border-2 rounded-xl cursor-pointer transition-all ${
                              active
                                ? "border-teal-500 bg-teal-50"
                                : "border-slate-200 hover:border-slate-300 hover:bg-slate-50"
                            }`}
                          >
                            <input
                              type="radio"
                              name="llm_model"
                              value={m.value}
                              checked={active}
                              onChange={(e) => setLlmModel(e.target.value)}
                              className="mt-1 w-4 h-4 text-teal-600 cursor-pointer"
                            />
                            <div className="flex-1 min-w-0">
                              <div className="flex items-center gap-2 flex-wrap">
                                <p className="font-semibold text-slate-900 text-sm">
                                  {m.label}
                                </p>
                                {m.recommended && (
                                  <span className="inline-flex items-center gap-1 px-1.5 py-0.5 bg-emerald-100 text-emerald-700 rounded text-[10px] font-bold uppercase">
                                    <Zap className="w-3 h-3" />
                                    khuyên dùng
                                  </span>
                                )}
                              </div>
                              {m.description && (
                                <p className="text-xs text-slate-500 mt-0.5">
                                  {m.description}
                                </p>
                              )}
                              <p className="text-[11px] text-slate-400 font-mono mt-1">
                                {m.value}
                              </p>
                            </div>
                          </label>
                        );
                      })}
                    </div>
                  </div>
                )}
              </div>
            )}
          </div>

          {/* Info Box */}
          <div className="bg-teal-50 border border-teal-200 rounded-xl p-5">
            <div className="flex items-start gap-3">
              <Sparkles className="w-5 h-5 text-teal-600 flex-shrink-0 mt-0.5" />
              <div className="text-sm text-teal-900">
                <p className="font-semibold mb-2">Phân tích sẽ cung cấp:</p>
                <ul className="space-y-1.5 text-xs">
                  <li>· Cấu trúc tài liệu (outline) và tổng hợp xuyên phần</li>
                  <li>· Mỗi phần có claim + bằng chứng + critique + trích dẫn gốc</li>
                  <li>· Câu hỏi nghiên cứu, đóng góp mới, hạn chế</li>
                  <li>· Tóm tắt điều hành cuối cùng</li>
                </ul>
              </div>
            </div>
          </div>

          {/* Processing time hint */}
          <div className="bg-blue-50 border border-blue-200 rounded-xl p-3">
            <p className="text-xs text-blue-800">
              <span className="font-semibold">💡 Mẹo:</span> Gemini free tier
              giới hạn 5 yêu cầu/phút nên có thể chậm 3-5 phút. Groq nhanh hơn
              nhiều nhưng chất lượng JSON output đôi khi kém ổn định hơn Gemini.
            </p>
          </div>

          {/* Actions */}
          <div className="flex items-center justify-end gap-3 pt-4 border-t border-slate-200">
            <button
              type="button"
              onClick={onClose}
              className="px-6 py-3 border border-slate-200 rounded-xl text-slate-700 hover:bg-slate-50 font-semibold transition-colors"
            >
              Hủy
            </button>
            <button
              type="submit"
              disabled={
                loading ||
                providersLoading ||
                !selectedDocumentId ||
                !llmProvider ||
                !llmModel
              }
              className="flex items-center gap-2 px-6 py-3 bg-gradient-to-r from-teal-600 to-teal-700 hover:from-teal-700 hover:to-teal-800 disabled:opacity-60 text-white rounded-xl font-semibold transition-all shadow-lg hover:shadow-xl disabled:shadow-none"
            >
              {loading ? (
                <>
                  <Loader className="w-5 h-5 animate-spin" />
                  <span>Đang bắt đầu...</span>
                </>
              ) : (
                <>
                  <Sparkles className="w-5 h-5" />
                  <span>Bắt đầu phân tích</span>
                </>
              )}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};

const DocumentOption = ({ doc, isSelected, onSelect, status }) => {
  return (
    <label
      className={`flex items-center gap-4 p-4 border-2 rounded-xl cursor-pointer transition-all ${
        isSelected
          ? "border-teal-500 bg-teal-50"
          : "border-slate-200 hover:border-slate-300 hover:bg-slate-50"
      }`}
    >
      <input
        type="radio"
        name="document"
        value={doc.id}
        checked={isSelected}
        onChange={(e) => onSelect(e.target.value)}
        className="w-5 h-5 text-teal-600 cursor-pointer"
      />
      <div className="flex-1 min-w-0">
        <p className="font-semibold text-slate-900">{doc.title}</p>
        {doc.source_type && (
          <p className="text-xs text-slate-500 uppercase tracking-wide">
            {doc.source_type}
          </p>
        )}
      </div>
      {status === "processed" ? (
        <div className="flex items-center gap-2 bg-emerald-100 text-emerald-700 px-3 py-1.5 rounded-lg flex-shrink-0">
          <CheckCircle2 className="w-4 h-4" />
          <span className="text-xs font-semibold">Sẵn sàng</span>
        </div>
      ) : (
        <div className="flex items-center gap-2 bg-amber-100 text-amber-700 px-3 py-1.5 rounded-lg flex-shrink-0">
          <Loader className="w-4 h-4" />
          <span className="text-xs font-semibold">Xử lý...</span>
        </div>
      )}
    </label>
  );
};

export default StartAnalysisModal;
