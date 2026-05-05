"""
scripts/migrate_initial_clinical_library.py
============================================

One-shot migration: loads semantic_chunks.json, formats each chunk through
the formatter agent (keyword fallback by default, LLM if keys are set), and
upserts into ChromaDB with enriched metadata.

Guarantees idempotency by deleting the target collection before re-ingestion
(wipe-and-rebuild strategy).

Usage
-----
    set PYTHONPATH=.
    python scripts/migrate_initial_clinical_library.py [options]

Options
-------
    --chunks PATH       Path to semantic_chunks.json
                        (default: data/rag_chunks/semantic_chunks.json)
    --output PATH       Output ChromaDB directory
                        (default: data/vector_db_mini_enriched)
    --collection NAME   ChromaDB collection name
                        (default: clinical_rag_mini_enriched)
    --books BOOK1,BOOK2 Comma-separated source_file prefixes to include
                        (default: all books)
    --batch-size N      Chunks per batch for embedding/upsert (default: 100)
    --use-llm           Enable LLM-based formatting (requires API key)
    --dry-run           Run formatter but skip ChromaDB writes
    --model NAME        Sentence-transformer model for embeddings
                        (default: all-mpnet-base-v2)

Environment overrides
---------------------
    UPHEAL_CHROMA_PATH       overrides --output
    UPHEAL_CHROMA_COLLECTION overrides --collection
    UPHEAL_EMBEDDING_MODEL   overrides --model
    OPENAI_API_KEY           enables OpenAI formatter (with --use-llm)
    GEMINI_API_KEY           enables Gemini formatter (with --use-llm)
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List, Sequence

# Ensure repo root is importable.
_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from services.ingestion.formatter_agent import (
    CRISIS_KEYWORDS,
    SYMPTOM_TAG_KEYWORDS,
    format_chunk,
    format_chunks_batch,
)
from services.shared.logging import get_logger
from services.shared.pathing import repo_root

logger = get_logger(__name__)

BATCH_SIZE = 100
DEFAULT_MODEL = "all-mpnet-base-v2"


def _format_chunk_metadata(chunk_text: str, use_llm: bool = False) -> Dict[str, Any]:
    """Format a chunk and return metadata dict suitable for ChromaDB upsert."""
    result = format_chunk(chunk_text, use_llm=use_llm)
    return {
        "difficulty": result["difficulty"],
        "xp_reward": result["xp_reward"],
        "clinical_tags": ",".join(result["symptom_tags"]),
        "safety_risk": str(result["safety_risk"]).lower(),
    }


def _format_batch_metadata(
    texts: List[str], use_llm: bool = False, batch_size: int = 25
) -> List[Dict[str, Any]]:
    """Format a batch of chunks through the formatter agent."""
    results = []
    for i in range(0, len(texts), batch_size):
        batch = texts[i : i + batch_size]
        batch_results = format_chunks_batch(batch, max_batch_size=batch_size, use_llm=use_llm)
        results.extend(batch_results)
    return results


def migrate(
    chunks_path: Path,
    output_path: Path,
    collection_name: str,
    target_books: List[str],
    batch_size: int,
    use_llm: bool,
    dry_run: bool,
    model_name: str,
) -> Dict[str, Any]:
    """
    Run the full migration pipeline.

    Returns a summary dict with counts and timing.
    """
    start_time = time.time()

    # ── 1. Load chunks ─────────────────────────────────────────────
    logger.info("migrate.load_start", path=str(chunks_path))
    if not chunks_path.is_file():
        raise SystemExit(f"Chunks file not found: {chunks_path}")

    with open(chunks_path, "r", encoding="utf-8") as f:
        all_chunks = json.load(f)

    total_raw = len(all_chunks)

    # Filter by target books if specified
    if target_books:
        chunks_data = [c for c in all_chunks if c.get("source_file") in target_books]
        logger.info(
            "migrate.filter_books",
            total_raw=total_raw,
            filtered=len(chunks_data),
            books=len(target_books),
        )
    else:
        chunks_data = all_chunks
        logger.info("migrate.all_books", total_raw=total_raw)

    if not chunks_data:
        raise SystemExit("No chunks found after filtering.")

    # ── 2. Format metadata ────────────────────────────────────────
    logger.info("migrate.format_start", chunks=len(chunks_data), use_llm=use_llm)
    texts = [c["text"] for c in chunks_data]
    formatted_metadatas = _format_batch_metadata(texts, use_llm=use_llm, batch_size=25)

    # ── 3. Build ChromaDB metadata dicts ───────────────────────────
    chroma_metadatas: List[Dict[str, Any]] = []
    for chunk, fmt in zip(chunks_data, formatted_metadatas):
        header = ""
        hh = chunk.get("header_hierarchy")
        if hh and isinstance(hh, list) and len(hh) > 0:
            header = str(hh[0])

        tags = fmt.get("symptom_tags") or ["general"]
        if isinstance(tags, str):
            tags = [t.strip() for t in tags.split(",") if t.strip()]
        if not tags:
            tags = ["general"]

        chroma_metadatas.append({
            "source_file": chunk.get("source_file", "unknown"),
            "char_count": int(chunk.get("char_count", 0)),
            "page_numbers": str(chunk.get("page_numbers", "")),
            "header": header,
            "clinical_tags": ",".join(str(t) for t in tags),
            "tag_primary": str(tags[0]),
            "difficulty": int(fmt.get("difficulty", 3)),
            "xp_reward": int(fmt.get("xp_reward", 10)),
            "safety_risk": str(fmt.get("safety_risk", False)).lower(),
            "utility_score": str(fmt.get("utility_score", 0.5)),
        })

    # ── 4. Write to ChromaDB (or dry-run) ─────────────────────────
    if dry_run:
        book_dist = Counter(c.get("source_file", "unknown") for c in chunks_data)
        summary = {
            "status": "dry_run",
            "total_raw_chunks": total_raw,
            "filtered_chunks": len(chunks_data),
            "book_distribution": dict(book_dist),
            "elapsed_seconds": round(time.time() - start_time, 2),
        }
        logger.info("migrate.dry_run_complete", **summary)
        return summary

    from sentence_transformers import SentenceTransformer
    import chromadb

    logger.info("migrate.model_loading", model=model_name)
    model = SentenceTransformer(model_name)

    output_path.mkdir(parents=True, exist_ok=True)
    client = chromadb.PersistentClient(path=str(output_path))

    # Idempotent: wipe existing collection before re-ingestion.
    try:
        client.delete_collection(name=collection_name)
        logger.info("migrate.collection_deleted", collection=collection_name)
    except Exception:
        pass

    collection = client.create_collection(
        name=collection_name,
        metadata={
            "description": "Enriched clinical RAG with formatter metadata",
        },
    )

    total = len(chunks_data)
    num_batches = (total + batch_size - 1) // batch_size
    ids = [c.get("chunk_id", f"chunk_{i}") for i, c in enumerate(chunks_data)]

    for batch_idx in range(num_batches):
        s = batch_idx * batch_size
        e = min(s + batch_size, total)
        batch_texts = texts[s:e]
        batch_ids = ids[s:e]
        batch_metas = chroma_metadatas[s:e]

        embeddings = model.encode(batch_texts, show_progress_bar=False)
        collection.add(
            embeddings=embeddings.tolist(),
            documents=batch_texts,
            ids=batch_ids,
            metadatas=batch_metas,
        )
        logger.info(
            "migrate.batch_added",
            batch=batch_idx + 1,
            total_batches=num_batches,
            chunks_so_far=e,
            total=total,
        )

    # ── 5. Write config.json ───────────────────────────────────────
    book_dist = Counter(c.get("source_file", "unknown") for c in chunks_data)
    cfg = {
        "model_name": model_name,
        "total_chunks": total,
        "collection_name": collection_name,
        "vector_db_path": str(output_path),
        "target_books": target_books or ["all"],
        "book_distribution": dict(book_dist),
        "last_ingestion": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "migration_script": "migrate_initial_clinical_library",
        "use_llm": use_llm,
    }
    with open(output_path / "config.json", "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2)

    elapsed = round(time.time() - start_time, 2)
    final_count = collection.count()

    logger.info(
        "migrate.complete",
        documents=final_count,
        elapsed_seconds=elapsed,
        collection=collection_name,
    )

    return {
        "status": "success",
        "total_raw_chunks": total_raw,
        "filtered_chunks": total,
        "documents_indexed": final_count,
        "elapsed_seconds": elapsed,
        "book_distribution": dict(book_dist),
        "output_path": str(output_path),
        "collection_name": collection_name,
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Migrate semantic_chunks.json into an enriched ChromaDB collection."
    )
    parser.add_argument(
        "--chunks",
        type=str,
        default=None,
        help="Path to semantic_chunks.json (default: data/rag_chunks/semantic_chunks.json)",
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="Output ChromaDB directory (default: data/vector_db_mini_enriched)",
    )
    parser.add_argument(
        "--collection",
        type=str,
        default=None,
        help="ChromaDB collection name (default: clinical_rag_mini_enriched)",
    )
    parser.add_argument(
        "--books",
        type=str,
        default=None,
        help="Comma-separated source_file prefixes to include (default: all)",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=BATCH_SIZE,
        help=f"Chunks per batch (default: {BATCH_SIZE})",
    )
    parser.add_argument(
        "--use-llm",
        action="store_true",
        default=False,
        help="Enable LLM-based formatting (requires OPENAI_API_KEY or GEMINI_API_KEY)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=False,
        help="Run formatter but skip ChromaDB writes",
    )
    parser.add_argument(
        "--model",
        type=str,
        default=None,
        help=f"Sentence-transformer model (default: {DEFAULT_MODEL})",
    )
    args = parser.parse_args(argv)

    root = repo_root()

    chunks_path = Path(args.chunks) if args.chunks else root / "data" / "rag_chunks" / "semantic_chunks.json"
    output_path = Path(args.output) if args.output else Path(
        os.environ.get("UPHEAL_CHROMA_PATH", str(root / "data" / "vector_db_mini_enriched"))
    )
    collection_name = args.collection or os.environ.get(
        "UPHEAL_CHROMA_COLLECTION", "clinical_rag_mini_enriched"
    )
    model_name = args.model or os.environ.get("UPHEAL_EMBEDDING_MODEL", DEFAULT_MODEL)

    target_books: List[str] = []
    if args.books:
        target_books = [b.strip() for b in args.books.split(",") if b.strip()]

    print(f"SEMANTIC_CHUNKS  = {chunks_path}")
    print(f"OUTPUT           = {output_path}")
    print(f"COLLECTION       = {collection_name}")
    print(f"MODEL            = {model_name}")
    print(f"TARGET_BOOKS     = {target_books or 'ALL'}")
    print(f"BATCH_SIZE        = {args.batch_size}")
    print(f"USE_LLM           = {args.use_llm}")
    print(f"DRY_RUN           = {args.dry_run}")
    print()

    result = migrate(
        chunks_path=chunks_path,
        output_path=output_path,
        collection_name=collection_name,
        target_books=target_books,
        batch_size=args.batch_size,
        use_llm=args.use_llm,
        dry_run=args.dry_run,
        model_name=model_name,
    )

    print("\n" + "=" * 60)
    print("MIGRATION SUMMARY")
    print("=" * 60)
    for k, v in result.items():
        if k == "book_distribution":
            print(f"  book_distribution:")
            for book, count in v.items():
                print(f"    {book}: {count}")
        else:
            print(f"  {k}: {v}")

    if result.get("status") == "dry_run":
        print("\nDry run complete. No documents written to ChromaDB.")
        return 0
    elif result.get("status") == "success":
        print(f"\nMigration complete: {result.get('documents_indexed', 0)} documents indexed.")
        return 0
    else:
        print(f"\nMigration failed: {result}")
        return 2


if __name__ == "__main__":
    sys.exit(main())