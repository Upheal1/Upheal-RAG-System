# UpHeal RAG System — Flutter Integration Guide

## Base URL

```
https://upheal-gateway.onrender.com
```

All endpoints below are relative to this base URL. Replace this if your Render service name differs.

---

## Authentication

All authenticated endpoints require a **Supabase JWT** in the `Authorization` header:

```dart
headers: {
  'Authorization': 'Bearer <supabase_jwt_token>',
  'Content-Type': 'application/json',
}
```

The JWT is obtained after Supabase Auth sign-in (email/password, OAuth, etc.). The backend validates it using the `SUPABASE_JWT_SECRET` and extracts `user_id` from the `sub` claim.

> **Unauthenticated endpoints** (no `Authorization` needed): `GET /health`, `GET /*/health`, `POST /audit`, `POST /api/telemetry/`

---

## Rate Limiting

| Endpoint | Limit |
|---|---|
| `POST /api/assess` | 10 requests / minute |

Other endpoints have no explicit rate limit but respect Render's infrastructure limits.

---

## API Endpoints

### 1. Health Check — `GET /health`

Unauthenticated. Lightweight check — does NOT load ML models.

**Response `200`:**
```json
{
  "status": "ok",
  "knowledge_base_healthy": true,
  "knowledge_base_documents": 42
}
```

---

### 2. Assessment — `POST /api/assess`

Authenticated. Rate-limited (10/min). Runs the full clinical assessment pipeline.

**Request:**
```json
{
  "user_id": "string (optional — overridden by JWT)",
  "session_id": "string (optional)",
  "locale": "en",
  "raw_forms_json": {
    "answers": {
      "gad7_q1": 0, "gad7_q2": 1, "gad7_q3": 2,
      "phq9_q1": 0, "phq9_q2": 1
    },
    "risk_flags": { "suicidal": false }
  },
  "screen_time_minutes": 120.0,
  "screenTimeData": {
    "totalMinutes": 180.0,
    "socialMinutes": 45.0,
    "productivityMinutes": 60.0,
    "dailyUsage": [
      { "packageName": "com.instagram.android", "usageTime": 30, "category": "social" },
      { "packageName": "com.google.android.apps.docs", "usageTime": 20, "category": "productivity" }
    ]
  },
  "answers": { "gad7_q1": 0, "phq9_q1": 1 }
}
```

| Field | Type | Required | Description |
|---|---|---|---|
| `raw_forms_json` | object/array | No | GAD-7/PHQ-9 form data |
| `answers` | object | No | Shorthand for `{"answers": {...}}` |
| `screen_time_minutes` | float | No | Total screen time in minutes |
| `screenTimeData` | object | No | Rich per-app screen time from Flutter |
| `locale` | string | No | Language code, default `"en"` |

**Response `200` — `AssessGatewayResponse`:**
```json
{
  "user_id": "...",
  "overview_paragraph": "Based on your assessment...",
  "suggested_tasks": [
    {
      "task_id": "task_001",
      "content": "Practice 4-7-8 breathing for 5 minutes",
      "symptom_tags": ["anxiety", "insomnia"],
      "difficulty": 2,
      "xp_reward": 10,
      "safety_risk": false,
      "utility_score": 0.85,
      "source_reference": "DSM-5 §300.02",
      "phase": "Quick Win",
      "metadata": {}
    }
  ],
  "safety_status": "GREEN",
  "next_checkup_days": 7,
  "days": [
    {
      "day_number": 1,
      "task": { "task_id": "...", "content": "...", "phase": "Quick Win", ... },
      "phase": "Quick Win",
      "day_context": "morning routine"
    }
  ],
  "total_days": 90,
  "assessment_required": false,
  "anxiety_probability": 0.32,
  "depression_probability": 0.45,
  "severity": { "anxiety": "mild", "depression": "moderate" },
  "comorbidity": "anxiety_depression",
  "rag_recommendations": [
    { "source": "DSM-5", "section": "Generalized Anxiety Disorder", "content": "...", "similarity": 0.89, "pages": "222-225" }
  ],
  "query_used": "anxiety mild depression moderate",
  "timestamp": "2026-05-18T12:00:00Z",
  "session_id": "uuid",
  "screen_time_insights": {
    "totalMinutes": 180.0,
    "socialRatio": 0.25,
    "productivityRatio": 0.33,
    "topSocialApps": ["com.instagram.android"],
    "topProductivityApps": ["com.google.android.apps.docs"],
    "appBreakdown": [
      { "packageName": "com.instagram.android", "percentage": 16.7, "category": "social" }
    ]
  }
}
```

