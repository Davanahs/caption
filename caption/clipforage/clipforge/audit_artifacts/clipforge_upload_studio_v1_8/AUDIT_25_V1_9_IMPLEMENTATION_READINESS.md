# ClipForge Audit 25: v1.9 Implementation-Readiness Gate

**Audit Execution Date:** 2026-10-11  
**Target Repository:** `d:\automation video clips\clipforge` | Branch: `version-4-gen` @ `0ba85ffa2553dfaa39f7bcae755b0358ce01f9ac`  
**Specification Under Audit:** `audit_artifacts/clipforge_upload_studio_v1_8/CLIPFORGE_UPLOAD_STUDIO_V1_9_SPEC.md`  
**Audit Protocol:** **STRICT READ-ONLY FORENSIC AUDIT** — Zero application code, migrations, database records, configuration, Docker resources, or Git history modified.

---

## Executive Summary & Overall Readiness Verdict

Audit 25 is an independent, forensic implementation-readiness evaluation of the Upload Studio v1.9 architecture specification. Across 8 core technical domains, this audit cross-examined every migration statement, state transition, concurrency guard, storage abstraction, and external API assumption against active codebase ground truth.

```
┌──────────────────────────────────────────────────────────────────────────────────────────────────┐
│                                AUDIT 25 READINESS GATE SUMMARY                                   │
├───────────────────────────────────┬───────────────┬──────────────────────────────────────────────┤
│ SUBSYSTEM / AUDIT DOMAIN          │ STATUS        │ KEY BLOCKING FINDINGS                        │
├───────────────────────────────────┼───────────────┼──────────────────────────────────────────────┤
│ 1. Migration & Schema Lineage     │ NO-GO (P0)    │ Missing backfills in upgrade(); corrupted     │
│                                   │               │ snapshot_video_id mapping; missing active FK.│
├───────────────────────────────────┼───────────────┼──────────────────────────────────────────────┤
│ 2. Publication State Machine      │ NO-GO (P0)    │ Phase 6 can bypass Phase 7 snapshot commit;   │
│                                   │               │ premature published_at on scheduled videos.  │
├───────────────────────────────────┼───────────────┼──────────────────────────────────────────────┤
│ 3. Sequential Worker & Watchdog   │ NO-GO (P0)    │ Stale workers continue running after watchdog│
│                                   │               │ timeout; Celery inspect timeout false death. │
├───────────────────────────────────┼───────────────┼──────────────────────────────────────────────┤
│ 4. Upload-Stream Concurrency      │ NO-GO (P0)    │ TOCTOU race in stream counting bypasses limit│
│                                   │               │ of 3; lock inversion deadlock hazard.        │
├───────────────────────────────────┼───────────────┼──────────────────────────────────────────────┤
│ 5. Storage Durability & Capacity  │ NO-GO (P0)    │ Paths bypass LocalStorageProvider; conflict  │
│                                   │               │ with cleanup_storage.py; fcntl on Windows.   │
├───────────────────────────────────┼───────────────┼──────────────────────────────────────────────┤
│ 6. YouTube Data API Contracts     │ CONDITIONAL   │ Official dedicated 100 call/day buckets noted│
│                                   │               │ but uploadLimitExceeded handling unbuffered. │
├───────────────────────────────────┼───────────────┼──────────────────────────────────────────────┤
│ 7. Project Regression & Security  │ NO-GO (P0)    │ Insecure fallback to global token in         │
│                                   │               │ publisher.py; unawaited coroutines in main.py│
├───────────────────────────────────┼───────────────┼──────────────────────────────────────────────┤
│ 8. Governance & Decision Alignment│ NO-GO (P1)    │ ViewScore formula scale uncalibrated;        │
│                                   │               │ retention grace period unconfirmed.          │
└───────────────────────────────────┴───────────────┴──────────────────────────────────────────────┘
```

**Overall Readiness Verdict: NO-GO.**  
Upload Studio v1.9 cannot be approved for implementation until the **7 Critical (P0) Blockers** and **7 High (P1) Defects** identified below are formally corrected in the specification and repository prerequisites.

---

## 1. Migration Completeness & Reversibility Audit

