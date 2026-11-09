# Deliverable N: Not-Tested / Blocked Verification Register

**Audit Baseline Date:** 2026-11-03 / 2026-11-04  
**Audit Target:** ClipForge Production Repository (`d:\automation video clips\clipforge`)  
**Audit Authority:** Master Forensic Specification §12, §13 & §14.N  
**Scope:** Exhaustive catalog of all unexecuted tests, blocked verifications, external dependency boundaries, and environmental prerequisites across Milestones M1, M2, and M3.  

---

## 1. Principles of Blocked Verification Accounting

In strict accordance with Master Specification §13:
1. **No Fake Passes:** A test written but not executed does NOT count as passed.
2. **Mock Boundaries:** Mocked socket tests prove code logic and contract adherence (Evidence Tier E1/E2), but do NOT prove live third-party service availability or account authorization (Evidence Tier E6).
3. **Safety First:** Read-only benchmark constraints strictly forbid mutating external accounts, incurring third-party financial charges, or modifying operational database containers.
4. **Transparent Denominators:** All unexecuted items are explicitly itemized below with exact root causes, prerequisites, and actionable gap-closing procedures.

---

## 2. Master Not-Tested / Blocked Register Summary Table

| Blocked ID | Subsystem / Operation | Category | Severity / Impact | Blocking Reason & Rule Constraint | Required Environment / Permissions | Action to Close Verification Gap |
|---|---|---|---|---|---|---|
| `BLK-EXT-001` | **Live YouTube OAuth Exchange & Shorts Publication** | Publishing / External API | High | Read-Only Safety Rule 0.3; External Account Protection; Socket Guard | Google OAuth Client Secret, live YouTube Channel with Shorts enabled, user browser consent | Run controlled staging upload in dedicated test channel with disposable sandbox credentials |
| `BLK-DB-001` | **PostgreSQL Disposable DB Test Suite (105 Tests)** | Database / Migrations | Medium | Local Container State Preservation; Avoid dropping/creating live schemas | Isolated ephemeral PostgreSQL instance on alternate port (`TEST_DATABASE_URL`) | Launch ephemeral Docker container (`postgres:15-alpine` on port 5433) and run 105 tests |
| `BLK-EXT-002` | **External Paid AI Provider Live Invocations** | AI / Transcriber / Dubbing | Medium | Financial Spend Ceiling; Read-Only Benchmark Mode; Offline Isolation | Live Groq API key, Gemini API key, ElevenLabs key, Pexels API key with billing enabled | Execute smoke test with $1.00 budget cap using pre-allocated developer sandbox credits |
| `BLK-MED-001` | **4K CPU Face-Tracking Latency Benchmark (Full-Length)** | Media Pipeline / OpenCV | Medium | CPU Time Ceiling; Lack of 10GB+ 4K Fixture; High Turnaround | Dedicated GPU test runner (CUDA/OpenCL), 4K 60fps 60-min authentic video fixture | Run offline benchmark script on GPU-enabled workstation with proxy downscaling |
| `BLK-AUD-001` | **Physical Hardware Audio Playback Auditioning** | Audio / Dubbing / SFX | Low | Headless Execution Environment; Lack of Physical Listening Station | Human QA tester, calibrated audio monitoring headphones/DAC | Human sensory listening sign-off across 10 sample rendered video files |

---

## 3. Comprehensive Detailed Blocked Item Profiles

---

### Blocked Item `BLK-EXT-001`: Live YouTube OAuth Exchange & Shorts Publication

