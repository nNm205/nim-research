<div align="center">

# NIM Research

### AI-powered Research Assistant with Multi-Agent LLMs and RAG

NIM Research is a full-stack AI document intelligence platform that helps users upload, analyze, search, and generate structured reports from research documents.
The system combines **FastAPI**, **React**, **PostgreSQL**, **Pinecone**, **LLM providers**, and a **multi-agent architecture** to transform unstructured documents into actionable insights.

[![Python](https://img.shields.io/badge/Python-3.11+-3776ab?style=flat-square\&logo=python\&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.135+-009688?style=flat-square\&logo=fastapi\&logoColor=white)](https://fastapi.tiangolo.com/)
[![React](https://img.shields.io/badge/React-19+-61DAFB?style=flat-square\&logo=react\&logoColor=black)](https://react.dev/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-14+-336791?style=flat-square\&logo=postgresql\&logoColor=white)](https://www.postgresql.org/)
[![Docker](https://img.shields.io/badge/Docker-Ready-2496ED?style=flat-square\&logo=docker\&logoColor=white)](https://www.docker.com/)

</div>

---

## 📖 Overview

**NIM Research** is designed for researchers, analysts, and knowledge workers who need to extract insights from large collections of documents.
Users can create projects, upload documents, run AI-powered analysis, ask questions over their knowledge base, and generate structured reports with source-grounded answers.

The project demonstrates practical experience in:

* Building full-stack web applications with **FastAPI** and **React**
* Designing **RAG pipelines** for document search and question answering
* Orchestrating multiple LLM-powered agents for complex workflows
* Managing authentication, projects, documents, reports, and real-time updates
* Integrating vector databases, relational databases, and external AI providers

---

## Key Features

| Feature                            | Description                                                                               |
| ---------------------------------- | ----------------------------------------------------------------------------------------- |
| **Document Analysis**              | Upload PDF, DOCX, and TXT files, then parse, chunk, embed, and analyze their content.     |
| **Retrieval-Augmented Generation** | Uses vector search to retrieve relevant document context before generating answers.       |
| **Multi-Agent Workflow**           | Specialized agents handle analysis, research, QA, synthesis, and workflow coordination.   |
| **AI Report Generation**           | Generates structured research summaries, executive summaries, and document-based reports. |
| **Knowledge Base Search**          | Enables semantic search and question answering across uploaded documents.                 |
| **Real-Time Progress Updates**     | Uses WebSocket communication to show live analysis and agent workflow status.             |
| **Authentication & Authorization** | Supports JWT authentication, password hashing, and role-based access control.             |
| **Project-Based Organization**     | Users can organize documents, analyses, and reports into separate projects.               |
| **Provider Flexibility**           | Supports multiple LLM and embedding providers through a pluggable provider design.        |

---

## 🖼️ Screenshots

### Authentication

<img src="./docs/images/nim_research_login.png" alt="Login Page" width="100%" />
<br />
<img src="./docs/images/nim_research_register.png" alt="Register Page" width="100%" />

### Dashboard

<img src="docs/images/nim_research_dashboard.png" alt="Dashboard" width="100%" />

### Projects

<img src="docs/images/nim_research_projects.png" alt="Projects Page" width="100%" />
<br />
<img src="docs/images/nim_research_project-detail.png" alt="Project Detail Page" width="100%" />

### Documents

<img src="docs/images/nim_research_documents.png" alt="Documents Page" width="100%" />

### Analysis

<img src="docs/images/nim_research_analysis.png" alt="Analysis In Progress" width="100%" />
<br />
<img src="docs/images/nim_research_analysis-result.png" alt="Analysis Result" width="100%" />

### Reports

<img src="docs/images/nim_research_reports.png" alt="Reports Page" width="100%" />

### Knowledge Base

<img src="docs/images/nim_research_knowledge-base.png" alt="Knowledge Base Page" width="100%" />

### Chat with Agents

<img src="docs/images/nim_research_chat.png" alt="Chat with Agents" width="100%" />

### Admin Panel

<img src="docs/images/nim_research_admin.png" alt="Admin Panel" width="100%" />

---

## ⚙️ Tech Stack

### Backend

* **FastAPI** — asynchronous Python web framework
* **SQLAlchemy 2.0** — ORM and database models
* **PostgreSQL** — relational database
* **Alembic** — database migrations
* **Pydantic v2** — request and response validation
* **JWT + bcrypt** — authentication and password security
* **Pytest** — backend testing

### AI / Machine Learning

* **LangChain / LangGraph** — LLM workflow and agent orchestration
* **OpenAI, Groq, Anthropic, OpenRouter** — supported LLM providers
* **Google AI, HuggingFace, Jina** — embedding providers
* **Pinecone** — vector database
* **RAG** — retrieval-augmented generation for grounded answers

### Frontend

* **React 19 + Vite** — frontend application
* **Tailwind CSS 4** — styling
* **React Router v7** — routing
* **Axios** — API communication
* **Native WebSocket** — real-time updates
* **Lucide React** — icon system

### Infrastructure

* **Docker & Docker Compose** — containerized development
* **Environment-based configuration**
* **Modular backend service architecture**

---

## System Architecture

<p align="center">
  <img src="docs/images/architecture.png" alt="System Architecture" width="90%" />
</p>

```text
Frontend: React + Vite
    |
    | HTTP / WebSocket
    v
Backend: FastAPI
    |
    |-- Auth / Projects / Documents / Analysis / Reports / Admin APIs
    |
    |-- Multi-Agent System
    |     |-- Orchestrator Agent
    |     |-- Analysis Agent
    |     |-- Research Agent
    |     |-- QA Agent
    |     |-- Synthesis Agent
    |
    |-- Services Layer
          |-- Document Service
          |-- Analysis Service
          |-- Report Service
          |-- Knowledge Base Service

Data Layer:
    |-- PostgreSQL for relational data
    |-- Pinecone for vector search
```

---

## Multi-Agent System

NIM Research uses a multi-agent architecture to divide complex document intelligence tasks into specialized responsibilities.

| Agent                  | Responsibility                                                              |
| ---------------------- | --------------------------------------------------------------------------- |
| **Orchestrator Agent** | Coordinates the workflow, routes tasks, and manages agent execution.        |
| **Analysis Agent**     | Extracts key information, entities, patterns, and summaries from documents. |
| **Research Agent**     | Retrieves relevant context from the knowledge base and supporting sources.  |
| **QA Agent**           | Answers user questions using retrieved document context.                    |
| **Synthesis Agent**    | Combines analysis outputs into structured reports and summaries.            |

---

## Core Workflow

```text
1. User creates a project
2. User uploads documents
3. Backend parses and chunks document content
4. Embeddings are generated and stored in Pinecone
5. User runs analysis or asks a question
6. Relevant chunks are retrieved through semantic search
7. Agents process the context and generate results
8. Results are saved and displayed in the dashboard
```

---

## ▶️ Getting Started

### Prerequisites

Make sure the following tools are installed:

* Python 3.11+
* Node.js 18+
* PostgreSQL 14+
* Docker & Docker Compose

---

### Option 1: Run with Docker

```bash
git clone https://github.com/nNm205/nim-research.git
cd nim-research/backend
docker-compose up -d
``` 

---

### Option 2: Run Locally

#### Backend

```bash
cd backend

python -m venv venv

# Windows
venv\Scripts\activate

# macOS / Linux
# source venv/bin/activate

pip install -r requirements.txt
copy .env.example .env

alembic upgrade head
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Backend API:

```text
http://localhost:8000
```

API Documentation:

```text
http://localhost:8000/docs
```

---

#### Frontend

```bash
cd frontend
npm install
copy .env.example .env
npm run dev
```

Frontend app:

```text
http://localhost:5173
```

---

## Environment Variables

Example backend configuration:

```env
DATABASE_URL=postgresql://user:password@localhost:5432/nim_eng

GROQ_API_KEY=your_groq_api_key
OPENAI_API_KEY=your_openai_api_key

PINECONE_API_KEY=your_pinecone_api_key
PINECONE_INDEX_NAME=nim-eng-index

SECRET_KEY=your_secret_key
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
```

Example frontend configuration:

```env
VITE_API_URL=http://localhost:8000
```

---

## API Highlights

Interactive API documentation is available through Swagger UI after running the backend:

```text
http://localhost:8000/docs
```

Main API modules include:

| Module             | Description                                                   |
| ------------------ | ------------------------------------------------------------- |
| **Auth**           | Register, login, refresh token, and manage authentication.    |
| **Projects**       | Create and manage research projects.                          |
| **Documents**      | Upload, list, retrieve, and delete documents.                 |
| **Analysis**       | Create analysis tasks and retrieve analysis results.          |
| **Reports**        | Generate, update, and manage AI-generated reports.            |
| **Knowledge Base** | Perform semantic search and RAG-based question answering.     |
| **Admin**          | Manage users, system settings, and administrative operations. |

---

## Project Structure

```text
nim-eng/
├── backend/
│   ├── app/
│   │   ├── agents/          # Multi-agent system
│   │   ├── routes/          # FastAPI route handlers
│   │   ├── services/        # Business logic layer
│   │   ├── models/          # SQLAlchemy models and providers
│   │   ├── schemas/         # Pydantic schemas
│   │   ├── database/        # Database configuration
│   │   ├── prompts/         # Agent prompt templates
│   │   ├── utils/           # Helper utilities
│   │   └── main.py          # Application entry point
│   ├── alembic/             # Database migrations
│   ├── tests/               # Backend tests
│   └── requirements.txt
│
├── frontend/
│   ├── src/
│   │   ├── pages/           # Page-level views
│   │   ├── components/      # Reusable UI components
│   │   ├── contexts/        # React contexts
│   │   ├── services/        # API clients
│   │   └── App.jsx
│   ├── package.json
│   └── vite.config.js
│
├── docs/
│   └── images/              # README screenshots and diagrams
└── .kiro/                   # Development specifications
```

---

## Testing

### Backend

```bash
cd backend
pytest
pytest --cov=app
```

### Frontend

```bash
cd frontend
npm run test
```

---

## Future Improvements

Planned improvements include:

* Advanced document citation highlighting
* More granular user roles and permissions
* Background task queue for long-running analysis jobs
* Evaluation pipeline for RAG answer quality
* Improved report templates and export formats
* Deployment configuration for cloud environments

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
