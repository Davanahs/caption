# CLIPFORGE — FULL WEBSITE & APPLICATION INVENTORY

**Document Type:** Comprehensive Architectural & Feature Inventory  
**Project:** ClipForge (`d:\automation video clips\clipforge`)  
**Git Branch:** `feature/layout` (HEAD: `68b9bcd7d3688c6bd8feb781d98df72d14351e97`)  
**Audit Depth:** Complete End-to-End Forensic Discovery  
**Execution Framework:** Gravitas

---

## 1. Architectural System Overview

ClipForge is an AI-powered YouTube Shorts and vertical video automation platform designed to ingest long-form videos (via YouTube URLs or direct local file uploads), perform speech recognition and scene understanding, detect speakers and faces, compute viral clipping opportunities, reframe video streams into 9:16 vertical composition, and publish clips to YouTube Shorts.

### End-to-End Data & Execution Flow
```mermaid
graph TD
    Browser[Browser / Next.js Client] -->|HTTP / WebSocket| FastApi[FastAPI Backend - Port 8000]
    Browser -->|Static Media| Mounts[Static Mounts: /outputs & /uploads]
    FastApi -->|Async Sessions| Postgres[(PostgreSQL 15 - Port 5433)]
    FastApi -->|Task Dispatch| Redis[(Redis 7 - Port 6379 DB 0)]
    Redis -->|Task Consumption| Worker[Celery Worker - Concurrency 4]
    Worker -->|State Updates| RedisBack[(Redis 7 - DB 1 Result Backend)]
    Worker -->|DB Sync| Postgres
    Worker -->|FFmpeg / MediaPipe / Whisper| Pipeline[Media Processing Engine]
    Pipeline -->|Artifacts & Videos| OutputDir[/app/outputs]
    Beat[Celery Beat] -->|Scheduled Sweeps| Redis
    FastApi -->|Background Scheduler| APScheduler[APScheduler Tasks]
    Worker -->|OAuth2 / Data API v3| YouTubeAPI[YouTube Partner API]
```

---

## 2. Page & Route Master Directory

