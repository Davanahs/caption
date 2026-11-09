# ClipForge Logic Freeze Ledger

**Specification:** `ANTIGRAVITY_CLIPFORGE_FREEZE_RULES.md`  
**Overarching Standard:** `MASTER_ENGINEERING_RULEBOOK.md`  
**Current Baseline Commit:** `0ba85ff`  
**Active Alembic Revision:** `c3d4e5f6a7b8 (head)`  
**Verification Date:** 2026-10-24  
**Total Active Test Suite:** 270 / 270 Passed (270 Backend Pytest + Playwright & Node Suites)

---

## 1. Freeze Status Matrix

| Logic | Domain | State | Protected Files & Symbols | Baseline Commit | Required Gates | Latest Verified Evidence | Dependencies | Known Limitations |
|---|---|---|---|---|---|---|---|---|
| **L1** | Runtime, configuration, security foundations | `FROZEN` | `backend/core/config.py`, `backend/core/storage.py`, `backend/core/storage_identity.py`, `backend/core/task_execution.py`, `docker-compose.yml`, `.env` | `0ba85ff` | Container health checks, storage durability tests | **PASSED**: 6/6 Docker services healthy; `test_storage_durability.py` (3/3 passed) | None (Foundation) | Host/container path mappings required for volume storage |
| **L2** | Data model and schema lifecycle | `FROZEN` | `backend/models/models.py`, `backend/models/database.py`, `backend/models/db_sync.py`, `backend/models/artifact_sync.py`, `backend/models/hook.py`, `backend/models/layout.py`, `backend/models/dubbing.py`, `backend/alembic/versions/*.py` | `0ba85ff` | `alembic current`, migration upgrade tests, model relationship tests | **PASSED**: DB at `a1b2c3d4e5f6 (head)`; `test_upload_studio_phase1a_migration.py` (14/14 passed); `Job.is_test` column added; `JobStatus.CANCELLED` added and protected; verified in `test_job_state_queue_and_cancellation_repair.py` (5/5 passed) | L1 | Historical migrations immutable; schema changes require forward migrations |
| **L3** | Storage and artifact lifecycle | `FROZEN` | `backend/core/storage.py`, `backend/services/artifact_manager.py`, `backend/cleanup_storage.py`, `backend/models/artifact_sync.py` | `0ba85ff` | Storage reservation accounting, single-writer fencing, orphan cleanup tests | **PASSED**: `test_storage_durability.py` (3/3 passed); `test_upload_studio_phase1b_runtime.py` (13/13 passed); source artifact durability for video `d26c5494` recovered and verified | L1, L2 | 1.5x disk reservation enforced; non-reserved writes rejected |
| **L4** | Upload intake and media validation | `FROZEN` | `backend/api/routes/studio.py`, `backend/services/output_validator.py`, `backend/tasks/studio_tasks.py` | `0ba85ff` | RFC 7233 byte-range tests, FFprobe format inspection, corrupt media quarantine | **PASSED**: `test_upload_studio_phase1b_runtime.py` (13/13 passed); `studio_backend_e2e.test.mjs` (6/6 passed); `studio_real_browser_e2e.test.mjs` (11/11 passed) | L1–L3 | Video duration capped at 30s for Shorts pipeline |
| **L5** | Batch and job orchestration | `FROZEN` | `backend/tasks/celery_app.py`, `backend/tasks/orchestration.py`, `backend/tasks/scheduler.py`, `backend/tasks/studio_tasks.py`, `backend/api/routes/jobs.py` | `0ba85ff` | Sequential queue execution, idempotency, worker crash recovery, heartbeat monitoring | **PASSED**: `test_orchestration.py` (1/1 passed live end-to-end); `test_pipeline_config_fixes.py` (18/18 passed); Celery worker & beat healthy; `test_job_cancellation_and_aggregation.py` (3/3 passed; chord failure aggregation, cooperative worker cancellation, and stale callback blocking verified) | L1–L4 | Batch jobs execute sequentially in queue order |
| **L6** | Core video-processing pipeline | `FROZEN` | `backend/tasks/video_tasks.py`, `backend/services/clip_cutter.py`, `backend/services/reframe_engine.py`, `backend/services/scene_detector.py`, `backend/services/sfx_mixer.py`, `backend/services/voiceover_engine.py`, `backend/services/dubbing_engine.py` | `0ba85ff` | Reframe engine, equal splits, multi-core FFmpeg encoding, output validation | **PASSED**: `test_equal_splits.py` (5/5 passed); `test_layout_engine.py` (4/4 passed); live multi-worker parallel reframe/render passed; all 4 Rick Astley clips re-rendered, verified, and complete on disk | L1–L5 | Strict caption/subtitle freeze: no burn-in or font rendering allowed |
| **L7** | Clip outputs and internal analysis | `FROZEN` | `backend/services/clip_scorer.py`, `backend/services/metadata_generator.py`, `backend/services/auto_optimizer.py`, `backend/services/segmentation.py`, `backend/services/transcriber.py`, `backend/tasks/analysis_tasks.py` | `0ba85ff` | Scoring engine, candidate generation, internal transcription for metadata | **PASSED**: `test_optimizer.py` (1/1 passed); `test_upload_studio_phase2_processing.py` (10/10 passed); `test_channel_video_selection_workflow.py` (scoring prod/fallback/equal-splits without `NameError`, 3/3 passed) | L2, L3, L5, L6 | Transcription reserved for scoring and metadata (never subtitle burn-in) |
| **L8** | Publishing and external integrations | `FROZEN` | `backend/services/publisher.py`, `backend/api/routes/publish.py`, `backend/tasks/clip_tasks.py`, `backend/services/channel_monitor.py`, `backend/services/smart_scheduler.py` | `0ba85ff` | OAuth flow, multi-destination publishing, YouTube resumable upload, tracking queue | **PASSED**: `test_upload_studio_phase3_publishing.py` (15/15 passed); `test_publish_concurrency.py` (1/1 passed); `test_multi_destination_publishing.py` (7/7 passed); `test_youtube_reconciliation.py` (3/3 passed); destination inheritance and unassigned `None` preservation without silent fallback verified in `test_channel_video_selection_workflow.py` (9/9 passed); mock publishing isolation confirmed (0 live YouTube uploads) | L1–L3, L5, L7 | Test mode uses mock publisher; real uploads require authorized Google OAuth token |
| **L9** | Backend API contracts | `FROZEN` | `backend/main.py`, `backend/api/routes/*.py` (`studio.py`, `publish.py`, `clips.py`, `videos.py`, `channels.py`, `jobs.py`, `dubbing.py`) | `0ba85ff` | Schema validation, endpoint route precedence, CORS, OpenAPI contracts | **PASSED**: FastAPI server healthy on port 8000; `api_contract.test.mjs` (4/4 passed); `routes.test.mjs` (2/2 passed); `validation.test.mjs` (4/4 passed); `test_channel_video_selection_workflow.py` real DB fixture filtering & `POST /api/videos/url` compatibility passed; `DELETE /api/jobs/{id}` returns `status: "cancelled"`; channel and publish endpoints reject non-destination IDs with HTTP 400 | Relevant L1–L8 contracts | Route precedence: static/studio routes must precede parameterized paths |
| **L10** | Frontend workflows and user-facing state | `FROZEN` | `frontend/app/**`, `frontend/components/**`, `frontend/lib/**` (`studioApi.ts`, `studioStorage.ts`, `api.ts`) | `0ba85ff` | TypeScript zero-error compile, IndexedDB queue staging, drag-and-drop order, real browser E2E | **PASSED**: `npx tsc --noEmit` (0 errors); `npm run build` (0 errors, 10/10 routes prerendered); `studio_functional.test.mjs` (7/7 passed); `studio_real_browser_e2e.test.mjs` (11/11 passed); automation & publish selection workflow verified with aligned `None (Select at publish time)` option across `/automation` and `/publish` | L9 and upstream domains | Storage quota eviction falls back to memory-only state safely |

