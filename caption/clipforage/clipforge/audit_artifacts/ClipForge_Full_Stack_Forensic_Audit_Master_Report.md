# ClipForge — Reconciled Full-Stack Forensic Audit Master Report

**Date of Reconciliation:** 2026-10-26  
**Auditor:** Antigravity Autonomous Coding Agent  
**Audit Target:** ClipForge Application (`d:\automation video clips\clipforge`)  
**Scope:** 8 Pages, 38 Components, 123 Registered Backend Endpoints, Celery Distributed Task Pipeline, Live Multi-Container Stack  
**Reconciliation Status:** **AUTHORITATIVELY RECONCILED AGAINST CODEBASE & RUNTIME EVIDENCE**

---

## 1. Executive Summary & Verification Classification

A complete forensic reconciliation of audit claims against actual codebase contracts, registered routes, test collections, and live container state has been executed.

### Authoritative System Totals
- **Total Registered Backend Endpoints (HTTP + WS):** **123 endpoints** (122 HTTP routes + 1 WebSocket endpoint).
  - **Level 4 (Probed live HTTP in running stack):** 23 endpoints (all primary GET read routes).
  - **Level 3 (Covered by automated pytest suites with mocks/fixtures):** 49 endpoints (mutation, scheduling, and processing pipelines).
  - **Level 2 (Referenced by frontend API client):** 4 endpoints.
  - **Level 1 (Registered in source / OpenAPI schema / static mounts):** 44 endpoints.
  - **Level 6 (Unverified / Live external Google OAuth code exchange):** 3 endpoints.
  - **Level 5 (Complete manual browser E2E workflow):** 0 in this automated session.
- **Total Unique Test Files in Repository (`backend/tests/`):** **39 test files**.
- **Total Unique Test Items Collected (`pytest --collect-only`):** **386 test items**.
- **Tests Executed in Current Session:** **311 unique tests executed across 30 test modules (311 passed, 0 failed)**.
  - *Reconciliation of Discrepancy:* The prior report claimed "324 passed / 23 suites" while its row table summed to 311 across 29 modules. The discrepancy arose from double-counting `test_equal_splits.py` (13 tests) which was run twice (311 + 13 = 324), and omitting 10 unexecuted test modules from the total suite count.
- **Frontend Health:** Next.js dev server running live on `http://localhost:3000` (HTTP 200). TypeScript compilation (`npx tsc --noEmit`) clean with zero errors. Production build (`npm run build`) generates all 8 static routes clean.
- **Docker Stack Health:** 6/6 containers online and healthy (`clipforge_backend`, `clipforge_worker`, `clipforge_beat`, `clipforge_flower`, `clipforge_postgres`, `clipforge_redis`).
- **Celery Distributed Tasks:** 31 background worker tasks active and registered.

---

## 2. Reconciled Page-by-Page Endpoint & Control Inventory

### Page 1: Dashboard (`/`)
- **Route:** `http://localhost:3000/` | **Frontend:** `frontend/app/page.tsx`
- **Interactive Controls:** 46 controls (`CTRL-DASH-001` to `046`) verified in source.
- **Actual Backend Routes:**
  - `GET /api/stats` (`getStats` -> metrics cards) — *Level 4 Probed Live*
  - `GET /api/jobs/active` (`getActiveJobs` -> active queue) — *Level 4 Probed Live*
  - `GET /api/jobs/history` (`getJobHistory` -> terminal queue) — *Level 4 Probed Live*
  - `GET /api/jobs/stats` (`getQueueStats` -> queue health summary) — *Level 4 Probed Live*
  - `POST /api/videos/url` (`submitYouTubeUrl` -> Start Clipping) — *Level 3 Tested* (*Corrected from misnamed `POST /api/process`*)
  - `DELETE /api/jobs/{id}` (`cancelJob` -> Cancel button) — *Level 3 Tested* (*Corrected from misnamed `POST /api/jobs/{id}/cancel`*)
  - `POST /api/jobs/{id}/retry` (`retryJob` -> Retry button) — *Level 3 Tested*
  - `WS /api/jobs/ws/{job_id}` (`new WebSocket` -> progress updates) — *Level 3 Tested* (*Corrected from misnamed `WS /ws/progress`*)
- **Tests Executed:** 33 tests across 4 modules passed (including `test_layout_engine.py` and `test_equal_splits.py`).

