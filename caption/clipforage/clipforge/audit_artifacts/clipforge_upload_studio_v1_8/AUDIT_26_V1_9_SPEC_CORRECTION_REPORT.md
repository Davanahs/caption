# ClipForge Upload Studio — Audit 26: Evidence-Gated v1.9 Specification Correction Report

**Audit Identifier:** AUDIT-26-SPEC-CORRECTION  
**Target Specification:** `audit_artifacts/clipforge_upload_studio_v1_8/CLIPFORGE_UPLOAD_STUDIO_V1_9_SPEC.md`  
**Evaluation Baseline:** Audit 25 Forensic Report (`AUDIT_25_V1_9_IMPLEMENTATION_READINESS.md`)  
**Execution Mode:** STRICT SPECIFICATION CORRECTION ONLY (No implementation, no migrations executed, no live API calls)  
**Date:** October 11, 2026  

---

## 1. Executive Summary & Verification Boundary

This report documents the comprehensive, evidence-gated correction of the **ClipForge Upload Studio v1.9 Technical Architecture Specification** (`CLIPFORGE_UPLOAD_STUDIO_V1_9_SPEC.md`) based on the forensic findings of Audit 25.

### Strict Execution Boundary Compliance
- **Specification-Only Changes:** Modifications were strictly confined to `audit_artifacts/clipforge_upload_studio_v1_8/CLIPFORGE_UPLOAD_STUDIO_V1_9_SPEC.md` and this report.
- **Zero Codebase Mutations:** No Python files, Alembic migrations, database rows, environment configurations, Docker resources, or Git history were modified or executed.
- **Zero Unverified Claims:** No theoretical test or planned migration has been documented as passed or executed at runtime. All verification procedures remain classified as **PLANNED (UNEXECUTED)** awaiting Phase 6 testing.
- **Preserved Core Subsystems:** The automated YouTube URL clipping pipeline (`POST /api/videos/url`), destination-specific OAuth token architecture, Whisper transcription for semantic scoring, complete caption/subtitle removal, and durable output namespaces remain 100% intact.

---

## 2. Audit 25 Finding Dispositions

Each finding from Audit 25 was evaluated against repository evidence, verified for architectural consistency, and assigned a formal disposition:

