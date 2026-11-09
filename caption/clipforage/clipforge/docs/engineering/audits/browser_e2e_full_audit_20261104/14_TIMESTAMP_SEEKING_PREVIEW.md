# Milestone M3 Audit Deliverable 14: Timestamp-Specific Frame Seeking & Decoded Frame Previews Audit

**Document ID**: `CLIPFORGE-AUDIT-20261104-14-FRAME-SEEKING`  
**Audit Target**: Video Frame Seeking Endpoint, Fast Decoding & Frontend Scrubber Preview  
**Milestone**: M3 — Media Pipeline & Celery Backend Execution  
**Auditor / Agent**: `browser_worker_m3`  
**Repository Working Directory**: `d:\automation video clips\clipforge`  
**Verification Date**: 2026-11-04  
**Audit Status**: **PASS — FULLY VERIFIED**  

---

## 1. Executive Summary & Verification Scope

A critical requirement of the ClipForge Acceptance QA Audit is verifying that video timestamp seeking in the interactive UI displays **genuine, freshly decoded video frames** rather than static placeholder images or simulated mock responses.

This deliverable audits the dedicated frame extraction API:
`GET /api/videos/{video_id}/frame?timestamp={timestamp}&shot_id={shot_id}`
across its security boundaries, FFmpeg fast-seek mechanics, multi-tier caching hierarchy, and frontend scrubber integration in `PodcastSelectionModal.tsx`.

Verification included direct live HTTP interrogation against `http://127.0.0.1:8000`, validation of cache HIT/MISS states, adversarial boundary testing (negative, infinite, NaN, out-of-bounds), and automated test execution of `test_podcast_frame_preview.py`.

---

## 2. API Endpoint Architecture & Security Boundaries

Source: `clipforge/backend/api/routes/videos.py:793-1010`

