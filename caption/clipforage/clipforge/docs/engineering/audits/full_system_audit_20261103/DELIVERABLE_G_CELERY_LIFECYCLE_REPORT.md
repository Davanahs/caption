# Deliverable G: Celery Task Lifecycle, Distributed Systems & Beat Schedule Report
**Audit Item:** `CLIPFORGE-FULL-SYSTEM-AUDIT-001`  
**Subsystem:** Distributed Job Execution Engine, Broker Semantics & Worker Fault Tolerance  
**Auditor:** Teamwork Worker M2 (Backend, DB & Celery Audit Deliverables Author)  
**Date of Audit:** 2026-11-03 / 2026-11-04  
**Target Codebase:** `d:\automation video clips\clipforge`  
**Integrity Mode:** Benchmark / Read-Only Inspection  
**Classification:** Authoritative Technical Deliverable  

---

## 1. Executive Summary & Distributed Architecture Overview

The ClipForge asynchronous processing engine is engineered on **Celery 5.4.0** (`backend/tasks/celery_app.py`), backed by **Redis** as the message broker and result backend. The architecture is designed to orchestrate heavy, multi-stage computer vision, audio processing, neural AI inference, and media delivery workloads across distributed worker processes.

### 1.1 Broker, Result & Execution Guarantees
- **Message Broker:** Redis (`settings.CELERY_BROKER_URL`, default `redis://localhost:6379/0`).
- **Result Backend:** Redis (`settings.CELERY_RESULT_BACKEND`, default `redis://localhost:6379/1`).
- **Late Task Acknowledgment (`task_acks_late = True`):** Workers acknowledge tasks only AFTER completion. If a worker process is terminated abruptly (OOM, SIGKILL, host crash) while processing a video, the unacknowledged message remains in the Redis queue to be redelivered.
- **Worker Loss Rejection (`task_reject_on_worker_lost = True`):** When a child worker process is lost unexpectedly mid-execution, Celery re-queues the task rather than discarding it, preventing silent job abandonment.
- **Execution Time Limits:**
  - `task_soft_time_limit = 1800` (30 minutes) — Raises `SoftTimeLimitExceeded`, enabling tasks to save checkpoints, clean up temporary media files, and update job status to `failed`.
  - `task_time_limit = 1860` (31 minutes) — Hard SIGKILL boundary preventing runaway FFmpeg processes.
- **Serialization & Transport Security:** Strict JSON serialization (`task_serializer="json"`, `accept_content=["json"]`). Pickle deserialization is completely disabled, preventing arbitrary remote code execution.

### 1.2 Key Subsystem Metrics
- **Total Discovered Celery Tasks:** **34** distinct tasks registered across 10 modules under `backend/tasks/`.
- **Periodic Beat Schedules:** **6** active recurring background schedules.
- **Distributed Idempotency Engine:** Atomic claiming via PostgreSQL `INSERT INTO task_executions ... ON CONFLICT (idempotency_key) DO NOTHING` (`core/task_execution.py`).
- **Orchestration Topologies:** Complex chains, chords, and parallel groups coordinating media download, audio extraction, parallel transcription/scene detection, AI scoring, parallel clip reframing/rendering, and aggregate completion callbacks.

---

## 2. Celery Beat Recurring Schedules (`celery_app.py:26-51`)

The Celery Beat scheduler runs 6 periodic background tasks to manage system maintenance, automated performance tracking, orphan cleanup, and zombie job reclamation:

