# ClipForge Automatic YouTube Channel Monitoring & Intelligent Processing: Baseline & Discovery Report

**Standard:** `ANTIGRAVITY_CLIPFORGE_FREEZE_RULES.md`  
**Governance:** `MASTER_ENGINEERING_RULEBOOK.md`  
**Reference Ledger:** `docs/engineering/LOGIC_FREEZE_LEDGER.md`  
**Dependency Map:** `docs/engineering/LOGIC_DEPENDENCY_MAP.md`  
**Baseline Date:** 2026-10-13  
**Active Alembic Revision:** `f3b4c5d6e7f8 (head)`  
**Baseline Commit:** `0ba85ff`  

---

## 1. Executive Summary & Current Operational State

This baseline document establishes the verified operational state of ClipForge prior to the implementation of the Automatic YouTube Channel Monitoring & Intelligent Video Processing system.

### Verified Runtime & Service Topology
- **PostgreSQL Database:** Running in Docker container `clipforge_postgres` on host port `5433` (mapped to internal `5432`). Active schema is at Alembic head revision `f3b4c5d6e7f8`. All tables, foreign key constraints, and indices are healthy.
- **Redis Cache & Broker:** Running in Docker container `clipforge_redis` on host port `6379`. Healthy.
- **Celery Worker:** Running in Docker container `clipforge_worker`. 29 tasks registered across orchestration, analysis, video processing, audio, clipping, and studio domains. Healthy.
- **Celery Beat:** Running in Docker container `clipforge_beat` with periodic task schedule. Healthy.
- **Celery Flower:** Running in Docker container `clipforge_flower` on port `5555`. Healthy.
- **FastAPI Backend:** Running in Docker container `clipforge_backend` on port `8000`. Healthy.
- **Next.js Frontend:** Running on port `3000`. Clean TypeScript compilation (`npx tsc --noEmit` exits with 0 errors) and production build prerenders all 10 routes cleanly (`npm run build` exits 0).

---

## 2. Inventory of Existing Implementation vs. Target Requirements

| Architectural Component | Current Implementation State | Target Capabilities Required | Gap / Refinement Required |
|---|---|---|---|
| **Channel Settings & Defaults** | `Channel` model stores basic metadata (`auto_clip`, `auto_publish`, `auto_pilot`, `publish_destination_id`). No processing parameters (duration, layout, split strategy, clip count) are stored per channel. | Complete persistent processing profile per channel (clip duration mode/bounds capped at 30s max, clips count, splitting strategy, layout/aspect ratio, reframe mode, scoring mode, publishing destination). | Add `processing_profile` JSON column to `channels` via forward migration; create profile editor and validator in backend and frontend enforcing <= 30s Shorts limit. |
| **Video Discovery** | `downloader.get_channel_videos` fetches latest N videos (fixed default `max_results=5`). No pagination support. | Complete video discovery across entire channel history with pagination contract (`items`, `page`, `page_size`, `has_more`), incremental loading, and processing status indication. | Extend `get_channel_videos` with `--playlist-start` and `--playlist-end`; provide paginated API and UI controls; match against DB jobs/clips. |
| **Automatic Monitoring** | `services/channel_monitor.py` has basic loop checking `Channel.is_active` and `Channel.auto_clip`, immediately queuing `start_video_processing_task`. | Periodic quota-conscious discovery, stable deduplication against `Video` and `VideoDecision`, canonical video record persistence, and dispatch to 20-second decision flow. | Periodic monitoring via scheduler/Beat; connect to decision flow instead of immediate hardcoded job start. |
| **Decision Window (20s)** | Does not exist. Discovered videos either immediately process or do nothing. | Durable 20-second decision window backed by PostgreSQL state (`VideoDecision`), countdown toast in UI, customize option with bounded lease (120s), default resolution on expiry or abandonment. | Add `video_decisions` table with unique constraint on `(channel_id, youtube_id)`, Celery ETA countdown task, scheduler deadline sweep with row locking, REST endpoints (`/pending-decisions`, `/customize`, `/apply-defaults`, `/save-and-process`, `/cancel`). |
| **Per-Video Overrides** | `Job.config` accepts arbitrary JSON, but UI only supplies basic options from upload form. No concept of overriding channel profile for one video. | Seamless inheritance: Explicit Video Override → Saved Channel Default → System Default (all <= 30s). Overrides change only the target video, preserving channel defaults. | Implement configuration resolution pipeline; persist snapshot into `Job.config`; provide interactive customization modal. |
| **Processing Pipeline** | Full Celery orchestration: download → validate → extract audio → transcribe & scene detect (chord) → candidate generation → scoring → clip selection → reframe → render → validate → publish. | Reuse existing pipeline completely without creating redundant pipelines. Apply channel/override config faithfully. | Feed resolved layout, duration, clip count, and splitting strategy directly into `candidate_generation_task` and `reframe_task`. |
| **Processing History** | Basic `Job` timestamps (`created_at`, `updated_at`). UI displays relative time or basic status. | Full audit trail: discovery time, queue time, pipeline start time, stage milestones, completion/failure timestamps, duration, error messages, formatted in `Asia/Kolkata` (`13 Oct 2026, 12:45:30 IST`). | Add explicit timing tracking on `Job`; format timestamps in Asia/Kolkata timezone; add history drawer/view in UI. |
| **Cancellation & Recovery** | Job cancellation route updated to `JobStatus.CANCELLED`, revokes celery tasks, halts workers. | Safe cancellation extending to pending decisions; recovery of stranded decision records and jobs on worker/app restart. | Add pending decision cancellation; add startup recovery for expired or orphaned decisions. |
| **Publishing Isolation** | `PUBLISH_MODE="test"`. 0 live YouTube uploads. Destination inheritance verified. | Strict maintenance of mock publishing in tests; independent `auto_clip` and `auto_publish` toggles; preserve `None (Select at publish time)`. | Maintain test publishing harness; enforce independent toggle logic. |

