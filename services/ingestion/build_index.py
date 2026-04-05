"""
Build an enriched Chroma index with formatter-derived metadata.

Default output is a *parallel* store (does not overwrite `data/vector_db_mini`):
  - Path: `data/vector_db_mini_enriched`
  - Collection: `clinical_rag_mini_enriched`

Override with env:
  UPHEAL_BUILD_CHROMA_PATH
  UPHEAL_BUILD_CHROMA_COLLECTION

Run from repo root with PYTHONPATH set:
  set PYTHONPATH=.
  python -m services.ingestion.build_index
"""
from __future__ import annotations

import json
import os
from collections import Counter
from pathlib import Path

from services.ingestion.formatter_agent import (
    default_format_chunk_metadata,
    difficulty_to_int,
    format_chunk_metadata,
)
from services.shared.pathing import repo_root


TARGET_BOOKS = [
    "Mind Over Mood PDF",
    "Cognitive Behavior Therapy - Basics and Beyond 2nd Edition",
    "Managing_Obsessions",
    "CHANGE THE WAY YOU FEEL BY",
]

BATCH_SIZE = 100


def main() -> None:
    root = repo_root()
    chunks_path = root / "data" / "rag_chunks" / "semantic_chunks.json"
    out_path = Path(
        os.environ.get(
            "UPHEAL_BUILD_CHROMA_PATH",
            str(root / "data" / "vector_db_mini_enriched"),
        )
    )
    collection_name = os.environ.get(
        "UPHEAL_BUILD_CHROMA_COLLECTION", "clinical_rag_mini_enriched"
    )
    model_name = "all-mpnet-base-v2"

    if not chunks_path.is_file():
        raise SystemExit(f"Chunks file not found: {chunks_path}")

    print(f"Loading chunks from {chunks_path}...")
    with open(chunks_path, "r", encoding="utf-8") as f:
        all_chunks = json.load(f)

    chunks_data = [c for c in all_chunks if c.get("source_file") in TARGET_BOOKS]
    print(f"Filtered to {len(chunks_data):,} chunks for TARGET_BOOKS")

    from sentence_transformers import SentenceTransformer
    import chromadb

    model = SentenceTransformer(model_name)
    out_path.mkdir(parents=True, exist_ok=True)
    client = chromadb.PersistentClient(path=str(out_path))

    try:
        client.delete_collection(name=collection_name)
        print(f"Deleted existing collection: {collection_name}")
    except Exception:
        pass

    collection = client.create_collection(
        name=collection_name,
        metadata={"description": "Enriched mini RAG with formatter metadata"},
    )

    total = len(chunks_data)
    num_batches = (total + BATCH_SIZE - 1) // BATCH_SIZE

    for batch_idx in range(num_batches):
        start = batch_idx * BATCH_SIZE
        end = min(start + BATCH_SIZE, total)
        batch = chunks_data[start:end]
        documents = [c["text"] for c in batch]
        ids = [c["chunk_id"] for c in batch]
        metadatas = []
        for chunk in batch:
            fmt = format_chunk_metadata(chunk["text"], default_format_chunk_metadata)
            tags = fmt.get("clinical_tags") or ["general"]
            if not isinstance(tags, list):
                tags = ["general"]
            tags = [str(t).strip() for t in tags if str(t).strip()]
            if not tags:
                tags = ["general"]
            tag_primary = tags[0]
            diff_int = difficulty_to_int(fmt.get("difficulty", "medium"))
            xp = int(fmt.get("xp_reward", 0) or 0)

            header = chunk["header_hierarchy"][0] if chunk.get("header_hierarchy") else ""
            metadatas.append(
                {
                    "source_file": chunk["source_file"],
                    "char_count": int(chunk["char_count"]),
                    "page_numbers": str(chunk["page_numbers"]),
                    "header": header,
                    "clinical_tags": ",".join(tags),
                    "tag_primary": tag_primary,
                    "difficulty": int(diff_int),
                    "xp_reward": int(xp),
                }
            )

        embeddings = model.encode(documents, show_progress_bar=False)
        collection.add(
            embeddings=embeddings.tolist(),
            documents=documents,
            ids=ids,
            metadatas=metadatas,
        )
        print(f"Batch {batch_idx + 1}/{num_batches} added ({end}/{total})")

    book_counts = Counter(c["source_file"] for c in chunks_data)
    cfg = {
        "model_name": model_name,
        "total_chunks": total,
        "collection_name": collection_name,
        "vector_db_path": str(out_path),
        "target_books": TARGET_BOOKS,
        "book_distribution": dict(book_counts),
    }
    with open(out_path / "config.json", "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2)

    print(f"Done. Documents: {collection.count():,} at {out_path}")
    print(
        "Set UPHEAL_CHROMA_PATH and UPHEAL_CHROMA_COLLECTION for the gateway "
        "to use this index (see docs/services/ingestion.md)."
    )


if __name__ == "__main__":
    main()
