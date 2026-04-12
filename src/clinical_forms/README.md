# Clinical Forms Module

Contains the assessment logic and Bayesian inference engine.

## Files

- `interactive_intake.py` - Standalone interactive assessment (terminal-based)
- `integrated_clinical_system.py` - Full system with RAG integration
- `rag_data_preparer.py` - Prepares data for RAG queries
- `data/forms/` - JSON templates for GAD-7, PHQ-9 questionnaires

## Usage

```bash
# Run standalone assessment
python interactive_intake.py

# Run with RAG integration
python integrated_clinical_system.py
```

Both scripts use Bayesian multi-label classification to calculate anxiety and depression probabilities independently, allowing for comorbidity detection.
