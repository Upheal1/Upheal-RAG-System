# UpHeal Deployment Task Plan

**Target:** Fully deployable RAG backend + frontend connectivity by end of day.

**Team:** Hozaifa (H), Yahya (Y), Abdalrahman (A)

**Deploy target:** Railway ($5/mo) · Auth: Supabase · DB: Supabase (PostgreSQL) · Vector: ChromaDB embedded

---

## Quick Legend

| Symbol | Meaning |
|--------|---------|
| 🔴 | Critical — blocks other tasks or deployment |
| 🟡 | Important — needed for production quality |
| 🟢 | Nice-to-have — can ship without |
| ⚠️ | DOUBLE-CHECK — logic that needs verification or further investigation |
| → | Dependency on another task |
| 🔒 | Must be done before deployment goes live |

---

## Phase 1: Backend Security 🔴🔒

> These block every downstream task. Must be done first.

### 1A. RLS Policies — Migration 012 🔴

**Owner:** H  
**Depends on:** Nothing  
**Significance:** Without RLS, anyone with the anon key can read/write every table. This is the single biggest security gap.

**File to create:** `supabase/migrations/012_enable_rls_policies.sql`

**Logic to implement:**

```sql
-- Enable RLS on all user-facing tables
ALTER TABLE users ENABLE ROW LEVEL SECURITY;
ALTER TABLE user_profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE assessment_responses ENABLE ROW LEVEL SECURITY;
ALTER TABLE roadmaps ENABLE ROW LEVEL SECURITY;
ALTER TABLE roadmap_tasks ENABLE ROW LEVEL SECURITY;
ALTER TABLE interaction_logs ENABLE ROW LEVEL SECURITY;
ALTER TABLE roadmap_mutations ENABLE ROW LEVEL SECURITY;
ALTER TABLE interest_profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE chat_sessions ENABLE ROW LEVEL SECURITY;
ALTER TABLE chat_messages ENABLE ROW LEVEL SECURITY;
ALTER TABLE retrieval_logs ENABLE ROW LEVEL SECURITY;
ALTER TABLE xp_transactions ENABLE ROW LEVEL SECURITY;

-- clinical_tasks: read-only for authenticated users
ALTER TABLE clinical_tasks ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Authenticated users can read clinical_tasks"
  ON clinical_tasks FOR SELECT
  TO authenticated
  USING (true);

-- retention_settings: service role only (no anon/authenticated access)
ALTER TABLE retention_settings ENABLE ROW LEVEL SECURITY;
-- No policies = no access for anon/authenticated

-- Users table: read/update own row only
CREATE POLICY "Users can read own row"
  ON users FOR SELECT
  TO authenticated
  USING (auth.uid() = id);

CREATE POLICY "Users can update own row"
  ON users FOR UPDATE
  TO authenticated
  USING (auth.uid() = id);

CREATE POLICY "Users can insert own row"
  ON users FOR INSERT
  TO authenticated
  WITH CHECK (auth.uid() = id);

-- user_profiles: own profile only
CREATE POLICY "Users can read own profile"
  ON user_profiles FOR SELECT
  TO authenticated
  USING (auth.uid() = user_id);

CREATE POLICY "Users can update own profile"
  ON user_profiles FOR UPDATE
  TO authenticated
  USING (auth.uid() = user_id);

CREATE POLICY "Users can insert own profile"
  ON user_profiles FOR INSERT
  TO authenticated
  WITH CHECK (auth.uid() = user_id);

-- assessment_responses: own responses only
CREATE POLICY "Users can read own assessments"
  ON assessment_responses FOR SELECT
  TO authenticated
  USING (auth.uid() = user_id);

CREATE POLICY "Users can insert own assessments"
  ON assessment_responses FOR INSERT
  TO authenticated
  WITH CHECK (auth.uid() = user_id);

-- roadmaps: own roadmaps only
CREATE POLICY "Users can read own roadmaps"
  ON roadmaps FOR SELECT
  TO authenticated
  USING (auth.uid() = user_id);

CREATE POLICY "Users can insert own roadmaps"
  ON roadmaps FOR INSERT
  TO authenticated
  WITH CHECK (auth.uid() = user_id);

-- roadmap_tasks: access via roadmap ownership
CREATE POLICY "Users can access roadmap tasks"
  ON roadmap_tasks FOR ALL
  TO authenticated
  USING (
    roadmap_id IN (
      SELECT id FROM roadmaps WHERE user_id = auth.uid()
    )
  );

-- interest_profiles: own profile only
CREATE POLICY "Users can access own interest profile"
  ON interest_profiles FOR ALL
  TO authenticated
  USING (auth.uid() = user_id);

-- chat_sessions: own sessions only
CREATE POLICY "Users can access own chat sessions"
  ON chat_sessions FOR ALL
  TO authenticated
  USING (auth.uid() = user_id);

-- chat_messages: access via session ownership
CREATE POLICY "Users can access chat messages"
  ON chat_messages FOR ALL
  TO authenticated
  USING (
    session_id IN (
      SELECT id FROM chat_sessions WHERE user_id = auth.uid()
    )
  );

-- interaction_logs: own logs only
CREATE POLICY "Users can read own interaction logs"
  ON interaction_logs FOR SELECT
  TO authenticated
  USING (auth.uid() = user_id);

CREATE POLICY "Users can insert own interaction logs"
  ON interaction_logs FOR INSERT
  TO authenticated
  WITH CHECK (auth.uid() = user_id);

-- xp_transactions: own transactions only
CREATE POLICY "Users can read own XP transactions"
  ON xp_transactions FOR SELECT
  TO authenticated
  USING (auth.uid() = user_id);

-- retrieval_logs: own logs only
CREATE POLICY "Users can insert own retrieval logs"
  ON retrieval_logs FOR INSERT
  TO authenticated
  WITH CHECK (auth.uid() = user_id);
```

**⚠️ DOUBLE-CHECK:**
- Verify `auth.uid()` matches the `user_id` column type (UUID). Supabase Auth creates UUIDs by default.
- Verify the `users` table `id` column is UUID and matches Supabase Auth's `auth.uid()`.
- Roadmap tasks need indirect policy: user can only access tasks if `roadmap_id` belongs to their roadmap (`roadmaps.user_id = auth.uid()`).

**Also update:** `supabase/combined_migrations.sql` (append this migration) and `supabase/README.md` (add row to migration table).

---

### 1B. Startup Environment Validation 🔴

**Owner:** H  
**Depends on:** Nothing (can be done in parallel with 1A)  
**Significance:** App should refuse to start without JWT secret, preventing unauthenticated deployments.