---

### 3. Roadmap — `POST /api/roadmap`

Authenticated. Generates a personalized 90-day clinical roadmap. Same input as assess but returns a cleaner response.

**Request:** Same fields as `/api/assess`, plus:

| Field | Type | Required | Description |
|---|---|---|---|
| `top_n` | int | No | Number of tasks (1-10), default 5 |

**Response `200` — `RoadmapResponse`:**
```json
{
  "user_id": "...",
  "overview_paragraph": "Based on your assessment...",
  "suggested_tasks": [...],
  "safety_status": "GREEN",
  "next_checkup_days": 7,
  "generated_at": "2026-05-18T12:00:00Z",
  "session_id": "uuid",
  "version": "1.0",
  "screen_time_insights": { ... },
  "days": [...],
  "total_days": 90,
  "assessment_required": false
}
```

---

### 4. Roadmap Status — `GET /api/roadmap/{user_id}/status`

Authenticated. Checks if the user needs to retake the assessment. The `user_id` path parameter must match the authenticated user's ID.

**Response `200`:**
```json
{
  "user_id": "...",
  "roadmap_id": "uuid",
  "roadmap_status": "ACTIVE",
  "current_day": 14,
  "total_days": 90,
  "assessment_required": false,
  "days_since_last_assessment": 14
}
```

---

### 5. Chat — `POST /api/chat`

Authenticated. Send a message to the AI therapist chatbot.

**Request:**
```json
{
  "session_id": "uuid or null for new session",
  "message": "I've been feeling anxious this week",
  "roadmap_id": "optional roadmap context uuid"
}
```

| Field | Type | Required | Description |
|---|---|---|---|
| `session_id` | string/null | No | Existing session ID, or `null` to create new |
| `message` | string | Yes | 1-4000 chars |
| `roadmap_id` | string | No | Provides personalized context |

**Response `200` — `ChatResponse`:**
```json
{
  "session_id": "uuid",
  "message_id": "uuid",
  "assistant_message": {
    "role": "assistant",
    "content": "I understand...",
    "metadata": {},
    "created_at": "2026-05-18T12:00:00Z"
  },
  "history": [
    { "role": "user", "content": "I've been feeling anxious", "metadata": {}, "created_at": "..." },
    { "role": "assistant", "content": "I understand...", "metadata": {}, "created_at": "..." }
  ],
  "relevant_task_id": "optional task id"
}
```

---

### 6. Chat History — `GET /api/chat/{session_id}/history`

Authenticated. Retrieves message history for a chat session.

**Response `200` — `ChatHistoryResponse`:**
```json
{
  "session_id": "uuid",
  "messages": [
    { "role": "user", "content": "...", "metadata": {}, "created_at": "..." },
    { "role": "assistant", "content": "...", "metadata": {}, "created_at": "..." }
  ],
  "total_count": 10
}
```

**Errors:** `404` if session not found.

---

### 7. Journal — List Entries — `GET /api/journal`

Authenticated. List journal entries for the current user.

**Query Parameters:**

| Param | Type | Default | Description |
|---|---|---|---|
| `page` | int | 1 | Page number |
| `limit` | int | 20 | Entries per page (max 100) |
| `include_archived` | bool | false | Include soft-deleted entries |

**Response `200` — `JournalListResponse`:**
```json
{
  "entries": [
    {
      "id": "uuid",
      "user_id": "...",
      "title": "Morning reflection",
      "content": "Today I felt...",
      "mood": "calm",
      "mood_rating": 7,
      "tags": ["morning", "gratitude"],
      "created_at": "2026-05-18T08:00:00Z",
      "updated_at": "2026-05-18T08:00:00Z",
      "is_archived": false
    }
  ],
  "total_count": 25,
  "page": 1,
  "limit": 20,
  "has_more": true
}
```

---

### 8. Journal — Create Entry — `POST /api/journal`

Authenticated. Create a new journal entry.

