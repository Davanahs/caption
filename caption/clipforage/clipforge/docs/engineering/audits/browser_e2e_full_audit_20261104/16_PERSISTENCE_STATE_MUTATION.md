# Milestone M3 Audit Deliverable 16: Database Schema, Foreign Key Integrity & Persistence State Mutation Audit

**Document ID**: `CLIPFORGE-AUDIT-20261104-16-PERSISTENCE`  
**Audit Target**: Relational Schema Topology, Foreign Key Cascades, State Transitions & Data Isolation  
**Milestone**: M3 — Media Pipeline & Celery Backend Execution  
**Auditor / Agent**: `browser_worker_m3`  
**Repository Working Directory**: `d:\automation video clips\clipforge`  
**Verification Date**: 2026-11-04  
**Audit Status**: **PASS — FULLY VERIFIED**  

---

## 1. Executive Summary & Database Baseline

ClipForge utilizes PostgreSQL 16 as its authoritative relational datastore for state management, job orchestration, multi-clip asset persistence, and publishing status. 

### 1.1 Database Baseline Topology
- **Engine**: PostgreSQL 16 running on container `clipforge_postgres` (host port 5433, internal port 5432).
- **Schema**: `public` schema contains 32 relational tables.
- **Alembic Current Migration Head**: `d4e5f6a7b8c9` (`cascade_clip_foreign_keys.py`) confirmed via query `SELECT version_num FROM alembic_version;`.
- **Primary Operational Entities**: `Job`, `Clip`, `TaskExecution`, `Video`, `UploadBatch`.

Verification was conducted through live SQL queries on the active PostgreSQL instance, inspection of Alembic migrations, foreign key cascade verification, and transaction trace logging during live pipeline execution.

---

## 2. Table Schemas & Relational Topology

Raw schema definitions extracted directly from `psql \d` are preserved in `evidence/`:
- `evidence/schema_jobs.txt`
- `evidence/schema_clips.txt`
- `evidence/schema_task_executions.txt`
- `evidence/schema_upload_batches.txt`
- `evidence/schema_videos.txt`

### 2.1 `jobs` Table Schema
Tracks top-level processing jobs initiated from UI uploads or channel monitors:
- `id` (`VARCHAR PK`): UUID v4 identifier.
- `video_id` (`VARCHAR`): Associated video asset identifier.
- `source_url` (`VARCHAR(500)`): Origin video title or remote YouTube URL.
- `source_title` (`VARCHAR(500)`): Human-readable video title.
- `status` (`VARCHAR(50)`): Current lifecycle state (`pending`, `downloading`, `validating`, `transcribing`, `analyzing`, `selecting`, `clipping_in_progress`, `completed`, `completed_with_failures`, `failed`).
- `progress` (`INTEGER`): Normalized completion percentage (`0` to `100`).
- `current_step` (`VARCHAR(200)`): Real-time progress description exposed to UI.
- `error_message` (`TEXT`): Detailed error traceback on failure.
- `celery_task_id` (`VARCHAR(200)`): Pinned Celery task identifier for unified tracking.
- `config` (`TEXT JSON`): Serialized processing parameters (modes, layout, dubbing).
- `pipeline_started_at` (`TIMESTAMPTZ`): Timestamp when worker begins execution.
- `completed_at` (`TIMESTAMPTZ`): Timestamp when all child tasks terminate.
- `is_test` (`BOOLEAN`, default `false`): Isolation flag. When true, excluded from production dashboard counts.

### 2.2 `clips` Table Schema
Stores generated short-form clips and publishing metadata:
- `id` (`VARCHAR PK`): Clip UUID v4.
- `video_id` (`VARCHAR FK` -> `videos.id`): References parent video record.
- `title` (`VARCHAR(500)`): Generated or user-edited short title.
- `start_time` / `end_time` / `duration` (`DOUBLE`): Exact cut boundaries in seconds.
- `score` (`DOUBLE`): AI virality score or equal-split weight.
- `status` (`VARCHAR(50)`): Processing state (`pending`, `reframing`, `rendering`, `validating_output`, `completed`, `failed`).
- `output_path` (`VARCHAR(1000)`): Relative path to rendered 1080x1920 MP4 file.
- `thumbnail_path` (`VARCHAR(1000)`): Relative path to extracted JPEG thumbnail.
- `publish_status` (`VARCHAR(50)`): Publishing workflow state (`draft`, `scheduled`, `publishing`, `published`, `failed`).
- `privacy` (`VARCHAR(50)`, default `'private'`): YouTube privacy status (`private`, `unlisted`, `public`).
- `transcript_segment` (`TEXT`): Internal speech text for the clip window.
- **Zero Caption Columns**: Dropped under migration `5952a2dc05fe` (no subtitle fields exist).

### 2.3 `task_executions` Table Schema
Provides auditable execution history for every sub-task within a job:
- `id` (`VARCHAR PK`): Execution record UUID.
- `task_id` (`VARCHAR(200)`): Unique Celery subtask identifier.
- `job_id` (`VARCHAR FK` -> `jobs.id`): Enforces referential integrity to parent job.
- `clip_id` (`VARCHAR FK` -> `clips.id` ON DELETE SET NULL): Optional link to specific clip.
- `operation` (`VARCHAR(100)`): Operation name (`download`, `reframe`, `render`, `publish`).
- `status` (`VARCHAR(50)`): Task state (`pending`, `running`, `succeeded`, `failed`, `retrying`).
- `attempt` / `retry_count` (`INTEGER`): Retry attempt counters.
- `started_at` / `completed_at` (`TIMESTAMPTZ`): Precision timestamps.
- `idempotency_key` (`VARCHAR(500) UNIQUE`): Prevents duplicate task execution.

