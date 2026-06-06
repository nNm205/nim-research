import { useState, useMemo, Component } from "react";
import { BlockMath, InlineMath } from "react-katex";
import "katex/dist/katex.min.css";
import {
  ChevronDown,
  FlaskConical,
  Database,
  BookOpen,
  Link2,
  ShieldCheck,
  ShieldAlert,
  Lightbulb,
  HelpCircle,
  Table as TableIcon,
  Sigma,
  ListTree,
  ScrollText,
  Beaker,
  MessageSquareQuote,
} from "lucide-react";

// ── Visual config ────────────────────────────────────────────────────────────
//
// Section-type styling lives here so the rest of the component stays focused
// on layout. Colours map onto the same palette used elsewhere in the app:
// teal as the primary accent, slate as the neutral baseline.

const SECTION_TYPE_STYLE = {
  abstract:        { tone: "slate",   label: "Abstract" },
  introduction:    { tone: "blue",    label: "Introduction" },
  background:      { tone: "indigo",  label: "Background" },
  related_work:    { tone: "indigo",  label: "Related Work" },
  methodology:     { tone: "violet",  label: "Methodology" },
  methods:         { tone: "violet",  label: "Methods" },
  results:         { tone: "emerald", label: "Results" },
  experiments:     { tone: "emerald", label: "Experiments" },
  discussion:      { tone: "cyan",    label: "Discussion" },
  conclusion:      { tone: "teal",    label: "Conclusion" },
  limitations:     { tone: "amber",   label: "Limitations" },
  future_work:     { tone: "fuchsia", label: "Future Work" },
  references:      { tone: "slate",   label: "References" },
  appendix:        { tone: "slate",   label: "Appendix" },
  acknowledgments: { tone: "slate",   label: "Acknowledgments" },
  other:           { tone: "slate",   label: "Section" },
};

const TONE_CLASSES = {
  slate:   { soft: "bg-slate-50",   chip: "bg-slate-100 text-slate-700",   ring: "ring-slate-200",   text: "text-slate-700"   },
  blue:    { soft: "bg-blue-50",    chip: "bg-blue-100 text-blue-700",     ring: "ring-blue-200",    text: "text-blue-700"    },
  indigo:  { soft: "bg-indigo-50",  chip: "bg-indigo-100 text-indigo-700", ring: "ring-indigo-200",  text: "text-indigo-700"  },
  violet:  { soft: "bg-violet-50",  chip: "bg-violet-100 text-violet-700", ring: "ring-violet-200",  text: "text-violet-700"  },
  emerald: { soft: "bg-emerald-50", chip: "bg-emerald-100 text-emerald-700", ring: "ring-emerald-200", text: "text-emerald-700" },
  cyan:    { soft: "bg-cyan-50",    chip: "bg-cyan-100 text-cyan-700",     ring: "ring-cyan-200",    text: "text-cyan-700"    },
  teal:    { soft: "bg-teal-50",    chip: "bg-teal-100 text-teal-700",     ring: "ring-teal-200",    text: "text-teal-700"    },
  amber:   { soft: "bg-amber-50",   chip: "bg-amber-100 text-amber-700",   ring: "ring-amber-200",   text: "text-amber-700"   },
  fuchsia: { soft: "bg-fuchsia-50", chip: "bg-fuchsia-100 text-fuchsia-700", ring: "ring-fuchsia-200", text: "text-fuchsia-700" },
};

const styleFor = (sectionType) => {
  const cfg = SECTION_TYPE_STYLE[sectionType] || SECTION_TYPE_STYLE.other;
  const tone = TONE_CLASSES[cfg.tone] || TONE_CLASSES.slate;
  return { ...cfg, ...tone };
};

const evidenceBadge = (t) => {
  const map = {
    experimental: "bg-blue-50 text-blue-700 ring-1 ring-blue-200",
    theoretical:  "bg-violet-50 text-violet-700 ring-1 ring-violet-200",
    citation:     "bg-teal-50 text-teal-700 ring-1 ring-teal-200",
    statistical:  "bg-indigo-50 text-indigo-700 ring-1 ring-indigo-200",
    anecdotal:    "bg-amber-50 text-amber-700 ring-1 ring-amber-200",
  };
  return map[t] || "bg-slate-50 text-slate-600 ring-1 ring-slate-200";
};

