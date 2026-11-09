# ClipForge AI Regimen Ingestion & Master Prompt Coverage Report

**Document Type:** Authoritative AI Regimen Ingestion, Operating Protocol & Prompt Coverage Map  
**Governing Operating Procedure:** `ClipForge_AI_Execution_Rules_and_Triple_Verification.md` (File A)  
**Prompt Library:** `ClipForge_Master_Phase_Prompts_Phase_0_to_10.md` (File B)  
**Onboarding Specification:** `ClipForge_AI_Regimen_Onboarding_Prompt.md`  
**Repository Root:** `D:\automation video clips\clipforge`  
**Date of Ingestion:** 2026-10-24  
**Active Baseline Git Branch:** `version-4-gen` (Commit `0ba85ff`)  
**Active Alembic Migration Head:** `c3d4e5f6a7b8`  

---

## 1. Executive Summary & Companion File Ingestion Audit

Both companion instruction files were opened, read completely from beginning to end without skimming, and verified 100% accessible:

| File Identifier | Exact File Path | Line Count | Byte Size | Status | Verification Scope |
|---|---|---|---|---|---|
| **File A** | `D:\automation video clips\clipforge\ClipForge_AI_Prompt_Pack\ClipForge_AI_Execution_Rules_and_Triple_Verification.md` | 372 lines | 28,822 bytes | **Fully Ingested** | Read lines 1–372 in full. All 19 governing operating rules mapped. |
| **File B** | `D:\automation video clips\clipforge\ClipForge_AI_Prompt_Pack\ClipForge_Master_Phase_Prompts_Phase_0_to_10.md` | 3,766 lines | 466,676 bytes | **Fully Ingested** | Read lines 1–3,766 in full. All Parts A, B, C, D and 52 work-item prompts mapped. |
| **Onboarding Spec** | `D:\automation video clips\clipforge\ClipForge_AI_Prompt_Pack\ClipForge_AI_Regimen_Onboarding_Prompt.md` | 156 lines | 13,793 bytes | **Fully Ingested** | Read lines 1–156 in full. Governing 10 onboarding requirements satisfied. |

### Prompt Inventory Summary Counts (Calculated From Source)
- **Part A (Current Canonical Execution Queue):** **4** copy-ready prompts (`C-01` through `C-04`)
- **Part B (Legacy Product Roadmap, Phases 0.1–7):** **8** coordinator main phases, **33** copy-ready prompts (`ROADMAP-0.1.1` through `ROADMAP-7.3`)
- **Part C (Proposed Roadmap Extensions, Phases 8–10):** **3** coordinator main phases, **15** copy-ready prompts (`ROADMAP-8.1` through `ROADMAP-10.5`)
- **Part D (Universal Prompt Deliverables & Standards):** 1 governing deliverable protocol
- **Total Copy-Ready Work-Item Prompts:** **52 prompts**
- **Total Coordinator Main Phase Prompts:** **11 phases**
- **Total Prompt Blocks in File B:** **63 blocks**

---

## 2. Core Operating Regimen & Governance Synthesis

### A. Autonomy Protocol & Stop Boundaries
1. **Autonomous Progression:** When an active work item satisfies all three verification passes, updates documentation records, and satisfies its exit gate, the agent proceeds automatically to the next unblocked canonical work item without pausing for routine confirmation.
2. **Strict High-Impact Stop Boundaries:** Explicit user confirmation is strictly mandatory prior to:
   - Destructive deletion/cleanup of real user media, outputs, uploads, or DB records.
   - Irreversible or destructive database migrations.
   - Real publishing or uploading to YouTube or external platforms (test mode with synthetic media must always be used during tests).
   - Rotating, connecting, or disconnecting live Google OAuth credentials or account ownership.
   - Changing security trust boundaries or exposing backend ports beyond `127.0.0.1`.
   - Modifying or disclosing secrets.

### B. Formal Approach-Selection Methodology (Rule 17)
Before implementing any non-trivial change, the agent must:
1. **Define the Problem:** State expected vs observed behavior, cite concrete evidence, and categorize information into:
   - **Verified Fact** (observable in current files/tests/runtime).
   - **Inference** (logical derivation from facts).
   - **Assumption** (working hypothesis requiring proof).
   - **Unknown** (missing evidence requiring discovery).