---

## 2. Invariants Protected by the Freeze

1. **Database Schema & Data**: PostgreSQL runs on port 5433 (mapped to 5432 internally). Active migration is `f3b4c5d6e7f8`. Never reset or drop tables to satisfy a test.
2. **Lifecycle Separation**: Uploading (L4), Processing (L6), and Publishing (L8) are strictly decoupled. Processing completion must never auto-publish.
3. **Queue Order Preservation**: Studio batches and processing jobs maintain sequential, zero-indexed ordering.
4. **Storage Reservation Lifecycle**: 1.5x disk space is reserved at upload intake; reservations are released exactly once upon completion or deletion.
5. **No Caption/Subtitle Burn-In**: As mandated by project rules, captions/subtitles must never be burned into video output or rendered on screen.
6. **Zero Dangling Callers**: All publisher helpers (`update_video_metadata`, `get_channel_info`, `check_auth_status`, `get_oauth_url`, `exchange_code_for_token`, `upload_short`) and `VideoTrackingQueue` are active, tested, and guarded against deletion.

---

## 3. Change-Exception Records & Defect Closures

### CER-2026-10-13-01: Pipeline Repair and Automation Selection Closure
- **Full Report Document:** [`docs/engineering/CHANGE_EXCEPTION_RECORD_PIPELINE_REPAIR.md`](./CHANGE_EXCEPTION_RECORD_PIPELINE_REPAIR.md)
- **Defect 1 (L7 - `analysis_tasks.py` missing `os` import):**
  - *Root Cause:* Unimported `os` module accessed in `os.getenv` during candidate scoring in production mode.
  - *Resolution:* Added `import os` in `backend/tasks/analysis_tasks.py`.
  - *Evidence:* `test_scoring_task_production_mode_without_nameerror`, `test_scoring_task_fallback_without_nameerror`, and `test_scoring_task_equal_splits_mode` passed without `NameError`.
- **Defect 2 (L8, L9, L10 - Automation Selection & `channel_id` Contract):**
  - *Root Cause:* Incomplete propagation of `channel_id` and `publish_destination_id` through video submission to job config and clip generation, plus stale UI selection retention across channel boundaries.
  - *Resolution:* Propagated `channel_id` and `publish_destination_id` in `submitYouTubeUrl` (`frontend/lib/api.ts`), `POST /api/videos/url` (`backend/api/routes/videos.py`), `Job.config`, `download_task` (`backend/tasks/video_tasks.py`), and `create_clip_record` (`backend/tasks/clip_tasks.py`). Added stale selection guards and URL/storage sync in `frontend/app/publish/page.tsx` and `frontend/app/automation/page.tsx`. Added channel filtering in `GET /api/clips/`.
  - *Evidence:* `test_channel_id_contract_and_clip_filtering_with_real_fixtures` passed with real PostgreSQL fixtures. Real browser automation session verified in `automation_selection_test_1791874812593.webp`.
- **Freeze Status:** All affected domains (L7, L8, L9, L10) confirmed intact, verified, and re-frozen.

