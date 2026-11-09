# ClipForge — CF-DEF-013 Production Deployment Runbook

**Document Version:** 1.0.0  
**Target Release:** `CF-DEF-013` (Publishing Privacy Hardening & Default Alignment)  
**Workspace:** [`d:/automation video clips/clipforge`](file:///d:/automation%20video%20clips/clipforge)  
**Target Branch:** `version-4-gen`  
**Execution Gate:** **MANUAL EXECUTION UPON SEPARATE EXPLICIT AUTHORIZATION ONLY**

---

## 1. Safety Boundaries & Mandatory Constraints

All operators executing this runbook MUST adhere strictly to the following boundaries:
1. **Zero Live YouTube Mutation:** Never execute `videos().insert` or `videos().update` against real YouTube channels.
2. **Legacy Public Shorts Intact (User-Intended Visibility):** YouTube Shorts `0OfOivc-tpU`, `39w4TLjreFU`, `L3ihlJVo_3A`, and `FoNMm4F9qIM` on channel `ClipSee` (`UCH90024qrJHA4amGRxnTldw`) were successfully uploaded by the backend as private and subsequently made public intentionally by the user directly on YouTube. They must remain untouched in their user-intended public state.
3. **No Unsafe DDL or Full DB Overwrites:** Routine rollback must NEVER execute `pg_restore --clean --if-exists` across the operational database.
4. **No Task Purging:** Never run `celery purge` or cancel tasks in flight to force an idle state.
5. **Secret Protection:** Never log, echo, or output PostgreSQL passwords, OAuth client secrets, refresh tokens, or connection strings in logs or terminals.

---

## 2. Pre-Maintenance Inspection & Task Producer Drain Gate

Before pausing services or modifying database state, operators must verify that all task producers and queues are idle.

### A. Task Producers Architecture

In the ClipForge runtime, there are three distinct task producers that can dispatch publication work:

| Producer | Process / Container | Schedule / Trigger | Work Dispatched | Risk if Unpaused During Deployment |
|---|---|---|---|---|
| **Producer 1: APScheduler** | `clipforge_backend` | Every 60s (`auto_publisher`) | Calls `run_auto_publisher()` in `scheduler.py` | Could initiate uploads while worker bytecode is mismatched |
| **Producer 2: Celery Beat** | `clipforge_beat` | Every 120s (`recover-stranded-publish-jobs`), every 15s (`sweep-pending-decisions`) | Queues `publish_clip_task` in Celery | Could re-queue stranded publish jobs with unhardened worker |
| **Producer 3: REST API** | `clipforge_backend` | User/Operator HTTP POST requests | `publish-now`, `schedule`, `retry` | External HTTP requests queuing tasks during migration |

### B. Read-Only Pre-Drain Checks (Must All Equal Zero)

Execute the following read-only checks. If ANY check returns non-zero, **WAIT** for ongoing work to complete naturally before proceeding.

```powershell
# 1. Verify Celery Worker has 0 active, reserved, or scheduled tasks
docker compose exec -T worker celery -A backend.tasks.process_video.celery_app inspect active reserved scheduled

# 2. Verify Redis broker celery queue depth is 0
docker compose exec -T redis redis-cli llen celery

# 3. Verify PostgreSQL has 0 clips in queued or publishing status
py -3.12 -c "from backend.models.database import SyncSessionLocal; from backend.models.models import Clip; session = SyncSessionLocal(); print('Active publish clips:', session.query(Clip).filter(Clip.publish_status.in_(['queued', 'publishing'])).count()); session.close()"

# 4. Verify 0 video decisions in awaiting or customizing status
py -3.12 -c "from backend.models.database import SyncSessionLocal; from backend.models.models import VideoDecision; session = SyncSessionLocal(); print('Active decisions:', session.query(VideoDecision).filter(VideoDecision.status.in_(['awaiting_settings', 'customizing'])).count()); session.close()"
```

### C. Pause All Task Producers

Once all pre-drain checks confirm zero active jobs, pause task producers in exact order:

```powershell
# Step 1: Stop Celery Beat (Closes Producer 2)
docker compose stop beat

# Step 2: Stop FastAPI Backend (Closes Producer 1 and Producer 3)
docker compose stop backend
```

*Verification:* Confirm `clipforge_backend` and `clipforge_beat` report status `Exited`:
```powershell
docker compose ps
```

### D. Post-Pause Task Queue & Operational Database Recheck Gate

Do NOT assume an earlier pre-drain check remains valid. After pausing Beat and Backend, immediately execute this secondary gate to guarantee that zero tasks slipped into the queue or were picked up by the worker during the shutdown window:

```powershell
# 1. Re-verify Redis broker celery queue depth is strictly 0
$queueDepth = (docker compose exec -T redis redis-cli llen celery).Trim()
if ($queueDepth -ne "0") {
    throw "Post-pause gate FAILED: $queueDepth tasks remain in Redis celery queue! Do not proceed with migration."
}

# 2. Re-verify Celery worker has 0 active, reserved, or scheduled tasks
docker compose exec -T worker celery -A backend.tasks.process_video.celery_app inspect active reserved scheduled

# 3. Re-verify PostgreSQL has 0 active publishing clips
docker compose exec -T postgres psql -U clipforge_user -d clipforge -c "SELECT count(*) FROM clips WHERE publish_status IN ('queued', 'publishing');"
```

---

## 3. Binary-Safe Pre-Migration Database Backup

PowerShell output redirection (`>`) can alter character encoding (UTF-16 LE) and corrupt binary archive streams. To ensure 100% byte preservation independent of PowerShell version, the dump is generated directly inside the container and copied out using `docker cp`.

```powershell
# 1. Create host backup directory outside Git working tree
New-Item -ItemType Directory -Force -Path "D:\automation video clips\clipforge\data\backups"

# 2. Generate custom-format binary dump inside postgres container directly to file
docker compose exec -T postgres pg_dump -U clipforge_user -d clipforge -Fc -f /tmp/clipforge_pre_CFDEF013.dump

# 3. Check pg_dump exit code (must be 0)
if ($LASTEXITCODE -ne 0) { throw "pg_dump failed with exit code $LASTEXITCODE" }

# 4. Inspect dump archive Table of Contents inside container
docker compose exec -T postgres pg_restore -l /tmp/clipforge_pre_CFDEF013.dump | Select-Object -First 10

# 5. Copy validated archive to host backup directory with timestamp
$backupFileName = "clipforge_pre_CFDEF013_$((Get-Date).ToUniversalTime().ToString('yyyyMMdd_HHmmss'))Z.dump"
$hostBackupPath = "D:\automation video clips\clipforge\data\backups\$backupFileName"
docker cp clipforge_postgres:/tmp/clipforge_pre_CFDEF013.dump $hostBackupPath

# 6. Verify host backup file exists and has non-zero size
$backupItem = Get-Item $hostBackupPath
if (-not $backupItem.Exists -or $backupItem.Length -le 1024) {
    throw "Host backup verification failed: file missing or abnormally small ($($backupItem.Length) bytes)"
}

# 7. Independent SHA-256 Checksum Verification (Container vs Host)
$containerHash = ((docker compose exec -T postgres sha256sum /tmp/clipforge_pre_CFDEF013.dump).Trim().Split()[0]).ToLower()
$hostHash = (Get-FileHash -Path $hostBackupPath -Algorithm SHA256).Hash.ToLower()
if ($containerHash -ne $hostHash) {
    throw "SHA-256 verification FAILED! Container ($containerHash) does not match Host ($hostHash). Backup is corrupted!"
}
Write-Host "Backup successfully verified on host with matching SHA-256: $hostHash ($($backupItem.Length) bytes)"

# 8. Clean up container temporary dump file
docker compose exec -T postgres rm /tmp/clipforge_pre_CFDEF013.dump
```

---

## 4. Operational Migration Execution & Verification

### A. Migration Environment & Target Verification

To eliminate any host-to-container port mapping discrepancies or Python library version drift, the migration is executed via a one-off Docker container (`docker compose run`) on the internal bridge network (`postgres:5432`), using the exact production Docker image and application environment.

```powershell
# 1. Verify current database revision (must be d4e5f6a7b8c9)
docker compose run --rm -w /app/backend backend alembic current

# 2. Verify repository heads (must be e6f7a8b9c0d1)
docker compose run --rm -w /app/backend backend alembic heads
```

### B. Apply Migration

```powershell
# 3. Execute migration upgrade to head
docker compose run --rm -w /app/backend backend alembic upgrade head
```

### C. Read-Only Schema & Revision Verification

```powershell
# 4. Verify new database revision in alembic_version table (must equal e6f7a8b9c0d1)
docker compose exec -T postgres psql -U clipforge_user -d clipforge -c "SELECT version_num FROM alembic_version;"

# 5. Verify PostgreSQL information_schema reflects server default 'private'
docker compose exec -T postgres psql -U clipforge_user -d clipforge -c "SELECT column_name, column_default, is_nullable FROM information_schema.columns WHERE table_name = 'clips' AND column_name = 'privacy';"
```
*Expected output for clips.privacy:*
- `column_default`: `'private'::character varying`
- `is_nullable`: `NO`

---

## 5. Worker Restart & Service Restoration Sequence

Celery workers do not auto-reload Python modules when files on disk change. Restarting the worker process ensures that the updated [`publisher.py`](file:///d:/automation%20video%20clips/clipforge/backend/services/publisher.py) and [`clip_tasks.py`](file:///d:/automation%20video%20clips/clipforge/backend/tasks/clip_tasks.py) bytecode is loaded into memory before any tasks can be dispatched.

```powershell
# 1. Restart Celery Worker to load hardened bytecode
docker compose restart worker

# 2. Verify Worker health via Celery ping (must respond 'pong')
docker compose exec -T worker celery -A backend.tasks.process_video.celery_app inspect ping

# 3. Verify Worker runtime imported function signatures and defaults
docker compose exec -T worker python -c "
import inspect
from backend.services.publisher import upload_short
sig = inspect.signature(upload_short)
assert sig.parameters['privacy'].default == 'private', f'Expected private, got {sig.parameters[\"privacy\"].default}'
assert sig.parameters['license_type'].default is None, f'Expected None, got {sig.parameters[\"license_type\"].default}'
assert sig.parameters['made_for_kids'].default is None, f'Expected None, got {sig.parameters[\"made_for_kids\"].default}'
print('SUCCESS: Worker runtime bytecode verified with hardened privacy and clean fallbacks.')
"

# 4. Start FastAPI Backend (Restores REST API & APScheduler)
docker compose start backend

# 5. Verify Backend service health endpoint
py -3.12 -c "
import urllib.request, json
res = json.loads(urllib.request.urlopen('http://127.0.0.1:8000/api/health').read())
assert res['components']['api'] == 'ok'
assert res['components']['db'] == 'ok'
assert res['components']['worker'] == 'online'
print('SUCCESS: Backend API health check passed:', res)
"

# 6. Start Celery Beat LAST (Restores periodic scheduler ONLY after Worker & Backend pass all checks)
# WARNING: Do NOT start Beat before the worker and backend are confirmed healthy.
docker compose start beat
```

---

## 6. Post-Deployment Acceptance Verification

Execute non-mutating validation to confirm full system integrity:

```powershell
# 1. Run targeted privacy hardening unit suite (Mocked API calls only)
py -3.12 -m pytest backend/tests/test_publishing_privacy_hardening.py -v

# 2. Run combined publisher regression suites (107 tests total)
py -3.12 -m pytest backend/tests/test_publishing_privacy_hardening.py backend/tests/test_pipeline_config_fixes.py backend/tests/test_c06_metadata_editor.py backend/tests/test_publishing_destination_repair.py backend/tests/test_c05_publish_queue_actions.py -v

# 3. Verify zero live YouTube mutations occurred during deployment
docker compose exec -T postgres psql -U clipforge_user -d clipforge -c "SELECT id, youtube_short_id, privacy, publish_status FROM clips WHERE youtube_short_id IN ('0OfOivc-tpU', '39w4TLjreFU', 'L3ihlJVo_3A', 'FoNMm4F9qIM');"
```

---

## 7. Rollback Procedures & Failure Recovery

### A. Routine Migration Rollback (Single-Column Default Revert)

If post-deployment checks fail or an unexpected regression occurs in publisher tasks, perform the routine rollback. **Do NOT restore a full database backup.**

```powershell
# 1. Stop Celery Beat and Backend to pause producers
docker compose stop beat backend

# 2. Revert Alembic migration back to revision d4e5f6a7b8c9
docker compose run --rm -w /app/backend backend alembic downgrade d4e5f6a7b8c9

# 3. Verify database revision reverted
docker compose exec -T postgres psql -U clipforge_user -d clipforge -c "SELECT version_num FROM alembic_version;"

# 4. Verify clips.privacy server default was safely dropped (None)
docker compose exec -T postgres psql -U clipforge_user -d clipforge -c "SELECT column_name, column_default, is_nullable FROM information_schema.columns WHERE table_name = 'clips' AND column_name = 'privacy';"
```

#### Why `downgrade()` Sets `server_default=None`:
- Reverting to `'public'` would silently re-introduce the exact defect that caused historical public uploads (`CF-DEF-013`).
- Setting `server_default=None` leaves the column with `NOT NULL` enforcement. Any application INSERT that omits `privacy` fails closed with a constraint error rather than silently publishing video content publicly.
- The SQLAlchemy ORM model maintains `Clip.privacy = "private"`.

### B. Disaster Recovery Procedure (Severe Database Corruption ONLY)

> [!CAUTION]
> **HIGH RISK — OPERATIONAL DATA LOSS HAZARD:**  
> Full database restore using `pg_restore --clean` will **permanently destroy** all clip metadata, rendering jobs, transcriptions, decisions, and analytics created after the pre-migration backup was taken.  
> This procedure is strictly prohibited for standard migration rollbacks. It is reserved exclusively for unrecoverable disk corruption, container volume loss, or catastrophic DDL disasters, and requires multi-operator approval.

```powershell
# DISASTER RECOVERY ONLY — NEVER EXECUTE FOR ROUTINE ROLLBACK
# 1. Confirm all application services are stopped
docker compose stop backend worker beat

# 2. Execute restore from verified pre-migration backup file
docker cp $hostBackupPath clipforge_postgres:/tmp/restore.dump
docker compose exec -T postgres pg_restore -U clipforge_user -d clipforge --clean --if-exists /tmp/restore.dump
docker compose exec -T postgres rm /tmp/restore.dump

# 3. Verify database consistency and restart services
docker compose start backend worker beat
```

---

## 8. Explicit Rollback & Abort Conditions

The deployment MUST be aborted and rolled back immediately if any of the following occur:
1. `alembic upgrade head` encounters an unhandled exception or SQL syntax error.
2. `clips.privacy` column default in `information_schema` is not `'private'::character varying`.
3. Celery worker fails to respond to `ping` within 30 seconds of restart.
4. Worker runtime signature check reveals `upload_short` has an unexpected default.
5. `/api/health` returns HTTP status other than `200 OK` or reports unhealthy database/worker.
6. Any unit test in `test_publishing_privacy_hardening.py` fails.
