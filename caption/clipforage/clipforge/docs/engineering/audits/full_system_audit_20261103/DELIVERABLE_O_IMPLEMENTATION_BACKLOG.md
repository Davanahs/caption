# Deliverable O: Prioritized Implementation & Remediation Backlog

**Audit Baseline Date:** 2026-11-03 / 2026-11-04  
**Audit Target:** ClipForge Production Repository (`d:\automation video clips\clipforge`)  
**Audit Authority:** Master Forensic Specification §12 & §14.O  
**Structure:** Prioritized by data safety, security posture, user impact, workflow dependencies, and implementation blast radius.  

---

## 1. Backlog Prioritization Methodology & Gating

Every backlog item is evaluated and prioritized against six objective criteria:
1. **Data Safety & Integrity:** Prevents data corruption, orphaned records, or accidental data exposure.
2. **Security & Vulnerability Severity:** Remediates high-impact OWASP ASVS exposures before network exposure.
3. **User & Creator Impact:** Resolves UX defects, accessibility barriers, or operational bottlenecks.
4. **Architectural Dependency Order:** Prerequisite infrastructure (e.g. crypto utilities) precedes dependent features.
5. **Implementation Blast Radius & Logic Freezes:** Favors minimal local corrections (Approach B) that avoid destabilizing verified code domains (L1–L10).
6. **Implementation Size:** Categorized as Extra Small (`XS`), Small (`S`), Medium (`M`), Large (`L`), or Extra Large (`XL`).

---

## 2. Master Prioritized Backlog Summary

| Rank | Task ID | Source Finding | Backlog Section | Priority | Size | Target Files & Components | Approval Gate |
|---|---|---|---|---|---|---|---|
| **1** | `TASK-SEC-01` | `FS-SEC-001` | Immediate Fix Candidate | **P1 (High)** | `S` | `backend/services/publisher.py`, `backend/core/crypto.py` | Owner Approval (L6) |
| **2** | `TASK-SEC-02` | `FS-SEC-005` | Immediate Fix Candidate | **P2 (Med)** | `XS` | `backend/core/config.py`, `backend/main.py` | None |
| **3** | `TASK-SEC-03` | `FS-SEC-006` | Immediate Fix Candidate | **P3 (Low)** | `XS` | `backend/core/config.py`, `backend/main.py:46` | None |
| **4** | `TASK-SEC-04` | `FS-SEC-003` | Immediate Fix Candidate | **P2 (Med)** | `XS` | `backend/api/routes/studio.py:465` | None |
| **5** | `TASK-SEC-05` | `FS-SEC-004` | Immediate Fix Candidate | **P2 (Med)** | `XS` | `backend/services/downloader.py:159` | None |
| **6** | `TASK-DB-01` | `FS-DB-002` | Immediate Fix Candidate | **P2 (Med)** | `XS` | `backend/models/models.py:417`, Alembic | Owner Approval (L3) |
| **7** | `TASK-UI-01` | `FS-UI-001` | Immediate Fix Candidate | **P2 (Med)** | `XS` | `frontend/components/RetentionHeatmap.tsx:58,80` | None |
| **8** | `TASK-UI-02` | `FS-UI-002` | Immediate Fix Candidate | **P3 (Low)** | `XS` | `frontend/app/automation/page.tsx:77` | None |
| **9** | `TASK-FE-01` | `FS-FE-001` | Immediate Fix Candidate | **P3 (Low)** | `S` | `frontend/app/analytics/`, `frontend/lib/` | None |
| **10** | `TASK-SEC-06` | `FS-SEC-002` | Capability Addition | **P1 (High)** | `M` | `backend/core/auth.py`, `backend/main.py`, `frontend/lib/api.ts` | Owner Approval (L1/L2) |
| **11** | `TASK-DB-02` | `FS-DB-001` | Capability Addition | **P2 (Med)** | `S` | `backend/models/models.py`, Alembic | Owner Approval (L3) |
| **12** | `TASK-MED-01` | `FS-MED-001` | Capability Addition | **P2 (Med)** | `M` | `backend/services/advanced_podcast_engine.py` | Owner Approval (L7) |
| **13** | `TASK-VER-01` | `BLK-DB-001` | Verification-Only Task | **P2 (Med)** | `S` | `backend/tests/` (7 deferred test suites) | Ephemeral DB Env |
| **14** | `TASK-VER-02` | `BLK-AUD-001` | Verification-Only Task | **P3 (Low)** | `XS` | QA Audio Audition Checklist | QA Listening Station |
| **15** | `TASK-BLK-01` | `BLK-EXT-001` | Blocked Validation Item | **P1 (High)** | `M` | `backend/scripts/verify_live_publishing_sandbox.py` | Staging Google Account |
| **16** | `TASK-BLK-02` | `BLK-EXT-002` | Blocked Validation Item | **P2 (Med)** | `S` | `backend/scripts/smoke_test_ai_providers.py` | API Credit Spend Cap |
| **17** | `TASK-DOC-01` | `FS-DOC-001` | Documentation Correction| **Info** | `XS` | `PROJECT_CONTINUITY.md`, `LOGIC_FREEZE_LEDGER.md` | None |

