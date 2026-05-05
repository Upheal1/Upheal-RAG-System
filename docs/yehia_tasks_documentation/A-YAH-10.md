# [A-YAH-10] POST /api/roadmap — Validated Response

## Task Overview

| Field | Value |
|-------|-------|
| Owner | Yahya |
| Phase | Phase 2 — Section 5 |
| Files | `services/gateway/schemas.py`, `services/gateway/main.py` |
| Complexity | S |
| Depends On | A-YAH-09 (Full Orchestration Chain) |
| Blocks | A-YAH-15 (14-day E2E Simulation) |
| Status | ✅ Complete |

## Purpose

Provides a dedicated `POST /api/roadmap` endpoint that returns a **clean `FinalRoadmap` response** without legacy clinical fields. This is the modern API contract for new clients, separate from the Flutter-compatible `POST /api/assess` which includes legacy fields like `anxiety_probability`, `severity`, `comorbidity`, and `rag_recommendations`.

## Endpoint

### `POST /api/roadmap`

Generates a personalized clinical roadmap for a user based on their assessment responses.

### Request Schema

```python
class RoadmapRequest(BaseModel):
    user_id: str
    session_id: Optional[str] = None
    locale: str = "en"
    raw_forms_json: Dict[str, Any] = Field(default_factory=dict)
    screen_time_minutes: float = 0.0
    answers: Optional[Dict[str, int]] = None
    top_n: int = Field(default=5, ge=1, le=10)
```

### Response Schema

```python
class RoadmapResponse(BaseModel):
    user_id: str
    overview_paragraph: str
    suggested_tasks: List[ClinicalTask]
    safety_status: Literal["GREEN", "YELLOW", "RED"]
    next_checkup_days: int
    generated_at: str
    session_id: Optional[str] = None
    version: str = "1.0"
```

### Example Request

```bash
curl -X POST http://localhost:8000/api/roadmap \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "user-123",
    "locale": "en",
    "screen_time_minutes": 90,
    "answers": {
      "gad7_q1": 2, "gad7_q2": 1, "gad7_q3": 2,
      "gad7_q4": 1, "gad7_q5": 2, "gad7_q6": 1, "gad7_q7": 0
    },
    "top_n": 5
  }'
```

### Example Response (GREEN)

```json
{
  "user_id": "user-123",
  "overview_paragraph": "Based on your responses and your screen-time pattern suggests higher usage than your threshold, here are tailored next steps focused on anxiety, stress, grounding. Start with the first suggestion today and use the rest as options over the next few days.",
  "suggested_tasks": [
    {
      "task_id": "t1",
      "content": "5-4-3-2-1 Grounding: Name 5 things you see, 4 you hear...",
      "symptom_tags": ["anxiety", "panic", "acute-stress"],
      "difficulty": 1,
      "xp_reward": 50,
      "safety_risk": false,
      "utility_score": 0.7,
      "source_reference": "grounding-technique-protocol-v1",
      "metadata": {"similarity": 0.85, "triple_threat_score": 0.62}
    }
  ],
  "safety_status": "GREEN",
  "next_checkup_days": 14,
  "generated_at": "2024-06-15T12:00:00+00:00",
  "session_id": "s-1",
  "version": "1.0"
}
```

### Example Response (RED — Crisis)

```json
{
  "user_id": "user-123",
  "overview_paragraph": "I'm really sorry you're going through this. If you feel in immediate danger...",
  "suggested_tasks": [
    {
      "task_id": "emergency_resources",
      "content": "I'm really sorry you're going through this...",
      "symptom_tags": ["suicidal"],
      "difficulty": 5,
      "xp_reward": 0,
      "safety_risk": false,
      "utility_score": 0.0,
      "source_reference": "auditor",
      "metadata": {}
    }
  ],
  "safety_status": "RED",
  "next_checkup_days": 1,
  "generated_at": "2024-06-15T12:00:00+00:00",
  "session_id": "s-1",
  "version": "1.0"
}
```

## Design Decisions

### Why a separate endpoint?

