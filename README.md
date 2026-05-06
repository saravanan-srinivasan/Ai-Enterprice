# Enterprise AI Knowledge & Decision Assistant

> **Production-grade RAG + Multi-Agent AI platform for enterprise knowledge management, anomaly detection, report generation, and decision support.**

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                        Enterprise AI Platform                        │
├──────────────┬──────────────┬───────────────────┬───────────────────┤
│  React UI    │  Nginx Proxy │   FastAPI Gateway  │   Observability   │
│  (Port 3000) │  (Port 80)   │   (Port 8000)      │   /metrics /health│
└──────────────┴──────┬───────┴────────┬──────────┴───────────────────┘
                       │               │
        ┌──────────────▼───────────────▼───────────────┐
        │              Service Layer                    │
        ├─────────────────┬─────────────────────────────┤
        │  Ingestion Svc  │     Agent Orchestrator       │
        │  ─────────────  │  ─────────────────────────  │
        │  PDF/TXT/JSON/  │  QueryAgent    AnalysisAgent │
        │  CSV/LOG Parser │  ReportAgent   ActionAgent   │
        │  HybridChunker  │  Tool Registry  Memory       │
        └────────┬────────┴──────────────┬──────────────┘
                 │                        │
        ┌────────▼────────┐    ┌─────────▼──────────────┐
        │   RAG Pipeline  │    │     LLM Provider        │
        │  ─────────────  │    │  ────────────────────── │
        │  EmbeddingEngine│    │  Anthropic Claude  ← primary
        │  VectorStore    │    │  OpenAI GPT-4o     ← fallback
        │  BM25 Retriever │    │  Retry + Fallback        │
        │  RRF Fusion     │    │  Token Tracking          │
        │  Compressor     │    └─────────────────────────┘
        └────────┬────────┘
                 │
        ┌────────▼──────────────────────────────────────┐
        │              Data Layer                        │
        ├──────────────┬────────────────┬────────────────┤
        │  ChromaDB /  │  PostgreSQL    │  Redis         │
        │  FAISS       │  (Metadata +   │  (Query Cache  │
        │  (Vectors)   │   Audit Log)   │   + Sessions)  │
        └──────────────┴────────────────┴────────────────┘
```

## Module Structure

```
enterprise-ai-assistant/
├── ingestion_service/          # Document processing pipeline
│   ├── processor.py            # PDF/TXT/JSON/CSV/LOG parsers
│   ├── chunker.py              # Hybrid semantic+recursive chunking
│   └── ingestor.py             # Pipeline coordinator + DB persistence
│
├── rag_pipeline/               # Retrieval-Augmented Generation
│   ├── vector_store.py         # ChromaDB & FAISS backends + embeddings
│   ├── retriever.py            # Hybrid BM25+semantic retrieval with RRF fusion
│   ├── llm_provider.py         # Anthropic/OpenAI abstraction + retry/fallback
│   └── prompts.py              # Agent-specific prompt templates + guardrails
│
├── agent_orchestrator/         # Multi-agent execution system
│   └── orchestrator.py         # QueryAgent, AnalysisAgent, ReportAgent, ActionAgent
│                               # + ToolRegistry, AgentMemory, I/O guardrails
│
├── api_gateway/                # FastAPI application
│   ├── main.py                 # App factory, middleware, lifespan
│   └── routes/
│       ├── documents.py        # POST /upload, GET /documents, DELETE /documents/{id}
│       ├── queries.py          # POST /query, GET /history, GET /history/{id}
│       ├── insights.py         # GET /insights, GET /insights/metrics
│       └── health.py           # GET /health, GET /health/ready, GET /metrics
│
├── frontend/                   # React + TypeScript + Tailwind UI
│   └── src/
│       ├── pages/              # ChatPage, DocumentsPage, InsightsPage, HistoryPage
│       ├── components/         # Sidebar, shared UI components
│       ├── store/              # Zustand global state
│       └── utils/api.ts        # Typed Axios API client
│
├── utils/                      # Shared infrastructure
│   ├── config.py               # Pydantic Settings (all env vars typed & validated)
│   ├── logger.py               # structlog JSON logging + MetricsLogger
│   ├── database.py             # Async SQLAlchemy + connection pooling
│   ├── cache.py                # Redis cache + rate limiter + session memory
│   └── models.py               # SQLAlchemy ORM + Pydantic schemas
│
├── data/sample/                # Realistic enterprise datasets
│   ├── logistics_delays.json   # 8 shipment records with Red Sea crisis data
│   ├── finance_report_q1.json  # Q1 2024 P&L with regional breakdown
│   ├── vendor_master_data.csv  # 20 vendor records with audit scores
│   ├── supply_chain_policy.txt # Policy manual with compliance rules
│   └── operational_logs.log    # System logs with incidents + anomalies
│
├── tests/
│   └── test_full_pipeline.py   # 30+ unit + integration tests
│
├── scripts/
│   ├── setup.sh                # One-command local dev setup
│   ├── seed_data.py            # Seed vector store with sample data
│   └── init_db.sql             # PostgreSQL extensions + baseline config
│
└── docker/
    ├── Dockerfile.backend      # Multi-stage Python build
    ├── Dockerfile.frontend     # Node build → Nginx static server
    └── nginx.conf              # Reverse proxy + JSON access logs