---

## 3. Section I: Immediate Fix Candidates

Immediate fix candidates are self-contained, low-risk, high-impact fixes that can be implemented cleanly using minimal local corrections (Approach B) without requiring structural refactoring.

---

### Task `TASK-SEC-01`: Encrypt YouTube OAuth Refresh Tokens at Rest
- **Finding ID:** `FS-SEC-001` (Severity: P1 High)
- **Target Files:**
  - Create: `backend/core/crypto.py`
  - Modify: `backend/services/publisher.py:1258–1270`
- **Technical Specification:**
  1. Author `backend/core/crypto.py` utilizing `cryptography.fernet.Fernet`. Derive encryption key from `settings.SECRET_KEY` using PBKDF2HMAC (SHA256, 100,000 iterations, static project salt).
  2. In `publisher.py:save_credentials()`, serialize `creds.to_json()`, encrypt the UTF-8 bytes with Fernet, and write the encrypted ciphertext blob to `tokens/youtube_token_{channel_id}.enc`.
  3. In `publisher.py:load_credentials()`, check for `.enc` file first. If present, read and decrypt before passing to `google.oauth2.credentials.Credentials.from_authorized_user_info()`. If only legacy `.json` exists, load plaintext, write `.enc`, and remove the unencrypted file (automatic migration).
- **Blast Radius & Freezes:** Confined strictly to credential file serialization in L6. Zero database schema or Celery changes.
- **Estimated Size:** **S (Small)**
- **Required Tests:** Author `backend/tests/test_token_encryption.py` testing encryption round-trip, invalid key handling, and legacy plaintext migration.

---

### Task `TASK-SEC-02`: Production Startup Guard for Default `SECRET_KEY`
- **Finding ID:** `FS-SEC-005` (Severity: P2 Medium)
- **Target Files:** `backend/core/config.py`, `backend/main.py:startup`
- **Technical Specification:**
  1. In `backend/core/config.py:Settings`, add a model validator:
     ```python
     @field_validator("SECRET_KEY")
     def validate_secret_key(cls, v: str, values):
         env = values.data.get("ENVIRONMENT", "development")
         if env == "production" and v == "dev-secret-key-change-in-production":
             raise ValueError("Insecure default SECRET_KEY detected in production environment!")
         return v
     ```
  2. For development mode, if `SECRET_KEY` is unset or default, generate a secure random 32-byte hex token and log a warning.
- **Blast Radius:** Configuration only; zero breaking changes in development.
- **Estimated Size:** **XS (Extra Small)**

---

