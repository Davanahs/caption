# ClipForge Engineering Defect & Capability Register

**Document Type:** Authoritative Defect & Architectural Gap Register  
**Governing Standard:** `MASTER_ENGINEERING_RULEBOOK.md` & `ANTIGRAVITY_CLIPFORGE_FREEZE_RULES.md`  
**Repository Root:** `d:\automation video clips\clipforge`  
**Active Phase:** Phase 0.1 (Baseline Reconciliation & Tracking)  
**Last Updated:** 2026-10-26
**Status Policy:** Every defect ID is stable, evidence-backed, and mapped to exact code locations, runtime tests, and proposed isolated remediation phases.

---

## 1. Summary Matrix

| Defect / Item ID | Category | Title | Affected Subsystem | Severity | Status | Target Remediation Phase |
|---|---|---|---|---|---|---|
| `CF-DEF-001` | Bug | Storage Cleanup Missing Globally on Backend | `clips.py`, `cleanup_storage.py` | High | `RESOLVED IN PHASE 1.3` | Phase 1.3 |
| `CF-DEF-002` | Bug | Cross-Origin Relative URL Bug in `RetentionHeatmap` | `RetentionHeatmap.tsx` | High | `RESOLVED IN PHASE 2.1` | Phase 2.1 |
| `CF-DEF-003` | UI Gap | Publishing Queue Cancel & Retry Actions Missing | `publish/page.tsx` | Medium | `RESOLVED IN PHASE 3.1` | Phase 3.1 |
| `CF-DEF-005` | UI Gap | Per-Video Analytics & Optimization Subsystem Disconnected | `analytics.py`, `analytics/page.tsx` | Medium | `RESOLVED & VERIFIED IN PHASE 4.1` | Phase 4.1 |
| `CF-DEF-007` | Doc Discrepancy | Documentation Migration Head Stale | `LOGIC_FREEZE_LEDGER.md` | Low | `RESOLVED IN PHASE 0.1` | Phase 0.1 |
| `CF-DEF-008` | Bug | Cross-Channel Batch Selection Loss & Indiscriminate Dequeue | `automation/page.tsx` | High | `RESOLVED IN PHASE 1.1` | Phase 1.1 |
| `CF-DEF-009` | Bug | Unscoped Synthetic Fixture Interception in Downloader/Transcriber | `downloader.py`, `transcriber.py` | Medium | `RESOLVED IN PHASE 1.2.1` | Phase 1.2.1 |
| `CF-DEF-010` | Bug | Decision Cancellation Terminal State Guard in Celery Beat Sweep | `orchestration.py` | Low | `RESOLVED IN PHASE 1.2.1` | Phase 1.2.1 (Incidental) |
| `CF-DEF-011` | Bug | Unscoped Synthetic SFX Fallback Generation in Production | `sfx_planner.py` | High | `RESOLVED IN PHASE 2.1.1A.1` | Phase 2.1.1A.1 |
| `CF-DEF-012` | Bug | Unsafe GET Side-Effects and Event-Loop Blocking in SFX Plan Retrieval | `clips.py`, `virality_predictor.py` | Medium | `RESOLVED IN PHASE 2.1.1B` | Phase 2.1.1B |
| `CF-DEF-013` | Discrepancy | Batch B Remote YouTube Privacy Desynchronization (`public` on YT, `private` in DB) | `publisher.py`, `prepare_publishing_batch.py` | Medium | `WRITABLE STATUS FIELD PRESERVATION AUDITED & VERIFIED (48/48 PRIVACY, 107 TOTAL PASSING)` | Publishing Privacy Hardening |
| `CF-DEF-014` | Doc Discrepancy | Conflicting Test Suite Totals Across Historical Reports (324 vs 311 vs 229 vs 460 actual) | Audit Reports | Low | `RECONCILED (AUDIT)` | Forensic Reconciliation |
| `CF-DEF-015` | Test Fixture | Missing Preamble Fixture in `studio_backend_e2e.test.mjs` | `studio_backend_e2e.test.mjs` | Low | `DOCUMENTED (AUDIT)` | Test Fixtures |
| `CF-DEF-016` | Limitation | Channel Discovery Ceiling Bounded by 100-Video Scan Cap | `downloader.py` | Low | `BOUNDED PAGINATION IMPLEMENTED (DEPTH 250)` | Gap Closure Phase 3 |
| `CF-DEF-017` | Test Runner | Unisolated Frontend Test Execution Against Live Backend | `frontend/package.json`, `test/*.test.mjs` | Medium | `RESOLVED (ISOLATED RUNNER & RUN_LIVE_E2E GUARDS)` | Safe Test Isolation |
| `CF-DEF-021` | UX | Four-Option Historical Selection Confusion | `automation/page.tsx` | Low | `RESOLVED IN MONITORING REPAIRS` | Monitoring Repairs |
| `CF-DEF-022` | Ingestion Bug | Self-Ingestion of Published Output Shorts via Channel Monitoring & Batch | `provenance.py`, `channel_monitor.py`, `channels.py`, `jobs.py` | High | `RESOLVED & VERIFIED IN MONITORING REPAIRS` | Monitoring Repairs |
| `CF-DEF-023` | Contract Bug | Auto-Publish Destination Enforcing & Worker Silent Failure | `channels.py`, `clip_tasks.py`, `automation/page.tsx` | High | `RESOLVED & VERIFIED IN AUDIT REPAIRS` | Monitoring Repairs |
| `REQ-GAP-001` | Architecture | Settings Backend Persistence Architecture | `settings.py`, `settings/page.tsx` | Medium | `RESOLVED & VERIFIED IN PHASE 5.1` | Phase 5.1 (C-09) |
| `CAP-001` | Capability | Multi-Language Auto-Dubbing Prototype | `dubbing.py`, `dubbing_tasks.py` | None | `DEFERRED CAPABILITY` | Phase 6.1 (Optional) |


---

## 2. Detailed Defect & Gap Specifications

### `CF-DEF-001` — Storage Cleanup Missing Globally on Backend
- **Category:** Functional Code Defect (Missing Backend Handlers)
- **Code Locations:**
  - Caller: `frontend/app/clips/page.tsx:253,266` via `previewCleanup()` and `executeCleanup()`
  - Client Definition: `frontend/lib/api.ts:129-130`
    * `export const previewCleanup = () => request<any>('/api/clips/cleanup/preview');`
    * `export const executeCleanup = () => request<any>('/api/clips/cleanup/execute', { method: 'POST' });`
  - Backend Module: `backend/api/routes/clips.py`
- **Expected Behavior:** `GET /api/clips/cleanup/preview` returns removable clips count and reclaimable bytes. `POST /api/clips/cleanup/execute` executes storage cleanup and returns deleted count.
- **Actual Observed Behavior:** Neither route exists in `clips.py` or anywhere in FastAPI.
- **Runtime Verification Evidence:**
  1. Python reflection searching all 106 registered routes for `'cleanup'` returned `[]`.
  2. Direct HTTP probe to `http://localhost:8000/api/clips/cleanup/preview` returned:
     `HTTP 404: {"detail":"Not Found"}`
  3. Direct HTTP probe to `http://localhost:8000/api/clips/cleanup/execute` returned:
     `HTTP 404: {"detail":"Not Found"}`
- **User Impact:** Clicking "Preview Cleanup" or "Execute Cleanup" on the Clips page throws browser alert error.
- **Severity:** High (Broken user-facing button causing runtime HTTP 404).
- **Dependencies:** L3 (Storage Service), L9 (API Routes), L10 (Clips UI).
- **Proposed Isolated Remediation:** In Phase 1.1, implement `GET /api/clips/cleanup/preview` and `POST /api/clips/cleanup/execute` in `backend/api/routes/clips.py` wrapping `backend.cleanup_storage.preview()` and `cleanup()`.

---

### `CF-DEF-002` — Cross-Origin Relative URL Bug in `RetentionHeatmap.tsx`
- **Category:** Functional Code Defect (URL Resolution / Port Mismatch)
- **Status:** **RESOLVED & VERIFIED IN PHASE 2.1**
- **Code Location:** `frontend/components/RetentionHeatmap.tsx`
- **Expected Behavior:** Component requests target the backend API server (`http://localhost:8000`) using typed methods in `@/lib/api`.
- **Actual Observed Behavior:** Previously used raw relative URLs without `API_BASE`. Because Next.js runs on port 3000 and has no API rewrites in `next.config.ts`, browser issued HTTP requests to `http://localhost:3000/api/clips/...`, returning 404 HTML from Next.js.
- **Remediation:** Replaced relative fetch calls in `RetentionHeatmap.tsx` with typed client methods `getClipRetention` and `applyAutofix` from `frontend/lib/api.ts`.
- **Runtime Verification Evidence:** Verified via `phase_2_1_browser_verification.test.mjs` and Playwright browser execution without relative 404 URL errors.
- **Severity:** High (Resolved).
- **Dependencies:** L7 (Analysis Endpoints), L9 (FastAPI), L10 (Retention Heatmap Widget).

---

### `CF-DEF-003` — Publishing Queue Cancel & Retry Actions Missing in UI
- **Category:** User Interface Gap (Missing Interactive Triggers)
- **Status:** **RESOLVED & VERIFIED IN PHASE 3.1 (C-05)**
- **Code Locations:**
  - Backend Endpoints: `GET /api/publish/queue`, `POST /api/publish/clips/{clip_id}/cancel`, `POST /api/publish/clips/{clip_id}/retry` (`backend/api/routes/publish.py`)
  - Client Helpers: `frontend/lib/api.ts` (`getPublishQueue`, `retryPublish`, `cancelPublish`)
  - UI Page: `frontend/app/publish/page.tsx`
- **Expected Behavior:** Queued, scheduled, failed, and in-flight publishing items displayed in `/publish` queue drawer render interactive Cancel, Retry, and Force Retry buttons allowing users to govern the publishing lifecycle.
- **Root Cause & Remediation:**
  1. `GET /api/publish/queue` previously selected only `publish_status.in_(["queued", "published"])`, masking failed, cancelling, and manual review items; expanded query to all active/historic publishing statuses and enriched with stage, progress, attempt, error, and timestamp metadata.
  2. `POST /api/publish/clips/{clip_id}/cancel` enhanced with immediate Celery revocation for pending/failed jobs and cooperative `cancelling` for active uploads.
  3. `POST /api/publish/clips/{clip_id}/retry` enhanced with progress reset, Celery dispatch, conflict guards (409 if running, 400 if published), and explicit `force=True` gating for `manual_review` clips.
  4. `frontend/app/publish/page.tsx` updated with responsive Cancel (`btn-cancel-publish-{id}`), Retry (`btn-retry-publish-{id}`), Force Retry (`btn-force-retry-{id}`), and Refresh (`btn-refresh-queue`) buttons, per-item loading spinners, expandable error boxes, and 4-second auto-polling.
- **Runtime Verification Evidence:** Verified with 18/18 passing tests in `backend/tests/test_c05_publish_queue_actions.py` and 71/71 system-wide regression tests. Clean TypeScript check and Next.js build.
- **Severity:** Medium (Resolved).
- **Dependencies:** L8 (Publishing), L9 (API Contracts), L10 (Publishing UI).

---

