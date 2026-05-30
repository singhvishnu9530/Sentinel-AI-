# 🛡️ Sentinel AI — Requirement Autopsy & Build Guide Engine

> Paste a project brief (or upload a PDF / Word doc / screenshot) and Sentinel AI turns it into a concrete, costed **build guide** — what technology to use, how to start, what it costs, and what to watch out for — so **any engineer can begin building without waiting on the senior lead.**

Sentinel AI attacks the most expensive failure mode in software teams: when a new project lands, only one senior person knows *how* to build it, becomes a bottleneck, and makes every decision alone. Sentinel turns a raw requirement into an expert-level, opinionated, vendor-neutral build blueprint in ~90 seconds.

---

## ✨ What it does

1. **Understands the brief** — typed, pasted, or extracted from an uploaded **PDF / Word / text file / image** (screenshots & whiteboards are transcribed by a vision model).
2. **Runs 5 specialist AI agents in parallel**, each researching the requirement live with web search.
3. **Synthesises one Build Guide** — problem statement, budget tiers, recommended stack with priced alternatives, expert implementation techniques, step-by-step build plan, deployment, cost, risks, and a security checklist.
4. **Stays interactive** — ask follow-up questions ("why Postgres?", "what if we use Azure?") answered with the report in context plus live web search.
5. **Exports** the guide to **Word (.docx)** and tracks **token cost** per session.

---

## 🏗️ Architecture Overview

```
                ┌─────────────────────────────────────────────┐
  User brief →  │  React UI (chat)  ──►  FastAPI (port 8001)   │
  PDF/img/doc   │   - auth (signup/login)                      │
                │   - /api/extract  (PDF/DOCX/TXT + image OCR) │
                │   - /api/chat     (LLM proxy, streaming)     │
                └───────────────┬─────────────────────────────┘
                                │ when a project brief is detected
                                ▼
                ┌─────────────────────────────────────────────┐
                │   LangGraph workflow (port 2024)             │
                │                                              │
   START ──┬──► Requirement Analyst ──┐                        │
           ├──► Tech Stack Advisor  ──┤                        │
           ├──► Complexity & Risk   ──┼──► Build Blueprint ──► END
           ├──► Security Analyser   ──┤    (synthesis agent)   │
           └──► NFR Detector        ──┘                        │
                (5 agents run in parallel, each with web_search)
                └─────────────────────────────────────────────┘
```