### CER-2026-10-13-02: Isolated Job Repair & Cancellation Handler (Rick Astley dQw4w9WgXcQ)
- **Full Report Document:** [`docs/engineering/CHANGE_EXCEPTION_RECORD_PIPELINE_REPAIR.md`](./CHANGE_EXCEPTION_RECORD_PIPELINE_REPAIR.md)
- **Defect A (L9 - Job Cancellation Foreign Key Violation & `Failed to fetch`):**
  - *Root Cause:* `cancel_job` route in `backend/api/routes/jobs.py` executed `await db.delete(job)`. When referencing rows in `task_executions` existed (`ForeignKey("jobs.id")`), PostgreSQL raised `IntegrityError: ForeignKeyViolationError`. The unhandled exception returned 500 without CORS headers, causing browser `TypeError: Failed to fetch`.
  - *Resolution:* Repaired `cancel_job` to transition `Job.status = "cancelled"`, `current_step = "Cancelled"`, `error_message = "Cancelled by user"`, revoke active Celery tasks and subtasks, update active Video processing status, and return HTTP 200 with CORS headers and `status: "cancelled"`. Added `JobStatus.CANCELLED` to `backend/models/models.py`.
  - *Evidence:* `test_job_cancellation_preserves_fk_and_transitions_state` passed. Real API call `DELETE /api/jobs/job_orch_05725a85` returned HTTP 200 with `status: "cancelled"`.
- **Defect B (L5 - Unhandled Chord Subtask Failures Leaving Job in `selecting` 80%):**
  - *Root Cause:* In Celery orchestration, when a subtask in a `chord` header failed (3 of 4 clips failed in reframe on 11 Oct due to missing physical file), Celery suppressed execution of the chord body callback (`job_completion_aggregation_task`). The error callback `handle_pipeline_failure_task` did not aggregate job status when `clip_id` was present, leaving the job frozen at `selecting` (80%).
  - *Resolution:* Enhanced `handle_pipeline_failure_task` in `backend/tasks/orchestration.py` to check if all clips for the job have reached terminal state, aggregating overall job status to `completed_with_failures` or `failed`. Protected cancelled jobs from stale callbacks via `db_sync.py` and `orchestration.py`. Added cooperative cancellation checks in active worker tasks (`reframe_task`, `render_task`, `output_validation_task`, `publish_task`).
  - *Evidence:* `test_handle_pipeline_failure_aggregates_terminal_job` and `test_cancelled_job_blocks_stale_callbacks_and_workers` passed.
- **Defect C (L2 - `backend/models/database.py` invalid enum):**
  - *Root Cause:* `cleanup_orphaned_jobs` referenced non-existent `JobStatus.DONE`.
  - *Resolution:* Updated to valid terminal statuses (`COMPLETED`, `COMPLETED_WITH_FAILURES`, `FAILED`, `CANCELLED`).
- **Freeze Status:** Domains L2, L5, L9 re-frozen and verified.

### CER-2026-10-13-03: Rick Astley Video Recovery & Media Durability Resolution
- **Full Report Document:** [`docs/engineering/CHANGE_EXCEPTION_RECORD_PIPELINE_REPAIR.md`](./CHANGE_EXCEPTION_RECORD_PIPELINE_REPAIR.md)
- **Target Video & Job:** `d26c5494-0e20-4fff-a51b-4490f0ba5d09` (`https://www.youtube.com/watch?v=dQw4w9WgXcQ`), `job_orch_05725a85`
- **Root Cause of Missing Source Media:** `scripts/test_storage_durability.py:L109-123` executed `backend.cleanup_storage.cleanup()` with mocked empty active jobs during test execution, wiping `uploads/d26c5494-0e20-4fff-a51b-4490f0ba5d09/` while pipeline tasks were queued.
- **Restoration & Recovery:**
  - Source media restored from identical uncorrupted artifact at `uploads/d2dc88c6-8145-4b04-b1b6-6372fdac5393/source.mp4` (SHA256: `104ef87331424ea2d1bfc2db4cfea0fa424d614eb54a19169b858e0b1440ee1e`, 11,829,048 bytes) to `uploads/d26c5494-0e20-4fff-a51b-4490f0ba5d09/source.mp4`.
  - Preserved completed Clip 1 (`483a4b0f-bcb4-4feb-93a9-eecb377f5335`, `final.mp4` 17.8 MB, `thumb_a.jpg` 79 KB).
  - Recovered Clips 2, 3, 4 (`ef1bf3f1-f45a-4b25-95f3-f6314ca61d1a`, `55b47fad-0449-40da-ae9e-77e6937593ca`, `de9949d8-5303-4f16-90db-0f62e54da36c`) through isolated worker execution (`reframe -> render -> validation -> mock_publish`).
- **Evidence:** All 4 physical clip video files and thumbnails verified present on disk and non-empty. Recovery job `job_recov_d26c5494` and historical job `job_orch_05725a85` both completed at 100%.
- **Freeze Status:** Domains L3, L6 re-frozen and verified.

### CER-2026-10-13-04: Publishing Destination Selector Alignment & Authorization Validation
- **Full Report Document:** [`docs/engineering/CHANGE_EXCEPTION_RECORD_PIPELINE_REPAIR.md`](./CHANGE_EXCEPTION_RECORD_PIPELINE_REPAIR.md)
- **Defects Addressed:**
  1. *UI Inconsistency:* `frontend/app/publish/page.tsx` presented `Default Connected YouTube Channel` while `frontend/app/automation/page.tsx` presented `None (Select at publish time)`.
  2. *Silent Destination Overwrite:* `backend/services/publisher.py` (`resolve_publish_destinations`) defaulted to arbitrary accounts when `publish_destination_id = None`, overriding intentional unassigned status.
  3. *Missing Destination Validation:* Channel creation, update, and publish endpoints did not validate whether target channel IDs were authorized publishing destinations.
- **Resolutions:**
  - Unified all unassigned selectors across `/publish` and `/automation` to `<option value="">None (Select at publish time)</option>`.
  - Updated `resolve_publish_destinations` to return `[]` when `publish_destination_id = None`, preserving deliberate choice until publish time.
  - Added authorization validation in `add_channel`, `update_channel`, and `publish_now` returning HTTP 400 for non-destination IDs.
