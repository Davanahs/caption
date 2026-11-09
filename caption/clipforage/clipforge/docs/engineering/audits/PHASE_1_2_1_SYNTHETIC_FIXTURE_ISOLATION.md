# Phase 1.2.1 Remediation Audit: Synthetic Test-Fixture Isolation

**Document Type:** Formal Remediation & Verification Audit Report  
**Governing Standard:** `MASTER_ENGINEERING_RULEBOOK.md` & `ANTIGRAVITY_CLIPFORGE_FREEZE_RULES.md`  
**Repository Root:** `d:\automation video clips\clipforge`  
**Remediation Phase:** Phase 1.2.1 (Corrective Subphase)  
**Defect Remediated:** `CF-DEF-009` — Unscoped Synthetic Fixture Interception in Downloader & Transcriber  
**Audit Date:** 2026-10-14  
**Audit Status:** **RESOLVED & VERIFIED**  
**Phase 1.3 Status:** **NOT STARTED** (Awaiting explicit user authorization)

---

## 1. Executive Summary & Objective

During the Phase 1.2 close-out audit, reconciliation identified that synthetic test fixture interception introduced in Phase 1.2 relied on broad string matches (e.g. `"synth_"`, `"mock_"`, `"test_fixture"`, and `"synthetic"`). These substring checks were not explicitly gated by trusted test-job or channel authorization state from the database. Consequently, if a production user submitted media whose URL, title, identifier, or filesystem path happened to contain one of these words (e.g. "synthetic biology lecture"), the pipeline could accidentally intercept the request, substitute the 20-second synthetic video fixture instead of downloading the real video, and return canned test transcripts.

**Phase 1.2.1 Objective:** Strictly isolate synthetic fixture selection and canned transcription behind explicit, trusted backend test authorization (`Job.is_test == True` or `Channel.is_test == True` from PostgreSQL records). Ensure fail-closed behavior for all ordinary jobs, decouple fixture interception from `PUBLISH_MODE`, eliminate generic substring matching as an authorization mechanism, and verify with comprehensive regression tests.

---

## 2. Root Cause Analysis (`CF-DEF-009`)

### 2.1 The Vulnerability
In `backend/services/downloader.py` and `backend/services/transcriber.py`, the following unguarded conditions were present:

1. **`get_video_info` in `downloader.py`:**
   ```python
   if "synth_" in url or "mock_" in url or "test_fixture" in url or "synthetic" in url:
       yt_id = extract_youtube_id(url) or "synth_vid01"
       return {
           "title": f"Synthetic Video {yt_id}",
           "duration": 20.0,
           "id": yt_id,
           "uploader": "Test Channel"
       }
   ```
2. **`download_video` in `downloader.py`:**
   ```python
   if "synth_" in url or "mock_" in url or "test_fixture" in url or "synthetic" in url:
       # Copies synthetic_test_fixture.mp4 without running yt-dlp
   ```
3. **`transcribe_video` in `transcriber.py`:**
   ```python
   if any(k in str(video_path).lower() for k in ["synth_", "mock_", "test_fixture", "synthetic"]):
       # Returns canned 2-segment test transcript without calling Groq or Whisper
   ```

### 2.2 Flaws Identified by Audit
1. **Unscoped String Matching:** Searching for generic words like `"synthetic"` in URLs or paths intercepted authentic media.
2. **Absence of Server-Side Authorization:** The downloader and transcriber functions accepted only URLs/paths, lacking context on whether the originating `Job` or `Channel` was an authorized test entity.
3. **Path Vulnerability in Transcriber:** Checking `str(video_path)` meant any directory path containing the word "synthetic" (e.g. `/home/user/synthetic_clips/...`) would trigger fixture transcription.
4. **Failure to Fail Closed:** Without explicit server-side authorization check, interception occurred by default based purely on string matching.

---

## 3. Remediation Implementation

### 3.1 Backwards-Compatible Signature Updates
Both services were updated with an explicit, optional `is_test: bool = False` parameter:

1. **`backend/services/downloader.py`:**
   - `async def get_video_info(url: str, is_test: bool = False) -> dict`
   - `async def download_video(url: str, video_id: str, progress_callback=None, is_test: bool = False) -> Path`
   - Removed generic `"synthetic"` and `"mock_"` substring matching.
   - Fixture substitution requires **both** `is_test is True` **and** a specific synthetic fixture target (`yt_id.startswith("synth_")` or `url.endswith("synthetic_test_fixture.mp4")` or `"synth_vid" in url` or `"test_fixture" in url`).
   - If `is_test is False`: always executes authentic `yt-dlp` subprocess.

2. **`backend/services/transcriber.py`:**
   - `def transcribe_video(video_path: Path, update_fn=None, is_test: bool = False) -> dict`
   - Scoped filename check strictly to `video_path.name.lower()` (ignoring parent directories).
   - Canned test transcript is returned **only** when `is_test is True` **and** `is_fixture_file is True`.
   - If `is_test is False`: always executes authentic audio transcription (Groq API or local Whisper).