const confidenceBadge = (level) => {
  if (level === "high")   return "bg-emerald-50 text-emerald-700 ring-1 ring-emerald-200";
  if (level === "medium") return "bg-amber-50 text-amber-700 ring-1 ring-amber-200";
  if (level === "low")    return "bg-red-50 text-red-700 ring-1 ring-red-200";
  return "bg-slate-50 text-slate-600 ring-1 ring-slate-200";
};

// ── Main Card ─────────────────────────────────────────────────────────────────
//
// Layout philosophy:
//
//   ┌──────────────────────────────────────────────────────────────────┐
//   │ Header (always visible)                                          │
//   │   • number badge + section title + type chip                     │
//   │   • 1-line summary preview                                       │
//   │   • compact stats row (claims · tables · formulas · subsections) │
//   ├──────────────────────────────────────────────────────────────────┤
//   │ Body (when expanded) — three tab views                           │
//   │   ┌─────────────┬───────────────┬──────────────────────────────┐ │
//   │   │ Tổng quan   │ Bằng chứng    │ Phản biện                    │ │
//   │   └─────────────┴───────────────┴──────────────────────────────┘ │
//   │                                                                  │
//   │  Tổng quan: summary (full) · key_points · subsections · terms    │
//   │  Bằng chứng: claims · methods · data · tables · formulas         │
//   │  Phản biện: critique · open questions · quotes · connections     │
//   └──────────────────────────────────────────────────────────────────┘
//
// Tabs only render if they have content. If only the overview tab has
// anything to show, the tab bar disappears entirely.