| Field | Detailed Audit Specification |
|---|---|
| **Blocked ID** | `BLK-EXT-001` |
| **Subsystem / Operation** | Multi-Channel YouTube Publishing (`backend/services/publisher.py`, `backend/tasks/clip_tasks.py:publish_clip_task`) |
| **Category** | External Integration / Live Mutation Boundary |
| **Severity / Impact** | **High** (Core value-stream delivery milestone: publishing generated Shorts to YouTube) |
| **Why Not Tested** | In strict accordance with the Mandatory Engineering Rules (Rule 0.3: *Preserve Working Functionality & Safe Operations*) and the Master Audit Specification (§15: *Do not make real YouTube/Google account mutations; do not upload or publish media*), live network requests to Google OAuth and YouTube Data API endpoints are intercepted and blocked by the pytest socket guard fixture. Mutating real user channels during an audit is strictly prohibited. |
| **What WAS Tested & Verified** | 1. *OAuth Data Model & Token Persistence:* File paths, JSON schemas, and pre-upload identity validation (`client.channels().list(mine=True)`) verified in `publisher.py:80–87`.<br>2. *Frontend Publishing Workstation:* UI simulator, metadata inputs, tags, and queue cards verified in `app/publish/page.tsx` (114 passing frontend tests).<br>3. *Publishing Privacy Hardening Suite:* All 53 unit tests in `backend/tests/test_publishing_privacy_hardening.py` executed live and passed, proving that API endpoints and Celery tasks reject public publishing and enforce private publication. |
| **Required Environment & Permissions** | 1. Google Cloud Console Project with YouTube Data API v3 enabled.<br>2. Registered OAuth 2.0 Client ID and Client Secret configured in `settings.YOUTUBE_CLIENT_ID` and `settings.YOUTUBE_CLIENT_SECRET`.<br>3. Active Google Account with an established YouTube channel authorized for video uploads.<br>4. Live interactive web browser session for human OAuth consent consent screen traversal.<br>5. Outbound HTTPS network socket access to `accounts.google.com` and `www.googleapis.com`. |
| **Action to Close Verification Gap** | 1. Provision an isolated "ClipForge Staging Sandbox" Google Cloud project and dedicated test YouTube channel (`ClipForge-Test-Sandbox-Channel`).<br>2. Author a standalone verification script `backend/scripts/verify_live_publishing_sandbox.py` configured with `is_test=True`.<br>3. Execute a single, watermarked 5-second test video upload set to `privacyStatus="private"`.<br>4. Inspect YouTube Studio API response, capture the returned Video ID (`video_id = resp["id"]`), and verify private visibility.<br>5. Immediately delete the uploaded test video via API to maintain zero permanent footprint. |

---

### Blocked Item `BLK-DB-001`: PostgreSQL Disposable DB Test Suite (105 Tests)

| Field | Detailed Audit Specification |
|---|---|
| **Blocked ID** | `BLK-DB-001` |
| **Subsystem / Operation** | Automated Database & Migration Integration Test Suites requiring `disposable_pg_db` fixture |
| **Category** | Database Integration / Container Isolation |
| **Severity / Impact** | **Medium** (105 out of 748 backend tests ($\sim 14.0\%$) deferred) |
| **Why Not Tested** | 7 backend test suites rely on pytest fixture `disposable_pg_db` (defined in `backend/tests/conftest.py`). This fixture executes `CREATE DATABASE test_db_...`, runs Alembic migrations, and executes `DROP DATABASE` on teardown. Executing these tests against the default local Docker container risked disrupting operational database schemas or exhausting connection pools during an active read-only audit run. |
| **Affected Suites & Test Counts** | 1. `backend/tests/test_c03_data_layer.py`: 12 tests<br>2. `backend/tests/test_phase13_auto_pilot.py`: 18 tests<br>3. `backend/tests/test_publishing_multi_destination.py`: 16 tests<br>4. `backend/tests/test_upload_studio_phase1.py`: 14 tests<br>5. `backend/tests/test_upload_studio_phase2.py`: 15 tests<br>6. `backend/tests/test_channel_destinations_api.py`: 15 tests<br>7. `backend/tests/test_db_migration_phase14.py`: 15 tests<br>*(Total Deferred: exactly 105 tests)* |
| **What WAS Tested & Verified** | 1. *Model Declarations:* All 31 SQLAlchemy models parsed and inspected dynamically via `Base.__subclasses__()`.<br>2. *Migration Linearity:* All 26 Alembic migration scripts from `34087f10bf78` to `e6f7a8b9c0d1` parsed and audited; verified 1 root, 0 branches, 1 head.<br>3. *Schema & Privacy Tests:* 53 tests in `test_publishing_privacy_hardening.py` and 44 tests in `test_phase_1_3_storage_cleanup.py` executed live and passed.<br>4. *Read-Only Introspection:* Live database connectivity, table listings, and schema integrity verified via read-only introspection scripts. |
| **Required Environment & Permissions** | 1. Ephemeral PostgreSQL service instance running on non-standard port (e.g. `localhost:5433`).<br>2. PostgreSQL superuser credentials (`postgres:postgres`) permitting dynamic `CREATE DATABASE` and `DROP DATABASE`.<br>3. Environment variable `TEST_DATABASE_URL=postgresql://postgres:postgres@localhost:5433/template_test_db`. |
| **Action to Close Verification Gap** | 1. Launch an isolated temporary PostgreSQL container:
```powershell
docker run -d --name clipforge-test-pg -p 5433:5432 -e POSTGRES_PASSWORD=postgres postgres:15-alpine
```
2. Execute the 7 deferred test suites targeting port 5433:
```powershell
$env:TEST_DATABASE_URL="postgresql://postgres:postgres@localhost:5433/test_db"
pytest backend/tests/test_c03_data_layer.py backend/tests/test_phase13_auto_pilot.py backend/tests/test_publishing_multi_destination.py backend/tests/test_upload_studio_phase1.py backend/tests/test_upload_studio_phase2.py backend/tests/test_channel_destinations_api.py backend/tests/test_db_migration_phase14.py
```
3. Record pass/fail metrics and terminate the ephemeral container (`docker rm -f clipforge-test-pg`). |