**File to create:** `services/shared/env_validation.py`

```python
"""Environment variable validation for production deployments."""

from __future__ import annotations

import os
import sys

from services.shared.logging import get_logger

logger = get_logger(__name__)

CRITICAL_VARS = ["SUPABASE_JWT_SECRET"]
WARNING_VARS = ["UPHEAL_SUPABASE_URL", "UPHEAL_SUPABASE_KEY"]
INFO_VARS = [
    "UPHEAL_CHROMA_PATH",
    "UPHEAL_CHROMA_COLLECTION",
    "UPHEAL_EMBEDDING_MODEL",
    "HOST",
    "PORT",
    "LOG_LEVEL",
]


def validate_env() -> None:
    """
    Validate critical environment variables on startup.

    - Fails hard (sys.exit) if critical vars are missing
    - Logs warnings if important vars are missing
    - Logs info for all detected configuration
    """
    # Critical: fail hard
    for var in CRITICAL_VARS:
        if not os.getenv(var):
            logger.error("env.validation.critical_missing", var=var)
            sys.exit(f"FATAL: Required environment variable {var} is not set. Refusing to start.")

    # Warnings
    for var in WARNING_VARS:
        if not os.getenv(var):
            logger.warning("env.validation.warning_missing", var=var)

    # Info log
    for var in INFO_VARS:
        val = os.getenv(var, "<not set>")
        logger.info("env.validation.config", var=var, value=val)
```

**File to modify:** `services/gateway/main.py`

```python
from services.shared.env_validation import validate_env

# Add at app startup:
@app.on_event("startup")
async def startup_event():
    validate_env()
```

---

### 1C. Add SUPABASE_JWT_SECRET to All Env Configs 🔴

**Owner:** H  
**Depends on:** 1B (needs the var name to be consistent)  
**Significance:** Without this in configs, deployments will fail on startup.

**Files to modify:**

**.env.example:**
```
# ... existing vars ...
SUPABASE_JWT_SECRET=your-supabase-jwt-secret-here
```

**deployments/.env.example:**
```
# ... existing vars ...
SUPABASE_JWT_SECRET=your-supabase-jwt-secret-here
```

**deployments/docker-compose.yml:**
```yaml
services:
  gateway:
    environment:
      # ... existing vars ...
      - SUPABASE_JWT_SECRET=${SUPABASE_JWT_SECRET:-}
```

**deployments/render.yaml:**
```json
{
  "envVars": [
    // ... existing vars ...
    {
      "key": "SUPABASE_JWT_SECRET",
      "value": "${SUPABASE_JWT_SECRET}",
      "sync": false
    }
  ]
}
```

---

### 1D. Wire Auth on Core Endpoints 🔴🔒

**Owner:** Y  
**Depends on:** 1B (validate_env must run first)  
**Significance:** Without auth on /api/assess and POST /api/roadmap, the API is completely open.

**File to modify:** `services/gateway/main.py`

```python
from services.gateway.auth_middleware import AuthenticatedUser, get_current_user

# Change assess endpoint:
@app.post("/api/assess", response_model=AssessGatewayResponse, tags=["assessment"])
async def assess(
    payload: Dict[str, Any],
    user: AuthenticatedUser = Depends(get_current_user),
) -> AssessGatewayResponse:
    # Use user.user_id from JWT, verify it matches payload["user_id"] for logging
    # ... rest of existing logic ...

# Change roadmap endpoint similarly:
@app.post("/api/roadmap", response_model=RoadmapResponse, tags=["roadmap"])
async def generate_roadmap(
    payload: Dict[str, Any],
    user: AuthenticatedUser = Depends(get_current_user),
) -> RoadmapResponse:
    # ... similar auth check ...
```

**⚠️ DOUBLE-CHECK:**
- After wiring auth, `user_id` must come from `user.user_id` (JWT token), NOT from the request payload. This is a security issue — if we trust `payload["user_id"]`, anyone can impersonate another user.
- The `/health` endpoint stays public (no auth).
- The `/knowledge_base/*`, `/ingestion/*`, `/assessment/*` health endpoints stay public.

---

### 1E. Parameterize CORS 🟡

**Owner:** H  
**Depends on:** Nothing (can be done in parallel)  
**Significance:** `allow_origins=["*"]` is fine for dev but must be locked for production.

**File to modify:** `services/gateway/main.py`

```python
import os
from fastapi.middleware.cors import CORSMiddleware

ALLOWED_ORIGINS = [o.strip() for o in os.getenv("ALLOWED_ORIGINS", "*").split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

---

## Phase 2: 90-Day Roadmap + Re-Assessment Cycle 🔴

> This is the core clinical logic change. The biggest ⚠️ area in the entire plan.

### 2A. Roadmap Schemas 🔴

**Owner:** Y  
**Depends on:** Nothing (can start in parallel)  
**Significance:** All downstream tasks depend on these schemas.

**File to modify:** `services/shared/schemas.py`

**Add:**

```python
class RoadmapDay(BaseModel):
    """
    A single day in a 90-day roadmap.

    - day_number: 1-90
    - task: The assigned clinical task for this day
    - phase: Quick Win / Ladder / Boss
    - day_context: Contextual description for variety (e.g., "morning routine")
    """

    day_number: int = Field(..., ge=1, le=90)
    task: ClinicalTask
    phase: Literal["Quick Win", "Ladder", "Boss"]
    day_context: str = ""  # e.g., "morning routine", "pre-sleep wind-down"


class ReassessmentStatus(BaseModel):
    """Status check for whether user needs to retake assessment."""

    user_id: str
    roadmap_id: Optional[str] = None
    roadmap_status: Optional[str] = None  # ACTIVE, IN_PROGRESS, COMPLETED, EXPIRED
    current_day: Optional[int] = None
    total_days: int = 90
    assessment_required: bool = False
    days_since_last_assessment: Optional[int] = None
```

**File to modify:** `services/gateway/schemas.py`

**Update `RoadmapResponse`:**

```python
class RoadmapResponse(BaseModel):
    """
    Clean roadmap response for `POST /api/roadmap`.
    Contains only the roadmap fields — no legacy clinical probabilities.
    """

    user_id: str
    overview_paragraph: str
    suggested_tasks: List[ClinicalTask] = Field(default_factory=list)
    safety_status: Literal["GREEN", "YELLOW", "RED"]
    next_checkup_days: int
    generated_at: str
    session_id: Optional[str] = None
    version: str = "1.0"
    screen_time_insights: Optional[ScreenTimeInsights] = None
    # NEW FIELDS for 90-day roadmap:
    days: List[RoadmapDay] = Field(default_factory=list)
    total_days: int = 90
    assessment_required: bool = False  # True if past day 90
