# UpHeal implementation approaches — comparison

Two execution strategies for delivering the four roadmap phases ([Phase 1](../phase-1-knowledge-infrastructure.md), [Phase 2](../phase-2-the-guild-roadmap-generation.md), [Phase 3](../phase-3-the-director-self-correction.md), [Phase 4](../phase-4-self-refining-loop.md)) with two developers: **Hozaifa** and **Yahya**.

## Section 1 — Philosophy comparison

Different teams tolerate different risks: some need a **stable substrate** before layering agents; others need a **demoable vertical slice** immediately and accept contract discipline plus mock–real parity work. Timeline pressure, familiarity with the repo, and how often Chroma or schema contracts are expected to change all argue for picking an approach deliberately rather than defaulting to “everyone starts coding.”

**Approach A (Foundation-First)** optimises for **stability and a clean handoff**: the knowledge plane (`services/knowledge_base/chroma_adapter.py`, ingestion, integrity) is proven before Yahya depends on it. **Approach B (Contract-First)** optimises for **speed and parallelism**: immutable schemas and a mock-backed adapter let both engineers ship from Day 1, with the real Chroma adapter swapped in once `tests/contracts/test_adapter_contract.py` passes on both implementations.

## Section 2 — At-a-glance comparison

| Dimension | Approach A: Foundation-First | Approach B: Contract-First |
|-----------|------------------------------|----------------------------|
| **Strategy** | Sequential by layer | Parallel from Day 1 |
| **First working API** | End of Week 2 | End of Week 1 |
| **Integration risk** | 🟢 Low | 🟡 Medium–High |
| **Merge conflicts** | 🟢 Rare | 🟡 Frequent |
| **Debugging complexity** | 🟢 Simple — layer by layer | 🔴 Hard — mocks vs real |
| **Best for** | First-time collaboration, unknown codebase | Experienced pair, tight deadline |
| **Hozaifa unblocks Yahya at** | Week 1 Day 4 (real adapter) | Week 1 Day 1 (mock adapter) |
| **Phase 1 complete by** | End of Week 1 | Mid Week 2 (built in parallel) |
| **Phase 4 complete by** | End of Week 4 | End of Week 3 |
| **Recommended when** | Quality and safety are the top priority | Time-to-demo is the top priority |

## Section 3 — Phase mapping summary

| Phase | Approach A execution | Approach B execution |
|-------|----------------------|----------------------|
| Phase 1 — Knowledge Infrastructure | Hozaifa completes the data layer first; Yahya scaffolds API and agents on fixtures | Both work in parallel; Yahya codes against the locked contract and mock adapter |
| Phase 2 — The Guild | Yahya swaps fixtures for real `chroma_adapter` after **A-HOZ-06**; Hozaifa adds Supabase + `services/shared/state.py` | Mock→real swap after **B-HOZ-07** passes contract tests; Hozaifa adds health + migrations |
| Phase 3 — The Director | Hozaifa owns evaluator + mutation engine; Yahya wires telemetry and pipeline overrides | Same ownership; evaluator/mutation start earlier alongside Guild polish |
| Phase 4 — Self-Refining Loop | Joint integration Week 4 (`utility_score`, `mutation_logic.py`, Triple-Threat v2) | Convergence Week 3; Week 4 buffer for hardening |

## Section 4 — Decision guide

```
Is this the first time Hozaifa and Yahya are working together?
  ├── YES → Is the deadline more than 4 weeks away?
  │           ├── YES → Use Approach A (Foundation-First)
  │           └── NO  → Use Approach B but add daily sync calls
  └── NO  → Use Approach B (Contract-First)
```

## Section 5 — Links

- [Approach A — Foundation-First](./approach-a-foundation-first.md)
- [Approach B — Contract-First](./approach-b-contract-first.md)
