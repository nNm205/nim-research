import { useState, useEffect, useRef } from "react";
import {
  X,
  Globe,
  GraduationCap,
  Link as LinkIcon,
  Upload,
  Loader,
  AlertCircle,
  ChevronDown,
  Cpu,
  FileText,
  Trash2,
} from "lucide-react";
import { documentService } from "../../services/documentService";

const MODES = [
  { id: "url",    label: "Từ URL",     icon: LinkIcon },
  { id: "upload", label: "Tải file lên", icon: Upload  },
];

const SOURCE_TYPES = [
  { value: "web",      label: "Trang web",  icon: Globe         },
  { value: "academic", label: "Học thuật",  icon: GraduationCap },
];

// Files this modal accepts. Server enforces the same set.
const ACCEPTED_FILE_TYPES = ".pdf,.html,.htm";
const MAX_FILE_BYTES = 50 * 1024 * 1024; // keep in sync with backend

// ── Main component ───────────────────────────────────────────────────────────
//
// Two ingestion modes:
//   1. "Từ URL"     — paste a link, the server fetches + parses it.
//   2. "Tải file lên" — drop or pick a local PDF/HTML file.
//
// Both share the same embedding-provider selector at the bottom.
//
// Layout: backdrop is a soft `bg-black/20` (no blur) so the page underneath
// stays visible. The modal itself uses an internal flex column with the
// scrollable region hidden via the ``no-scrollbar`` utility (defined in
// index.css) — content can still scroll via wheel/keyboard, just without
// the visual weight of a scrollbar.
const CreateDocumentModal = ({ onClose, onCreate, projectId }) => {
  const [mode, setMode] = useState("url");

  return (
    <div className="fixed inset-0 bg-black/20 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-2xl max-w-2xl w-full max-h-[90vh] flex flex-col shadow-2xl overflow-hidden">
        {/* Header */}
        <div className="border-b border-slate-200 px-8 py-5 flex items-center justify-between flex-shrink-0">
          <h2 className="text-2xl font-bold text-slate-900">Thêm tài liệu mới</h2>
          <button
            onClick={onClose}
            className="text-slate-400 hover:text-slate-600 transition-colors p-1 hover:bg-slate-100 rounded-lg"
          >
            <X className="w-6 h-6" />
          </button>
        </div>

        {/* Mode tabs */}
        <div className="flex border-b border-slate-200 px-8 flex-shrink-0">
          {MODES.map(({ id, label, icon: Icon }) => (
            <button
              key={id}
              onClick={() => setMode(id)}
              className={`flex items-center gap-2 px-4 py-3.5 text-sm font-semibold border-b-2 transition-colors -mb-px ${
                mode === id
                  ? "border-teal-600 text-teal-700"
                  : "border-transparent text-slate-500 hover:text-slate-700"
              }`}
            >
              <Icon className="w-4 h-4" />
              {label}
            </button>
          ))}
        </div>

        {/* Body — scrollable but scrollbar hidden */}
        <div className="flex-1 overflow-y-auto no-scrollbar">
          {mode === "url" ? (
            <URLIngestForm
              projectId={projectId}
              onClose={onClose}
              onCreate={onCreate}
            />
          ) : (
            <FileUploadForm
              projectId={projectId}
              onClose={onClose}
              onCreate={onCreate}
            />
          )}
        </div>
      </div>
    </div>
  );
};

