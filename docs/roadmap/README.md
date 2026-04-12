# UpHeal Roadmap — Executive Overview

UpHeal is a clinical, agentic RAG platform: structured assessments and longitudinal signals drive retrieval from a metadata-rich knowledge base, specialist agents shape personalised therapeutic roadmaps, and future supervisory layers (the Director) close the loop with telemetry, mutation policies, and eventually knowledge-base refinement. This folder is the canonical roadmap suite: four phases move from **Knowledge Infrastructure** (the brain) through **The Guild** (roadmap generation), **The Director** (self-correction), and a **Self-Refining Loop** (reflective intelligence).

## High-Level System Map

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         PHASE 1 — Knowledge Infrastructure                   │
│                    (Building Factory → enriched Chroma + contracts)        │
└─────────────────────────────────────────────────────────────────────────────┘
                                        │
                                        ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                    PHASE 2 — The Guild (Roadmap Generation)                  │
│         Profiler → Architect (retrieve + rerank) → Gamifier → Auditor       │
└─────────────────────────────────────────────────────────────────────────────┘
                                        │
                                        ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                 PHASE 3 — The Director (Self-Correction)                     │
│              Telemetry + Evaluator + Mutation Engine → Architect overrides   │
└─────────────────────────────────────────────────────────────────────────────┘
                                        │
                                        ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                 PHASE 4 — Self-Refining Loop                                 │
│        Full Director + utility-weighted retrieval + KB evolution (Supabase)│
└─────────────────────────────────────────────────────────────────────────────┘

Terminology: **The Guild** = Phases 1 + 2 (foundation + multi-agent roadmap). **The Director** = Phases 3 + 4 (supervision, mutations, and long-term refinement).
```

## Phase Summary

| Phase | Name | Core Metaphor | Status |
|-------|------|---------------|--------|
| 1 | Knowledge Infrastructure | The Building Factory | 🔲 Planned |
| 2 | The Guild | Roadmap Generation | 🔲 Planned |
| 3 | The Director | Self-Correction Loop | 🔲 Planned |
| 4 | Self-Refining Loop | Reflective Intelligence | 🔲 Planned |

## Phase Documents

- [Phase 1 — Knowledge Infrastructure](./phase-1-knowledge-infrastructure.md)
- [Phase 2 — The Guild: Roadmap Generation](./phase-2-the-guild-roadmap-generation.md)
- [Phase 3 — The Director: Self-Correction](./phase-3-the-director-self-correction.md)
- [Phase 4 — Self-Refining Loop](./phase-4-self-refining-loop.md)

## Related

- [Upcoming modifications (legacy staging notes)](./upheal-rag-next-phase.md) — historical microservices checklist vs current repo.