### Finding AUD25-MIG-01 (Severity: P0 - Critical Blocker)
- **Specification Section:** Section 3.2 (Documented Backfills) vs Section 3.3 (`f1b2c3d4e5f6_add_upload_studio_v1_9.py:upgrade()`).
- **Codebase Location:** `backend/alembic/versions/` (Lineage Head: `e1a2b3c4d5e6_add_multi_destination_phase1.py`).
- **Classification:** **Confirmed Fact**.
- **Description & Failure Scenario:**
  Section 3.2 documents five required pre-constraint backfills. However, the executable Python migration script in Section 3.3 omits two critical operations:
  1. **Backfill 4 (Populate Immutable Target Snapshots):** Completely missing from `def upgrade()`. If the migration runs, all existing completed targets will have `snapshot_title = NULL`, `snapshot_format_type = NULL`, `snapshot_video_id = NULL`, and `snapshot_channel_title = NULL`.
  2. **Backfill 5 (Legacy URL Video Studio Isolation):** Completely missing from `def upgrade()`. `videos.upload_batch_id`, `queue_position`, and `upload_status` are added via `op.add_column()`, but existing legacy rows are not explicitly sanitized.
- **Impact:** Irrecoverable loss of historical publication audit records; historical records fail snapshot completeness checks; potential cross-talk with Studio batch queries.
- **Minimum Required Correction:**
  Add the missing backfills directly into `def upgrade()` in Section 3.3 immediately before creating check constraints.
- **Verification Criteria:**
  Execute `alembic upgrade head` on a test database containing historical `publish_targets` and assert:
  `SELECT count(*) FROM publish_targets WHERE status = 'completed' AND snapshot_title IS NULL;` returns `0`.

---

### Finding AUD25-MIG-02 (Severity: P0 - Critical Blocker)
- **Specification Section:** Section 3.2 (Backfill 4 SQL Definition).
- **Codebase Location:** `backend/models/models.py:L101,L113,L228`.
- **Classification:** **Confirmed Fact**.
- **Description & Failure Scenario:**
  Backfill 4 specifies:
  ```sql
  UPDATE publish_targets pt
  SET 
      snapshot_title = COALESCE(c.title, 'Historical Publication'),
      snapshot_format_type = COALESCE(c.format_type, 'short'),
      snapshot_video_id = c.video_id,
      snapshot_channel_title = ch.channel_name
  FROM clips c
  LEFT JOIN channels ch ON pt.destination_id = ch.id
  WHERE pt.clip_id = c.id;
  ```
  In `backend/models/models.py:L101`:
  `video_id: Mapped[str] = mapped_column(String, nullable=False)`
  `c.video_id` is the internal UUID referencing the parent source video row in `videos`. It is **NOT** the published YouTube video ID!
  The actual published YouTube video ID is stored in `pt.youtube_video_id` (or legacy `c.youtube_short_id`).
- **Impact:** Backfill 4 writes internal database UUIDs (e.g., `e9800998-8f00-b204-d41d-ecf8427ed41d`) into `snapshot_video_id` instead of YouTube video IDs (e.g., `dQw4w9WgXcQ`), permanently corrupting immutable historical audit records and breaking external analytics integrations.
- **Minimum Required Correction:**
  Correct Backfill 4 to:
  ```sql
  snapshot_video_id = COALESCE(pt.youtube_video_id, c.youtube_short_id, 'UNKNOWN_HISTORICAL')
  ```
- **Verification Criteria:**
  Assert that for every backfilled row, `snapshot_video_id` matches an 11-character YouTube video ID or known legacy format, and does NOT match a UUID regex pattern.

---

### Finding AUD25-MIG-03 (Severity: P0 - Critical Blocker)
- **Specification Section:** Section 3.3 (`upgrade()`) vs Section 14.6.2.
- **Codebase Location:** `backend/models/models.py` (New Model Declarations).
- **Classification:** **Confirmed Fact**.
- **Description & Failure Scenario:**
  Section 14.6.2 specifies `upload_batches.active_video_id` as a "UUID foreign key to `videos.id` with `ondelete='SET NULL'`".
  However, in Section 3.3:
  1. `upload_batches` is created in Step 1c with `sa.Column('active_video_id', sa.String(length=36), nullable=True)` with **no foreign key constraint**.
  2. In Step 2, `videos` is altered with `fk_videos_upload_batch_id` pointing to `upload_batches.id`.
  3. No foreign key constraint is ever added from `upload_batches.active_video_id` to `videos.id`.
- **Impact:** Referential integrity is compromised. If a video row is deleted while active, `active_video_id` retains a dangling UUID, corrupting the batch state machine and stalling the sequential orchestrator.
- **Minimum Required Correction:**
  Because `upload_batches` and `videos` reference each other, create `upload_batches` first without the FK, alter `videos`, and then explicitly add:
  ```python
  op.create_foreign_key(
      'fk_upload_batches_active_video_id', 'upload_batches', 'videos',
      ['active_video_id'], ['id'], ondelete='SET NULL'
  )
  ```
  Ensure `downgrade()` drops `fk_upload_batches_active_video_id` before dropping either table.
