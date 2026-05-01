# A-YAH-04: Knowledge Retrieval in Pipeline (Real Adapter)

## Task Metadata

| Field      | Value                            |
|------------|----------------------------------|
| Task ID    | A-YAH-04                         |
| Owner      | Yahya                            |
| Phase      | Phase 2 — Section 2              |
| File(s)    | `services/architect/pipeline.py`  |
| Complexity | M                                |
| Depends On | A-HOZ-06, A-YAH-02, A-YAH-03     |
| Blocks     | A-YAH-05                         |
| Status     | In Progress                      |

## Overview

Implements the knowledge retrieval stage of the architect pipeline. Fetches candidate tasks from the ChromaDB adapter (or falls back to fixtures), applies difficulty and symptom-tag overlap filters, and returns a filtered list ready for reranking.

## What Was Built

### 1. `RetrievalQuery` Schema (`services/shared/schemas.py`)

New Pydantic model controlling retrieval parameters:

```python
class RetrievalQuery(BaseModel):
    symptom_keywords: List[str]      # Tags to match against task symptom_tags
    max_difficulty: int = 5          # Ceiling for difficulty filtering
    boost_digital_detox: bool = False # Flag for future reranker use
    candidate_count: int = 10        # Number of candidates to fetch (default 10)
    locale: str = "en"               # Locale for downstream auditor
    query_text: Optional[str] = None # Free-text query for embedding search
```

### 2. `retrieve_candidates()` Function (`services/architect/pipeline.py`)

Core retrieval function that:

1. **Fetches raw candidates** from `ChromaKnowledgeBase.retrieve_tasks()` when the KB is healthy, or falls back to hardcoded fixtures (`tests/fixtures/clinical_tasks.py`).
2. **Applies difficulty filter**: `task.difficulty <= min(user_level, max_difficulty)`.
3. **Applies symptom overlap filter**: keeps only tasks where at least one `task.symptom_tag` (case-insensitive) matches a `symptom_keyword`.
4. **Logs the retrieval query text** and filter outcomes via structured JSON logging.

### 3. Updated `run_architect_pipeline()`

Now accepts optional `ChromaKnowledgeBase` and `RetrievalQuery` parameters:

- If `candidate_tasks` is provided, skips retrieval and uses the supplied list.
- If `candidate_tasks` is `None`, calls `retrieve_candidates()` internally.
- Empty results trigger a fixture fallback to guarantee the pipeline always produces output.
- Uses `RetrievalQuery.locale` for the auditor if provided, otherwise falls back to the `locale` kwarg.

## Filtering Logic

### Difficulty Filter

```
effective_max = min(user_level, max_difficulty)
keep tasks where task.difficulty <= effective_max
```

### Symptom Overlap Filter

```
keep tasks where set(task.symptom_tags) & set(symptom_keywords) is not empty
If symptom_keywords is empty, pass all tasks through.
```

## Acceptance Criteria

| Criterion                                     | Status |
|-----------------------------------------------|--------|
| Integration test uses real small Chroma path  | Passes via `chroma_kb` parameter when available |
| Candidate count configurable; default 10      | Passes — `RetrievalQuery.candidate_count` defaults to 10 |
| Logs retrieval query text for debugging       | Passes — structured JSON logs at start, fallback, and done events |

## Files Changed

| File | Change |
|------|--------|
| `services/shared/schemas.py` | Added `RetrievalQuery` model |
| `services/architect/pipeline.py` | Added `retrieve_candidates()`, helper filters, updated `run_architect_pipeline()` |
| `tests/test_pipeline_retrieval.py` | New test file with 17 test cases |

## Test Coverage

### `_apply_difficulty_filter`
- Filters tasks above user level
- Respects `max_difficulty` below user level
- No filter when all within range
- Returns empty when none qualify

### `_apply_symptom_overlap_filter`
- Keeps tasks with matching tags
- Case-insensitive matching
- Returns all when no keywords provided
- No match returns empty

### `retrieve_candidates()`
- Fixture fallback when `chroma_kb` is `None`
- Fixture fallback when `chroma_kb` is unhealthy
- Uses Chroma when healthy
- Applies difficulty filter after Chroma fetch
- Applies symptom overlap filter after Chroma fetch
- Default candidate count is 10
- Respects custom candidate count

### `run_architect_pipeline()`
- Pipeline with candidate tasks directly
- Pipeline uses fixture fallback without tasks or KB
- Pipeline with Chroma KB
- Pipeline uses retrieval query locale for auditor

## Integration Notes

- **Chroma adapter interface**: Calls `chroma_kb.retrieve_tasks(user_context, query_text=query_text, top_k=candidate_count)`. Must match Hozaifa's adapter signature.
- **Fixture fallback**: Depends on `tests/fixtures/clinical_tasks.py` (A-YAH-03). Returns first N tasks from `SAMPLE_TASKS`.
- **Structured logging**: Uses `get_logger(__name__)` from `services/shared/logging.py`. Events:
  - `architect.pipeline.retrieve_candidates.start`
  - `architect.pipeline.retrieve_candidates.chroma_success`
  - `architect.pipeline.retrieve_candidates.fixture_fallback`
  - `architect.pipeline.retrieve_candidates.done`
- **Risk**: Hozaifa may change metadata keys (`tag_primary`, etc.) — the symptom overlap filter works on `symptom_tags` which is stable from `ClinicalTask`.

## How to Run Tests

```bash
pytest tests/test_pipeline_retrieval.py -v
```