| Finding ID | Audit 25 Finding Summary | Severity | Disposition | Architectural Rationale & Correction Summary |
| :--- | :--- | :---: | :---: | :--- |
| **AUD25-MIG-01** | Missing backfills in executable `upgrade()` definition | P0 | **Accepted and corrected in specification** | Added all five required backfills to the executable `upgrade()` code block in Section 3.3. Reconciled Sections 3.2 and 3.3. |
| **AUD25-MIG-02** | Corrupted historical snapshot identifier mapping | P0 | **Partially accepted; remedy revised** | **Revision:** Rejected substituting source-video UUIDs and rejected introducing synthetic `UNKNOWN_HISTORICAL` strings. Implemented truthful resolution via `COALESCE(pt.youtube_video_id, c.youtube_short_id)` yielding `NULL` when unknown. Preserved provenance for manual reconciliation. Excised universal 11-char regex assertion. |
| **AUD25-MIG-03** | Missing foreign key on `upload_batches.active_video_id` | P0 | **Accepted and corrected in specification** | Added `active_video_id` foreign key referencing `videos(id)` with `ondelete='SET NULL'` in upgrade. Added symmetric constraint drop in `downgrade()`. |
| **AUD25-MIG-04** | Unchecked status domain causing migration failure | P0 | **Accepted and corrected in specification** | Added pre-migration fail-closed assertion verifying that only documented legacy statuses (`pending`, `publishing`, `success`, `completed`, `failed`) exist before applying constraints. Aborts upgrade on unexpected values. |
| **AUD25-MIG-05** | Irreversible `success` $\to$ `completed` normalization | P1 | **Accepted and corrected in specification** | Explicitly documented the one-way normalization in Section 3.2, 3.4, and the legacy reconciliation matrix. Downgrade preserves `completed` without synthesizing legacy `success`. |
| **AUD25-PUB-01** | Unsafe Phase 6 finalization split and partial commit race | P0 | **Accepted and corrected in specification** | Corrected Sections 4, 5, 6, and 7 so Phase 6 strictly establishes `remote_verified`. Phase 7 commits terminal status (`completed`), metadata snapshots, and `finalized` phase in a single atomic ACID transaction. |
| **AUD25-PUB-02** | Premature `published_at` timestamp on scheduled releases | P0 | **Accepted and corrected in specification** | Decoupled internal `scheduled_at`, remote `status.publishAt`, and actual public release `snippet.publishedAt`. Mandated `published_at` remains `NULL` until remote state establishes public release. |
| **AUD25-PUB-03** | Blind retry on `manual_review` targets risking duplicate uploads | P0 | **Accepted and corrected in specification** | Prohibited automated retries or re-invoking `videos.insert` on targets in `manual_review`. Specified human resolution protocol requiring manual action payload and audit logging before any state transition. |
| **AUD25-SEQ-01** | Stale worker continuation and insufficient fencing in sequential orchestration | P0 | **Accepted and corrected in specification** | Corrected Section 14.6 to document that `revoke(terminate=True)` and watchdog timeouts are not guaranteed fencing. Defined 5-milestone active lease fencing check against `execution_token` and attempt-isolated scratch directories (`outputs/studio_scratch/{video_id}_{token}/`). |
| **AUD25-CON-01** | TOCTOU race in 3-stream upload concurrency limit | P0 | **Accepted and corrected in specification** | Corrected Section 14.4.1 to eliminate unlocked count check. Specified atomic check-and-claim inside exclusive Level 2 batch row lock (`SELECT ... FOR UPDATE`), with explicit slot lifecycle. |
| **AUD25-CON-02** | Unordered multi-row locking risking database deadlocks | P1 | **Accepted and corrected in specification** | Defined Section 14.4.6 establishing a strict monotonic 3-level lock hierarchy: Level 1 (Coordinator) $\to$ Level 2 (Batch) $\to$ Level 3 (Video). Prohibited reverse-order acquisition. |
| **AUD25-STO-01** | Storage namespace collision and cleanup deletion risk | P0 | **Accepted and corrected in specification** | Aligned staging and source storage with `LocalStorageProvider` (`uploads/studio_staging/`, `uploads/studio_sources/`, `outputs/studio/`). Explicitly exempted studio staging and scratch paths from `backend/cleanup_storage.py`. |
| **AUD25-STO-02** | Incompatible `fcntl.flock` on Windows runtime | P1 | **Partially accepted; remedy revised** | **Revision:** Confirmed application environment includes Windows. Specified PostgreSQL row locks (`SELECT ... FOR UPDATE`) as the primary cross-platform concurrency barrier, combined with a platform-aware file lock adapter. |
| **AUD25-API-01** | Inaccurate YouTube Data API v3 quota contracts and writable properties | P1 | **Accepted and corrected in specification** | Updated Section 6 with official Google API quotas: dedicated 100 calls/day for `videos.insert`, 100 calls/day for `search.list`, 50 units for `videos.update`. Documented 5,000 UTF-8 byte limit and writable vs response-only property tables. |
| **AUD25-SEC-01** | Channel token resolution fallback risking wrong-account publishing | P0 | **Accepted and corrected in specification** | Specified strict destination-ID-based token resolution (`tokens/youtube_token_{channel_id}.json`) for Upload Studio, failing closed if missing, with zero fallback to global tokens. |
| **AUD25-SEC-02** | Unawaited coroutine invocations in AsyncIOScheduler | P1 | **Accepted and corrected in specification** | Documented scheduler repair (direct coroutine await) as a mandatory Phase 3 prerequisite before activating automated background publishing. |

---

## 3. Specification Sections Modified & Correction Details

### Section 1 & Section 2: Architecture Scope & Governance Register
- **Title & Prerequisite Clarification:** Updated document header to reflect Audit 26 corrections. Mandated that zero implementation authorization is granted until all P0 defects are resolved and prerequisites satisfied.
- **Unresolved Decision Isolation:** Maintained three product decisions as explicitly pending stakeholder sign-off:
  1. *ViewScore 8.0 Threshold Calibration:* Kept proposed normalized ratio formula as candidate awaiting approval; preserved existing URL-pipeline formula without alteration.
  2. *Raw Upload Retention Period:* Kept retention lifespan (immediate vs 24h grace) as pending decision.
  3. *Per-Channel Daily Upload Budget:* Kept the 20-uploads-per-channel daily limit as a proposal awaiting product sign-off.