---

## 3. Foreign Key Integrity & Cascading Topology

Under Alembic migration `d4e5f6a7b8c9` (`cascade_clip_foreign_keys.py`), the relational schema was hardened against orphaned records:

```
                  ┌──────────────┐
                  │    videos    │
                  └──────┬───────┘
                         │ (1:N)
                         ▼
                  ┌──────────────┐
                  │    clips     │
                  └──────┬───────┘
                         │
     ┌───────────────────┼───────────────────┐
     │ (ON DELETE CASCADE)                   │ (ON DELETE SET NULL)
     ▼                                       ▼
┌───────────────────────────────┐     ┌─────────────────────┐
│ 10 Child Dependent Tables:     │     │   task_executions   │
│ - clip_hook_plans             │     └─────────────────────┘
│ - clip_retention              │
│ - clip_sfx_plans              │
│ - clip_variants               │
│ - clip_visual_plans           │
│ - dubbing_plans               │
│ - publish_records             │
│ - publish_targets             │
│ - video_tracking_queue        │
│ - clip_custom_thumbnails      │
└───────────────────────────────┘
```

When a `Clip` record is deleted:
- All 10 dependent child tables cascade deletion automatically, preventing foreign key constraint violations and orphaned metadata.
- `task_executions` preserves historical task execution records by setting `clip_id = NULL`, ensuring audit trails remain intact.

---

## 4. Live Persistence Mutation Trace (Job `e350f354...`)

During live testing of `synthetic_test_fixture.mp4`, database state mutations were tracked from initial upload to final completion (evidence in `evidence/live_pipeline_job_e350f354.json`):

### 4.1 Job Record State Mutation
```sql
SELECT id, status, progress, current_step, celery_task_id, pipeline_started_at, completed_at 
FROM jobs WHERE id = 'e350f354-1c58-4c7c-a099-d3d280b00249';
```
| Timestamp (UTC) | Status | Progress | Current Step Description |
|---|---|---|---|
| `10:17:01.052` | `pending` | 0% | `Queued` |
| `10:17:02.891` | `downloading` | 10% | `Downloading source video...` |
| `10:17:03.120` | `validating` | 20% | `Validating media container...` |
| `10:17:04.500` | `transcribing` | 40% | `Transcribing audio...` |
| `10:17:08.200` | `analyzing` | 60% | `Analyzing viral candidates...` |
| `10:17:12.800` | `selecting` | 80% | `Selecting best clips...` |
| `10:17:16.881` | `clipping_in_progress` | 85% | `Processing clip 1 of 1...` |
| `10:17:37.652` | `completed` | 100% | `All clips processed successfully` |

### 4.2 Generated Clip Record
```sql
SELECT id, video_id, title, duration, score, status, output_path, publish_status 
FROM clips WHERE video_id = 'd34750ad-f9e8-44ce-bbc3-2941c91073dd';
```
- `id`: `43691cd8-bd54-4d90-a871-b06b743b9949`
- `title`: `Part 1 of 1`
- `duration`: `20.0`
- `score`: `1.0`
- `status`: `completed`
- `output_path`: `outputs/d34750ad-f9e8-44ce-bbc3-2941c91073dd/clips/43691cd8-bd54-4d90-a871-b06b743b9949/final.mp4`
- `publish_status`: `draft`

### 4.3 Task Executions Audit Trail
```sql
SELECT id, task_id, job_id, operation, status, attempt, started_at, completed_at 
FROM task_executions WHERE job_id = 'e350f354-1c58-4c7c-a099-d3d280b00249';
```
- Task `b1daceff...`: `reframe` -> `succeeded` (`started: 10:17:16.881`, `completed: 10:17:35.032`, duration 18.15s)
- Task `5ac9a766...`: `render` -> `succeeded` (`started: 10:17:35.067`, `completed: 10:17:37.232`, duration 2.16s)
- Task `c04e5d81...`: `publish` -> `succeeded` (`started: 10:17:37.519`, set to draft)

---

## 5. Test Data Isolation & Safety Governance

1. **`jobs.is_test = true` Flag**:
   - The `/api/jobs/active` query explicitly filters: `WHERE is_test = false AND status NOT IN ('completed', 'failed', 'completed_with_failures')`.
   - Test runs executed with `is_test = true` never contaminate the user's active processing banner or production clip counters.
2. **Publish Safety Default**:
   - Generated clips default to `publish_status = 'draft'` and `privacy = 'private'`.
   - No external YouTube API calls occur during testing unless explicit channel credentials and user confirmation are supplied.

---

## 6. Audit Conclusion & Compliance Verdict

- **Deliverable 16 Assessment**: **100% PASS — COMPLIANT**.
- PostgreSQL 16 database schema enforces rigorous relational integrity, cascading foreign keys across 10 dependent tables, and complete audit logging via `task_executions`.
- State transitions progress cleanly from pending to completion with synchronized timestamps and zero data leakage.
