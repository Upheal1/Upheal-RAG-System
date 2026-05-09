# Hozaifa Implementation Changelog

Changelog for Hozaifa's implementation tasks (Phase 1 - Knowledge Infrastructure).

---

## [Unreleased]

---

## [Completed]

### A-HOZ-07: Integrity Check Script

**Status:** ✅ Done

**Files Changed:**
- `scripts/verify_integrity.py` - Integrity checker for ChromaDB metadata
- `tests/test_verify_integrity.py` - 22 tests

**Features Implemented:**
- Scans every document in a ChromaDB collection for mandatory metadata fields
- Validates `difficulty` (1-5), `xp_reward` (>= 0), and `clinical_tags` (non-empty)
- Paginates through large collections (500-item batches)
- Pretty-prints violation table with `task_id` and missing/invalid fields
- Exit code 0 when clean, 1 when violations found, 2 on checker errors
- Respects `UPHEAL_CHROMA_PATH` and `UPHEAL_CHROMA_COLLECTION` env vars
- Runnable standalone: `python scripts/verify_integrity.py [<path> <collection>]`

**Testing:** 22 tests passing

---

### A-HOZ-08: GET /health for Knowledge Base

**Status:** ✅ Done

**Files Changed:**
- `services/knowledge_base/router.py` - Refactored with `KnowledgeBaseHealthResponse` Pydantic model
- `services/knowledge_base/chroma_adapter.py` - Added `get_collection_metadata()` helper
- `tests/test_kb_router.py` - 9 tests
- `docs/services/microservices.md` - Documented endpoint

**Features Implemented:**
- Response shape matches Phase 1 spec: `indexed_tasks`, `storage_status`, `last_ingestion`
- `storage_status` derived as `healthy` | `degraded` | `unavailable`
- `last_ingestion` read from collection metadata or `config.json` fallback
- OpenAPI-validated response model

**Testing:** 9 tests passing

---

### A-HOZ-10: Supabase Schema (Expanded) + Schema Enhancement Sprint

**Branch:** `A-HOZ-06-chroma-adapter`
**Status:** ✅ Done

**Files Changed:**
- `supabase/migrations/001_create_interaction_logs.sql`
- `supabase/migrations/002_create_roadmap_mutations.sql`
- `supabase/migrations/003_create_users_and_profiles.sql`
- `supabase/migrations/004_create_clinical_tasks.sql`
- `supabase/migrations/005_create_roadmaps_and_tasks.sql`
- `supabase/migrations/006_create_assessment_responses.sql`
- `supabase/migrations/007_create_interest_profiles.sql`
- `supabase/migrations/008_add_foreign_keys.sql`
- `supabase/migrations/009_create_retrieval_logs_and_chat.sql` *(new)*
- `supabase/migrations/010_add_data_retention_cleanup.sql` *(new)*
- `supabase/migrations/011_fix_security_definer_functions.sql` *(new)*
- `supabase/README.md`
- `supabase/combined_migrations.sql`
- `docs/database-schema.md` *(new)*

**Schema Implemented (001–008):**
- `users` — auth baseline
- `user_profiles` — GAD-7/PHQ-9 scores, screen time, user_level
- `assessment_responses` — raw form submissions (EN/AR)
- `clinical_tasks` — canonical task definitions synced with Chroma metadata
- `roadmaps` / `roadmap_tasks` — per-generation roadmap with validity window
- `interaction_logs` — Phase 3 telemetry (VIEWED/STARTED/COMPLETED/SKIPPED)
- `roadmap_mutations` — Director mutation audit trail
- `interest_profiles` — Director-evolved tag/modality preferences

**Schema Enhancements (009–011):**
- `retrieval_logs` — Chroma retrieval traces with similarity scores and filters for Director self-correction
- `chat_sessions` / `chat_messages` — LLM conversational history
- `xp_transactions` — Gamification audit ledger (every XP change traced)
- `retention_settings` — Configurable cleanup policy per log table
- `log_table_sizes` — Monitoring view for table growth
- `user_profiles` — **Removed** `modality_weights` and `tag_boosts` (redundancy fix; dynamic prefs live in `interest_profiles`)
- `interaction_logs` — Added `user_rating` (1–5) and `feedback_text` for qualitative Director signals
- `roadmap_tasks.status` — Changed from `TEXT` to `roadmap_task_status` enum (ASSIGNED/IN_PROGRESS/COMPLETED/SKIPPED/DROPPED)
- `roadmap_mutations` — Security fix: wrapped `rls_auto_enable` revocation in conditional `DO $$` block
- Cleanup functions: `cleanup_interaction_logs()`, `cleanup_chat_messages()`, `cleanup_retrieval_logs()`, `cleanup_assessment_responses()`, `run_all_cleanup()`
- Security helper: `list_security_definer_functions()` — audits exposed SECURITY DEFINER functions