- **5 parallel analysis agents** each answer one question (what to build, what to use + cost, what's hard / risky, security, performance & scale). They run concurrently via LangGraph fan-out.
- **1 synthesis agent** (`build_blueprint`) reads all 5 reports, resolves cross-agent conflicts, verifies facts via web search, and produces the final guide.
- Every agent is a **LangChain `create_agent`** with **structured (Pydantic) output**, **model + tool retry middleware**, and a **SQLite checkpointer** for resilient runs.

### Anti-hallucination & no vendor bias
Agents must commit to concrete recommendations with stated assumptions (never "TBD"), verify prices/versions with live web search rather than memory, and treat AWS/Azure/GCP and OpenAI/Anthropic/Gemini/open-source as equally valid — preferring the team's existing ecosystem.

---

## 🤖 AI Tools & Tech Stack

| Layer | Technology |
|---|---|
| **LLM** | `gpt-5.2` via **Azure AI Foundry** (OpenAI-compatible endpoint), incl. vision for image OCR |
| **Agent framework** | **LangChain** `create_agent` + `ModelRetryMiddleware`, `ToolRetryMiddleware` |
| **Orchestration** | **LangGraph** (parallel fan-out → synthesis), `SqliteSaver` checkpointer |
| **Web research tool** | **Tavily** search API (`web_search` tool) |
| **Observability** | **LangSmith** tracing |
| **Backend** | **FastAPI** + Uvicorn (auth, chat proxy, document/image extraction) |
| **Auth & storage** | **SQLite** + **bcrypt** password hashing |
| **Doc extraction** | `pypdf` (PDF), `python-docx` (Word), vision LLM (images) |
| **Frontend** | **React 19 + Vite + TypeScript + Tailwind CSS** |
| **Export** | `docx` (Word build-guide export) |
| **Testing** | `pytest` + `pytest-asyncio` (19 tests, mocked LLM) |

---

## 📁 Repository Structure

```
Hackthon/
├── Sentinel-AI-/                 # Backend
│   ├── auth_server.py            # FastAPI entry (port 8001)
│   ├── langgraph.json            # LangGraph graph config (port 2024)
│   ├── start.sh                  # runs auth_server + langgraph dev together
│   ├── requirements.txt
│   ├── data/                     # SQLite DBs (users, agent checkpoints)
│   ├── test/                     # 19 pytest tests
│   └── src/
│       ├── agents/               # 5 analysis agents + build_blueprint
│       ├── prompts/              # one prompt per agent + shared grounding
│       ├── graphs/workflow.py    # LangGraph fan-out → synthesis
│       ├── models/state.py       # shared graph state
│       ├── tools/web_search.py   # Tavily tool
│       └── utils/                # auth, chat, extract, database endpoints
└── Sentinel_frontend/            # Frontend (React + Vite)
    └── src/
        ├── components/           # AuthPage, Sidebar, ChatMessage, AnalysisReport…
        └── utils/                # api, auth, exportDocx
```

---

## ⚙️ Setup Instructions

### Prerequisites
- **Python 3.12+**, **Node.js 18+**, npm
- An **Azure AI Foundry** deployment of a `gpt-5.2`-class model, and a **Tavily** API key

### 1. Backend (`Sentinel-AI-/`)
```bash
cd Sentinel-AI-
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
```

Create `Sentinel-AI-/.env`:
```env
azure_endpoint="https://<your-resource>.services.ai.azure.com/openai/v1"
FOUNDRY_API_KEY="<your-azure-foundry-key>"
OPENAI_MODEL="gpt-5.2"
TAVILY_API_KEY="<your-tavily-key>"
LANGCHAIN_API_KEY="<optional-langsmith-key>"
LANGCHAIN_TRACING_V2=true
LANGCHAIN_PROJECT="Sentinel AI"
```

### 2. Frontend (`Sentinel_frontend/`)
```bash
cd Sentinel_frontend
npm install
```
No secrets live in the frontend — all API keys stay server-side.

---

## ▶️ Running the App

Open **three terminals** (or use `start.sh` for the two backend services):

```bash
# Terminal 1 + 2 — backend (LangGraph on :2024, FastAPI on :8001)
cd Sentinel-AI- && source venv/bin/activate && ./start.sh

# Terminal 3 — frontend (Vite on :5173)
cd Sentinel_frontend && npm run dev
```

Then open **http://localhost:5173**, create an account, and paste/upload a project brief.

---

## 🧪 Testing

```bash
cd Sentinel-AI- && source venv/bin/activate && pytest test/ -v
```
19 tests cover the agents, the full LangGraph orchestration, the auth + chat API, the database layer, and the web-search tool. The LLM is mocked, so tests run in ~2s with no API cost.

---

## 🚀 Key Features

- 📄 **Multi-format input** — type, paste, or upload PDF / Word / text / **image (vision OCR)**
- ⚡ **Parallel multi-agent analysis** with live web research
- 💰 **Budget tiers** (Lean / Balanced / Scale) + **priced alternatives** per layer — the user chooses by cost
- 🧠 **Expert implementation techniques** — frameworks, patterns, libraries, not just tool names
- 💬 **Follow-up Q&A** grounded in the report + live web search
- 📥 **Word (.docx) export** of the full build guide
- 🔢 **Live token-cost tracking** per session
- 🔐 **Auth** (bcrypt) + persisted chat sessions

---

## 👥 Team

> _Replace with your team's real names, emails, and roles before submission._

| Name | Role | Responsibilities |
|---|---|---|
| Vishnu Singh | Full-stack / AI Engineer | Agent design, LangGraph workflow, backend & frontend |
| Pradumn Patidar | Senior Data Scientist | AI agent design, prompt engineering, model & evaluation |

---

*Built for [Hackathon name] · Powered by Azure AI Foundry, LangGraph & LangChain.*
