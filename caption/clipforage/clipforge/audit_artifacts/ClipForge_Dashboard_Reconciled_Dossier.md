# ClipForge — Dashboard (`/`) Reconciled Component & Endpoint Dossier

**Route:** `http://localhost:3000/`  
**Frontend Component:** `frontend/app/page.tsx`  
**Subcomponents:** `frontend/components/ProcessVideoModal.tsx`, `frontend/components/LayoutThumbnailSelector.tsx`  
**Date of Reconciliation:** 2026-10-26  
**Auditor:** Antigravity Autonomous Coding Agent  
**Reconciliation Status:** **RECONCILED & CORRECTED** (Authoritative source: active codebase)

---

## 1. Reconciled Endpoint Inventory

The following table reflects the **exact, verified backend routes and frontend callers** in the current repository. Superseded or misnamed route identifiers from earlier draft reports (`POST /api/process`, `POST /api/jobs/{id}/cancel`, `WS /ws/progress`) have been corrected to match the actual code contracts.

| Endpoint / Action | Method | Actual Backend Route | Backend Handler | Frontend Function / Caller | Payload / Contract | Verification Level |
|---|---|---|---|---|---|---|
| **System Health Check** | `GET` | `/api/health` | `backend.main:health` | N/A (System Diagnostics) | None -> `{ status, components, version, app }` | Level 4 (Probed live HTTP 200) |
| **Dashboard Metrics** | `GET` | `/api/stats` | `backend.main:stats` | `getStats()` (`api.ts:16`) | None -> `{ total_videos, total_clips, published_clips, active_channels }` | Level 4 (Probed live HTTP 200) |
| **Active Jobs Queue** | `GET` | `/api/jobs/active` | `backend.api.routes.jobs:list_active_jobs` | `getActiveJobs()` (`api.ts:433`) | None -> `Job[]` (non-terminal jobs, newest first) | Level 4 (Probed live HTTP 200) |
| **Job History Queue** | `GET` | `/api/jobs/history` | `backend.api.routes.jobs:list_job_history` | `getJobHistory(limit)` (`api.ts:434`) | `?limit=50` -> `Job[]` (terminal jobs: completed, failed, cancelled) | Level 4 (Probed live HTTP 200) |
| **Queue Health Stats** | `GET` | `/api/jobs/stats` | `backend.api.routes.jobs:get_job_stats` | `getQueueStats(includeTest)` (`api.ts:436`) | `?include_test=false` -> `{ queue, last_failure }` | Level 4 (Probed live HTTP 200) |
| **Single Job Details** | `GET` | `/api/jobs/{job_id}` | `backend.api.routes.jobs:get_job` | `getJob(id)` (`api.ts:428`) | Path param `job_id` -> `Job` object | Level 3 (Covered by test fixtures) |
| **Cancel Active Job** | `DELETE` | `/api/jobs/{job_id}` | `backend.api.routes.jobs:cancel_job` | `cancelJob(id)` (`api.ts:435`) | Path param `job_id` -> `{ message, job_id, status }` | Level 3 (Covered by unit & Celery revoke tests) |
| **Retry Failed Job** | `POST` | `/api/jobs/{job_id}/retry` | `backend.api.routes.jobs:retry_failed_job` | `retryJob(id)` (`api.ts:438`) | Path param `job_id` -> `{ status, job_id, new_celery_task_id }` | Level 3 (Covered by retry tests) |
| **Submit YouTube URL** | `POST` | `/api/videos/url` | `backend.api.routes.videos:process_youtube_url` | `submitYouTubeUrl(...)` (`api.ts:40`) | Form-Data: `url`, `num_clips`, `reframe_mode`, `clip_mode`, etc. -> `{ job_id, message, url }` | Level 3 (Covered by orchestration tests) |
| **Submit Batch URLs** | `POST` | `/api/videos/batch` | `backend.api.routes.videos:process_youtube_urls_batch` | `submitBatchYouTubeUrls(...)` (`api.ts:140`) | JSON: `{ urls: string[], clips_count, ... }` -> `{ status, total_submitted, jobs }` | Level 3 (Covered by batch tests) |
| **Upload Video File** | `POST` | `/api/videos/upload` | `backend.api.routes.videos:upload_video_file` | `uploadVideoFile(...)` (`api.ts:95`) | Multi-part file + form options -> `{ job_id, message }` | Level 3 (Covered by upload tests) |
| **Real-Time Job Telemetry** | `WS` | `/api/jobs/ws/{job_id}` | `backend.api.routes.jobs:job_status_ws` | `new WebSocket(...)` (`page.tsx:760`) | WebSocket connection per active `job_id`; pushes status every 1.0s until terminal | Level 3 (Covered by WebSocket tests) |

---

## 2. Reconciled Interactive Controls Catalog (46 Controls)

- **Input Section:** `CTRL-DASH-001` (URL input), `CTRL-DASH-002` (Paste button), `CTRL-DASH-003` (Clear button).
- **Configuration Controls:** `CTRL-DASH-004` (Target duration: 15s/30s/60s/Auto), `CTRL-DASH-005` (Mode toggle: AI Highlights vs Equal Split), `CTRL-DASH-006` (Equal split target segment duration), `CTRL-DASH-007` (Safety clip count cap).
- **Layout Presets (`LayoutThumbnailSelector`):** `CTRL-DASH-008` (Center Crop, Fill Blur, Split Screen, Multi-Split, Stacked 16:9, Creative Transform).
- **AI Enhancement Toggles:** `CTRL-DASH-009` (Hook Overlay), `CTRL-DASH-010` (B-Roll Cutaway), `CTRL-DASH-011` (SFX Placement), `CTRL-DASH-012` (Dubbing toggle), `CTRL-DASH-013` (Dubbing language selector), `CTRL-DASH-014` (Auto-SFX toggle).
- **Submission & Progress:** `CTRL-DASH-015` (Start Clipping button triggering `/api/videos/url`), `CTRL-DASH-016` to `025` (Real-time progress bar, stage indicator, WebSocket stream to `/api/jobs/ws/{job_id}`, dynamic fallback polling).
- **Job History Table & Actions:** `CTRL-DASH-026` to `046` (Status tabs: All, Active, Completed, Failed; search filter; IST timestamp format; Cancel button calling `DELETE /api/jobs/{id}`; Retry button calling `POST /api/jobs/{id}/retry`).

---

## 3. Reconciled Test Evidence

- **Tests Covering Dashboard Modules:**
  - `test_job_cancellation_and_aggregation.py`: **3 unique tests** passed.
  - `test_job_state_queue_and_cancellation_repair.py`: **5 unique tests** passed.
  - `test_equal_splits.py`: **13 unique tests** passed.
  - `test_layout_engine.py`: **7 unique tests** passed.
- **Total Unique Dashboard Tests:** **28 unique test cases** across 4 modules (100% passing).
- *Discrepancy Note:* Earlier claims of "30/30" or "33" in historical notes stemmed from aggregating repeated runs or including auxiliary test suites. The authoritative count of unique test cases in these 4 modules is 28.