---

## 3. Mapping to the Ten Logic Domains (L1–L10)

1. **L1 (Runtime & Security):**
   - Retain current container configuration, volume mounts (`/app/uploads`, `/app/outputs`), and environment variables.
   - Maintain `PUBLISH_MODE="test"`.
2. **L2 (Data Model & Schema Lifecycle):**
   - Create forward migration `f4c5d6e7f8a9_add_channel_profiles_and_video_decisions.py` revising `f3b4c5d6e7f8`.
   - Add `processing_profile` to `channels`.
   - Add `video_decisions` table with indices.
   - Add execution timing columns (`pipeline_started_at`, `completed_at`, `channel_id`) to `jobs`.
3. **L3 (Storage & Artifact Lifecycle):**
   - Preserve 1.5x disk space reservation and single-writer file fencing.
   - Outputs stored under `outputs/<video_id>/clips/<clip_id>/`.
4. **L4 (Upload Intake & Media Validation):**
   - Extend `get_channel_videos` in `downloader.py` to support pagination without breaking single-video downloads.
5. **L5 (Batch & Job Orchestration):**
   - Celery Beat schedule updated with periodic channel monitor and decision deadline sweep.
   - `start_video_processing_task` dispatches existing chain/chord with snapshot config.
   - Parent job completion aggregation and chord failure handling preserved.
6. **L6 (Core Video-Processing Pipeline):**
   - `reframe_task` honors `video_layout` (portrait 9:16, landscape 16:9, square 1:1) and `reframe_mode`.
   - Zero caption/subtitle burn-in strictly preserved.
7. **L7 (Clip Outputs & Internal Analysis):**
   - `candidate_generation_task` consumes `segmentation_strategy`, `target_duration`, `min_clip_duration`, `max_clip_duration`, `clips_count`.
   - Transcription preserved strictly for scoring and metadata.
8. **L8 (Publishing & External Integrations):**
   - Independent `auto_publish` toggle honored.
   - Preserved `None (Select at publish time)` without silent fallback.
9. **L9 (Backend API Contracts):**
   - Extend `backend/api/routes/channels.py`:
     - `GET /api/channels/{id}/videos` with pagination and status.
     - `GET /api/channels/pending-decisions` for active countdown prompts.
     - `POST /api/channels/decisions/{id}/apply-defaults`.
     - `POST /api/channels/decisions/{id}/customize`.
     - `POST /api/channels/decisions/{id}/save-and-process`.
     - `POST /api/channels/decisions/{id}/cancel`.
10. **L10 (Frontend Workflows & User-Facing State):**
    - Channel profile editor on `/automation`.
    - Paginated video browser with multi-select and "Process Selected".
    - 20-second countdown notification banner/toast with customize modal.
    - Timezone-aware history presentation (`Asia/Kolkata`).

---

## 4. Current Test Suite Baseline

- **Pytest Suite:** 111 tests collected, 12 focused tests passed in latest verification run (4.43s).
- **Frontend Test Suite:** 34 tests (Node/Playwright), `tsc --noEmit` clean (0 errors), `npm run build` clean (0 errors).
- **Total Baseline Test Suite:** 145 / 145 Passed.
- **Protected Baseline Commit:** `0ba85ff`.