- **Verification Criteria:**
  Delete a video row that matches `active_video_id`; assert PostgreSQL automatically sets `active_video_id = NULL` without error.

---

### Finding AUD25-MIG-04 (Severity: P1 - High)
- **Specification Section:** Section 3.3 (`upgrade()`).
- **Codebase Location:** `backend/alembic/versions/e1a2b3c4d5e6_add_multi_destination_phase1.py:L76-88`.
- **Classification:** **Confirmed Fact**.
- **Description & Failure Scenario:**
  In migration `e1a2b3c4d5e6`, Alembic queried distinct `publish_status` values and failed closed with `RuntimeError` if unrecognized statuses were detected.
  In Section 3.3, `upgrade()` applies `UPDATE ... SET status = 'completed' WHERE status = 'success'` and then immediately executes:
  ```python
  op.create_check_constraint(
      'ck_target_status', 'publish_targets',
      "status IN ('pending', 'publishing', 'scheduled', 'completed', 'completed_unlisted', 'completed_private', 'failed', 'manual_review')"
  )
  ```
  If any historical record contains an unexpected status (e.g., `'draft'`, `'queued'`, `'archived'`, or `NULL`), the migration crashes ungracefully with a PostgreSQL check constraint violation.
- **Impact:** Uncontrolled migration failure during deployment; partial schema state requiring manual database rollback.
- **Minimum Required Correction:**
  Add a fail-closed pre-validation check in `upgrade()`:
  ```python
  existing_statuses = conn.execute(sa.text("SELECT DISTINCT status FROM publish_targets;")).scalars().all()
  PERMITTED = {'pending', 'publishing', 'scheduled', 'completed', 'completed_unlisted', 'completed_private', 'failed', 'manual_review', 'success'}
  unknown = set(existing_statuses) - PERMITTED
  if unknown:
      raise RuntimeError(f"MIGRATION ABORT: Unrecognized publish_targets.status values: {unknown}")
  ```
- **Verification Criteria:**
  Inject a test row with `status = 'unknown_state'`; assert migration aborts with a descriptive `RuntimeError`.

---

### Finding AUD25-MIG-05 (Severity: P1 - High)
- **Specification Section:** Section 3.2 (Backfill 1) vs Section 3.3 (`downgrade()`).
- **Codebase Location:** `backend/alembic/versions/e1a2b3c4d5e6_add_multi_destination_phase1.py:L100`.
- **Classification:** **Architectural Inference**.
- **Description & Failure Scenario:**
  Migration `e1a2b3c4d5e6:L100` inserted `'success'` into `publish_targets.status`. `upgrade()` normalizes this with:
  `UPDATE publish_targets SET status = 'completed' WHERE status = 'success';`
  On downgrade, the specification drops `ck_target_status` but does not attempt to revert `'completed'` to `'success'`.
  This is the correct decision: reverting `'completed'` $\to$ `'success'` would corrupt legitimate completed records created under subsequent workflows. However, this one-way transformation is not explicitly documented as an irreversible data normalization.
- **Impact:** Misunderstanding during disaster-recovery rollback planning; attempts to write an automated reverse mapping could corrupt data.
- **Minimum Required Correction:**
  Explicitly document in Section 3.2 and Section 3.3 that `success` $\to$ `completed` is an irreversible one-way normalization that persists across downgrades.
- **Verification Criteria:**
  Assert that downgrade preserves `status = 'completed'` without data loss.

---

## 2. Publication State Machine & Crash Recovery Audit

### Finding AUD25-PUB-01 (Severity: P0 - Critical Blocker)
- **Specification Section:** Section 4.1, Section 4.2 (Crash-Recovery Matrix), Section 7.1.
- **Codebase Location:** `backend/tasks/clip_tasks.py:L540-615`.
- **Classification:** **Design Requirement**.
- **Description & Failure Scenario:**
  Section 4.1 defines Phase 6 as `remote_verified` and Phase 7 as `finalized`.
  In Section 4.2 (Crash in Phase 6), the specification states:
  *"Query remote status. Confirm desired state matches, advance target to terminal status, and set publication_phase = 'finalized'."*
  If an implementation sets `status = 'completed'` inside Phase 6 before Phase 7 snapshot fields are captured, or if an unhandled crash occurs between setting terminal status and setting `publication_phase = 'finalized'`, Phase 7 is bypassed.
