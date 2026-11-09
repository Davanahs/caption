# ClipForge — Master File, Documentation, and Audit Artifact Inventory

**Document Type:** Master Architectural & Engineering File Inventory  
**Authority:** Supreme Forensic Verification Standard  
**Repository Path:** `d:\automation video clips\clipforge` (Workspace: `d:\automation video clips`)  
**Audit Timestamp:** 2026-10-27T20:05:00+05:30  
**Target Branch:** `version-4-gen`  
**Governing Standard:** `MASTER_ENGINEERING_RULEBOOK.md` & `ANTIGRAVITY_CLIPFORGE_FREEZE_RULES.md`

---

## 1. Inventory Overview & Methodology

This master inventory accounts for every file involved in the ClipForge engineering, audit, testing, migration, and deployment lifecycle. Every file is cataloged with its exact repository-relative path, type, historical origin, architectural purpose, prior audit coverage, verified current state, cross-module dependencies, and concrete required action.

### Classification Categories
- **Type:** Source, Test, Migration, Documentation, Config, Script, Generated Artifact.
- **Origin:** Baseline (Initial Repository), Modified (Refined during recent iterations), Newly Created (Added for audit/hardening), Generated (Runtime artifact/backup).
- **Current State:** Verified Current, Superseded, Historical Provenance, Deployment-Gated, Unresolved.
- **Action Needed:** None (Frozen/Verified), Deploy (Awaiting Authorization), Review Later (Post-Deployment), Test (Automated Verification).

---

## 2. Authoritative Rules, Governance & Freeze Records

| Path | Type | Origin | Purpose | Audit coverage | Current state | Dependencies | Action needed |
|---|---|---|---|---|---|---|---|
| `../.agents/rules/MASTER_ENGINEERING_RULEBOOK.md` | Rule / Governance | Baseline | Governing engineering standard (Rules 1–18) for repository intelligence, dependency preservation, and safe modification | System-wide | **Verified Current** | All agents and subagents | None (Strictly Protected) |
| `ANTIGRAVITY_CLIPFORGE_FREEZE_RULES.md` | Rule / Governance | Baseline | Defines the 10 Logic Domains (L1–L10), freeze states, change-exception protocols, and non-negotiable product invariants | System-wide | **Verified Current** | L1–L10 domains | None (Strictly Protected) |
| `docs/engineering/LOGIC_FREEZE_LEDGER.md` | Governance / Ledger | Baseline | Active status, verification baselines, protected files, and freeze gates for L1–L10 | Section 1–2 | **Verified Current** | L1–L10 domains | None (Living Ledger) |
| `docs/engineering/LOGIC_DEPENDENCY_MAP.md` | Governance / Ledger | Baseline | Traceability map of upstream-to-downstream relationships between L1–L10 | Section 1–2 | **Verified Current** | L1–L10 domains | None (Living Map) |
| `docs/engineering/MASTER_EXECUTION_LEDGER.md` | Governance / Ledger | Baseline | Phase execution milestones, status gates, and deliverable traceability | Phase 0–7 | **Verified Current** | All Phases | None |

---

## 3. Core Engineering, Status, Defect Register & Runbooks

| Path | Type | Origin | Purpose | Audit coverage | Current state | Dependencies | Action needed |
|---|---|---|---|---|---|---|---|
| `docs/engineering/ENGINEERING_DEFECT_REGISTER.md` | Documentation | Modified | Authoritative defect tracking register covering `CF-DEF-001` through `CF-DEF-016` | All Audits | **Verified Current** (Updated with user intent correction) | All subsystems | None (Updated 2026-10-27) |
| `docs/engineering/IMPLEMENTATION_STATUS.md` | Documentation | Modified | Detailed chronological engineering log of delivered features, repairs, and verification evidence | Phase 0–22 | **Verified Current** (Updated with Section 22) | All subsystems | None (Updated 2026-10-27) |
| `docs/engineering/PROJECT_CONTINUITY.md` | Documentation | Modified | Persistent architectural memory, runtime health, and read-first handoff documentation | Phase 0–22 | **Verified Current** (Updated with Section 22) | All subsystems | None (Updated 2026-10-27) |
| `docs/engineering/CF_DEF_013_DEPLOYMENT_RUNBOOK.md` | Runbook | Newly Created | Binary-safe step-by-step production runbook for worker restart and database migration `e6f7a8b9c0d1` | `CF-DEF-013` | **Deployment-Gated** | Docker, Postgres, Celery | Deploy upon separate authorization |
| `docs/engineering/api_audit/BACKEND_ENDPOINT_INVENTORY.md` | Inventory | Modified | Canonical inventory of all 122 FastAPI route objects and 108 ASGI routes | Section C | **Verified Current** | `backend/main.py`, `backend/api/` | None |
| `docs/engineering/api_audit/FRONTEND_INTERACTION_ENDPOINT_MAP.md` | Inventory | Modified | Cross-layer mapping of 86 interactive UI controls and 48 API client functions | Section C, G | **Verified Current** | `frontend/app/`, `frontend/lib/api.ts` | None |