```

---

### 2B. 90-Day Task Generation Algorithm 🔴⚠️

**Owner:** H  
**Depends on:** 2A (schemas must exist)  
**Significance:** This is the core clinical logic. ⚠️ MUST BE DOUBLE-CHECKED.

**File to modify:** `services/architect/pipeline.py`

**Add new function:**

```python
def generate_ninety_day_plan(
    candidates: List[ClinicalTask],
    user_context: UserContext,
    total_days: int = 90,
) -> List[RoadmapDay]:
    """
    Generate a 90-day roadmap with 1 task per day.

    Phase allocation:
      Days 1-7   → Quick Win  (difficulty 1-2)
      Days 8-30  → Ladder     (difficulty 3)
      Days 31-90 → Boss       (difficulty 4-5)

    When unique tasks are exhausted within a phase, repeat with
    day-specific context labels to give each repetition a fresh lens.
    """
    PHASES = [
        ("Quick Win", 1, 7, [1, 2]),    # days 1-7, difficulty 1-2
        ("Ladder", 8, 30, [3]),           # days 8-30, difficulty 3
        ("Boss", 31, 90, [4, 5]),         # days 31-90, difficulty 4-5
    ]

    DAY_CONTEXTS = [
        "morning routine",
        "midday check-in",
        "evening wind-down",
        "stress relief",
        "focus boost",
        "pre-sleep calm",
        "weekend reset",
        "commute companion",
        "mindful break",
    ]

    days = []
    for phase_name, start_day, end_day, difficulties in PHASES:
        phase_candidates = [t for t in candidates if t.difficulty in difficulties]

        # Fallback: if no candidates match this phase's difficulty,
        # use all candidates (don't leave days empty)
        if not phase_candidates:
            phase_candidates = list(candidates)

        day_in_phase = 0
        for day_num in range(start_day, end_day + 1):
            # Cycle through candidates with rotation
            idx = day_in_phase % len(phase_candidates)
            task = phase_candidates[idx]

            # Apply day context for variety when repeating
            context_idx = day_in_phase % len(DAY_CONTEXTS)

            days.append(
                RoadmapDay(
                    day_number=day_num,
                    task=task,
                    phase=phase_name,
                    day_context=DAY_CONTEXTS[context_idx],
                )
            )
            day_in_phase += 1

    return days
```

**⚠️ DOUBLE-CHECK LOGIC — NEEDS VERIFICATION:**

1. **Phase boundaries:** Is 7 days for Quick Win, 23 for Ladder, 60 for Boss the right clinical split? Consult with clinical team if possible.
2. **Task repetition:** When we cycle through tasks within a phase, are day contexts ("morning routine", "evening wind-down") sufficient to differentiate? Or should we add more context variety?
3. **Empty phase handling:** If ChromaDB returns 0 tasks for a difficulty level (e.g., no difficulty 4-5 tasks), we fall back to using ALL candidates. Is this clinically acceptable?
4. **Difficulty progression:** Should difficulty ramp smoothly (day 1 → difficulty 1, day 90 → difficulty 5) rather than phase-based jumps?
5. **Safety override:** If `safety_risk=True` on any task, should it be excluded from the Boss phase? The auditor already handles RED/YELLOW safety status, but individual task safety_risk should be reviewed.
6. **Re-assessment trigger:** After day 90, the user MUST retake GAD-7/PHQ-9. The frontend should not allow skipping this. Verify this is enforced on both backend (roadmap status = EXPIRED → assessment_required = true) and frontend (redirect to form).
7. **Day counting:** How should `current_day` increment? Option A: Based on calendar days since roadmap creation. Option B: Based on completed tasks (interaction_logs with COMPLETED status). **Recommendation:** Calendar days (simpler, more predictable for clinical compliance).

**⚠️ CRITICAL QUESTION FOR FURTHER INVESTIGATION:**
- What happens if the user's severity improves during the 90 days? Should the roadmap dynamically adjust (Director override already exists for this), or stay static until the next assessment cycle? Current architecture supports dynamic overrides via `roadmap_mutations`, but the 90-day plan is static. This needs a design decision.

---

### 2C. 90-Day Roadmap in Orchestrator 🔴

**Owner:** H  
**Depends on:** 2A, 2B  
**Significance:** Wires the 90-day plan into the main assessment response.

**File to modify:** `services/gateway/orchestrator.py`

- Call `generate_ninety_day_plan` after `_run_architect`
- Include `days` list in the response
- Set `next_checkup_days` based on phase (7 for Quick Win phase, 30 for Ladder, etc.)
- Update `FinalRoadmap` to include `days` field

---

### 2D. Roadmap Status + Re-Assessment Endpoint 🔴

**Owner:** Y  
**Depends on:** 1D (auth must be wired), 2A (schemas)  
**Significance:** Frontend needs this to know if user must retake the assessment.

**File to modify:** `services/roadmap/router.py`

**Add:**

```python
@router.get("/{user_id}/status", response_model=ReassessmentStatus)
async def get_roadmap_status(
    user_id: str,
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> ReassessmentStatus:
    """
    Check if user needs to retake the assessment.

    Returns assessment_required=True if:
    - No active roadmap exists
    - Current day >= 90
    - Roadmap status is COMPLETED or EXPIRED
    """
    # Verify user can only access their own status
    if str(current_user.user_id) != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot access other user's roadmap status",
        )

    hook = SupabaseSyncHook("roadmaps")

    # Get most recent roadmap
    result = (
        hook.client.table("roadmaps")
        .select("*")
        .eq("user_id", user_id)
        .order("valid_from", desc=True)
        .limit(1)
        .execute()
    )

    if not result.data:
        return ReassessmentStatus(
            user_id=user_id,
            assessment_required=True,
            days_since_last_assessment=None,
        )

    roadmap = result.data[0]
    valid_from = datetime.fromisoformat(roadmap["valid_from"].replace("Z", "+00:00"))
    days_since = (datetime.now(timezone.utc) - valid_from).days + 1
    current_day = min(days_since, 90)
    assessment_required = (
        current_day >= 90 or
        roadmap["status"] in ["COMPLETED", "EXPIRED"]
    )

    return ReassessmentStatus(
        user_id=user_id,
        roadmap_id=roadmap["id"],
        roadmap_status=roadmap["status"],
        current_day=current_day,
        total_days=90,
        assessment_required=assessment_required,
        days_since_last_assessment=days_since,
    )
