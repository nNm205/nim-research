import { useEffect, useState } from "react";
import {
  X,
  Loader,
  AlertCircle,
  Cpu,
  ChevronDown,
  Sparkles,
  FileSearch,
} from "lucide-react";
import { documentService } from "../../services/documentService";

// ── Publisher classifier (FE mirror of backend ``publisher_classifier``)
//
// Keep this list in sync with backend
// ``app/tools/search/publisher_classifier.py``. The FE uses it purely
// for "can the user click submit?" gating and the warning banner — the
// authoritative check still happens server-side.
const TRUSTED_PUBLISHERS = new Set(["arxiv", "ieee", "acm", "researchgate"]);

const DOI_PREFIX_MAP = {
  "10.48550": "arxiv",
  "10.1109": "ieee",
  "10.1145": "acm",
};

const HOST_SUFFIX_MAP = [
  ["arxiv.org", "arxiv"],
  ["ieee.org", "ieee"],
  ["ieeexplore.ieee.org", "ieee"],
  ["computer.org", "ieee"],
  ["dl.acm.org", "acm"],
  ["acm.org", "acm"],
  ["researchgate.net", "researchgate"],
];

const _hostOf = (rawUrl) => {
  if (!rawUrl) return null;
  try {
    const u = new URL(rawUrl);
    let h = (u.hostname || "").toLowerCase();
    if (h.startsWith("www.")) h = h.slice(4);
    return h || null;
  } catch {
    return null;
  }
};

const classifyPublisher = ({ doi, url, pdfUrl, source }) => {
  if (source && String(source).toLowerCase() === "arxiv") return "arxiv";

  if (doi) {
    let d = String(doi).trim().toLowerCase();
    for (const prefix of ["https://doi.org/", "http://doi.org/", "doi.org/", "doi:"]) {
      if (d.startsWith(prefix)) {
        d = d.slice(prefix.length);
        break;
      }
    }
    const head = d.split("/", 1)[0];
    if (DOI_PREFIX_MAP[head]) return DOI_PREFIX_MAP[head];
  }

  for (const candidate of [url, pdfUrl]) {
    const host = _hostOf(candidate);
    if (!host) continue;
    for (const [suffix, pub] of HOST_SUFFIX_MAP) {
      if (host === suffix || host.endsWith("." + suffix)) return pub;
    }
  }
  return "other";
};

/**
 * Modal that adds a single research search result into the current project.
 *
 * Why this modal exists:
 *   - Search results don't always carry a ``pdf_url`` (Google Scholar / web
 *     hits in particular). The backend will try to find a PDF (Unpaywall /
 *     arXiv-derived / scrape page meta) and fall back to ingesting the
 *     landing page HTML.
 *   - The user may want to override the default embedding provider for
 *     this single ingestion (e.g. to try a multilingual model on a
 *     Vietnamese paper).
 *
 * Props:
 *   - result: SearchResult row from the API
 *   - projectId: target project
 *   - onClose: dismiss the modal
 *   - onIngested(document): called when ingest succeeds
 */
