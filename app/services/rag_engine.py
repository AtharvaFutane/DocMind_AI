from typing import List, Dict, Any, Optional
import openai
from app.config import get_settings
from app.services.embedder import EmbeddingService
from app.services.vector_store import FAISSVectorStore, VectorMetadata
from app.services.cache import ResponseCache

settings = get_settings()


SYSTEM_PROMPT = """You are DocuMind, a friendly and highly knowledgeable technical documentation assistant.
You answer developer questions using the provided documentation context below.

Rules:
1. Answer based strictly on the provided context. If the context doesn't contain the answer, say: "I couldn't find this in the documentation. Try searching the docs directly."
2. Cite your sources using only the readable document title/filename (e.g. "according to test_doc.txt") in your response text.
3. Do NOT print raw URL paths or upload paths (like "upload/abc-123/...") in your response text.
4. Do NOT include a "Sources" section or footer at the end of your text response (the frontend displays clean citation badges below the message bubble automatically).
5. Provide a warm, conversational, yet highly professional and accurate response.
6. Structure your response beautifully using Markdown. Use clear headings, bullet points, bold key terms, and lists.
7. Use code snippets from the context when available.

Context format: Each chunk is labeled with [Source N: Title | URL]
"""


class RAGEngine:
    """
    Orchestrates the full RAG pipeline:
    1. Embed the user's question
    2. Retrieve top-k similar chunks from FAISS
    3. Build a prompt with retrieved context
    4. Call GPT-4o to generate a cited answer
    5. Cache the result in Redis

    This is the core AI component of the project.
    """

    def __init__(
        self,
        embedder: EmbeddingService,
        vector_store: FAISSVectorStore,
        cache: ResponseCache,
    ):
        self.embedder = embedder
        self.vector_store = vector_store
        self.cache = cache
        self.llm_client = openai.AsyncOpenAI(
            api_key=settings.api_key,
            base_url=settings.api_base_url,
        )

    def _build_context_block(
        self, retrieved: List[tuple[VectorMetadata, float]]
    ) -> str:
        """Format retrieved chunks into the context block for the prompt."""
        context_parts = []
        for i, (meta, score) in enumerate(retrieved):
            context_parts.append(
                f"[Source {i+1}: {meta.page_title} | {meta.page_url}]\n"
                f"{meta.chunk_text}\n"
                f"(Relevance score: {score:.3f})"
            )
        return "\n\n---\n\n".join(context_parts)

    def _build_user_prompt(self, question: str, context: str) -> str:
        return f"""Documentation Context:
{context}

---

Developer Question: {question}

Please answer this question using only the documentation context above."""

    async def answer(
        self,
        question: str,
        conversation_history: Optional[List[Dict[str, str]]] = None,
    ) -> Dict[str, Any]:
        """
        Full RAG pipeline for a question.

        Returns:
            {
                "answer": str,          # Markdown formatted answer
                "sources": [            # Cited sources
                    {"title": str, "url": str, "score": float}
                ],
                "from_cache": bool,
                "chunks_retrieved": int
            }
        """
        # Check response cache first
        cache_key = f"rag:{question}"
        cached = await self.cache.get(cache_key)
        if cached:
            cached["from_cache"] = True
            return cached

        # Step 1: Embed the question
        question_embedding = await self.embedder.embed_single(question)

        # Step 2: Retrieve top-k chunks
        retrieved = self.vector_store.search(
            query_embedding=question_embedding,
            top_k=settings.top_k_results,
        )

        if not retrieved:
            return {
                "answer": "The documentation hasn't been indexed yet. Please trigger a crawl first.",
                "sources": [],
                "from_cache": False,
                "chunks_retrieved": 0,
            }

        # Step 3: Build prompt
        context_block = self._build_context_block(retrieved)
        user_prompt = self._build_user_prompt(question, context_block)

        # Step 4: Build message history (for multi-turn conversations)
        messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        if conversation_history:
            messages.extend(conversation_history[-6:])  # Last 3 turns for context
        messages.append({"role": "user", "content": user_prompt})

        # Step 5: Call GPT-4o
        response = await self.llm_client.chat.completions.create(
            model=settings.api_chat_model,
            messages=messages,
            max_tokens=settings.api_max_tokens,
            temperature=0.1,        # Low temp for factual, consistent answers
        )

        answer_text = response.choices[0].message.content

        # Step 6: Extract sources
        sources = [
            {
                "title": meta.page_title,
                "url": meta.page_url,
                "score": round(score, 4),
            }
            for meta, score in retrieved
        ]

        result = {
            "answer": answer_text,
            "sources": sources,
            "from_cache": False,
            "chunks_retrieved": len(retrieved),
        }

        # Cache for 1 hour
        await self.cache.set(cache_key, result, ttl=3600)
        return result
