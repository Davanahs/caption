# ClipForge — Forensic Pipeline Audit Report

> **Audit Framework:** Comprehensive Pipeline Audit, Bug Detection & Consistency Analysis  
> **Auditor Role:** Senior Software Architect, Backend Engineer, Data-Engineering Expert, QA Engineer, Debugging Specialist  
> **Scope:** Complete codebase — input → preprocessing → processing → API/model calls → validation → persistence → retries/failures → output → UI/observability  
> **Directive:** ANALYZE ONLY — no code modifications

---

## TABLE OF CONTENTS

1. [Executive Summary](#1-executive-summary)
2. [Architecture Reconstruction](#2-architecture-reconstruction)
3. [Critical Findings (P0 / P1)](#3-critical-findings-p0--p1)
4. [Complete Issue Registry](#4-complete-issue-registry)
5. [State Machine Analysis](#5-state-machine-analysis)
6. [Failure & Recovery Analysis](#6-failure--recovery-analysis)
7. [Data Integrity Analysis](#7-data-integrity-analysis)
8. [API & Quota Analysis](#8-api--quota-analysis)
9. [Database Analysis](#9-database-analysis)
10. [UI/Backend Consistency Analysis](#10-uibackend-consistency-analysis)
11. [Testing Gap Analysis](#11-testing-gap-analysis)
12. [Contradiction & Duplication Analysis](#12-contradiction--duplication-analysis)
13. [Cascading Failure Scenarios](#13-cascading-failure-scenarios)
14. [Risk Assessment](#14-risk-assessment)
15. [Recommended Remediation Order](#15-recommended-remediation-order)
16. [Required Tests Before Production](#16-required-tests-before-production)
17. [Final Verdict](#17-final-verdict)

---

## 1. EXECUTIVE SUMMARY

**Overall Health: UNSTABLE — NOT SAFE FOR PRODUCTION**

The ClipForge pipeline has accumulated significant architectural debt, hidden bugs, race conditions, and data-integrity risks that make it unsafe to run on real production data without remediation. While the codebase demonstrates impressive feature breadth and several genuinely sophisticated components (Kalman-filter face tracking, LLM routing with failover, parallel clip processing), the foundational layers — state management, database access patterns, failure handling, and idempotency — are fundamentally flawed.

**Key Determinations:**

- The pipeline **can and will** create duplicate records under retry and batch scenarios.
- The database layer has **two competing access paths** (async SQLAlchemy + sync raw sqlite3) with no coordination, creating observable race conditions.
- **State transitions are not atomic** — a job can be marked "done" while its clips are only partially saved.
- **Failure recovery is incomplete** — retries do not clean up partial state, orphan records survive restart, and the WebSocket polling mechanism can leak database connections.
- **Multiple contradictions exist** between what the API accepts, what the Celery task expects, and what the database stores.

**Count of Issues by Severity:**

| Severity | Count | Description |
|----------|-------|-------------|
| **P0 — Critical** | 9 | Data corruption, permanent data loss, catastrophic failure, severe security |
| **P1 — High** | 14 | Major incorrect behavior, processing failure, large-scale inconsistency |
| **P2 — Medium** | 12 | Reliability problems, recoverable inconsistencies, operational problems |
| **P3 — Low** | 8 | Minor bugs, cleanup issues, code quality problems |

---

## 2. ARCHITECTURE RECONSTRUCTION

### 2.1 Component / Data-Flow Map

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         INPUT LAYER                                          │
├─────────────────────────────────────────────────────────────────────────────┤
│  Sources:                                                                    │
│    • POST /api/videos/url      (YouTube URL)                                │
│    • POST /api/videos/upload   (local MP4/MOV file)                         │
│    • POST /api/videos/batch    (multiple YouTube URLs)                      │
│    • APScheduler (auto)        (channel monitoring every 30 min)            │
│                                                                              │
│  Validation: Regex URL check only. No size limit. No content scan.          │
│  Output: Job record (SQLite), File on disk (./uploads/{uuid}/)              │
└─────────────────────────────────┬───────────────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                      CELERY TASK QUEUE (Redis)                               │
├─────────────────────────────────────────────────────────────────────────────┤
│  Task: process_video_task (single monolithic task)                          │
│  Workers: concurrency=4 (Docker), unbounded (local)                         │
│  Retry: max_retries=3, autoretry_for=(ConnectionError, TimeoutError, OSError)│
│  Ack: task_acks_late=True, task_reject_on_worker_lost=True                  │
│  Beat: track_and_optimize_clips every 12 hours                              │
└─────────────────────────────────┬───────────────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                     PIPELINE PROCESSING (Celery Worker)                      │
├─────────────────────────────────────────────────────────────────────────────┤
│  Step 1: DOWNLOAD (yt-dlp)                                                   │
│    Input: YouTube URL                                                        │
│    Output: MP4 file (./uploads/{video_id}/video.mp4)                        │
│    State: job.status="downloading", progress=10-24%                         │
│                                                                              │
│  Step 2: TRANSCRIBE (Whisper local OR Groq API)                             │
│    Input: Downloaded MP4                                                     │
│    Output: {"text": "...", "segments": [...]}                               │
│    State: job.status="transcribing", progress=25-48%                        │
│                                                                              │
│  Step 3: SCENE DETECT (PySceneDetect)                                        │
│    Input: Downloaded MP4                                                     │
│    Output: List of (start, end) scene boundaries                            │
│    Runs in parallel with transcription via ThreadPoolExecutor               │
│                                                                              │
│  Step 4: SCORE CLIPS (Heuristic + LLM)                                      │
│    Input: transcript segments + scene boundaries                            │
│    Output: List of ClipCandidate (start, end, score, title)                 │
│    State: job.status="analyzing", progress=45%                              │
│                                                                              │
│  Step 5: PROCESS CLIPS (ThreadPoolExecutor, max 4 workers)                  │
│    Per clip: Cut → Reframe → Caption → Thumbnail → Save DB                  │
│    State: job.status="clipping", progress=50-95%                            │
│                                                                              │
│  Step 6: CLEANUP & FINALIZE                                                  │
│    Delete source file, increment channel counter, notify                     │
│    State: job.status="done", progress=100%                                  │
└─────────────────────────────────┬───────────────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                      PERSISTENCE LAYER                                       │
├─────────────────────────────────────────────────────────────────────────────┤
│  Primary: SQLite (single file: clipforge.db)                                │
│    • Async path: SQLAlchemy 2.0 + aiosqlite (FastAPI routes)                │
│    • Sync path: raw sqlite3 (Celery workers via db_sync.py)                 │
│    • WAL mode enabled on both paths                                         │
│    • check_same_thread=False (required for aiosqlite)                       │
│    • No connection pooling on sync path                                     │
│                                                                              │
│  Filesystem:                                                                 │
│    • Uploads: ./uploads/{uuid}/video.mp4                                    │
│    • Outputs: ./outputs/{video_id}/{clip_id}/final.mp4                      │
│    • Thumbnails: ./outputs/{video_id}/{clip_id}/thumbnail.jpg               │
│    • No cleanup policy for outputs                                          │
└─────────────────────────────────┬───────────────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                        OUTPUT LAYER                                          │
├─────────────────────────────────────────────────────────────────────────────┤
│  • Clips Library UI (GET /api/clips/)                                       │
│  • Job Status WebSocket (ws://host/api/jobs/ws/{job_id})                    │
│  • YouTube Publishing (POST /api/clips/{id}/publish)                        │
│  • Auto-publish (inside Celery task if channel.auto_publish=True)           │
│  • Scheduled Publishing (APScheduler every 1 min)                           │
│  • Analytics Tracking (Celery Beat every 12h)                               │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 2.2 Execution Flow Trace

**Trace: Single YouTube URL submission through the pipeline**

```
[Browser] POST /api/videos/url
  → FastAPI route (async SQLAlchemy session)
  → Creates Job row with status="pending"
  → Commits to SQLite via aiosqlite
  → Dispatches Celery task: process_video_task.delay(youtube_url=..., job_id=...)
  → Returns {job_id, message, url} to browser

[Celery Worker] process_video_task starts
  → update_job_sync(job_id, "downloading", 10, ...)  [SYNC sqlite3 write]
  → asyncio.run(get_video_info(youtube_url))  [async inside Celery]
  → asyncio.run(download_video(...))  [async inside Celery]
  → create_video_record(video_id, title, ...)  [SYNC sqlite3 write, INSERT OR IGNORE]
  → link_job_video_sync(job_id, video_id)  [SYNC sqlite3 write]
  → check_and_transcode_av1(video_file)  [FFmpeg subprocess]
  
  → update_job_sync(job_id, "transcribing", 25, ...)  [SYNC sqlite3 write]
  → asyncio.run(run_parallel_tasks())  [nested event loop]
    → ThreadPoolExecutor runs transcribe_video (Whisper, CPU-intensive)
    → ThreadPoolExecutor runs detect_scenes (PySceneDetect)
    → Returns transcript + scenes
  → IF transcript has text:
    → raw sqlite3 UPDATE videos SET transcript=? WHERE id=?  [BYPASSES SQLAlchemy]
  → IF transcription fails: segments=[], scenes=[] but pipeline CONTINUES

  → update_job_sync(job_id, "analyzing", 45, ...)  [SYNC sqlite3 write]
  → asyncio.run(find_best_clips(...))  [nested event loop, calls LLM router]
  → IF best_clips is empty: raise ValueError → job marked FAILED

  → ThreadPoolExecutor(max_workers=min(total_clips, 4))  [parallel clip processing]
    → FOR EACH CLIP (in parallel threads):
      → asyncio.run(cut_clip(...))  [nested event loop per thread]
      → generate_ass(...) or generate_srt(...)
      → asyncio.run(reframe_to_vertical(...))  [nested event loop]
      → OPTIONAL: B-Roll, Hook Intro, Auto-Dubbing  [conditional imports]
      → asyncio.run(extract_thumbnail(...))
      → save_clip_record(...)  [SYNC sqlite3 write from thread]
      → generate_metadata(...)  [asyncio.run inside thread]
      → save_clip_metadata(...)  [SYNC sqlite3 write from thread]
      → IF auto_publish: upload_short(...) + raw sqlite3 UPDATE clips ... [from thread]
      → delete intermediate files

  → update_job_sync(job_id, "done", 100, ...)  [SYNC sqlite3 write]
  → notify_clips_generated(...)  [fire-and-forget thread]
  → Return {"status": "done", "video_id": ..., "clips": ...}

[Browser] WebSocket /api/jobs/ws/{job_id}
  → Opens AsyncSessionLocal every 1 second
  → Polls Job row until status in {done, failed}
  → Closes connection
```

### 2.3 Source of Truth Map

| Information | Source of Truth | Derived Copies | Sync Mechanism |
|-------------|----------------|----------------|----------------|
| Job status | `jobs` table (SQLite) | WebSocket stream, Celery task state | Poll-based (1s interval) |
| Video metadata | `videos` table | None | Direct DB read/write |
| Clip metadata | `clips` table + filesystem | Thumbnail file, SRT file | Manual file operations |
| Transcript | `videos.transcript` (TEXT) | In-memory during pipeline | Pipeline writes once |
| Publish status | `clips.publish_status` | YouTube API (external) | One-way (DB → YouTube) |
| Channel state | `channels` table | APScheduler memory | Direct DB read/write |
| Analytics | `clips` denormalized columns + `video_analytics` table | YouTube API | Celery Beat polling |

---

## 3. CRITICAL FINDINGS (P0 / P1)

### P0-001: SQLite Concurrent Access from Async + Sync Paths Causes Database Corruption Risk

**Severity:** P0 — Critical  
**Category:** Database / Concurrency  
**File:** `backend/models/database.py`, `backend/models/db_sync.py`, `backend/tasks/process_video.py`  
**Function:** `get_db()`, `get_connection()`, `process_video_task()`, all `db_sync` functions

**Problem:** The application uses TWO different database access patterns on the SAME SQLite file simultaneously:
1. FastAPI routes use `aiosqlite` via SQLAlchemy async sessions (`AsyncSessionLocal`)
2. Celery workers use raw `sqlite3` synchronous connections (`db_sync.py`)

Both access paths enable WAL mode (`PRAGMA journal_mode=WAL`) but SQLite WAL mode still has limitations:
- Only ONE writer at a time (readers can proceed)
- The busy_timeout (30s) means writers spin-wait rather than fail fast
- If a writer holds the lock and crashes, the WAL file grows unbounded
- `check_same_thread=False` (required for aiosqlite) removes SQLite's thread-safety guardrails

**Concrete Evidence:**
```python
# backend/models/database.py:10
engine = create_async_engine(
    settings.DATABASE_URL,
    connect_args={"check_same_thread": False},  # REQUIRED for aiosqlite but dangerous
)

# backend/models/db_sync.py:6-9
def get_connection():
    conn = sqlite3.connect(str(settings.DB_PATH), timeout=30)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA busy_timeout=30000;")
    return conn
```

The Celery worker (running in a separate process) opens raw sqlite3 connections while the FastAPI app holds aiosqlite connections. When the channel monitor (APScheduler in FastAPI process) checks channels and the Celery worker simultaneously updates job progress, both attempt to write to the same WAL.

**Root Cause:** SQLite was chosen as "zero-config" without considering the multi-process reality (FastAPI + Celery worker + Celery beat + APScheduler all as separate processes/containers).

**Impact:** Intermittent "database is locked" errors, potential WAL corruption, lost writes, jobs appearing stuck.

**Reproduction:** Start a video processing job via channel auto-monitor. While it's processing, open the dashboard and navigate to the Clips Library. The dashboard stats query (`/api/stats` uses raw sqlite3) and the worker's job update (`update_job_sync` uses raw sqlite3) compete with the async session for clips listing.

**Recommended Fix:** Migrate to PostgreSQL. If migration is delayed, route ALL database access through a single synchronous connection pool shared by both API (via `asyncio.to_thread`) and Celery workers.

---

### P0-002: Nested Event Loops in Celery Task Cause RuntimeError or Deadlock

**Severity:** P0 — Critical  
**Category:** Concurrency / Async  
**File:** `backend/tasks/process_video.py`  
**Function:** `process_video_task()`  
**Lines:** 165, 177, 222-223, 266, 311, 341, 407, 412, 414, 442

**Problem:** The Celery task uses `asyncio.run()` multiple times inside a synchronous Celery worker context. `asyncio.run()` creates a NEW event loop and closes it when done. Calling `asyncio.run()` inside an already-running loop (or inside a thread that has a loop) raises `RuntimeError: asyncio.run() cannot be called from a running event loop`.

**Concrete Evidence:**
```python
# Line 165: asyncio.run(get_video_info(youtube_url))
# Line 177: asyncio.run(download_video(...))
# Line 222-223: asyncio.run(run_parallel_tasks())  # Inside the main task body
# Line 266: asyncio.run(find_best_clips(...))
# Line 311: asyncio.run(cut_clip(...))  # INSIDE ThreadPoolExecutor thread!
# Line 341: asyncio.run(reframe_to_vertical(...))  # INSIDE ThreadPoolExecutor thread!
# Line 407: asyncio.run(extract_thumbnail(...))  # INSIDE ThreadPoolExecutor thread!
# Line 412: asyncio.run(analyze_content(...))  # INSIDE ThreadPoolExecutor thread!
# Line 442: asyncio.run(generate_metadata(...))  # INSIDE ThreadPoolExecutor thread!
```

The task body itself runs `asyncio.run()` at the top level. But when `ThreadPoolExecutor` spawns worker threads, those threads call `asyncio.run()` AGAIN. If the thread happens to inherit any event loop state, or if `asyncio.run()` is called concurrently from multiple threads, Python's asyncio will raise `RuntimeError`.

**Root Cause:** The codebase was originally async (FastAPI) and async functions were reused in the synchronous Celery context by wrapping them in `asyncio.run()`. The addition of `ThreadPoolExecutor` for parallel clip processing compounded the problem.

**Impact:** Intermittent `RuntimeError` crashes during clip processing. The crash happens INSIDE a ThreadPoolExecutor thread, which may cause the future to fail silently (returning `False` from `process_one_clip`) OR hanging the thread pool.

**Reproduction:** Submit a video with `num_clips >= 2` so that ThreadPoolExecutor spawns multiple threads. Each thread calls `asyncio.run(cut_clip(...))`. On some Python versions/platforms, this will raise RuntimeError.

**Recommended Fix:** Do NOT use `asyncio.run()` inside threads. Either:
1. Make the Celery task itself async (requires Celery 5.3+ with `@app.task` and event loop management), OR
2. Convert all async service functions to synchronous versions for Celery workers, OR
3. Use `asyncio.new_event_loop()` + `loop.run_until_complete()` explicitly in each thread with proper cleanup.

---

### P0-003: ThreadPoolExecutor + SQLite Writes from Multiple Threads = Race Condition

**Severity:** P0 — Critical  
**Category:** Concurrency / Data Integrity  
**File:** `backend/tasks/process_video.py`  
**Function:** `process_one_clip()` (closure inside `process_video_task`)  
**Lines:** 424-435, 451-461, 478-485

**Problem:** The `process_one_clip` closure runs inside `ThreadPoolExecutor` threads. Inside this closure, it calls `save_clip_record()`, `save_clip_metadata()`, and (if auto_publish) raw `sqlite3.connect()` + `UPDATE`. These are all SYNC writes to the SAME SQLite database from MULTIPLE concurrent threads.

**Concrete Evidence:**
```python
# backend/tasks/process_video.py:424-435
save_clip_record(
    clip_id=clip_id, video_id=video_id, title=clip.title,
    start=clip.start, end=clip.end, duration=clip.duration,
    score=clip.score, output_path=str(final_clip),
    thumbnail_path=str(thumb_file),
    transcript_segment=clip.text[:500] if hasattr(clip, "text") else "",
)

# backend/models/db_sync.py:71-102
# save_clip_record opens a NEW sqlite3 connection, executes INSERT, commits, closes
# This happens from EACH ThreadPoolExecutor worker thread concurrently
```

While SQLite with WAL mode supports concurrent readers, writers are serialized. With 4 threads all trying to write simultaneously, each thread waits up to 30 seconds (`busy_timeout=30000`). If the timeout is exceeded, SQLite raises "database is locked". The exception is caught by the clip-level try/except (lines 509-518) which marks the clip as failed and cleans up its directory — but the job continues, leaving partial data.

**Root Cause:** Parallel clip processing was added without considering that all clip save operations write to the same SQLite file.

**Impact:** Clips randomly fail to save with "database is locked". Job reports "Done! Generated X/Y clips" where X < Y, with no indication which clips failed or why. The filesystem has orphaned directories.

**Reproduction:** Submit a video that produces 5+ clips. With 4 parallel workers, at least 2-3 will attempt to write to the database simultaneously.

**Recommended Fix:** Serialize ALL database writes from the ThreadPoolExecutor. Collect clip results in memory and write them all from the MAIN thread after `as_completed()` finishes.

---

### P0-004: Job Retry Creates Duplicate Video and Clip Records

**Severity:** P0 — Critical  
**Category:** Data Integrity / Idempotency  
**File:** `backend/api/routes/jobs.py`, `backend/tasks/process_video.py`  
**Function:** `retry_failed_job()`, `process_video_task()`  
**Lines:** 211-257 (jobs.py), 155, 188, 424 (process_video.py)

**Problem:** The `/api/jobs/{job_id}/retry` endpoint resets a failed job to `status="pending"` and re-queues the Celery task with the SAME `job_id`. However, the pipeline generates a NEW `video_id = str(uuid.uuid4())` on every task invocation (line 155), creates a NEW Video record (line 188), and creates NEW Clip records (line 424) — WITHOUT cleaning up the old video/clips from the failed attempt.

**Concrete Evidence:**
```python
# backend/api/routes/jobs.py:211-257
@router.post("/{job_id}/retry")
async def retry_failed_job(job_id: str, db: AsyncSession = Depends(get_db)):
    # ... validation ...
    job.status = "pending"  # Reset status
    job.progress = 0
    job.error_message = None
    await db.commit()
    
    task = process_video_task.delay(
        youtube_url=job.source_url,
        job_id=job.id,  # SAME job_id
    )
    # job.celery_task_id is updated but old clips remain

# backend/tasks/process_video.py:155
video_id = str(uuid.uuid4())  # NEW video_id every time!
if not job_id:
    job_id = self.request.id or str(uuid.uuid4())

# Line 188: create_video_record(video_id, ...)  # NEW Video row
# Line 424: save_clip_record(clip_id=clip_id, video_id=video_id, ...)  # NEW Clip rows
```

The retry also does NOT:
- Delete old output files from the failed attempt
- Delete old Video record (if any was created before failure)
- Delete old Clip records
- Update the `video_id` FK on the Job row (the old link remains)

**Root Cause:** The retry endpoint was designed to re-queue the task without understanding that the pipeline is not idempotent — it always generates new IDs and new records.

**Impact:** Each retry creates orphaned Video records, orphaned Clip records, and duplicate output files on disk. The clips library shows multiple sets of clips for the same source video. Disk space is wasted.

**Reproduction:**
1. Submit a YouTube URL
2. Let the job fail (e.g., disconnect network during download)
3. Click "Retry" in the UI
4. Observe: the job succeeds, but the Clips Library now has clips from BOTH the failed attempt (if any were saved before failure) AND the retry.

**Recommended Fix:** Before retrying, delete all associated Video, Clip records and output files from the previous attempt. OR make the pipeline idempotent by using deterministic IDs derived from (job_id + clip_index).

---

### P0-005: Direct Raw SQLite UPDATE Bypasses SQLAlchemy Session and ORM

**Severity:** P0 — Critical  
**Category:** Data Integrity / Architecture  
**File:** `backend/tasks/process_video.py`  
**Function:** `process_video_task()`  
**Lines:** 228-232, 478-485

**Problem:** The pipeline writes transcript data and publish status using raw `sqlite3` connections that bypass the SQLAlchemy ORM entirely. This means:
1. The SQLAlchemy session cache becomes stale
2. No ORM hooks fire (no validation, no defaults, no relationships)
3. The write is not part of any transaction managed by SQLAlchemy
4. If the async API reads the same row immediately after, it may get stale data

**Concrete Evidence:**
```python
# backend/tasks/process_video.py:228-232
if full_text:
    import sqlite3 as _sq3
    _c = _sq3.connect(str(settings.DB_PATH), timeout=30)
    _c.execute("UPDATE videos SET transcript=? WHERE id=?", (full_text, video_id))
    _c.commit()
    _c.close()

# backend/tasks/process_video.py:478-485
import sqlite3
conn = sqlite3.connect(str(settings.DB_PATH), timeout=30)
conn.execute(
    "UPDATE clips SET publish_status='published', youtube_short_id=?, published_at=? WHERE id=?",
    (youtube_short_id, datetime.utcnow().isoformat(), clip_id)
)
conn.commit()
conn.close()
```

**Root Cause:** The developer needed synchronous DB access from Celery and created `db_sync.py`, but then also embedded ad-hoc sqlite3 code directly in the pipeline task for convenience.

**Impact:** Data inconsistency between what SQLAlchemy sees and what's actually in the database. The `videos.transcript` column is updated via raw SQL but the async session may still hold the old value. The `clips.publish_status` is updated via raw SQL but the Clip ORM object is never refreshed.

**Recommended Fix:** Consolidate ALL database access through `db_sync.py` functions. Remove ALL inline sqlite3 connections from the pipeline task.

---

### P0-006: Channel Monitor Race Condition Creates Duplicate Processing

**Severity:** P0 — Critical  
**Category:** Race Condition / Data Integrity  
**File:** `backend/services/channel_monitor.py`  
**Function:** `check_channel_for_new_videos()`, `run_channel_monitor()`  
**Lines:** 15-51, 54-89

**Problem:** The channel monitor checks for new videos by looking at the `Video` table. But the `Video` record is only created AFTER download starts (inside the Celery task). There is a window of time between "job queued" and "video record created" where the same video can be detected as "new" again.

**Concrete Evidence:**
```python
# backend/services/channel_monitor.py:32-37
existing = await db.execute(
    select(Video).where(Video.youtube_id == yt_id)
)
if existing.scalar_one_or_none():
    continue  # Skip if already processed

# BUT the Video record is created INSIDE the Celery task:
# backend/tasks/process_video.py:188
# create_video_record(video_id, title, youtube_url or "", yt_id or "", ...)
```

If APScheduler runs channel check every 30 minutes, and a Celery task takes >30 minutes to start (queue backup), the next scheduled check will see the same video as "new" because the Video record hasn't been created yet.

**Root Cause:** The "already processed" check looks at the Video table instead of the Job table. Jobs are created immediately but Videos are created inside the task.

**Impact:** The same video is processed multiple times, creating duplicate clips, wasting compute, and potentially publishing duplicates to YouTube.

**Reproduction:**
1. Add a channel with auto_clip=True
2. Upload a new video to that channel
3. Trigger channel check → job queued
4. Before the Celery worker starts the job, trigger channel check again
5. The same video is queued again

**Recommended Fix:** Check the `Job` table (not `Video` table) for existing pending/processing jobs with the same `source_url`. Also add a unique constraint or deduplication check at job creation time.

---

### P0-007: No Authentication on Any Endpoint

**Severity:** P0 — Critical  
**Category:** Security  
**File:** All files in `backend/api/routes/`  
**Function:** All route handlers

**Problem:** Every single API endpoint is completely open. No JWT, no session cookies, no API keys, no OAuth (beyond the YouTube publishing flow which only protects YouTube, not the ClipForge API).

**Concrete Evidence:** No `Depends(get_current_user)` or any auth dependency on any route. The `CORSMiddleware` allows `https://*.netlify.app` — any Netlify subdomain can make requests.

**Impact:** Anyone with network access can: delete all clips, publish spam to your YouTube channel, trigger infinite channel checks, upload malicious files, read all data.

**Recommended Fix:** Add JWT-based authentication. Protect all routes. Add role-based access control.

---

### P0-008: Settings Page Saves OAuth Credentials to localStorage

**Severity:** P0 — Critical  
**Category:** Security  
**File:** `frontend/app/settings/page.tsx`  
**Function:** `SettingsPage()`, `handleSave()`  
**Lines:** 33-43

**Problem:** The settings page stores YouTube Client ID and Client Secret in `localStorage` — plaintext, accessible by any JavaScript, never sent to backend, never actually used.

**Concrete Evidence:**
```typescript
// frontend/app/settings/page.tsx:39
localStorage.setItem('clipforge_settings', JSON.stringify(env));
```

**Impact:** OAuth credentials permanently stored in browser plaintext. XSS can steal them. Settings don't actually affect backend behavior.

**Recommended Fix:** Remove credential fields from frontend. Create secure backend settings endpoint.

---

### P0-009: `task_acks_late=True` + `task_reject_on_worker_lost=True` Without Dead Letter Queue

**Severity:** P0 — Critical  
**Category:** Reliability / Celery  
**File:** `backend/tasks/process_video.py`  
**Function:** Celery app configuration  
**Lines:** 19-36

**Problem:** With `task_acks_late=True`, tasks are acknowledged only after completion. With `task_reject_on_worker_lost=True`, if a worker dies mid-task, the task is re-queued. But there is no dead letter queue, no max retry limit for worker deaths, and no circuit breaker. A task that consistently crashes the worker will loop forever.

**Concrete Evidence:**
```python
# backend/tasks/process_video.py:26-29
task_acks_late=True,
task_reject_on_worker_lost=True,
```

The `max_retries=3` on the task decorator only applies to exceptions in `autoretry_for`. If the worker process itself is killed (OOM, segfault, SIGKILL), Celery will re-queue the task infinitely because `task_reject_on_worker_lost=True` with no dead letter queue.

**Impact:** Runaway retry loops consuming all workers. A single bad video that OOMs the worker will be retried forever, blocking the queue.

**Recommended Fix:** Add a dead letter queue. Set a global max retry limit. Add a circuit breaker for worker death events.

---

## 4. COMPLETE ISSUE REGISTRY

| ID | Severity | Category | File | Function | Problem | Root Cause | Impact | Reproduction | Recommended Fix |
|----|----------|----------|------|----------|---------|------------|--------|--------------|-----------------|
| PIPE-001 | P0 | Database/Concurrency | `backend/models/database.py` | `engine` creation | SQLite accessed from async SQLAlchemy + sync raw sqlite3 simultaneously with `check_same_thread=False` | Architecture chose SQLite for multi-process setup | Data corruption, "database is locked" errors, lost writes | Run channel monitor while job is processing | Migrate to PostgreSQL |
| PIPE-002 | P0 | Concurrency/Async | `backend/tasks/process_video.py` | `process_video_task` | Multiple `asyncio.run()` calls inside Celery task and ThreadPoolExecutor threads | Reused async functions in sync Celery context | RuntimeError, thread deadlock, silent clip failures | Submit video with num_clips >= 2 | Convert async services to sync for Celery |
| PIPE-003 | P0 | Concurrency/Data Integrity | `backend/tasks/process_video.py` | `process_one_clip` closure | ThreadPoolExecutor threads write to same SQLite DB concurrently | Parallel clip processing without serialized DB access | "database is locked", orphaned clips, partial saves | Submit video producing 5+ clips | Collect results in memory, write from main thread |
| PIPE-004 | P0 | Data Integrity | `backend/api/routes/jobs.py` + `backend/tasks/process_video.py` | `retry_failed_job()` + `process_video_task()` | Retry generates NEW video_id and NEW clips without cleaning up old state | Pipeline not idempotent | Duplicate records, orphaned files, wasted disk | Fail a job, click retry | Delete old records/files before retry OR use deterministic IDs |
| PIPE-005 | P0 | Data Integrity | `backend/tasks/process_video.py` | `process_video_task()` | Raw sqlite3 UPDATE bypasses SQLAlchemy ORM (transcript update, publish status) | Convenience coding over architectural consistency | Stale ORM cache, inconsistent reads, no validation | Read video transcript via API immediately after pipeline writes it | Consolidate all DB access through db_sync.py |
| PIPE-006 | P0 | Race Condition | `backend/services/channel_monitor.py` | `check_channel_for_new_videos()` | "Already processed" check looks at Video table, but Video is created INSIDE the task | Wrong table used for deduplication | Same video processed multiple times | Queue backup >30 min with channel monitoring | Check Job table for existing pending jobs |
| PIPE-007 | P0 | Security | `backend/api/routes/*.py` | All routes | Zero authentication/authorization on any endpoint | Single-user local tool design | Full data exposure, channel hijacking, DOS | Access API from any origin | Add JWT auth to all routes |
| PIPE-008 | P0 | Security | `frontend/app/settings/page.tsx` | `handleSave()` | OAuth credentials stored in browser localStorage | Misunderstanding of env var architecture | Credential theft via XSS | Open settings page, enter credentials | Remove from frontend, add secure backend endpoint |
| PIPE-009 | P0 | Reliability | `backend/tasks/process_video.py` | Celery config | `task_acks_late=True` + `task_reject_on_worker_lost=True` with no dead letter queue | Attempted resilience without full retry topology | Infinite retry loops, worker pool deadlock | Kill worker mid-task repeatedly | Add dead letter queue, global retry limit |
| PIPE-010 | P1 | Data Integrity | `backend/api/routes/clips.py` | `list_clips()` | `.outerjoin(Video)` with `.scalars().all()` loses joined columns | Incorrect SQLAlchemy query pattern | `source_title` and `source_url` always None from join | Call /api/clips/ and inspect response | Use `.mappings().all()` or select specific columns |
| PIPE-011 | P1 | Performance | `backend/api/routes/clips.py` | `list_clips()` | N+1 query: fetches Video separately for each clip in loop | Inefficient query pattern | O(n) DB queries for n clips | List clips with 50+ items | Eager load Video in single query |
| PIPE-012 | P1 | API Contract | `backend/api/routes/videos.py` | `process_youtube_url()` | Accepts BOTH `num_clips` and `clips_count` as Form params | Backward compatibility alias that conflicts | `clips_count` default (3) overrides `num_clips` | POST with num_clips=5, clips_count=3 | Remove one parameter, keep single source of truth |
| PIPE-013 | P1 | Input Validation | `backend/api/routes/videos.py` | `upload_video_file()` | No file size limit check before writing to disk | Missing validation | Disk exhaustion, OOM, DOS | Upload 10GB+ file | Add max file size check (e.g., 2GB) |
| PIPE-014 | P1 | State Management | `backend/models/models.py` | `JobStatus` enum | `RETRYING` state exists but no code transitions TO it | Added to enum but never used | Dead enum value, confusing state machine | Search codebase for `JobStatus.RETRYING` | Remove unused state or implement retry transition |
| PIPE-015 | P1 | State Management | `backend/models/models.py` | `PublishStatus` enum | `FAILED` state exists but no code ever sets it | Added to enum but never used | Dead enum value | Search codebase for `publish_status='failed'` | Remove or implement failed publish handling |
| PIPE-016 | P1 | Database | `backend/models/database.py` | `init_db()` | Runs 30+ ALTER TABLE statements on EVERY startup | Schema migration anti-pattern | Slow startup, failed migrations ignored silently | Restart server 10 times | Use Alembic for migrations |
| PIPE-017 | P1 | Database | `backend/models/db_sync.py` | `save_clip_record()` | Hardcodes default column values inline instead of using model defaults | Convenience over maintainability | Schema change requires updating db_sync.py AND models.py | Add new column with default | Use INSERT OR IGNORE with column names only |
| PIPE-018 | P1 | Concurrency | `backend/main.py` | `scheduled_channel_check()` | Wraps async `run_channel_monitor` in `asyncio.to_thread()` | Incorrect async/thread boundary | Function may not execute correctly, exceptions swallowed | Trigger scheduled channel check | Call async function directly without to_thread |
| PIPE-019 | P1 | Reliability | `backend/tasks/process_video.py` | `process_video_task()` | On transcription failure, sets segments=[] and continues instead of failing | Overly permissive error handling | Produces clips with empty/no captions, misleading quality | Submit video with unparseable audio | Fail the job if transcription fails and no scenes detected |
| PIPE-020 | P1 | Architecture | `backend/models/models.py` | Multiple tables | `VideoMetadata`, `VideoAnalytics`, `OptimizationLog`, `VideoTrackingQueue`, `ContentAnalysis`, `SEOAnalysis`, `OptimizationContext`, `PipelineMetrics` tables exist but have NO API routes or usage | Tables added but integration incomplete | Dead schema, confusion about source of truth | Search for these table names in API routes | Either implement full feature or remove unused tables |
| PIPE-021 | P1 | Data Integrity | `backend/tasks/process_video.py` | `process_video_task()` | `video_id` generated before `job_id` check, wasting UUID if job_id provided | Incorrect ordering | Wasted UUID generation | Call task with explicit job_id | Move video_id generation after job_id fallback |
| PIPE-022 | P1 | API Contract | `backend/api/routes/jobs.py` | `get_job_stats()` | Function defined TWICE (lines 62-75 and 165-208) | Copy-paste or merge artifact | Second definition overrides first, first is unreachable | Call /api/jobs/stats | Remove duplicate function |
| PIPE-023 | P1 | Reliability | `backend/api/routes/jobs.py` | `cancel_job()` | Deletes job from DB but does NOT clean up associated files | Incomplete cleanup | Orphaned video/clip files on disk | Cancel a job, check filesystem | Delete associated uploads/outputs on cancel |
| PIPE-024 | P1 | Performance | `backend/api/routes/jobs.py` | `job_status_ws()` | Opens new AsyncSessionLocal every 1 second per WebSocket client | Naive polling implementation | DB connection exhaustion under load | Open 50 dashboard tabs | Use Redis pub/sub or cache job status |
| PIPE-025 | P1 | Security | `backend/main.py` | `/api/stats` | Uses raw sqlite3 sync connection while app uses async SQLAlchemy | Mixed access pattern | Race condition with worker writes | Call /api/stats during active processing | Use async SQLAlchemy session |
| PIPE-026 | P1 | Reliability | `backend/models/database.py` | `cleanup_orphaned_jobs()` | Finds orphaned jobs but does NOT auto-fail them | Conservative design | Jobs stuck in non-terminal state forever | Restart server with active jobs | Auto-fail orphaned jobs or add explicit recovery |
| PIPE-027 | P1 | API Contract | `backend/api/routes/videos.py` | `process_youtube_url()` + `process_video_task()` | Task decorator has `max_retries=3` but error handler manually sets status="retrying" then `raise` | Confused retry responsibility | Status says "retrying" but Celery handles retry internally, creating mismatched state | Cause transient error, observe status | Remove manual retry status, let Celery handle it |
| PIPE-028 | P2 | Data Integrity | `backend/models/models.py` | `Clip` model | `tags` stored as JSON string in TEXT column | No native JSON support in SQLite | Manual serialization/deserialization, no validation | Store array in tags, read back | Use JSON type or separate junction table |
| PIPE-029 | P2 | Data Integrity | `backend/models/models.py` | `Clip` model | Analytics columns denormalized into Clip table while `video_analytics` table also exists | Dual storage for same data | Inconsistency, confusion about source of truth | Compare clip.analytics_views vs video_analytics.view_count | Consolidate into single storage |
| PIPE-030 | P2 | Type Safety | `backend/models/models.py` | `Clip` model | `analytics_last_checked` is String(50) not DateTime | Schema inconsistency | Cannot do date arithmetic, sorting issues | Compare to other DateTime columns | Change to DateTime |
| PIPE-031 | P2 | Architecture | `backend/models/models.py` | `VideoMetadata` | `video_id` is String with no foreign key constraint | Referential integrity gap | Orphaned metadata records | Delete a video, check metadata table | Add foreign key constraint |
| PIPE-032 | P2 | Architecture | `backend/models/models.py` | `ContentAnalysis` | `clip_id` is primary key but no FK to clips | Referential integrity gap | Orphaned analysis records | Delete a clip, check content_analysis table | Add foreign key constraint |
| PIPE-033 | P2 | Reliability | `backend/tasks/process_video.py` | `process_video_task()` | B-Roll, Hook Intro, Auto-Dubbing use conditional imports inside try blocks | Optional features not validated at startup | Silent failures if modules missing | Run without those service modules | Add startup validation for optional features |
| PIPE-034 | P2 | Performance | `backend/tasks/process_video.py` | `process_video_task()` | `ThreadPoolExecutor` calls `asyncio.run()` inside each thread | Nested event loops, thread overhead | Thread hangs, RuntimeError | Process 4 clips in parallel | Remove asyncio.run from threads |
| PIPE-035 | P2 | API Contract | `backend/api/routes/clips.py` | `publish_clip()` | Calls `upload_short()` synchronously — blocks event loop | Synchronous call in async route | Request timeout, server unresponsive | Publish a large clip to YouTube | Use `asyncio.to_thread()` or async YouTube client |
| PIPE-036 | P2 | Reliability | `backend/services/channel_monitor.py` | `check_channel_for_new_videos()` | `yt_id` extraction: `video.get("url", "").split("v=")[-1]` returns full URL if no "v=" | Fragile URL parsing | Invalid video IDs, failed processing | Channel with non-YouTube URLs | Use robust URL parsing with validation |
| PIPE-037 | P2 | State Management | `backend/services/channel_monitor.py` | `check_channel_for_new_videos()` | `last_video_id` check prevents re-processing but also prevents processing if video was previously "last" | Overly restrictive dedup | Video never processed if it was the last one previously | Re-upload same video to channel | Use job-based dedup instead |
| PIPE-038 | P2 | Reliability | `backend/tasks/process_video.py` | `process_video_task()` | Progress calculation uses shared mutable list `_clips_done[0]` with Lock | Shared mutable state in parallel processing | Race condition in progress reporting | Process clips with varying durations | Use atomic counter or Celery's built-in progress |
| PIPE-039 | P2 | Security | `backend/core/config.py` | `Settings` | `CONTENT_ID_BYPASS` flags for copyright circumvention | Ethical/legal concern | Potential Terms of Service violation, legal risk | Enable CONTENT_ID_BYPASS | Remove copyright circumvention features |
| PIPE-040 | P2 | Reliability | `backend/tasks/process_video.py` | `process_video_task()` | Hook title text: `getattr(settings, 'HOOK_TITLE_DEFAULT', True)` | Config value not defined in Settings | Always True regardless of user intent | Check settings.HOOK_TITLE_DEFAULT | Add to config or use explicit parameter |
| PIPE-041 | P2 | Data Integrity | `backend/tasks/process_video.py` | `process_one_clip()` | On clip failure, `shutil.rmtree(clip_dir)` deletes directory but DB record may already exist | Cleanup before state check | File deleted but DB record remains, broken download links | Cause clip to fail after save_clip_record | Check DB state before filesystem cleanup |
| PIPE-042 | P2 | API Contract | `backend/api/routes/jobs.py` | `retry_failed_job()` | Does NOT clear video_id FK, old clips, or old output files | Incomplete state reset | Duplicate/wrong associations | Retry a failed job | Clear all associated state before retry |
| PIPE-043 | P3 | Code Quality | `backend/tasks/process_video.py` | `process_video_task()` | `_ClipProxy` class defined inline inside function | Memory overhead, code smell | New class definition every function call | Use equal_split mode | Define class at module level |
| PIPE-044 | P3 | Code Quality | `backend/tasks/process_video.py` | `process_video_task()` | Multiple `import os` / `import os as _os` inside try blocks | Redundant imports | Slight overhead, code smell | Any B-Roll/Hook/Dub path | Move imports to top of file |
| PIPE-045 | P3 | Code Quality | `backend/tasks/process_video.py` | `process_video_task()` | `hasattr(clip, "text")` checked repeatedly instead of using property | Repetitive code | Maintenance burden, inconsistency risk | Any clip processing | Normalize clip interface with dataclass |
| PIPE-046 | P3 | Code Quality | `backend/models/models.py` | `Job` model | `celery_task_id` is String(200) but Celery IDs are UUIDs (36 chars) | Overly wide column | Minor storage waste | Check schema | Use String(36) |
| PIPE-047 | P3 | Code Quality | `backend/api/routes/videos.py` | `list_videos()` | Hardcoded limit of 50 with no pagination parameters | UX limitation | Cannot browse large libraries | Have 100+ videos | Add pagination (offset/limit) |
| PIPE-048 | P3 | Observability | `backend/tasks/process_video.py` | `process_video_task()` | Uses `print()` for all logging | No structured logs, no levels | Debugging difficult, logs lost on restart | Any pipeline run | Replace with Python logging module |
| PIPE-049 | P3 | Testing | Entire codebase | N/A | Zero automated tests | Development without safety net | Regression risk, fear of refactoring | Run pytest — 0 tests found | Add pytest suite |
| PIPE-050 | P3 | UI/UX | `frontend/app/settings/page.tsx` | `SettingsPage()` | Settings save to localStorage but never sent to backend | Non-functional settings | User thinks config is saved but backend ignores it | Change any setting, restart backend | Implement backend settings endpoint |

---

## 5. STATE MACHINE ANALYSIS

### 5.1 Job Status States

```
                    ┌─────────────┐
         ┌─────────→│   PENDING   │←────────┐
         │          │  (initial)  │         │
         │          └──────┬──────┘         │
         │                 │ retry          │
         │          ┌──────▼──────┐         │
         │          │ DOWNLOADING │         │
         │          └──────┬──────┘         │
         │                 │                │
         │          ┌──────▼──────┐         │
         │          │TRANSCRIBING │         │
         │          └──────┬──────┘         │
         │                 │                │
         │          ┌──────▼──────┐         │
         │          │  ANALYZING  │         │
         │          └──────┬──────┘         │
         │                 │                │
         │          ┌──────▼──────┐         │
         │          │  CLIPPING   │         │
         │          └──────┬──────┘         │
         │                 │                │
    ┌────┴────┐     ┌──────▼──────┐    ┌────┴────┐
    │  DONE   │←────│  (implicit) │    │  FAILED │
    │(success)│     │   states    │    │(fatal)  │
    └─────────┘     └─────────────┘    └─────────┘
         ↑                                  │
         └──────────────────────────────────┘
              (retry endpoint resets to PENDING)
```

**Observed Issues:**
- `RETRYING` is defined in `JobStatus` enum (line 17 of models.py) but NO code ever transitions a job to this state
- The retry endpoint (jobs.py:233) resets to `"pending"` (string literal), not `JobStatus.PENDING` (enum)
- The error handler in process_video.py (line 574) sets status="retrying" for transient errors, but Celery handles the actual retry — the status is misleading because the task is re-queued, not actively retrying
- After max retries exhausted, status becomes "failed" but there is no FAILED → PENDING transition except via the manual retry endpoint

### 5.2 Publish Status States

```
┌─────────┐    publish    ┌─────────┐    schedule    ┌─────────┐
│  DRAFT  │──────────────→│ QUEUED  │──────────────→│PUBLISHED│
│ (initial)│               │         │   (time due)   │         │
└─────────┘               └─────────┘               └─────────┘
     │
     └────────────────────────────────────────────────→ ?
```

**Observed Issues:**
- `FAILED` is defined in `PublishStatus` enum (line 26) but NO code ever sets `publish_status='failed'`
- Auto-publish failure (process_video.py:493-495) prints error but does NOT update publish_status
- Scheduled publish failure (main.py scheduled_publish_check) sets `publish_status = "failed"` (string, not enum)
- YouTube publish failure in `publish_clip()` (clips.py:372) raises HTTPException but does NOT update publish_status

### 5.3 Invalid State Transitions Possible

| From | To | How | Is It Valid? |
|------|-----|-----|--------------|
| PENDING | DOWNLOADING | Task starts | ✅ Yes |
| CLIPPING | DONE | All clips processed | ✅ Yes |
| CLIPPING | FAILED | Exception in main try block | ✅ Yes |
| DONE | PENDING | Manual retry endpoint | ⚠️ Should clean up first |
| FAILED | PENDING | Manual retry endpoint | ⚠️ Should clean up first |
| DONE | DOWNLOADING | None | ✅ Not possible |
| FAILED | CLIPPING | None | ✅ Not possible |
| PENDING | RETRYING | Error handler sets it | ❌ Misleading — Celery retries, not job |
| QUEUED | FAILED | Scheduled publish fails | ✅ Yes (but uses string not enum) |

---

## 6. FAILURE & RECOVERY ANALYSIS

### 6.1 Failure Mode Matrix

| Failure | Detected? | Classified? | Retried? | Max Retries | After Exhausted | Persisted? | Resumable? | Duplicate Risk? |
|---------|-----------|-------------|----------|-------------|-----------------|------------|------------|-----------------|
| Network drop during download | ✅ Yes | Transient | ✅ Celery auto | 3 | FAILED | ✅ Status updated | ❌ No | ❌ No (same job_id) |
| yt-dlp returns 429 | ✅ Yes | Fatal (ValueError) | ❌ No | 0 | FAILED | ✅ Status updated | ❌ No | ❌ No |
| Whisper model load fails | ✅ Yes | Fatal | ❌ No | 0 | FAILED | ✅ Status updated | ❌ No | ❌ No |
| Transcription empty | ⚠️ Silent | Warning only | ❌ No | 0 | CONTINUES | ⚠️ Partial | ❌ No | ❌ No |
| LLM scoring timeout | ✅ Yes | Fatal | ❌ No | 0 | FAILED | ✅ Status updated | ❌ No | ❌ No |
| FFmpeg cut fails | ✅ Yes | Fatal (per-clip) | ❌ No | 0 | Clip skipped | ✅ Job continues | ❌ No | ⚠️ Partial clip dir may remain |
| SQLite "database is locked" | ✅ Yes | Fatal (per-clip) | ❌ No | 0 | Clip skipped | ✅ Job continues | ❌ No | ⚠️ DB record may be missing |
| Auto-publish YouTube error | ✅ Yes | Warning only | ❌ No | 0 | Clip saved as draft | ✅ Status=published via raw SQL | ❌ No | ❌ No |
| Worker OOM/crash | ⚠️ Maybe | Unknown | ✅ Re-queued | ∞ | Re-queued | ⚠️ Orphan state | ⚠️ Maybe | ⚠️ Yes (if partial saves) |
| Disk full | ✅ Yes | Fatal | ❌ No | 0 | FAILED | ✅ Status updated | ❌ No | ⚠️ Partial files remain |
| Invalid video format | ✅ Yes | Fatal | ❌ No | 0 | FAILED | ✅ Status updated | ❌ No | ❌ No |

### 6.2 Retry Behavior Analysis

**Celery Retry Configuration:**
```python
@celery_app.task(
    bind=True,
    name="process_video",
    max_retries=3,
    autoretry_for=(ConnectionError, TimeoutError, OSError),
    retry_backoff=True,
    retry_backoff_max=60,
    retry_jitter=True,
    default_retry_delay=5,
)
```

**Analysis:**
- Only `ConnectionError`, `TimeoutError`, and `OSError` are auto-retried
- `ValueError` (bad URL, invalid format) is NOT retried — immediately FAILED
- `RuntimeError` (nested event loop) is NOT retried — immediately FAILED
- The task's error handler (lines 565-589) sets status="retrying" for transient errors, but this is MISLEADING because:
  - For auto-retryable errors: Celery handles the retry automatically. The status="retrying" is set, then the task raises, then Celery re-queues it. On re-queue, the status is reset to whatever the task starts with (it starts at "downloading", not "retrying"). So the "retrying" status is only visible for milliseconds.
  - For non-retryable errors: The status is set to "failed" and the exception is raised. This is correct.
- **Critical Gap:** There is NO exponential backoff for the MANUAL retry endpoint (`/api/jobs/{job_id}/retry`). A user can click retry infinitely.

### 6.3 Resume After Interruption

**Scenario: Server restart during active job**

1. `cleanup_orphaned_jobs()` runs on startup
2. Finds jobs with status NOT IN {done, failed}
3. Logs them: "Startup: N job(s) were mid-flight"
4. Does NOT auto-fail them
5. Celery MAY re-pick them up if they were in the queue
6. BUT if the worker was mid-task, the task is lost (unless `task_acks_late` saves it)
7. With `task_acks_late=True`, the task is re-queued automatically
8. The task re-runs from the BEGINNING, generating a NEW video_id and NEW clips

**Result:** After restart + re-queue, you have:
- The original Job row (still linked to old video_id or none)
- A NEW Video row (from the re-run)
- NEW Clip rows (from the re-run)
- Old output files (if any were created before crash)

---

## 7. DATA INTEGRY ANALYSIS

### 7.1 Corruption Scenarios

#### Scenario A: Pipeline crashes during database update

**Trigger:** Worker killed via SIGKILL during `save_clip_record()`

**State after crash:**
- Job status: "clipping" (non-terminal)
- Clip record: MAY exist (if commit completed) or MAY NOT (if killed mid-commit)
- Files on disk: raw.mp4 exists, final.mp4 MAY exist
- Video record: EXISTS (created at start)

**On restart:**
- `cleanup_orphaned_jobs()` finds the job but does NOT auto-fail
- Celery re-queues the task (acks_late)
- Task re-runs from beginning with NEW video_id
- Result: Duplicate Video record, duplicate clips, orphan files

#### Scenario B: API succeeds but database write fails

**Trigger:** YouTube upload succeeds but sqlite3 UPDATE fails (disk full)

**State:**
- Video is LIVE on YouTube
- Clip record still shows `publish_status='draft'`
- No `youtube_short_id` in database

**On retry:**
- Manual retry would re-process the entire video
- Auto-publish would try to upload AGAIN (duplicate YouTube video)

#### Scenario C: Database succeeds but process crashes before status update

**Trigger:** All clips saved to DB, but worker crashes before `update_job_sync(job_id, "done", ...)`

**State:**
- Job status: "clipping" (non-terminal)
- All clips exist in DB and on disk
- Job is orphaned

**On restart:**
- Task is re-queued, re-runs from beginning
- Creates NEW video + NEW clips
- Original clips remain in library

#### Scenario D: Same item enters processing twice

**Trigger:** Channel monitor race condition (PIPE-006)

**State:**
- Two Job records for the same YouTube URL
- Both eventually create Video records
- Both create Clip sets
- Result: Duplicate clips in library

#### Scenario E: Quota exhausted halfway through processing

**Trigger:** YouTube Data API quota (10,000 units/day) exhausted during auto-publish

**State:**
- Some clips published, others not
- No quota tracking or budgeting
- Next channel check will still try to publish

#### Scenario F: A job repeatedly fails

**Trigger:** Bad video format causes ValueError on every retry

**State:**
- After 3 Celery retries: status="failed"
- User can manually retry via endpoint (infinite times)
- Each manual retry creates NEW records

#### Scenario G: User manually skips an item

**Trigger:** User cancels/deletes a job

**State:**
- Job record deleted from DB
- Celery task revoked with SIGTERM
- BUT: Video and Clip records may already exist
- Output files remain on disk

### 7.2 Idempotency Analysis

| Operation | Idempotent? | Why Not? | Risk |
|-----------|-------------|----------|------|
| `create_job_sync()` | ✅ Yes | INSERT with PK, duplicate key would fail | Low |
| `create_video_record()` | ❌ NO | Uses NEW uuid every time | Duplicate videos |
| `save_clip_record()` | ❌ NO | Uses NEW uuid every time | Duplicate clips |
| `save_clip_metadata()` | ✅ Yes | UPDATE by clip_id | Low |
| `update_job_sync()` | ✅ Yes | UPDATE by job_id | Low |
| `upload_short()` | ❌ NO | Creates new YouTube video every time | Duplicate uploads |
| `process_video_task()` | ❌ NO | Generates new IDs, writes new records | Full duplication |
| `check_channel_for_new_videos()` | ❌ NO | No distributed lock | Duplicate jobs |

---

## 8. API & QUOTA ANALYSIS

### 8.1 External APIs Used

| API | Purpose | Rate Limit | Quota | Current Handling |
|-----|---------|------------|-------|------------------|
| YouTube Data API v3 | Publish videos, set thumbnails | 10,000 units/day | 10,000/day | No quota tracking |
| Groq API | Transcription ( Whisper ) | Varies by plan | Varies | 25MB file limit checked |
| OpenRouter | LLM scoring | Varies | Varies | 120s timeout |
| Nvidia NIM | LLM fallback | Varies | Varies | 60s timeout |
| Ollama (local) | LLM fallback | N/A (local) | N/A | Disabled in code |
| yt-dlp | Video download | N/A | N/A | No retry logic |

### 8.2 Quota Risks

1. **YouTube API:** Auto-publish + scheduled publish + thumbnail upload + channel info fetch all consume quota. No central quota tracker exists. A batch of 10 videos with 5 clips each, auto-published = 50 uploads ≈ 80,000 units (exceeds daily quota).

2. **Groq API:** If GROQ_API_KEY is set, EVERY video's audio is uploaded. No caching. Re-processing the same video consumes quota again.

3. **OpenRouter:** Every video scoring calls the API. The prompt includes full transcript segments, consuming significant tokens. No response caching.

### 8.3 Retry Amplification

- Celery auto-retry on `ConnectionError` / `TimeoutError` / `OSError` with max 3 retries
- Each retry re-downloads the video (full bandwidth consumption)
- Each retry re-transcribes (full compute consumption)
- Each retry re-scores via LLM (full API quota consumption)
- **There is NO checkpointing** — retries restart from Step 1, not from the failed step

---

## 9. DATABASE ANALYSIS

### 9.1 Schema Assessment

| Table | Row Estimate | Issues |
|-------|-------------|--------|
| videos | ~100-1000 | No index on youtube_id. transcript is TEXT (unbounded). No FK constraints. |
| clips | ~500-5000 | 20+ columns, denormalized analytics. No index on video_id. tags as JSON string. |
| jobs | ~100-1000 | No index on status. celery_task_id is 200 chars (waste). |
| channels | ~10-100 | clips_generated counter can drift. |
| metadata | 0 (unused) | No FK to videos. No API routes. |
| video_analytics | 0 (unused) | Duplicate of clips denormalized columns. No API routes. |
| optimizations | 0 (unused) | No FK to clips. No API routes. |
| video_tracking_queue | 0 (unused) | No API routes. |
| content_analysis | 0 (unused) | clip_id is PK but not FK. No API routes. |
| seo_analysis | 0 (unused) | clip_id is PK but not FK. No API routes. |
| optimization_context | 0 (unused) | No API routes. |
| pipeline_metrics | 0 (unused) | No API routes. |

### 9.2 Transaction Safety

**Current Pattern:**
- FastAPI routes: Use SQLAlchemy `async with session` — single transaction per request
- Celery workers: Use raw sqlite3 with explicit `conn.commit()` per function call
- Pipeline task: Multiple independent sqlite3 commits across the task lifecycle

**Problems:**
1. There is NO single transaction wrapping the entire pipeline
2. A crash after `save_clip_record()` but before job status update leaves orphaned clips
3. The auto-publish sqlite3 UPDATE (line 478-485) is a separate transaction from clip creation
4. `cleanup_orphaned_jobs()` explicitly does NOT clean up — leaving partial state

### 9.3 Migration Strategy

The `init_db()` function runs 30+ `ALTER TABLE` statements in a try/except block on EVERY startup:
```python
for column_name, column_type in [... 30 items ...]:
    try:
        await conn.execute(text(f"ALTER TABLE clips ADD COLUMN {column_name} {column_type}"))
    except Exception:
        pass  # Already exists
```

**Problems:**
- Slows startup (30 ALTER attempts)
- Swallows ALL errors, not just "column already exists"
- If a column rename happens, old code still tries to add old name
- No rollback mechanism for partial failures
- `Base.metadata.create_all()` runs first, then ALTER attempts run — if they fail silently, schema is inconsistent

---

## 10. UI/BACKEND CONSISTENCY ANALYSIS

### 10.1 API Contract Mismatches

| Frontend Expects | Backend Provides | Mismatch |
|-----------------|------------------|----------|
| `num_clips` parameter | `num_clips` AND `clips_count` both accepted | Backend uses `clips_count` (default 3) |
| Settings saved to backend | Settings saved to localStorage only | Backend never receives settings |
| Job status "retrying" visible | Status flashes "retrying" then resets | User never sees retrying state |
| `source_title` in clip list | `outerjoin` with `.scalars()` loses it | Always null in response |
| Analytics from `video_analytics` table | Analytics from `clips` denormalized columns | Frontend may show stale data |

### 10.2 Progress Tracking Inconsistencies

- The WebSocket polls every 1 second but the job status only updates at pipeline milestones
- Progress percentages are hardcoded (10, 25, 45, 50-95, 100) not calculated from actual work
- The `_clips_done[0]` counter in ThreadPoolExecutor is shared mutable state — progress may jump erratically
- If a clip fails, `_clips_done` increments but `clips_saved` does not — progress bar reaches 100% but result says "X/Y clips"

---

## 11. TESTING GAP ANALYSIS

### 11.1 What Is Tested

| Component | Test Coverage |
|-----------|--------------|
| Database models | ❌ None |
| API routes | ❌ None |
| Celery tasks | ❌ None |
| FFmpeg integration | ❌ None |
| Whisper integration | ❌ None |
| LLM router | ❌ None |
| Face tracking | ❌ None |
| YouTube publishing | ❌ None |
| Frontend components | ❌ None |
| Frontend API client | ❌ None |

### 11.2 High-Value Tests That Would Catch Existing Bugs

1. **Test: Retry job creates no duplicates** → Would catch PIPE-004
2. **Test: Channel monitor deduplication** → Would catch PIPE-006
3. **Test: Parallel clip processing with SQLite** → Would catch PIPE-003
4. **Test: asyncio.run inside ThreadPoolExecutor** → Would catch PIPE-002
5. **Test: Raw sqlite3 bypasses ORM** → Would catch PIPE-005
6. **Test: List clips returns source_title** → Would catch PIPE-010
7. **Test: Cancel job cleans up files** → Would catch PIPE-023
8. **Test: Upload size limit enforced** → Would catch PIPE-013
9. **Test: Job stats endpoint returns correct counts** → Would catch PIPE-022 (duplicate function)
10. **Test: Equal split mode produces expected clips** → Would catch PIPE-012 (parameter conflict)

---

## 12. CONTRADICTION & DUPLICATION ANALYSIS

### 12.1 Contradictions Found

| # | Contradiction | Evidence |
|---|--------------|----------|
| 1 | `JobStatus.RETRYING` exists in enum but is never transitioned to | `models.py:17` vs codebase search |
| 2 | `PublishStatus.FAILED` exists but never set | `models.py:26` vs codebase search |
| 3 | `num_clips` parameter accepted but `clips_count` (default 3) always wins | `videos.py:23-24` vs `process_video.py:245` |
| 4 | `settings.HOOK_TITLE_DEFAULT` referenced but not defined in Settings | `process_video.py:339` vs `config.py` |
| 5 | Async `run_channel_monitor` wrapped in `asyncio.to_thread()` | `main.py:24-25` — to_thread expects sync function |
| 6 | `cleanup_orphaned_jobs` says "worker will re-pick them up" but with `task_acks_late=True` they may not | `database.py:85-86` vs Celery behavior |
| 7 | LLM router comment says "Ollama intentionally DISABLED" but README promotes Ollama | `llm_router.py:240-242` vs `README.md` |
| 8 | Analytics stored in BOTH `clips` denormalized columns AND `video_analytics` table | `models.py:84-93` vs `models.py:141-150` |
| 9 | `tags` stored as JSON string in TEXT column, but `VideoMetadata` stores as comma-separated String | `models.py:66` vs `models.py:135` |
| 10 | Pipeline task handles retry in error block but Celery also handles retry via decorator | `process_video.py:565-589` vs decorator `autoretry_for` |

### 12.2 Duplicate Implementations

| # | Duplicate | Location | Which Is Used? |
|---|-----------|----------|----------------|
| 1 | `get_job_stats()` | `jobs.py:62-75` AND `jobs.py:165-208` | Second definition (line 165) overrides first |
| 2 | SQLite connection setup | `database.py` (async) AND `db_sync.py` (sync) | Both used simultaneously |
| 3 | PRAGMA WAL mode | `database.py:18-20` (event listener) AND `database.py:42-43` (init_db) AND `db_sync.py:7` | All three set it redundantly |
| 4 | Analytics storage | `clips` table (denormalized) AND `video_analytics` table | `clips` table is used by API routes |
| 5 | Transcript update | `db_sync.py` (none) AND inline sqlite3 in `process_video.py:228-232` | Inline version is used |
| 6 | Publish status update | `clips.py:361-365` (ORM) AND `process_video.py:478-485` (raw SQL) | Both used in different paths |
| 7 | Settings persistence | `.env` file (backend) AND `localStorage` (frontend) AND `config.py` defaults | Backend uses `.env`, frontend uses `localStorage` — never synchronized |

---

## 13. CASCADING FAILURE SCENARIOS

### Scenario 1: Worker OOM During Parallel Clip Processing

```
Video with 8 clips submitted
→ ThreadPoolExecutor spawns 4 workers
→ Worker 3 loads MediaPipe (memory spike)
→ Worker 3 OOMs, kernel kills process
→ task_acks_late=True → task NOT acknowledged
→ task_reject_on_worker_lost=True → task re-queued
→ Celery retry #1: re-downloads, re-transcribes, re-scores
→ Hits same 8-clip video → OOM again
→ Celery retry #2: same
→ Celery retry #3: same
→ max_retries exhausted → status="failed"
→ User clicks "Retry" manually → infinite loop possible
→ Disk fills with duplicate output files
→ SQLite WAL grows unbounded from failed writes
```

### Scenario 2: Channel Monitor Storm

```
APScheduler fires channel_check every 30 minutes
→ 10 active channels each have 2 new videos
→ 20 jobs queued in Redis
→ Celery workers process 4 at a time (concurrency=4)
→ Processing takes 15 minutes per video
→ Next APScheduler tick fires while queue still has 16 jobs
→ Channel monitor sees same videos (Video records not yet created)
→ 20 MORE jobs queued
→ Queue grows exponentially
→ Redis memory exhaustion
→ SQLite writer contention from 40+ concurrent workers
→ "database is locked" errors cascade
→ All jobs fail, disk fills, system unusable
```

### Scenario 3: YouTube Quota Death Spiral

```
Channel auto-publish enabled
→ 50 clips generated across 10 videos
→ Each upload costs ~1600 YouTube API units
→ Total: 80,000 units (quota is 10,000/day)
→ Upload #7 fails with quotaExceeded
→ Error is caught, printed, but clip status set to "published" via raw SQL
→ Next scheduled check tries to publish more
→ More quotaExceeded errors
→ Error logs fill disk
→ No circuit breaker stops the attempts
→ Quota resets at midnight but backlog is huge
→ System churns on failing publishes for hours
```

### Scenario 4: Database Lock Cascade

```
ThreadPoolExecutor processing 4 clips in parallel
→ Clip 1: save_clip_record() → opens sqlite3 connection → writes → OK
→ Clip 2: save_clip_record() → opens sqlite3 connection → WAITS (Clip 1 writing)
→ Clip 3: save_clip_record() → opens sqlite3 connection → WAITS
→ Clip 4: save_clip_record() → opens sqlite3 connection → WAITS
→ Clip 1 commit completes
→ Clip 2 gets lock → writes → commit
→ Clip 3 gets lock → but FFmpeg is still running in thread 3
→ Thread 3's asyncio.run(reframe_to_vertical()) hangs
→ Clip 3's save_clip_record() never called
→ Thread 3 timeout (none set) → hangs forever
→ ThreadPoolExecutor never completes
→ Job stuck at "clipping" forever
→ WebSocket polls indefinitely
→ User sees frozen progress bar at 85%
```

---

## 14. RISK ASSESSMENT

### Overall Risk Classification: **HIGH — NOT PRODUCTION READY**

| Risk Category | Level | Justification |
|--------------|-------|---------------|
| Data Corruption | **CRITICAL** | P0-001, P0-003, P0-005 — concurrent SQLite writes, nested event loops, raw SQL bypass |
| Data Loss | **HIGH** | P0-004 (retry orphans), P1-023 (cancel doesn't cleanup), P1-026 (orphan jobs not recovered) |
| Duplicate Data | **CRITICAL** | P0-004, P0-006, PIPE-041 — retry and race conditions create duplicates |
| Security | **CRITICAL** | P0-007, P0-008 — no auth, credentials in localStorage |
| Availability | **HIGH** | P0-009 (infinite retry), P1-024 (connection leak), cascading failure scenarios |
| Correctness | **HIGH** | P1-010 (lost joined data), P1-012 (parameter conflict), P1-019 (empty transcription continues) |
| Observability | **MEDIUM** | P3-048 (print only), missing structured logging |
| Maintainability | **MEDIUM** | P2-020 (dead tables), P2-043 (inline classes), duplicate code |

---

## 15. RECOMMENDED REMEDIATION ORDER

### Phase 1 — Data Safety (Week 1)

| Priority | Issue | Action |
|----------|-------|--------|
| 1 | PIPE-001 | Migrate to PostgreSQL OR consolidate all DB access through a single sync pool |
| 2 | PIPE-003 | Serialize all DB writes from ThreadPoolExecutor — collect results, write from main thread |
| 3 | PIPE-005 | Remove ALL inline sqlite3 from pipeline task — route through db_sync.py exclusively |
| 4 | PIPE-004 | Make retry idempotent: cleanup old records/files before retry, or use deterministic IDs |
| 5 | PIPE-006 | Check Job table (not Video table) for duplicate detection in channel monitor |

### Phase 2 — Correctness (Week 2)

| Priority | Issue | Action |
|----------|-------|--------|
| 6 | PIPE-002 | Remove asyncio.run() from Celery task and ThreadPoolExecutor threads |
| 7 | PIPE-010 | Fix list_clips query to use proper join result mapping |
| 8 | PIPE-012 | Remove duplicate `clips_count` parameter, use `num_clips` only |
| 9 | PIPE-019 | Fail job if transcription fails AND no scenes detected |
| 10 | PIPE-022 | Remove duplicate `get_job_stats()` function |

### Phase 3 — Reliability (Week 3)

| Priority | Issue | Action |
|----------|-------|--------|
| 11 | PIPE-009 | Add dead letter queue, global retry limit, circuit breaker |
| 12 | P0-007 | Implement JWT authentication on all API routes |
| 13 | P0-008 | Remove credential fields from frontend, create secure backend settings endpoint |
| 14 | PIPE-023 | Make cancel_job cleanup associated files and records |
| 15 | PIPE-013 | Add file size limit validation on upload |

### Phase 4 — Consistency (Week 4)

| Priority | Issue | Action |
|----------|-------|--------|
| 16 | PIPE-014/015 | Remove unused enum values OR implement their transitions |
| 17 | PIPE-016 | Replace dynamic ALTER TABLE with Alembic migrations |
| 18 | PIPE-020 | Remove unused tables OR implement full features |
| 19 | PIPE-028/029 | Consolidate tags storage and analytics storage |
| 20 | All contradictions | Resolve each contradiction (document behavior vs implementation) |

### Phase 5 — Observability (Week 5)

| Priority | Issue | Action |
|----------|-------|--------|
| 21 | PIPE-048 | Replace all print() with structured logging (correlation IDs, levels) |
| 22 | PIPE-024 | Replace WebSocket DB polling with Redis pub/sub |
| 23 | PIPE-026 | Auto-fail orphaned jobs on startup with configurable timeout |
| 24 | — | Add Prometheus metrics for queue depth, processing duration, error rates |

### Phase 6 — Performance (Week 6)

| Priority | Issue | Action |
|----------|-------|--------|
| 25 | PIPE-011 | Fix N+1 query in clips list |
| 26 | PIPE-034 | Remove asyncio.run from ThreadPoolExecutor threads |
| 27 | PIPE-035 | Make YouTube upload async (run in thread pool) |
| 28 | — | Add checkpointing so retries resume from failed step, not beginning |

### Phase 7 — Cleanup (Week 7)

| Priority | Issue | Action |
|----------|-------|--------|
| 29 | PIPE-043/044/045 | Refactor inline class, redundant imports, repeated hasattr checks |
| 30 | PIPE-047 | Add pagination to video and clip lists |
| 31 | — | Add comprehensive test suite (prioritize the 10 high-value tests) |
| 32 | — | Security audit and penetration test |

---

## 16. REQUIRED TESTS BEFORE PRODUCTION

The following tests MUST pass before the pipeline is considered safe for real data:

1. **Test: Concurrent job processing does not corrupt SQLite** — Run 5 jobs simultaneously, verify all complete without "database is locked" errors.

2. **Test: Retry creates no duplicates** — Submit a job, fail it at the scoring step, retry it, verify exactly ONE video record and expected clip count exist.

3. **Test: Channel monitor deduplication** — Trigger channel check twice within 1 minute for same channel, verify exactly ONE job queued per new video.

4. **Test: Cancel cleans up everything** — Submit a job, cancel it mid-processing, verify: no job record, no video record, no clip records, no files on disk.

5. **Test: Server restart recovery** — Start a job, kill the Celery worker mid-task, restart server, verify: orphaned job is either recovered or cleaned up, no duplicate records.

6. **Test: Parallel clip processing with 8 clips** — Submit video producing 8 clips, verify all 8 save to DB without "database is locked".

7. **Test: Empty transcription handling** — Submit video with no audio, verify job fails gracefully (not produces empty-caption clips).

8. **Test: File size limit enforcement** — Attempt upload of 5GB file, verify immediate rejection before disk write.

9. **Test: API authentication required** — Attempt every API endpoint without auth token, verify 401 Unauthorized.

10. **Test: Quota exhaustion handling** — Simulate YouTube quota exceeded, verify auto-publish stops attempts, marks clips as queued (not published), and notifies user.

11. **Test: list_clips returns source_title** — Create clip with associated video, call /api/clips/, verify source_title is present and correct.

12. **Test: Job stats accuracy** — Create mix of pending/active/done/failed jobs, call /api/jobs/stats, verify counts match actual state.

---

## 17. FINAL VERDICT

### Is the pipeline safe to run on production/real data right now?

## **NO.**

### Direct Answer with Justification:

The ClipForge pipeline is **NOT safe** for production use due to the following non-negotiable issues:

1. **P0-001 (SQLite concurrent access):** Multiple processes writing to the same SQLite file will eventually corrupt data or cause permanent "database is locked" failures.

2. **P0-002 (Nested event loops):** The `asyncio.run()` calls inside ThreadPoolExecutor threads will cause `RuntimeError` on some platforms, silently failing clips.

3. **P0-003 (ThreadPoolExecutor DB writes):** Parallel clip processing writes to SQLite from multiple threads, causing race conditions and lost clip records.

4. **P0-004 (Retry duplicates):** Manual retry creates duplicate video and clip records without cleaning up old state.

5. **P0-006 (Channel monitor race):** The same video can be processed multiple times, creating duplicate clips and wasting resources.

6. **P0-007/P0-008 (Security):** Zero authentication and credentials stored in browser localStorage make the system fundamentally insecure.

### What Can Safely Be Run Now:

- **Local development** with a single worker (`--concurrency=1`) and NO channel monitoring
- **Single video uploads** with manual review before any publish action
- **The face tracking and reframe logic** in isolation (these components are well-engineered)

### What Should NOT Be Run:

- **Channel auto-monitoring** (will create duplicate jobs under load)
- **Auto-publish** (will exhaust YouTube quota, create duplicate uploads)
- **Batch processing** (will overwhelm SQLite, create resource contention)
- **Any deployment exposed to the internet** (no authentication)

### What Data Should Be Backed Up:

- `clipforge.db` — the entire database (but note: it may already have inconsistencies)
- `./outputs/` directory — all generated clips
- `./uploads/` directory — source videos
- `youtube_token.json` — OAuth credentials

### What Components Need Fixing First:

1. **Database layer** (PIPE-001, PIPE-003, PIPE-005) — migrate to PostgreSQL or serialize all writes
2. **Celery task architecture** (PIPE-002, PIPE-004) — remove nested event loops, make idempotent
3. **Channel monitor** (PIPE-006) — fix deduplication logic
4. **Security** (P0-007, P0-008) — add authentication, remove localStorage credentials
5. **State management** (PIPE-014, PIPE-015, PIPE-026) — clean up unused states, auto-recover orphans

---

*End of Forensic Audit Report*

---

# Production Capacity & User Access

## Objective

Determine how many users the current ClipForge deployment can support when exposed through a public domain. Capacity is determined from the actual deployment architecture and configuration (Docker Compose, Celery, and DB config), not theoretical maximums.

---

## 1. Deployment Architecture

`	ext
Frontend: Next.js (Local, not orchestrated in docker-compose)
Backend: FastAPI (Uvicorn)
API server: 1 instance (default workers)
Worker count: 1 container
Celery worker concurrency: 4
Celery queues: default
Celery Beat: 1 container
PostgreSQL: 1 container (15-alpine)
Redis: 1 container (7-alpine)
MinIO/S3: None (Local volume mounts)
Reverse proxy: None
Container count: 6
CPU: Unconstrained by Docker
RAM: Unconstrained by Docker
GPU: None configured (CPU-bound FFmpeg processing)
GPU VRAM: N/A
Storage: Local host volumes (./data, ./uploads, ./outputs)
Network: Bridge network (docker-compose default)
`

---

## 2. User Access Model

`	ext
Anonymous users: SUPPORTED
Authenticated users: NOT SUPPORTED
Multiple accounts: NOT SUPPORTED
Multiple simultaneous sessions: SUPPORTED (Stateless API)
Multiple simultaneous uploads: SUPPORTED (Bound by disk I/O)
Multiple simultaneous video-processing jobs: SUPPORTED (Up to 4)
Multiple simultaneous publishing jobs: SUPPORTED (Up to 4)
Multiple simultaneous dubbing jobs: SUPPORTED (Up to 4)
Multiple simultaneous AI requests: SUPPORTED (Up to 4)
`

---

## 3. Concurrency Capacity

### FastAPI
`	ext
workers: 1 (uvicorn default)
threads: Default asyncio threadpool
async concurrency: Native async
connection pool size: 5 (DB_POOL_SIZE) + 5 (DB_MAX_OVERFLOW)
`

### Celery
`	ext
worker instances: 1
concurrency per worker: 4
total task concurrency: 4
`

### PostgreSQL
`	ext
pool size: 5
max overflow: 5
maximum configured connections: 10 per process (10 for API, 10 for Worker)
`

### Redis
`	ext
broker capacity/configuration: default alpine config
backend capacity/configuration: default alpine config
`

---

## 4. Resource Bottlenecks

`	ext
RESOURCE: Celery workers
CURRENT CONFIGURATION: concurrency=4
EXPECTED LIMIT: 4 concurrent background jobs (video/AI/dubbing)
EVIDENCE: docker-compose.yml (\command: celery ... --concurrency=4\)

RESOURCE: PostgreSQL connections
CURRENT CONFIGURATION: pool_size=5, max_overflow=5
EXPECTED LIMIT: ~10 concurrent active database API requests
EVIDENCE: backend/core/config.py

RESOURCE: Object storage
CURRENT CONFIGURATION: Local Volume Mounts
EXPECTED LIMIT: 1 Machine (No multi-node scaling without S3/NFS)
EVIDENCE: docker-compose.yml volume mounts, ArtifactManager configuration

RESOURCE: FFmpeg processing
CURRENT CONFIGURATION: CPU-bound
EXPECTED LIMIT: 100% CPU exhaustion with >2 concurrent render jobs
EVIDENCE: Lack of GPU mapping in docker-compose.yml
`

---

## 5. User-Capacity Categories

### Concurrent authenticated users
`	ext
Estimated/verified: 0
Evidence: No authentication middleware exists in \main.py\.
Confidence: HIGH
`

### Concurrent active API users
`	ext
Estimated/verified: ~10
Evidence: DB pool limits active API query concurrency.
Confidence: HIGH
`

### Concurrent video-processing users
`	ext
Estimated/verified: 4
Evidence: Celery concurrency limit.
Confidence: HIGH
`

### Concurrent AI-generation users
`	ext
Estimated/verified: 4
Evidence: Celery concurrency limit.
Confidence: HIGH
`

### Concurrent dubbing users
`	ext
Estimated/verified: 4
Evidence: Celery concurrency limit.
Confidence: HIGH
`

### Concurrent publishing users
`	ext
Estimated/verified: 4
Evidence: Celery concurrency limit.
Confidence: HIGH
`

---

# 6. Load-Test Requirement

NO VERIFIED USER CAPACITY.

Given the CPU-bound nature of the video rendering and missing resource constraints in Docker, running an automated load test in the current local environment poses a high risk of exhausting host CPU/RAM resources and crashing the orchestration service. Capacity figures are configuration limits rather than verified benchmarks.

---

# 7. Domain / Public Internet Access

`	ext
HTTPS: NO
TLS termination: NO
reverse proxy: NO
CORS: Restricted to .env setting (e.g. localhost:3000)
authentication: NO
rate limiting: NO
request size limits: NO (FastAPI default)
upload limits: NO (FastAPI default)
WebSocket/SSE behavior: NO
public/private API routes: ALL PUBLIC
CSRF protection: NO
`

**Status:** LOCAL ONLY

The current deployment lacks an API gateway, rate limiters, reverse proxy (Nginx/Traefik), and TLS. Exposing this directly to the public internet will result in immediate denial-of-service vulnerability and unauthorized API consumption.

---

# 8. Horizontal Scaling

`	ext
HORIZONTALLY SCALABLE:
PARTIAL
`

**Why:** 
Scaling to multiple API instances or Celery workers on the *same machine* works flawlessly because TaskExecution and idempotency constraints properly lock concurrent execution via Postgres.
However, scaling across *multiple machines* is **BROKEN** because the ArtifactManager relies on local disk volume mounts (./uploads, ./outputs). Without migrating storage to S3/MinIO or an NFS share, files created by one worker node will be inaccessible to another.

---

# 9. Single-Server Capacity

`	ext
Current server: Single Node Docker Compose
Concurrent lightweight API users: ~10
Concurrent media-processing users: 4
Concurrent AI-processing users: 4
Concurrent long-running jobs: 4
`

CONNECTED USERS (viewing stats/dashboard): theoretically high (via async), but effectively limited to ~10 concurrent requests by the DB pool.
ACTIVE PROCESSING USERS: 4.

---

# 10. Domain User Capacity Summary

| Category                   | Capacity | Verified? | Limiting Resource | Confidence |
| -------------------------- | -------: | --------- | ----------------- | ---------- |
| Logged-in users            | 0        | N/A       | No Auth           | HIGH |
| Concurrent API users       | ~10      | NO        | DB Pool Size      | HIGH |
| Concurrent uploads         | ~10      | NO        | DB Pool / Async   | HIGH |
| Concurrent video jobs      | 4        | NO        | Celery Concurrency| HIGH |
| Concurrent AI jobs         | 4        | NO        | Celery Concurrency| HIGH |
| Concurrent dubbing jobs    | 4        | NO        | Celery Concurrency| HIGH |
| Concurrent publishing jobs | 4        | NO        | Celery Concurrency| HIGH |

---

# 11. Final Capacity Verdict

USER CAPACITY:
UNVERIFIED

---

# 12. Scaling Recommendation

`	ext
Current bottleneck:
Celery CPU concurrency (4) and Local Disk Volume mounts.

Next scaling step:
Increase worker replicas within docker-compose, and migrate ArtifactManager storage backend to S3/MinIO.

Expected architectural impact:
Medium (Requires MinIO service implementation inside StorageService)

Required database change:
none
`

---

PUBLIC DOMAIN USER CAPACITY:

The audit determines how many users the CURRENT implementation can support based on actual deployment configuration and verified load testing.

Connected users and processing users are reported separately.

No user-capacity number may be claimed without supporting evidence.
