# Audit 18 — Test Inventory, Regression Coverage, and Safe Execution

**Audit Mode:** READ-ONLY Test Inventory, Regression Coverage, and Safe Execution Audit  
**Workspace:** `d:\automation video clips\clipforge`  
**Artifact File:** `audit_artifacts/clipforge_upload_studio_v1_8/18_test_coverage_results.md`  
**Execution Timestamp:** 2026-10-11  

---

## 1. Executive Summary

A forensic, two-pass test audit was conducted on ClipForge to inventory all automated tests, test scripts, and regression coverage; establish isolation and safety boundaries; and safely execute verified isolated tests without mutating production or application data.

### Double Verification Methodology
1. **Pass 1 (Pre-Execution Inventory & Isolation Inspection):**
   - Comprehensive inventory of test files across `frontend/test/`, `backend/tests/`, `tests/` (root), `scripts/`, `backend/scripts/`, and root verification scripts.
   - Fixture and configuration inspection to identify state-changing resources: live PostgreSQL database connections (`SyncSessionLocal`, `AsyncSessionLocal`), active Redis/Celery queue dispatch (`start_video_processing_task.delay()`, `apply_async()`), persistent disk mutations (`uploads/`, `outputs/`), and external YouTube API calls.
   - Strict safety segregation: only demonstrably isolated, side-effect-free unit/contract tests were authorized for execution.
2. **Pass 2 (Execution Results & Claimed vs. Actual Assertion Analysis):**
   - Safe execution of authorized test suites, capturing exact CLI commands, timings, outputs, and exit codes.
   - Rigorous assertion forensics: evaluating whether passing tests actually verify Upload Studio v1.8 production logic or merely assert against local test-file mocks, tautologies, or duplicated helpers.

### High-Level Execution Summary
- **Total Test Files Inventoried:** 27 files across frontend, backend, root, and scripts directories.
- **Tests Executed Safely:** 72 tests across 12 test files (10 frontend Node.js contract/validation tests + 62 backend/root pytest unit tests).
- **Tests Passed:** 71 tests (10 frontend + 61 backend/root).
- **Tests Failed:** 1 test (`tests/test_pipeline_config_fixes.py::TestParameterBugFix::test_publish_task_source_uses_privacy` — pre-existing assertion drift).
- **Tests Skipped for Safety:** 15 files / test suites (database mutators, Celery task dispatchers, filesystem wipers, live external API callers).

---

## 2. Phase A: Test Inventory & Isolation Classification

### 2.1 Complete Inventory & Safety Classification Matrix