**Request:**
```json
{
  "title": "Evening reflection",
  "content": "I had a productive day...",
  "mood": "happy",
  "mood_rating": 8,
  "tags": ["evening", "productivity"]
}
```

| Field | Type | Required | Constraints |
|---|---|---|---|
| `title` | string | Yes | 1-200 chars |
| `content` | string | Yes | 1-10000 chars |
| `mood` | string | No | Max 50 chars |
| `mood_rating` | int | No | 1-10 |
| `tags` | string[] | No | Max 10 items |

**Response `201` — `JournalEntry`:** Same shape as `/api/journal` list items.

---

### 9. Journal — Get Entry — `GET /api/journal/{entry_id}`

Authenticated. Retrieve a single journal entry.

**Response `200`:** `JournalEntry` object.

**Errors:** `404` if not found.

---

### 10. Journal — Update Entry — `PUT /api/journal/{entry_id}`

Authenticated. Update fields of an existing journal entry.

**Request:** All fields optional (partial update).
```json
{
  "title": "Updated title",
  "mood_rating": 6
}
```

**Response `200`:** Updated `JournalEntry`.

---

### 11. Journal — Archive Entry — `DELETE /api/journal/{entry_id}`

Authenticated. Soft-delete (archive) a journal entry.

**Response `204`:** No content.

---

### 12. Telemetry — `POST /api/telemetry/`

Unauthenticated. Log a user-task interaction event.

**Request:**
```json
{
  "user_id": "uuid",
  "task_id": "uuid",
  "interaction_type": "VIEWED",
  "completion_time": 300,
  "drop_off_point": null,
  "xp_earned": 10,
  "dedupe_key": "uuid (optional, idempotency)",
  "user_rating": 4,
  "feedback_text": "Task was helpful"
}
```

| Field | Type | Required | Description |
|---|---|---|---|
| `user_id` | UUID | Yes | User identifier |
| `task_id` | UUID | Yes | Task identifier |
| `interaction_type` | enum | Yes | `VIEWED`, `STARTED`, `COMPLETED`, `SKIPPED` |
| `completion_time` | int | No | Seconds, ≥ 0 |
| `drop_off_point` | float | No | 0.0-1.0 |
| `xp_earned` | int | No | ≥ 0 |
| `dedupe_key` | UUID | No | Idempotency key |
| `user_rating` | int | No | 1-5 |
| `feedback_text` | string | No | Max 1000 chars |

**Response `201`:**
```json
{
  "log_id": "uuid",
  "user_id": "uuid",
  "task_id": "uuid",
  "interaction_type": "VIEWED",
  "recorded_at": "2026-05-18T12:00:00Z",
  "idempotent": false
}
```

Returns `204` if duplicate (`dedupe_key` match).

---

### 13. Audit — `POST /audit`

Unauthenticated. Run a clinical safety audit on a roadmap.

**Request:**
```json
{
  "user_id": "string",
  "overview_paragraph": "string",
  "task_contents": [
    {
      "task_id": "task_001",
      "content": "Practice breathing exercise",
      "symptom_tags": ["anxiety"],
      "safety_risk": false,
      "difficulty": 2,
      "xp_reward": 10,
      "utility_score": 0.8,
      "source_reference": "DSM-5",
      "metadata": {}
    }
  ],
  "locale": "en"
}
```

**Response `200` — `AuditResult`:**
```json
{
  "safety_status": "GREEN",
  "next_checkup_days": 14,
  "emergency_payload": null,
  "flags": {
    "crisis_detected": false,
    "crisis_keywords_found": [],
    "robotic_tone_detected": false,
    "safety_risk_task_found": false,
    "safety_risk_task_ids": [],
    "frustration_detected": false,
    "frustration_score": 0.0
  },
  "overview_paragraph": "...",
  "task_ids": ["task_001"],
  "frustration_score": 0.0,
  "amber_advisory": false
}
```

When `safety_status` is `"RED"`, `emergency_payload` is populated:
```json
{
  "emergency_payload": {
    "message": "Immediate support is available...",
    "hotlines": [
      { "name": "988 Suicide & Crisis Lifeline", "number": "988", "description": "24/7 support" }
    ],
    "immediate_action": "Contact emergency services or a crisis helpline immediately.",
    "locale": "en"
  }
}
```

---

### 14. Service Health Checks (Unauthenticated)

