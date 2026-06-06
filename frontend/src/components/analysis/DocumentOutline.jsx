import { BookOpen, Users, Tag, ChevronRight } from "lucide-react";

/**
 * Render the document_outline JSON object emitted by the AnalysisAgent.
 * Shape:
 *   {
 *     title, document_type, main_topics: [], primary_audience,
 *     sections: [{
 *       index, title, number, type, one_line_purpose,
 *       chunk_count, char_count,
 *       subsections: [{ number, title }]
 *     }]
 *   }
 */
const DocumentOutline = ({ outline, onSectionClick }) => {
  if (!outline || (!outline.title && !outline.sections?.length)) return null;

  const docTypeLabel = (outline.document_type || "").replace(/_/g, " ");

  return (
    <div className="space-y-5">
      {/* Type + audience */}
      {(outline.document_type || outline.primary_audience) && (
        <div className="flex flex-wrap gap-2">
          {outline.document_type && (
            <span className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-teal-50 border border-teal-100 text-teal-700 rounded-lg text-xs font-semibold capitalize">
              <BookOpen className="w-3.5 h-3.5" />
              {docTypeLabel}
            </span>
          )}
          {outline.primary_audience && (
            <span className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-slate-50 border border-slate-200 text-slate-700 rounded-lg text-xs font-medium">
              <Users className="w-3.5 h-3.5" />
              {outline.primary_audience}
            </span>
          )}
        </div>
      )}

      {/* Main topics */}
      {outline.main_topics?.length > 0 && (
        <div>
          <p className="text-xs font-bold text-slate-500 uppercase tracking-wide mb-2">
            Chủ đề chính
          </p>
          <div className="flex flex-wrap gap-2">
            {outline.main_topics.map((topic, idx) => (
              <span
                key={idx}
                className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-white border border-violet-200 text-violet-700 rounded-lg text-sm font-medium"
              >
                <Tag className="w-3 h-3" />
                {topic}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Section list with subsections */}
      {outline.sections?.length > 0 && (
        <div>
          <p className="text-xs font-bold text-slate-500 uppercase tracking-wide mb-2">
            Cấu trúc tài liệu
          </p>
          <ol className="space-y-2">
            {outline.sections.map((sec) => (
              <SectionRow
                key={sec.index}
                section={sec}
                onClick={onSectionClick}
              />
            ))}
          </ol>
        </div>
      )}
    </div>
  );
};

const SectionRow = ({ section, onClick }) => {
  const hasSubs = section.subsections && section.subsections.length > 0;
  const numberLabel = section.number || `${section.index + 1}`;

  return (
    <li>
      <div
        onClick={() => onClick && onClick(section.index)}
        className={`flex items-start gap-3 bg-white rounded-xl border border-slate-200 p-3 ${
          onClick
            ? "cursor-pointer hover:border-teal-300 hover:shadow-sm transition-all"
            : ""
        }`}
      >
        <span className="flex-shrink-0 w-9 h-9 rounded-lg bg-teal-100 text-teal-700 text-xs font-bold flex items-center justify-center font-mono">
          {numberLabel}
        </span>
        <div className="flex-1 min-w-0">
          <div className="flex items-baseline gap-2 flex-wrap">
            <span className="font-semibold text-slate-800 text-sm">
              {section.title}
            </span>
            {section.type && (
              <span className="px-1.5 py-0.5 bg-slate-100 text-slate-600 rounded text-[10px] font-bold uppercase">
                {section.type.replace(/_/g, " ")}
              </span>
            )}
          </div>
          {section.one_line_purpose && (
            <p className="text-xs text-slate-500 mt-1 leading-snug">
              {section.one_line_purpose}
            </p>
          )}
          {(section.chunk_count || section.char_count) && (
            <p className="text-[11px] text-slate-400 mt-1 font-mono">
              {section.chunk_count ? `${section.chunk_count} chunks` : ""}
              {section.chunk_count && section.char_count ? " · " : ""}
              {section.char_count
                ? `${section.char_count.toLocaleString()} ký tự`
                : ""}
            </p>
          )}
        </div>
        {hasSubs && (
          <span className="px-1.5 py-0.5 bg-slate-100 text-slate-600 rounded text-[10px] font-bold shrink-0">
            {section.subsections.length} mục con
          </span>
        )}
      </div>

      {/* Indented subsection list */}
      {hasSubs && (
        <ul className="mt-1.5 ml-12 space-y-1">
          {section.subsections.map((sub, i) => (
            <li
              key={`${sub.number}-${i}`}
              className="flex items-start gap-2 px-3 py-1.5 text-sm text-slate-700"
            >
              <ChevronRight className="w-3 h-3 text-slate-300 mt-1 shrink-0" />
              <span className="font-mono text-[11px] font-bold text-slate-500 shrink-0 mt-0.5">
                {sub.number}
              </span>
              <span className="leading-snug">{sub.title}</span>
            </li>
          ))}
        </ul>
      )}
    </li>
  );
};

export default DocumentOutline;