const SectionInsightCard = ({ section, defaultOpen = false }) => {
  const [open, setOpen] = useState(defaultOpen);
  const [tab, setTab] = useState("overview");

  const subsections = useMemo(
    () => section?.subsections || [],
    [section]
  );
  const critique = useMemo(
    () => section?.critique || {},
    [section]
  );

  const counts = useMemo(
    () => ({
      keyPoints: section?.key_points?.length || 0,
      claims: section?.claims?.length || 0,
      methods: section?.methods_or_techniques?.length || 0,
      data: section?.data_or_experiments?.length || 0,
      tables: section?.tables?.length || 0,
      formulas: section?.formulas?.length || 0,
      terms: section?.notable_terms?.length || 0,
      quotes: section?.notable_quotes?.length || 0,
      connections: section?.connections?.length || 0,
      openQuestions: section?.open_questions?.length || 0,
      subsections: subsections.length,
      critiqueStrengths: critique.strengths?.length || 0,
      critiqueWeaknesses: critique.weaknesses?.length || 0,
      critiqueAssumptions: critique.assumptions?.length || 0,
    }),
    [section, subsections.length, critique]
  );

  const hasOverview =
    !!section?.summary ||
    !!section?.purpose ||
    counts.keyPoints > 0 ||
    counts.terms > 0 ||
    counts.subsections > 0;

  const hasEvidence =
    counts.claims +
      counts.methods +
      counts.data +
      counts.tables +
      counts.formulas >
    0;

  const hasCritique =
    counts.critiqueStrengths +
      counts.critiqueWeaknesses +
      counts.critiqueAssumptions +
      counts.quotes +
      counts.connections +
      counts.openQuestions >
    0;

  // Pick the first non-empty tab as the default whenever the active one is
  // empty (e.g. user collapsed and reopened with content removed).
  const activeTab = useMemo(() => {
    const candidates = [
      ["overview", hasOverview],
      ["evidence", hasEvidence],
      ["critique", hasCritique],
    ];
    const current = candidates.find(([key]) => key === tab);
    if (current && current[1]) return tab;
    const first = candidates.find(([, has]) => has);
    return first ? first[0] : "overview";
  }, [tab, hasOverview, hasEvidence, hasCritique]);

  if (!section) return null;

  const hasAnyContent = hasOverview || hasEvidence || hasCritique;

  const style = styleFor(section.section_type);

  return (
    <div className="bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden hover:shadow-md transition-shadow">
      {/* ── Card header ───────────────────────────────────────────────── */}
      <button
        onClick={() => setOpen((v) => !v)}
        className="w-full flex items-start gap-4 px-5 py-4 hover:bg-slate-50/60 transition-colors text-left"
      >
        <div
          className={`flex-shrink-0 w-11 h-11 rounded-xl ${style.chip} flex items-center justify-center font-bold text-sm`}
        >
          {section.number || (section.section_index ?? 0) + 1}
        </div>

        <div className="min-w-0 flex-1 space-y-1.5">
          <div className="flex items-center gap-2 flex-wrap">
            <h4 className="text-base font-bold text-slate-900 leading-tight">
              {section.title || "Untitled section"}
            </h4>
            <span
              className={`px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wide ${style.chip}`}
            >
              {style.label}
            </span>
            {!hasAnyContent && (
              <span className="px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wide bg-amber-50 text-amber-700 ring-1 ring-amber-200">
                Trống
              </span>
            )}
          </div>

          {!open && (section.summary || section.purpose) && (
            <p className="text-sm text-slate-600 line-clamp-2 leading-snug">
              {section.summary || section.purpose}
            </p>
          )}

          <div className="flex items-center gap-2 flex-wrap">
            {section.chunk_indices?.length > 0 && (
              <MetaChip>
                {section.chunk_indices.length} chunk
                {section.chunk_indices.length > 1 ? "s" : ""}
              </MetaChip>
            )}
            {counts.subsections > 0 && (
              <MetaChip icon={ListTree}>
                {counts.subsections} mục con
              </MetaChip>
            )}
            {counts.claims > 0 && (
              <MetaChip icon={Lightbulb} color="text-amber-600">
                {counts.claims} claim
              </MetaChip>
            )}
            {counts.tables > 0 && (
              <MetaChip icon={TableIcon} color="text-emerald-600">
                {counts.tables} bảng
              </MetaChip>
            )}
            {counts.formulas > 0 && (
              <MetaChip icon={Sigma} color="text-indigo-600">
                {counts.formulas} công thức
              </MetaChip>
            )}
          </div>
        </div>

        <ChevronDown
          className={`w-5 h-5 text-slate-400 flex-shrink-0 transition-transform duration-200 mt-1 ${
            open ? "rotate-180" : ""
          }`}
        />
      </button>

      {/* ── Card body ─────────────────────────────────────────────────── */}
      {open && (
        <div className="border-t border-slate-100">
          {!hasAnyContent ? (
            <div className="m-5 px-4 py-3 bg-amber-50 ring-1 ring-amber-100 rounded-xl text-sm text-amber-800 leading-relaxed">
              LLM không trả về nội dung phân tích cho phần này. Có thể do nội
              dung quá ngắn, JSON không hợp lệ, hoặc bị chặn bởi safety
              filter. Thử chạy lại phân tích hoặc đổi LLM provider.
            </div>
          ) : (
            <>
              {/* Tab bar — only shown when more than one tab has content */}
              {[hasOverview, hasEvidence, hasCritique].filter(Boolean).length >
                1 && (
                <div className="flex items-center gap-1 px-5 pt-4 border-b border-slate-100">
                  {hasOverview && (
                    <Tab
                      label="Tổng quan"
                      icon={ScrollText}
                      active={activeTab === "overview"}
                      onClick={() => setTab("overview")}
                    />
                  )}
                  {hasEvidence && (
                    <Tab
                      label="Bằng chứng"
                      icon={Beaker}
                      active={activeTab === "evidence"}
                      onClick={() => setTab("evidence")}
                      count={
                        counts.claims +
                        counts.methods +
                        counts.data +
                        counts.tables +
                        counts.formulas
                      }
                    />
                  )}
                  {hasCritique && (
                    <Tab
                      label="Phản biện"
                      icon={ShieldCheck}
                      active={activeTab === "critique"}
                      onClick={() => setTab("critique")}
                      count={
                        counts.critiqueStrengths +
                        counts.critiqueWeaknesses +
                        counts.critiqueAssumptions +
                        counts.quotes +
                        counts.connections +
                        counts.openQuestions
                      }
                    />
                  )}
                </div>
              )}

              <div className="p-5">
                {activeTab === "overview" && (
                  <OverviewTab
                    section={section}
                    counts={counts}
                    subsections={subsections}
                  />
                )}
                {activeTab === "evidence" && (
                  <EvidenceTab section={section} counts={counts} />
                )}
                {activeTab === "critique" && (
                  <CritiqueTab
                    section={section}
                    counts={counts}
                    critique={critique}
                  />
                )}
              </div>
            </>
          )}
        </div>
      )}
    </div>
  );
};

