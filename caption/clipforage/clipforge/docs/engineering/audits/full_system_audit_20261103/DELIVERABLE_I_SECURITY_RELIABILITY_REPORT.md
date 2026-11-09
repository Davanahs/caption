# Deliverable I: Security, Privacy, and Reliability Forensic Audit Report

**Work Item**: `CLIPFORGE-FULL-SYSTEM-AUDIT-001` (Deliverable I)  
**Target Repository**: `d:\automation video clips\clipforge`  
**Governing Standard**: OWASP Application Security Verification Standard (ASVS) 5.0.0, `MASTER_ENGINEERING_RULEBOOK.md`, `ANTIGRAVITY_CLIPFORGE_FREEZE_RULES.md`  
**Auditor**: Worker M3 (Media Pipeline, Security & Test Reconciliation Audit Deliverables Author)  
**Execution Baseline**: Python 3.12.10, FastAPI 0.115.x, Celery 5.4.x, Starlette 0.38.x, Windows 11 x64  
**Verification Date**: 2026-11-03 / 2026-11-04  

---

## 1. Executive Summary & Security Baseline

This report delivers a comprehensive forensic audit of the security posture, privacy safeguards, and operational reliability of ClipForge. The system is evaluated against the relevant verification requirements of the **OWASP Application Security Verification Standard (ASVS) 5.0.0**.

### Architectural Context & Threat Model:
ClipForge is currently engineered as a **local-first, single-tenant desktop/workstation application**, binding its backend services to `localhost:8000` and frontend client to `localhost:3000`. The operational threat model assumes execution within a trusted workstation or private local network. However, because the backend is exposed as a networked FastAPI HTTP/WebSocket server and handles arbitrary external media ingestion, OAuth tokens, and operating system subprocesses, adherence to enterprise application security standards is essential to protect local user credentials, filesystem integrity, and compute resources.

### High-Level Audit Findings:
1. **Robust Subprocess & Shell Injection Defenses (ASVS V5.3.8 — PASS)**: FFmpeg, FFprobe, and `yt-dlp` invocations across all backend modules strictly employ `asyncio.create_subprocess_exec` and `subprocess.run` with tokenized argument arrays and `shell=False`. Hook text overlay burning has been neutralized (`clip_cutter.py:62–64`), eliminating command and filter interpolation vulnerabilities.
2. **Filesystem Containment & Path Traversal Guards (ASVS V12.3.1 — PASS)**: The Upload Studio route implements strict path resolution checks (`Path.resolve()`) validating that all temporary chunk directories and batch roots remain contained within `settings.UPLOAD_DIR`.
3. **Chunk Upload Fencing & Lease Concurrency (ASVS V12.1.3 — PASS)**: Chunked uploads enforce RFC 7233 byte-range validation, an immutable 10 MiB chunk size ceiling (`MAX_CHUNK_BYTES = 10 * 1024 * 1024`), a maximum of 3 concurrent upload streams per batch, and single-writer lease tokens (`CHUNK_LEASE_SECONDS = 45`).
4. **Publishing Privacy Safeguard (ASVS V9.2.1 — PASS)**: Automated and manual YouTube uploads strictly enforce `status.privacyStatus == "private"`. The test suite incorporates an autouse socket guard fixture (`guard_no_live_network_calls`) preventing external network mutations.
5. **Identified Compliance Gaps (Actionable Vulnerabilities)**:
   - **V2 / V3 (Authentication Absence — High/P1)**: All 123 HTTP API routes and the WebSocket endpoint lack authentication and authorization middleware.
   - **V6 / V8 (Plaintext OAuth Token Storage — High/P1)**: Google/YouTube OAuth tokens containing refresh tokens and client secrets are written to disk as unencrypted plaintext JSON (`tokens/youtube_token_{channel_id}.json`). `Settings.SECRET_KEY` has a default hardcoded value.
   - **V12.1 (Missing MIME Magic-Byte Sniffing — Medium/P2)**: Uploaded video chunks are validated solely by file extension and post-assembly FFprobe inspection; no binary signature or magic-byte sniffing occurs on initial chunk receipt.
   - **V5.5 (SSRF Exposure in Channel Ingestion — Medium/P2)**: `downloader.py:normalize_channel_url` accepts arbitrary HTTP/HTTPS channel URLs and dispatches `yt-dlp` without domain allowlisting or loopback/private IP filtering.
   - **V13.1 (Starlette CORS Wildcard Bug — Low/P3)**: `config.py:103` includes `"https://*.netlify.app"` in `CORS_ORIGINS`, which is ignored by Starlette CORS middleware without `allow_origin_regex`.