**Foreign keys:** 15 FK constraints linking all tables to `users`, `clinical_tasks`, `roadmaps`, `chat_sessions`.

**Cloud Deployment:** All 11 migrations applied to `gcxxmjptbyvlabqzcprv.supabase.co`.

**UUID Standard:** Switched from `uuid_generate_v4()` (uuid-ossp) to `gen_random_uuid()` (pgcrypto) for universal Supabase compatibility.

---

### A-HOZ-06: ChromaDB Hybrid Adapter ⭐ GATE

**Branch:** `A-HOZ-06-chroma-adapter`
**Status:** ✅ Done

**Files Changed:**
- `services/knowledge_base/chroma_adapter.py` - Full hybrid ChromaDB adapter
- `services/shared/schemas.py` - Added `RetrievalQuery` schema, updated `ClinicalTask` with top-level `safety_risk`/`utility_score`
- `services/gateway/main.py` - Updated `retrieve_tasks()` call site to use `RetrievalQuery`
- `tests/test_chroma_adapter.py` - 27 unit tests covering all new logic
- `tests/integration/test_chroma_adapter_real.py` - 10 integration tests against real ChromaDB collection
- `tests/fixtures/clinical_tasks.py` - Promoted `safety_risk`/`utility_score` to top-level fields

**Features Implemented:**
- `RetrievalQuery` schema with `query_text`, `symptom_keywords`, `max_difficulty`, `boost_digital_detox`
- `ClinicalTask.safety_risk` and `ClinicalTask.utility_score` promoted from `metadata` to top-level fields
- `ChromaKnowledgeBase.retrieve_tasks(query, user_context, top_k)` refactored to accept `RetrievalQuery`
- `max_difficulty` filter applied via ChromaDB `where` clause (`$lte`)
- `boost_digital_detox` reranks tasks with digital-detox tags to the front
- HNSW configuration: explicit `cosine` space, tunable `ef_search`, `ef_construction`, `m` params
- `get_or_create_collection` with metadata for consistent HNSW settings
- `_safety_risk_from_metadata()` and `_utility_score_from_metadata()` helper extractors
- Comprehensive unit + integration test suite

**Testing:** 45 unit tests + 10 integration tests passing

---

### A-HOZ-05: Formatter Agent

