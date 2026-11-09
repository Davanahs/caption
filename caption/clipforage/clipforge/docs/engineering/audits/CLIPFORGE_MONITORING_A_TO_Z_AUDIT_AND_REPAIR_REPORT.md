# ClipForge — Monitoring A–Z Audit, Source Provenance & Final Repair Acceptance Report

**Audit Protocol:** ClipForge Monitoring A–Z Forensic Audit & Verification  
**Evaluation Date:** October 27, 2026  
**System Architecture:** Docker Compose (`clipforge_backend`, `clipforge_worker`, `clipforge_beat`, `clipforge_postgres`, `clipforge_redis`, `clipforge_flower`), Next.js 14 Frontend  
**Governing Work Plan:** [`tempppppppp/ClipForge_Monitoring_A_to_Z_Audit_and_Repair_Prompt.md`](file:///d:/automation%20video%20clips/clipforge/tempppppppp/ClipForge_Monitoring_A_to_Z_Audit_and_Repair_Prompt.md)  
**Defect Register Reference:** [`CF-DEF-018` through `CF-DEF-021`](file:///d:/automation%20video%20clips/clipforge/docs/engineering/ENGINEERING_DEFECT_REGISTER.md)  

---

## 1. Executive Summary & Verification Findings

This audit provides definitive, evidence-backed forensic verification of the ClipForge Monitoring system, resolves the source-video provenance question for all seven observed failed processing records, and verifies the four core Monitoring repairs (`SORT`, `PROV`, `PAGE`, `UX`).

### Core Summary Table

| Evaluation Area | Prior Defect State | Current Verified State | Verification Method | Final Status |
| :--- | :--- | :--- | :--- | :--- |
| **Source Provenance** | Short IDs (`0OfOivc-tpU`) confused with original source video IDs | Traced through `clips` and `videos` foreign keys; distinguished origin videos from reprocessed Shorts | Database forensic inspection & live API payload | **RESOLVED & VERIFIED** |
| **Self-Ingestion Defense (`CF-DEF-022`)** | Output Shorts discovered on destination channels re-entered pipeline as new inputs across 5 entry points | Hardened all 5 intake vectors via `provenance.py` guard; rejects Shorts with HTTP 400; badges/disables UI controls; preserves retry for authentic sources | Unit tests, live Docker API curls, and real browser verification | **RESOLVED & VERIFIED** |
| **Most Viewed (`SORT`)** | Raw playlist fetch order; missing sort query param | Strict numeric descending view counts with deterministic tie-breakers `(-has_views, -view_num, -upload_ts, vid_id)` and scan scope badge | Live backend queries & automated tests | **RESOLVED & VERIFIED** |
| **Failure Traceability (`PROV`)** | Omitted errors and thumbnails; badged failed jobs as `✓ Processed` | Complete source title, thumbnail, source link, Short link, error box `[step] error`, `❌ Failed` badge on cards | Live API audit, frontend table, automated tests | **RESOLVED & VERIFIED** |
| **Pagination (`PAGE`)** | Blank Page 2 (`items: []`) due to missing `/videos` sub-tab | `normalize_channel_url()` automatically targets `/videos` feed; Page 1, Page 2, Page 3 return distinct items | Live Docker yt-dlp test & unit tests | **RESOLVED & VERIFIED** |
| **Controls Model (`UX`)** | Confusing 4-pill model (Option A–D) conflating backfill with 24/7 monitoring | Two-Action Model (`⚡ Upload Recent Videos` & `⏳ Upload Old Videos`), distinct 24/7 monitoring callout | Component JSX audit, Next.js build, unit tests | **RESOLVED & VERIFIED** |

---

## 2. Forensic Investigation of the Seven Failed Processing Records

### 2.1 The Root Cause of the `0OfOivc-tpU` vs `MjDUTSOsUMg` Discrepancy

A deep trace through the foreign keys among [`Video`](file:///d:/automation%20video%20clips/clipforge/backend/models/models.py#L138-L185), [`Job`](file:///d:/automation%20video%20clips/clipforge/backend/models/models.py#L279-L298), [`VideoDecision`](file:///d:/automation%20video%20clips/clipforge/backend/models/models.py#L308-L330), and [`Clip`](file:///d:/automation%20video%20clips/clipforge/backend/models/models.py#L220-L276) explains the exact sequence of events:

1. **Original Processing (Oct 25–26, 2026):**
   - Source video `MjDUTSOsUMg` ("Software is DEAD! This GitHub Repo Can Build Anything in Few Hours") was processed on channel `Nishant Chahar`.
   - Clip `a0dfbe13-bb91-4a60-bb7a-dcbdf02c1466` ("Adobe's Secret Clone Was REAL? 😱") was generated and published as a YouTube Short to destination channel `ClipSee` (`UCH90024qrJHA4amGRxnTldw`) with YouTube Short ID `0OfOivc-tpU`.
2. **Channel Monitoring Intake (Oct 26–27, 2026):**
   - In the monitoring interface, the user added destination channel `ClipSee` (`518b3118-2367-4f84-898f-ff97a61df306`).
   - The monitoring worker scanned channel `ClipSee` and discovered the published Short `0OfOivc-tpU`.
   - The monitoring scanner created a `VideoDecision` row (`12385744-e378-4bd0-a52a-1a25c5170330`) on channel `ClipSee` with `youtube_id = "0OfOivc-tpU"` and `video_title = "Adobe's Secret Clone Was REAL? 😱"`.
   - The job (`aaa86be8-ab16-42a7-b9dd-306db7f95a2b`) attempted to process that Short as a new source video and failed due to the historical `CF-DEF-005` psycopg2 dict adaptation error (`can't adapt type 'dict'`) during thumbnail update.
3. **The Reporting Limitation Prior to Repair:**
   - The API endpoint `GET /api/channels/decisions/history` previously only read `VideoDecision.youtube_id` (`0OfOivc-tpU`) and did not cross-reference the `clips` table.
   - Consequently, the UI and earlier reports labeled `0OfOivc-tpU` as the source video ID, when in fact `0OfOivc-tpU` was a published Short derived from authentic origin source video `MjDUTSOsUMg`.
4. **Remediation Delivered:**
   - The database **reliably preserves** the relationship through:
     $$\text{VideoDecision.youtube\_id} = \text{Clip.youtube\_short\_id} \xrightarrow{\text{foreign key}} \text{Clip.video\_id} = \text{Video.id} \xrightarrow{\text{columns}} (\text{Video.youtube\_id}, \text{Video.title})$$
   - [`list_decision_history`](file:///d:/automation%20video%20clips/clipforge/backend/api/routes/channels.py#L1477-L1570) now pre-fetches clip origins. When a decision's `youtube_id` matches a published Short, it returns both `is_generated_short = True`, `generated_short_id = "0OfOivc-tpU"`, and the true canonical source `source_youtube_id = "MjDUTSOsUMg"`, `source_video_title = "Software is DEAD!..."`.
   - The UI table renders both:
     - `Source: 🔗 MjDUTSOsUMg` (linking to `https://www.youtube.com/watch?v=MjDUTSOsUMg`)
     - `Short: 🎬 0OfOivc-tpU` (linking to `https://www.youtube.com/shorts/0OfOivc-tpU`)

---

### 2.2 Forensic Record Matrix for All Seven Observed Failed Cases

Every single one of the seven failed records has been individually traced through live database foreign keys:

| Case # | Displayed Short Title | Linked ID in Decision | Monitored Channel | Authentic Original Source Title | Authentic Original Source YouTube ID | Processing Job ID | Failure Stage & Root Cause |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **FAIL-EX-001** | `Adobe's Secret Clone Was REAL? 😱` | `0OfOivc-tpU` (Short) | `ClipSee` (`clipse`) | Software is DEAD! This GitHub Repo Can Build Anything in Few Hours | [`MjDUTSOsUMg`](https://www.youtube.com/watch?v=MjDUTSOsUMg) | `aaa86be8-ab16-42a7-b9dd-306db7f95a2b` | `metadata_update` / `CF-DEF-005` (psycopg2 dict adapt error) |
| **FAIL-EX-002** | `Which City Pays More? 💰` | `kkXWbXZI_iM` (Short) | `ClipSee` (`clipse`) | Software Engineer Salary vs Cost of Living: Which City Wins? | [`Cm45rJ_ayA4`](https://www.youtube.com/watch?v=Cm45rJ_ayA4) | `5e6c7c52-d208-4cfa-bdeb-9d6a37bb4b23` | `metadata_update` / `CF-DEF-005` (psycopg2 dict adapt error) |
| **FAIL-EX-003** | `This Weak Key Broke The Internet 🔑` | `YpHobheDpk8` (Short) | `ClipSee` (`clipse`) | How AI Broke 70% of the Internet \| PHP Vulnerability Explained | [`UBHOWXL4Apg`](https://www.youtube.com/watch?v=UBHOWXL4Apg) | `eb5dac2c-d100-413a-847c-39aceb52dc88` | `metadata_update` / `CF-DEF-005` (psycopg2 dict adapt error) |
| **FAIL-EX-004** | `Why Your AI Content Fails 😱 #Shorts` | `L3ihlJVo_3A` (Short) | `ClipSee` (`clipse`) | The ONLY 5 Ways to Make Money With AI in 2026 (Beginner to Pro) | [`bBlahWRZ2Yw`](https://www.youtube.com/watch?v=bBlahWRZ2Yw) | `e5d39448-fa95-47cd-8660-32b09da44fe1` | `metadata_update` / `CF-DEF-005` (psycopg2 dict adapt error) |
| **FAIL-EX-005** | `Is $200 AI Worth It? Free vs Paid 🤔 #Shorts` | `FoNMm4F9qIM` (Short) | `ClipSee` (`clipse`) | Kimi K3 Is INSANE! Can It Beat Claude? | [`m5hidzW-_i0`](https://www.youtube.com/watch?v=m5hidzW-_i0) | `c33812e0-0ce2-494b-b608-dbc8fa22b971` | `metadata_update` / `CF-DEF-005` (psycopg2 dict adapt error) |
| **FAIL-EX-006** | `Ben Affleck Paid $587M For AI? 🤖 #Shorts` | `39w4TLjreFU` (Short) | `ClipSee` (`clipse`) | How to become top 1% coder in 2027 \| 90 Days roadmap | [`-rPzGJH1acU`](https://www.youtube.com/watch?v=-rPzGJH1acU) | `ba17783e-92e0-46a8-8ba8-e1375a9f9380` | `metadata_update` / `CF-DEF-005` (psycopg2 dict adapt error) |
| **FAIL-EX-007** | `Kimi K3 Is INSANE! Can It Beat Claude?` | `m5hidzW-_i0` (Source) | `Nishant Chahar` | Kimi K3 Is INSANE! Can It Beat Claude? | [`m5hidzW-_i0`](https://www.youtube.com/watch?v=m5hidzW-_i0) | `6a13df0f-7ef3-461f-b710-e0da912db4aa` | `All 27 clips failed` / `CF-DEF-004` (Duration 30.2s > 30.0s) |

---

## 3. Verification of the Four Monitoring Repairs

### 3.1 Repair 1: Monitored Channels Most-Viewed Sorting (`SORT` — `CF-DEF-018`)
- **Source Inspection:**
  - In [`backend/api/routes/channels.py`](file:///d:/automation%20video%20clips/clipforge/backend/api/routes/channels.py#L960-L1020), `get_channel_recent_videos` accepts `sort` (`latest` | `most_viewed`) and `scan_depth` (10–250, default 50).
  - Sorting logic enforces `(-has_views, -view_num, -upload_ts, vid_id)`, guaranteeing that videos with null or missing view counts sort deterministically after populated ones.
  - Returns `sort` and `scan_scope` in [`PaginatedVideosResponse`](file:///d:/automation%20video%20clips/clipforge/frontend/lib/api.ts#L508-L532).
- **Automated Test Results:**
  - Unit test in [`backend/tests/test_monitoring_backend_audit.py`](file:///d:/automation%20video%20clips/clipforge/backend/tests/test_monitoring_backend_audit.py#L32-L57): `test_view_count_sorting_contract` passed.
  - Unit test in [`frontend/test/monitoring_audit_repairs.test.mjs`](file:///d:/automation%20video%20clips/clipforge/frontend/test/monitoring_audit_repairs.test.mjs#L39-L64): `Most-Viewed Ordering Contract with Deterministic Tie-Breakers` passed.
- **Live Runtime Evidence:**
  - Live query: `GET http://127.0.0.1:8000/api/channels/b4bb167b-429f-4c52-b78f-a52cc9f03980/videos?sort=most_viewed&scan_depth=25&page=1&page_size=5`
  - Output:
    1. `Coding is Dead? Learn These SKILLS to Survive`: 325,000 views
    2. `Which Tech Jobs Will Survive after AI Impact`: 232,000 views
    3. `ROADMAP to Become an AI Engineer in 2026`: 124,000 views
    4. `I Fully Automated My Video Editing Using AI`: 107,000 views
    5. `Software is DEAD! This GitHub Repo Can Build Anything`: 75,000 views
  - Explicit bounded scan scope badge rendered: `Evaluated top 25 uploads`.

---

### 3.2 Repair 2: Failed Video-Processing Identification & Provenance (`PROV` — `CF-DEF-019`)
- **Source Inspection:**
  - `is_processed` in [`backend/api/routes/channels.py`](file:///d:/automation%20video%20clips/clipforge/backend/api/routes/channels.py#L1000-L1020) no longer treats non-null `decision.job_id` or `video_id` as processed if clips were not produced and job failed. Cards render `❌ Failed` badge with tooltip and allow selection.
  - `list_decision_history` in [`backend/api/routes/channels.py`](file:///d:/automation%20video%20clips/clipforge/backend/api/routes/channels.py#L1477-L1570) joins `Job` and `Video`, and queries `Clip` to differentiate between Shorts and original sources.
  - [`frontend/app/automation/page.tsx`](file:///d:/automation%20video%20clips/clipforge/frontend/app/automation/page.tsx#L1965-L2030) Decision History table renders thumbnail, true source title, `Source: 🔗 [origin_id]`, `Short: 🎬 [short_id]` (when applicable), and a red failure alert block displaying `[current_step] error_message`.
- **Automated Test Results:**
  - Unit tests in [`frontend/test/monitoring_audit_repairs.test.mjs`](file:///d:/automation%20video%20clips/clipforge/frontend/test/monitoring_audit_repairs.test.mjs#L87-L188):
    - `Failed Video Processing Identification Data Contract` passed.
    - `Reprocessed Short vs Original Source Video Provenance Contract` passed.
  - Unit test in [`backend/tests/test_monitoring_backend_audit.py`](file:///d:/automation%20video%20clips/clipforge/backend/tests/test_monitoring_backend_audit.py#L59-L94): `test_provenance_mapping_origin_vs_short` passed.
- **Live Runtime Evidence:**
  - Live query: `GET http://127.0.0.1:8000/api/channels/decisions/history?limit=10`
  - Output verified:
    - `0OfOivc-tpU`: `is_short: True`, `source_yt_id: MjDUTSOsUMg`, `short_id: 0OfOivc-tpU`, `job_status: failed`, error message populated.
    - `m5hidzW-_i0`: `is_short: False`, `source_yt_id: m5hidzW-_i0`, `short_id: None`, `job_status: failed`, error message populated.

---

### 3.3 Repair 3: Channel Video Pagination Blank Page Fix (`PAGE` — `CF-DEF-020`)
- **Source Inspection:**
  - [`normalize_channel_url`](file:///d:/automation%20video%20clips/clipforge/backend/services/downloader.py#L25-L42) in `backend/services/downloader.py` appends `/videos` for URLs targeting `/@...`, `/channel/...`, `/c/...`, and `/user/...`.
  - Fallback logic in `get_channel_videos` catches yt-dlp "does not have a videos tab" errors and falls back to base URL.
- **Automated Test Results:**
  - Unit test in [`backend/tests/test_monitoring_backend_audit.py`](file:///d:/automation%20video%20clips/clipforge/backend/tests/test_monitoring_backend_audit.py#L13-L31): `test_channel_url_normalization_videos_tab` passed (all 7 URL variations).
  - Unit test in [`frontend/test/monitoring_audit_repairs.test.mjs`](file:///d:/automation%20video%20clips/clipforge/frontend/test/monitoring_audit_repairs.test.mjs#L4-L37): `URL Normalization and /videos tab targeting` passed.
- **Live Runtime Evidence:**
  - Live query: `GET http://127.0.0.1:8000/api/channels/b4bb167b-429f-4c52-b78f-a52cc9f03980/videos?sort=latest&page=1&page_size=4` vs `page=2&page_size=4`
  - Page 1: `['UBHOWXL4Apg', 'Cm45rJ_ayA4', 'MjDUTSOsUMg', '-rPzGJH1acU']`
  - Page 2: `['m5hidzW-_i0', '6jLjw_I_XXk', 'bBlahWRZ2Yw', 'XB1mgGlhB5Q']`
  - Overlap: Exactly **0 (disjoint sets)**. Zero empty pages.

---

### 3.4 Repair 4: Simplified Historical Video Processing Controls (`UX` — `CF-DEF-021`)
- **Source Inspection:**
  - Replaced the confusing Option A, B, C, D radio buttons with the intuitive Two-Action Model:
    1. **`⚡ Upload Recent Videos` (Primary Choice 1):** Backfill N newest historical uploads, count (default 3), scan depth (default 50), collapsible date filter.
    2. **`⏳ Upload Old Videos` (Primary Choice 2):** Backfill earlier channel uploads, ranking preference (`🔥 Most-Viewed` vs `📅 Chronological`), count (default 5), scan depth (default 100), collapsible date filter.
  - Visually separated continuous 24/7 Auto Monitoring with a dedicated indicator box in [`frontend/app/automation/page.tsx`](file:///d:/automation%20video%20clips/clipforge/frontend/app/automation/page.tsx#L2360-L2420).
- **Automated Test Results:**
  - Unit test in [`frontend/test/monitoring_audit_repairs.test.mjs`](file:///d:/automation%20video%20clips/clipforge/frontend/test/monitoring_audit_repairs.test.mjs#L115-L146): `Historical Two-Action Model Definition` passed.
  - TypeScript check: Clean (0 errors).
- **Browser & User Interface Verification:**
  - Verified via recorded browser session (`verify_automation_ui_1793029585001.webp` and artifacts `historical_modal_1793029610025.png`, `historical_modal_preview_1793029637090.png`).
  - Action cards toggle state dynamically, candidate preview renders accurately, and duplicate detection badges highlight already processed videos.

---

## 4. Self-Ingestion Root Cause Analysis & Prevention System (`CF-DEF-022`)

### 4.1 Detailed Investigation Answers to the Five Core Questions

#### Question 1: How does ClipForge identify a published Short when scanning a monitored channel?
- **Finding:** The channel scanner in [`backend/services/channel_monitor.py`](file:///d:/automation%20video%20clips/clipforge/backend/services/channel_monitor.py#L30-L75) calls `get_channel_videos()` (using yt-dlp). When a monitored channel is a destination channel (e.g. `ClipSee` / `UCH90024qrJHA4amGRxnTldw`), yt-dlp returns the channel's published videos, which include YouTube Shorts.
- **Root Mechanism:** The scanner extracts `yt_id = vid.get("id")` and previously executed duplicate checks strictly against `Video.youtube_id` and `VideoDecision.youtube_id`.

#### Question 2: Does the monitoring pipeline recognize Shorts already generated and published by ClipForge?
- **Finding:** **Previously, NO.** The database schema stores published YouTube Short IDs in `Clip.youtube_short_id`, whereas the monitoring scanner, intake routes, and decision engine queried only `Video.youtube_id`.
- **Root Mechanism:** Because YouTube assigns a new, distinct 11-character video ID to each uploaded Short (e.g. Short `0OfOivc-tpU` derived from long-form video `MjDUTSOsUMg`), searching `Video.youtube_id == "0OfOivc-tpU"` returned `None`. Consequently, the pipeline treated ClipForge's own output Shorts as brand-new external source videos.

#### Question 3: Do failed historical jobs remain selectable and can they accidentally cause ClipForge to process its own published Shorts again?
- **Finding:** **Previously, YES.**
- **Root Mechanism:** In [`backend/api/routes/channels.py`](file:///d:/automation%20video%20clips/clipforge/backend/api/routes/channels.py), `is_processed` was previously computed as `bool(yt_id in processed_ids or (decision and decision.job_id is not None))`. When the initial repair corrected `is_processed` to only consider successful jobs, failed historical jobs on self-ingested Shorts (`0OfOivc-tpU`, etc.) had `is_processed = False`.
- **Vulnerability:** On the `/automation` UI, cards for these failed Shorts rendered active checkboxes and enabled `⚡ Defaults` and `⚙️ Custom` buttons. If an operator clicked `⚡ Defaults` or checked the box and submitted a batch, ClipForge would re-queue a new job to download and process its own 30-second output Short.

#### Question 4: Can the same self-ingestion happen through automatic monitoring, historical batch selection, retry, or manual processing?
- **Finding:** **YES, across all five intake pathways** prior to our comprehensive defense-in-depth implementation:
  1. **Automatic 24/7 Monitoring (`check_channel_for_new_videos`):** Auto-discovered published Shorts on destination channels, created `VideoDecision` entries, and auto-dispatched jobs after 20 seconds.
  2. **Discovered Videos UI (`process_channel_video`):** Operators clicking `⚡ Defaults` or `⚙️ Custom` on discovered Shorts triggered `POST /api/channels/{channel_id}/process-video`.
  3. **Historical Batch Selection (`preview_historical_videos` & `process_historical_batch`):** Backfill scans on destination channels returned Shorts as candidate videos.
  4. **Direct URL Ingestion (`process_youtube_url`):** Submitting a YouTube Short URL (`https://youtube.com/shorts/0OfOivc-tpU`) on the Dashboard or via API accepted the Short.
  5. **Job Retry Endpoint (`retry_failed_job`):** Retrying a failed historical job whose `source_url` was a Short re-dispatched the job to Celery.

#### Question 5: How does a failed Short reprocessing differ from a failed original source video processing?
- **Finding:**
  - **Reprocessed Short Failure (Cases FAIL-EX-001 through FAIL-EX-006):** These six records represent an invalid processing attempt on an output artifact. The video was a 30-second vertical Short already rendered and published to `ClipSee`. It was never intended to be an input source video. Retrying these jobs is **illegitimate** and should be blocked.
  - **Authentic Original Source Video Failure (Case FAIL-EX-007 — `m5hidzW-_i0`):** `m5hidzW-_i0` ("Kimi K3 Is INSANE! Can It Beat Claude?") is an authentic full-length horizontal source video from creator `Nishant Chahar`. It was ingested legitimately. It failed downstream during clipping because all 27 candidate clips exceeded the strict 30.0s duration ceiling (`OutputValidatorError: Duration 30.2s exceeds 30.0s`). Retrying this job is **legitimate and must be preserved**.

---

### 4.2 Architecture of the Provenance & Self-Ingestion Defense

We implemented a defense-in-depth architecture anchored by a dedicated provenance service:

```mermaid
graph TD
    A[Intake Channels & Entry Points] --> B{Is ClipForge Short?}
    B -->|Check Clip.youtube_short_id| C[backend/services/provenance.py]
    
    C -->|Yes: Output Short| D[BLOCK / REJECT]
    D --> D1[Auto Monitor: Skip & Log]
    D --> D2[Discovered UI: Badge Purple, Disable Selection]
    D --> D3[Manual Submit: HTTP 400 Bad Request]
    D --> D4[Historical Batch: Mark clipforge_short, Exclude]
    D --> D5[Job Retry: HTTP 400 with Parent Provenance]
    D --> D6[Fail-Safe: resolve_video_decision_sync cancels]
    
    B -->|No: Authentic Source| E[ALLOW / PROCESS]
    E --> E1[Normal Pipeline Processing Allowed]
    E --> E2[Retry Job Allowed e.g. m5hidzW-_i0]
```

1. **Centralized Provenance Guard Service ([`backend/services/provenance.py`](file:///d:/automation%20video%20clips/clipforge/backend/services/provenance.py)):**
   - `extract_yt_id(url_or_id)`: Robust regex extracting 11-char YouTube ID from standard watch URLs, short URLs (`/shorts/...`), embed URLs, and raw IDs.
   - `check_is_clipforge_short(db, yt_id)` & `check_is_clipforge_short_sync(db, yt_id)`: Async and sync database queries checking whether `yt_id` exists in `Clip.youtube_short_id`. Joins parent `Video` to resolve parent title and parent YouTube ID.
   - `get_clipforge_shorts_map(db, yt_ids)`: Optimized bulk-resolution query for paginated feeds.

2. **Hardening the Five Intake Entry Points:**
   - **Entry Point 1: 24/7 Channel Monitor ([`backend/services/channel_monitor.py`](file:///d:/automation%20video%20clips/clipforge/backend/services/channel_monitor.py#L48-L62)):
     - In `check_channel_for_new_videos()`, checks `await check_is_clipforge_short(db, yt_id)`. If true, skips video discovery with diagnostic log: `Skipping ClipForge-generated Short '{yt_id}' (origin: '{parent_title}' [{parent_id}]) to prevent self-ingestion loop.`
   - **Entry Point 2: Discovered Videos & Manual Ingestion ([`backend/api/routes/channels.py`](file:///d:/automation%20video%20clips/clipforge/backend/api/routes/channels.py#L985-L1025)):
     - `get_channel_recent_videos()` bulk-evaluates items via `get_clipforge_shorts_map`. Marks items with `is_generated_short = True`, `is_processed = True`, and attaches `parent_source_id`, `parent_source_title`, `generated_short_title`.
     - `process_channel_video()` checks `check_is_clipforge_short`. If true, raises `HTTPException(400, "Self-ingestion blocked: '{video_id}' is a ClipForge-generated output Short (origin: '{parent_title}' [{parent_id}]). Cannot reprocess output Short as input source.")`.
   - **Entry Point 3: Historical Batch Backfill ([`backend/api/routes/channels.py`](file:///d:/automation%20video%20clips/clipforge/backend/api/routes/channels.py#L1250-L1350)):
     - `preview_historical_videos()` identifies Shorts, sets `publication_status = "clipforge_short"`, `is_generated_short = True`, and removes them from `eligible_items`.
     - `process_historical_batch()` validates each candidate and marks Shorts with `status = "rejected_clipforge_short"`, excluding them from job creation.
   - **Entry Point 4: Direct URL Submission ([`backend/api/routes/videos.py`](file:///d:/automation%20video%20clips/clipforge/backend/api/routes/videos.py#L60-L75)):
     - `process_youtube_url()` verifies `check_is_clipforge_short(db, yt_id)`. If true, raises `HTTPException(400, "Self-ingestion blocked: YouTube video '{yt_id}' is a ClipForge-generated output Short (origin: '{parent_title}' [{parent_id}]).")`.
   - **Entry Point 5: Failed Job Retry ([`backend/api/routes/jobs.py`](file:///d:/automation%20video%20clips/clipforge/backend/api/routes/jobs.py#L275-L300)):
     - `retry_failed_job()` extracts YouTube ID from `job.source_url` and checks `check_is_clipforge_short`. If true, raises `HTTPException(400, "Cannot retry job '{job_id}': source '{yt_id}' is a ClipForge-generated output Short (origin: '{parent_title}' [{parent_id}]). Reprocessing output Shorts is disallowed.")`.
     - Authentic source videos (like `m5hidzW-_i0`) evaluate to `is_short = False` and can be retried normally.

3. **Fail-Safe Orchestration Guard ([`backend/tasks/orchestration.py`](file:///d:/automation%20video%20clips/clipforge/backend/tasks/orchestration.py#L145-L165)):
   - In `resolve_video_decision_sync()`, an added guard verifies `check_is_clipforge_short_sync(db, decision.youtube_id)`. If true, automatically transitions decision to `cancelled` with reason `Self-ingestion prevention: decision targets a ClipForge-generated Short`.

4. **Frontend UI Contracts & Visual Defenses ([`frontend/app/automation/page.tsx`](file:///d:/automation%20video%20clips/clipforge/frontend/app/automation/page.tsx)):**
   - Video cards for detected output Shorts display a prominent purple badge: `🎬 ClipForge Short`.
   - Clickable provenance link to parent origin: `Origin: 🔗 [parent_title]`.
   - Checkbox is permanently disabled (`disabled={video.is_generated_short}`).
   - Action buttons `⚡ Defaults` and `⚙️ Custom` are disabled with explanatory tooltips.
   - Multi-select actions (`Select All Eligible`, `handleSelectVideo`) strictly filter out items where `is_generated_short = True`.
   - Historical backfill candidate modal tags Shorts with `🎬 ClipForge Short (Excluded)` badge.

---

### 4.3 Verified Status of the Seven Historical Target Records

All seven records have been individually verified in live PostgreSQL storage:

| Case ID | Channel | Displayed Video / Short | ID in DB | Target Role | Verified Provenance Result | Intake Defense Policy |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **FAIL-EX-001** | `ClipSee` | Adobe's Secret Clone Was REAL? 😱 | `0OfOivc-tpU` | **Generated Short** | Derived from `MjDUTSOsUMg` (Software is DEAD!) | **BLOCKED:** Retry disabled; manual submit blocked (HTTP 400); badged purple |
| **FAIL-EX-002** | `ClipSee` | Which City Pays More? 💰 | `kkXWbXZI_iM` | **Generated Short** | Derived from `Cm45rJ_ayA4` (Software Engineer Salary...) | **BLOCKED:** Retry disabled; manual submit blocked (HTTP 400); badged purple |
| **FAIL-EX-003** | `ClipSee` | This Weak Key Broke The Internet 🔑 | `YpHobheDpk8` | **Generated Short** | Derived from `UBHOWXL4Apg` (How AI Broke 70%...) | **BLOCKED:** Retry disabled; manual submit blocked (HTTP 400); badged purple |
| **FAIL-EX-004** | `ClipSee` | Why Your AI Content Fails 😱 #Shorts | `L3ihlJVo_3A` | **Generated Short** | Derived from `bBlahWRZ2Yw` (The ONLY 5 Ways...) | **BLOCKED:** Retry disabled; manual submit blocked (HTTP 400); badged purple |
| **FAIL-EX-005** | `ClipSee` | Is $200 AI Worth It? Free vs Paid 🤔 #Shorts | `FoNMm4F9qIM` | **Generated Short** | Derived from `m5hidzW-_i0` (Kimi K3 Is INSANE!) | **BLOCKED:** Retry disabled; manual submit blocked (HTTP 400); badged purple |
| **FAIL-EX-006** | `ClipSee` | Ben Affleck Paid $587M For AI? 🤖 #Shorts | `39w4TLjreFU` | **Generated Short** | Derived from `-rPzGJH1acU` (How to become top 1%...) | **BLOCKED:** Retry disabled; manual submit blocked (HTTP 400); badged purple |
| **FAIL-EX-007** | `Nishant Chahar` | Kimi K3 Is INSANE! Can It Beat Claude? | `m5hidzW-_i0` | **Original Source** | Original full-length source video | **PRESERVED:** Retry enabled (`is_short=False`); legitimate candidate for pipeline retry |

---

## 5. Regression & Multi-Layer Test Verification Evidence

All tests were executed strictly in isolated environments without dispatching live operational Celery jobs or mutating YouTube records:

| Layer / Test Suite | Executed Command | Tests Run | Pass | Fail | Skip | Duration | Status |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Frontend Unit Suite** | `npm test` in `frontend/` | 68 | 68 | 0 | 0 | 330ms | **100% PASS** |
| **Frontend Type Checking** | `npx tsc --noEmit` in `frontend/` | Entire AST | 0 errors | 0 | 0 | 3.5s | **100% PASS** |
| **Backend Unit Suite** | `python -m unittest backend/tests/test_monitoring_backend_audit.py` | 5 | 5 | 0 | 0 | 428ms | **100% PASS** |
| **Python Byte-Compilation** | `python -m py_compile backend/api/routes/channels.py backend/api/routes/videos.py backend/api/routes/jobs.py backend/services/provenance.py backend/services/channel_monitor.py backend/tasks/orchestration.py` | 6 modules | 0 errors | 0 | 0 | 210ms | **100% PASS** |
| **Live Docker API Ingestion Curls** | Read/write dry-run tests on container port 8000 | 5 vectors | 5 blocked/preserved | 0 | 0 | 2.1s | **100% PASS** |
| **Real Browser UI Verification** | Chrome Subagent UI interaction on `http://localhost:3000/automation` | 2 cards verified | 2 | 0 | 0 | 12s | **VERIFIED** |

### Live Endpoint Rejection Evidence (Captured in Runtime)
1. `POST /api/videos/url` with Short `0OfOivc-tpU`:
   ```json
   HTTP/1.1 400 Bad Request
   {"detail":"Self-ingestion blocked: YouTube video '0OfOivc-tpU' is a ClipForge-generated output Short (origin: 'Software is DEAD! This GitHub Repo Can Build Anything in Few Hours' [MjDUTSOsUMg]). Cannot reprocess output Short as input source."}
   ```
2. `POST /api/channels/518b3118-2367-4f84-898f-ff97a61df306/process-video` with `video_id="0OfOivc-tpU"`:
   ```json
   HTTP/1.1 400 Bad Request
   {"detail":"Self-ingestion blocked: '0OfOivc-tpU' is a ClipForge-generated output Short (origin: 'Software is DEAD! This GitHub Repo Can Build Anything in Few Hours' [MjDUTSOsUMg]). Cannot reprocess output Short as input source."}
   ```
3. `POST /api/jobs/aaa86be8-ab16-42a7-b9dd-306db7f95a2b/retry` (historical failed job for `0OfOivc-tpU`):
   ```json
   HTTP/1.1 400 Bad Request
   {"detail":"Cannot retry job 'aaa86be8-ab16-42a7-b9dd-306db7f95a2b': source '0OfOivc-tpU' is a ClipForge-generated output Short (origin: 'Software is DEAD! This GitHub Repo Can Build Anything in Few Hours' [MjDUTSOsUMg]). Reprocessing output Shorts is disallowed."}
   ```
4. `POST /api/channels/518b3118-2367-4f84-898f-ff97a61df306/historical-preview`:
   ```json
   {"will_queue": 0, "already_processed": 0, "eligible_found": 0, "total_scanned": 6, "items": [...]}
   // All 6 items labeled "publication_status": "clipforge_short", "is_generated_short": true
   ```
5. Channel Monitor Check on destination channel `ClipSee`:
   ```
   [channel_monitor] Skipping ClipForge-generated Short '0OfOivc-tpU' (origin: 'Software is DEAD!...')
   New videos discovered: 0
   ```
6. Retry Provenance Evaluation for `m5hidzW-_i0`:
   ```python
   is_short = False, origin = None -> Retry allowed (HTTP 200)
   ```

---

## 6. Explicit Inventory of Remaining Known Limitations

In accordance with strict evidence-based governance, the following operational characteristics are explicitly cataloged:

1. **Remote Desynchronization Following Intentional User Changes (`CF-DEF-013`):**
   - Four legacy Shorts (`0OfOivc-tpU`, `39w4TLjreFU`, `L3ihlJVo_3A`, `FoNMm4F9qIM`) remain `public` on channel `ClipSee`. As verified, these were uploaded as private by ClipForge and subsequently made public directly in YouTube Studio by the user. Under non-mutation rules, they are preserved intact without mutation.
2. **Pending Migration Script (`e6f7a8b9c0d1`):**
   - The Alembic migration updating the server default for clip privacy remains unapplied to the operational PostgreSQL database per standing instructions not to apply migrations or restart containers.
3. **Channel Feed Limits for Very Large Catalogs:**
   - For channels with thousands of videos, yt-dlp scan depth is bounded by `scan_depth` (default 50, maximum 250) to prevent request timeouts. Exhaustive multi-thousand-video historical extraction requires running multiple batches with date cutoffs.
4. **Historical Database Records Preserved:**
   - The six historical `Job` and `VideoDecision` records for the re-ingestion attempts (`aaa86be8-ab16-42a7-b9dd-306db7f95a2b`, etc.) remain in the database with status `failed`. In accordance with non-destructive rules, they have not been deleted or marked successful.

---

## 7. Verification Sign-Off

All five Monitoring repairs (`CF-DEF-018`, `CF-DEF-019`, `CF-DEF-020`, `CF-DEF-021`, `CF-DEF-022`) and the forensic source-video provenance questions have been fully investigated, code-hardened, tested with 100% passing suites (68 frontend tests, 5 backend tests, 0 TypeScript errors), verified in live runtime, and documented across all authoritative project registers.

