import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.crawl import Page, Chunk
from app.services.parser import DocumentParser
from app.services.chunker import TextChunker
from app.services.vector_store import VectorMetadata
from app.config import get_settings

router = APIRouter()
settings = get_settings()


@router.post("/upload", status_code=201)
async def upload_file(
    request: Request,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
):
    """
    Upload a documentation file (PDF, TXT, DOCX, MD),
    parse its text, chunk it, generate embeddings,
    and save it in PostgreSQL and the FAISS vector index.
    """
    filename = file.filename or "uploaded_file"
    ext = filename.split(".")[-1].lower() if "." in filename else ""
    if ext not in ("pdf", "docx", "txt", "md"):
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file format: .{ext}. Only PDF, DOCX, TXT, and MD are supported."
        )

    # Read content
    try:
        content = await file.read()
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Could not read uploaded file: {str(e)}")

    # Extract text
    try:
        extracted_text = DocumentParser.parse(filename, content)
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"Failed to parse text from file: {str(e)}")

    clean_text = extracted_text.strip()
    if len(clean_text) < 10:
        raise HTTPException(
            status_code=422,
            detail="The extracted text from the file is too short (under 10 characters)."
        )

    # Clear previous documents/vectors, chat sessions/messages, and response cache to keep only this upload
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
        print(f"Failed to clear Redis response cache on upload: {e}")

    # Create a unique pseudo-URL for the upload to satisfy page URL uniqueness constraints
    file_id = str(uuid.uuid4())
    pseudo_url = f"upload/{file_id}/{filename}"

    # Create Page ORM record
    page = Page(
        url=pseudo_url,
        title=filename,
        clean_text=clean_text,
        section_headers=[],
        crawl_job_id=None,
        depth=0,
        scraped_at=datetime.now(timezone.utc),
    )
    db.add(page)
    await db.commit()
    await db.refresh(page)

    # Chunk text
    chunker = TextChunker(settings.chunk_size, settings.chunk_overlap)
    chunks = chunker.chunk_text(clean_text, pseudo_url, filename)

    if not chunks:
        return {
            "page_id": page.id,
            "filename": filename,
            "chunks_indexed": 0,
            "message": "File was empty or did not contain indexable text chunks."
        }

    # Embed chunks
    embedder = request.app.state.embedder
    vector_store = request.app.state.vector_store

    texts = [c.text for c in chunks]
    try:
        embeddings = await embedder.embed_batch(texts)
    except Exception as e:
        # Rollback: Clean up the created page if embedding fails
        await db.delete(page)
        await db.commit()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate embeddings via OpenAI: {str(e)}"
        )

    # Save chunks in PostgreSQL
    metadata_list = []
    for i, chunk in enumerate(chunks):
        faiss_idx = vector_store.total_vectors + i
        db_chunk = Chunk(
            page_id=page.id,
            chunk_index=chunk.chunk_index,
            text=chunk.text,
            token_estimate=chunk.token_estimate,
            faiss_index=faiss_idx,
        )
        db.add(db_chunk)
        # Flush to get DB-generated ID without committing yet
        await db.flush()

        metadata_list.append(
            VectorMetadata(
                chunk_id=db_chunk.id,
                page_url=chunk.page_url,
                page_title=chunk.page_title,
                chunk_text=chunk.text,
                chunk_index=chunk.chunk_index,
            )
        )

    # Commit chunks to database
    await db.commit()

    # Add vectors to FAISS index
    try:
        vector_store.add_vectors(embeddings, metadata_list)
    except ValueError as e:
        # Truncate tables to keep sync since index was reset
        from sqlalchemy import text
        await db.execute(
            text("TRUNCATE TABLE chunks, pages, crawl_jobs, chat_sessions, chat_messages RESTART IDENTITY CASCADE;")
        )
        await db.commit()
        raise HTTPException(
            status_code=409,
            detail=f"Vector database dimension mismatch detected. Database and index have been reset. Please upload your file again. Error: {str(e)}"
        )
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"Extracted database records, but failed to index in FAISS vector store: {str(e)}"
        )

    return {
        "page_id": page.id,
        "filename": filename,
        "chunks_indexed": len(chunks),
        "message": f"Successfully parsed and indexed {len(chunks)} text chunks."
    }
