# [A-YAH-03] Hardcoded `ClinicalTask` Fixture Set

## Task Overview

| Field | Value |
|-------|-------|
| Owner | Yahya |
| Phase | Phase 1 — scaffolding |
| File | `tests/fixtures/clinical_tasks.py` |
| Complexity | S |
| Depends On | A-HOZ-01 (Pydantic schemas) |
| Blocks | A-YAH-04, A-YAH-05 |
| Status | ✅ Complete |

## Purpose

Creates a set of hardcoded `ClinicalTask` instances that simulate ChromaDB retrieval until **A-HOZ-06** (the real ChromaDB adapter) is ready. This enables pure logic unit testing without external dependencies.

## Implementation Details

### Files Created

1. **`tests/fixtures/__init__.py`** - Package initializer exporting fixtures
2. **`tests/fixtures/clinical_tasks.py`** - Main fixture module

### Fixtures Provided

#### SAMPLE_TASKS (12 tasks)
Covers difficulty levels 1-5 with varied `symptom_tags`:

| Task ID | Difficulty | Primary Tags | Safety Risk |
|---------|-------------|--------------|-------------|
| fixture-001 | 1 | anxiety, panic, acute-stress | False |
| fixture-002 | 1 | anxiety, insomnia, stress | False |
| fixture-003 | 2 | depression, anxiety, cognitive-distortion | False |
| fixture-004 | 2 | depression, low-motivation, anhedonia | False |
| fixture-005 | 1 | anxiety, stress, panic | False |
| fixture-006 | 3 | anxiety, generalized-anxiety | False |
| fixture-007 | 2 | insomnia, sleep-disturbance, stress | False |
| fixture-008 | 4 | anxiety, catastrophizing, overthinking | False |
| fixture-009 | 3 | depression, burnout, meaninglessness | False |
| fixture-010 | 3 | depression, procrastination, low-motivation | False |
| fixture-011 | 2 | stress, anxiety, somatic-symptoms | False |
| fixture-012 | 3 | depression, social-withdrawal, isolation | False |

#### SAFETY_EDGE_CASE_TASKS (2 tasks)
Critical for auditor testing:

| Task ID | Safety Risk | Purpose |
|---------|-------------|---------|
| fixture-danger-001 | **True** | Crisis protocol trigger |
| fixture-danger-002 | False | Trauma-informed grounding |

### Scenario Mapping

The `FIXTURE_SCENARIO_MAP` provides lookup by test scenario:

```python
from tests.fixtures.clinical_tasks import SAMPLE_TASKS, SAFETY_EDGE_CASE_TASKS, FIXTURE_SCENARIO_MAP

# Get tasks for mild anxiety
anxiety_tasks = [t for t in SAMPLE_TASKS if t.task_id in FIXTURE_SCENARIO_MAP["anxiety-mild"]]

# Get safety test cases
safety_tasks = SAFETY_EDGE_CASE_TASKS

# Get one task per difficulty level
difficulty_sweep = [t for t in SAMPLE_TASKS if t.task_id in FIXTURE_SCENARIO_MAP["difficulty-sweep"]]
```

## Acceptance Criteria

- [x] Exactly ≥10 tasks (12 provided in SAMPLE_TASKS)
- [x] At least one `safety_risk=True` (`fixture-danger-001`)
- [x] Fixtures importable as `from tests.fixtures.clinical_tasks import SAMPLE_TASKS`
- [x] Documented mapping from fixture IDs to test scenarios

## Metadata Schema

Each fixture includes:

| Field | Type | Description |
|-------|------|-------------|
| `safety_risk` | bool | Triggers auditor override if True |
| `utility_score` | float | [0-1] for Phase 4 reranking |
| `modality` | str | breathing, cognitive, behavioral, etc. |
| `duration_minutes` | int | Estimated completion time |
| `form_type` | str | Category of therapeutic technique |

## Usage in Microservices

This fixture module is designed to be consumed by:

1. **`services/assessment/core.py`** - Profiler logic testing
2. **`services/architect/pipeline.py`** - Retrieval pipeline testing (until A-YAH-04)
3. **`services/architect/auditor.py`** - Safety gate testing

## Testing

Run to verify fixtures:

```bash
pytest tests/test_fixtures.py -v
```

## Notes

- All task content uses clinically-accurate therapeutic techniques
- Crisis task (`fixture-danger-001`) has `xp_reward=0` and triggers RED safety path
- Fixtures use controlled vocabulary for `symptom_tags` matching roadmap spec