| Endpoint | Purpose | Response |
|----------|---------|----------|
| `POST /api/assess` | Legacy Flutter compatibility | `AssessGatewayResponse` (roadmap + clinical probabilities, severity, RAG recommendations) |
| `POST /api/roadmap` | Modern clean API | `RoadmapResponse` (roadmap only, no legacy fields) |

The roadmap endpoint:
- **Does NOT include** `anxiety_probability`, `depression_probability`, `severity`, `comorbidity`, `rag_recommendations`, `query_used`
- **Includes** `generated_at`, `version` for API tracking
- Reuses the same orchestration chain as `/api/assess` — no duplicated logic

### How it works

```
POST /api/roadmap
       ↓
RoadmapRequest validation
       ↓
run_assessment_chain() (same orchestrator as /api/assess)
       ↓
Extract roadmap fields only → RoadmapResponse
       ↓
JSON response to client
```

The endpoint calls `run_assessment_chain()` (from A-YAH-09) and strips the legacy fields, returning only the clean roadmap data. The `top_n` parameter is applied as a slice on the returned tasks list.

## Implementation Details

### Files Created

| File | Purpose |
|------|---------|
| `services/gateway/schemas.py` | `RoadmapRequest`, `RoadmapResponse` Pydantic models |
| `tests/test_roadmap_endpoint.py` | 16 unit tests |

### Files Modified

| File | Change |
|------|--------|
| `services/gateway/main.py` | Added `POST /api/roadmap` endpoint, imported `RoadmapRequest`, `RoadmapResponse` |

## Response Fields

| Field | Type | Description |
|-------|------|-------------|
| `user_id` | str | The user who requested the roadmap |
| `overview_paragraph` | str | Personalized summary of next steps |
| `suggested_tasks` | List[ClinicalTask] | Up to `top_n` tasks, ordered by relevance |
| `safety_status` | str | `"GREEN"`, `"YELLOW"`, or `"RED"` |
| `next_checkup_days` | int | Recommended days before next assessment (14 for GREEN, 7 for YELLOW, 1 for RED) |
| `generated_at` | str | ISO-8601 timestamp of generation |
| `session_id` | str or null | Echoed from request |
| `version` | str | API version (`"1.0"`) |

## Safety Behavior

| Scenario | safety_status | next_checkup_days | Task Count |
|----------|--------------|-------------------|------------|
| Normal assessment | GREEN | 14 | up to `top_n` |
| Robotic tone detected | YELLOW | 7 | up to `top_n` |
| Crisis keywords in input | RED | 1 | 1 (emergency_resources) |
| safety_risk=True task found | RED | 1 | 1 (emergency_resources) |

## Testing

16 unit tests in `tests/test_roadmap_endpoint.py`:

| Test Class | Coverage |
|------------|----------|
| `TestRoadmapRequestSchema` | Minimal request, top_n range, answers merging (3 tests) |
| `TestRoadmapResponseSchema` | Minimal response, no legacy fields (2 tests) |
| `TestRoadmapHappyPath` | 200 with tasks + overview, generated_at, version field (3 tests) |
| `TestRoadmapCrisisPath` | Crisis text returns RED status with emergency task (1 test) |
| `TestRoadmapContractSnapshot` | Exact field set validation, no legacy fields leaked (2 tests) |
| `TestRoadmapLocale` | EN/AR locale propagation to orchestrator (2 tests) |
| `TestRoadmapTopN` | top_n=3 limits tasks, top_n=1 single task (2 tests) |
| `TestRoadmapEmptyAnswers` | No answers returns valid roadmap with defaults (1 test) |

Run to verify:

```bash
pytest tests/test_roadmap_endpoint.py -v
```

## Acceptance Criteria

- [x] Happy path returns 200 with tasks array and overview
- [x] Crisis path returns RED payload per Phase 2
- [x] Contract snapshot test prevents accidental field removal

## Integration Points

| Consumer | How it uses the endpoint |
|----------|------------------------|
| New mobile/web clients | `POST /api/roadmap` for clean roadmap without legacy fields |
| Flutter app (legacy) | Continues using `POST /api/assess` with full clinical data |
| Future: A-YAH-15 (14-day E2E) | Calls `/api/roadmap` repeatedly to track roadmap evolution |