### `CF-DEF-004` — Clip AI Enhancement Routes Unwired to UI
- **Category:** User Interface Gap (Unwired Subsystems)
- **Status:** **RESOLVED & VERIFIED IN PHASE 2.1**
- **Code Locations:**
  - Backend Endpoints in `backend/api/routes/clips.py`:
    * `GET /api/clips/{clip_id}/broll-plan`, `POST /api/clips/{clip_id}/broll-apply`
    * `GET /api/clips/{clip_id}/sfx-plan`, `POST /api/clips/{clip_id}/sfx-apply`
    * `GET /api/clips/{clip_id}/hook`, `POST /api/clips/{clip_id}/hook/plan`, `POST /api/clips/{clip_id}/hook/apply`
  - UI Page: `frontend/app/clips/page.tsx`
  - API Client: `frontend/lib/api.ts`
- **Expected Behavior:** In the Clip Preview modal, users can preview and apply AI B-roll, SFX, and Hook plans with interactive controls.
- **Root Cause & Remediation:**
  1. Frontend client helpers (`getBrollPlan`, `applyBrollPlan`, `getSfxPlan`, `applySfxPlan`, `getHookPlan`, `generateHookPlan`, `applyHookPlan`) and TypeScript models were missing in `frontend/lib/api.ts`; added in full.
  2. `PreviewModal` in `frontend/app/clips/page.tsx` lacked AI creative enhancement controls; implemented glassmorphic AI Creative Enhancements suite with 3 tabs (Hooks, B-Roll, SFX), live plan previews, and task dispatch triggers.
  3. Fixed backend defect in `backend/tasks/clip_tasks.py` importing `ArtifactManager` from non-existent `storage.manager`.
  4. Fixed `analyze_hook_opportunities_task` in `backend/tasks/hook_tasks.py` to persist `ClipHookPlan` in database.
  5. Fixed `SFXPlanner` in `backend/services/sfx_planner.py` to support mock synthesis fallback when database asset tables are empty and corrected `ArtifactType.AUDIO_SFX`.
- **Runtime Verification Evidence:**
  - Acceptance suite: `backend/tests/test_phase_2_1_clip_ai_enhancements.py` (15/15 passed in 5.68s).
  - Full regression suite: 59/59 passed across all suites in 14.30s.
  - TypeScript compilation: `npx tsc --noEmit` clean (0 errors).
  - Next.js production build: `npm run build` clean (exit code 0).
  - Real browser Playwright verification: `frontend/test/phase_2_1_browser_verification.test.mjs` passed with 4 screenshots (`01_preview_modal_ai_enhancements_hook.png`, `02_preview_modal_ai_enhancements_broll.png`, `03_preview_modal_ai_enhancements_sfx.png`, `04_preview_modal_ai_enhancement_applied.png`).
- **Severity:** Medium (Resolved).
- **Dependencies:** L6 (Video Processing), L7 (Clip Analysis), L9 (FastAPI), L10 (Clips UI).

---

### `CF-DEF-005` — Per-Video Analytics & Optimization Subsystem Disconnected
- **Category:** User Interface Gap (Unwired Endpoints)
- **Status:** **RESOLVED & VERIFIED IN PHASE 4.1 (C-07)**
- **Code Locations:**
  - Backend Endpoints in `backend/api/routes/analytics.py`:
    * `GET /api/analytics/{video_id}`
    * `GET /api/analytics/active`
    * `POST /api/analytics/track/{video_id}`
    * `POST /api/analytics/cancel/{task_id}`
    * `POST /api/analytics/optimize/{video_id}`
    * `PATCH /api/analytics/optimize/{video_id}/flag`
    * `GET /api/analytics/optimize/{video_id}/log`
    * `GET /api/analytics/seo/{video_id}`
  - UI Page: `frontend/app/analytics/page.tsx`
  - API Client: `frontend/lib/api.ts`
  - Service Module: `backend/new_files/performance_tracker.py`
- **Expected Behavior:** Analytics dashboard allows selecting a video to view SEO recommendations, view optimization logs, start/cancel active tracking tasks, and toggle auto-optimization.
- **Root Cause & Remediation:**
  1. Fixed missing `timedelta` import in `backend/new_files/performance_tracker.py` that crashed tracking task creation.
  2. Enriched `list_active_trackers()` with full database queue attributes (`clip_id`, `youtube_video_id`, `uploaded_at`, `next_check_at`, `optimization_attempts`, `last_score`, `status`).
  3. Protected FastAPI event loop against sync blocking I/O using `await asyncio.to_thread(...)` in `start_tracker`, `cancel_tracker`, and `list_active`.
  4. Added dual-direction cross-lookup in `get_seo_analysis`, `get_analytics`, and `get_optimization_log` to seamlessly resolve queries whether addressed with parent `Video.id` or child `Clip.id`.
  5. Implemented `_parse_list()` to normalize hashtag/tag strings, JSON strings, or string arrays into clean string lists for interactive hashtag/keyword chips.
  6. Added 7 typed client methods and 7 TypeScript models to `frontend/lib/api.ts`.
  7. Built comprehensive per-video drilldown on `frontend/app/analytics/page.tsx` with target clip dropdown, VSI score badges, trend arrows, views/likes/comments stats, SEO intelligence chips, auto-optimization logs, and active tracker lifecycle controls.
- **Runtime Verification Evidence:**
  - Focused test suite: `backend/tests/test_c07_video_analytics.py` (16/16 passed in 40.53s).
  - Full system regression: 104/104 passed in 171.99s.
  - TypeScript compilation: `npx tsc --noEmit` clean (0 errors).
  - Next.js production build: `npm run build` clean (11/11 static pages prerendered).
- **Severity:** Medium (Resolved).
- **Dependencies:** L7 (Analysis), L8 (Publishing), L9 (API Contracts), L10 (Analytics UI).

---

### `REQ-GAP-001` — Settings Persistence Architecture
- **Category:** Architecture / Backend Persistence & Dynamic Configuration
- **Code Locations:** `backend/api/routes/settings.py`, `frontend/app/settings/page.tsx`, `frontend/lib/api.ts`, `backend/core/config.py`, `backend/main.py`
- **Delivered Remediation in Phase 5.1 (C-09):**
  1. Created dedicated `backend/api/routes/settings.py` with `GET /api/settings` and `PUT /api/settings`.
  2. Implemented sensitive credential masking: `YOUTUBE_CLIENT_SECRET_SET` flag and `YOUTUBE_CLIENT_SECRET_MASKED` ("••••••••") prevent leaking plaintext secrets in API responses.
  3. Implemented safe partial update: submitting placeholder mask does not overwrite genuine secrets.
  4. Implemented strict parameter validation (allowed Whisper models, clip limit bounds [1, 20], channel check interval bounds [5, 1440], reframe modes).
  5. Implemented durable persistence to `data/settings.json` (protected by `.gitignore`) and immediate dynamic in-memory synchronization of `backend.core.config.settings`.
  6. Connected `init_dynamic_settings()` to backend startup in `backend/main.py`.
  7. Updated `frontend/app/settings/page.tsx` with live backend synchronization, graceful offline `localStorage` fallback, and deterministic testids.
- **Verification Evidence:**
  - `backend/tests/test_c09_settings_persistence.py`: 15/15 passed in 3.57s.
  - Combined differential regression: 134/134 passed across 9 suites in 48.75s.
  - Frontend static build: `npx tsc --noEmit` clean (0 errors), `npm run build` clean (all 11 static routes prerendered).
- **Status:** **RESOLVED & VERIFIED IN PHASE 5.1 (C-09)**.

---

### `CF-DEF-007` — Documentation Migration Head Stale
- **Category:** Documentation Discrepancy
- **Locations:** `docs/engineering/LOGIC_FREEZE_LEDGER.md:6`, `LOGIC_DEPENDENCY_MAP.md:6`
- **Current Code / Evidence:**
  - `python -m alembic current` -> `c3d4e5f6a7b8 (head)`
  - Older documentation claimed `a1b2c3d4e5f6` or `f3b4c5d6e7f8`
- **Status:** `RESOLVED IN PHASE 0.1` (Reconciled across all ledgers, maps, and status docs).

---

### `CF-DEF-008` — Cross-Channel Batch Selection Loss & Indiscriminate Dequeue
- **Category:** Functional Code Defect (Batch Selection & Outcome Reconciliation)
- **Code Locations:** `frontend/app/automation/page.tsx:645-730`
- **Initial Defect:**
  1. The sticky batch action bar routed all selected videos across channels into a single target channel ID (`targetChannelId = Object.values(selectedVideos)[0]?.channelId || selectedChannelId`), conflating channel identities.
  2. Batch submission cleared `setSelectedVideos({})` unconditionally on HTTP response, even if backend returned individual items as `rejected` or `failed`.
  3. Network transport exceptions were treated as complete failure, losing tracking of uncertain outcomes.
- **Remediation Delivered in Phase 1.1:**
  1. Separated Behavior A (global sticky bar groups strictly by `v.channelId`, never cross-contaminates channel payloads or reassigns channel identities) and Behavior B (explicit channel-scoped batch dispatch).
  2. Implemented item-level outcome reconciliation (`reconcileBatchOutcomes`): only confirmed `queued` and `already_processing` items are removed from selection; `rejected`, `failed`, and `unresolved` items remain selected in `selectedVideos`.
  3. Network error uncertainty safely preserves selection for retry and relies on verified server duplicate detection.
- **Verification Evidence:**
  - `frontend/test/automation_batch_selection.test.mjs` (8/8 unit/integration tests passed in 897ms).
  - `backend/tests/test_automation_repairs.py` (7/7 pytest tests passed in 4.50s).
  - `npx tsc --noEmit` clean (0 errors), Next.js production build clean (11/11 prerendered).
- **Status:** `RESOLVED IN PHASE 1.1`.

---

### `CAP-001` — Multi-Language Auto-Dubbing Prototype (Deferred Capability)
- **Category:** Optional Architectural Capability (Explicitly Not a Defect)
- **Code Locations:** `backend/api/routes/dubbing.py`, `backend/tasks/dubbing_tasks.py`
- **Current State:** Backend routes `/api/dubbing/{clip_id}` exist. Zero frontend callers.
- **Project Governance Invariant:** Optional dubbing is outside implementation scope and deferred until explicitly authorized.
- **Status:** `DEFERRED CAPABILITY`.

---

### `CF-DEF-009` — Unscoped Synthetic Fixture Interception in Downloader & Transcriber
- **Category:** Functional Code Defect (Unsafe Test Fixture Interception)
- **Code Locations:**
  - `backend/services/downloader.py:30, 71`
  - `backend/services/transcriber.py:117`
- **Initial Defect Description:**
  - Synthetic fixture interception added during Phase 1.2 triggers on broad substring checks (`"synth_"`, `"mock_"`, `"test_fixture"`, `"synthetic"`).
  - The check is **not** gated to test mode (`is_test=True` on Channel/Job or `settings.PUBLISH_MODE == "test"`).
  - If a production user submits a real YouTube video with `"synthetic"` in the URL, title, or path (e.g. synthetic biology, synthetic diamonds), the system intercepts the request, copies the 20s test fixture instead of downloading the video, and returns a synthetic transcript.