```

**⚠️ DOUBLE-CHECK:**
- Edge case: what if user has no roadmap at all (first time)? → `assessment_required = True`
- Edge case: what if roadmap creation fails? → should still return `assessment_required = True`
- The `current_day` calculation: `(now - roadmap.valid_from).days + 1`

---

### 2E. Supabase Migration for 90-Day Roadmap 🟡

**Owner:** Y  
**Depends on:** 1A (RLS must exist first)  
**Significance:** Schema change needed for persistent 90-day roadmaps.

**File to create:** `supabase/migrations/013_roadmap_ninety_day.sql`

```sql
-- Add total_days and current_day to roadmaps table
ALTER TABLE roadmaps ADD COLUMN IF NOT EXISTS total_days INT DEFAULT 90;
ALTER TABLE roadmaps ADD COLUMN IF NOT EXISTS current_day INT DEFAULT 1;

-- Note: The roadmap_status enum already has the needed values
-- ACTIVE, COMPLETED, EXPIRED, SUPERSEDED
-- No enum changes needed

-- Trigger to auto-create user profile on signup (missing from 003 migration)
-- Create this if it doesn't exist
CREATE OR REPLACE FUNCTION public.handle_new_user()
RETURNS TRIGGER AS $$
BEGIN
    INSERT INTO public.users (id, email, created_at, updated_at)
    VALUES (new.id, new.email, now(), now());

    INSERT INTO public.user_profiles (user_id, created_at, updated_at)
    VALUES (new.id, now(), now());

    RETURN NEW;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Create trigger on auth.users if not exists
DROP TRIGGER IF EXISTS on_auth_user_created ON auth.users;
CREATE TRIGGER on_auth_user_created
    AFTER INSERT ON auth.users
    FOR EACH ROW
    EXECUTE FUNCTION public.handle_new_user();
```

**Also update:** `supabase/combined_migrations.sql` and `supabase/README.md`.

---

## Phase 3: Screen Time Per-App Percentages 🟡

### 3A. Schema Changes for Per-App Breakdown

**Owner:** Y  
**Depends on:** Nothing (can start in parallel with Phase 1)  
**Significance:** Better personalization with app-level data.

**File to modify:** `services/shared/schemas.py`

**Changes:**

```python
class ScreenTimeAppUsage(BaseModel):
    """Per-app screen time usage data."""

    packageName: str
    usageTime: int = 0  # minutes
    category: str = "other"
    percentage: float = 0.0  # NEW: % of total screen time


class AppPercentage(BaseModel):
    """Single app's percentage of total screen time."""

    packageName: str
    percentage: float
    category: str


class ScreenTimeInsights(BaseModel):
    """Screen time insights for response payload."""

    totalMinutes: float = 0.0
    socialRatio: float = 0.0
    productivityRatio: float = 0.0
    topSocialApps: List[str] = Field(default_factory=list)
    topProductivityApps: List[str] = Field(default_factory=list)
    appBreakdown: List[AppPercentage] = Field(default_factory=list)  # NEW
```

---

### 3B. Compute Per-App Percentages

**Owner:** Y  
**Depends on:** 3A (schemas)  
**Significance:** The actual computation logic.

**File to modify:** `services/assessment/core.py`

In `parse_screen_time_data()`:

```python
def parse_screen_time_data(data: ScreenTimeData) -> dict:
    """
    Parse rich Flutter screen time data into derived metrics.

    Returns per-app percentages and enhanced R_app.
    """
    total = data.totalMinutes

    if total <= 0:
        return {
            "total_minutes": 0.0,
            "social_ratio": 0.0,
            "productivity_ratio": 0.0,
            "top_social_apps": [],
            "top_productivity_apps": [],
            "enhanced_r_app": 0.0,
            "app_breakdown": [],
        }

    # Compute per-app percentages
    app_breakdown = []
    for app in data.dailyUsage:
        pct = (app.usageTime / total) * 100 if total > 0 else 0
        app.percentage = round(pct, 1)
        app_breakdown.append(
            AppPercentage(
                packageName=app.packageName,
                percentage=app.percentage,
                category=app.category.lower(),  # Normalize to lowercase
            )
        )

    # Sort by percentage descending
    app_breakdown.sort(key=lambda x: x.percentage, reverse=True)

    # Extract top social/productivity apps
    top_social = [
        app.packageName
        for app in data.dailyUsage
        if app.category.lower() == "social"
    ]
    top_social.sort(
        key=lambda name: next(
            (a.usageTime for a in data.dailyUsage if a.packageName == name), 0
        ),
        reverse=True,
    )[:5]

    top_productivity = [
        app.packageName
        for app in data.dailyUsage
        if app.category.lower() == "productivity"
    ]
    top_productivity.sort(
        key=lambda name: next(
            (a.usageTime for a in data.dailyUsage if a.packageName == name), 0
        ),
        reverse=True,
    )[:5]

    base_r = sigmoid_r_app(total, threshold_minutes=60.0)

    social_ratio = data.social_ratio
    productivity_ratio = data.productivity_ratio
    enhanced_r = base_r + (social_ratio * 0.15) - (productivity_ratio * 0.10)
    enhanced_r = max(0.0, min(1.0, enhanced_r))

    return {
        "total_minutes": total,
        "social_ratio": social_ratio,
        "productivity_ratio": productivity_ratio,
        "top_social_apps": top_social,
        "top_productivity_apps": top_productivity,
        "enhanced_r_app": enhanced_r,
        "app_breakdown": app_breakdown,
    }
```

**⚠️ DOUBLE-CHECK:**
- Frontend sends `usageTime` in **minutes** (confirmed from `AppUsage.toJson()` in Flutter: `'usageTime': usageTime.inMinutes`). Verify this matches the backend's expectation (`ScreenTimeAppUsage.usageTime` — currently documented as int, which aligns).
- Frontend `ScreenTimeModel.dailyUsage` uses categories: `"Social"`, `"Productivity"`, `"Entertainment"`, etc. Backend `ScreenTimeAppUsage.category` expects lowercase. **Need to normalize case** — add `.lower()` when parsing.

---

### 3C. Use Per-App Data in Architect Scoring

**Owner:** H  
**Depends on:** 3B  
**Significance:** This is where personalization actually happens.

**File to modify:** `services/architect/pipeline.py`

**Logic change in `_triple_threat_score`:**

```python
def _calculate_social_heavy_penalty(app_breakdown: List[AppPercentage]) -> float:
    """
    If social apps > 30% of total screen time, return boost factor.
    If productivity apps > 50%, return reduced boost factor.
    """
    total_social_pct = sum(
        app.percentage
        for app in app_breakdown
        if app.category == "social"
    )

    total_productivity_pct = sum(
        app.percentage
        for app in app_breakdown
        if app.category == "productivity"
    )

    if total_social_pct > 30.0:
        return 1.15  # Boost detox by 15%
    elif total_productivity_pct > 50.0:
        return 0.85  # Reduce detox boost by 15%
    else:
        return 1.0


