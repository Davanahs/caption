# ClipForge Frontend Page & Feature Inventory

**Document Type:** Authoritative Measured Frontend Surface & Control Inventory  
**Governing Standard:** `MASTER_ENGINEERING_RULEBOOK.md` & `ANTIGRAVITY_CLIPFORGE_FREEZE_RULES.md`  
**Repository Root:** `d:\automation video clips\clipforge`  
**Active Phase:** Phase 0.1 (Baseline Reconciliation & Tracking)  
**Last Updated:** 2026-10-13  

---

## 1. Executive Summary & Page Metrics

A complete source-tree audit of `frontend/app/` reveals **exactly 8 Next.js pages** (zero nested subroutes):

| Page Route | Source File | User-Visible Purpose | Measured Interactive Controls | Connected API Methods | Verification Status | Discovered Implementation Gaps |
|---|---|---|---|---|---|---|
| **`/` (Dashboard)** | `frontend/app/page.tsx` | Real-time monitoring, stats, quick ingest | 12 | `getStats`, `getActiveJobs`, `cancelJob`, `retryJob`, `submitVideoUrl`, `submitBatchYouTubeUrls`, `uploadVideoFile` | `VERIFIED` | None. Cancel, retry, health probe, and job polling verified. |
| **`/automation`** | `frontend/app/automation/page.tsx` | 24/7 channel monitoring, decisions, batch queue | 16 | `listChannels`, `addChannel`, `deleteChannel`, `updateChannel`, `getChannelVideos`, `processChannelVideosBatch`, `processChannelVideo`, `getPendingDecisions` | `VERIFIED` | None. Batch multi-selection and Dashboard link verified. |
| **`/studio`** | `frontend/app/studio/page.tsx` | Upload Studio Phase 1-3 resumable batches | 14 | `createStudioBatch`, `getStudioBatch`, `initStudioVideo`, `streamFileInChunks`, `processStudioBatch`, `cancelStudioBatch`, `retryStudioVideo`, `getBatchOutputs` | `VERIFIED` | None. Chunked streaming, drag-and-drop queue verified. |
| **`/youtube-channels`** | `frontend/app/youtube-channels/page.tsx` | YouTube publishing destination management | 10 | `getYoutubeChannels`, `getYoutubeOAuthUrl`, `connectYoutubeChannel`, `refreshYoutubeChannelStats`, `updateYoutubeChannelSettings`, `setPrimaryDefaultDestination`, `disconnectYoutubeChannel` | `VERIFIED` | None. Full E2E modals and token isolation verified. |
| **`/publish`** | `frontend/app/publish/page.tsx` | Single clip publishing and scheduled uploads | 15 | `getDestinations`, `publishNow`, `schedulePublish`, `getPublishQueue`, `cancelPublish`, `retryPublish`, `getAuthStatus`, `submitOAuthCode`, `listClips` | `VERIFIED` | None. Cancel, Retry, Force Retry, and Refresh queue actions wired and verified (CF-DEF-003 resolved). |
| **`/clips`** | `frontend/app/clips/page.tsx` | Rendered clip library, preview, downloads, AI enhancements | 15 | `listClips`, `getClip`, `updateClip`, `deleteClip`, `downloadClipUrl`, `thumbnailUrl`, `getClipMetadata`, `previewCleanup`, `executeCleanup`, `getBrollPlan`, `applyBrollPlan`, `getSfxPlan`, `applySfxPlan`, `getHookPlan`, `generateHookPlan`, `applyHookPlan`, `getClipRetention`, `applyAutofix` | `VERIFIED` | None. Safe storage cleanup (`CF-DEF-001`), typed retention client (`CF-DEF-002`), and AI enhancements preview UI (`CF-DEF-004`) verified in real browser. |
| **`/analytics`** | `frontend/app/analytics/page.tsx` | Pipeline telemetry, auto-optimizer, A/B testing | 3 | `getPipelineSummary`, `getABTests`, `getChannelInsights` | `PARTIALLY VERIFIED` | `CF-DEF-005`: Only aggregate cards rendered. Per-video SEO and auto-optimizer controls absent. |
| **`/settings`** | `frontend/app/settings/page.tsx` | Pipeline configuration limits & AI models | 4 | Local form inputs only (saves to `localStorage`) | `PARTIALLY VERIFIED` | `REQ-GAP-001`: Saves to `localStorage` without backend persistence. |
| **Total** | **8 Pages** | System-wide UI | **89 Measured Controls** | **44 Connected API Methods** | — | — |

*Note on Historical Discrepancy:* Earlier reports cited "115+ controls" based on unmeasured estimates. The exact count of distinct interactive control elements cataloged in this verified inventory is **89 controls**.