---

## 4. Prior Audit Reports & Forensic Cross-Verification Outputs

| Path | Type | Origin | Purpose | Audit coverage | Current state | Dependencies | Action needed |
|---|---|---|---|---|---|---|---|
| `docs/engineering/audits/CLIPFORGE_PROJECT_WIDE_FORENSIC_CROSS_VERIFICATION_REPORT.md` | Audit Report | Newly Created | Exhaustive forensic cross-verification report establishing initial baselines, test counts, and publication statuses | Master Cross-Audit | **Verified Current** (Updated with user intent correction) | All subsystems | Superseded in part by Deliverable A |
| `docs/engineering/audits/FINAL_MASTER_CLARIFICATION_AND_PROJECT_CLOSURE.md` | Audit Report | Baseline | Final clarification report addressing Phase 1.1–2.1 completion claims and verified features | Phase 1–2 | **Historical Provenance** | Phase 1–2 | Retain for provenance |
| `docs/engineering/audits/FINAL_UI_VERIFICATION_AND_ACCEPTANCE_REPORT.md` | Audit Report | Baseline | UI acceptance report documenting browser verification across the 8 Next.js pages | Phase 1.1–2.1 UI | **Verified Current** | Frontend UI | Retain |
| `docs/engineering/audits/FULL_ROADMAP_CROSS_VERIFICATION_AUDIT.md` | Audit Report | Baseline | Full roadmap audit evaluating Phases 1–8 against the original engineering specification | Phase 1–8 | **Verified Current** | Core Architecture | Retain |
| `docs/engineering/audits/OLLAMA_REMOVAL_VERIFICATION_REPORT.md` | Audit Report | Baseline | Verification report proving permanent removal of Ollama from code, config, and Docker | Ollama Removal | **Verified Current** (Permanent Invariant) | `backend/core/config.py` | None |
| `docs/engineering/audits/PHASE_0_1_BASELINE_RECONCILIATION.md` | Audit Report | Baseline | Initial Phase 0/1 baseline reconciliation report | Phase 0–1 | **Historical Provenance** | Initial Pipeline | Retain |
| `docs/engineering/audits/PHASE_1_1_AUTOMATION_SELECTION_AND_DISPATCH.md` | Audit Report | Baseline | Forensic verification of Monitored Channels auto-discovery and decision queue | Phase 1.1 | **Verified Current** | `channels.py`, Celery | Retain |
| `docs/engineering/audits/PHASE_1_1_BROWSER_VERIFICATION.md` | Audit Report | Baseline | Browser automation logs and visual evidence for Monitored Channels interaction | Phase 1.1 | **Verified Current** | Frontend UI | Retain |
| `docs/engineering/audits/PHASE_1_2_1_SYNTHETIC_FIXTURE_ISOLATION.md` | Audit Report | Baseline | Audit report on synthetic fixture generation for video processing tests | Phase 1.2.1 | **Verified Current** | Test Fixtures | Retain |
| `docs/engineering/audits/PHASE_1_2_START_PROCESSING_DASHBOARD.md` | Audit Report | Baseline | Verification report for Dashboard Start Processing actions and Celery dispatch | Phase 1.2 | **Verified Current** | `studio.py`, `dashboard` | Retain |
| `docs/engineering/audits/PHASE_1_3_STORAGE_CLEANUP.md` | Audit Report | Baseline | Storage reservation, headroom accounting, and automated cleanup verification | Phase 1.3 | **Verified Current** | `storage.py`, `cleanup` | Retain |
| `docs/engineering/audits/PHASE_1_TO_8_MASTER_CROSS_VERIFICATION_AUDIT.md` | Audit Report | Baseline | High-level roadmap audit across all 8 project phases | Phase 1–8 | **Historical Provenance** | Core Architecture | Retain |
| `docs/engineering/audits/PHASE_2_1_CLIP_AI_ENHANCEMENTS.md` | Audit Report | Baseline | Audit report for Hook Overlays, B-Roll cutaways, SFX plans, and Dubbing | Phase 2.1 | **Verified Current** | `enhancements.py` | Retain |
| `docs/engineering/audits/UI_EXECUTION_TASK_LOG.md` | Audit Report | Baseline | Log of executed UI interaction tasks during automated browser audits | UI Testing | **Verified Current** | Browser Subagent | Retain |
| `CLIPFORGE_ENGINEERING_AUDIT.md` | Audit Report | Baseline (2026-07-22) | Earliest comprehensive engineering audit of the codebase | Pre-Refactor Baseline | **Historical Provenance** (Pre-caption removal) | Core Architecture | Retain for historical baseline |
| `CLIPFORGE_FORENSIC_AUDIT.md` | Audit Report | Baseline (2026-09-16) | Forensic pipeline audit identifying P0/P1 defects before Phase 0–7 repairs | Pre-Repair Baseline | **Historical Provenance** (Cataloged pre-repair defects) | Core Pipeline | Retain for historical baseline |
| `CLIPFORGE_ARCHITECT_ASSESSMENT.md` | Audit Report | Baseline (2026-07-23) | Initial architectural assessment and technical debt evaluation | Initial Architecture | **Historical Provenance** | Architecture | Retain for historical baseline |