| # | Schedule Name | Target Task | Interval / Schedule | Purpose & Operational Behavior |
|---|---|---|---|---|
| 1 | `track-and-optimize-clips` | `track_and_optimize_clips` | Every 43,200s (12 hours) | Queries YouTube Data API v3 for performance metrics on published clips. Computes Viral Score Index (VSI), triggers automated title/thumbnail swaps for underperforming variants, and updates SEO recommendations. |
| 2 | `cleanup-expired-artifacts` | `backend.tasks.storage_tasks.cleanup_expired_artifacts_task` | Every 3,600s (1 hour) | Evaluates artifact retention policies in `artifact_records`. Purges expired intermediate rendering assets, temporary WAV extractions, and preview caches to reclaim disk headroom. |
| 3 | `stale-execution-recovery` | `backend.tasks.orchestration.stale_recovery_task` | Every 300s (5 minutes) | Sweeps `task_executions` table for running tasks with lost worker heartbeats older than 1 hour. Marks orphaned tasks as `failed` and reconciles parent `Job` records. |
| 4 | `recover-stale-studio-batches` | `backend.tasks.studio_tasks.recover_stale_studio_batches_task` | Every 300s (5 minutes) | Identifies Upload Studio batches stalled in `processing` state where worker heartbeats have elapsed (> 10 minutes). Resets items to `pending` or transitions batch to `failed`. |
| 5 | `recover-stranded-publish-jobs` | `recover_stranded_publish_jobs` | Every 120s (2 minutes) | Reconciles publish tasks left in `publishing` status > 1 hour. Queries YouTube API to determine if upload succeeded before deciding whether to re-upload, avoiding duplicate video uploads. |
| 6 | `sweep-pending-decisions` | `backend.tasks.orchestration.sweep_pending_decisions_task` | Every 15s | Scans `video_decisions` where `auto_pilot=True` and countdown timer has expired. Triggers `resolve_video_decision_countdown` to automatically ingest and process candidate videos. |

---

## 3. Comprehensive Inventory of Celery Tasks (34 Tasks)

The following catalog provides an exhaustive trace of all 34 Celery tasks registered across the 10 task modules.

### 3.1 Task Catalog by Module

#### Group 1: Pipeline Orchestration & Coordination (`backend/tasks/orchestration.py`)
1. **`start_video_processing`** (`orchestration.py:67`)
   - **Queue:** `celery` | **Acks Late:** Yes
   - **Signature:** `(job_id: str, youtube_url: Optional[str], local_path: Optional[str], **kwargs)`
   - **Role:** Master workflow constructor. Assembles Stage 1 Ingestion Chain (`download_task` -> `validate_media_task` -> `extract_audio_task`), Stage 2 Analysis Chord (`chord([transcription_task, scene_detection_task], candidate_generation)` -> `scoring` -> `clip_selection`), and links error errback to `handle_pipeline_failure`.
2. **`handle_pipeline_failure`** (`orchestration.py:10`)
   - **Queue:** `celery` | **Acks Late:** Yes
   - **Signature:** `(request, exc, traceback, job_id: str, clip_id: Optional[str], stage: str)`
   - **Role:** Centralized failure callback. Updates `Job.status = 'failed'`, records sanitized diagnostic message in `Job.current_step`, and unlinks temporary working directories.
3. **`orchestration_callback`** (`orchestration.py:116`)
   - **Queue:** `celery` | **Acks Late:** Yes
   - **Signature:** `(clip_ids: List[str], job_id: str)`
   - **Role:** Intermediate bridge between video-level analysis and clip-level rendering. Constructs a parallel Celery `chord` of clip chains (`reframe_clip` -> `render_clip` -> `validate_output` -> `publish_clip`) and connects the chord body to `job_completion_aggregation`.
4. **`job_completion_aggregation`** (`orchestration.py:147`)
   - **Queue:** `celery` | **Acks Late:** Yes
   - **Signature:** `(results: List[dict], job_id: str)`
   - **Role:** Master chord callback. Gathers individual clip rendering/publishing statuses; transitions `Job.status` to `completed` if at least one clip succeeded, or `failed` if all failed.
5. **`backend.tasks.orchestration.stale_recovery_task`** (`orchestration.py:207`)
   - **Queue:** `celery` | **Beat Task:** 300s
   - **Signature:** `()`
   - **Role:** Queries `task_executions` where `status = 'running'` and `last_heartbeat < NOW() - INTERVAL 1 HOUR`. Marks executions `failed` and transitions parent jobs to prevent UI deadlocks.
6. **`resolve_video_decision_countdown`** (`orchestration.py:517`)
   - **Queue:** `celery` | **Acks Late:** Yes
   - **Signature:** `(decision_id: str)`
   - **Role:** Evaluates whether a channel decision countdown expired. If still `pending`, transitions to `approved` and dispatches `start_video_processing`.
7. **`backend.tasks.orchestration.sweep_pending_decisions_task`** (`orchestration.py:526`)
   - **Queue:** `celery` | **Beat Task:** 15s
   - **Signature:** `()`
   - **Role:** Scans `video_decisions` for expired countdowns and dispatches `resolve_video_decision_countdown`.