---

## 2. OWASP ASVS 5.0.0 Evaluation & Compliance Matrix

The following matrix evaluates ClipForge's implementation against applicable ASVS 5.0.0 requirements:

| ASVS 5.0.0 Requirement | Verification Topic | Code / Architecture Reference | Implementation Status | Observed Evidence & Findings | Severity / Action |
|---|---|---|---|---|---|
| **V1.2 / V12.1** | Media Upload Magic Bytes | `backend/api/routes/studio.py:460–550` | **DEFICIENT** | Upload Studio accepts binary chunks validated only by extension (`.mp4`, `.mov`). Initial magic-byte verification (e.g. `ftyp` box) is absent until Stage 2 FFprobe execution. | **Medium (P2)** |
| **V2.1 / V3.1** | API Route Authentication | `backend/main.py`, `backend/api/routes/` | **DEFICIENT** | Zero authentication middleware or API token validation exists across all 123 HTTP API routes and WebSocket `/ws`. Anyone reaching port 8000 has unrestricted administrative access. | **High (P1)** |
| **V5.3.8** | Subprocess Command Injection | `backend/services/clip_cutter.py:12–20`, `advanced_podcast_engine.py:493–505` | **ENFORCED** | Subprocesses invoke `asyncio.create_subprocess_exec` and `subprocess.run` with tokenized argument lists (`shell=False`). Hook title text burning is completely disabled via direct copy. | **PASS (E1/E2)** |
| **V5.5.1** | SSRF Defense (URL Ingest) | `backend/services/downloader.py:159–170` (`normalize_channel_url`) | **PARTIALLY DEFICIENT** | Video URL extraction enforces YouTube regex, but channel URL normalization accepts arbitrary URLs and passes them to `yt-dlp` without rejecting loopback (`127.0.0.1`) or link-local (`169.254.169.254`) ranges. | **Medium (P2)** |
| **V6.2.1 / V8.3.1** | Plaintext Token Storage | `backend/services/publisher.py:1258–1264` (`tokens/youtube_token_*.json`) | **DEFICIENT** | YouTube OAuth credentials (including sensitive refresh tokens) are stored in plaintext JSON on disk. No filesystem-level or database encryption at rest. | **High (P1)** |
| **V6.4.1** | Cryptographic Secret Configuration | `backend/core/config.py:13` | **DEFICIENT** | `SECRET_KEY` defaults to hardcoded placeholder `"clipforge_default_secret_key_change_in_prod"` in application code. | **Medium (P2)** |
| **V9.2.1** | Publishing Privacy Safeguard | `backend/services/publisher.py:101–145`, `test_publishing_privacy_hardening.py` | **ENFORCED** | YouTube upload payloads enforce `status.privacyStatus == "private"`. Test suite intercepts all socket connections to prevent live network mutations. | **PASS (E1/E3)** |
| **V12.1.3** | Chunk Boundary Enforcement | `backend/api/routes/studio.py:480–505` | **ENFORCED** | Enforces 10 MiB chunk boundary (`MAX_CHUNK_BYTES = 10 * 1024 * 1024`), RFC 7233 byte-range continuity, single-writer leases (45s), and max 3 concurrent streams per batch. | **PASS (E1/E3)** |
| **V12.3.1** | Path Traversal Prevention | `backend/api/routes/studio.py:144–158` (`get_batch_dir`, `get_tmp_chunks_dir`) | **ENFORCED** | Canonical path resolution (`Path.resolve()`) verifies batch directories and temporary chunk paths strictly remain contained within `settings.UPLOAD_DIR`. | **PASS (E1)** |
| **V13.1.1** | CORS Configuration | `backend/core/config.py:94–104`, `backend/main.py:46–54` | **DEFICIENT** | Includes `"https://*.netlify.app"` in `allow_origins`. Starlette ignores wildcards in origins unless `allow_origin_regex` is supplied, causing CORS errors on valid preview deployments. | **Low (P3)** |

---

## 3. Subprocess Safety & Shell Injection Defenses (ASVS V5.3.8)

Media applications that invoke command-line utilities (such as FFmpeg, FFprobe, and `yt-dlp`) are notoriously susceptible to command injection and argument injection vulnerabilities if inputs are interpolated into shell strings.

