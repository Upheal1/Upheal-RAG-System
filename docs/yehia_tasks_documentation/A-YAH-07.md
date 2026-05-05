# [A-YAH-07] Clinical Auditor and Safety Gate

## Task Overview

| Field | Value |
|-------|-------|
| Owner | Yahya |
| Phase | Phase 2 — Section 4 |
| Files | `services/auditor/core.py`, `services/auditor/i18n.py`, `services/auditor/schemas.py`, `services/auditor/router.py` |
| Complexity | L |
| Depends On | A-YAH-06 (Gamifier Agent) |
| Blocks | A-YAH-09 (Full Orchestration), A-YAH-12 (Sentiment Hook) |
| Status | ✅ Complete |

## Purpose

Implements the clinical safety gate that all client-facing responses must pass through. Detects crisis keywords (EN/AR), robotic tone, and tasks flagged with `safety_risk=True`. Returns structured emergency payloads with hotline data when a RED audit is triggered.

**Key design decision:** Implemented as a standalone microservice under `services/auditor/` rather than remaining inline in `services/architect/auditor.py`. This follows the microservice architecture pattern and makes the auditor independently testable and callable via its own FastAPI router.

## Implementation Details

### Files Created

| File | Purpose |
|------|---------|
| `services/auditor/__init__.py` | Package initializer |
| `services/auditor/i18n.py` | Crisis keywords (26 EN + 32 AR), guidance messages, hotline data for both locales |
| `services/auditor/schemas.py` | Pydantic models: `AuditRequest`, `AuditResult`, `EmergencyPayload`, `HotlineResource`, `AuditFlags` |
| `services/auditor/core.py` | `ClinicalAuditor` class with `audit()`, `detect_crisis()`, `scan_safety_risk_tasks()`, `apply_to_roadmap()` |
| `services/auditor/router.py` | FastAPI router: `POST /audit`, `GET /auditor/health` |

### Files Modified

| File | Change |
|------|--------|
| `services/architect/auditor.py` | Replaced with thin re-exports to `services.auditor.*` for backward compatibility |
| `services/gateway/main.py` | Registered `/auditor` router |

### Architecture

```
Input: FinalRoadmap + List[ClinicalTask] + locale
       ↓
ClinicalAuditor.scan_safety_risk_tasks(tasks)    # priority 1 — hard override
       ↓
ClinicalAuditor.detect_crisis(overview_text)     # priority 2 — keyword scan
       ↓
ClinicalAuditor.detect_robotic_tone(overview)    # priority 3 — tone check
       ↓
AuditResult (safety_status, emergency_payload, flags)
```

### Safety Priority Order

1. **safety_risk=True task** → RED (hard override, bypasses all text checks)
2. **Crisis keywords** in text → RED (with emergency payload)
3. **Robotic tone** detected → YELLOW
4. **Safe** → GREEN

### Workaround for Missing Gamifier (A-YAH-06)

Since the Gamifier is not yet implemented, the auditor accepts a raw `List[ClinicalTask]` directly via the `tasks` parameter on `audit()` and `audit_roadmap()`:

```python
auditor = ClinicalAuditor(locale="en")
result = auditor.audit(roadmap, tasks=candidate_tasks)
```

This scans all tasks for `safety_risk=True` flags before text-based checks, so crisis tasks are caught even without gamifier sequencing.

## API Schemas

### AuditRequest

```python
class AuditRequest(BaseModel):
    user_id: str
    overview_paragraph: str
    task_contents: List[Dict[str, Any]]  # ClinicalTask-like dicts
    locale: str = "en"
```

### AuditResult

```python
class AuditResult(BaseModel):
    safety_status: Literal["GREEN", "YELLOW", "RED"]
    next_checkup_days: int               # 1 for RED, 7 for YELLOW, 14 for GREEN
    emergency_payload: EmergencyPayload  # only present on RED
    flags: AuditFlags
    overview_paragraph: str
    task_ids: List[str]
```

### EmergencyPayload (RED only)

```python
class EmergencyPayload(BaseModel):
    message: str
    hotlines: List[HotlineResource]      # name, number, description
    immediate_action: str
    locale: str
```

### HotlineResource

| Field | Type | Description |
|-------|------|-------------|
| `name` | str | Hotline name (localized) |
| `number` | str | Phone number or text format (e.g., "Text HOME to 741741") |
| `description` | str | When to use this hotline |

### Hotline Data by Locale

| Locale | Hotlines |
|--------|----------|
| `en` | Emergency Services (911), 988 Suicide & Crisis Lifeline, Crisis Text Line |
| `ar` | الطوارئ (911), خط المساعدة للأزمات (988), خط الأزمات عبر الرسائل |

## i18n Constants

All strings centralized in `services/auditor/i18n.py`:

| Constant | Count | Description |
|----------|-------|-------------|
| `CRISIS_KEYWORDS_EN` | 26 | English crisis phrases |
| `CRISIS_KEYWORDS_AR` | 32 | Arabic crisis phrases |
| `ROBOTIC_TONE_KEYWORDS` | 10 | AI-disclaimer language patterns |
| `GUIDANCE_MESSAGES` | 2 locales × 2 levels | Red/yellow guidance text |
| `HOTLINES` | 2 locales × 3 entries | Emergency resources |

Arabic-mode auditor also scans for English keywords (cross-detection).

## Crisis Keywords (English)

```
suicide, kill myself, end my life, harm myself, self-harm, self harm,
suicidal, overdose, immediate danger, want to die, can't go on,
no reason to live, hurt myself, cut myself, jump off, hang myself,
poison myself, take pills, shoot myself, end it all, don't want to live,
ending it all, better off dead, kill me
```

## Crisis Keywords (Arabic)

```
انتحار, انتحر, اقتل نفسي, انهي حياتي, اذاء نفسي, انتحاري,
جرعة زائدة, خطر فوري, اريد الموت, أريد الموت, أريد أن أموت,
ما ارد العيش, ما أريد العيش, ما عندي سبب للعيش, اضرب نفسي,
أضرب نفسي, اجرح نفسي, أجرح نفسي, اقطع نفسي, أقطع نفسي,
ارمي حالي, أرمي حالي, اشنق حالي, أشنق حالي, ما في سبب عيش
```

## Usage Examples

### Module-level function (backward compatible)

```python
from services.auditor.core import audit_roadmap
# or: from services.architect.auditor import audit_roadmap  # legacy compat

roadmap = FinalRoadmap(...)
audited = audit_roadmap(roadmap, locale="en", tasks=candidate_tasks)
```

### ClinicalAuditor class (full control)

```python
from services.auditor.core import ClinicalAuditor

auditor = ClinicalAuditor(locale="ar")
result = auditor.audit(roadmap, tasks=tasks)

if result.safety_status == "RED":
    print(result.emergency_payload.hotlines)
    print(result.flags.crisis_keywords_found)
```

### Via HTTP endpoint

```bash
curl -X POST http://localhost:8000/auditor/audit \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "u-123",
    "overview_paragraph": "I need help ending my life",
    "task_contents": [{"task_id": "t1", "content": "breathe", "symptom_tags": ["anxiety"], "difficulty": 1, "xp_reward": 50, "safety_risk": false, "source_reference": "ref"}],
    "locale": "en"
  }'
```

## Testing

61 unit tests across 16 test classes in `tests/test_auditor.py`:

| Test Class | Coverage |
|------------|----------|
| `TestResolveLocale` | Locale normalization (4 tests) |
| `TestI18nConstants` | Keyword/message/hotline integrity (8 tests) |
| `TestCrisisDetection` | EN/AR keyword detection, case-insensitive, no false positives (7 tests) |
| `TestRoboticToneDetection` | AI-disclaimer detection (3 tests) |
| `TestSafetyRiskTaskScan` | safety_risk=True task scanning (4 tests) |
| `TestEmergencyPayload` | Payload construction for EN/AR (3 tests) |
| `TestAuditGreen` | Safe text paths (5 tests) |
| `TestAuditRedCrisis` | Crisis-triggered RED paths (4 tests) |
| `TestAuditRedSafetyRisk` | Task-flag RED override (4 tests) |
| `TestAuditYellow` | Robotic tone YELLOW paths (2 tests) |
| `TestAuditPriority` | Priority ordering: safety_risk > crisis > robotic > green (2 tests) |
| `TestAuditResultSchema` | Pydantic model validation (2 tests) |
| `TestBackwardCompatAuditRoadmap` | Module-level function compat (6 tests) |
| `TestLegacyImportCompat` | `from services.architect.auditor` imports (2 tests) |
| `TestAuditRequestSchema` | Request model validation (2 tests) |
| `TestApplyToRoadmap` | In-place roadmap mutation (3 tests) |

Run to verify:

```bash
pytest tests/test_auditor.py -v
```

## Acceptance Criteria

- [x] RED path returns hotline structure from Phase 2 emergency object table
- [x] CI tests for green / yellow / red / Arabic keyword paths
- [x] `safety_risk=True` on any task forces override
- [x] Arabic crisis keywords implemented (32 phrases)
- [x] All strings centralized in `i18n.py` module only
- [x] Backward compatible with existing `services/architect/auditor.py` imports

## Integration Points

| Consumer | How it uses auditor |
|----------|-------------------|
| `services/architect/pipeline.py` | `audit_roadmap(draft, locale=resolved_locale)` as final step in `run_architect_pipeline()` |
| `services/gateway/main.py` | Router mounted at `/auditor` prefix |
| Future: `services/architect/auditor.py` | Re-exports from `services.auditor.*` — no logic duplication |