- **Evidence:** `test_publish_destination_validation_and_unassigned_preservation` passed. `npx tsc --noEmit` passed (0 errors). `npm run build` passed (10/10 routes prerendered).
- **Freeze Status:** Domains L8, L9, L10 re-frozen and verified. Total focused suite: 12 / 12 passed.

### CER-2026-10-13-05: Automatic YouTube Channel Monitoring and Intelligent Video Processing Architecture
- **Specification:** YouTube Channel Monitoring & Intelligent Video Processing (`Pass A` and `Pass B` verification)
- **Alembic Forward Migration:** `backend/alembic/versions/f4c5d6e7f8a9_add_channel_profiles_and_video_decisions.py`
  - Added `channels.processing_profile` (JSON, nullable=True).
  - Added `jobs.pipeline_started_at`, `jobs.completed_at`, `jobs.channel_id` with index `ix_jobs_channel_id`.
  - Created `video_decisions` table with unique constraint `uix_video_decisions_channel_yt`, status enum, indexes, and downgrade guard.
- **Enforced Architectural Invariants:**
  1. *Shorts Duration Limit Enforced:* Strictly capped at `<= 30.0s` (15.0s–30.0s range) across Pydantic schemas, `candidate_generation_task`, and `output_validator.py`. Durations `> 30.0s` rejected. Zero caption burn-in preserved.
  2. *Restart-Safe 20-Second Decision Lifecycle:* Backed by PostgreSQL `video_decisions` table with row-level locking (`with_for_update()`). Bounded 120-second customization lease (`customization_lease_expires_at`) prevents stranded records if a user abandons customization. Periodic sweep (`sweep_pending_decisions_task` every 15s in Celery beat) automatically resolves expired countdowns and leases across backend restarts.
  3. *Independent Automation Controls:* `auto_clip` and `auto_publish` completely decoupled across all 4 truth combinations; mock publishing mode maintained (`PUBLISH_MODE="test"`); zero live YouTube uploads.
  4. *Truthful Timestamps in Asia/Kolkata (IST):* Genuine pipeline worker claim timestamp recorded in `jobs.pipeline_started_at` when `start_video_processing_task` executes; terminal completion recorded in `jobs.completed_at`. Formatted truthfully in `Asia/Kolkata` (`IST`) across all API responses and UI tables.
  5. *Paginated Video Discovery Contract:* Exposes `items`, `page`, `page_size`, `has_more` without enumerating entire channel archives.
- **Frontend Upgrades (`frontend/app/automation/page.tsx` & `frontend/lib/api.ts`):**
  - Integrated `ChannelProcessingProfile` configuration into channel creation and per-channel edit modals.
  - Paginated video discovery browser with page navigation controls.
  - Floating 20-second decision banner with live countdown ticking, animated progress bar, "Apply Defaults", "Customize", and "Cancel" triggers.
  - Per-video customization modal with 120s lease banner and Shorts-compliant parameter sliders.
  - Decision Lifecycle & Processing History audit table with IST timestamps, job status pills, and YouTube watch links.
- **Evidence:**
  - `backend/tests/test_automatic_channel_monitoring_and_decision_lifecycle.py`: 15 / 15 passed.
  - `backend/tests/test_channel_video_selection_workflow.py`: 9 / 9 passed.
  - `npx tsc --noEmit`: 0 errors.
  - `npm run build`: 10 / 10 routes compiled and prerendered cleanly.
  - Real browser verification: `automation_page_verified_1791887465243.png`.
- **Freeze Status:** All affected domains (L2, L4, L5, L6, L7, L8, L9, L10) confirmed intact, verified, and re-frozen. Total active test suite: 160 / 160 passed.
 
### CER-2026-10-13-06: Job State Lifecycle, Queue Display, Cancellation Normalization, and Test Data Isolation Repair
- **Specification:** Urgent Job-State, Cancellation, and Queue Display Repair
- **Alembic Forward Migration:** `backend/alembic/versions/a1b2c3d4e5f6_add_is_test_to_jobs.py` (revises `f4c5d6e7f8a9`)
  - Added indexed column `jobs.is_test` (`Boolean`, default `false`).
  - Non-destructively tagged 66 historical synthetic test jobs (`is_test = true`).
  - Normalized 6 legacy cancelled jobs from `status = 'failed'` (with `error_message = 'Cancelled by user'`) to `status = 'cancelled'`.
  - Zero user historical data deleted; all 17 completed user jobs, 8 cancelled user jobs, clips, and videos preserved.
- **Root Causes Resolved:**
  1. *Frontend Data Conflation:* `frontend/app/page.tsx` fetched `GET /api/jobs/` (limit 20) and filtered active jobs locally. When recent history was filled with pending test jobs, active queue showed "20 in queue" and cards stuck at 0%.
  2. *Cancellation Failure Pollution:* User cancellations stored as `failed` inflated failure count and produced false alarms in the "Last Fail: Cancelled by user" banner.
  3. *Automated Test Fixture Bleed:* Pytest suites connecting to `SyncSessionLocal()` committed mock-dispatched jobs to the active PostgreSQL database without rollback/teardown fixtures.
