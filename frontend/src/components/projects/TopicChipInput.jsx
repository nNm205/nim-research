import { useRef } from "react";
import { X, Tag } from "lucide-react";

/**
 * Tag-style chip editor for the project ``topic`` field.
 *
 * Used by both ``CreateProjectModal`` and the edit form in
 * ``ProjectDetailPage`` so the create / edit experience is identical.
 *
 * Props:
 *   topics: string[]            — current chips
 *   draft: string               — text in the live input
 *   onTopicsChange(next)        — replace the chip list
 *   onDraftChange(next)         — update the draft input
 *   placeholder?: string
 *   disabled?: boolean
 */
const TopicChipInput = ({
  topics,
  draft,
  onTopicsChange,
  onDraftChange,
  placeholder,
  disabled = false,
}) => {
  const inputRef = useRef(null);

  const addTopicFromDraft = () => {
    const value = draft.trim().replace(/,+$/, "").trim();
    if (!value) return;
    if (topics.some((t) => t.toLowerCase() === value.toLowerCase())) {
      onDraftChange("");
      return;
    }
    onTopicsChange([...topics, value]);
    onDraftChange("");
  };

  const handleKeyDown = (e) => {
    if (e.key === "Enter" || e.key === "," || e.key === "Tab") {
      if (draft.trim()) {
        e.preventDefault();
        addTopicFromDraft();
      }
    } else if (e.key === "Backspace" && !draft && topics.length > 0) {
      onTopicsChange(topics.slice(0, -1));
    }
  };

  const handlePaste = (e) => {
    const pasted = e.clipboardData.getData("text");
    if (!pasted.includes(",")) return;
    e.preventDefault();
    const items = pasted.split(",").map((s) => s.trim()).filter(Boolean);
    const merged = [...topics];
    for (const item of items) {
      if (!merged.some((t) => t.toLowerCase() === item.toLowerCase())) {
        merged.push(item);
      }
    }
    onTopicsChange(merged);
    onDraftChange("");
  };

  const removeTopic = (idx) => {
    onTopicsChange(topics.filter((_, i) => i !== idx));
  };

  const effectivePlaceholder =
    placeholder ??
    (topics.length === 0
      ? "Nhập chủ đề rồi Enter (ví dụ: Machine Learning)"
      : "Thêm chủ đề khác...");

  return (
    <div>
      <div
        onClick={() => inputRef.current?.focus()}
        className={`flex flex-wrap items-center gap-2 px-3 py-2 border border-slate-200 rounded-xl bg-white focus-within:ring-2 focus-within:ring-teal-500 focus-within:ring-offset-2 focus-within:border-transparent transition-all cursor-text min-h-[3rem] ${
          disabled ? "opacity-60 pointer-events-none" : ""
        }`}
      >
        {topics.map((t, idx) => (
          <span
            key={`${t}-${idx}`}
            className="inline-flex items-center gap-1.5 px-2.5 py-1 bg-violet-50 ring-1 ring-violet-200 text-violet-700 rounded-lg text-sm font-medium"
          >
            <Tag className="w-3 h-3" />
            {t}
            <button
              type="button"
              onClick={(e) => {
                e.stopPropagation();
                removeTopic(idx);
              }}
              className="ml-0.5 text-violet-400 hover:text-violet-700 transition-colors"
              aria-label={`Xóa chủ đề ${t}`}
            >
              <X className="w-3 h-3" />
            </button>
          </span>
        ))}

        <input
          ref={inputRef}
          type="text"
          value={draft}
          onChange={(e) => onDraftChange(e.target.value)}
          onKeyDown={handleKeyDown}
          onPaste={handlePaste}
          onBlur={() => draft.trim() && addTopicFromDraft()}
          disabled={disabled}
          className="flex-1 min-w-[10rem] outline-none bg-transparent text-slate-900 placeholder:text-slate-400 py-1"
          placeholder={effectivePlaceholder}
        />
      </div>
      <p className="text-xs text-slate-500 mt-2">
        Nhấn{" "}
        <kbd className="px-1.5 py-0.5 bg-slate-100 rounded font-mono text-[10px]">
          Enter
        </kbd>{" "}
        hoặc{" "}
        <kbd className="px-1.5 py-0.5 bg-slate-100 rounded font-mono text-[10px]">
          ,
        </kbd>{" "}
        để thêm;{" "}
        <kbd className="px-1.5 py-0.5 bg-slate-100 rounded font-mono text-[10px]">
          Backspace
        </kbd>{" "}
        để xóa chủ đề cuối.
      </p>
    </div>
  );
};

/**
 * Read-only display of project topics as colored chips. Used in
 * ProjectDetailPage (display mode) and ProjectCard.
 */
export const TopicChipList = ({ topics, max }) => {
  if (!topics || topics.length === 0) return null;
  const visible = max ? topics.slice(0, max) : topics;
  const overflow = max && topics.length > max ? topics.length - max : 0;

  return (
    <div className="flex flex-wrap items-center gap-2">
      {visible.map((t, idx) => (
        <span
          key={`${t}-${idx}`}
          className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-white ring-1 ring-violet-200 text-violet-700 rounded-lg text-sm font-medium hover:bg-violet-50 transition-colors"
        >
          <Tag className="w-3 h-3" />
          {t}
        </span>
      ))}
      {overflow > 0 && (
        <span className="inline-flex items-center px-2.5 py-1 bg-slate-50 ring-1 ring-slate-200 text-slate-500 rounded-lg text-xs font-medium">
          +{overflow} khác
        </span>
      )}
    </div>
  );
};

export default TopicChipInput;