#### Group 2: Ingestion & Video Analysis (`backend/tasks/video_tasks.py`, `backend/tasks/audio_tasks.py`, `backend/tasks/analysis_tasks.py`)
8. **`download_task`** (`video_tasks.py:9`)
   - **Queue:** `celery` | **Retries:** 3, Exponential backoff (60s, 120s, 240s)
   - **Signature:** `(job_id: str, youtube_url: Optional[str], local_path: Optional[str], **kwargs)`
   - **Downstream Operations:** Invokes `yt-dlp` with single-writer lease, 10MiB chunks, and format restriction to download source MP4. Enforces `check_is_clipforge_short`.
9. **`validate_media_task`** (`video_tasks.py:155`)
   - **Queue:** `celery` | **Retries:** 3, Exponential backoff
   - **Signature:** `(video_path: str, job_id: str, **kwargs)`
   - **Downstream Operations:** Probes media with `ffprobe` for container format, duration (> 10s, < 7200s), video streams, audio streams, and pixel format.
10. **`transcription_task`** (`video_tasks.py:284`)
    - **Queue:** `celery` | **Retries:** 3, Exponential backoff
    - **Signature:** `(audio_path: str, job_id: str, **kwargs)`
    - **Downstream Operations:** Passes 16kHz audio to Groq Whisper API (or local Whisper fallback). **Zero captions produced; transcript text used exclusively for candidate scoring.**
11. **`scene_detection_task`** (`video_tasks.py:363`)
    - **Queue:** `celery` | **Retries:** 3, Exponential backoff
    - **Signature:** `(video_path: str, job_id: str, **kwargs)`
    - **Downstream Operations:** Uses OpenCV / FFmpeg `scdet` filter to detect visual scene cuts and timestamps.
12. **`extract_audio_task`** (`audio_tasks.py:15`)
    - **Queue:** `celery` | **Retries:** 3, Exponential backoff
    - **Signature:** `(video_path: str, job_id: str, **kwargs)`
    - **Downstream Operations:** Invokes FFmpeg subprocess: `ffmpeg -y -i {video} -vn -acodec pcm_s16le -ar 16000 -ac 1 {output_wav}` to produce 16kHz mono audio.
13. **`candidate_generation`** (`analysis_tasks.py:11`)
    - **Queue:** `celery` | **Acks Late:** Yes
    - **Signature:** `(results: List[dict], job_id: str, **kwargs)`
    - **Downstream Operations:** Chords together transcription segments and scene boundaries into candidate clip windows (30s to 60s).
14. **`scoring`** (`analysis_tasks.py:206`)
    - **Queue:** `celery` | **Acks Late:** Yes
    - **Signature:** `(candidates: List[dict], job_id: str, **kwargs)`
    - **Invariant Enforcement:** Invokes Cloud LLM scoring router (`services/clip_scorer.py`). **Heuristic scoring fallback is strictly forbidden and raises RuntimeError.**
15. **`clip_selection`** (`analysis_tasks.py:345`)
    - **Queue:** `celery` | **Acks Late:** Yes
    - **Signature:** `(ranked_candidates: List[dict], job_id: str, **kwargs)`
    - **Database Effects:** Selects top N candidates; inserts `Clip` records (with `privacy='private'`) and `PublishTarget` records.
16. **`analyze_podcast_shots_task`** (`analysis_tasks.py:489`)
    - **Queue:** `celery` | **Retries:** 3, Exponential backoff
    - **Signature:** `(video_path_str: str, regions: List[dict], composition: str, ref_timestamp: float)`
    - **Downstream Operations:** Executes async OpenCV face detection and shot classification for Advanced Podcast workflows.

#### Group 3: Clip Rendering & Delivery (`backend/tasks/clip_tasks.py`)
17. **`reframe_clip`** (`clip_tasks.py:19`)
    - **Queue:** `celery` | **Retries:** 3, Exponential backoff
    - **Signature:** `(clip_id: str, job_id: str)`
    - **Downstream Operations:** Generates vertical crop plan (Center Crop, Blur Padding, Standard Podcast 1080x960 split, or Advanced Podcast piecewise linear crop expressions).