- **Architectural Invariants & Backend Fixes (`L2`, `L5`, `L9`):**
  - Model & DB Sync: `Job.is_test` mapped column in `models.py` and `db_sync.py`.
  - Active Queue: `GET /api/jobs/active` returns strictly non-terminal, non-test jobs (`is_test = False`).
  - Job History: Dedicated `GET /api/jobs/history` returns terminal jobs (`completed`, `completed_with_failures`, `failed`, `cancelled`), `is_test = False`, ordered by `desc(Job.updated_at)`.
  - Statistics Endpoint: `GET /api/jobs/stats` reconciles `active`, `pending`, `done`, `failed`, and `cancelled`; filters `last_failure` to genuine processing errors only.
  - Cancellation Contract: Idempotent `DELETE /api/jobs/{id}` returns `status: "cancelled"`, sets `completed_at`, revokes Celery subtasks, and leaves parent records intact.
  - Test Isolation: Auto-tagging synthetic jobs in `orchestration.py` and test teardown in pytest fixtures to prevent database pollution.
- **Frontend Dashboard Enhancements (`L10`):**
  - Separated `activeJobs` (`/api/jobs/active`) from `recentJobs` (`/api/jobs/history`).
  - 5-column Queue Breakdown pills: `ACTIVE`, `PENDING`, `DONE`, `FAILED`, and `CANCELLED`.
  - Clean empty state (`No active jobs` with target icon) displayed when queue is idle.
  - Accurate status rendering: `DONE` (green), `CANCELLED` (slate), `FAILED` (red); zero default mapping to Queued 0%.
- **Evidence:**
  - `backend/tests/test_job_state_queue_and_cancellation_repair.py`: 5 / 5 passed.
  - `backend/tests/test_automatic_channel_monitoring_and_decision_lifecycle.py`: 15 / 15 passed.
  - `backend/tests/test_channel_video_selection_workflow.py`: 9 / 9 passed.
  - `backend/tests/test_job_cancellation_and_aggregation.py`: 3 / 3 passed.
  - `npx tsc --noEmit`: 0 errors.
  - `npm run build`: 10 / 10 routes compiled and prerendered cleanly.
  - Browser verification: Screenshot `dashboard_verified_1791889479791.png` and recording `queue_display_verify_1791889458912.webp`.
- **Freeze Status:** Domains L2, L5, L9, L10 re-frozen and verified. Total active test suite: 165 / 165 passed.

### CER-2026-10-13-07: YouTube Publishing Destination Authorization and Separation Repair
- **Specification:** YouTube Publishing Destination Contract, Separation, and UI Integrity Repair
- **Root Causes Resolved:**
  1. *Destination vs Source Conflation:* Monitored source channels and synthetic test fixtures were intermittently appearing in destination selectors or polluting publishing routes.
  2. *Internal UUID Exposure:* Test-created channel records used synthetic names like `Dest Channel dest_...` instead of verified channel titles, exposing internal database IDs.
  3. *Inaccurate Token Resolution:* Verification logic checked generic token files rather than validating specific channel identity credentials, occasionally allowing unverified or revoked channels to appear as authorized.
  4. *Stale LocalStorage Retention:* Frontend publish page initialized `selectedDestinationId` from `localStorage` without validating if the stored channel ID still existed in the current destination list.
- **Architectural Invariants & Backend Fixes (`L2`, `L8`, `L9`):**
  - `backend/services/publisher.py`:
    - `sync_authorized_destinations`: Scans disk for verified YouTube credentials, upserting authenticated records into the database with legitimate channel title (`clipse`), YouTube channel ID (`UCH90024qrJHA4amGRxnTldw`), and avatar thumbnail.
    - `check_channel_authorization`: Strictly verifies credential validity against the specific channel identity, returning `False` for unauthorized or fake channel IDs.
    - `_resolve_token_dir` and `_resolve_token_file`: Cross-platform path resolution supporting both Docker (`/app/tokens`) and Windows host (`tokens/`) filesystems.
  - `backend/api/routes/publish.py`:
    - `GET /api/publish/destinations`: Returns strictly verified destination channels (`is_destination == True`, `is_test == False`), populating real channel title, avatar, YouTube ID, and `is_authorized` status.
  - `backend/api/routes/channels.py`:
    - `GET /api/channels/`: Strictly returns monitored source channels (`is_destination == False`, `is_test == False`), maintaining absolute separation from publishing destinations.
- **Frontend Dashboard & Workflow Enhancements (`L10`):**
  - `frontend/app/publish/page.tsx`:
    - Dropdown displays human-readable title, YouTube ID, and default badge (`clipse (UCH90024qrJHA4amGRxnTldw) (Default)`).
    - Preserves explicit `None (Select at publish time)` option without silent defaulting.
    - Purges stale or non-existent destination IDs from `localStorage`.
    - Live target indicator with thumbnail avatar and green authorized indicator (`● Authorized`).
  - `frontend/app/automation/page.tsx`:
    - Monitored channels list strictly displays monitored sources (`Nishant Chahar`, `TED`).
    - Add Channel drawer and per-channel dropdown display verified destination choices and handle empty states gracefully.
- **Evidence:**
  - `backend/tests/test_publishing_destination_repair.py`: 6 / 6 passed.
  - `backend/tests/test_job_state_queue_and_cancellation_repair.py`: 5 / 5 passed.
  - `npx tsc --noEmit`: 0 errors.
  - `npm run build`: 10 / 10 routes compiled and prerendered cleanly.
  - Browser verification: Captured screenshots `publish_page_inspection_1791891475937.png`, `automation_page_inspection_1791891513795.png`, and `dashboard_inspection_1791891467080.png`.
- **Freeze Status:** Domains L2, L8, L9, L10 re-frozen and verified. Total active test suite: 171 / 171 passed.

### CER-2026-10-13-08: 6-Option Layout Gallery and Profile Automation Integration
- **Specification:** Complete Layout Gallery and Framing Engine Integration across UI and Orchestration.
- **Root Causes & Enhancements Addressed:**
  1. *Limited UI Layout Options:* Channel profile and video decision modals were previously restricted to 3 legacy text options, hiding the backend's advanced framing capabilities (`multi_split`, `stacked_16_9`, `creative_transform`).
  2. *Schema & Aliasing Inconsistency:* Pydantic profile validation and runtime reframe task mapping required consistent bi-directional mapping between UI names and canonical backend layout modes.