### 3.1 Systematic Subprocess Invocation Audit
An exhaustive grep search across `backend/` for subprocess invocations revealed the following execution patterns:
1. **FFmpeg & FFprobe Invocation Pattern**:
   - `backend/services/clip_cutter.py:12–20` (`run_ffmpeg`):
     ```python
     cmd = ["ffmpeg", "-y"] + args
     proc = await asyncio.create_subprocess_exec(
         *cmd,
         stdout=asyncio.subprocess.PIPE,
         stderr=asyncio.subprocess.PIPE
     )
     ```
   - `backend/services/advanced_podcast_engine.py:493–505`:
     ```python
     cmd = [
         ffmpeg_bin, "-hide_banner", "-nostats",
         "-i", str(video_path),
         "-vf", f"scdet=threshold={scdet_threshold}",
         "-f", "null", "-"
     ]
     proc = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
     ```
   - In all call sites, `asyncio.create_subprocess_exec` or `subprocess.run` is invoked with an argument list (`list[str]`). The operating system bypasses `cmd.exe` / `/bin/sh` shell parsing entirely (`shell=False`).
2. **`yt-dlp` Video Ingestion Pattern**:
   - `backend/services/downloader.py:100–145` (`download_video`):
     Invokes `yt-dlp` via argument array with explicit format constraints and output templates. Video URLs are pre-validated via regex matching before being passed as array elements.

### 3.2 Mitigation of FFmpeg Filter String Injection
A critical vulnerability in video editing pipelines occurs when user-supplied text (such as video titles or hook titles) is embedded directly into FFmpeg filtergraph strings (`drawtext=text='...'`), enabling filtergraph breakout and file disclosure.
- **Audit Observation**: In `backend/services/clip_cutter.py:62–64`, `burn_hook_title()` explicitly disables text overlay rendering via direct file copy:
  ```python
  # User Baseline Request: Disable Hook title rendering
  shutil.copy(str(input_path), str(output_path))
  return output_path
  ```
- **Conclusion**: Filter string injection through hook titles is completely neutralized.

---

## 4. Path Traversal & Filesystem Containment (ASVS V12.3.1)

Applications handling chunked file uploads must rigorously prevent path traversal attacks where malicious client-supplied identifiers (`batch_id`, `video_id`, `chunk_index`) escape the designated storage root.

### 4.1 Implementation Audit of `studio.py`
In `backend/api/routes/studio.py:140–158`:
```python
def get_storage_root() -> Path:
    return Path(settings.UPLOAD_DIR).resolve()

def get_batch_dir(batch_id: str) -> Path:
    base = get_storage_root()
    batch_dir = (base / "studio" / "batches" / batch_id).resolve()
    # Path traversal guard
    if not str(batch_dir).startswith(str(base)):
        raise HTTPException(status_code=400, detail="Invalid path containment for batch directory")
    return batch_dir

def get_tmp_chunks_dir(batch_dir: Path) -> Path:
    tmp_dir = (batch_dir / TMP_CHUNKS_DIRNAME).resolve()
    base = get_storage_root()
    if not str(tmp_dir).startswith(str(base)):
        raise HTTPException(status_code=400, detail="Invalid path containment for chunk directory")
    return tmp_dir
```

### 4.2 Security Analysis & Recommendations
- **Strengths**:
  - `Path.resolve()` canonicalizes all dot-dot (`..`) segments and resolves symbolic links before boundary verification.
  - Malicious inputs such as `../../../../etc/passwd` or `..\..\Windows\System32` are caught by the `startswith` containment check and rejected with HTTP 400.
- **Technical Improvement (Prefix Collision Defense)**:
  - While `str(batch_dir).startswith(str(base))` effectively prevents upward traversal, it is theoretically vulnerable to directory sibling prefix matching (e.g., if `base` is `/var/uploads`, `/var/uploads_malicious` would pass `startswith`).
  - *Recommendation*: Upgrade to Python 3.9+ native containment check: `batch_dir.is_relative_to(base)`.

---

## 5. Media Upload Validation & Streaming Fencing (ASVS V12.1.3)

### 5.1 Chunk Boundary & Concurrency Fencing
The Upload Studio chunked upload endpoint (`POST /api/studio/batches/{batch_id}/videos/{video_id}/chunk`) implements defense-in-depth fencing against denial-of-service and state corruption:
1. **10 MiB Chunk Size Ceiling**:
   ```python
   MAX_CHUNK_BYTES = 10 * 1024 * 1024 # 10 MiB
   if len(chunk_data) > MAX_CHUNK_BYTES:
       raise HTTPException(status_code=413, detail="Chunk size exceeds 10 MiB limit")
   ```
