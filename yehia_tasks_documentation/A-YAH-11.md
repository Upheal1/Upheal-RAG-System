# A-YAH-11: POST /api/telemetry

## Task Metadata

| Field      | Value                      |
|------------|----------------------------|
| Task ID    | A-YAH-11                   |
| Owner      | Yahya                      |
| Phase      | Phase 3 — Section 1        |
| File(s)    | `services/telemetry/`      |
| Complexity | M                          |
| Depends On | A-HOZ-10                   |
| Blocks     | A-HOZ-12                   |
| Status     | Completed                  |

## Overview

Implemented a dedicated telemetry microservice for logging user-task interactions to Supabase. The endpoint accepts interaction events (VIEWED, STARTED, COMPLETED, SKIPPED), validates them, and persists to the `interaction_logs` table with optimistic locking.

## What Was Built

### 1. Microservice Structure

Created `services/telemetry/` with the following modules:

| File | Purpose |
|------|---------|
| `__init__.py` | Package marker |
| `schemas.py` | Pydantic models for request/response |
| `service.py` | Business logic for Supabase interaction |
| `router.py` | FastAPI route definition |

### 2. Schemas (`services/telemetry/schemas.py`)

```python
class InteractionType(str, Enum):
    VIEWED = "VIEWED"
    STARTED = "STARTED"
    COMPLETED = "COMPLETED"
    SKIPPED = "SKIPPED"

class TelemetryRequest(BaseModel):
    user_id: UUID
    task_id: UUID
    interaction_type: InteractionType
    completion_time: Optional[int] = Field(default=None, ge=0)
    drop_off_point: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    xp_earned: int = Field(default=0, ge=0)
    dedupe_key: Optional[UUID] = None

class TelemetryResponse(BaseModel):
    log_id: UUID
    user_id: UUID
    task_id: UUID
    interaction_type: InteractionType
    recorded_at: str
    idempotent: bool = False
```

### 3. Service Logic (`services/telemetry/service.py`)

`TelemetryService` class:
- Uses `SupabaseSyncHook` for optimistic-locking inserts
- Implements idempotency via optional `dedupe_key`
- Validates `interaction_type` enum
- Validates `completion_time` (>=0), `drop_off_point` (0.0-1.0), `xp_earned` (>=0)

### 4. Router (`services/telemetry/router.py`)

```python
@router.post(
    "/",
    response_model=TelemetryResponse,
    status_code=status.HTTP_201_CREATED,
)
def log_telemetry(request: TelemetryRequest) -> TelemetryResponse:
```

### 5. Gateway Integration

Added to `services/gateway/main.py`:
```python
from services.telemetry.router import router as telemetry_router
app.include_router(telemetry_router, prefix="/api", tags=["telemetry"])
```

## API Contract

### POST /api/telemetry

**Request:**
```json
{
  "user_id": "550e8400-e29b-41d4-a716-446655440000",
  "task_id": "550e8400-e29b-41d4-a716-446655440001",
  "interaction_type": "COMPLETED",
  "completion_time": 60,
  "drop_off_point": 1.0,
  "xp_earned": 15,
  "dedupe_key": "550e8400-e29b-41d4-a716-446655440002"
}
```

**Response (201):**
```json
{
  "log_id": "550e8400-e29b-41d4-a716-446655440003",
  "user_id": "550e8400-e29b-41d4-a716-446655440000",
  "task_id": "550e8400-e29b-41d4-a716-446655440001",
  "interaction_type": "COMPLETED",
  "recorded_at": "2026-05-06T01:30:00Z",
  "idempotent": false
}
```

**Validation:**
- `user_id`, `task_id`: Valid UUID required
- `interaction_type`: Must be one of VIEWED|STARTED|COMPLETED|SKIPPED
- `completion_time`: Optional, must be >= 0
- `drop_off_point`: Optional, must be 0.0-1.0
- `xp_earned`: Defaults to 0, must be >= 0
- `dedupe_key`: Optional UUID for idempotent logging

## Acceptance Criteria

| Criterion | Status |
|-----------|--------|
| Validates enums VIEWED\|STARTED\|COMPLETED\|SKIPPED | Passes — 5 enum tests |
| Persists user_id from request and server timestamp | Passes — recorded_at set by Supabase |
| Returns 201/200 with idempotent dedupe key | Passes — 201 created, idempotent flag in response |

## Test Coverage

### TestTelemetryRequest (10 tests)
- Valid request with all fields
- Valid request with minimal fields
- All 4 interaction types valid
- Invalid interaction type rejection
- Invalid completion_time (negative)
- Invalid drop_off_point (>1.0)
- Invalid drop_off_point (<0.0)
- Invalid xp_earned (negative)

### TestTelemetryService (3 tests)
- Log interaction success (inserts row)
- Idempotent hit (dedupe_key exists, returns existing)
- New dedupe_key (inserts with custom log_id)

### TestTelemetryResponse (1 test)
- Response creation with all fields

## Files Changed

| File | Action |
|------|--------|
| `services/telemetry/__init__.py` | New |
| `services/telemetry/schemas.py` | New |
| `services/telemetry/service.py` | New |
| `services/telemetry/router.py` | New |
| `services/gateway/main.py` | Added telemetry router |
| `tests/test_telemetry.py` | New |

## How to Run Tests

```bash
pytest tests/test_telemetry.py -v
```

## Integration Notes

- **Supabase dependency**: Requires `UPHEAL_SUPABASE_URL` and `UPHEAL_SUPABASE_KEY` environment variables
- **Database table**: `interaction_logs` (from migration 001)
- **Optimistic locking**: Uses `SupabaseSyncHook` from `services/shared/state.py`
- **Retry backoff**: Uses `retry_with_backoff` for transient failures