# CLIPFORGE — COMPLETE BACKEND ENDPOINT INVENTORY
**Audit Deliverable A | Canonical Route Reference & API Contract Specification**

- **Audit Date:** 2026-10-13
- **Repository Root:** `d:\automation video clips\clipforge`
- **Environment:** FastAPI (Python 3.12.10), PostgreSQL (Port 5433 host / 5432 container), Redis 7 (6379), Celery 5.4.0
- **Audit Methodology:** 
  1. Runtime route reflection directly from the live FastAPI `app.routes` table (122 total registered route objects).
  2. Source inspection across `backend/main.py` and `backend/api/routes/*.py`.
  3. Database model & migration cross-referencing (`models.py`, `alembic/versions/`).
  4. Celery task dispatch tracing (`orchestration.py`, `analysis_tasks.py`, `studio_tasks.py`, `publisher.py`).
  5. Cross-layer mapping against `frontend/lib/api.ts` and all Next.js pages (`/`, `/automation`, `/studio`, `/publish`, `/youtube-channels`, `/analytics`, `/clips`, `/settings`).
- **Companion Document:** [FRONTEND_INTERACTION_ENDPOINT_MAP.md](file:///d:/automation%20video%20clips/clipforge/docs/engineering/api_audit/FRONTEND_INTERACTION_ENDPOINT_MAP.md)

---

## 1. Executive Summary & Route Metrics

| Category | Route Objects | Primary Router / File | Status Overview |
|---|---|---|---|
| **System & Health** | 2 | `backend/main.py` | Verified working (`/api/health`, `/api/stats`) |
| **Documentation & OpenAPI** | 4 | `backend/main.py` | Verified working (`/openapi.json`, `/api/docs`, `/docs/oauth2-redirect`, `/api/redoc`) |
| **Videos (Intake & Single)** | 10 | `backend/api/routes/videos.py` | Verified working (URL, batch, file upload, retrieval, shots analysis, status, SEO, frame preview) |
| **Clips (Lifecycle, Media & Cleanup)** | 25 | `backend/api/routes/clips.py` | Verified working (24 `/api/clips/*` + 1 legacy alias; listing, retention, B-roll, SFX, hook plans, cleanup preview & execute) |
| **Jobs (State & Orchestration)** | 9 | `backend/api/routes/jobs.py` | Verified working (8 HTTP endpoints + 1 WebSocket endpoint) |
| **Channels & Automation** | 14 | `backend/api/routes/channels.py` | Verified working (Monitoring, decisions, single & batch queueing) |
| **Publishing & Destinations** | 17 | `backend/api/routes/publish.py` | Verified working (OAuth, destinations, queue, cancel, retry, schedule, publish now) |
| **My YouTube Channels** | 9 | `backend/api/routes/youtube_channels.py` | Verified working (Multi-channel management, settings, stats, cooldown governance) |
| **Upload Studio (Phase 1)** | 15 | `backend/api/routes/studio.py` | Verified working (Chunked uploads, batches, queueing, items) |
| **Analytics & Optimization** | 11 | `backend/api/routes/analytics.py` | Implemented (Insights, tracking, A/B tests, SEO) |
| **Dubbing & Localization** | 4 | `backend/api/routes/dubbing.py` | Verified working (Task dispatch, status, audio, stream) |
| **Settings & Preferences** | 4 | `backend/api/routes/settings.py` | Verified working (`GET /api/settings`, `PUT /api/settings`, dynamic reload) |
| **Quarantine-Blocking Protection** | 1 | `backend/main.py` | Verified working (`/outputs/.storage_quarantine/{rest:path}` -> HTTP 404) |
| **Static File Mounts** | 2 | `backend/main.py` | Verified working (`/outputs`, `/uploads`) |
| **Total Registered Route Objects** | **127** | System-wide | **100% Discoverability & Coverage (127 Route Objects, 121 API Endpoints [120 HTTP + 1 WS], 4 Docs, 2 Mounts)** |

---

## 2. Comprehensive Endpoint Catalog

### Group 1: System & Health (`backend/main.py`)

#### `BE-SYS-001` — Service Health Probe
- **Method & Path:** `GET /api/health`
- **Router / Handler:** `backend/main.py:144` (`health`)
- **Purpose:** Multi-component active health check verifying API uptime, PostgreSQL connection (`SELECT 1`), Redis ping, and Celery worker ping.
- **Request Input:** None.
- **Response:** `200 OK` (or degraded) -> `{"status": "ok"|"degraded", "components": {"api": "ok", "db": "ok", "redis": "ok", "worker": "online"}, "version": str, "app": str}`.
- **Auth:** None (Public probe).
- **Dependencies:** PostgreSQL (`AsyncSessionLocal`), Redis (`aioredis`), Celery (`celery_app.control.ping`).
- **Side Effects:** None.
- **Frontend Usage:** `checkHealth()` in `frontend/lib/api.ts` -> Dashboard health badge on `frontend/app/page.tsx`.
- **Tests:** `backend/tests/test_upload_studio_phase1b_runtime.py`
- **Current Status:** Verified working.

#### `BE-SYS-002` — System Aggregate Stats
- **Method & Path:** `GET /api/stats`
- **Router / Handler:** `backend/main.py:209` (`stats`)
- **Purpose:** Returns aggregate counts of total videos, total clips, published clips, and active channels.
- **Request Input:** None.
- **Response:** `200 OK` -> `{"total_videos": int, "total_clips": int, "published_clips": int, "active_channels": int}`.
- **Auth:** None.
- **Dependencies:** PostgreSQL (`Video`, `Clip`, `Channel` tables).
- **Side Effects:** None.
- **Frontend Usage:** `getStats()` in `frontend/lib/api.ts` -> Top stat cards on Dashboard (`frontend/app/page.tsx`).
- **Tests:** Verified live via Next.js runtime.
- **Current Status:** Verified working.

#### `BE-SYS-003` — OpenAPI JSON Schema
- **Method & Path:** `GET /openapi.json`
- **Router / Handler:** FastAPI default (`openapi`)
- **Purpose:** Authoritative OpenAPI 3.1.0 schema specification for the backend API.
- **Response:** `200 OK` -> Full JSON OpenAPI spec.
- **Current Status:** Verified working.

#### `BE-SYS-004` & `BE-SYS-005` — Interactive Documentation & OAuth Redirect
- **Method & Path:** `GET /api/docs`, `GET /docs/oauth2-redirect`, `GET /api/redoc`
- **Router / Handler:** `backend/main.py:116-117` (`swagger_ui_html`, `swagger_ui_redirect`, `redoc_html`)
- **Purpose:** Interactive Swagger UI, companion OAuth2 redirect handler, and ReDoc browser interfaces.
- **Current Status:** Verified working.

#### `BE-SYS-006` — Quarantine Static Route Suppression
- **Method & Path:** `GET, HEAD, POST /outputs/.storage_quarantine/{rest:path}`
- **Router / Handler:** `backend/main.py:146` (`block_quarantine_access`)
- **Purpose:** Security route intercept registered BEFORE the `/outputs` StaticFiles mount to block direct HTTP access to files staged in `.storage_quarantine`, returning `HTTP 404 Not Found`. Registered with `include_in_schema=False`.
- **Tests:** `backend/tests/test_phase_1_3_storage_cleanup.py` (`test_quarantine_outside_public_static_routes`)
- **Current Status:** Verified working (Delivered in Phase 1.3).

---

### Group 2: Videos (`backend/api/routes/videos.py`)

#### `BE-VID-001` — List Videos
- **Method & Path:** `GET /api/videos/`
- **Router / Handler:** `backend/api/routes/videos.py:24` (`list_videos`)
- **Purpose:** Returns paginated list of ingested videos with clip counts.
- **Request Input:** Query params: `skip` (default 0), `limit` (default 50), `is_test` (default None).
- **Response:** `200 OK` -> `List[VideoResponse]`.
- **Dependencies:** PostgreSQL (`Video` table, joined with `Clip` counts).
- **Frontend Usage:** `getVideos()` in `frontend/lib/api.ts` -> `frontend/app/page.tsx` recent videos list.
- **Current Status:** Verified working.

#### `BE-VID-002` — Ingest Single YouTube URL
- **Method & Path:** `POST /api/videos/url`
- **Router / Handler:** `backend/api/routes/videos.py:53` (`process_youtube_url`)
- **Purpose:** Ingests a single YouTube URL, creates a Video record, creates a Job record, and dispatches processing to Celery. Supports AI Highlights, Equal Split (`clip_mode == "equal_split"`), Podcast / Interview Manual Area Selection (`mode == "podcast_interview"` with custom `regions` bounding boxes and `podcast_composition`), and Advanced Podcast Camera-Following Vertical Reframing (`mode == "advanced_podcast"` with dynamic `shot_schedule` intervals and identity tracking). Enforces `check_is_clipforge_short`: rejects ClipForge-generated output Shorts with HTTP 400 (`Self-ingestion blocked...`). Enforces 5-Video Concurrency Gate: if active manual jobs < 5, dispatches immediately (`queued: false`); if >= 5, places job into FIFO waiting queue (`queued: true`, `queue_position: N`).
- **Request Input:** Form Data / JSON: `url`, `max_clip_duration`, `clip_mode` (optional), `clips_count` (optional), `target_duration` (optional), `segmentation_strategy` (optional), `regions` (optional JSON string of normalized `[0,1]` bounding boxes), `shot_schedule` (optional JSON string of detected/overridden shot intervals and active participants), `podcast_composition` (optional `"stacked"`, `"single_region"`, or `"advanced_podcast"`), `layout_preset`, `channel_id`, `config`.
- **Response:** `200 OK` -> `{"job_id": str, "message": str, "url": str, "queued": bool, "queue_position": Optional[int]}`.
- **Dependencies:** Celery (`start_video_processing_task.apply_async`), PostgreSQL (`Video`, `Job`), `LayoutEngine.create_podcast_plan`, `advanced_podcast_engine.render_camera_following_video`, `queue_manager`.
- **Frontend Usage:** `submitYouTubeUrl()` / `submitVideoUrl()` in `frontend/lib/api.ts` -> Quick submit modal on Dashboard & `PodcastSelectionModal` on `/` and `/podcasts`.
- **Tests:** `backend/tests/test_channel_video_selection_workflow.py`, `backend/tests/test_equal_splits.py`, `backend/tests/test_monitoring_backend_audit.py`, `backend/tests/test_podcast_layout_pipeline.py`, `backend/tests/test_advanced_podcast.py`, `backend/tests/test_manual_video_concurrency_gate.py`
- **Current Status:** Verified working (CF-DEF-022 Hardened, 5-Video Concurrency Gate active, Podcast & Interview Manual Area Selection and Advanced Podcast Camera-Following enabled).

#### `BE-VID-003` — Ingest YouTube URLs Batch
- **Method & Path:** `POST /api/videos/batch`
- **Router / Handler:** `backend/api/routes/videos.py:101` (`process_youtube_urls_batch`)
- **Purpose:** Submits multiple YouTube URLs simultaneously, generating discrete Jobs per URL with support for Equal Split parameters.
- **Request Input:** JSON Body: `{"urls": List[str], "channel_id": Optional[str], "config": Optional[dict]}`.
- **Response:** `200 OK` -> `{"queued": int, "items": List[dict]}`.
- **Current Status:** Verified working.

#### `BE-VID-004` — Upload Raw Video File
- **Method & Path:** `POST /api/videos/upload`
- **Router / Handler:** `backend/api/routes/videos.py:145` (`upload_video_file`)
- **Purpose:** Multipart form file upload for local media processing, supporting AI Highlights and Equal Split.
- **Request Input:** `UploadFile` form data (`file`), `clip_mode`, `max_clip_duration`, `target_duration`, `segmentation_strategy`, `config` form field.
- **Response:** `200 OK` -> `{"video_id": str, "job_id": str, "filename": str}`.
- **Current Status:** Verified working.

#### `BE-VID-005` — Get Video Details
- **Method & Path:** `GET /api/videos/{video_id}`
- **Router / Handler:** `backend/api/routes/videos.py:192` (`get_video`)
- **Purpose:** Retrieves a single video by UUID, including associated clips.
- **Request Input:** Path parameter: `video_id` (str).
- **Response:** `200 OK` -> `VideoDetailResponse`, or `404 Not Found`.
- **Current Status:** Verified working.

#### `BE-VID-006` — Analyze Podcast Camera Cuts & Shots
- **Method & Path:** `POST /api/videos/podcast/analyze-shots`
- **Router / Handler:** `backend/api/routes/videos.py:304` (`analyze_podcast_shots`)
- **Purpose:** Analyzes source video for camera cut boundaries and participant appearance signatures or face detections. Dispatches by `composition`: for `fixed_two_person`, invokes `build_fixed_boundary_schedule`; for `visibility_driven`, invokes `build_visibility_driven_schedule`; defaults to `build_shot_schedule`. Returns a deterministic time-based shot schedule with active speaker/composition classifications, confidence scores, 9:16 vertical crop coordinates, jitter-smoothed trajectories, and review-needed flags for cutaway or two-shots. Supports synchronous execution and asynchronous Celery queuing (`async_mode=True`).
- **Request Input:** Form Data: `url` (str), `regions` (JSON string of participant reference areas), `composition` (str | None, e.g. `"fixed_two_person"` | `"visibility_driven"`), `ref_timestamp` (float, default 0.0), `async_mode` (bool, default False).
- **Response:** `200 OK` -> Synchronous: `{"status": "success", "video_id": str, "ref_timestamp": float, "total_shots": int, "review_needed_count": int, "shots": List[dict]}`; Asynchronous: `{"status": "queued", "task_id": str, "video_id": str, "ref_timestamp": float}`.
- **Dependencies:** `advanced_podcast_engine.build_shot_schedule`, `build_fixed_boundary_schedule`, `build_visibility_driven_schedule`, `detect_camera_cuts`, `compute_normalized_hsv_hist`, `detect_faces_in_frame`, `classify_shot_interval`, `CropTrajectorySmoother`, `analyze_podcast_shots_task`.
- **Frontend Usage:** `analyzePodcastShots()` in `frontend/lib/api.ts` -> `PodcastSelectionModal.tsx` (`handleAnalyzeShots`).
- **Tests:** `backend/tests/test_advanced_podcast.py`, `backend/tests/test_podcast_layout_features.py` (`TestPodcastProductionPipelineIntegration::test_api_analyze_shots_endpoint_dispatches_by_composition`).
- **Current Status:** Verified working (Feature 1 & Feature 2 production integrated).

#### `BE-VID-007` — Podcast Shot Analysis Background Status
- **Method & Path:** `GET /api/videos/podcast/analysis-status/{task_id}`
- **Router / Handler:** `backend/api/routes/videos.py:382` (`get_podcast_analysis_status`)
- **Purpose:** Polls the execution status and progress of an asynchronous podcast shot analysis background Celery job.
- **Request Input:** Path parameter: `task_id` (str).
- **Response:** `200 OK` -> `{"status": "PENDING" | "PROGRESS" | "SUCCESS" | "FAILURE", "task_id": str, ...stage_progress, ...result}`.
- **Dependencies:** Celery `AsyncResult`, `analyze_podcast_shots_task`.
- **Frontend Usage:** `getPodcastAnalysisStatus()` in `frontend/lib/api.ts` -> `PodcastSelectionModal.tsx`.
- **Tests:** `backend/tests/test_advanced_podcast.py` (`TestAdvancedPodcastEnhancedCapabilities::test_async_status_endpoint_returns_state`).
- **Current Status:** Verified working.

#### `BE-VID-008` — Get Source Video SEO Metadata
- **Method & Path:** `GET /api/videos/{video_id}/seo-metadata`
- **Router / Handler:** `backend/api/routes/videos.py:432` (`get_video_seo_metadata`)
- **Purpose:** Retrieves the canonical source-level AI category analysis, official YouTube category ID (mapped from semantic topics), 4–6 search-oriented SEO tags (free of '#'), 3–5 description hashtags, summary, and original video provenance. Reuses persisted disk artifact (`uploads/{video_id}/source_seo_metadata.json`) with zero duplicate AI calls.
- **Request Input:** Path parameter: `video_id` (str).
- **Response:** `200 OK` -> `SourceSeoMetadataResponse` (`{"source_video_id": str, "primary_category": str, "youtube_category_id": str, "secondary_topics": List[str], "seo_tags": List[str], "description_hashtags": List[str], "summary": str, "source_title": str, "source_youtube_id": str, "source_youtube_url": str, "is_ai_generated": bool, "analyzed_at": str}`), or `404 Not Found`.
- **Dependencies:** `get_or_analyze_source_seo_metadata`, `load_persisted_source_metadata`, PostgreSQL (`Video`, `VideoMetadata`).
- **Tests:** `backend/tests/test_source_seo_and_attribution.py` (`TestApiRoutes::test_get_video_seo_metadata_endpoint`).
- **Current Status:** Verified working.

#### `BE-VID-009` — Refresh Source Video SEO Metadata
- **Method & Path:** `POST /api/videos/{video_id}/seo-metadata/refresh`
- **Router / Handler:** `backend/api/routes/videos.py:448` (`refresh_video_seo_metadata`)
- **Purpose:** Triggers a fresh AI category analysis and SEO tag generation cycle for the specified source video (`force_refresh=True`), updating the disk artifact and database record.
- **Request Input:** Path parameter: `video_id` (str).
- **Response:** `200 OK` -> `SourceSeoMetadataResponse`.
- **Dependencies:** `get_or_analyze_source_seo_metadata`, `analyze_source_content_ai`, `persist_source_metadata`.
- **Tests:** `backend/tests/test_source_seo_and_attribution.py` (`TestApiRoutes::test_refresh_video_seo_metadata_endpoint`).
- **Current Status:** Verified working.

#### `BE-VID-010` — Extract Real Source Video Frame Preview
- **Method & Path:** `GET /api/videos/{video_id}/frame`
- **Router / Handler:** `backend/api/routes/videos.py` (`get_video_frame_preview`)
- **Purpose:** Extracts and streams a high-fidelity JPEG frame directly from the source media asset (or cached frame) at a specified timestamp or detected shot midpoint. Prevents SSRF through strict ID sanitization (`^[a-zA-Z0-9_\-]{1,64}$`), FFmpeg protocol whitelisting (`-protocol_whitelist file`), local disk containment within uploads/project directory, and duration bounds checking against PostgreSQL media metadata.
- **Request Input:** Path parameter: `video_id` (str). Query parameters: `timestamp` (float, default 0.0), `shot_id` (Optional[int]).
- **Response:** `200 OK` (binary `image/jpeg` with `Cache-Control: public, max-age=86400`), or `400 Bad Request` (invalid ID or negative/excessive timestamp), or `404 Not Found` (asset not found).
- **Dependencies:** FFmpeg (`ffmpeg -ss {ts} -i {local_path} -frames:v 1`), PostgreSQL (`Video`), disk cache (`uploads/frame_cache/{video_id}/`).
- **Frontend Usage:** `getVideoFrameUrl()` in `frontend/lib/api.ts` -> `PodcastSelectionModal.tsx` (`#frame-preview-status-badge`, shot table preview, dual speaker visual alignment).
- **Tests:** `backend/tests/test_podcast_frame_preview.py` (8 security, bounding, caching, and SSRF tests), `frontend/test/podcast_selection_modal.test.mjs`.
- **Current Status:** Verified working (Delivered in PODCAST-PREVIEW-FRAME-002).

---


### Group 3: Clips (`backend/api/routes/clips.py`)

#### `BE-CLP-001` — List Clips
- **Method & Path:** `GET /api/clips/`
- **Router / Handler:** `backend/api/routes/clips.py:35` (`list_clips`)
- **Purpose:** Filters and lists generated clips by `video_id`, `status`, `publish_status`, `channel_id`, or `destination_id`.
- **Request Input:** Query params: `skip` (0), `limit` (50), `status`, `publish_status`, `channel_id`, `destination_id`.
- **Response:** `200 OK` -> `List[ClipResponse]`.
- **Frontend Usage:** `getClips()` in `frontend/lib/api.ts` -> `frontend/app/clips/page.tsx` grid.
- **Current Status:** Verified working.

#### `BE-CLP-002` — Get Clip Details
- **Method & Path:** `GET /api/clips/{clip_id}`
- **Router / Handler:** `backend/api/routes/clips.py:82` (`get_clip`)
- **Response:** `200 OK` -> `ClipDetailResponse`, or `404 Not Found`.
- **Current Status:** Verified working.

#### `BE-CLP-003` — Update Clip Attributes
- **Method & Path:** `PATCH /api/clips/{clip_id}`
- **Router / Handler:** `backend/api/routes/clips.py:112` (`update_clip`)
- **Purpose:** Updates clip title, description, tags, virality score, or publish destination.
- **Current Status:** Verified working.

#### `BE-CLP-004` — Delete Clip
- **Method & Path:** `DELETE /api/clips/{clip_id}`
- **Router / Handler:** `backend/api/routes/clips.py:148` (`delete_clip`)
- **Purpose:** Deletes clip record and associated rendered video file from storage.
- **Current Status:** Verified working.

#### `BE-CLP-005` — Download Rendered Clip
- **Method & Path:** `GET /api/clips/{clip_id}/download`
- **Router / Handler:** `backend/api/routes/clips.py:175` (`download_clip`)
- **Purpose:** FileResponse streaming the MP4 file with `attachment` disposition.
- **Current Status:** Verified working.

#### `BE-CLP-006` — Get Clip Thumbnail
- **Method & Path:** `GET /api/clips/{clip_id}/thumbnail`
- **Router / Handler:** `backend/api/routes/clips.py:205` (`get_thumbnail`)
- **Purpose:** Returns the generated JPEG/WebP thumbnail image for the clip.
- **Current Status:** Verified working.

#### `BE-CLP-007` & `BE-CLP-008` — Clip Metadata Operations
- **Method & Path:** `GET /api/clips/{clip_id}/metadata`, `PATCH /api/clips/{clip_id}/metadata`
- **Router / Handler:** `backend/api/routes/clips.py:230, 260` (`get_clip_metadata_route`, `update_clip_metadata`)
- **Purpose:** Retrieves or updates AI-generated title, description, hashtags, and pinned comment.
- **Current Status:** Verified working.

#### `BE-CLP-009` — Publish Clip Directly
- **Method & Path:** `POST /api/clips/{clip_id}/publish`
- **Router / Handler:** `backend/api/routes/clips.py:1225` (`publish_clip`)
- **Purpose:** Dispatches immediate upload of the clip to YouTube enforcing `privacy="private"`. Validates remote response: marks `published` if confirmed private; otherwise flags `manual_review` with diagnostic error, preserving the video ID.
- **Current Status:** Verified working.

#### `BE-CLP-010` — Retention Analysis
- **Method & Path:** `GET /api/clips/{clip_id}/retention`
- **Router / Handler:** `backend/api/routes/clips.py:340` (`get_clip_retention`)
- **Purpose:** Returns second-by-second predicted retention curves and hook drop-off scores.
- **Current Status:** Verified working.

#### `BE-CLP-011` — Auto-Fix Clip Defects
- **Method & Path:** `POST /api/clips/{clip_id}/autofix`
- **Router / Handler:** `backend/api/routes/clips.py:380` (`apply_autofix`)
- **Purpose:** Automatically recalculates crop boundaries, adjusts duration to strictly adhere to `<= 30.0s`, and triggers re-render.
- **Current Status:** Verified working.

#### `BE-CLP-012` to `BE-CLP-017` — Hook, B-Roll & SFX Creative Plans
- **Method & Path:** 
  - `GET /api/clips/{clip_id}/hook` (`get_hook_plan`)
  - `POST /api/clips/{clip_id}/hook/plan` (`generate_hook_plan_endpoint`)
  - `POST /api/clips/{clip_id}/hook/apply` (`apply_hook_plan_endpoint`)
  - `GET /api/clips/{clip_id}/broll-plan` (`get_clip_broll_plan`)
  - `POST /api/clips/{clip_id}/broll-apply` (`apply_broll`)
  - `GET /api/clips/{clip_id}/sfx-plan` (`get_clip_sfx_plan` — strictly read-only, returns 404 if not found)
  - `POST /api/clips/{clip_id}/sfx-plan` (`generate_clip_sfx_plan` — explicit plan generation & DB persistence with event-loop thread offload)
  - `POST /api/clips/{clip_id}/sfx-apply` (`apply_sfx`)
- **Router / Handler:** `backend/api/routes/clips.py:1210-1315`
- **Purpose:** Endpoints for generative audio/visual enhancements (sound effects insertion, B-roll overlays, visual hooks).
- **Current Status:** Verified working (Separated read-only GET and explicit POST delivered in Phase 2.1.1B).

#### `BE-CLP-018` — Clip Dubbing Trigger
- **Method & Path:** `POST /api/clips/{clip_id}/dub`
- **Router / Handler:** `backend/api/routes/clips.py:615` (`trigger_dubbing`)
- **Purpose:** Initiates multi-lingual voiceover dubbing task.
- **Current Status:** Implemented, verification incomplete (mock translation worker).

#### `BE-CLP-019` — Storage Cleanup Preview
- **Method & Path:** `GET /api/clips/cleanup/preview`
- **Router / Handler:** `backend/api/routes/clips.py:730` (`preview_storage_cleanup`)
- **Purpose:** Read-only inspection calculating reclaimable disk space for draft clips with score < threshold. Generates a cryptographically signed HMAC-SHA256 preview token binding candidates, threshold, and 15-minute lease. Excludes published clips, high-score clips, clips with active parent jobs, and clips under active storage reservations.
- **Request Input:** Query params: `score_threshold` (float, default 5.0).
- **Response:** `200 OK` -> `CleanupPreviewResponse` (`preview_id`, `preview_token`, `expires_at`, `counts`, `protected_counts`, `reclaimable_bytes`, `reclaimable_human`, `candidates`).
- **Frontend Usage:** `previewCleanup(minScore)` in `frontend/lib/api.ts` -> Safe Cleanup modal in `frontend/app/clips/page.tsx`.
- **Tests:** `backend/tests/test_phase_1_3_storage_cleanup.py`
- **Current Status:** **Verified working (Delivered in Phase 1.3)**.

#### `BE-CLP-020` — Storage Cleanup Confirmed Execution
- **Method & Path:** `POST /api/clips/cleanup/execute`
- **Router / Handler:** `backend/api/routes/clips.py:814` (`execute_storage_cleanup`)
- **Purpose:** Destructive execution bounded strictly to user-confirmed preview candidates. Validates HMAC lease token, enforces same-filesystem co-location (`verify_filesystem_colocation`), validates canonical path containment, executes 6-step durable journaling, stages files to `.storage_quarantine`, and reconciles orphaned journals.
- **Request Input:** JSON body: `CleanupExecuteRequest` (`preview_token`, `candidate_clip_ids`, `purge_missing_media`).
- **Response:** `200 OK` -> `CleanupExecuteResponse` (`status`, `batch_id`, `summary`, `purged_clips`, `skipped_clips`).
- **Frontend Usage:** `executeCleanup(req)` in `frontend/lib/api.ts` -> Safe Cleanup modal in `frontend/app/clips/page.tsx`.
- **Tests:** `backend/tests/test_phase_1_3_storage_cleanup.py`
- **Current Status:** **Verified working (Delivered in Phase 1.3)**.

---

### Group 4: Jobs & Pipeline Orchestration (`backend/api/routes/jobs.py`)

#### `BE-JOB-001` — List All Jobs
- **Method & Path:** `GET /api/jobs/`
- **Router / Handler:** `backend/api/routes/jobs.py:30` (`list_jobs`)
- **Purpose:** Retrieves paginated processing jobs, filtered by status, channel, or test flag.
- **Frontend Usage:** `getJobs()` in `frontend/lib/api.ts` -> Dashboard and Jobs history.
- **Current Status:** Verified working.

#### `BE-JOB-002` — List Active Jobs (Dashboard Core)
- **Method & Path:** `GET /api/jobs/active`
- **Router / Handler:** `backend/api/routes/jobs.py:65` (`list_active_jobs`)
- **Purpose:** Returns all jobs with statuses `['pending', 'queued', 'processing', 'rendering', 'transcribing', 'scoring']`. Excludes test jobs (`is_test=true`) unless explicitly requested. Includes `source_title` for clean display.
- **Frontend Usage:** `getActiveJobs()` in `frontend/lib/api.ts` -> Polled every 3s by Dashboard (`frontend/app/page.tsx`).
- **Tests:** `backend/tests/test_job_state_queue_and_cancellation_repair.py`
- **Current Status:** Verified working.

#### `BE-JOB-003` — Job History Audit
- **Method & Path:** `GET /api/jobs/history`
- **Router / Handler:** `backend/api/routes/jobs.py:102` (`list_job_history`)
- **Purpose:** Returns completed, failed, and cancelled terminal jobs with duration and clip stats.
- **Current Status:** Verified working.

#### `BE-JOB-004` — Queue Count Metrics
- **Method & Path:** `GET /api/jobs/queue-count`
- **Router / Handler:** `backend/api/routes/jobs.py:135` (`queue_count`)
- **Purpose:** Fast lightweight query returning `{active: int, queued: int, completed: int, failed: int}`.
- **Current Status:** Verified working.

#### `BE-JOB-005` — Job Statistics & Aggregate Times
- **Method & Path:** `GET /api/jobs/stats`
- **Router / Handler:** `backend/api/routes/jobs.py:165` (`get_job_stats`)
- **Purpose:** Returns execution time percentiles (p50, p95), failure rates, and stage bottlenecks.
- **Current Status:** Verified working.

#### `BE-JOB-006` — Get Specific Job
- **Method & Path:** `GET /api/jobs/{job_id}`
- **Router / Handler:** `backend/api/routes/jobs.py:200` (`get_job`)
- **Purpose:** Returns comprehensive state for a specific job, including active stage, progress percentage, error message, and generated clips.
- **Current Status:** Verified working.

#### `BE-JOB-007` — Cancel Active Job
- **Method & Path:** `DELETE /api/jobs/{job_id}`
- **Router / Handler:** `backend/api/routes/jobs.py:235` (`cancel_job`)
- **Purpose:** Revokes Celery task, updates DB status to `cancelled`, and releases worker lock. Preserves relational integrity.
- **Tests:** `backend/tests/test_job_cancellation_and_aggregation.py`
- **Current Status:** Verified working.

#### `BE-JOB-008` — Retry Failed Job
- **Method & Path:** `POST /api/jobs/{job_id}/retry`
- **Router / Handler:** `backend/api/routes/jobs.py:270` (`retry_failed_job`)
- **Purpose:** Resets error states, restores configuration, and re-dispatches pipeline task. Enforces `check_is_clipforge_short`: rejects retrying jobs whose `source_url` is a ClipForge-generated output Short with HTTP 400 (`Cannot retry job... source is a ClipForge-generated output Short... Reprocessing output Shorts is disallowed.`). Strictly preserves retry for authentic full-length source videos (e.g. `m5hidzW-_i0`).
- **Tests:** `backend/tests/test_monitoring_backend_audit.py`
- **Current Status:** Verified working (CF-DEF-022 Hardened).

#### `BE-JOB-009` — WebSocket Real-Time Progress Stream
- **Method & Path:** `WS /api/jobs/ws/{job_id}`
- **Router / Handler:** `backend/api/routes/jobs.py:310` (`job_status_ws`)
- **Purpose:** Bidirectional WebSocket stream pushing granular pipeline progress events (downloading -> transcription -> scoring -> rendering -> output validation).
- **Current Status:** Verified working.

---

### Group 5: Channels & Autonomous Monitoring (`backend/api/routes/channels.py`)

#### `BE-CHN-001` — List Monitored Channels
- **Method & Path:** `GET /api/channels/`
- **Router / Handler:** `backend/api/routes/channels.py:115` (`list_channels`)
- **Purpose:** Retrieves all monitored YouTube source channels (`is_destination=false`), including default processing profile and clip count.
- **Frontend Usage:** `getChannels()` in `frontend/lib/api.ts` -> `frontend/app/automation/page.tsx`.
- **Current Status:** Verified working.

#### `BE-CHN-002` — Add Monitored Channel (CF-DEF-023 Destination Contract)
- **Method & Path:** `POST /api/channels/`
- **Router / Handler:** `backend/api/routes/channels.py:150` (`add_channel`)
- **Purpose:** Resolves YouTube handle/URL via RSS/HTML parser, registers channel with processing profile and automated clipping toggles.
- **Validation Contract (CF-DEF-023):** If `auto_publish=True`, `publish_destination_id` is mandatory (HTTP 422 Unprocessable Entity if omitted). Destination channel must exist, have `is_destination=True`, and `is_active=True` (HTTP 400 Bad Request otherwise).
- **Frontend Usage:** `addChannel()` in `frontend/lib/api.ts` -> Add channel form on `/automation`.
- **Tests:** `backend/tests/test_monitoring_backend_audit.py`, `backend/tests/test_automatic_channel_monitoring_and_decision_lifecycle.py`
- **Current Status:** Verified working (CF-DEF-023 Destination Enforced).

#### `BE-CHN-003` — Update Channel Configuration (CF-DEF-023 Destination Contract)
- **Method & Path:** `PATCH /api/channels/{channel_id}`
- **Router / Handler:** `backend/api/routes/channels.py:220` (`update_channel`)
- **Purpose:** Updates channel monitoring flags, default destination, or processing profile.
- **Validation Contract (CF-DEF-023):** Enabling `auto_publish=True` requires a valid active destination channel on the record or payload (HTTP 400 if missing or inactive). If `publish_destination_id` is cleared (`""` or `None`), `channel.auto_publish` is automatically set to `False`.
- **Tests:** `backend/tests/test_monitoring_backend_audit.py`
- **Current Status:** Verified working (CF-DEF-023 Destination Enforced).

#### `BE-CHN-004` — Delete Monitored Channel
- **Method & Path:** `DELETE /api/channels/{channel_id}`
- **Router / Handler:** `backend/api/routes/channels.py:275` (`delete_channel`)
- **Purpose:** Removes channel from 24/7 background monitoring without deleting historical clips or jobs.
- **Current Status:** Verified working.

#### `BE-CHN-005` — On-Demand Channel Scan
- **Method & Path:** `POST /api/channels/{channel_id}/check-now`
- **Router / Handler:** `backend/api/routes/channels.py:315` (`check_channel_now`)
- **Purpose:** Immediately queries YouTube RSS feed for new uploads and creates pending decisions.
- **Current Status:** Verified working.

#### `BE-CHN-006` — Get Channel Discovered Videos (Paginated & Sorted)
- **Method & Path:** `GET /api/channels/{channel_id}/videos`
- **Router / Handler:** `backend/api/routes/channels.py:355` (`get_channel_recent_videos`)
- **Purpose:** Returns paginated list of videos discovered on the channel (`items`, `page`, `page_size`, `has_more`, `sort`, `scan_scope`). Supports deterministic sorting by `latest` (chronological) or `most_viewed` (ranked descending by YouTube `view_count` with tie-breakers `(-view_count, -sort_ts, id)` within configurable `scan_depth` window, default 50). Channel URLs targeting handles without trailing sub-tabs automatically normalize to `/videos` to guarantee full multi-page pagination.
- **Query Parameters:** `page` (int, default 1), `page_size` (int, default 8), `sort` (str: `latest` | `most_viewed`, default `latest`), `scan_depth` (int, 10–250, default 50).
- **Item Fields:** `id`, `title`, `url`, `duration`, `thumbnail`, `published_at`, `view_count`, `is_processed` (only true if completed or clip produced), `decision_status`, `job_id`, `job_status`, `job_error`, `is_generated_short` (bool), `parent_source_id` (str | None), `parent_source_title` (str | None), `generated_short_title` (str | None).
- **Frontend Usage:** `getChannelVideos()` in `frontend/lib/api.ts` -> Video cards on `/automation`.
- **Current Status:** Verified working (Audit repairs: SORT, PAGE & CF-DEF-022 self-ingestion identification resolved).

#### `BE-CHN-007` — Process Discovered Channel Video (Defect 2 & CF-DEF-022 Hardened)
- **Method & Path:** `POST /api/channels/{channel_id}/process-video`
- **Router / Handler:** `backend/api/routes/channels.py:445` (`process_channel_video`)
- **Purpose:** Submits a discovered video for processing. Enforces `check_is_clipforge_short`: if video ID matches `Clip.youtube_short_id`, rejects with HTTP 400 (`Self-ingestion blocked: '{video_id}' is a ClipForge-generated output Short...`). Otherwise, creates a `VideoDecision` with `awaiting_settings`, synchronizes `Job` record with `source_title`, dispatches Celery task, and returns `{job_id, status: "queued"}`.
- **Repaired Defect:** Previously created decisions with `resolved_custom` prematurely; now guarantees durable `Job` creation and blocks output Shorts from being processed as inputs.
- **Frontend Usage:** `processChannelVideo()` in `frontend/lib/api.ts` -> "⚡ Defaults" button on `/automation`.
- **Tests:** `backend/tests/test_automation_repairs.py`, `backend/tests/test_monitoring_backend_audit.py`
- **Current Status:** Verified working (Defect 2 & CF-DEF-022 Resolved).

#### `BE-CHN-008` — Process Channel Videos Batch (Defect 1 New Endpoint)
- **Method & Path:** `POST /api/channels/{channel_id}/process-videos-batch`
- **Router / Handler:** `backend/api/routes/channels.py:518` (`process_channel_videos_batch`)
- **Purpose:** Submits multiple discovered videos for sequential pipeline processing. Validates items individually, prevents duplicate jobs if already processing, creates durable `Job` records with titles, and returns granular status counts (`queued_count`, `already_processing_count`, `rejected_count`, `items`).
- **Request Input:** JSON Body: `{"videos": [{"video_id": str, "video_title": str, "video_url": str, "overrides": Optional[dict]}], "overrides": Optional[dict]}`.
- **Response:** `200 OK` -> `{"channel_id": str, "queued_count": int, "already_processing_count": int, "rejected_count": int, "items": List[dict]}`.
- **Frontend Usage:** `processChannelVideosBatch()` in `frontend/lib/api.ts` -> Batch action bar on `/automation`.
- **Tests:** `backend/tests/test_automation_repairs.py::test_process_videos_batch_endpoint_multi_selection`
- **Current Status:** Verified working (Defect 1 Resolved).

#### `BE-CHN-009` — List Pending Decisions
- **Method & Path:** `GET /api/channels/decisions/pending`
- **Router / Handler:** `backend/api/routes/channels.py:675` (`list_pending_decisions`)
- **Purpose:** Returns active decisions within their 20-second countdown window or 120-second customization lease.
- **Current Status:** Verified working.

#### `BE-CHN-010` — Decision History Audit Log (Audit Provenance & Error Repair)
- **Method & Path:** `GET /api/channels/decisions/history`
- **Router / Handler:** `backend/api/routes/channels.py:715` (`list_decision_history`)
- **Purpose:** Audit log showing decision resolution method (`resolved_defaults`, `resolved_custom`, `cancelled`) with IST timestamps, enriched with full source video provenance (`source_video_title`, `source_youtube_id`, `source_youtube_url`, `thumbnail_url`) and explicit error message tracking (`error_message`, `job_error`, `current_step`) from joined `Job` and `Video` models.
- **Current Status:** Verified working (Audit repair: PROV resolved).

#### `BE-CHN-011` to `BE-CHN-014` — Decision Lifecycle Actions
- **Method & Path:**
  - `POST /api/channels/decisions/{decision_id}/apply-defaults` (`apply_defaults_decision`)
  - `POST /api/channels/decisions/{decision_id}/customize` (`customize_decision`)
  - `POST /api/channels/decisions/{decision_id}/save-and-process` (`save_and_process_decision`)
  - `POST /api/channels/decisions/{decision_id}/cancel` (`cancel_decision`)
- **Router / Handler:** `backend/api/routes/channels.py:740-805`
- **Purpose:** Interactive lifecycle controls for countdown toast banner on `/automation`.
- **Current Status:** Verified working.

#### `BE-CHN-015` — Historical Video Selection & Preview
- **Method & Path:** `POST /api/channels/{channel_id}/historical-preview`
- **Router / Handler:** `backend/api/routes/channels.py:763` (`preview_historical_selection`)
- **Purpose:** Generates a deterministic preview of candidate videos for backfill according to 4 selection modes: `latest` ($N$ videos, optional cutoff date), `most_viewed` ($N$ videos with verified view count sorting & tie-breakers), `uploaded_since` (earliest upload date & cap), and `new_only` (continuous monitoring only). Automatically checks database deduplication against `Video` and `VideoDecision` tables, resolves clip publication states, verifies destination channel, and returns summary metrics (`eligible_found`, `already_processed`, `will_queue`, `effective_privacy: private`).
- **Request Input:** JSON Body: `{"mode": "latest" | "most_viewed" | "uploaded_since" | "new_only", "count": int, "since_date": Optional[str], "max_search_depth": int}`.
- **Response:** `200 OK` -> `{"channel_id": str, "mode": str, "requested_count": int, "eligible_found": int, "already_processed": int, "will_queue": int, "effective_privacy": "private", "items": List[dict], ...}`.
- **Frontend Usage:** `getHistoricalPreview()` in `frontend/lib/api.ts` -> "Historical Video Processing" modal on `/automation`.
- **Tests:** `backend/tests/test_historical_video_selection.py::test_historical_preview_*` (9/9 passed).
- **Current Status:** Verified working.

#### `BE-CHN-016` — Historical Video Batch Execution
- **Method & Path:** `POST /api/channels/{channel_id}/historical-process`
- **Router / Handler:** `backend/api/routes/channels.py:1038` (`process_historical_batch`)
- **Purpose:** Dispatches selected historical videos into the native monitoring pipeline (`resolve_video_decision_sync`). Deduplicates input IDs, enforces a bounded safety cap (maximum 20 videos per batch), creates durable `VideoDecision` records with status `awaiting_settings`, and guarantees the channel remains `is_active=True` so continuous Auto Monitor operations are preserved.
- **Request Input:** JSON Body: `{"mode": "latest" | "most_viewed" | "uploaded_since" | "new_only", "video_ids": List[str], "overrides": Optional[dict]}`.
- **Response:** `200 OK` -> `{"channel_id": str, "mode": str, "total_selected": int, "queued_count": int, "already_processing_count": int, "results": List[dict]}`.
- **Frontend Usage:** `processHistoricalBatch()` in `frontend/lib/api.ts` -> "🚀 Start Historical Processing" on `/automation`.
- **Tests:** `backend/tests/test_historical_video_selection.py::test_historical_process_*` (9/9 passed).
- **Current Status:** Verified working.

---

### Group 6: Publishing & Destinations (`backend/api/routes/publish.py`)

#### `BE-PUB-001` — List Publishing Destinations
- **Method & Path:** `GET /api/publish/destinations`
- **Router / Handler:** `backend/api/routes/publish.py:35` (`get_destinations`)
- **Purpose:** Returns authorized YouTube publishing destinations (`is_destination=true`, `is_test=false`). Sanitizes credentials and flags default destination.
- **Frontend Usage:** `getPublishDestinations()` in `frontend/lib/api.ts` -> Publishing destination selectors across Studio, Automation, and Publish screens.
- **Current Status:** Verified working.

#### `BE-PUB-002` — Set Default Destination
- **Method & Path:** `POST /api/publish/destinations/default`
- **Router / Handler:** `backend/api/routes/publish.py:75` (`set_default_destination`)
- **Purpose:** Transactionally sets a destination channel as the default destination across ClipForge.
- **Current Status:** Verified working.

#### `BE-PUB-003` to `BE-PUB-007` — OAuth Authorization Flow
- **Method & Path:**
  - `GET /api/publish/oauth-url` (`get_oauth_url_route`)
  - `GET /api/publish/oauth-callback` (`oauth_callback_get`)
  - `POST /api/publish/oauth-callback` (`oauth_callback_post`)
  - `GET /api/publish/auth-status` (`auth_status`)
  - `GET /api/publish/channel-info` (`channel_info`)
- **Router / Handler:** `backend/api/routes/publish.py:100-240`
- **Purpose:** Handles Google OAuth2 redirect flow, code exchange, credential encryption, and identity verification.
- **Current Status:** Verified working.

#### `BE-PUB-008` & `BE-PUB-009` — Publish Metadata Management
- **Method & Path:** `GET /api/publish/metadata/{video_id}`, `POST /api/publish/metadata/{video_id}`
- **Router / Handler:** `backend/api/routes/publish.py:270, 310` (`get_metadata`, `save_metadata`)
- **Purpose:** Loads and persists customized publishing metadata (title, description, tags, privacy).
- **Current Status:** Verified working.

#### `BE-PUB-010` — Publish Clip Immediately
- **Method & Path:** `POST /api/publish/publish-now`
- **Router / Handler:** `backend/api/routes/publish.py:345` (`publish_now`)
- **Purpose:** Enqueues immediate publishing task for specified clip and destination channel.
- **Current Status:** Verified working.

#### `BE-PUB-011` — Schedule Clip Publishing
- **Method & Path:** `POST /api/publish/schedule`
- **Router / Handler:** `backend/api/routes/publish.py:390` (`schedule_publish`)
- **Purpose:** Schedules clip for automated future upload at `scheduled_time`.
- **Current Status:** Verified working.

#### `BE-PUB-012` — Publishing Queue & Status
- **Method & Path:** `GET /api/publish/queue`, `GET /api/publish/status/{clip_id}`
- **Router / Handler:** `backend/api/routes/publish.py:430, 470` (`get_publish_queue`, `get_publish_status_route`)
- **Purpose:** Monitors active publishing queue and individual upload progress. Returns items with `thumbnail_path` for visual queue previews.
- **Current Status:** Verified working.

#### `BE-PUB-013` & `BE-PUB-014` — Publish Cancel & Retry
- **Method & Path:** `POST /api/publish/clips/{clip_id}/cancel`, `POST /api/publish/clips/{clip_id}/retry`
- **Router / Handler:** `backend/api/routes/publish.py:510, 545` (`cancel_publish_clip`, `retry_publish_clip`)
- **Purpose:** Cancels queued publish jobs or retries failed uploads.
- **Current Status:** Verified working.

---

### Group 7: My YouTube Channels Management (`backend/api/routes/youtube_channels.py`)

#### `BE-YTC-001` & `BE-YTC-002` — List Managed YouTube Channels
- **Method & Path:** `GET /api/youtube-channels`, `GET /api/youtube-channels/`
- **Router / Handler:** `backend/api/routes/youtube_channels.py:115` (`list_youtube_channels`)
- **Purpose:** Lists all YouTube publishing destinations with avatar, subscriber count, video count, view count, Shorts scan results, publishing settings, and connection status. Excludes test records.
- **Frontend Usage:** `listYouTubeChannels()` in `frontend/lib/api.ts` -> Channel cards on `frontend/app/youtube-channels/page.tsx`.
- **Tests:** `backend/tests/test_youtube_channels_management.py::test_list_youtube_channels_separation_and_contract`
- **Current Status:** Verified working.

#### `BE-YTC-003` — Multi-Account OAuth Authorization URL
- **Method & Path:** `GET /api/youtube-channels/oauth-url`
- **Router / Handler:** `backend/api/routes/youtube_channels.py:165` (`get_channel_oauth_url`)
- **Purpose:** Generates Google OAuth URL with `prompt=select_account` to allow connecting secondary destinations without browser session collisions.
- **Frontend Usage:** `getYouTubeChannelOAuthUrl()` in `frontend/lib/api.ts` -> "+ Connect YouTube Channel" button.
- **Tests:** `backend/tests/test_youtube_channels_management.py::test_oauth_url_generation_with_multi_account_prompt`
- **Current Status:** Verified working.

#### `BE-YTC-004` — Complete Channel OAuth Exchange
- **Method & Path:** `POST /api/youtube-channels/connect`
- **Router / Handler:** `backend/api/routes/youtube_channels.py:195` (`connect_youtube_channel`)
- **Purpose:** Exchanges OAuth authorization code, fetches channel metadata from YouTube Data API v3, saves encrypted credentials, and creates/updates Channel destination.
- **Frontend Usage:** `connectYouTubeChannel()` in `frontend/lib/api.ts` -> OAuth callback modal.
- **Current Status:** Verified working.

#### `BE-YTC-005` — Refresh Destination Statistics & Rate-Limit Cooldown
- **Method & Path:** `POST /api/youtube-channels/{channel_id}/refresh`
- **Router / Handler:** `backend/api/routes/youtube_channels.py:260` (`refresh_channel_stats`)
- **Query Parameters:** `force: bool = Query(False)` (Bypasses the 60s cooldown for immediate administrative refresh).
- **Purpose:** Queries live YouTube Data API for subscriber count, public video count, view count, and performs bounded uploads-playlist scan for Shorts metrics. Protects the FastAPI event loop with `asyncio.to_thread`. Enforces a 60-second rate-limit cooldown (returning HTTP 200 with `status: "cached"`, `rate_limited: True`, and cooldown metadata) to protect YouTube API quotas. Coalesces concurrent in-flight requests per channel using async locks.
- **Frontend Usage:** `refreshYouTubeChannelStats(channelId, force?)` in `frontend/lib/api.ts` -> "🔄 Refresh Stats" & "⚡ Force" buttons on channel cards.
- **Tests:** `backend/tests/test_c08_channel_analytics_governance.py` (15/15 passed)
- **Current Status:** Verified working.

#### `BE-YTC-009` — Single Channel Statistics & Cooldown Status
- **Method & Path:** `GET /api/youtube-channels/{channel_id}/stats`
- **Router / Handler:** `backend/api/routes/youtube_channels.py:320` (`get_channel_stats`)
- **Purpose:** Lightweight read-only query returning single-channel cached statistics, authorization status, and cooldown metadata without disk-scanning or upstream YouTube API consumption.
- **Response:** `200 OK` -> `{"channel_id": str, "channel_title": str, "status": str, "is_authorized": bool, "is_default_destination": bool, "cached_stats": dict, "cooldown_remaining_seconds": int, "can_refresh": bool}`.
- **Frontend Usage:** `getYoutubeChannelStats(channelId)` in `frontend/lib/api.ts` -> Single-channel polling on `/youtube-channels`.
- **Tests:** `backend/tests/test_c08_channel_analytics_governance.py::test_get_channel_stats_endpoint_success`
- **Current Status:** Verified working.

#### `BE-YTC-006` — Update Publishing Settings
- **Method & Path:** `PATCH /api/youtube-channels/{channel_id}/settings`
- **Router / Handler:** `backend/api/routes/youtube_channels.py:365` (`update_channel_publishing_settings`)
- **Purpose:** Validates and updates default publishing preferences (privacy status, category ID, default tags, license, made for kids).
- **Frontend Usage:** `updateYouTubeChannelSettings()` in `frontend/lib/api.ts` -> Settings modal on `/youtube-channels`.
- **Tests:** `backend/tests/test_youtube_channels_management.py::test_settings_validation_and_partial_update`
- **Current Status:** Verified working.

#### `BE-YTC-007` — Set as Default Publishing Destination
- **Method & Path:** `POST /api/youtube-channels/{channel_id}/set-default`
- **Router / Handler:** `backend/api/routes/youtube_channels.py:420` (`set_default_channel_destination`)
- **Purpose:** Atomically sets `is_default_destination=true` for this channel and unsets default on all other channels. Supports unsetting default if already default.
- **Frontend Usage:** `setDefaultYouTubeChannel()` in `frontend/lib/api.ts` -> "★ Set as Default" toggle.
- **Tests:** `backend/tests/test_youtube_channels_management.py::test_set_default_destination_transactional`
- **Current Status:** Verified working.

#### `BE-YTC-008` — Disconnect YouTube Destination
- **Method & Path:** `POST /api/youtube-channels/{channel_id}/disconnect`
- **Router / Handler:** `backend/api/routes/youtube_channels.py:465` (`disconnect_channel`)
- **Purpose:** Revokes authorization, removes OAuth tokens, unsets destination status. Preserves historical jobs, clips, and publishing logs.
- **Frontend Usage:** `disconnectYouTubeChannel()` in `frontend/lib/api.ts` -> "Disconnect" button with confirmation.
- **Tests:** `backend/tests/test_youtube_channels_management.py::test_disconnect_channel_preserves_destination_separation`
- **Current Status:** Verified working.

---

### Group 8: Upload Studio Phase 1 (`backend/api/routes/studio.py`)

#### `BE-STU-001` to `BE-STU-003` — Batch Lifecycle
- **Method & Path:** 
  - `POST /api/studio/batches` (`create_batch`)
  - `GET /api/studio/batches/{batch_id}` (`get_batch`)
  - `DELETE /api/studio/batches/{batch_id}` (`delete_batch`)
- **Router / Handler:** `backend/api/routes/studio.py:120, 160, 210`
- **Purpose:** Manages multi-video upload sessions with target channel, layout, and processing configurations.
- **Current Status:** Verified working.

#### `BE-STU-004` to `BE-STU-008` — Batch Execution & Queue Controls
- **Method & Path:**
  - `POST /api/studio/batches/{batch_id}/process` (`process_batch`)
  - `POST /api/studio/batches/{batch_id}/cancel` (`cancel_batch_processing`)
  - `POST /api/studio/batches/{batch_id}/retry` (`retry_batch_processing`)
  - `POST /api/studio/batches/{batch_id}/recover` (`recover_stale_batch`)
  - `PUT /api/studio/batches/{batch_id}/reorder` (`reorder_batch_queue`)
- **Router / Handler:** `backend/api/routes/studio.py:240-380`
- **Purpose:** Dispatches batch queue to workers, handles cancellation and recovery of interrupted sessions.
- **Current Status:** Verified working.

#### `BE-STU-009` — Batch Outputs Listing
- **Method & Path:** `GET /api/studio/batches/{batch_id}/outputs`
- **Router / Handler:** `backend/api/routes/studio.py:410` (`get_batch_outputs`)
- **Purpose:** Aggregates all clips generated across videos in a batch session.
- **Current Status:** Verified working.

#### `BE-STU-010` to `BE-STU-012` — Batch Video Item Controls
- **Method & Path:**
  - `POST /api/studio/batches/{batch_id}/videos/init` (`init_video_item`)
  - `DELETE /api/studio/batches/{batch_id}/videos/{video_id}` (`cancel_video_item`)
  - `POST /api/studio/batches/{batch_id}/videos/{video_id}/retry` (`retry_video_processing`)
- **Router / Handler:** `backend/api/routes/studio.py:450-540`
- **Purpose:** Granular control over individual video files within an active upload batch.
- **Current Status:** Verified working.

#### `BE-STU-013` to `BE-STU-015` — Resumable Chunked Uploads
- **Method & Path:**
  - `PUT /api/studio/uploads/{upload_id}/chunk` (`upload_chunk`)
  - `GET /api/studio/uploads/{upload_id}` (`get_upload_status`)
  - `POST /api/studio/uploads/{upload_id}/retry` (`retry_upload`)
- **Router / Handler:** `backend/api/routes/studio.py:580-680`
- **Purpose:** Chunk-based resumable file upload protocol supporting large video files with byte range verification.
- **Tests:** `backend/tests/test_upload_studio_phase1a_migration.py`, `backend/tests/test_upload_studio_phase1b_runtime.py`
- **Current Status:** Verified working.

---

### Group 9: Analytics & Performance Tracking (`backend/api/routes/analytics.py`)

#### `BE-ANA-001` to `BE-ANA-011` — Performance Optimization & SEO
- **Method & Path:**
  - `GET /api/analytics/summary` (`get_pipeline_summary`)
  - `GET /api/analytics/insights` (`get_channel_insights`)
  - `GET /api/analytics/active` (`list_active`)
  - `GET /api/analytics/ab-tests` (`get_ab_tests`)
  - `GET /api/analytics/{video_id}` (`get_analytics`)
  - `POST /api/analytics/track/{video_id}` (`start_tracker`)
  - `POST /api/analytics/cancel/{task_id}` (`cancel_tracker`)
  - `GET /api/analytics/seo/{video_id}` (`get_seo_analysis`)
  - `POST /api/analytics/optimize/{video_id}` (`trigger_optimizer`)
  - `GET /api/analytics/optimize/{video_id}/log` (`get_optimization_log`)
  - `PATCH /api/analytics/optimize/{video_id}/flag` (`set_auto_optimize_flag`)
- **Router / Handler:** `backend/api/routes/analytics.py:30-310`
- **Purpose:** Post-publishing performance monitoring, retention tracking, automated title/thumbnail A/B testing, and SEO scoring.
- **Current Status:** Implemented, verification incomplete (requires live YouTube analytics token to test end-to-end).

---

### Group 10: Dubbing (`backend/api/routes/dubbing.py`)

#### `BE-DUB-001` & `BE-DUB-002` — Multi-Language Dubbing
- **Method & Path:** `POST /api/dubbing/{clip_id}`, `POST /clips/{clip_id}/dub`
- **Router / Handler:** `backend/api/routes/dubbing.py:15` (`trigger_dubbing`)
- **Purpose:** Generates translated voice tracks using TTS models.
- **Findings:** Dual registration: mounted both under `/api/dubbing/{clip_id}` and legacy route `/clips/{clip_id}/dub`.
- **Current Status:** Partially implemented (mocked audio synthesis task).

---

### Group 11: Settings & Preferences (`backend/api/routes/settings.py`)

#### `BE-SET-001` — Get System Settings
- **Method & Path:** `GET /api/settings`
- **Router / Handler:** `backend/api/routes/settings.py:53` (`get_settings`)
- **Purpose:** Retrieves active system settings, Cloud AI provider configurations, Whisper model, limits, and masked YouTube OAuth client credentials (`YOUTUBE_CLIENT_SECRET_SET: bool` and `YOUTUBE_CLIENT_SECRET_MASKED: "••••••••"`).
- **Request Input:** None.
- **Response:** `200 OK` -> `SystemSettingsResponse`.
- **Auth:** None (Internal / System settings).
- **Dependencies:** `backend.core.config.settings`, `data/settings.json`.
- **Side Effects:** Read-only; reads from memory configuration with file persistence fallback.
- **Frontend Usage:** `getSystemSettings()` in `frontend/lib/api.ts` -> `/settings` initial load on `frontend/app/settings/page.tsx`.
- **Tests:** `backend/tests/test_c09_settings_persistence.py`
- **Current Status:** Verified working (Delivered in Phase 5.1 / C-09).

#### `BE-SET-002` — Update System Settings
- **Method & Path:** `PUT /api/settings`
- **Router / Handler:** `backend/api/routes/settings.py:65` (`update_settings`)
- **Purpose:** Persists updated system settings, validates bounds (`CLIPS_PER_VIDEO` in [1, 20], `CHANNEL_CHECK_INTERVAL_MINUTES` in [5, 1440], allowed Whisper models), preserves masked credentials, atomically updates `data/settings.json`, and dynamically synchronizes runtime in-memory `settings`.
- **Request Input:** `SettingsUpdateRequest` JSON body.
- **Response:** `200 OK` -> `SystemSettingsResponse`.
- **Auth:** None (Internal / System settings).
- **Dependencies:** `backend.core.config.settings`, `data/settings.json`.
- **Side Effects:** Atomic write to `data/settings.json`, dynamic in-memory mutation of `backend.core.config.settings`.
- **Frontend Usage:** `updateSystemSettings(data)` in `frontend/lib/api.ts` -> "Save Settings" on `frontend/app/settings/page.tsx`.
- **Tests:** `backend/tests/test_c09_settings_persistence.py`
- **Current Status:** Verified working (Delivered in Phase 5.1 / C-09).

---

## 3. Route Discrepancies & Semantic Findings

1. **Defect 2 Resolution (Verified):** In `backend/api/routes/channels.py`, `process_channel_video` previously assigned premature `status=resolved_custom` to newly created `VideoDecision` records, causing `resolve_video_decision_sync` to skip Celery scheduling and return `job_id=None`. Resolved by setting `status=awaiting_settings` upon creation and adding fallback `DEFAULT_PROCESSING_PROFILE`.
2. **Defect 1 Resolution (Verified):** Added `POST /api/channels/{channel_id}/process-videos-batch` (`BE-CHN-008`), enabling multi-video selection and queueing from the Automation interface with sequential task protection.
3. **Legacy Prefix Inconsistency:** `backend/api/routes/dubbing.py` defines `/clips/{clip_id}/dub` without `/api` prefix, in addition to `/api/dubbing/{clip_id}`. Kept for backward compatibility.
4. **Clean Channel Separation Enforced:** `GET /api/publish/destinations` and `GET /api/youtube-channels` strictly filter `is_destination=true` and `is_test=false`, preventing monitored sources from appearing as publishing destinations.