```

---

## Quick Start

### Option A — Docker (Recommended)

```bash
# 1. Clone and configure
git clone <repo-url> && cd enterprise-ai-assistant
cp .env.example .env
# Edit .env — set ANTHROPIC_API_KEY (or OPENAI_API_KEY)

# 2. Start all services
docker compose up -d

# 3. Seed sample data
docker compose exec backend python scripts/seed_data.py

# 4. Open the app
open http://localhost:3000          # React UI
open http://localhost:8000/docs     # API Swagger
```

### Option B — Local Development

```bash
# 1. Run setup script (creates venv, installs deps, starts DB/Redis via Docker)
chmod +x scripts/setup.sh && ./scripts/setup.sh

# 2. Activate env and set API key
source .venv/bin/activate
export ANTHROPIC_API_KEY=your-key-here

# 3. Start backend
uvicorn api_gateway.main:app --reload --port 8000

# 4. Start frontend (in a new terminal)
cd frontend && npm run dev
```

---

## API Reference

### Document Ingestion

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/v1/upload` | Upload PDF/TXT/JSON/CSV/LOG for indexing |
| `GET`  | `/api/v1/documents` | List all documents with status |
| `GET`  | `/api/v1/documents/stats` | Vector store + ingestion statistics |
| `DELETE` | `/api/v1/documents/{id}` | Remove document and its vectors |

**Upload Example:**
```bash
curl -X POST http://localhost:8000/api/v1/upload \
  -F "file=@quarterly_report.pdf" \
  -F "source_tag=finance"
```

### Query Execution

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/v1/query` | Submit query to AI agents |
| `GET`  | `/api/v1/history` | Paginated query audit log |
| `GET`  | `/api/v1/history/{id}` | Single query result by ID |

**Query Example:**
```bash
curl -X POST http://localhost:8000/api/v1/query \
  -H "Content-Type: application/json" \
  -d '{
    "question": "What are the main causes of shipping delays in Q1 2024?",
    "agent_type": "analysis",
    "session_id": "session_abc123",
    "top_k": 5,
    "include_sources": true
  }'
```

**Response:**
```json
{
  "query_id": "550e8400-e29b-41d4-a716-446655440000",
  "answer": "Based on the Q1 2024 logistics data [Source 1]...",
  "agent_type": "analysis",
  "confidence_score": 0.87,
  "sources": [
    {
      "filename": "logistics_delays.json",
      "relevance_score": 0.94,
      "content_preview": "Red Sea crisis caused 14-day delays...",
      "page_number": null
    }
  ],
  "tokens_used": 2841,
  "latency_ms": 1204,
  "cached": false
}
```

### Insights & Metrics

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET`  | `/api/v1/insights` | AI-generated insights |
| `GET`  | `/api/v1/insights/metrics` | System KPIs and usage stats |
| `GET`  | `/health` | Liveness probe |
| `GET`  | `/health/ready` | Readiness (checks DB, Redis, VectorStore) |
| `GET`  | `/metrics` | Runtime metrics snapshot |

---

## Agent System

Four specialized agents, each with distinct behavior:

| Agent | `agent_type` | Best For |
|-------|-------------|----------|
| **Query Agent** | `query` | Factual Q&A — "What is the on-time delivery rate?" |
| **Analysis Agent** | `analysis` | Pattern extraction — "Analyze vendor risk factors" |
| **Report Agent** | `report` | Structured documents — "Generate Q1 logistics report" |
| **Action Agent** | `action` | Decision support — "Should we switch carriers?" |

