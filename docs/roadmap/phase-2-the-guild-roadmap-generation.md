# Phase 2 — The Guild: Roadmap Generation

## Overview

Phase 2 orchestrates **The Guild**: three specialist agents (Profiler, Architect, Gamifier) plus a mandatory **Clinical Auditor**, turning a raw assessment into a personalised, gamified roadmap grounded in Phase 1 knowledge. The flow is strictly linear: profile → retrieve and rerank → sequence and scale rewards → safety gate before any client response.

## Architecture Diagram

```
POST /api/roadmap  (services/gateway/main.py)
        │
        ▼
┌───────────────────┐
│ Profiler          │  services/assessment/core.py
│ UserContext +     │  sigmoid R_app, normalised scores
│ RetrievalQuery    │
└─────────┬─────────┘
          ▼
┌───────────────────┐
│ Architect         │  services/architect/pipeline.py
│ Chroma top-10     │  hybrid filters + Triple-Threat score
│ → top-5 tasks     │
└─────────┬─────────┘
          ▼
┌───────────────────┐
│ Gamifier          │  services/architect/logic.py
│ XP + sequencing   │  Quick Win → ladder → Boss
└─────────┬─────────┘
          ▼
┌───────────────────┐
│ Clinical Auditor  │  services/architect/auditor.py
│ empathy + crisis  │  (non-negotiable gate)
└─────────┬─────────┘
          ▼
    FinalRoadmap → client
```

## Detailed Specifications

### Section 1 — The Profiler Agent (`services/assessment/`)

#### 1.1 `services/assessment/core.py` — Bayesian–sigmoid user context

**Sigmoid digital-strain formula**

```math
R_{app} = \frac{1}{1 + e^{-0.05 \cdot (screen\_time\_minutes - 60)}}
```

**Why sigmoid:** Screen-time harm is not linear; small increases near typical use matter less than sustained very high use. A sigmoid gives a bounded \(0\)–\(1\) “strain” signal with steeper sensitivity past a clinically chosen midpoint (here, 60 minutes as anchor), matching saturating behavioural responses often seen in compulsive use patterns.

**Example inputs → \(R_{app}\)** (illustrative)

| `screen_time_minutes` | Approx. \(R_{app}\) |
|----------------------:|--------------------:|
| 0 | ≈ 0.18 |
| 60 | 0.50 |
| 120 | ≈ 0.82 |
| 300 | ≈ 0.99 |

**Clinical score normalisation**

```math
gad7\_normalised = \frac{gad7\_score}{21}
```

```math
phq9\_normalised = \frac{phq9\_score}{27}
```

**Module output:** a fully populated `UserContext` object (Phase 1 schema), including `r_app` and `clinical_weights` derived from normalised scales and any Bayesian blend policy retained from legacy engines.

#### 1.2 Query synthesis

- **Algorithm:** Rank symptom domains by normalised score; take **top-3** domains; map each to canonical **keywords** for retrieval (controlled vocabulary).
- **Example:** If `gad7_normalised > phq9_normalised`, prioritise keywords such as `["Anxiety Reduction", "Calmness", "Grounding"]`.
- **Output:** a `RetrievalQuery` with `query_text`, `symptom_keywords`, `max_difficulty`, and `boost_digital_detox` set from `r_app > 0.8`.

---

### Section 2 — The Architect Agent (`services/architect/`)

#### 2.1 Knowledge retrieval and candidate selection (`services/architect/pipeline.py`)

- Call `services/knowledge_base/chroma_adapter.py` to fetch **top-10** candidates.
- Apply **hybrid filter:** `difficulty <= user_level` (from `RetrievalQuery.max_difficulty` or derived user tier) AND **overlap** between `symptom_tags` and query keywords (Jaccard or set intersection threshold documented in code comments).

#### 2.2 Triple-Threat reranking engine

**Scoring formula**

```math
Score = (SemanticSimilarity \times 0.4) + (FormWeight \times 0.3) + (R_{app} \times 0.3)
```

| Component | Weight | Definition |
|-----------|--------|------------|
| `SemanticSimilarity` | 0.4 | Cosine similarity between query embedding and chunk embedding |
| `FormWeight` | 0.3 | Jaccard overlap between `symptom_tags` and user’s top clinical domains |
| `R_app` | 0.3 | Channel that boosts grounding / digital-detox alignment when screen strain is high |

**Digital detox boost:** When `boost_digital_detox = True`, multiply `FormWeight` by **1.5** for tasks whose tags intersect `{"grounding", "digital-detox", "mindfulness"}` (case-normalised). Cap final `Score` at `1.0` if needed for stable ordering.