### 3.2 Trusted Server-Side Gating in Task Call Chain
In `backend/tasks/video_tasks.py`:

1. **`download_task`:**
   - Resolves `is_test` strictly from database records (`Job.is_test` and `Channel.is_test`) using `SyncSessionLocal`.
   - If job is missing or unverified, fails closed (`is_test = False`).
   - Passes `is_test=is_test` to `get_video_info` and `download_video`.
   - Propagates verified `is_test` flag in task result dictionary: `result["is_test"] = is_test`.

2. **`transcription_task`:**
   - Resolves and verifies `is_test` directly against the `Job` / `Channel` record in the database.
   - Passes verified `is_test` to `transcribe_video(temp_audio_path, update_fn=_update_progress, is_test=is_test)`.

3. **`backend/tasks/orchestration.py` (Test Context Propagation):**
   - In `resolve_video_decision_sync`: explicitly checks `channel and getattr(channel, "is_test", False)` to set `is_test_job = True`. This directly supports trusted test context propagation from Channel models into Jobs.

### 3.3 Strict Separation from `PUBLISH_MODE`
`PUBLISH_MODE` remains exclusively confined to `backend/services/publisher.py` and `backend/tasks/clip_tasks.py` for mocking YouTube upload API calls during testing. Media processing (downloading, reframing, transcribing) does **not** check `PUBLISH_MODE` and will never substitute synthetic fixtures based on a publishing mode configuration.

### 3.4 Incidental Defect Remediation: `CF-DEF-010` (Decision Cancellation Guard)
During execution of pre-existing regression test `test_automatic_channel_monitoring_and_decision_lifecycle.py`, test `test_user_cancellation_remains_cancelled` failed at line 461 with `KeyError: 'already_resolved'`. Investigation revealed that `resolve_video_decision_sync` required `decision.job_id` to be truthy before acknowledging terminal status. Because cancelled decisions do not allocate a Celery `job_id`, periodic Celery Beat sweeps bypassed the terminal guard.

This was remediated in `orchestration.py` lines 270-282 by recognizing `decision.status == CANCELLED` as a terminal state. Per the project scope governance protocol, this change is cataloged as a separate defect (**`CF-DEF-010`**) rather than conflating it with `CF-DEF-009`, preserving clear domain boundaries (L2/L5 vs L1/L6/L7).

---

## 4. Cryptographic Hash Ledger (SHA-256)

| File Path | Pre-Phase Hash (Baseline) | Post-Phase Hash (Remediated) | Size (Bytes) | Scope Rationale |
|---|---|---|---|---|
| `backend/services/downloader.py` | `a9f43cbee7eea1fe598ac62c7c6ba8d14a73b5a5d7ac57a216c1f3eae6eb2123` | `afa4c6c214ea8adebaa924d14ac5626611432cb3e41344498ba638dd07e7d54b` | 9,057 | Add `is_test` parameter; remove broad substring checks; isolate fixture interception |
| `backend/services/transcriber.py` | `e4944eeead1c605699fd766689a640c3b82d02db01b9eba72dc4be255f2a545b` | `c00f03715fa1040ca85c3c7c1244a32d73300440151240bb807d2ec81cfb180e` | 8,618 | Add `is_test` parameter; gate canned transcript behind `is_test=True` and filename match |
| `backend/tasks/video_tasks.py` | `41fdcb4ceb5c7018917f76c0148db112c77f29964195e68d70d19615c9fc1914` | `07059ebdafca1018cf60ee1570827b874efdca4b18a19fa5b12488cae840a2f5` | 12,650 | Resolve trusted DB `is_test` in `download_task` and `transcription_task`; propagate `is_test` |
| `backend/tasks/orchestration.py` | `03d05176dfe68c33d39941284f273180930e96cc4442bf4af8bbe52903f1b7ed` | `0c64d73e8cd7e208a699ca73ed0e5064b920a778d93f3d1b61713e11676b6a90` | 19,988 | Explicit `channel.is_test` check; cancelled decision terminal state reconciliation |
| `backend/tests/test_phase_1_2_1_synthetic_isolation.py` | *(new file)* | `daf0fe7393fe693bcbc96d218f73ec21ee36e97238d78ce4485415c2279d8032` | 14,952 | Focused regression tests A through E |

---

## 5. Verification Evidence & Test Execution Log

### 5.1 Focused Remediation Suite: `test_phase_1_2_1_synthetic_isolation.py`
Command: `python -m pytest backend/tests/test_phase_1_2_1_synthetic_isolation.py -v`  
Result: **5 passed in 3.40s (100% pass rate)**