| Endpoint | Method | Description |
|---|---|---|
| `/assessment/health` | GET/HEAD | Assessment service status |
| `/knowledge_base/health` | GET/HEAD | ChromaDB health + document count |
| `/architect/health` | GET/HEAD | Architect service status |
| `/ingestion/health` | GET/HEAD | Ingestion service status |
| `/auditor/health` | GET/HEAD | Auditor service status |
| `/api/roadmap/health` | GET/HEAD | Roadmap service status |

---

## Flutter Integration

### Dependencies (`pubspec.yaml`)

```yaml
dependencies:
  http: ^1.2.0
  supabase_flutter: ^2.5.0
```

### Setup — `main.dart`

```dart
import 'package:supabase_flutter/supabase_flutter.dart';

void main() async {
  WidgetsFlutterBinding.ensureInitialized();
  await Supabase.initialize(
    url: 'https://your-project.supabase.co',
    anonKey: 'your-anon-key',
  );
  runApp(const UpHealApp());
}
```

### API Client

```dart
import 'package:http/http.dart' as http;
import 'package:supabase_flutter/supabase_flutter.dart';

class UpHealApi {
  static const String baseUrl = 'https://upheal-gateway.onrender.com';

  static Map<String, String> _headers() {
    final token = Supabase.instance.client.auth.currentSession?.accessToken ?? '';
    return {
      'Authorization': 'Bearer $token',
      'Content-Type': 'application/json',
    };
  }

  // ── Health ──
  static Future<Map<String, dynamic>> healthCheck() async {
    final res = await http.get(Uri.parse('$baseUrl/health'));
    return _json(res);
  }

  // ── Assess ──
  static Future<Map<String, dynamic>> assess({
    Map<String, dynamic>? rawFormsJson,
    Map<String, int>? answers,
    double? screenTimeMinutes,
    Map<String, dynamic>? screenTimeData,
    String locale = 'en',
    String? sessionId,
  }) async {
    final body = <String, dynamic>{
      if (rawFormsJson != null) 'raw_forms_json': rawFormsJson,
      if (answers != null) 'answers': answers,
      if (screenTimeMinutes != null) 'screen_time_minutes': screenTimeMinutes,
      if (screenTimeData != null) 'screenTimeData': screenTimeData,
      'locale': locale,
      if (sessionId != null) 'session_id': sessionId,
    };
    final res = await http.post(
      Uri.parse('$baseUrl/api/assess'),
      headers: _headers(),
      body: jsonEncode(body),
    );
    return _json(res);
  }

  // ── Roadmap ──
  static Future<Map<String, dynamic>> generateRoadmap({
    Map<String, dynamic>? rawFormsJson,
    Map<String, int>? answers,
    double? screenTimeMinutes,
    Map<String, dynamic>? screenTimeData,
    int topN = 5,
    String locale = 'en',
  }) async {
    final body = <String, dynamic>{
      if (rawFormsJson != null) 'raw_forms_json': rawFormsJson,
      if (answers != null) 'answers': answers,
      if (screenTimeMinutes != null) 'screen_time_minutes': screenTimeMinutes,
      if (screenTimeData != null) 'screenTimeData': screenTimeData,
      'top_n': topN,
      'locale': locale,
    };
    final res = await http.post(
      Uri.parse('$baseUrl/api/roadmap'),
      headers: _headers(),
      body: jsonEncode(body),
    );
    return _json(res);
  }

  // ── Roadmap Status ──
  static Future<Map<String, dynamic>> roadmapStatus(String userId) async {
    final res = await http.get(
      Uri.parse('$baseUrl/api/roadmap/$userId/status'),
      headers: _headers(),
    );
    return _json(res);
  }

  // ── Chat ──
  static Future<Map<String, dynamic>> sendMessage({
    required String message,
    String? sessionId,
    String? roadmapId,
  }) async {
    final body = <String, dynamic>{
      'message': message,
      if (sessionId != null) 'session_id': sessionId,
      if (roadmapId != null) 'roadmap_id': roadmapId,
    };
    final res = await http.post(
      Uri.parse('$baseUrl/api/chat'),
      headers: _headers(),
      body: jsonEncode(body),
    );
    return _json(res);
  }

  static Future<Map<String, dynamic>> chatHistory(String sessionId) async {
    final res = await http.get(
      Uri.parse('$baseUrl/api/chat/$sessionId/history'),
      headers: _headers(),
    );
    return _json(res);
  }

  // ── Journal ──
  static Future<Map<String, dynamic>> listJournal({
    int page = 1,
    int limit = 20,
    bool includeArchived = false,
  }) async {
    final res = await http.get(
      Uri.parse('$baseUrl/api/journal?page=$page&limit=$limit'
          '&include_archived=$includeArchived'),
      headers: _headers(),
    );
    return _json(res);
  }

  static Future<Map<String, dynamic>> createJournal({
    required String title,
    required String content,
    String? mood,
    int? moodRating,
    List<String>? tags,
  }) async {
    final body = <String, dynamic>{
      'title': title,
      'content': content,
      if (mood != null) 'mood': mood,
      if (moodRating != null) 'mood_rating': moodRating,
      if (tags != null) 'tags': tags,
    };
    final res = await http.post(
      Uri.parse('$baseUrl/api/journal'),
      headers: _headers(),
      body: jsonEncode(body),
    );
    return _json(res);
  }

  static Future<Map<String, dynamic>> getJournal(String entryId) async {
    final res = await http.get(
      Uri.parse('$baseUrl/api/journal/$entryId'),
      headers: _headers(),
    );
    return _json(res);
  }

  static Future<Map<String, dynamic>> updateJournal(String entryId, {
    String? title,
    String? content,
    String? mood,
    int? moodRating,
    List<String>? tags,
  }) async {
    final body = <String, dynamic>{
      if (title != null) 'title': title,
      if (content != null) 'content': content,
      if (mood != null) 'mood': mood,
      if (moodRating != null) 'mood_rating': moodRating,
      if (tags != null) 'tags': tags,
    };
    final res = await http.put(
      Uri.parse('$baseUrl/api/journal/$entryId'),
      headers: _headers(),
      body: jsonEncode(body),
    );
    return _json(res);
  }

  static Future<void> archiveJournal(String entryId) async {
    final res = await http.delete(
      Uri.parse('$baseUrl/api/journal/$entryId'),
      headers: _headers(),
    );
    if (res.statusCode != 204) {
      throw Exception('Failed to archive journal entry: ${res.statusCode}');
    }
  }

  // ── Telemetry ──
  static Future<Map<String, dynamic>> logTelemetry({
    required String userId,
    required String taskId,
    required String interactionType, // VIEWED | STARTED | COMPLETED | SKIPPED
    int? completionTime,
    double? dropOffPoint,
    int xpEarned = 0,
    String? dedupeKey,
    int? userRating,
    String? feedbackText,
  }) async {
    final body = <String, dynamic>{
      'user_id': userId,
      'task_id': taskId,
      'interaction_type': interactionType,
      if (completionTime != null) 'completion_time': completionTime,
      if (dropOffPoint != null) 'drop_off_point': dropOffPoint,
      'xp_earned': xpEarned,
      if (dedupeKey != null) 'dedupe_key': dedupeKey,
      if (userRating != null) 'user_rating': userRating,
      if (feedbackText != null) 'feedback_text': feedbackText,
    };
    final res = await http.post(
      Uri.parse('$baseUrl/api/telemetry/'),
      headers: {'Content-Type': 'application/json'},
      body: jsonEncode(body),
    );
    return _json(res);
  }

  // ── Audit ──
  static Future<Map<String, dynamic>> audit({
    required String userId,
    required String overviewParagraph,
    required List<Map<String, dynamic>> taskContents,
    String locale = 'en',
  }) async {
    final body = <String, dynamic>{
      'user_id': userId,
      'overview_paragraph': overviewParagraph,
      'task_contents': taskContents,
      'locale': locale,
    };
    final res = await http.post(
      Uri.parse('$baseUrl/audit'),
      headers: {'Content-Type': 'application/json'},
      body: jsonEncode(body),
    );
    return _json(res);
  }

  static Map<String, dynamic> _json(http.Response res) {
    if (res.statusCode >= 400) {
      throw Exception('API error ${res.statusCode}: ${res.body}');
    }
    return jsonDecode(res.body) as Map<String, dynamic>;
  }
}
```