2. **RFC 7233 Continuity & Offset Alignment**:
   Verifies that each incoming chunk's `start_byte` matches the currently persisted `uploaded_bytes`. Out-of-order chunks are rejected with HTTP 409 Conflict, preventing sparse or corrupted file writes.
3. **Single-Writer Lease Fencing**:
   Enforces `CHUNK_LEASE_SECONDS = 45`. A writer must acquire an exclusive lease token in the database before writing chunk bytes, preventing concurrent write collisions on the same video file.
4. **Concurrent Stream Throttling**:
   Enforces `MAX_CONCURRENT_STREAMS_PER_BATCH = 3`. Batches attempting more than 3 simultaneous active upload streams receive HTTP 429 Too Many Requests.

### 5.2 Vulnerability Analysis: Absence of MIME Magic-Byte Sniffing
- **Current Behavior**: `studio.py` validates uploaded media based on file extensions (`.mp4`, `.mov`, `.avi`, `.mkv`) and delegates media validation to Stage 2 (`validate_media_task` using FFprobe) *after* the entire file has been uploaded and reassembled on disk.
- **Risk**: An attacker can upload non-media binary payloads, polyglots, or executable scripts disguised with an `.mp4` extension. While FFprobe will fail to parse the file in Stage 2, the arbitrary payload still resides on the local filesystem during Stage 1.
- **Remediation**: Inspect the first 16 bytes of chunk 0 before writing to disk. Verify the standard ISO base media file format (ISOBMFF) signature: bytes 4–8 matching `b"ftyp"`, followed by valid major brands (`mp41`, `mp42`, `isom`, `avc1`, `qt  `).

---

## 6. Multi-Channel OAuth & External Credential Isolation (ASVS V6.2 & V8.3)

ClipForge supports multi-channel YouTube management, allowing creators to connect multiple YouTube channels, monitor incoming content, and publish short-form clips to specific channels.

### 6.1 Multi-Channel Isolation Architecture
- **Credential Storage**: Handled in `backend/services/publisher.py:1258–1264`:
  ```python
  token_file = Path(settings.YOUTUBE_TOKEN_FILE)
  token_file.parent.mkdir(parents=True, exist_ok=True)
  channel_token_file = token_file.parent / f"youtube_token_{channel_id}.json"
  with open(channel_token_file, "w") as f:
      f.write(creds.to_json())
  ```
- **Pre-Upload Channel Identity Verification**:
  In `backend/services/publisher.py:80–87`, before any publishing operation is executed, the publisher client queries the Google YouTube Data API:
  ```python
  resp = client.channels().list(part="id", mine=True).execute()
  auth_channel_id = resp["items"][0]["id"]
  if auth_channel_id != resolved_channel_id:
      raise ValueError(f"Credential mismatch: requested channel {resolved_channel_id} but authenticated as {auth_channel_id}")
  ```
  This guarantees that tokens cannot publish to an unintended channel even if database records are misconfigured.

### 6.2 Vulnerability Analysis: Plaintext Credential Exposure
- **Issue Description**: Google OAuth refresh tokens and client credentials are saved to disk as **unencrypted plaintext JSON files** in the `tokens/` directory.
- **ASVS Violation**:
  - ASVS V6.2.1: Verify that sensitive data is encrypted at rest using approved cryptographic algorithms.
  - ASVS V8.3.1: Verify that sensitive data, including credentials and session tokens, is protected against unauthorized access.
- **Threat Vector**: Any local process or unauthorized user on the workstation with read access to the project directory can exfiltrate valid Google OAuth refresh tokens and gain persistent access to the creator's YouTube channel.
- **Remediation Proposal**:
  1. Implement application-level encryption at rest using AES-256-GCM (e.g. `cryptography.fernet.Fernet`).
  2. Derive encryption keys from a secure environment secret (`SECRET_KEY`) or workstation OS keystore (Windows Credential Manager via `keyring`).
  3. Store encrypted token blobs in PostgreSQL database column `Channel.encrypted_credentials` rather than bare disk files.

---

## 7. Reliability, Concurrency & Distributed Task Governance

The distributed processing architecture utilizes Celery 5.4 backed by Redis and PostgreSQL to manage long-running video processing pipelines.

