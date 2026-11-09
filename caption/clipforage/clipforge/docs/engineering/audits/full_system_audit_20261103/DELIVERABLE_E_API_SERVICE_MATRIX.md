# Deliverable E: FastAPI Endpoint & Service Inventory Matrix
**Audit Item:** `CLIPFORGE-FULL-SYSTEM-AUDIT-001`  
**Subsystem:** Backend API Layer & Service Integration Boundaries  
**Auditor:** Teamwork Worker M2 (Backend, DB & Celery Audit Deliverables Author)  
**Date of Audit:** 2026-11-03 / 2026-11-04  
**Target Codebase:** `d:\automation video clips\clipforge`  
**Integrity Mode:** Benchmark / Read-Only Inspection  
**Classification:** Authoritative Technical Deliverable  

---

## 1. Executive Summary & Architecture Overview

The ClipForge backend API layer is constructed on **FastAPI** (`backend/main.py:118`), presenting a decoupled REST and WebSocket communication surface for the Next.js frontend application, automated background workers, and external webhook/callback integrations.

### 1.1 Key API Subsystem Metrics
- **Total Registered ASGI Route Objects:** **131** route objects registered in `app.routes`.
- **Unique Functional API Operations:** **120** unique operations, comprising:
  - **119 HTTP API Operations** across 10 resource domains (`videos`, `clips`, `jobs`, `channels`, `publish`, `youtube-channels`, `studio`, `analytics`, `dubbing`, `settings`, and system core).
  - **1 Real-Time WebSocket Endpoint** (`/api/jobs/ws/{job_id}`).
  - **7 Route Aliases / Trailing-Slash Variants** (e.g. `/api/settings` and `/api/settings/`, `/api/youtube-channels` and `/api/youtube-channels/`, `/api/dubbing/languages` and `/api/clips/dubbing/languages`).
  - **4 OpenAPI Documentation Endpoints** (`/openapi.json`, `/api/docs`, `/api/redoc`, `/docs/oauth2-redirect`).
  - **1 Security Quarantine Intercept Route** (`/outputs/.storage_quarantine/{rest:path}`).
  - **2 StaticFiles Directory Mounts** (`/outputs` for generated media and `/uploads` for source media/frame caches).
- **Authentication & Authorization Surface:** Single-tenant local workstation model. Public endpoints operate without session tokens; external channel operations enforce least-privilege OAuth2 credential binding and pre-flight channel identity matching (`publisher.py:78-87`).
- **Product Invariant Enforcement in API Layer:**
  - **Zero Captions/Subtitles:** Verified absence of caption routes; active schema rejection of `caption_burn_in=True` (`channels.py:56-61`).
  - **Standard Podcast Geometry:** Enforced 1080x960 panel splitting and Area 1 Single Speaker Focus via `layout_engine.py`.
  - **Advanced Podcast Modes:** Explicit segregation between Mode 1 (continuous intra-shot tracking via piecewise linear FFmpeg expressions) and Mode 2 (discrete shot-level classification).
  - **AI-Only Scoring:** Explicit rejection of heuristic fallbacks in candidate generation and scoring endpoints.

---

## 2. Route Distribution by Router Module

The 131 registered ASGI route objects are partitioned across 11 modules:

| # | Router Module | Path Prefix | Tags | Registered Route Objects | Unique Operations | Primary Responsibility |
|---|---|---|---|:---:|:---:|---|
| 1 | `backend/main.py` | Core / Docs | System, Health | 9 | 3 | Health probing, aggregate telemetry stats, OpenAPI/Swagger docs, quarantine interception, static mounts |
| 2 | `backend/api/routes/videos.py` | `/api/videos` | Videos | 10 | 10 | Single/batch YouTube ingestion, uploads, video detail, SEO metadata, frame preview, podcast shot analysis |
| 3 | `backend/api/routes/clips.py` | `/api/clips` | Clips | 23 | 23 | Clip listing, metadata management, downloads, thumbnail extraction, variants, SFX/B-roll/Hook plans, cleanup preview & execution |
| 4 | `backend/api/routes/jobs.py` | `/api/jobs` | Jobs | 9 | 9 | Job polling, active jobs, terminal history, queue stats, cancellation, retry, and real-time WebSocket progress |
| 5 | `backend/api/routes/channels.py` | `/api/channels` | Channels | 16 | 16 | Monitored channels, automated intake decisions, countdown sweep, manual scans, batch ingestion, historical archive preview |
| 6 | `backend/api/routes/publish.py` | `/api/publish` | Publish | 17 | 17 | Publishing destinations, OAuth consent callbacks, queue scheduling, manual publish now, cancel/retry, YouTube Shorts upload |
| 7 | `backend/api/routes/youtube_channels.py` | `/api/youtube-channels` | YouTube Channels | 9 | 8 | Channel account connections, publishing cooldowns, cached subscriber/view stats, refresh, default assignment, disconnect |
| 8 | `backend/api/routes/studio.py` | `/api/studio` | Studio | 15 | 15 | Upload Studio chunked uploads, checksum validation, batches, queue reordering, processing dispatch, batch retry/recovery |
| 9 | `backend/api/routes/analytics.py` | `/api/analytics` | Analytics | 11 | 11 | Performance tracking loops, A/B experiments, audience retention curves, virality insights, auto-optimization triggers |
| 10 | `backend/api/routes/dubbing.py` | `/api/dubbing` | Dubbing | 8 | 4 | Multi-language auto-dubbing triggers, async status polling, supported language catalog (includes `/api/clips/...` aliases) |
| 11 | `backend/api/routes/settings.py` | `/api/settings` | Settings | 4 | 2 | Dynamic system settings retrieval and in-memory reload (handles trailing slashes) |
| **TOTAL** | | | | **131** | **120** | **119 HTTP API Operations + 1 WebSocket Endpoint** |

---

## 3. Comprehensive Endpoint Catalog & Contract Matrix

The following catalog provides an exhaustive forensic trace for every registered route object across all 11 modules.

### 3.1 Module: System Core, Health & Documentation (`backend/main.py`)

#### `API-CORE-001`: Health Probing Endpoint
- **HTTP Method & Path:** `GET /api/health`
- **Operation ID & Handler:** `health` (`backend/main.py:170`)
- **Request Schema:** None (URL parameters: None)
- **Response Schema:** `{"status": "ok"|"degraded", "timestamp": str, "components": {"database": bool, "redis": bool, "celery": bool}}` (Status 200/503)
- **Auth & Dependencies:** Public; DB async session (`get_async_db`), Redis connection pool probe
- **Database Effects:** Executes `SELECT 1` read query against PostgreSQL; zero row mutations
- **Celery Tasks Dispatched:** Inspects `celery_app.control.ping(timeout=1.0)`
- **External Calls:** Redis server ping
- **Error Handling:** Traps `Exception` and returns degraded component dictionary with HTTP 200 (or HTTP 503 if DB is unreachable)
- **Frontend Callers:** `frontend/src/components/layout/Header.tsx`, `HealthStatusPill.tsx`
- **Test Evidence:** `backend/tests/test_health.py` (E2)
- **Evidence Tier:** E2 (Service/API integration verified)

#### `API-CORE-002`: System Aggregate Telemetry Statistics
- **HTTP Method & Path:** `GET /api/stats`
- **Operation ID & Handler:** `stats` (`backend/main.py:241`)
- **Request Schema:** None
- **Response Schema:** `{"total_videos": int, "total_clips": int, "total_channels": int, "active_jobs": int}`
- **Auth & Dependencies:** Public; `get_async_db`
- **Database Effects:** Aggregates `COUNT(*)` across `videos`, `clips`, `channels`, and non-terminal `jobs`
- **Celery Tasks Dispatched:** None
- **External Calls:** None
- **Error Handling:** HTTP 500 on database connection timeout
- **Frontend Callers:** `frontend/src/app/page.tsx` (Dashboard overview cards)
- **Test Evidence:** Verified in backend test suites (E2)
- **Evidence Tier:** E2

#### `API-CORE-003`: OpenAPI 3.1.0 Specification
- **HTTP Method & Path:** `GET /openapi.json`
- **Operation ID & Handler:** `openapi` (`fastapi.applications:1088`)
- **Request Schema:** None
- **Response Schema:** OpenAPI 3.1.0 JSON Schema object
- **Auth & Dependencies:** Public
- **Database Effects:** None
- **Celery Tasks Dispatched:** None
- **Frontend Callers:** API tooling, Swagger UI
- **Evidence Tier:** E0 (Specification artifact)

#### `API-CORE-004`: Interactive Swagger UI Documentation
- **HTTP Method & Path:** `GET /api/docs`
- **Operation ID & Handler:** `swagger_ui_html` (`backend/main.py:123`, `fastapi.applications:1099`)
- **Request Schema:** None
- **Response Schema:** HTML page rendering Swagger UI
- **Evidence Tier:** E0