- **Severity:** Medium (Potential false-positive interception of real production videos containing common keywords).
- **Remediation Delivered in Phase 1.2.1:**
  1. Updated `get_video_info` and `download_video` in `downloader.py` and `transcribe_video` in `transcriber.py` to accept backwards-compatible `is_test: bool = False`.
  2. Removed generic `"synthetic"` and `"mock_"` substring matching from URLs.
  3. Gated fixture substitution strictly behind `is_test is True` AND specific fixture target identifier (`synth_*` or `synthetic_test_fixture.mp4`).
  4. Resolved trusted test authorization in `download_task` and `transcription_task` (`video_tasks.py`) strictly from database `Job.is_test` and `Channel.is_test` records, failing closed (`is_test = False`) when absent or unverified.
  5. Kept fixture selection completely separated from `PUBLISH_MODE`.
- **Verification Evidence:**
  - `backend/tests/test_phase_1_2_1_synthetic_isolation.py` (5/5 passed: Tests A through E).
  - Existing regression suites: 33/33 passed across failure handling, automation batching, monitoring lifecycle, and queue repair.
  - Live Celery worker end-to-end orchestration verified (`test_orchestration.py`, 1/1 passed).
  - Audit Report: `docs/engineering/audits/PHASE_1_2_1_SYNTHETIC_FIXTURE_ISOLATION.md`.
- **Status:** `RESOLVED IN PHASE 1.2.1`.

---

### `CF-DEF-010` — Decision Cancellation Terminal State Guard in Celery Beat Sweep
- **Category:** Functional Code Defect (State Machine Guard Flaw in Video Decision Lifecycle)
- **Code Location:** `backend/tasks/orchestration.py:270-282`
- **Initial Defect Description:**
  - In `resolve_video_decision_sync`, terminal state protection was gated by `if decision.status in (RESOLVED_DEFAULTS, RESOLVED_CUSTOM, CANCELLED) and decision.job_id:`.
  - When a user explicitly cancelled an awaiting decision via `action="cancel"`, `decision.status` became `cancelled`, but `decision.job_id` remained `None` because cancellation occurs before a Celery job is created.
  - When a periodic Celery Beat sweep (`sweep_pending_decisions_task`) or stale countdown task ran `resolve_video_decision_sync(action="sweep")` on the cancelled decision, it bypassed the terminal guard because `decision.job_id` was `None`. It fell through to the ineligible status branch, returning `{"skipped": "ineligible_status"}` and omitting `"already_resolved": True`.
- **Reproducible Failure Evidence:**
  - Running pre-existing test `backend/tests/test_automatic_channel_monitoring_and_decision_lifecycle.py::test_user_cancellation_remains_cancelled` failed at line 461:
    `assert res_sweep["already_resolved"] is True` -> `KeyError: 'already_resolved'`.
- **Scope Distinction from CF-DEF-009:**
  - `CF-DEF-009` is strictly confined to downloader/transcriber synthetic fixture isolation (Domain L1 / L6 / L7).
  - `CF-DEF-010` is a state machine guard issue in `resolve_video_decision_sync` (Domain L2 / L5). It does NOT affect fixture selection or media downloading.
- **Remediation Delivered in Phase 1.2.1:**
  - Updated terminal state protection in `orchestration.py` lines 270-282 to recognize `CANCELLED` as a terminal state regardless of whether `job_id` exists:
    `if ((decision.status in (RESOLVED_DEFAULTS, RESOLVED_CUSTOM) and decision.job_id) or decision.status == CANCELLED): return {"already_resolved": True}`.
- **Verification Evidence:**
  - `test_automatic_channel_monitoring_and_decision_lifecycle.py` passed 15/15 tests cleanly (including `test_user_cancellation_remains_cancelled`).
- **Status:** `RESOLVED IN PHASE 1.2.1 (INCIDENTAL REGRESSION FIX)`.

---

### `CF-DEF-011` — Unscoped Synthetic SFX Fallback Generation in Production
- **Category:** Functional Code Defect (Unscoped Synthetic Fixture Generation in Production Path)
- **Status:** **RESOLVED & VERIFIED IN PHASE 2.1.1A.1**
- **Code Location:** `backend/services/sfx_planner.py`
- **Initial Defect Description:**
  - In `SFXPlanner.generate_plan()`, when no eligible SFX assets were found in the `sfx_assets` database table, fallback generation via `_mock_generate_asset()` was executed unconditionally without verifying whether the clip was an explicit test fixture or a real production video.
  - If a production environment lacked pre-seeded sound effect assets, plan requests for real user clips generated synthetic 440Hz/880Hz/220Hz sine wave audio tones via FFmpeg, registered synthetic `SFXAsset` records in production database tables, and mixed placeholder audio into real user videos.
- **Remediation Delivered in Phase 2.1.1A & Phase 2.1.1A.1:**
  1. **Strict Trusted Test-Context Authorization (Phase 2.1.1A.1):**
     - Completely removed identifier prefix matching (`test_sfx_`, `test_fixture_`, `p21_test_`, `test_p21_`, etc.) from `_is_trusted_test_clip()`. No string prefix, filename, or run-identity substring can independently authorize test fallback.
     - Resolved test context strictly through verified, authoritative database relationships: `Job.is_test` (via `clip.video_id` or `clip.run_identity`) and `Channel.is_test` (via `video.channel_id` or `job.channel_id`).
     - Conflict & Ambiguity Guard: If both `Job` and `Channel` records exist with conflicting test flags (`bool(job.is_test) != bool(channel.is_test)`), logs a warning and fails closed (`False`).
     - Missing Context Guard: If neither `Job` nor `Channel` exists, fails closed (`False`).
     - Untrusted Caller Override Guard: Caller-supplied `is_test=False` fails closed immediately (`False`). Caller-supplied `is_test=True` is verified against database context; if authoritative database state does not confirm test context, it fails closed (`False`). No untrusted API parameter can turn a production clip into a test fixture.
  2. **Synthetic Mock Filtering (Phase 2.1.1A):**
     - Implemented `_is_synthetic_mock_asset(asset)` to identify autogenerated placeholder tone assets.
     - Filtered eligible assets in `generate_plan()` so production clips strictly exclude synthetic mock assets, preventing previously synthesized test tones from being selected for real clips.
  3. **Gated Fallback Tone Synthesis (Phase 2.1.1A):**
     - Test context: generates synthetic placeholder sine wave tones via `_mock_generate_asset()` as documented.
     - Production context: logs a warning, skips synthesis/persistence, and returns a safe empty plan (`SFXPlan(clip_id=clip_id, placements=[])`).
  4. **Subprocess & Persistence Hardening (Phase 2.1.1A):**
     - Hardened `_mock_generate_asset()` to assert FFmpeg exit code and validate artifact registration before committing to the database, preventing orphaned artifact records on failure.
- **Verification Evidence (Distinguished Across Tiers):**
  - **Tier 1 (Focused Regression Tests):** `backend/tests/test_phase_2_1_1a_sfx_production_isolation.py`: 14/14 passed in 5.40s covering:
    1. Verified test job permits synthetic fallback when library is empty.
    2. Verified test channel permits fallback only where contract treats it as authoritative.
    3. Production clip with normal UUID and `Job.is_test=False` is denied fallback.
    4. Production clip with test prefixes (`test_sfx_`, `test_fixture_`, `p21_test_`, `test_p21_`) denied fallback when DB context identifies it as production.
    5. Missing clip fails closed (`False`).
    6. Missing job and channel context fails closed (`False`).
    7. Conflicting job and channel flags (`True-False` and `False-True`) fail closed (`False`).
    8. Untrusted parameter `explicit_is_test=True` cannot override production clip (`Job.is_test=False`).
    9. Explicit `is_test=False` fails closed even if DB says test.
    10. Normal planning with real assets ignores synthetic filter.
    11. Production clip filters out previously synthesized mock assets.
    12. Repeated plan requests reuse existing synthetic assets without duplicate creation.
    13. Subprocess FFmpeg failure cleanly aborts without orphaned records.
  - **Tier 2 (Combined System Regression Suite):** 73/73 passed across 7 test suites in 31.63s (`test_phase_2_1_1a_sfx_production_isolation.py` [14], `test_phase_2_1_clip_ai_enhancements.py` [15], `test_phase_1_3_storage_cleanup.py` [20], `test_phase_1_2_1_synthetic_isolation.py` [5], `test_phase_1_2_execution_and_failure_handling.py` [5], `test_automation_repairs.py` [7], `test_youtube_channels_management.py` [7]).
  - **Tier 3 (Static Code Verification):** TypeScript `npx tsc --noEmit` clean (0 errors).
  - **Tier 4 (In-Process Task / Service Execution):** Fully verified in-process via `AsyncSession` and `SFXPlanner` service invocations in pytest test harness.
  - **Tier 5 (Live Docker Celery Worker):** **UNVERIFIED.** The Docker container `clipforge_worker` was not restarted and did not execute tasks in Phase 2.1.1A.1; live worker execution remains unverified pending container restart.
- **Severity:** High (Resolved).
- **Dependencies:** L7 (Audio/SFX Services), L9 (API Routes).

---

### `CF-DEF-012` — Unsafe GET Side-Effects and Event-Loop Blocking in SFX Plan Retrieval
- **Category:** Functional Code Defect (HTTP Semantics Violation & Async Event-Loop Blocking)
- **Status:** **RESOLVED & VERIFIED IN PHASE 2.1.1B**
- **Code Locations:**
  - `backend/api/routes/clips.py:1240-1305` (`get_clip_sfx_plan`, `generate_clip_sfx_plan`)
  - `backend/services/virality_predictor.py:32-75` (`ViralityPredictor.analyze_clip`)
  - `frontend/lib/api.ts:250` (`generateSfxPlan`)
  - `frontend/components/RetentionHeatmap.tsx:100-115` (`applySfx`)
  - `frontend/app/clips/page.tsx:280-310` (`PreviewModal`, `handleLoadSfxPlan`)
- **Expected Behavior:**
  1. `GET /api/clips/{clip_id}/sfx-plan` is strictly read-only and idempotent. Returns an existing persisted `ClipSFXPlan` or HTTP 404 Not Found without creating or mutating database records, synthesizing placeholder assets, or running media analysis.
  2. `POST /api/clips/{clip_id}/sfx-plan` explicitly generates, persists, and returns the SFX plan. Validates clip existence, executes retention risk analysis if missing, synthesizes tones strictly under verified test context, commits `ClipSFXPlan`, and returns plan JSON.
  3. Heavy synchronous media analysis (`ViralityPredictor.analyze_clip`), which invokes multiple `ffprobe` subprocesses, is offloaded off FastAPI's async event loop via `asyncio.to_thread` to prevent thread starvation and event loop blocking.
- **Actual Observed Behavior Prior to Remediation:**
  1. Every `GET /api/clips/{clip_id}/sfx-plan` request for a clip without an existing plan triggered database mutations: it ran `ViralityPredictor` and committed a `ClipRetention` record, and `SFXPlanner.generate_plan` persisted a `ClipSFXPlan` record on every GET call.
  2. `ViralityPredictor.analyze_clip` ran synchronous `ffprobe` subprocesses directly on FastAPI's main async event loop, blocking all concurrent HTTP requests.
  3. Frontend lacked an explicit `generateSfxPlan` client method and used GET indiscriminately.
