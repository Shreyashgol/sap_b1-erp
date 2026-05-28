# SAP B1 Purchase Supervisor Agent

A unified **FastAPI backend + Streamlit Supervisor UI** for SAP Business One purchase workflows.

A single **Supervisor Agent** (powered by LangGraph + Claude LLM) classifies every natural-language prompt and routes it to the correct sub-agent — Purchase Order, AP Invoice, or Purchase Return — without the user needing to know which document type they need.

---

## Architecture

```
User (Streamlit UI)
       │
       ▼
Supervisor Agent  ──LangGraph routing──►  Purchase Order Agent
(supervisor_agent.py)                 ├──► AP Invoice Agent
                                      └──► Purchase Return Agent
       │                                        │
       │                                        ▼
       └──────────────────────────────  FastAPI Backend (app/main.py)
                                                │
                                        External SAP HANA DB API (vzone.in)
                                        SAP Business One Service Layer
```

**LLM stack:** All intent parsing, routing, SQL generation, and chat responses run through the **Claude API** (`claude-opus-4-7` by default).

**RAG fetch:** Analytical fetch queries (totals, rankings, overdue, etc.) bypass the intent parser and use ChromaDB + `sentence-transformers` to retrieve relevant schema and example SQL, then generate a strict SAP HANA `SELECT` query via Claude. The query is safely executed against an external SAP HANA Database API endpoint.

---

## Folder Structure

```
sap/
├── .env.example              ← copy to .env and fill in your secrets
├── .gitignore
├── README.md
├── requirements.txt
├── pyproject.toml
├── streamlit_app.py          ← Streamlit Supervisor UI entry point
│
├── app/
│   ├── main.py               ← FastAPI application entry point
│   ├── config.py             ← All settings loaded from .env
│   ├── chat_response.py      ← Formats the final chatbot reply via Claude
│   │
│   ├── agents/
│   │   ├── big_supervisor_agent.py
│   │   ├── purchase_team/    ← Purchase Order / AP Invoice / Purchase Return agents
│   │   └── sales_team/       ← Sales Order / AR Invoice / Sales Return agents
│   │
│   ├── api/
│   │   ├── purchase_orders.py
│   │   ├── ap_invoices.py
│   │   ├── purchase_returns.py
│   │   └── sales.py
│   │
│   ├── crud/                 ← Repository layer (DB reads/writes per document type)
│   ├── db/                   ← SQLAlchemy models and pool initialisation
│   ├── model/                ← Pydantic intent models
│   ├── schema/               ← Pydantic request/response schemas
│   │
│   ├── operations/
│   │   ├── claude_client.py  ← Thin wrapper around the Claude messages API
│   │   ├── llm_client.py     ← Unified chat_completion() delegates to claude_client
│   │   ├── sap_client.py     ← SAP Business One Service Layer HTTP client
│   │   ├── purchase_rag.py   ← ChromaDB RAG store + SQL generation for analytics
│   │   ├── sales_rag.py      ← Sales RAG SQL generation for analytics
│   │   ├── sql_executor.py   ← Safe SQL fetch executor with timeout
│   │   ├── error_handler.py  ← SAP error message translator
│   │   └── utils.py          ← Guest auth shim + dynamic agent module loader
│   │
│   └── rag/
│       └── data/
│           ├── purchase_tables.json  ← SAP table/column schema for RAG
│           └── purchase_queries.json ← Example SQL queries for RAG retrieval
│
└── shared/
    ├── env.py        ← .env file loader (no python-dotenv dependency)
    ├── bootstrap.py  ← sys.path helper for repo-root resolution
    └── db/
        └── runtime.py ← SQLAlchemy engine factory shared by all agents
```

---

## Prerequisites

| Requirement | Notes |
|---|---|
| Python ≥ 3.10 | `python3 --version` |
| PostgreSQL | Neon (recommended) or any Postgres instance |
| Claude API key | Anthropic Console API key |
| SAP Business One | Service Layer URL (for write operations) |

---

## Setup

### 1. Clone and create your environment file

```bash
cp .env.example .env
```

Open `.env` and fill in **at minimum**:

```bash
SAP_AGENTS_DATABASE_URL=postgresql://user:pass@host:5432/dbname?sslmode=require
CLAUDE_API_KEY=sk-ant-...
CLAUDE_MODEL=claude-opus-4-7
CLAUDE_PROMPT_CACHE=true
```

### 2. Create a virtual environment and install dependencies

```bash
python3 -m venv myvenv
./myvenv/bin/pip install -r requirements.txt
```

---

## Environment Variables

All variables are read from `.env` at startup via `shared/env.py`.

| Variable | Required | Default | Description |
|---|---|---|---|
| `SAP_AGENTS_DATABASE_URL` | ✅ | — | PostgreSQL connection string |
| `CLAUDE_API_KEY` | ✅ | — | Claude/Anthropic API key for all LLM calls |
| `SAP_BASE_URL` | ⬜ | `http://localhost:50000/b1s/v1` | SAP Service Layer base URL |
| `SAP_USERNAME` | ⬜ | `manager` | SAP login username |
| `SAP_PASSWORD` | ⬜ | `password` | SAP login password |
| `SAP_COMPANYDB` | ⬜ | `SBODEMOUS` | SAP company database name |
| `CLAUDE_BASE_URL` | ⬜ | `https://api.anthropic.com/v1` | Claude API endpoint |
| `CLAUDE_MODEL` | ⬜ | `claude-opus-4-7` | Claude model to use |
| `CLAUDE_API_VERSION` | ⬜ | `2023-06-01` | Anthropic API version header |
| `CLAUDE_PROMPT_CACHE` | ⬜ | `true` | Adds Claude `cache_control` to reusable system prompts |
| `PURCHASE_RAG_EMBEDDING_MODEL` | ⬜ | `BAAI/bge-base-en-v1.5` | Sentence-transformer model for ChromaDB |
| `PURCHASE_RAG_PERSIST_DIR` | ⬜ | `.rag_chroma/purchase` | ChromaDB persistence directory |
| `SQL_QUERY_TIMEOUT` | ⬜ | `30` | Max seconds for a raw SQL fetch |