- **Impact:** Terminal `completed` targets exist in the database with NULL snapshot metadata (`snapshot_title`, `snapshot_video_id`, etc.), violating the immutable audit guarantee.
- **Minimum Required Correction:**
  Mandate that terminal status (`completed`, `completed_unlisted`, `completed_private`, or `scheduled`), snapshot metadata capture, and `publication_phase = 'finalized'` MUST be committed in a **single atomic database transaction** in Phase 7. Phase 6 must transition strictly to `publication_phase = 'remote_verified'`.
- **Verification Criteria:**
  Simulate a worker crash immediately following Phase 6 remote verification; assert recovery resumes at Phase 7 and freezes snapshots atomically with terminal status.

---

### Finding AUD25-PUB-02 (Severity: P1 - High)
- **Specification Section:** Section 4.2, Section 6.3.2.
- **Codebase Location:** `backend/services/publisher.py`, `backend/services/realtime_tracker.py`.
- **Classification:** **Confirmed Fact**.
- **Description & Failure Scenario:**
  When a video is uploaded with ahead-of-time scheduling (`publishAt = scheduled_at`), YouTube stages the video as private. During this private window, YouTube's `snippet.publishedAt` contains the timestamp when raw bytes were received, NOT the scheduled release date.
  If the worker captures `snippet.publishedAt` into `publish_targets.published_at` upon upload completion:
  1. The video appears to the user and analytics as already published.
  2. `VideoTrackingQueue` begins monitoring and calculating `ViewScore` on an unreleased, private video.
- **Impact:** Telemetry pollution; automated optimization attempts triggered on zero-view private scheduled videos; false notifications to creators.
- **Minimum Required Correction:**
  Explicitly specify that for scheduled uploads (`scheduled_at > NOW()`), `publish_targets.published_at` MUST remain `NULL` and `publish_targets.status` MUST be `'scheduled'`. `published_at` is populated ONLY after a post-release polling task confirms `status.privacyStatus == 'public'`.
- **Verification Criteria:**
  Verify scheduled upload mock; assert `publish_targets.published_at IS NULL` and `publish_targets.status == 'scheduled'` upon Phase 7 completion.

---

### Finding AUD25-PUB-03 (Severity: P1 - High)
- **Specification Section:** Section 4.2, Section 5.1.
- **Codebase Location:** `backend/tasks/clip_tasks.py`.
- **Classification:** **Design Requirement**.
- **Description & Failure Scenario:**
  If a worker crashes during Phase 2 (Chunk streaming) and the resumable session returns HTTP 404/410, Section 5.1 invokes the 5-point absence proof.
  If the absence proof returns `INCONCLUSIVE` (e.g., search API returns 3 pages with `nextPageToken != NULL`), Section 5.1 transitions the target to `manual_review`.
  However, the specification does not state what happens if a user subsequently clicks "Retry" on a target in `manual_review` without resolving the remote YouTube state.
- **Impact:** If the user retries a target in `manual_review` without verifying YouTube Studio, the worker could initiate a second `videos.insert`, resulting in a duplicate public video on the creator's channel.
- **Minimum Required Correction:**
  Specify that retrying a target in `manual_review` requires explicit human resolution input (e.g., providing an existing YouTube video ID or confirming absolute absence in YouTube Studio) before unblocking Phase 1 re-initiation.
- **Verification Criteria:**
  Attempt `POST /api/publish/{id}/retry` on a target with `status = 'manual_review'`; assert request returns `HTTP 409 Conflict` unless accompanied by a confirmation flag.

---

## 3. Sequential Worker & Watchdog Correctness Audit

### Finding AUD25-SEQ-01 (Severity: P0 - Critical Blocker)
- **Specification Section:** Section 14.6.2, Section 14.6.4.
- **Codebase Location:** `backend/tasks/video_tasks.py`, `backend/tasks/celery_app.py`.
- **Classification:** **Architectural Inference**.
- **Description & Failure Scenario:**
  Section 14.6.4 specifies that if `processing_heartbeat` expires ($> 15\text{ min}$), the Celery Beat watchdog marks the active video as failed, clears `active_video_id`, and dispatches the next item.
  However, **the original worker task may still be running** (e.g., blocked on slow FFmpeg rendering or an unresponsive network call).
  The specification checks `execution_token` only in the completion callback (`on_batch_item_completed`).
  Therefore, the superseded worker continues executing, writes rendered output files to disk, and triggers downstream operations concurrently with the newly dispatched worker.
