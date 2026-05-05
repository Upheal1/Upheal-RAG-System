# [A-YAH-09] Full Orchestration Chain in Gateway

## Task Overview

| Field | Value |
|-------|-------|
| Owner | Yahya |
| Phase | Phase 2 — Section 5 |
| Files | `services/gateway/orchestrator.py`, `services/gateway/main.py`, `services/architect/pipeline.py` |
| Complexity | M |
| Depends On | A-YAH-01, A-YAH-02, A-YAH-05, A-YAH-07 |
| Blocks | A-YAH-10 (POST /api/roadmap), A-YAH-11 (POST /api/telemetry) |
| Status | ✅ Complete |

## Purpose

Wires the full assessment chain into a single request path: **Profiler → Architect → Auditor** with per-stage structured logging, timing metrics, and safe error handling. No stage failure exposes stack traces to the client.

**Key design decision:** Extracted orchestration logic from the inline `assess()` function in `main.py` into a dedicated `services/gateway/orchestrator.py` module. This makes the chain independently testable and separates gateway routing from business logic.

## Chain Architecture

```
POST /api/assess
       ↓
run_assessment_chain()
       ↓
Stage 1: Profiler (build_user_context)
  → UserContext with form_scores, r_app, user_stats
       ↓
Stage 2: Architect (retrieve → rerank → sequence → overview → audit)
  → FinalRoadmap with safety_status, suggested_tasks
       ↓
Stage 3: Assemble (translate to legacy AssessGatewayResponse)
  → anxiety_probability, depression_probability, severity, comorbidity
       ↓
JSON response to client
```

## Gamifier Workaround

Since A-YAH-06 (Gamifier Agent, assigned to Ahmed) is not implemented, the chain includes a **pass-through hook** at the sequencing stage:

### In pipeline.py

```python
def _sequence_tasks(tasks, user_context) -> List[ClinicalTask]:
    """Hook for A-YAH-06. Currently returns tasks unchanged."""
    return list(tasks)
```

### In orchestrator.py

```python
def _sequence_tasks(tasks, user_context) -> list:
    """Hook for A-YAH-06. Currently returns tasks unchanged."""
    return tasks
```

Both hooks are clearly marked with `TODO` comments for when the Gamifier is implemented. The pipeline hook is called inside `run_architect_pipeline()`, and the orchestrator hook is called before the pipeline invocation.

## Error Handling

Each stage is wrapped in a try/except block. If any stage fails:

| Failed Stage | Fallback Behavior |
|-------------|------------------|
| Profiler | Returns `UserContext` with defaults (no crash) |
| Query build | Returns safe YELLOW advisory response |
| Architect | Returns YELLOW advisory: "We're preparing your personalized roadmap..." |
| Assemble | Returns YELLOW advisory with severity defaults |

**Never exposes:**
- Stack traces
- Internal error messages
- Database connection strings
- Any sensitive data

Fallback response always has:
- `safety_status = "YELLOW"`
- `query_used = "fallback"`
- Advisory overview paragraph (clinically appropriate, no error language)

## Structured Logging

Every stage logs `start` and `done` events with timing:

| Event | Fields Logged |
|-------|--------------|
| `gateway.assess.profiler.start` | `user_id` |
| `gateway.assess.profiler.done` | `user_id`, `form_scores`, `r_app`, `duration_ms` |
| `gateway.assess.architect.start` | `user_id`, `query_text`, `locale` |
| `gateway.assess.architect.done` | `user_id`, `task_count`, `safety_status`, `duration_ms` |
| `gateway.assess.assemble.start` | `user_id` |
| `gateway.assess.assemble.done` | `user_id`, `safety_status`, `duration_ms` |
| `gateway.assess.{stage}.error` | `user_id`, `failed_stage`, `error` |
| `gateway.assess.fallback.activated` | `user_id`, `failed_stage` |

Plus the existing `Score breakdown` compact log line in the assemble stage.