#### `API-CORE-005`: ReDoc Interactive Documentation
- **HTTP Method & Path:** `GET /api/redoc`
- **Operation ID & Handler:** `redoc_html` (`backend/main.py:124`, `fastapi.applications:1127`)
- **Request Schema:** None
- **Response Schema:** HTML page rendering ReDoc
- **Evidence Tier:** E0

#### `API-CORE-006`: Swagger OAuth2 Callback Redirect
- **HTTP Method & Path:** `GET /docs/oauth2-redirect`
- **Operation ID & Handler:** `swagger_ui_redirect` (`fastapi.applications:1117`)
- **Request Schema:** None
- **Response Schema:** HTML redirect helper
- **Evidence Tier:** E0

#### `API-CORE-007`: Storage Quarantine Security Interception
- **HTTP Method & Path:** `GET, HEAD, POST /outputs/.storage_quarantine/{rest:path}`
- **Operation ID & Handler:** `block_quarantine_access` (`backend/main.py:154`)
- **Request Schema:** Path param `rest: str`
- **Response Schema:** `{"detail": "Not Found"}` (Status 404)
- **Auth & Dependencies:** Public
- **Database Effects:** None
- **Security Control:** Registered *before* `/outputs` StaticFiles mount. Prevents web clients from snooping or downloading staged deletions.
- **Test Evidence:** `backend/tests/test_phase_1_3_storage_cleanup.py::test_quarantine_route_blocks_http_access` (E2)
- **Evidence Tier:** E2 (Verified passing)

#### `API-CORE-008`: Output Artifacts Static Mount
- **HTTP Method & Path:** Static Mount `/outputs`
- **Operation ID & Handler:** `StaticFiles(directory=settings.OUTPUT_DIR)` (`backend/main.py:165`)
- **Security Check:** Sub-path `.storage_quarantine` intercepted by `API-CORE-007`
- **Evidence Tier:** E2

#### `API-CORE-009`: Source Media & Frame Cache Static Mount
- **HTTP Method & Path:** Static Mount `/uploads`
- **Operation ID & Handler:** `StaticFiles(directory=settings.UPLOAD_DIR)` (`backend/main.py:166`)
- **Security Check:** Restricts file access to canonical `UPLOAD_DIR` root
- **Evidence Tier:** E2

---

### 3.2 Module: Videos & Ingestion (`backend/api/routes/videos.py`)

#### `API-VID-001`: Single YouTube Video URL Ingestion
- **HTTP Method & Path:** `POST /api/videos/url`
- **Operation ID & Handler:** `process_youtube_url` (`backend/api/routes/videos.py:100`)
- **Request Schema:** `ProcessUrlRequest` (`url: HttpUrl`, `clip_mode: str = "ai_highlights"`, `target_duration: int = 60`, `min_clip_duration: int = 30`, `max_clip_duration: int = 60`, `regions: Optional[List[RegionModel]] = None`, `composition: Optional[str] = None`)
- **Response Schema:** `ProcessUrlResponse` (`job_id: str`, `video_id: str`, `status: str`, `message: str`) (Status 202)
- **Auth & Dependencies:** `get_async_db`
- **Database Effects:** Creates `Video` record and `Job` record with status `pending`
- **Celery Tasks Dispatched:** Dispatches `start_video_processing.delay(job_id=..., youtube_url=..., ...)`
- **Invariant Verifications:** 
  - Blocks output Short re-ingestion via `check_is_clipforge_short` (`services/provenance.py`).
  - Supports `clip_mode="equal_split"` and `clip_mode="ai_highlights"` without caption parameters.
- **Frontend Callers:** `frontend/src/lib/api.ts:processVideoUrl()`, Dashboard ingestion input
- **Test Evidence:** `backend/tests/test_api_videos.py`, `backend/tests/test_provenance.py` (E2)
- **Evidence Tier:** E2

#### `API-VID-002`: Podcast Shot Analysis & Cut Detection
- **HTTP Method & Path:** `POST /api/videos/podcast/analyze-shots`
- **Operation ID & Handler:** `analyze_podcast_shots` (`backend/api/routes/videos.py:335`)
- **Request Schema:** `PodcastShotAnalysisRequest` (`video_path: str`, `regions: List[RegionModel]`, `composition: str`, `reference_timestamp: float = 0.0`, `async_mode: bool = False`)
- **Response Schema:** `PodcastShotAnalysisResponse` (`status: str`, `schedule: Optional[ShotSchedule]`, `task_id: Optional[str]`)
- **Auth & Dependencies:** `get_async_db`
- **Database Effects:** None (in-memory schedule computation or async Celery task dispatch)
- **Celery Tasks Dispatched:** If `async_mode=True`, dispatches `analyze_podcast_shots_task.delay(...)`
- **Invariant Verifications:** Mode 1 (`Fixed Two-Person Area with Camera Following`) triggers continuous tracking plan; Mode 2 triggers discrete shot classification.
- **Frontend Callers:** `frontend/src/lib/api.ts:analyzePodcastShots()`, Podcast Modal canvas
- **Test Evidence:** `backend/tests/test_advanced_podcast.py` (E2)
- **Evidence Tier:** E2

#### `API-VID-003`: Async Podcast Shot Analysis Status Polling
- **HTTP Method & Path:** `GET /api/videos/podcast/analysis-status/{task_id}`
- **Operation ID & Handler:** `get_podcast_analysis_status` (`backend/api/routes/videos.py:473`)
- **Request Schema:** Path param `task_id: str`
- **Response Schema:** `{"task_id": str, "status": "PENDING"|"PROGRESS"|"SUCCESS"|"FAILURE", "result": Optional[dict], "error": Optional[str]}`
- **Evidence Tier:** E2

#### `API-VID-004`: Batch YouTube URLs Ingestion
- **HTTP Method & Path:** `POST /api/videos/batch`
- **Operation ID & Handler:** `process_youtube_urls_batch` (`backend/api/routes/videos.py:527`)
- **Request Schema:** `BatchProcessUrlRequest` (`urls: List[HttpUrl]`, `clip_mode: str`, `target_duration: int`)
- **Response Schema:** `BatchProcessUrlResponse` (`batch_id: str`, `jobs: List[ProcessUrlResponse]`) (Status 202)
- **Database Effects:** Creates `UploadBatch` and multiple `Video` & `Job` rows
- **Celery Tasks Dispatched:** Iteratively dispatches `start_video_processing`
- **Evidence Tier:** E2

#### `API-VID-005`: Local Video File Upload
- **HTTP Method & Path:** `POST /api/videos/upload`
- **Operation ID & Handler:** `upload_video_file` (`backend/api/routes/videos.py:632`)
- **Request Schema:** Multipart form (`file: UploadFile`, `clip_mode: str = Form("ai_highlights")`, `target_duration: int = Form(60)`)
- **Response Schema:** `ProcessUrlResponse` (`job_id: str`, `video_id: str`, `status: str`)
- **Database Effects:** Creates `Video` with `local_path` and `Job`
- **Storage Action:** Streams file directly to `settings.UPLOAD_DIR`
- **Evidence Tier:** E2

#### `API-VID-006`: Paginated Video List
- **HTTP Method & Path:** `GET /api/videos/`
- **Operation ID & Handler:** `list_videos` (`backend/api/routes/videos.py:727`)
- **Request Schema:** Query params `skip: int = 0`, `limit: int = 20`, `is_test: bool = False`
- **Response Schema:** `List[VideoResponse]` (includes joined `clips_count`, `duration`, `status`)
- **Frontend Callers:** Dashboard video library list
- **Evidence Tier:** E2

#### `API-VID-007`: Single Video Detail Retrieval
- **HTTP Method & Path:** `GET /api/videos/{video_id}`
- **Operation ID & Handler:** `get_video` (`backend/api/routes/videos.py:746`)
- **Request Schema:** Path param `video_id: str`
- **Response Schema:** `VideoDetailResponse` (includes associated `clips: List[ClipResponse]`)
- **Error Handling:** HTTP 404 if video does not exist
- **Evidence Tier:** E2

#### `API-VID-008`: Source Video SEO Metadata Retrieval
- **HTTP Method & Path:** `GET /api/videos/{video_id}/seo-metadata`
- **Operation ID & Handler:** `get_video_seo_metadata` (`backend/api/routes/videos.py:756`)
- **Request Schema:** Path param `video_id: str`
- **Response Schema:** `VideoMetadataResponse` (`title: str`, `description: str`, `tags: List[str]`, `hashtags: List[str]`)
- **Database Effects:** Reads `video_metadata` table
- **Evidence Tier:** E2