---

## Running the Application

### Start the FastAPI backend

```bash
./myvenv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Verify it's up:

```bash
curl http://127.0.0.1:8000/
# → {"message": "SAP B1 Purchase Supervisor Agent is running"}
```

### Start the Streamlit UI

Open a **second terminal** from the repo root:

```bash
./myvenv/bin/python -m streamlit run streamlit_app.py \
  --server.address 127.0.0.1 --server.port 8501
```

Then open: **http://127.0.0.1:8501**

In the sidebar:
- Keep **FastAPI URL** as `http://127.0.0.1:8000`
- Log in with your credentials (default demo: `user1` / `pass123456`)
- Type any purchase request in plain English — the Supervisor routes it automatically
- Open the **Supervisor and backend details** expander to view the real-time **Agent Flow**, the generated **SAP HANA SQL**, and the resulting JSON.

---

## Using the Package After Installation

Once installed the package exposes the FastAPI app and all agents as importable modules.

### 1. Configure environment variables

```bash
cp .env.example .env
# Fill in SAP_AGENTS_DATABASE_URL and CLAUDE_API_KEY (minimum required)
```

### 2. Start the FastAPI backend

```bash
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Verify it's running:

```bash
curl http://127.0.0.1:8000/
# → {"message": "SAP B1 Purchase Supervisor Agent is running"}
```

### 3. Start the Streamlit Supervisor UI

Open a **second terminal**:

```bash
streamlit run streamlit_app.py --server.address 127.0.0.1 --server.port 8501
```

Then open **http://127.0.0.1:8501** in your browser.

### 4. Use the agents in your own Python code

```python
from app.agents.purchase_team.supervisor_agent import execute

# Route any natural-language purchase prompt automatically
result = execute("Show me the latest 5 purchase orders for vendor V001")
print(result)
```

```python
from app.agents.big_supervisor_agent import route

result = route("Create a purchase order for 10 units of item A00001 from vendor V001")
print(result)
```

---

## Building the `.whl` Yourself

If you want to rebuild the wheel from source:

```bash
python3 -m pip install build
python3 -m build --wheel
# Output: dist/sap_erp_supervisor_agent-0.1.0-py3-none-any.whl
```

---

## API Examples

### Run a purchase order prompt

```bash
curl -X POST "http://127.0.0.1:8000/purchase-orders/parse-and-execute" \
  -H "Content-Type: application/json" \
  -d '{"prompt": "Show me the latest 5 purchase orders for vendor V001"}'
```

### Run an AP invoice prompt

```bash
curl -X POST "http://127.0.0.1:8000/ap-invoices/parse-and-execute" \
  -H "Content-Type: application/json" \
  -d '{"prompt": "What is the total AP invoice balance due this month?"}'
```

### Run a purchase return prompt

```bash
curl -X POST "http://127.0.0.1:8000/purchase-returns/parse-and-execute" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"prompt": "Show me the latest 5 purchase returns"}'
```

---

## Features

| Feature | Status |
|---|---|
| Supervisor Agent (LangGraph) routes PO / AP Invoice / Purchase Return | ✅ |
| Purchase Order: create, update, fetch, cancel, close | ✅ |
| AP Invoice: create, update, fetch, cancel, close, reopen | ✅ |
| Purchase Return: create, update, fetch, cancel, close, reopen | ✅ |
| Bulk CSV / XLSX upload for purchase orders | ✅ |
| OCR document reading (PDF, PNG, JPG — macOS only) | ✅ |
| Analytical RAG fetch (ChromaDB + Claude HANA SQL generation) | ✅ |
| Transparent UI showing full Agent Routing Flow & SQL Generation | ✅ |
| Fully simulated Dummy SAP Service Layer for local development | ✅ |
| External SAP HANA Database API integration | ✅ |
| Claude LLM for all inference | ✅ |

---

## Verification

Quick import and routing smoke-test:

```bash
PYTHONDONTWRITEBYTECODE=1 ./myvenv/bin/python - <<'PY'
from app.main import app
from app.agents.big_supervisor_agent import route
print(app.title)
print(len(app.routes))
result = route("show latest purchase orders")
print(result["routing_decision"]["documentType"])
PY
```



---

## Development Notes

- All new code belongs inside the `app/` package.
- Add document-agent logic under `app/agents/<agent_name>/`.
- Add SAP API endpoints under `app/api/`.
- Add repository/CRUD logic under `app/crud/`.
- Add PostgreSQL models under `app/db/`.
- Add intent/data models under `app/model/`.
- Add shared operations under `app/operations/`.
- Add request/response schemas under `app/schema/`.
- **Never commit real credentials.** Keep all secrets in `.env` (already in `.gitignore`).
