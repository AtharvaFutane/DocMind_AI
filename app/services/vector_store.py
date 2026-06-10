import json
import numpy as np
import faiss
from pathlib import Path
from typing import List, Tuple
from dataclasses import dataclass, asdict


@dataclass
class VectorMetadata:
    """Metadata associated with each vector in the FAISS index."""
    chunk_id: int
    page_url: str
    page_title: str
    chunk_text: str
    chunk_index: int


class FAISSVectorStore:
    """
    Manages a FAISS index with accompanying metadata store.

    FAISS stores float32 vectors and enables fast cosine-similarity search.
    Metadata (URLs, titles, text) is stored separately as JSON since FAISS
    only stores vectors and integer IDs.

    Index type: IndexFlatIP (Inner Product) — equivalent to cosine similarity
    when vectors are L2-normalized (which OpenAI embeddings are).
    """

    DEFAULT_EMBEDDING_DIM = 3072

    def __init__(self, index_path: str):
        self.index_path = Path(index_path)
        self.index_path.mkdir(parents=True, exist_ok=True)
        self.faiss_file = self.index_path / "index.faiss"
        self.metadata_file = self.index_path / "metadata.json"

        self.index: faiss.IndexFlatIP = None
        self.metadata: List[VectorMetadata] = []
        self.was_reset = False
        self._load_or_create()

    def _load_or_create(self):
        """Load existing index from disk or create a new one."""
        if self.faiss_file.exists() and self.metadata_file.exists():
            try:
                self.index = faiss.read_index(str(self.faiss_file))
                with open(self.metadata_file, "r") as f:
                    raw = json.load(f)
                    self.metadata = [VectorMetadata(**item) for item in raw]
            except Exception as e:
                print(f"Error loading FAISS index: {e}. Recreating index.")
                self.index = faiss.IndexFlatIP(self.DEFAULT_EMBEDDING_DIM)
                self.metadata = []
                self.was_reset = True
                self.save()
        else:
            self.index = faiss.IndexFlatIP(self.DEFAULT_EMBEDDING_DIM)
            self.metadata = []

    def reset_with_dimension(self, dim: int):
        """Reset the index and metadata with a specific dimension."""
        self.index = faiss.IndexFlatIP(dim)
        self.metadata = []
        self.was_reset = True
        self.save()

    def save(self):
        """Persist index and metadata to disk."""
        self.index_path.mkdir(parents=True, exist_ok=True)
        faiss.write_index(self.index, str(self.faiss_file))
        with open(self.metadata_file, "w") as f:
            json.dump([asdict(m) for m in self.metadata], f)

    def add_vectors(
        self,
        embeddings: List[List[float]],
        metadata_list: List[VectorMetadata],
    ):
        """Add vectors to FAISS index with their metadata."""
        if not embeddings:
            return

        vectors = np.array(embeddings, dtype=np.float32)
        dim = vectors.shape[1]

        # L2 normalize for cosine similarity via inner product
        faiss.normalize_L2(vectors)

        if self.index is None:
            self.index = faiss.IndexFlatIP(dim)
        elif self.index.d != dim:
            print(f"FAISS index dimension mismatch: index has {self.index.d}, but incoming vectors have {dim}. Resetting index.")
            self.reset_with_dimension(dim)
            raise ValueError(f"Dimension mismatch: index had {self.index.d}, but incoming vectors have {dim}. The index has been reset.")

        self.index.add(vectors)
        self.metadata.extend(metadata_list)
        self.save()

    def search(
        self, query_embedding: List[float], top_k: int = 5
    ) -> List[Tuple[VectorMetadata, float]]:
        """
        Search for most similar chunks to a query embedding.
        Returns list of (metadata, similarity_score) tuples.
        """
        if self.index is None or self.index.ntotal == 0:
            return []

        query_vector = np.array([query_embedding], dtype=np.float32)
        faiss.normalize_L2(query_vector)

        scores, indices = self.index.search(query_vector, top_k)

        results = []
        for score, idx in zip(scores[0], indices[0]):
            if idx == -1:   # FAISS returns -1 for empty slots
                continue
            if idx < len(self.metadata):
                results.append((self.metadata[idx], float(score)))

        return results

    def clear(self):
        """Clear the entire index and metadata."""
        dim = self.index.d if self.index is not None else self.DEFAULT_EMBEDDING_DIM
        self.index = faiss.IndexFlatIP(dim)
        self.metadata = []
        self.save()

    @property
    def total_vectors(self) -> int:
        """Total number of vectors in the index."""
        return self.index.ntotal
