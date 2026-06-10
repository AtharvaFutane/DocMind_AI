"""
Health check endpoint.
"""
from fastapi import APIRouter, Request

router = APIRouter()


@router.get("/health")
async def health_check(request: Request):
    """
    Health check endpoint.
    Returns service status and vector store statistics.
    """
    vector_store = request.app.state.vector_store

    return {
        "status": "healthy",
        "service": "DocuMind API",
        "version": "1.0.0",
        "vector_store": {
            "total_vectors": vector_store.total_vectors,
            "index_path": str(vector_store.index_path),
        },
    }