### Task `TASK-SEC-03`: Fix Starlette Wildcard CORS Origin Parsing
- **Finding ID:** `FS-SEC-006` (Severity: P3 Low)
- **Target Files:** `backend/core/config.py:103`, `backend/main.py:46`
- **Technical Specification:**
  1. In `backend/core/config.py`, remove `"https://*.netlify.app"` from `CORS_ORIGINS`.
  2. Add setting: `CORS_ORIGIN_REGEX: str = r"https://.*\.netlify\.app"`
  3. In `backend/main.py:46`, update `app.add_middleware(CORSMiddleware)`:
     ```python
     app.add_middleware(
         CORSMiddleware,
         allow_origins=settings.CORS_ORIGINS,
         allow_origin_regex=settings.CORS_ORIGIN_REGEX,
         allow_credentials=True,
         allow_methods=["*"],
         allow_headers=["*"],
     )
     ```
- **Blast Radius:** Zero. Enables Netlify deploy preview testing.
- **Estimated Size:** **XS (Extra Small)**

---

### Task `TASK-SEC-04`: Pre-Upload MIME Magic-Byte Validation on Chunk 0
- **Finding ID:** `FS-SEC-003` (Severity: P2 Medium)
- **Target Files:** `backend/api/routes/studio.py:465–480`
- **Technical Specification:**
  1. In `upload_chunk()` handler, when `start_byte == 0`:
     ```python
     if start_byte == 0 and len(chunk_data) >= 12:
         # Check ISOBMFF signature (ftyp at bytes 4..8)
         is_isobmff = chunk_data[4:8] == b"ftyp"
         # Check Matroska/WebM EBML signature (0x1A45DFA3 at bytes 0..4)
         is_matroska = chunk_data[:4] == b"\x1a\x45\xdf\xa3"
         # Check AVI RIFF signature
         is_riff = chunk_data[:4] == b"RIFF" and chunk_data[8:12] == b"AVI "
         if not (is_isobmff or is_matroska or is_riff):
             raise HTTPException(
                 status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                 detail="Uploaded file signature does not match a valid media container (MP4/MOV/MKV/AVI)."
             )
     ```
- **Blast Radius:** Confined to `studio.py` chunk 0 validation.
- **Estimated Size:** **XS (Extra Small)**

---

### Task `TASK-SEC-05`: SSRF Filtering on Monitored Channel URLs
- **Finding ID:** `FS-SEC-004` (Severity: P2 Medium)
- **Target Files:** `backend/services/downloader.py:159–175`
- **Technical Specification:**
  1. In `normalize_channel_url(url: str) -> str`:
     ```python
     parsed = urllib.parse.urlparse(url.strip())
     if parsed.scheme not in ("http", "https"):
         raise ValueError("Invalid URL scheme: must be http or https")
     allowed_hosts = {"youtube.com", "www.youtube.com", "m.youtube.com", "youtu.be"}
     if parsed.netloc.lower() not in allowed_hosts:
         raise ValueError(f"Domain '{parsed.netloc}' is not an authorized YouTube domain.")
     ```
- **Blast Radius:** Confined to URL ingestion. Protects against internal network probing.
- **Estimated Size:** **XS (Extra Small)**

---

### Task `TASK-DB-01`: Align `PublishTarget.privacy` Model Default to Private
- **Finding ID:** `FS-DB-002` (Severity: P2 Medium)
- **Target Files:** `backend/models/models.py:417`, `backend/alembic/versions/`
- **Technical Specification:**
  1. In `backend/models/models.py:417`, change:
     ```python
     # From:
     privacy = sa.Column(sa.String(20), nullable=False, default="public")
     # To:
     privacy = sa.Column(sa.String(20), nullable=False, default="private", server_default="private")
     ```
  2. Author migration `backend/alembic/versions/e7f8a9b0c1d2_align_publish_target_privacy_default.py` setting `ALTER TABLE publish_targets ALTER COLUMN privacy SET DEFAULT 'private';`.