def rerank_tasks(
    tasks: Sequence[ClinicalTask],
    user_context: UserContext,
    *,
    top_n: int = 5,
    boost_digital_detox: bool = False,
) -> List[ClinicalTask]:
    r_app = float(user_context.app_exposure_ratios.get("r_app", 0.0))

    # Calculate social/prod penalty from app breakdown
    app_breakdown = []
    if user_context.screen_time_data:
        parsed = parse_screen_time_data(user_context.screen_time_data)
        app_breakdown = parsed["app_breakdown"]

    social_penalty = _calculate_social_heavy_penalty(app_breakdown)

    scored: List[Tuple[float, ClinicalTask]] = []
    for task in tasks:
        sim = float(task.metadata.get("similarity", 0.0))
        form_weight = _form_weight_from_context(user_context, task)
        utility_score = getattr(task, "utility_score", 0.5)
        base_score = _triple_threat_score(
            similarity=sim,
            form_weight=form_weight,
            r_app=r_app,
            utility_score=utility_score,
        )

        # Apply detox boost with social penalty
        if boost_digital_detox:
            final_score = _apply_detox_boost(base_score * social_penalty, task, boost_digital_detox)
        else:
            final_score = base_score

        scored.append((final_score, task))

    scored.sort(key=lambda x: (x[0], -x[1].difficulty, x[1].task_id), reverse=True)

    n = max(1, int(top_n))
    top_with_scores = scored[:n]
    top_tasks = [t for _, t in top_with_scores]
    for t, (score, _) in zip(top_tasks, top_with_scores):
        t.metadata["triple_threat_score"] = float(score)
    return top_tasks
```

**⚠️ DOUBLE-CHECK:**
- The thresholds (30% social = detox boost, 50% productivity = reduce detox) are assumptions. These need clinical validation.
- The category names from frontend (`"Social"`, `"Productivity"`, `"Entertainment"`) must be normalized to match the backend's `_DETOX_BOOST_TAGS`.

---

## Phase 4: Frontend Supabase Auth + API Connectivity 🔴🔒

> These tasks are for Abdalrahman on the frontend repo: https://github.com/Upheal1/frontend

### 4A. Add Supabase Flutter Package

**Owner:** A  
**Depends on:** 1D (backend auth must be ready to accept Supabase JWT)  
**Significance:** Required for all auth changes.

**File to modify:** `pubspec.yaml`

```yaml
dependencies:
  supabase_flutter: ^2.6.0
  # KEEP firebase_core and firebase_auth temporarily until migration is verified
```

**Create:** `lib/services/supabase_service.dart`

```dart
import 'package:supabase_flutter/supabase_flutter.dart';

class SupabaseService {
  static SupabaseClient get client => Supabase.instance.client;

  static Future<void> initialize({
    required String url,
    required String anonKey,
  }) async {
    await Supabase.initialize(url: url, anonKey: anonKey);
  }

  static String? get currentUserId => client.auth.currentUser?.id;
  static Future<String?> get idToken async =>
      client.auth.currentSession?.accessToken;

  /// Auth state stream for AuthWrapper
  static Stream<AuthState> get authStateStream =>
      client.auth.onAuthStateChange;
}
```

---

### 4B. Create Auth Service (Supabase Wrapper)

**Owner:** A  
**Depends on:** 4A  
**Significance:** Replaces Firebase Auth throughout the app.

**Create:** `lib/services/auth_service.dart`

```dart
import 'package:supabase_flutter/supabase_flutter.dart';

class AuthService {
  final SupabaseClient _client = Supabase.instance.client;

  Future<AuthResponse> signIn(String email, String password) async {
    return await _client.auth.signInWithPassword(
      email: email,
      password: password,
    );
  }

  Future<AuthResponse> signUp(String email, String password) async {
    return await _client.auth.signUp(
      email: email,
      password: password,
    );
  }

  Future<void> signOut() async {
    await _client.auth.signOut();
  }

  Stream<AuthState> get authStateStream => _client.auth.onAuthStateChange;
  String? get currentUserId => _client.auth.currentUser?.id;
  Future<String?> get idToken async =>
      _client.auth.currentSession?.accessToken;
}
```

**⚠️ DOUBLE-CHECK:**
- Supabase Auth uses email/password by default. Verify the current Firebase Auth flow supports this, or if phone auth /OAuth providers are needed.
- After sign-up, Supabase creates a user in `auth.users`. The `users` table in our schema needs a trigger to auto-create a row there (handled in task 2E).

---

### 4C. Update upheal_api.dart — Add Auth Headers + New Endpoints

**Owner:** A  
**Depends on:** 4A (Supabase initialized for token)  
**Significance:** Without auth headers, all API calls will return 401.

**File to modify:** `lib/services/upheal_api.dart`

**Changes:**

```dart
import '../services/supabase_service.dart';

class UphealApi {
  final String baseUrl;
  const UphealApi({required this.baseUrl});

  Uri _uri(String path) => Uri.parse('$baseUrl$path');

  /// Get auth headers with JWT token
  Future<Map<String, String>> _getHeaders() async {
    final token = await SupabaseService.idToken;
    return {
      'Content-Type': 'application/json',
      if (token != null) 'Authorization': 'Bearer $token',
    };
  }

  /// Call assessment endpoint with auth headers
  Future<Map<String, dynamic>> assess({
    required Map<String, int> answers,
    required String userId,
    String? sessionId,
    Map<String, dynamic>? screenTimeData,
  }) async {
    final headers = await _getHeaders();
    final payload = <String, dynamic>{
      'answers': answers,
      'user_id': userId,
    };
    if (sessionId != null) payload['session_id'] = sessionId;
    if (screenTimeData != null) payload['screenTimeData'] = screenTimeData;

    final response = await http.post(
      _uri('/api/assess'),
      headers: headers,
      body: jsonEncode(payload),
    ).timeout(const Duration(seconds: 30));

    if (response.statusCode != 200) {
      throw Exception('Assessment failed (${response.statusCode})');
    }
    return jsonDecode(response.body);
  }

