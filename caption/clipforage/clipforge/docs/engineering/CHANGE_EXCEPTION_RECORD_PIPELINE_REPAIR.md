# Frozen Logic Change-Exception Report & Defect Closure

**Standard:** `ANTIGRAVITY_CLIPFORGE_FREEZE_RULES.md` (Section 4)  
**Ledger Reference:** `docs/engineering/LOGIC_FREEZE_LEDGER.md`  
**Date:** 2026-10-13  
**Status:** `RESOLVED & RE-FROZEN`  
**Execution Context:** Local Windows Docker / Next.js / Celery Runtime

---

## 1. Scope & Frozen Domains Affected

This change-exception addresses two targeted defects identified in the pipeline restoration and automation selection workflow:

1. **Defect 1 (L7 - Internal Analysis)**: Missing `os` import in candidate scoring task.
2. **Defect 2 (L8, L9, L10 - Automation Selection & Channel Contract)**: Incomplete propagation of `channel_id` and `publish_destination_id` from UI selection through video intake to clip generation, alongside stale UI selection retention across channel boundaries.

### Protected Files & Symbols Modified

| Domain | File Path | Symbols / Contracts | Modification Type |
|---|---|---|---|
| **L7** | `backend/tasks/analysis_tasks.py` | `scoring_task`, `ai_score_candidates` | Bugfix (`import os`) |
| **L8** | `backend/tasks/clip_tasks.py` | `create_clip_record`, destination inheritance | Data contract propagation |
| **L9** | `backend/api/routes/videos.py` | `submit_video_url`, `Job.config` payload | Optional parameter contract |
| **L9** | `backend/api/routes/channels.py` | `add_channel`, `get_channel_videos` | Destination binding & RSS listing |
| **L9** | `backend/api/routes/clips.py` | `list_clips` (`channel_id` filter) | Query filter implementation |
| **L9** | `backend/tasks/video_tasks.py` | `download_task` | `Video.channel_id` persistence |
| **L10** | `frontend/lib/api.ts` | `submitYouTubeUrl`, `listClips`, `getChannelRecentVideos` | Frontend API client contract |
| **L10** | `frontend/app/publish/page.tsx` | `handleDestinationChange`, `handleSelectClip` | Stale selection guard, URL/storage sync |
| **L10** | `frontend/app/automation/page.tsx` | `handleSelectVideo`, channel card activation | Visual state, stale clearance, URL/storage sync |
| **Tests**| `backend/tests/test_channel_video_selection_workflow.py` | 8 focused automated tests | Test fixture validation |

---

## 2. Defect 1: Missing `os` Import in `analysis_tasks.py`

### Root Cause
In `backend/tasks/analysis_tasks.py`, `scoring_task` evaluates environment variables (e.g. `os.getenv("SCORING_MODE")`, `os.getenv("GEMINI_API_KEY")`) when running in production scoring mode. Because `os` was omitted from the module-level imports, any execution reaching the production scoring branch raised:
```text
NameError: name 'os' is not defined
```

### Minimal Diff
```python
--- a/backend/tasks/analysis_tasks.py
+++ b/backend/tasks/analysis_tasks.py
@@ -13,6 +13,7 @@
 import json
 import logging
 import math
+import os
```

### Focused Test Evidence
Tested via `backend/tests/test_channel_video_selection_workflow.py`:
- `test_scoring_task_production_mode_without_nameerror`: **PASSED**
- `test_scoring_task_fallback_without_nameerror`: **PASSED**
- `test_scoring_task_equal_splits_mode`: **PASSED**

### Verified Runtime Behavior
Celery worker correctly processes analysis tasks in production mode, fallback mode, and equal-splits mode without `NameError`.

---

## 3. Defect 2: Automation & Publishing Selection Workflow & `channel_id` Contract

### Root Cause
1. **Contract Disconnect**: Channel identification (`channel_id`) and publishing targets (`publish_destination_id`) selected in the frontend were not accepted by `submitYouTubeUrl` / `POST /api/videos/url`, omitting them from `Job.config`. Consequently, `download_task` left `Video.channel_id` null, and generated clips did not inherit destination metadata.
2. **Stale UI Selections**:
   - In `frontend/app/publish/page.tsx`, switching the publishing destination dropdown left previously selected clips active even if they belonged to a different destination channel.
   - In `frontend/app/automation/page.tsx`, discovered videos from Channel A remained selected when collapsing Channel A and navigating Channel B.
   - Selections were lost on page refresh.