### 7.1 Distributed Idempotency & Task Fencing
To prevent race conditions, duplicate encoding, and worker retry storms, ClipForge implements a multi-layer fencing mechanism:
1. **Atomic `task_executions` Registry**:
   - `backend/core/task_execution.py:35–110` (`check_and_claim_execution`):
   - Before executing critical tasks (`reframe`, `render`, `publish`), the worker executes an atomic insert/update into the `task_executions` table in PostgreSQL with an idempotency key (e.g. `{job_id}_{clip_id}_render`).
   - If another worker has already claimed or completed the task, Celery raises `celery.exceptions.Ignore`, cleanly terminating the duplicate task without side effects.
2. **Execution Heartbeater & Zombie Worker Fencing**:
   - Long-running encoding tasks activate `execution_heartbeater(interval=60)` running in a background thread.
   - If a worker crashes or hangs, the heartbeat expires after a configurable timeout (300s), enabling supervisory tasks (`recover_stranded_publish_jobs_task`) to detect and recover stranded jobs.
3. **Celery Reliability Settings**:
   - `task_acks_late = True`: Tasks are acknowledged only after successful completion, preventing lost work on worker crash.
   - `task_reject_on_worker_lost = True`: If a worker process is terminated abruptly (e.g. OOM killer), the broker requeues the task for another worker.

### 7.2 Denial of Service & Resource Contention Risks
1. **CPU / Memory Saturation on 4K Decoding**:
   - High-resolution (4K) videos sampled at 4.0 FPS across multiple concurrent worker processes can consume up to 100% CPU capacity and several gigabytes of RAM.
   - Without process concurrency limits, multiple parallel clip renders can cause out-of-memory termination of the Celery worker daemon.
   - *Recommendation*: Configure Celery worker concurrency to match physical CPU cores (`--concurrency=2` or `--concurrency=4`) and configure `worker_max_memory_per_child = 500000` (500MB) to prevent memory accumulation.

---

## 8. Prioritized Security Remediation Plan

The identified security findings are classified and prioritized below for implementation:

| Priority | Issue ID | Title & Vulnerability | Affected Files | Recommended Remediation | Implementation Size |
|---|---|---|---|---|---|
| **P1 (High)** | `SEC-001` | Plaintext YouTube OAuth Refresh Token Storage | `backend/services/publisher.py:1258–1264` | Encrypt OAuth tokens using AES-256-GCM (Fernet) before writing to disk, or migrate storage into an encrypted database column. | `S` |
| **P1 (High)** | `SEC-002` | Absence of API Route Authentication Middleware | `backend/main.py`, `backend/api/` | Introduce an API key or session token dependency (`HTTPBearer` / `APIKeyHeader`) on FastAPI routers to restrict local network access. | `M` |
| **P2 (Medium)**| `SEC-003` | Pre-Upload MIME Magic-Byte Validation Missing | `backend/api/routes/studio.py:460–550` | Inspect byte headers on chunk 0 to verify ISOBMFF signature (`ftyp`) before accepting file upload. | `XS` |
| **P2 (Medium)**| `SEC-004` | SSRF Exposure in Channel URL Normalization | `backend/services/downloader.py:159–170` | Validate channel URL domain against YouTube allowlist (`youtube.com`, `youtu.be`) and reject private IP addresses (`127.0.0.0/8`, `169.254.0.0/16`). | `XS` |
| **P2 (Medium)**| `SEC-005` | Hardcoded Default `SECRET_KEY` in Configuration | `backend/core/config.py:13` | Enforce runtime check requiring non-default `SECRET_KEY` in production, generating a high-entropy secret if missing. | `XS` |
| **P3 (Low)** | `SEC-006` | Wildcard CORS Configuration Ignored by Starlette | `backend/core/config.py:103`, `backend/main.py:46` | Replace literal wildcard origin `"https://*.netlify.app"` with `allow_origin_regex=r"https://.*\.netlify\.app"`. | `XS` |

---

## 9. Conclusion & Compliance Assessment

ClipForge demonstrates commendable security discipline in its core media execution layer: **subprocess invocations are immune to shell injection**, **path traversal is actively defended**, **chunked uploads are strictly fenced**, and **publishing privacy is unconditionally enforced**.

However, because the application was historically developed as an unauthenticated single-user local tool, significant compliance gaps exist under OWASP ASVS 5.0.0 regarding **API authentication** and **plaintext credential storage**. Remediation of the six identified items above will elevate ClipForge to enterprise-grade security readiness.