// ── Tabs ────────────────────────────────────────────────────────────────────

const OverviewTab = ({ section, counts, subsections }) => (
  <div className="space-y-4">
    {(section.summary || section.purpose) && (
      <div>
        {section.summary && (
          <p className="text-slate-700 leading-relaxed whitespace-pre-wrap text-[15px]">
            {section.summary}
          </p>
        )}
        {section.purpose && (
          <div className="mt-3 pt-3 border-t border-slate-100 text-sm text-slate-600 flex items-start gap-2">
            <span className="text-teal-600 font-semibold shrink-0">Vai trò:</span>
            <span className="italic">{section.purpose}</span>
          </div>
        )}
      </div>
    )}

    {counts.keyPoints > 0 && (
      <Block icon={Lightbulb} color="amber" title="Ý chính">
        <ul className="space-y-1.5">
          {section.key_points.map((p, i) => (
            <li
              key={i}
              className="flex items-start gap-2 text-[14px] text-slate-700 leading-relaxed"
            >
              <span className="text-amber-500 mt-1 shrink-0">▸</span>
              <span>{p}</span>
            </li>
          ))}
        </ul>
      </Block>
    )}

    {counts.subsections > 0 && (
      <Block icon={ListTree} color="slate" title={`Mục con (${counts.subsections})`}>
        <ul className="grid grid-cols-1 sm:grid-cols-2 gap-2">
          {subsections.map((sub, i) => (
            <li
              key={`${sub.number}-${i}`}
              className="flex items-start gap-2 px-3 py-2 bg-slate-50 rounded-lg ring-1 ring-slate-200 text-sm"
            >
              <span className="font-mono text-[11px] font-bold text-slate-500 shrink-0 mt-0.5">
                {sub.number}
              </span>
              <span className="text-slate-700 leading-snug">{sub.title}</span>
            </li>
          ))}
        </ul>
      </Block>
    )}

    {counts.terms > 0 && (
      <Block icon={BookOpen} color="teal" title={`Thuật ngữ (${counts.terms})`}>
        <dl className="grid grid-cols-1 md:grid-cols-2 gap-2">
          {section.notable_terms.map((t, i) => (
            <div
              key={i}
              className="bg-slate-50 rounded-lg ring-1 ring-slate-200 px-3 py-2"
            >
              <dt className="text-sm font-bold text-teal-700">{t.term}</dt>
              {t.definition && (
                <dd className="text-xs text-slate-600 mt-0.5 leading-snug">
                  {t.definition}
                </dd>
              )}
            </div>
          ))}
        </dl>
      </Block>
    )}
  </div>
);

const EvidenceTab = ({ section, counts }) => (
  <div className="space-y-5">
    {counts.claims > 0 && (
      <Block
        icon={Lightbulb}
        color="violet"
        title={`Khẳng định & bằng chứng (${counts.claims})`}
      >
        <div className="space-y-2">
          {section.claims.map((c, i) => (
            <ClaimRow key={i} claim={c} />
          ))}
        </div>
      </Block>
    )}

    {counts.methods > 0 && (
      <Block icon={FlaskConical} color="violet" title="Phương pháp & kỹ thuật">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
          {section.methods_or_techniques.map((m, i) => (
            <div
              key={i}
              className="bg-slate-50 rounded-lg ring-1 ring-slate-200 px-3 py-2.5"
            >
              <p className="text-sm font-bold text-slate-800">{m.name}</p>
              {m.role && (
                <p className="text-xs text-slate-600 mt-1 leading-snug">
                  {m.role}
                </p>
              )}
            </div>
          ))}
        </div>
      </Block>
    )}

    {counts.data > 0 && (
      <Block icon={Database} color="blue" title="Dữ liệu & thực nghiệm">
        <div className="space-y-2">
          {section.data_or_experiments.map((d, i) => (
            <div
              key={i}
              className="bg-slate-50 rounded-lg ring-1 ring-slate-200 px-3 py-2.5"
            >
              {d.kind && (
                <span className="inline-block px-1.5 py-0.5 bg-blue-100 text-blue-700 rounded text-[10px] font-bold uppercase mb-1.5 tracking-wide">
                  {d.kind.replace(/_/g, " ")}
                </span>
              )}
              <p className="text-sm text-slate-700 leading-relaxed">
                {d.description}
              </p>
            </div>
          ))}
        </div>
      </Block>
    )}

    {counts.tables > 0 && (
      <Block icon={TableIcon} color="emerald" title={`Bảng (${counts.tables})`}>
        <div className="space-y-3">
          {section.tables.map((t, i) => (
            <TableBlock key={i} table={t} />
          ))}
        </div>
      </Block>
    )}

    {counts.formulas > 0 && (
      <Block icon={Sigma} color="indigo" title={`Công thức (${counts.formulas})`}>
        <div className="space-y-3">
          {section.formulas.map((f, i) => (
            <FormulaBlock key={i} formula={f} />
          ))}
        </div>
      </Block>
    )}
  </div>
);