### Page 2: Automation & Channel Monitoring (`/automation`)
- **Route:** `http://localhost:3000/automation` | **Frontend:** `frontend/app/automation/page.tsx`
- **Interactive Controls:** 40 controls (`CTRL-AUTO-001` to `040`) across 6 components.
- **Actual Backend Routes:**
  - `GET /api/channels/` (`getChannels`) — *Level 4 Probed Live*
  - `POST /api/channels/` (`createChannel`) — *Level 3 Tested*
  - `POST /api/channels/{id}/check-now` (`syncChannelNow`) — *Level 3 Tested*
  - `GET /api/channels/decisions/pending` (`getPendingDecisions`) — *Level 4 Probed Live*
  - `POST /api/channels/decisions/{id}/approve` (`approveDecision`) — *Level 3 Tested*
  - `POST /api/channels/decisions/{id}/reject` (`rejectDecision`) — *Level 3 Tested*
  - `PUT /api/channels/decisions/{id}/customize` (`customizeDecision`) — *Level 3 Tested*
  - `GET /api/channels/decisions/history` (`getDecisionHistory`) — *Level 4 Probed Live*
- **Tests Executed:** 48 tests across 4 modules passed.

### Page 3: Upload Studio (`/studio`)
- **Route:** `http://localhost:3000/studio` | **Frontend:** `frontend/app/studio/page.tsx`
- **Interactive Controls:** 22 controls (`CTRL-STUDIO-001` to `022`).
- **Actual Backend Routes:**
  - `POST /api/studio/batches` (`createBatch`) — *Level 3 Tested*
  - `GET /api/studio/batches/{id}` (`getBatch`) — *Level 3 Tested*
  - `POST /api/studio/batches/{id}/videos/init` (`initVideoItem`) — *Level 3 Tested*
  - `PUT /api/studio/uploads/{id}/chunk` (`uploadChunk`) — *Level 3 Tested*
  - `POST /api/studio/batches/{id}/process` (`processBatch`) — *Level 3 Tested*
  - `POST /api/studio/batches/{id}/recover` (`recoverStaleBatch`) — *Level 3 Tested*
- **Tests Executed:** 52 tests across 4 modules passed.

### Page 4: My YouTube Channels (`/youtube-channels`)
- **Route:** `http://localhost:3000/youtube-channels` | **Frontend:** `frontend/app/youtube-channels/page.tsx`
- **Interactive Controls:** 25 controls (`CTRL-YT-001` to `025`).
- **Actual Backend Routes:**
  - `GET /api/youtube-channels/` (`listChannels`) — *Level 4 Probed Live*
  - `GET /api/youtube-channels/oauth-url` (`getOAuthUrl`) — *Level 4 Probed Live*
  - `POST /api/youtube-channels/connect` (`connectChannel`) — *Level 6 Unverified Live*
  - `PATCH /api/youtube-channels/{id}/settings` (`updateSettings`) — *Level 3 Tested*
  - `POST /api/youtube-channels/{id}/disconnect` (`disconnectChannel`) — *Level 3 Tested*
- **Tests Executed:** 25 tests across 3 modules passed.

### Page 5: Publish Queue (`/publish`)
- **Route:** `http://localhost:3000/publish` | **Frontend:** `frontend/app/publish/page.tsx`
- **Interactive Controls:** 35 controls (`CTRL-PUB-001` to `035`).
- **Actual Backend Routes:**
  - `GET /api/publish/destinations` (`getDestinations`) — *Level 4 Probed Live*
  - `GET /api/publish/queue` (`getPublishQueue`) — *Level 4 Probed Live*
  - `GET /api/publish/auth-status` (`getAuthStatus`) — *Level 4 Probed Live*
  - `POST /api/publish/publish-now` (`publishNow`) — *Level 3 Tested*
  - `POST /api/publish/schedule` (`schedulePublish`) — *Level 3 Tested*
  - `POST /api/publish/clips/{id}/retry` (`retryPublishClip`) — *Level 3 Tested*
- **Tests Executed:** 49 tests across 5 modules passed.

### Page 6: Clips Library (`/clips`)
- **Route:** `http://localhost:3000/clips` | **Frontend:** `frontend/app/clips/page.tsx`
- **Interactive Controls:** 52 controls (`CTRL-CLIP-001` to `052`).
- **Actual Backend Routes:**
  - `GET /api/clips/` (`listClips`) — *Level 4 Probed Live*
  - `GET /api/clips/{id}` (`getClip`) — *Level 3 Tested*
  - `POST /api/clips/{id}/autofix` (`applyAutofix`) — *Level 3 Tested*
  - `POST /api/clips/{id}/broll-apply` (`applyBroll`) — *Level 3 Tested*
  - `POST /api/clips/{id}/hook/apply` (`applyHookPlan`) — *Level 3 Tested*
  - `POST /api/clips/{id}/sfx-apply` (`applySfx`) — *Level 3 Tested*
  - `GET /api/dubbing/languages` (`getDubbingLanguages`) — *Level 4 Probed Live*
  - `POST /api/dubbing/{id}` (`triggerDubbing`) — *Level 3 Tested*
  - `DELETE /api/clips/{id}` (`deleteClip`) — *Level 3 Tested*
  - `GET /api/clips/cleanup/preview` (`previewCleanup`) — *Level 4 Probed Live*
