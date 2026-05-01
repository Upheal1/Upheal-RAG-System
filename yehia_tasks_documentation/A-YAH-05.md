# A-YAH-05: Triple-Threat Reranking Engine

## Task Metadata

| Field      | Value                            |
|------------|----------------------------------|
| Task ID    | A-YAH-05                         |
| Owner      | Yahya                            |
| Phase      | Phase 2 — Section 2              |
| File(s)    | `services/architect/pipeline.py`  |
| Complexity | L                                |
| Depends On | A-YAH-04                         |
| Blocks     | A-YAH-06, A-YAH-14               |
| Status     | In Progress                      |

## Overview

Enhances the reranking engine with three key upgrades:
1. **FormWeight** uses Jaccard similarity instead of raw score averaging
2. **Digital Detox Boost** promotes grounding/detox tasks when flagged
3. **Deterministic tie-break** ensures stable ordering

## Scoring Formula

```
Score = (SemanticSimilarity × 0.4) + (FormWeight × 0.3) + (R_app × 0.3)
```

When `boost_digital_detox` is `True` and the task has a detox-related tag:
```
FinalScore = Score × (1 + 0.15)
```

## Changes from A-YAH-04

### 1. FormWeight → Jaccard Overlap

| Before | After |
|--------|-------|
| Average of matching form scores (0..100 → 0..1) | Jaccard = \|task_tags ∩ user_domains\| / \|task_tags ∪ user_domains\| |

**Example:**
- User domains: `{"anxiety", "depression"}`
- Task tags: `{"anxiety", "panic"}`
- Jaccard = `{"anxiety"}` / `{"anxiety", "panic", "depression"}` = **1/3 ≈ 0.33**

### 2. Digital Detox Boost

When `RetrievalQuery.boost_digital_detox = True`, tasks with any of these tags get a 15% score multiplier:
- `grounding`
- `breathing`
- `somatic`
- `mindfulness`
- `relaxation`
- `digital-detox`

### 3. Deterministic Tie-Break

Sort key: `(score, -difficulty, task_id)` — all descending.

For equal scores:
1. Lower difficulty ranks first (easier tasks are safer)
2. Alphabetical task_id for complete determinism

## New Functions

### `_jaccard_overlap(task_tags, user_domains) -> float`
Case-insensitive Jaccard similarity between task symptom tags and user's form score keys.

### `_apply_detox_boost(score, task, boost) -> float`
Applies `1.15×` multiplier if boost is enabled and the task has a detox tag.

## API Changes

### `rerank_tasks()`
```python
def rerank_tasks(
    tasks: Sequence[ClinicalTask],
    user_context: UserContext,
    *,
    top_n: int = 5,
    boost_digital_detox: bool = False,  # NEW
) -> List[ClinicalTask]:
```

### `run_architect_pipeline()`
Now passes `retrieval_query.boost_digital_detox` through to `rerank_tasks()`.

## Acceptance Criteria

| Criterion | Status |
|-----------|--------|
| Ordering changes when `boost_digital_detox` toggles | Passes — grounding task jumps ahead of higher-similarity non-detox task |
| FormWeight uses Jaccard overlap on tags vs user domains | Passes — exact/partial/zero overlap tests verified |
| Top-5 output stable given fixed inputs (deterministic tie-break) | Passes — repeated calls produce identical ordering |

## Files Changed

| File | Action |
|------|--------|
| `services/architect/pipeline.py` | Replaced `_form_weight_from_context`, added `_jaccard_overlap`, `_apply_detox_boost`, `_DETOX_BOOST_TAGS`, `_DETOX_BOOST_FACTOR`; updated `rerank_tasks` and `run_architect_pipeline` |
| `tests/test_reranking.py` | New test file with 14 test cases |

## Test Coverage

### Jaccard Overlap (7 tests)
- Exact overlap (1.0)
- Partial overlap (1/3)
- Zero overlap (0.0)
- Case-insensitive matching
- Empty task tags
- Empty user domains
- Both empty

### Digital Detox Boost (5 tests)
- Boost applies to grounding, breathing, mindfulness tasks
- No boost for non-detox tags (cbt, journaling)
- No boost when flag disabled
- Boost changes ordering (grounding task jumps ahead)
- No ordering change when no detox tasks present

### Deterministic Tie-Break (3 tests)
- Equal scores → lower difficulty first
- Equal scores + equal difficulty → alphabetical task_id
- Repeated calls produce identical output

### Pipeline Integration (1 test)
- `RetrievalQuery.boost_digital_detox` propagates through `run_architect_pipeline()`

## How to Run Tests

```bash
pytest tests/test_reranking.py -v
```