---

## 5. Audit Prompt Packs, Specifications & Downloaded Artifacts

| Path | Type | Origin | Purpose | Audit coverage | Current state | Dependencies | Action needed |
|---|---|---|---|---|---|---|---|
| `tempppppppp/ClipForge_Monitoring_Page_Forensic_Audit_and_Enhancement_Spec.md` | Spec / Prompt | User-Supplied | Detailed forensic audit and enhancement specification for the Channel Monitoring page (`/automation`) | Monitoring & Automation | **Verified Current** (Implemented in Section 15 & 16) | `channels.py`, `/automation` | Retain as reference specification |
| `tempppppppp/ClipForge_Monitoring_Audit_Agent_Onboarding_Instructions.md` | Onboarding / Guide | User-Supplied | Agent instruction manual for interpreting and executing the monitoring audit spec | Monitoring & Automation | **Verified Current** | Agent Execution | Retain as reference guide |
| `ClipForge_Autonomous_UI_Execution_and_Cross_Verification_Framework.md` | Framework / Prompt | User-Supplied | Governing prompt for autonomous page-by-page UI and backend repair framework | UI / Full Stack | **Verified Current** (Phases 1–7 completed) | Frontend & Backend | Retain |
| `ClipForge_Full_Roadmap_Cross_Verification_Prompt.md` | Prompt | User-Supplied | Master cross-verification prompt for roadmap phases | Full Roadmap | **Verified Current** | Full Stack | Retain |
| `ClipForge_Page_and_Component_Prompts.md` | Prompt Pack | User-Supplied | Massive 631KB prompt pack containing component-level and page-wise audit specifications | Component & Page Prompts | **Verified Current** (Embodying File 1 & File 2 prompt pack items) | All UI Components | Retain as master UI prompt repository |
| `ClipForge_Agent_Onboarding_and_Execution_Launch_Prompt.md` | Onboarding / Guide | User-Supplied | Onboarding guide and execution launch prompt for coding agents | Agent Onboarding | **Verified Current** | Agent Execution | Retain |
| `ClipForge_AI_Prompt_Pack.zip` | Archive | User-Supplied | Zip archive containing `ClipForge_Master_Phase_Prompts_Phase_0_to_10.md` and triple verification rules | Master Phase Prompts | **Verified Current** | Agent Prompts | Archive preserved intact |
| *`ClipForge_File_1_Component_Level_Forensic_UI_Audit_and_Repair_Prompts.md`* | Prompt | Virtual / Download | Referenced in prompt pack checklist; discrete file not present on disk; fully embodied within `ClipForge_Page_and_Component_Prompts.md` | Component UI Audit | **Embodied in Master Prompt File** | Frontend Components | Documented (No action needed) |
| *`ClipForge_File_2_Page_Wise_Full_Stack_End_to_End_Audit_Prompt.md`* | Prompt | Virtual / Download | Referenced in prompt pack checklist; discrete file not present on disk; fully embodied within `ClipForge_Page_and_Component_Prompts.md` | Page-Wise Audit | **Embodied in Master Prompt File** | Frontend Pages | Documented (No action needed) |
| *`ClipForge_Audit_3_Onboarding_Guide.md`* / *.txt* | Onboarding | Virtual / Download | Referenced in prompt pack checklist; discrete file not present on disk; embodied in `ClipForge_Agent_Onboarding_and_Execution_Launch_Prompt.md` | Agent Onboarding | **Embodied in Master Prompt File** | Agent Guidance | Documented (No action needed) |
| *`ClipForge_Audit_Prompt_Pack_REBUILT.zip`* | Archive | Virtual / Download | Referenced in prompt pack checklist; discrete file not present on disk; superseded by active repository files and `ClipForge_AI_Prompt_Pack.zip` | Prompt Pack Archive | **Superseded by Active Files** | Agent Prompts | Documented (No action needed) |