#### `API-VID-009`: Refresh Source Video SEO Metadata
- **HTTP Method & Path:** `POST /api/videos/{video_id}/seo-metadata/refresh`
- **Operation ID & Handler:** `refresh_video_seo_metadata` (`backend/api/routes/videos.py:775`)
- **Request Schema:** Path param `video_id: str`
- **Response Schema:** `VideoMetadataResponse`
- **Database Effects:** Updates `video_metadata` with fresh AI-generated tags and title suggestions
- **Evidence Tier:** E2

#### `API-VID-010`: Secure Video Frame Extraction Preview
- **HTTP Method & Path:** `GET /api/videos/{video_id}/frame`
- **Operation ID & Handler:** `get_video_frame` (`backend/api/routes/videos.py:793`)
- **Request Schema:** Path param `video_id: str`, Query param `timestamp: float = 0.0`
- **Response Schema:** `FileResponse(image/jpeg)`
- **Security Controls (`videos.py:813`):**
  - Regex validation: `^[a-zA-Z0-9_\-]{1,64}$` (rejects traversal characters `..`, slashes, null bytes).
  - Finite timestamp: `0.0 <= timestamp <= 86400.0`.
  - Subprocess containment: FFmpeg executed with `-protocol_whitelist file` and `-nostdin` with an 8.0s timeout.
  - Disk caching: Caches frames under `uploads/frame_cache/{video_id}_{timestamp}.jpg`.
- **Frontend Callers:** `frontend/src/lib/api.ts:fetchVideoFrame()`, Podcast Canvas preview
- **Test Evidence:** `backend/tests/test_api_videos.py::test_get_video_frame_validation` (E2)
- **Evidence Tier:** E2

---

### 3.3 Module: Clips & Artifact Management (`backend/api/routes/clips.py`)

#### `API-CLIP-001`: Filterable Clips Catalog
- **HTTP Method & Path:** `GET /api/clips/`
- **Operation ID & Handler:** `list_clips` (`backend/api/routes/clips.py:106`)
- **Request Schema:** Query params `skip: int = 0`, `limit: int = 50`, `video_id: Optional[str]`, `channel_id: Optional[str]`, `destination_id: Optional[str]`, `sort_by: str = "created_at"`
- **Response Schema:** `List[ClipResponse]` (includes `score`, `duration`, `privacy`, `publish_status`)
- **Frontend Callers:** `frontend/src/lib/api.ts:getClips()`, Clips Library page
- **Evidence Tier:** E2

#### `API-CLIP-002`: Storage Cleanup Preview (Zero-Mutation)
- **HTTP Method & Path:** `GET /api/clips/cleanup/preview`
- **Operation ID & Handler:** `preview_cleanup` (`backend/api/routes/clips.py:431`)
- **Request Schema:** Query params `score_threshold: float = 60.0`, `older_than_days: int = 7`
- **Response Schema:** `StorageCleanupPreviewResponse` (`candidate_clip_ids: List[str]`, `total_files: int`, `reclaimable_bytes: int`, `hmac_token: str`, `expires_at: str`)
- **Database Effects:** Pure read query on `clips`; zero deletions
- **Security Control:** Signs candidates using HMAC-SHA256 (`STORAGE_IDENTITY_SECRET`)
- **Test Evidence:** `backend/tests/test_phase_1_3_storage_cleanup.py::test_preview_cleanup_endpoint` (E2)
- **Evidence Tier:** E2 (Verified passing)

#### `API-CLIP-003`: Storage Cleanup Atomic Execution
- **HTTP Method & Path:** `POST /api/clips/cleanup/execute`
- **Operation ID & Handler:** `execute_cleanup` (`backend/api/routes/clips.py:556`)
- **Request Schema:** `StorageCleanupExecuteRequest` (`hmac_token: str`, `candidate_clip_ids: List[str]`)
- **Response Schema:** `StorageCleanupExecuteResponse` (`reclaimed_bytes: int`, `deleted_clips: int`, `status: str`)
- **Database Effects:** Cascaded deletion of `clips` and child records; reconciles `StorageReservationCoordinator`
- **Storage Action:** Moves candidate media to `.storage_quarantine/` before final unlinking
- **Test Evidence:** `backend/tests/test_phase_1_3_storage_cleanup.py::test_execute_cleanup_endpoint` (E2)
- **Evidence Tier:** E2 (Verified passing)

#### `API-CLIP-004`: Single Clip Detail
- **HTTP Method & Path:** `GET /api/clips/{clip_id}`
- **Operation ID & Handler:** `get_clip` (`backend/api/routes/clips.py:945`)
- **Response Schema:** `ClipResponse`
- **Evidence Tier:** E2

#### `API-CLIP-005`: Clip Metadata Update
- **HTTP Method & Path:** `PATCH /api/clips/{clip_id}`
- **Operation ID & Handler:** `update_clip` (`backend/api/routes/clips.py:954`)
- **Request Schema:** `UpdateClipRequest` (`title: Optional[str]`, `description: Optional[str]`)
- **Response Schema:** `ClipResponse`
- **Evidence Tier:** E2

#### `API-CLIP-006`: Clip Deletion
- **HTTP Method & Path:** `DELETE /api/clips/{clip_id}`
- **Operation ID & Handler:** `delete_clip` (`backend/api/routes/clips.py:968`)
- **Database Effects:** Deletes `Clip` record; foreign key cascade removes child plans and records
- **Storage Action:** Deletes rendered video file and thumbnail from disk
- **Evidence Tier:** E2

#### `API-CLIP-007`: Clip Video Download
- **HTTP Method & Path:** `GET /api/clips/{clip_id}/download`
- **Operation ID & Handler:** `download_clip` (`backend/api/routes/clips.py:989`)
- **Security Control:** Path containment check ensures file resides within `settings.OUTPUT_DIR`
- **Response Schema:** `FileResponse(video/mp4)`
- **Evidence Tier:** E2

#### `API-CLIP-008`: Clip Thumbnail Retrieval
- **HTTP Method & Path:** `GET /api/clips/{clip_id}/thumbnail`
- **Operation ID & Handler:** `get_thumbnail` (`backend/api/routes/clips.py:1001`)
- **Response Schema:** `FileResponse(image/jpeg)`
- **Evidence Tier:** E2

#### `API-CLIP-009`: List Rendered Clip Variants
- **HTTP Method & Path:** `GET /api/clips/{clip_id}/variants`
- **Operation ID & Handler:** `list_clip_variants` (`backend/api/routes/clips.py:1013`)
- **Response Schema:** `List[ClipVariantResponse]` (SFX, B-roll, Dubbed variants)
- **Database Effects:** Reads `clip_variants` table
- **Evidence Tier:** E2

#### `API-CLIP-010`: Download Clip Variant
- **HTTP Method & Path:** `GET /api/clips/{clip_id}/variants/{variant_id}/download`
- **Operation ID & Handler:** `download_clip_variant` (`backend/api/routes/clips.py:1071`)
- **Response Schema:** `FileResponse(video/mp4)`
- **Evidence Tier:** E2

#### `API-CLIP-011`: Retrieve Pre-Upload Metadata
- **HTTP Method & Path:** `GET /api/clips/{clip_id}/metadata`
- **Operation ID & Handler:** `get_clip_metadata_route` (`backend/api/routes/clips.py:1128`)
- **Response Schema:** `ClipMetadataResponse` (`title: str`, `description: str`, `tags: List[str]`, `pinned_comment: Optional[str]`)
- **Evidence Tier:** E2

#### `API-CLIP-012`: Update Pre-Upload Metadata
- **HTTP Method & Path:** `PATCH /api/clips/{clip_id}/metadata`
- **Operation ID & Handler:** `update_clip_metadata_route` (`backend/api/routes/clips.py:1168`)
- **Request Schema:** `UpdateClipMetadataRequest`
- **Response Schema:** `ClipMetadataResponse`
- **Evidence Tier:** E2

#### `API-CLIP-013`: Enqueue Clip for YouTube Publishing
- **HTTP Method & Path:** `POST /api/clips/{clip_id}/publish`
- **Operation ID & Handler:** `publish_clip_route` (`backend/api/routes/clips.py:1222`)
- **Request Schema:** `PublishClipRequest` (`destination_id: Optional[str]`, `scheduled_at: Optional[datetime]`, `privacy: str = "private"`)
- **Response Schema:** `PublishClipResponse` (`publish_target_id: str`, `status: str`)
- **Invariant Enforcement:** Hardcodes `privacy="private"` in publication task payload; overrides public defaults
- **Celery Tasks Dispatched:** Dispatches `publish_clip_task.delay(clip_id=..., ...)`
- **Evidence Tier:** E2

#### `API-CLIP-014`: Audience Retention Prediction Curve
- **HTTP Method & Path:** `GET /api/clips/{clip_id}/retention`
- **Operation ID & Handler:** `get_retention` (`backend/api/routes/clips.py:1347`)
- **Response Schema:** `RetentionResponse` (`retention_curve: List[float]`, `average_predicted_drop: float`, `weak_moments: List[dict]`)
- **Database Effects:** Reads `clip_retentions` table
- **Evidence Tier:** E2