const CritiqueTab = ({ section, counts, critique }) => (
  <div className="space-y-5">
    {(counts.critiqueStrengths +
      counts.critiqueWeaknesses +
      counts.critiqueAssumptions >
      0) && (
      <Block icon={ShieldCheck} color="slate" title="Đánh giá phản biện">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
          {counts.critiqueStrengths > 0 && (
            <CritiqueGroup
              label="Điểm mạnh"
              items={critique.strengths}
              color="emerald"
              icon={ShieldCheck}
            />
          )}
          {counts.critiqueWeaknesses > 0 && (
            <CritiqueGroup
              label="Điểm yếu"
              items={critique.weaknesses}
              color="red"
              icon={ShieldAlert}
            />
          )}
          {counts.critiqueAssumptions > 0 && (
            <CritiqueGroup
              label="Giả định"
              items={critique.assumptions}
              color="amber"
            />
          )}
        </div>
      </Block>
    )}

    {counts.openQuestions > 0 && (
      <Block icon={HelpCircle} color="indigo" title="Câu hỏi mở">
        <ul className="space-y-1.5">
          {section.open_questions.map((q, i) => (
            <li
              key={i}
              className="flex items-start gap-2 px-3 py-2 bg-indigo-50 rounded-lg ring-1 ring-indigo-100 text-sm text-slate-700 leading-snug"
            >
              <span className="text-indigo-500 font-bold mt-0.5 shrink-0">
                ?
              </span>
              <span>{q}</span>
            </li>
          ))}
        </ul>
      </Block>
    )}

    {counts.quotes > 0 && (
      <Block icon={MessageSquareQuote} color="slate" title="Trích dẫn đáng chú ý">
        <div className="space-y-2">
          {section.notable_quotes.map((q, i) => (
            <blockquote
              key={i}
              className="border-l-2 border-teal-400 bg-slate-50 px-3 py-2 rounded-r-lg"
            >
              <p className="text-sm text-slate-700 italic leading-relaxed">
                &ldquo;{q.quote}&rdquo;
              </p>
              {q.chunk_index !== undefined && q.chunk_index !== null && (
                <p className="text-[10px] text-teal-600 mt-1 font-mono">
                  chunk #{q.chunk_index}
                </p>
              )}
            </blockquote>
          ))}
        </div>
      </Block>
    )}

    {counts.connections > 0 && (
      <Block icon={Link2} color="cyan" title="Liên kết tới phần khác">
        <div className="space-y-2">
          {section.connections.map((c, i) => (
            <div
              key={i}
              className="flex items-start gap-2 bg-slate-50 rounded-lg ring-1 ring-slate-200 px-3 py-2"
            >
              <span className="px-1.5 py-0.5 bg-cyan-100 text-cyan-700 rounded text-[10px] font-bold uppercase shrink-0 tracking-wide">
                {(c.relation || "").replace(/_/g, " ")}
              </span>
              <div className="min-w-0 flex-1">
                <p className="text-sm font-semibold text-slate-800 leading-snug">
                  → {c.to_section}
                </p>
                {c.note && (
                  <p className="text-xs text-slate-600 mt-0.5">{c.note}</p>
                )}
              </div>
            </div>
          ))}
        </div>
      </Block>
    )}
  </div>
);