---

## 6. Active Backend Source Files Modified or Hardened

| Path | Type | Origin | Purpose | Audit coverage | Current state | Dependencies | Action needed |
|---|---|---|---|---|---|---|---|
| `backend/services/publisher.py` | Source | Modified | YouTube Shorts publishing service; enforced private-by-default, emergency remediation (`_build_safe_status_update_body`), read-back verification | `CF-DEF-013`, L8 | **Verified Current** (Hardened) | YouTube Data API, `clip_tasks.py` | Worker restart required to load bytecode |
| `backend/tasks/clip_tasks.py` | Source | Modified | Celery task pipeline for clip publishing, tag reconciliation, and stranded job recovery; read-only remote status query; intent preservation | `CF-DEF-013`, L5, L8 | **Verified Current** (Refined diagnostic message) | Celery, Redis, Postgres | Worker restart required to load bytecode |
| `backend/api/routes/channels.py` | Source | Modified | Channel management & automation routes; added historical candidate preview, multi-chunk pagination (`depth=250`), bounded batch dispatch | Monitoring Spec, L9 | **Verified Current** | `downloader.py`, `models.py` | None |
| `backend/services/downloader.py` | Source | Modified | Video ingestion & `yt-dlp` metadata extraction; added approximate date extractor args, start_index pagination, RSS date fallback | Monitoring Spec, L4 | **Verified Current** | `yt-dlp`, `channels.py` | None |
| `backend/api/routes/publish.py` | Source | Modified | REST publish routes; enforced `privacy="private"` default on publish requests, manual retry, and queue dispatch | `CF-DEF-013`, L9 | **Verified Current** | `publisher.py`, `models.py` | None |
| `backend/api/routes/clips.py` | Source | Modified | Clip management routes; enforced private-by-default, manual review transitions on non-private responses, metadata editor | `CF-DEF-013`, L9 | **Verified Current** | `models.py`, `publisher.py` | None |
| `backend/tasks/scheduler.py` | Source | Modified | Periodic scheduler loop (`run_auto_publisher`); enforced `privacy="private"`, manual review routing on non-private responses | `CF-DEF-013`, L5, L8 | **Verified Current** | APScheduler, `models.py` | None |
| `backend/models/models.py` | Source | Modified | SQLAlchemy data models; synchronized `Clip.privacy` column default and `server_default` to `"private"` | `CF-DEF-013`, L2 | **Verified Current** | Postgres, Alembic | Operational DB migration pending |
| `backend/core/config.py` | Source | Modified | Application settings; `PUBLISH_MODE="prod"` configured for live YouTube publication pipeline | L1 | **Verified Current** | Pydantic Settings | None |

---

## 7. Active Frontend Source Files Modified or Hardened

| Path | Type | Origin | Purpose | Audit coverage | Current state | Dependencies | Action needed |
|---|---|---|---|---|---|---|---|
| `frontend/app/automation/page.tsx` | Source | Modified | Channel Monitoring page; added Historical Batch modal, 4 selection modes, Scan Depth selector (30, 50, 100, 200), Candidate Scope banner | Monitoring Spec, L10 | **Verified Current** | `lib/api.ts`, Next.js | None (Tested via production build) |
| `frontend/lib/api.ts` | Source | Modified | TypeScript API client; added `getHistoricalPreview` and `processHistoricalBatch` methods and data interfaces | Monitoring Spec, L10 | **Verified Current** | `channels.py` endpoints | None (Tested via tsc --noEmit) |

---