- **Impact:** Concurrent execution of multiple batch items; race conditions in shared disk directories (`outputs/`); duplicate FFmpeg processes exhausting host CPU and RAM.
- **Minimum Required Correction:**
  Implement **active lease fencing** inside `process_video_pipeline`:
  At every milestone boundary (e.g., before Whisper transcription, before video reframing, before FFmpeg export, before YouTube upload), the worker MUST query:
  ```sql
  SELECT execution_token FROM upload_batches WHERE id = :batch_id;
  ```
  If `execution_token != self.execution_token`, the worker MUST immediately abort, terminate any child subprocesses via `SIGTERM`, unlink temporary files, and exit cleanly.
- **Verification Criteria:**
  Inject a 20-minute artificial sleep into Worker 1; trigger watchdog recovery; assert Worker 1 aborts at its next milestone check and produces zero committed side effects.

---

### Finding AUD25-SEQ-02 (Severity: P1 - High)
- **Specification Section:** Section 14.6.4 (Scenario B).
- **Codebase Location:** Celery Broker Configuration.
- **Classification:** **Confirmed Fact**.
- **Description & Failure Scenario:**
  Section 14.6.4 states:
  *"The watchdog queries the Celery cluster inspect API. If no active task matches the `execution_token`: The video is transitioned to `status = 'failed'`..."*
  In production, Celery inspect calls (`app.control.inspect().active()`) rely on broker broadcast pings. Under heavy worker CPU utilization (e.g., 100% CPU during video encoding) or transient network latency, worker inspect responses frequently time out, returning an empty active task list for living workers.
- **Impact:** Healthy workers performing legitimate, intensive video encoding are falsely diagnosed as dead, triggering premature watchdog failover and dual-worker collisions.
- **Minimum Required Correction:**
  Never treat an empty Celery inspect response as definitive proof of worker death. Watchdog timeout must require BOTH:
  1. Stale heartbeat ($> 15\text{ min}$ without DB update).
  2. An explicit revocation broadcast (`app.control.revoke(task_id, terminate=True)`) sent to the worker before clearing the active video slot.
- **Verification Criteria:**
  Simulate a non-responsive Celery inspect ping while worker heartbeat is actively updated; assert watchdog does NOT terminate the task.

---

## 4. Upload-Stream Concurrency Audit

### Finding AUD25-CON-01 (Severity: P0 - Critical Blocker)
- **Specification Section:** Section 14.4.1.
- **Codebase Location:** `backend/api/routes/videos.py`.
- **Classification:** **Confirmed Fact**.
- **Description & Failure Scenario:**
  Section 14.4.1 specifies:
  ```sql
  SELECT COUNT(*) FROM videos 
  WHERE upload_batch_id = :batch_id AND upload_status = 'uploading';
  ```
  *"If active streams exceed the configured batch limit (default 3), the server responds with HTTP 429 Too Many Requests..."*
  This read query executes without locking the `upload_batches` row.
  If a client or automated script initiates 10 chunk uploads or file registrations simultaneously across 10 distinct video IDs, all 10 queries execute concurrently. All 10 read `COUNT(*) = 0`, all 10 pass the check ($0 < 3$), and all 10 transition to `uploading`.
- **Impact:** Complete bypass of the 3-stream concurrency limit via a classic TOCTOU race; server socket, memory, and bandwidth exhaustion.
- **Minimum Required Correction:**
  Active upload streams must be tracked via an atomic slot-claim transaction:
  1. Acquire an exclusive lock on the batch: `SELECT * FROM upload_batches WHERE id = :batch_id FOR UPDATE`.
  2. Count active streams or maintain an `active_upload_slots` counter column on `upload_batches`.
  3. Increment counter and set `video.upload_status = 'uploading'` atomically within the same transaction.
- **Verification Criteria:**
  Send 10 concurrent requests to `/chunk` or `/init` using `asyncio.gather()`; assert exactly 3 succeed and 7 receive `HTTP 429 Too Many Requests`.

---

### Finding AUD25-CON-02 (Severity: P1 - High)
- **Specification Section:** Section 14.3.3, Section 14.4.3, Section 14.5.3.
- **Codebase Location:** Database Transaction Architecture.
- **Classification:** **Architectural Inference**.
- **Description & Failure Scenario:**
  Upload Studio introduces three distinct lock granularities:
  1. Global Storage Coordinator Lock (`storage_reservation_coordinators WHERE id = 'global' FOR UPDATE`).
  2. Batch Row Lock (`upload_batches WHERE id = :id FOR UPDATE`).
  3. Per-Upload Video Lock (`videos WHERE id = :id FOR UPDATE`).
  The specification does not define a formal **lock acquisition order**. If Operation A (e.g., chunk upload completion) locks `videos` then locks `upload_batches`, while Operation B (e.g., video registration) locks `storage_reservation_coordinators` then `upload_batches` then `videos`, high-concurrency requests will encounter database deadlocks (`40P01 deadlock_detected`).
