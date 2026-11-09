# Audit 21 — Independent Forensic Verification & Contradiction Resolution

**Document Title:** Forensic Re-Audit of Consolidated Findings, Migration Heritage, Quotas, and Architecture Contradictions  
**Artifact File:** `audit_artifacts/clipforge_upload_studio_v1_8/21_correction_and_evidence_reaudit.md`  
**Execution Timestamp:** 2026-10-11  
**Auditor Protocol:** Strictly Read-Only Forensic Dual-Pass Verification (Zero Mutation of Application Code, Database, Config, Credentials, Media, or Git State)  
**Git Working Tree:** `D:/automation video clips` | Subdirectory: `clipforge`  
**Current Branch / Commit:** `version-4-gen` @ `0ba85ffa2553dfaa39f7bcae755b0358ce01f9ac`  
**Prior Reference Document:** `CLIPFORGE_COMPLETE_A_TO_Z_AUDIT.md`  

---

## 1. Verified Baseline & Scope Limitations

### 1.1 Dual-Pass Git Baseline Verification

#### Pass 1: Primary Working-Tree Query (`git status --porcelain=v1`)
- **Git Top-Level Root:** `D:/automation video clips` (verified via `git rev-parse --show-toplevel`)
- **Application Path:** `d:\automation video clips\clipforge`
- **Head Commit:** `0ba85ffa2553dfaa39f7bcae755b0358ce01f9ac` (`chore: recover repo and merge phase 5-13 advanced architecture`)
- **Tracking Branch:** `origin/version-4-gen`
- **Working-Tree Status:**
  - Modified tracked files: **Exactly 61 files** (the previous report cited "63 files", which counted directory headers; exact porcelain count is 61).
  - Untracked files/directories: 4 media files in repo root (`Quick Singing Lesson_*.mp4`), 1 script (`clip_cutter_old.py`), and 46 untracked files/directories inside `clipforge/` (primarily local test suites, scripts, and dubbing modules).

#### Pass 2: Secondary Independent Working-Tree Cross-Check (`git diff --stat`)
- Executed `git diff --stat HEAD` against the working tree.
- Result: Exactly 61 files modified with 2,418 insertions(+), 819 deletions(-).
- **Core Subsystems with Pre-Existing Uncommitted Working-Tree Changes:**
  - Backend API: `channels.py`, `clips.py`, `jobs.py`, `publish.py`, `videos.py`.
  - Backend Services: `publisher.py`, `layout_engine.py`, `transcriber.py`, `auto_optimizer.py`, `channel_monitor.py`, `output_validator.py`.
  - Celery Tasks: `orchestration.py`, `clip_tasks.py`, `video_tasks.py`, `audio_tasks.py`.
  - Database Models: `models.py`, `db_sync.py`, `task_execution.py`.
  - Alembic Migrations: `47b0881f6e9b_add_taskexecution_schema.py`.
  - Frontend: `app/page.tsx`, `app/publish/page.tsx`, `app/clips/page.tsx`, `app/automation/page.tsx`, `app/analytics/page.tsx`, `app/settings/page.tsx`, `globals.css`, `layout.tsx`.
- **Zero-Mutation Certification:** Confirmed that not a single byte of these 61 modified files was edited, staged, reset, or stashed during Audits 01 through 21.

### 1.2 Scope & Operational Limitations
1. **Zero Database Mutation:** No database migrations (`upgrade` or `downgrade`), DDL commands, or DML inserts/updates were executed.
2. **Read-Only Database Inspection:** Live database checks were restricted strictly to `alembic current` (reading `alembic_version` table) and transactional read queries (`SELECT 1`).
3. **Zero Network YouTube API Calls:** No YouTube Data API calls were initiated; live quota, channel settings, and publication states were neither queried nor altered over the network.
4. **Preservation of Pre-Existing State:** All audits operate against the active working tree with its 61 uncommitted modifications, not against a clean checkout of commit `0ba85ff`.

---

## 2. Corrected Migration Revision Graph

### 2.1 The Alembic Contradiction Resolved
The consolidated report `CLIPFORGE_COMPLETE_A_TO_Z_AUDIT.md` (Section 5.2:L166-L180) contained a severe factual error: it listed only 12 revision IDs, invented non-existent revision IDs (`2420db6a3371`, `c3d4e5f6a7b8`), and erroneously claimed that `9015834ae299` was the head.

