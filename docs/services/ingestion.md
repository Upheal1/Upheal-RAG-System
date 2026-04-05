# Ingestion: enriched Chroma index

## Roadmap

Team roadmap: [../roadmap/upheal-rag-next-phase.md](../roadmap/upheal-rag-next-phase.md).

## Why a parallel store?

The legacy mini index at `data/vector_db_mini` (collection `clinical_rag_mini`) has metadata without `clinical_tags`, `tag_primary`, `difficulty`, or `xp_reward`. Rebuilding **in place** would break environments until everyone re-runs the builder.

The enriched builder writes by default to:

- **Path:** `data/vector_db_mini_enriched`
- **Collection:** `clinical_rag_mini_enriched`

## Build

From the **repository root**:

```bash
python -m pip install -r requirements.txt
export PYTHONPATH=.
python -m services.ingestion.build_index
```

Windows (cmd):

```bat
set PYTHONPATH=.
python -m services.ingestion.build_index
```

Optional environment variables:

| Variable | Meaning |
|----------|---------|
| `UPHEAL_BUILD_CHROMA_PATH` | Output directory for Chroma persistence |
| `UPHEAL_BUILD_CHROMA_COLLECTION` | Collection name |

## Point the gateway at the enriched index

```bash
export UPHEAL_CHROMA_PATH=/abs/path/to/Upheal-RAG-System/data/vector_db_mini_enriched
export UPHEAL_CHROMA_COLLECTION=clinical_rag_mini_enriched
```

Windows (PowerShell):

```powershell
$env:UPHEAL_CHROMA_PATH = "D:\Career\Grad Project\Upheal-RAG-System\data\vector_db_mini_enriched"
$env:UPHEAL_CHROMA_COLLECTION = "clinical_rag_mini_enriched"
```

If these are unset, the gateway uses legacy `data/vector_db_mini` + `clinical_rag_mini` (metadata filters are skipped when `tag_primary` is missing).

## Related code

- [`services/ingestion/build_index.py`](../../services/ingestion/build_index.py)
- [`services/ingestion/formatter_agent.py`](../../services/ingestion/formatter_agent.py)
