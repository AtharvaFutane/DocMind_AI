"""Initial schema

Revision ID: 001
Revises:
Create Date: 2024-01-01 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, ARRAY

# revision identifiers, used by Alembic.
revision = '001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # Crawl jobs tracker
    op.create_table(
        "crawl_jobs",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("url", sa.Text, nullable=False),
        sa.Column("status", sa.String(20), default="queued"),
        sa.Column("max_depth", sa.Integer, default=10),
        sa.Column("pages_crawled", sa.Integer, default=0),
        sa.Column("chunks_indexed", sa.Integer, default=0),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("error", sa.Text),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # Individual scraped pages
    op.create_table(
        "pages",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("url", sa.Text, unique=True, nullable=False),
        sa.Column("title", sa.Text),
        sa.Column("clean_text", sa.Text),
        sa.Column("section_headers", JSONB),
        sa.Column("crawl_job_id", sa.Integer, sa.ForeignKey("crawl_jobs.id")),
        sa.Column("depth", sa.Integer, default=0),
        sa.Column("scraped_at", sa.DateTime(timezone=True)),
    )
    op.create_index("idx_pages_crawl_job", "pages", ["crawl_job_id"])
    op.create_index("idx_pages_url", "pages", ["url"])

    # Text chunks (linked to FAISS by chunk_id = FAISS internal index)
    op.create_table(
        "chunks",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("page_id", sa.Integer, sa.ForeignKey("pages.id")),
        sa.Column("chunk_index", sa.Integer),
        sa.Column("text", sa.Text),
        sa.Column("token_estimate", sa.Integer),
        sa.Column("faiss_index", sa.Integer),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("idx_chunks_page", "chunks", ["page_id"])
    op.create_index("idx_chunks_faiss", "chunks", ["faiss_index"])

    # Chat sessions
    op.create_table(
        "chat_sessions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("last_active", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # Chat messages
    op.create_table(
        "chat_messages",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("session_id", sa.String(36), sa.ForeignKey("chat_sessions.id")),
        sa.Column("role", sa.String(10)),
        sa.Column("content", sa.Text),
        sa.Column("sources", JSONB),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("idx_messages_session", "chat_messages", ["session_id"])


def downgrade():
    op.drop_table("chat_messages")
    op.drop_table("chat_sessions")
    op.drop_table("chunks")
    op.drop_table("pages")
    op.drop_table("crawl_jobs")
