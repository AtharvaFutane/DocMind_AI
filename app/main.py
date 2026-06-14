"""
DocuMind FastAPI Application — Main Entrypoint.
"""
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
import redis.asyncio as aioredis

from app.config import get_settings
from app.database import init_db, engine
from app.services.vector_store import FAISSVectorStore
from app.services.embedder import EmbeddingService
from app.services.rag_engine import RAGEngine
from app.services.cache import ResponseCache
from app.routers import crawl, chat, health, upload

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown lifecycle."""
    # Startup
    db_url = settings.database_url
    masked_url = db_url
    if "@" in db_url:
        parts = db_url.split("@", 1)
        prefix = parts[0]
        suffix = parts[1]
        if ":" in prefix:
            prefix_parts = prefix.split(":", 2)
            if len(prefix_parts) > 2:
                masked_url = f"{prefix_parts[0]}:{prefix_parts[1]}:***@{suffix}"
            else:
                masked_url = f"{prefix_parts[0]}:***@{suffix}"
        else:
            masked_url = f"{prefix}:***@{suffix}"
    print(f"Startup: Connecting to database at {masked_url}")
    await init_db()

    redis_client = aioredis.from_url(settings.redis_url, decode_responses=True)
    vector_store = FAISSVectorStore(settings.faiss_index_path)
    embedder = EmbeddingService(redis_client)

    # Make document storage ephemeral: Clear FAISS index and PostgreSQL tables on startup
    print("Startup: Initializing fresh session (clearing FAISS index and database tables).")
    vector_store.clear()
    from sqlalchemy import text
    async with engine.begin() as conn:
        await conn.execute(
            text("TRUNCATE TABLE chunks, pages, crawl_jobs, chat_sessions, chat_messages RESTART IDENTITY CASCADE;")
        )

    # Dynamically verify embedding dimension and configure the fresh FAISS index
    try:
        test_emb = await embedder.embed_single("test")
        emb_dim = len(test_emb)
        print(f"Embedding model dimension verified: {emb_dim}")
        vector_store.reset_with_dimension(emb_dim)
    except Exception as e:
        print(f"Failed to verify embedding dimension at startup: {e}")

    cache = ResponseCache(redis_client)
    rag = RAGEngine(embedder, vector_store, cache)

    app.state.redis = redis_client
    app.state.vector_store = vector_store
    app.state.embedder = embedder
    app.state.rag = rag

    yield

    # Shutdown
    await redis_client.close()


app = FastAPI(
    title="DocuMind API",
    description="RAG-powered documentation Q&A bot",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router, tags=["health"])
app.include_router(crawl.router, prefix="/api", tags=["crawl"])
app.include_router(chat.router, prefix="/api", tags=["chat"])
app.include_router(upload.router, prefix="/api", tags=["upload"])

# Serve frontend static files — mount LAST so API routes take priority
app.mount("/", StaticFiles(directory="frontend", html=True), name="frontend")