### Section 3: Database Migration Specification (`f1b2c3d4e5f6`)
- **Executable `upgrade()` Reconciliation (§3.3):**
  - Added fail-closed status domain validation before creating `ck_target_status`.
  - Added Backfill 1: `status = 'success'` $\to$ `'completed'`.
  - Added Backfill 2: `publication_phase = 'finalized'` for completed targets; `'legacy_unmanaged'` for unfinalized legacy targets.
  - Added Backfill 3: Truthful historical snapshot resolution via `COALESCE(pt.youtube_video_id, c.youtube_short_id)` yielding `NULL` when unknown. Excised video UUID fallback and synthetic `UNKNOWN_HISTORICAL` strings.
  - Added Backfill 4: Circular foreign key `upload_batches.active_video_id` referencing `videos.id` with `ondelete='SET NULL'`.
  - Added Backfill 5: `format_type = 'short'` default for historical clips.
- **Fail-Closed `downgrade()` (§3.3):**
  - Added checks aborting downgrade if Studio batches, manual videos, or orphaned records exist.
  - Added symmetric removal of `fk_upload_batch_active_video`, `uq_batch_queue_pos`, all tables, and added columns.
- **Legacy Reconciliation Matrix (§3.4):**
  - Added formal table documenting each historical state, resulting migrated state, and preservation policy.

### Section 4 & Section 5: Publication State Machine & Terminal Finalization
- **Phase 6 / Phase 7 Decoupling (§4.2, §5.2):**
  - Phase 6 is strictly read-only verification (`remote_verified`).
  - Phase 7 commits terminal status (`completed`), metadata snapshots (`final_title`, `final_tags`, etc.), and `finalized` phase in a single atomic database transaction.
  - Defined recoverable Phase 7 crash protocol: if the worker crashes before or during transaction commit, recovery re-reads remote state and safely re-attempts Phase 7 commit without re-uploading bytes.
- **Timestamp Separation (§4.4, §5.3):**
  - `scheduled_at` (internal intended release time) and `status.publishAt` (Google API parameter) remain distinct from `published_at`.
  - `published_at` remains strictly `NULL` until remote API polling confirms the video is publicly visible.
- **`manual_review` Human Resolution Protocol (§5.4):**
  - Explicitly prohibited re-invoking `videos.insert` or restarting automated retries from `manual_review`.
  - Defined human action payload (`action IN ('link_existing', 'retry_upload', 'abandon')`) with mandatory audit logging in `OptimizationLog`.

### Section 6 & Section 7: YouTube Data API v3 Official Contracts & Security
- **Official Google Contracts (§6.1, §6.2):**
  - Documented official dedicated quotas: 100 calls/day dedicated for `videos.insert`, 100 calls/day for `search.list`, 50 units for `videos.update`.
  - Enforced 5,000 UTF-8 byte validation for video descriptions.
  - Provided comprehensive Writable Properties vs. Read-Only Properties reference tables.
- **Strict Destination Token Resolution (§7.1, §7.2):**
  - Specified channel-specific token lookup (`tokens/youtube_token_{channel_id}.json`).
  - Studio uploads fail closed immediately if channel token is missing, with zero fallback to global tokens.

### Section 9: Storage Architecture & Namespace Alignment
- **Namespace Integration (§9.1):**
  - Aligned staging path: `uploads/studio_staging/{batch_id}/{upload_id}.part`.
  - Aligned completed source path: `uploads/studio_sources/{upload_id}.{ext}`.
  - Aligned attempt-isolated scratch: `outputs/studio_scratch/{video_id}_{execution_token}/`.
  - Aligned durable outputs: `outputs/studio/{clip_id}.mp4` within protected `outputs/` namespace.
- **Storage Cleanup Exclusions (§9.3):**
  - Explicitly exempted Studio staging and scratch directories from `backend/cleanup_storage.py` age-based deletion.