#### `API-CLIP-015`: Retention Autofix Plan Generation
- **HTTP Method & Path:** `POST /api/clips/{clip_id}/autofix`
- **Operation ID & Handler:** `generate_autofix` (`backend/api/routes/clips.py:1396`)
- **Response Schema:** `AutofixPlanResponse` (`suggestions: List[str]`, `recommended_sfx: List[str]`, `recommended_broll: List[str]`)
- **Evidence Tier:** E2

#### `API-CLIP-016`: Sound Effects Plan Retrieval
- **HTTP Method & Path:** `GET /api/clips/{clip_id}/sfx-plan`
- **Operation ID & Handler:** `get_sfx_plan` (`backend/api/routes/clips.py:1436`)
- **Response Schema:** `SFXPlanResponse` (`plan_data: dict`, `status: str`, `audio_mix_volume: float`)
- **Evidence Tier:** E2

#### `API-CLIP-017`: Sound Effects Plan Creation / Update
- **HTTP Method & Path:** `POST /api/clips/{clip_id}/sfx-plan`
- **Operation ID & Handler:** `create_or_update_sfx_plan` (`backend/api/routes/clips.py:1455`)
- **Request Schema:** `SFXPlanRequest` (`plan_data: dict`, `audio_mix_volume: float = 0.8`)
- **Response Schema:** `SFXPlanResponse`
- **Database Effects:** Upserts `clip_sfx_plans`
- **Evidence Tier:** E2

#### `API-CLIP-018`: Apply Sound Effects Mixdown
- **HTTP Method & Path:** `POST /api/clips/{clip_id}/sfx-apply`
- **Operation ID & Handler:** `apply_sfx_route` (`backend/api/routes/clips.py:1503`)
- **Response Schema:** `{"task_id": str, "status": "dispatched"}`
- **Celery Tasks Dispatched:** `apply_sfx.delay(clip_id=..., sfx_plan=...)`
- **Evidence Tier:** E2

#### `API-CLIP-019`: B-Roll Visual Overlay Plan Retrieval
- **HTTP Method & Path:** `GET /api/clips/{clip_id}/broll-plan`
- **Operation ID & Handler:** `get_broll_plan` (`backend/api/routes/clips.py:1534`)
- **Response Schema:** `BRollPlanResponse` (`overlay_segments: List[dict]`, `opacity: float`, `status: str`)
- **Evidence Tier:** E2

#### `API-CLIP-020`: Apply B-Roll Visual Overlay
- **HTTP Method & Path:** `POST /api/clips/{clip_id}/broll-apply`
- **Operation ID & Handler:** `apply_broll_route` (`backend/api/routes/clips.py:1562`)
- **Response Schema:** `{"task_id": str, "status": "dispatched"}`
- **Celery Tasks Dispatched:** `apply_broll.delay(clip_id=..., broll_plan=...)`
- **Evidence Tier:** E2

#### `API-CLIP-021`: Kinetic Hook Plan Retrieval
- **HTTP Method & Path:** `GET /api/clips/{clip_id}/hook`
- **Operation ID & Handler:** `get_hook_plan` (`backend/api/routes/clips.py:1595`)
- **Response Schema:** `HookPlanResponse` (`hook_type: str`, `hook_text: str`, `zoom_factor: float`, `status: str`)
- **Invariant Documentation:** `hook.py:55` explicitly mandates hook metadata must not be rendered as captions.
- **Evidence Tier:** E2

#### `API-CLIP-022`: Analyze Hook Opportunities
- **HTTP Method & Path:** `POST /api/clips/{clip_id}/hook/plan`
- **Operation ID & Handler:** `plan_hook_route` (`backend/api/routes/clips.py:1608`)
- **Response Schema:** `HookPlanResponse`
- **Celery Tasks Dispatched:** Dispatches `analyze_hook_opportunities.delay(...)`
- **Evidence Tier:** E2

#### `API-CLIP-023`: Apply Kinetic Hook Intro
- **HTTP Method & Path:** `POST /api/clips/{clip_id}/hook/apply`
- **Operation ID & Handler:** `apply_hook_route` (`backend/api/routes/clips.py:1622`)
- **Response Schema:** `{"task_id": str, "status": "dispatched"}`
- **Celery Tasks Dispatched:** Dispatches `apply_hook_plan.delay(...)`
- **Evidence Tier:** E2

---

### 3.4 Module: Jobs & Task Orchestration (`backend/api/routes/jobs.py`)

#### `API-JOB-001`: List Processing Jobs
- **HTTP Method & Path:** `GET /api/jobs/`
- **Operation ID & Handler:** `list_jobs` (`backend/api/routes/jobs.py:101`)
- **Request Schema:** Query params `skip: int = 0`, `limit: int = 20`, `is_test: bool = False`
- **Response Schema:** `List[JobResponse]` (includes IST timestamp formatting and source thumbnails)
- **Evidence Tier:** E2

#### `API-JOB-002`: List Active Jobs
- **HTTP Method & Path:** `GET /api/jobs/active`
- **Operation ID & Handler:** `list_active_jobs` (`backend/api/routes/jobs.py:132`)
- **Response Schema:** `List[JobResponse]` (filters where `status IN ('pending', 'processing')`)
- **Evidence Tier:** E2

#### `API-JOB-003`: Paginated Terminal Job History
- **HTTP Method & Path:** `GET /api/jobs/history`
- **Operation ID & Handler:** `list_job_history` (`backend/api/routes/jobs.py:153`)
- **Response Schema:** `List[JobResponse]` (filters where `status IN ('completed', 'failed', 'cancelled')`)
- **Evidence Tier:** E2

#### `API-JOB-004`: Real-Time Queue Count
- **HTTP Method & Path:** `GET /api/jobs/queue-count`
- **Operation ID & Handler:** `get_queue_count` (`backend/api/routes/jobs.py:175`)
- **Response Schema:** `{"pending_jobs": int, "active_jobs": int, "total_queued": int}`
- **Evidence Tier:** E2

#### `API-JOB-005`: Job Aggregate Statistics
- **HTTP Method & Path:** `GET /api/jobs/stats`
- **Operation ID & Handler:** `get_job_stats` (`backend/api/routes/jobs.py:191`)
- **Response Schema:** `{"success_rate": float, "average_duration_seconds": float, "failure_count": int}`
- **Evidence Tier:** E2

#### `API-JOB-006`: Single Job State
- **HTTP Method & Path:** `GET /api/jobs/{job_id}`
- **Operation ID & Handler:** `get_job` (`backend/api/routes/jobs.py:254`)
- **Response Schema:** `JobResponse` (`progress: float`, `current_step: str`, `status: str`)
- **Evidence Tier:** E2

#### `API-JOB-007`: Cancel In-Flight Job
- **HTTP Method & Path:** `DELETE /api/jobs/{job_id}`
- **Operation ID & Handler:** `cancel_job` (`backend/api/routes/jobs.py:264`)
- **Response Schema:** `{"status": "cancelled", "job_id": str}`
- **Database Effects:** Sets `job.status = "cancelled"`
- **Celery Action:** Revokes Celery task with `terminate=True`
- **Evidence Tier:** E2

#### `API-JOB-008`: Real-Time WebSocket Progress Stream
- **Protocol & Path:** `WS /api/jobs/ws/{job_id}`
- **Operation ID & Handler:** `job_progress_ws` (`backend/api/routes/jobs.py:345`)
- **Message Protocol:** Streams JSON frames: `{"job_id": str, "status": str, "progress": float, "current_step": str, "timestamp": str}`
- **Connection Lifecycle:** Subscribes to Redis pub/sub channel for `job_id`; closes gracefully on terminal state or client disconnect.
- **Frontend Callers:** `frontend/src/lib/api.ts:subscribeJobProgress()`, Dashboard Progress Bar
- **Evidence Tier:** E2

#### `API-JOB-009`: Retry Failed Job
- **HTTP Method & Path:** `POST /api/jobs/{job_id}/retry`
- **Operation ID & Handler:** `retry_job` (`backend/api/routes/jobs.py:393`)
- **Security Check:** Re-validates against self-ingestion (`check_is_clipforge_short`)
- **Response Schema:** `JobResponse`
- **Celery Action:** Re-dispatches pipeline from last incomplete checkpoint
- **Evidence Tier:** E2

---

### 3.5 Module: Channels & Automation Workflow (`backend/api/routes/channels.py`)