---

### Blocked Item `BLK-EXT-002`: External Paid AI Provider Live Invocations

| Field | Detailed Audit Specification |
|---|---|
| **Blocked ID** | `BLK-EXT-002` |
| **Subsystem / Operation** | Third-party generative AI, cloud transcription, voice synthesis, and stock video integrations (`Groq Whisper`, `Gemini Flash`, `ElevenLabs`, `Pexels API`) |
| **Category** | External Integration / Financial Boundary |
| **Severity / Impact** | **Medium** (Moment scoring, cloud speech recognition, multi-language dubbing) |
| **Why Not Tested** | In strict accordance with Master Specification §15 (*Do not call real paid AI/TTS/translation/stock providers unnecessarily*), live API calls to paid external services were mocked or stubbed. Running hundreds of test iterations against live paid APIs would incur monetary costs, exhaust rate quotas, and create non-deterministic test failures if external network services fluctuate. |
| **What WAS Tested & Verified** | 1. *Local Whisper Pipeline:* Whisper execution using local weights (`tiny`, `base`) verified without external network calls.<br>2. *Scoring Contract & AI-Only Invariant:* In `clip_scorer.py:230`, verified that if AI scoring returns an error, the system raises `RuntimeError` and refuses heuristic fallback.<br>3. *Client Request Formatting:* Request payloads, prompt structures, error handling, and response schema parsing verified via mocked integration suites (`test_c10_dubbing_pipeline.py`, `test_audit_coverage_reconciliation.py`). |
| **Required Environment & Permissions** | 1. Active developer accounts with valid API keys for Groq, Google AI Studio (Gemini), ElevenLabs, and Pexels.<br>2. Pre-funded API credit balances ($5.00 minimum across providers).<br>3. Environment variables configured: `GROQ_API_KEY`, `GEMINI_API_KEY`, `ELEVENLABS_API_KEY`, `PEXELS_API_KEY`.<br>4. Unrestricted outbound HTTPS internet access. |
| **Action to Close Verification Gap** | 1. Set up a dedicated developer sandbox environment with hard credit limits ($2.00 spend cap per provider).<br>2. Run a standalone smoke test script `backend/scripts/smoke_test_ai_providers.py` using a single 15-second audio fixture (`tests/fixtures/sample_audio_15s.wav`).<br>3. Verify:
   - Groq Whisper returns accurate word-level transcription timestamps.
   - Gemini returns valid JSON moment candidates with scores between 0 and 100.
   - ElevenLabs returns a valid MP3 audio stream for a 5-word dubbing sample.
   - Pexels returns valid video URL links for query `"podcast studio"`.
4. Document the exact HTTP status codes, latency, and response schemas. |

---

### Blocked Item `BLK-MED-001`: 4K CPU Face-Tracking Latency Benchmark (Full-Length)