// ── Shared embedding-provider section ────────────────────────────────────────
//
// Both forms expose the same collapsible "Embedding Provider" picker so the
// user can override the default embedder for this single ingestion.
const EmbeddingProviderSection = ({
  providers,
  selectedProvider,
  setSelectedProvider,
  selectedModel,
  setSelectedModel,
  show,
  setShow,
}) => {
  if (providers.length === 0) return null;

  const currentModels =
    providers.find((p) => p.value === selectedProvider)?.models || [];

  const onChooseProvider = (providerValue) => {
    setSelectedProvider(providerValue);
    const providerData = providers.find((p) => p.value === providerValue);
    const recommended = providerData?.models.find((m) => m.recommended);
    setSelectedModel(recommended?.value || providerData?.models[0]?.value || null);
  };

  return (
    <div className="border border-slate-200 rounded-xl overflow-hidden">
      <button
        type="button"
        onClick={() => setShow(!show)}
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
          className={`w-4 h-4 text-slate-400 transition-transform ${show ? "rotate-180" : ""}`}
        />
      </button>

      {show && (
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
                      <p className="text-xs text-slate-500 mt-0.5">{m.description}</p>
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
  );
};

// ── Embedding provider hook (shared) ─────────────────────────────────────────

function useEmbeddingProviders() {
  const [providers, setProviders] = useState([]);
  const [selectedProvider, setSelectedProvider] = useState(null);
  const [selectedModel, setSelectedModel] = useState(null);
  const [show, setShow] = useState(false);

  useEffect(() => {
    documentService
      .getEmbeddingProviders()
      .then(setProviders)
      .catch(() => {});
  }, []);

  return {
    providers,
    selectedProvider,
    setSelectedProvider,
    selectedModel,
    setSelectedModel,
    show,
    setShow,
  };
}

// ── URL Ingest Form ──────────────────────────────────────────────────────────
const URLIngestForm = ({ projectId, onClose, onCreate }) => {
  const [url, setUrl] = useState("");
  const [sourceType, setSourceType] = useState("web");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const embedding = useEmbeddingProviders();

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!url.trim()) return;

    setError("");
    setLoading(true);
    try {
      const doc = await documentService.ingestFromURL(
        projectId,
        url.trim(),
        sourceType,
        embedding.selectedProvider,
        embedding.selectedModel,
      );
      onCreate(doc);
    } catch (err) {
      setError(
        err.response?.data?.detail ||
          "Không thể tải nội dung từ URL này. Hãy thử URL khác hoặc tải file lên trực tiếp.",
      );
    } finally {
      setLoading(false);
    }
  };

  return (
    <form onSubmit={handleSubmit} className="p-8 space-y-6">
      {error && (
        <div className="flex items-start gap-3 bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-xl text-sm">
          <AlertCircle className="w-4 h-4 flex-shrink-0 mt-0.5" />
          <span>{error}</span>
        </div>
      )}

      <div>
        <label className="block text-sm font-semibold text-slate-900 mb-3">
          Loại nguồn
        </label>
        <div className="flex gap-3">
          {SOURCE_TYPES.map(({ value, label, icon: Icon }) => (
            <button
              key={value}
              type="button"
              onClick={() => setSourceType(value)}
              className={`flex items-center gap-2 px-4 py-2.5 rounded-xl border-2 text-sm font-semibold transition-all ${
                sourceType === value
                  ? "border-teal-500 bg-teal-50 text-teal-700"
                  : "border-slate-200 text-slate-600 hover:border-slate-300"
              }`}
            >
              <Icon className="w-4 h-4" />
              {label}
            </button>
          ))}
        </div>
      </div>

      <div>
        <label className="block text-sm font-semibold text-slate-900 mb-2">
          URL tài liệu <span className="text-red-500">*</span>
        </label>
        <input
          type="url"
          required
          value={url}
          onChange={(e) => setUrl(e.target.value)}
          placeholder="https://arxiv.org/pdf/... hoặc https://example.com/article"
          className="w-full px-4 py-3 border border-slate-300 rounded-xl focus:outline-none focus:ring-2 focus:ring-teal-500 focus:border-transparent transition-all text-slate-900 text-sm"
        />
        <p className="text-xs text-slate-500 mt-2">
          Hỗ trợ: PDF (arXiv, PubMed, ...), trang web, bài báo khoa học
        </p>
      </div>

      <EmbeddingProviderSection {...embedding} />

      <div className="bg-teal-50 border border-teal-200 rounded-xl p-4 text-sm text-teal-800">
        <p className="font-semibold mb-1">Hệ thống sẽ tự động:</p>
        <ul className="space-y-1 text-teal-700">
          <li>• Tải và trích xuất nội dung từ URL</li>
          <li>• Chia nhỏ thành các đoạn (chunks)</li>
          <li>• Tạo vector embeddings để tìm kiếm ngữ nghĩa</li>
        </ul>
      </div>

      <FormActions
        onClose={onClose}
        loading={loading}
        disabled={!url.trim()}
        loadingLabel="Đang xử lý..."
        submitLabel="Tải & lưu tài liệu"
        SubmitIcon={Globe}
      />
    </form>
  );
};

