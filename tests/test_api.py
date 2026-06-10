"""
API integration tests.
NOTE: These tests require a running PostgreSQL, Redis, and the app to be fully initialized.
For CI, use docker-compose to set up the infrastructure first.
"""
import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app


@pytest.mark.asyncio
async def test_health_check():
    """Test that the health endpoint returns 200 with status info."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert "status" in data
    assert data["status"] == "healthy"


@pytest.mark.asyncio
async def test_chat_requires_question():
    """Test that POST /api/chat requires a question field."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post("/api/chat", json={})
    assert response.status_code == 422    # Unprocessable entity


@pytest.mark.asyncio
async def test_crawl_invalid_url():
    """Test that POST /api/crawl rejects invalid URLs."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post("/api/crawl", json={"url": "not-a-url"})
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_crawl_missing_url():
    """Test that POST /api/crawl requires a URL."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post("/api/crawl", json={})
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_crawl_status_not_found():
    """Test that GET /api/crawl/99999 returns 404."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/crawl/99999")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_session_not_found():
    """Test that GET /api/sessions/nonexistent/messages returns 404."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/sessions/nonexistent-id/messages")
    assert response.status_code == 404
