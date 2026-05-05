# A-YAH-13: Director override read in pipeline

## Task Metadata

| Field      | Value                            |
|------------|----------------------------------|
| Task ID    | A-YAH-13                         |
| Owner      | Yahya                            |
| Phase      | Phase 3 — Section 2              |
| File(s)    | `services/architect/`            |
| Complexity | M                                |
| Depends On | A-HOZ-13                         |
| Blocks     | A-YAH-14                         |
| Status     | Completed                        |

## Overview

Loads active `MutationInstruction` from Supabase before retrieval and applies constraints to `RetrievalQuery`. The Director (Hozaifa) writes directives to `roadmap_mutations` table, and this task reads them to constrain the architect pipeline.

## What Was Built

### 1. New Module: `services/architect/director_override.py`

```python
@dataclass
class DirectorDirective:
    directive_id: UUID
    user_id: UUID
    max_difficulty: Optional[int] = None
    xp_multiplier: Optional[float] = None
    tag_focus: List[str] = None
    valid_until: Optional[datetime] = None
    
    def is_expired(self) -> bool:
        """Check if directive has expired."""
```

### 2. Functions

| Function | Purpose |
|----------|---------|
| `load_active_directive(user_id)` | Query Supabase for active directive |
| `apply_directive_constraints(directive, query)` | Apply constraints to RetrievalQuery |

### 3. Constraints Applied

| Directive Field | Action |
|-----------------|--------|
| `max_difficulty: 2` | Override `query.max_difficulty = min(original, 2)` |
| `tag_focus: ["anxiety"]` | Add to `query.symptom_keywords` |
| `valid_until: past` | Skip directive (expired) |

### 4. Pipeline Integration

Updated `run_architect_pipeline()` in `services/architect/pipeline.py`:

```python
rq = retrieval_query or RetrievalQuery()

directive = load_active_directive(user_context.user_id)
if directive is not None:
    rq = apply_directive_constraints(directive, rq)

pre_filtered = retrieve_candidates(user_context, rq, chroma_kb=chroma_kb)
```

## Acceptance Criteria

| Criterion | Status |
|-----------|--------|
| max_difficulty: 2 limits tasks to difficulty ≤2 | Passes |
| Expired directives ignored using valid_until | Passes |
| Unit test with stubbed Supabase/Director client | Passes |

## Test Coverage

### TestDirectorDirective (5 tests)
- Directive creation with all fields
- Default tag_focus to empty list
- is_expired with no expiry (returns False)
- is_expired with future (returns False)
- is_expired with past (returns True)

### TestApplyDirectiveConstraints (5 tests)
- No directive max_difficulty (unchanged)
- max_difficulty lowered when directive lower
- max_difficulty not increased when directive higher
- tag_focus added to symptom_keywords
- tag_focus deduplicates existing keywords

### TestLoadActiveDirective (4 tests)
- No directive returns None
- Active directive loaded from client
- Expired directive ignored
- Invalid UUID returns None

### TestPipelineIntegration (2 tests)
- Pipeline uses directive constraints
- Pipeline skips expired directive

**Total: 16 tests, all passing**

## Files Changed

| File | Action |
|------|--------|
| `services/architect/director_override.py` | New — directive loading and constraint logic |
| `services/architect/pipeline.py` | Modified — integrated directive loading |
| `tests/test_director_override.py` | New — 16 unit tests |

## How to Run Tests

```bash
pytest tests/test_director_override.py -v
```

## Integration Notes

- **Supabase table**: `roadmap_mutations` (from migration 002)
- **Query strategy**: Most recent non-expired directive for user
- **Fallback**: If no directive, pipeline works normally
- **Error handling**: Invalid UUIDs, parse errors return None gracefully