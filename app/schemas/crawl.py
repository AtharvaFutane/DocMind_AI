"""
Pydantic request/response schemas for crawl endpoints.
"""
from typing import Optional
from datetime import datetime
from pydantic import BaseModel, field_validator


class CrawlRequest(BaseModel):
    """Request body for POST /api/crawl."""
    url: str
    max_depth: Optional[int] = 10

    @field_validator("url")
    @classmethod
    def validate_url(cls, v: str) -> str:
        """Validate that the URL is a proper HTTP(S) URL."""
        if not v.startswith(("http://", "https://")):
            raise ValueError("URL must start with http:// or https://")
        return v


class CrawlResponse(BaseModel):
    """Response for POST /api/crawl."""
    crawl_job_id: int
    status: str
    message: str


class CrawlStatusResponse(BaseModel):
    """Response for GET /api/crawl/{job_id}."""
    crawl_job_id: int
    status: str
    pages_crawled: int = 0
    chunks_indexed: int = 0
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error: Optional[str] = None


class CrawlJobListItem(BaseModel):
    """A single crawl job in a list response."""
    id: int
    url: str
    status: str
    pages_crawled: int = 0
    chunks_indexed: int = 0
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True
