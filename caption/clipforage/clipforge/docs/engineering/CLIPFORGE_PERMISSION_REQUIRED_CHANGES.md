# CLIPFORGE — PERMISSION-REQUIRED CHANGES & PROPOSALS REGISTER

**Document Type:** Formal Engineering Permission Requests & Architectural Proposal Register  
**Project:** ClipForge (`d:\automation video clips\clipforge`)  
**Active Branch / HEAD:** `feature/layout` (`68b9bcd7d3688c6bd8feb781d98df72d14351e97`)  
**Authority Reference:** Section 17, Category M3 of Master Audit Specification  
**Execution Methodology:** Gravitas

---

## 1. Governance & Protocol

In strict accordance with Section 17 (Category M3), no changes involving architectural redesigns, multi-component layout adjustments, API contract modifications, database schema migrations, background worker changes, or continuous participant tracking are executed autonomously.

This document formally records all discovered issues requiring explicit user authorization, detailing:
- The underlying problem and root cause.
- Technical and user impact.
- Proposed engineering implementation.
- Specific files and dependencies affected.
- Testing, rollback, and verification strategy.
- Risk assessment.

---

## 2. Permission-Required Proposals

### PROPOSAL #1: Responsive Horizontal Overflow Normalization across Mobile & Tablet [IMPLEMENTED & VERIFIED]

- **Issue ID:** `ISSUE-02`
- **Severity:** P3 (Layout / Responsive Usability)
- **Status:** **`APPROVED & IMPLEMENTED UNDER MICRO-FIX #2 AUTHORITY`**
- **Affected Routes:**
  1. `/publish` (Publish Queue): Tablet 768px ($304\text{px}$ overflow) & Mobile 390px ($682\text{px}$ overflow); 320px ($752\text{px}$ overflow)
  2. `/youtube-channels` (Connected Channels): Mobile 390px ($186\text{px}$ overflow); 320px ($256\text{px}$ overflow)
  3. `/analytics` (Analytics Dashboard): Mobile 390px ($142\text{px}$ overflow); 320px ($212\text{px}$ overflow)
  4. `/podcasts` (Podcasts Studio): Mobile 390px ($61\text{px}$ overflow); 320px ($131\text{px}$ overflow)
  5. `/automation` (Automation Decisions): Mobile 390px ($3\text{px}$ overflow); 320px ($73\text{px}$ overflow)
- **Root Cause:**
  Desktop-first CSS grid templates (`grid-template-columns: repeat(...)`) and fixed `min-width` inputs lacked fluid clamping (`min(100%, Xpx)`), toolbar flex wrapping, and horizontal scroll wrappers (`overflow-x: auto`).
- **Implemented Remediation:**
  1. Added `.table-responsive-wrapper { width: 100%; max-width: 100%; overflow-x: auto; -webkit-overflow-scrolling: touch; }` to `frontend/app/globals.css`.
  2. Wrapped wide data tables in `/analytics`, `/automation`, and `/publish` within `.table-responsive-wrapper`.
  3. Replaced rigid minmax constraints with fluid constraints (`min(100%, 480px)`).
  4. Added `flexWrap: 'wrap'` to headers and action rows.
  5. Constrained select dropdowns with `minWidth: 0, width: '100%', maxWidth: '100%'`.
