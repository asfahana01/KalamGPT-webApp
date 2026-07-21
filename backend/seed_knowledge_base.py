"""
seed_knowledge_base.py — One-time script to populate the RAG knowledge base

Run this ONCE after setting up the backend, to index Kalam's books/speeches
(the same corpus you collected in Phase 1) into the vector database.

Usage:
    python seed_knowledge_base.py

Reads from: ./knowledge_sources/*.txt
(Copy your kalam_corpus.txt or individual book/speech text files here)
"""

import os
from knowledge.rag_engine import rag_engine

SOURCES_DIR = "./knowledge_sources"


def main():
    os.makedirs(SOURCES_DIR, exist_ok=True)

    txt_files = [f for f in os.listdir(SOURCES_DIR) if f.endswith(".txt")]

    if not txt_files:
        print(f"⚠️  No .txt files found in {SOURCES_DIR}/")
        print(f"   Copy your kalam_corpus.txt (from Phase 1) into this folder and re-run.")
        return

    print(f"Found {len(txt_files)} source file(s) to index...")
    print("-" * 50)

    total_chunks = 0
    for filename in txt_files:
        file_path = os.path.join(SOURCES_DIR, filename)

        # Infer source type from filename (customize as needed)
        source_type = "book"
        if "speech" in filename.lower():
            source_type = "speech"
        elif "interview" in filename.lower():
            source_type = "interview"

        title, chunk_count = rag_engine.index_from_file(file_path, source_type=source_type)
        total_chunks += chunk_count
        print(f"  ✅ {title}: {chunk_count} chunks indexed")

    print("-" * 50)
    print(f"✅ Knowledge base seeding complete!")
    print(f"   Total chunks indexed: {total_chunks}")

    stats = rag_engine.get_stats()
    print(f"   Vector DB stats: {stats}")


if __name__ == "__main__":
    main()