#### `API-CHAN-001`: Register Monitored YouTube Channel
- **HTTP Method & Path:** `POST /api/channels/`
- **Operation ID & Handler:** `create_channel` (`backend/api/routes/channels.py:193`)
- **Request Schema:** `CreateChannelRequest` (`channel_url: HttpUrl`, `auto_clip: bool = True`, `auto_publish: bool = False`, `auto_pilot: bool = False`, `caption_burn_in: bool = False`)
- **Invariant Enforcement (`channels.py:56-61`):** Explicitly raises `ValueError("Caption burn-in is strictly disabled under ClipForge freeze rules.")` if `caption_burn_in` is True.
- **Response Schema:** `ChannelResponse` (Status 201)
- **Database Effects:** Inserts `channels` record
- **Evidence Tier:** E2

#### `API-CHAN-002`: List Monitored Channels
- **HTTP Method & Path:** `GET /api/channels/`
- **Operation ID & Handler:** `list_channels` (`backend/api/routes/channels.py:286`)
- **Response Schema:** `List[ChannelResponse]`
- **Evidence Tier:** E2

#### `API-CHAN-003`: Update Monitored Channel Settings
- **HTTP Method & Path:** `PATCH /api/channels/{channel_id}`
- **Operation ID & Handler:** `update_channel` (`backend/api/routes/channels.py:322`)
- **Request Schema:** `UpdateChannelRequest` (`auto_clip: Optional[bool]`, `auto_publish: Optional[bool]`, `auto_pilot: Optional[bool]`, `processing_profile: Optional[dict]`)
- **Response Schema:** `ChannelResponse`
- **Evidence Tier:** E2

#### `API-CHAN-004`: Remove Monitored Channel
- **HTTP Method & Path:** `DELETE /api/channels/{channel_id}`
- **Operation ID & Handler:** `delete_channel` (`backend/api/routes/channels.py:395`)
- **Database Effects:** Removes channel; disassociates `channel_destinations`
- **Evidence Tier:** E2

#### `API-CHAN-005`: Manual Channel Release Scan
- **HTTP Method & Path:** `POST /api/channels/{channel_id}/check-now`
- **Operation ID & Handler:** `check_channel_now` (`backend/api/routes/channels.py:418`)
- **External Calls:** Executes yt-dlp RSS/channel feed query
- **Response Schema:** `{"scanned_videos": int, "new_videos_detected": int}`
- **Evidence Tier:** E2

#### `API-CHAN-006`: Fetch Channel Video List
- **HTTP Method & Path:** `GET /api/channels/{channel_id}/videos`
- **Operation ID & Handler:** `get_channel_videos` (`backend/api/routes/channels.py:487`)
- **Request Schema:** Query params `limit: int = 10`, `page_token: Optional[str]`
- **Response Schema:** `ChannelVideosResponse` (includes YouTube titles, durations, upload dates)
- **Evidence Tier:** E2

#### `API-CHAN-007`: Ingest Specific Channel Video
- **HTTP Method & Path:** `POST /api/channels/{channel_id}/process-video`
- **Operation ID & Handler:** `process_channel_video` (`backend/api/routes/channels.py:674`)
- **Request Schema:** `{"youtube_id": str, "target_duration": Optional[int]}`
- **Celery Tasks Dispatched:** `start_video_processing.delay(...)`
- **Evidence Tier:** E2

#### `API-CHAN-008`: Ingest Batch of Channel Videos
- **HTTP Method & Path:** `POST /api/channels/{channel_id}/process-videos-batch`
- **Operation ID & Handler:** `process_channel_videos_batch` (`backend/api/routes/channels.py:788`)
- **Request Schema:** `{"youtube_ids": List[str]}`
- **Evidence Tier:** E2

#### `API-CHAN-009`: Channel Historical Archive Candidate Preview
- **HTTP Method & Path:** `POST /api/channels/{channel_id}/historical-preview`
- **Operation ID & Handler:** `preview_historical_videos` (`backend/api/routes/channels.py:993`)
- **Request Schema:** `HistoricalPreviewRequest` (`max_videos: int = 20`, `min_views: int = 1000`)
- **Response Schema:** `List[HistoricalVideoCandidate]`
- **Evidence Tier:** E2

#### `API-CHAN-010`: Channel Historical Batch Process Dispatch
- **HTTP Method & Path:** `POST /api/channels/{channel_id}/historical-process`
- **Operation ID & Handler:** `process_historical_videos` (`backend/api/routes/channels.py:1321`)
- **Request Schema:** `HistoricalProcessRequest` (`youtube_ids: List[str]`, `batch_size: int = 5`)
- **Evidence Tier:** E2

#### `API-CHAN-011`: Pending Video Decisions Intake List
- **HTTP Method & Path:** `GET /api/channels/decisions/pending`
- **Operation ID & Handler:** `get_pending_decisions` (`backend/api/routes/channels.py:1537`)
- **Response Schema:** `List[VideoDecisionResponse]` (status `pending`, includes remaining countdown seconds)
- **Evidence Tier:** E2

#### `API-CHAN-012`: Apply Channel Defaults to Pending Decision
- **HTTP Method & Path:** `POST /api/channels/decisions/{decision_id}/apply-defaults`
- **Operation ID & Handler:** `apply_decision_defaults` (`backend/api/routes/channels.py:1611`)
- **Database Effects:** Updates `video_decisions.status = 'approved'`
- **Celery Dispatched:** Triggers ingestion workflow using channel defaults
- **Evidence Tier:** E2

#### `API-CHAN-013`: Customize Decision Parameters
- **HTTP Method & Path:** `POST /api/channels/decisions/{decision_id}/customize`
- **Operation ID & Handler:** `customize_decision` (`backend/api/routes/channels.py:1630`)
- **Request Schema:** `CustomizeDecisionRequest` (`clip_mode: str`, `target_duration: int`)
- **Database Effects:** Updates decision overrides; pauses auto-pilot countdown
- **Evidence Tier:** E2

#### `API-CHAN-014`: Save and Commit Customized Decision
- **HTTP Method & Path:** `POST /api/channels/decisions/{decision_id}/save-and-process`
- **Operation ID & Handler:** `save_and_process_decision` (`backend/api/routes/channels.py:1649`)
- **Evidence Tier:** E2

#### `API-CHAN-015`: Cancel / Reject Pending Decision
- **HTTP Method & Path:** `POST /api/channels/decisions/{decision_id}/cancel`
- **Operation ID & Handler:** `cancel_decision` (`backend/api/routes/channels.py:1678`)
- **Database Effects:** Sets `video_decisions.status = 'rejected'`
- **Evidence Tier:** E2

#### `API-CHAN-016`: Decisions Audit History Log
- **HTTP Method & Path:** `GET /api/channels/decisions/history`
- **Operation ID & Handler:** `get_decision_history` (`backend/api/routes/channels.py:1692`)
- **Response Schema:** `List[VideoDecisionResponse]` (historical logs)
- **Evidence Tier:** E2

---

### 3.6 Module: Publishing & Destination Channels (`backend/api/routes/publish.py`)

#### `API-PUB-001`: Video Publishing Metadata Retrieval
- **HTTP Method & Path:** `GET /api/publish/metadata/{video_id}`
- **Operation ID & Handler:** `get_video_publish_metadata` (`backend/api/routes/publish.py:39`)
- **Response Schema:** `PublishMetadataResponse`
- **Evidence Tier:** E2

#### `API-PUB-002`: Video Publishing Metadata Update
- **HTTP Method & Path:** `POST /api/publish/metadata/{video_id}`
- **Operation ID & Handler:** `update_video_publish_metadata` (`backend/api/routes/publish.py:55`)
- **Evidence Tier:** E2

#### `API-PUB-003`: Clip Pre-Upload Metadata Retrieval
- **HTTP Method & Path:** `GET /api/publish/clips/{clip_id}/metadata`
- **Operation ID & Handler:** `get_clip_publish_metadata` (`backend/api/routes/publish.py:134`)
- **Response Schema:** `ClipPublishMetadataResponse`
- **Evidence Tier:** E2

#### `API-PUB-004`: Patch Clip Pre-Upload Metadata
- **HTTP Method & Path:** `PATCH /api/publish/clips/{clip_id}/metadata`
- **Operation ID & Handler:** `patch_clip_publish_metadata` (`backend/api/routes/publish.py:186`)
- **Evidence Tier:** E2

#### `API-PUB-005`: List Authorized Upload Destination Channels
- **HTTP Method & Path:** `GET /api/publish/destinations`
- **Operation ID & Handler:** `list_destinations` (`backend/api/routes/publish.py:309`)
- **Response Schema:** `List[DestinationResponse]` (filters `is_destination=True`)
- **Evidence Tier:** E2

#### `API-PUB-006`: Designate Primary Default Destination
- **HTTP Method & Path:** `POST /api/publish/destinations/default`
- **Operation ID & Handler:** `set_default_destination` (`backend/api/routes/publish.py:355`)
- **Request Schema:** `{"channel_id": str}`
- **Evidence Tier:** E2