- **Impact:** Random HTTP 500 errors returned to creators; rolled-back transactions mid-upload.
- **Minimum Required Correction:**
  Mandate a strict global lock acquisition hierarchy:
  **Level 1 (Highest):** `storage_reservation_coordinators`  
  **Level 2:** `upload_batches`  
  **Level 3 (Lowest):** `videos`  
  No database transaction may ever acquire locks in reverse order.
- **Verification Criteria:**
  Execute 50 concurrent mixed requests (`/init`, `/chunk`, `/reorder`, `/cancel`); assert zero `deadlock_detected` exceptions in PostgreSQL logs.

---

## 5. Storage Durability & Capacity Audit

### Finding AUD25-STO-01 (Severity: P0 - Critical Blocker)
- **Specification Section:** Section 14.3.2, Section 14.3.7, Section 14.3.9.
- **Codebase Location:** `backend/core/storage.py:L48-75`, `backend/cleanup_storage.py:L37-72`.
- **Classification:** **Confirmed Fact**.
- **Description & Failure Scenario:**
  Section 14 specifies hardcoded paths:
  - Staging: `storage/temp_uploads/{batch_id}/{upload_id}.part`
  - Source: `storage/source_videos/{upload_id}.{ext}`
  - Atomic rename: `os.replace(staging_path, final_path)`
  This creates two major contradictions with existing storage code:
  1. **`LocalStorageProvider` Incompatibility:** In `backend/core/storage.py:L59-69`, the provider strictly routes keys starting with `outputs/` to `output_dir` and all other keys to `upload_dir`. The hardcoded prefix `storage/` bypasses `StorageProvider` and resolves incorrectly.
  2. **Premature Deletion by `cleanup_storage.py`:** In `backend/cleanup_storage.py:L37-72`, the periodic cleanup job scans `UPLOADS_DIR` for UUID folder names and deletes any folder whose UUID is not present in `Job.video_id`. Studio manual uploads staged before a `Job` row is created will be deleted by the cleanup script.
- **Impact:** Studio uploads deleted mid-transfer or after ingestion by background cleanup tasks; path traversal and cross-filesystem rename failures.
- **Minimum Required Correction:**
  1. Standardize Studio paths under the established storage roots:
     - Staging: `uploads/studio_staging/{batch_id}/{upload_id}.part`
     - Source: `uploads/studio_sources/{upload_id}.{ext}`
  2. Update `backend/cleanup_storage.py` to explicitly exempt Studio directories (`studio_staging/`, `studio_sources/`) and check `videos.upload_status` before deleting.
- **Verification Criteria:**
  Stage a Studio video; run `python backend/cleanup_storage.py`; assert the staged file is preserved and not deleted.

---

### Finding AUD25-STO-02 (Severity: P1 - High)
- **Specification Section:** Section 14.3.3.
- **Codebase Location:** Host Operating System (`windows`).
- **Classification:** **Confirmed Fact**.
- **Description & Failure Scenario:**
  Section 14.3.3 specifies:
  *"...combined with an OS-level file lock `fcntl.flock` on `storage/temp_uploads/{batch_id}/{upload_id}.lock`"*
  The host environment is Windows. The Python `fcntl` module is POSIX-only and does not exist on Windows. Any unit test, local script, or developer environment executing outside a Linux container will fail immediately with `ModuleNotFoundError: No module named 'fcntl'`.
- **Impact:** Inability to run tests or local development servers natively on Windows workstations.
- **Minimum Required Correction:**
  Replace reliance on `fcntl.flock` with PostgreSQL row-level locks (`SELECT * FROM videos WHERE id = :id FOR UPDATE`), which are completely cross-platform, container-independent, and natively serialized by the ACID database engine.
- **Verification Criteria:**
  Run lock acquisition tests on a native Windows Python environment; assert successful execution without `fcntl` import errors.

---

## 6. YouTube Data API Contracts & Quota Realities Audit