### 2.1 Identifier Sanitization & Directory Traversal Protection
```python
if not re.match(r"^[a-zA-Z0-9_\-]{1,64}$", video_id):
    raise HTTPException(status_code=400, detail="Invalid video_id identifier format.")
```
- Restricts `video_id` strictly to alphanumeric characters, dashes, and underscores (max 64 chars).
- Rejects path traversal tokens (`..`, `/`, `\`), preventing arbitrary filesystem reads.
- Verifies canonical filesystem containment: Resolves physical path via `resolved_path.resolve()` and asserts it is contained within `settings.UPLOAD_DIR`, `settings.BASE_DIR`, or current working directory.

### 2.2 Numerical Bounds & Finite Float Validation
```python
if not math.isfinite(timestamp):
    raise HTTPException(status_code=400, detail="Timestamp must be a finite numeric value.")
if timestamp < 0.0:
    raise HTTPException(status_code=400, detail="Timestamp must be non-negative (>= 0.0).")
if timestamp > 86400.0:
    raise HTTPException(status_code=400, detail="Timestamp exceeds maximum allowed media duration (86400s).")
```
- Mathematical Validation: Rejects `NaN`, `Infinity`, `-Infinity`.
- Non-Negative Guard: Rejects negative time offsets (`timestamp < 0.0`).
- Global Ceiling: Rejects timestamps exceeding 24 hours (86,400s).
- Video-Specific Duration Guard: Interrogates database `Video.duration`; if `timestamp > video.duration + 0.5s`, returns `HTTP 400 Bad Request: "Requested timestamp X.XXs exceeds video duration Y.YYs."`

---

## 3. FFmpeg Fast-Seek & Frame Extraction Mechanics

### 3.1 Input Seeking (`-ss` before `-i`)
When extracting a single decoded frame, placing `-ss` before `-i` instructs FFmpeg to utilize container keyframe indexes for near-instant seeking to the nearest keyframe, decoding only the few intervening frames up to the exact requested timestamp:

```python
ffmpeg_cmd = [
    "ffmpeg", "-y", "-nostdin",
    "-protocol_whitelist", "file",
    "-ss", f"{timestamp:.3f}",
    "-i", str(resolved_path),
    "-vframes", "1",
    "-q:v", "2",
    "-f", "image2",
    str(tmp_path)
]
```

### 3.2 Security & Process Execution Flags
- `-y`: Overwrites temporary file without prompting.
- `-nostdin`: Disables standard input interaction, preventing daemon deadlocks.
- `-protocol_whitelist file`: Strictly locks FFmpeg to local filesystem protocol, neutralizing SSRF or network injection vectors.
- `-vframes 1`: Decodes exactly one single frame.
- `-q:v 2`: High-quality JPEG quantization (preserving facial landmarks).
- `-f image2`: Direct image container format.
- Subprocess Timeout: Wrapped in `asyncio.wait_for(..., timeout=8.0)`. If FFmpeg hangs for 8 seconds, the process is killed (`proc.kill()`) and returns `HTTP 504 Gateway Timeout`.
- Atomic Rename: Writes to `tmp_path` and renames to `cache_file` via `tmp_path.replace(cache_file)` to ensure concurrent requests never read incomplete frames.

---

## 4. Multi-Tier Caching Hierarchy

1. **Filesystem Cache**:
   - Location: `{settings.UPLOAD_DIR}/frame_cache/{video_id}/{timestamp:.3f}.jpg`
   - Hit Condition: If cache file exists and `file.stat().st_size > 0`, returns immediately without spawning FFmpeg subprocess.
2. **HTTP Response Headers**:
   - `X-Frame-Timestamp`: Target timestamp rounded to 3 decimal places.
   - `X-Source-Id`: Normalized `video_id`.
   - `X-Frame-Cache`: Emits `HIT` on cache hit; emits `MISS` when extracted via FFmpeg.
   - `Cache-Control`: `public, max-age=3600` (browser caching for 1 hour).
   - `Content-Type`: `image/jpeg`.

---

## 5. Frontend Scrubber Integration & Race Cancellation

Source: `clipforge/frontend/components/PodcastSelectionModal.tsx:51-58, 150-224`

### 5.1 Scrubber Scrubbing & AbortController
During interactive playback or manual timeline scrubbing, users trigger rapid successive timestamp seeking:
- `abortControllerRef`: Every new timestamp scrub cancels previous pending in-flight HTTP requests (`abortController.abort()`), eliminating network congestion and out-of-order UI frame displays.
- Client-Side Object URL Cache (`frameCacheRef`): Caches downloaded frame blobs in memory. Subsequent scrubs across visited timestamps render instantly without network roundtrips.
- Lifecycle Cleanup: Upon modal unmount, `useEffect` cleanups iterate through `frameCacheRef` and revoke all created object URLs via `URL.revokeObjectURL()`, preventing browser memory leaks.

---

## 6. Live Verification Evidence & Test Execution

### 6.1 Live HTTP Interrogation Results
Executed live queries against `http://127.0.0.1:8000` using video `d34750ad-f9e8-44ce-bbc3-2941c91073dd` (raw JSON evidence in `evidence/frame_seeking_validation.json`):

| Test Case | Request URL | HTTP Status | Response Header / Error Detail | Verification Finding |
|---|---|---|---|---|
| **Initial Seek** | `.../frame?timestamp=12.5` | `200 OK` | `X-Frame-Cache: MISS`, `Content-Length: 13259` | Decoded genuine JPEG frame via FFmpeg |
| **Cached Seek** | `.../frame?timestamp=12.5` | `200 OK` | `X-Frame-Cache: HIT`, `Content-Length: 13259` | Instant cache hit (< 5ms response time) |
| **Existing Timestamp** | `.../frame?timestamp=5.0` | `200 OK` | `X-Frame-Cache: HIT`, `Content-Length: 13085` | Validated decoded JPEG frame |
| **Negative Offset** | `.../frame?timestamp=-1.0` | `400 Bad Request` | `{"detail":"Timestamp must be non-negative (>= 0.0)."}` | Bounds validation enforced |
| **Extreme Ceiling** | `.../frame?timestamp=99999.0` | `400 Bad Request` | `{"detail":"Timestamp exceeds maximum allowed media duration (86400s)."}` | Global ceiling enforced |
| **Exceed Video Duration** | `.../frame?timestamp=50.0` | `400 Bad Request` | `{"detail":"Requested timestamp 50.00s exceeds video duration 20.00s."}` | Dynamic duration boundary enforced |
| **Malformed NaN** | `.../frame?timestamp=NaN` | `400 Bad Request` | `{"detail":"Timestamp must be a finite numeric value."}` | Finite float enforcement verified |

### 6.2 Test Suite Execution
- **`pytest backend/tests/test_podcast_frame_preview.py -v`**: All tests passed (100% pass rate).
- **`npm test --prefix clipforge/frontend`**:
  - `test/podcast_selection_modal.test.mjs`:
    - `Frame preview endpoint client integration and status badge`: PASSED
    - `Shot table row keyboard accessibility and race cancellation`: PASSED

---

## 7. Audit Conclusion & Compliance Verdict

- **Deliverable 14 Assessment**: **100% PASS — COMPLIANT**.
- The timestamp frame preview endpoint decodes authentic video frames via FFmpeg `-ss` input seeking and `-vframes 1`.
- Multi-tier caching (`X-Frame-Cache: HIT/MISS`) guarantees high performance, while rigorous bounds checking prevents invalid time queries and path traversal attacks.
- Frontend integration safely manages in-flight request cancellation and object URL lifecycle.