### Section 14: Bulk Upload, Concurrency, Locking & Sequential Processing
- **Cross-Platform Mutex & Compensation Truncation (§14.3.3, §14.3.4):**
  - Replaced Unix `fcntl.flock` assumption with PostgreSQL row lock `SELECT * FROM videos WHERE id = :upload_id FOR UPDATE` as the authoritative cross-platform barrier.
  - Specified filesystem rollback truncation (`f.truncate(L)`) on restart/retry recovery.
- **Atomic Stream Slot Claim (§14.4.1):**
  - Eliminated TOCTOU race by evaluating active stream count and claiming slot inside Level 2 batch row lock.
  - Defined full slot lifecycle (claim, normal release, error release, disconnect timeout release).
- **Three-Level Lock Hierarchy (§14.4.6):**
  - Established monotonic lock order: Level 1 (Coordinator) $\to$ Level 2 (Batch) $\to$ Level 3 (Video).
  - Mathematically eliminated deadlock cycles across multi-entity operations.
- **Active Lease Fencing Protocol (§14.6.1, §14.6.2, §14.6.3, §14.6.5):**
  - Clarified that `revoke(terminate=True)` and watchdog timeouts are best-effort OS signals, not guaranteed termination.
  - Mandated active lease fencing checks against `execution_token` at 5 pipeline milestones (Pre-Whisper, Pre-Rendering, Pre-Promotion, DB Commit, Pre-Publish).
  - Mandated attempt-isolated scratch directories. Stale workers are locked out of promoting files or committing database changes.
  - Specified watchdog authoritative token supersession: rotates batch execution token before advancing orchestrator, ensuring old worker cannot commit authoritative side effects.

---

## 4. Remaining Unresolved Decisions & Product Governance

The following three items remain formally classified as **Product Decision Pending** and are isolated from architectural correctness:

1. **ViewScore Formula Scale Calibration (Section 2, Section 11):**
   - *Status:* Proposal awaiting stakeholder sign-off.
   - *Behavior:* Studio targets use the proposed candidate normalized ratio formula once approved; existing automated URL pipeline in `performance_tracker.py` remains 100% unaltered.
2. **Raw Upload Media Retention Period (Section 2, Section 9.3):**
   - *Status:* Pending product sign-off.
   - *Options:* Immediate deletion upon successful clipping vs. 24-hour grace period for creator re-clipping.
3. **Per-Channel Daily Upload Budget (Section 2, Section 6.1):**
   - *Status:* Proposal awaiting stakeholder approval.
   - *Behavior:* Documented as an optional business rule (20 uploads/channel/day); not hardcoded into system logic without product sign-off.

---

## 5. Final Defect Matrix (Post-Audit 26 Correction)

| Defect ID | Category | Original Severity | Post-Correction Status | Verification Evidence |
| :--- | :--- | :---: | :---: | :--- |
| **AUD25-MIG-01** | Migration Backfills | P0 | **RESOLVED** | Section 3.3 includes all 5 pre-constraint backfills in executable `upgrade()`. |
| **AUD25-MIG-02** | Snapshot ID Mapping | P0 | **RESOLVED** | Section 3.3 uses truthful `COALESCE(pt.youtube_video_id, c.youtube_short_id)` yielding NULL when unknown. |
| **AUD25-MIG-03** | Active Video FK | P0 | **RESOLVED** | Section 3.3 adds FK with `ondelete='SET NULL'` in upgrade and clean drop in downgrade. |
| **AUD25-MIG-04** | Status Domain Check | P0 | **RESOLVED** | Section 3.3 adds fail-closed pre-validation aborting upgrade on unexpected status values. |
| **AUD25-MIG-05** | Status Normalization | P1 | **RESOLVED** | Section 3.2, 3.4, and reconciliation matrix document one-way normalization. |
| **AUD25-PUB-01** | Phase 6/7 Finalization | P0 | **RESOLVED** | Section 4.2 & 5.2 decouple remote verification from atomic finalization transaction. |
| **AUD25-PUB-02** | Scheduled Timestamps | P0 | **RESOLVED** | Section 4.4 & 5.3 mandate `published_at` remains NULL until public release. |
| **AUD25-PUB-03** | Manual Review Retries | P0 | **RESOLVED** | Section 5.4 mandates human resolution protocol; prohibits duplicate `videos.insert`. |
| **AUD25-SEQ-01** | Sequential Fencing | P0 | **RESOLVED** | Section 14.6 specifies 5-milestone lease fencing and attempt-isolated scratch dirs. |
| **AUD25-CON-01** | Stream Limit TOCTOU | P0 | **RESOLVED** | Section 14.4.1 specifies atomic slot check-and-claim inside batch row lock. |
| **AUD25-CON-02** | Lock Hierarchy | P1 | **RESOLVED** | Section 14.4.6 defines strict Level 1 $\to$ Level 2 $\to$ Level 3 monotonic lock ordering. |
| **AUD25-STO-01** | Storage Namespace | P0 | **RESOLVED** | Section 9.1 & 14.3 align paths under `LocalStorageProvider` and exempt from cleanup. |
| **AUD25-STO-02** | Windows File Locking | P1 | **RESOLVED** | Section 14.3.3 establishes PostgreSQL row lock as authoritative cross-platform barrier. |
| **AUD25-API-01** | YouTube Quota Contracts | P1 | **RESOLVED** | Section 6 aligns with official Google dedicated daily quotas and 5,000-byte cap. |
| **AUD25-SEC-01** | Token Resolution | P0 | **RESOLVED** | Section 7.1 specifies strict channel-specific token resolution with zero fallback. |
| **AUD25-SEC-02** | Scheduler Async Await | P1 | **RESOLVED** | Section 12 mandates direct await in scheduler as Phase 3 prerequisite. |

