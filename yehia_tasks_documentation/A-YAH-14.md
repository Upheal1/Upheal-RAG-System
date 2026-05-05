# A-YAH-14: Triple-Threat v2 (add `UtilityScore`)

## Task Metadata

| Field      | Value                            |
|------------|----------------------------------|
| Task ID    | A-YAH-14                         |
| Owner      | Yahya                            |
| Phase      | Phase 4 — Section 3              |
| File(s)    | `services/architect/pipeline.py` |
| Complexity | M                                |
| Depends On | A-HOZ-14, A-YAH-05               |
| Blocks     | A-YAH-15                         |
| Status     | Completed                        |

## Overview

Updated the reranking formula to include `utility_score` from clinical tasks. This is the Phase 4 scoring that replaces the Phase 2 formula with a four-term weighted score.

## What Was Built

### Updated Formula

**Phase 2 (old):**
```
Score = (SemanticSimilarity × 0.4) + (FormWeight × 0.3) + (R_app × 0.3)
```

**Phase 4 (new):**
```
Score = (SemanticSimilarity × 0.35) + (FormWeight × 0.25) + (R_app × 0.25) + (UtilityScore × 0.15)
```

### Changes to `services/architect/pipeline.py`

1. **Updated `_triple_threat_score()`:**
   - Added `utility_score` parameter (defaults to 0.5)
   - Normalizes utility to [0,1] before weighting
   - Uses new weight distribution (0.35, 0.25, 0.25, 0.15)

2. **Updated `rerank_tasks()`:**
   - Extracts `task.utility_score` from each clinical task
   - Passes to scoring function

### Key Behaviors

| Behavior | Implementation |
|----------|----------------|
| UtilityScore normalized | `max(0.0, min(1.0, float(utility_score)))` |
| Default utility | 0.5 (from ClinicalTask schema default) |
| RED bypass | Safety check happens in auditor, not ranking |
| Weight distribution | 35% similarity, 25% form, 25% R_app, 15% utility |

## Acceptance Criteria

| Criterion | Status |
|-----------|--------|
| `UtilityScore` normalised to [0,1] before weighting | Passes |
| Regression tests show ordering changes when utility differs at fixed similarity | Passes |
| RED safety path still bypasses ranking games | Passes |

## Test Coverage

Added 7 new tests in `tests/test_reranking.py`:

### TestTripleThreatV2UtilityScore (7 tests)
- Utility score normalized to 1.0 (clamps >1)
- Utility score normalized to 0.0 (clamps <0)
- Utility score defaults to 0.5 when not provided
- Different utility changes task ordering
- Utility at fixed similarity changes ordering
- Utility weight is 0.15 in formula
- RED safety path bypasses ranking

**Total: 25 tests (18 existing + 7 new), all passing**

## Files Changed

| File | Action |
|------|--------|
| `services/architect/pipeline.py` | Updated `_triple_threat_score()` and `rerank_tasks()` |
| `tests/test_reranking.py` | Added 7 new tests |

## How to Run Tests

```bash
pytest tests/test_reranking.py -v
```

## Integration Notes

- **UtilityScore source**: `ClinicalTask.utility_score` (default 0.5 from schema)
- **Normalization**: Clamps to [0.0, 1.0] before weighting
- **Backward compatibility**: Default parameter ensures existing code works
- **Phase 4 weights**: New distribution reflects utility metric importance