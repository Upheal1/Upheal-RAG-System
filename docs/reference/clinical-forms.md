# Clinical forms module (`src/clinical_forms`)

Assessment logic and Bayesian multi-label inference (anxiety / depression paths).

## Files

| File | Purpose |
|------|---------|
| `interactive_intake.py` | Terminal-based interactive assessment |
| `integrated_clinical_system.py` | Assessment plus RAG-style integration flow |
| `rag_data_preparer.py` | Structured payload for external RAG |
| `data/forms/` | JSON templates (e.g. GAD-7, PHQ-9) |

## Usage

```bash
cd src/clinical_forms
python interactive_intake.py
python integrated_clinical_system.py
```

Bayesian updates treat anxiety and depression with separate path probabilities to support comorbidity.

## Relation to `services/`

The gateway loads [`src/api/assessment_engine.py`](../../src/api/assessment_engine.py) for blended scoring; deeper form logic can be ported or shared from this module over time — see [Roadmap](../roadmap/upheal-rag-next-phase.md).
