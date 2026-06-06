import { useState } from "react";
import { X } from "lucide-react";
import TopicChipInput from "./TopicChipInput";

/**
 * Modal that creates a new project.
 *
 * Topic input uses the shared TopicChipInput so the create / edit /
 * detail-view chip styling stays consistent.
 */
const CreateProjectModal = ({ onClose, onCreate }) => {
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [researchScope, setResearchScope] = useState("");
  const [topics, setTopics] = useState([]); // array of strings
  const [topicDraft, setTopicDraft] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError("");
    setLoading(true);

    // Accept any chip the user typed but didn't confirm with Enter.
    let finalTopics = topics;
    if (topicDraft.trim()) finalTopics = [...topics, topicDraft.trim()];

    try {
      await onCreate({
        name,
        description,
        topic: finalTopics.join(", "),
        research_scope: researchScope,
      });
    } catch (err) {
      setError(err.response?.data?.detail || "Không thể tạo dự án");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-black/20 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-2xl max-w-2xl w-full max-h-[90vh] flex flex-col shadow-2xl overflow-hidden">
        {/* Header */}
        <div className="border-b border-slate-200 px-8 py-5 flex items-center justify-between flex-shrink-0">
          <h2 className="text-2xl font-bold text-slate-900">Tạo dự án mới</h2>
          <button
            onClick={onClose}
            className="text-slate-400 hover:text-slate-600 transition-colors p-1 hover:bg-slate-100 rounded-lg"
          >
            <X className="w-6 h-6" />
          </button>
        </div>

        {/* Body — scrollable but scrollbar hidden */}
        <form
          onSubmit={handleSubmit}
          className="flex-1 overflow-y-auto no-scrollbar p-8 space-y-6"
        >
          {error && (
            <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-xl text-sm font-medium">
              {error}
            </div>
          )}

          <div>
            <label className="block text-sm font-semibold text-slate-900 mb-2">
              Tên dự án <span className="text-red-500">*</span>
            </label>
            <input
              type="text"
              required
              minLength={3}
              maxLength={255}
              value={name}
              onChange={(e) => setName(e.target.value)}
              className="w-full px-4 py-3 border border-slate-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-teal-500 focus:ring-offset-2 focus:border-transparent transition-all text-slate-900"
              placeholder="Ví dụ: Nghiên cứu ảnh hưởng của AI tới giáo dục"
            />
          </div>

          <div>
            <label className="block text-sm font-semibold text-slate-900 mb-2">
              Chủ đề <span className="text-slate-400">(Tùy chọn)</span>
            </label>
            <TopicChipInput
              topics={topics}
              draft={topicDraft}
              onTopicsChange={setTopics}
              onDraftChange={setTopicDraft}
            />
          </div>

          <div>
            <label className="block text-sm font-semibold text-slate-900 mb-2">
              Mô tả <span className="text-slate-400">(Tùy chọn)</span>
            </label>
            <textarea
              rows={4}
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              className="w-full px-4 py-3 border border-slate-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-teal-500 focus:ring-offset-2 focus:border-transparent transition-all resize-none text-slate-900"
              placeholder="Mô tả chi tiết về nội dung, mục tiêu và ý nghĩa của dự án nghiên cứu..."
            />
          </div>

          <div>
            <label className="block text-sm font-semibold text-slate-900 mb-2">
              Phạm vi nghiên cứu{" "}
              <span className="text-slate-400">(Tùy chọn)</span>
            </label>
            <textarea
              rows={4}
              value={researchScope}
              onChange={(e) => setResearchScope(e.target.value)}
              className="w-full px-4 py-3 border border-slate-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-teal-500 focus:ring-offset-2 focus:border-transparent transition-all resize-none text-slate-900"
              placeholder="Xác định phạm vi, giới hạn, các giả thuyết và mục tiêu cụ thể của dự án..."
            />
          </div>

          <div className="flex items-center justify-end gap-3 pt-6 border-t border-slate-200">
            <button
              type="button"
              onClick={onClose}
              className="px-6 py-3 border border-slate-200 rounded-xl text-slate-700 hover:bg-slate-50 font-semibold transition-colors"
            >
              Hủy
            </button>
            <button
              type="submit"
              disabled={loading}
              className="px-6 py-3 bg-gradient-to-r from-teal-600 to-teal-700 hover:from-teal-700 hover:to-teal-800 disabled:opacity-60 text-white rounded-xl font-semibold transition-all shadow-lg hover:shadow-xl"
            >
              {loading ? "Đang tạo..." : "Tạo dự án"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};

export default CreateProjectModal;