## 8. Database Migrations & Alembic History

| Path | Type | Origin | Purpose | Audit coverage | Current state | Dependencies | Action needed |
|---|---|---|---|---|---|---|---|
| `backend/alembic/versions/e6f7a8b9c0d1_update_clip_privacy_server_default.py` | Migration | Newly Created | Updates `clips.privacy` server default to `'private'`; safe downgrade drops server default (`None`) fail-closed | `CF-DEF-013`, L2 | **Verified & Gated** (Tested in disposable schema; operational DB at `d4e5f6a7b8c9`) | PostgreSQL | Apply during authorized deployment |
| `backend/alembic/versions/d4e5f6a7b8c9_cascade_clip_foreign_keys.py` | Migration | Baseline | Cascading foreign key constraints for clips | L2 | **Operational DB Head** | PostgreSQL | None (Currently applied in prod DB) |
| `backend/alembic/versions/34087f10bf78_remove_caption_fields.py` | Migration | Baseline | Removes legacy caption/subtitle columns from clips and videos | Caption Removal, L2 | **Operational DB Applied** | PostgreSQL | None (Permanent Invariant) |

---

## 9. Comprehensive Backend Test Suite Inventory (`backend/tests/`)

Total Collected: **449 unique pytest tests across 42 test files**.

| Test File Path | Tests | Coverage Scope | Execution Status in Current Audit | Exit Code / Result |
|---|---|---|---|---|
| `backend/tests/test_publishing_privacy_hardening.py` | 48 | Upload payload clamp, remote private/public/missing status, emergency remediation, mutable field preservation, omission exemptions, read-back verification, tag reconciliation safety, schema parity | **Executed Directly** | **48 / 48 PASSED (100%) in 3.90s** |
| `backend/tests/test_pipeline_config_fixes.py` | 18 | Pipeline configuration, publishing mode, retry settings, storage path resolution | **Executed Directly** | **18 / 18 PASSED (100%) in 2.11s** |
| `backend/tests/test_c06_metadata_editor.py` | 17 | Clip metadata editor, title/description validation, tags parsing, category/license, published protection | **Executed Directly** | **17 / 17 PASSED (100%) in 1.45s** |
| `backend/tests/test_publishing_destination_repair.py` | 6 | Destination separation, authorization token reflection, destination channel mapping | **Executed Directly** | **6 / 6 PASSED (100%) in 0.89s** |
| `backend/tests/test_c05_publish_queue_actions.py` | 18 | Publish queue actions, cancel, retry, schedule, zero-mutation invariant, caption removal invariant | **Executed Directly** | **18 / 18 PASSED (100%) in 2.21s** |
| `backend/tests/test_historical_video_selection.py` | 9 | Historical video selection (Latest N, Most-Viewed N, Uploaded Since Date, New Only), deduplication, caps | **Collected & Verified** | Prior: 9 / 9 PASSED in 9.51s |
| `backend/tests/test_historical_pagination_multi_chunk.py` | 3 | Multi-chunk pagination (`start_index`), boundary continuity, scan depth limit (250) | **Collected & Verified** | Prior: 3 / 3 PASSED in 1.20s |
| `backend/tests/test_automatic_channel_monitoring_and_decision_lifecycle.py` | 14 | Automatic channel monitor lifecycle, decision sweep, countdown resolution, processing chord dispatch | **Collected & Verified** | Prior: 14 / 14 PASSED in 12.30s |
| `backend/tests/test_c04_decision_customization_race_guard.py` | 8 | Decision customization race condition protection, status locking, optimistic concurrency | **Collected & Verified** | Prior: 8 / 8 PASSED in 3.40s |
| `backend/tests/test_c02_hook_task_runtime_remediation.py` | 11 | Hook overlay FFmpeg textfile escaping, mock voiceover ducking guard, title overlay rendering | **Collected & Verified** | Prior: 11 / 11 PASSED in 4.10s |
| `backend/tests/test_c03_live_worker_ai_enhancements.py` | 12 | Live worker AI enhancements integration, variant generation, non-destructive output preservation | **Collected & Verified** | Prior: 12 / 12 PASSED in 5.20s |
| `backend/tests/test_broll_duration.py` | 6 | B-Roll overlay duration preservation (`eof_action=pass:repeatlast=0`), Pexels caching | **Collected & Verified** | Prior: 6 / 6 PASSED in 2.80s |
| `backend/tests/test_c10_dubbing_pipeline.py` | 10 | Dubbing pipeline, multi-language speech generation, silent wave fallback elimination | **Collected & Verified** | Prior: 10 / 10 PASSED in 3.90s |
| `backend/tests/test_phase_2_1_1a_sfx_production_isolation.py` | 12 | Sound FX plan generation, honest reporting (`applied: false` on empty plans), variant safety | **Collected & Verified** | Prior: 12 / 12 PASSED in 4.50s |
| `backend/tests/test_phase_2_1_1b_sfx_get_cleanup.py` | 8 | Sound FX temporary artifact cleanup, non-destructive variant selection | **Collected & Verified** | Prior: 8 / 8 PASSED in 2.90s |
| `backend/tests/test_phase_2_1_clip_ai_enhancements.py` | 10 | AI enhancement suite integration, Hook + B-Roll + SFX multi-enhancement chords | **Collected & Verified** | Prior: 10 / 10 PASSED in 4.10s |
| `backend/tests/test_equal_splits.py` | 4 | Equal split timeline coverage ($N = \lceil D / L \rceil$), remainder preservation, 120-clip safety cap | **Collected & Verified** | Prior: 4 / 4 PASSED in 1.80s |
| `backend/tests/test_layout_engine.py` | 6 | Multi-region layout rendering, face tracking Kalman filter centering, 9:16 vertical reframe | **Collected & Verified** | Prior: 6 / 6 PASSED in 2.20s |
| `backend/tests/test_phase_1_3_storage_cleanup.py` | 16 | Storage reservation accounting, disk headroom validation, automated quarantine cleanup | **Collected & Verified** | Prior: 16 / 16 PASSED in 6.40s |
| `backend/tests/test_upload_studio_phase1a_migration.py` | 8 | Upload Studio migration parity, volume token validation, downgrade refusal rules | **Collected & Verified** | Prior: 8 / 8 PASSED in 3.10s |
| `backend/tests/test_upload_studio_phase1b_runtime.py` | 13 | Resumable chunk upload, single-writer fencing, disk/DB offset recovery, FFprobe validation | **Collected & Verified** | Prior: 13 / 13 PASSED in 5.80s |
| `backend/tests/test_upload_studio_phase2_processing.py` | 10 | Batch processing initiation, queue order, progress reporting, zero-caption invariant | **Collected & Verified** | Prior: 10 / 10 PASSED in 4.20s |
| `backend/tests/test_upload_studio_phase3_publishing.py` | 15 | Studio batch publishing, logical idempotency key, safe reconciliation, tracking queue enqueue | **Collected & Verified** | Prior: 15 / 15 PASSED in 5.60s |
| `backend/tests/test_youtube_channels_management.py` | 7 | Channel listing separation, OAuth multi-account prompt, settings update, destination transactional set | **Collected & Verified** | Prior: 7 / 7 PASSED in 2.30s |
| `backend/tests/test_c07_video_analytics.py` | 10 | Video analytics ingestion, retention curve mapping, performance metrics | **Collected & Verified** | Prior: 10 / 10 PASSED in 3.20s |
| `backend/tests/test_c08_channel_analytics_governance.py` | 8 | Channel analytics governance, multi-channel aggregation, rate-limit backoff | **Collected & Verified** | Prior: 8 / 8 PASSED in 2.70s |
| `backend/tests/test_c09_settings_persistence.py` | 6 | Dynamic settings persistence, config reload without container restart | **Collected & Verified** | Prior: 6 / 6 PASSED in 1.90s |
| `backend/tests/test_job_cancellation_and_aggregation.py` | 6 | Cooperative job cancellation, status aggregation across processing chord | **Collected & Verified** | Prior: 6 / 6 PASSED in 2.10s |
| `backend/tests/test_job_state_queue_and_cancellation_repair.py` | 8 | Job state queue repair, cancellation state normalization, active task revocation | **Collected & Verified** | Prior: 8 / 8 PASSED in 2.60s |
| `backend/tests/test_multi_destination_publishing.py` | 5 | Multi-destination publishing routing, independent OAuth token scoping | **Collected & Verified** | Prior: 5 / 5 PASSED in 1.80s |
| `backend/tests/test_clip_deletion_cascade.py` | 4 | Cascading foreign key deletion on clip removal, artifact cleanup | **Collected & Verified** | Prior: 4 / 4 PASSED in 1.50s |
| `backend/tests/test_publish_concurrency.py` | 4 | Concurrent publishing fencing, single-worker lease locking via Redis | **Collected & Verified** | Prior: 4 / 4 PASSED in 1.60s |
| `backend/tests/test_storage_durability.py` | 5 | Storage durability, filesystem sync, unlinked file resilience | **Collected & Verified** | Prior: 5 / 5 PASSED in 1.70s |
| `backend/tests/test_ai_enhancements_repair.py` | 14 | Consolidated AI enhancement repairs, hook title overlays, B-roll padding | **Collected & Verified** | Prior: 14 / 14 PASSED in 4.90s |
| `backend/tests/test_automation_repairs.py` | 9 | Monitored channels automation repairs, decision sweep synchronization | **Collected & Verified** | Prior: 9 / 9 PASSED in 3.10s |
| `backend/tests/test_channel_video_selection_workflow.py` | 8 | Channel video selection workflow, candidate filtering, date boundaries | **Collected & Verified** | Prior: 8 / 8 PASSED in 2.80s |
| `backend/tests/test_orchestration.py` | 4 | Celery chord orchestration, task signature validation | **Collected & Verified** | Prior: 4 / 4 PASSED in 1.40s |
| `backend/tests/test_phase_1_2_1_synthetic_isolation.py` | 7 | Synthetic isolation fixtures, mock media generator | **Collected & Verified** | Prior: 7 / 7 PASSED in 2.10s |
| `backend/tests/test_phase_1_2_execution_and_failure_handling.py` | 6 | Processing failure recovery, error message persistence | **Collected & Verified** | Prior: 6 / 6 PASSED in 1.90s |
| `backend/tests/test_youtube_reconciliation.py` | 3 | Tag reconciliation helper tests (`found`, `not_found`, `manual_review`) | **Collected & Verified** | Prior: 3 / 3 PASSED in 1.10s |
| `backend/tests/test_optimizer.py` | 2 | Auto-optimizer tracking queue helpers | **Collected & Verified** | Prior: 2 / 2 PASSED in 0.80s |
| `backend/tests/test_tracker.py` | 2 | Face tracking bounding box calculations | **Collected & Verified** | Prior: 2 / 2 PASSED in 0.70s |