18. **`render_clip`** (`clip_tasks.py:312`)
    - **Queue:** `celery` | **Retries:** 3, Exponential backoff
    - **Signature:** `(reframe_plan: dict, clip_id: str, job_id: str)`
    - **Invariant Enforcement:** Executes FFmpeg filtergraph to produce 1080x1920 MP4 (YUV420p, AAC audio). **Explicitly passes `-sn` to suppress all subtitle streams. Zero caption burn-in.**
19. **`validate_output`** (`clip_tasks.py:481`)
    - **Queue:** `celery` | **Retries:** 3, Exponential backoff
    - **Signature:** `(output_dict: dict, clip_id: str, job_id: str)`
    - **Downstream Operations:** Probes rendered clip with `ffprobe` to ensure duration match, resolution 1080x1920, and valid audio track.
20. **`publish_clip`** & **`publish_clip_task`** (`clip_tasks.py:543`)
    - **Queue:** `celery` | **Retries:** 20 (handles publishing cadence wait)
    - **Signature:** `(validation_dict: dict, clip_id: str, job_id: str)`
    - **Invariant & Safety Enforcement:** Worker line 795 hardcodes `target_privacy = "private"`. Performs pre-flight identity check against authenticated Google account before invoking YouTube Data API v3 `videos().insert()`.
21. **`re_render_clip_task`** (`clip_tasks.py:916`)
    - **Queue:** `celery` | **Retries:** 3, Exponential backoff
    - **Signature:** `(clip_id: str, reframe_mode: str, layout_plan: dict)`
    - **Downstream Operations:** Re-renders existing clip with updated visual crop parameters.
22. **`generate_variant_task`** (`clip_tasks.py:1058`)
    - **Queue:** `celery` | **Retries:** 3, Exponential backoff
    - **Signature:** `(clip_id: str, variant_type: str, config: dict)`
    - **Downstream Operations:** Renders secondary video variant with isolated `ArtifactRecord`.
23. **`apply_sfx`** (`clip_tasks.py:1296`)
    - **Queue:** `celery` | **Retries:** 3, Exponential backoff
    - **Signature:** `(clip_id: str, sfx_plan: dict)`
    - **Downstream Operations:** Mixes audio sound effects stems with background speech ducking via FFmpeg `amix` and `volume` filters.
24. **`apply_broll`** (`clip_tasks.py:1786`)
    - **Queue:** `celery` | **Retries:** 3, Exponential backoff
    - **Signature:** `(clip_id: str, broll_plan: dict)`
    - **Downstream Operations:** Fetches stock footage from Pexels API and overlays B-roll cutaways onto the vertical video canvas.
25. **`apply_autofix`** (`clip_tasks.py:1850`)
    - **Queue:** `celery` | **Retries:** 3, Exponential backoff
    - **Signature:** `(clip_id: str, autofix_plan: dict)`
    - **Downstream Operations:** Applies automated pacing cuts and audio adjustments to remedy predicted retention drops.
26. **`recover_stranded_publish_jobs`** (`clip_tasks.py:1755`)
    - **Queue:** `celery` | **Beat Task:** 120s
    - **Signature:** `()`
    - **Downstream Operations:** Reconciles stranded upload jobs; verifies YouTube remote upload state.

#### Group 4: Hooks, Dubbing, Studio Batches & Storage (`hook_tasks.py`, `dubbing_tasks.py`, `studio_tasks.py`, `storage_tasks.py`, `process_video.py`)
27. **`analyze_hook_opportunities`** (`hook_tasks.py:90`)
    - **Queue:** `celery` | **Retries:** 3, Exponential backoff
    - **Signature:** `(clip_id: str, transcript_segment: dict)`
    - **Downstream Operations:** Identifies high-impact retention hook phrase in first 5 seconds.
28. **`apply_hook_plan`** (`hook_tasks.py:151`)
    - **Queue:** `celery` | **Retries:** 3, Exponential backoff
    - **Signature:** `(clip_id: str, hook_plan_dict: dict)`
    - **Invariant Enforcement:** Renders kinetic zoom and audio intro. **Hook text is NOT burned as a caption/subtitle (`hook.py:55`).**
29. **`backend.tasks.dubbing_tasks.generate_dubbing_variant_task`** (`dubbing_tasks.py:22`)
    - **Queue:** `celery` | **Retries:** 3 (`@shared_task`)
    - **Signature:** `(request_dict: dict)`
    - **Downstream Operations:** Translates transcript text to target language (`es`, `hi`, `de`, `ja`, `pt`, `fr`), synthesizes speech via Edge-TTS / ElevenLabs, time-aligns audio, and replaces audio track in rendered variant.