- **Remediation Delivered (Phase 2.1.1B):**
  1. **Strictly Read-Only GET Endpoint:** Refactored `GET /api/clips/{clip_id}/sfx-plan` in `backend/api/routes/clips.py` to query only `select(ClipSFXPlan).where(ClipSFXPlan.clip_id == clip_id)`. Returns 404 (`{"detail": "SFX plan not found. Explicitly generate plan first."}`) if no plan exists or if clip does not exist. Performs zero DB writes, zero task dispatches, and zero media analysis.
  2. **Explicit POST Generation Endpoint:** Added `POST /api/clips/{clip_id}/sfx-plan` in `backend/api/routes/clips.py`. Verifies clip existence, reuses existing `ClipRetention` or requires rendered video file on disk, executes `ViralityPredictor.analyze_clip` via `await asyncio.to_thread(...)`, runs `SFXPlanner.generate_plan()` under Phase 2.1.1A.1 test context authorization, persists `ClipSFXPlan`, and returns plan JSON.
  3. **Event-Loop Offloading:** Updated both `POST /{clip_id}/sfx-plan` and `GET /{clip_id}/retention` to run `ViralityPredictor.analyze_clip` inside `await asyncio.to_thread(...)`. Database operations (`db.commit()`, `db.refresh()`) remain strictly on the async event loop without passing `AsyncSession` across threads.
  4. **Pydantic V2 Serialization & Helper Methods:** Added `@property def overall_score(self) -> float:` to `RetentionAnalysis` and `analyze_clip()` method to `ViralityPredictor`. Updated deprecated `.dict()` calls to `.model_dump()`.
  5. **Frontend API & Component Integration:** Exported `generateSfxPlan` in `frontend/lib/api.ts`. In `PreviewModal` (`frontend/app/clips/page.tsx`), prefetch existing plan on mount via read-only GET; trigger explicit POST generation on clicking "Load / Re-generate Plan" (`data-testid="btn-load-sfx"`). Updated `RetentionHeatmap.tsx` to retrieve existing plan or generate if missing before applying.
- **Verification Evidence (Distinguished Across Tiers):**
  - **Tier 1 (Focused Regression Tests):** `backend/tests/test_phase_2_1_1b_sfx_get_cleanup.py`: 9/9 passed in 5.84s:
    1. Repeated GET returns existing plan without DB mutations.
    2. GET with no existing plan does not mutate DB or create records (returns 404).
    3. GET does not invoke `ViralityPredictor` or `ffprobe`.
    4. Explicit POST generates and persists expected plan.
    5. Repeated and concurrent POST generations are consistent and idempotent.
    6. Missing clip and missing media files handled gracefully with 404 / 400.
    7. Test context isolation preserved on generation (production context returns empty placements without mock tones).
    8. Event-loop offloading executes `ViralityPredictor` on worker thread.
    9. Media analysis failure propagates cleanly without orphaned state.
  - **Tier 2 (Combined System Regression Suite):** 63/63 passed across 5 test suites in 20.56s (`test_phase_2_1_clip_ai_enhancements.py` [15], `test_phase_2_1_1a_sfx_production_isolation.py` [14], `test_phase_2_1_1b_sfx_get_cleanup.py` [9], `test_phase_1_2_1_synthetic_isolation.py` [5], `test_phase_1_3_storage_cleanup.py` [20]).
  - **Tier 3 (Static Code Verification & Build):**
    * TypeScript `npx tsc --noEmit` clean (0 errors).
    * Next.js production build (`npm run build`) clean (11/11 static pages generated).
    * Node test runner unit tests (`npm test`): 18/18 passed in 94ms.
  - **Tier 4 (In-Process Task / Service Execution):** Fully verified in-process via `AsyncSession` and `SFXPlanner` service invocations in pytest test harness.
  - **Tier 5 (Live Docker Celery Worker):** **UNVERIFIED.** Live worker container restart deferred; live worker execution remains unverified pending container reload.
- **Severity:** Medium (Resolved).
- **Dependencies:** L7 (Audio/SFX Services, Retention Prediction), L9 (API Routes), L10 (Clips UI & Retention Heatmap).

---

### `CF-DEF-013` — Remote YouTube Privacy Desynchronization Following Intentional External Visibility Changes & Publishing Privacy Acceptance Audit
- **Category:** Discrepancy / State Desynchronization & Defensive Publishing Hardening
- **Status:** **WRITABLE STATUS FIELD PRESERVATION AUDITED & VERIFIED (EXEMPTION VS OMISSION-DELETION CONTRACT HONORED; 48/48 PRIVACY TESTS PASSING; 107/107 COMBINED REGRESSION; 4 HISTORICAL REMOTE PUBLIC SHORTS PRESERVED WITHOUT MUTATION)**
- **Code Locations:** `backend/services/publisher.py`, `backend/tasks/clip_tasks.py`, `backend/api/routes/publish.py`, `backend/api/routes/clips.py`, `backend/tasks/scheduler.py`, `backend/models/models.py`, `backend/alembic/versions/e6f7a8b9c0d1_update_clip_privacy_server_default.py`, `backend/tests/test_publishing_privacy_hardening.py`
- **Incident Re-Classification & Confirmed User Intent (Dated Correction 2026-10-27):**
  - **Confirmed User Clarification (Source of Truth):** The backend successfully uploaded all 6 YouTube Shorts with `private` visibility. Following successful upload, the user intentionally changed four videos (`0OfOivc-tpU`, `39w4TLjreFU`, `L3ihlJVo_3A`, and `FoNMm4F9qIM`) to `public` directly in YouTube Studio.
  - **Intentional User Changes vs. Upload Defects:** The four public videos were **intentional user changes**, NOT evidence that the original backend uploads failed to use private privacy settings.
  - **Local Database State:** PostgreSQL records remained `Clip.privacy = "private"` because ClipForge lacked an automated mechanism to synchronize downstream remote changes back into local clip records.
  - **Actual Software Issue:** A one-way privacy synchronization gap: ClipForge did not keep its local privacy state synchronized with the user's later changes on YouTube.
  - **Superseded Historical Assumption:** The previous forensic hypothesis (that legacy pre-`af5eed9` code uploaded these 4 Shorts with public defaults) is explicitly **SUPERSEDED** by the confirmed user clarification. The earlier hypothesis is preserved in historical notes below solely for audit provenance.
  - **Future Publishing Hardening Justification:** Private-by-default request enforcement, payload clamping, and read-back verification remain critical architectural safeguards for automated pipelines, but they are justified on defensive engineering grounds, not by misattributing user-intended public settings as upload failures.
  - **Data Model Limitation & Proposed Separation:** The current `Clip` model (`backend/models/models.py`) contains a single `privacy` column that conflates desired local upload policy with remotely observed visibility. In Phase 2, reconciliation updates `Clip.privacy = remote_privacy` and flags `manual_review` for operator awareness without altering remote YouTube state. The recommended backward-compatible schema enhancement for future milestones is to separate `remote_privacy: Mapped[str | None]` and `remote_privacy_synced_at: Mapped[datetime | None]` so intentional external visibility changes can be recognized without triggering discrepancy alerts.
- **Expected Behavior:**
  1. Video visibility submitted in the YouTube upload request (`status.privacyStatus`) strictly equals `"private"` for every automated upload.
  2. Remote responses returned by YouTube Data API v3 are inspected:
     - Remote `status.privacyStatus == "private"`: recorded as published and confirmed private.
     - Remote `status.privacyStatus == "public"`: system must NOT report confirmed private or record `published`; transitions to `manual_review` with error message.
     - Remote returns missing/incomplete status: flagged as `"unconfirmed"` and transitions to `manual_review`.
     - Remote returns video ID before unexpected/incomplete response: video ID is preserved (never lost!).
     - An upload raises an exception: task must not falsely record a confirmed successful private upload.
  3. Database model column defaults and PostgreSQL schema `server_default` are synchronized to `'private'`.
  4. Local database records are never treated as proof of remote state; reconciliation queries remote `status.privacyStatus`.
  5. Emergency remediation payload semantics:
     - Never copy read-only server-determined `status.madeForKids` into uploader-declared `status.selfDeclaredMadeForKids`.
     - Omit `selfDeclaredMadeForKids` and `containsSyntheticMedia` when unknown; per official YouTube Data API v3 documentation, these fields are explicitly exempt from deletion upon omission. Never default to `False`.
     - Preserves `license`, `embeddable`, and `publicStatsViewable` (including explicit `False` values). Under standard PUT full replacement semantics, omission deletes/resets existing properties to defaults, destroying creator intent. If unknown, fail safe into `manual_review` via `UnsafeStatusRemediationError`.
     - Never carry forward a future `status.publishAt` into a private remediation without explicit authorization, and never silently strip it. If present, halt automated remediation into `manual_review`.
     - Re-read remote status after any corrective update; only confirm private if read-back reports `privacyStatus == "private"`.
- **Actual Observed Behavior Prior to Hardening:**
  A live read-only query to the YouTube Data API v3 on channel `ClipSee` (`UCH90024qrJHA4amGRxnTldw`) confirms:
  * `YpHobheDpk8`: `privacyStatus: "private"` (Matches DB)
  * `kkXWbXZI_iM`: `privacyStatus: "private"` (Matches DB)
  * `0OfOivc-tpU`: `privacyStatus: "public"` (Desynced from DB `private` — user intentionally set public on YouTube)
  * `39w4TLjreFU`: `privacyStatus: "public"` (Desynced from DB `private` — user intentionally set public on YouTube)
  * `L3ihlJVo_3A`: `privacyStatus: "public"` (Desynced from DB `private` — user intentionally set public on YouTube)
  * `FoNMm4F9qIM`: `privacyStatus: "public"` (Desynced from DB `private` — user intentionally set public on YouTube)
  Although local PostgreSQL records reflect `Clip.privacy = "private"`, 4 of the 6 YouTube Shorts are currently `public` on YouTube due to confirmed subsequent user changes. Under explicit audit safety constraints ("Do not change privacy on existing publications during this audit; do not modify publications without explicit separate authorization"), these remote publications remain untouched.

- **Root Cause & Historical Classification:**
  1. **Primary Operational Cause (Confirmed User Intent):** The 4 videos were intentionally transitioned to `public` directly on YouTube by the user after successful private uploads by the backend.
  2. **Technical Software Defect:** ClipForge's local records (`Clip.privacy`) remained set to `"private"` because the platform did not synchronize external YouTube visibility modifications back to PostgreSQL.
  3. **Superseded Forensic Theory (Pre-`af5eed9` Defaults):** *(SUPERSEDED HISTORICAL ASSUMPTION)* Early audit findings hypothesized that pre-`af5eed9` code defaults (`privacy="public"`) caused the public state. While code defaults did historically default to public prior to commit `af5eed9`, the user confirmed that the actual uploads for these 6 videos were submitted as private, and the public visibility was manually set thereafter.
  4. **Tag Reconciliation Gap:** In earlier passes, tag reconciliation (`check_external_youtube_state`) matched videos by tag but only inspected ID and snippet, without querying or synchronizing remote `status.privacyStatus`.
  5. **Preservation of User Intent:** Tag reconciliation now queries remote privacy and updates local records to match (`c.privacy = remote_privacy`), never mutates remote YouTube state, and flags discrepancies for operator review.