- **Blast Radius:** Database model default only. Matches Celery worker behavior.
- **Estimated Size:** **XS (Extra Small)**

---

### Task `TASK-UI-01`: Replace `window.alert()` in Retention Heatmap with Toast
- **Finding ID:** `FS-UI-001` (Severity: P2 Medium)
- **Target Files:** `clipforge/frontend/components/RetentionHeatmap.tsx:58, 80`
- **Technical Specification:**
  1. Import toast notification hook or define component state `[toastMessage, setToastMessage] = useState<string | null>(null)`.
  2. Replace `window.alert("Applying AI Auto-Fix Hook plan...")` with `setToastMessage("AI Auto-Fix Hook plan applied successfully.")`.
  3. Render accessible toast banner with `role="status"` and `aria-live="polite"`.
- **Blast Radius:** Single frontend component.
- **Estimated Size:** **XS (Extra Small)**

---

### Task `TASK-UI-02`: Associate Channel URL Input with Helper Text
- **Finding ID:** `FS-UI-002` (Severity: P3 Low)
- **Target Files:** `clipforge/frontend/app/automation/page.tsx:77–85`
- **Technical Specification:**
  1. Add `id="channel-url-helper"` to the helper paragraph `<p>`.
  2. Add `aria-describedby="channel-url-helper"` to `<input id="channel-url">`.
- **Blast Radius:** Single HTML attribute addition.
- **Estimated Size:** **XS (Extra Small)**

---

### Task `TASK-FE-01`: Frontend ESLint Debt Cleanup
- **Finding ID:** `FS-FE-001` (Severity: P3 Low)
- **Target Files:** `frontend/app/analytics/page.tsx`, `frontend/lib/podcastCoordinates.ts`
- **Technical Specification:**
  1. Define explicit TypeScript interfaces for analytics metrics (`interface VideoRetentionMetric`, `interface ChannelAnalyticsPayload`). Replace all 8 `any` type casts in `analytics/page.tsx`.
  2. In `frontend/lib/podcastCoordinates.ts:620–630`, convert unmutated `let` variables to `const`.
  3. Run `npm run lint` and verify 0 warnings and 0 errors.
- **Blast Radius:** Frontend TypeScript annotations; zero runtime logic changes.
- **Estimated Size:** **S (Small)**

---

## 4. Section II: Capability Additions

Capability additions represent structural enhancements that introduce new security boundaries, schema constraints, or media performance improvements.

---

### Task `TASK-SEC-06`: Implement FastAPI Route Authentication Dependency
- **Finding ID:** `FS-SEC-002` (Severity: P1 High)
- **Target Files:**
  - Create: `backend/core/auth.py`
  - Modify: `backend/main.py`, `backend/api/`, `frontend/lib/api.ts`
- **Technical Specification:**
  1. Author `backend/core/auth.py` defining `get_current_api_key(api_key: str = Security(api_key_header)) -> str`.
  2. Read valid keys from `settings.CLIPFORGE_API_KEYS` (list of strings) or constant-time comparison against `settings.API_KEY`.
  3. Include dependency on all `api_router` inclusions in `backend/main.py:75–115`, while exempting public health check `/api/health` and OpenAPI docs `/api/docs`.
  4. In `frontend/lib/api.ts` and `frontend/lib/studioApi.ts`, inject header `X-ClipForge-Key: process.env.NEXT_PUBLIC_API_KEY` on all fetch calls.
- **Blast Radius:** System-wide API boundary. Requires coordinating backend dependency with frontend client headers.
- **Estimated Size:** **M (Medium)**
- **Approval Gate:** Owner Approval & Logic Domain Freeze Exception (L1 / L2).

---

