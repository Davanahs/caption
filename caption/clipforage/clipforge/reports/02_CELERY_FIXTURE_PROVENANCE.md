# Verification Report: CELERY-FIXTURE-PROVENANCE-008
## Media Provenance and Source Acquisition Hardening

**Document:** `reports/02_CELERY_FIXTURE_PROVENANCE.md`  
**Work Item:** `CELERY-FIXTURE-PROVENANCE-008`  
**Timestamp:** 2026-11-04T02:18:25+05:30  
**Evaluator:** ClipForge Autonomous Verification Lead (Gravitas Reliability Runtime)  

---

### 1. Disposition
**DELIVERED & VERIFIED** (100% Complete).

---

### 2. Objective & Architectural Trace
The objective is to establish deterministic proof of which media the Celery worker decodes, preventing unintentional substitution of synthetic media in production and verifying fast-failure on corrupt or missing inputs.

#### Complete Source Path Trace:
1. **API / Job Input:** Client supplies `url` (or uploads video file).
2. **Database Persistence:**
   - In `backend/tasks/video_tasks.py` (`download_task`), `is_test` authorization is strictly derived from database records (`job_rec.is_test` or `ch_rec.is_test`).
   - Substring matching on words like "test", "mock", or "synthetic" in URLs or titles is strictly prohibited and absent from the code.
3. **Celery Task Args & Resolver (`analyze_podcast_shots_task`):**
   - **Step A (Local Direct):** If `candidate_direct = Path(url)` is a file, resolves directly to canonical absolute path (`local_direct`).
   - **Step B (Local Upload):** If `url` is relative, checks `settings.UPLOAD_DIR` and `uploads/`. Guards against path traversal via `".." not in Path(url).parts` and `.is_relative_to(upload_dir)`. Resolves as `local_upload`.
   - **Step C (YouTube / Download):** If not a local file, checks `extract_youtube_id(url)`. If cached `{yt_id}.mp4` exists in uploads, resolves as `cached_youtube`. Otherwise, invokes `download_video(url, video_id=f"analysis_{yt_id}")` as `downloaded_youtube`.
   - **Fast Rejection:** If not a local file and not a valid YouTube URL, immediately raises `FileNotFoundError`. If file size is 0, raises `ValueError`.
4. **Decode Boundary Verification:**
   - Prior to decode/downstream scene detection, `analyze_podcast_shots_task` reads the exact binary stream, hashes it with SHA-256, checks byte size, and emits a structured `provenance` metadata record:
     ```json
     {
       "source_type": "local_direct" | "local_upload" | "cached_youtube" | "downloaded_youtube",
       "resolved_path": "/path/to/media.mp4",
       "sha256": "<64-char-hex>",
       "size_bytes": 123456,
       "video_id": "<id>"
     }
     ```

---

### 3. Canonical Local Test Fixture Provenance
- **Canonical Path:** `d:\automation video clips\clipforge\uploads\synthetic_test_fixture.mp4`
- **File Size:** `317,936 bytes`
- **SHA-256 Hash:** `0705329F6433AB657A924B03E2F1FE415EDF69E5ED03565B801A96DF106E60F6`
- **FFprobe Inspection:**
  - Video: H.264, 640x360, 30 fps
  - Audio: AAC, stereo
  - Duration: 20.000000s
  - Bitrate: 127,174 bps

---

### 4. Empirical Test Suite Evidence (`test_celery_fixture_provenance.py`)
- **Command:** `python -m pytest backend/tests/test_celery_fixture_provenance.py -v`
- **Result:** **10 passed, 1 warning in 1.81s** (Exit code: 0)
- **Scenarios Verified:**
  1. `test_local_direct_provenance`: Direct local path reads exact SHA-256 and byte size without calling downloader.
  2. `test_local_upload_relative_provenance`: Relative path in `uploads/` resolves securely without calling downloader.
  3. `test_youtube_url_invokes_downloader_without_local_fallback`: YouTube URL downloads with correct `video_id` and does not hijack synthetic fixture.
  4. `test_cached_youtube_url_uses_cache_without_downloader`: Cached YouTube video reuses existing upload file.
  5. `test_missing_file_fails_fast_before_downstream_work`: Missing file raises `FileNotFoundError` before downstream scheduling.
  6. `test_corrupt_empty_file_fails_fast`: 0-byte file raises `ValueError` before scene detection.
  7. `test_invalid_url_not_youtube_and_not_file_fails_fast`: Arbitrary invalid URL fails fast without network attempts.
  8. `test_path_traversal_attempt_fails_fast`: Path traversal attacks (`../../etc/passwd`) are rejected.
  9. `test_celery_task_registration_and_signature`: Confirms `analyze_podcast_shots_task` is registered in Celery app registry.
  10. `test_historical_task_provenance_root_cause_audit`: Audits Redis DB 1 historical task `4a905c3c-ad6b-4f8a-9319-5a57ece28204`.

---

### 5. Historical Task Audit
- **Task ID:** `4a905c3c-ad6b-4f8a-9319-5a57ece28204`
- **Finding:** Historical task succeeded prior to provenance hardening; the regex extracted `synthetic_t` from `synthetic_test_fixture`, which fell back to the synthetic file in `possible_paths`. With the hardened implementation, full cryptographic provenance is recorded in the task metadata, and untrusted inputs can never silently fall back to synthetic files.

---

### 6. Progress & Completion Rating
- **Pre-Task Estimate:** 0% complete / 100% pending
- **Post-Verification Actual:** **100% complete** / 0% pending
- **Status:** Closed and fully verified.