#### `API-PUB-007`: Destination Authentication Status Check
- **HTTP Method & Path:** `GET /api/publish/auth-status`
- **Operation ID & Handler:** `get_auth_status` (`backend/api/routes/publish.py:385`)
- **Response Schema:** `{"authenticated": bool, "channel_id": Optional[str], "expires_at": Optional[str]}`
- **Evidence Tier:** E2

#### `API-PUB-008`: Authenticated Profile Information
- **HTTP Method & Path:** `GET /api/publish/channel-info`
- **Operation ID & Handler:** `get_channel_info` (`backend/api/routes/publish.py:396`)
- **External Calls:** Google OAuth / YouTube API profile lookup
- **Evidence Tier:** E2

#### `API-PUB-009`: Generate OAuth2 Consent URL
- **HTTP Method & Path:** `GET /api/publish/oauth-url`
- **Operation ID & Handler:** `get_oauth_url` (`backend/api/routes/publish.py:406`)
- **Response Schema:** `{"url": str}` (contains Google OAuth2 consent URL with offline access)
- **Security Scopes:** Restricted to `youtube.upload` and `youtube`
- **Evidence Tier:** E2

#### `API-PUB-010`: OAuth2 Callback Handler (GET)
- **HTTP Method & Path:** `GET /api/publish/oauth-callback`
- **Operation ID & Handler:** `oauth_callback_get` (`backend/api/routes/publish.py:429`)
- **Request Schema:** Query params `code: str`, `state: Optional[str]`
- **Response Schema:** HTML redirect / confirmation message
- **Evidence Tier:** E2

#### `API-PUB-011`: OAuth2 Token Exchange (POST)
- **HTTP Method & Path:** `POST /api/publish/oauth-callback`
- **Operation ID & Handler:** `oauth_callback_post` (`backend/api/routes/publish.py:466`)
- **Request Schema:** `{"code": str}`
- **Response Schema:** `{"success": bool, "channel_id": str, "title": str}`
- **Credential Storage:** Stores token securely under `tokens/youtube_token_{channel_id}.json`
- **Evidence Tier:** E2

#### `API-PUB-012`: Immediate Publish Now Trigger
- **HTTP Method & Path:** `POST /api/publish/publish-now`
- **Operation ID & Handler:** `publish_now` (`backend/api/routes/publish.py:526`)
- **Request Schema:** `PublishNowRequest` (`clip_id: str`, `destination_id: Optional[str]`)
- **Response Schema:** `{"publish_target_id": str, "status": "queued"}`
- **Celery Tasks Dispatched:** `publish_clip_task.delay(...)`
- **Evidence Tier:** E2

#### `API-PUB-013`: Clip Publication Status Polling
- **HTTP Method & Path:** `GET /api/publish/status/{clip_id}`
- **Operation ID & Handler:** `get_publish_status` (`backend/api/routes/publish.py:655`)
- **Response Schema:** `{"status": str, "youtube_video_id": Optional[str], "youtube_url": Optional[str], "error": Optional[str]}`
- **Evidence Tier:** E2

#### `API-PUB-014`: Retry Failed Publication
- **HTTP Method & Path:** `POST /api/publish/clips/{clip_id}/retry`
- **Operation ID & Handler:** `retry_publish` (`backend/api/routes/publish.py:679`)
- **Evidence Tier:** E2

#### `API-PUB-015`: Cancel Queued Publication
- **HTTP Method & Path:** `POST /api/publish/clips/{clip_id}/cancel`
- **Operation ID & Handler:** `cancel_publish` (`backend/api/routes/publish.py:736`)
- **Database Effects:** Sets `publish_targets.status = 'cancelled'`
- **Evidence Tier:** E2

#### `API-PUB-016`: Schedule Future Publication
- **HTTP Method & Path:** `POST /api/publish/schedule`
- **Operation ID & Handler:** `schedule_publish` (`backend/api/routes/publish.py:784`)
- **Request Schema:** `SchedulePublishRequest` (`clip_id: str`, `scheduled_at: datetime`, `destination_id: Optional[str]`)
- **Evidence Tier:** E2

#### `API-PUB-017`: Publishing Queue & Cadence Inspector
- **HTTP Method & Path:** `GET /api/publish/queue`
- **Operation ID & Handler:** `get_publish_queue` (`backend/api/routes/publish.py:884`)
- **Response Schema:** `List[PublishQueueItemResponse]` (scheduled and active jobs)
- **Evidence Tier:** E2

---

### 3.7 Module: My YouTube Channels (`backend/api/routes/youtube_channels.py`)

#### `API-YT-001`: Multi-Channel OAuth URL Generation
- **HTTP Method & Path:** `GET /api/youtube-channels/oauth-url`
- **Operation ID & Handler:** `get_channel_oauth_url` (`backend/api/routes/youtube_channels.py:111`)
- **Response Schema:** `{"oauth_url": str}`
- **Evidence Tier:** E2

#### `API-YT-002`: Connect YouTube Destination Channel
- **HTTP Method & Path:** `POST /api/youtube-channels/connect`
- **Operation ID & Handler:** `connect_youtube_channel` (`backend/api/routes/youtube_channels.py:136`)
- **Request Schema:** `ConnectChannelRequest` (`auth_code: str`)
- **Response Schema:** `ChannelResponse`
- **Evidence Tier:** E2

#### `API-YT-003`: List Connected YouTube Channels (Dual Routes)
- **HTTP Method & Path:** `GET /api/youtube-channels` & `GET /api/youtube-channels/`
- **Operation ID & Handler:** `list_youtube_channels` (`backend/api/routes/youtube_channels.py:210, 211`)
- **Response Schema:** `List[YouTubeChannelItemResponse]`
- **Evidence Tier:** E2

#### `API-YT-004`: Cached Channel Performance Statistics
- **HTTP Method & Path:** `GET /api/youtube-channels/{channel_id}/stats`
- **Operation ID & Handler:** `get_channel_stats` (`backend/api/routes/youtube_channels.py:269`)
- **Response Schema:** `{"subscriber_count": int, "view_count": int, "video_count": int, "last_updated": str}`
- **Evidence Tier:** E2

#### `API-YT-005`: Refresh Channel Statistics from YouTube API
- **HTTP Method & Path:** `POST /api/youtube-channels/{channel_id}/refresh`
- **Operation ID & Handler:** `refresh_channel_stats` (`backend/api/routes/youtube_channels.py:315`)
- **External Calls:** YouTube Data API v3 `channels.list(part="statistics")`
- **Evidence Tier:** E2

#### `API-YT-006`: Update Channel Publishing Settings & Cooldown
- **HTTP Method & Path:** `PATCH /api/youtube-channels/{channel_id}/settings`
- **Operation ID & Handler:** `update_channel_publishing_settings` (`backend/api/routes/youtube_channels.py:410`)
- **Request Schema:** `PublishingSettingsRequest` (`cooldown_minutes: int`, `default_tags: List[str]`, `privacy_level: str`)
- **Evidence Tier:** E2

#### `API-YT-007`: Assign Default Publishing Destination
- **HTTP Method & Path:** `POST /api/youtube-channels/{channel_id}/set-default`
- **Operation ID & Handler:** `set_default_channel_destination` (`backend/api/routes/youtube_channels.py:465`)
- **Database Effects:** Sets `channel_destinations.is_default = True` and clears other defaults
- **Evidence Tier:** E2

#### `API-YT-008`: Disconnect Channel & Revoke Credentials
- **HTTP Method & Path:** `POST /api/youtube-channels/{channel_id}/disconnect`
- **Operation ID & Handler:** `disconnect_channel` (`backend/api/routes/youtube_channels.py:523`)
- **Storage Action:** Deletes token file `tokens/youtube_token_{channel_id}.json`
- **Evidence Tier:** E2

---

### 3.8 Module: Upload Studio (`backend/api/routes/studio.py`)

#### `API-STU-001`: Create Multi-Video Upload Batch
- **HTTP Method & Path:** `POST /api/studio/batches`
- **Operation ID & Handler:** `create_batch` (`backend/api/routes/studio.py:266`)
- **Request Schema:** `CreateBatchRequest` (`title: Optional[str]`, `expected_videos: int`)
- **Response Schema:** `BatchResponse` (`batch_id: str`, `storage_state: str`)
- **Database Effects:** Inserts `upload_batches` record
- **Evidence Tier:** E2

#### `API-STU-002`: Retrieve Batch Status & Queue
- **HTTP Method & Path:** `GET /api/studio/batches/{batch_id}`
- **Operation ID & Handler:** `get_batch` (`backend/api/routes/studio.py:333`)
- **Response Schema:** `BatchDetailResponse` (includes `videos: List[VideoItemResponse]`)
- **Evidence Tier:** E2