**Current Residual Defect Count:**
- **P0 Defects:** 0 remaining.
- **P1 Defects:** 0 remaining.
- **P2 Defects:** 0 remaining.

---

## 6. Phase-by-Phase Go / No-Go Gate Matrix

| Implementation Phase | Phase Scope | Prerequisites Met? | Gate Verdict | Conditions for Proceeding |
| :--- | :--- | :---: | :---: | :--- |
| **Phase 0: Security & Environment Hardening** | Port bindings, OAuth file isolation, destination token mapping | YES | **GO (READY FOR REVIEW)** | Require code review of token resolution logic before deployment. |
| **Phase 1: Database Migration (`f1b2c3d4e5f6`)** | Schema tables, constraints, backfills, fail-closed downgrade | YES | **GO (READY FOR REVIEW)** | Test on isolated staging DB with production-like historical snapshot. |
| **Phase 2: Publishing Engine Core** | 7-Phase state machine, atomic Phase 7 finalization, retry safety | YES | **GO (READY FOR REVIEW)** | Implement mock YouTube API test harnesses for 308 resume and 409 conflict. |
| **Phase 3: Scheduler Repair** | Direct coroutine await in `AsyncIOScheduler` | YES | **GO (READY FOR REVIEW)** | Verify zero unawaited coroutine warnings in test environment. |
| **Phase 4: Backend Studio REST Router** | Ingestion endpoints, atomic slot claim, sequential orchestrator | YES | **GO (READY FOR REVIEW)** | Verify Level 1 $\to$ 2 $\to$ 3 lock acquisition order in integration tests. |
| **Phase 5: Frontend Studio Interface** | Bulk drag-and-drop, queue display, byte-accurate progress | YES | **GO (READY FOR REVIEW)** | Implement optimistic versioning conflict handler and WCAG keyboard support. |
| **Phase 6: Automated Regression & Sandbox Testing** | Full end-to-end sandbox verification, multi-worker stress tests | PENDING PHASES 0–5 | **HOLD** | Cannot execute Phase 6 until code implementation of Phases 0–5 is completed. |

---

## 7. Final Verdict

### Specification Assessment
The target specification `audit_artifacts/clipforge_upload_studio_v1_8/CLIPFORGE_UPLOAD_STUDIO_V1_9_SPEC.md` has been systematically reconciled against repository evidence and official Google API documentation. All identified P0 and P1 technical contradictions, data-loss hazards, TOCTOU races, fencing loopholes, and unsafe state transitions have been resolved.

### Readiness Statement
**The corrected v1.9 specification is internally coherent, technically sound, and READY FOR STAKEHOLDER ARCHITECTURAL REVIEW.**

> [!IMPORTANT]
> **Implementation Gate:** This audit and correction task was executed under strict read-only boundaries. No implementation code, database migrations, or live API calls were executed. Actual implementation planning may proceed only after formal stakeholder sign-off on the specification and the three pending product decisions.