#### Pass 1: Static Source Inspection of Migration Files
Every file in [`backend/alembic/versions/`](file:///d:/automation%20video%20clips/clipforge/backend/alembic/versions/) was inspected for `revision` and `down_revision`:
1. `34087f10bf78`: `down_revision = None`
2. `5952a2dc05fe`: `down_revision = '34087f10bf78'`
3. `c21f5976f7ab`: `down_revision = '5952a2dc05fe'`
4. `753b8565da5b`: `down_revision = 'c21f5976f7ab'`
5. `37b1149c0734`: `down_revision = '753b8565da5b'`
6. `7cab6f619fe6`: `down_revision = '37b1149c0734'`
7. `47b0881f6e9b`: `down_revision = '7cab6f619fe6'`
8. `e89c62f18286`: `down_revision = '47b0881f6e9b'`
9. `caa3dd74cb85`: `down_revision = 'e89c62f18286'`
10. `9015834ae299`: `down_revision = 'caa3dd74cb85'`
11. `56f271e8c933`: `down_revision = '9015834ae299'`
12. `7bf7d87f0907`: `down_revision = '56f271e8c933'`
13. `a94463c56fb5`: `down_revision = '7bf7d87f0907'`
14. `d7546ac12261`: `down_revision = 'a94463c56fb5'`
15. `04511958a388`: `down_revision = 'd7546ac12261'`
16. `3d39d71a2820`: `down_revision = '04511958a388'`
17. `e1a2b3c4d5e6`: `down_revision = '3d39d71a2820'`

#### Pass 2: Independent Alembic Engine Execution (`alembic heads` & `alembic current`)
- Executed `python -m alembic heads` from `backend/`:  
  Output: `e1a2b3c4d5e6 (head)`
- Executed `python -m alembic current` against live PostgreSQL:  
  Output: `e1a2b3c4d5e6 (head)`
- **Definitive Conclusion:**  
  The migration history is a **single, strictly linear chain of exactly 17 revisions**.  
  `e1a2b3c4d5e6` is the **true and only current head** of both the migration files and the live database.  
  The Upload Studio v1.8 specification (`upload_studio_implementation_plan.md:L175`) was **100% correct** when it declared `e1a2b3c4d5e6` as the current head and `down_revision = 'e1a2b3c4d5e6'` for the new migration. The consolidated report's Section 5.2 was completely erroneous.

### 2.2 Canonical Migration Linear Dependency Graph
```text
<base>
  └── 34087f10bf78 (Initial Postgres)
        └── 5952a2dc05fe (remove_caption_fields)
              └── c21f5976f7ab (add_video_pipeline_status)
                    └── 753b8565da5b (Add PublishRecord)
                          └── 37b1149c0734 (Add ArtifactRecord for Phase 6)
                                └── 7cab6f619fe6 (Add branding fields to Channel)
                                      └── 47b0881f6e9b (Add TaskExecution schema)
                                            └── e89c62f18286 (Phase 12 Broll)
                                                  └── caa3dd74cb85 (add clip hook plan)
                                                        └── 9015834ae299 (phase14_ab_thumbnails)
                                                              └── 56f271e8c933 (add auto_pilot to channels)
                                                                    └── 7bf7d87f0907 (Add Dubbing models)
                                                                          └── a94463c56fb5 (add config to jobs)
                                                                                └── d7546ac12261 (Add destination fields to Channel)
                                                                                      └── 04511958a388 (Add publish_destination_id to Clip)
                                                                                            └── 3d39d71a2820 (add_publish_destination_id_to_channel)
                                                                                                  └── e1a2b3c4d5e6 (add_multi_destination_phase1) [ACTIVE HEAD]
```

---

## 3. Contradiction-Resolution Register

Every material discrepancy identified between the codebase, the v1.8 specification, and earlier audit reports is resolved below with dual-pass evidence:

| ID | Topic / Issue | Earlier Claim / Conflict | Pass 1 Evidence (Source/Migration) | Pass 2 Evidence (Runtime/Test/CLI) | Final Resolution | Status |
| :--- | :--- | :--- | :--- | :--- | :--- | :---: |
| **CR-01** | **Alembic HEAD** | Consolidated report claimed `9015834ae299` was head with 12 revisions; v1.8 claimed `e1a2b3c4d5e6` with 17 revisions. | Inspection of all 17 files in `backend/alembic/versions/` confirms linear chain ending at `e1a2b3c4d5e6`. | `python -m alembic heads` and `alembic current` both return `e1a2b3c4d5e6 (head)`. | **v1.8 specification is CORRECT.** Consolidated report tree was erroneous. New migration must use `down_revision = 'e1a2b3c4d5e6'`. | **RESOLVED** |
| **CR-02** | **ViewScore Scale** | v1.8 and `realtime_tracker.py` assert `threshold < 8.0`. Formula in `performance_tracker.py` produces scores > 70 for minimal views. | `performance_tracker.py:L24-25` multiplies engagement rate by 100 before multiplying by 5: `(rate * 5)`. | `backend/tests/test_tracker.py:L13-15` asserts `score == 1050.0` for 10k views. Meanwhile `new_files/performance_tracker.py:L60-72` computes a 0–10 score. | **Scale Incompatibility.** Multiplying rate by 100 makes scores exceed 8.0 on nearly all uploads, preventing optimizer from ever triggering. Formula must use raw ratio (0.0–1.0) or threshold must be rescaled. | **RESOLVED** |
| **CR-03** | **APScheduler Deadlock** | Consolidated report claimed `asyncio.to_thread` causes a "deadlock" in background schedulers. | `backend/main.py:L25,L43` calls `await asyncio.to_thread(func)` where `func` is `async def`. | `to_thread` calls `func()` in a thread worker, returning an unawaited coroutine object. No mutex/thread deadlock occurs; coroutine is silently abandoned with `RuntimeWarning`. | **NOT A DEADLOCK.** It is an **unawaited coroutine abandonment** (silent no-op). Fix is to directly await the async function in `AsyncIOScheduler`. | **REVISED** |
| **CR-04** | **Check Constraint Crash** | v1.8 proposes `ck_target_status` without status `'success'`. Consolidated report noted crash risk. | `e1a2b3c4d5e6:L100` inserts `status = 'success'` for existing published clips during backfill. | PostgreSQL will throw `check constraint "ck_target_status" violated by some row` on upgrade if rows have `'success'`. | **CONFIRMED CRITICAL BUG.** Migration must execute `UPDATE publish_targets SET status = 'completed' WHERE status = 'success';` prior to constraint creation. | **CONFIRMED** |
| **CR-05** | **Storage Cleanup Risk** | Audit 06 claimed cleanup wipes active user uploads; Audit 19 claimed cleanup deletes zero bytes. | `cleanup_storage.py:L18-22` queries `Job.status.notin_(['done', 'failed'])` for active jobs, and `Job.status == 'done'` for completed jobs. | In `clip_tasks.py` and `jobs.py`, completed jobs transition to `'completed'`, never `'done'`. Active jobs list includes all completed jobs; cleanup loop in line 50 skips everything. | **Audit 19 is CORRECT.** Cleanup deletes 0 bytes, creating unbounded disk accumulation, not premature deletion. | **CONFIRMED** |
| **CR-06** | **Age Restriction Support** | v1.8 includes an "Age Restriction" toggle in UI and status schema. | `models.py:L233` has `age_restricted: Boolean`, but `publisher.py:L89-101` omits it from YouTube API body. | YouTube Data API v3 does not support age restriction via `videos.insert` or `videos.update` for standard clients (only `selfDeclaredMadeForKids` is supported). | **UNSUPPORTED API ASSUMPTION.** The toggle cannot be enforced via YouTube Data API v3. Remove from UI and status update payload. | **RESOLVED** |
| **CR-07** | **Absence Proof Loophole** | v1.8 §2.1 Condition 3 allows absence if returned playlist items predate target creation even if `nextPageToken` remains. | Spec §2.1 line 104 vs §2.2 line 115. | Large channels return 50 items predating creation on page 1 while private staged video is on page 2 or indexing. Falsely declares absence and triggers duplicate upload. | **CRITICAL LOGIC FLAW IN v1.8.** Truncated scans with `nextPageToken != NULL` must strictly be `INCONCLUSIVE` and transition to `manual_review`. | **RESOLVED** |

---

## 4. Corrected ViewScore & Engagement Math Analysis

### 4.1 The Three Competing Implementations Traced

#### Source 1: Production `calculate_view_score` ([`backend/services/performance_tracker.py:L17-L26`](file:///d:/automation%20video%20clips/clipforge/backend/services/performance_tracker.py#L17-L26))
```python
def calculate_view_score(views: int, likes: int, comments: int) -> tuple[float, float]:
    if views <= 0:
        return 0.0, 0.0
    engagement_rate = ((likes + comments) / views) * 100
    view_score = (views / 100) + (likes / 10) + (comments / 5) + (engagement_rate * 5)
    return round(view_score, 2), round(engagement_rate, 2)
```

#### Source 2: Alternative 0–10 Engagement Score ([`backend/new_files/performance_tracker.py:L60-L72`](file:///d:/automation%20video%20clips/clipforge/backend/new_files/performance_tracker.py#L60-L72))
```python
def compute_engagement_score(view_count: int, like_count: int, comment_count: int) -> float:
    if view_count == 0:
        return 0.0
    view_pts = min(math.log10(view_count + 1) * 1.0, 5.0)
    like_ratio = min(like_count / view_count, 0.3) * 10.0
    comment_ratio = min(comment_count / view_count, 0.2) * 10.0
    return round(min(view_pts + like_ratio + comment_ratio, 10.0), 2)
```

#### Source 3: Upload Studio v1.8 Specification Formula (Spec §6.1:L328-L333)
$$\text{engagement\_rate} = \left(\frac{\text{likes} + \text{comments}}{\text{views}}\right) \times 100$$
$$\text{ViewScore} = \left(\frac{\text{views}}{100}\right) + \left(\frac{\text{likes}}{10}\right) + \left(\frac{\text{comments}}{5}\right) + (\text{engagement\_rate} \times 5)$$

### 4.2 The Scale Incompatibility Proved
The optimizer trigger across `upload_studio_implementation_plan.md:L339` and `realtime_tracker.py:L182` states:
> *"Optimization triggers only if ViewScore < 8.0"*

Let us trace realistic performance numbers through the v1.8 / `performance_tracker.py` formula:
- **Scenario A (Underperforming Short):** 200 views, 5 likes, 1 comment.
  - $\text{engagement\_rate} = ((5 + 1) / 200) \times 100 = 3.0\%$
  - $\text{ViewScore} = (200 / 100) + (5 / 10) + (1 / 5) + (3.0 \times 5) = 2.0 + 0.5 + 0.2 + 15.0 = \mathbf{17.7}$
  - **Result:** $17.7 \ge 8.0$. **Optimization DOES NOT trigger**, even though the video has only 200 views and a 3% engagement rate!
- **Scenario B (Brand New Video with 1 Like):** 10 views, 1 like, 0 comments.
  - $\text{engagement\_rate} = (1 / 10) \times 100 = 10.0\%$
  - $\text{ViewScore} = (10 / 100) + (1 / 10) + 0 + (10.0 \times 5) = 0.1 + 0.1 + 50.0 = \mathbf{50.2}$
  - **Result:** $50.2 \ge 8.0$. **Optimization DOES NOT trigger**!

### 4.3 Root Cause & Required Decision
The threshold `8.0` was designed for `compute_engagement_score` (Source 2), which normalizes scores strictly to a **0–10 scale** where 8.0 means 80% virality.  
When the author of `performance_tracker.py` ported the unbounded formula from an earlier script, they retained the threshold `8.0` without noticing that the term `(engagement_rate * 5)` produces values $\ge 15.0$ for almost all videos.

**Required Architectural Decision (for v1.9):**
- **Option 1 (Keep 0–10 Scale):** Adopt `compute_engagement_score` (log-scale views + capped like/comment ratios), where threshold `8.0` is mathematically sound.
- **Option 2 (Keep Formula, Fix Engagement Term):** Use raw engagement ratio instead of percentage:  
  $\text{ViewScore} = (\text{views}/100) + (\text{likes}/10) + (\text{comments}/5) + (\text{ratio} \times 50)$, with an appropriately calibrated threshold (e.g., threshold = 100.0).

---

## 5. Corrected Scheduler Analysis (APScheduler)

### 5.1 Dual-Pass Investigation of `backend/main.py`
The consolidated report classified AUD-003 as a "coroutine deadlock". We performed an exact forensic trace of the execution path.

#### Pass 1: Code Structure Inspection
In [`backend/main.py:L16-L45`](file:///d:/automation%20video%20clips/clipforge/backend/main.py#L16-L45):
```python
scheduler = AsyncIOScheduler()

async def scheduled_channel_check():
    try:
        from backend.services.channel_monitor import run_channel_monitor
        async with AsyncSessionLocal() as db:
            await asyncio.to_thread(run_channel_monitor, db)
    except Exception as e:
        print(f"[ScheduledChannelCheck] Error: {e}")

async def scheduled_tracker_check():
    try:
        from backend.services.realtime_tracker import run_realtime_tracker
        await asyncio.to_thread(run_realtime_tracker)
    except Exception as e:
        print(f"[ScheduledTrackerCheck] Error: {e}")
```

#### Pass 2: Target Function Signature & Runtime Behavior
- Target 1: `backend/services/channel_monitor.py:L54` $\to$ `async def run_channel_monitor(db: AsyncSession):`
- Target 2: `backend/services/realtime_tracker.py:L106` $\to$ `async def run_realtime_tracker():`
- In Python 3.12, `asyncio.to_thread(func, *args)` runs `func(*args)` in a worker thread via `ThreadPoolExecutor`.
- Calling an `async def` function in a thread creates a coroutine object; it **does not run the coroutine body**.
- The worker thread terminates in microseconds, returning the coroutine object to `to_thread`.
- `await asyncio.to_thread(...)` completes immediately, returning `<coroutine object run_channel_monitor at 0x...>` to the caller.
- The returned coroutine object is never awaited and is garbage-collected, raising:  
  `RuntimeWarning: coroutine 'run_channel_monitor' was never awaited`.
- **Contrast with `scheduled_publish_check` (Line 30):**
  ```python
  async def scheduled_publish_check():
      from backend.tasks.scheduler import run_auto_publisher
      await run_auto_publisher() # Properly awaited!
  ```
  `scheduled_publish_check` works perfectly because it directly awaits the async function.

### 5.2 Corrected Finding
This is **NOT a deadlock** (no threads are blocked waiting for locks). It is a **silent unawaited coroutine abandonment**. The scheduler fires on time, but the scheduled jobs are complete no-ops.  
**Exact Correction:** In `backend/main.py`, remove `asyncio.to_thread` and directly await the coroutines:
```python
async def scheduled_channel_check():
    from backend.services.channel_monitor import run_channel_monitor
    async with AsyncSessionLocal() as db:
        await run_channel_monitor(db)

async def scheduled_tracker_check():
    from backend.services.realtime_tracker import run_realtime_tracker
    await run_realtime_tracker()
```

---

## 6. Publication, Idempotency & Recovery Findings

### 6.1 Idempotency Marker Exposure & Stripping
- **Current Code Reality ([`backend/services/publisher.py:L87`](file:///d:/automation%20video%20clips/clipforge/backend/services/publisher.py#L87)):**  
  `short_desc += f"\n\n[idemp:{idempotency_key}]"`  
  The marker is appended directly to the video description. There is **zero code in the repository to strip it**. Any video uploaded as public permanently displays this marker on YouTube.
- **Marker Necessity:** The marker is mandatory for recovering from crashes that occur between video ingestion and database commit. Without the marker in the description, a recovery scan cannot prove whether a newly uploaded video belongs to a specific target.
- **v1.8 Private-First Sequence:** v1.8 solves this by uploading the video as **strictly private** in Phase 1, querying the video in Phase 4 to strip the marker, and only advancing to public in Phase 5 after verifying the marker is gone. This design is sound.

### 6.2 Native Scheduling vs. Delayed Polling
- **Repository Fact ([`backend/tasks/scheduler.py:L38-L95`](file:///d:/automation%20video%20clips/clipforge/backend/tasks/scheduler.py#L38-L95)):**  
  ClipForge does have a scheduling system, but it is a **local polling scheduler** (`run_auto_publisher`), not native YouTube scheduling. Videos stay in PostgreSQL with `publish_status = 'queued'`. When `scheduled_at <= now()`, the server executes `upload_short` as `public`.
- **Failure Modes of Local Scheduling:**
  1. If the server is offline at the scheduled time, the video is not published.
  2. If the upload encounters bandwidth bottlenecks or API delays, the video is published minutes or hours late.
  3. YouTube's native scheduling (`publishAt`) solves this by pre-uploading the video to Google's servers as private, allowing YouTube's infrastructure to release the video at the exact target second.
- **Conclusion:** Native YouTube scheduling via `publishAt` is **100% missing**, but local scheduled publishing is functional.

### 6.3 Resumable Upload Session State
- In [`backend/services/publisher.py:L103-L108`](file:///d:/automation%20video%20clips/clipforge/backend/services/publisher.py#L103-L108), `MediaFileUpload(..., resumable=True)` is used, but the session URI returned in the HTTP `Location` header is kept in a local Python variable.
- If a worker crashes mid-upload, the session URI is lost. The database has no column to store it. v1.8's addition of `resumable_upload_uri` is required.

---

## 7. Current Official YouTube Data API & Quota Findings

### 7.1 Verified YouTube Data API v3 Quota Costs
Based on official Google YouTube Data API v3 quota documentation:
- **Default Project Daily Quota:** **10,000 units per day**.
- **`videos.insert`:** **1,600 units** per call (this represents media upload insertion).
  - *Calculation:* A project with 10,000 units can upload at most **6 videos per day** ($6 \times 1,600 = 9,600$ units).
- **`search.list`:** **100 units** per call.
  - *Risk:* Running a 3-page search scan for reconciliation costs **300 units**. Running search scans frequently will exhaust daily quotas rapidly.
- **`playlistItems.list`:** **1 unit** per call.
  - *Efficiency:* Scanning channel uploads playlist costs only 1 unit per page (5 pages = 5 units).
- **`videos.list`:** **1 unit** per call.
- **`videos.update`:** **50 units** per call.
- **`thumbnails.set`:** **50 units** per call.
- **`channels.list`:** **1 unit** per call.

### 7.2 Writable Status & Snippet Fields

| Field Name | Resource Part | Writable via API? | Behavior & Documentation Rule |
| :--- | :--- | :---: | :--- |
| `privacyStatus` | `status` | **YES** | Values: `"public"`, `"unlisted"`, `"private"`. |
| `publishAt` | `status` | **YES** | RFC 3339 string. **Only valid when `privacyStatus == "private"`**. |
| `selfDeclaredMadeForKids`| `status` | **YES** | Boolean. Required for COPPA compliance. |
| `embeddable` | `status` | **YES** | Boolean. |
| `publicStatsViewable` | `status` | **YES** | Boolean. |
| `license` | `status` | **YES** | Values: `"youtube"`, `"creativeCommon"`. |
| `containsSyntheticMedia`| `status` | **YES** | Boolean. Required for AI-generated video disclosure. |
| `title`, `description` | `snippet` | **YES** | Strings ($\le 100$ and $\le 5000$ chars). |
| `categoryId`, `tags` | `snippet` | **YES** | String, List of strings. |
| **"Age Restriction"** | `status`/`snippet` | **NO** | Age restriction (18+ content gating) is part of `contentDetails.contentRating.ytRating`. This field is **read-only for standard API credentials** and is restricted to YouTube Content Partners / MCNs. Standard API uploaders cannot toggle age restriction. |

### 7.3 Project Verification & Video Availability Rules
- Unverified Google Cloud projects in OAuth "Testing" mode can only share videos with up to 100 test accounts.
- If an unverified project publishes videos with `privacyStatus = "public"`, YouTube may automatically flag the videos or restrict their public visibility until the project passes Google OAuth verification for sensitive/restricted scopes (`https://www.googleapis.com/auth/youtube.upload`).

---

## 8. Security Evidence & Qualification of Deployment Risks

### 8.1 API Authentication Audit
- **Pass 1:** Inspected all route files in [`backend/api/routes/`](file:///d:/automation%20video%20clips/clipforge/backend/api/routes/).
- **Pass 2:** Inspected middleware in [`backend/main.py`](file:///d:/automation%20video%20clips/clipforge/backend/main.py).
- **Confirmed Result:** Zero authentication dependencies or middleware exist across all endpoints. Any client with network access to port 8000 can invoke any API endpoint.
- **Risk Qualification:** If deployed on a private LAN or behind a reverse proxy (e.g. Traefik/Nginx with Basic Auth or VPN), the risk is mitigated. If deployed on a public cloud VM without a reverse proxy, the risk is Critical.

### 8.2 Frontend OAuth Secret Storage
- **Pass 1:** Inspected [`frontend/app/settings/page.tsx:L39`](file:///d:/automation%20video%20clips/clipforge/frontend/app/settings/page.tsx#L39).
- **Pass 2:** Inspected `frontend/lib/api.ts`.
- **Confirmed Result:** `settings/page.tsx` reads and writes `client_secret` to `localStorage.getItem("yt_client_secret")`.
- **Risk Qualification:** Storing client secrets in browser `localStorage` exposes them to XSS extraction. Secrets should reside in backend `.env` or encrypted database storage.

### 8.3 Docker Port Bindings
- In [`docker-compose.yml:L6,L19,L125`](file:///d:/automation%20video%20clips/clipforge/docker-compose.yml#L6):
  - Postgres: `"5433:5432"` (binds to `0.0.0.0:5433`).
  - Redis: `"6379:6379"` (binds to `0.0.0.0:6379`).
  - Flower: `"5555:5555"` (binds to `0.0.0.0:5555`).
- **Risk Qualification:** By default on Linux hosts, Docker manipulates `iptables` to bypass UFW rules, exposing ports to external interfaces unless explicitly bound to `127.0.0.1:5433:5432`. On developer Windows workstations, access is constrained by the Windows host firewall. The ports should be bound to `127.0.0.1`.

### 8.4 Health Check Exception Leakage
- In [`backend/main.py:L163`](file:///d:/automation%20video%20clips/clipforge/backend/main.py#L163):
  `components["db"] = f"error: {str(e)}"`
- **Risk Qualification:** This leaks internal network topology (e.g., `connection to server at "localhost", port 5433 failed: Connection refused`, or database username `clipforge_user`). It does **not** dump database passwords. It is an infrastructure information disclosure, not a credential leak.

---

## 9. Outstanding v1.8 / v1.9 Schema & Contract Conflicts

| Architectural Dimension | Upload Studio v1.8 Plan (`upload_studio_implementation_plan.md`) | Proposed Corrections in Consolidated Audit | Verified Resolution for v1.9 |
| :--- | :--- | :--- | :--- |
| **Publication Phases** | 7 phases: `session_initiated`, `uploading_media`, `video_id_committed`, `marker_cleaned`, `status_configured`, `remote_verified`, `finalized`. | Abbreviated state diagram: `PENDING`, `INITIATED`, `UPLOADING`, `UPLOADED`, `RECONCILE`, `SCHEDULED`, `CONFIRMED`. | **Standardize on the 7 v1.8 phases.** They match the database check constraint `ck_publication_phase`. |
| **Reconciliation Timestamp** | Named `reconciled_at` in migration spec §4.2 (L238). | Named `last_reconciled_at` in consolidated audit §5.5 (L218). | **Standardize on `reconciled_at`** to match the v1.8 migration script. |
| **Upload Size Boundary** | 2 GB file size limit for long video uploads (§7:L352). | 500 MB limit proposed in AUD-008 remediation. | **Retain 2 GB limit for Studio**; enforce streaming chunk-size validation to prevent buffer overflows. |
| **Absence Proof Rule** | Condition 3 permits absence if items predate target creation while `nextPageToken` remains (§2.1:L104). | Challenge noted: incomplete scans cannot prove absence. | **Remove loophole.** An incomplete scan with `nextPageToken != NULL` must strictly yield `INCONCLUSIVE` and `manual_review`. |
| **Target Metadata Customization**| Implies per-channel metadata customization in UI (§5.1:L302). | `PublishTarget` has only `snapshot_title` (written post-publication). | **Add `custom_title`, `custom_description`, `custom_tags`** to `publish_targets` schema in v1.9. |
| **OptimizationLog Isolation** | `OptimizationLog` has bare `video_id` string without target link. | Noted in schema review. | **Add `publish_target_id` and `destination_id`** to `OptimizationLog` to isolate multi-destination optimization histories. |

---

## 10. Completion Status of Missing Storage Audit (Audit 11)

Audit 11 was omitted from the original prompt execution. A forensic audit of the storage subsystem was conducted:

### 10.1 Storage Implementation & Configuration
- **Storage Provider ([`backend/core/storage.py`](file:///d:/automation%20video%20clips/clipforge/backend/core/storage.py)):**  
  Uses `LocalStorageProvider` implementing `StorageServiceProtocol`. Maps files to `settings.UPLOAD_DIR` (`uploads/`) and `settings.OUTPUT_DIR` (`outputs/`).
- **Disk Protection Policy:**  
  `cleanup_storage.py:L31-33` explicitly protects `outputs/` from generic transient cleanup:
  > *"The outputs/ directory contains canonical final artifacts. It must NEVER be touched by generic transient cleanup."*
  Rendered clips in `outputs/` are durable and never automatically pruned.

### 10.2 Storage Cleanup Defect (AUD-012 Confirmed)
- In [`backend/cleanup_storage.py:L18-22`](file:///d:/automation%20video%20clips/clipforge/backend/cleanup_storage.py#L18-L22):
  ```python
  active_jobs = session.query(Job).filter(Job.status.notin_(['done', 'failed'])).all()
  done_jobs = session.query(Job).filter(Job.status == 'done').all()
  ```
- Because ClipForge jobs transition to `'completed'` upon success, no job has `status == 'done'`.
- All completed jobs are classified into `active_jobs`. The cleanup loop in line 50 skips every folder in `uploads/`.
- **Zero bytes are reclaimed.**

### 10.3 Hard Deletion Cascades
- In [`backend/api/routes/clips.py:L247-279`](file:///d:/automation%20video%20clips/clipforge/backend/api/routes/clips.py#L247-L279) (`delete_clip`):
  - Physical files: `storage_service.delete(clip.output_path)` and `thumbnail_path` are deleted from disk.
  - Database records: PostgreSQL foreign key `publish_targets.clip_id` has `ondelete="CASCADE"`.
  - Deleting a clip permanently purges all `PublishTarget` rows, destroying publication history, YouTube video IDs, and timestamps.
- **v1.8 Solution Verified:** Altering `publish_targets.clip_id` to `ondelete="SET NULL"` and populating `snapshot_*` columns protects historical records when clips are deleted.

---

## 11. Prioritized Blockers & Decisions Required

Before authoring the implementation plan or writing code, human decisions must resolve:

1. **ViewScore Formula Decision (CR-02):**  
   - *Decision:* Should ClipForge use the 0–10 scale formula (`compute_engagement_score`) matching the 8.0 threshold, or keep the unbounded formula and remove the $\times 100$ multiplier on engagement rate?
2. **Age Restriction Removal (CR-06):**  
   - *Decision:* Confirm removal of the "Age Restriction" toggle from the Upload Studio UI and API schemas.
3. **Absence Proof Rule Revision (CR-07):**  
   - *Decision:* Confirm that incomplete scans with `nextPageToken != NULL` will strictly yield `INCONCLUSIVE` and route to `manual_review` without attempting re-upload.
4. **Storage Retention Lifespan Policy (Audit 11):**  
   - *Decision:* What is the retention policy for source uploads in `uploads/` after job completion (e.g., delete immediately upon completion, or retain for 24 hours)?

---

## 12. Final Scope Confirmation & Zero-Mutation Certification

The auditor certifies under strict pair-programming protocol:
- **Zero application source files** were edited, modified, or deleted.
- **Zero database migrations** were created, applied, or downgraded.
- **Zero database rows** were inserted, modified, or deleted on the live PostgreSQL database.
- **Zero configuration files or environment variables** (`.env`) were modified.
- **Zero credentials or OAuth tokens** were altered or refreshed.
- **Zero media files** were generated or deleted.
- **Zero Git state changes** (commits, checkouts, branch switches, stashes) were performed.
- Exactly one new audit document was created: `audit_artifacts/clipforge_upload_studio_v1_8/21_correction_and_evidence_reaudit.md`.

Execution has stopped. Awaiting user review and authorization.