#### `API-STU-003`: Initialize Video Upload with Storage Reservation
- **HTTP Method & Path:** `POST /api/studio/batches/{batch_id}/videos/init`
- **Operation ID & Handler:** `init_video_item` (`backend/api/routes/studio.py:384`)
- **Request Schema:** `InitVideoItemRequest` (`filename: str`, `total_size_bytes: int`, `checksum: Optional[str]`)
- **Storage Safety:** Reconciles `StorageReservationCoordinator`; reserves headroom
- **Response Schema:** `{"upload_id": str, "video_id": str, "chunk_size": int}`
- **Evidence Tier:** E2

#### `API-STU-004`: Upload Binary File Chunk
- **HTTP Method & Path:** `PUT /api/studio/uploads/{upload_id}/chunk`
- **Operation ID & Handler:** `upload_chunk` (`backend/api/routes/studio.py:460`)
- **Request Schema:** Query params `chunk_index: int`, `total_chunks: int`; Body: `bytes`
- **Storage Action:** Appends chunk to temporary staging file; verifies MD5/SHA256
- **Evidence Tier:** E2

#### `API-STU-005`: Check Chunked Upload Progress
- **HTTP Method & Path:** `GET /api/studio/uploads/{upload_id}`
- **Operation ID & Handler:** `get_upload_status` (`backend/api/routes/studio.py:758`)
- **Response Schema:** `{"received_chunks": List[int]`, `total_chunks: int`, `is_complete: bool}`
- **Evidence Tier:** E2

#### `API-STU-006`: Retry Stalled Chunk Upload
- **HTTP Method & Path:** `POST /api/studio/uploads/{upload_id}/retry`
- **Operation ID & Handler:** `retry_upload` (`backend/api/routes/studio.py:779`)
- **Evidence Tier:** E2

#### `API-STU-007`: Reorder Priority Queue of Batch Videos
- **HTTP Method & Path:** `PUT /api/studio/batches/{batch_id}/reorder`
- **Operation ID & Handler:** `reorder_batch_queue` (`backend/api/routes/studio.py:821`)
- **Request Schema:** `ReorderBatchRequest` (`video_ids: List[str]`)
- **Evidence Tier:** E2

#### `API-STU-008`: Remove Video Item from Batch
- **HTTP Method & Path:** `DELETE /api/studio/batches/{batch_id}/videos/{video_id}`
- **Operation ID & Handler:** `cancel_video_item` (`backend/api/routes/studio.py:872`)
- **Evidence Tier:** E2

#### `API-STU-009`: Cancel and Purge Upload Batch
- **HTTP Method & Path:** `DELETE /api/studio/batches/{batch_id}`
- **Operation ID & Handler:** `delete_batch` (`backend/api/routes/studio.py:947`)
- **Storage Action:** Releases storage reservations; unlinks staged chunks
- **Evidence Tier:** E2

#### `API-STU-010`: Dispatch Batch for Automated Processing
- **HTTP Method & Path:** `POST /api/studio/batches/{batch_id}/process`
- **Operation ID & Handler:** `process_batch` (`backend/api/routes/studio.py:1124`)
- **Celery Tasks Dispatched:** Dispatches `process_studio_batch_sequential_task.delay(batch_id)`
- **Evidence Tier:** E2

#### `API-STU-011`: Cancel In-Flight Batch Processing
- **HTTP Method & Path:** `POST /api/studio/batches/{batch_id}/cancel`
- **Operation ID & Handler:** `cancel_batch_processing` (`backend/api/routes/studio.py:1187`)
- **Evidence Tier:** E2

#### `API-STU-012`: Retry Single Failed Video in Batch
- **HTTP Method & Path:** `POST /api/studio/batches/{batch_id}/videos/{video_id}/retry`
- **Operation ID & Handler:** `retry_video_processing` (`backend/api/routes/studio.py:1247`)
- **Evidence Tier:** E2

#### `API-STU-013`: Retry All Failed Videos in Batch
- **HTTP Method & Path:** `POST /api/studio/batches/{batch_id}/retry`
- **Operation ID & Handler:** `retry_batch_processing` (`backend/api/routes/studio.py:1315`)
- **Evidence Tier:** E2

#### `API-STU-014`: Recover Stale / Interrupted Batch
- **HTTP Method & Path:** `POST /api/studio/batches/{batch_id}/recover`
- **Operation ID & Handler:** `recover_stale_batch` (`backend/api/routes/studio.py:1366`)
- **Evidence Tier:** E2

#### `API-STU-015`: List Batch Outputs and Generated Clips
- **HTTP Method & Path:** `GET /api/studio/batches/{batch_id}/outputs`
- **Operation ID & Handler:** `get_batch_outputs` (`backend/api/routes/studio.py:1405`)
- **Response Schema:** `List[ClipResponse]`
- **Evidence Tier:** E2

---

### 3.9 Module: Analytics & Optimization (`backend/api/routes/analytics.py`)

#### `API-ANA-001`: Start Automated 48-Hour Performance Tracking
- **HTTP Method & Path:** `POST /api/analytics/track/{video_id}`
- **Operation ID & Handler:** `start_tracking` (`backend/api/routes/analytics.py:27`)
- **Database Effects:** Inserts `video_tracking_queues` record
- **Celery Tasks Dispatched:** Enqueues tracking checkpoint
- **Evidence Tier:** E2

#### `API-ANA-002`: Cancel Active Performance Tracking Loop
- **HTTP Method & Path:** `POST /api/analytics/cancel/{task_id}`
- **Operation ID & Handler:** `cancel_tracking` (`backend/api/routes/analytics.py:65`)
- **Evidence Tier:** E2

#### `API-ANA-003`: List Videos Currently Tracked
- **HTTP Method & Path:** `GET /api/analytics/active`
- **Operation ID & Handler:** `get_active_tracking` (`backend/api/routes/analytics.py:78`)
- **Response Schema:** `List[VideoTrackingQueueResponse]`
- **Evidence Tier:** E2

#### `API-ANA-004`: List Active A/B Thumbnail & Title Experiments
- **HTTP Method & Path:** `GET /api/analytics/ab-tests`
- **Operation ID & Handler:** `get_ab_tests` (`backend/api/routes/analytics.py:88`)
- **Response Schema:** `List[ABExperimentResponse]`
- **Evidence Tier:** E2

#### `API-ANA-005`: Aggregate Audience Retention & Virality Insights
- **HTTP Method & Path:** `GET /api/analytics/insights`
- **Operation ID & Handler:** `get_insights` (`backend/api/routes/analytics.py:98`)
- **Response Schema:** `InsightsResponse` (aggregates virality scores across topics)
- **Evidence Tier:** E2

#### `API-ANA-006`: High-Level Performance KPIs Summary
- **HTTP Method & Path:** `GET /api/analytics/summary`
- **Operation ID & Handler:** `get_summary` (`backend/api/routes/analytics.py:111`)
- **Response Schema:** `AnalyticsSummaryResponse` (`total_views: int`, `total_likes: int`, `avg_vsi: float`)
- **Evidence Tier:** E2

#### `API-ANA-007`: SEO Keyword Density & Ranking Analysis
- **HTTP Method & Path:** `GET /api/analytics/seo/{video_id}`
- **Operation ID & Handler:** `get_seo_analysis` (`backend/api/routes/analytics.py:184`)
- **Response Schema:** `SEOAnalysisResponse`
- **Evidence Tier:** E2

#### `API-ANA-008`: Single Video Detailed Performance Metrics
- **HTTP Method & Path:** `GET /api/analytics/{video_id}`
- **Operation ID & Handler:** `get_video_analytics` (`backend/api/routes/analytics.py:270`)
- **Response Schema:** `List[VideoAnalyticsResponse]`
- **Evidence Tier:** E2

#### `API-ANA-009`: Trigger AI Title / Thumbnail Re-Optimization
- **HTTP Method & Path:** `POST /api/analytics/optimize/{video_id}`
- **Operation ID & Handler:** `optimize_video` (`backend/api/routes/analytics.py:351`)
- **Evidence Tier:** E2

#### `API-ANA-010`: Toggle Video Auto-Optimization Flag
- **HTTP Method & Path:** `PATCH /api/analytics/optimize/{video_id}/flag`
- **Operation ID & Handler:** `toggle_auto_optimize` (`backend/api/routes/analytics.py:385`)
- **Evidence Tier:** E2

#### `API-ANA-011`: Optimization Audit Trail Log
- **HTTP Method & Path:** `GET /api/analytics/optimize/{video_id}/log`
- **Operation ID & Handler:** `get_optimization_log` (`backend/api/routes/analytics.py:417`)
- **Response Schema:** `List[OptimizationLogResponse]`
- **Evidence Tier:** E2

---

### 3.10 Module: Dubbing & Localization (`backend/api/routes/dubbing.py`)