2. **Compare Plausible Technical Approaches:** Contrast at least two (or three when meaningfully distinct) options:
   - *Option A:* Minimal local repair.
   - *Option B:* Reuse of established architecture/patterns.
   - *Option C:* Structural/architectural modification.
3. **Qualitative Matrix Evaluation:** Evaluate options against 10 criteria: Correctness, Data/Security Safety, Architecture Fit, Compatibility, Concurrency/Idempotency, Failure Recovery, Operational Impact, Reversibility, Testability, and Scope/Maintenance. Numerical scores are prohibited; decisions are justified through explicit technical trade-offs.

### C. Mandatory Three Verification Passes (Rule 7)
Every phase and subphase must execute and document all three passes in order:
1. **Pass 1 — Implementation & Acceptance Verification:** Execute focused tests for the root cause and edge cases; run affected module tests; run static checks (`npx tsc --noEmit`); inspect the diff to confirm only intended files changed.
2. **Pass 2 — Independent Adversarial Self-Challenge:** Adopt a critical reviewer perspective to challenge design assumptions: evaluate failure paths, stale data, concurrency races, malformed input, and production/test isolation. Add and execute adversarial tests.
3. **Pass 3 — Differential Re-Verification:** Compare the final Git diff and working tree against Pass 1 and Pass 2 evidence. Explicitly document any edits made between passes, rerun affected tests on the final tree, and confirm that all documentation reflects the final verified code.

### D. Distinction of Verification Evidence Tiers (Rule 8)
Evidence must never be conflated or inflated:
1. **Tier 1 (Source Inspection):** Code/configuration inspection only; does not prove runtime behavior.
2. **Tier 2 (Unit / Mocked Tests):** Isolated tests with mocked dependencies; does not prove worker or external behavior.
3. **Tier 3 (API Integration Tests):** ASGI HTTP requests against live FastAPI server and PostgreSQL database.
4. **Tier 4 (In-Process Task Execution):** Direct execution (e.g. `task.apply()`); does not prove worker daemon consumption.
5. **Tier 5 (Live Celery Worker Execution):** Live execution by an active Celery worker container consuming tasks from Redis.
6. **Tier 6 (Real Browser Verification):** Playwright automated browser interaction validating actual DOM rendering and network requests.
7. **Tier 7 (Full End-to-End Verification):** Complete UI + API + DB + live Celery worker + filesystem media artifact generation.

---

## 3. Comprehensive Prompt Coverage Map

### Section 1: Part A — Current Canonical Execution Queue (4 Prompts)

| Prompt ID | Title | Roadmap Section | Objective | Key Contracts & Call Sites | Prerequisites | Scope Boundary | Evidence Obligations |
|---|---|---|---|---|---|---|---|
| `C-01` | Canonical Phase 2.1.1B | Canonical Queue | Make SFX plan retrieval read-only; offload media analysis off FastAPI event loop | `backend/api/routes/clips.py`, `backend/services/virality_predictor.py`, `frontend/lib/api.ts` | Phase 2.1.1A.1 | Separate read-only GET (404 on missing) from explicit POST; `asyncio.to_thread` for FFprobe | Focused test suite, DB write-invariance test, thread assertion (**DELIVERED & VERIFIED**) |
| `C-02` | Hook Task Runtime Remediation | Canonical Queue | Resolve Celery worker failures in `apply_hook_task` and `analyze_hook_opportunities_task` | `backend/tasks/hook_tasks.py`, `backend/services/hook_generator.py`, `ClipRetention.analysis_json` | Phase 2.1.1B | Synchronous task event-loop bridge, schema normalization of `analysis_json`, managed artifact resolution | In-process and worker task execution, media validation, rendered `ClipVariant` |
| `C-03` | Live Docker Worker Refresh & AI Enhancement Verification | Canonical Queue | Refresh `clipforge_worker` container bytecode and verify end-to-end task execution | `docker-compose.yml`, Docker daemon, Redis Celery queues | `C-02` | Least disruptive worker reload; preserve persistent volumes and DB state | Live worker task consumption, Celery log trace, output artifact verification |
| `C-04` | Canonical Phase 2.2 (`CF-DEF-007`) | Canonical Queue | Single-video decision customization race condition guard | `backend/services/channel_monitor.py`, `backend/tasks/scheduler.py`, `VideoDecision` | `C-03` | Extend customization lease during active editing, guard Celery Beat sweep | Concurrent lease tests, sweep simulation, state-transition assertions |