### Screen Time Integration (Android)

```dart
import 'package:usage_stats/usage_stats.dart';

Future<Map<String, dynamic>> collectScreenTimeData() async {
  final now = DateTime.now();
  final start = now.subtract(const Duration(hours: 24));

  final stats = await UsageStats.queryUsageStats(start.millisecondsSinceEpoch, now.millisecondsSinceEpoch);

  double totalMinutes = 0;
  double socialMinutes = 0;
  double productivityMinutes = 0;
  final dailyUsage = <Map<String, dynamic>>[];

  const socialPackages = {'com.instagram.android', 'com.facebook.katana', 'com.twitter.android', 'com.snapchat.android', 'com.zhiliaoapp.musically'};
  const productivityPackages = {'com.google.android.apps.docs', 'com.microsoft.office.outlook', 'com.todoist', 'com.notion'};

  for (final s in stats) {
    final minutes = (s.totalTimeInForeground ?? 0) / 60000.0;
    if (minutes < 1) continue;

    String category = 'other';
    if (socialPackages.contains(s.packageName)) { category = 'social'; socialMinutes += minutes; }
    if (productivityPackages.contains(s.packageName)) { category = 'productivity'; productivityMinutes += minutes; }

    totalMinutes += minutes;
    dailyUsage.add({'packageName': s.packageName, 'usageTime': s.totalTimeInForeground ?? 0, 'category': category});
  }

  return {
    'totalMinutes': totalMinutes,
    'socialMinutes': socialMinutes,
    'productivityMinutes': productivityMinutes,
    'dailyUsage': dailyUsage,
  };
}
```