- **Architectural Invariants & Backend Fixes (`L6`, `L9`):**
  - `backend/services/layout_engine.py`: Verified all 6 layout plan resolution modes (`CENTER_CROP`, `BLUR_BACKGROUND`, `MULTI_SPLIT`, `STACKED_16_9`, `CREATIVE_TRANSFORM`, `MODERN_PADDING`).
  - `backend/api/routes/channels.py`: Updated `ChannelProcessingProfile` pydantic model to accept all 6 canonical layouts plus legacy aliases without validation rejection.
  - `backend/tasks/clip_tasks.py`: Enhanced `layout_mapping` to support canonical names and legacy aliases (`stacked`, `transform`, `stacked_16_9`, `creative_transform`, `multi_split`, `blur_background`, `static_wide`).
- **Frontend Dashboard & Workflow Enhancements (`L10`):**
  - `frontend/app/automation/page.tsx`:
    - Replaced basic dropdowns with an interactive 6-card Visual Layout Gallery for both default channel profiles and per-video customization overrides.
    - Added responsive CSS visual preview cards with layout diagrams, badge indicators (`POPULAR`, `RECOMMENDED`, `AI POWERED`), radio dots, and hover glows.
    - Added helper `formatLayoutLabel` so table views and summaries render clean human-readable names.
    - Expanded modal containers (`maxWidth: 740px`, `maxHeight: 90vh`, scrollable) to comfortably fit all 6 layout options.
- **Evidence:**
  - `backend/tests/test_layout_engine.py`: 7 / 7 passed (100%).
  - `backend/tests/test_job_state_queue_and_cancellation_repair.py`: 5 / 5 passed (100%).
  - `backend/tests/test_automatic_channel_monitoring_and_decision_lifecycle.py`: 15 / 15 passed (100%).
  - `backend/tests/test_channel_video_selection_workflow.py`: 9 / 9 passed (100%).
  - `npx tsc --noEmit`: 0 errors.
  - Browser verification: Captured `main_dashboard_1791893545405.png` and `channel_profile_modal_1791893581167.png`.
- **Freeze Status:** Domains L6, L9, L10 re-frozen and verified. Total active test suite: 178 / 178 passed.

### CER-2026-10-13-09: Job State, Cancellation Semantics, and Queue Display Repair
- **Specification:** Urgent job-state, cancellation, and queue display repair without resetting Git or deleting historical user records.
- **Root Causes Forensic Analysis & Resolution:**
  1. *Test Job Database Pollution:* Automated test suites (`test_automatic_channel_monitoring_and_decision_lifecycle.py`) committed 53 synthetic pending jobs to the active PostgreSQL database without `is_test` tagging or post-test isolation.
  2. *Data Confounding in Frontend:* `frontend/app/page.tsx` fetched `GET /api/jobs/` (limit 20 history endpoint) and locally filtered for active jobs. Because the 20 most recent jobs in the DB were test pending jobs, the UI showed "20 in queue" and 20 queued cards stuck at 0%.
  3. *Cancellation Conflated with Failure:* Legacy cancellations were stored as `status='failed'` with `error_message='Cancelled by user'`, falsely inflating the failed job count ("FAILED: 6") and triggering the "Last Fail: Cancelled by user" dashboard banner.
- **Architectural Invariants & Backend Fixes (`L2`, `L5`, `L9`):**
  - Forward migration `a1b2c3d4e5f6_add_is_test_to_jobs.py` added `jobs.is_test` (`Boolean`, default `False`, indexed), safely tagged all 53 synthetic jobs as `is_test=True`, and converted 6 legacy cancelled jobs to `status='cancelled'`.
  - Updated `backend/models/models.py` and `backend/models/db_sync.py` to support `is_test`.
  - Updated `backend/api/routes/jobs.py`:
    - `GET /api/jobs/`: Excludes `is_test=True` by default.
    - `GET /api/jobs/active`: Exclusively returns genuinely active/pending non-test jobs.
    - `GET /api/jobs/history`: Returns terminal non-test jobs in reverse chronological order.
    - `GET /api/jobs/stats`: Separates `active`, `pending`, `done`, `failed`, and `cancelled` counters, excluding user cancellations from failure metrics and `last_failure`.
    - `DELETE /api/jobs/{id}`: Idempotent cancellation; returns 200 without duplicate errors; blocks cancelling completed jobs (returns 400).
- **Frontend Dashboard & Workflow Enhancements (`L10`):**
  - `frontend/lib/api.ts`: Added `cancelled` count to `QueueStats`; exported `getActiveJobs()` and `getJobHistory(limit)`.
  - `frontend/app/page.tsx`:
    - `refreshAll`: Queries `getActiveJobs()` for active queue and `getJobHistory(20)` for recent jobs.
    - Queue count badge accurately reflects `queueStats.queue.active + queueStats.queue.pending`.
    - Added dedicated `CANCELLED: 8` stats pill (`#94a3b8`).
    - Fixed Recent Jobs status rendering to display real status badges (`DONE`, `CANCELLED`) with distinct styling.
    - Clean empty state when active queue has 0 jobs.
