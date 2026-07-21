"""
knowledge/rag_engine.py — 1.4 Knowledge Repository + 1.5 RAG Layer

Retrieval-Augmented Generation: retrieves relevant passages from Kalam's
actual books/speeches using semantic similarity search, then injects
them as context for the language model to ground its response in real text.

Uses ChromaDB (lightweight, file-based vector database — no server needed)
with sentence-transformers for embeddings.
"""

import os
import chromadb
from chromadb.utils import embedding_functions
import re


class RAGEngine:
    """
    Manages the vector knowledge base and semantic retrieval.
    """

    def __init__(self, persist_directory: str = "./knowledge/vector_db"):
        self.persist_directory = persist_directory
        os.makedirs(persist_directory, exist_ok=True)

        # ChromaDB client — persists to disk, no external server needed
        self.client = chromadb.EphemeralClient()

        # Lightweight embedding model — runs on CPU, ~80MB
        self.embedding_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name="all-MiniLM-L6-v2"
        )

        self.collection = self.client.get_or_create_collection(
            name="kalam_knowledge",
            embedding_function=self.embedding_fn,
            metadata={"description": "Dr. A.P.J. Abdul Kalam's books, speeches, and writings"},
        )

    # ── Indexing (Knowledge Repository construction) ─────────────────────────

    def chunk_text(self, text: str, chunk_size: int = 300, overlap: int = 50) -> list[str]:
        """
        Split raw text into overlapping chunks for embedding.
        Overlap preserves context across chunk boundaries.
        """
        words = text.split()
        chunks = []
        step = chunk_size - overlap

        for i in range(0, len(words), step):
            chunk = " ".join(words[i:i + chunk_size])
            if len(chunk.split()) > 20:  # skip tiny trailing chunks
                chunks.append(chunk)

        return chunks

    def index_document(self, text: str, source_title: str, source_type: str = "book"):
        """
        Chunk and embed a document into the vector database.
        Called during initial setup and whenever new source material is added.
        """
        chunks = self.chunk_text(text)

        if not chunks:
            return 0

        ids = [f"{source_title}_{i}" for i in range(len(chunks))]
        metadatas = [
            {"source": source_title, "type": source_type, "chunk_index": i}
            for i in range(len(chunks))
        ]

        self.collection.upsert(
            documents=chunks,
            ids=ids,
            metadatas=metadatas,
        )

        return len(chunks)

    def index_from_file(self, file_path: str, source_type: str = "book"):
        """Index a plain text file into the knowledge base."""
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            text = f.read()

        title = os.path.splitext(os.path.basename(file_path))[0]
        count = self.index_document(text, title, source_type)
        return title, count

    # ── Retrieval (RAG query time) ────────────────────────────────────────────

    def retrieve_context(self, query: str, top_k: int = 3) -> list[dict]:
        """
        Semantic search: retrieve the top-k most relevant chunks for a query.
        Returns list of {text, source, score} dicts.
        """
        if self.collection.count() == 0:
            return []

        results = self.collection.query(
            query_texts=[query],
            n_results=min(top_k, self.collection.count()),
        )

        retrieved = []
        if results["documents"] and results["documents"][0]:
            for doc, meta, dist in zip(
                results["documents"][0],
                results["metadatas"][0],
                results["distances"][0],
            ):
                retrieved.append({
                    "text": doc,
                    "source": meta.get("source", "unknown"),
                    "relevance_score": round(1 - dist, 3),  # convert distance to similarity
                })

        return retrieved

    def build_augmented_prompt(self, user_query: str, top_k: int = 3) -> tuple[str, list[dict]]:
        """
        Build a RAG-augmented prompt: retrieves relevant Kalam text and
        prepends it as grounding context for the language model.

        Returns (augmented_context_string, raw_retrieved_chunks)
        """
        chunks = self.retrieve_context(user_query, top_k=top_k)

        if not chunks:
            return "", []

        context_parts = [
            f"[From {c['source']}]: {c['text']}" for c in chunks
        ]
        context_str = "\n\n".join(context_parts)

        return context_str, chunks

    def get_stats(self) -> dict:
        """Return knowledge base statistics for admin/report purposes."""
        return {
            "total_chunks": self.collection.count(),
            "collection_name": self.collection.name,
        }


# Singleton instance — initialized once at app startup
rag_engine = RAGEngine()
