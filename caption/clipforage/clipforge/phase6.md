# Phase 6: Automated Storage Lifecycle & S3/MinIO Object Backing Engine

## 🎯 Goal
Implement automated retention rules, temporary render file purging, disk threshold alerts, and optional S3/MinIO cloud object storage backing with presigned URLs to prevent system outages caused by full disks and enable horizontal scaling.

---

## 🛠️ Implementation Tasks

### 1. Storage Manager & Garbage Collection Engine
- **Target Files:** `backend/services/storage_manager.py` (NEW), `backend/core/config.py`
- Create `StorageManager` service:
  - Immediate Purge: Delete raw input downloads (`./uploads/*`) as soon as clip cutting pass finishes.
  - Intermediate Purge: Delete raw crop streams and uncompressed frame caches immediately after Pass 2 overlay composition completes.
  - Final Clip Retention: Retain output clips (`./outputs/*`) for a configurable retention window (e.g. 14 days) before auto-archiving or purging.

### 2. S3 / MinIO Cloud Object Storage Integration
- **Target Files:** `backend/services/s3_storage.py` (NEW), `backend/core/config.py`
- Add optional S3/MinIO cloud object storage driver (`boto3` / `aioboto3`):
  - Automatically uploads final `final.mp4` clips and thumbnails to S3 bucket (`clipforge-media`).
  - Generates secure presigned download URLs for frontend playback, bypassing local disk storage constraints completely in production.

### 3. Celery Beat Automated Cleanup Job
- **Target Files:** `backend/tasks/cleanup_tasks.py` (NEW), `backend/core/celery_app.py`
- Schedule an automated Celery Beat maintenance task `cleanup_storage_job` running every 6 hours:
  - Scans `./uploads` and `./outputs` directories.
  - Removes orphaned directories not associated with active database records.
  - Enforces max total disk quota (e.g. 50 GB limit). If quota is exceeded, purges oldest non-favorited local clips.

### 4. Disk Space Monitoring & Guardrails
- **Target File:** `backend/api/routes/videos.py`
- Add a disk pre-check before accepting new video downloads or file uploads (`shutil.disk_usage`).
- Reject submissions if free disk space is less than 5 GB with HTTP 507 ("Insufficient Storage").

---

## 🧪 Verification & Acceptance Criteria

1. **S3 Presigned URL Test:** Configure MinIO container. Upload a video clip and verify `final.mp4` is pushed to object storage and served via a valid presigned URL.
2. **Auto-Purge Test:** Process a 500 MB video. Verify source file in `./uploads` is automatically deleted immediately after clip generation.
3. **Guardrail Test:** Simulate low disk space (<5 GB). Verify incoming upload requests fail fast with explicit warning messages.
