# Quick Reference — Implementation

## Branch Naming Convention

```
A-HOZ-XX-<short-name>  # Hozaifa tasks
A-YAH-XX-<short-name>  # Yahya tasks
```

Examples:
- `A-HOZ-02-logging`
- `A-HOZ-03-pdf-extraction`
- `A-YAH-06-gamifier`

## Workflow

1. **Create branch from `main`:**
   ```bash
   git checkout main
   git pull origin main
   git checkout -b A-HOZ-XX-feature-name
   ```

2. **Implement task**

3. **Add tests:**
   ```bash
   pytest tests/ -v
   ```

4. **Commit:**
   ```bash
   git add .
   git commit -m "feat(A-HOZ-XX): description"
   ```

5. **Push and create PR:**
   ```bash
   git push -u origin A-HOZ-XX-feature-name
   gh pr create --base staging --title "feat(A-HOZ-XX): description"
   ```

6. **Update docs:**
   - Update `docs/implementation/README.md`
   - Update `docs/implementation/hozaifa-changelog.md`

## Important Gates

| Gate | Blocker | Unlocks |
|------|---------|---------|
| A-HOZ-06 | ChromaDB hybrid adapter | Yahya's real retrieval |
| A-HOZ-10 | Supabase migrations | Yahya's telemetry |
| A-HOZ-13 | Mutation engine | Yahya's pipeline overrides |

## Critical Dependencies

```
A-HOZ-01 ──┬──► A-HOZ-02 ──► A-HOZ-03 ──► A-HOZ-04 ──► A-HOZ-05 ──► A-HOZ-06 ⭐
            │                                                       │
            └──► A-YAH-01, A-YAH-02, A-YAH-03 ◄────────────────────┘
```

## Testing

Run all tests:
```bash
pytest tests/ -v
```

Run specific test file:
```bash
pytest tests/test_logging.py -v
```

Run with coverage:
```bash
pytest tests/ --cov=services --cov-report=term-missing
```

## File Locations

| Component | Path |
|-----------|------|
| Shared schemas | `services/shared/schemas.py` |
| Logging | `services/shared/logging.py` |
| Pathing | `services/shared/pathing.py` |
| Ingestion | `services/ingestion/` |
| Knowledge Base | `services/knowledge_base/` |
| Assessment | `services/assessment/` |
| Architect | `services/architect/` |
| Gateway | `services/gateway/` |
| Tests | `tests/` |
| Scripts | `scripts/` |

## Key Patterns

### Using the Logger

```python
from services.shared.logging import get_logger

log = get_logger(__name__)  # service = "ingestion.pdf_utils"
log.info("ingestion.pdf.start", source_path="/data/test.pdf", sha256="abc")

# Convenience helpers
from services.shared.logging import log_pdf_start, log_formatter_done, log_chroma_upsert
log_pdf_start("/data/test.pdf", "sha256abc", logger=log)
```

### ClinicalTask Schema

```python
from services.shared.schemas import ClinicalTask

task = ClinicalTask(
    task_id="uuid",
    content="Deep breathing exercise for anxiety",
    symptom_tags=["anxiety", "grounding"],
    difficulty=1,
    xp_reward=50,
    source_reference="CBT Manual p.45",
)
```

### UserContext for Testing

```python
from services.shared.schemas import UserContext

ctx = UserContext(
    user_id="user_123",
    timestamp="2026-04-13T10:00:00Z",
    form_scores={"anxiety": 75, "depression": 40},
    app_exposure_ratios={"r_app": 0.82},
    user_stats={"xp": 500, "level": 3},
)
```