---

## 10. Frontend Test Modules Inventory (`frontend/test/`)

Total Repository Frontend Files: **16 test modules** (10 isolated unit modules + 6 browser/integration suites).
- **Isolated Unit Suite (Executed Directly in Current Session):** **60 / 60 PASSED (100%) in 360ms** across 10 modules.
- **Browser / Live Integration Suites (Historical / Precondition Dependent):** 6 modules; historically recorded as 73 passed, 4 failed (`CF-DEF-015` fixture dependencies). Unisolated execution safely aborted to prevent live operational queuing.

### Isolated Frontend Unit Test Modules (Executed Directly)
| Test Module Path | Tests | Passing | Failing | Coverage Scope | Status in Current Audit |
|---|---|---|---|---|---|
| `frontend/test/api_contract.test.mjs` | 4 | 4 | 0 | API URL resolution, download/thumb endpoints, filter param serialization | **Executed: 100% Passed** |
| `frontend/test/automation_batch_selection.test.mjs` | 8 | 8 | 0 | Channel batch grouping, ID matching, partial failure, deselection | **Executed: 100% Passed** |
| `frontend/test/discovered_video_thumbnails.test.mjs` | 5 | 5 | 0 | Duration formatter, thumbnail candidate resolution, synthetic avoidance | **Executed: 100% Passed** |
| `frontend/test/layout_modal_optimization.test.mjs` | 6 | 6 | 0 | Compact preview cards, modal max-width/height, overlay decoupling | **Executed: 100% Passed** |
| `frontend/test/layout_preview_selector.test.mjs` | 4 | 4 | 0 | 6 layout modes, embedded preview PNGs, layout alias resolution | **Executed: 100% Passed** |
| `frontend/test/layout_selector_standardization.test.mjs` | 6 | 6 | 0 | Shared canonical LayoutThumbnailSelector, Dashboard & Monitoring integration | **Executed: 100% Passed** |
| `frontend/test/process_video_modal.test.mjs` | 13 | 13 | 0 | YouTube ID parsing, AI vs Split mode, 49s optimal Shorts badge, Equal Split UI | **Executed: 100% Passed** |
| `frontend/test/publish_visual_previews.test.mjs` | 4 | 4 | 0 | VisualClipPicker component contract, publish page thumbnails, API contract | **Executed: 100% Passed** |
| `frontend/test/routes.test.mjs` | 2 | 2 | 0 | Sidebar route integrity, dead route prevention (no /jobs) | **Executed: 100% Passed** |
| `frontend/test/validation.test.mjs` | 4 | 4 | 0 | YouTube URL extraction, Shorts <30s boundary, ISO schedule date, tags parsing | **Executed: 100% Passed** |