### Minimal Diffs & Changes
1. **`frontend/app/publish/page.tsx`**:
   - Added destination channel selector with `localStorage` and `?channel=` URL sync.
   - Added stale selection guard in `handleDestinationChange`: automatically unsets `selectedClip` and clears form state if the active clip belongs to a different destination channel.
   - Labeled and disabled incompatible clips in the dropdown selector.
   - Connected target destination badge to the mobile Short simulator preview.
2. **`frontend/app/automation/page.tsx`**:
   - Added explicit channel activation state (`Active Channel` badge, border accent).
   - Added video card selection (`✓ Selected for Pipeline`, glow border).
   - Added automatic clearance of stale video selections when switching active channels.
   - Persisted selection state to `localStorage` and URL parameters.
3. **`backend/api/routes/videos.py` & `backend/tasks/video_tasks.py`**:
   - Accepted optional `channel_id` and `publish_destination_id` in `submit_video_url` form-data.
   - Propagated fields into `Job.config`.
   - In `download_task`, persisted `channel_id` to `Video.channel_id`.
4. **`backend/tasks/clip_tasks.py`**:
   - Inherited `publish_destination_id` onto created `Clip` records from job configuration.
5. **`backend/api/routes/clips.py`**:
   - Implemented real database filtering: `GET /api/clips/?channel_id=<uuid>` filters clips strictly by the source video's channel.

### Focused Test Evidence
- **Backend Test Suite**: `py -3.12 -m pytest backend/tests/test_channel_video_selection_workflow.py -v` (8/8 passed in 12.70s):
  - `test_channel_model_and_requests_have_publish_destination_id`: **PASSED**
  - `test_scoring_task_fallback_without_nameerror`: **PASSED**
  - `test_clip_selection_inherits_publish_destination`: **PASSED**
  - `test_video_model_has_channel_id_field`: **PASSED**
  - `test_clip_model_has_publish_destination_id`: **PASSED**
  - `test_scoring_task_production_mode_without_nameerror`: **PASSED**
  - `test_scoring_task_equal_splits_mode`: **PASSED**
  - `test_channel_id_contract_and_clip_filtering_with_real_fixtures`: **PASSED**
- **Browser Automation Verification**:
  - Live session recorded to `automation_selection_test_1791874812593.webp`.
  - Confirmed: channel selection, video selection, refresh persistence, stale selection clearance on destination switch, and mock preview responsiveness.

---

## 4. Verification of Publishing Execution Harness (Mock vs Live)

### Forensic Findings
An audit of Celery task execution, service configuration, and PostgreSQL database records was conducted for the full orchestration run (Job `job_orch_329a077b`):
- `backend/core/config.py`: `PUBLISH_MODE` defaults to `"test"`.
- `backend/services/publisher.py`: `_mock_upload_short` is invoked when `PUBLISH_MODE == "test"`.
- PostgreSQL Database: All 4 generated clips contain mock video IDs:
  - `mock_56e64c39`
  - `mock_f87c6f6d`
  - `mock_8c6ab096`
  - `mock_820360c8`
- `PublishTarget` Table: **0 records**. No authenticated Google OAuth tokens existed for external upload.
- `PublishRecord` Table: **0 live upload records** from the test run.

### Critical Determination
**Live YouTube publishing was NOT invoked.** The recorded pipeline execution ran exclusively through the mock publishing provider. Test isolation is verified and protected against accidental external uploads.

---

## 5. Refreeze Status & Sign-off

- All identified defects are resolved.
- No existing tests were weakened.
- No database tables were dropped or modified out-of-band.
- All 10 focused workflow and cancellation tests pass cleanly.
- Logic domains L1–L10 are restored to **FROZEN** status.

---

## 6. CER-2026-10-13-02: Isolated Job Repair & Cancellation Handler (Rick Astley `dQw4w9WgXcQ`)