| Page ID | Route Path | User-Facing Title | Primary Entry Point | Major Components Used | Core API Endpoints | State & Storage Dependencies | Background Worker Tasks | Browser Status |
| :---: | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :---: |
| **PAGE-01** | `/` | Dashboard | Sidebar `⚡ Dashboard` | `ProcessVideoModal`, `PodcastSelectionModal`, `LayoutThumbnailSelector`, StatsCounter, QueueTracker | `/api/stats`, `/api/videos/url`, `/api/videos/batch`, `/api/jobs/active`, `/api/jobs/history`, `/api/jobs/stats`, `/api/jobs/ws/{id}` | Local component state, WebSocket live sync, job polling | `start_video_processing`, `candidate_generation`, `scoring`, `reframe_clip`, `render_clip` | **PASS (HTTP 200)** |
| **PAGE-02** | `/podcasts` | Podcasts / Interviews Studio | Sidebar `🎙️ Podcasts` | `PodcastSelectionModal`, Area bounding canvas, Live 9:16 preview container | `/api/videos/podcast/analyze-shots`, `/api/videos/podcast/analysis-status/{id}`, `/api/videos/url` | Drag/drop bounding boxes, normalized coordinates `[0,1]`, shot schedule state | `analyze_podcast_shots_task`, `start_video_processing` | **PASS (HTTP 200)** |
| **PAGE-03** | `/studio` | Upload Studio | Sidebar `🎞️ Upload Studio` | Chunked file uploader, batch queue manager, video item list, reselection prompt | `/api/studio/batches/*`, `/api/studio/uploads/*`, `/api/health` | IndexedDB `staged_videos`, resumable upload state, single-writer lease | `process_studio_batch_sequential_task`, `on_studio_video_finished_task`, `recover_stale_studio_batches_task` | **PASS (HTTP 200)** |
| **PAGE-04** | `/clips` | Clips Library | Sidebar `🎬 Clips Library` | `PreviewModal`, `RetentionHeatmap`, Storage cleanup modal, Multi-variant selector | `/api/clips/*`, `/api/clips/cleanup/*`, `/api/clips/{id}/hook/*`, `/api/clips/{id}/broll-*`, `/api/clips/{id}/sfx-*`, `/api/dubbing/*` | Clip filtering, sorting, variant selection, pagination | `apply_hook_plan`, `apply_broll`, `apply_sfx`, `generate_dubbing_variant_task`, `cleanup_expired_artifacts_task` | **PASS (HTTP 200)** |
| **PAGE-05** | `/analytics` | Analytics & Insights | Sidebar `📊 Analytics` | Performance tracker cards, SEO score inspector, Optimization log, Realtime tracker controls | `/api/analytics/*`, `/api/analytics/summary`, `/api/analytics/ab-tests`, `/api/analytics/insights`, `/api/analytics/active` | Selected clip metrics, auto-optimizer flag, active telemetry trackers | `track_and_optimize_clips`, background delayed analytics poller | **PASS (HTTP 200)** |
| **PAGE-06** | `/automation` | Monitored Channels & Automation | Sidebar `🤖 Automation` | Monitored channels table, video discovery list, decision countdown modal, channel profile editor | `/api/channels/*`, `/api/channels/decisions/*`, `/api/channels/{id}/historical-*` | Channel profiles, batch selection map, decision countdown timer | `sweep_pending_decisions_task`, `resolve_video_decision_countdown`, periodic channel monitoring | **PASS (HTTP 200)** |
| **PAGE-07** | `/youtube-channels` | My YouTube Channels | Sidebar `📺 My YouTube Channels` | Connected channels grid, OAuth connect modal, channel publishing settings modal, stats cooldown | `/api/youtube-channels/*`, `/api/youtube-channels/oauth-url`, `/api/youtube-channels/connect` | Connected channel credentials, quota cooldown timers (60s), primary destination selection | Synchronous token exchange, channel-scoped credential caching | **PASS (HTTP 200)** |
| **PAGE-08** | `/publish` | Publish Queue & Scheduler | Sidebar `🚀 Publish` | `VisualClipPicker`, Publishing queue list, scheduling form, destination picker | `/api/publish/*`, `/api/publish/queue`, `/api/publish/publish-now`, `/api/publish/schedule` | Selected clip metadata, publishing destination ID, schedule timestamp | `publish_clip_task`, `recover_stranded_publish_jobs` | **PASS (HTTP 200)** |
| **PAGE-09** | `/settings` | System Settings | Sidebar `⚙️ Settings` | System settings form, secret masked inputs, model selectors, quota intervals | `/api/settings`, `/api/health` | Dynamic settings in `.env`, localStorage offline fallback, masked secret states | Dynamic settings synchronization across API and worker tasks | **PASS (HTTP 200)** |

---

## 3. UI Component Inventory & State Mapping

### A. Shared Global Navigation (`Sidebar.tsx`)
- **Visual Purpose:** Primary persistent sidebar on desktop/tablet, slide-out drawer on mobile.
- **Diagnostic Panel:** Polls `/api/health` and `/api/jobs/stats` every 10 seconds via AbortController (4s timeout).
- **Status Dots:** Realtime health indicators for API, Database, Redis, and Worker.
- **Worker Status Badge:** Active vs Queued job counter with green (`online`) / red (`offline`) state.
- **Responsive Drawer:** Hamburger toggle, backdrop overlay, escape key dismissal, automatic route change closure.

### B. Video Ingestion Modals
1. **`ProcessVideoModal.tsx`:**
   - Single & batch YouTube URL configuration.
   - Clip generation modes: AI Highlights (`ai_highlights`) vs Full Source Equal Split (`equal_split`).
   - Duration presets: 15s, 30s, 45s, 49s (Optimal badge), 60s (Max badge).
   - Layout selector integration (`fill_blur`, `fit_black`, `smart_crop`, `stacked_16_9`, `center_crop`, `split_screen`).
   - Optional enhancements: Viral hook titles, B-roll insertions, Sound FX, Multi-language dubbing.
2. **`PodcastSelectionModal.tsx`:**
   - Multi-speaker video bounding box editor.
   - Dual-mode architecture: Manual area layout (`stacked` / `single_region`) vs Advanced Camera Following (`fixed_two_person` / `visibility_driven`).
   - Normalized coordinate transformations (`podcastCoordinates.ts`) with outward integer rounding.
   - Dynamic 9:16 output preview mirror with provenance disclaimers.
   - Cut schedule inspector with interactive row selection (`onClick`).

### C. Upload Studio Components (`app/studio/page.tsx`)
- Drag-and-drop file ingestion zone with multi-file staging.
- Reselection recovery for evicted File Blobs (`reattachFileBlob`).
- Storage simulation mode controls (`none`, `quota_blob_evict`, `fatal_write_fail`).
- Client-side resumable streaming (`streamFileInChunks`) with RFC 7233 byte-range validation.