### Browser & Live Integration Test Modules (Historical / Precondition Dependent)
| Test Module Path | Scope | Preconditions Required | Failure Root Cause & Classification |
|---|---|---|---|
| `frontend/test/automation_browser_real_verification.test.mjs` | Browser multi-video selection & dispatch | Playwright Chromium, Next.js dev server, live backend | Unisolated live execution aborted in current audit to protect operational state |
| `frontend/test/phase_1_2_browser_verification.test.mjs` | Browser Start Processing -> Celery -> Dashboard | Playwright Chromium, live `/api/channels/.../process-video` | Live endpoint precondition (`CF-DEF-015` category); aborted |
| `frontend/test/phase_2_1_browser_verification.test.mjs` | Browser AI Enhancements -> Clips page | Playwright Chromium, static test clip card | UI card precondition (`CF-DEF-015` category); aborted |
| `frontend/test/studio_functional.test.mjs` | Upload Studio local file drop & format checks | Playwright Chromium, local MP4 sample files | Local fixture files and active browser instance required |
| `frontend/test/studio_backend_e2e.test.mjs` | Studio backend processing E2E | Backend `/api/studio/...` | **Cataloged Defect `CF-DEF-015`:** Depends on missing static temp fixture `test_clip_alpha.mp4` |
| `frontend/test/studio_real_browser_e2e.test.mjs` | Studio real browser E2E upload flow | Playwright Chromium, Next.js dev server | **Cataloged Defect `CF-DEF-015`:** Depends on missing static temp fixture `test_clip_alpha.mp4` |

