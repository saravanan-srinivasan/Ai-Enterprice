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
        │  EmbeddingEngine│    │  Groq API (llama-3.3)   │
        │  VectorStore    │    │  Free tier: 30 req/min  │
        │  BM25 Retriever │    │  Retry + Rate Limiting  │
        │  RRF Fusion     │    │  Token Tracking         │
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
│   ├── llm_provider.py         # Groq API provider with retry logic
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

### ✅ Production Deployment (Render + Netlify)

**Ready to go live?** See [DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md) for complete instructions.

- **Backend**: Render ($5/month)
- **Frontend**: Netlify (free)
- **LLM**: Groq (free tier available)
- **Total Cost**: ~$17/month

### Option A — Docker (Recommended for Local Dev)

```bash
# 1. Clone and configure
git clone <repo-url> && cd enterprise-ai-assistant
cp .env.example .env
# Edit .env — set GROQ_API_KEY from https://console.groq.com/api-keys (FREE)

# 2. Start all services
docker compose up -d

# 3. Seed sample data
docker compose exec backend python scripts/seed_data.py

# 4. Open the app
open http://localhost:5173          # React UI (Vite)
open http://localhost:8000/docs     # API Swagger
```

### Option B — Local Development

```bash
# 1. Get Groq API key (FREE)
# Visit: https://console.groq.com/api-keys
# Sign up → Create API key → Copy it

# 2. Install dependencies
pip install -r requirements.txt
cd frontend && npm install && cd ..

# 3. Set API key
export GROQ_API_KEY="sk-your-key-here"

# 4. Start backend (Terminal 1)
uvicorn api_gateway.main:app --reload --port 8000

# 5. Start frontend (Terminal 2)
cd frontend && npm run dev

# Open: http://localhost:5173
```

---

## 📚 Documentation

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
# Required - Get FREE API key from https://console.groq.com/api-keys
GROQ_API_KEY=sk-...

# LLM (Groq-only)
LLM_MODEL=llama-3.3-70b-versatile
LLM_TEMPERATURE=0.1
LLM_MAX_TOKENS=4096
LLM_TIMEOUT_SECONDS=60

# RAG tuning
TOP_K_RETRIEVAL=5
CHUNK_SIZE=512
CHUNK_OVERLAP=64

# Database & Cache
DATABASE_URL=postgresql+asyncpg://...  # Auto-provided by Render
REDIS_URL=redis://...                  # Auto-provided by Render

# Frontend Access
CORS_ORIGINS=https://your.netlify.app,http://localhost:5173

# Performance
CACHE_TTL_SECONDS=3600
RATE_LIMIT_PER_MINUTE=60
AGENT_TIMEOUT_SECONDS=120
WORKERS=1  # Keep at 1 for Render Starter plan

# Storage
DATA_DIR=/opt/render/project/data

# See .env.example for all available options
```

See [.env.example](.env.example) for complete documentation.

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

## Production Deployment

This project is **production-ready** and can be deployed to Render + Netlify in 15 minutes.

**See [DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md) for complete step-by-step instructions.**

### Pre-Deployment Checklist

- [ ] Get Groq API key: https://console.groq.com/api-keys (FREE)
- [ ] Set environment variables (see `.env.example`)
- [ ] Run local tests: `pytest tests/ -v`
- [ ] Test locally: `bash deploy.sh`
- [ ] See [CHECKLIST.md](CHECKLIST.md) for full validation

### Deployment Targets

| Component | Platform | Cost | Setup Time |
|-----------|----------|------|-----------|
| Backend (FastAPI) | Render | $5/month | 5 min |
| Frontend (React) | Netlify | Free | 5 min |
| Database | Render PostgreSQL | $7/month | Auto |
| Cache | Render Redis | $5/month | Auto |
| **Total** | | **~$17/month** | **15 min** |

---

## Technology Stack

| Layer | Technology |
|-------|-----------|
| Backend framework | FastAPI (async) + Uvicorn + uvloop |
| LLM provider | **Groq API** (llama-3.3-70b-versatile) |
| Embeddings | sentence-transformers (`all-MiniLM-L6-v2`, local, no API) |
| Vector store | ChromaDB (default) or FAISS |
| Keyword search | rank-bm25 (BM25Okapi) |
| Database | PostgreSQL 16 + SQLAlchemy async |
| Cache / Sessions | Redis 7 + hiredis |
| Document parsing | pdfplumber, chardet, csv, json |
| Logging | structlog (JSON in prod, colored in dev) |
| Frontend | React 18, TypeScript, Vite, Tailwind CSS |
| State management | Zustand + TanStack Query |
| Charts | Recharts |
| Deployment | Render (backend) + Netlify (frontend) |
| Container | Docker + Docker Compose + Nginx (optional) |
| Testing | pytest + pytest-asyncio + httpx |

---

## License

MIT — See LICENSE file. Enterprise use permitted.
