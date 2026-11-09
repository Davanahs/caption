# Verification Report: PODCAST-PREVIEW-FRAME-002
## Timestamp-Accurate Source-Frame Preview

**Document:** `reports/06_PODCAST_PREVIEW_FRAME.md`  
**Work Item:** `PODCAST-PREVIEW-FRAME-002`  
**Timestamp:** 2026-11-04T02:22:00+05:30  
**Evaluator:** ClipForge Autonomous Verification Lead (Gravitas Reliability Runtime)  

---

### 1. Disposition
**DELIVERED & VERIFIED** (100% Complete).

---

### 2. Objective & Architectural Trace
Provide real source-video frame extraction at arbitrary shot timestamps to replace generic placeholders and thumbnails, with complete protection against SSRF, path traversal, command injection, and unbounded compute.

#### Architecture:
- **Endpoint:** `GET /api/videos/{video_id}/frame`
- **Query Parameters:** `timestamp: float` (required), `shot_id: Optional[int]` (optional)
- **Response:** `FileResponse` with MIME `image/jpeg`, `X-Frame-Cache` (`MISS` / `HIT`), and `X-Frame-Timestamp`.

---

### 3. Security & Boundary Hardening
1. **Identifier Validation (SSRF & Traversal Guard):**
   - Identifier is strictly validated against `^[a-zA-Z0-9_\-\.]+$` and rejects `".."`, `"/"`, `"\\"`, and metacharacters.
   - Remote URL schemes (e.g. `http://169.254.169.254`) and shell metacharacters are rejected with HTTP 400.
2. **Numeric Timestamp Bounds:**
   - Rejects NaN, $\pm\infty$, and negative timestamps (`timestamp < 0.0`).
   - Validates timestamp against database `video.duration`; requests exceeding duration return HTTP 400.
3. **Storage Root Containment:**
   - Source video paths must resolve strictly within `settings.UPLOAD_DIR` or registered storage paths.
4. **Subprocess Sandboxing & Timeout:**
   - Invokes FFmpeg via `asyncio.create_subprocess_exec` (zero shell interpolation).
   - Enforces `-protocol_whitelist file`, `-nostdin`, `-ss`, `-vframes 1`, `-q:v 2`.
   - Hard execution timeout: 8.0s (`asyncio.wait_for`).
5. **Deterministic Cleanup & Caching:**
   - Temporary frames created via `tempfile.mkstemp` with guaranteed unlinking in `finally:` block.
   - Verified frames cached in `uploads/frame_cache/{video_id}/frame_{timestamp:.3f}.jpg` with HTTP Cache-Control headers.

---

### 4. Empirical Test Suite Evidence (`test_podcast_frame_preview.py`)
- **Command:** `python -m pytest backend/tests/test_podcast_frame_preview.py -v`
- **Result:** **8 passed, 6 warnings in 4.55s** (Exit code: 0)
- **Scenarios Verified:**
  1. `test_frame_preview_invalid_video_id_rejected`: Path traversal and metacharacter injection return 400/404.
  2. `test_frame_preview_invalid_timestamp_rejected`: Negative, NaN, and $> \text{duration}$ return 400; non-numeric returns 422.
  3. `test_frame_preview_nonexistent_asset_returns_404`: Non-existent assets return 404.
  4. `test_frame_preview_extraction_and_caching`: Generates real JPEG bytes; validates `MISS` followed by `HIT`.
  5. `test_frame_preview_respects_db_video_duration`: Enforces DB duration limit (requesting 8.0s on 5.0s video returns 400).
  6. `test_frame_preview_exact_start_boundary`: 0.0s start boundary extracts cleanly.
  7. `test_frame_preview_remote_url_rejected_as_id`: SSRF attempts targeting cloud metadata or localhost return 400/404.
  8. `test_frame_preview_temp_cleanup`: Confirms zero dangling temporary extraction files remain.

---

### 5. Progress & Completion Rating
- **Pre-Task Estimate:** 0% complete / 100% pending
- **Post-Verification Actual:** **100% complete** / 0% pending
- **Status:** Closed and fully verified.

