"""
Crawl management endpoints.
"""
from typing import List
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.database import get_db
from app.schemas.crawl import CrawlRequest, CrawlResponse, CrawlStatusResponse, CrawlJobListItem
from app.models.crawl import CrawlJob, Page, Chunk
from app.workers.tasks import start_crawl_task

router = APIRouter()


@router.post("/crawl", response_model=CrawlResponse, status_code=202)
async def trigger_crawl(
    request: Request,
    body: CrawlRequest,
    db: AsyncSession = Depends(get_db),
):
    # Clear previous documents/vectors, chat sessions/messages, and response cache to keep only this crawl
    vector_store = request.app.state.vector_store
    vector_store.clear()
    from sqlalchemy import text
    await db.execute(
        text("TRUNCATE TABLE chunks, pages, crawl_jobs, chat_sessions, chat_messages RESTART IDENTITY CASCADE;")
    )
    await db.commit()

    try:
        redis_client = request.app.state.redis
        async for key in redis_client.scan_iter("rag:*"):
            await redis_client.delete(key)
    except Exception as e:
        print(f"Failed to clear Redis response cache on crawl: {e}")

    # Create crawl job record
    job = CrawlJob(
        url=body.url,
        status="queued",
        max_depth=body.max_depth or 10,
    )
    db.add(job)
    await db.commit()
    await db.refresh(job)

    # Dispatch to Celery
    start_crawl_task.delay(
        crawl_job_id=job.id,
        start_url=body.url,
        max_depth=job.max_depth,
        faiss_index_path=str(request.app.state.vector_store.index_path),
    )

    return CrawlResponse(
        crawl_job_id=job.id,
        status="queued",
        message=f"Crawl queued for {body.url}",
    )


@router.post("/clear", status_code=200)
async def clear_workspace(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """
    Clear all uploaded files, crawl jobs, pages, chunks, and the FAISS vector index,
    along with response caches and chat sessions/messages.
    """
    # 1. Clear FAISS index
    vector_store = request.app.state.vector_store
    vector_store.clear()

    # 2. Clear Database Tables
    from sqlalchemy import text
    await db.execute(
        text("TRUNCATE TABLE chunks, pages, crawl_jobs, chat_sessions, chat_messages RESTART IDENTITY CASCADE;")
    )
    await db.commit()

    # 3. Clear Redis Cache
    try:
        redis_client = request.app.state.redis
        async for key in redis_client.scan_iter("rag:*"):
            await redis_client.delete(key)
    except Exception as e:
        print(f"Failed to clear Redis response cache on clear: {e}")

    return {"message": "All data, vector index, and cache cleared successfully."}



@router.get("/crawl/{job_id}", response_model=CrawlStatusResponse)
async def get_crawl_status(job_id: int, db: AsyncSession = Depends(get_db)):
    """Poll crawl job status and progress."""
    job = await db.get(CrawlJob, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Crawl job not found")
    return CrawlStatusResponse(
        crawl_job_id=job.id,
        status=job.status,
        pages_crawled=job.pages_crawled,
        chunks_indexed=job.chunks_indexed,
        started_at=job.started_at,
        completed_at=job.completed_at,
        error=job.error,
    )


@router.get("/crawl", response_model=List[CrawlJobListItem])
async def list_crawl_jobs(db: AsyncSession = Depends(get_db)):
    """List all crawl jobs."""
    result = await db.execute(
        select(CrawlJob).order_by(CrawlJob.created_at.desc())
    )
    jobs = result.scalars().all()
    return [
        CrawlJobListItem(
            id=job.id,
            url=job.url,
            status=job.status,
            pages_crawled=job.pages_crawled,
            chunks_indexed=job.chunks_indexed,
            created_at=job.created_at,
        )
        for job in jobs
    ]


@router.get("/sources")
async def list_sources(db: AsyncSession = Depends(get_db)):
    """List all indexed sources (completed web crawls and uploaded files)."""
    # 1. Fetch completed crawl jobs
    crawl_result = await db.execute(
        select(CrawlJob).where(CrawlJob.status == "completed").order_by(CrawlJob.completed_at.desc())
    )
    crawl_jobs = crawl_result.scalars().all()

    # 2. Fetch uploaded documents (pages with crawl_job_id IS NULL) joined with Chunk count
    stmt = (
        select(Page, func.count(Chunk.id))
        .outerjoin(Chunk, Page.id == Chunk.page_id)
        .where(Page.crawl_job_id == None)
        .group_by(Page.id)
        .order_by(Page.scraped_at.desc())
    )
    uploaded_result = await db.execute(stmt)
    uploaded_data = uploaded_result.all()

    return {
        "crawls": [
            {
                "id": job.id,
                "url": job.url,
                "pages_crawled": job.pages_crawled,
                "chunks_indexed": job.chunks_indexed,
                "created_at": job.created_at.isoformat() if job.created_at else None,
            }
            for job in crawl_jobs
        ],
        "uploads": [
            {
                "id": page.id,
                "filename": page.title,
                "url": page.url,
                "uploaded_at": page.scraped_at.isoformat() if page.scraped_at else None,
                "chunks_indexed": chunk_count,
            }
            for page, chunk_count in uploaded_data
        ]
    }
