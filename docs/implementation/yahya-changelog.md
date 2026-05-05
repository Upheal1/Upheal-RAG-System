# Yahya Implementation Changelog

Changelog for Yahya's implementation tasks (Phase 2-4 - The Guild, Director, Self-Refining).

---

## [Unreleased]

### A-YAH-08: Arabic + English Localisation Constants
**Status:** ✅ Done (absorbed into A-YAH-07)  
**Files:** `services/auditor/i18n.py`

The i18n constants for crisis keywords, hotline data, and guidance messages were implemented as part of A-YAH-07. No separate module needed.

---

## [Previous - Already in main]

### A-YAH-01: FastAPI Scaffold
**Status:** ✅ Done  
**File:** `services/gateway/main.py`

### A-YAH-02: Profiler Agent
**Status:** ✅ Done  
**Files:**
- `services/assessment/core.py` - Sigmoid R_app, form scoring, Bayesian blend
- `services/assessment/router.py`

### A-YAH-03: ClinicalTask Fixtures
**Status:** ✅ Done  
**File:** `tests/fixtures/clinical_tasks.py`

### A-YAH-07: Clinical Auditor
**Status:** ✅ Done  
**Files:**
- `services/auditor/core.py` - ClinicalAuditor class
- `services/auditor/i18n.py` - EN/AR crisis keywords, messages, hotlines
- `services/auditor/schemas.py` - AuditResult, EmergencyPayload, etc.
- `services/auditor/router.py` - FastAPI router

Features:
- Crisis keywords (English + Arabic)
- Robotic tone detection
- RED/YELLOW/GREEN safety status
- safety_risk=True task override
- Structured emergency payload with hotlines
- 61 unit tests

### A-YAH-09: Full Orchestration Chain
**Status:** ✅ Done  
**Files:**
- `services/gateway/orchestrator.py` - Chain orchestration, error handling, stage logging
- `services/gateway/main.py` - Refactored to use orchestrator
- `services/architect/pipeline.py` - Added _sequence_tasks() hook

Features:
- Profiler → Architect → Auditor chain
- Per-stage structured logging with timing
- Safe fallback on any stage failure (never exposes stack traces)
- Gamifier pass-through hook (ready for A-YAH-06)
- 21 unit tests

### A-YAH-10: POST /api/roadmap
**Status:** ✅ Done  
**Files:**
- `services/gateway/schemas.py` - RoadmapRequest, RoadmapResponse
- `services/gateway/main.py` - Added POST /api/roadmap endpoint

Features:
- Clean roadmap response without legacy clinical fields
- Separate from POST /api/assess (which includes legacy Flutter fields)
- Contract snapshot test prevents accidental field removal
- Supports top_n parameter (1-10)
- 16 unit tests

---

## Pending Tasks

### A-YAH-04: Knowledge Retrieval (Real Adapter)
**File:** `services/architect/pipeline.py`  
**Depends On:** A-HOZ-06  
**Status:** 🔲 Blocked until A-HOZ-06

Requirements:
- Fetch top-10 from chroma_adapter
- Apply difficulty <= user_level filter
- symptom_tags overlap with query keywords

### A-YAH-05: Triple-Threat Reranking
**File:** `services/architect/pipeline.py`  
**Depends On:** A-YAH-04  
**Status:** 🔲 Blocked

Formula:
```
Score = (SemanticSimilarity × 0.4) + (FormWeight × 0.3) + (R_app × 0.3)
```

Requirements:
- Digital detox boost when `boost_digital_detox = True`
- FormWeight uses Jaccard overlap
- Stable tie-breaking

### A-YAH-06: Gamifier Agent
**File:** `services/architect/logic.py`  
**Assignee:** Ahmed  
**Status:** 🔲 Not Started

XP Formula:
```
xp_reward_final = BaseXP × difficulty × (1 + user_level × 0.1)
```

Requirements:
- Quick Win: difficulty=1, highest XP
- Middle: ascending difficulty 1→3
- Boss Task: highest difficulty, highest therapeutic impact

---

## Phase 3 — The Director

### A-YAH-11: POST /api/telemetry
**File:** `services/gateway/main.py`  
**Depends On:** A-HOZ-10 (Supabase)  
**Status:** 🔲 Blocked

Payload:
```json
{
  "task_id": "uuid",
  "interaction_type": "VIEWED|STARTED|COMPLETED|SKIPPED",
  "completion_time": 120,
  "drop_off_point": 0.75,
  "xp_earned": 50
}
```

### A-YAH-12: Sentiment Hook
**File:** `services/architect/auditor.py`  
**Status:** 🔲 Not Started

Requirements:
- Lightweight sentiment classifier
- Output `frustration_score` ∈ [0, 1]
- `frustration_score > 0.7` sets AMBER advisory
- Does not override RED crisis path

### A-YAH-13: Director Override in Pipeline
**File:** `services/architect/pipeline.py`  
**Depends On:** A-HOZ-13  
**Status:** 🔲 Blocked

Requirements:
- Load active MutationInstruction before retrieval
- Respect `max_difficulty`, XP multiplier, tag focus
- Ignore expired directives using `valid_until`

---

## Phase 4 — Self-Refining

### A-YAH-14: Triple-Threat v2
**File:** `services/architect/pipeline.py`  
**Depends On:** A-HOZ-14  
**Status:** 🔲 Blocked

Formula (Phase 4):
```
Score = (SemanticSimilarity × 0.35) + (FormWeight × 0.25) + (R_app × 0.25) + (UtilityScore × 0.15)
```

### A-YAH-15: 14-day E2E Simulation
**File:** `tests/integration/test_roadmap_evolution_14d.py`  
**Depends On:** A-YAH-14, A-HOZ-15, A-HOZ-11  
**Status:** 🔲 Blocked

Requirements:
- Scripted telemetry drives Director mutations
- Assert difficulty, modality, or tone shift
- Document seed and thresholds
