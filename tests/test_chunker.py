"""
Unit tests for the TextChunker service.
These tests run without any external services (no DB, no Redis, no OpenAI).
"""
import pytest
from app.services.chunker import TextChunker


class TestTextChunker:
    """Tests for TextChunker."""

    def test_basic_chunking(self):
        """Test that basic text is chunked correctly."""
        chunker = TextChunker(chunk_size=100, chunk_overlap=20)
        text = "First paragraph.\n\nSecond paragraph.\n\nThird paragraph."
        chunks = chunker.chunk_text(text, "http://example.com", "Test Page")
        assert len(chunks) >= 1
        for chunk in chunks:
            assert chunk.page_url == "http://example.com"
            assert chunk.page_title == "Test Page"
            assert len(chunk.text) > 0

    def test_chunk_metadata(self):
        """Test that chunk metadata is populated correctly."""
        chunker = TextChunker(chunk_size=100, chunk_overlap=20)
        text = "Hello world paragraph."
        chunks = chunker.chunk_text(text, "http://example.com/docs", "Docs Page")
        assert len(chunks) == 1
        chunk = chunks[0]
        assert chunk.page_url == "http://example.com/docs"
        assert chunk.page_title == "Docs Page"
        assert chunk.chunk_index == 0
        assert chunk.char_start == 0
        assert chunk.char_end > 0
        assert chunk.token_estimate >= 0

    def test_overlap_exists(self):
        """Test that overlapping content exists between consecutive chunks."""
        chunker = TextChunker(chunk_size=50, chunk_overlap=20)
        long_text = "\n\n".join(
            [f"Paragraph {i} with enough words to be useful and take up space." for i in range(20)]
        )
        chunks = chunker.chunk_text(long_text, "http://example.com", "Long Page")
        assert len(chunks) > 1
        # Check overlap: end of chunk N should appear in start of chunk N+1
        if len(chunks) > 1:
            end_of_first = chunks[0].text[-100:]
            start_of_second = chunks[1].text[:200]
            # They should share some content
            assert len(set(end_of_first.split()) & set(start_of_second.split())) > 0

    def test_empty_text(self):
        """Test that empty text returns no chunks."""
        chunker = TextChunker(chunk_size=100, chunk_overlap=20)
        chunks = chunker.chunk_text("", "http://example.com", "Empty")
        assert len(chunks) == 0

    def test_whitespace_only_text(self):
        """Test that whitespace-only text returns no chunks."""
        chunker = TextChunker(chunk_size=100, chunk_overlap=20)
        chunks = chunker.chunk_text("   \n\n   \n   ", "http://example.com", "Whitespace")
        assert len(chunks) == 0

    def test_single_paragraph(self):
        """Test that a single paragraph produces one chunk."""
        chunker = TextChunker(chunk_size=1000, chunk_overlap=100)
        text = "This is a single paragraph with no double newlines."
        chunks = chunker.chunk_text(text, "http://example.com", "Single")
        assert len(chunks) == 1
        assert chunks[0].text == text

    def test_chunk_indices_are_sequential(self):
        """Test that chunk indices are numbered sequentially from 0."""
        chunker = TextChunker(chunk_size=30, chunk_overlap=5)
        long_text = "\n\n".join([f"Paragraph number {i} with some content." for i in range(15)])
        chunks = chunker.chunk_text(long_text, "http://example.com", "Test")
        for i, chunk in enumerate(chunks):
            assert chunk.chunk_index == i

    def test_token_estimation(self):
        """Test the rough token estimation (1 token ≈ 4 chars)."""
        chunker = TextChunker()
        assert chunker._estimate_tokens("1234") == 1
        assert chunker._estimate_tokens("12345678") == 2
        assert chunker._estimate_tokens("") == 0

    def test_custom_chunk_size(self):
        """Test chunking with custom size/overlap parameters."""
        chunker = TextChunker(chunk_size=256, chunk_overlap=64)
        assert chunker.chunk_size == 256
        assert chunker.chunk_overlap == 64

    def test_paragraph_sentence_splitting(self):
        """Test that a single long paragraph exceeding chunk_size is split on sentences."""
        chunker = TextChunker(chunk_size=10, chunk_overlap=2)
        # This paragraph is around 25 tokens (100 chars), which exceeds chunk_size of 10.
        long_paragraph = "Sentence one is here. Sentence two is longer. Sentence three is also here."
        chunks = chunker.chunk_text(long_paragraph, "http://example.com", "Long Paragraph")
        assert len(chunks) > 1
        for chunk in chunks:
            assert chunk.token_estimate <= 10