- **Tests Executed:** 68 tests across 6 modules passed.

### Page 7: Analytics (`/analytics`)
- **Route:** `http://localhost:3000/analytics` | **Frontend:** `frontend/app/analytics/page.tsx`
- **Interactive Controls:** 12 controls (`ANA-01` to `04`).
- **Actual Backend Routes:**
  - `GET /api/analytics/summary` (`getAnalyticsSummary`) — *Level 4 Probed Live*
  - `GET /api/analytics/ab-tests` (`getABTests`) — *Level 4 Probed Live*
  - `GET /api/analytics/insights` (`getInsights`) — *Level 4 Probed Live*
  - `GET /api/analytics/active` (`getActiveTrackers`) — *Level 4 Probed Live*
  - `POST /api/analytics/cancel/{task_id}` (`cancelTracker`) — *Level 3 Tested*
- **Tests Executed:** 21 tests across 3 modules passed.

### Page 8: Settings (`/settings`)
- **Route:** `http://localhost:3000/settings` | **Frontend:** `frontend/app/settings/page.tsx`
- **Interactive Controls:** 15 controls (`SET-01` to `04`).
- **Actual Backend Routes:**
  - `GET /api/settings` (`getSettings`) — *Level 4 Probed Live*
  - `PUT /api/settings` (`updateSettings`) — *Level 3 Tested*
- **Tests Executed:** 15 tests across 1 module passed.

---

## 3. Reconciled Test Execution Ledger

| Command # | Focus Area / Target Modules | Collected | Passed | Failed | Status |
|---|---|---|---|---|---|
| **CMD 1** | Dashboard (Cancellation, State Queue, Equal Splits, Layout) | 33 | 33 | 0 | PASS |
| **CMD 2** | Automation (Race Guard, Polling, Lifecycle, Selection) | 48 | 48 | 0 | PASS |
| **CMD 3** | Upload Studio (Migration, Runtime, Processing, Publishing) | 52 | 52 | 0 | PASS |
| **CMD 4** | YouTube Channels (Management, Governance, Reconciliation) | 25 | 25 | 0 | PASS |
| **CMD 5** | Publish Queue (Actions, Metadata, Multi-Dest, Concurrency, Repair) | 49 | 49 | 0 | PASS |
| **CMD 6** | Clips Library (AI Enhancements, B-Roll, Hooks, Dubbing, Cleanup, Cascade) | 68 | 68 | 0 | PASS |
| **CMD 7** | Analytics (Video Analytics, Tracker, Optimizer) | 21 | 21 | 0 | PASS |
| **CMD 8** | Settings (Backend Persistence, Secret Masking, Runtime Sync) | 15 | 15 | 0 | PASS |
| **TOTAL** | **Session Test Runs (Unique Test Cases Executed)** | **311** | **311** | **0** | **PASS** |

*Note on Double Counting:* An auxiliary execution of `test_equal_splits.py` (13 tests) produced a combined tally of 324 runs in the previous un-reconciled report. The authoritative count of **unique test cases executed** is **311**.

---

## 4. Reconciled External Services & Enhancement Truth

1. **Pexels Video B-Roll Integration:**
   - **Configuration:** `PEXELS_API_KEY` is present in `.env` and loaded by `backend.core.config.Settings`. `PexelsService.is_configured()` returns `True`.
   - **Verification Reality:** The automated test suite (`test_ai_enhancements_repair.py`) verified `PexelsService` search parsing, attribution extraction, 24h caching, and HTTP 401/429 handling using **unit test mocks** (`patch("urllib.request.urlopen")`). **Live network requests to the external Pexels API were NOT performed** in this test pass.
2. **YouTube Video Publishing:**
   - **Verification Reality:** Publishing test suites (`test_upload_studio_phase3_publishing.py`, `test_multi_destination_publishing.py`, `test_publish_concurrency.py`) ran with `is_test = True` and mocked API responses. **Zero live videos were published to YouTube** during this audit session. The historical YouTube record `YTjZ7CPCkP8` is preserved as read-only historical verification data.
3. **Equal Split Timeline Coverage:**
   - Mathematical formula $N = \lceil D / L \rceil$ verified against duration test fixtures. Trailing micro-segments are absorbed.
4. **Captions & Watermarks:**
   - ASS/SRT caption burn-in remains removed from all active rendering code.
   - Phase 8 watermark branding remains deferred under DEC-007.