const IngestSearchResultModal = ({ result, projectId, onClose, onIngested }) => {
  const [providers, setProviders] = useState([]);
  const [selectedProvider, setSelectedProvider] = useState(null);
  const [selectedModel, setSelectedModel] = useState(null);
  const [showEmbedding, setShowEmbedding] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    documentService.getEmbeddingProviders()
      .then(setProviders)
      .catch(() => {});
  }, []);

  const currentModels =
    providers.find((p) => p.value === selectedProvider)?.models || [];

  const onChooseProvider = (providerValue) => {
    setSelectedProvider(providerValue);
    const providerData = providers.find((p) => p.value === providerValue);
    const recommended = providerData?.models.find((m) => m.recommended);
    setSelectedModel(recommended?.value || providerData?.models[0]?.value || null);
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!result?.id) {
      setError("Kết quả tìm kiếm thiếu ID, không thể xử lý. Hãy chạy lại phiên tìm kiếm.");
      return;
    }
    setError("");
    setLoading(true);
    try {
      const doc = await documentService.ingestSearchResult(
        projectId,
        result.id,
        selectedProvider,
        selectedModel,
      );
      onIngested(doc);
    } catch (err) {
      // Surface the most informative error we can. FastAPI 422 returns
      // detail as either a string or a list of pydantic errors.
      const detail = err.response?.data?.detail;
      let message;
      if (typeof detail === "string") {
        message = detail;
      } else if (Array.isArray(detail) && detail.length > 0) {
        message = detail
          .map((d) => `${(d.loc || []).slice(-1)[0] || "field"}: ${d.msg}`)
          .join("; ");
      } else {
        message = "Không thể thêm tài liệu này. Hãy thử kết quả khác.";
      }
      setError(message);
    } finally {
      setLoading(false);
    }
  };

  // Heuristic preview of which path the server will take. Purely cosmetic
  // — the server runs the real lookup. Helps the user understand what
  // they're about to do.
  const willUsePdf =
    !!result.pdf_url ||
    /arxiv\.org\/abs\//i.test(result.url || "") ||
    (result.url || "").toLowerCase().endsWith(".pdf");

  // Classify the publisher of this hit. Mirrors the backend's
  // ``publisher_classifier`` logic (DOI prefix → publisher, else URL
  // host suffix). Drop a hit when its publisher is not in the trusted
  // whitelist; the backend would reject it anyway.
  const publisher = classifyPublisher({
    doi: result.doi,
    url: result.url,
    pdfUrl: result.pdf_url,
    source: result.source,
  });
  const isTrusted = TRUSTED_PUBLISHERS.has(publisher);
  const isResearchGate = publisher === "researchgate";

  return (
    <div className="fixed inset-0 bg-black/20 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-2xl max-w-2xl w-full max-h-[90vh] flex flex-col shadow-2xl overflow-hidden">
        {/* Header */}
        <div className="border-b border-slate-200 px-6 py-4 flex items-start justify-between flex-shrink-0">
          <div className="min-w-0 flex-1">
            <h2 className="text-xl font-bold text-slate-900">Thêm vào dự án</h2>
            <p className="text-xs text-slate-500 mt-1 truncate" title={result.title}>
              {result.title}
            </p>
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

          {/* Non-trusted-publisher warning — block ingest up-front. */}
          {!isTrusted && (
            <div className="flex items-start gap-3 bg-amber-50 border border-amber-200 text-amber-800 px-4 py-3 rounded-xl text-sm">
              <AlertCircle className="w-4 h-4 flex-shrink-0 mt-0.5" />
              <div>
                <p className="font-semibold">Nguồn không thuộc nhóm tin cậy</p>
                <p className="text-xs mt-0.5 leading-snug">
                  Hệ thống chỉ nạp tài liệu từ các publisher học thuật tin
                  cậy: <strong>arXiv</strong>, <strong>IEEE</strong>,{" "}
                  <strong>ACM</strong>, <strong>ResearchGate</strong>. Kết
                  quả này (publisher: <span className="font-mono">{publisher}</span>)
                  không thuộc nhóm trên nên không thể thêm vào dự án.
                </p>
              </div>
            </div>
          )}

          {/* ResearchGate-specific note — even when trusted, RG-hosted
              PDFs are resolved via Unpaywall instead of fetched directly. */}
          {isTrusted && isResearchGate && (
            <div className="flex items-start gap-3 bg-blue-50 border border-blue-200 text-blue-800 px-4 py-3 rounded-xl text-sm">
              <AlertCircle className="w-4 h-4 flex-shrink-0 mt-0.5" />
              <div>
                <p className="font-semibold">Bài viết trên ResearchGate</p>
                <p className="text-xs mt-0.5 leading-snug">
                  Theo điều khoản sử dụng của ResearchGate, hệ thống sẽ KHÔNG
                  tải PDF trực tiếp từ rg.net. Thay vào đó sẽ tìm bản Open
                  Access tương đương qua DOI / Unpaywall. Nếu không có bản
                  OA, bài này sẽ được bỏ qua.
                </p>
              </div>
            </div>
          )}

          {/* What the server will do */}
          <div className="bg-slate-50 border border-slate-200 rounded-xl p-4 space-y-2">
            <div className="flex items-center gap-2 text-sm font-semibold text-slate-700">
              <FileSearch className="w-4 h-4 text-teal-600" />
              Hệ thống sẽ tự động:
            </div>
            <ol className="text-xs text-slate-600 leading-relaxed pl-5 list-decimal space-y-1">
              <li>
                {willUsePdf ? (
                  <>
                    Tải PDF từ{" "}
                    <span className="font-semibold text-teal-700">
                      {result.pdf_url ? "đường dẫn PDF có sẵn" : "URL gốc"}
                    </span>
                  </>
                ) : result.doi ? (
                  <>
                    Tìm bản PDF Open Access qua{" "}
                    <code className="font-mono text-[11px]">DOI</code> + scrape
                    trang gốc
                  </>
                ) : (
                  <>
                    Quét trang gốc tìm liên kết PDF — nếu không tìm thấy,
                    kết quả này sẽ <strong>bị bỏ qua</strong> (không nạp HTML
                    để giữ chất lượng nguồn)
                  </>
                )}
              </li>
              <li>Trích xuất văn bản, bảng và công thức từ PDF</li>
              <li>Chia chunks và tạo vector embeddings</li>
              <li>Lưu vào dự án để sẵn sàng phân tích</li>
            </ol>
          </div>

          {/* Embedding provider selector */}
          {providers.length > 0 && (
            <div className="border border-slate-200 rounded-xl overflow-hidden">
              <button
                type="button"
                onClick={() => setShowEmbedding(!showEmbedding)}
                className="w-full flex items-center justify-between px-4 py-3 bg-slate-50 hover:bg-slate-100 transition-colors text-sm"
              >
                <div className="flex items-center gap-2 font-semibold text-slate-700">
                  <Cpu className="w-4 h-4 text-teal-600" />
                  Embedding Provider
                  {selectedProvider ? (
                    <span className="text-xs font-normal text-slate-500 ml-1">
                      — {providers.find((p) => p.value === selectedProvider)?.label}
                      {selectedModel &&
                        ` / ${currentModels.find((m) => m.value === selectedModel)?.label}`}
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
                <div className="p-4 space-y-4 border-t border-slate-200">
                  <div>
                    <label className="block text-xs font-semibold text-slate-600 mb-2 uppercase tracking-wide">
                      Provider
                    </label>
                    <div className="grid grid-cols-3 gap-2">
                      {providers.map((p) => (
                        <button
                          key={p.value}
                          type="button"
                          onClick={() => onChooseProvider(p.value)}
                          className={`flex flex-col items-center gap-1 px-3 py-2.5 rounded-xl border-2 text-xs font-semibold transition-all ${
                            selectedProvider === p.value
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
                  </div>

                  {selectedProvider && currentModels.length > 0 && (
                    <div>
                      <label className="block text-xs font-semibold text-slate-600 mb-2 uppercase tracking-wide">
                        Model
                      </label>
                      <div className="space-y-2">
                        {currentModels.map((m) => (
                          <label
                            key={m.value}
                            className={`flex items-start gap-3 p-3 rounded-xl border-2 cursor-pointer transition-all ${
                              selectedModel === m.value
                                ? "border-teal-500 bg-teal-50"
                                : "border-slate-200 hover:border-slate-300"
                            }`}
                          >
                            <input
                              type="radio"
                              name="embedding_model"
                              value={m.value}
                              checked={selectedModel === m.value}
                              onChange={() => setSelectedModel(m.value)}
                              className="mt-0.5 text-teal-600"
                            />
                            <div className="flex-1 min-w-0">
                              <div className="flex items-center gap-2">
                                <span className="text-sm font-semibold text-slate-800">
                                  {m.label}
                                </span>
                                {m.recommended && (
                                  <span className="px-1.5 py-0.5 bg-teal-100 text-teal-700 text-xs font-bold rounded">
                                    Đề xuất
                                  </span>
                                )}
                                <span className="text-xs text-slate-400 ml-auto">
                                  {m.dimensions}d
                                </span>
                              </div>
                              <p className="text-xs text-slate-500 mt-0.5">
                                {m.description}
                              </p>
                            </div>
                          </label>
                        ))}
                      </div>
                    </div>
                  )}

                  {selectedProvider && (
                    <button
                      type="button"
                      onClick={() => {
                        setSelectedProvider(null);
                        setSelectedModel(null);
                      }}
                      className="text-xs text-slate-500 hover:text-slate-700 underline"
                    >
                      Dùng cấu hình mặc định
                    </button>
                  )}
                </div>
              )}
            </div>
          )}

          {/* Footer actions */}
          <div className="flex items-center justify-end gap-3 pt-2">
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
              disabled={loading || !isTrusted}
              className="flex items-center gap-2 px-5 py-2.5 bg-gradient-to-r from-teal-600 to-teal-700 hover:from-teal-700 hover:to-teal-800 disabled:opacity-60 disabled:cursor-not-allowed text-white rounded-xl font-semibold transition-all shadow-lg"
            >
              {loading ? (
                <>
                  <Loader className="w-4 h-4 animate-spin" />
                  Đang xử lý...
                </>
              ) : (
                <>
                  <Sparkles className="w-4 h-4" />
                  Thêm & xử lý
                </>
              )}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};

export { IngestSearchResultModal };
export default IngestSearchResultModal;