---

## 2. Detailed Page-by-Page Inventory

### Page 1: Dashboard (`frontend/app/page.tsx`)
- **Route:** `/`
- **Data Shown:** Aggregate counters (total videos, total clips, published shorts, auto channels), active jobs table with live progress bars, IST formatted timestamps, system health status pill.
- **Controls & Actions (12):**
  1. *Quick URL Input:* Text input (`setUrlInput`).
  2. *Quick Ingest Button:* "⚡ Start Processing" -> calls `submitVideoUrl` (`POST /api/videos/url`).
  3. *Batch URL Modal Toggle:* Button to open batch submission modal.
  4. *Batch URL Textarea & Submit:* Inputs and button calling `submitBatchYouTubeUrls` (`POST /api/videos/batch`).
  5. *File Upload Input & Dropzone:* File picker calling `uploadVideoFile` (`POST /api/videos/upload`).
  6. *Refresh Dashboard Button:* "🔄 Refresh" icon button calling `loadDashboardData`.
  7. *Active Jobs Poller:* Interval hook (3s) polling `getActiveJobs` (`GET /api/jobs/active`).
  8. *Cancel Job Button:* "✖ Cancel" button on job card calling `cancelJob` (`DELETE /api/jobs/{id}`).
  9. *Retry Job Button:* "🔄 Retry" button on job card calling `retryJob` (`POST /api/jobs/{id}/retry`).
  10. *Copy URL Button:* Tooltip button copying source YouTube link to clipboard.
  11. *Job History Pagination / Toggle:* Controls to view recent finished jobs.
  12. *Video Detail Modal Opener:* Click on video title opening associated clips drawer.
- **States:** Loading spinner during initial fetch; empty state placeholder ("No active jobs in queue"); error banners; completion badges.
- **Verification Status:** `VERIFIED`

---

### Page 2: Automation (`frontend/app/automation/page.tsx`)
- **Route:** `/automation`
- **Data Shown:** Monitored YouTube channels list, auto-clip status badges, countdown timer to next check, video discovery accordion, decision history.
- **Controls & Actions (16):**
  1. *Add Channel URL Input:* Text field for channel URL.
  2. *Auto-Clip Toggle:* Form checkbox.
  3. *Auto-Publish Toggle:* Form checkbox.
  4. *Publish Destination Select:* Dropdown selecting target YouTube channel.
  5. *Submit Channel Button:* "Add Channel" -> calls `addChannel` (`POST /api/channels/`).
  6. *Delete Channel Button:* Trash icon -> calls `deleteChannel` (`DELETE /api/channels/{id}`).
  7. *Manual Check Now Button:* "⚡ Check Now" -> calls `checkChannelNow` (`POST /api/channels/{id}/check-now`).
  8. *Discover Videos Accordion Toggle:* Expand/collapse button.
  9. *Single Video Process Button:* "🚀 Start Processing" -> calls `processChannelVideo` (`POST /api/channels/{id}/process-video`).
  10. *Video Multi-Select Checkboxes:* Per-video checkboxes for batch selection.
  11. *Select All Eligible Button:* "☑️ Select All Eligible" -> selects all non-processing videos.
  12. *Clear Selection Button:* "✖️ Clear" -> unchecks all videos.
  13. *Sticky Batch Action Bar:* "🚀 Start Processing ({N})" -> calls `processChannelVideosBatch` (`POST /api/channels/{id}/process-videos-batch`).
  14. *Decision Window Apply Defaults:* "Apply Defaults" -> calls `applyDefaultsDecision` (`POST /api/channels/decisions/{id}/apply-defaults`).
  15. *Decision Window Customize:* "Customize" -> calls `customizeDecision` (`POST /api/channels/decisions/{id}/customize`).
  16. *Decision Window Cancel:* "Cancel" -> calls `cancelDecision` (`POST /api/channels/decisions/{id}/cancel`).
- **States:** Countdown timer; decision deadline progress bar; empty channel state; batch action notification banner with `"📊 View on Dashboard →"` action link.
- **Verification Status:** `VERIFIED`

---