  /// Get roadmap status (check if reassessment needed)
  Future<Map<String, dynamic>> roadmapStatus(String userId) async {
    final headers = await _getHeaders();
    final response = await http.get(
      _uri('/api/roadmap/$userId/status'),
      headers: headers,
    );

    if (response.statusCode != 200) {
      throw Exception('Failed to get roadmap status (${response.statusCode})');
    }
    return jsonDecode(response.body);
  }

  /// Generate new roadmap
  Future<Map<String, dynamic>> roadmap({
    required String userId,
    required Map<String, int> answers,
    Map<String, dynamic>? screenTimeData,
    int? topN,
  }) async {
    final headers = await _getHeaders();
    final payload = <String, dynamic>{
      'user_id': userId,
      'answers': answers,
    };
    if (screenTimeData != null) payload['screenTimeData'] = screenTimeData;
    if (topN != null) payload['top_n'] = topN;

    final response = await http.post(
      _uri('/api/roadmap'),
      headers: headers,
      body: jsonEncode(payload),
    );

    if (response.statusCode != 200) {
      throw Exception('Failed to generate roadmap (${response.statusCode})');
    }
    return jsonDecode(response.body);
  }
}
```

**⚠️ DOUBLE-CHECK:**
- If token is expired, Supabase Flutter SDK auto-refreshes. Verify this works in practice.
- The `user_id` should come from the JWT token on the backend side (task 1D), NOT from the payload. Frontend can still send it for logging, but backend should verify it matches the JWT's `sub` claim.

---

### 4D. Update main.dart — Replace Firebase Init with Supabase

**Owner:** A  
**Depends on:** 4A, 4B  
**Significance:** Core app initialization.

**File to modify:** `lib/main.dart`

```dart
// OLD:
// await Firebase.initializeApp(options: DefaultFirebaseOptions.currentPlatform);

// NEW:
await SupabaseService.initialize(
  url: SUPABASE_URL,
  anonKey: SUPABASE_ANON_KEY,
);
```

**Also update:** `AuthWrapper` — replace `FirebaseAuth.instance.authStateChanges()` with Supabase auth state stream:

```dart
class AuthWrapper extends StatefulWidget {
  const AuthWrapper({super.key});

  @override
  State<AuthWrapper> createState() => _AuthWrapperState();
}

class _AuthWrapperState extends State<AuthWrapper> {
  @override
  Widget build(BuildContext context) {
    return StreamBuilder<AuthState>(
      stream: SupabaseService.authStateStream,
      builder: (context, snapshot) {
        final session = snapshot.data?.session;
        if (session != null) {
          return const RootNav();
        } else {
          return const LoginScreen();
        }
      },
    );
  }
}
```

**⚠️ DOUBLE-CHECK:**
- The `firebase_options.dart` file can be removed only after ALL Firebase references are gone.
- Check for any `FirebaseAuth.instance.currentUser` references in screens other than `main.dart` and `login_screen.dart`.

---

### 4E. Update login_screen.dart — Supabase Auth

**Owner:** A  
**Depends on:** 4B  
**Significance:** Login flow must work with Supabase.

**Replace in `_GadPhqFormScreenState._onSubmitPressed` and similar auth locations:**

```dart
// OLD:
// final userId = FirebaseAuth.instance.currentUser?.uid ?? 'anonymous';

// NEW:
final userId = AuthService().currentUserId ?? 'anonymous';
```

**In login screen:**

```dart
// OLD:
// await FirebaseAuth.instance.signInWithEmailAndPassword(email, password);

// NEW:
await AuthService().signIn(email, password);
```

```dart
// OLD:
// await FirebaseAuth.instance.createUserWithEmailAndPassword(email, password);

// NEW:
await AuthService().signUp(email, password);
```

```dart
// OLD:
// await FirebaseAuth.instance.signOut();

// NEW:
await AuthService().signOut();
```

---

### 4F. Update gad_phq_form_screen.dart — Auth ID + Screen Time

**Owner:** A  
**Depends on:** 4C, 4E  
**Significance:** Assessment must use real user ID and pass screen time data.

**Changes:**

```dart
Future<void> _onSubmitPressed(BuildContext context) async {
  // ... existing code ...

  // 1. Use Supabase user ID
  final userId = AuthService().currentUserId ?? 'anonymous';

  // 2. Get ScreenTimeModel and build screen time data
  final screenTimeModel = context.read<ScreenTimeModel>();
  final screenTimeData = {
    'totalMinutes': screenTimeModel.totalScreenTime.inMinutes.toDouble(),
    'socialMinutes': screenTimeModel.categoryUsage['Social']?.inMinutes.toDouble() ?? 0.0,
    'productivityMinutes': screenTimeModel.categoryUsage['Productivity']?.inMinutes.toDouble() ?? 0.0,
    'dailyUsage': screenTimeModel.dailyUsage.map((app) => {
      'packageName': app.packageName,
      'usageTime': app.usageTime.inMinutes,
      'category': app.category.toLowerCase(),  // IMPORTANT: lowercase for backend
    }).toList(),
  };

  // 3. Call API with screen time data
  Map<String, dynamic>? results;
  try {
    final api = UphealApi(baseUrl: uphealBaseUrl);
    results = await api.assess(
      answers: answers,
      userId: userId,
      screenTimeData: screenTimeData,
    );
    debugPrint('RAG API response received: $results');
  } catch (e) {
    debugPrint('RAG API call failed: $e');
    // ... show snackbar error ...
  }

  // ... rest of existing logic ...
}
```

**⚠️ DOUBLE-CHECK:**
- `screenTimeModel.categoryUsage` keys are `"Social"`, `"Productivity"`, `"Entertainment"` (capitalized). Backend expects lowercase. Must add `.toLowerCase()`.
- `app.usageTime` is a `Duration` — convert to minutes with `.inMinutes`.
- Verify the frontend has access to `ScreenTimeModel` data at the point of form submission (it should be available via Provider).

---

### 4G. Replace Firestore Calls with Supabase

**Owner:** A  
**Depends on:** 4A, 4B  
**Significance:** Data must live in Supabase, not Firestore.

**Replace all `FirebaseFirestore.instance.collection(...)` calls:**

| Firestore collection | Supabase table | Notes |
|---------------------|---------------|-------|
| `clinical_assessments` | `assessment_responses` | Use Supabase client to insert |
| `users` | `users` + `user_profiles` | Supabase Auth creates `auth.users`, trigger auto-creates `public.users` |

**Example replacement:**

```dart
// OLD:
await FirebaseFirestore.instance
    .collection('clinical_assessments')
    .add({
      'answers': answers,
      'created_at': DateTime.now().toIso8601String(),
      'user_id': userId,
    });

