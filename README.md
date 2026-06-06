<div align="center">

# NIM Research

### AI-powered research assistant for academic document analysis

A full-stack platform that ingests research papers, extracts structured insights section-by-section, runs cross-source literature search, and chains everything into a single one-click pipeline — so you can go from "what's known about X?" to a fully analysed corpus in minutes.

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

Researchers spend hours on the boring parts of literature work — searching across databases, downloading PDFs, scrolling through them, taking notes section by section, then connecting the dots. NIM Research automates each of those steps and puts them on one pipeline.

**Three core workflows**:

- **Upload & analyse** — drop a PDF or paste an arXiv URL. The platform parses it (handling 2-column layouts, math symbols, tables), chunks it section-aware, embeds each chunk, then runs a section-by-section LLM analysis that extracts claims, methods, data, tables, formulas, critique, and quotes. Results render as scannable cards with KaTeX math, sortable tables, and an executive summary.
- **Multi-source search** — query arXiv, Google Scholar, and Semantic Scholar in parallel; results are deduplicated and re-ranked by semantic relevance. Click "Add to project" on any result and the system auto-locates a downloadable PDF (Unpaywall via DOI, arXiv-derived, or scraped from the landing page) and runs the full ingest pipeline.
- **Auto-research** — type a topic, pick how many papers to ingest and which LLM to use, walk away. The orchestrator chains *search → ingest top-N → analyse each → report* into a single background task with a live progress panel showing every stage.

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
    <td align="center"><sub>Generated reports</sub></td>
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
- **Auto-research**: search → ingest top-N → analyse each → report, all in one background task with a live 4-stage progress panel
- Standalone analyses also get a live progress panel

### LLM + embedding flexibility

- 5 LLM providers: **Gemini**, **Groq**, **OpenAI**, **Claude**, **OpenRouter** — pick one per analysis
- 3 embedding providers: **HuggingFace**, **Jina**, **Google AI**
- Free-tier-aware retry: parses `retryDelay` from Gemini 429 responses, exponential backoff for others, sequential analyses inside the auto-research orchestrator

### UX

- Tag-chip topic editor with keyboard shortcuts (Enter / comma / Backspace)
- Cross-project documents and analyses pages with project + status filter chips
- Live progress panels with per-stage steppers, per-item counters, embedded sub-progress
- Tables auto-detect numeric columns and right-align with tabular numbers
- KaTeX-rendered math with error boundary fallback to raw LaTeX

### Performance

- Async DB session compatible with **Supabase Supavisor pooler** (per-call UUID-named prepared statements, statement cache disabled)
- pgvector for semantic chunk search
- pg_trgm GIN indexes for fast title/content fuzzy search in the knowledge base
- List endpoints defer heavy `content` / JSONB columns; counts via `GROUP BY` instead of `len(selectin)`
- Window function `count(*) OVER ()` instead of separate count + fetch queries

---

## Tech stack

### Backend
- **FastAPI** with async/await throughout
- **SQLAlchemy 2.0** + **asyncpg** for the async path, **psycopg2** for sync admin paths
- **PostgreSQL 15** with **pgvector** and **pg_trgm** extensions
- **Alembic** migrations
- **LangChain** + **LangGraph** for agent orchestration
- **PyMuPDF** + **pdfplumber** for PDF parsing
- **httpx** for outbound HTTP (Unpaywall, S2 API)

### Frontend
- **React 19** + **Vite** + **Tailwind 4**
- **React Router v7**
- **react-katex** for math rendering
- **Lucide** icons
- Polling-based progress updates (3s interval while a session is active)

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
│  React + Vite  │   HTTP + 3s polling for live   │    FastAPI     │
│  + Tailwind    │ ◄──────────────────────────────►   (async)      │
└────────────────┘                                └───────┬────────┘
                                                          │
                          ┌───────────────────────────────┴────────────────────────┐
                          │                                                        │
                          ▼                                                        ▼
        ┌──────────────────────────────────┐                     ┌────────────────────────────┐
        │         AnalysisAgent            │                     │      AutoResearchService   │
        │      (LangGraph pipeline)        │                     │       (orchestrator)       │
        │                                  │                     │                            │
        │  load_chunks → map_sections      │                     │  search → ingest top-N     │
        │   → build_outline → analyse      │                     │   → analyse each → done    │
        │   → synthesize → persist         │                     │                            │
        └────────────┬─────────────────────┘                     └─────────────┬──────────────┘
                     │                                                         │
                     │ uses                                              uses  │
                     ▼                                                         ▼
        ┌──────────────────────────────────────────────────────────────────────────────┐
        │  Service layer: documents · analyses · projects · research · KB · reports   │
        └────────────────────────────────────┬─────────────────────────────────────────┘
                                             │
                  ┌──────────────────────────┴──────────────────────────┐
                  ▼                                                     ▼
   ┌─────────────────────────────┐                   ┌──────────────────────────────────┐
   │  PostgreSQL + pgvector      │                   │  External APIs                   │
   │                             │                   │  · arXiv · Google Scholar (SerpAPI)│
   │  · projects · documents     │                   │  · Semantic Scholar · Unpaywall  │
   │  · document_chunks (vector) │                   │  · LLM providers · Embedding     │
   │  · analyses · reports · kb  │                   │    providers                     │
   └─────────────────────────────┘                   └──────────────────────────────────┘
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
│   │   │   └── ...
│   │   ├── models/
│   │   │   ├── llm_providers/               # 5 LLM provider implementations
│   │   │   ├── embedding_providers/         # 3 embedding implementations
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
│   ├── alembic/versions/                    # 9 migrations
│   ├── scripts/                             # one-off maintenance scripts
│   └── requirements.txt
├── frontend/
│   └── src/
│       ├── pages/                           # AnalysisResults, ProjectDetail, …
│       ├── components/
│       │   ├── analysis/                    # SectionInsightCard, progress panels
│       │   ├── projects/                    # AutoResearchModal, TopicChipInput
│       │   ├── research/                    # IngestSearchResultModal, progress
│       │   └── documents/                   # CreateDocumentModal (URL + upload)
│       ├── services/                        # API clients
│       └── hooks/                           # useAnalysisPolling
└── docs/images/                             # screenshots
```

---

## Roadmap

- [ ] PDF citation highlighting on analysis results
- [ ] Background job queue (Celery/RQ) instead of in-process `asyncio.create_task`
- [ ] Evaluation harness for analysis quality across paper genres
- [ ] Export reports as Word / LaTeX with citation formatting
- [ ] Multi-tenant team workspaces with role-based access
- [ ] Cloud deployment templates (Vercel + Render / Fly.io)

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