| Directory / Location | File Name | Test Category | State-Changing Resources | Isolation Status | Action Taken | Rationale |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `frontend/test/` | [api_contract.test.mjs](file:///d:/automation%20video%20clips/clipforge/frontend/test/api_contract.test.mjs) | Frontend Contract | None (In-memory strings & FormData) | **Fully Isolated** | **Executed** | Pure in-memory unit assertions using Node test runner. |
| `frontend/test/` | [routes.test.mjs](file:///d:/automation%20video%20clips/clipforge/frontend/test/routes.test.mjs) | Route Integrity | None (Read-only `fs.existsSync`) | **Fully Isolated** | **Executed** | Read-only static page verification against `frontend/app/`. |
| `frontend/test/` | [validation.test.mjs](file:///d:/automation%20video%20clips/clipforge/frontend/test/validation.test.mjs) | Frontend Validation | None (In-memory regex & date math) | **Fully Isolated** | **Executed** | Pure in-memory unit logic. |
| `frontend/` | [test_forensics.js](file:///d:/automation%20video%20clips/clipforge/frontend/test_forensics.js) | E2E Browser / WS | Localhost:3000, writes `forensics_report.md` | **Un-isolated** | **Inspected Only** | Requires running Next.js dev server on port 3000; mutates disk. |
| `backend/tests/` | [test_equal_splits.py](file:///d:/automation%20video%20clips/clipforge/backend/tests/test_equal_splits.py) | Backend Unit (Math) | None (Pure math segmentation) | **Fully Isolated** | **Executed** | Pure mathematical division of video segments. |
| `backend/tests/` | [test_layout_engine.py](file:///d:/automation%20video%20clips/clipforge/backend/tests/test_layout_engine.py) | Backend Unit (Layout) | None (In-memory geometry) | **Fully Isolated** | **Executed** | Pure in-memory layout plan resolution. |
| `backend/tests/` | [test_optimizer.py](file:///d:/automation%20video%20clips/clipforge/backend/tests/test_optimizer.py) | Backend Unit (Prompt) | None (Patched `ab_testing_engine`) | **Fully Isolated** | **Executed** | Mock-isolated prompt string construction test. |
| `backend/tests/` | [test_pipeline_config_fixes.py](file:///d:/automation%20video%20clips/clipforge/backend/tests/test_pipeline_config_fixes.py) | Backend Unit (Config) | None (Python mocks & signature inspect) | **Fully Isolated** | **Executed** | Signature inspection and mock parameter parsing. |
| `backend/tests/` | [test_tracker.py](file:///d:/automation%20video%20clips/clipforge/backend/tests/test_tracker.py) | Backend Unit (Math) | None (Pure math formulas) | **Fully Isolated** | **Executed** | Mathematical formula validation for ViewScore. |
| `backend/tests/` | [test_youtube_reconciliation.py](file:///d:/automation%20video%20clips/clipforge/backend/tests/test_youtube_reconciliation.py) | Backend Unit (Mock) | None (Local simulator) | **Fully Isolated** | **Executed** | In-memory simulator testing status mapping logic. |
| `backend/tests/` | [test_multi_destination_publishing.py](file:///d:/automation%20video%20clips/clipforge/backend/tests/test_multi_destination_publishing.py) | Integration (Publish) | **Live PostgreSQL (`localhost:5433`)** | **Un-isolated** | **Skipped (Safety)** | Directly calls `SyncSessionLocal()`, creating & deleting DB rows. |
| `backend/tests/` | [test_publish_concurrency.py](file:///d:/automation%20video%20clips/clipforge/backend/tests/test_publish_concurrency.py) | Concurrency / Locks | **Live PostgreSQL (`localhost:5433`)** | **Un-isolated** | **Skipped (Safety)** | Inserts/deletes `TaskExecution`, `Clip`, `Job` rows on live database. |
| `backend/tests/` | [test_storage_durability.py](file:///d:/automation%20video%20clips/clipforge/backend/tests/test_storage_durability.py) | Storage Durability | **Storage Directories (`uploads/`, `outputs/`)** | **Un-isolated** | **Skipped (Safety)** | Writes files to `settings.UPLOAD_DIR`, triggers `cleanup()`. |
| `backend/tests/` | [test_orchestration.py](file:///d:/automation%20video%20clips/clipforge/backend/tests/test_orchestration.py) | Pipeline Integration | **Live DB, Live Celery Worker, YouTube DL** | **Un-isolated** | **Skipped (Safety)** | Creates Job in live DB, dispatches live Celery task, polls 300s. |
| `tests/` (root) | [test_celery_orchestration.py](file:///d:/automation%20video%20clips/clipforge/tests/test_celery_orchestration.py) | Celery Unit (Mock) | None (Patched `SyncSessionLocal`) | **Fully Isolated** | **Executed** | Mock-isolated task completion aggregation & status transitions. |
| `tests/` (root) | [test_pipeline_config_fixes.py](file:///d:/automation%20video%20clips/clipforge/tests/test_pipeline_config_fixes.py) | Backend Unit (Config) | None (Python mocks & signature inspect) | **Fully Isolated** | **Executed** | Root copy of config tests (discovered 1 assertion drift failure). |
| `tests/` (root) | [test_tracker.py](file:///d:/automation%20video%20clips/clipforge/tests/test_tracker.py) | Reframe Unit (Math) | None (Pure coordinate smoothing) | **Fully Isolated** | **Executed** | Mathematical smoothing and dead-zone calculations. |
| `backend/` | [test_boundaries.py](file:///d:/automation%20video%20clips/clipforge/backend/test_boundaries.py) | Manual Script | None | **Ad-hoc Script** | **Inspected Only** | Standalone script with print statements; zero assertions. |
| `backend/` | [test_concurrency.py](file:///d:/automation%20video%20clips/clipforge/backend/test_concurrency.py) | Manual Script | **Live DB, Live Celery Queue (`celery`)** | **Un-isolated** | **Skipped (Safety)** | Dispatches 2 concurrent tasks to active Celery worker. |
| `backend/` | [test_face_crop.py](file:///d:/automation%20video%20clips/clipforge/backend/test_face_crop.py) | Manual Script | Hardcoded `/app/outputs/.../raw.mp4` | **Un-isolated** | **Skipped (Safety)** | Hardcoded Linux container path; requires container volume video. |
| `backend/` | [test_reframer.py](file:///d:/automation%20video%20clips/clipforge/backend/test_reframer.py) | Manual Script | Hardcoded `/app/uploads/dummy_landscape.mp4` | **Un-isolated** | **Skipped (Safety)** | Invokes ffmpeg rendering on container path. |
| `backend/` | [test_sendcmd_crop.py](file:///d:/automation%20video%20clips/clipforge/backend/test_sendcmd_crop.py) | Manual Script | Hardcoded `/app/outputs/test_cmd.txt` | **Un-isolated** | **Skipped (Safety)** | Executes ffmpeg subprocess writing MP4 to `/app/outputs/`. |
| `backend/` | [test_worker_crash.py](file:///d:/automation%20video%20clips/clipforge/backend/test_worker_crash.py) | Manual Script | **Live DB, Live Celery Worker** | **Un-isolated** | **Skipped (Safety)** | Inserts Job in live DB, triggers task to test worker crash. |
| `backend/` | [verify_phase15.py](file:///d:/automation%20video%20clips/clipforge/backend/verify_phase15.py) | Verification Script | **Live DB, Creates `dummy_phase15_*.mp4`** | **Un-isolated** | **Skipped (Safety)** | Generates temporary MP4 files via ffmpeg and mutates live DB. |
| `backend/` | [verify_schema.py](file:///d:/automation%20video%20clips/clipforge/backend/verify_schema.py) | Schema Verification | Live PostgreSQL connection (`sync_engine`) | **Read-only DB** | **Inspected Only** | Checks table metadata; skipped execution to maintain isolation. |
| `scripts/` | [test_cleanup_separation.py](file:///d:/automation%20video%20clips/clipforge/scripts/test_cleanup_separation.py) | Cleanup Script | **Live DB, Writes & Deletes Files** | **Un-isolated** | **Skipped (Safety)** | Directly invokes `cleanup()`, mutating database and filesystem. |
| Root | [test_6_cleanup.py](file:///d:/automation%20video%20clips/clipforge/test_6_cleanup.py) | Cleanup Script | **Live DB, Deletes Low-Score Clips** | **Un-isolated** | **Skipped (Safety)** | Runs `execute_cleanup(db=db)`, deleting live clips with score < 5.0. |

---

## 3. Phase B: Safe Execution Log & Exact Results

### 3.1 Frontend Suite Execution
- **Command:** `npm test`  
- **Working Directory:** `d:\automation video clips\clipforge\frontend`  
- **Environment:** Node.js v24.14.0  
- **Exit Code:** `0`  
- **Execution Duration:** 113.3 ms  
- **Full Execution Log:**
```text
> frontend@0.1.0 test
> node --test test/**/*.test.mjs

✔ API Contract: Base URL falls back to localhost:8000 when unset (0.7877ms)
✔ API Contract: Download and Thumbnail URLs construct canonical endpoint paths (0.3624ms)
✔ API Contract: Clips query string builder serializes only defined filter params (0.397ms)
✔ API Contract: Upload form data maps options accurately to backend fields (23.3447ms)
✔ Route Integrity: All Sidebar routes exist as valid Next.js app pages (5.7299ms)
✔ Dead Route Prevention: No page navigates to nonexistent /jobs route (1.9732ms)
✔ Validation: YouTube URL extraction across standard URL formats (1.4704ms)
✔ Validation: Shorts duration boundary strictly enforces < 30.0s (0.2738ms)
✔ Validation: Schedule date must reject past dates and accept future ISO strings (0.5772ms)
✔ Validation: Publish tags parsing splits and trims comma-separated input (0.7832ms)
ℹ tests 10
ℹ suites 0
ℹ pass 10
ℹ fail 0
ℹ cancelled 0
ℹ skipped 0
ℹ todo 0
ℹ duration_ms 113.2971
```

---

### 3.2 Backend Isolated Suite Execution (`backend/tests/`)
- **Command:** `python -m pytest backend/tests/test_equal_splits.py backend/tests/test_layout_engine.py backend/tests/test_optimizer.py backend/tests/test_pipeline_config_fixes.py backend/tests/test_tracker.py backend/tests/test_youtube_reconciliation.py -v`  
- **Working Directory:** `d:\automation video clips\clipforge`  
- **Environment:** Python 3.12.10, pytest 9.1.1, pluggy 1.6.0  
- **Exit Code:** `0`  
- **Execution Duration:** 3.38 s  
- **Full Execution Log:**
```text
============================= test session starts =============================
platform win32 -- Python 3.12.10, pytest-9.1.1, pluggy-1.6.0
rootdir: D:\automation video clips\clipforge
plugins: anyio-4.13.0
collecting ... collected 35 items

backend/tests/test_equal_splits.py::test_source_shorter_than_target_duration PASSED [  2%]
backend/tests/test_equal_splits.py::test_fixed_target_duration_remainder_omitted PASSED [  5%]
backend/tests/test_equal_splits.py::test_safety_cap_max_clips PASSED     [  8%]
backend/tests/test_equal_splits.py::test_absent_target_duration_divides_evenly PASSED [ 11%]
backend/tests/test_equal_splits.py::test_invalid_duration_raises PASSED  [ 14%]
backend/tests/test_layout_engine.py::test_resolve_plan_center_crop PASSED [ 17%]
backend/tests/test_layout_engine.py::test_resolve_plan_blur_background PASSED [ 20%]
backend/tests/test_layout_engine.py::test_resolve_plan_multi_split PASSED [ 22%]
backend/tests/test_layout_engine.py::test_resolve_plan_creative_transform PASSED [ 25%]
backend/tests/test_optimizer.py::test_build_reoptimize_prompt_formatting PASSED [ 28%]
backend/tests/test_pipeline_config_fixes.py::TestDynamicClipCount::test_clips_count_1 PASSED [ 31%]
backend/tests/test_pipeline_config_fixes.py::TestDynamicClipCount::test_clips_count_3 PASSED [ 34%]
backend/tests/test_pipeline_config_fixes.py::TestDynamicClipCount::test_clips_count_default_when_no_config PASSED [ 37%]
backend/tests/test_pipeline_config_fixes.py::TestDynamicClipCount::test_clips_count_invalid_negative PASSED [ 40%]
backend/tests/test_pipeline_config_fixes.py::TestDynamicClipCount::test_clips_count_invalid_string PASSED [ 42%]
backend/tests/test_pipeline_config_fixes.py::TestDynamicClipCount::test_duration_config_overrides_defaults PASSED [ 45%]
backend/tests/test_pipeline_config_fixes.py::TestDynamicClipCount::test_duration_max_less_than_min_fallback PASSED [ 48%]
backend/tests/test_channel_scoped_publishing::test_get_youtube_client_channel_token_path PASSED [ 51%]
backend/tests/test_channel_scoped_publishing::test_no_channel_uses_default_token PASSED [ 54%]
backend/tests/test_channel_scoped_publishing::test_upload_short_accepts_channel_id PASSED [ 57%]
backend/tests/test_channel_scoped_publishing::test_check_external_state_accepts_channel_id PASSED [ 60%]
backend/tests/test_channel_scoped_publishing::test_channel_mismatch_detected PASSED [ 62%]
backend/tests/test_clips_generated_counter::test_save_clip_record_accepts_run_identity PASSED [ 65%]
backend/tests/test_clips_generated_counter::test_save_clip_record_accepts_metadata_fields PASSED [ 68%]
backend/tests/test_clips_generated_counter::test_counter_increment_by_actual_count PASSED [ 71%]
backend/tests/test_clips_generated_counter::test_idempotent_rerun_no_double_count PASSED [ 74%]
backend/tests/test_parameter_bug_fix::test_upload_short_has_privacy_not_privacy_status PASSED [ 77%]
backend/tests/test_parameter_bug_fix::test_publish_task_source_uses_privacy PASSED [ 80%]
backend/tests/test_tracker.py::test_calculate_view_score_zero_views PASSED [ 82%]
backend/tests/test_tracker.py::test_calculate_view_score_high_engagement PASSED [ 85%]
backend/tests/test_tracker.py::test_calculate_view_score_low_engagement PASSED [ 88%]
backend/tests/test_tracker.py::test_calculate_view_score_negative_views PASSED [ 91%]
backend/tests/test_youtube_reconciliation.py::test_external_state_found PASSED [ 94%]
backend/tests/test_youtube_reconciliation.py::test_external_state_not_found PASSED [ 97%]
backend/tests/test_youtube_reconciliation.py::test_external_state_manual_review PASSED [100%]

============================== warnings summary ===============================
backend\models\layout.py:100: PydanticDeprecatedSince20: `min_items` is deprecated and will be removed, use `min_length` instead.
backend\core\config.py:5: PydanticDeprecatedSince20: Support for class-based `config` is deprecated, use ConfigDict instead.
google\api_core\_python_package_support.py:206: FutureWarning: Package google.api_core depends on grpcio (version < 1.83.0 PQC deprecation).
======================= 35 passed, 3 warnings in 3.38s ========================
```

---

### 3.3 Root Isolated Suite Execution (`tests/`)
- **Command:** `python -m pytest tests/test_celery_orchestration.py tests/test_tracker.py tests/test_pipeline_config_fixes.py -v`  
- **Working Directory:** `d:\automation video clips\clipforge`  
- **Exit Code:** `1` (1 failure, 26 passed)  
- **Execution Duration:** 3.66 s  
- **Failure Traceback:**
```text
================================== FAILURES ===================================
__________ TestParameterBugFix.test_publish_task_source_uses_privacy __________

self = <test_pipeline_config_fixes.TestParameterBugFix object at 0x0000025A7FE8B260>

    def test_publish_task_source_uses_privacy(self):
        import inspect
        import backend.tasks.clip_tasks as ct
        source = inspect.getsource(ct.publish_task)
        assert "privacy_status=" not in source
>       assert 'privacy="private"' in source
E       assert 'privacy="private"' in '@celery_app.task(\n    bind=True,\n    name="publish_clip",\n    **DEFAULT_RETRY_KWARGS,\n)\ndef publish_task(self, result: dict):\n...
...
                    yt_id = upload_short(
                        video_path=temp_path,
                        title=title,
                        description=description,
                        tags=tags,
                        privacy=target_privacy,
                        made_for_kids=target_kids,
                        channel_id=dest_yt_channel_id,
                        idempotency_key=idemp_key
                    )
...
tests\test_pipeline_config_fixes.py:248: AssertionError
=========================== short test summary info ===========================
FAILED tests/test_pipeline_config_fixes.py::TestParameterBugFix::test_publish_task_source_uses_privacy
================== 1 failed, 26 passed, 3 warnings in 3.66s ===================
```

#### Forensic Diagnosis of Root Failure
- **Failure Classification:** **Pre-existing test assertion drift**.
- **Evidence:**  
  In Upload Studio v1.8, the single hardcoded publication path was refactored to support destination-specific privacy (`target_privacy = target.privacy or "public"`), resulting in `upload_short(..., privacy=target_privacy, ...)`.  
  - The updated test copy in `backend/tests/test_pipeline_config_fixes.py:L248` tests: `assert "privacy=" in source` (**PASSED**).  
  - The duplicate root copy in `tests/test_pipeline_config_fixes.py:L248` was never synchronized and still asserts: `assert 'privacy="private"' in source` (**FAILED**).  
  As instructed, no source or test files were modified to force this test to pass.

---

### 3.4 Pytest Module Namespace Collision During Combined Execution
When attempting to run the combined backend and root suites in a single pytest command without import flags:
```text
python -m pytest backend/tests/... tests/...
```
Pytest halted collection with an `import file mismatch` error:
```text
ERROR collecting tests/test_pipeline_config_fixes.py
import file mismatch:
imported module 'test_pipeline_config_fixes' has this __file__ attribute:
  D:\automation video clips\clipforge\backend\tests\test_pipeline_config_fixes.py
which is not the same as the test file we want to collect:
  D:\automation video clips\clipforge\tests\test_pipeline_config_fixes.py
```
- **Cause:** Duplicate file basenames in `backend/tests/` and `tests/` without package namespace isolation.  
- **Resolution:** Tested with `--import-mode=importlib`, which successfully loaded and executed both copies (61 passed, 1 failed in 3.86s).

---

## 4. Pass 2: Claimed Coverage vs. Assertion Reality

A critical mandate of Audit 18 is to verify whether existing tests actually validate application guarantees or merely test trivial mocks, tautologies, or test-local helper functions.

### 4.1 Tautological & Self-Testing Defects Identified

#### 1. Self-Testing YouTube Reconciliation Simulator
- **File:** [backend/tests/test_youtube_reconciliation.py](file:///d:/automation%20video%20clips/clipforge/backend/tests/test_youtube_reconciliation.py)  
- **Claimed Scope:** Reconciles YouTube video ID and manual review status on publishing recovery.  
- **Forensic Reality:**  
  The test **does not import or execute any production code**. It defines a local helper function directly in the test file:
  ```python
  def simulate_publish_task_logic(external_id_result):
      ...
  ```
  The test functions (`test_external_state_found`, `test_external_state_not_found`, `test_external_state_manual_review`) only assert against this 15-line test-local simulator function.  
  - **Verdict:** **Zero production coverage**. If `backend/tasks/clip_tasks.py` or `backend/services/publisher.py` changes or breaks, this test will continue to pass.

#### 2. Mock Integer Addition Tautology
- **File:** [backend/tests/test_pipeline_config_fixes.py:L214-L222](file:///d:/automation%20video%20clips/clipforge/backend/tests/test_pipeline_config_fixes.py#L214-L222)  
- **Claimed Scope:** "C. Accurate clips_generated tracking (atomic, idempotent)".  
- **Forensic Reality:**  
  The test `test_counter_increment_by_actual_count` contains:
  ```python
  channel = make_mock_channel(clips_generated=10)
  actual_new = 3
  before = channel.clips_generated
  channel.clips_generated += actual_new
  after = channel.clips_generated
  assert before == 10
  assert after == 13
  ```
  It tests Python's integer addition (`10 + 3 == 13`) on a `unittest.mock.MagicMock`. It never calls `backend/models/db_sync.py::save_clip_record`, never touches SQLAlchemy, and executes zero SQL `UPDATE channels SET clips_generated = ...`.  
  - **Verdict:** **Zero production database or concurrency coverage**.

#### 3. List Length Invariance Tautology
- **File:** [backend/tests/test_pipeline_config_fixes.py:L223-L230](file:///d:/automation%20video%20clips/clipforge/backend/tests/test_pipeline_config_fixes.py#L223-L230)  
- **Claimed Scope:** "Idempotent rerun no double count".  
- **Forensic Reality:**  
  ```python
  channel = make_mock_channel(clips_generated=13)
  existing_clips = [make_mock_clip(clip_id=f"c{i}") for i in range(3)]
  result = [c.id for c in existing_clips]
  assert len(result) == 3
  assert channel.clips_generated == 13
  ```
  It asserts that creating a list of mocks does not mutate an unreferenced mock attribute.  
  - **Verdict:** **Zero production logic verified**.

#### 4. Hardcoded String Inequality Tautology
- **File:** [backend/tests/test_pipeline_config_fixes.py:L190-L194](file:///d:/automation%20video%20clips/clipforge/backend/tests/test_pipeline_config_fixes.py#L190-L194)  
- **Claimed Scope:** Channel identity mismatch detection.  
- **Forensic Reality:**  
  ```python
  requested = "UC_channel_A"
  authenticated = "UC_channel_B"
  assert authenticated != requested
  ```
  Tests that two hardcoded Python strings are not equal.  
  - **Verdict:** **Zero production authentication or token verification**.

#### 5. Frontend Duplicated Helper Function Isolation
- **Files:** [frontend/test/validation.test.mjs](file:///d:/automation%20video%20clips/clipforge/frontend/test/validation.test.mjs), [frontend/test/api_contract.test.mjs](file:///d:/automation%20video%20clips/clipforge/frontend/test/api_contract.test.mjs)  
- **Claimed Scope:** Validates frontend form URL parsing, duration restrictions (< 30.0s), and API endpoint formatting.  
- **Forensic Reality:**  
  Neither test imports functions from `frontend/app/` or `frontend/lib/`. The helper functions (`extractYouTubeVideoId`, `validateShortDuration`, `validateScheduleDate`, `parseTags`, `buildUploadFormData`, `buildClipsQuery`) are re-implemented directly inside the test files.  
  - **Verdict:** Validates the theoretical specification, but cannot detect regressions or breaking changes made to the actual Next.js component implementations in `frontend/app/publish/page.tsx` or `frontend/app/clips/page.tsx`.

---

## 5. Detailed Inspection of Tests Skipped for Safety

The following tests were thoroughly inspected and intentionally skipped during verification execution because their isolation cannot be established:

### 1. `backend/tests/test_multi_destination_publishing.py`
- **Side Effects:** Directly opens a `SyncSessionLocal()` connection to `postgresql://clipforge:clipforge@localhost:5433/clipforge`.  
- **Mutations:** Inserts `Channel` (source, destination, inactive), `ChannelDestination`, `Video`, `Clip`, and `PublishTarget` rows into the active database. Although it contains a teardown fixture, a crash during execution leaves dirty test records in the active database.
- **Safety Violation:** Breaches rule: *"Do not run a test if its isolation cannot be established. Identify tests that may create or mutate databases."*

### 2. `backend/tests/test_publish_concurrency.py`
- **Side Effects:** Connects to live PostgreSQL and deletes/inserts records on `TaskExecution`, `Clip`, `Video`, and `Job` tables.
- **Concurrency Danger:** Spawns 5 concurrent Python threads calling `check_and_claim_execution` against the live database without in-memory database isolation.

### 3. `backend/tests/test_storage_durability.py`
- **Side Effects:** Creates real files directly in `settings.UPLOAD_DIR` and `settings.OUTPUT_DIR`.
- **Destructive Action:** Calls `backend.cleanup_storage.cleanup()`, which scans directory trees and deletes un-referenced files. Running this against a live workspace risks deleting real user media or uploaded videos.

### 4. `backend/tests/test_orchestration.py`
- **Side Effects:** Inserts a Job record into live PostgreSQL and calls `start_video_processing_task.delay()`.
- **Worker Danger:** Dispatches a Celery task directly to the active Celery worker (`clipforge_worker` container), triggering yt-dlp download of an external YouTube video (`https://www.youtube.com/watch?v=dQw4w9WgXcQ`), ffmpeg slicing, and mock publishing loops.

### 5. `backend/verify_phase15.py`
- **Side Effects:** Executes shell command `ffmpeg -y -f lavfi -i color=c=black:s=1280x720:r=30 ... dummy_phase15_{uuid}.mp4` directly in the project root directory.
- **Evidence of Prior Pollution:** 15 leftover `dummy_phase15_*.mp4` artifacts were discovered during directory inventory from previous un-isolated runs.

---

## 6. Regression Coverage Gaps & Unverified Behaviors

Comparing claimed Upload Studio v1.8 features against existing verified automated tests reveals major gaps:

| Feature / Architectural Guarantee | Claimed Status | Verified by Safe Automated Tests? | Actual Verification Status & Forensic Gap |
| :--- | :--- | :--- | :--- |
| **Multi-Destination Target Isolation** | Implemented | **NO** | Unverified in safe suite. Only covered by `test_multi_destination_publishing.py` which requires an un-isolated live PostgreSQL database. |
| **YouTube OAuth Token Multi-Channel Selection** | Implemented | **NO** | Only string path format (`youtube_token_{id}.json`) is checked. Zero automated tests exist for OAuth token refresh, expiry handling, or credential selection. |
| **Native YouTube Scheduling (`publishAt`)** | Implemented | **NO** | Zero automated tests verify `publishAt` parameter passing, timezone conversion, or private-to-scheduled state transition. |
| **APScheduler Background Execution** | Claimed | **NO** | Zero tests exist. Runtime inspection in Audit 17 proved `asyncio.to_thread` coroutine invocation bug deadlocks the scheduler permanently. |
| **FastAPI Route Contracts & Validation** | Implemented | **NO** | Zero backend API route integration tests (`test_routes.py` or FastAPI `TestClient`) exist. API endpoints are completely untested by automated suites. |
| **Database Migrations (Alembic)** | 17 Versions | **NO** | Zero migration downgrade/upgrade tests exist. |
| **Distributed Task Lock & Claim Idempotency** | Implemented | **NO** | Only covered by un-isolated live-DB concurrency test. |
| **ViewScore Formula & Performance Tracker** | Implemented | **YES** | Verified by pure unit tests in `backend/tests/test_tracker.py` (4/4 passed). |
| **Reframe Coordinate Smoothing & Deadzones** | Implemented | **YES** | Verified by pure unit tests in `tests/test_tracker.py` (3/3 passed). |
| **Equal Split Math Segmentation** | Implemented | **YES** | Verified by pure unit tests in `backend/tests/test_equal_splits.py` (5/5 passed). |
| **Layout Mode Resolution & Geometry** | Implemented | **YES** | Verified by pure unit tests in `backend/tests/test_layout_engine.py` (4/4 passed). |
| **Frontend Route Existence & Jobs Dead-Route Check** | Implemented | **YES** | Verified by Node.js static assertions in `frontend/test/routes.test.mjs` (2/2 passed). |

---

## 7. Audit 18 Scorecard & Summary

### 7.1 Test Count Scorecard

```text
┌─────────────────────────────────────────────────────────────┐
│                    CLIPFORGE TEST AUDIT 18                   │
├─────────────────────────────────────────────────────────────┤
│ Total Test Files Inventoried:                           27   │
│ Total Isolated Test Files Executed:                     12   │
│ Total Individual Tests Executed:                        72   │
│   ├── Passed Tests:                                     71   │
│   └── Failed Tests:                                      1   │
│                                                             │
│ Tests Skipped for Safety (Live DB / Worker / Storage):  15   │
│                                                             │
│ Tests with Tautological / Zero-Production Value:         5   │
│ Critical Regression Gaps (Zero Automated Coverage):      7   │
└─────────────────────────────────────────────────────────────┘
```

### 7.2 Summary of Findings
1. **Core Mathematical Engines are Robustly Verified:**  
   Segmentation geometry (`test_equal_splits.py`), layout engine resolution (`test_layout_engine.py`), ViewScore calculation (`test_tracker.py`), and frame smoothing algorithms (`tests/test_tracker.py`) have 100% isolated, passing unit tests.
2. **False Sense of Coverage in Critical Publishing & Config Modules:**  
   Key pipeline tests (`test_youtube_reconciliation.py` and sections of `test_pipeline_config_fixes.py`) test local test-file simulators or mock additions rather than production application code.
3. **Absence of an Isolated Test Database Fixture:**  
   Integration tests (`test_multi_destination_publishing.py`, `test_publish_concurrency.py`, `test_storage_durability.py`) connect directly to the shared/live PostgreSQL instance (`localhost:5433`). The repository lacks an isolated SQLite in-memory or ephemeral test database fixture setup (`conftest.py`).
4. **Pre-Existing Test Drift Between Root and Backend Suites:**  
   Duplicate copies of test files exist in root `tests/` and `backend/tests/` with identical module names, causing pytest collection namespace collisions. Furthermore, the root copy of `test_pipeline_config_fixes.py` broke due to un-synchronized assertions after the v1.8 dynamic privacy update.