### Task `TASK-DB-02`: PostgreSQL Catalog Foreign Keys on Core Entities
- **Finding ID:** `FS-DB-001` (Severity: P2 Medium)
- **Target Files:** `backend/models/models.py:186, 233, 284`, `backend/alembic/versions/`
- **Technical Specification:**
  1. Author pre-migration cleanup SQL to identify and prune any orphaned records:
     ```sql
     DELETE FROM clips WHERE video_id NOT IN (SELECT id FROM videos);
     DELETE FROM jobs WHERE video_id NOT IN (SELECT id FROM videos);
     ```
  2. Author migration `e8f9a0b1c2d3_add_video_catalog_foreign_keys.py`:
     ```python
     op.create_foreign_key(
         "fk_clips_video_id_videos",
         "clips", "videos", ["video_id"], ["id"], ondelete="CASCADE"
     )
     op.create_foreign_key(
         "fk_jobs_video_id_videos",
         "jobs", "videos", ["video_id"], ["id"], ondelete="CASCADE"
     )
     ```
  3. Update `backend/models/models.py` to declare `sa.ForeignKey("videos.id", ondelete="CASCADE")`.
- **Blast Radius:** Database catalog level. Guarantees relational integrity on direct SQL deletions.
- **Estimated Size:** **S (Small)**
- **Approval Gate:** Owner Approval & Logic Domain Freeze Exception (L3 Database).

---

### Task `TASK-MED-01`: 4K Face-Tracking Resolution Proxy Optimization
- **Finding ID:** `FS-MED-001` (Severity: P2 Medium)
- **Target Files:** `backend/services/advanced_podcast_engine.py:1366–1515`
- **Technical Specification:**
  1. In `analyze_podcast_shots_task`, inspect incoming video resolution $(W, H)$.
  2. If $W > 1920$ or $H > 1080$:
     - Compute scale factor: $s = 540.0 / H$.
     - Downsample frame: `small_frame = cv2.resize(frame, (int(W * s), 540), interpolation=cv2.INTER_LINEAR)`.
     - Execute OpenCV face detection on `small_frame`.
     - Rescale detected bounding boxes back to normalized coordinates $(x / (W * s), y / 540)$.
  3. This reduces pixel volume on 4K media by $\approx 16\times$ ($3840 \times 2160 \to 960 \times 540$), dramatically accelerating CPU execution with zero impact on crop accuracy.
- **Blast Radius:** Internal helper function in `advanced_podcast_engine.py`.
- **Estimated Size:** **M (Medium)**
- **Approval Gate:** Owner Approval & Logic Domain Freeze Exception (L7 Advanced Podcast).

---

## 5. Section III: Verification-Only Tasks

Verification-only tasks require execution in dedicated environments without altering application source code.

---

### Task `TASK-VER-01`: Execute 105 Deferred Disposable PostgreSQL DB Tests
- **Finding ID:** `BLK-DB-001`
- **Execution Environment:** Ephemeral Docker PostgreSQL container on port 5433.
- **Command:**
  ```powershell
  docker run -d --name clipforge-test-pg -p 5433:5432 -e POSTGRES_PASSWORD=postgres postgres:15-alpine
  $env:TEST_DATABASE_URL="postgresql://postgres:postgres@localhost:5433/test_db"
  pytest backend/tests/test_c03_data_layer.py backend/tests/test_phase13_auto_pilot.py backend/tests/test_publishing_multi_destination.py backend/tests/test_upload_studio_phase1.py backend/tests/test_upload_studio_phase2.py backend/tests/test_channel_destinations_api.py backend/tests/test_db_migration_phase14.py
  docker rm -f clipforge-test-pg
  ```
- **Estimated Size:** **S (Small)**

---

### Task `TASK-VER-02`: Structured Human Audio QA Sensory Auditioning
- **Finding ID:** `BLK-AUD-001`
- **Execution Environment:** Calibrated audio workstation with studio reference monitors.
- **Action:** Audition 5 sample rendered video outputs across ducking transitions, speech intelligibility, and SFX timing. Sign off audio QA verification log.
- **Estimated Size:** **XS (Extra Small)**