### D. Clips Library Components (`app/clips/page.tsx`)
- `PreviewModal`: HTML5 video player, download links, variant switcher (original, hook, broll, sfx, dubbed).
- `RetentionHeatmap`: Second-by-second predicted engagement curve with drop-off markers.
- Storage Cleanup Modal: Quarantine preview and execute actions with date and status filters.

### E. Automation & Monitoring Components (`app/automation/page.tsx`)
- `LayoutPreviewSelector.tsx`: Visual preview cards for all 6 layout framing choices.
- `YouTubeVideoThumbnail.tsx`: Resilient image loader with fallback strategies for YouTube CDN thumbnails.
- Decision Countdown Modal: 15-second auto-pilot countdown timer with customize, apply defaults, and cancel actions.

---

## 4. Backend Service & Pipeline Architecture

| Service Module | File Path | Functional Responsibility | Database Models | Upstream / Downstream Callers |
| :--- | :--- | :--- | :--- | :--- |
| **Layout Engine** | `backend/services/layout_engine.py` | 9:16 vertical reframe filtergraphs, blur backgrounds, face tracking crops | `Video`, `Clip` | `clip_tasks.reframe_clip` |
| **Advanced Podcast Engine** | `backend/services/advanced_podcast_engine.py` | Dual-speaker framing, shot boundary reframing, visibility classifier | `Job`, `Video` | `analysis_tasks.analyze_podcast_shots_task` |
| **Downloader** | `backend/services/downloader.py` | `yt-dlp` YouTube video and audio stream ingestion, resolution capping | `Video` | `video_tasks.download_task` |
| **Scene Detector** | `backend/services/scene_detector.py` | Content-aware visual scene boundary detection via PySceneDetect | `ContentAnalysis` | `analysis_tasks.scene_detection_task` |
| **Transcriber** | `backend/services/transcriber.py` | Fast speech-to-text with word-level timestamps via Faster-Whisper | `ContentAnalysis` | `analysis_tasks.transcription_task` |
| **Clip Scorer** | `backend/services/clip_scorer.py` | Heuristic and AI viral score prediction, hook detection, transcript windowing | `Clip` | `clip_tasks.scoring` |
| **Publisher** | `backend/services/publisher.py` | YouTube Partner API upload, metadata setting, privacy governance | `PublishRecord`, `Channel` | `scheduler.publish_clip_task` |
| **Channel Monitor** | `backend/services/channel_monitor.py` | RSS and API feed discovery of new long-form videos on monitored channels | `Channel`, `VideoDecision` | `main.scheduled_channel_check` |
| **Realtime Tracker** | `backend/services/realtime_tracker.py` | YouTube video performance tracking (views, likes, retention velocity) | `VideoAnalytics`, `Optimizations` | `main.scheduled_tracker_check` |

---

## 5. Celery Task Registry Architecture

All 34 production tasks are imported and discovered via `TASK_MODULES` in `backend/tasks/celery_app.py`:
- `backend.tasks.orchestration`: `start_video_processing`, `orchestration_callback`, `handle_pipeline_failure`, `job_completion_aggregation`, `stale_recovery_task`, `sweep_pending_decisions_task`, `resolve_video_decision_countdown`.
- `backend.tasks.video_tasks`: `download_task`, `validate_media_task`, `validate_output`.
- `backend.tasks.audio_tasks`: `extract_audio_task`.
- `backend.tasks.analysis_tasks`: `transcription_task`, `scene_detection_task`, `analyze_podcast_shots_task`.
- `backend.tasks.clip_tasks`: `candidate_generation`, `clip_selection`, `scoring`, `reframe_clip`, `render_clip`.
- `backend.tasks.scheduler`: `publish_clip`, `publish_clip_task`, `recover_stranded_publish_jobs`, `track_and_optimize_clips`.
- `backend.tasks.storage_tasks`: `cleanup_expired_artifacts_task`, `detect_orphans_task`.
- `backend.tasks.hook_tasks`: `analyze_hook_opportunities`, `apply_hook_plan`, `apply_broll`, `apply_sfx`, `apply_autofix`.
- `backend.tasks.dubbing_tasks`: `generate_dubbing_variant_task`.
- `backend.tasks.studio_tasks`: `process_studio_batch_sequential_task`, `on_studio_video_finished_task`, `recover_stale_studio_batches_task`.