### Usage Example — Sending an Assessment with Screen Time

```dart
final screenTimeData = await collectScreenTimeData();

final result = await UpHealApi.assess(
  answers: {'gad7_q1': 2, 'gad7_q2': 1, 'phq9_q1': 1, 'phq9_q2': 0},
  screenTimeData: screenTimeData,
);

final safetyStatus = result['safety_status']; // "GREEN" | "YELLOW" | "RED"
final tasks = (result['suggested_tasks'] as List).cast<Map<String, dynamic>>();
final days = (result['days'] as List).cast<Map<String, dynamic>>();
```

---

## Error Responses

All endpoints return errors in this shape:

```json
{
  "detail": "Error message describing what went wrong"
}
```

| Code | Meaning |
|---|---|
| `401` | Missing or invalid JWT token |
| `403` | Authenticated but not authorized (e.g., accessing another user's data) |
| `404` | Resource not found |
| `422` | Validation error |
| `429` | Rate limited |
| `500` | Server error |

---

## CORS

The server allows cross-origin requests. In production, set the `ALLOWED_ORIGINS` env var on Render to restrict origins:

```
ALLOWED_ORIGINS=https://your-frontend.vercel.app,https://upheal.app
```

During development, `*` is the default, so all origins are allowed.

---

## Quick Reference Table

| # | Method | Endpoint | Auth | Description |
|---|---|---|---|---|
| 1 | GET | `/health` | No | Gateway health check |
| 2 | POST | `/api/assess` | Yes | Full clinical assessment |
| 3 | POST | `/api/roadmap` | Yes | Generate 90-day roadmap |
| 4 | GET | `/api/roadmap/{user_id}/status` | Yes | Check reassessment status |
| 5 | POST | `/api/chat` | Yes | Send chat message |
| 6 | GET | `/api/chat/{session_id}/history` | Yes | Get chat history |
| 7 | GET | `/api/journal` | Yes | List journal entries |
| 8 | POST | `/api/journal` | Yes | Create journal entry |
| 9 | GET | `/api/journal/{entry_id}` | Yes | Get single entry |
| 10 | PUT | `/api/journal/{entry_id}` | Yes | Update entry |
| 11 | DELETE | `/api/journal/{entry_id}` | Yes | Archive entry |
| 12 | POST | `/api/telemetry/` | No | Log task interaction |
| 13 | POST | `/audit` | No | Run safety audit |
| 14 | GET | `/assessment/health` | No | Assessment service health |
| 15 | GET | `/knowledge_base/health` | No | Knowledge base health |
| 16 | GET | `/architect/health` | No | Architect service health |
| 17 | GET | `/ingestion/health` | No | Ingestion service health |
| 18 | GET | `/auditor/health` | No | Auditor service health |
| 19 | GET | `/api/roadmap/health` | No | Roadmap service health |