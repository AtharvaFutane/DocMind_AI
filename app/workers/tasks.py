"""
Celery task definitions for background processing.
"""
import subprocess
import asyncio
from datetime import datetime, timezone
from celery import shared_task
from celery.utils.log import get_task_logger
import psycopg2
from app.config import get_settings

logger = get_task_logger(__name__)
settings = get_settings()


@shared_task(bind=True, max_retries=3)
def start_crawl_task(
    self,
    crawl_job_id: int,
    start_url: str,
    max_depth: int,
    faiss_index_path: str,
):
    """
    Background task that:
    1. Runs Scrapy spider for the given URL
    2. Chunks the scraped pages
    3. Embeds chunks and adds to FAISS
    4. Updates crawl_job status in PostgreSQL
    """
    db_url = settings.sync_database_url
    conn = psycopg2.connect(db_url)
    cursor = conn.cursor()

    try:
        # Update job to running
        cursor.execute(
            "UPDATE crawl_jobs SET status='running', started_at=%s WHERE id=%s",
            (datetime.now(timezone.utc), crawl_job_id),
        )
        conn.commit()

        # Step 1: Run Scrapy spider as subprocess
        logger.info(f"Starting Scrapy crawl for {start_url}")
        result = subprocess.run(
            [
                "scrapy", "crawl", "docs_spider",
                "-a", f"start_url={start_url}",
                "-a", f"crawl_job_id={crawl_job_id}",
                "-s", f"DEPTH_LIMIT={max_depth}",
                "-s", f"DATABASE_URL={db_url}",
            ],
            cwd="scraper",
            capture_output=True,
            text=True,
            timeout=3600,    # 1 hour max
        )

        if result.returncode != 0:
            raise RuntimeError(f"Scrapy failed: {result.stderr}")

        # Step 2: Get crawled pages from DB
        cursor.execute(
            "SELECT id, url, title, clean_text FROM pages WHERE crawl_job_id=%s",
            (crawl_job_id,),
        )
        pages = cursor.fetchall()
        logger.info(f"Crawled {len(pages)} pages")

        # Step 3: Chunk and embed (run async code from sync context)
        asyncio.run(
            _chunk_and_embed_pages(pages, crawl_job_id, faiss_index_path, cursor, conn)
        )

        # Update job to completed
        cursor.execute(
            """UPDATE crawl_jobs
               SET status='completed', completed_at=%s, pages_crawled=%s
               WHERE id=%s""",
            (datetime.now(timezone.utc), len(pages), crawl_job_id),
        )
        conn.commit()
        logger.info(f"Crawl job {crawl_job_id} completed successfully")

    except Exception as exc:
        cursor.execute(
            "UPDATE crawl_jobs SET status='failed', error=%s WHERE id=%s",
            (str(exc), crawl_job_id),
        )
        conn.commit()
        logger.error(f"Crawl job {crawl_job_id} failed: {exc}")
        raise self.retry(exc=exc, countdown=60)
    finally:
        cursor.close()
        conn.close()


async def _chunk_and_embed_pages(pages, crawl_job_id, faiss_index_path, cursor, conn):
    """Chunk pages, generate embeddings, store in FAISS + PostgreSQL."""
    import redis.asyncio as aioredis
    from app.services.chunker import TextChunker
    from app.services.embedder import EmbeddingService
    from app.services.vector_store import FAISSVectorStore, VectorMetadata

    redis_client = aioredis.from_url(settings.redis_url, decode_responses=True)
    chunker = TextChunker(settings.chunk_size, settings.chunk_overlap)
    embedder = EmbeddingService(redis_client)
    vector_store = FAISSVectorStore(faiss_index_path)

    all_chunks = []
    all_page_ids = []

    for page_id, url, title, text in pages:
        if not text:
            continue
        chunks = chunker.chunk_text(text, url, title)
        for chunk in chunks:
            all_chunks.append(chunk)
            all_page_ids.append(page_id)

    if not all_chunks:
        await redis_client.close()
        return

    # Batch embed all chunks
    texts = [c.text for c in all_chunks]
    embeddings = await embedder.embed_batch(texts)

    # Add to FAISS and save metadata to PostgreSQL
    metadata_list = []
    for i, (chunk, page_id) in enumerate(zip(all_chunks, all_page_ids)):
        faiss_idx = vector_store.total_vectors + i
        cursor.execute(
            """INSERT INTO chunks (page_id, chunk_index, text, token_estimate, faiss_index)
               VALUES (%s, %s, %s, %s, %s) RETURNING id""",
            (page_id, chunk.chunk_index, chunk.text, chunk.token_estimate, faiss_idx),
        )
        row = cursor.fetchone()
        metadata_list.append(
            VectorMetadata(
                chunk_id=row[0],
                page_url=chunk.page_url,
                page_title=chunk.page_title,
                chunk_text=chunk.text,
                chunk_index=chunk.chunk_index,
            )
        )

    conn.commit()
    try:
        vector_store.add_vectors(embeddings, metadata_list)
    except ValueError as e:
        logger.warning(f"Dimension mismatch in Celery task: {e}. Truncating database tables to keep sync.")
        cursor.execute("TRUNCATE TABLE chunks, pages, crawl_jobs RESTART IDENTITY CASCADE;")
        conn.commit()
        raise RuntimeError(f"FAISS index and SQL database were reset due to dimension mismatch: {e}")

    # Update chunks_indexed count on job
    cursor.execute(
        "UPDATE crawl_jobs SET chunks_indexed=%s WHERE id=%s",
        (len(all_chunks), crawl_job_id),
    )
    conn.commit()
    await redis_client.close()


@shared_task
def recrawl_all_jobs():
    """Weekly task to re-crawl all completed crawl jobs."""
    db_url = settings.sync_database_url
    conn = psycopg2.connect(db_url)
    cursor = conn.cursor()
    cursor.execute("SELECT id, url, max_depth FROM crawl_jobs WHERE status='completed'")
    jobs = cursor.fetchall()
    cursor.close()
    conn.close()

    for job_id, url, max_depth in jobs:
        start_crawl_task.delay(
            crawl_job_id=job_id,
            start_url=url,
            max_depth=max_depth,
            faiss_index_path=settings.faiss_index_path,
        )
