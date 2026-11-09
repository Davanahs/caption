# ClipForge — Phase 1.3 Final Implementation Plan
## Storage Cleanup Endpoint Backend Delivery & UI Integration

**Document Version:** 6.0.0 (Final Deployment Trust-Boundary Gate Revision)  
**Phase Status:** `IN PROGRESS (INVESTIGATION & PLANNING)`  
**Target Defect:** `CF-DEF-001` — Storage Cleanup Missing Globally on Backend  
**Affected Domains:** L3 (Storage Service), L9 (API Routes), L10 (Clips UI)  
**Repository:** `d:\automation video clips\clipforge`  
**Git Branch:** `version-4-gen` (Commit `0ba85ffa2553dfaa39f7bcae755b0358ce01f9ac`)  
**Active Alembic Head:** `c3d4e5f6a7b8`  

---

## 1. Executive Summary & Defect Scope

In ClipForge, the Clips page (`/clips`) contains a user-facing button and modal designed for "🧹 Safe Cleanup". When clicked, the frontend UI executes:
1. `previewCleanup()` -> `GET /api/clips/cleanup/preview` to fetch counts of removable clips and estimated disk space recovery.
2. A confirmation modal displaying:
   - Low Score (< 5.0) clips
   - Missing Artifacts (unavailable/broken media files)
   - Total Unique Clips eligible for pruning
3. `executeCleanup()` -> `POST /api/clips/cleanup/execute` to safely prune eligible clips and reclaim disk space upon explicit user confirmation.

**The Defect (`CF-DEF-001`):**  
Neither endpoint (`GET /api/clips/cleanup/preview` nor `POST /api/clips/cleanup/execute`) exists in `backend/api/routes/clips.py` or anywhere in FastAPI. When a user clicks the "Safe Cleanup" button, the frontend fails with an unhandled rejection and displays an alert: `"Failed to preview cleanup"` (due to `HTTP 404 Not Found`).

### Architectural Scope & Boundaries
- **Transient Upload Pruning (`backend/cleanup_storage.py`):** Standalone maintenance script and Celery task that prunes downloaded YouTube source videos in `uploads/` for completed jobs. **Strictly prohibited** from touching `outputs/`.
- **Clips Library Safe Pruning (`/api/clips/cleanup/*`):** User-facing management of the generated clips library in `outputs/` and the `clips` table on `/clips`.

---

## 2. Pre-Flight Working-Tree Baseline & Cryptographic Hashes

### Working Tree State
- **Branch:** `version-4-gen`
- **Head Commit:** `0ba85ffa2553dfaa39f7bcae755b0358ce01f9ac`
- **Working Tree:** Dirty baseline strictly preserved (62 modified tracked files, 64+ untracked artifacts). Zero resets, zero cleans, zero blanket reverts.

### SHA-256 Pre-Modification Baseline Hashes
| File Path | SHA-256 Baseline Hash | File Size | Phase 1.3 Role |
|---|---|---|---|
| `backend/api/routes/clips.py` | `545f3b83ddd116d4f865f5f97a293bef01a9782e7483c80ffb231512f30025e4` | 22,890 bytes | Primary endpoint implementation target (`GET/POST /api/clips/cleanup/*`) |
| `frontend/app/clips/page.tsx` | `c16707b3fecf7f113acc7b97bcbbc4b9ad3d268ec9e566342c65b553cb1113e7` | 35,761 bytes | UI caller, modal presentation, candidate binding, and feedback |
| `frontend/lib/api.ts` | `4165a4040a4e8b22f22a877fc8ebd70069f7bc51d7edf9f1169de2eb03c5bbb1` | 21,753 bytes | Typed client helpers (`previewCleanup`, `executeCleanup`) |
| `backend/cleanup_storage.py` | `0bef5940e5f02b1f80d5c332f82110fa06f6e7b9ae3af6e6a8a52fecce186553` | 3,010 bytes | Read-only reference: Transient upload pruning script (**Zero-touch**) |
| `backend/services/artifact_manager.py` | `c22c89f10f0d12de28e16c4827902a24afc72b37f49e5e402ac853a2ff955669` | 12,866 bytes | Read-only reference: Artifact lifecycle and deletion (**Zero-touch**) |
| `backend/models/artifact_sync.py` | `bd6ec9f7290f8e5353f2bc782b3f832e6ce39b7f4d33d85e0dabbb9ac4bb3273` | 8,824 bytes | Read-only reference: Synchronous DB engine (**Zero-touch**) |
| `backend/core/storage.py` | `e7a26aa4892ff5114ae713039f85e5b78459176425f9788b09d81e73513e7810` | 10,012 bytes | Read-only reference: Storage provider path resolution (**Zero-touch**) |
| `backend/main.py` | `634734742915efe9f27149ff59417338502be15691c8ff08c3e78fac24dcf0ea` | 8,915 bytes | Route registration and quarantine URL suppression (**Zero-touch during planning**) |
| `docker-compose.yml` | `079712128ae3ea22f481c62956cf5742a03fbe40dcf16d40fb1767098e9ca83d` | 4,952 bytes | Deployment trust boundary mapping (`127.0.0.1:8000:8000`) |

---

## 3. Empirical Filesystem Co-Location Proof & Mount Analysis

