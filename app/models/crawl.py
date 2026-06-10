"""
ORM models for crawl-related tables: crawl_jobs, pages, chunks.
"""
from datetime import datetime
from typing import Optional, List
from sqlalchemy import Integer, String, Text, DateTime, ForeignKey, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base


class CrawlJob(Base):
    """Tracks a crawl job and its status."""
    __tablename__ = "crawl_jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    url: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="queued")
    max_depth: Mapped[int] = mapped_column(Integer, default=10)
    pages_crawled: Mapped[int] = mapped_column(Integer, default=0)
    chunks_indexed: Mapped[int] = mapped_column(Integer, default=0)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Relationships
    pages: Mapped[List["Page"]] = relationship("Page", back_populates="crawl_job")


class Page(Base):
    """A single scraped documentation page."""
    __tablename__ = "pages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    url: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    title: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    clean_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    section_headers: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    crawl_job_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("crawl_jobs.id"), nullable=True
    )
    depth: Mapped[int] = mapped_column(Integer, default=0)
    scraped_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Relationships
    crawl_job: Mapped[Optional["CrawlJob"]] = relationship("CrawlJob", back_populates="pages")
    chunks: Mapped[List["Chunk"]] = relationship("Chunk", back_populates="page")


class Chunk(Base):
    """A text chunk from a documentation page, linked to FAISS index."""
    __tablename__ = "chunks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    page_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("pages.id"), nullable=True
    )
    chunk_index: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    token_estimate: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    faiss_index: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Relationships
    page: Mapped[Optional["Page"]] = relationship("Page", back_populates="chunks")