- **Target Files:**
  - [`frontend/app/globals.css`](file:///d:/automation%20video%20clips/clipforge/frontend/app/globals.css)
  - [`frontend/app/publish/page.tsx`](file:///d:/automation%20video%20clips/clipforge/frontend/app/publish/page.tsx)
  - [`frontend/app/youtube-channels/page.tsx`](file:///d:/automation%20video%20clips/clipforge/frontend/app/youtube-channels/page.tsx)
  - [`frontend/app/analytics/page.tsx`](file:///d:/automation%20video%20clips/clipforge/frontend/app/analytics/page.tsx)
  - [`frontend/app/podcasts/page.tsx`](file:///d:/automation%20video%20clips/clipforge/frontend/app/podcasts/page.tsx)
  - [`frontend/app/automation/page.tsx`](file:///d:/automation%20video%20clips/clipforge/frontend/app/automation/page.tsx)
- **Verification Evidence:**
  - Automated Playwright audit across 5 routes × 5 viewports (1920×1080, 1366×768, 768×1024, 390×844, 320×568): **25/25 runs verified with 0px horizontal page overflow (100% PASS)**.
  - Full suite `npm test`: **112/112 tests passed**.
  - TypeScript static typecheck: Clean exit code 0.
  - Complete before/after measurements in `tmp/clipforge_full_website_audit/overflow_analysis_after.json`.
- **Reversibility:** Fully backed up with pre-edit byte-for-byte snapshots in `scratch/pre_overflow_fix_snapshots/`.

---

### PROPOSAL #2: Real-Time Server-Side Video Frame Extraction API for Preview Modal (M3)

- **Issue ID:** `ISSUE-04`
- **Severity:** P3 (Feature Enhancement / Preview Fidelity)
- **Affected Route & Component:** `/podcasts` -> `PodcastSelectionModal.tsx`
- **Root Cause:**
  The frontend modal displays geometric layout previews and thumbnails. Real-time extraction of high-resolution video frames at exact shot timestamps (`t = start_time`) requires a dedicated backend frame extraction endpoint.
- **Proposed Correction:**
  1. Add an authenticated endpoint `POST /api/videos/extract-frame` accepting `{ video_url: string, timestamp_sec: number }`.
  2. The endpoint invokes a fast, single-frame FFmpeg extraction (`ffmpeg -ss {timestamp} -i {url} -vframes 1 -q:v 2 {out.jpg}`).
  3. The frontend `PodcastSelectionModal.tsx` fetches and displays the extracted frame as the background canvas when selecting cuts in the schedule table.
- **Target Files:**
  - `backend/api/routes/videos.py`
  - `backend/services/layout_engine.py`
  - `frontend/lib/api.ts`
  - `frontend/components/PodcastSelectionModal.tsx`
- **Risk Assessment:** Medium. Introduces a new API route and invokes FFmpeg on-demand. Requires rate-limiting to prevent server exhaustion.
- **Verification Plan:** Pytest API unit test, mock YouTube download, Playwright browser test verifying extracted frame rendering.

---

### PROPOSAL #3: Online Continuous Subject Motion Tracker for Dynamic Interviews (M3)

- **Issue ID:** `ISSUE-03`
- **Severity:** INFO / Architectural Limitation
- **Affected Backend Services:**
  - `backend/services/layout_engine.py`
  - `backend/services/advanced_podcast_engine.py`
- **Root Cause:**
  ClipForge's Fixed Two-Person reframing architecture computes 1 face crop per scene cut interval and applies smoothing between cut boundaries. In videos where participants pace or move across the room within a single shot, the camera does not continuously re-center them frame-by-frame.
- **Proposed Correction:**
  1. Integrate a lightweight continuous online tracker (e.g., ByteTrack or optical flow smoothing) within `CropTrajectorySmoother`.
  2. Sample face positions at 5 FPS rather than 1 frame per cut, interpolating smooth panning trajectories via cubic splines.
  3. Enforce maximum panning velocity to prevent jitter.
- **Target Files:**
  - `backend/services/advanced_podcast_engine.py`
  - `backend/services/layout_engine.py`
- **Risk Assessment:** High. Modifies core media-processing math and increases rendering compute time by approximately 15–20%.
- **Verification Plan:** Synthetic panning video fixture, frame luminance analysis, trajectory smoothness assertion tests.

---

### PROPOSAL #4: Docker Base Image Python Version Upgrade (M3)

- **Issue ID:** `ISSUE-06`
- **Severity:** P4 (Technical Debt)
- **Affected Docker Containers:** `clipforge_backend`, `clipforge_worker`, `clipforge_beat`, `clipforge_flower`
- **Root Cause:**
  Base image uses Python 3.11 (`python:3.11-slim`), which triggers an upstream Google API Core deprecation notice regarding support retirement in late 2027.
- **Proposed Correction:**
  1. Update `backend/Dockerfile` base image from `python:3.11-slim` to `python:3.12-slim`.
  2. Verify wheel compatibility for PyTorch, MediaPipe, Faster-Whisper, and AsyncPG.
  3. Rebuild Docker container images.
- **Target Files:**
  - `backend/Dockerfile`
  - `backend/requirements.txt`
- **Risk Assessment:** Medium. Python 3.12 may have binary wheel incompatibilities with specific machine learning dependencies if unpinned.
- **Verification Plan:** Full container build, healthcheck verification, and complete Pytest regression suite.