// ── Helper components ────────────────────────────────────────────────────────

const Tab = ({ label, icon: Icon, active, onClick, count }) => (
  <button
    onClick={onClick}
    className={`relative inline-flex items-center gap-1.5 px-4 py-2.5 text-sm font-semibold border-b-2 transition-colors ${
      active
        ? "border-teal-600 text-teal-700"
        : "border-transparent text-slate-500 hover:text-slate-700"
    }`}
  >
    {Icon && <Icon className="w-4 h-4" />}
    {label}
    {count !== undefined && count > 0 && (
      <span
        className={`ml-1 px-1.5 py-0.5 rounded text-[10px] font-bold ${
          active ? "bg-teal-100 text-teal-700" : "bg-slate-100 text-slate-500"
        }`}
      >
        {count}
      </span>
    )}
  </button>
);

const MetaChip = ({ children, icon: Icon, color }) => (
  <span className="inline-flex items-center gap-1 px-2 py-0.5 bg-slate-50 ring-1 ring-slate-200 text-slate-600 rounded text-[11px] font-medium">
    {Icon && <Icon className={`w-3 h-3 ${color || ""}`} />}
    {children}
  </span>
);

const Block = ({ icon: Icon, color, title, children }) => {
  const colorClasses = {
    amber:   "text-amber-700",
    violet:  "text-violet-700",
    blue:    "text-blue-700",
    emerald: "text-emerald-700",
    indigo:  "text-indigo-700",
    teal:    "text-teal-700",
    cyan:    "text-cyan-700",
    slate:   "text-slate-700",
    red:     "text-red-700",
  };
  return (
    <div>
      <div
        className={`flex items-center gap-2 mb-2.5 ${
          colorClasses[color] || colorClasses.slate
        }`}
      >
        <Icon className="w-3.5 h-3.5" />
        <h5 className="text-[11px] font-bold uppercase tracking-wider">
          {title}
        </h5>
      </div>
      {children}
    </div>
  );
};

const ClaimRow = ({ claim }) => (
  <div className="bg-slate-50 rounded-lg ring-1 ring-slate-200 px-3 py-2.5">
    <p className="text-sm text-slate-800 font-medium leading-snug mb-1.5">
      {claim.claim}
    </p>
    {claim.supporting_evidence && (
      <p className="text-xs text-slate-600 leading-relaxed mb-1.5">
        <span className="font-semibold text-slate-500">Bằng chứng:</span>{" "}
        {claim.supporting_evidence}
      </p>
    )}
    {(claim.evidence_type || claim.confidence) && (
      <div className="flex items-center gap-1.5 flex-wrap">
        {claim.evidence_type && (
          <span
            className={`px-1.5 py-0.5 rounded text-[10px] font-bold uppercase tracking-wide ${evidenceBadge(
              claim.evidence_type
            )}`}
          >
            {claim.evidence_type}
          </span>
        )}
        {claim.confidence && (
          <span
            className={`px-1.5 py-0.5 rounded text-[10px] font-bold uppercase tracking-wide ${confidenceBadge(
              claim.confidence
            )}`}
          >
            tin cậy: {claim.confidence}
          </span>
        )}
      </div>
    )}
  </div>
);

const CritiqueGroup = ({ label, items, color, icon: Icon }) => {
  const palette = {
    emerald: { bg: "bg-emerald-50", ring: "ring-emerald-100", text: "text-emerald-700", dot: "text-emerald-500" },
    red:     { bg: "bg-red-50",     ring: "ring-red-100",     text: "text-red-700",     dot: "text-red-400" },
    amber:   { bg: "bg-amber-50",   ring: "ring-amber-100",   text: "text-amber-700",   dot: "text-amber-500" },
  };
  const p = palette[color] || palette.amber;
  return (
    <div className={`${p.bg} rounded-lg ring-1 ${p.ring} px-3 py-2.5`}>
      <div className={`flex items-center gap-1.5 mb-1.5 ${p.text}`}>
        {Icon && <Icon className="w-3 h-3" />}
        <span className="text-[10px] font-bold uppercase tracking-wider">
          {label}
        </span>
      </div>
      <ul className="space-y-1">
        {items.map((s, i) => (
          <li
            key={i}
            className="text-xs text-slate-700 flex items-start gap-1.5 leading-snug"
          >
            <span className={`${p.dot} shrink-0`}>•</span>
            <span>{s}</span>
          </li>
        ))}
      </ul>
    </div>
  );
};

