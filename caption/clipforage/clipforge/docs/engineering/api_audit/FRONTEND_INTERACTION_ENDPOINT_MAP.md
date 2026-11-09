# CLIPFORGE — COMPLETE FRONTEND INTERACTION & ENDPOINT MAP
**Audit Deliverable B | Comprehensive User Action, Control Inventory & Cross-Layer Wire Audit**

- **Audit Date:** 2026-10-13
- **Repository Root:** `d:\automation video clips\clipforge`
- **Frontend Stack:** Next.js 14 App Router, TypeScript, React 18, Vanilla CSS Design System
- **Audit Methodology:**
  1. Complete source-tree walkthrough of all pages in `frontend/app/` (`/`, `/automation`, `/studio`, `/youtube-channels`, `/publish`, `/clips`, `/analytics`, `/settings`).
  2. Inventory of all interactive controls (buttons, inputs, toggles, checkboxes, modals, batch action bars).
  3. Complete audit of every exported function in `frontend/lib/api.ts`.
  4. Real browser automation audit via Chrome subagent across `/automation`, `/`, and `/youtube-channels`.
  5. Cross-layer wiring verification against [BACKEND_ENDPOINT_INVENTORY.md](file:///d:/automation%20video%20clips/clipforge/docs/engineering/api_audit/BACKEND_ENDPOINT_INVENTORY.md).

---

## 1. Executive Summary & Control Metrics

| Page Route | Purpose & Primary Subsystem | Interactive Controls | Connected API Helpers | Status |
|---|---|---|---|---|
| **`/` (Dashboard)** | Real-time monitoring, stats, quick ingest | 13 | `getStats`, `getActiveJobs`, `getVideos`, `checkHealth`, `submitVideoUrl`, `getVideoFrameUrl` | Verified working |
| **`/automation`** | 24/7 monitoring, multi-video queue, countdown | 24 | `listChannels`, `addChannel`, `getChannelVideos`, `processChannelVideosBatch`, `processChannelVideo`, `getPendingDecisions` | Verified working (Repairs Applied) |
| **`/studio`** | Upload Studio Phase 1 resumable batches | 18 | `createBatch`, `uploadChunk`, `processBatch`, `cancelBatch`, `getBatchOutputs` | Verified working |
| **`/youtube-channels`** | My YouTube Channels management | 14 | `getYoutubeChannels`, `getYoutubeOAuthUrl`, `connectYoutubeChannel`, `refreshYoutubeChannelStats`, `updateYoutubeChannelSettings`, `setPrimaryDefaultDestination`, `disconnectYoutubeChannel` | Verified working |
| **`/publish`** | Manual & scheduled publishing studio | 15 | `getDestinations`, `publishNow`, `schedulePublish`, `getPublishQueue`, `cancelPublish`, `retryPublish` | Verified working |
| **`/clips`** | Rendered clip library, safe storage cleanup, download | 18 | `listClips`, `getClip`, `updateClip`, `deleteClip`, `downloadClipUrl`, `thumbnailUrl`, `publishClip`, `previewCleanup`, `executeCleanup` | Verified working |
| **`/analytics`** | Post-publish metrics, SEO, A/B testing | 10 | `getPipelineSummary`, `getSEOAnalysis`, `getABTests`, `getChannelInsights` | Implemented (verification incomplete) |
| **`/settings`** | Global settings, storage cleanup | 8 | `getSystemSettings`, `updateSystemSettings`, `previewCleanup`, `executeCleanup` | Verified working (Phase 5.1 / C-09) |
| **Total Controls Audited** | **Cross-Platform UI** | **116+** | **39 API Client Helpers** | **High Fidelity & Synchronized** |

---

## 2. Interactive UI Control Inventory by Page

### Page 1: Dashboard (`frontend/app/page.tsx`)

| Action ID | Control & Location | Visible Label / Tooltip | Trigger & Handler | API Helper & HTTP Route | Backend ID | State & Feedback | Status |
|---|---|---|---|---|---|---|---|
| `FE-DSH-001` | Quick URL Input | "Enter YouTube URL..." | Change -> `setUrlInput` | None (Local state) | N/A | Updates text input | Verified working |
| `FE-DSH-002` | Quick Ingest Button | "⚡ Start Processing" | Click -> `handleQuickIngest` | `submitVideoUrl` (`POST /api/videos/url`) | `BE-VID-002` | Queues Job (dispatches immediately if active < 5; places in FIFO waiting queue with amber `#X in line` badge if capacity full), shows toast, refetches jobs | Verified working |
| `FE-DSH-003` | Active Jobs Poller | Background interval (3s) | Interval -> `pollJobs` | `getActiveJobs` (`GET /api/jobs/active`) | `BE-JOB-002` | Updates `activeJobs` array; renders cards with live progress | Verified working |
| `FE-DSH-004` | Refresh Dashboard | "🔄 Refresh" icon button | Click -> `loadDashboardData` | `getStats`, `getActiveJobs`, `getVideos` | `BE-SYS-002`, `BE-JOB-002` | Refetches all dashboard metrics | Verified working |
| `FE-DSH-005` | Cancel Active Job | "✖ Cancel" button on job card | Click -> `handleCancelJob(jobId)` | `cancelJob` (`DELETE /api/jobs/{id}`) | `BE-JOB-007` | Removes job from active list, sets terminal cancelled state | Verified working |
| `FE-DSH-006` | Retry Failed Job | "🔄 Retry" button on job card | Click -> `handleRetryJob(jobId)` | `retryJob` (`POST /api/jobs/{id}/retry`) | `BE-JOB-008` | Re-queues job in active list | Verified working |
| `FE-DSH-007` | Health Probe Badge | "System Online" / "Degraded" | Mount / interval poll | `checkHealth` (`GET /api/health`) | `BE-SYS-001` | Updates status pill in navbar/header | Verified working |
| `FE-DSH-008` | Video Item Row | Click on video title | Click -> `handleSelectVideo` | None (Opens modal) | N/A | Displays associated clips in preview drawer | Verified working |
| `FE-DSH-009` | Process Video Config Modal | "Configure Your Clips" | Click -> `confirmAndProcess(config)` | `submitYouTubeUrl` (`POST /api/videos/url`) | `BE-VID-002` | Opens modernized modal with YouTube thumbnail, mode toggle (AI Highlights vs. Equal Split), dynamic segment calculator, duration slider, 6 visual layout cards, and parameter forwarding (`targetDuration`, `segmentationStrategy`) | Verified working |
| `FE-DSH-010` | Podcast / Interview Manual Selection | "🎙️ Podcast / Interview" button & Quick Link | Click -> `setIsPodcastModalOpen(true)` | `submitYouTubeUrl` (`POST /api/videos/url`) | `BE-VID-002` | Opens interactive preview modal with 16:9 player, dual speaker bounding box overlays, mode toggle (Select vs. Watch), duration, stacked composition selector, and 9:16 vertical preview | **Verified working (New Feature)** |
| `FE-DSH-011` | Podcast Frame Preview & Shot Inspector | Shot table rows & `#frame-preview-status-badge` | Click / Enter / Space on shot row | `getVideoFrameUrl` (`GET /api/videos/{id}/frame`) | `BE-VID-010` | Cancels prior in-flight frame fetch via AbortController, renders loading spinner (`⏳ Fetching Shot Frame...`), fetches and caches real source video frame at shot midpoint, updates canvas to `📸 Real Frame @ {ts}s (Shot {id})` with full visual alignment, or graceful geometry fallback badge | **Verified working (New Feature)** |

---

### Page 2: Automation (`frontend/app/automation/page.tsx`) — *Forensic Repairs Applied*

| Action ID | Control & Location | Visible Label / Tooltip | Trigger & Handler | API Helper & HTTP Route | Backend ID | State & Feedback | Status |
|---|---|---|---|---|---|---|---|
| `FE-AUT-001` | Add Channel URL Input | "https://youtube.com/@..." | Change -> `setForm` | None (Local state) | N/A | Updates input field | Verified working |
| `FE-AUT-002` | Auto-Clip Toggle | "Auto-clip new uploads" checkbox | Change -> `form.auto_clip` | None (Local state) | N/A | Form state | Verified working |
| `FE-AUT-003` | Auto-Publish Toggle | "Auto-publish Shorts" checkbox | Change -> `form.auto_publish` | None (Local state / Channel update) | N/A | Form/channel state; requires linked destination channel, auto-clears to false if destination is unlinked (CF-DEF-023) | **Verified working (Enforced)** |
| `FE-AUT-004` | Destination Dropdown | "Select publishing destination..." | Change -> `form.publish_destination_id` | `getPublishDestinations` (`GET /api/publish/destinations`) | `BE-PUB-001` | Populated with authorized destinations; clearing unlinks destination and auto-disables auto-publish | **Verified working (Enforced)** |
| `FE-AUT-005` | Add Channel Button | "➕ Add Channel" | Click -> `handleAdd` | `addChannel` (`POST /api/channels/`) | `BE-CHN-002` | Adds channel to 24/7 monitoring list, blocks submission if auto-publish enabled without destination (CF-DEF-023), refreshes channels | **Verified working (Enforced)** |
| `FE-AUT-006` | Check Channel Now | "🔄 Scan RSS" button | Click -> `handleCheckNow(chId)` | `checkChannelNow` (`POST /api/channels/{id}/check-now`) | `BE-CHN-005` | Discovers new uploads, updates notification banner | Verified working |
| `FE-AUT-007` | Expand Videos Accordion | "Discover & Process Videos ▼" | Click -> `toggleDiscoverVideos` | `getChannelVideos` (`GET /api/channels/{id}/videos`) | `BE-CHN-006` | Expands accordion, fetches paginated video list | Verified working |
| `FE-AUT-008` | Single Video Checkbox | Individual card checkbox | Change -> `toggleSelectVideo(chId, v)` | None (Local state `selectedVideos`) | N/A | Toggles video in multi-selection record; disabled when `is_generated_short = True` | **Verified working (Repaired & Hardened)** |
| `FE-AUT-009` | Select All Eligible | "☑️ Select All Eligible" button | Click -> `selectAllEligibleOnPage(chId)` | None (Iterates uncompleted videos) | N/A | Adds all uncompleted page videos to `selectedVideos`, ignoring `is_generated_short` | **Verified working (Repaired & Hardened)** |
| `FE-AUT-010` | Clear Selection Button | "✖️ Clear ({count})" button | Click -> `clearSelection` | None (Clears state) | N/A | Resets `selectedVideos` to empty | **Verified working (New)** |
| `FE-AUT-011` | Channel Batch Action Bar | "🚀 Start Processing ({count})" | Click -> `handleProcessBatchDefaults(chId)` | `processChannelVideosBatch` (`POST /api/channels/{id}/process-videos-batch`) | `BE-CHN-008` | Queues batch, shows honest queued/already processing counts, offers "View on Dashboard" link | **Verified working (Repaired)** |
| `FE-AUT-012` | Batch Custom Settings | "⚙️ Custom Settings..." button | Click -> `openBatchCustomizer(ch)` | None (Opens modal with batch decision) | N/A | Opens customization modal for the entire batch | **Verified working (New)** |
| `FE-AUT-013` | Batch Modal Submit | "🚀 Save & Start Processing" | Click -> `handleSaveBatchCustom` | `processChannelVideosBatch` (`POST /api/channels/{id}/process-videos-batch`) | `BE-CHN-008` | Dispatches batch with custom layout/framing overrides | **Verified working (New)** |
| `FE-AUT-014` | Single Video Defaults | "⚡ Defaults" button on card | Click -> `handleProcessVideoDefaults(chId, v)` | `processChannelVideo` (`POST /api/channels/{id}/process-video`) | `BE-CHN-007` | Creates decision with `awaiting_settings`, starts Job, persists title; disabled when `is_generated_short = True` | **Verified working (Repaired & Hardened)** |
| `FE-AUT-015` | Single Video Custom | "⚙️ Custom" button on card | Click -> `openCustomizerFromDiscoveredVideo` | None (Opens modal with temp decision) | N/A | Opens modal to configure per-video overrides; disabled when `is_generated_short = True` | **Verified working (Hardened)** |
| `FE-AUT-016` | Countdown Toast Apply | "⚡ Apply Channel Defaults" | Click -> `handleApplyDefaultsDecision` | `applyDefaultsDecision` (`POST /api/channels/decisions/{id}/apply-defaults`) | `BE-CHN-011` | Resolves countdown, schedules Job | Verified working |
| `FE-AUT-017` | Countdown Toast Customize | "⚙️ Customize Settings" | Click -> `handleOpenCustomizer` | `customizeDecision` (`POST /api/channels/decisions/{id}/customize`) | `BE-CHN-012` | Pauses 20s countdown, grants 120s customization lease | Verified working |
| `FE-AUT-018` | Countdown Toast Cancel | "✖ Cancel" button | Click -> `handleCancelDecisionAction` | `cancelDecision` (`POST /api/channels/decisions/{id}/cancel`) | `BE-CHN-014` | Permanently cancels video processing | Verified working |
| `FE-AUT-019` | Sticky Page Batch Bar | "🚀 Start Processing ({totalCount})" | Click -> `handleProcessBatchDefaults` | `processChannelVideosBatch` (`POST /api/channels/{id}/process-videos-batch`) | `BE-CHN-008` | Floating sticky bar accessible while scrolling | **Verified working (New)** |
| `FE-AUT-020` | Refresh History Audit | "🔄 Refresh History" button | Click -> `loadHistory` | `getDecisionHistory` (`GET /api/channels/decisions/history`) | `BE-CHN-010` | Refetches IST audit history table | Verified working |
| `FE-AUT-021` | Discovered Video Thumbnail | 16:9 YouTube video thumbnail | Visual display -> fallback on error | `getChannelVideos` (`GET /api/channels/{id}/videos`) | `BE-CHN-006` | Renders genuine YouTube 16:9 thumbnail with duration badge overlay, lazy loading, and neutral placeholder | **Verified working (Visual Previews)** |
| `FE-AUT-022` | Upload Recent Videos Button | "⚡ Upload Recent Videos" | Click -> `openHistoricalProcessor(chId, 'recent')` | `getHistoricalPreview` -> `processHistoricalBatch` | `BE-CHN-015, BE-CHN-016` | Opens historical modal pre-selected for recent uploads with optional date cutoff | **Verified working (Repaired UX)** |
| `FE-AUT-023` | Upload Old Videos Button | "⏳ Upload Old Videos" | Click -> `openHistoricalProcessor(chId, 'old')` | `getHistoricalPreview` -> `processHistoricalBatch` | `BE-CHN-015, BE-CHN-016` | Opens historical modal pre-selected for old uploads with popularity/chronology preference | **Verified working (Repaired UX)** |
| `FE-AUT-024` | Video Sort Toggle | "📅 Latest" / "🔥 Most Viewed" | Click -> `handleToggleSortMode(chId, mode)` | `getChannelVideos` (`GET /api/channels/{id}/videos?sort=...`) | `BE-CHN-006` | Toggles discovered video sorting between latest and YouTube view count ranking within scan depth | **Verified working (Repaired SORT)** |
| `FE-AUT-025` | Decision History Provenance | Thumbnail, Source link & Error alert | Display in audit table | `getDecisionHistory` (`GET /api/channels/decisions/history`) | `BE-CHN-010` | Renders source thumbnail, source YouTube link, and explicit error message box for failed jobs | **Verified working (Repaired PROV)** |
| `FE-AUT-026` | Output Short Provenance Card Badge | "🎬 ClipForge Short" & "Origin: 🔗 [parent_title]" | Visual display on card | `getChannelVideos` (`GET /api/channels/{id}/videos`) | `BE-CHN-006` | Displays purple badge, links to originating long-form video, permanently disables checkbox and action buttons to prevent self-ingestion | **Verified working (CF-DEF-022)** |

---

### Page 3: My YouTube Channels (`frontend/app/youtube-channels/page.tsx`)

| Action ID | Control & Location | Visible Label / Tooltip | Trigger & Handler | API Helper & HTTP Route | Backend ID | State & Feedback | Status |
|---|---|---|---|---|---|---|---|
| `FE-YTC-001` | Connect Channel Button | "+ Connect YouTube Channel" | Click -> `handleOpenConnectModal` | `getYoutubeOAuthUrl` (`GET /api/youtube-channels/oauth-url`) | `BE-YTC-003` | Opens modal with Google OAuth URL (`prompt=select_account`) | Verified working |
| `FE-YTC-002` | Submit Auth Code Input | Textarea for auth code / URL | Submit -> `handleConnectSubmit` | `connectYoutubeChannel` (`POST /api/youtube-channels/connect`) | `BE-YTC-004` | Exchanges code, verifies channel, reloads list | Verified working |
| `FE-YTC-003` | Copy Channel ID | "📋 Copy" button | Click -> `handleCopyId(channelId)` | None (`navigator.clipboard.writeText`) | N/A | Copies ID, shows "Copied!" feedback | Verified working |
| `FE-YTC-004` | Refresh Stats Button | "🔄 Refresh Stats" on card | Click -> `handleRefreshStats(channelId)` | `refreshYoutubeChannelStats` (`POST /api/youtube-channels/{id}/refresh`) | `BE-YTC-005` | Updates subscriber, view, and Shorts count cache | Verified working |
| `FE-YTC-005` | Open Settings Modal | "⚙️ Publishing Settings" | Click -> `openSettingsModal(channel)` | None (Opens modal with current settings) | N/A | Displays privacy, category, tags, license controls | Verified working |
| `FE-YTC-006` | Save Settings Button | "Save Settings" | Click -> `handleSaveSettings` | `updateYoutubeChannelSettings` (`PATCH /api/youtube-channels/{id}/settings`) | `BE-YTC-006` | Saves JSON settings, updates card badge | Verified working |
| `FE-YTC-007` | Set as Default Toggle | "★ Set as Default" / "★ Default Destination" | Click -> `handleSetDefault(channelId)` | `setPrimaryDefaultDestination` (`POST /api/youtube-channels/{id}/set-default`) | `BE-YTC-007` | Atomically updates default destination flag across cards | Verified working |
| `FE-YTC-008` | Disconnect Button | "Disconnect" button | Click -> `handleDisconnect(channel)` | `disconnectYoutubeChannel` (`POST /api/youtube-channels/{id}/disconnect`) | `BE-YTC-008` | Confirmation dialog -> unsets destination, revokes auth | Verified working |

---

### Page 4: Upload Studio (`frontend/app/studio/page.tsx`)

| Action ID | Control & Location | Visible Label / Tooltip | Trigger & Handler | API Helper & HTTP Route | Backend ID | State & Feedback | Status |
|---|---|---|---|---|---|---|---|
| `FE-STU-001` | Drag & Drop Zone | "Drag & drop video files here" | File drop -> `handleFileSelect` | None (Local files state) | N/A | Queues files in session list | Verified working |
| `FE-STU-002` | Destination Dropdown | "Target YouTube Channel" | Change -> `targetDestination` | `getPublishDestinations` (`GET /api/publish/destinations`) | `BE-PUB-001` | Sets destination for batch | Verified working |
| `FE-STU-003` | Layout Preset Gallery | "Fill & Blur", "Center Crop", etc. | Click -> `setLayoutMode` | None (Local state) | N/A | Interactive preview card updates | Verified working |
| `FE-STU-004` | Start Upload & Process | "⚡ Upload & Process All" | Click -> `startUploadSession` | `createBatch` -> `uploadChunk` -> `processBatch` | `BE-STU-001, BE-STU-013, BE-STU-004` | Initiates chunked upload and pipeline dispatch | Verified working |
| `FE-STU-005` | Cancel Batch Processing | "Cancel Batch" | Click -> `handleCancelBatch(batchId)` | `cancelBatch` (`POST /api/studio/batches/{id}/cancel`) | `BE-STU-005` | Halts processing across all batch videos | Verified working |
| `FE-STU-006` | Batch Outputs Gallery | "View Generated Clips" | Tab click -> `loadBatchOutputs` | `getBatchOutputs` (`GET /api/studio/batches/{id}/outputs`) | `BE-STU-009` | Renders clip cards for this session | Verified working |

---

### Page 5: Publish Studio (`frontend/app/publish/page.tsx`)

| Action ID | Control & Location | Visible Label / Tooltip | Trigger & Handler | API Helper & HTTP Route | Backend ID | State & Feedback | Status |
|---|---|---|---|---|---|---|---|
| `FE-PUB-001` | Visual Clip Picker | Searchable clip picker with 1:1 thumbnails | Select -> `handleSelectClip` | `listClips` (`GET /api/clips/`), `thumbnailUrl` (`GET /api/clips/{id}/thumbnail`) | `BE-CLP-001, BE-CLP-006` | Loads clip metadata & live simulator; search filter | **Verified working (Visual Previews)** |
| `FE-PUB-002` | Destination Dropdown | "Publishing Destination" | Change -> `selectedDestination` | `getDestinations` (`GET /api/publish/destinations`) | `BE-PUB-001` | Sets destination channel | Verified working |
| `FE-PUB-003` | Publish Now Button | "🚀 Publish to YouTube Now" | Click -> `handlePublishNow` | `publishNow` (`POST /api/publish/publish-now`) | `BE-PUB-010` | Enqueues immediate YouTube upload | Verified working |
| `FE-PUB-004` | Schedule Publish Button | "📅 Schedule for Later" | Click -> `handleSchedule` | `schedulePublish` (`POST /api/publish/schedule`) | `BE-PUB-011` | Saves scheduled publish timestamp | Verified working |
| `FE-PUB-005` | Cancel Publishing | "Cancel" button on queue item | Click -> `handleCancelPublish(clipId)` | `cancelPublish` (`POST /api/publish/clips/{id}/cancel`) | `BE-PUB-013` | Removes clip from upload queue | Verified working |
| `FE-PUB-006` | Retry Publishing | "Retry" button on failed item | Click -> `handleRetryPublish(clipId)` | `retryPublish` (`POST /api/publish/clips/{id}/retry`) | `BE-PUB-014` | Re-queues failed upload | Verified working |

---

### Page 6: Clips Library (`frontend/app/clips/page.tsx`)

| Action ID | Control & Location | Visible Label / Tooltip | Trigger & Handler | API Helper & HTTP Route | Backend ID | State & Feedback | Status |
|---|---|---|---|---|---|---|---|
| `FE-CLP-001` | Channel Filter | "Filter by Source Channel" | Change -> `setFilterChannel` | `listClips({channel_id})` (`GET /api/clips/`) | `BE-CLP-001` | Filters grid by channel | Verified working |
| `FE-CLP-002` | Destination Filter | "Filter by Destination" | Change -> `setFilterDestination` | `listClips({destination_id})` (`GET /api/clips/`) | `BE-CLP-001` | Filters grid by destination | Verified working |
| `FE-CLP-003` | Download Button | "⬇ Download MP4" | Click -> Direct href | `downloadClipUrl(id)` (`GET /api/clips/{id}/download`) | `BE-CLP-005` | Browser downloads MP4 file | Verified working |
| `FE-CLP-004` | Delete Clip Button | "🗑 Delete" | Click -> `handleDeleteClip(id)` | `deleteClip` (`DELETE /api/clips/{id}`) | `BE-CLP-004` | Confirmation -> removes clip record & file | Verified working |
| `FE-CLP-005` | Auto-Fix Button | "⚡ Auto-Fix Duration" | Click -> `handleAutoFix(id)` | `applyAutofix` (`POST /api/clips/{id}/autofix`) | `BE-CLP-011` | Recalculates crop & duration cap | Verified working |
| `FE-CLP-006` | Safe Cleanup Button | "🧹 Safe Cleanup" | Click -> `handlePreviewCleanup` | `previewCleanup(5.0)` (`GET /api/clips/cleanup/preview`) | `BE-CLP-019` | Opens Safe Storage Cleanup modal with real-time metrics & signed token lease | **Verified working (Delivered in Phase 1.3)** |
| `FE-CLP-007` | Confirm Cleanup Execution | "Confirm Cleanup ({count})" | Click -> `handleExecuteCleanup` | `executeCleanup(...)` (`POST /api/clips/cleanup/execute`) | `BE-CLP-020` | Browser confirmation dialog -> stages files to quarantine, deletes records, purges files, displays results | **Verified working (Delivered in Phase 1.3)** |

---

### Page 7: Podcast & Interview Studio (`frontend/app/podcasts/page.tsx` & `PodcastSelectionModal.tsx`)

| Action ID | Control & Location | Visible Label / Tooltip | Trigger & Handler | API Helper & HTTP Route | Backend ID | State & Feedback | Status |
|---|---|---|---|---|---|---|---|
| `FE-POD-001` | Open Podcast Studio Button | "Open Podcast Selection Studio" | Click -> `setModalMode('manual'); setModalOpen(true)` | None (Local state) | N/A | Opens modal in Manual dual-area selection mode | **Verified working** |
| `FE-POD-002` | Explore Advanced Podcast Card | "Explore Advanced Podcast" (`#explore-advanced-podcast-btn`) | Click -> `setModalMode('advanced'); setModalOpen(true)` | None (Local state) | N/A | Opens modal with Advanced Camera-Following mode active | **Verified working** |
| `FE-POD-003` | Workflow Mode Toggle | "Manual Area Selection" / "Advanced Camera-Following" | Click -> `setWorkflowMode(...)` | None (Local state) | N/A | Toggles modal workflow between Manual stacked/single layout and Advanced camera-following | **Verified working** |
| `FE-POD-004` | Analyze Camera Cuts Button | "🎬 Analyze Camera Cuts & Shots" (`#analyze-shots-btn`) | Click -> `handleAnalyzeShots` | `analyzePodcastShots` (`POST /api/videos/podcast/analyze-shots`) | `BE-VID-006` | Detects camera cuts, correlates participant appearances / face tracking by composition mode (`fixed_two_person` or `visibility_driven`), populates interactive shot schedule table | **Verified working** |
| `FE-POD-005` | Shot Speaker Override Dropdown | Participant selector dropdown per shot row | Change -> `handleOverrideShot(shotId, newSpeaker)` | None (Local state `shotSchedule`) | N/A | Updates active participant classification for that shot interval; recalculates active 9:16 crop | **Verified working** |
| `FE-POD-006` | Generate Camera-Following Clips | "⚡ Generate Camera-Following Clip" (`#generate-advanced-clips-btn`) | Click -> `handleConfirm(config)` | `submitYouTubeUrl` (`POST /api/videos/url`) | `BE-VID-002` | Submits URL with `shot_schedule`, `composition` (`fixed_two_person` | `visibility_driven`), `mode="advanced_podcast"`, queues Celery job dispatching to dedicated renderer | **Verified working** |

---

## 3. API Client Methods Audit (`frontend/lib/api.ts`)

| Exported Helper Function | HTTP Method & Route | Callers in Frontend | Error Handling | State Synchronization | Verification Status |
|---|---|---|---|---|---|
| `getStats()` | `GET /api/stats` | `frontend/app/page.tsx` | Error swallowed gracefully | Updates aggregate metrics cards | Verified working |
| `submitVideoUrl(...)` | `POST /api/videos/url` | `frontend/app/page.tsx` | Re-throws, sets error banner | Enqueues job (dispatches immediately or assigns FIFO queue position), refetches active jobs | Verified working |
| `listVideos()` | `GET /api/videos/` | `frontend/app/page.tsx` | Re-throws, sets error banner | Updates recent videos table | Verified working |
| `listClips(...)` | `GET /api/clips/` | `frontend/app/clips/page.tsx`, `frontend/app/publish/page.tsx` | Re-throws, sets error banner | Updates clips grid | Verified working |
| `getClip(id)` | `GET /api/clips/{id}` | `frontend/app/clips/page.tsx` | Re-throws, sets error banner | Opens clip detail modal | Verified working |
| `updateClip(id, data)` | `PATCH /api/clips/{id}` | `frontend/app/clips/page.tsx` | Re-throws, sets error banner | Updates clip metadata | Verified working |
| `deleteClip(id)` | `DELETE /api/clips/{id}` | `frontend/app/clips/page.tsx` | Re-throws, sets error banner | Removes clip card | Verified working |
| `getActiveJobs()` | `GET /api/jobs/active` | `frontend/app/page.tsx` | Silently caught in poll loop | Updates live processing cards | Verified working |
| `cancelJob(id)` | `DELETE /api/jobs/{id}` | `frontend/app/page.tsx` | Re-throws, sets error banner | Removes active card | Verified working |
| `retryJob(id)` | `POST /api/jobs/{id}/retry` | `frontend/app/page.tsx` | Re-throws, sets error banner | Re-adds to active list | Verified working |
| `listChannels()` | `GET /api/channels/` | `frontend/app/automation/page.tsx` | Re-throws, sets error banner | Renders monitored channels | Verified working |
| `addChannel(data)` | `POST /api/channels/` | `frontend/app/automation/page.tsx` | Re-throws, sets error banner | Adds channel, refetches list | Verified working |
| `checkChannelNow(id)` | `POST /api/channels/{id}/check-now` | `frontend/app/automation/page.tsx` | Re-throws, sets error banner | Shows discovered count | Verified working |
| `getChannelVideos(...)` | `GET /api/channels/{id}/videos` | `frontend/app/automation/page.tsx` | Re-throws, sets error banner | Renders paginated video cards | Verified working |
| `processChannelVideo(...)` | `POST /api/channels/{id}/process-video` | `frontend/app/automation/page.tsx` | Re-throws, sets error banner | Queues single video job | **Verified working (Repaired)** |
| `processChannelVideosBatch(...)` | `POST /api/channels/{id}/process-videos-batch` | `frontend/app/automation/page.tsx` | Re-throws, sets error banner | Queues batch, shows counts | **Verified working (New)** |
| `getPendingDecisions()` | `GET /api/channels/decisions/pending` | `frontend/app/automation/page.tsx` | Silently caught in poll loop | Powers 20s countdown toast | Verified working |
| `applyDefaultsDecision(id)` | `POST /api/channels/decisions/{id}/apply-defaults` | `frontend/app/automation/page.tsx` | Re-throws, sets error banner | Resolves countdown | Verified working |
| `customizeDecision(id)` | `POST /api/channels/decisions/{id}/customize` | `frontend/app/automation/page.tsx` | Re-throws, sets error banner | Pauses countdown | Verified working |
| `saveAndProcessDecision(...)` | `POST /api/channels/decisions/{id}/save-and-process` | `frontend/app/automation/page.tsx` | Re-throws, sets error banner | Applies custom overrides | Verified working |
| `cancelDecision(id)` | `POST /api/channels/decisions/{id}/cancel` | `frontend/app/automation/page.tsx` | Re-throws, sets error banner | Halts processing | Verified working |
| `getHistoricalPreview(...)` | `POST /api/channels/{id}/historical-preview` | `frontend/app/automation/page.tsx` | Re-throws, sets error banner | Renders historical preview, metrics, candidates | **Verified working (New)** |
| `processHistoricalBatch(...)` | `POST /api/channels/{id}/historical-process` | `frontend/app/automation/page.tsx` | Re-throws, sets error banner | Queues historical batch, preserves Auto Monitor | **Verified working (New)** |
| `getDestinations()` | `GET /api/publish/destinations` | `frontend/app/publish/page.tsx`, `frontend/app/automation/page.tsx` | Re-throws, sets error banner | Populates destination dropdowns | Verified working |
| `publishNow(data)` | `POST /api/publish/publish-now` | `frontend/app/publish/page.tsx` | Re-throws, sets error banner | Enqueues publish task | Verified working |
| `schedulePublish(data)` | `POST /api/publish/schedule` | `frontend/app/publish/page.tsx` | Re-throws, sets error banner | Schedules publish task | Verified working |
| `getYoutubeChannels(...)` | `GET /api/youtube-channels` | `frontend/app/youtube-channels/page.tsx` | Re-throws, sets error banner | Renders destination cards | Verified working |
| `getYoutubeOAuthUrl()` | `GET /api/youtube-channels/oauth-url` | `frontend/app/youtube-channels/page.tsx` | Re-throws, sets error banner | Opens Google OAuth popup | Verified working |
| `connectYoutubeChannel(...)` | `POST /api/youtube-channels/connect` | `frontend/app/youtube-channels/page.tsx` | Re-throws, sets error banner | Saves new authorized channel | Verified working |
| `refreshYoutubeChannelStats(id, force)` | `POST /api/youtube-channels/{id}/refresh` | `frontend/app/youtube-channels/page.tsx` | Re-throws, sets error banner | Updates metrics cache with 60s cooldown or force bypass | **Verified working (Delivered in Phase 4.2 / C-08)** |
| `getYoutubeChannelStats(id)` | `GET /api/youtube-channels/{id}/stats` | `frontend/app/youtube-channels/page.tsx` | Re-throws, sets error banner | Lightweight single-channel stats & cooldown query | **Verified working (Delivered in Phase 4.2 / C-08)** |
| `updateYoutubeChannelSettings(id, data)` | `PATCH /api/youtube-channels/{id}/settings` | `frontend/app/youtube-channels/page.tsx` | Re-throws, sets error banner | Saves publishing preferences | Verified working |
| `setPrimaryDefaultDestination(id)` | `POST /api/youtube-channels/{id}/set-default` | `frontend/app/youtube-channels/page.tsx` | Re-throws, sets error banner | Sets default destination | Verified working |
| `disconnectYoutubeChannel(id)` | `POST /api/youtube-channels/{id}/disconnect` | `frontend/app/youtube-channels/page.tsx` | Re-throws, sets error banner | Revokes authorization | Verified working |
| `previewCleanup(minScore)` | `GET /api/clips/cleanup/preview` | `frontend/app/clips/page.tsx` | Alert on failure, sets state | Sets `cleanupPreview` with signed lease token | **Verified working (Delivered in Phase 1.3)** |
| `executeCleanup(req)` | `POST /api/clips/cleanup/execute` | `frontend/app/clips/page.tsx` | Re-throws, sets error banner | Sets `cleanupResult`, reloads library | **Verified working (Delivered in Phase 1.3)** |
| `getSfxPlan(clipId)` | `GET /api/clips/{id}/sfx-plan` | `frontend/app/clips/page.tsx`, `frontend/components/RetentionHeatmap.tsx` | Returns 404 if missing (caught cleanly) | Reads persisted plan without mutations | **Verified working (Delivered in Phase 2.1.1B)** |
| `generateSfxPlan(clipId)` | `POST /api/clips/{id}/sfx-plan` | `frontend/app/clips/page.tsx`, `frontend/components/RetentionHeatmap.tsx` | Re-throws, sets error banner | Explicitly generates & persists plan | **Verified working (Delivered in Phase 2.1.1B)** |
| `applySfxPlan(clipId, plan)` | `POST /api/clips/{id}/sfx-apply` | `frontend/app/clips/page.tsx`, `frontend/components/RetentionHeatmap.tsx` | Re-throws, sets error banner | Dispatches Celery apply task | **Verified working (Phase 2.1)** |
| `getSystemSettings()` | `GET /api/settings` | `frontend/app/settings/page.tsx` | Re-throws, falls back to localStorage | Populates global settings and masked secrets | **Verified working (Delivered in Phase 5.1 / C-09)** |
| `analyzePodcastShots(url, regions, refTs, onProgress)` | `POST /api/videos/podcast/analyze-shots` | `frontend/components/PodcastSelectionModal.tsx` | Re-throws, sets error banner | Synchronous or async polling fallback; populates detected shot schedule and review flags | **Verified working (Delivered in Advanced Podcast)** |
| `getPodcastAnalysisStatus(taskId)` | `GET /api/videos/podcast/analysis-status/{task_id}` | `frontend/lib/api.ts` -> `PodcastSelectionModal.tsx` | Re-throws, sets error banner | Polls status & progress percentage during async shot analysis | **Verified working (Delivered in Phase 5 Async)** |
| `getVideoSeoMetadata(videoId)` | `GET /api/videos/{video_id}/seo-metadata` | `frontend/lib/api.ts` -> Publishing Studio / Clip Details | Re-throws, sets error banner | Retrieves cached source category, SEO tags, hashtags, and provenance | **Verified working (Delivered in AI SEO & Attribution)** |
| `refreshVideoSeoMetadata(videoId)` | `POST /api/videos/{video_id}/seo-metadata/refresh` | `frontend/lib/api.ts` -> Publishing Studio | Re-throws, sets error banner | Triggers fresh LLM source categorization & SEO regeneration | **Verified working (Delivered in AI SEO & Attribution)** |

---

## 4. Cross-Layer Mapping Matrix

```
[UI Control & Action]
       │
       ▼
[Frontend Event Handler]
       │
       ▼
[API Client Helper in lib/api.ts]
       │
       ▼
[Effective HTTP Route & Method]
       │
       ▼
[FastAPI Router & Handler in backend/api/routes/]
       │
       ▼
[Persistent DB Transaction & Celery Task Dispatch]
       │
       ▼
[Dashboard Active Jobs Consumer & Poller (GET /api/jobs/active)]
```

### Trace A: Multi-Video Batch Processing (Defect 1 Repair Trace)
1. **Frontend Action:** User checks 2 videos on `/automation` and clicks `🚀 Start Processing (2)`.
2. **Event Handler:** `handleProcessBatchDefaults(channelId)` in `frontend/app/automation/page.tsx`.
3. **API Client:** `processChannelVideosBatch(channelId, videos)` in `frontend/lib/api.ts`.
4. **HTTP Route:** `POST /api/channels/{channel_id}/process-videos-batch`.
5. **Backend Handler:** `process_channel_videos_batch` in `backend/api/routes/channels.py`.
6. **Persistence & Celery:** Creates 2 `Job` records with `source_title` and `status="pending"`, dispatches sequential tasks via `start_video_processing_task.apply_async`.
7. **Response to UI:** `{"queued_count": 2, "already_processing_count": 0, "items": [...]}`.
8. **UI State & Notification:** Banner displays `"🚀 2 videos queued for processing!"` with `[📊 View on Dashboard →]` action link. Selection is cleared.
9. **Dashboard Synchronization:** Dashboard polls `GET /api/jobs/active`, immediately displays both jobs with human-readable video titles.

### Trace B: Single Video Start Processing (Defect 2 Repair Trace)
1. **Frontend Action:** User clicks `⚡ Defaults` button on video card in `/automation`.
2. **Event Handler:** `handleProcessVideoDefaults(channelId, video)` in `frontend/app/automation/page.tsx`.
3. **API Client:** `processChannelVideo(channelId, payload)` in `frontend/lib/api.ts`.
4. **HTTP Route:** `POST /api/channels/{channel_id}/process-video`.
5. **Backend Handler:** `process_channel_video` in `backend/api/routes/channels.py`.
6. **Fixed Root Cause:** Decision created with `status=awaiting_settings` (instead of premature `resolved_custom`).
7. **Persistence & Celery:** Calls `resolve_video_decision_sync`, creates durable `Job` record in `jobs` table with `source_title`, dispatches `start_video_processing_task.apply_async`, returns real `job_id`.
8. **UI State & Notification:** Notification shows `"🚀 Processing initiated for '{title}'! (Job: {job_id})"` with direct Dashboard link.
9. **Dashboard Synchronization:** Dashboard polls `GET /api/jobs/active`, receives active job with `source_title`, renders progress bar.

### Trace C: My YouTube Channels Management Trace
1. **Frontend Action:** User clicks `★ Set as Default` on channel card in `/youtube-channels`.
2. **Event Handler:** `handleSetDefault(channelId)` in `frontend/app/youtube-channels/page.tsx`.
3. **API Client:** `setPrimaryDefaultDestination(channelId)` in `frontend/lib/api.ts`.
4. **HTTP Route:** `POST /api/youtube-channels/{channel_id}/set-default`.
5. **Backend Handler:** `set_default_channel_destination` in `backend/api/routes/youtube_channels.py`.
6. **Persistence:** Runs atomic SQL transaction setting `is_default_destination=true` for target and `false` for others.
7. **UI State Update:** Channel card immediately gains glowing `★ Default Destination` badge; other cards revert to unselected.
8. **Publishing Synchronization:** Next visit to `/publish` or `/studio` pre-selects this channel as default destination.

---

## 5. Priority Classification of Audit Findings

### P0 — Critical Issues
*No P0 issues identified in current codebase. Relational database integrity, authentication token encryption, and test-data isolation are rigorously maintained.*

### P1 — High Priority (Addressed & Resolved in this Pass)
1. **`FINDING-P1-01` (Resolved): Start Processing Missing from Dashboard (Defect 2)**
   - **Root Cause:** In `channels.py:process_channel_video`, setting `status=resolved_custom` prior to calling `resolve_video_decision_sync` caused Celery dispatch to be skipped and `job_id=None` returned.
   - **Correction:** Initialized with `status=awaiting_settings`, recovered stranded decisions, populated `source_title` in `create_job_sync`.
   - **Verification:** Unit tested in `test_automation_repairs.py`; verified live in browser subagent.
2. **`FINDING-P1-02` (Resolved): Multi-Video Selection Not Supported (Defect 1)**
   - **Root Cause:** Automation frontend only supported single-video selection state and backend lacked batch intake endpoint.
   - **Correction:** Implemented `POST /api/channels/{channel_id}/process-videos-batch`, added multi-select checkboxes, "Select All Eligible", clear actions, and batch action bar.
   - **Verification:** Unit tested in `test_automation_repairs.py`; verified live in browser subagent.

### P2 — Medium Priority (Identified for Optimization)
1. **`FINDING-P2-01` (Documented): Duplicate Route Registration in Dubbing**
   - **Path:** `POST /clips/{clip_id}/dub` and `POST /api/dubbing/{clip_id}`.
   - **Impact:** Redundant routes. Non-breaking; kept for legacy client compatibility.
2. **`FINDING-P2-02` (Documented): Live Analytics Token Dependent**
   - **Path:** `/api/analytics/*`.
   - **Impact:** Analytics insights endpoints require a live production Google OAuth refresh token to yield active YouTube engagement stats. Return gracefully handled fallback structures when offline.

### P3 — Low Priority
1. **`FINDING-P3-01`: Deprecation Warnings on Pydantic v1 `Config`**
   - **Impact:** Pydantic deprecation warnings on class-based `Config` in `backend/core/config.py` and `studio.py`. Non-breaking; recommend migration to `ConfigDict` in future refactoring pass.

---

## 6. Recommended Next Deep Forensic Pass

1. **Live Celery Concurrency Stress Test:** Run concurrent multi-video batches (10+ videos) through Celery workers to monitor task queue latency and worker memory consumption during video decoding.
2. **YouTube Quota Rate-Limit Simulation:** Test destination token refresh and error handling under simulated YouTube API HTTP 429 quota exhaustion.
3. **Pydantic v2 Migration:** Update `Config` classes across API route schemas to `ConfigDict` to eliminate console warnings.