---

### Section 3 — The Gamifier Agent (`services/architect/logic.py`)

#### 3.1 Dynamic XP and levelling

**XP formula**

```math
xp\_{reward}^{final} = BaseXP \times difficulty \times (1 + user\_level \times 0.1)
```

(`BaseXP` may come from the task’s indexed `xp_reward`; `user_level` is the gamification tier, not clinical severity.)

#### 3.2 Task sequencing rules

| Position in roadmap | Rule |
|---------------------|------|
| First task (“Quick Win”) | `difficulty = 1`, highest immediate adjusted `xp_reward` among eligible tasks |
| Middle tasks | Ascending difficulty (1 → 3) where clinically appropriate |
| Final task (“Boss Task”) | Highest `difficulty`, highest therapeutic impact score among safe candidates |

---

### Section 4 — The Clinical Auditor (`services/architect/auditor.py`) — Safety gate

> ⚠️ **Safety Note:** This component is non-negotiable. No roadmap is returned to the client without passing this gate.

#### Empathy check

- LLM-graded rubric on `overview_paragraph`: warmth, non-dismissive tone, absence of cold diagnostic language. Failure → regenerate once with stricter system prompt; second failure → AMBER pathway (short supportive copy + general resources).

#### Crisis guardrail

- If **any** task has `safety_risk = True`, **or** consolidated LLM output matches crisis triggers below → **emergency override**: replace roadmap body with hotline resources; set `safety_status = "RED"`.

**Trigger keywords (English)**  
`suicide`, `kill myself`, `end it all`, `self-harm`, `no reason to live`, `better off dead`, `hurt myself`, `want to die`

**Trigger keywords (Arabic)**  
`انتحار`, `أؤذي نفسي`, `لا أريد العيش`, `أريد الموت`, `إيذاء النفس`  
(Extend list with clinician-reviewed phrases; treat normalisation for alef/hamza variants.)

#### Emergency override response object (structure)

| Field | Type | Description |
|-------|------|-------------|
| `safety_status` | `str` | `"RED"` |
| `roadmap_id` | `UUID` \| `null` | Null or tombstoned id |
| `overview_paragraph` | `str` | Short, supportive crisis message (bilingual snippets allowed) |
| `tasks` | `List[dict]` | Empty or single static “reach out now” task with hotlines |
| `resources` | `List[dict]` | `{ "region": "...", "phone": "...", "label_ar": "...", "label_en": "..." }` |
| `audit_flags` | `List[str]` | e.g. `["CRISIS_KEYWORD", "TASK_SAFETY_RISK"]` |

---

### Section 5 — Orchestration (`services/gateway/main.py`)

Full chain (endpoint name may be `POST /api/roadmap` or aligned with existing `POST /api/assess` — document final route in gateway OpenAPI):

```
POST /api/roadmap
  └─► Profiler (services/assessment/core.py)     → UserContext + RetrievalQuery
        └─► Architect (services/architect/pipeline.py)     → Ranked top-5 ClinicalTasks
              └─► Gamifier (services/architect/logic.py)   → XP-enriched, sequenced roadmap
                    └─► Auditor (services/architect/auditor.py) → Safety-checked final roadmap
```

---

## Technical Deliverables

- [ ] `services/assessment/core.py` — Sigmoid `R_app` calculation and clinical score normalisation implemented.
- [ ] `services/architect/pipeline.py` — Triple-Threat reranking logic implemented.
- [ ] `services/architect/logic.py` — Gamifier XP formula and task sequencing implemented.
- [ ] `services/architect/auditor.py` — Empathy check, crisis guardrail, Arabic/English keyword list implemented.
- [ ] `services/gateway/main.py` — Full orchestration chain (Profiler → Architect → Gamifier → Auditor) implemented.

## Success Metric

> **Clinical relevance**: In a test case where a user has high screen time (`R_app > 0.8`) but low anxiety scores, the top recommendation must be a “Digital Detox” or “Mindful Presence” task, even if “Anxiety Breathing” has a higher raw semantic similarity score.

## File Map

```
services/assessment/core.py       # Profiler: UserContext, RetrievalQuery, R_app, normalisation
services/architect/pipeline.py    # Retrieval orchestration + Triple-Threat rerank
services/architect/logic.py       # Gamifier: XP scaling + roadmap sequencing
services/architect/auditor.py     # Empathy + crisis gate + emergency override payload
services/gateway/main.py          # HTTP orchestration for The Guild chain
```