// ── TableBlock ───────────────────────────────────────────────────────────────
//
// Heuristic: cells that look numeric (digits + optional . , % or unit) are
// right-aligned with tabular numbers so columns of metrics line up cleanly.

const _NUM_RE = /^[-+]?\d[\d\s.,]*(?:\s*[%×x]\s*)?$/;
const isNumeric = (cell) => _NUM_RE.test(String(cell || "").trim());

const TableBlock = ({ table }) => {
  const headers = useMemo(
    () => (Array.isArray(table?.headers) ? table.headers : []),
    [table]
  );
  const rows = useMemo(
    () => (Array.isArray(table?.rows) ? table.rows : []),
    [table]
  );
  const cols = Math.max(headers.length, ...rows.map((r) => r.length), 1);

  // For each column, decide if it's a numeric column based on the majority of
  // its values. This drives right-alignment + tabular-nums.
  const colIsNumeric = useMemo(() => {
    const out = new Array(cols).fill(false);
    for (let c = 0; c < cols; c++) {
      let numeric = 0;
      let total = 0;
      for (const r of rows) {
        const v = (r || [])[c];
        if (v == null || String(v).trim() === "") continue;
        total += 1;
        if (isNumeric(v)) numeric += 1;
      }
      out[c] = total > 0 && numeric / total >= 0.6;
    }
    return out;
  }, [rows, cols]);

  if (!table) return null;

  const padded = (cells) => {
    const out = (cells || []).slice(0, cols).map((c) => (c == null ? "" : String(c)));
    while (out.length < cols) out.push("");
    return out;
  };

  return (
    <div className="bg-white rounded-xl ring-1 ring-emerald-200 overflow-hidden">
      {(table.title || table.chunk_index !== undefined) && (
        <div className="px-4 py-2.5 bg-emerald-50/70 flex items-baseline justify-between gap-3 flex-wrap border-b border-emerald-100">
          <p className="font-bold text-emerald-900 text-sm flex items-center gap-1.5">
            <TableIcon className="w-3.5 h-3.5" />
            {table.title || "Bảng"}
          </p>
          {table.chunk_index !== undefined && table.chunk_index !== null && (
            <span className="text-[10px] text-emerald-700 font-mono">
              chunk #{table.chunk_index}
            </span>
          )}
        </div>
      )}

      {(headers.length > 0 || rows.length > 0) && (
        <div className="overflow-x-auto">
          <table className="w-full text-sm border-collapse">
            {headers.length > 0 && (
              <thead>
                <tr>
                  {padded(headers).map((h, i) => (
                    <th
                      key={i}
                      className={`px-3 py-2 font-semibold text-emerald-900 bg-emerald-50/40 border-b border-emerald-200 whitespace-nowrap ${
                        colIsNumeric[i] ? "text-right" : "text-left"
                      }`}
                    >
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
            )}
            <tbody>
              {rows.map((r, ri) => (
                <tr
                  key={ri}
                  className="border-b border-emerald-50 last:border-0 hover:bg-emerald-50/20"
                >
                  {padded(r).map((c, ci) => (
                    <td
                      key={ci}
                      className={`px-3 py-2 text-slate-700 ${
                        colIsNumeric[ci]
                          ? "text-right font-mono tabular-nums"
                          : "text-left"
                      }`}
                    >
                      {c}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {(table.summary || table.key_finding) && (
        <div className="px-4 py-2.5 border-t border-emerald-100 bg-white space-y-1.5">
          {table.summary && (
            <p className="text-xs text-slate-700 leading-relaxed">
              <span className="font-semibold text-emerald-700">Tóm tắt: </span>
              {table.summary}
            </p>
          )}
          {table.key_finding && (
            <p className="text-xs text-slate-700 leading-relaxed">
              <span className="font-semibold text-emerald-700">Phát hiện: </span>
              {table.key_finding}
            </p>
          )}
        </div>
      )}
    </div>
  );
};

// ── FormulaBlock with KaTeX ──────────────────────────────────────────────────

const FormulaBlock = ({ formula }) => {
  if (!formula) return null;
  const expression = (formula.expression || "").trim();
  if (!expression) return null;
  const variables = Array.isArray(formula.variables) ? formula.variables : [];
  const latex = (formula.latex || "").trim();

  return (
    <div className="bg-white rounded-xl ring-1 ring-indigo-200 overflow-hidden">
      <div className="px-4 py-2.5 bg-indigo-50/70 flex items-baseline justify-between gap-3 flex-wrap border-b border-indigo-100">
        <p className="font-bold text-indigo-900 text-sm flex items-center gap-1.5">
          <Sigma className="w-3.5 h-3.5" />
          {formula.label ? `Phương trình ${formula.label}` : "Phương trình"}
        </p>
        {formula.chunk_index !== undefined && formula.chunk_index !== null && (
          <span className="text-[10px] text-indigo-700 font-mono">
            chunk #{formula.chunk_index}
          </span>
        )}
      </div>

      {/* Rendered formula — center-aligned, scrollable on overflow */}
      <div className="px-4 py-4 bg-white border-b border-indigo-50 overflow-x-auto">
        <div className="min-w-fit flex justify-center text-[1.05em]">
          {latex ? (
            <SafeBlockMath latex={latex} fallback={expression} />
          ) : (
            <pre className="text-sm text-slate-800 whitespace-pre-wrap font-mono leading-relaxed">
              {expression}
            </pre>
          )}
        </div>
      </div>

      {(formula.explanation || variables.length > 0 || latex) && (
        <div className="px-4 py-3 bg-white space-y-2.5">
          {formula.explanation && (
            <p className="text-xs text-slate-700 leading-relaxed">
              <span className="font-semibold text-indigo-700">Giải thích: </span>
              {formula.explanation}
            </p>
          )}

          {variables.length > 0 && (
            <div>
              <p className="text-[10px] font-semibold text-indigo-700 uppercase tracking-wider mb-1.5">
                Biến số
              </p>
              <ul className="grid grid-cols-1 md:grid-cols-2 gap-1.5">
                {variables.map((v, i) => (
                  <li
                    key={i}
                    className="flex items-baseline gap-2 text-xs text-slate-700 px-2 py-1 bg-indigo-50/40 rounded ring-1 ring-indigo-100"
                  >
                    <span className="font-mono text-indigo-800 shrink-0 text-[12px]">
                      <SafeInlineMath latex={v.symbol} fallback={v.symbol} />
                    </span>
                    {v.meaning && (
                      <span className="leading-snug text-slate-600">
                        {v.meaning}
                      </span>
                    )}
                  </li>
                ))}
              </ul>
            </div>
          )}

          {latex && expression !== latex && (
            <details className="border-t border-indigo-50 pt-2">
              <summary className="text-[10px] font-semibold text-indigo-700 uppercase tracking-wider cursor-pointer hover:text-indigo-900">
                Biểu thức gốc
              </summary>
              <pre className="text-xs text-slate-700 whitespace-pre-wrap font-mono leading-relaxed mt-2">
                {expression}
              </pre>
            </details>
          )}
        </div>
      )}
    </div>
  );
};

// ── KaTeX wrappers with an error boundary so render errors don't propagate ──

class KatexErrorBoundary extends Component {
  constructor(props) {
    super(props);
    this.state = { failed: false };
  }
  static getDerivedStateFromError() {
    return { failed: true };
  }
  componentDidCatch() {
    /* swallow */
  }
  render() {
    if (this.state.failed) return this.props.fallback;
    return this.props.children;
  }
}

const SafeBlockMath = ({ latex, fallback }) => (
  <KatexErrorBoundary
    fallback={
      <pre className="text-sm text-slate-800 whitespace-pre-wrap font-mono leading-relaxed">
        {fallback || latex}
      </pre>
    }
  >
    <BlockMath math={latex} />
  </KatexErrorBoundary>
);

const SafeInlineMath = ({ latex, fallback }) => (
  <KatexErrorBoundary fallback={<span>{fallback || latex}</span>}>
    <InlineMath math={latex} />
  </KatexErrorBoundary>
);

export default SectionInsightCard;