### A. The Cross-Device Link Failure in Docker
Inspection of [`docker-compose.yml`](file:///d:/automation%20video%20clips/clipforge/docker-compose.yml#L37-L43) reveals how directories are mounted into the runtime container:
```yaml
    volumes:
      - ./backend:/app/backend
      - ./uploads:/app/uploads
      - ./outputs:/app/outputs
      - ./tmp:/tmp
      - ./tokens:/app/tokens
```
In Docker Compose, `./outputs` is an isolated host bind mount attached to `/app/outputs`.

Empirical execution inside the running `clipforge_backend` container proved:
- `/app/outputs` device ID (`st_dev`): **`70`** (Host bind mount)
- `/app/storage_quarantine` device ID (`st_dev`): **`91`** (Container root overlayfs `/`)
- Attempting `os.replace('/app/outputs/source.tmp', '/app/storage_quarantine/target.tmp')` failed with:
  `OSError: [Errno 18] Invalid cross-device link` (`EXDEV`)

On the Windows host, both directories share `st_dev == 12449818848094589980` because they reside on NTFS drive `D:`. Relying on the host drive letter creates a catastrophic runtime defect when executed inside Docker.

### B. Safe Preflight Check Specification
To prevent runtime `EXDEV` errors and eliminate non-atomic copy-and-delete fallbacks:
1. **Mandatory Device ID Verification:**
   Before staging any batch, the execution service runs a strict preflight check:
   ```python
   class CrossDeviceLinkError(RuntimeError):
       """Raised when source and quarantine paths reside on different filesystem devices."""
       pass

   def verify_filesystem_colocation(source_dir: Path, quarantine_dir: Path) -> None:
       """
       Verifies that source and quarantine directories reside on the exact same filesystem device.
       Uses os.stat().st_dev. On Linux/Unix, also cross-checks statvfs (f_fsid) where available.
       Fails closed: if devices differ or cannot be verified, raises CrossDeviceLinkError.
       NEVER falls back to copy-and-delete across device boundaries.
       """
       resolved_source = source_dir.resolve(strict=False)
       resolved_quar = quarantine_dir.resolve(strict=False)
       
       # Ensure directory or parent exists for stat inspection
       source_probe = resolved_source if resolved_source.exists() else resolved_source.parent
       quar_probe = resolved_quar if resolved_quar.exists() else resolved_quar.parent
       
       source_stat = os.stat(source_probe)
       quar_stat = os.stat(quar_probe)
       
       if source_stat.st_dev != quar_stat.st_dev:
           raise CrossDeviceLinkError(
               f"Filesystem co-location preflight check failed: "
               f"Source directory ({source_probe}, dev={source_stat.st_dev}) and quarantine directory "
               f"({quar_probe}, dev={quar_stat.st_dev}) reside on different filesystem devices. "
               f"Atomic os.replace() is impossible across mount boundaries, and fallback "
               f"to non-atomic copy-and-delete is strictly prohibited."
           )
           
       if hasattr(os, "statvfs"):
           try:
               source_vfs = os.statvfs(source_probe)
               quar_vfs = os.statvfs(quar_probe)
               if source_vfs.f_fsid != 0 and quar_vfs.f_fsid != 0 and source_vfs.f_fsid != quar_vfs.f_fsid:
                   raise CrossDeviceLinkError(
                       f"Filesystem statvfs check failed: f_fsid mismatch between "
                       f"source ({source_vfs.f_fsid}) and quarantine ({quar_vfs.f_fsid})."
                   )
           except OSError:
               pass
   ```

### C. Design Evaluation & Blocker Resolution
If `settings.BASE_DIR / "storage_quarantine"` is used directly in Docker, `verify_filesystem_colocation` fails immediately (`70 != 91`). Attempting `os.replace()` across mount boundaries fails, and silent fallback to copy-and-delete is strictly prohibited because copy-and-delete is non-atomic, duplicates disk usage, can fail halfway, and violates the zero-data-loss invariant.

Two distinct architectural options are documented for review:

- **Option A (Subdirectory within OUTPUT_DIR with Route Intercept & External Journal - Recommended):**
  - Quarantine directory: `QUARANTINE_ROOT = settings.OUTPUT_DIR / ".storage_quarantine"`
  - Inside Docker, both `/app/outputs` and `/app/outputs/.storage_quarantine` share `st_dev == 70`.
  - On the Windows host, both share the same NTFS device ID.
  - `os.replace()` is guaranteed to execute as an instantaneous, atomic directory entry update.
  - **Static mount protection:** Handled via Section 3.D below.
  - **Journal protection:** The journal is stored completely outside `OUTPUT_DIR` at `settings.BASE_DIR / "storage_cleanup_journals"` (device independent).
- **Option B (Docker Volume Mount Update - Separately Reviewed Design):**
  - Requires updating `docker-compose.yml` to mount a dedicated or unified storage root (e.g. `./storage:/app/storage` containing `outputs/` and `storage_quarantine/` on the same host volume).
  - Requires updating container deployment configurations and restarting containers.
  - If Option B is preferred by product engineering, it requires a separately approved deployment change outside the scope of Phase 1.3.

### D. Quarantine URL Isolation from Static Mounts & Exact Route Ordering
In Starlette / FastAPI, routes registered on `app` are evaluated in strict linear sequence:
- If a mount route `app.mount("/outputs", StaticFiles(...))` is registered first, Starlette's `Mount` intercepts all URL paths prefixed with `/outputs/` and delegates to `StaticFiles`, which serves files present on disk (including dotfiles).
- Therefore, to guarantee that quarantined files cannot be retrieved over HTTP, the explicit quarantine-blocking route **MUST be registered on `app` BEFORE `app.mount("/outputs", ...)`** in [`backend/main.py`](file:///d:/automation%20video%20clips/clipforge/backend/main.py#L137-L141):

```python
# ── Quarantine Protection Route (Registered BEFORE static mount) ────────────
@app.api_route(
    "/outputs/.storage_quarantine/{rest:path}",
    methods=["GET", "HEAD", "POST"],
    include_in_schema=False
)
async def block_quarantine_access(rest: str):
    raise HTTPException(status_code=404, detail="Not Found")

# ── Static Files (output videos/thumbnails) ─────────────────────────────────
app.mount("/outputs", StaticFiles(directory=str(settings.OUTPUT_DIR)), name="outputs")
app.mount("/uploads", StaticFiles(directory=str(settings.UPLOAD_DIR)), name="uploads")
```

**Real Application Verification Requirement:**  
The implementation acceptance test (Test 7) must test the actual running `backend.main:app` instance (via `AsyncClient(transport=ASGITransport(app=app))` or `TestClient(app)`), physically stage a test file in `settings.OUTPUT_DIR / ".storage_quarantine" / "batch_test" / "test_artifact.mp4"`, and assert that `GET /outputs/.storage_quarantine/batch_test/test_artifact.mp4` returns `HTTP 404 Not Found`. A standalone or mock FastAPI app whose route order differs from `backend/main.py` is strictly prohibited as proof.

---

## 4. Crash-Durable Journal Ordering & Recovery Protocol

To eliminate false claims of cross-subsystem atomicity between the filesystem and PostgreSQL, all operations follow a crash-durable 6-step ordering coordinated by an intent journal (`journal.json`).

### Journal Path and Public Static Mount Isolation
- **Journal Storage Location:** `settings.BASE_DIR / "storage_cleanup_journals" / f"batch_{batch_id}" / "journal.json"`
  - In container: `/app/storage_cleanup_journals/batch_{batch_id}/journal.json`
  - On host: `d:\automation video clips\clipforge\storage_cleanup_journals\batch_{batch_id}\journal.json`
- **Isolation Guarantee:** The journal resides strictly **outside** `settings.OUTPUT_DIR` and is **never** accessible through `/outputs` or any FastAPI static-file mount.
- **Server-Generated Paths Only:** The journal records only canonical server-generated paths resolved via `settings.OUTPUT_DIR`. Client-supplied filesystem paths are strictly ignored and never recorded or executed.

### The 6-Step Crash-Durable Move Sequence
Before each filesystem move:
1. **Step 1 (Persist Intent in Journal):** Write the intended operation to `journal.json.tmp`:
   - `clip_id`: UUID of candidate
   - `canonical_source`: Resolved server-side path in `outputs/...`
   - `quarantine_destination`: Target path in `.storage_quarantine/batch_{id}/...`
   - `candidate_identity`: Canonical clip identifier
   - `expected_size_bytes`: Integer file size
   - `item_state`: `"INTENT_DECLARED"`
   - `batch_state`: `"STAGING"`
2. **Step 2 (Flush & Synchronise Journal File):** Flush the Python user-space buffer (`f.flush()`) and synchronise the OS disk buffer via `os.fsync(f.fileno())`.
3. **Step 3 (Atomically Replace Journal & Sync Containing Directory):**
   - Execute `os.replace("journal.json.tmp", "journal.json")`. The intent is now durable on disk.
   - Synchronise the containing journal directory descriptor where supported (on POSIX, `dir_fd = os.open(journal_dir, os.O_RDONLY); os.fsync(dir_fd); os.close(dir_fd)`).
4. **Step 4 (Perform Same-Filesystem Move):**
   - Execute `os.replace(canonical_source, quarantine_destination)`. On the same filesystem volume, this is an instantaneous, atomic directory entry pointer update.
5. **Step 5 (Synchronise Affected Directories):**
   - Synchronise both the source containing directory and the quarantine destination directory descriptors where supported (`os.fsync(dir_fd)`).
6. **Step 6 (Persist Completed Staging State):**
   - Update journal entry to `item_state = "STAGED"` using the atomic flush-sync-replace procedure before advancing to database operations.

Advance to database operations **only after all candidate files reach `"STAGED"`**.

### Crash Recovery Matrix Across Every Boundary
| Crash Boundary | Journal State | Actual Filesystem State | Database State | Deterministic Recovery Action |
|---|---|---|---|---|
| **Boundary 1:** After intent durable, before move | `INTENT_DECLARED` | File at `canonical_source`, target empty | Intact | Detect file present at source; quarantine empty. The move never occurred. Abort batch, remove empty quarantine directory, update journal to `CANCELLED_UNMOVED`. Original state intact. |
| **Boundary 2:** Immediately after move, before staging persisted | `INTENT_DECLARED` | File at `quarantine_destination`, source missing | Intact | Detect file in quarantine with matching expected size; source missing. DB was never touched. Restore file to `canonical_source` via atomic `os.replace()`, sync directories, update journal to `ROLLED_BACK`. Original state restored. |
| **Boundary 3:** Staging completed, before DB commit | `STAGED` | All candidate files in quarantine | Intact | Database was never mutated. Query DB: candidate clips still exist. Read journal, restore all staged files back to `canonical_source`. Update journal to `ROLLED_BACK`. Original state restored. |
| **Boundary 4:** DB transaction committed, before journal updated | `DB_COMMITTING` / `STAGED` | All candidate files in quarantine | Committed | Query PostgreSQL for candidate `clip_id`: records do not exist (transaction committed). Proceed with physical purge of quarantined files, remove quarantine folder, update journal to `COMPLETED`. |
| **Boundary 5:** During purge of multiple files | `PURGING` | Some files unlinked, some remaining | Committed | Query PostgreSQL: records deleted. Idempotently unlink remaining files in quarantine directory, remove directory, update journal to `COMPLETED`. |
| **Boundary 6:** File, DB record, or shared reference changed since staging | `STAGED` | Files in quarantine | Mutated (external change) | Re-evaluate candidate status against DB. If DB not committed and clip became published or active reservation acquired: roll back files to `canonical_source`, abort batch. If state is ambiguous or unresolvable: **PRESERVE DATA.** Do not delete or overwrite files. Mark batch `BLOCKED_AWAITING_RECOVERY`, generate high-priority recovery blocker report, and alert operator. |

### Startup Recovery Hook
`reconcile_quarantine()` executes on application startup in `backend/main.py:lifespan`, scanning `storage_cleanup_journals` and `.storage_quarantine` for unfinished batches and executing the recovery matrix before the API accepts incoming requests.

---

## 5. Localhost-Only Deployment Trust-Boundary Gate & Authorization Audit

### A. Verified Authorization Audit Findings
Inspection of the actual application codebase confirms:
1. **Authentication Middleware / Dependencies:** **None exist.** `backend/main.py` configures only `CORSMiddleware`. There are zero authentication middlewares, HTTPBearer, OAuth2 schemes, or session dependencies.
2. **Session or User Identity Validation:** **None exist.** There is no `User` model in `backend/models/models.py`. There are no user accounts, user IDs, session cookies, or user tokens anywhere in the database or FastAPI route contracts.
3. **API-Key or Credential Validation:** **None exist.** No API key headers or authentication dependencies exist in `backend/api/`.
4. **Existing Destructive Operations:** All existing destructive endpoints in the application—including:
   - `DELETE /api/clips/{clip_id}` ([`backend/api/routes/clips.py:143`](file:///d:/automation%20video%20clips/clipforge/backend/api/routes/clips.py#L143))
   - `DELETE /api/channels/{channel_id}` ([`backend/api/routes/channels.py`](file:///d:/automation%20video%20clips/clipforge/backend/api/routes/channels.py))
   - `POST /api/jobs/{job_id}/cancel` ([`backend/api/routes/jobs.py`](file:///d:/automation%20video%20clips/clipforge/backend/api/routes/jobs.py))  
   rely solely on `db: AsyncSession = Depends(get_db)`. Anyone who can send an HTTP request to port 8000 can invoke them. `Depends(get_db)` provides database session lifecycle injection; it provides zero authentication or authorization.
5. **CORS Role:** `CORSMiddleware` in `backend/main.py` restricts browser-originated cross-origin resource sharing from unauthorized origins. It does not authenticate requests or authorize callers.

**Explicit Statement of Fact:**  
A verified authentication or authorization mechanism **has not been established** in ClipForge. Claiming that `Depends(get_db)` or `CORSMiddleware` provides authorization is factually false.

### B. Verification of Localhost-Only Deployment Trust Boundary
Before adopting the loopback publication gate, the following verifications were empirically conducted:
1. **Frontend-to-Backend Connectivity:**
   - In [`frontend/lib/api.ts`](file:///d:/automation%20video%20clips/clipforge/frontend/lib/api.ts#L1), [`frontend/lib/studioApi.ts`](file:///d:/automation%20video%20clips/clipforge/frontend/lib/studioApi.ts#L9), and [`frontend/components/Sidebar.tsx`](file:///d:/automation%20video%20clips/clipforge/frontend/components/Sidebar.tsx#L53), the API base defaults to `http://localhost:8000` via `process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'`.
   - On the host, `localhost` resolves to `127.0.0.1`. When the backend is published to `127.0.0.1:8000:8000`, the Next.js frontend (running on host port 3000) connects seamlessly to the backend on loopback.
2. **External Access Dependencies:**
   - Inspection of [`docker-compose.yml`](file:///d:/automation%20video%20clips/clipforge/docker-compose.yml) confirms that `worker`, `beat`, `flower`, `redis`, and `postgres` communicate strictly over the internal Docker bridge network (`clipforge_default`).
   - Neither the Celery worker nor any background task connects to host port 8000; they connect directly to `redis://redis:6379/0` and `postgresql://postgres:5432/clipforge`.
   - Ollama is accessed via `http://host.docker.internal:11434`.
   - Zero internal or required background services depend on external access to host port 8000.
3. **Current Host Listener vs. Intended Publication:**
   - Active host probe (`netstat -ano | findstr :8000`) confirmed:  
     `TCP 0.0.0.0:8000 LISTENING PID 22308` (Docker userland proxy).
   - Because `docker-compose.yml` currently specifies `ports: - "8000:8000"`, the unauthenticated API is published on all host network interfaces, exposing destructive operations to the local area network (LAN/Wi-Fi).
   - Specifying `127.0.0.1:8000:8000` instructs Docker to bind host port 8000 strictly to the loopback interface (`127.0.0.1`), causing all incoming packets from external network adapters to be rejected at the OS socket/firewall layer.
4. **Internal Docker Container Networking:**
   - Docker Compose `ports` directives control only host-level port forwarding. Restricting host publication to `127.0.0.1` does not affect inter-container DNS or communication on the internal bridge network.
5. **Documented Application Use Case:**
   - ClipForge is documented in `AGENTS.md` and `PROJECT_CONTINUITY.md` as a local, single-operator desktop automation studio running on the workstation. There is no requirement for LAN, multi-tenant, or remote Internet access.
6. **Container Binding vs. Host Publication Distinction:**
   - Inside the container, Uvicorn runs: `uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload`.
   - Binding Uvicorn to `0.0.0.0` inside the container is required so that Docker's bridge network proxy can route packets into the container.
   - The security boundary is enforced at the host publication layer: publishing exclusively as `127.0.0.1:8000:8000` prevents exposure outside the host machine.

### C. Mandatory Security Gate for Phase 1.3 Execution
**Inviolable Gate:**  
Phase 1.3 execution must not expose unauthenticated destructive cleanup endpoints to the LAN or Internet.
1. Prior to activating destructive cleanup execution, the backend host publication in `docker-compose.yml` must be constrained to loopback:
   ```yaml
       ports:
         - "127.0.0.1:8000:8000"
         - "127.0.0.1:8080:8080"
   ```
2. **Fail-Stop Requirement:** If the backend cannot be constrained to the local-only trust boundary without breaking required application functionality, stop immediately and request separate authorization for an architectural security design. Do not invent an unapproved authentication system, and do not treat CORS, `Depends(get_db)`, or the HMAC preview token as authorization.
3. **Documented Remaining Trust Assumption:**  
   Local processes running on the host machine that are capable of establishing connections to `127.0.0.1:8000` are within the trusted boundary. Loopback binding protects against remote and LAN-based network attacks, but **does not authenticate individual local OS processes**.

### D. Role of the HMAC-SHA256 Preview Token
Because application-level user authentication does not exist, the HMAC-SHA256 preview token serves strictly as an **integrity and confirmation lease**, **NOT** an authorization mechanism:
1. **Purpose:** Guarantees that the execute payload corresponds identically to what the server calculated and what the user reviewed in the preview modal, and that execution occurs within a valid 15-minute lease.
2. **Secret Resolution:** Evaluated via [`resolve_storage_identity_secret()`](file:///d:/automation%20video%20clips/clipforge/backend/core/storage_identity.py#L26-L43). Rejects empty secrets, whitespace-only secrets, and known insecure placeholders (`"clipforge_default_secret_key_change_in_prod"`, `"changeme"`, `"secret"`). Requires minimum 16 characters. Fails closed on startup if insecure.
3. **Canonical Payload Construction:**
   ```json
   {
     "preview_id": "8f9a2b1c-3d4e-4f5a-6b7c-8d9e0f1a2b3c",
     "issued_at": 1791924000,
     "expires_at": 1791924900,
     "candidate_ids_hash": "a1b2c3d4e5f6...",
     "candidate_count": 4,
     "score_threshold": 5.0,
     "purge_missing_media": false
   }
   ```
   - `candidate_ids_hash`: `sha256(",".join(sorted(candidate_clip_ids)).encode('utf-8')).hexdigest()`.
   - Payload is canonically encoded with lexicographically sorted keys: `json.dumps(payload, sort_keys=True, separators=(',', ':')).encode('utf-8')`.
4. **Constant-Time Verification:** Signatures are verified using `hmac.compare_digest(computed_sig, provided_sig)` to prevent timing side-channels.
5. **Strict Token Rejection:**
   - Malformed structure (not `payload_b64.signature_hex` or invalid base64/JSON) -> `HTTP 400 Bad Request`.
   - Tampered payload or signature mismatch -> `HTTP 401 Unauthorized` / `HTTP 400 Bad Request`.
   - Expired timestamp (`now > expires_at`) -> `HTTP 400 Bad Request`.
   - Candidate ID mismatch (`computed_hash != candidate_ids_hash`) -> `HTTP 400 Bad Request`.
6. **Zero Sensitive Logging:** The secret and token signatures are never logged. Log entries record only `preview_id`, candidate count, and elapsed validation time.

---

## 6. Canonical Path Containment & Escape Rejection

All paths are resolved and validated using strict `Path.relative_to()` containment:

```python
def validate_canonical_containment(target_path: Path | str, approved_root: Path) -> Path:
    """
    Enforces strict canonical path containment using resolved Path.relative_to().
    Rejects traversals, symlinks escaping the root, and root destruction.
    """
    if not target_path:
        raise ValueError("Target path cannot be empty")
        
    resolved_target = Path(target_path).resolve(strict=False)
    resolved_root = approved_root.resolve(strict=True)
    
    # 1. Root destruction barrier
    if resolved_target == resolved_root:
        raise ValueError(f"Security violation: Target is the storage root itself: {target_path}")
        
    # 2. Strict relative_to containment check
    try:
        rel = resolved_target.relative_to(resolved_root)
    except ValueError:
        raise ValueError(f"Path traversal detected: {target_path} is outside approved root {approved_root}")
        
    # 3. Guard against '.' or empty relative segments
    if str(rel) in ("", ".", ".."):
        raise ValueError(f"Invalid containment target: {target_path}")
        
    # 4. Strict subpath containment (must reside in clips subfolder)
    parts = rel.parts
    if len(parts) < 3 or parts[1] != "clips":
        raise ValueError(f"Target path does not reside in an approved clips subpath: {rel}")
        
    # 5. File extension whitelist
    ALLOWED_EXTENSIONS = {".mp4", ".mov", ".mkv", ".webm", ".jpg", ".jpeg", ".png", ".webp", ".json", ".wav"}
    if resolved_target.suffix.lower() not in ALLOWED_EXTENSIONS and resolved_target.is_file():
        raise ValueError(f"Unsupported file type for cleanup: {resolved_target.suffix}")
        
    return resolved_target
```

### Shared Reference Guard
Before moving or unlinking any physical file:
1. Query `Clip`: Does any other clip (`id != candidate.id`) share this `output_path` or `thumbnail_path`?
2. Query `ArtifactRecord`: Does any artifact record with a different owner share this `storage_key`?
3. If shared references exist, the physical file is **not moved or unlinked**. Only the candidate clip's database record is unlinked, leaving the physical file intact for the other consumer (`shared_files_retained: true`).

---

## 7. Writer Coordination & Storage Reservation Invariants

To guarantee that cleanup never races an active worker writing or consuming an artifact:

1. **Storage Reservation Invariant:**
   - Query `Video`: `select(Video).where(Video.id == clip.video_id)`.
   - If `Video.reservation_state in [VideoReservationState.RESERVED.value, VideoReservationState.HEADROOM_ONLY.value]`, the clip is **skipped** (`reason="active_storage_reservation"`).
2. **Active Pipeline Barrier:**
   - Query `Job`: `select(Job).where(Job.video_id == clip.video_id)`.
   - If `Job.status not in ["completed", "completed_with_failures", "failed", "cancelled"]`, the clip is **skipped** (`reason="parent_job_active"`).
3. **Active Celery Task Barrier:**
   - Query `TaskExecution`: `select(TaskExecution).where(TaskExecution.clip_id == clip.id, TaskExecution.status.in_(["pending", "running", "retrying"]))`.
   - If active tasks exist, the clip is **skipped** (`reason="active_celery_task"`).
4. **Filesystem Writer Lock Barrier:**
   - Before moving any file, inspect the clip directory (`outputs/{video_id}/clips/{clip_id}/`).
   - If temporary files exist (`.tmp_*` or `.part`) or an exclusive file handle cannot be acquired, the candidate is **skipped** (`reason="file_write_in_progress"`).

---

## 8. Missing-Media Separation & Decoupling

The UI renders missing media as `⚠️ MEDIA MISSING` when `output_path` is missing or unreadable on disk.

### Implementation Policy
1. **Preview Reporting:**
   - `counts.low_score`: Count of eligible clips scored `< 5.0` that have verified physical files on disk.
   - `counts.unavailable`: Count of clips whose output files are missing from disk.
   - `reclaimable_bytes`: Calculated strictly from verified physical files. Missing files contribute `0` bytes.
2. **Execution Safety Policy:**
   - Default: `purge_missing_media = False`.
   - The execute endpoint will **only** delete clips in the `low_score` category that possess physical files.
   - Unavailable clips are reported as non-mutated diagnostic items (`"skipped_unavailable_default"`).
   - Only if the client explicitly passes `"purge_missing_media": true` along with explicit candidate IDs will missing-media database records be pruned.

---

## 9. Publishing & History Safeguards

### Inviolable Protection Rules
| Entity / State | Condition | Cleanup Action | Rationale |
|---|---|---|---|
| `Clip.publish_status` | `"published"` | **STRICTLY PROTECTED** | Active public YouTube Short |
| `Clip.youtube_short_id` | Not `None` and non-empty | **STRICTLY PROTECTED** | Linked to YouTube video ID |
| `PublishRecord` | `status in ["completed", "publishing"]` | **STRICTLY PROTECTED** | Active upload / audit record |
| `VideoTrackingQueue` | `status == "active"` | **STRICTLY PROTECTED** | Real-time analytics tracking active |
| `ClipPublishDestination` | `status in ["published", "publishing", "scheduled"]` | **STRICTLY PROTECTED** | Scheduled or published to external channel |

### Cascade Scope Boundary
For eligible unpublished low-score clips, cascade deletion in PostgreSQL is strictly restricted to local draft planning records:
- `ClipVariant` (draft visual reframing variants)
- `ClipRetention` (draft retention analysis data)
- `ClipSFXPlan`, `ClipVisualPlan`, `ClipHookPlan` (draft enhancement plans)
- `ArtifactRecord` (strictly where `owner_type == 'clip'` and `owner_id == clip.id`, with zero shared references)

Publishing tables (`publish_records`, `channels`, `youtube_destinations`) and global video history (`videos`, `jobs`) are **never** deleted by clip cleanup.

---

## 10. Execution Semantics & Response Contract

### Batch Execution Model
- **Validation & Staging:** Evaluated per candidate. Candidates that are protected, locked, or changed state are skipped.
- **Database Commit:** Atomic transaction across all successfully staged candidates.
- **Physical Reclamation:** Bytes are reported as reclaimed **only after** physical unlinking from `storage_quarantine` is verified.

### Response Contracts

#### `GET /api/clips/cleanup/preview`
```json
{
  "preview_token": "eyJhbGciOiJIUzI1NiJ9...signature",
  "preview_id": "8f9a2b1c-3d4e-4f5a-6b7c-8d9e0f1a2b3c",
  "expires_at": 1791924900,
  "counts": {
    "low_score": 3,
    "unavailable": 1,
    "total_unique": 4
  },
  "reclaimable_bytes": 104857600,
  "reclaimable_human": "100.00 MB",
  "candidates": [
    {
      "clip_id": "c1a2b3c4-...",
      "title": "Low Score Clip 1",
      "score": 3.4,
      "category": "low_score",
      "output_path": "outputs/vid1/clips/c1/final.mp4",
      "size_bytes": 52428800
    }
  ],
  "protected_counts": {
    "published": 5,
    "high_score": 12,
    "active_jobs": 1,
    "active_reservations": 0
  }
}
```

#### `POST /api/clips/cleanup/execute`
**Request Payload:**
```json
{
  "preview_token": "eyJhbGciOiJIUzI1NiJ9...signature",
  "candidate_clip_ids": ["c1a2b3c4-...", "c2b3c4d5-..."],
  "purge_missing_media": false
}
```

**Response Payload:**
```json
{
  "status": "success",
  "summary": {
    "requested_count": 2,
    "deleted_clip_records": 1,
    "purged_physical_files": 2,
    "shared_files_retained": 0,
    "skipped_count": 1,
    "failed_count": 0,
    "confirmed_reclaimed_bytes": 52428800,
    "confirmed_reclaimed_human": "50.00 MB"
  },
  "deleted_clip_ids": ["c1a2b3c4-..."],
  "skipped_candidates": [
    {
      "clip_id": "c2b3c4d5-...",
      "reason": "unavailable_media_retained_by_default"
    }
  ],
  "retained_shared_files": [],
  "recovery_pending": []
}
```

---

## 11. Exact Proposed Files to Modify

| File | Exact Changes |
|---|---|
| [`docker-compose.yml`](file:///d:/automation%20video%20clips/clipforge/docker-compose.yml) | Constrain backend published ports to loopback: `127.0.0.1:8000:8000` (and `127.0.0.1:8080:8080`). **(Planning gate: only modified upon explicit authorization)** |
| [`backend/api/routes/clips.py`](file:///d:/automation%20video%20clips/clipforge/backend/api/routes/clips.py) | Add HMAC token generator/validator, canonical containment validator, co-location preflight check, crash-durable journal executor, `GET /api/clips/cleanup/preview`, and `POST /api/clips/cleanup/execute` before line 119. |
| [`backend/main.py`](file:///d:/automation%20video%20clips/clipforge/backend/main.py) | Register quarantine route intercept returning 404 for `/outputs/.storage_quarantine/{rest:path}` **before** line 139 (`app.mount("/outputs", ...)`), and invoke `reconcile_quarantine()` in `lifespan()`. |
| [`frontend/lib/api.ts`](file:///d:/automation%20video%20clips/clipforge/frontend/lib/api.ts) | Export typed interfaces (`CleanupPreviewResponse`, `CleanupExecuteResponse`, etc.) and update `executeCleanup(data)`. |
| [`frontend/app/clips/page.tsx`](file:///d:/automation%20video%20clips/clipforge/frontend/app/clips/page.tsx) | Pass `preview_token` and `candidate_clip_ids` into `executeCleanup()`, enhance modal with `reclaimable_human` and safety notice, display detailed results. |
| [`backend/tests/test_phase_1_3_storage_cleanup.py`](file:///d:/automation%20video%20clips/clipforge/backend/tests/test_phase_1_3_storage_cleanup.py) | **New file:** 20 isolated unit/integration tests with synthetic fixtures. |

**Zero-Touch Invariants:**
- `backend/cleanup_storage.py` is untouched.
- `backend/services/artifact_manager.py` is untouched.
- `backend/core/storage.py` is untouched.
- `backend/models/models.py` is untouched (zero schema changes or migrations).

---

## 12. Expanded Isolated Acceptance Test Matrix (20 Tests + Deployment Checks)

The new test suite [`backend/tests/test_phase_1_3_storage_cleanup.py`](file:///d:/automation%20video%20clips/clipforge/backend/tests/test_phase_1_3_storage_cleanup.py) will execute against isolated temporary roots (`tempfile.mkdtemp()`) and prefixed database entities (`P13_TEST_*`), never real user artifacts:

### Unit & Integration Acceptance Tests (20 Tests)
1. **Test 1 — Preview Read-Only Invariant:** Verify `GET /api/clips/cleanup/preview` mutates zero files and zero database rows.
2. **Test 2 — Preview Token HMAC Tampering Rejection:** Verify tampered signature or modified payload is rejected with `HTTP 401 Unauthorized` / `HTTP 400 Bad Request`.
3. **Test 3 — Preview Token Expiry Rejection:** Verify expired token (`now > expires_at`) is rejected with `HTTP 400 Bad Request`.
4. **Test 4 — Preview Token Candidate Mismatch Rejection:** Verify submitting candidate IDs differing from the reviewed preview token is rejected with `HTTP 400 Bad Request`.
5. **Test 5 — Insecure Secret Rejection:** Verify `resolve_storage_identity_secret` rejects empty secrets, placeholders (`"clipforge_default_secret_key_change_in_prod"`, `"changeme"`), and secrets < 16 chars, failing closed.
6. **Test 6 — Preview Token Integrity Contract (Not Auth Substitute):** Prove that the preview token functions strictly as an integrity and confirmation lease (binding candidate set hash and lease window), not an authentication token. Verify that malformed, replayed, or altered tokens fail closed.
7. **Test 7 — Quarantine URL 404 Isolation on Real Application:** Exercise the **actual running `backend.main:app` instance** (via ASGI test client) with a physical file staged in `settings.OUTPUT_DIR / ".storage_quarantine" / "batch_test" / "test_artifact.mp4"`. Verify that `GET` and `HEAD` requests to `/outputs/.storage_quarantine/batch_test/test_artifact.mp4` return `HTTP 404 Not Found` and zero bytes of the file are retrievable. Using a standalone or mock FastAPI app whose route order differs from `backend/main.py` is strictly prohibited.
8. **Test 8 — Filesystem Co-Location Preflight Check:** Verify `verify_filesystem_colocation` detects device ID mismatches (`st_dev` difference) and raises `CrossDeviceLinkError` without attempting `os.replace` or falling back to copy-and-delete.
9. **Test 9 — High-Score Asset Preservation:** Clips with `score >= 5.0` (`5.00` and `5.01`) are excluded from candidates and rejected if submitted to execute.
10. **Test 10 — Published Asset Protection:** Clips with `publish_status = 'published'` or valid `youtube_short_id` are strictly protected and rejected from execution.
11. **Test 11 — Active Pipeline & Reservation Protection:** Clips linked to active jobs (`Job.status = 'transcribing'`) or active reservations (`HEADROOM_ONLY`) are strictly protected.
12. **Test 12 — Shared Artifact Reference Preservation:** If an artifact is shared across two clips, deleting one clip unlinks its database record but retains the physical file on disk (`shared_files_retained == 1`).
13. **Test 13 — Missing-Media Safe Separation:** Missing-media records are reported in `counts.unavailable` but are skipped by default when `purge_missing_media = False`.
14. **Test 14 — Canonical Path Containment & Escape Rejection:** Traversal attempts (`Path.relative_to`) and root destruction attempts are blocked.
15. **Test 15 — Crash Recovery Scenario 1 (Intent durable, before move):** Simulates crash after Step 3 of 6-step ordering (`INTENT_DECLARED`). Verify recovery cancels batch, removes quarantine directory; canonical files intact.
16. **Test 16 — Crash Recovery Scenario 2 (Immediately after move, before staging persisted):** Simulates crash immediately after Step 4 (`os.replace` succeeded, but journal is still `INTENT_DECLARED` and DB untouched). Verify recovery restores file back to canonical source and marks journal `ROLLED_BACK`.
17. **Test 17 — Crash Recovery Scenario 3 (Staged, before DB commit):** Simulates crash after Step 6 before database commit. Verify recovery queries DB, finds clips intact, restores all staged files to canonical paths, and marks journal `ROLLED_BACK`.
18. **Test 18 — Crash Recovery Scenario 4 (DB committed, before purge):** Simulates crash after DB commit. Recovery detects clips missing in DB, proceeds with physical purge of quarantined files, and marks journal `COMPLETED`.
19. **Test 19 — Crash Recovery Scenario 5 (Purge interrupted):** 5 files quarantined, 2 unlinked, process crashes. Verify recovery idempotently unlinks remaining 3 files and removes quarantine directory.
20. **Test 20 — External Conflict & Ambiguous State Handling:** Simulates state change during staging (clip published or shared reference created) or ambiguous DB status. Proves recovery rolls back uncommitted changes, preserves physical data, and marks batch `BLOCKED_AWAITING_RECOVERY` without data loss.

### Deployment Trust-Boundary Verification Checks
In addition to the 20 unit/integration tests, the verification suite demonstrates:
- **Loopback Publication Verification:** Verify that `docker compose port backend 8000` outputs `127.0.0.1:8000` (and `netstat` confirms no listener on `0.0.0.0:8000`).
- **Frontend Connectivity:** Verify Next.js frontend (`http://localhost:3000`) successfully fetches `/api/health` and `/api/clips/cleanup/preview` from `http://127.0.0.1:8000`.
- **Quarantine Static Block:** Verify real `backend.main:app` blocks `/outputs/.storage_quarantine/...` via route intercept preceding the static mount.
- **Data Isolation:** Verify all destructive operations execute against isolated `tempfile` and prefixed DB records.

---

## 13. Acceptance Criteria & Completion Gates

Phase 1.3 execution will conclude only after satisfying:
1. **Deployment Security Gate:** Backend published host port is verified bound strictly to `127.0.0.1:8000` before destructive operations are callable.
2. **Endpoint Delivery:** Both endpoints return `200 OK` adhering to the revised schemas.
3. **Automated Verification:** All 20 tests in `test_phase_1_3_storage_cleanup.py` pass cleanly (20/20).
4. **Regression Safety:** All 38 existing tests across 5 test suites continue to pass.
5. **Static Analysis & Build:** `npx tsc --noEmit` clean (0 errors) and `npm run build` clean.
6. **Browser Verification:** Real Playwright browser test confirming clicking "Safe Cleanup" opens the modal with valid counts, confirming execution deletes the candidate and reclaims storage, and refreshing persists the updated library state.
7. **Defect Ledger:** `CF-DEF-001` marked `RESOLVED IN PHASE 1.3`.
8. **Stop Condition:** Phase 1.4 remains strictly `NOT STARTED`.
