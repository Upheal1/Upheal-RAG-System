# Yahya Implementation Changelog

Changelog for Yahya's implementation tasks (Phase 2-4 - The Guild, Director, Self-Refining).

---

## [Unreleased]

All tasks pending until A-HOZ-06 gate is cleared.

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

### A-YAH-07: Clinical Auditor
**Status:** ✅ Done  
**File:** `services/architect/auditor.py`

Features:
- Crisis keywords (English + Arabic)
- Robotic tone detection
- RED/YELLOW/GREEN safety status

---

## Pending Tasks

### A-YAH-03: ClinicalTask Fixtures
**File:** `tests/fixtures/clinical_tasks.py`  
**Status:** 🔲 Not Started (can start immediately)

Requirements:
- ≥10 realistic ClinicalTask instances
- Difficulty 1-5 coverage
- At least one `safety_risk=True` for auditor tests
- Importable as `from tests.fixtures.clinical_tasks import SAMPLE_TASKS`

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
**Status:** 🔲 Not Started (can start immediately)

XP Formula:
```
xp_reward_final = BaseXP × difficulty × (1 + user_level × 0.1)
```

Requirements:
- Quick Win: difficulty=1, highest XP
- Middle: ascending difficulty 1→3
- Boss Task: highest difficulty, highest therapeutic impact

### A-YAH-08: i18n Constants
**File:** `services/architect/i18n.py`  
**Status:** 🔲 Not Started

Requirements:
- Centralize crisis strings
- Hotline labels (EN/AR)
- Auditor messages
- At least one test with locale="ar"

### A-YAH-09: Full Orchestration Chain
**File:** `services/gateway/main.py`  
**Depends On:** A-YAH-05, A-YAH-06, A-YAH-07  
**Status:** 🔲 Blocked

Chain: Profiler → Architect → Gamifier → Auditor

### A-YAH-10: POST /api/roadmap
**File:** `services/gateway/main.py`  
**Depends On:** A-YAH-09  
**Status:** 🔲 Blocked

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
