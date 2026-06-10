import pytest
import io
from httpx import AsyncClient, ASGITransport
from unittest.mock import patch, AsyncMock
from app.main import app


@pytest.mark.asyncio
async def test_upload_invalid_extension():
    """Test that uploading a file with an unsupported extension returns 400."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        files = {"file": ("test.png", b"fake image content", "image/png")}
        response = await client.post("/api/upload", files=files)

    assert response.status_code == 400
    assert "Unsupported file format" in response.json()["detail"]


@pytest.mark.asyncio
async def test_upload_too_short():
    """Test that uploading a file with very short text returns 422."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        files = {"file": ("test.txt", b"too short", "text/plain")}
        response = await client.post("/api/upload", files=files)

    assert response.status_code == 422
    assert "extracted text from the file is too short" in response.json()["detail"]


@pytest.mark.asyncio
@patch("app.services.embedder.EmbeddingService.embed_batch")
async def test_upload_txt_success(mock_embed_batch):
    """Test successful text file upload and indexing with mocked embedding call."""
    mock_embed_batch.return_value = [[0.1] * 1536]

    with patch("app.services.vector_store.FAISSVectorStore.add_vectors") as mock_add_vectors:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            file_content = (
                b"This is a longer mock document text. It contains enough words to satisfy the "
                b"length check and trigger chunking. " * 5
            )
            files = {"file": ("document.txt", file_content, "text/plain")}
            response = await client.post("/api/upload", files=files)

        assert response.status_code == 201
        data = response.json()
        assert "page_id" in data
        assert data["filename"] == "document.txt"
        assert data["chunks_indexed"] > 0
        assert "Successfully parsed and indexed" in data["message"]