## Implementation Details

### Files Created

| File | Purpose |
|------|---------|
| `services/gateway/orchestrator.py` | Chain orchestration: `_run_profiler()`, `_run_architect()`, `_assemble_response()`, `_safe_fallback_response()`, `run_assessment_chain()`, `_sequence_tasks()` hook |

### Files Modified

| File | Change |
|------|--------|
| `services/gateway/main.py` | Replaced inline chain with `run_assessment_chain()` call. Moved `_kb` instantiation into health_check to avoid global import issues |
| `services/architect/pipeline.py` | Added `_sequence_tasks()` hook function, called between rerank and overview generation |

### Key Functions

| Function | Module | Purpose |
|----------|--------|---------|
| `run_assessment_chain()` | orchestrator.py | Main entry point — runs all 3 stages with error handling |
| `_run_profiler()` | orchestrator.py | Builds UserContext from raw forms + screen time |
| `_run_architect()` | orchestrator.py | Retrieves tasks, applies sequencing hook, runs pipeline |
| `_assemble_response()` | orchestrator.py | Translates FinalRoadmap → AssessGatewayResponse with legacy fields |
| `_safe_fallback_response()` | orchestrator.py | Generates degraded but safe response on any stage failure |
| `_sequence_tasks()` | orchestrator.py + pipeline.py | Gamifier pass-through hook (two locations) |

## Usage

### Gateway endpoint (existing — unchanged API)

```bash
curl -X POST http://localhost:8000/api/assess \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "user-123",
    "locale": "en",
    "screen_time_minutes": 90,
    "raw_forms_json": {"answers": {"gad7_q1": 2, "gad7_q2": 1, ...}}
  }'
```

### Programmatic orchestration

```python
from services.gateway.orchestrator import run_assessment_chain

response = run_assessment_chain(
    user_id="user-123",
    raw_payload={"answers": {...}},
    screen_time_minutes=90.0,
    locale="ar",
    session_id="session-abc",
)
```

## Testing

21 unit tests in `tests/test_orchestration.py`:

| Test Class | Coverage |
|------------|----------|
| `TestSequenceTasksHook` | Pass-through behavior, empty list, order preservation (3 tests) |
| `TestSafeFallbackResponse` | YELLOW status, no stack traces, session ID preservation, with answers (5 tests) |
| `TestOrchestrationHappyPath` | Full chain returns valid AssessGatewayResponse with tasks, legacy fields, RAG recommendations (4 tests) |
| `TestOrchestrationErrors` | Profiler/architect/assemble failures → safe fallback, never exposes stack trace (4 tests) |
| `TestLocalePropagation` | EN/AR locale flows through all stages (2 tests) |
| `TestScreenTimeDrivesRApp` | High and zero screen time paths (2 tests) |
| `TestEmptyForms` | No answers → mild defaults (1 test) |

Run to verify:

```bash
pytest tests/test_orchestration.py -v
```

## Acceptance Criteria

- [x] Single request path exercises all stages with structured logging
- [x] Exceptions from KB return safe JSON error, not stack traces to client
- [x] OpenAPI documents request/response models (unchanged from before)
- [x] Per-stage timing metrics logged
- [x] Gamifier hook in place for A-YAH-06 integration

## Integration Points

| Consumer | How it uses orchestrator |
|----------|------------------------|
| `services/gateway/main.py` | `POST /api/assess` calls `run_assessment_chain()` |
| Future: A-YAH-06 (Gamifier) | Replace `_sequence_tasks()` pass-through with actual XP scaling + sequencing |
| Future: A-YAH-10 (POST /api/roadmap) | Will call same chain with different response shape |

## Notes

- The orchestrator creates its own `ChromaKnowledgeBase` instance at module level (`_kb`). This is consistent with the previous pattern in `main.py`.
- The `main.py` health_check now creates a local `_kb` instance to avoid circular import issues.
- All existing tests pass — the refactoring is backward compatible.
