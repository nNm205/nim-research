<div align="center">

# NIM Research

### AI-powered research assistant for academic document analysis

A full-stack platform that ingests research papers, extracts structured insights section-by-section, runs cross-source literature search, generates polished reports, and chains everything into a single one-click pipeline — so you can go from "what's known about X?" to a fully analysed corpus with publishable summaries in minutes.

[![Python](https://img.shields.io/badge/Python-3.11+-3776ab?style=flat-square&logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.135+-009688?style=flat-square&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![React](https://img.shields.io/badge/React-19-61DAFB?style=flat-square&logo=react&logoColor=black)](https://react.dev/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-15+-336791?style=flat-square&logo=postgresql&logoColor=white)](https://www.postgresql.org/)
[![pgvector](https://img.shields.io/badge/pgvector-enabled-336791?style=flat-square)](https://github.com/pgvector/pgvector)
[![LangGraph](https://img.shields.io/badge/LangGraph-pipeline-1c3d5a?style=flat-square)](https://langchain-ai.github.io/langgraph/)
[![Tailwind](https://img.shields.io/badge/Tailwind-4-38B2AC?style=flat-square&logo=tailwind-css&logoColor=white)](https://tailwindcss.com/)

</div>

---

## What it does

Researchers spend hours on the boring parts of literature work — searching across databases, downloading PDFs, scrolling through them, taking notes section by section, then connecting the dots and writing it all up. NIM Research automates each of those steps and puts them on one pipeline.

**Four core workflows**:

- **Upload & analyse** — drop a PDF or paste an arXiv URL. The platform parses it (handling 2-column layouts, math symbols, tables), chunks it section-aware, embeds each chunk, then runs a section-by-section LLM analysis that extracts claims, methods, data, tables, formulas, critique, and quotes. Results render as scannable cards with KaTeX math, sortable tables, and an executive summary.
- **Multi-source search** — query arXiv, Google Scholar, and Semantic Scholar in parallel; results are deduplicated and re-ranked by semantic relevance. Click "Add to project" on any result and the system auto-locates a downloadable PDF (Unpaywall via DOI, arXiv-derived, or scraped from the landing page) and runs the full ingest pipeline.
- **Auto-research** — type a topic, pick how many papers to ingest and which LLM to use, walk away. The orchestrator chains *search → ingest top-N → analyse each* into a single background task with a live progress panel showing every stage.
- **Generate reports** — pick one of four templates (research summary / literature review / data analysis / custom) and the system deterministically composes Markdown + styled HTML from the project's documents and analyses. Download as `.html`, `.docx`, or `.md` with one click. No extra LLM cost — the analysis stage already paid for the insight extraction.

---

## Screenshots

<table>
  <tr>
    <td width="50%"><img src="docs/images/nim_research_dashboard.png" alt="Dashboard" /></td>
    <td width="50%"><img src="docs/images/nim_research_projects.png" alt="Projects" /></td>
  </tr>
  <tr>
    <td align="center"><sub>Dashboard overview</sub></td>
    <td align="center"><sub>Projects list with topic chips and stats</sub></td>
  </tr>
  <tr>
    <td><img src="docs/images/nim_research_project-detail.png" alt="Project detail" /></td>
    <td><img src="docs/images/nim_research_documents.png" alt="Documents" /></td>
  </tr>
  <tr>
    <td align="center"><sub>Project workspace with auto-research and live progress</sub></td>
    <td align="center"><sub>Cross-project documents aggregator</sub></td>
  </tr>
  <tr>
    <td><img src="docs/images/nim_research_analysis.png" alt="Analysis results" /></td>
    <td><img src="docs/images/nim_research_reports.png" alt="Reports" /></td>
  </tr>
  <tr>
    <td align="center"><sub>Section-by-section analysis with KaTeX, tables, and tabs</sub></td>
    <td align="center"><sub>Generated reports with HTML/DOCX/Markdown export</sub></td>
  </tr>
  <tr>
    <td><img src="docs/images/nim_research_knowledge-base.png" alt="Knowledge Base" /></td>
    <td><img src="docs/images/nim_research_login.png" alt="Login" /></td>
  </tr>
  <tr>
    <td align="center"><sub>Knowledge base with trigram search</sub></td>
    <td align="center"><sub>Authentication</sub></td>
  </tr>
</table>

---

## Features

### Document ingestion

- Upload PDF or HTML (drag-drop, 50 MB cap) **or** paste a URL — system fetches and parses it
- 2-column-aware PDF extraction (PyMuPDF block mode + reading-order column clustering)
- Heading detection by font size + numbered/named regex with sequence validation, so list items like "1. First metric" inside subsection 6.1 are not misinterpreted as new sections
- Tables extracted with pdfplumber and embedded as markdown blocks
- Equations detected by math-symbol density + LaTeX cues, rendered with KaTeX in the UI
- Section-aware chunker tags every chunk with `section_title`, `section_number`, `subsections` so downstream agents can map chunks to sections deterministically

### Section-grounded analysis

- LangGraph pipeline: `load_chunks → map_sections → build_outline → analyse_sections → synthesize → persist`
- One LLM call per section produces a structured insight object: summary, purpose, key points, claims (with evidence type + confidence), methods, data/experiments, tables, formulas, notable terms, critique, open questions, quotes
- One final synthesis call produces narrative + executive summary in a single round-trip
- Smart truncation (head + tail) for long sections instead of map-reduce — saves LLM quota
- Heuristic fallback when LLM fails so a card never renders empty
- Total: **~N+1 LLM calls** for an N-section paper

### Multi-source search + auto-pipeline

- Parallel search across **arXiv**, **Google Scholar**, **Semantic Scholar** (1 RPS rate-limited with API key)
- Re-ranked by semantic relevance to query
- **PDF finder service**: Unpaywall (via DOI) → arXiv-derived → page scrape (citation_pdf_url meta + fallback `<a href>`)
- **Auto-research**: search → ingest top-N → analyse each → finalise, all in one background task with a live 4-stage progress panel
- Standalone analyses also get a live progress panel
- Background tasks held by strong refs so the GC can't silently cancel a running pipeline mid-flight; a `lifespan` startup hook flips any leftover `running` rows from a previous crash to `failed` so the live progress panel never gets stuck

### Report generator

- 4 templates: **research summary**, **literature review**, **data analysis**, **custom**
- Deterministic composition over the structured fields the analysis pipeline already extracted (key findings, methodology, limitations, future work, narrative synthesis, …) — **zero LLM calls** at report time, so regeneration is free and reproducible
- Renders Markdown + styled HTML side-by-side; HTML is fully self-contained (inline CSS, inline SVG icons) so the file stays presentable when downloaded or emailed
- Native `.docx` export via python-docx (proper Word headings, tables, bullet lists — no Pandoc / LibreOffice required)
- Per-document tag chips and a clickable source-link chip with host + external-link icon, matching the project's chip style throughout the app
- Reports are scoped to a project (created from `ProjectDetailPage`) and aggregated cross-project on `/reports` for browsing

### Notifications

- Persistent `notifications` table per user — survives backend restarts and tab switches
- Agents push a row whenever a long-running task finalises: analysis completed/failed, research search done, auto-research pipeline done, report created
- Bell dropdown in the header polls every 15 s with badge count, optimistic mark-as-read, deep-links into the source entity, and per-row delete
- Categorised by workflow (analysis · research · auto_research · report · document) so the UI can colour-code rows

### LLM + embedding flexibility

- 5 LLM providers: **Gemini**, **Groq**, **OpenAI**, **Claude**, **OpenRouter** — pick one per analysis
- 3 embedding providers: **HuggingFace**, **Jina**, **Google AI**
- Free-tier-aware retry: parses `retryDelay` from Gemini 429 responses, exponential backoff for others, sequential analyses inside the auto-research orchestrator

### UX

- Tag-chip topic editor with keyboard shortcuts (Enter / comma / Backspace)
- Cross-project Documents / Analyses / Reports pages — same filter-chips + search + grid pattern across all three
- Live progress panels with per-stage steppers, per-item counters, embedded sub-progress
- Tables auto-detect numeric columns and right-align with tabular numbers
- KaTeX-rendered math with error boundary fallback to raw LaTeX
- Modals share one consistent shape: `bg-black/20` backdrop, sticky header with icon block, `no-scrollbar` scrollable body, inline submit/cancel actions

### Performance

- Async DB session compatible with **Supabase Supavisor pooler** (per-call UUID-named prepared statements, statement cache disabled)
- pgvector for semantic chunk search
- pg_trgm GIN indexes for fast title/content fuzzy search in the knowledge base
- List endpoints defer heavy `content` / JSONB columns; counts via `GROUP BY` instead of `len(selectin)`
- Project counts (documents / analyses / reports / research sessions) computed in **one** SQL statement with four `LEFT JOIN`-ed subqueries — replaces the previous four sequential `GROUP BY` round-trips
- Dashboard fires **two parallel requests** (projects + notifications) and derives every stat client-side — replaces the old N+1 pattern that issued up to 10 sequential calls
- Window function `count(*) OVER ()` instead of separate count + fetch queries

---

## Tech stack

### Backend
- **FastAPI** with async/await throughout, lifespan hook for stale-task recovery
- **SQLAlchemy 2.0** + **asyncpg** for the async path, **psycopg2** for sync admin paths
- **PostgreSQL 15** with **pgvector** and **pg_trgm** extensions
- **Alembic** migrations
- **LangChain** + **LangGraph** for agent orchestration
- **PyMuPDF** + **pdfplumber** for PDF parsing
- **python-docx** for native Word export
- **httpx** for outbound HTTP (Unpaywall, S2 API)

### Frontend
- **React 19** + **Vite** + **Tailwind 4**
- **React Router v7**
- **react-katex** for math rendering
- **Lucide** icons
- Polling-based progress + notification updates (3 s for in-flight tasks, 15 s for the notification bell)

### LLM / Embedding providers (pluggable)
- LLM: Google Gemini, Groq, OpenAI, Anthropic Claude, OpenRouter
- Embedding: HuggingFace Inference, Jina AI, Google AI
- Vector store: **pgvector** (built into PostgreSQL — no separate service needed)

### Infrastructure
- Docker Compose for local development
- Environment-based configuration via `.env`

---

## Architecture

```
┌────────────────┐                                ┌────────────────┐
│  React + Vite  │   HTTP polling (3 s tasks /    │    FastAPI     │
│  + Tailwind    │ ◄───────15 s notifications)────►   (async)      │
└────────────────┘                                └───────┬────────┘
                                                          │
            ┌─────────────────────────────────────────────┼─────────────────────────────┐
            │                                             │                             │
            ▼                                             ▼                             ▼
┌──────────────────────────┐         ┌────────────────────────────┐    ┌────────────────────────────┐
│      AnalysisAgent       │         │     AutoResearchService    │    │   Deterministic Report     │
│   (LangGraph pipeline)   │         │       (orchestrator)       │    │       generator (no LLM)   │
│                          │         │                            │    │                            │
│  load_chunks → map_      │         │  search → ingest top-N     │    │  aggregate Documents +     │
│  sections → build_       │         │   → analyse each → done    │    │  Analyses → render MD +    │
│  outline → analyse →     │         │   (strong-ref tasks,       │    │  styled HTML + DOCX        │
│  synthesize → persist    │         │    crash-safe)             │    │                            │
└────────────┬─────────────┘         └─────────────┬──────────────┘    └─────────────┬──────────────┘
             │                                     │                                 │
             │ uses                          uses  │                          reads  │
             ▼                                     ▼                                 ▼
┌──────────────────────────────────────────────────────────────────────────────────────────────────┐
│  Service layer: documents · analyses · projects · research · KB · reports · notifications       │
└────────────────────────────────────┬─────────────────────────────────────────────────────────────┘
                                     │
              ┌──────────────────────┴──────────────────────┐
              ▼                                             ▼
┌─────────────────────────────────┐         ┌──────────────────────────────────┐
│  PostgreSQL + pgvector          │         │  External APIs                   │
│                                 │         │  · arXiv · Google Scholar (SerpAPI)│
│  · projects · documents         │         │  · Semantic Scholar · Unpaywall  │
│  · document_chunks (vector)     │         │  · LLM providers · Embedding     │
│  · analyses · reports · kb      │         │    providers                     │
│  · notifications                │         │                                  │
└─────────────────────────────────┘         └──────────────────────────────────┘
```

---

## Quick start

### Prerequisites

- Python 3.11+
- Node.js 18+
- PostgreSQL 15 with `pgvector` and `pg_trgm` extensions enabled (or use [Supabase](https://supabase.com/) which has both pre-installed)
- A free Gemini, Groq, or OpenAI API key (Gemini's free tier is enough to try the platform)

### Backend

```bash
cd backend

python -m venv venv
# Windows
venv\Scripts\activate
# macOS / Linux
# source venv/bin/activate

pip install -r requirements.txt

# Configure
copy .env.example .env       # Windows
# cp .env.example .env       # macOS / Linux
# then edit .env (see "Environment" below)

# Migrate
alembic upgrade head

# Run
uvicorn app.main:app --reload --port 8000
```

API at `http://localhost:8000`. Swagger UI at `http://localhost:8000/docs`.

### Frontend

```bash
cd frontend
npm install
copy .env.example .env       # Windows
# cp .env.example .env       # macOS / Linux
npm run dev
```

App at `http://localhost:5173`.

---

## Environment

Backend `.env` (only the values the platform actually reads):

```env
APP_NAME=NIM Research
DEBUG=False

# Database (Supabase / local Postgres with pgvector + pg_trgm)
DATABASE_URL=postgresql://user:pass@host:5432/dbname

# Auth
JWT_SECRET_KEY=replace_with_a_long_random_string
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=10080

# LLM providers — at least one required
PROVIDER=gemini
MODEL_NAME=gemini-2.5-flash
GROQ_API_KEY=...
GROQ_BASE_URL=https://api.groq.com/openai/v1
OPENAI_API_KEY=...
OPENAI_BASE_URL=https://api.openai.com/v1
CLAUDE_API_KEY=...
CLAUDE_BASE_URL=https://api.anthropic.com/v1
OPENROUTER_API_KEY=...
OPENROUTER_BASE_URL=https://openrouter.ai/api/v1

# Embedding providers — at least one required
EMBEDDING_PROVIDER=huggingface
EMBEDDING_MODEL=ibm-granite/granite-embedding-97m-multilingual-r2
HUGGINGFACE_API_KEY=...
GOOGLEAI_API_KEY=...
JINA_API_KEY=...

# Search APIs (optional but unlocks Google Scholar + web search)
SERP_API_KEY=...
SEMANTIC_API_KEY=...

REDIS_URL=redis://localhost:6379   # placeholder; not currently used
```

Frontend `.env`:

```env
VITE_API_URL=http://localhost:8000
```

---

## API surface

Interactive docs at `http://localhost:8000/docs`. Highlights:

| Endpoint                                                       | What it does                                              |
| -------------------------------------------------------------- | --------------------------------------------------------- |
| `POST /api/v1/projects/{id}/documents/upload-file`             | Upload a PDF/HTML file directly                           |
| `POST /api/v1/projects/{id}/documents/ingest-url`              | Ingest a public URL                                       |
| `POST /api/v1/projects/{id}/documents/ingest-search-result`    | Ingest a research-search result (auto PDF lookup)         |
| `POST /api/v1/projects/{id}/research`                          | Start a multi-source search session                       |
| `POST /api/v1/projects/{id}/auto-research`                     | Search → ingest top-N → analyse, all chained              |
| `POST /api/v1/projects/{id}/analyze`                           | Analyse a single document with chosen LLM                 |
| `GET  /api/v1/analysis/{id}/results`                           | Full structured insight (sections, synthesis, summary)    |
| `POST /api/v1/projects/{id}/reports`                           | Create a report — auto-composes from documents + analyses |
| `POST /api/v1/reports/{id}/regenerate`                         | Re-run the deterministic generator over current data      |
| `GET  /api/v1/reports/{id}/download/{md\|html\|docx}`           | Download as Markdown, styled HTML, or native Word         |
| `GET  /api/v1/notifications`                                   | Latest notifications + unread count for the bell badge    |
| `POST /api/v1/notifications/mark-read`                         | Mark some / all notifications as read                     |
| `GET  /api/v1/llm/providers`                                   | Available LLM providers + models                          |
| `GET  /api/v1/embeddings/providers`                            | Available embedding providers + models                    |
| `GET  /api/v1/documents`                                       | All documents owned by the user across every project      |
| `GET  /api/v1/analyses`                                        | All analyses owned by the user across every project       |

---

## Project structure

```
nim-eng/
├── backend/
│   ├── app/
│   │   ├── agents/
│   │   │   ├── analysis_agent.py            # LangGraph pipeline
│   │   │   ├── research_agent.py            # multi-source search
│   │   │   └── tools/
│   │   │       ├── analysis/                # 7 tools used by AnalysisAgent
│   │   │       └── research/                # progress tracker
│   │   ├── routes/                          # FastAPI handlers
│   │   ├── services/
│   │   │   ├── auto_research_service.py     # search → ingest → analyse chain
│   │   │   ├── document_ingestion_service.py
│   │   │   ├── pdf_finder_service.py        # Unpaywall + arXiv + scrape
│   │   │   ├── notification_service.py      # persistent bell-icon alerts
│   │   │   ├── report_generator/            # deterministic MD/HTML/DOCX
│   │   │   ├── stale_recovery.py            # mark zombie running rows failed
│   │   │   └── ...
│   │   ├── models/
│   │   │   ├── llm_providers/               # 5 LLM provider implementations
│   │   │   ├── embedding_providers/         # 3 embedding implementations
│   │   │   ├── notification.py
│   │   │   └── ...
│   │   ├── tools/document/
│   │   │   ├── parsers/                     # PDF + HTML
│   │   │   ├── chunkers/                    # section-aware chunker
│   │   │   ├── fetchers/                    # PDF + HTML fetchers
│   │   │   └── vectorstores/                # pgvector
│   │   ├── tools/search/                    # arxiv, scholar, semantic, web
│   │   ├── prompts/                         # LLM prompt templates
│   │   ├── schemas/                         # Pydantic validation
│   │   ├── database/                        # async + sync sessions
│   │   └── main.py
│   ├── alembic/versions/                    # migrations
│   ├── scripts/                             # one-off maintenance scripts
│   └── requirements.txt
├── frontend/
│   └── src/
│       ├── pages/                           # AnalysisResults, ProjectDetail, Reports, …
│       ├── components/
│       │   ├── analysis/                    # SectionInsightCard, progress panels
│       │   ├── projects/                    # AutoResearchModal, TopicChipInput
│       │   ├── research/                    # IngestSearchResultModal, progress
│       │   ├── reports/                     # ReportCard, CreateReportModal
│       │   ├── documents/                   # CreateDocumentModal (URL + upload)
│       │   └── layout/                      # DashboardLayout, NotificationCenter
│       ├── services/                        # API clients
│       └── hooks/                           # useAnalysisPolling
└── docs/images/                             # screenshots
```

---

## 👨‍💻 Author

**Nguyễn Nhật Minh**

* GitHub: https://github.com/nNm205
* Email: [minh2m5@gmail.com](mailto:minh2m5@gmail.com)

---

<div align="center"> 

**If you find this project useful, please consider giving it a star ⭐ .** 

*Built with ☕ and a lot of git commit --amend* 

</div>
