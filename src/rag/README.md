# RAG Module

RAG (Retrieval-Augmented Generation) system for clinical recommendations.

## Files

- `query_rag.py` - Query the vector database
- `process_dsm5.py` - Process and embed DSM-5-TR book
- `semantic_chunker.py` - Chunk PDFs by semantic headers
- `build_vector_store.py` - Build ChromaDB from chunks

## Vector Database

- **Source**: DSM-5-TR (3,255 chunks)
- **Model**: all-mpnet-base-v2
- **Storage**: `../../data/vector_db_mini/`

## Usage

```bash
# Query the database
python query_rag.py

# Or with specific query
python query_rag.py --query "treatment for anxiety"

# Rebuild database (if needed)
python process_dsm5.py
```

The system uses semantic chunking (by document headers) rather than fixed-size chunks for better context preservation.