// NEW:
await SupabaseService.client
    .from('assessment_responses')
    .insert({
      'user_id': userId,
      'form_payload': {'answers': answers},
      'gad7_score': gadTotal,
      'phq9_score': phqTotal,
      'recorded_at': DateTime.now().toIso8601String(),
    });
```

**⚠️ DOUBLE-CHECK:**
- Need a Supabase trigger to auto-create a row in `public.users` when a new user signs up via Supabase Auth. This trigger is created in task 2E.

---

### 4H. Wire journal_api_service.dart to Real Backend

**Owner:** A  
**Depends on:** 4C (auth headers)  
**Significance:** Journal CRUD currently fails silently (placeholder URL).

**Replace in `lib/services/journal_api_service.dart`:**

```dart
import '../config.dart';  // Imports API_BASE_URL

class JournalApiService {
  final Dio _dio;

  JournalApiService({Dio? dio})
      : _dio = dio ?? Dio(BaseOptions(
            baseUrl: API_BASE_URL,  // = 'https://api.example.com'  <-- FIXED!
            connectTimeout: const Duration(seconds: 30),
            receiveTimeout: const Duration(seconds: 30),
          )) {
    // Add auth interceptor
    _dio.interceptors.add(InterceptorsWrapper(
      onRequest: (options, handler) async {
        final token = await AuthService().idToken;
        if (token != null) {
          options.headers['Authorization'] = 'Bearer $token';
        }
        handler.next(options);
      },
    ));
  }

  // Endpoints: POST /journal, GET /journal, GET /journal/{id}, PUT /journal/{id}, DELETE /journal/{id}
}
```

---

### 4I. Update config.dart

**Owner:** A  
**Depends on:** Nothing (can be done immediately)  
**Significance:** Without real URLs, nothing connects.

**Create/Update:** `lib/config.dart`

```dart
// Supabase Configuration
const String SUPABASE_URL = String.fromEnvironment(
  'SUPABASE_URL',
  defaultValue: 'https://gcxxmjptbyvlabqzcprv.supabase.co',
);

const String SUPABASE_ANON_KEY = String.fromEnvironment(
  'SUPABASE_ANON_KEY',
  defaultValue: '',
);

// API Configuration
const String API_BASE_URL = String.fromEnvironment(
  'UPHEAL_API_URL',
  defaultValue: 'https://upheal-gateway.up.railway.app',
);
```

---

### 4J. Remove Firebase Dependencies (AFTER 4A-4G are verified)

**Owner:** A  
**Depends on:** 4A, 4B, 4D, 4E, 4G  
**Significance:** Cleanup — remove unused packages.

**Remove from `pubspec.yaml`:**

```yaml
# REMOVE:
# firebase_core: ^4.2.1
# firebase_auth: ^6.1.2
# cloud_firestore: ^6.1.1
```

**Delete:** `lib/firebase_options.dart`

**⚠️ ONLY do this after confirming Supabase Auth works end-to-end.**

---

## Phase 5: Railway Deployment 🔴🔒

### 5A. Update railway.json with All Env Vars

**Owner:** H  
**Depends on:** 1A-1E, 2A-2E, 3A-3C  
**Significance:** Can't deploy without correct config.

**File to modify:** `deployments/railway.json`

```json
{
  "$schema": "https://railway.app/schema.json",
  "build": {
    "builder": "DOCKERFILE",
    "dockerfilePath": "deployments/Dockerfile"
  },
  "deploy": {
    "numReplicas": 1,
    "restartPolicyType": "ON_FAILURE",
    "restartPolicyMaxRetries": 10
  },
  "services": [
    {
      "name": "gateway",
      "source": ".",
      "dockerfile": "deployments/Dockerfile",
      "port": 8000,
      "healthCheckPath": "/health",
      "environment": [
        {
          "key": "SUPABASE_JWT_SECRET",
          "value": "${SUPABASE_JWT_SECRET}"
        },
        {
          "key": "UPHEAL_SUPABASE_URL",
          "value": "https://gcxxmjptbyvlabqzcprv.supabase.co"
        },
        {
          "key": "UPHEAL_SUPABASE_KEY",
          "value": "${UPHEAL_SUPABASE_KEY}"
        },
        {
          "key": "UPHEAL_CHROMA_PATH",
          "value": "./data/vector_db_mini_enriched"
        },
        {
          "key": "UPHEAL_CHROMA_COLLECTION",
          "value": "clinical_rag_mini_enriched"
        },
        {
          "key": "UPHEAL_EMBEDDING_MODEL",
          "value": "all-mpnet-base-v2"
        },
        {
          "key": "ALLOWED_ORIGINS",
          "value": "*"
        },
        {
          "key": "LOG_LEVEL",
          "value": "INFO"
        },
        {
          "key": "PYTHONPATH",
          "value": "/app"
        }
      ]
    }
  ]
}
```

---

### 5B. Set Railway Secrets

**Owner:** H  
**Depends on:** 5A  
**Significance:** Secrets must not be in code.

Set in Railway dashboard:

| Variable | Source |
|----------|--------|
| `SUPABASE_JWT_SECRET` | Supabase Dashboard → Settings → API → JWT Secret |
| `UPHEAL_SUPABASE_KEY` | Supabase Dashboard → Settings → API → service_role key |

---

### 5C. Run Supabase Migrations

**Owner:** H  
**Depends on:** 1A (RLS), 2E (90-day migration)  
**Significance:** Database schema must be up to date.

```bash
# From the repo root
supabase db push

# Or manually if needed:
psql $SUPABASE_DB_URL -f supabase/migrations/012_enable_rls_policies.sql
psql $SUPABASE_DB_URL -f supabase/migrations/013_roadmap_ninety_day.sql
```

**⚠️ DOUBLE-CHECK:**
- Run migrations in order: 001-011 (already applied), then 012, 013.
- Verify no errors on RLS policies.
- Test RLS by connecting with anon key and verifying read/write restrictions.

---

### 5D. Deploy and Test

**Owner:** H  
**Depends on:** 5A, 5B, 5C  
**Significance:** The final deployment.

**Test checklist:**

```bash
# 1. Health check
curl https://upheal-gateway.up.railway.app/health
# Should return: {"status": "ok", "knowledge_base_healthy": true, ...}

# 2. Auth required test
curl -X POST https://upheal-gateway.up.railway.app/api/assess \
  -H "Content-Type: application/json" \
  -d '{"user_id": "test", "answers": {"gad7_q1": 0}}'
# Should return: 401 Unauthorized