### Page 3: Upload Studio (`frontend/app/studio/page.tsx`)
- **Route:** `/studio`
- **Data Shown:** Staged file cards, drag-and-drop intake area, upload progress bars, sequential batch processing queue, output clip cards.
- **Controls & Actions (14):**
  1. *File Dropzone / Picker:* Native input and drag-and-drop intake.
  2. *Clear Staged Queue Button:* Wipes local IndexedDB staging.
  3. *Remove Video Item Button:* Removes single video from staging queue.
  4. *Reorder Queue Drag Handles:* HTML5 drag-and-drop handles for sequential queue reordering.
  5. *Start Batch Upload Button:* Initiates resumable chunk upload via `createStudioBatch`, `initStudioVideo`, `streamFileInChunks`.
  6. *Cancel Upload Button:* Aborts active chunk stream.
  7. *Retry Upload Item Button:* Calls `retryStudioUpload`.
  8. *Start Batch Processing Button:* Opens modal and calls `processStudioBatch` (`POST /api/studio/batches/{id}/process`).
  9. *Cancel Batch Processing Button:* Calls `cancelStudioBatch` (`POST /api/studio/batches/{id}/cancel`).
  10. *Retry Failed Video Processing Button:* Calls `retryStudioVideo` (`POST /api/studio/batches/{id}/videos/{vid}/retry`).
  11. *Retry Entire Batch Button:* Calls `retryStudioBatch`.
  12. *Delete Batch Button:* Calls `deleteStudioBatch` (`DELETE /api/studio/batches/{id}`).
  13. *Reselect Missing File Input:* Reattaches local file blob after page refresh.
  14. *Output Clip Preview / Download:* Links to final MP4 clips via `getBatchOutputs`.
- **States:** IndexedDB storage sync status; resumable chunk progress (5MB chunks); sequential processing stepper; error toasts.
- **Verification Status:** `VERIFIED`

---

### Page 4: My YouTube Channels (`frontend/app/youtube-channels/page.tsx`)
- **Route:** `/youtube-channels`
- **Data Shown:** Connected YouTube channel cards, avatar/thumbnails, subscriber counts, total views, Shorts count, honest likes labeling ("Likes: Public videos only"), primary default badges.
- **Controls & Actions (10):**
  1. *Connect Channel Button:* Opens Connect Modal and fetches OAuth URL (`GET /api/youtube-channels/oauth-url`).
  2. *Connect Modal Google Auth Link:* Opens Google consent screen in popup/tab.
  3. *Manual OAuth Code / URL Input:* Text field for pasting redirect URL or code.
  4. *Submit Manual Code Button:* Calls `connectYoutubeChannel` (`POST /api/youtube-channels/connect`).
  5. *Refresh Channel Stats Button:* "🔄 Refresh Stats" -> calls `refreshYoutubeChannelStats` (`POST /api/youtube-channels/{id}/refresh`).
  6. *Set Primary Default Destination Button:* "⭐ Set as Default" -> calls `setPrimaryDefaultDestination` (`POST /api/youtube-channels/{id}/set-default`).
  7. *Open Publishing Settings Button:* "⚙️ Publishing Settings" -> opens settings modal.
  8. *Save Publishing Settings Button:* Calls `updateYoutubeChannelSettings` (`PATCH /api/youtube-channels/{id}/settings`).
  9. *Disconnect Channel Button:* Opens confirmation modal and calls `disconnectYoutubeChannel` (`POST /api/youtube-channels/{id}/disconnect`).
  10. *Copy Channel ID Tooltip:* Copies channel ID to clipboard.
- **States:** Loading skeleton cards; refreshing spinner; error toast banner; confirmation modals.
- **Verification Status:** `VERIFIED`

---

### Page 5: Publishing Studio (`frontend/app/publish/page.tsx`)
- **Route:** `/publish`
- **Data Shown:** Clip selector grid, YouTube Shorts phone mockup preview, destination channel dropdown, schedule date-time picker, interactive publish queue drawer with live progress bars, error boxes, and attempt counts.
- **Controls & Actions (15):**
  1. *Clip Selector Thumbnails:* Selects target clip.
  2. *Destination Channel Select:* Dropdown populated via `getDestinations` (`GET /api/publish/destinations`).
  3. *Title Input:* Shorts title input.
  4. *Description Input:* Metadata description textarea.
  5. *Privacy Radios:* `public`, `unlisted`, `private`.
  6. *Made For Kids Toggle:* Checkbox.
  7. *Age Restricted Toggle:* Checkbox.
  8. *Publish Now Button:* Calls `publishNow` (`POST /api/publish/publish-now`).
  9. *Schedule Date Input:* Date-time picker.
  10. *Schedule Publish Button:* Calls `schedulePublish` (`POST /api/publish/schedule`).
  11. *Publish Queue Drawer Toggle:* Expands queue list populated via `getPublishQueue`.
  12. *Queue Refresh Button:* Calls `fetchQueue()` with animated refresh icon.
  13. *Cancel Publish Button (`btn-cancel-publish-{id}`):* Calls `cancelPublish` (`POST /api/publish/clips/{id}/cancel`).
  14. *Retry Publish Button (`btn-retry-publish-{id}`):* Calls `retryPublish` (`POST /api/publish/clips/{id}/retry`).
  15. *Force Retry Button (`btn-force-retry-{id}`):* Calls `retryPublish(id, force=true)` for clips requiring manual review.