---

### Section 2: Part B — Legacy Product Roadmap Prompts (8 Main Phases, 33 Subphase Prompts)

*Note: Aliased with `ROADMAP-*` to eliminate phase-number collisions with actual canonical execution history.*

#### Main Phase 0.1: Reconcile Baseline (Coordinator)
- `ROADMAP-0.1.1`: Git state and migration history (`alembic/versions/`, `git status`)
- `ROADMAP-0.1.2`: API and frontend inventories (`BACKEND_ENDPOINT_INVENTORY.md`, `FRONTEND_INTERACTION_ENDPOINT_MAP.md`)
- `ROADMAP-0.1.3`: Historical test evidence reconciliation (Verify 0 skipped/false green claims)
- `ROADMAP-0.1.4`: Active defect register (`ENGINEERING_DEFECT_REGISTER.md`)

#### Main Phase 1: Automation & Channel Integrity (Coordinator)
- `ROADMAP-1.1`: Multi-video batch processing (`channels.py`, multi-channel batch isolation)
- `ROADMAP-1.2`: Start Processing to Dashboard (Durable `Job` creation, Celery chord, dashboard progress link)
- `ROADMAP-1.3`: Channel disconnection and source/destination role separation (`youtube_channels.py`, token isolation)
- `ROADMAP-1.4`: Multi-account OAuth security (`prompt=select_account consent`, scoped tokens)
- `ROADMAP-1.5`: Shorts analytics accuracy (Duration <= 60s cap, honest metric labeling)
- `ROADMAP-1.6`: Publishing settings application (Per-channel defaults and presets)

#### Main Phase 2: API Connections & Safe Cleanup (Coordinator)
- `ROADMAP-2.1`: RetentionHeatmap API URLs (Eliminate relative URL fetch bug `CF-DEF-002`)
- `ROADMAP-2.2`: Cleanup preview endpoint (`GET /api/clips/cleanup/preview`, HMAC signed token lease)
- `ROADMAP-2.3`: Cleanup execution endpoint (`POST /api/clips/cleanup/execute`, staged quarantine isolation)
- `ROADMAP-2.4`: Inventory and contract reconciliation (Route catalog and frontend map synchronization)

#### Main Phase 3: Clips & AI Enhancement Workflows (Coordinator)
- `ROADMAP-3.1`: Hook generation and application (`hook_tasks.py`, `ClipHookPlan`)
- `ROADMAP-3.2`: B-roll planning and application (`broll_planner.py`, `ClipVisualPlan`)
- `ROADMAP-3.3`: SFX planning and application (`sfx_planner.py`, `ClipSFXPlan`, ducked audio)
- `ROADMAP-3.4`: Clips workflow consistency (Preview modal multi-tab synchronization)

#### Main Phase 4: Publishing Management (Coordinator)
- `ROADMAP-4.1`: Cancel publishing (`POST /api/publish/queue/{id}/cancel`, Celery revoke)
- `ROADMAP-4.2`: Retry publishing (`POST /api/publish/queue/{id}/retry`, re-enqueue)
- `ROADMAP-4.3`: Publish-status polling (Active queue polling, terminal state feedback)
- `ROADMAP-4.4`: Metadata editor integration (In-place title, description, and tags editor on publish cards)

#### Main Phase 5: Analytics & Optimization (Coordinator)
- `ROADMAP-5.1`: Per-video performance details (Drilldown cards for video-level metrics)
- `ROADMAP-5.2`: SEO diagnostics (Hashtag, title score, and retention curve recommendations)
- `ROADMAP-5.3`: Tracking queue lifecycle (Automated polling of published video performance)
- `ROADMAP-5.4`: Optimization lifecycle (A/B testing and auto-tuning recommendations)

