# RAG module (`src/rag`)

Scripts for chunking, building the vector store, and ad hoc queries.

## Notable files

| File | Purpose |
|------|---------|
| `query_rag.py` | Query Chroma |
| `process_dsm5.py` | Process / embed DSM-5-TR content |
| `semantic_chunker.py` | Semantic (header-based) chunking |
| `build_vector_store.py` | Build Chroma from chunks |
| `build_vector_store_mini.py` | Smaller focused index for prototyping |

## Vector database

- **Embeddings:** `all-mpnet-base-v2`
- **Typical storage:** `data/vector_db_mini/` (paths may vary by script working directory)

## Usage examples

```bash
cd src/rag
python query_rag.py
python query_rag.py --query "treatment for anxiety"
```

Rebuild flows depend on your dataset; see script headers and [Ingestion & vector index](../services/ingestion.md) for the enriched `services/ingestion/build_index.py` path used by the gateway.

## Design note

Chunking uses document structure (headers) rather than only fixed token windows to preserve clinical context where configured.