All agents share:
- **Short-term memory** via Redis (configurable window, default 10 turns)
- **Tool calling** (context retrieval, anomaly detection, statistics)
- **Chain-of-thought** (internal `<think>` tags stripped before response)
- **Self-confidence evaluation** guardrail (0.0–1.0 score)
- **Output filtering** (removes prompt injection attempts)

---

## RAG Pipeline

```
User Query
    │
    ▼
Embed query (sentence-transformers/all-MiniLM-L6-v2, dim=384)
    │
    ├──► Dense search  → ChromaDB/FAISS (cosine similarity, top-15)
    │
    └──► Sparse search → BM25Okapi on candidate corpus
                │
                ▼
    Reciprocal Rank Fusion (RRF k=60) → merged top-5
                │
                ▼
    Context Compression (dedup + token budget enforcement)
                │
                ▼
    Prompt injection → LLM → Answer + confidence eval
```

**Chunking strategy:**
- **PDFs**: Page-aware → semantic (sentence-boundary) splitting
- **Structured (JSON/CSV)**: Record-aware recursive splitting  
- **Logs**: Rolling line-window grouping
- **Text**: Pure semantic chunking with overlap

---

## Configuration

All settings are in `.env` (validated by Pydantic Settings on startup):

```env
# Required
ANTHROPIC_API_KEY=sk-ant-...

# LLM
LLM_PROVIDER=anthropic              # anthropic | openai | gemini
LLM_MODEL=claude-sonnet-4-20250514
LLM_TEMPERATURE=0.1

# RAG tuning
TOP_K_RETRIEVAL=5
CHUNK_SIZE=512
CHUNK_OVERLAP=64

# Performance
CACHE_TTL_SECONDS=3600
RATE_LIMIT_PER_MINUTE=60
AGENT_TIMEOUT_SECONDS=120
```

---

## Running Tests

```bash
# Install test dependencies
source .venv/bin/activate

# Run all tests
pytest tests/ -v

# Run specific test class
pytest tests/test_full_pipeline.py::TestDocumentProcessors -v

# Run with coverage
pytest tests/ --cov=. --cov-report=html
```

The test suite covers:
- Document processors (PDF, TXT, JSON, CSV, LOG)
- Chunking strategies (recursive, semantic, hybrid)
- BM25 retrieval + fusion logic
- Prompt templates + guardrail evaluation
- LLM provider formatting + fallback
- Agent memory + input/output sanitization
- Cache key determinism + Redis interactions
- FastAPI endpoints (validation, routing, schema)

---

## Production Checklist

- [ ] Set a strong `SECRET_KEY` (≥ 32 random chars)
- [ ] Use secrets manager (AWS Secrets Manager / Vault) for `ANTHROPIC_API_KEY`
- [ ] Enable TLS on Nginx (`certbot` / ACM)
- [ ] Set `APP_ENV=production` and `DEBUG=false`
- [ ] Configure Postgres with proper password and restricted network access
- [ ] Enable Redis `requirepass` and TLS
- [ ] Set up log shipping (Datadog / CloudWatch / ELK)
- [ ] Wire Prometheus scrape to `/metrics` endpoint
- [ ] Set `CORS_ORIGINS` to your actual domain
- [ ] Review `RATE_LIMIT_PER_MINUTE` for your expected load
- [ ] Run `pytest tests/` in CI before every deploy

---

## Technology Stack

| Layer | Technology |
|-------|-----------|
| Backend framework | FastAPI (async) + Uvicorn + uvloop |
| LLM providers | Anthropic Claude, OpenAI GPT-4o |
| Embeddings | sentence-transformers (`all-MiniLM-L6-v2`) |
| Vector store | ChromaDB (default) or FAISS |
| Keyword search | rank-bm25 (BM25Okapi) |
| Database | PostgreSQL 16 + SQLAlchemy async |
| Cache / Sessions | Redis 7 + hiredis |
| Document parsing | pdfplumber, chardet, csv, json |
| Logging | structlog (JSON in prod, colored in dev) |
| Frontend | React 18, TypeScript, Vite, Tailwind CSS |
| State management | Zustand + TanStack Query |
| Charts | Recharts |
| Container | Docker + Docker Compose + Nginx |
| Testing | pytest + pytest-asyncio + httpx |

---

## License

MIT — See LICENSE file. Enterprise use permitted.