// ── File Upload Form ─────────────────────────────────────────────────────────
const FileUploadForm = ({ projectId, onClose, onCreate }) => {
  const [file, setFile] = useState(null);
  const [dragActive, setDragActive] = useState(false);
  const [progress, setProgress] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const fileInputRef = useRef(null);
  const embedding = useEmbeddingProviders();

  const validateFile = (f) => {
    if (!f) return "Vui lòng chọn file";
    const lower = f.name.toLowerCase();
    const okExt =
      lower.endsWith(".pdf") || lower.endsWith(".html") || lower.endsWith(".htm");
    if (!okExt) return "Chỉ chấp nhận file PDF (.pdf) hoặc HTML (.html, .htm)";
    if (f.size > MAX_FILE_BYTES) {
      return `File quá lớn (tối đa ${MAX_FILE_BYTES / 1024 / 1024} MB)`;
    }
    return null;
  };

  const onPick = (f) => {
    const err = validateFile(f);
    if (err) {
      setError(err);
      setFile(null);
      return;
    }
    setError("");
    setFile(f);
  };

  const onDrop = (e) => {
    e.preventDefault();
    setDragActive(false);
    const f = e.dataTransfer?.files?.[0];
    if (f) onPick(f);
  };

  const onDragOver = (e) => {
    e.preventDefault();
    setDragActive(true);
  };

  const onDragLeave = () => setDragActive(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!file) return;

    setError("");
    setLoading(true);
    setProgress(0);
    try {
      const doc = await documentService.uploadFile(
        projectId,
        file,
        embedding.selectedProvider,
        embedding.selectedModel,
        (progressEvent) => {
          if (progressEvent.total) {
            const pct = Math.round(
              (progressEvent.loaded * 100) / progressEvent.total,
            );
            setProgress(pct);
          }
        },
      );
      onCreate(doc);
    } catch (err) {
      setError(
        err.response?.data?.detail ||
          "Không thể xử lý file này. Hãy thử file khác hoặc dùng URL.",
      );
    } finally {
      setLoading(false);
    }
  };

  return (
    <form onSubmit={handleSubmit} className="p-8 space-y-6">
      {error && (
        <div className="flex items-start gap-3 bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-xl text-sm">
          <AlertCircle className="w-4 h-4 flex-shrink-0 mt-0.5" />
          <span>{error}</span>
        </div>
      )}

      {/* Drop zone */}
      {!file && (
        <button
          type="button"
          onClick={() => fileInputRef.current?.click()}
          onDrop={onDrop}
          onDragOver={onDragOver}
          onDragLeave={onDragLeave}
          className={`w-full flex flex-col items-center justify-center gap-3 px-6 py-12 rounded-2xl border-2 border-dashed transition-all cursor-pointer ${
            dragActive
              ? "border-teal-500 bg-teal-50"
              : "border-slate-300 bg-slate-50 hover:border-slate-400 hover:bg-slate-100"
          }`}
        >
          <div
            className={`w-14 h-14 rounded-2xl flex items-center justify-center ${
              dragActive ? "bg-teal-100" : "bg-white border border-slate-200"
            }`}
          >
            <Upload
              className={`w-7 h-7 ${dragActive ? "text-teal-600" : "text-slate-500"}`}
            />
          </div>
          <div className="text-center">
            <p className="text-sm font-semibold text-slate-700">
              Kéo thả file vào đây hoặc{" "}
              <span className="text-teal-600">bấm để chọn</span>
            </p>
            <p className="text-xs text-slate-500 mt-1.5">
              PDF / HTML · tối đa {MAX_FILE_BYTES / 1024 / 1024} MB
            </p>
          </div>
          <input
            ref={fileInputRef}
            type="file"
            accept={ACCEPTED_FILE_TYPES}
            onChange={(e) => onPick(e.target.files?.[0])}
            className="hidden"
          />
        </button>
      )}

      {/* Selected file preview */}
      {file && (
        <div className="flex items-center gap-4 px-4 py-4 rounded-2xl border border-slate-200 bg-slate-50">
          <div className="w-12 h-12 rounded-xl bg-rose-50 border border-rose-200 flex items-center justify-center flex-shrink-0">
            <FileText className="w-5 h-5 text-rose-600" />
          </div>
          <div className="flex-1 min-w-0">
            <p className="text-sm font-semibold text-slate-900 truncate">
              {file.name}
            </p>
            <p className="text-xs text-slate-500 mt-0.5">
              {(file.size / 1024).toFixed(1)} KB
              {file.type && ` · ${file.type}`}
            </p>
            {loading && progress > 0 && (
              <div className="mt-2 h-1.5 bg-slate-200 rounded-full overflow-hidden">
                <div
                  className="h-full bg-teal-600 transition-all"
                  style={{ width: `${progress}%` }}
                />
              </div>
            )}
          </div>
          {!loading && (
            <button
              type="button"
              onClick={() => {
                setFile(null);
                if (fileInputRef.current) fileInputRef.current.value = "";
              }}
              className="text-slate-400 hover:text-red-600 transition-colors p-1.5 hover:bg-red-50 rounded-lg"
              aria-label="Bỏ chọn file"
            >
              <Trash2 className="w-4 h-4" />
            </button>
          )}
        </div>
      )}

      <EmbeddingProviderSection {...embedding} />

      <div className="bg-teal-50 border border-teal-200 rounded-xl p-4 text-sm text-teal-800">
        <p className="font-semibold mb-1">Hệ thống sẽ tự động:</p>
        <ul className="space-y-1 text-teal-700">
          <li>• Trích xuất nội dung văn bản, bảng và công thức</li>
          <li>• Chia nhỏ thành các đoạn (chunks)</li>
          <li>• Tạo vector embeddings để tìm kiếm ngữ nghĩa</li>
        </ul>
      </div>

      <FormActions
        onClose={onClose}
        loading={loading}
        disabled={!file}
        loadingLabel="Đang tải lên..."
        submitLabel="Tải lên & xử lý"
        SubmitIcon={Upload}
      />
    </form>
  );
};

// ── Shared submit/cancel button row ──────────────────────────────────────────
const FormActions = ({
  onClose,
  loading,
  disabled,
  loadingLabel,
  submitLabel,
  SubmitIcon,
}) => (
  <div className="flex items-center justify-end gap-3 pt-2">
    <button
      type="button"
      onClick={onClose}
      disabled={loading}
      className="px-6 py-3 border border-slate-200 rounded-xl text-slate-700 hover:bg-slate-50 font-semibold transition-colors disabled:opacity-50"
    >
      Hủy
    </button>
    <button
      type="submit"
      disabled={loading || disabled}
      className="flex items-center gap-2 px-6 py-3 bg-gradient-to-r from-teal-600 to-teal-700 hover:from-teal-700 hover:to-teal-800 disabled:opacity-60 disabled:cursor-not-allowed text-white rounded-xl font-semibold transition-all shadow-lg"
    >
      {loading ? (
        <>
          <Loader className="w-4 h-4 animate-spin" />
          {loadingLabel}
        </>
      ) : (
        <>
          {SubmitIcon && <SubmitIcon className="w-4 h-4" />}
          {submitLabel}
        </>
      )}
    </button>
  </div>
);

export default CreateDocumentModal;