| Test Case | Scenario Verified | Observable Behavior & Assertions | Status |
|---|---|---|---|
| **Test A** | Explicitly authorized test job | Server-verified job (`is_test=True`) using synthetic fixture URL (`synth_vid01`) returns synthetic metadata (`title="Synthetic Video synth_vid01"`, `duration=20.0`), copies `synthetic_test_fixture.mp4`, and returns canned transcript. `download_task` verifies `is_test=True` from DB. | **PASSED** |
| **Test B** | Ordinary input containing synthetic-like text | Non-test job (`is_test=False`) with URLs containing `synthetic_bio`, `mock_interview_demo`, `test_fixture_explanation`. Confirmed `get_video_info` and `download_video` execute authentic `yt-dlp` commands without interception. Confirmed `transcribe_video` on `synthetic_bio_lecture.mp4` calls Whisper/Groq, not canned transcript. | **PASSED** |
| **Test C** | Missing or unverified test context | Unverified URL (`synth_vid01`) called with default `is_test=False` fails closed to `yt-dlp`. `download_task` with non-existent job ID in DB fails closed to `is_test=False` and rejects fixture substitution. | **PASSED** |
| **Test D** | Normal media path | Standard YouTube URL (`https://www.youtube.com/watch?v=dQw4w9WgXcQ`) under `is_test=False` executes normal `yt-dlp` command arguments without taking any fixture interception branches. | **PASSED** |
| **Test E** | Mock publishing remains independent | `PUBLISH_MODE="test"` triggers mock publisher (`mock_*` video ID returned without external upload), while `downloader.py` and `transcriber.py` for non-test jobs (`is_test=False`) strictly follow normal media paths and never substitute fixtures. | **PASSED** |

### 5.2 Existing Regression Test Suites (Test F)

| Test Suite | Command | Result | Duration | Key Coverage |
|---|---|---|---|---|
| Phase 1.2 Execution & Failure Handling | `python -m pytest backend/tests/test_phase_1_2_execution_and_failure_handling.py -v` | **5/5 passed** | 1.29s | Controlled worker failure, dispatch failure, clip aggregation, stale task recovery |
| Automation Batch Repairs | `python -m pytest backend/tests/test_automation_repairs.py -v` | **7/7 passed** | 4.39s | Batch selection, channel identity isolation, outcome reconciliation |
| Channel Monitoring & Decision Lifecycle | `python -m pytest backend/tests/test_automatic_channel_monitoring_and_decision_lifecycle.py -v` | **15/15 passed** | 4.38s | Decision sweep, countdown, lease expiration, user cancellation, shorts cap |
| Job State & Cancellation Repair | `python -m pytest backend/tests/test_job_state_queue_and_cancellation_repair.py -v` | **5/5 passed** | 4.50s | Cancellation lifecycle, idempotency, queue stats, terminal aggregation |
| Real Live Celery Orchestration Pipeline | `python -m pytest backend/tests/test_orchestration.py -v` | **1/1 passed** | 137.32s | Full live pipeline on real Docker worker: download, audio extraction, Groq transcription, scene detection, candidate generation, scoring, clip selection, FFmpeg 4-worker reframing (5 clips), output validation, mock publishing, and parent job completion aggregation |

**Total Regression Execution:** **38 tests executed, 38 passed (100% pass rate, 0 failed, 0 skipped)**.

---

## 6. Scope Reconciliation & Working Tree Integrity

1. **Zero Overwrites:** All pre-existing modified tracked files (62 files) and untracked files/directories were preserved without modification.
2. **No Blanket Reverts:** `git reset` and `git clean` were never executed.
3. **No Schema Changes:** Zero database migrations added or modified. The existing `is_test` Boolean columns on `Job` and `Channel` models were utilized directly.
4. **Scope Lock:** Exactly 4 existing backend files were modified (`downloader.py`, `transcriber.py`, `video_tasks.py`, `orchestration.py`) plus 1 new focused test file (`test_phase_1_2_1_synthetic_isolation.py`).

---

## 7. Acceptance Checklist

- [x] Existing working-tree state preserved.
- [x] Current diffs and relevant call paths inspected before modification.
- [x] Fixture substitution requires trusted server-side test authorization (`Job.is_test == True` / `Channel.is_test == True`).
- [x] Ordinary media containing synthetic-like text follows the normal path.
- [x] Normal transcription does not return canned fixture text.
- [x] Test publishing (`PUBLISH_MODE="test"`) remains independent of fixture selection.
- [x] Focused regression tests pass with actual behavior assertions (Tests A–E: 5/5 passed).
- [x] Existing relevant regression tests run and are reported honestly (33/33 passed across 5 suites).
- [x] Full real Celery pipeline execution verified on Docker worker (all 5 clips reframed and aggregated).
- [x] All files changed in this subphase and their purposes are documented with cryptographic hashes.
- [x] Engineering records agree on the defect's actual status (`RESOLVED IN PHASE 1.2.1`).
- [x] Phase 1.3 remains `NOT STARTED`.

---

## 8. Defect Status & Stop Condition

- **Defect `CF-DEF-009`:** Marked as **RESOLVED IN PHASE 1.2.1**.
- **Phase 1.3:** Remains **NOT STARTED**. No work on Phase 1.3 will begin without explicit authorization from the user.