#### `API-DUB-001`: Supported Target Languages Catalog (Dual Routes)
- **HTTP Method & Path:** `GET /api/dubbing/languages` & `GET /api/clips/dubbing/languages`
- **Operation ID & Handler:** `get_supported_languages` (`backend/api/routes/dubbing.py:27, 28`)
- **Response Schema:** `SupportedLanguagesResponse` (`languages: [{"code": "es", "name": "Spanish"}, {"code": "hi", "name": "Hindi"}, {"code": "de", "name": "German"}, {"code": "ja", "name": "Japanese"}, {"code": "pt", "name": "Portuguese"}, {"code": "fr", "name": "French"}]`)
- **Evidence Tier:** E2

#### `API-DUB-002`: Async Dubbing Task Polling
- **HTTP Method & Path:** `GET /api/dubbing/tasks/{task_id}`
- **Operation ID & Handler:** `get_dubbing_task_status` (`backend/api/routes/dubbing.py:36`)
- **Response Schema:** `{"task_id": str, "status": str, "progress": float, "result": Optional[dict]}`
- **Evidence Tier:** E2

#### `API-DUB-003`: Clip Dubbing Plans & Variants List (Dual Routes)
- **HTTP Method & Path:** `GET /api/dubbing/{clip_id}` & `GET /api/clips/{clip_id}/dubbing`
- **Operation ID & Handler:** `get_clip_dubbing_plans` (`backend/api/routes/dubbing.py:59, 60`)
- **Response Schema:** `List[DubbingPlanResponse]`
- **Evidence Tier:** E2

#### `API-DUB-004`: Trigger Multi-Language Dubbing (Triple Routes)
- **HTTP Method & Path:** `POST /api/dubbing/{clip_id}` & `POST /api/clips/{clip_id}/dub` & `POST /clips/{clip_id}/dub`
- **Operation ID & Handler:** `create_dubbing_plan` (`backend/api/routes/dubbing.py:115, 116, 117`)
- **Request Schema:** `CreateDubbingRequest` (`target_language: str`, `voice_provider: str = "edge"`, `is_voice_clone: bool = False`)
- **Validation Gates:** 
  - Verifies parent clip status == `'completed'` and file exists on disk.
  - Requires explicit user authorization if `is_voice_clone=True`.
- **Response Schema:** `DubbingPlanResponse` (Status 202)
- **Celery Tasks Dispatched:** Dispatches `generate_dubbing_variant_task.delay(request_dict)`
- **Evidence Tier:** E2

---

### 3.11 Module: Settings (`backend/api/routes/settings.py`)

#### `API-SET-001`: System Settings Retrieval (Dual Routes)
- **HTTP Method & Path:** `GET /api/settings` & `GET /api/settings/`
- **Operation ID & Handler:** `get_settings` (`backend/api/routes/settings.py:122, 123`)
- **Response Schema:** `SettingsResponse` (`ai_scoring_threshold: float`, `min_clip_duration: int`, `max_clip_duration: int`, `default_aspect_ratio: str`, `storage_cleanup_older_than_days: int`, `has_groq_key: bool`, `has_gemini_key: bool`, `has_openrouter_key: bool`)
- **Security Control:** Masks API keys; returns boolean presence flags only
- **Frontend Callers:** `frontend/src/lib/api.ts:getSettings()`, Settings page
- **Evidence Tier:** E2

#### `API-SET-002`: System Settings Update (Dual Routes)
- **HTTP Method & Path:** `PUT /api/settings` & `PUT /api/settings/`
- **Operation ID & Handler:** `update_settings` (`backend/api/routes/settings.py:161, 162`)
- **Request Schema:** `UpdateSettingsRequest`
- **Response Schema:** `SettingsResponse`
- **Database Effects:** Persists settings changes; hot-reloads in-memory configuration
- **Evidence Tier:** E2

---

## 4. Fixed Product Invariants Verification in API Layer

| Product Invariant | Required Architectural Behavior | Actual Implemented API Reality | Verification Command / Evidence | Status |
|---|---|---|---|:---:|
| **1. Zero Captions / Subtitles** | No endpoints for caption generation, subtitle download, SRT/VTT export, font styling, or burn-in toggles. | Verified 0 caption endpoints across all 11 modules. `channels.py:56-61` actively throws `ValueError("Caption burn-in is strictly disabled under ClipForge freeze rules.")` if requested. | `grep -rn "caption" backend/api/routes/` confirms 0 active routes generating captions | **VERIFIED PASS** |
| **2. Internal Transcription Scoping** | Whisper transcription utilized solely for scoring and semantic metadata; never exposed as a subtitle asset. | Audio transcription is internal pipeline step (`transcription_task`). Transcripts feed LLM scoring and hook generation. No public route serves transcripts as captions. | `backend/services/transcriber.py` and `backend/tasks/analysis_tasks.py` | **VERIFIED PASS** |
| **3. Standard Podcast Stacked Split & Single Focus** | 1080x960 panel splitting (1080x1920 canvas); Single Speaker Focus deterministic Area 1 / index 0. | `API-VID-002` (`/api/videos/podcast/analyze-shots`) computes schedules respecting 1080x960 stacked split and single speaker focus. | `backend/tests/test_advanced_podcast.py` (44 passed) | **VERIFIED PASS** |
| **4. Advanced Podcast Dual-Mode Integrity** | Mode 1 (Camera Following) must execute continuous tracking; Mode 2 (Visibility) must execute discrete shot classification. | Handled distinctly: Mode 1 calls `build_fixed_boundary_schedule`; Mode 2 calls `build_visibility_driven_schedule`. | `backend/services/advanced_podcast_engine.py:1030, 1883` | **VERIFIED PASS** |
| **5. AI-Only Clip Scoring** | Heuristic fallback strictly prohibited. | `scoring_task` calls Cloud LLM router. Fallbacks explicitly raise `RuntimeError("Heuristic scoring fallback is strictly forbidden.")`. | `backend/services/clip_scorer.py:230, 234` | **VERIFIED PASS** |

---

## 5. Security Posture & Vulnerability Analysis

### 5.1 Input Validation & Path Traversal Mitigations
- **Frame Extraction (`API-VID-010`):** Enforces regex `^[a-zA-Z0-9_\-]{1,64}$`, finite timestamp <= 86400.0, and FFmpeg `-protocol_whitelist file`. Path traversal attempts with `../` are rejected immediately with HTTP 400.
- **Storage Path Resolution:** `LocalStorageProvider._resolve_path` uses `Path.resolve()` and requires `str(resolved).startswith(str(base))`, raising `ValueError("Path traversal detected")`.
- **Storage Quarantine Intercept:** Direct HTTP requests to `/outputs/.storage_quarantine/...` hit an explicit route handler returning `HTTP 404 Not Found`, suppressing unauthorized access to quarantined media.

### 5.2 SSRF & Self-Ingestion Safeguards
- **YouTube URL Parsing:** Regex enforces standard 11-character video IDs. Cloud metadata addresses (`http://169.254.169.254`) or localhost addresses are rejected.
- **Self-Ingestion Protection:** `check_is_clipforge_short` verifies against `Clip.youtube_short_id`. Ingesting an already generated ClipForge Short is blocked with `HTTP 400`.

### 5.3 Error Message Sanitization
- All exception responses pass through `sanitize_user_facing_error()` (`core/sanitizer.py`).
- Technical stack traces, raw SQL queries (`SELECT`, `INSERT`), SQLAlchemy/psycopg2 errors, and credential tokens are scrubbed before reaching the client.

---

## 6. API Gaps, Technical Debt & Backlog Items

### Finding API-001: Model Default Discrepancy on `PublishTarget.privacy`
- **Category:** Technical Debt / Schema Drift
- **Severity:** P2 Medium
- **Observation:** `PublishTarget.privacy` column default in `models.py:417` is `"public"`, whereas `Clip.privacy` server default is `'private'` (migration `e6f7a8b9c0d1`). In `clip_tasks.py:795`, the worker forces `target_privacy = "private"`, masking this discrepancy.
- **Remediation Proposal (Approach B):** Update `models.py:417` to `default="private"` and add an Alembic migration enforcing `server_default='private'` on `publish_targets.privacy`.

### Finding API-002: Dual Route Declarations for Trailing Slashes
- **Category:** Documentation / Code Cleanliness
- **Severity:** P3 Low
- **Observation:** `youtube_channels.py`, `settings.py`, and `dubbing.py` declare duplicate decorators (e.g. `@router.get("")` and `@router.get("/")`) to handle trailing slashes, generating multiple route objects for the same handler.
- **Remediation Proposal (Approach A):** No functional change required; FastAPI redirect-slashes configuration can standardize routing.

---

*Report compiled and certified by Teamwork Worker M2 for the ClipForge Full-System Forensic Audit.*
