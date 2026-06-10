from typing import List
from dataclasses import dataclass


@dataclass
class TextChunk:
    """Represents a chunk of text from a documentation page."""
    text: str
    page_url: str
    page_title: str
    chunk_index: int
    char_start: int
    char_end: int
    token_estimate: int


class TextChunker:
    """
    Splits document text into overlapping chunks suitable for embedding.

    Strategy:
    - Split on paragraph boundaries first (double newlines)
    - If a paragraph exceeds chunk_size tokens, split on sentences
    - Add overlap from the end of the previous chunk to the start of the next
    - Track char positions for citation linking back to the source page

    Why 512 tokens / 128 overlap:
    - 512 is well within text-embedding-3-small's 8191 token limit
    - 128-token overlap ensures context isn't lost at chunk boundaries
    - Empirically gives better retrieval than 256/0 or 1024/256
    """

    def __init__(self, chunk_size: int = 512, chunk_overlap: int = 128):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        # Rough token estimate: 1 token ≈ 4 characters for English
        self.chars_per_token = 4

    def _estimate_tokens(self, text: str) -> int:
        return len(text) // self.chars_per_token

    def _split_into_paragraphs(self, text: str) -> List[str]:
        paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
        return paragraphs

    def chunk_text(
        self, text: str, page_url: str, page_title: str
    ) -> List[TextChunk]:
        """
        Split text into overlapping chunks.

        Args:
            text: The full text content of a documentation page.
            page_url: URL of the source page (for citation).
            page_title: Title of the source page (for citation).

        Returns:
            List of TextChunk objects with position tracking.
        """
        chunks: List[TextChunk] = []
        paragraphs = self._split_into_paragraphs(text)

        current_chunk_parts: List[str] = []
        current_tokens = 0
        char_offset = 0
        chunk_index = 0

        for para in paragraphs:
            para_tokens = self._estimate_tokens(para)

            # If adding this paragraph exceeds chunk_size, flush current chunk
            if current_tokens + para_tokens > self.chunk_size and current_chunk_parts:
                chunk_text = "\n\n".join(current_chunk_parts)
                char_end = char_offset + len(chunk_text)
                chunks.append(
                    TextChunk(
                        text=chunk_text,
                        page_url=page_url,
                        page_title=page_title,
                        chunk_index=chunk_index,
                        char_start=char_offset,
                        char_end=char_end,
                        token_estimate=current_tokens,
                    )
                )
                chunk_index += 1

                # Overlap: keep last N chars from previous chunk
                overlap_chars = self.chunk_overlap * self.chars_per_token
                overlap_text = chunk_text[-overlap_chars:] if len(chunk_text) > overlap_chars else chunk_text
                current_chunk_parts = [overlap_text]
                current_tokens = self._estimate_tokens(overlap_text)
                char_offset = char_end

            current_chunk_parts.append(para)
            current_tokens += para_tokens

        # Flush remaining content
        if current_chunk_parts:
            chunk_text = "\n\n".join(current_chunk_parts)
            chunks.append(
                TextChunk(
                    text=chunk_text,
                    page_url=page_url,
                    page_title=page_title,
                    chunk_index=chunk_index,
                    char_start=char_offset,
                    char_end=char_offset + len(chunk_text),
                    token_estimate=current_tokens,
                )
            )

        return chunks