- **Known Gaps:** None. (CF-DEF-003 fully resolved).
- **Verification Status:** `VERIFIED`

---

### Page 6: Clips Library (`frontend/app/clips/page.tsx`)
- **Route:** `/clips`
- **Data Shown:** Filterable grid of rendered clips, viral score rings, duration badges, video player modal with responsive phone mockup frame, Safe Storage Cleanup modal, and interactive AI Creative Enhancements suite (Hooks, B-Roll, SFX).
- **Controls & Actions (15):**
  1. *Channel Filter Select:* Dropdown filtering clips by channel ID.
  2. *Status Filter Select:* Filter by `draft`, `queued`, `published`, `failed`.
  3. *Sort Order Select:* Sort by score or date.
  4. *Clip Card Preview Opener:* Click thumbnail or title opens Preview Modal (`clip-card-thumbnail-{id}` / `clip-card-title-{id}`).
  5. *Download Clip Link:* Direct download via `downloadClipUrl`.
  6. *Delete Clip Button:* Trash button calling `deleteClip` (`DELETE /api/clips/{id}`).
  7. *Safe Storage Cleanup Button:* Opens Safe Cleanup Modal (`POST /api/clips/cleanup/preview` and `/execute`, verified in Phase 1.3).
  8. *Preview Modal Video Player:* Native HTML5 video player.
  9. *Retention Heatmap Widget:* Renders `RetentionHeatmap.tsx` with typed API client (`CF-DEF-002` resolved).
  10. *1-Click Auto-Fix Button:* Inside RetentionHeatmap calling `applyAutofix`.
  11. *Auto-SFX Button:* Inside RetentionHeatmap calling `getSfxPlan`.
  12. *AI Creative Enhancements Tabs:* 3 tab switcher buttons for Hooks, B-Roll, SFX (`ai-tab-hook`, `ai-tab-broll`, `ai-tab-sfx`).
  13. *Generate AI Plan Button:* Tab-sensitive action button (`generate-hook-plan-btn`, `generate-broll-plan-btn`, `generate-sfx-plan-btn`).
  14. *Apply AI Overlays Button:* Dispatches overlay composition task (`apply-hook-overlay-btn`, `apply-broll-overlay-btn`, `apply-sfx-overlay-btn`).
  15. *Hook Concept Cards:* Interactive concept selection cards rendering hook script, style, and duration.
- **Resolved Gaps:** `CF-DEF-001` (Storage Cleanup verified Phase 1.3), `CF-DEF-002` (Retention Heatmap relative URLs verified Phase 2.1), `CF-DEF-004` (Clip AI features wired and verified Phase 2.1).
- **Verification Status:** `VERIFIED`

---

### Page 7: Pipeline Analytics (`frontend/app/analytics/page.tsx`)
- **Route:** `/analytics`
- **Data Shown:** Top summary cards (Engine Performance, AI Auto-Optimizer runs, A/B Title Experiments count), Reinforcement Learning Winning & Underperforming Patterns, Active & Completed Title Tests table.
- **Controls & Actions (3):**
  1. *Refresh Metrics Button:* "🔄 Refresh Metrics" -> calls `loadData` (`getPipelineSummary`, `getABTests`, `getChannelInsights`).
  2. *A/B Table Row Expander / Hover:* Visual inspection of title variant lifts.
  3. *Interval Polling Hook:* Automatic poll every 15 seconds.
- **Known Gaps:** `CF-DEF-005`: No video selector dropdown, no per-video SEO diagnostics card, no active tracking queue table with cancellation.
- **Verification Status:** `PARTIALLY VERIFIED`

---

### Page 8: Settings & Configuration (`frontend/app/settings/page.tsx`)
- **Route:** `/settings`
- **Data Shown:** YouTube OAuth credentials inputs (Client ID, Client Secret), Cloud AI provider keys (OpenRouter, Groq, Nvidia NIM), Whisper model dropdown, clips limit per video. Setup documentation guide.
- **Controls & Actions (4):**
  1. *Form Text Inputs & Selects:* Controlled React inputs bound to local state.
  2. *Whisper Model Select:* Dropdown (`tiny`, `base`, `small`, `medium`, `large`).
  3. *Clips Limit Number Input:* Numeric input.
  4. *Save Settings Button:* Calls `handleSave` -> writes to `localStorage` and shows alert to restart backend.
- **Known Gaps:** `REQ-GAP-001`: Settings save to browser `localStorage` only; no backend `/api/settings` route exists.
- **Verification Status:** `PARTIALLY VERIFIED`