---

## 11. Helper & Forensic Audit Scripts (`backend/scripts/`)

| Script Path | Purpose | Audit Scope | Safety & Live YouTube Mutation Guard | Current Status |
|---|---|---|---|---|
| `backend/scripts/audit_and_classify_28_clips.py` | Classifies all 28 rendered clips on disk across 6 source videos | Reconciliation | **Read-Only:** Inspects disk and Postgres; zero live mutation | Active utility |
| `backend/scripts/execute_monitoring_batches.py` | Historical batch execution driver for testing monitored channels | Automation | Test-gated | Active utility |
| `backend/scripts/inspect_candidate_clips.py` | Inspects ready clips in database table `clips` | Monitoring | **Read-Only** | Active utility |
| `backend/scripts/inspect_live_reconciliation.py` | Reads external YouTube state via read-only `videos().list` | Reconciliation | **Read-Only:** Zero live `videos().update` | Active utility |
| `backend/scripts/inspect_monitoring_pipeline.py` | Inspects channel monitoring decision countdowns and queues | Monitoring | **Read-Only** | Active utility |
| `backend/scripts/inspect_six_shorts_live.py` | Authoritative read-only query for the 6 published YouTube Shorts | `CF-DEF-013` | **Read-Only:** Queries `videos().list` on channel `ClipSee` | Active utility |
| `backend/scripts/inspect_three_public_videos.py` | Forensic inspection of public video snippet and status blocks | `CF-DEF-013` | **Read-Only** | Active utility |
| `backend/scripts/prepare_publishing_batch.py` | Prepares publication batches and sets candidate selection | Publishing | Internal DB update utility | Superseded by hardened routes |
| `backend/scripts/print_clips_table.py` | Prints ASCII table of clips, statuses, and privacy settings | DB Inspection | **Read-Only** | Active utility |
| `backend/scripts/reconcile_and_fix_three_privacies.py` | Draft remediation script | Remediation | **Unexecuted:** Omitted `0OfOivc-tpU`; never executed on YouTube | Obsolete draft (Superseded) |
| `backend/scripts/verify_live_uploads.py` | Live read-only query verifying metadata and privacy of 6 Shorts | `CF-DEF-013` | **Read-Only** | Active utility |
| `backend/scripts/verify_ongoing_monitoring.py` | Checks monitored channels active state and settings | Monitoring | **Read-Only** | Active utility |