### Investigation Findings
- **Job ID:** `job_orch_05725a85`
- **Video ID:** `d26c5494-0e20-4fff-a51b-4490f0ba5d09`
- **Source URL:** `https://www.youtube.com/watch?v=dQw4w9WgXcQ`
- **Historical Context:** On 11 Oct 2026 at 10:42:23 IST, candidate generation and clip selection succeeded (progress 80%), creating 4 clip records. During downstream parallel processing in a Celery chord, 3 of 4 reframe tasks failed due to missing source media.
- **Root Cause of 80% Stall:** In Celery, when subtasks in a `chord` header raise an exception, Celery suppresses invocation of the chord callback (`job_completion_aggregation_task`). The error callback `handle_pipeline_failure_task` did not aggregate job status when `clip_id` was present, leaving the job indefinitely in `selecting` at 80%.
- **Root Cause of Cancellation Failure:** In `backend/api/routes/jobs.py`, `cancel_job` executed `await db.delete(job)`. Because `task_executions` contained rows with `ForeignKey("jobs.id")`, PostgreSQL raised `ForeignKeyViolationError`. The unhandled exception returned 500 without CORS headers, causing browser `TypeError: Failed to fetch`.

### Minimal Corrections
1. **`backend/api/routes/jobs.py` (`cancel_job`):**
   - Transitioned `Job.status = JobStatus.CANCELLED.value`, `current_step = "Cancelled"`, `error_message = "Cancelled by user"`.
   - Revoked active Celery tasks and running subtasks in `task_executions`.
   - Updated associated `Video.processing_status` if active to `cancelled`.
   - Preserved job and task execution audit records in PostgreSQL, returning HTTP 200 with `status: "cancelled"`.
2. **`backend/models/models.py` (`JobStatus`):**
   - Added `CANCELLED = "cancelled"` enum value.
3. **`backend/models/db_sync.py` & `backend/tasks/orchestration.py`:**
   - Protected cancelled jobs from stale callbacks: `update_job_sync` refuses to overwrite `'cancelled'`, and `job_completion_aggregation_task` skips cancelled jobs.
4. **`backend/tasks/clip_tasks.py`:**
   - Active worker tasks (`reframe_task`, `render_task`, `output_validation_task`, `publish_task`) perform cooperative cancellation checks on `job.status == "cancelled"` and abort immediately without producing outputs.
5. **`backend/models/database.py` (`cleanup_orphaned_jobs`):**
   - Included `JobStatus.CANCELLED.value` in terminal status list.

### Test & Runtime Evidence
- `test_job_cancellation_preserves_fk_and_transitions_state`: **PASSED**
- `test_cancelled_job_blocks_stale_callbacks_and_workers`: **PASSED**
- `test_handle_pipeline_failure_aggregates_terminal_job`: **PASSED**
- Real API call `DELETE /api/jobs/job_orch_05725a85` returned HTTP 200 with `status: "cancelled"`.
- `GET /api/jobs/active` returned `[]` (0 stuck jobs remaining).

---

## 7. CER-2026-10-13-03: Rick Astley Video Recovery & Media Durability Resolution

### Investigation & Root Cause of Missing Source Media
- **Target Video:** `d26c5494-0e20-4fff-a51b-4490f0ba5d09` (`https://www.youtube.com/watch?v=dQw4w9WgXcQ`)
- **Root Cause:** Analysis of storage test routines revealed that `scripts/test_storage_durability.py:L109-123` executed `backend.cleanup_storage.cleanup()` with mocked empty active job lists. Because `cleanup()` swept through `UPLOADS_DIR` removing any directory whose UUID was not in the mock list, the live upload directory `uploads/d26c5494-0e20-4fff-a51b-4490f0ba5d09/` was removed from disk while downstream tasks were queued.
- **Artifact Recovery:** An identical, uncorrupted copy of the source download was identified at `uploads/d2dc88c6-8145-4b04-b1b6-6372fdac5393/source.mp4` (SHA256: `104ef87331424ea2d1bfc2db4cfea0fa424d614eb54a19169b858e0b1440ee1e`, 11,829,048 bytes), matching the PostgreSQL `ArtifactRecord` exactly.
- **Source Restoration:** Restored to `uploads/d26c5494-0e20-4fff-a51b-4490f0ba5d09/source.mp4` via `storage_service.put` and verified existence inside both host and Docker container `/app/uploads/`.

