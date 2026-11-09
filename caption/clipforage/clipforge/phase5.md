# Phase 5: Celery Pipeline Modularization & Fault Tolerance DAG

## 🎯 Goal
Decompose the 400+ line monolithic `process_video_task` into a modular Celery DAG task chain (`download_task | transcribe_task | score_task | reframe_task | publish_task`) with exponential backoff retries, Redis priority queues, and a Dead Letter Queue (DLQ).

---

## 🛠️ Implementation Tasks

### 1. Granular Task Decomposition
- **Target Files:** `backend/tasks/pipeline_tasks.py` (NEW), `backend/tasks/process_video.py`
- Split the monolithic task into modular Celery sub-tasks:
  - `download_video_task(job_id, video_url)`
  - `transcribe_audio_task(job_id, video_id)`
  - `score_clips_task(job_id, video_id)`
  - `reframe_clip_task(job_id, clip_id)`

  - `publish_clip_task(job_id, clip_id)`

### 2. Priority Queue Routing (High vs Background)
- **Target Files:** `backend/core/celery_app.py`, `backend/api/routes/videos.py`
- Configure 3 distinct Redis execution queues:
  - `high_priority`: Manual user uploads & single clip restyles (processed instantly).
  - `default`: Automated YouTube channel monitoring jobs.
  - `low_priority`: Analytics processing & periodic disk cleanup jobs.

### 3. Celery Canvas Chain & State Machine
- **Target Files:** `backend/core/celery_app.py`, `backend/api/routes/videos.py`
- Wire sub-tasks into a Celery Canvas chain:
  ```python
  pipeline = chain(
      download_video_task.s(job_id),
      transcribe_audio_task.s(),
      score_clips_task.s(),
      group(reframe_clip_task.s(clip_id) for clip_id in clip_ids)
  )
  ```
- Store intermediate task results in PostgreSQL after each step so failed pipelines can resume from the exact point of failure.

### 4. Retry Topology & Dead Letter Queue (DLQ)
- **Target File:** `backend/core/celery_app.py`
- Configure per-task retry limits and backoff:
  ```python
  @celery_app.task(bind=True, max_retries=3, default_retry_delay=10, autoretry_for=(NetworkError,))
  ```
- Add Dead Letter Queue routing for tasks exceeding maximum retries, logging root-cause tracebacks to the database.

---

## 🧪 Verification & Acceptance Criteria

1. **Priority Preemption Test:** Trigger a background channel check. Simultaneously submit a manual video upload. Confirm manual video task jumps to front of queue in `high_priority`.
2. **Partial Failure Recovery Test:** Simulate a crash during `reframe_task`. Trigger pipeline retry and verify it resumes from reframing without re-downloading or re-transcribing audio.
3. **DLQ Verification:** Trigger a permanent failure (corrupted video file). Verify task is gracefully rejected to DLQ and job status is updated to `failed` with detailed error logs.