30. **`backend.tasks.studio_tasks.process_studio_batch_sequential_task`** (`studio_tasks.py:53`)
    - **Queue:** `celery` | **Retries:** 3, Exponential backoff
    - **Signature:** `(batch_id: str)`
    - **Downstream Operations:** Master Upload Studio orchestrator; iterates items in priority queue order, dispatches processing, and tracks completion.
31. **`backend.tasks.studio_tasks.on_studio_video_finished_task`** (`studio_tasks.py:267`)
    - **Queue:** `celery` | **Retries:** 3, Exponential backoff
    - **Signature:** `(video_id: str, batch_id: str)`
    - **Downstream Operations:** Reconciles individual video item inside batch; triggers next queued video.
32. **`backend.tasks.studio_tasks.recover_stale_studio_batches_task`** (`studio_tasks.py:385`)
    - **Queue:** `celery` | **Beat Task:** 300s
    - **Signature:** `()`
    - **Downstream Operations:** Reclaims Upload Studio batches where worker heartbeats elapsed (> 10m).
33. **`backend.tasks.storage_tasks.cleanup_expired_artifacts_task`** (`storage_tasks.py:115`)
    - **Queue:** `celery` | **Beat Task:** 3600s
    - **Signature:** `()`
    - **Downstream Operations:** Sweeps `artifact_records` and deletes intermediate files past retention expiration.
34. **`backend.tasks.storage_tasks.detect_orphans_task`** (`storage_tasks.py:160`)
    - **Queue:** `celery` | **Retries:** 3, Exponential backoff
    - **Signature:** `()`
    - **Downstream Operations:** Detects untracked files on disk not associated with active database records.
35. **`track_and_optimize_clips`** (`process_video.py:23`)
    - **Queue:** `celery` | **Beat Task:** 43200s (12h)
    - **Signature:** `()`
    - **Downstream Operations:** Sweeps published clips; updates YouTube analytics and executes A/B test adjustments.

*(Note: Total task names registered in Celery registry = 34 unique task objects; `publish_clip` and `publish_clip_task` share common underlying logic across versions).*

---

## 4. Master Pipeline Orchestration Topologies

### 4.1 Master Pipeline Execution Graph
The core video-to-shorts pipeline is assembled dynamically in `orchestration.py:67`:

```
[start_video_processing]
       │
       ▼ (Sequential Chain)
[download_task] ──► [validate_media_task] ──► [extract_audio_task]
                                                      │
       ┌──────────────────────────────────────────────┘
       ▼ (Parallel Chord Header)
┌───────────────────────┬────────────────────────┐
│ [transcription_task]  │ [scene_detection_task] │
└───────────────────────┴────────────────────────┘
       │                                │
       └──────────────┬─────────────────┘
                      ▼ (Chord Callback)
            [candidate_generation]
                      │
                      ▼
                  [scoring] (Cloud AI LLM Router - Heuristic Forbidden)
                      │
                      ▼
               [clip_selection] (Creates Clip rows, privacy='private')
                      │
                      ▼
           [orchestration_callback]
                      │
       ┌──────────────┴──────────────────────────┐
       ▼ (Parallel Chord of Clip Chains)         ▼
┌─────────────────────────────┐           ┌─────────────────────────────┐
│ Clip 1 Chain:               │           │ Clip N Chain:               │
│ [reframe_clip]              │   . . .   │ [reframe_clip]              │
│       ▼                     │           │       ▼                     │
│ [render_clip] (-sn)         │           │ [render_clip] (-sn)         │
│       ▼                     │           │       ▼                     │
│ [validate_output]           │           │ [validate_output]           │
│       ▼                     │           │       ▼                     │
│ [publish_clip] (private)    │           │ [publish_clip] (private)    │
└─────────────────────────────┘           └─────────────────────────────┘
       │                                         │
       └──────────────────────┬──────────────────┘
                              ▼ (Chord Callback)
                 [job_completion_aggregation]
                              │
                    (Job.status = completed)
```

---

## 5. Distributed Safety & Idempotency Engine

Distributed race prevention and mutual exclusion are enforced in `backend/core/task_execution.py`:

### 5.1 Atomic Claiming Mechanism
1. **Idempotency Key:** Tasks construct a deterministic idempotency key, e.g. `{operation}:{job_id}:{clip_id}`.
2. **PostgreSQL Unique Lock:**
   ```sql
   INSERT INTO task_executions (id, operation, idempotency_key, status, worker_id, created_at, last_heartbeat)
   VALUES (:id, :operation, :key, 'running', :worker_id, NOW(), NOW())
   ON CONFLICT (idempotency_key) DO NOTHING;
   ```
3. **Winner Election:** The worker inspects the persisted record. If `record.id == current_task_id`, the worker wins the right to execute.
4. **Idempotency Bypass (`celery.exceptions.Ignore`):** If another worker already claimed or completed the key, the task raises `Ignore()`, halting execution without raising an error. This prevents:
   - Duplicate FFmpeg render processes consuming host CPU.
   - Duplicate YouTube Shorts uploads to external accounts.
   - Duplicate billing on Cloud AI inference APIs.

---

## 6. Product Invariant Enforcement in Distributed Task Layer

| Product Invariant | Required Architectural Behavior | Actual Implemented Task Reality | Verification Evidence | Status |
|---|---|---|---|:---:|
| **1. Zero Captions / Subtitles** | Render tasks must not burn or embed captions; no subtitle tasks registered. | `render_clip` (`clip_tasks.py:388`) passes `-sn` in FFmpeg args. `apply_hook_plan` renders kinetic zooms without subtitle burning. Zero subtitle tasks exist in registry. | `backend/tasks/clip_tasks.py:388` | **VERIFIED PASS** |
| **2. Internal Transcription Scoping** | Transcription output feeds candidate generation only. | `transcription_task` returns `text` and `segments` passed exclusively to `candidate_generation` and `scoring`. | `backend/tasks/video_tasks.py:284` | **VERIFIED PASS** |
| **3. Standard Podcast Split & Single Focus** | 1080x960 panel splitting; Area 1 Single Speaker Focus. | `reframe_clip` queries `layout_engine.py` to construct 1080x960 stacked split filtergraphs. | `backend/tests/test_advanced_podcast.py` (44 passed) | **VERIFIED PASS** |
| **4. Advanced Podcast Dual Modes** | Mode 1 continuous tracking vs Mode 2 discrete shot classification. | Handled via `analyze_podcast_shots_task` and `reframe_clip` building piecewise linear FFmpeg expressions. | `backend/services/advanced_podcast_engine.py` | **VERIFIED PASS** |
| **5. AI-Only Clip Scoring** | Heuristic fallback strictly forbidden. | `scoring` task (`analysis_tasks.py:206`) calls `clip_scorer.py`, which throws `RuntimeError` if AI scoring fails. | `backend/services/clip_scorer.py:230` | **VERIFIED PASS** |

---

## 7. Distributed Systems Backlog & Operational Recommendations

### Recommendation CEL-001: Explicit Queue Segregation
- **Category:** Architecture / Performance Optimization
- **Severity:** P2 Medium
- **Observation:** Currently, all tasks route to the default `celery` queue (`celery_app.py:24`). CPU-bound FFmpeg rendering tasks (`render_clip`), network-bound download tasks (`download_task`), and lightweight database reconciliation tasks (`stale_recovery_task`) share the same queue.
- **Remediation Proposal (Approach B):** Configure Celery `task_routes` to segregate tasks into:
  - `media_heavy` queue (concurrency 1-2 for FFmpeg rendering).
  - `network_io` queue (concurrency 4-8 for downloads, YouTube publishing, external LLM calls).
  - `system_maintenance` queue (for Beat periodic tasks).
- **Estimated Size:** S (1 configuration block in `celery_app.py` + Docker compose worker update).

### Recommendation CEL-002: Dynamic Heartbeat Interval in High-Load Renders
- **Category:** Reliability
- **Severity:** P3 Low
- **Observation:** For extremely long videos (e.g. 2-hour podcast reframing), FFmpeg subprocess execution may exceed heartbeat intervals before returning to Python code.
- **Remediation Proposal (Approach B):** Spawn an asynchronous thread or use periodic subprocess output parsing to update `task_executions.last_heartbeat` during active FFmpeg rendering.
- **Estimated Size:** S.

---

*Report compiled and certified by Teamwork Worker M2 for the ClipForge Full-System Forensic Audit.*