**Branch:** `A-HOZ-05-formatter-agent`
**PR:** [#19](https://github.com/Upheal1/Upheal-RAG-System/pull/19)
**Status:** ✅ Done

**Files Changed:**
- `services/ingestion/formatter_agent.py` - LLM integration implementation
- `tests/test_formatter_agent.py` - 26 new tests
- `.env.example` - Added LLM API key configuration

**Features Implemented:**
- LLM integration (OpenAI GPT / Google Gemini via env vars)
- Per-chunk labeling: difficulty (1-5), xp_reward, symptom_tags, safety_risk
- Output validates against ClinicalTask schema
- Crisis keywords detection (suicide, self-harm, etc.) sets safety_risk = True
- Token/cost guard with batch size cap (max 25)
- Fallback keyword-based formatter when no LLM configured

**Testing:** 138 tests passing (all tests)

---

### A-HOZ-04: Semantic Chunker

**Branch:** `A-HOZ-04-semantic-chunker`
**PR:** [#8](https://github.com/Upheal1/Upheal-RAG-System/pull/8)
**Status:** ✅ Done

**Files Changed:**
- `services/ingestion/semantic_chunker.py` - Semantic chunking implementation
- `tests/test_semantic_chunker.py` - 30 new tests

**Features Implemented:**
- Sentence-aware splitting with regex-based boundary detection
- Sliding window aligned to sentence boundaries
- 15% overlap between consecutive chunks
- Topic-shift detection via embedding cosine similarity drop
- Token count estimation with word-based approximation
- Chunk overlap info analysis

**Testing:** 101 tests passing (all tests)

---

### A-HOZ-03: PDF Extraction and Noise Filter

**Branch:** `A-HOZ-03-pdf-extraction`
**PR:** [#7](https://github.com/Upheal1/Upheal-RAG-System/pull/7)
**Status:** ✅ Done (pending merge)

**Files Changed:**
- `services/ingestion/pdf_utils.py` - PDF extraction and noise filtering
- `tests/test_pdf_utils.py` - 38 new tests

**Features Implemented:**
- Text extraction using pdfplumber with structure preservation
- Noise filtering: bibliography, headers/footers, disclaimers, index sections
- Unicode normalization and whitespace cleanup
- SHA-256 file hashing for integrity
- Overlapping chunk extraction
- Batch processing with `extract_all_pdfs()`
- Structured logging integration

**Testing:** 71 tests passing

---

### A-HOZ-09: Initial Clinical PDF Migration Script

**Status:** ✅ Done

**Files Changed:**
- `scripts/migrate_initial_clinical_library.py` - Full pipeline migration script
- `tests/test_migrate.py` - 12 tests (10 unit, 2 integration)

**Features Implemented:**
- Loads `semantic_chunks.json`, formats metadata via formatter agent, embeds, upserts into ChromaDB
- Idempotent: wipe-and-rebuild strategy (deletes existing collection before re-ingestion)
- `--books` filter for specific source files, or ingests all by default
- `--use-llm` flag for LLM-based formatting (keyword fallback by default)
- `--dry-run` mode for validation without ChromaDB writes
- Structured logging end-to-end via `services.shared.logging`
- Emits `config.json` with `last_ingestion` timestamp for health endpoint
- Respects `UPHEAL_CHROMA_PATH`, `UPHEAL_CHROMA_COLLECTION`, `UPHEAL_EMBEDDING_MODEL` env vars
- CLI: `python scripts/migrate_initial_clinical_library.py [options]`

**Testing:** 12 tests (10 unit + 2 integration with embedding model)

---

### A-HOZ-02: Structured JSON Logger

**Branch:** `A-HOZ-02-logging`
**PR:** [#5](https://github.com/Upheal1/Upheal-RAG-System/pull/5)
**Status:** ✅ Done (merged to staging)

**Files Changed:**
- `services/shared/logging.py` - Complete rewrite with structured JSON logging
- `tests/test_logging.py` - 17 new tests

**Features Implemented:**
- `JSONFormatter` - Formats log records as valid JSON with timestamp, service, event, payload
- `ContextFilter` - Thread-safe per-request context injection
- `get_logger(name)` - Returns structured logger with auto-derived service names
- `configure_logging()` - Configures root logger with JSON/plain output, optional file path
- Convenience helpers: `log_pdf_start()`, `log_chunk_created()`, `log_formatter_done()`, `log_chroma_upsert()`

**Testing:** 71 tests passing

---

### A-HOZ-01: Pydantic Schemas

**Status:** ✅ Done (in `main`)
**Commit:** 362f70e

**Files:**
- `services/shared/schemas.py` - ClinicalTask, UserContext, FinalRoadmap, LegacyRAGRecommendation, AssessGatewayResponse

---

## Completed

### A-HOZ-11: State Manager

**Branch:** `A-HOZ-11`
**Status:** ✅ Done

**Files Changed:**
- `services/shared/state.py` - Full state manager module
- `tests/test_state.py` - 40 unit tests
- `.env.example` - Added `UPHEAL_DATA_DIR`, `UPHEAL_SUPABASE_URL`, `UPHEAL_SUPABASE_KEY`

**Features Implemented:**
- **Pathing helpers:** `data_root()`, `books_dir()`, `rag_chunks_dir()`, `vector_db_path()`, `semantic_chunks_path()`, `config_path()`, `list_pdf_books()`, `ensure_data_dirs()` — all env-override aware (`UPHEAL_DATA_DIR`, `UPHEAL_CHROMA_PATH`, `UPHEAL_CHROMA_COLLECTION`, `UPHEAL_EMBEDDING_MODEL`)
- **Supabase sync hooks:** `SupabaseSyncHook` with optimistic locking (`version` column), `insert_row()`, `fetch_one()`, `upsert_row()` (conflict detection), `delete_row()`, lazy client construction from env vars
- **Offline retry backoff:** `retry_with_backoff()` with exponential backoff (1 s → 2 s → 4 s → … cap 60 s), configurable retryable predicate, `OfflineRetryExhausted` exception
- **Utilities:** `file_sha256()` for integrity checks, `load_config()` / `save_config()` for ingestion config.json round-trips
- **`SyncConflictError`** raised on stale optimistic-lock writes

**Testing:** 40 unit tests passing

---

## Pending Tasks

---