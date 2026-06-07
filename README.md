<div align="center">

# NIM Research

### AI-powered research assistant for academic document analysis

A full-stack platform that ingests research papers, extracts structured insights section-by-section, runs cross-source literature search, generates polished reports, and chains everything into a single one-click pipeline — so you can go from "what's known about X?" to a fully analysed corpus, an LLM-synthesised report, and a 0–100 quality score in minutes.

[![Python](https://img.shields.io/badge/Python-3.11+-3776ab?style=flat-square&logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.135+-009688?style=flat-square&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![React](https://img.shields.io/badge/React-19-61DAFB?style=flat-square&logo=react&logoColor=black)](https://react.dev/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-15+-336791?style=flat-square&logo=postgresql&logoColor=white)](https://www.postgresql.org/)
[![pgvector](https://img.shields.io/badge/pgvector-enabled-336791?style=flat-square)](https://github.com/pgvector/pgvector)
[![LangGraph](https://img.shields.io/badge/LangGraph-pipeline-1c3d5a?style=flat-square)](https://langchain-ai.github.io/langgraph/)
[![Tailwind](https://img.shields.io/badge/Tailwind-4-38B2AC?style=flat-square&logo=tailwind-css&logoColor=white)](https://tailwindcss.com/)

</div>

---

## 🎯 What it does

Researchers spend hours on the boring parts of literature work — searching across databases, downloading PDFs, scrolling through them, taking notes section by section, then connecting the dots and writing it all up. NIM Research automates each of those steps and puts them on one pipeline.

**Six core workflows**:

- **Upload & analyse** — drop a PDF or paste an arXiv URL. The platform parses it with **docling** (layout analysis, reading-order reconstruction, heading detection, table extraction), recovers Unicode math via PyMuPDF bbox extraction, chunks it section-aware, embeds each chunk, then runs a section-by-section LLM analysis that extracts claims, methods, data, tables, formulas, critique, and quotes. Results render as scannable cards with KaTeX math, sortable tables, and an executive summary.
- **Multi-source search** — query arXiv, Google Scholar, and Semantic Scholar in parallel; results are deduplicated, classified by publisher, filtered to a **trusted academic whitelist** (arXiv · IEEE · ACM · ResearchGate), then re-ranked by semantic relevance. Click "Add to project" on any result and the system auto-locates a downloadable PDF (Unpaywall via DOI, arXiv-derived, or scraped from the landing page) and runs the full ingest pipeline.
- **Auto-research** — type a topic, pick how many papers to ingest and which LLM to use, walk away. The orchestrator chains *search → ingest top-N → analyse each* into a single background task with a live progress panel showing every stage, and can optionally tail the run with *report → synthesis → QA*.
- **Generate reports** — pick one of four templates (research summary / literature review / data analysis / custom) and the system deterministically composes Markdown + styled HTML from the project's documents and analyses. Download as `.html`, `.docx`, or `.md` with one click. No LLM cost — the analysis stage already paid for the insight extraction.
- **Synthesis (LLM)** — opt-in pass that takes a deterministic report and rewrites it as a coherent cross-document narrative: the agent designs an outline, writes per-section prose with inline `[n]` citations, generates an executive summary, and emits APA + BibTeX bibliographies. The original template body is preserved for one-click rollback.
- **Quality Assurance** — opt-in pass that scores a report 0–100 across **format · citations · facts · grammar**. Format and citation checks are deterministic; fact-check and grammar use one LLM call each. The result is a verdict (excellent · good · needs review · poor), a per-axis score, and a concrete issue list — surfaced in the report sidebar.

---

## 🖼️ Screenshots

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

## ✨ Features

### 📥 Document ingestion

- Upload PDF or HTML (drag-drop, 50 MB cap) **or** paste a URL — system fetches and parses it
- **docling-based PDF parser**: layout analysis + reading-order reconstruction + heading detection + table structure extraction in a single pass
- PyMuPDF fallback decodes the formulas docling marks `<!-- formula-not-decoded -->`: raw text is read under each formula bbox so Unicode math like `softmax(QKᵀ/√dₖ)V` is preserved and wrapped in `[Equation]` ` ```formula ` blocks
- Legacy PyMuPDF + pdfplumber pipeline kept as automatic fallback (`pdf_parser_legacy.py`) when docling fails on a particular document
- Section-aware chunker recognises **numbered** (`1.`, `1.2`, `1.2.3`), **Roman** (`I.`, `II.`, `III.`), **letter sub-headings** (`A.`, `B.` bound to the most recent Roman parent — IEEE / ACM style), and **named** headings (Introduction, Tóm tắt, Tài liệu tham khảo, …) with sequence validation, so list items inside a subsection aren't misinterpreted as new sections
- Vietnamese-friendly capitalisation variant of named-heading patterns matches "Tóm tắt" / "Tài liệu tham khảo" without forcing every word capitalised
- Equations rendered with KaTeX in the UI; tables rendered as sortable, numeric-aware HTML

### 🧠 Section-grounded analysis

- LangGraph pipeline: `load_chunks → map_sections → build_outline → analyse_sections → synthesize → persist`
- One LLM call per section produces a structured insight object: summary, purpose, key points, claims (with evidence type + confidence), methods, data/experiments, tables, formulas, notable terms, critique, open questions, quotes
- One final synthesis call produces narrative + executive summary in a single round-trip
- Smart truncation (head + tail) for long sections instead of map-reduce — saves LLM quota
- Heuristic fallback when LLM fails so a card never renders empty
- Total: **~N+1 LLM calls** for an N-section paper

### 🔎 Multi-source search + auto-pipeline

- Parallel search across **arXiv**, **Google Scholar**, **Semantic Scholar** (1 RPS rate-limited with API key)
- **Trusted-publisher filter**: every hit is classified by DOI prefix and URL host into one of `{arxiv, ieee, acm, researchgate, other}`; non-trusted hits are dropped up-front so the user never sees results they couldn't ingest. The classifier is mirrored on the FE so the ingest button is gated client-side too.
- **PDF finder service**: Unpaywall (via DOI) → arXiv-derived → page scrape (citation_pdf_url meta + fallback `<a href>`). Per RG ToS, ResearchGate-hosted PDFs are **never fetched** — the finder routes through Unpaywall instead and skips the paper if no Open Access copy exists
- Re-ranked by semantic relevance to query
- **Auto-research**: search → ingest top-N → analyse each → optional `report → synthesise → qa` → finalise, all in one background task with a live progress panel that builds its stage list dynamically based on the toggles you set
- Standalone analyses, syntheses, and QA runs each get their own live progress panel
- Background tasks held by strong refs so the GC can't silently cancel a running pipeline mid-flight; a `lifespan` startup hook flips any leftover `running` rows (analyses, research sessions, syntheses, QA runs) from a previous crash to `failed` so the live progress panels never get stuck

### 📝 Report generator

- 4 templates: **research summary**, **literature review**, **data analysis**, **custom**
- Deterministic composition over the structured fields the analysis pipeline already extracted (key findings, methodology, limitations, future work, narrative synthesis, …) — **zero LLM calls** at report time, so regeneration is free and reproducible
- Renders Markdown + styled HTML side-by-side; HTML is fully self-contained (inline CSS, inline SVG icons) so the file stays presentable when downloaded or emailed
- Native `.docx` export via python-docx (proper Word headings, tables, bullet lists — no Pandoc / LibreOffice required)
- Smart `update_report` policy: structural changes (title / type / included docs) regenerate from data; user-supplied markdown re-renders the cached HTML through markdown-it-py so the preview reflects the edit; metadata-only patches leave the body alone
- Project topic shown as comma-split chips on the cover, matching the project list visual language
- Reports are scoped to a project (created from `ProjectDetailPage`) and aggregated cross-project on `/reports` for browsing

### ✍️ Synthesis (LLM-driven cross-document writer)

- LangGraph pipeline: `load_context → build_outline → synthesize_narrative → generate_summary → build_citations → render_report → persist`
- **3 LLM calls** per report: outline (1), narrative with inline `[n]` citations (1), executive summary + key takeaways (1)
- Deterministic citation manager produces both APA bibliography and BibTeX
- Overwrites `Report.content` / `Report.html_content` with the synthesised version while preserving the previous deterministic body in `synthesis_metadata.original_template_*` — one-click rollback restores it
- Live per-step progress panel polls `/synthesis/status` every 3 s; notifications fire on completion under a dedicated `synthesis` category

### ✅ Quality assurance

- Pipeline: `format → citations → facts → grammar → score → persist`
- **Deterministic**: format validator (heading hierarchy, table structure, length budget) and citation verifier (every `[n]` resolves to an entry in `synthesis_metadata.citation_entries` or the project's documents)
- **LLM-backed (2 calls)**: fact-checker samples claims and verifies each as `supported / partial / unsupported` against the analysis evidence; grammar+clarity pass surfaces concrete bilingual (Vietnamese / English) issues
- Quality scorer combines the four axes into an overall **0–100** score and a verdict (`excellent` ≥ 90, `good` 75–89, `needs_review` 60–74, `poor` < 60), persisted on `Report.qa_report`
- Sidebar panel shows score + per-axis breakdown; a modal renders the full issue list with snippets and severity tags

### 🔔 Notifications

- Persistent `notifications` table per user — survives backend restarts and tab switches
- Agents push a row whenever a long-running task finalises: analysis, research search, auto-research pipeline, report created, **synthesis completed**, **QA completed**
- Bell dropdown in the header polls every 15 s with badge count, optimistic mark-as-read, deep-links into the source entity, and per-row delete
- Categorised by workflow (analysis · research · auto_research · report · synthesis · qa · document) so the UI can colour-code rows

### 🔌 LLM + embedding flexibility

- 5 LLM providers: **Gemini**, **Groq**, **OpenAI**, **Claude**, **OpenRouter** — pick one per analysis / synthesis / QA run
- 3 embedding providers: **HuggingFace**, **Jina**, **Google AI**
- Free-tier-aware retry: parses `retryDelay` from Gemini 429 responses, exponential backoff for others, sequential analyses inside the auto-research orchestrator

### 🎨 UX

- Tag-chip topic editor with keyboard shortcuts (Enter / comma / Backspace)
- Cross-project Documents / Analyses / Reports pages — same filter-chips + search + grid pattern across all three
- Live progress panels with per-stage steppers, per-item counters, embedded sub-progress; auto-research stepper renders the exact sequence about to run
- Tables auto-detect numeric columns and right-align with tabular numbers
- KaTeX-rendered math with error boundary fallback to raw LaTeX
- Modals share one consistent shape: `bg-black/20` backdrop, sticky header, `no-scrollbar` scrollable body, inline submit/cancel actions

### ⚡ Performance

- Async DB session **auto-detects pooler vs direct Postgres**: with Supabase Supavisor or PgBouncer the engine disables prepared-statement caching and uses UUID-named statements (transaction-mode pooler swaps backends between calls); with a direct Postgres connection (local docker-compose, bare-metal) it enables `pool_pre_ping` + the standard asyncpg cache for proper connection-loss recovery
- pgvector for semantic chunk search
- pg_trgm GIN indexes for fast title/content fuzzy search in the knowledge base
- List endpoints defer heavy `content` / JSONB columns; counts via `GROUP BY` instead of `len(selectin)`
- Project counts (documents / analyses / reports / research sessions) computed in **one** SQL statement with four `LEFT JOIN`-ed subqueries — replaces the previous four sequential `GROUP BY` round-trips
- Dashboard fires **two parallel requests** (projects + notifications) and derives every stat client-side — replaces the old N+1 pattern that issued up to 10 sequential calls
- Window function `count(*) OVER ()` instead of separate count + fetch queries

---

## 🛠️ Tech stack

### ⚙️ Backend
- **FastAPI** with async/await throughout, lifespan hook for stale-task recovery
- **SQLAlchemy 2.0** + **asyncpg** for the async path, **psycopg2** for sync admin paths
- **PostgreSQL 15** with **pgvector** and **pg_trgm** extensions
- **Alembic** migrations
- **LangChain** + **LangGraph** for agent orchestration (analysis, synthesis, QA)
- **docling** for primary PDF parsing, **PyMuPDF** + **pdfplumber** for legacy fallback and formula bbox decoding
- **markdown-it-py** for user-edited markdown → HTML re-rendering
- **python-docx** for native Word export
- **httpx** for outbound HTTP (Unpaywall, S2 API)

### 💻 Frontend
- **React 19** + **Vite** + **Tailwind 4**
- **React Router v7**
- **react-katex** for math rendering
- **Lucide** icons
- Polling-based progress + notification updates (3 s for in-flight tasks, 15 s for the notification bell)

### 🤖 LLM / Embedding providers (pluggable)
- LLM: Google Gemini, Groq, OpenAI, Anthropic Claude, OpenRouter
- Embedding: HuggingFace Inference, Jina AI, Google AI
- Vector store: **pgvector** (built into PostgreSQL — no separate service needed)

### 🐳 Infrastructure
- **Docker Compose** stack: `postgres` (pgvector/pg16) · `backend` (FastAPI + alembic auto-migrate) · `frontend` (nginx + built SPA)
- Reverse-proxied: nginx serves the SPA and proxies `/api`, `/docs`, `/openapi.json` to the backend, so the FE bundle uses relative URLs and the same image runs in dev / staging / prod
- Persistent named volumes for Postgres data, uploaded PDFs, app logs, and the docling model cache
- Healthchecks on every service; backend depends on Postgres `service_healthy` so migrations always run against a ready DB
- CPU-only PyTorch installed from `download.pytorch.org/whl/cpu` to keep the backend image around 2 GB instead of 6 GB
- Environment-based configuration via `.env` files (root `.env` for Postgres creds, `backend/.env` for app secrets)

---

## 🏗️ Architecture

```
┌────────────────┐                                ┌────────────────┐
│  React + Vite  │   HTTP polling (3 s tasks /    │    FastAPI     │
│  + Tailwind    │ ◄───────15 s notifications)────►   (async)      │
└────────────────┘                                └───────┬────────┘
                                                          │
       ┌──────────────────┬──────────────────┬────────────┼────────────┬──────────────────┐
       │                  │                  │            │            │                  │
       ▼                  ▼                  ▼            ▼            ▼                  ▼
┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────┐  ┌──────────┐  ┌──────────────┐
│ Analysis     │  │ AutoResearch │  │ Report       │  │ Synth.   │  │ QA       │  │ Notification │
│ Agent        │  │ Service      │  │ generator    │  │ Agent    │  │ Agent    │  │ Service      │
│ (LangGraph)  │  │ (chains all) │  │ (no LLM)     │  │ (3 LLM)  │  │ (2 LLM)  │  │ (persistent) │
│              │  │              │  │              │  │          │  │          │  │              │
│ load_chunks  │  │ search       │  │ aggregate    │  │ outline  │  │ format   │  │ bell badge   │
│ → map_sec    │  │ → ingest     │  │ Documents +  │  │ →        │  │ →        │  │ → mark read  │
│ → build_     │  │ → analyse    │  │ Analyses     │  │ narrative│  │ citations│  │ → deep-link  │
│ outline →    │  │ → [report]   │  │ → MD + HTML  │  │ →        │  │ →        │  │              │
│ analyse →    │  │ → [synth]    │  │ + DOCX       │  │ summary  │  │ facts    │  │              │
│ synthesize   │  │ → [qa]       │  │              │  │ →        │  │ →        │  │              │
│ → persist    │  │ → done       │  │              │  │ citations│  │ grammar  │  │              │
│              │  │              │  │              │  │ → render │  │ → score  │  │              │
└──────┬───────┘  └──────┬───────┘  └──────┬───────┘  └────┬─────┘  └────┬─────┘  └──────┬───────┘
       │                 │                 │               │             │               │
       └─────────────────┴─────────────────┴───────────────┴─────────────┴───────────────┘
                                                  │
                                                  ▼
┌──────────────────────────────────────────────────────────────────────────────────────────────────┐
│  Service layer: documents · analyses · projects · research · KB · reports · synthesis · qa     │
│                 · notifications · search (publisher whitelist) · pdf-finder (RG-safe)          │
└────────────────────────────────────┬─────────────────────────────────────────────────────────────┘
                                     │
              ┌──────────────────────┴──────────────────────┐
              ▼                                             ▼
┌─────────────────────────────────┐         ┌──────────────────────────────────┐
│  PostgreSQL + pgvector          │         │  External APIs                   │
│                                 │         │  · arXiv · Google Scholar (SerpAPI)│
│  · projects · documents         │         │  · Semantic Scholar · Unpaywall  │
│  · document_chunks (vector)     │         │  · LLM providers · Embedding     │
│  · analyses · reports           │         │    providers                     │
│    (synthesis_*  + qa_* fields) │         │                                  │
│  · kb · notifications           │         │                                  │
└─────────────────────────────────┘         └──────────────────────────────────┘
```

---

## 🚀 Quick start

### 🐳 Option 1: Docker (recommended)

The fastest way to run the full stack. One command brings up Postgres + backend + frontend with networking, healthchecks, and persistent volumes wired up.

**Prerequisites**: [Docker Desktop](https://www.docker.com/products/docker-desktop/) running. That's it — no Python, no Node.js, no Postgres install needed on the host.

```cmd
REM 1. Configure
copy .env.example .env                  REM Postgres creds for the container
copy backend\.env.example backend\.env  REM LLM / embedding API keys

REM 2. Edit backend\.env and fill in at least one LLM key
REM    (Gemini's free tier or Groq is enough to try the platform)

REM 3. Build + run
docker compose up -d --build
```

**First build takes ~10–15 minutes** because the backend image installs PyTorch (CPU-only), docling, sentence-transformers, and the rest of the ML stack. Subsequent runs reuse the image — `docker compose up -d` boots in seconds.

| URL                              | What you get                                |
| -------------------------------- | ------------------------------------------- |
| `http://localhost:5173`          | Web app (nginx serves the React SPA)        |
| `http://localhost:5173/docs`     | Swagger via nginx proxy                     |
| `http://localhost:8000/docs`     | Swagger directly on the backend             |
| `http://localhost:8000/health`   | Liveness probe (returns `{"status":"ok"}`)  |
| `localhost:5432`                 | Postgres for psql / DBeaver inspection      |

The first PDF you upload triggers docling to download its layout + table-detection models (~500 MB into the `model_cache` volume). Subsequent uploads are instant. Use `docker compose logs -f backend` to watch the model fetch progress.

**Common operations**:

```cmd
docker compose ps              REM container status
docker compose logs -f backend REM tail backend logs
docker compose down            REM stop everything (data preserved in volumes)
docker compose down -v         REM stop AND wipe Postgres / model cache
```

The stack ships with a `pgvector/pgvector:pg16` image so `vector`, `pg_trgm`, and `btree_gin` extensions are created automatically on first boot via `infra/postgres/init.sql`.

### 🔧 Option 2: Local development (host install)

Useful when you want hot-reload (`uvicorn --reload` + Vite HMR) or to debug Python line-by-line.

**Prerequisites**

- Python 3.11+
- Node.js 18+
- PostgreSQL 15 with `pgvector` and `pg_trgm` extensions enabled (or use [Supabase](https://supabase.com/) which has both pre-installed)
- A free Gemini, Groq, or OpenAI API key

**Backend**

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

**Frontend**

```bash
cd frontend
npm install
copy .env.example .env       # Windows
# cp .env.example .env       # macOS / Linux
npm run dev
```

App at `http://localhost:5173`.

---

## 🔐 Environment

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

## 🌐 API surface

Interactive docs at `http://localhost:8000/docs`. Highlights:

| Endpoint                                                       | What it does                                                      |
| -------------------------------------------------------------- | ----------------------------------------------------------------- |
| `POST /api/v1/projects/{id}/documents/upload-file`             | Upload a PDF/HTML file directly                                   |
| `POST /api/v1/projects/{id}/documents/ingest-url`              | Ingest a public URL                                               |
| `POST /api/v1/projects/{id}/documents/ingest-search-result`    | Ingest a research-search result (publisher-whitelisted, auto PDF) |
| `POST /api/v1/projects/{id}/research`                          | Start a multi-source search session                               |
| `POST /api/v1/projects/{id}/auto-research`                     | Search → ingest → analyse, optionally chained with report/synth/QA |
| `POST /api/v1/projects/{id}/analyze`                           | Analyse a single document with chosen LLM                         |
| `GET  /api/v1/analysis/{id}/results`                           | Full structured insight (sections, synthesis, summary)            |
| `POST /api/v1/projects/{id}/reports`                           | Create a report — auto-composes from documents + analyses         |
| `POST /api/v1/reports/{id}/regenerate`                         | Re-run the deterministic generator over current data              |
| `GET  /api/v1/reports/{id}/download/{md\|html\|docx}`           | Download as Markdown, styled HTML, or native Word                 |
| `POST /api/v1/reports/{id}/synthesize`                         | Dispatch SynthesisAgent (LLM cross-document narrative)            |
| `GET  /api/v1/reports/{id}/synthesis/status`                   | Poll synthesis progress                                           |
| `GET  /api/v1/reports/{id}/synthesis`                          | Full synthesis result (outline, narrative, summary, citations)    |
| `POST /api/v1/reports/{id}/synthesis/rollback`                 | Restore the deterministic template body                           |
| `POST /api/v1/reports/{id}/qa`                                 | Dispatch QualityAssuranceAgent                                    |
| `GET  /api/v1/reports/{id}/qa/status`                          | Poll QA progress                                                  |
| `GET  /api/v1/reports/{id}/qa/report`                          | Full QA report (per-axis scores + issue list)                     |
| `POST /api/v1/reports/{id}/full-pipeline`                      | Synthesise then QA chained in one background task                 |
| `GET  /api/v1/notifications`                                   | Latest notifications + unread count for the bell badge            |
| `POST /api/v1/notifications/mark-read`                         | Mark some / all notifications as read                             |
| `GET  /api/v1/llm/providers`                                   | Available LLM providers + models                                  |
| `GET  /api/v1/embeddings/providers`                            | Available embedding providers + models                            |
| `GET  /api/v1/documents`                                       | All documents owned by the user across every project              |
| `GET  /api/v1/analyses`                                        | All analyses owned by the user across every project               |

---

## 📁 Project structure

```
nim-eng/
├── backend/
│   ├── app/
│   │   ├── agents/
│   │   │   ├── analysis_agent.py            # LangGraph: per-document insight extraction
│   │   │   ├── research_agent.py            # multi-source search
│   │   │   ├── synthesis_agent.py           # LangGraph: LLM cross-document writer
│   │   │   ├── qa_agent.py                  # LangGraph: 0–100 quality score
│   │   │   └── tools/
│   │   │       ├── analysis/                # tools used by AnalysisAgent
│   │   │       ├── research/                # progress tracker (auto-stage builder)
│   │   │       ├── synthesis/               # context loader, outline builder,
│   │   │       │                            #   narrative synth, summary gen,
│   │   │       │                            #   citation manager, report composer
│   │   │       └── qa/                      # format / citation / fact / grammar /
│   │   │                                    #   quality scorer
│   │   ├── routes/                          # FastAPI handlers (incl. synthesis.py)
│   │   ├── services/
│   │   │   ├── auto_research_service.py     # search → ingest → analyse [→ report → synth → qa]
│   │   │   ├── document_ingestion_service.py  # publisher-whitelisted PDF-only ingest
│   │   │   ├── pdf_finder_service.py        # Unpaywall + arXiv + scrape (RG-safe)
│   │   │   ├── notification_service.py      # persistent bell-icon alerts
│   │   │   ├── synthesis_service.py         # dispatch + status helpers
│   │   │   ├── qa_service.py                # dispatch + status helpers
│   │   │   ├── report_generator/            # deterministic MD/HTML/DOCX
│   │   │   ├── stale_recovery.py            # mark zombie running rows failed
│   │   │   └── ...
│   │   ├── models/
│   │   │   ├── llm_providers/               # 5 LLM provider implementations
│   │   │   ├── embedding_providers/         # 3 embedding implementations
│   │   │   ├── notification.py
│   │   │   ├── report.py                    # synthesis_* + qa_* fields
│   │   │   └── ...
│   │   ├── tools/document/
│   │   │   ├── parsers/                     # docling-based pdf_parser.py +
│   │   │   │                                #   pdf_parser_legacy.py fallback
│   │   │   ├── chunkers/                    # section-aware (numbered/Roman/letter/named)
│   │   │   ├── fetchers/                    # PDF + HTML fetchers
│   │   │   └── vectorstores/                # pgvector
│   │   ├── tools/search/
│   │   │   ├── publisher_classifier.py      # arxiv / ieee / acm / researchgate / other
│   │   │   └── arxiv, scholar, semantic, web
│   │   ├── prompts/                         # LLM prompt templates (incl. synthesis.py, qa.py)
│   │   ├── schemas/                         # Pydantic validation (incl. synthesis.py, qa.py)
│   │   ├── database/                        # async + sync sessions
│   │   └── main.py
│   ├── alembic/versions/                    # migrations (incl. add_report_synthesis_qa_fields)
│   ├── scripts/                             # one-off maintenance scripts
│   └── requirements.txt
├── frontend/
│   └── src/
│       ├── pages/                           # AnalysisResults, ProjectDetail, Reports, …
│       ├── components/
│       │   ├── analysis/                    # SectionInsightCard, progress panels
│       │   ├── projects/                    # AutoResearchModal (with report/synth/qa toggles)
│       │   ├── research/                    # IngestSearchResultModal (publisher-aware)
│       │   ├── reports/                     # ReportCard, CreateReportModal,
│       │   │                                #   AIEnhancementPanel, QAReportModal,
│       │   │                                #   PipelineProgressPanel
│       │   ├── documents/                   # CreateDocumentModal (URL + upload)
│       │   └── layout/                      # DashboardLayout, NotificationCenter
│       ├── services/                        # API clients (incl. synthesisService, qaService)
│       └── hooks/                           # useAnalysisPolling, useReportEnhancement
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