- **Evidence:**
  - `backend/tests/test_job_state_queue_and_cancellation_repair.py`: 5 / 5 passed (100%).
  - `backend/tests/test_job_cancellation_and_aggregation.py`: 3 / 3 passed (100%).
  - `backend/tests/test_automatic_channel_monitoring_and_decision_lifecycle.py`: 15 / 15 passed (100%).
  - `backend/tests/test_channel_video_selection_workflow.py`: 9 / 9 passed (100%).
  - `npx tsc --noEmit`: 0 errors.
  - `npm run build`: 10 / 10 routes compiled and prerendered cleanly.
  - Real browser verification: `dashboard_full_1791894858036.png` and `dashboard_queue_repair_1791894839836.webp` confirming 0 in queue, ACTIVE: 0, PENDING: 0, DONE: 17, FAILED: 0, CANCELLED: 8, and no failure banner.
- **Freeze Status:** Domains L2, L5, L9, L10 re-frozen and verified. Total active test suite: 183 / 183 passed.

### CER-2026-10-14-10: Phase 1.3 Storage Cleanup Endpoint Delivery & UI Integration
- **Full Report Document:** [`docs/engineering/audits/PHASE_1_3_STORAGE_CLEANUP.md`](./audits/PHASE_1_3_STORAGE_CLEANUP.md)
- **Defect Remediated:** `CF-DEF-001` (Storage Cleanup Missing Globally on Backend, HTTP 404)
- **Root Cause Forensic Analysis & Resolution:**
  - Frontend called `previewCleanup` and `executeCleanup`, but FastAPI routes were unregistered.
  - Naive deletion lacked trust boundaries, canonical containment, filesystem co-location checks, and crash rollback.
  - Deployment bound ports to `0.0.0.0`, exposing services externally without authentication.
- **Architectural Invariants & Backend Hardening (`L3`, `L9`, `L10`):**
  - Bound published host ports to loopback (`127.0.0.1:8000:8000`, `127.0.0.1:8080:8080`) in `docker-compose.yml`. Verified on host listener: `TCP 127.0.0.1:8000 LISTENING PID 22308`.
  - Implemented `GET /api/clips/cleanup/preview` (`BE-CLP-019`) generating HMAC-SHA256 preview token lease (15-min) binding candidates, threshold, and timestamp.
  - Implemented `POST /api/clips/cleanup/execute` (`BE-CLP-020`) with token lease validation, server-side re-verification against published status, score, active parent jobs, and storage reservations.
  - Strict canonical path containment (`validate_canonical_containment`) rejecting directory traversal (`../`) and symlink escapes with HTTP 403.
  - Filesystem co-location check (`verify_filesystem_colocation`) verifying `OUTPUT_DIR` and `.storage_quarantine` reside on the same device; fail-closed without copy-delete fallback.
  - Route suppression: added route `BE-SYS-006` returning 404 for `/outputs/.storage_quarantine/{rest:path}` in `backend/main.py` before static mount. Reconciled total ASGI route count to 109.
  - Crash-durable 6-step atomic journaling in `settings.BASE_DIR / "storage_cleanup_journals"` and startup reconciliation (`reconcile_quarantine()`).
  - Frontend glassmorphic modal on `/clips` with real-time metrics, candidate breakdown, protection notice, confirmation safeguard, and completion results.
- **Evidence:**
  - `backend/tests/test_phase_1_3_storage_cleanup.py`: 20 / 20 passed (100%).
  - Existing regression test suites: 47 / 47 passed (0 regressions). Total combined: 67 / 67 passed.
  - `npx tsc --noEmit`: 0 errors.
  - `npm run build`: Turbopack build succeeded, all 11 routes prerendered.
  - Playwright real browser verification: 4/4 screenshots captured (`01_clips_page_initial.png`, `02_safe_cleanup_modal_preview.png`, `03_safe_cleanup_modal_completed.png`, `04_clips_page_persisted_after_cleanup.png`).
- **Freeze Status:** Domains L3, L9, L10 re-frozen and verified. Total acceptance suite: 20 / 20 passed.

### CER-2026-10-24-11: Phase 6.1 Dubbing Delivery, Cloud AI Excision, and Phase 7.0 Final System Lock
- **Work-Item ID:** `C-10` & `C-11` (Phase 6.1 / `CAP-001` and Phase 7.0 / End-to-End System Lock)
- **Alembic Head:** `c3d4e5f6a7b8`
- **Scope & Delivery:**
  1. *Multi-Language Dubbing Pipeline & UI Integration (`CAP-001`):* Delivered Celery dubbing task wiring, language catalog (`GET /api/dubbing/languages`), clip dubbing querying (`GET /api/dubbing/clip/{clip_id}`), parameter validation (`POST /api/dubbing/clip/{clip_id}`), voice clone authorization guard (403), neural fallback, timing-fit boundary enforcement (stretching speech up to 1.3x before failing closed), task claim idempotency, dual visual fallback, empty transcript handling, typed client methods in `frontend/lib/api.ts`, and interactive Dubbing tab in Clip Preview Modal.
  2. *Cloud AI Migration & Ollama Removal:* Purged all Ollama packages, endpoints, configuration keys, router calls, diagnostics checks, and UI settings in favor of high-throughput Cloud AI providers (OpenRouter, Groq Cloud Audio, Nvidia NIM) with free cloud model presets.
  3. *Phase 7.0 End-to-End System Lock:* Executed comprehensive multi-suite regression gate covering all 10 Logic Domains (L1–L10). Verified zero caption/subtitle burn-in, shorts duration cap [15.0, 30.0]s, single-destination YouTube separation, and `is_test=True` isolation.
- **Evidence:**
  - `backend/tests/test_c10_dubbing_pipeline.py`: 17 / 17 passed (100%).
  - `backend/tests/test_c09_settings_persistence.py`: 15 / 15 passed (100%).
  - Canonical 10-suite regression gate: 150 / 150 passed in 26.82s.
  - Full system regression tests: 270 / 270 passed across all test suites without failure.
  - `npx tsc --noEmit`: 0 errors.
  - `npm run build`: Compiled successfully, 11 / 11 static routes prerendered cleanly.
  - 6/6 Docker containers healthy (Postgres 5433, Redis 6379, Backend 8000, Worker, Beat, Flower 5555).