#### Main Phase 6: Settings Persistence (Coordinator)
- `ROADMAP-6.1`: Settings contract and security (Define persistent settings schema and auth)
- `ROADMAP-6.2`: Backend settings API (`GET/PUT /api/settings`)
- `ROADMAP-6.3`: Frontend settings persistence (Migrate from localStorage to backend API)
- `ROADMAP-6.4`: Runtime-effect verification (Confirm system honors stored settings)

#### Main Phase 7: Final Integration & Regression (Coordinator)
- `ROADMAP-7.1`: End-to-end acceptance matrix (Full pipeline run from intake to publish)
- `ROADMAP-7.2`: Cross-subsystem data consistency (Reconcile DB rows against filesystem media)
- `ROADMAP-7.3`: Documentation and freeze (Final ledger lock, documentation closure)

---

### Section 3: Part C — Proposed Roadmap Extension Prompts (3 Main Phases, 15 Subphase Prompts)

*Note: Marked strictly as PROPOSED. Not authorized for implementation until explicit user approval and requirement discovery.*

#### Main Phase 8 (PROPOSED): Production Hardening (Coordinator)
- `ROADMAP-8.1`: Trust-boundary and security audit
- `ROADMAP-8.2`: Dependency and container reproducibility
- `ROADMAP-8.3`: Secrets and credential lifecycle
- `ROADMAP-8.4`: Error handling and operational health
- `ROADMAP-8.5`: Backup, restore and recovery drill

#### Main Phase 9 (PROPOSED): Performance & Reliability (Coordinator)
- `ROADMAP-9.1`: Queue and worker capacity baseline
- `ROADMAP-9.2`: Timeouts, retries and idempotency
- `ROADMAP-9.3`: Storage lifecycle and artifact reconciliation
- `ROADMAP-9.4`: Database performance and concurrency
- `ROADMAP-9.5`: Observability and incident diagnosis

#### Main Phase 10 (PROPOSED): Release Readiness & Maintenance (Coordinator)
- `ROADMAP-10.1`: Requirements and acceptance closure
- `ROADMAP-10.2`: Clean-environment installation rehearsal
- `ROADMAP-10.3`: Production deployment checklist
- `ROADMAP-10.4`: Rollback and incident recovery rehearsal
- `ROADMAP-10.5`: Final release gate and maintenance handoff

---

## 4. Current Repository State & Canonical Next Work Item

### A. Current Verified Status
1. **Phase 2.1.1B (`C-01`):** **DELIVERED & VERIFIED.** Read-only `GET /api/clips/{id}/sfx-plan` and explicit `POST /api/clips/{id}/sfx-plan` implemented with `asyncio.to_thread` event-loop offloading. Verified via 9/9 passed tests in `test_phase_2_1_1b_sfx_get_cleanup.py` and 63/63 system regression pass.
2. **Current Alembic Head:** `c3d4e5f6a7b8` (24 linear revisions).
3. **Current ASGI Route Count:** 110 route objects (103 API endpoints).
4. **Current Working Tree:** Clean baseline preserved; zero destructive git commands executed.

### B. Canonical Next Work Item Justification
- **Canonical Next Prompt:** **`C-02`: Hook task runtime remediation**
- **Evidence-Based Rationale:**
  - `C-01` is confirmed delivered in current code and engineering ledgers.
  - Section 8.A of `docs/engineering/audits/PHASE_2_1_CLIP_AI_ENHANCEMENTS.md` documents that `apply_hook_task` currently fails in Celery worker execution due to `RuntimeError: There is no current event loop in thread 'MainThread'` on line 145 of `backend/tasks/hook_tasks.py`.
  - Furthermore, `analyze_hook_opportunities_task` fails when `ClipRetention.analysis_json` is stored as a raw list of risk dictionaries rather than an unpacked `RetentionAnalysis` model.
  - Addressing `C-02` resolves the known worker failure before attempting container reload in `C-03`.