| Field | Detailed Audit Specification |
|---|---|
| **Blocked ID** | `BLK-MED-001` |
| **Subsystem / Operation** | Full-length 4K (3840x2160) video face detection and intra-shot trajectory calculation (`advanced_podcast_engine.py:analyze_podcast_shots_task`) |
| **Category** | Media Processing / Performance Capability |
| **Severity / Impact** | **Medium** (Long-running processing time on high-resolution source media) |
| **Why Not Tested** | Full-length (60-minute) 4K 60fps media files require processing 216,000 video frames. Sampling at `intra_sample_fps=4.0` yields 14,400 analyzed frames. On CPU-only workstation hardware, running Haar cascade face detection across 14,400 4K frames would take several hours and exceed test runner timeouts. Furthermore, multi-gigabyte 4K media files are excluded from Git repository storage. |
| **What WAS Tested & Verified** | 1. *Real Media Smoke Tests:* Verified on authentic 1080p and 720p media fixtures (`tests/fixtures/test_podcast.mp4` and `tests/fixtures/real_podcast_multi_speaker_sample.mp4`).<br>2. *Algorithmic Integrity:* Verified face detection coordinates, exponential smoothing (`alpha=0.20`), deadband filtering (`deadband=0.02`), and cut snapping across 75 passing podcast unit tests.<br>3. *Parity Geometry:* Verified 1080x960 split and single-speaker focus geometries on 4K coordinate inputs via `test_podcast_geometry_parity.py`. |
| **Required Environment & Permissions** | 1. Dedicated GPU workstation equipped with NVIDIA GPU (RTX 3080 or better) with CUDA 12.x and cuDNN enabled.<br>2. OpenCV compiled with CUDA support (`opencv-python` with CUDA bindings).<br>3. Authentic 4K test asset: 10-minute 3840x2160 ProRes or H.264 podcast sample (stored in external test bucket). |
| **Action to Close Verification Gap** | 1. Implement proxy downscaling (Issue `FS-MED-001` Approach B): downscale 4K frames to 540p prior to Haar detection, normalizing coordinates back to 4K dimensions.<br>2. Execute benchmark script `backend/scripts/benchmark_4k_face_tracking.py` recording total execution seconds, average FPS, CPU utilization, and peak RAM consumption.<br>3. Confirm that processing speed achieves >= 1.0x real-time (<= 600s for a 10-minute clip). |

---

### Blocked Item `BLK-AUD-001`: Physical Hardware Audio Playback Auditioning

| Field | Detailed Audit Specification |
|---|---|
| **Blocked ID** | `BLK-AUD-001` |
| **Subsystem / Operation** | Subjective audio quality, speech intelligibility, SFX ducking smoothness, and acoustic artifacts in final rendered clips |
| **Category** | Quality Assurance / Human Sensory Validation |
| **Severity / Impact** | **Low** (Automated checks verify stream headers and decibel levels, but cannot perceive subjective acoustic quality) |
| **Why Not Tested** | The automated audit execution environment operates headlessly without physical human audio monitoring or hardware speaker/headphone transducers connected. |
| **What WAS Tested & Verified** | 1. *FFprobe Stream Auditing:* Verified presence of stereo AAC audio streams at 44.1kHz / 48kHz with continuous non-zero bitrates.<br>2. *Silent Channel Detection:* Executed `astats` audio filter to verify RMS level is above noise floor and audio is not muted.<br>3. *Filtergraph Continuity:* Verified audio filter chains: `[0:a]atrim=start={clip_start}:end={clip_end},asetpts=PTS-STARTPTS[outa]`. |
| **Required Environment & Permissions** | 1. QA Workstation equipped with calibrated studio monitoring headphones or near-field reference monitors.<br>2. Human QA engineer conducting structured listening tests. |
| **Action to Close Verification Gap** | 1. Generate 5 sample rendered clips across Standard Stacked Split, Single Speaker, and Advanced Podcast modes.<br>2. Conduct a human listening audit using a standardized QA checklist:
   - Voice clarity and frequency balance.
   - Absence of audio pops, clicks, or phase cancellation at cut boundaries.
   - Smooth ducking of background music / SFX beneath spoken dialogue (-18dB ducking).
3. Record signed listening QA approval log. |

---

## 4. Reconciliation with System Readiness

The existence of these **5 blocked verification items** does NOT indicate software defects. Rather, they demarcate the exact boundary between **hermetic, non-destructive audit verification** and **live production operational deployment**.

In Deliverable P (*System Readiness Statement*), these items are directly integrated into the readiness determination, correctly categorizing the application as **Partially Verified with Named Gaps**:
- **Workstation Local Processing:** **100% Functionally Verified** (E6).
- **External Publishing & Cloud Services:** **Verified at Contract Layer (E1/E2)**; requires staging sandbox authorization to advance to E6.