- **Remediation & Hardening Delivered:**
  1. **Publisher Enforcement & Payload Hardening (`backend/services/publisher.py`):**
     - Updated `upload_short` signature default to `privacy: str = "private"`.
     - Strict safety clamp: Any non-private privacy value passed to an automated upload path is clamped to `"private"` with a logged warning.
     - YouTube Data API response inspection: Extracts `confirmed_privacy = response.get("status", {}).get("privacyStatus")`. If missing, sets `"privacy": "unconfirmed"` and `"privacy_confirmed": False` (never falls back to requested privacy). Returns `{"id": video_id, "url": ..., "privacy": confirmed_privacy, "privacy_confirmed": is_confirmed}`.
     - Preserves created video ID even if status block is missing.
  2. **Celery Pipeline Tasks (`backend/tasks/clip_tasks.py`):**
     - Updated `publish_clip_task` default signature to `privacy: str = "private"`.
     - In `publish_clip_task`, Step 2 reconciliation queries YouTube Data API `videos().list(part="status")` so local DB is never treated as proof of remote state; sets `c.privacy = remote_privacy`. If remote is not private or lookup fails, transitions to `manual_review`, preserving video ID and diagnostic error.
     - In `publish_task` and `publish_clip_task` Step 5 finalization, checks `is_confirmed_private`. If private, marks `published`. If `"public"`, `"unconfirmed"`, or remediation was withheld, transitions to `manual_review` with error message, preserving `c.youtube_short_id`.
     - In `recover_stranded_publish_jobs_task`, explicitly dispatches retry with `kwargs={"channel_id": ..., "privacy": "private"}`.
  3. **API Routes (`backend/api/routes/publish.py` & `backend/api/routes/clips.py`):**
     - Updated `PublishRequest.privacy` schema default to `"private"`.
     - Updated `retry_publish_clip` in `publish.py` to explicitly pass `"privacy": "private"`.
     - Updated `publish_clip` endpoint in `clips.py` to pass `privacy="private"`. Sets `clip.publish_status = "published"` only if `confirmed_privacy == "private"`; otherwise transitions to `manual_review`.
  4. **Scheduler Loop (`backend/tasks/scheduler.py`):**
     - Updated `run_auto_publisher` to explicitly set `clip_privacy = "private"`. Sets `c.publish_status = "published"` only if `confirmed_privacy == "private"`; otherwise transitions to `manual_review` with error logged.
  5. **Data Model & Schema Consistency (`backend/models/models.py` & Alembic):**
     - Updated `Clip.privacy` column default and `server_default` to `"private"`.
     - Discovered PostgreSQL operational database column default was `'public'::character varying`.
     - Created Alembic migration [`backend/alembic/versions/e6f7a8b9c0d1_update_clip_privacy_server_default.py`](file:///d:/automation%20video%20clips/clipforge/backend/alembic/versions/e6f7a8b9c0d1_update_clip_privacy_server_default.py) to set `server_default='private'` (downgrade to `'public'`).
     - Verified migration upgrade and downgrade parity on an isolated disposable PostgreSQL schema (`temp_privacy_audit_schema`), without mutating operational production data.
  6. **Final Privacy Remediation Semantics & Writable Status Field Preservation Audit:**
     - Introduced `UnsafeStatusRemediationError(ValueError)` in `publisher.py`.
     - Re-implemented `_build_safe_status_update_body` and proactive querying in `upload_short`:
       * **License (`license`):** Preserves existing license (`"youtube"` or `"creativeCommon"`). If missing from remote status, checks explicit caller fallback. If unknown, never defaults to `"youtube"` (which would silently replace Creative Commons licenses) and never omits it (which resets to YouTube standard on YouTube); raises `UnsafeStatusRemediationError` and halts automated remediation into `manual_review`.
       * **Embedding & Public Statistics (`embeddable`, `publicStatsViewable`):** Preserves existing boolean values (including explicit `False`). Under YouTube Data API full replacement semantics, omitting existing properties deletes or resets them to defaults (`True`), which destroys creator privacy intent. If either value is unknown, never omits or guesses defaults; raises `UnsafeStatusRemediationError` and halts automated remediation into `manual_review`.
       * **Made for Kids (`selfDeclaredMadeForKids`) & Synthetic Media (`containsSyntheticMedia`):** Official YouTube Data API v3 `videos.update` documentation explicitly exempts `status.selfDeclaredMadeForKids` and `status.containsSyntheticMedia` from the standard omitted-property deletion rule. When unknown, safely omitting them preserves existing remote declarations without fabricating legal claims or blocking remediation. Server-determined `status.madeForKids` is NEVER copied to `selfDeclaredMadeForKids`.
       * **Scheduled Publication (`publishAt`):** Never carried forward into private remediation (which schedules future public release). If `publishAt` is present in remote status, raises `UnsafeStatusRemediationError` unless `allow_cancel_scheduled_publish=True` is explicitly passed. Never silently dropped without policy authorization.
       * **Read-Only vs Mutable Fields:** Strips read-only properties (`uploadStatus`, `failureReason`, `rejectionReason`, `madeForKids`). Preserves mutable properties (`license`, `embeddable`, `publicStatsViewable`, `containsSyntheticMedia`).
       * **Proactive Status Fetching:** In `upload_short`, if insert response status block lacks `license`, `embeddable`, or `publicStatsViewable`, proactively queries `videos().list(part="status")` before attempting remediation.
     - In `upload_short`, caught `UnsafeStatusRemediationError`, set `remediation_status = f"remediation_withheld: {unsafe_err}"`, logged critical warning, preserved video ID, and withheld automated `videos().update`.
     - In `clip_tasks.py` and `scheduler.py`, added `"withheld"` to critical remediation alerts.

- **Status Payload Contract Specification (YouTube Data API v3 `videos.update(part="status")`):**

| Status Property | Writable? | Reliably Obtained? | Semantically Correct to Preserve? | What Happens if Missing? | Safe Automated Update Possible? |
|---|---|---|---|---|---|
| `privacyStatus` | Yes | Yes (target is forced to `'private'`) | Yes (enforces ClipForge private-only invariant) | Set to `'private'` | **Yes** |
| `license` | Yes | Yes (from `existing.get("license")` or fallback) | Yes (preserves YouTube Standard vs Creative Commons) | **FAIL SAFE:** If unknown, raise `UnsafeStatusRemediationError` -> `manual_review` (never silently assume `"youtube"` or omit) | **Gated** (Only if known license exists) |
| `embeddable` | Yes | Yes (from `existing.get("embeddable")` or fallback) | Yes (preserves embedding permission, including `False`) | **FAIL SAFE:** If unknown, raise `UnsafeStatusRemediationError` -> `manual_review` (omission deletes existing `False`, resetting to default `True`) | **Gated** (Only if known boolean exists) |
| `publicStatsViewable` | Yes | Yes (from `existing.get("publicStatsViewable")` or fallback) | Yes (preserves public metrics visibility, including `False`) | **FAIL SAFE:** If unknown, raise `UnsafeStatusRemediationError` -> `manual_review` (omission deletes existing `False`, resetting to default `True`) | **Gated** (Only if known boolean exists) |
| `selfDeclaredMadeForKids` | Yes | Yes (from `existing` or `fallback_made_for_kids`) | **Only if creator declaration is known**; copying `madeForKids` violates COPPA | **EXEMPT FROM DELETION:** Safely omitted if unknown per official YouTube docs; preserves remote declaration | **Yes** (Omitted if unknown; never copy `madeForKids`) |
| `containsSyntheticMedia` | Yes | Yes (from `existing` or `fallback_contains_synthetic_media`) | Yes (preserves AI/synthetic disclosure) | **EXEMPT FROM DELETION:** Safely omitted if unknown per official YouTube docs; preserves remote declaration | **Yes** (Omitted if unknown) |
| `publishAt` | Yes | Yes (from `existing.get("publishAt")`) | **NO** for private remediation (schedules future public release); dropping silently violates schedule | **FAIL SAFE:** If present and not explicitly cancelled, raise `UnsafeStatusRemediationError` -> `manual_review` | **Gated** (Only when absent or explicitly cancelled) |
| `madeForKids` | **NO (Read-only)** | Yes (returned by API) | **NO** (Submitting causes HTTP 400 Bad Request; copying to `selfDeclaredMadeForKids` falsifies legal certification) | Strictly excluded from update payload | **Yes (Stripped)** |
| `uploadStatus` | **NO (Read-only)** | Yes (returned by API) | **NO** (Submitting causes HTTP 400 Bad Request) | Strictly excluded from update payload | **Yes (Stripped)** |
| `failureReason` | **NO (Read-only)** | Yes (returned by API) | **NO** (Submitting causes HTTP 400 Bad Request) | Strictly excluded from update payload | **Yes (Stripped)** |
| `rejectionReason` | **NO (Read-only)** | Yes (returned by API) | **NO** (Submitting causes HTTP 400 Bad Request) | Strictly excluded from update payload | **Yes (Stripped)** |

- **Separate Statuses by Domain (Emergency Remediation & Deployment Gate):**
  1. **Private-by-default request construction:** **VERIFIED & ENFORCED IN CODE.** All active upload paths (`upload_short`, `publish_task`, `publish_clip_task`, `run_auto_publisher`, `publish_clip` route) enforce `privacyStatus="private"`. Non-private overrides are clamped to `"private"`.
  2. **Safe status-payload construction:** **VERIFIED & AUDITED IN CODE & MOCKS.** Evaluated against the official YouTube Data API v3 contract. All read-only fields (`madeForKids`, `uploadStatus`, `failureReason`, `rejectionReason`) are stripped. All non-exempt mutable fields (`license`, `embeddable`, `publicStatsViewable`) are verified present or fail safe into `manual_review`. Exemption fields (`selfDeclaredMadeForKids`, `containsSyntheticMedia`) safely omitted when unknown.
  3. **Made for Kids declaration preservation:** **VERIFIED & ENFORCED IN CODE.** Server-determined `madeForKids` is NEVER copied to `selfDeclaredMadeForKids`. Unknown declarations are omitted per API deletion exemption without fabricating declarations.
  4. **Scheduled-publication handling:** **VERIFIED & ENFORCED IN CODE.** Future `publishAt` is NEVER carried forward into private remediation, and existing schedules are NEVER silently removed. If `publishAt` is detected, automated remediation is withheld and flagged `manual_review` unless `allow_cancel_scheduled_publish=True` is explicitly passed.
  5. **Remote read-back verification:** **VERIFIED & AUDITED IN CODE & MOCKS.** A mandatory read-only `videos().list(part="status", id=video_id)` is executed following `videos().update`. Remote state is declared confirmed private ONLY when read-back confirms `privacyStatus == "private"`. If read-back fails or reports public, flags `remediation_readback_still_public` / `remediation_readback_exception`, transitions clip to `manual_review`, and preserves video ID.
  6. **Runtime worker deployment:** **PENDING CELERY WORKER RESTART.** `clipforge_backend` runs with `--reload` and is up to date. Background workers `clipforge_worker` and `clipforge_beat` do NOT auto-reload and hold pre-hardening bytecode. `docker compose restart worker beat` remains pending and is required prior to live publishing.
  7. **Operational database migration:** **PENDING OPERATIONAL UPGRADE.** Migration `e6f7a8b9c0d1_update_clip_privacy_server_default.py` was verified for upgrade and safe downgrade (`server_default=None`, fail-safe NOT NULL) on an isolated schema. Operational PostgreSQL database remains at `d4e5f6a7b8c9` pending scheduled deployment (`alembic upgrade head`).
  8. **Four legacy Shorts that remain public:** **PRESERVED INTACT WITHOUT MUTATION (USER-INTENDED PUBLIC STATE).** YouTube Shorts `0OfOivc-tpU`, `39w4TLjreFU`, `L3ihlJVo_3A`, and `FoNMm4F9qIM` remain remotely public on channel `ClipSee`. Confirmed as intentional user visibility modifications. Non-destructive safety boundaries strictly respected: zero live `videos().update` calls executed against them.

- **Verification Evidence (Distinguished Across Tiers):**
  - **Tier 1 (Targeted Hardening & Emergency Remediation Unit Tests):** `backend/tests/test_publishing_privacy_hardening.py`: **48/48 passed (100%) in 5.21s**:
    1. `test_upload_short_payload_forces_private_even_when_public_passed`: Verifies payload clamp forces `"private"`.
    2. `test_upload_short_payload_defaults_to_private_when_omitted`: Verifies default payload is `"private"`.
    3. `test_youtube_returns_private_records_published_and_confirmed_private`: Case 1: remote private -> published & confirmed private.
    4. `test_youtube_returns_public_records_manual_review_not_confirmed_private`: Case 2: remote public -> manual_review, not confirmed private.
    5. `test_youtube_returns_missing_status_records_unconfirmed_and_manual_review`: Case 3: missing status -> unconfirmed & manual_review.
    6. `test_safe_status_update_body_preserves_writable_fields_and_omits_readonly`: Validates mutable fields preserved and read-only stripped.
    7. `test_safe_status_update_body_rejects_made_for_kids_copy_and_safely_omits_unknown_coppa`: Proves `madeForKids=True` does NOT become `selfDeclaredMadeForKids=True`, and unknown declaration is safely omitted per exemption.
    8. `test_safe_status_update_body_preserves_explicit_self_declaration`: Proves explicitly known `selfDeclaredMadeForKids` is preserved.
    9. `test_safe_status_update_body_preserves_known_license`: Proves existing license ("creativeCommon") is preserved.
    10. `test_safe_status_update_body_uses_fallback_license_when_existing_missing`: Proves explicit fallback license is used when existing is missing.
    11. `test_safe_status_update_body_rejects_unknown_license`: Proves missing license without fallback raises `UnsafeStatusRemediationError`.
    12. `test_upload_short_withholds_remediation_when_license_unknown`: Proves `upload_short` withholds update and preserves video ID when license is unknown.
    13. `test_safe_status_update_body_preserves_existing_embeddable_values`: Proves explicit `False` and `True` values of `embeddable` are preserved.
    14. `test_safe_status_update_body_rejects_missing_embeddable`: Proves missing `embeddable` without fallback raises `UnsafeStatusRemediationError`.
    15. `test_upload_short_withholds_remediation_when_embeddable_unknown`: Proves `upload_short` withholds update and preserves video ID when embeddable is unknown.
    16. `test_safe_status_update_body_preserves_existing_public_stats_values`: Proves explicit `False` and `True` values of `publicStatsViewable` are preserved.
    17. `test_safe_status_update_body_rejects_missing_public_stats`: Proves missing `publicStatsViewable` without fallback raises `UnsafeStatusRemediationError`.
    18. `test_upload_short_withholds_remediation_when_public_stats_unknown`: Proves `upload_short` withholds update and preserves video ID when publicStatsViewable is unknown.
    19. `test_safe_status_update_body_preserves_synthetic_media_when_known`: Proves explicit `containsSyntheticMedia` is preserved.
    20. `test_safe_status_update_body_omits_synthetic_media_when_unknown`: Proves unknown `containsSyntheticMedia` is safely omitted per API deletion exemption.
    21. `test_upload_short_emergency_remediates_when_coppa_unknown_by_safely_omitting`: Proves emergency remediation proceeds cleanly when COPPA is unknown by safely omitting it.
    22. `test_safe_status_update_body_rejects_scheduled_publish_at`: Proves scheduled `publishAt` halts automated remediation into `manual_review`.
    23. `test_safe_status_update_body_explicit_cancellation_of_scheduled_publish_at`: Proves `publishAt` can be explicitly cleared when `allow_cancel_scheduled_publish=True`.
    24. `test_upload_short_withholds_remediation_when_scheduled_publish_at_present`: Proves `upload_short` withholds update when `publishAt` is present without cancellation authorization.
    25. `test_safe_status_update_body_normal_private_upload_without_schedule`: Proves normal private-only upload without schedule produces safe update body.
    26. `test_upload_short_preserves_video_id_on_missing_privacy_status`: Preserves video ID on unexpected response.
    27. `test_upload_short_missing_privacy_status_read_only_inspection_confirms_private`: Insert omits privacy, read-only inspection discovers private.
    28. `test_upload_short_missing_privacy_status_read_only_inspection_discovers_public_and_remediates`: Insert omits privacy, inspection discovers public, remediates and confirms private.
    29. `test_upload_short_emergency_remediates_public_insert_to_private`: Emergency remediation: insert returns public -> safe update and read-back confirms private.
    30. `test_upload_short_emergency_remediation_failure_flags_critical`: Emergency update fails -> returns public with critical diagnostic.
    31. `test_upload_short_correction_succeeds_but_subsequent_readback_reports_public`: Update succeeds but read-back reports public -> flags still public.
    32. `test_upload_short_correction_succeeds_but_subsequent_readback_fails`: Update succeeds but read-back fails -> flags readback exception and unconfirmed.
    33. `test_publish_clip_task_handles_remediated_public_insert`: Remediated video placed in manual_review with operational alert.
    34. `test_publish_clip_task_handles_failed_remediation_critical_alert`: Failed remediation placed in manual_review with critical public alert.
    35. `test_publish_clip_task_handles_readback_still_public_critical_alert`: Read-back still public placed in manual_review with critical alert.
    36. `test_publish_clip_task_handles_withheld_remediation_critical_alert`: Withheld remediation placed in manual_review with critical alert.
    37. `test_upload_raises_exception_marks_failed_honestly`: Upload exception marks failed honestly, never records success.
    38. `test_upload_raises_transient_exception_retries_without_recording_success`: Transient error triggers retry without recording success.
    39. `test_recovery_task_preserves_private_policy`: Verifies stranded job recovery dispatches with `privacy="private"`.
    40. `test_models_clip_privacy_default_is_private`: Verifies `Clip` model column default and server_default are `"private"`.
    41. `test_publish_request_default_privacy_is_private`: Verifies `PublishRequest` Pydantic schema default is `"private"`.
    42. `test_scheduler_auto_publisher_enforces_private_privacy`: Verifies scheduler auto-publisher loop enforces `"private"`.
    43. `test_clips_route_publish_clip_preserves_private_policy`: Verifies POST /api/clips/{id}/publish passes `"private"` and sets confirmed status.
    44. `test_reconciliation_detects_remote_public_and_flags_manual_review`: Verifies tag reconciliation queries remote status, detects public, and flags manual_review.
    45. `test_reconciliation_api_lookup_failure_flags_manual_review_and_preserves_id`: Verifies API lookup failure flags manual_review and preserves ID.
    46. `test_reconciliation_never_calls_videos_update_for_existing_videos`: Verifies reconciliation never invokes videos.update for pre-existing videos.
    47. `test_alembic_migration_e6f7a8b9c0d1_upgrade_and_downgrade_parity_in_isolated_schema`: Verifies migration upgrade to 'private', safe downgrade to None (drop default), and NOT NULL constraint enforcement.
    48. `test_no_real_youtube_mutation_endpoints_called_in_suite`: Verifies zero live YouTube mutation calls.
  - **Tier 2 (Combined Publisher Regression Suite):** **107/107 passed (100%) across 5 test suites in 16.51s**:
    - `test_publishing_privacy_hardening.py`: 48/48 passed.
    - `test_pipeline_config_fixes.py`: 18/18 passed.
    - `test_c06_metadata_editor.py`: 17/17 passed.
    - `test_publishing_destination_repair.py`: 6/6 passed.
    - `test_c05_publish_queue_actions.py`: 18/18 passed.
  - **Tier 3 (Static Code Verification & Build):**
    - TypeScript `npx tsc --noEmit` clean (0 errors).
    - Next.js production build (`npm run build`) clean (11/11 static pages generated).
  - **Tier 4 (Live Read-Only YouTube Ground Truth):** Confirmed via read-only `inspect_six_shorts_live.py` (2 private, 4 public). Zero mutations executed against live YouTube videos.

- **Severity:** Medium (Resolved in code for payload enforcement, safe remediation request construction, mandatory read-back verification, and schema parity; historical remote publications preserved intact).
- **Dependencies:** L8 (Publishing Service), L9 (API Routes), L10 (Publish UI).

---

### `CF-DEF-014` — Conflicting Test Suite Totals Across Historical Reports
- **Category:** Documentation Discrepancy / Incomplete Aggregation
- **Status:** **RECONCILED (AUDIT)**
- **Code Locations:** Historical audit reports (`ClipForge_Full_Stack_Forensic_Audit_Master_Report.md`, etc.)
- **Expected Behavior:** Consistent, accurate, and reproducible test counts across all documentation.
- **Actual Observed Behavior:** Historical reports reported 324 vs 311 vs 229 tests due to counting partial test passes during intermediate implementation phases.
- **Verification Evidence:** Full collection `py -3.12 -m pytest backend/tests --collect-only -q` identified exactly **395 pytest test cases across 40 test files**. In `frontend/test/`, exactly **65 unit/contract tests across 10 modules** exist.
- **Severity:** Low.
- **Action Taken:** Reconciled authoritative counts across all canonical project documents.

---

### `CF-DEF-015` — Missing Preamble Fixture in `studio_backend_e2e.test.mjs`
- **Category:** Test Fixture Precondition Dependency
- **Status:** **DOCUMENTED (AUDIT)**
- **Code Locations:** `frontend/test/studio_backend_e2e.test.mjs`
- **Expected Behavior:** Automated test scripts generate their own isolated synthetic media fixtures.
- **Actual Observed Behavior:** `studio_backend_e2e.test.mjs` hardcodes an assertion checking for an existing temporary video file at `C:\Users\Chinmaygouda\AppData\Local\Temp\test_clip_alpha.mp4`. If this local file is absent, the script throws `AssertionError: Missing test_clip_alpha.mp4`.
- **Severity:** Low. Does not affect application runtime.
- **Action Taken:** Documented as a test fixture precondition.

---

### `CF-DEF-016` — Channel Video Discovery Ceiling Bounded by 100-Video Scan Cap
- **Category:** Architecture Limitation / Rate Limit Protection
- **Status:** **BOUNDED HISTORICAL SCANNING IMPLEMENTED (CEILING RAISED TO 250)**
- **Code Locations:** `backend/services/downloader.py`, `backend/api/routes/channels.py`, `frontend/app/automation/page.tsx`
- **Expected Behavior:** Discovery extracts recent uploads safely with pagination beyond 100, while explicitly communicating candidate scope to avoid misleading claims of complete channel history.
- **Actual Observed Behavior Prior to Fix:** `downloader.py` clamped single-page extraction to 50 items and `preview_historical_videos` did not paginate beyond page 1.
- **Remediation Delivered:**
  1. Implemented `start_index` in `downloader.py` and offset-based pagination in `preview_historical_videos` in `backend/api/routes/channels.py` up to `max_search_depth` (up to 250 videos in 100-item chunks) with deduplication and seamless chunk boundaries.
  2. Added `candidate_scope` metadata (`scanned_count`, `search_depth_limit`, `scope_type`, `description`) to API responses.
  3. Added Historical Scan Depth dropdown (30, 50, 100, 200 videos) and candidate scope banner in `frontend/app/automation/page.tsx`.
  4. Relabeled Option B to "Most-viewed (in Scan Scope)" to prevent misleading channel-wide claims.
- **Verification Evidence:**
  `backend/tests/test_historical_pagination_multi_chunk.py` passed 6/6; `backend/tests/test_historical_video_selection.py` passed 9/9. TypeScript type check clean (0 errors), Next.js production build clean (11/11 static pages generated).
- **Severity:** Low (Bounded Scanning Operational).

---

### `CF-DEF-017` — Unisolated Frontend Test Runner Execution Against Live Backend
- **Category:** Test Runner Safety / Environment Isolation
- **Status:** **RESOLVED IN TEST RUNNER REPAIR**
- **Code Locations:**
  - `frontend/package.json`
  - `frontend/test/phase_1_2_browser_verification.test.mjs`
  - `frontend/test/phase_2_1_browser_verification.test.mjs`
  - `frontend/test/studio_backend_e2e.test.mjs`
  - `frontend/test/studio_real_browser_e2e.test.mjs`
- **Expected Behavior:** Standard `npm test` executes strictly isolated unit and contract tests in-memory with zero network requests or background task queuing. Live end-to-end tests require an explicit operator environment flag (`RUN_LIVE_E2E=true`) before contacting host backends or operational databases, and skip safely when the flag is absent.
- **Actual Observed Behavior Prior to Fix:** `frontend/package.json` defined `"test": "node --test test/**/*.test.mjs"`. Running `npm test` invoked all 16 test files indiscriminately, causing `phase_1_2_browser_verification.test.mjs` to issue raw HTTP POST requests to `http://localhost:8000/api/channels/ch_phase12_e2e/process-video`. While the requests failed with 404 (channel non-existent), running unisolated tests risked operational queue pollution.
- **Remediation Delivered:**
  1. Updated `frontend/package.json`: default `"test"` executes strictly the 10 isolated unit test modules (`api_contract`, `automation_batch_selection`, `discovered_video_thumbnails`, `layout_modal_optimization`, `layout_preview_selector`, `layout_selector_standardization`, `process_video_modal`, `publish_visual_previews`, `routes`, `validation`).
  2. Added separated npm scripts: `"test:unit"`, `"test:browser:mocked"`, and `"test:e2e:live"`.
  3. Added explicit `RUN_LIVE_E2E=true` environment guards across all 4 live E2E test files (`phase_1_2_browser_verification.test.mjs`, `phase_2_1_browser_verification.test.mjs`, `studio_backend_e2e.test.mjs`, `studio_real_browser_e2e.test.mjs`). If `process.env.RUN_LIVE_E2E !== 'true'`, tests call `t.skip()` and exit within 1ms before executing network calls or launching browsers.
  4. Parameterized backend URLs across all test files with `process.env.API_BASE || 'http://localhost:8000'`, eliminating hardcoded URL bypasses.
- **Verification Evidence:**
  1. `npm test`: Exactly **60/60 PASSED (100%) in 407ms**, 0 failing, 0 skipped, 0 network requests.
  2. `npm run test:e2e:live`: Exactly **4/4 SKIPPED safely in 756ms** when run without `RUN_LIVE_E2E=true`.
  3. Zero Celery tasks, zero Redis queue messages, zero database records, and zero YouTube API mutations verified.
- **Severity:** Medium (Resolved in test runner configuration & test guards).

---

### `CF-DEF-018` — Monitored Channel Videos Missing View Count Sorting (SORT)
- **Category:** Sorting / Ordering Defect
- **Status:** **RESOLVED IN MONITORING AUDIT REPAIRS**
- **Code Locations:** `backend/api/routes/channels.py`, `frontend/lib/api.ts`, `frontend/app/automation/page.tsx`
- **Expected Behavior:** When the user selects "Most Viewed", videos must be ordered descending by verified YouTube `view_count` with deterministic tie-breakers `(-view_count, -sort_ts, id)` and nulls sorted last.
- **Actual Observed Behavior Prior to Fix:** Discovered videos endpoint had no `sort` query parameter and returned items strictly in raw flat-playlist fetch order. UI lacked sort controls on discovered videos.
- **Remediation Delivered:**
  1. Backend `get_channel_recent_videos` (`GET /api/channels/{channel_id}/videos`) added `sort` parameter (`latest` | `most_viewed`) and `scan_depth` (10–250, default 50).
  2. Implemented numeric descending sorting with `(-has_views, -view_num, -upload_ts, vid_id)`.
  3. Added segmented sort controls (`📅 Latest` vs `🔥 Most Viewed`) with scan scope badge in `frontend/app/automation/page.tsx`.
- **Verification Evidence:** Direct live query to Nishant Chahar channel returned sorted items: 325,000 > 278,000 > 232,000 > 197,000 > 189,000 on page 1, followed by 169,000 > 145,000 on page 2. Unit tests in `frontend/test/monitoring_audit_repairs.test.mjs` and `backend/tests/test_monitoring_backend_audit.py` passed 100%.

---

### `CF-DEF-019` — Decision History Missing Source Provenance & Error Message (PROV)
- **Category:** Provenance & Failure Traceability Defect
- **Status:** **RESOLVED & VERIFIED IN MONITORING AUDIT REPAIRS**
- **Code Locations:** `backend/api/routes/channels.py`, `frontend/lib/api.ts`, `frontend/app/automation/page.tsx`, `frontend/test/monitoring_audit_repairs.test.mjs`, `backend/tests/test_monitoring_backend_audit.py`
- **Expected Behavior:** Failed video-processing attempts must display original YouTube video title, thumbnail (where available), direct validated source link/ID, and explicit error message/stage. When a monitored video is in fact a previously generated/published Short, the UI and API must distinguish the generated Short ID/link from its authentic originating source video ID/link.
- **Actual Observed Behavior Prior to Fix:**
  1. `list_decision_history` omitted `Job.error_message`, `Job.source_title`, `Job.source_url`, and thumbnail.
  2. `GET /api/channels/{channel_id}/videos` badged failed jobs as `✓ Processed` because `Video` record or `decision.job_id` was non-null, blocking user re-selection.
  3. When destination channel `clipse` was monitored, published Shorts (`0OfOivc-tpU`, `kkXWbXZI_iM`, etc.) were scanned as intake videos. The API reported `0OfOivc-tpU` as the source video ID rather than tracing through `clips.youtube_short_id` and foreign key `clips.video_id` to the authentic origin source video (`MjDUTSOsUMg` — "Software is DEAD! This GitHub Repo Can Build Anything in Few Hours").
- **Remediation Delivered:**
  1. Updated `list_decision_history` in `backend/api/routes/channels.py` to join `Job`, `Video`, and pre-fetch clip origins from `Clip` + parent `Video`. The endpoint now serializes:
     - `is_generated_short`: Boolean indicating if the item is a reprocessed published Short.
     - `generated_short_id` / `generated_short_url` / `generated_short_title`: Distinct Short references (`https://www.youtube.com/shorts/...`).
     - `source_youtube_id` / `source_video_title` / `source_youtube_url`: Canonical originating full-length source video (`https://www.youtube.com/watch?v=...`).
     - `error_message` / `job_error` / `current_step`: Explicit failure stage and exception details.
  2. Fixed `is_processed` logic in `get_channel_recent_videos` to only evaluate to `True` if `clip_count > 0` or `job_status == 'completed'`. Added `job_status`, `job_error`, and `view_count` to video items.
  3. Updated `frontend/app/automation/page.tsx` Decision History table:
     - Displays thumbnail and true source video title.
     - Displays originating source link (`Source: 🔗 [source_id]`).
     - Displays reprocessed Short link (`Short: 🎬 [short_id]`) in magenta badge when `is_generated_short` is true.
     - Displays red failure alert container with `[current_step] error_message`.
  4. Discovered video cards now display `❌ Failed` badge with error tooltip, allowing failed items to be selected and re-queued.
- **Verification Evidence:**
  1. Live read-only query to `/api/channels/decisions/history?limit=10` confirmed:
     - `0OfOivc-tpU`: `is_short: True`, `source_yt_id: MjDUTSOsUMg`, `short_id: 0OfOivc-tpU`, `job_status: failed`.
     - `kkXWbXZI_iM`: `is_short: True`, `source_yt_id: Cm45rJ_ayA4`, `short_id: kkXWbXZI_iM`, `job_status: failed`.
     - `YpHobheDpk8`: `is_short: True`, `source_yt_id: UBHOWXL4Apg`, `short_id: YpHobheDpk8`, `job_status: failed`.
     - `L3ihlJVo_3A`: `is_short: True`, `source_yt_id: bBlahWRZ2Yw`, `short_id: L3ihlJVo_3A`, `job_status: failed`.
     - `FoNMm4F9qIM`: `is_short: True`, `source_yt_id: m5hidzW-_i0`, `short_id: FoNMm4F9qIM`, `job_status: failed`.
     - `39w4TLjreFU`: `is_short: True`, `source_yt_id: -rPzGJH1acU`, `short_id: 39w4TLjreFU`, `job_status: failed`.
     - `m5hidzW-_i0`: `is_short: False`, `source_yt_id: m5hidzW-_i0`, `short_id: None`, `job_status: failed`.
  2. Unit test suites passed 100%:
     - `frontend/test/monitoring_audit_repairs.test.mjs` (6/6 passing).
     - `backend/tests/test_monitoring_backend_audit.py` (3/3 passing).
     - Entire frontend test suite: 66/66 passing. Type check: 0 errors (`npx tsc --noEmit`).

---

### `CF-DEF-020` — Empty Subsequent Pages Due to Missing `/videos` Tab Path (PAGE)
- **Category:** Upstream Extraction / URL Scheme Normalization Defect
- **Status:** **RESOLVED IN MONITORING AUDIT REPAIRS**
- **Code Locations:** `backend/services/downloader.py`
- **Expected Behavior:** Paginating discovered videos must return subsequent chunks (Page 2, Page 3) for channels with large catalogs.
- **Actual Observed Behavior Prior to Fix:** Page 1 returned 8 items, but Page 2 returned `items: []`. Root cause: channel URL lacked `/videos` tab, causing yt-dlp to extract the YouTube channel "Home" tab which only contains an ~8-item shelf.
- **Remediation Delivered:**
  1. Created `normalize_channel_url()` in `backend/services/downloader.py`. Automatically appends `/videos` for channel URLs targeting handles (`/@...`), `/channel/...`, `/c/...`, and `/user/...`.
  2. Added graceful fallback to base channel URL if yt-dlp reports the channel does not have a videos tab.
- **Verification Evidence:** Tested on `https://www.youtube.com/@NishantChahar11` in Docker: Page 1 returned 8 items, Page 2 returned 8 items, Page 3 returned 8 items with `has_more=True`. Unit tests passed 100%.

---

### `CF-DEF-021` — Four-Option Historical Selection Confusion (UX)
- **Category:** User Experience / Information Architecture Defect
- **Status:** **RESOLVED IN MONITORING AUDIT REPAIRS**
- **Code Locations:** `frontend/app/automation/page.tsx`
- **Expected Behavior:** Historical processing should present two clear primary actions: "Upload Recent Videos" and "Upload Old Videos", while retaining secondary controls (count, depth, popularity ranking, date cutoff, candidate preview) and keeping continuous 24/7 monitoring visually distinct.
- **Actual Observed Behavior Prior to Fix:** UI presented 4 radio cards (Option A, Option B, Option C, Option D) that conflated historical backfill with ongoing monitoring and confused operators.
- **Remediation Delivered:**
  1. Replaced 4 pills in Channel Subpanel with two primary action buttons: `⚡ Upload Recent Videos` (Primary Choice 1) and `⏳ Upload Old Videos` (Primary Choice 2).
  2. Restructured Historical Modal to feature the Two-Action Model:
     - "Upload Recent Videos": count (default 3), scan depth, collapsible date cutoff.
     - "Upload Old Videos": popularity ranking (`🔥 Most-Viewed` vs `📅 Chronological`), count (default 5), scan depth, collapsible date cutoff.
  3. Added a dedicated continuous monitoring indicator clearly separating 24/7 automated clipping of new uploads from historical backfill.
- **Verification Evidence:** `frontend/test/monitoring_audit_repairs.test.mjs` state transition tests passed. TypeScript type check clean (0 errors), all 65 frontend tests passed.

---

### `CF-DEF-022` — Self-Ingestion of Published Output Shorts via Channel Monitoring, Batch Selection, Manual Processing, and Retry
- **Category:** Ingestion Pipeline / Provenance Defense Defect
- **Status:** **RESOLVED & VERIFIED IN MONITORING REPAIRS**
- **Code Locations:**
  - `backend/services/provenance.py` (New central provenance service)
  - `backend/services/channel_monitor.py` (`check_channel_for_new_videos`)
  - `backend/api/routes/channels.py` (`get_channel_recent_videos`, `process_channel_video`, `preview_historical_videos`, `process_historical_batch`)
  - `backend/api/routes/videos.py` (`process_youtube_url`)
  - `backend/api/routes/jobs.py` (`retry_failed_job`)
  - `backend/tasks/orchestration.py` (`resolve_video_decision_sync`)
  - `frontend/lib/api.ts` (`PaginatedVideosResponse`, `HistoricalCandidateItem`)
  - `frontend/app/automation/page.tsx` (Card badges, disabled checkbox, disabled buttons, origin display)
- **Initial Defect Description:**
  - Forensic analysis of historical failed jobs on destination channel `clipse` (`UCH90024qrJHA4amGRxnTldw`) revealed 6 failed jobs (`0OfOivc-tpU`, `kkXWbXZI_iM`, `YpHobheDpk8`, `L3ihlJVo_3A`, `FoNMm4F9qIM`, `39w4TLjreFU`) in which ClipForge-generated Shorts were discovered on the destination channel and treated as new intake videos.
  - The scanner and ingestion endpoints only checked `Video.youtube_id` (long-form source IDs) and `VideoDecision.youtube_id`, completely omitting `Clip.youtube_short_id`.
  - When self-ingested jobs failed, `is_processed` evaluated to `False`, rendering active checkboxes and buttons in Discovered Videos, allowing accidental re-queueing.
  - The job retry endpoint (`POST /api/jobs/{id}/retry`) re-submitted Celery tasks for ClipForge Shorts.
  - An authentic source video (`m5hidzW-_i0` / Kimi K3) failed due to a legitimate duration boundary limit (`OutputValidatorError: Duration 30.2s exceeds 30.0s`), requiring its retry capability to be preserved while blocking the 6 self-ingested Shorts.
- **Remediation Delivered:**
  1. **Central Provenance Service:** Created `backend/services/provenance.py` with `check_is_clipforge_short`, `check_is_clipforge_short_sync`, `get_clipforge_shorts_map`, and `extract_yt_id`.
  2. **Automatic 24/7 Monitor Protection:** In `check_channel_for_new_videos`, skips any discovered video whose ID exists in `Clip.youtube_short_id`.
  3. **Discovered Videos Provenance:** In `get_channel_recent_videos`, tags output Shorts with `is_generated_short = True`, `is_processed = True`, `parent_source_id`, `parent_source_title`.
  4. **Manual Processing Protection:** In `process_channel_video`, rejects ClipForge Short IDs with HTTP 400.
  5. **Historical Preview & Batch Exclusion:** In `preview_historical_videos`, tags candidates with `clipforge_short` and excludes them from `eligible_items`. In `process_historical_batch`, rejects Short IDs with `"rejected_clipforge_short"`.
  6. **Direct URL Protection:** In `process_youtube_url`, rejects Short URLs with HTTP 400.
  7. **Job Retry Guard:** In `retry_failed_job`, rejects retrying Short jobs with HTTP 400 while permitting authentic source videos (`m5hidzW-_i0`).
  8. **Fail-Safe Decision Resolution:** In `resolve_video_decision_sync`, cancels decision if target video is an output Short.
  9. **Frontend UI Defense:**
     - Discovered video cards show purple `🎬 ClipForge Short` badge, origin source link, disabled checkbox, and disabled `⚡ Defaults` / `⚙️ Custom` action buttons.
     - `selectAllEligibleOnPage` and `toggleSelectVideo` strictly ignore ClipForge Shorts.
     - Historical modal preview displays `🎬 ClipForge Short (Excluded)` badge and origin title.
- **Verification Evidence:**
  1. All 7 historical failed entries individually verified:
     - 6 ClipSee Shorts blocked from re-ingestion, retry rejected with HTTP 400, provenance accurately displayed.
     - 1 Nishant Chahar source video (`m5hidzW-_i0`) evaluated as `is_short = False` with retry capability preserved.
  2. Live API execution verified:
     - `POST /api/videos/url` for `0OfOivc-tpU` -> HTTP 400 blocked.
     - `POST /api/channels/{id}/process-video` for `0OfOivc-tpU` -> HTTP 400 blocked.
     - `POST /api/jobs/aaa86be8-ab16-42a7-b9dd-306db7f95a2b/retry` -> HTTP 400 blocked.
     - `GET /api/channels/518b3118-2367-4f84-898f-ff97a61df306/videos` -> all 6 items returned with `is_generated_short: True`, `is_processed: True`, and parent source titles/IDs.
     - `POST /historical-preview` on ClipSee -> `will_queue: 0`, `eligible_found: 0`.
     - `POST /historical-process` on ClipSee -> all Shorts rejected with `status: rejected_clipforge_short`.
     - Channel monitor execution on ClipSee -> 0 new videos discovered.
  3. Test suites:
     - Backend unit tests (`backend/tests/test_monitoring_backend_audit.py`): 5/5 passing in 0.305s.
     - Frontend test suite: 68/68 passing in 192ms.
     - TypeScript typecheck: 0 errors (`npx tsc --noEmit`).
  4. Real browser verification: captured screenshots showing `🎬 ClipForge Short` badge and origin links.

---

### `CF-DEF-023` — Auto-Publish Destination Enforcing & Worker Silent Publishing Failure
- **Category:** Publishing Pipeline / API Contract & Worker Logic Defect
- **Status:** **RESOLVED & VERIFIED IN AUDIT REPAIRS**
- **Code Locations:**
  - `backend/api/routes/channels.py` (`add_channel`, `update_channel`)
  - `backend/tasks/clip_tasks.py` (`publish_task`, `publish_clip_task`)
  - `frontend/app/automation/page.tsx` (`handleAdd`, `handleToggle`)
  - `backend/tests/test_monitoring_backend_audit.py`
  - `frontend/test/monitoring_audit_repairs.test.mjs`
- **Initial Defect Description:**
  1. **API Validation Absence:** Backend permitted enabling `auto_publish = True` without a linked destination channel (`publish_destination_id = None`), leading to stranded publish jobs where generated clips had no destination to be uploaded to.
  2. **Worker Silent Bypass Bug:** In `clip_tasks.py` worker (`publish_task`), the worker previously inspected `dest_channel.auto_publish`. Because destination channels (e.g., `ClipSee`) are output channels and never set `auto_publish = True` on themselves (only intake source channels have auto-publish configured), the worker silently skipped publishing every target and marked the status as `"completed"` without ever calling YouTube upload.
  3. **Frontend Invariant Absence:** In `frontend/app/automation/page.tsx`, operators could toggle auto-publish without a destination channel selected, or clear the destination while leaving auto-publish active.
- **Remediation Delivered:**
  1. **Backend Route Enforcing:**
     - `POST /api/channels`: Returns HTTP 422 if `auto_publish=True` without `publish_destination_id`. Validates destination exists, is marked `is_destination=True`, and `is_active=True` (returns HTTP 400 otherwise).
     - `PATCH /api/channels/{id}`: Blocks enabling `auto_publish=True` without an active destination. When destination is cleared (`publish_destination_id=""` or `None`), auto-clears `auto_publish = False`.
  2. **Worker Logic Fix in `publish_task`:**
     - Corrected worker to inspect source channel and `job.config["auto_publish"]` instead of destination channel.
     - When `auto_publish` is disabled for the job/channel, preserves clip in `"draft"` status and `PublishTarget` remains `"pending"` for manual publishing from the Studio.
     - When `auto_publish` is enabled, verifies destination exists and active, then uploads to destination YouTube channel.
  3. **Frontend UI Enforcing:**
     - `handleAdd`: Validates destination selection before submitting channel creation if auto-publish is toggled.
     - `handleToggle`: Rejects toggling auto-publish on without a destination. Automatically disables auto-publish if the destination channel is unlinked.
- **Verification Evidence:**
  1. Backend test suite (`test_monitoring_backend_audit.py`): 7/7 passing in 0.54s.
  2. Celery dispatch defense tests (`test_publish_task_dispatch_defense.py`): 5/5 passing in 5.62s.
  3. Studio publishing tests (`test_upload_studio_phase3_publishing.py`): 15/15 passing in 2m29s.
  4. Privacy hardening tests (`test_publishing_privacy_hardening.py`): 48/48 passing.
  5. Frontend test suite (`monitoring_audit_repairs.test.mjs`): 9/9 audit repair suites (69/69 total frontend tests) passing in 209ms.
  6. TypeScript compilation (`npx tsc --noEmit`): 0 errors.
  7. Python syntax check (`python -m compileall backend`): 0 errors.




