# DocuMind — Technical Documentation Q&A Bot

A RAG-powered chatbot that scrapes any software documentation website and lets developers ask natural-language questions, receiving cited, accurate answers pulled directly from the docs.

## 🚀 Features

- **RAG Pipeline**: Retrieval Augmented Generation using OpenAI embeddings + GPT-4o
- **Docs Crawler**: Scrapy spider that recursively crawls any documentation site
- **Smart Chunking**: 512-token chunks with 128-token overlap for optimal retrieval
- **Vector Search**: FAISS IndexFlatIP with L2-normalized cosine similarity
- **Redis Caching**: Two-level cache (embeddings + responses) for performance
- **Async Pipeline**: Celery background tasks for non-blocking crawl operations
- **Chat Sessions**: Multi-turn conversations with history persistence
- **Live Citations**: Every answer includes source links to the original docs
- **Production Infrastructure**: Docker Compose with PostgreSQL, Redis, Celery

## 📋 Prerequisites

- Docker & Docker Compose
- OpenAI API key

## ⚡ Quick Start

### 1. Clone and configure

```bash
cd documind
cp .env.example .env
```

Edit `.env` and add your OpenAI API key:
```
OPENAI_API_KEY=sk-your-actual-key-here
```

### 2. Start all services

```bash
docker-compose up --build
```

This starts:
- **FastAPI app** → http://localhost:8000
- **PostgreSQL** → localhost:5432
- **Redis** → localhost:6379
- **Celery Worker** (background tasks)
- **Celery Beat** (scheduled re-crawls)

### 3. Open the UI

Navigate to http://localhost:8000 in your browser.

### 4. Index documentation

Enter a docs URL (e.g., `https://fastapi.tiangolo.com`) and click "Crawl & Index". The crawler will:
1. Crawl all pages within the domain
2. Clean and chunk the text
3. Generate embeddings via OpenAI
4. Store vectors in FAISS for retrieval

### 5. Ask questions

Once indexing completes, ask any question about the docs. You'll get a cited answer in seconds.

## 🏗️ Architecture

```
┌──────────────┐    ┌──────────────┐    ┌──────────────────┐
│ Scrapy Spider│───▶│ Text Cleaner │───▶│ Chunk Splitter   │
│ (crawls docs)│    │ (strip HTML) │    │ (512 tok/128 ovr)│
└──────────────┘    └──────────────┘    └────────┬─────────┘
                                                  │
                    ┌────────────────────────────▼──────────┐
                    │  OpenAI Embeddings → FAISS + Postgres  │
                    └────────────────────────────────────────┘

┌──────────────┐    ┌──────────────┐    ┌──────────────────┐
│  User Query  │───▶│ Embed Query  │───▶│ FAISS top-k      │
│  /api/chat   │    │              │    │ similarity search│
└──────────────┘    └──────────────┘    └────────┬─────────┘
                                                  │
                    ┌────────────────────────────▼──────────┐
                    │  GPT-4o generates cited answer          │
                    └────────────────────────────────────────┘
```

## 📡 API Reference

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Health check + vector store stats |
| POST | `/api/crawl` | Trigger new documentation crawl |
| GET | `/api/crawl/{job_id}` | Poll crawl job status |
| GET | `/api/crawl` | List all crawl jobs |
| POST | `/api/chat` | Ask a question |
| GET | `/api/sessions/{id}/messages` | Get chat history |
| DELETE | `/api/sessions/{id}` | Delete session |

### Example: Ask a question

```bash
curl -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{"question": "How do I implement OAuth2 with FastAPI?"}'
```

## 🧪 Running Tests

```bash
# Unit tests (no infrastructure needed)
pytest tests/test_chunker.py -v

# Integration tests (requires Docker services running)
docker-compose up -d
pytest tests/test_api.py -v
```

## 📁 Project Structure

```
documind/
├── docker-compose.yml          # Infrastructure
├── Dockerfile                  # App container
├── requirements.txt            # Python deps
├── alembic.ini                 # DB migrations config
├── alembic/                    # Migration files
├── scraper/                    # Scrapy project
│   └── documind_scraper/
│       └── spiders/
│           └── docs_spider.py  # Main crawler
├── app/                        # FastAPI application
│   ├── main.py                 # App entrypoint
│   ├── config.py               # Settings
│   ├── database.py             # SQLAlchemy async
│   ├── models/                 # ORM models
│   ├── schemas/                # Pydantic schemas
│   ├── routers/                # API endpoints
│   ├── services/               # Business logic
│   │   ├── chunker.py          # Text chunking
│   │   ├── embedder.py         # OpenAI embeddings
│   │   ├── vector_store.py     # FAISS index
│   │   ├── rag_engine.py       # RAG pipeline
│   │   └── cache.py            # Redis cache
│   └── workers/                # Celery tasks
├── frontend/
│   └── index.html              # Chat UI
├── data/                       # Persistent data
└── tests/                      # Test suite
```

## 🔧 Tech Stack

| Layer | Technology |
|-------|-----------|
| Language | Python 3.11+ |
| Web Scraping | Scrapy 2.11 |
| Embeddings | OpenAI text-embedding-3-small |
| Generation | OpenAI GPT-4o |
| Vector Store | FAISS |
| API Framework | FastAPI |
| Database | PostgreSQL 15 |
| Cache | Redis 7 |
| Task Queue | Celery 5.3 |
| ORM | SQLAlchemy 2.0 (async) |
| Containerization | Docker Compose |

## Author
Atharva N. Futane