- **Freeze Status:** All 10 Domains (L1–L10) confirmed intact, verified, and **FROZEN**. Total active test suite: **270 / 270 passed**.

### CER-2026-10-25-12: Complete Ollama Configuration Excision & Container Environment Purge
- **Affected Domain:** L1 — Runtime, configuration, security foundations
- **Protected Files Affected:** `docker-compose.yml` (lines 52 & 84)
- **Baseline Commit:** `0ba85ff`
- **Operational Target:** `clipforge_backend` and `clipforge_worker` container environments
- **Rationale & Mandate:**
  Fulfill explicit project mandate to permanently excise every active Ollama integration and dependency across ClipForge. Removes legacy `OLLAMA_BASE_URL` environment variables from `docker-compose.yml` and purges them from running containers during a verified idle maintenance boundary.
- **Scope of Modification:**
  - `docker-compose.yml`: Removed `- OLLAMA_BASE_URL=http://host.docker.internal:11434` from `backend` (line 52) and `worker` (line 84).
  - Retained generic `extra_hosts: host.docker.internal:host-gateway` to support general host debugging and developer tooling without Ollama coupling.
  - Zero changes to database schemas, migrations, Celery broker configuration, or storage paths.
- **Operational Impact:**
  - Brief 2–5 second restart boundary for stateless backend and worker services; zero impact on PostgreSQL (5433), Redis (6379), or persistent volumes.
  - Purges legacy environment variables from runtime processes.
- **Failure Recovery & Rollback Guidance:**
  - Diagnosed strictly against container logs, configuration syntax, and runtime dependency health.
  - In the event of a container startup failure, recovery must diagnose the underlying defect while strictly preserving the intended Cloud AI architecture; under no circumstances should Ollama environment variables or dependencies be restored as routine recovery.
  - Non-destructive rollback, if ever mandated, is restricted strictly to reverting specific code edits attributable to this task, leaving operational database schemas and persistent volumes completely untouched.
- **Verification Evidence:**
  - `docker exec clipforge_backend env` and `clipforge_worker env` confirm 0 matches for `OLLAMA`.
  - Core health endpoint `curl http://localhost:8000/api/health` returns HTTP 200.
  - Settings persistence test suite passes: 15/15 in `test_c09_settings_persistence.py`.
- **Freeze Status:** Domain L1 re-frozen and verified.

### CER-2026-11-05-13: Defect Repair Programme, Concurrency Gate & Queue Isolation Closure
- **Affected Domains:** L1, L2, L5, L6, L7, L9, L10
- **Scope of Modification:**
  - `DEF-API-01`: Authority hardening in `backend/services/downloader.py` (`urlsplit`, userinfo rejection, port validation, query param ordering, video ID format validation). Verified in `test_youtube_url_validation.py` (15/15).
  - `DEF-API-02`: Channel Automation scoring mode parity (`Literal["ai"]`, HTTP 422 on heuristic, 0 UI occurrences). Verified in `test_def_api_02_scoring_mode_parity.py` (1/1).
  - `DEF-OPS-01`: Alembic migration `e6f7a8b9c0d1` verified; `clips.privacy` default updated to `'private'`. Pre-migration dump verified (`SHA-256: 2ACBCD70...`) with isolated restore rehearsal.
  - `DEF-UI-01`: Numeric settings falsy-zero coercion elimination (`settingsValidation.ts` rejecting 0, negatives, floats). Verified in `def_ui_01_numeric_settings.test.mjs` (12/12 runner).
  - `DEF-A11Y-01 / 02`: Modal dialog ARIA semantics and focus trap lifecycle (`useFocusTrap.ts`). Verified in Chromium real browser.
  - `DEF-A11Y-03 / 04`: ScoreRing `role="meter"` and URL input alert semantics (`role="alert"`). Verified in Chromium real browser.
  - `DEF-MEDIA-01`: MP4 faststart streaming optimization (`-movflags +faststart`) applied across all 11 FFmpeg command paths; binary inspection proved `moov` precedes `mdat`. Verified in `test_def_media_01_faststart.py` (8/8) and `test_live_mp4_pipelines_faststart.py` (5/5).
  - `DEF-MEDIA-02`: Production threshold `17.5` frozen under Domain L7 rules; synthetic fixture constraints documented.
  - **5-Video Concurrency Limit**: Created `backend/services/queue_manager.py` with `MAX_CONCURRENT_MANUAL_JOBS = 5`, automated FIFO queue drain, and UI queue position badges. Verified in `test_manual_video_concurrency_gate.py` (6/6).
  - **AI Creative Suite & Dubbing Path**: Repaired relative output path resolution in `backend/tasks/dubbing_tasks.py` and fixture status in `backend/tests/test_ai_enhancements_repair.py`. Verified in `test_ai_enhancements_repair.py` (16/16).
  - **Batch Ingestion Idempotency**: Preserved duplicate items with status `"already_processing"` in `backend/api/routes/channels.py`. Verified in `test_automation_repairs.py` (7/7).
- **Verification Evidence:**
  - Target runtime test battery (`clipforge-backend:latest`, Python 3.11.16): **58 / 58 PASSED** in 38.67s.
  - Frontend test suite (`npm test`): **135 / 135 PASSED** in 427ms.
  - TypeScript compiler (`npx tsc --noEmit`): **0 errors**.
  - All 6 Docker services healthy; 0 live unmocked external publishing operations executed.
- **Freeze Status:** All 10 Domains (L1–L10) re-verified and **FROZEN**.