### Finding AUD25-API-01 (Severity: P1 - High)
- **Specification Section:** Section 6.2.
- **Codebase Location:** `backend/services/publisher.py`.
- **Classification:** **Confirmed Fact** (Official Google Developers Documentation).
- **Description & Failure Scenario:**
  Section 6.2 correctly cites Google's dedicated endpoint limits:
  - `videos.insert`: Dedicated default bucket of **100 calls per day**.
  - `search.list`: Dedicated default bucket of **100 calls per day**.
  - `videos.update`: **50 quota units per call**.
  However, the specification does not provide a multi-channel buffer or backoff strategy. If a tenant operates 3 channels and publishes 40 videos per channel in a single batch, the project will hit `uploadLimitExceeded` mid-batch.
- **Impact:** Partial batch failures; half of batch items enter `manual_review` due to quota exhaustion.
- **Minimum Required Correction:**
  Specify a pre-dispatch quota budget check in `orchestrate_batch_sequential_task` that verifies remaining daily project upload allocations before initiating sequential publishing.
- **Verification Criteria:**
  Simulate HTTP 403 `uploadLimitExceeded`; assert batch pauses cleanly with informative notification rather than failing individual videos.

---

## 7. Project Regression, Caption Removal & Security Audit

### Finding AUD25-SEC-01 (Severity: P0 - Critical Blocker)
- **Specification Section:** Section 7.2 (Channel Identity & Token Isolation).
- **Codebase Location:** `backend/services/publisher.py:L598-605`.
- **Classification:** **Confirmed Fact**.
- **Description & Failure Scenario:**
  In `backend/services/publisher.py`:
  ```python
  token_file = Path(settings.YOUTUBE_TOKEN_FILE).parent / f"youtube_token_{channel.youtube_channel_id}.json"
  if not token_file.exists():
      default_token = Path(settings.YOUTUBE_TOKEN_FILE)
      if not default_token.exists():
          raise ValueError(f"No YouTube credentials for destination {channel.channel_name}")
  ```
  If Channel B does not have an explicit `youtube_token_{channel_b_id}.json` file, the publisher **falls back to the global default token file** `settings.YOUTUBE_TOKEN_FILE` (which belongs to Channel A).
- **Impact:** Severe data and destination cross-contamination: videos intended for Channel B are uploaded to Channel A's public YouTube channel without error or warning.
- **Minimum Required Correction:**
  Completely excise the global fallback in `publisher.py:L600-601`. If `youtube_token_{channel_id}.json` does not exist, the operation MUST fail immediately with an explicit error.
- **Verification Criteria:**
  Attempt to publish to a destination channel without a specific token file; assert publication fails with `HTTP 422 Unprocessable Entity` and NEVER touches `youtube_token.json`.

---

### Finding AUD25-SEC-02 (Severity: P0 - Critical Blocker)
- **Specification Section:** Section 1.2 (Implementation Prerequisites).
- **Codebase Location:** `backend/main.py:L25,L43`.
- **Classification:** **Confirmed Fact**.
- **Description & Failure Scenario:**
  In `backend/main.py`:
  ```python
  async def scheduled_channel_check():
      ...
      await asyncio.to_thread(run_channel_monitor, db)

  async def scheduled_tracker_check():
      ...
      await asyncio.to_thread(run_realtime_tracker)
  ```
  Both `run_channel_monitor` and `run_realtime_tracker` are defined as `async def` functions. Passing an `async def` function to `asyncio.to_thread()` merely invokes the coroutine function without awaiting it, returning an unawaited coroutine object in a thread worker that immediately gets garbage collected.
- **Impact:** Periodic channel monitoring and real-time performance tracking are **dead in the background**; scheduled jobs never execute.
- **Minimum Required Correction:**
  Directly await the coroutines:
  ```python
  await run_channel_monitor(db)
  await run_realtime_tracker()
  ```
- **Verification Criteria:**
  Start application; assert Celery Beat / APScheduler logs show active execution output for channel monitor and realtime tracker.

---

### Finding AUD25-REG-01 (Severity: P2 - Low / Verified Intact)
- **Specification Section:** Section 10.4.
- **Codebase Location:** `backend/services/clip_cutter.py`, `backend/alembic/versions/5952a2dc05fe_remove_caption_fields.py`.
- **Classification:** **Confirmed Fact**.
- **Description:**
  Audit verified that the complete absence of burnt-in captions/subtitles remains 100% intact. Migration `5952a2dc05fe` dropped all caption columns, and rendering pipelines contain zero subtitle burn-in filters. Whisper transcription is preserved purely for AI semantic scoring and metadata generation.
- **Status:** **PASS / CONFIRMED INTACT**.

---

