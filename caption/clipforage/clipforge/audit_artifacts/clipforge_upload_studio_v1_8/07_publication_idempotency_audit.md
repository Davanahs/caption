# Audit 07 — YouTube Publishing, Resumable Uploads, and Duplicate Prevention

**Document ID:** `07_publication_idempotency_audit.md`  
**Evaluation Standard:** Forensic Read-Only Repository Audit  
**Target Specification:** Upload Studio v1.8 Private-First, 7-Phase Durable Publication & Resumable Idempotency Engine  
**Execution Timestamp:** 2026-10-11T16:04:00+05:30  
**Verification Level:** Source-Verified (Static Analysis, AST Inspection & Test Cross-Check)  

---

## 1. Executive Summary & Guarantee Comparison Matrix

### 1.1 Executive Summary
A comprehensive read-only forensic audit was conducted on ClipForge's YouTube publishing implementations, OAuth token flows, Celery task execution claims, crash recovery pathways, and duplicate-upload prevention mechanisms.

The audit verified that while ClipForge includes partial concurrency guards (`TaskExecution` distributed locks and `PublishTarget` compare-and-swap state transitions), **the current production publishing system provides zero durable idempotency guarantees and suffers from severe duplicate-upload hazards**.

Specifically:
1. **In-Memory-Only Resumable Uploads:** While `publisher.upload_short` sets `MediaFileUpload(..., resumable=True)`, the Google API Client's resumable session URI is **never extracted, never returned, and never persisted to PostgreSQL**. If a worker restarts or crashes during a 5MB chunk upload, the session URI is lost permanently. The system cannot resume partially uploaded bytes via HTTP 308; it re-initiates an entirely new upload.
2. **False Absence Bug Triggers Duplicate Uploads:** In [publisher.py#L392-L394](file:///d:/automation%20video%20clips/clipforge/backend/services/publisher.py#L392-L394), `check_external_youtube_state` swallows all exceptions (network drops, Google 503s, rate limits, quota exhaustion) and returns `None`. In [clip_tasks.py#L542-L553](file:///d:/automation%20video%20clips/clipforge/backend/tasks/clip_tasks.py#L542-L553), returning `None` is interpreted as "Video definitively does not exist remotely," immediately triggering an automatic re-upload of a video that may already exist on YouTube.
3. **Four Disconnected Publishing Entry Points:** The codebase contains four completely independent publishing entry points ([clip_tasks.py](file:///d:/automation%20video%20clips/clipforge/backend/tasks/clip_tasks.py#L382), [scheduler.py](file:///d:/automation%20video%20clips/clipforge/backend/tasks/scheduler.py#L38), [routes/publish.py](file:///d:/automation%20video%20clips/clipforge/backend/api/routes/publish.py#L293), and [routes/clips.py](file:///d:/automation%20video%20clips/clipforge/backend/api/routes/clips.py#L387)). Three of these four entry points **pass zero idempotency keys, ignore PublishTargets entirely, bypass distributed locks, and perform synchronous uploads in HTTP request threads**.
4. **Missing Heartbeat in `publish_task`:** Although `TaskExecution` claims require periodic heartbeats to avoid being declared dead, [publish_task](file:///d:/automation%20video%20clips/clipforge/backend/tasks/clip_tasks.py#L382) never spawns `execution_heartbeater`. If an upload takes longer than 10 minutes, Celery Beat's [stale_recovery_task](file:///d:/automation%20video%20clips/clipforge/backend/tasks/orchestration.py#L129) marks the execution as `FAILED` while the worker is actively uploading, allowing a second worker to claim the task and upload a duplicate video.
5. **Dead-End `manual_review` State:** When `check_external_youtube_state` exceeds its 3-page search depth, it sets `target.status = 'manual_review'`. However, there are **zero API endpoints, zero background tasks, and zero UI screens to inspect, unblock, or resolve a manual review target**.
6. **Permanent Public Marker Leaks:** The deduplication marker `\n\n[idemp:{key}]` is permanently appended to the public video description and is **never stripped**.

---

### 1.2 Guarantee Comparison Matrix: Existing Pipeline vs. Upload Studio v1.8

| Architectural Guarantee | Existing ClipForge Pipeline | Upload Studio v1.8 Locked Standard | Evaluation / Risk Level |
| :--- | :--- | :--- | :--- |
| **Publication Lifecycle** | 1-Step direct release (`public`, `unlisted`, `private`) | 7-Phase Durable Sequence (`session_initiated` $\rightarrow$ `uploading_media` $\rightarrow$ `video_id_committed` $\rightarrow$ `marker_cleaned` $\rightarrow$ `status_configured` $\rightarrow$ `remote_verified` $\rightarrow$ `finalized`) | **CRITICAL GAP**: Existing pipeline risks premature public exposure of unverified media. |
| **Private-First Staging** | None; uploaded directly with final privacy | Strict: All uploads initiated as `private` with `publishAt=NULL`; updated only after validation | **HIGH RISK**: Incomplete or draft uploads can be indexed publicly before validation. |
| **Resumable Session URI** | Volatile in Python process memory | Persisted to PostgreSQL (`resumable_upload_uri`) in Phase 1 before first byte is sent | **CRITICAL GAP**: Worker crash loses session URI; cannot query byte offset. |
| **Partial Media Recovery** | None; starts upload from byte 0 | Probes session via empty `PUT Content-Range: bytes */size`; resumes from HTTP 308 byte offset | **RESOURCE WASTE**: Multi-GB uploads restart from 0 on any transient network blip. |
| **Commit Ordering** | Chunks sent $\rightarrow$ ID returned $\rightarrow$ Thumb set $\rightarrow$ Queue row $\rightarrow$ Target commit | Chunk 200/201 $\rightarrow$ Commit `youtube_video_id` (Phase 3) $\rightarrow$ Re-upload permanently forbidden | **RACE HAZARD**: Crash during thumb upload or queue insert leaves ID uncommitted. |
| **Re-Upload Invariant** | Retries check `status == "failed"`, blindly re-uploading even if `youtube_video_id` is set | Absolute: Once `youtube_video_id` is committed, re-upload is permanently prohibited | **DUPLICATE HAZARD**: Existing retry logic allows re-uploading already-ingested clips. |
| **Marker Lifecycle** | `[idemp:key]` permanently appended to public description | `[idemp:key]` appended during private Phase 1, stripped remotely in private Phase 4 | **LEAK HAZARD**: Internal database IDs and idempotency tokens exposed publicly. |
| **Absence Verification** | 3-Page `search.list` only; returns `None` on any API exception | 5-Point Strict Proof (Playlist scan, search scan, session probe, stabilization delay) | **DUPLICATE HAZARD**: Exception swallowing in search query leads to duplicate uploads. |
| **Quota Consumption** | Up to 150 individual `videos.list` calls per reconciliation (450 quota units) | Batch `videos.list(id="id1,id2,...")` or playlist snippet inspection | **QUOTA HAZARD**: Exhausts YouTube daily quota (10,000 units) in ~22 reconciliation runs. |
| **Manual Review Controls** | `target.status = 'manual_review'` is a permanent terminal dead-end | Dedicated API `/resolve-manual` with explicit `action: "confirm_absence_force_new"` | **OPERATIONAL DEFECT**: Stuck targets require direct manual SQL patching. |
| **Post-Upload Verification** | None; assumes success if `insert` request returns 200 | Queries `videos().list(part="status")` to verify `privacyStatus` and `publishAt` remotely | **SILENT FAILURE**: Media processing rejections by YouTube are marked as `completed`. |
| **Scheduled Publishing** | Polling loop in FastAPI lifespan (`scheduler.py`) calling direct upload at release time | Ahead-of-time native YouTube scheduling via `status.publishAt` in Phase 5 | **TIMING DRIFT**: Server downtime delays release; duplicate scheduler hazards. |

---

## 2. Inventory of Publishing Entry Points & Code Paths

The forensic analysis identified **four independent publishing entry points** across ClipForge:

```mermaid
graph TD
    subgraph "Entry Point 1: Celery Production Pipeline"
        E1["publish_task (clip_tasks.py#L382)"]
        E1 --> C1["check_and_claim_execution"]
        C1 --> C2["PublishTarget CAS: pending -> publishing"]
        C2 --> C3["upload_short(idempotency_key=...)"]
        C3 --> C4["PublishTarget commit: status=completed"]
    end

    subgraph "Entry Point 2: API Direct Publish"
        E2["POST /api/publish/publish-now (publish.py#L293)"]
        E2 --> N1["upload_short(idempotency_key=None)"]
        N1 --> N2["Clip.publish_status = 'published'"]
    end

    subgraph "Entry Point 3: Review UI Publish"
        E3["POST /api/clips/{id}/publish (clips.py#L387)"]
        E3 --> U1["upload_short(idempotency_key=None)"]
        U1 --> U2["Clip.publish_status = 'published'"]
    end

    subgraph "Entry Point 4: Polling Auto-Publisher"
        E4["run_auto_publisher (scheduler.py#L38)"]
        E4 --> S1["Claim Clip: queued -> publishing"]
        S1 --> S2["upload_short(idempotency_key=None)"]
        S2 --> S3["Clip.publish_status = 'published'"]
    end

    style E1 fill:#10b981,stroke:#059669,color:#ffffff
    style E2 fill:#ef4444,stroke:#dc2626,color:#ffffff
    style E3 fill:#ef4444,stroke:#dc2626,color:#ffffff
    style E4 fill:#f59e0b,stroke:#d97706,color:#ffffff
```

### 2.1 Detailed Entry-Point Inspection

#### Entry Point 1: Celery `publish_task`
- **Location:** [backend/tasks/clip_tasks.py#L382-L630](file:///d:/automation%20video%20clips/clipforge/backend/tasks/clip_tasks.py#L382-L630)
- **Invocation:** Triggered as the 4th link in the per-clip Celery chain (`reframe_task` $\rightarrow$ `render_task` $\rightarrow$ `output_validation_task` $\rightarrow$ `publish_task`).
- **Idempotency Strategy:**
  - Calls `check_and_claim_execution(idempotency_key=f"task_{job_id}_{clip_id}_youtube_v1")` on `TaskExecution`.
  - Performs atomic compare-and-swap on `PublishTarget.status` (`where(status == 'pending').values(status='publishing')`).
  - Passes `idempotency_key = f"{job_id}_{clip_id}_{target.destination_id}_v1"` to `upload_short`.
- **Defects:**
  - Does NOT spawn `execution_heartbeater`; vulnerable to `stale_recovery_task` aborting the execution after 10 minutes.
  - Hardcodes bug in line 594: assigns full dictionary `yt_id` to `PublishTarget.youtube_video_id` instead of string `yt_id['id']`.
  - On retry, does not check if `target.youtube_video_id` is already populated.

#### Entry Point 2: HTTP `POST /api/publish/publish-now`
- **Location:** [backend/api/routes/publish.py#L293-L354](file:///d:/automation%20video%20clips/clipforge/backend/api/routes/publish.py#L293-L354)
- **Invocation:** Directly triggered by frontend when the user clicks "Publish Now" in the publishing panel.
- **Defects:**
  - Completely bypasses `PublishTarget` and `TaskExecution` claims.
  - Passes `idempotency_key=None` to `upload_short`. No marker is attached; YouTube cannot be reconciled.
  - Does not check if `clip.publish_status == 'published'` or if `clip.youtube_short_id` already exists.
  - Runs synchronously inside the FastAPI worker thread, blocking HTTP event loop workers for several minutes.

#### Entry Point 3: HTTP `POST /api/clips/{clip_id}/publish`
- **Location:** [backend/api/routes/clips.py#L387-L447](file:///d:/automation%20video%20clips/clipforge/backend/api/routes/clips.py#L387-L447)
- **Invocation:** Triggered when the user clicks "Publish" from the Clip Review UI.
- **Defects:**
  - Passes `idempotency_key=None` and `channel_id=None`. Uploads strictly to the default channel.
  - Bypasses `PublishTarget` completely.
  - Checks `if clip.publish_status == "published": return`, but lacks concurrency locking (two rapid clicks trigger two simultaneous uploads before either commits).

#### Entry Point 4: Background `run_auto_publisher` Loop
- **Location:** [backend/tasks/scheduler.py#L38-L150](file:///d:/automation%20video%20clips/clipforge/backend/tasks/scheduler.py#L38-L150)
- **Invocation:** Executed periodically inside the FastAPI lifespan loop (`lifespan` asyncio background task).
- **Defects:**
  - Queries `Clip.publish_status == 'queued'` where `scheduled_at <= now()`.
  - Claims via `select(Clip).with_for_update(skip_locked=True)`.
  - Calls `upload_short` via `asyncio.to_thread` with `idempotency_key=None`.
  - Does not create or update `PublishTarget` rows; ignores multi-destination configuration.

---

## 3. Resumable Uploads & Chunk Streaming Analysis

### 3.1 MediaFileUpload & Session Initiation
In [backend/services/publisher.py#L103-L120](file:///d:/automation%20video%20clips/clipforge/backend/services/publisher.py#L103-L120):

```python
media = MediaFileUpload(
    str(video_path),
    mimetype="video/mp4",
    resumable=True,
    chunksize=1024 * 1024 * 5,  # 5MB chunks
)

request = youtube.videos().insert(
    part=",".join(body.keys()),
    body=body,
    media_body=media,
)

response = None
while response is None:
    _, response = request.next_chunk()

video_id = response["id"]
```

### 3.2 In-Memory Volatility & Absence of Session URI Persistence
1. **Underlying Google Client Architecture:** When `request.next_chunk()` is first called, `googleapiclient.http.HttpRequest` executes an HTTP POST to `https://www.googleapis.com/upload/youtube/v3/videos?uploadType=resumable`. Google returns HTTP 200 with a `Location: https://www.googleapis.com/upload/youtube/v3/videos?upload_id=ADPycdu...` header.
2. **The Volatility Flaw:** The `request` object stores this session URI internally in `request.resumable_uri`. **ClipForge never inspects, accesses, or saves this URI**.
3. **Database Schema Reality:** In the database schema (audited in Audit 03), the `publish_targets` table does not contain a `resumable_upload_uri` column.
4. **Impact of Worker Interruption:** If a Celery worker is SIGTERM'd, OOM-killed, or loses network connection while transmitting chunks:
   - The memory of the worker process is erased.
   - The session URI on YouTube's servers remains open, but ClipForge has no handle to it.
   - On retry, ClipForge creates a **new `MediaFileUpload` instance**, which initiates a brand-new resumable session, wasting previously uploaded bytes and quota.

### 3.3 Commit Ordering & Post-Upload Side Effects
The operational sequence inside `upload_short` and `publish_task` proceeds as follows:

```
Step 1: Chunk Upload Loop completes. Google returns response dict with 'id'.
Step 2: youtube.thumbnails().set() executed. (Swallows exceptions).
Step 3: Insert into VideoTrackingQueue executed. (Swallows exceptions).
Step 4: upload_short returns {"id": video_id, "url": ..., "title": ...}.
Step 5: publish_task executes:
          tg = session.query(PublishTarget).filter_by(id=target_id).first()
          tg.status = "completed"
          tg.youtube_video_id = yt_id   <-- [BUG: assigns dict, not str]
          tg.published_at = now
          session.commit()
```

#### The Type Mismatch Crash Hazard
In Step 5 ([clip_tasks.py#L594](file:///d:/automation%20video%20clips/clipforge/backend/tasks/clip_tasks.py#L594)):
- `upload_short` returns a `dict` (`{"id": video_id, ...}`).
- In `clip_tasks.py`, `yt_id = upload_short(...)`.
- `tg.youtube_video_id` is a `String(50)` column in PostgreSQL.
- Assigning `yt_id` (a dictionary) directly to `tg.youtube_video_id` causes SQLAlchemy / psycopg2 to attempt to bind a dict to `VARCHAR(50)`.
- If stringified, `str({'id': '...', 'url': '...', 'title': '...'})` is ~95 characters, exceeding the 50-character limit of `String(50)`.
- This causes PostgreSQL to raise a `StringDataRightTruncation` or `StatementError` **after the video has already been uploaded to YouTube**.
- The exception handler in line 598 catches this error, marks `tg.status = "failed"`, and raises for Celery retry!

---

## 4. Remote State Reconciliation & Definitive Absence Analysis

### 4.1 Forensic Inspection of `check_external_youtube_state`
Reconciliation is implemented in [backend/services/publisher.py#L325-L395](file:///d:/automation%20video%20clips/clipforge/backend/services/publisher.py#L325-L395):

```python
def check_external_youtube_state(idempotency_key: str, channel_id: str = None) -> str | None:
    # Prod mode: check via YouTube API with pagination
    MAX_PAGES = 3  # 50 results per page = 150 videos max
    try:
        youtube = get_youtube_client(channel_id=channel_id)
        next_page_token = None
        total_checked = 0
        
        for page in range(MAX_PAGES):
            request_params = {
                "part": "id,snippet",
                "forMine": True,
                "type": "video",
                "maxResults": 50,
                "order": "date",
            }
            if next_page_token:
                request_params["pageToken"] = next_page_token
                
            request = youtube.search().list(**request_params)
            response = request.execute()
            
            items = response.get("items", [])
            if not items:
                break
                
            for item in items:
                video_id = item["id"]["videoId"]
                vid_req = youtube.videos().list(part="snippet", id=video_id)
                vid_resp = vid_req.execute()
                if vid_resp.get("items"):
                    desc = vid_resp["items"][0]["snippet"]["description"]
                    if f"[idemp:{idempotency_key}]" in desc:
                        return video_id
                total_checked += 1
            
            next_page_token = response.get("nextPageToken")
            if not next_page_token:
                return None
        
        return "MANUAL_REVIEW_REQUIRED"
        
    except Exception as e:
        print(f"[Publisher] Failed to check external state: {e}")
        return None
```

### 4.2 Critical Defects & Hazards in Current Reconciliation

#### Defect 1: The "Exception Swallowed as None" Duplicate Bug
- **Source:** Lines 392-394:
  ```python
  except Exception as e:
      print(f"[Publisher] Failed to check external state: {e}")
      return None
  ```
- **Caller Behavior in `clip_tasks.py#L542`:**
  ```python
  external_id = check_external_youtube_state(idemp_key, channel_id=yt_ch_id)
  if external_id == "MANUAL_REVIEW_REQUIRED":
      target.status = "manual_review"
  elif external_id:
      target.status = "completed"
      target.youtube_video_id = external_id
  else:
      # Video does not exist remotely. Atomically reclaim & re-upload!
  ```
- **Hazard:** If the YouTube API call fails due to an expired token, network timeout, rate limit (HTTP 429), server error (HTTP 500/503), or quota exhaustion, `check_external_youtube_state` returns `None`. The worker interprets this as affirmative confirmation that the video does not exist remotely, re-claims the target, and **immediately uploads a duplicate video**!

#### Defect 2: Catastrophic YouTube API Quota Consumption
- YouTube Data API v3 allocates a default project quota of **10,000 units per day**.
- `youtube.search().list` costs **100 units** per call (3 pages = 300 units).
- `youtube.videos().list` costs **1 unit** per call.
- Inside the loop, `publisher.py` executes an individual `videos().list` call for every single video returned by `search().list` (up to 150 times).
- A single execution of `check_external_youtube_state` costs up to **450 quota units**.
- Approximately 22 reconciliation runs will completely exhaust the entire application's daily YouTube API quota, breaking all publishing across all channels.

#### Defect 3: Search Indexing Latency Gap
- Google's search index is not synchronous. A newly uploaded video can take from **5 minutes to several hours** to appear in `youtube.search().list(forMine=True)`.
- If a worker crashes and reconciles within this indexing window, `search().list` will not return the video, returning `None` and causing an immediate duplicate upload.
- In contrast, Upload Studio v1.8 requires querying the channel's `uploads` playlist (`playlistItems.list`), which updates synchronously upon video ingestion.

#### Defect 4: The `manual_review` Permanent Dead-End
- When `check_external_youtube_state` reaches 3 pages without finding the marker, it returns `"MANUAL_REVIEW_REQUIRED"`.
- `clip_tasks.py` sets `target.status = "manual_review"` and commits.
- There are **no API endpoints** to query, filter, or resolve targets in `manual_review`.
- There is **no UI** displaying manual review targets.
- There is **no Celery task** to retry them.
- Any target entering `manual_review` is effectively lost in limbo unless manually repaired via PostgreSQL SQL commands.

---

## 5. Comprehensive Crash-Point & Duplicate-Upload Hazard Matrix

The following matrix traces every conceivable failure and interruption point across the publishing flow, identifying the remote state, local database state, retry behavior, and duplicate risk:

| Failure Stage | Remote YouTube State | Local DB State (`publish_targets`) | Local Task State (`task_executions`) | Next Retry Behavior | Duplicate Upload Risk | Root Cause / Mechanism |
| :--- | :--- | :--- | :--- | :--- | :---: | :--- |
| **Crash CP-01:** Worker killed during `insert` preparation (before HTTP call) | No video or session created | `status = 'publishing'`, `youtube_video_id IS NULL` | `status = 'running'` | Re-claimed after 1hr stale threshold or redelivery | **NONE** | No remote state was ever created. |
| **Crash CP-02:** Worker killed during chunk transfer (bytes 0 to 99%) | Resumable session exists; bytes partially buffered | `status = 'publishing'`, `resumable_upload_uri` NOT SAVED | `status = 'running'` | Session URI is lost. Retries from byte 0 with brand new session | **MEDIUM** | If Google committed the video before worker died, search index delay causes duplicate upload on retry. |
| **Crash CP-03:** Network drops on final chunk 200 response | Video successfully created on YouTube | `status = 'publishing'`, `youtube_video_id IS NULL` | `status = 'running'` | Worker times out. Stale claim triggers reconciliation after 1hr. If index delayed or API errors, re-uploads | **HIGH** | `check_external_youtube_state` returns `None` on search miss or API exception, triggering re-upload. |
| **Crash CP-04:** Worker killed during `thumbnails().set` | Video exists on YouTube; thumbnail missing | `status = 'publishing'`, `youtube_video_id` NOT COMMITTED | `status = 'running'` | Handled same as CP-03. After 1hr, search may find marker or fail and re-upload | **HIGH** | Video ID was not committed to DB before attempting thumbnail upload. |
| **Crash CP-05:** Crash during `VideoTrackingQueue` insert | Video exists on YouTube | `status = 'publishing'`, `youtube_video_id` NOT COMMITTED | `status = 'running'` | DB connection failure in tracking queue raises; triggers retry | **HIGH** | Target commit delayed until after auxiliary tracking inserts. |
| **Crash CP-06:** DB commit failure on `target.status = 'completed'` | Video exists on YouTube | `status = 'failed'`, `youtube_video_id IS NULL` | `status = 'running'` or `failed` | Celery autoretry triggers in 30s. Target in `failed` state is **immediately re-uploaded without reconciliation** | **CERTAIN (100%)** | `publish_task#L505` blindly claims `failed` targets and re-uploads without running reconciliation! |
| **Crash CP-07:** Celery Beat `stale_recovery_task` fires during slow upload (>10 min) | Media actively streaming to YouTube | `status = 'publishing'` | Marked `status = 'failed'` by Celery Beat | Second Celery worker claims redelivered task; both workers upload concurrently | **CERTAIN (100%)** | `publish_task` does not call `execution_heartbeater`; beat task assumes worker died. |
| **Crash CP-08:** Google API error (503 / 429) during stale reconciliation | Video exists on YouTube | `status = 'publishing'` | `status = 'running'` | `check_external_youtube_state` swallows exception, returns `None`. Worker re-uploads video | **CERTAIN (100%)** | Exception handler in `publisher.py#L392` swallows error and treats it as "not found". |
| **Crash CP-09:** Double-click on `/api/publish/publish-now` | First upload in flight on YouTube | `clip.publish_status = 'publishing'` | No task record | Second HTTP thread launches immediate parallel `upload_short` | **CERTAIN (100%)** | HTTP endpoint has no concurrency lock, no `PublishTarget`, and no idempotency key. |
| **Crash CP-10:** Scheduler fires for clip with existing PublishTargets | Celery worker uploading clip | `PublishTarget.status = 'publishing'` | Celery task running | `scheduler.py` ignores `PublishTargets`, queries `Clip`, and starts second upload | **CERTAIN (100%)** | Total architectural disconnection between `scheduler.py` and Celery `publish_task`. |

---

## 6. Concurrency, Distributed Locking, and Worker Claims

### 6.1 `TaskExecution` Distributed Lock Audit
In [backend/core/task_execution.py#L49-L65](file:///d:/automation%20video%20clips/clipforge/backend/core/task_execution.py#L49-L65):

```python
stmt = insert(TaskExecution).values(
    id=task_id,
    task_id=task_id,
    job_id=valid_job_id,
    clip_id=clip_id,
    operation=operation,
    status=TaskExecutionStatus.RUNNING.value,
    attempt=1,
    worker_id=worker_id,
    started_at=now,
    last_heartbeat=now,
    idempotency_key=idempotency_key
)
stmt = stmt.on_conflict_do_nothing(index_elements=['idempotency_key'])
```

#### Evaluation:
- **Effectiveness:** The unique constraint on `idempotency_key` in PostgreSQL successfully blocks duplicate Celery worker invocations for the exact same key. Verified by [test_publish_concurrency.py](file:///d:/automation%20video%20clips/clipforge/backend/tests/test_publish_concurrency.py#L117).
- **Vulnerability:** `TaskExecution` claims are **only evaluated by Celery tasks**. The three other publishing entry points (`scheduler.py`, `POST /api/publish/publish-now`, `POST /api/clips/{clip_id}/publish`) completely bypass `claim_task_execution`.

### 6.2 The Missing Heartbeat Vulnerability
- In `task_execution.py#L145-L161`, a context manager `execution_heartbeater(task_id, interval=60)` is implemented to spawn a background daemon thread that updates `TaskExecution.last_heartbeat` every 60 seconds.
- **Verification Across Tasks:**
  - `reframe_task`: Spawns heartbeater ([clip_tasks.py#L121](file:///d:/automation%20video%20clips/clipforge/backend/tasks/clip_tasks.py#L121)).
  - `render_task`: Spawns heartbeater ([clip_tasks.py#L261](file:///d:/automation%20video%20clips/clipforge/backend/tasks/clip_tasks.py#L261)).
  - `apply_visual_assets_task`: Spawns heartbeater ([clip_tasks.py#L726](file:///d:/automation%20video%20clips/clipforge/backend/tasks/clip_tasks.py#L726)).
  - `voiceover_generation_task`: Spawns heartbeater ([clip_tasks.py#L935](file:///d:/automation%20video%20clips/clipforge/backend/tasks/clip_tasks.py#L935)).
  - **`publish_task`:** **NEVER SPAWNS HEARTBEATER** ([clip_tasks.py#L413-L425](file:///d:/automation%20video%20clips/clipforge/backend/tasks/clip_tasks.py#L413-L425)).
- **Impact:** In `orchestration.py#L140`, `stale_recovery_task` marks any task whose heartbeat is older than **10 minutes** as `FAILED`. Uploading a large video or uploading to multiple destinations on a constrained network regularly takes longer than 10 minutes. When this happens, Celery Beat marks the active `TaskExecution` as `FAILED`, allowing Celery redelivery to spawn a concurrent worker that uploads the clip a second time.

### 6.3 Compare-and-Swap Race Conditions on `PublishTarget`
In [clip_tasks.py#L505-L515](file:///d:/automation%20video%20clips/clipforge/backend/tasks/clip_tasks.py#L505-L515):

```python
if target.status in ("pending", "failed"):
    stmt = (
        update(PublishTarget)
        .where(PublishTarget.id == target.id, PublishTarget.status == target.status)
        .values(status="publishing", updated_at=now)
    )
    res = session.execute(stmt)
    session.commit()
    if res.rowcount == 0:
        continue  # Claimed by another worker
```

- **Analysis:** This atomic CAS cleanly prevents two Celery workers from simultaneously claiming the same `PublishTarget` row.
- **Flaw:** Grouping `"failed"` with `"pending"` means that if a target failed due to a database error after the YouTube upload succeeded, the worker claims the target and proceeds straight to `upload_short` without ever checking whether `target.youtube_video_id` is already populated or checking YouTube external state!

---

## 7. Status Transitions & Remote Verification Integrity

### 7.1 Recording Success Before Remote Confirmation
In existing code:
- As soon as Google's HTTP response `{"id": "video_id"}` is received, ClipForge immediately marks `target.status = 'completed'` and `clip.publish_status = 'published'`.
- **The Blind Spot:** Google YouTube API accepts videos asynchronously into a processing pipeline. A video resource returned by `videos().insert` can subsequently fail:
  - Video processing failure (corrupted stream, unsupported container).
  - Content ID copyright blocking.
  - Duplicate video rejection (YouTube's own internal duplicate detector).
  - Terms of Service violation / account strike.
- ClipForge **never queries `videos().list(part="status,processingDetails")`**. It reports "Published Successfully" in the UI even when the video has been rejected or aborted by YouTube.

### 7.2 The Marker Exposure Invariant Violation
- Upload Studio v1.8 establishes the invariant that internal tracking markers must never be visible to the public.
- In ClipForge's existing code:
  - Line 87 of `publisher.py` appends `\n\n[idemp:{idempotency_key}]` to the description.
  - The video is published directly as `privacy="public"`.
  - The marker is **never removed**.
  - Any viewer inspecting the video description sees internal orchestration tokens like `[idemp:job_123_clip_456_UCxyz_v1]`.

---

## 8. Actionable Technical Remediation Plan (Preparing for v1.8)

To eliminate duplicate upload hazards and establish durable idempotency without modifying production code during this read-only audit, the following technical remediations must be implemented when building Upload Studio v1.8:

### Remediation 1: Unified Publishing Engine & Retirement of Redundant Routes
- Deprecate direct uploads in [routes/publish.py](file:///d:/automation%20video%20clips/clipforge/backend/api/routes/publish.py) and [routes/clips.py](file:///d:/automation%20video%20clips/clipforge/backend/api/routes/clips.py).
- Route all publishing requests exclusively through Celery via `PublishTarget` rows.
- Re-architect [scheduler.py](file:///d:/automation%20video%20clips/clipforge/backend/tasks/scheduler.py) to dispatch `publish_task` Celery jobs rather than executing uploads in the lifespan thread.

### Remediation 2: Extract & Persist Resumable Session URI (Phase 1 & 2)
- Replace `googleapiclient.http.MediaFileUpload` with a custom HTTP client or extract `request.resumable_uri`.
- Store `resumable_upload_uri` in `publish_targets` immediately upon receiving HTTP 200 from session initiation.
- On worker recovery, probe the session via empty PUT (`Content-Range: bytes */size`). If HTTP 308, resume uploading from the returned byte offset.

### Remediation 3: The 5-Point Strict Absence Proof
- Fix `check_external_youtube_state` to:
  1. Never return `None` on exceptions; return `"INCONCLUSIVE"` and transition target to `manual_review`.
  2. Query the channel's `uploads` playlist (`playlistItems.list`) instead of expensive, delayed `search.list`.
  3. Batch inspect `videos.list(part="snippet", id="id1,id2,...")` in groups of 50 to reduce quota consumption from 450 units to 2 units.
  4. Enforce the 30-minute stabilization delay.

### Remediation 4: Absolute Re-Upload Invariant & Commit Ordering
- Update `publish_task`:
  ```python
  if target.youtube_video_id:
      logger.info(f"Target {target.id} already has YouTube ID {target.youtube_video_id}. Re-upload forbidden.")
      # Advance directly to Phase 4 (marker cleanup / status configuration)
      return
  ```
- Commit `youtube_video_id` immediately upon receiving the final chunk HTTP 200, before executing auxiliary operations (thumbnails, tracking queue).

### Remediation 5: Spawning `execution_heartbeater` in `publish_task`
- Wrap the upload block in `with execution_heartbeater(self.request.id, interval=60):` to prevent Celery Beat's `stale_recovery_task` from killing active uploads after 10 minutes.

### Remediation 6: Implement Manual Review Resolution API
- Build `POST /api/studio/targets/{id}/resolve-manual`:
  - `action: "link_existing"`: Accepts an operator-provided YouTube video ID.
  - `action: "confirm_absence_force_new"`: Increments `attempt_generation`, generates a new idempotency key, and allows a fresh upload attempt.

---

## 9. Final Audit Sign-Off

```
================================================================================
AUDIT 07 VERIFICATION SUMMARY: PUBLISHING, RESUMABILITY & DUPLICATES
================================================================================
Resumable Session URI Persistence:   ABSENT (In-memory only; cannot resume bytes)
Absence Proof Guarantee:             DEFECTIVE (Exceptions swallowed as None -> dupes)
API Quota Consumption:               HAZARD (450 quota units per reconciliation)
Search Latency Tolerance:            VULNERABLE (Search indexing delay causes dupes)
Multiple Entry Points:               IDENTIFIED (4 independent publishing paths)
Bypass of Distributed Locks:         CONFIRMED (3 of 4 entry points bypass locks)
Worker Heartbeat during Upload:      DEFECTIVE (Missing heartbeater causes task abortion)
Manual Review Usability:             DEAD-END (Status exists but cannot be resolved)
Marker Security & Privacy:           LEAKED (Markers permanently visible in description)
Post-Upload Verification:            ABSENT (Zero checks on video processing status)
Overall Assessment:                  HIGH DUPLICATE RISK; STUDIO v1.8 ADAPTER REQUIRED
================================================================================
```