# 3. Full assessment with auth (use a real Supabase JWT)
curl -X POST https://upheal-gateway.up.railway.app/api/assess \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <valid-supabase-jwt>" \
  -d '{
    "user_id": "test-user-id",
    "answers": {
      "gad7_q1": 2, "gad7_q2": 1, "gad7_q3": 2, "gad7_q4": 1, "gad7_q5": 2, "gad7_q6": 1, "gad7_q7": 2,
      "phq9_q1": 1, "phq9_q2": 2, "phq9_q3": 1, "phq9_q4": 2, "phq9_q5": 1, "phq9_q6": 2, "phq9_q7": 1, "phq9_q8": 2, "phq9_q9": 1
    },
    "screenTimeData": {
      "totalMinutes": 180.0,
      "socialMinutes": 72.0,
      "productivityMinutes": 36.0,
      "dailyUsage": [
        {"packageName": "com.instagram.android", "usageTime": 85, "category": "social"},
        {"packageName": "com.whatsapp", "usageTime": 52, "category": "social"},
        {"packageName": "com.microsoft.teams", "usageTime": 30, "category": "productivity"}
      ]
    }
  }'
# Should return: 200 OK with 90-day roadmap

# 4. Test roadmap status endpoint
curl https://upheal-gateway.up.railway.app/api/roadmap/test-user-id/status \
  -H "Authorization: Bearer <valid-supabase-jwt>"
# Should return: roadmap status, current_day, assessment_required

# 5. Verify ChromaDB loads (response should include vector DB document count)
# Already included in /health response
```

---

## Phase 6: Production Hardening 🟡

### 6A. Lock CORS

**Owner:** H  
**Depends on:** 5D (deploy verified)  
After frontend URL is known, set `ALLOWED_ORIGINS` to the actual domain.

**Example:**
```
ALLOWED_ORIGINS=https://upheal.app,https://upheal-frontend.netlify.app
```

---

### 6B. Add Rate Limiting

**Owner:** Y  
**Depends on:** 1D  
Add `slowapi` to requirements.txt. Apply 10 req/min to `/api/assess`.

**File to modify:** `services/gateway/main.py`

```python
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)

app.state.limiter = limiter

@app.post("/api/assess")
@limiter.limit("10/minute")
async def assess(...):
    ...
```

**File to modify:** `requirements.txt`

```
slowapi>=0.1.9
```

---

### 6C. Scale Uvicorn Workers

**Owner:** H  
**Depends on:** 5D  
Change Dockerfile CMD to use multiple workers.

**File to modify:** `deployments/Dockerfile`

```dockerfile
# OLD:
# CMD ["python", "-m", "uvicorn", "services.gateway.main:app", "--host", "0.0.0.0", "--port", "8000"]

# NEW:
CMD ["python", "-m", "uvicorn", "services.gateway.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
```

---

## ⚠️ DOUBLE-CHECK ITEMS — REQUIRES FURTHER INVESTIGATION

| # | Item | Owner | Why it needs verification |
|---|------|-------|---------------------------|
| DC-1 | 90-day phase boundaries (7/23/60 days) | H | Clinical validity — is this the right split? |
| DC-2 | Task repetition algorithm | H | When unique tasks < 90 days, are day-context labels enough differentiation? |
| DC-3 | Social/detox boost thresholds (30% social, 50% productivity) | H | These are assumptions, not clinically validated |
| DC-4 | `current_day` calculation method | Y | Calendar days vs task completion — which? Recommendation: calendar days |
| DC-5 | Supabase Auth → `public.users` auto-create trigger | H | Need migration 014 for this. Users table must auto-populate on signup. |
| DC-6 | Frontend category case mismatch | A | Frontend sends `"Social"`, backend expects `"social"`. Must normalize. |
| DC-7 | `user_id` from JWT vs payload | Y | Backend must use JWT `sub` claim, not payload `user_id`. Security issue. |
| DC-8 | Roadmap re-assessment enforcement | A | Frontend must redirect to form, not allow skipping |
| DC-9 | Empty phase fallback (no tasks matching difficulty) | H | Current fallback uses all candidates. Is this acceptable? |
| DC-10 | Chat service placeholder | H | `services/chat/service.py:_generate_response` returns hardcoded text. Not blocking but noted. |

---

## Task Assignment Summary

| Owner | Tasks | Total Est. Time |
|-------|-------|-----------------|
| **Hozaifa (H)** | 1A, 1B, 1C, 1E, 2B, 2C, 3C, 5A, 5B, 5C, 5D, 6A, 6C, DC-5 | ~6 hours |
| **Yahya (Y)** | 1D, 2A, 2D, 2E, 3A, 3B, 6B, DC-7 | ~5 hours |
| **Abdalrahman (A)** | 4A, 4B, 4C, 4D, 4E, 4F, 4G, 4H, 4I, 4J, DC-6, DC-8 | ~6 hours |

---

## Critical Path for Completion

The minimum set of tasks that must be completed for deployment:

1. **H: 1A** (RLS Policies) ← Blocks everything downstream
2. **H: 1B** (Env Validation) ← Blocks startup
3. **H: 1C** (JWT Secret in env files) ← Blocks deployment config
4. **Y: 1D** (Wire Auth on endpoints) ← Blocks secure API
5. **Y: 2A** (Roadmap Schemas) ← Blocks 90-day roadmap
6. **H: 2B** (90-Day Algorithm) ← Core clinical logic
7. **H: 2C** (90-Day in Orchestrator) ← Wires roadmap
8. **Y: 2D** (Roadmap Status Endpoint) ← Frontend needs this
9. **Y: 2E** (Supabase Migration) ← Database schema
10. **A: 4A-4C** (Supabase auth + API connectivity) ← Frontend auth
11. **A: 4F** (Form screen with screen time) ← Assessment submission
12. **H: 5A-5D** (Railway deployment) ← Go live

**Estimated minimum time with parallel execution: ~6-7 hours**

---

## Communication Protocol

1. **All tasks marked 🔴 must be completed before any 🟡 tasks**
2. **Any ⚠️ item must be flagged in Discord/Telegram immediately when discovered**
3. **If a task takes longer than estimated, escalate immediately — don't block others**
4. **Use branch naming: `hozaifa/1a-rls-policies`, `yahya/1d-auth-wiring`, `abdalrahman/4a-supabase-auth`**
5. **PR all changes to `staging` branch, then merge to `main` for deployment**

---

## Emergency Contacts

- **Hozaifa:** Backend/Deployment lead
- **Yahya:** API/Services lead  
- **Abdalrahman:** Frontend/Connectivity lead

**If stuck on any task for >30 minutes, escalate immediately.**