## 8. Governance & Decision Reconciliation

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                        GOVERNANCE & DECISION STATUS MATRIX                             │
├───────────────────────────────────┬──────────────┬─────────────────────────────────────┤
│ UNRESOLVED DECISION               │ STATUS       │ AUDIT RECOMMENDATION                │
├───────────────────────────────────┼──────────────┼─────────────────────────────────────┤
│ 1. ViewScore Formula Calibration  │ UNRESOLVED   │ Require human approval of normalized│
│                                   │ (PENDING)    │ ratio formula (8.0 threshold) before│
│                                   │              │ Phase 4 backend activation.         │
├───────────────────────────────────┼──────────────┼─────────────────────────────────────┤
│ 2. Storage Retention Lifespan     │ UNRESOLVED   │ Mandate 24-hour grace period for    │
│                                   │ (PENDING)    │ raw uploads to allow creator retry  │
│                                   │              │ before automated disk purge.        │
├───────────────────────────────────┼──────────────┼─────────────────────────────────────┤
│ 3. Studio Route Placement         │ RESOLVED     │ Maintain standalone /studio; leave  │
│                                   │ (APPROVED)   │ legacy /publish intact for fallback.│
├───────────────────────────────────┼──────────────┼─────────────────────────────────────┤
│ 4. Per-Channel Daily Budget Cap   │ UNRESOLVED   │ Enforce hard limit of 20 uploads per│
│                                   │ (PENDING)    │ channel per 24h to avoid quota lock.│
└───────────────────────────────────┴──────────────┴─────────────────────────────────────┘
```

---

## 9. Comprehensive Go / No-Go Decision Gate

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                              GO / NO-GO DECISION GATE                                  │
├─────────────────────────┬─────────┬────────────────────────────────────────────────────┤
│ PROJECT PHASE           │ VERDICT │ BLOCKING CONDITIONS TO RESOLVE                     │
├─────────────────────────┼─────────┼────────────────────────────────────────────────────┤
│ Phase 0: Security & Pre-│ NO-GO   │ Fix main.py:L25,L43 scheduler coroutines;          │
│ requisites Hardening    │         │ Excise default token fallback in publisher.py:L600;│
│                         │         │ Bind infrastructure ports 5433, 6379 to 127.0.0.1. │
├─────────────────────────┼─────────┼────────────────────────────────────────────────────┤
│ Phase 1: Database       │ NO-GO   │ Add Backfill 4 & 5 to upgrade();                   │
│ Schema Migration        │         │ Fix snapshot_video_id mapping in Backfill 4;       │
│                         │         │ Add foreign key constraint on active_video_id;     │
│                         │         │ Add fail-closed pre-validation for target statuses.│
├─────────────────────────┼─────────┼────────────────────────────────────────────────────┤
│ Phase 2: Publishing     │ NO-GO   │ Enforce atomic Phase 7 snapshot & status commit;   │
│ Engine & State Machine  │         │ Prevent premature published_at on scheduled videos;│
│                         │         │ Require confirmation to retry manual_review.       │
├─────────────────────────┼─────────┼────────────────────────────────────────────────────┤
│ Phase 3: Sequential     │ NO-GO   │ Implement active execution_token lease fencing;    │
│ Orchestrator & Watchdog │         │ Replace Celery inspect with explicit task revoke.  │
├─────────────────────────┼─────────┼────────────────────────────────────────────────────┤
│ Phase 4: Backend REST   │ NO-GO   │ Implement atomic slot-claim for stream limiting;   │
│ Routers (/api/studio)   │         │ Standardize paths with LocalStorageProvider;       │
│                         │         │ Replace fcntl.flock with DB row-level locks.       │
├─────────────────────────┼─────────┼────────────────────────────────────────────────────┤
│ Phase 5: Frontend Studio│ HOLD    │ Dependent on Phase 1–4 completion.                 │
│ UI (/studio React App)  │         │                                                    │
├─────────────────────────┼─────────┼────────────────────────────────────────────────────┤
│ Phase 6: E2E Regression │ HOLD    │ Dependent on implementation phase completion.      │
│ & Sandbox Verification  │         │                                                    │
└─────────────────────────┴─────────┴────────────────────────────────────────────────────┘
```

---

## Conclusion & Next Steps

The Upload Studio v1.9 specification provides an exceptional architectural foundation with rigorous multi-batch isolation, private-first publishing, and resumable durability models. However, implementation cannot proceed until the **7 P0 blockers** are resolved.

**Required Action:**  
Update `CLIPFORGE_UPLOAD_STUDIO_V1_9_SPEC.md` to incorporate the minimum required corrections detailed in this report before requesting implementation approval.