### Clip Recovery & Verification
- **Preserved Completed Clip:** Clip 1 (`483a4b0f-bcb4-4feb-93a9-eecb377f5335`) had already completed rendering on Oct 11. Its artifacts (`final.mp4` - 17.8 MB and `thumb_a.jpg` - 79 KB) were verified intact on disk and in DB.
- **Recovered Failed Clips:** Clips 2, 3, 4 (`ef1bf3f1-f45a-4b25-95f3-f6314ca61d1a`, `55b47fad-0449-40da-ae9e-77e6937593ca`, `de9949d8-5303-4f16-90db-0f62e54da36c`) were individually reset to pending and processed through the isolated worker pipeline: `reframe_task -> render_task -> output_validation_task -> publish_task` (mock publish mode).
- **Physical Output Verification:**
  - Clip 1: `outputs/d26c5494-0e20-4fff-a51b-4490f0ba5d09/clips/483a4b0f-bcb4-4feb-93a9-eecb377f5335/final.mp4` (verified)
  - Clip 2: `outputs/d26c5494-0e20-4fff-a51b-4490f0ba5d09/clips/ef1bf3f1-f45a-4b25-95f3-f6314ca61d1a/final.mp4` (verified)
  - Clip 3: `outputs/d26c5494-0e20-4fff-a51b-4490f0ba5d09/clips/55b47fad-0449-40da-ae9e-77e6937593ca/final.mp4` (verified)
  - Clip 4: `outputs/d26c5494-0e20-4fff-a51b-4490f0ba5d09/clips/de9949d8-5303-4f16-90db-0f62e54da36c/final.mp4` (verified)
- **Database Status:** All 4 clips transitioned to `completed` in PostgreSQL, linked to completed recovery job `job_recov_d26c5494` (progress: 100%).

---

## 8. CER-2026-10-13-04: Publishing Destination Selector Alignment & Authorization Validation

### Inconsistency & Root Cause
1. **UI Wording Discrepancy:**
   - `frontend/app/publish/page.tsx:L494` presented `<option value="">Default Connected YouTube Channel</option>`.
   - `frontend/app/automation/page.tsx:L310` presented `<option value="">None (Select at publish time)</option>` and line 405 presented `<option value="">None (Unassigned)</option>`.
   - While both carried `value=""`, the publish UI framed it as defaulting to the connected channel, whereas automation framed it as leaving the destination unassigned.
2. **Silent Overwrite of Intentional None:**
   - In `backend/services/publisher.py` (`resolve_publish_destinations`), when a monitored channel had `publish_destination_id = None`, the resolver fell back to `Channel.is_default_destination == True`, silently overriding the user's deliberate choice to leave the destination unassigned until publish time.
3. **Missing Authorization Validation:**
   - Channel creation (`POST /api/channels/`), channel update (`PATCH /api/channels/{id}`), and immediate publishing (`POST /api/publish/publish-now`) did not validate whether the destination channel ID was an authorized publishing destination (`is_destination == True`).

### Minimal Corrections
1. **Frontend UI Alignment:**
   - Unified all unassigned selectors across `frontend/app/publish/page.tsx` and `frontend/app/automation/page.tsx` to:
     `<option value="">None (Select at publish time)</option>`.
   - Fixed `frontend/app/publish/page.tsx` clip selection to set `selectedDestinationId = ''` when a clip has no destination, instead of falling back to arbitrary local storage.
2. **Backend Destination Resolution (`backend/services/publisher.py`):**
   - Updated `resolve_publish_destinations`: if a source channel has `publish_destination_id = None` (and no `ChannelDestination` default rows exist), returns `[]` to preserve intentional `None (Select at publish time)` without silent fallback.
   - Supported single `publish_destination_id` in `job_config`.
3. **Destination Authorization Validation:**
   - `backend/api/routes/channels.py`: `add_channel` and `update_channel` reject nonexistent or non-destination channel IDs with HTTP 400.
   - `backend/api/routes/publish.py`: `publish_now` rejects nonexistent or non-destination channel IDs with HTTP 400.
   - `backend/api/routes/videos.py`: inherits `publish_destination_id` from monitored channel if not explicitly passed.

### Test Evidence
- `test_publish_destination_validation_and_unassigned_preservation`: **PASSED**
  - Confirmed rejection of non-destination and nonexistent channels with HTTP 400.
  - Confirmed `resolve_publish_destinations` preserves `[]` when `publish_destination_id = None`.
  - Confirmed `POST /api/publish/publish-now` rejects unauthorized destinations with HTTP 400.
- `npx tsc --noEmit`: **PASSED** (0 TypeScript errors).
- All 12 focused backend tests in `test_job_cancellation_and_aggregation.py` and `test_channel_video_selection_workflow.py`: **12/12 PASSED**.

