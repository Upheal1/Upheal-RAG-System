# A-YAH-12: Sentiment hook + frustration_score

## Task Metadata

| Field      | Value                            |
|------------|----------------------------------|
| Task ID    | A-YAH-12                         |
| Owner      | Yahya                            |
| Phase      | Phase 3 — Section 1              |
| File(s)    | `services/auditor/`              |
| Complexity | M                                |
| Depends On | A-YAH-07                         |
| Blocks     | A-HOZ-12                         |
| Status     | Completed                        |

## Overview

Added lightweight sentiment classifier to detect user frustration in chat feedback. When `frustration_score > 0.7`, an AMBER advisory is set for the Director. The sentiment analysis does NOT override crisis (RED) or robotic tone (YELLOW) - it's additional metadata.

## What Was Built

### 1. New Module: `services/auditor/sentiment.py`

```python
class SentimentClassifier:
    """Lightweight keyword-based sentiment classifier."""
    
    FRUSTRATION_KEYWORDS_EN = [
        "frustrated", "annoyed", "stuck", "confused", "overwhelmed",
        "hate", "terrible", "awful", "worst", "useless", "waste",
        "pointless", "hopeless", "giving up", "can't do", "impossible",
        "fed up", "sick of", "done with", "ridiculous", "angry", "irritated",
    ]
    
    POSITIVE_KEYWORDS_EN = [
        "great", "helpful", "useful", "thank", "better", "good",
        "amazing", "excellent", "awesome", "love", "appreciate", "perfect",
    ]
    
    AMBER_THRESHOLD = 0.7
```

**Scoring formula:**
- Each frustration keyword adds `0.15` to score
- Each positive keyword subtracts `0.10` from score
- Score clamped to `[0.0, 1.0]`

### 2. Updated Schemas: `services/auditor/schemas.py`

**AuditFlags** - Added:
```python
frustration_detected: bool = False
frustration_score: float = 0.0
```

**AuditResult** - Added:
```python
frustration_score: float = 0.0
amber_advisory: bool = False
```

### 3. Integration: `services/auditor/core.py`

- Added `_sentiment` property to `ClinicalAuditor`
- Added `_compute_frustration()` method
- Integrated into `audit()` method - runs on all paths (GREEN, YELLOW, RED)

**Priority order (unchanged):**
1. safety_risk=True → RED
2. Crisis keywords → RED
3. Robotic tone → YELLOW
4. Otherwise → GREEN

**Frustration behavior:**
- Runs on all paths but does NOT change safety status
- RED/YELLOW path includes frustration metadata for Director telemetry
- AMBER advisory = `frustration_score > 0.7`

## Acceptance Criteria

| Criterion | Status |
|-----------|--------|
| Output stored or forwarded with timestamp and user id | Passes — in AuditResult |
| Does not override Phase 2 RED crisis path | Passes — RED always wins |
| Version pin for model/rules documented | Passes — keyword lists in code |
| At least one test uses locale="ar" path | Passes — test_arabic_keywords |

## Test Coverage

### TestSentimentClassifier (8 tests)
- No text returns zero
- Frustration keywords increase score
- Multiple frustration keywords accumulate
- Positive keywords decrease score
- Score clamped to max 1.0
- Score clamped to min 0.0
- Arabic keywords detected
- AMBER threshold (0.8=True, 0.7/0.5=False)

### TestDetectFrustration (2 tests)
- Basic detection
- Arabic locale detection

### TestClinicalAuditorFrustration (5 tests)
- GREEN roadmap with no frustration
- Frustrated roadmap triggers AMBER advisory
- RED crisis not overridden by frustration
- YELLOW robotic tone with frustration
- AuditFlags include frustration fields

### TestAuditResultFrustration (2 tests)
- AuditResult schema with frustration fields
- AuditFlags schema with frustration fields

**Total: 17 tests, all passing**

## Files Changed

| File | Action |
|------|--------|
| `services/auditor/sentiment.py` | New — SentimentClassifier |
| `services/auditor/schemas.py` | Modified — Added frustration fields |
| `services/auditor/core.py` | Modified — Integrated sentiment |
| `tests/test_sentiment.py` | New — 17 unit tests |

## How to Run Tests

```bash
pytest tests/test_sentiment.py -v
```

## Integration Notes

- **AMBER threshold**: 0.7 — above this, Director receives advisory
- **Keywords**: EN + AR supported, case-insensitive matching
- **Performance**: Lightweight keyword matching, no ML model needed
- **Future**: Can be upgraded to ML-based classifier if needed