---

## 6. Section IV: Blocked Validation Items

Blocked validation items require external account provisioning, third-party sandboxes, or user consent before they can be executed.

---

### Task `TASK-BLK-01`: YouTube Staging Sandbox Publishing Smoke Test
- **Finding ID:** `BLK-EXT-001`
- **Prerequisite:** Dedicated Google Cloud Sandbox OAuth credentials and test YouTube channel.
- **Action:** Author standalone script `backend/scripts/verify_live_publishing_sandbox.py` to upload a 5-second test Short with `privacyStatus="private"`, verify video ID via API, and immediately delete the test upload.
- **Estimated Size:** **M (Medium)**

---

### Task `TASK-BLK-02`: Paid AI Provider Smoke Test with $1.00 Budget Cap
- **Finding ID:** `BLK-EXT-002`
- **Prerequisite:** Pre-funded developer sandbox API keys with spend cap ($1.00).
- **Action:** Execute single 15-second audio sample through live Groq Whisper, Gemini Flash scoring, ElevenLabs voice synthesis, and Pexels stock video lookup. Capture live API responses.
- **Estimated Size:** **S (Small)**

---

## 7. Section V: Documentation Corrections

Documentation corrections reconcile historical project continuity records without modifying application code.

---

### Task `TASK-DOC-01`: Reconcile Test Count Denominator to 862 Tests
- **Finding ID:** `FS-DOC-001`
- **Target Files:** `docs/engineering/PROJECT_CONTINUITY.md`, `docs/engineering/LOGIC_FREEZE_LEDGER.md`
- **Action:** Update test inventory tables to reflect the true verified baseline:
  - Total Python Backend Tests: **748 tests** (across 68 files and 58 classes)
  - Total JavaScript Frontend Tests: **114 tests** (across 15 suites)
  - Grand Total Repository Tests: **862 tests**
  - Clarify that historical "331 tests" was an arbitrary subset that omitted 529 backend tests.
- **Estimated Size:** **XS (Extra Small)**

---

## 8. Section VI: Closed / No-Change Items (Verified Invariants)

In strict accordance with project rulebooks, the following 10 core subsystems and invariants are **100% verified** and **MUST NOT BE CHANGED**:

1. **Zero-Caption / Subtitle Prohibition (`VRF-INV-001`):** Completely verified across FFmpeg filtergraphs (`-sn`), database models, routes, and UI. No captions or subtitles may be added or rendered.
2. **Standard Podcast Stacked Split (`VRF-INV-002`):** Verified at 1080x960 per panel, centered black padding, and `ScaleMode.CONTAIN`. No dimension changes permitted.
3. **Single Speaker Focus (`VRF-INV-003`):** Verified deterministic mapping of Area 1 / index 0 to full 1080x1920 canvas.
4. **Advanced Podcast Dual Modes (`VRF-INV-004`):** Continuous tracking Mode 1 and discrete visibility classification Mode 2 must remain separate.
5. **Zero-Cut Fallback Guard (`VRF-INV-005` / `CER-2026-L7-001`):** FFmpeg exit code 0 discovering 0 cuts must never trigger OpenCV fallback on single-camera footage.
6. **AI-Only Moment Scoring (`VRF-INV-006`):** Heuristic or random scoring fallback on AI failure remains strictly forbidden.
7. **Subprocess Injection Immunity (`VRF-SEC-001`):** All external binaries must continue to use list arguments with `shell=False`.
8. **Path Traversal Containment (`VRF-SEC-002`):** `Path.resolve()` containment checking against upload directory must be preserved.
9. **Resumable Chunk Upload Streaming Fences (`VRF-SEC-003`):** 10 MiB limit, RFC 7233 continuity, 45s leases, and max 3 concurrent streams must be preserved.
10. **Private Publishing Hardening (`VRF-SEC-004`):** Worker override `target_privacy = "private"` and server default `'private'` must be preserved.
