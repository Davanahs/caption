# ClipForge Master Phase Prompt Pack — Detailed Copy-Ready Prompts, Phases 0.1–10

**Revision:** Expanded prompt specification, generated 24 October 2026.  
**Repository reported by project records:** `D:\automation video clips\clipforge` (agent must recheck current location/state).  
**Companion rules:** `ClipForge_AI_Execution_Rules_and_Triple_Verification.md`.  
**AI-maintained rationale record:** `docs/engineering/AI_DECISION_LOG.md`.

## Purpose and standard format

This is a prompt library, not a claim that every work item is still open. Each prompt is intended to be copied and run independently. The agent must reconcile the current repository state before acting. If a requested scope is already complete and evidence confirms it, the correct action is to verify/document and make no redundant code change.

Every individual prompt explicitly requires this format: (1) problem and objective, (2) preflight/source evidence, (3) comparison of plausible approaches, (4) evidence-based method choice and rejected alternatives, (5) narrow implementation boundaries, (6) acceptance tests and cross-verification, (7) three verification passes, (8) post-implementation self-questioning, (9) documentation/decision record, and (10) honest stop/continue decision. The full instructions are repeated in each copy-ready prompt so it can be used in isolation.

### Important phase-number collision rule

The user-supplied roadmap has legacy phase numbers that conflict with actual implementation history. For example, current canonical Phase 1.3 is reported as storage cleanup, while `ROADMAP-1.3` below means channel disconnection/source-destination separation. The old roadmap's `ROADMAP-2.2` means cleanup preview, while canonical Phase 2.2 currently means `CF-DEF-007` single-video decision customization race guard. **Never renumber or overwrite historical work.** Use `ROADMAP-*` IDs for the original product roadmap and canonical IDs from `PHASE_TRACKER.md` for actual execution.

### Current product invariants

- No caption/subtitle generation, SRT/ASS, karaoke highlighting, subtitle font rendering, or subtitle burn-in. Transcription remains allowed for internal scoring, semantic analysis and metadata.
- Shorts output duration remains capped at 30 seconds unless the owner explicitly changes it.
- Preserve all existing tracked changes and untracked files. Never use destructive resets/blanket reverts.
- Tests must not publish real YouTube content. Use synthetic fixtures, isolated test context and mock providers.
- Do not destroy persistent DB/storage/token volumes. High-impact actions against actual user data or real accounts require owner authorization.
- Distinguish UI “queued” from task completion and in-process task execution from a live Celery worker.

## How to use this pack

1. Install the companion rules file in the agent's persistent project instruction location; keep this file as the prompt library.
2. Start with **Current canonical execution queue** below. Do not jump directly into an old roadmap item whose implementation may already exist.
3. The agent proceeds autonomously through the next unblocked work item after all three verification passes; it does not ask for routine approval between subphases. It stops for genuine blockers and high-impact irreversible actions.
4. A main-phase prompt is a coordinator: it executes the child prompts sequentially, not as one large patch. Every child prompt is a separate freeze/verification boundary.
5. Phases 8–10 are marked **PROPOSED** because the supplied roadmap formally defines only phases through 7. Their prompts begin with discovery, scope validation and acceptance definition; do not invent product features or claim the owner approved them.

---

# PART A — Current canonical execution queue

**Source of truth:** current repository files, latest defect register, phase tracker and audits. The queue below reflects reports as of 24 October 2026 and must be rechecked before execution.



### Copy-ready prompt — C-01: Canonical Phase 2.1.1B

```text
You are the ClipForge engineering agent working in `D:\automation video clips\clipforge`.

WORK ITEM: C-01 — Canonical Phase 2.1.1B
STATE: Reconcile current repository state before acting. Do not assume this item is open just because it appears in the roadmap.

1. PROBLEM / OBJECTIVE
SFX plan retrieval must be read-only; explicit generation must not block the FastAPI event loop.

2. PREFLIGHT AND EVIDENCE COLLECTION
Read `AGENTS.md`, the applicable freeze/rule files, `docs/engineering/PHASE_TRACKER.md`, `MASTER_EXECUTION_LEDGER.md`, `IMPLEMENTATION_STATUS.md`, `ENGINEERING_DEFECT_REGISTER.md`, `PIPELINE_CATALOG_AND_DEPENDENCY_GRAPH.md`, `FRONTEND_PAGE_FEATURE_INVENTORY.md`, `PROJECT_CONTINUITY.md`, and the newest relevant audit/decision-log entries. Read only files relevant to this scope in depth, but reconcile any status claims before editing.
Inspect actual current source, schema, runtime route/client/task contracts, tests and caller/callee relationships. Reproduce the reported behavior with a safe isolated fixture where feasible. Separate VERIFIED FACTS, INFERENCES and UNKNOWNS. Record exact file paths, line ranges, commands and observed outputs.
Inspect `backend/api/routes/clips.py`, `backend/services/sfx_planner.py`, `ClipSFXPlan`, `ClipRetention`, `ViralityPredictor.analyze_clip()` and all call sites, `frontend/lib/api.ts`, the Clips preview UI, Celery task patterns, and the current audit. The historic audit reported that GET committed both retention and plan records and ran synchronous FFprobe work; re-prove each claim before changing anything.
Capture `git status --short`, branch/commit, existing diff/untracked inventory and relevant environment/container identity before editing. Protect all pre-existing changes. Do not assume old hashes, route counts, schema revisions or historic reports still reflect the current environment.

3. COMPARE APPROACHES AND JUSTIFY THE CHOICE
Alternative evaluation required: Compare (A) keep current GET side effects, (B) make GET read-only and add explicit POST generation, (C) shift all generation to Celery. Compare correctness, UX contract, latency, idempotency, DB consistency, operational complexity and compatibility. Pick the smallest approach that meets read-only semantics and moves expensive work off-loop. Record why other options are rejected.
Before coding, write a small comparison table in the decision log: option; correctness against acceptance criteria; data/security risk; compatibility; concurrency/idempotency; complexity/maintenance; reversibility; evidence for/against. Do not create arbitrary numerical scores. Explain why the chosen approach is proportionate to the proven root cause and why each rejected alternative is inferior for this evidence.
If the current implementation already meets the requirement, choose verification-only and avoid a redundant change. If requirements remain ambiguous and a wrong choice would be consequential, stop at a documented blocker rather than invent behavior.

4. IMPLEMENTATION BOUNDARY
Implement only this work item. Prefer the smallest complete, maintainable fix using existing models, APIs, task lifecycle, storage/artifact and frontend patterns. Avoid duplicate frameworks, helpers, routes, state machines, database fields or tests when an existing abstraction meets the requirement.
Preserve all unrelated behavior and frozen components. Do not remove code based on apparent lack of callers without a call-site/dependency audit. Do not change public API semantics without documenting callers, compatibility plan and tests. Any migration must be justified, forward-only and data-preserving.
Scope-specific acceptance criteria:
- GET returns persisted state only and does not create/update plan or retention rows, synthesize mock assets, dispatch generation, or run expensive analysis.
- Missing-plan behavior is deterministic and compatible with the current UI contract; choose empty result vs 404 based on actual API conventions and document it.
- Generation is explicit through an existing or narrowly added POST action. It validates clip/media, persists result, returns actionable failure, and cannot duplicate/conflict under repeated or concurrent requests.
- Synchronous media analysis is moved off the event loop using established patterns; AsyncSession is never shared across threads/tasks.
- Trusted test-context authorization from Phase 2.1.1A.1 remains authoritative. Apply-SFX behavior, cancellation, artifact owner/retention and normal assets stay intact.

5. REQUIRED TESTING
Add focused regression tests for the root cause and relevant negative, failure, boundary, retry, concurrency and stale-state paths. Assert durable database/filesystem/worker state as applicable, not only mocked return values. Use synthetic media, disposable test records and test provider mode. Never publish to real YouTube or destructive-clean real data.
- Repeated GET has zero relevant database changes.
- GET of missing plan has no write, synthesis, dispatch or FFprobe invocation.
- POST generation succeeds on valid fixture and reports failures accurately.
- Concurrent POSTs are idempotent or serialize consistently.
- Invalid/missing media, predictor failure, DB failure and frontend refresh are exercised.
- Existing SFX isolation, storage lifecycle and orchestration regressions; frontend typecheck/build when touched.
Run the exact focused suite, relevant regressions, static checks and build/browser/integration tests required by the changed layers. Capture actual commands, counts, exit codes, warning/failure output and environment. Do not claim a test ran if only drafted or launched without a completed result.

6. THREE VERIFICATION PASSES — REQUIRED FOR THIS ITEM
PASS 1 — Implementation verification: review diff against every acceptance criterion; run focused tests and the affected workflow; prove expected state and failure behavior.
PASS 2 — Independent challenge: stop thinking like the implementation author. Re-read the requirement and original defect evidence. Try to falsify the fix with adversarial inputs, conflicts, retries, parallel requests, stale state and failure injection. Compare alternative approaches again. Inspect whether the tests could pass while production is still broken. Fix any issue discovered and record changes since Pass 1.
PASS 3 — Differential re-verification: re-read the final diff and working tree from scratch. Compare final code with Passes 1 and 2, identify all changes introduced after each earlier pass, rerun affected focused tests and relevant regressions against the final tree, and verify reports/status files match the final code. Any new code change invalidates the affected previous pass; repeat it.

7. EXPLICIT SELF-CHALLENGE QUESTIONS
- What concrete evidence proves the original problem existed?
- Why does each changed line/function need to exist?
- What alternative was considered and why was it rejected?
- Could a real production record or untrusted caller reach the test/mock path?
- What happens on failure, retry, concurrency, restart and stale response?
- What does this test prove, and what does it not prove?
- Did I preserve all previous working-tree files and frozen behavior?
- What changed between verification passes and why?
- Which claims remain unverified or depend on an environmental assumption?

8. REQUIRED RECORDS AND FINAL RESPONSE
Update only applicable canonical documents: phase tracker, master ledger, implementation status, defect register, relevant API/frontend/pipeline inventories, audit report and `docs/engineering/AI_DECISION_LOG.md`. Preserve old audit records and append corrections instead of rewriting history. Make status consistent everywhere.
Record work-item ID, before/after working-tree status, root cause, option comparison and rationale, files changed and purpose, relevant hashes if practical, each pass and test result, evidence tier (source/unit/mock/API/in-process/live worker/browser/full E2E), risks, limitations and next dependency.
Report statuses honestly: DELIVERED & VERIFIED, PARTIALLY VERIFIED, BLOCKED or REOPENED. Do not say full E2E without the real required components running together.

9. STOP / CONTINUE RULE
Do not start a different implementation item in parallel or expand this scope to unrelated fixes. Complete all three passes, update records and then continue automatically to the next unblocked item in the master execution queue without waiting for routine approval. Stop only for a real blocker, unresolved high-impact product choice, credential/account action, real publication, destructive action against actual data, or an environment change that requires owner authorization. If blocked, document exact evidence and work safely on independent unblocked work only if it does not depend on the blocker.
Never use `git reset`, `git clean`, blanket reverts, destructive DB resets, `docker compose down -v`, or broad file deletion. Do not reintroduce captions/subtitles; preserve transcription for internal scoring/semantic analysis; retain the frozen Shorts duration limit unless the owner explicitly changes it.
```


### Copy-ready prompt — C-02: Hook task runtime remediation

```text
You are the ClipForge engineering agent working in `D:\automation video clips\clipforge`.

WORK ITEM: C-02 — Hook task runtime remediation
STATE: Reconcile current repository state before acting. Do not assume this item is open just because it appears in the roadmap.

1. PROBLEM / OBJECTIVE
Hook planning/application previously failed in task execution despite browser UI dispatch; reported issues include event-loop use, retention JSON shape and non-managed media paths.

2. PREFLIGHT AND EVIDENCE COLLECTION
Read `AGENTS.md`, the applicable freeze/rule files, `docs/engineering/PHASE_TRACKER.md`, `MASTER_EXECUTION_LEDGER.md`, `IMPLEMENTATION_STATUS.md`, `ENGINEERING_DEFECT_REGISTER.md`, `PIPELINE_CATALOG_AND_DEPENDENCY_GRAPH.md`, `FRONTEND_PAGE_FEATURE_INVENTORY.md`, `PROJECT_CONTINUITY.md`, and the newest relevant audit/decision-log entries. Read only files relevant to this scope in depth, but reconcile any status claims before editing.
Inspect actual current source, schema, runtime route/client/task contracts, tests and caller/callee relationships. Reproduce the reported behavior with a safe isolated fixture where feasible. Separate VERIFIED FACTS, INFERENCES and UNKNOWNS. Record exact file paths, line ranges, commands and observed outputs.
Re-inspect `backend/tasks/hook_tasks.py`, Hook plan models and routes, `RetentionAnalysis` and stored `analysis_json`, task registration, current worker logs, artifact manager/download contexts, render graph, `ClipVariant` and `ArtifactRecord`. Historical exceptions are hypotheses until reproduced against current source and current worker.
Capture `git status --short`, branch/commit, existing diff/untracked inventory and relevant environment/container identity before editing. Protect all pre-existing changes. Do not assume old hashes, route counts, schema revisions or historic reports still reflect the current environment.

3. COMPARE APPROACHES AND JUSTIFY THE CHOICE
Alternative evaluation required: Compare synchronous task bridge choices only after proving the call context, schema normalization choices based on actual stored JSON, and managed artifact resolution reuse vs existing validated direct paths. Never select `asyncio.run()` by slogan; choose based on event-loop reality and repository patterns.
Before coding, write a small comparison table in the decision log: option; correctness against acceptance criteria; data/security risk; compatibility; concurrency/idempotency; complexity/maintenance; reversibility; evidence for/against. Do not create arbitrary numerical scores. Explain why the chosen approach is proportionate to the proven root cause and why each rejected alternative is inferior for this evidence.
If the current implementation already meets the requirement, choose verification-only and avoid a redundant change. If requirements remain ambiguous and a wrong choice would be consequential, stop at a documented blocker rather than invent behavior.

4. IMPLEMENTATION BOUNDARY
Implement only this work item. Prefer the smallest complete, maintainable fix using existing models, APIs, task lifecycle, storage/artifact and frontend patterns. Avoid duplicate frameworks, helpers, routes, state machines, database fields or tests when an existing abstraction meets the requirement.
Preserve all unrelated behavior and frozen components. Do not remove code based on apparent lack of callers without a call-site/dependency audit. Do not change public API semantics without documenting callers, compatibility plan and tests. Any migration must be justified, forward-only and data-preserving.
Scope-specific acceptance criteria:
- Use a synchronous/async boundary appropriate to the actual Celery task; do not blindly use `asyncio.run()` or `get_event_loop()` without inspecting the caller context.
- Parse actual supported retention JSON shapes explicitly and validate data without making schema validation lax.
- Resolve media through the established managed storage abstraction, not guessed filesystem paths.
- Persist HookPlan/ClipHookPlan and rendered variant state consistently; never report success before render, validation and commit succeed.
- Preserve Hook as a distinct overlay feature; no caption/subtitle generation or text burned as captions.

5. REQUIRED TESTING
Add focused regression tests for the root cause and relevant negative, failure, boundary, retry, concurrency and stale-state paths. Assert durable database/filesystem/worker state as applicable, not only mocked return values. Use synthetic media, disposable test records and test provider mode. Never publish to real YouTube or destructive-clean real data.
- Valid retention payload; legacy/list/object payload only if explicitly supported; malformed payload.
- Missing clip, missing media, missing retained artifact, failed voice/render component.
- Success creates valid output media, ClipVariant and ArtifactRecord with correct owner/key/retention.
- Worker task terminal status is consistent with output/DB state.
- Focused tests, nearby task/orchestration suites, browser/backend contract as applicable.
Run the exact focused suite, relevant regressions, static checks and build/browser/integration tests required by the changed layers. Capture actual commands, counts, exit codes, warning/failure output and environment. Do not claim a test ran if only drafted or launched without a completed result.

6. THREE VERIFICATION PASSES — REQUIRED FOR THIS ITEM
PASS 1 — Implementation verification: review diff against every acceptance criterion; run focused tests and the affected workflow; prove expected state and failure behavior.
PASS 2 — Independent challenge: stop thinking like the implementation author. Re-read the requirement and original defect evidence. Try to falsify the fix with adversarial inputs, conflicts, retries, parallel requests, stale state and failure injection. Compare alternative approaches again. Inspect whether the tests could pass while production is still broken. Fix any issue discovered and record changes since Pass 1.
PASS 3 — Differential re-verification: re-read the final diff and working tree from scratch. Compare final code with Passes 1 and 2, identify all changes introduced after each earlier pass, rerun affected focused tests and relevant regressions against the final tree, and verify reports/status files match the final code. Any new code change invalidates the affected previous pass; repeat it.

7. EXPLICIT SELF-CHALLENGE QUESTIONS
- What concrete evidence proves the original problem existed?
- Why does each changed line/function need to exist?
- What alternative was considered and why was it rejected?
- Could a real production record or untrusted caller reach the test/mock path?
- What happens on failure, retry, concurrency, restart and stale response?
- What does this test prove, and what does it not prove?
- Did I preserve all previous working-tree files and frozen behavior?
- What changed between verification passes and why?
- Which claims remain unverified or depend on an environmental assumption?

8. REQUIRED RECORDS AND FINAL RESPONSE
Update only applicable canonical documents: phase tracker, master ledger, implementation status, defect register, relevant API/frontend/pipeline inventories, audit report and `docs/engineering/AI_DECISION_LOG.md`. Preserve old audit records and append corrections instead of rewriting history. Make status consistent everywhere.
Record work-item ID, before/after working-tree status, root cause, option comparison and rationale, files changed and purpose, relevant hashes if practical, each pass and test result, evidence tier (source/unit/mock/API/in-process/live worker/browser/full E2E), risks, limitations and next dependency.
Report statuses honestly: DELIVERED & VERIFIED, PARTIALLY VERIFIED, BLOCKED or REOPENED. Do not say full E2E without the real required components running together.

9. STOP / CONTINUE RULE
Do not start a different implementation item in parallel or expand this scope to unrelated fixes. Complete all three passes, update records and then continue automatically to the next unblocked item in the master execution queue without waiting for routine approval. Stop only for a real blocker, unresolved high-impact product choice, credential/account action, real publication, destructive action against actual data, or an environment change that requires owner authorization. If blocked, document exact evidence and work safely on independent unblocked work only if it does not depend on the blocker.
Never use `git reset`, `git clean`, blanket reverts, destructive DB resets, `docker compose down -v`, or broad file deletion. Do not reintroduce captions/subtitles; preserve transcription for internal scoring/semantic analysis; retain the frozen Shorts duration limit unless the owner explicitly changes it.
```


### Copy-ready prompt — C-03: Live Docker worker refresh and AI enhancement verification

```text
You are the ClipForge engineering agent working in `D:\automation video clips\clipforge`.

WORK ITEM: C-03 — Live Docker worker refresh and AI enhancement verification
STATE: Reconcile current repository state before acting. Do not assume this item is open just because it appears in the roadmap.

1. PROBLEM / OBJECTIVE
Source-level and in-process success did not prove the deployed worker imported the updated source or completed tasks.

2. PREFLIGHT AND EVIDENCE COLLECTION
Read `AGENTS.md`, the applicable freeze/rule files, `docs/engineering/PHASE_TRACKER.md`, `MASTER_EXECUTION_LEDGER.md`, `IMPLEMENTATION_STATUS.md`, `ENGINEERING_DEFECT_REGISTER.md`, `PIPELINE_CATALOG_AND_DEPENDENCY_GRAPH.md`, `FRONTEND_PAGE_FEATURE_INVENTORY.md`, `PROJECT_CONTINUITY.md`, and the newest relevant audit/decision-log entries. Read only files relevant to this scope in depth, but reconcile any status claims before editing.
Inspect actual current source, schema, runtime route/client/task contracts, tests and caller/callee relationships. Reproduce the reported behavior with a safe isolated fixture where feasible. Separate VERIFIED FACTS, INFERENCES and UNKNOWNS. Record exact file paths, line ranges, commands and observed outputs.
Inspect Compose services, image/build mounts, worker command, source mounts, dependency environment, current container identity, health, logs, dirty tree, and persistent volumes. Establish how the running worker gets source changes before restarting anything.
Capture `git status --short`, branch/commit, existing diff/untracked inventory and relevant environment/container identity before editing. Protect all pre-existing changes. Do not assume old hashes, route counts, schema revisions or historic reports still reflect the current environment.

3. COMPARE APPROACHES AND JUSTIFY THE CHOICE
Alternative evaluation required: Compare source-mounted worker refresh, container rebuild/recreate, or image rebuild based on actual compose config. Select the least disruptive method that guarantees new code in the worker. Preserve all data volumes. Do not use a generic restart if a stale image remains.
Before coding, write a small comparison table in the decision log: option; correctness against acceptance criteria; data/security risk; compatibility; concurrency/idempotency; complexity/maintenance; reversibility; evidence for/against. Do not create arbitrary numerical scores. Explain why the chosen approach is proportionate to the proven root cause and why each rejected alternative is inferior for this evidence.
If the current implementation already meets the requirement, choose verification-only and avoid a redundant change. If requirements remain ambiguous and a wrong choice would be consequential, stop at a documented blocker rather than invent behavior.

4. IMPLEMENTATION BOUNDARY
Implement only this work item. Prefer the smallest complete, maintainable fix using existing models, APIs, task lifecycle, storage/artifact and frontend patterns. Avoid duplicate frameworks, helpers, routes, state machines, database fields or tests when an existing abstraction meets the requirement.
Preserve all unrelated behavior and frozen components. Do not remove code based on apparent lack of callers without a call-site/dependency audit. Do not change public API semantics without documenting callers, compatibility plan and tests. Any migration must be justified, forward-only and data-preserving.
Scope-specific acceptance criteria:
- Rebuild/recreate/restart only the needed service(s), if necessary, using the existing deployment convention; preserve Postgres, Redis, upload/output volumes, tokens and all persistent data.
- Use isolated synthetic fixture and authoritative test context.
- For SFX, B-roll and Hook separately, record API request, task ID, current worker identity, task consumption, terminal status, artifact validity, DB records and UI refresh state.
- Confirm no live YouTube publication occurred.

5. REQUIRED TESTING
Add focused regression tests for the root cause and relevant negative, failure, boundary, retry, concurrency and stale-state paths. Assert durable database/filesystem/worker state as applicable, not only mocked return values. Use synthetic media, disposable test records and test provider mode. Never publish to real YouTube or destructive-clean real data.
- One true live-worker task per feature, not task.apply() alone.
- Valid media using ffprobe/media probing and expected stream properties.
- ClipVariant, ArtifactRecord and physical/storage key agree.
- A failure is represented as failure with no false success or orphan artifact.
- Regression tests and actual browser/backend check where feature requires UI proof.
Run the exact focused suite, relevant regressions, static checks and build/browser/integration tests required by the changed layers. Capture actual commands, counts, exit codes, warning/failure output and environment. Do not claim a test ran if only drafted or launched without a completed result.

6. THREE VERIFICATION PASSES — REQUIRED FOR THIS ITEM
PASS 1 — Implementation verification: review diff against every acceptance criterion; run focused tests and the affected workflow; prove expected state and failure behavior.
PASS 2 — Independent challenge: stop thinking like the implementation author. Re-read the requirement and original defect evidence. Try to falsify the fix with adversarial inputs, conflicts, retries, parallel requests, stale state and failure injection. Compare alternative approaches again. Inspect whether the tests could pass while production is still broken. Fix any issue discovered and record changes since Pass 1.
PASS 3 — Differential re-verification: re-read the final diff and working tree from scratch. Compare final code with Passes 1 and 2, identify all changes introduced after each earlier pass, rerun affected focused tests and relevant regressions against the final tree, and verify reports/status files match the final code. Any new code change invalidates the affected previous pass; repeat it.

7. EXPLICIT SELF-CHALLENGE QUESTIONS
- What concrete evidence proves the original problem existed?
- Why does each changed line/function need to exist?
- What alternative was considered and why was it rejected?
- Could a real production record or untrusted caller reach the test/mock path?
- What happens on failure, retry, concurrency, restart and stale response?
- What does this test prove, and what does it not prove?
- Did I preserve all previous working-tree files and frozen behavior?
- What changed between verification passes and why?
- Which claims remain unverified or depend on an environmental assumption?

8. REQUIRED RECORDS AND FINAL RESPONSE
Update only applicable canonical documents: phase tracker, master ledger, implementation status, defect register, relevant API/frontend/pipeline inventories, audit report and `docs/engineering/AI_DECISION_LOG.md`. Preserve old audit records and append corrections instead of rewriting history. Make status consistent everywhere.
Record work-item ID, before/after working-tree status, root cause, option comparison and rationale, files changed and purpose, relevant hashes if practical, each pass and test result, evidence tier (source/unit/mock/API/in-process/live worker/browser/full E2E), risks, limitations and next dependency.
Report statuses honestly: DELIVERED & VERIFIED, PARTIALLY VERIFIED, BLOCKED or REOPENED. Do not say full E2E without the real required components running together.

9. STOP / CONTINUE RULE
Do not start a different implementation item in parallel or expand this scope to unrelated fixes. Complete all three passes, update records and then continue automatically to the next unblocked item in the master execution queue without waiting for routine approval. Stop only for a real blocker, unresolved high-impact product choice, credential/account action, real publication, destructive action against actual data, or an environment change that requires owner authorization. If blocked, document exact evidence and work safely on independent unblocked work only if it does not depend on the blocker.
Never use `git reset`, `git clean`, blanket reverts, destructive DB resets, `docker compose down -v`, or broad file deletion. Do not reintroduce captions/subtitles; preserve transcription for internal scoring/semantic analysis; retain the frozen Shorts duration limit unless the owner explicitly changes it.
```


### Copy-ready prompt — C-04: Canonical Phase 2.2 — CF-DEF-007 single-video decision customization race guard

```text
You are the ClipForge engineering agent working in `D:\automation video clips\clipforge`.

WORK ITEM: C-04 — Canonical Phase 2.2 — CF-DEF-007 single-video decision customization race guard
STATE: Reconcile current repository state before acting. Do not assume this item is open just because it appears in the roadmap.

1. PROBLEM / OBJECTIVE
Concurrent or stale single-video customization requests may overwrite or act on the wrong decision/clip; this item is separate from old roadmap label `ROADMAP-2.2`.

2. PREFLIGHT AND EVIDENCE COLLECTION
Read `AGENTS.md`, the applicable freeze/rule files, `docs/engineering/PHASE_TRACKER.md`, `MASTER_EXECUTION_LEDGER.md`, `IMPLEMENTATION_STATUS.md`, `ENGINEERING_DEFECT_REGISTER.md`, `PIPELINE_CATALOG_AND_DEPENDENCY_GRAPH.md`, `FRONTEND_PAGE_FEATURE_INVENTORY.md`, `PROJECT_CONTINUITY.md`, and the newest relevant audit/decision-log entries. Read only files relevant to this scope in depth, but reconcile any status claims before editing.
Inspect actual current source, schema, runtime route/client/task contracts, tests and caller/callee relationships. Reproduce the reported behavior with a safe isolated fixture where feasible. Separate VERIFIED FACTS, INFERENCES and UNKNOWNS. Record exact file paths, line ranges, commands and observed outputs.
Read the current defect entry for `CF-DEF-007`, trace the exact UI, local state, API schema, DB decision records, job/task references and task dispatch. Inspect prior batch-selection fixes and cancellation/terminal-state guards to reuse existing invariants.
Capture `git status --short`, branch/commit, existing diff/untracked inventory and relevant environment/container identity before editing. Protect all pre-existing changes. Do not assume old hashes, route counts, schema revisions or historic reports still reflect the current environment.

3. COMPARE APPROACHES AND JUSTIFY THE CHOICE
Alternative evaluation required: Compare an existing optimistic-version/claim mechanism, conditional DB update/transaction lock, and schema-backed version field only if necessary. Select based on actual isolation level and model constraints. Avoid broad locks that reduce unrelated throughput.
Before coding, write a small comparison table in the decision log: option; correctness against acceptance criteria; data/security risk; compatibility; concurrency/idempotency; complexity/maintenance; reversibility; evidence for/against. Do not create arbitrary numerical scores. Explain why the chosen approach is proportionate to the proven root cause and why each rejected alternative is inferior for this evidence.
If the current implementation already meets the requirement, choose verification-only and avoid a redundant change. If requirements remain ambiguous and a wrong choice would be consequential, stop at a documented blocker rather than invent behavior.

4. IMPLEMENTATION BOUNDARY
Implement only this work item. Prefer the smallest complete, maintainable fix using existing models, APIs, task lifecycle, storage/artifact and frontend patterns. Avoid duplicate frameworks, helpers, routes, state machines, database fields or tests when an existing abstraction meets the requirement.
Preserve all unrelated behavior and frozen components. Do not remove code based on apparent lack of callers without a call-site/dependency audit. Do not change public API semantics without documenting callers, compatibility plan and tests. Any migration must be justified, forward-only and data-preserving.
Scope-specific acceptance criteria:
- Prove race with a deterministic test before fixing.
- Use narrow server-side validation and an existing optimistic-lock/version/claim pattern if available; propose schema changes only if current model cannot enforce the required invariant.
- Reject stale or conflicting requests with explicit conflict response instead of silently overwriting newer state.
- Preserve unrelated selected items, jobs and decision records; keep retry behavior predictable.
- Do not rework multi-video batch selection unless the same invariant requires it.

5. REQUIRED TESTING
Add focused regression tests for the root cause and relevant negative, failure, boundary, retry, concurrency and stale-state paths. Assert durable database/filesystem/worker state as applicable, not only mocked return values. Use synthetic media, disposable test records and test provider mode. Never publish to real YouTube or destructive-clean real data.
- Two simultaneous customizations of same item; two different items in parallel.
- Stale version, duplicate submission, cancellation/terminal state, invalid ID/ownership.
- Database final state and response statuses are consistent.
- Regression for existing batch multi-channel selection and Dashboard updates.
- Actual API/worker/browser tier called out accurately.
Run the exact focused suite, relevant regressions, static checks and build/browser/integration tests required by the changed layers. Capture actual commands, counts, exit codes, warning/failure output and environment. Do not claim a test ran if only drafted or launched without a completed result.

6. THREE VERIFICATION PASSES — REQUIRED FOR THIS ITEM
PASS 1 — Implementation verification: review diff against every acceptance criterion; run focused tests and the affected workflow; prove expected state and failure behavior.
PASS 2 — Independent challenge: stop thinking like the implementation author. Re-read the requirement and original defect evidence. Try to falsify the fix with adversarial inputs, conflicts, retries, parallel requests, stale state and failure injection. Compare alternative approaches again. Inspect whether the tests could pass while production is still broken. Fix any issue discovered and record changes since Pass 1.
PASS 3 — Differential re-verification: re-read the final diff and working tree from scratch. Compare final code with Passes 1 and 2, identify all changes introduced after each earlier pass, rerun affected focused tests and relevant regressions against the final tree, and verify reports/status files match the final code. Any new code change invalidates the affected previous pass; repeat it.

7. EXPLICIT SELF-CHALLENGE QUESTIONS
- What concrete evidence proves the original problem existed?
- Why does each changed line/function need to exist?
- What alternative was considered and why was it rejected?
- Could a real production record or untrusted caller reach the test/mock path?
- What happens on failure, retry, concurrency, restart and stale response?
- What does this test prove, and what does it not prove?
- Did I preserve all previous working-tree files and frozen behavior?
- What changed between verification passes and why?
- Which claims remain unverified or depend on an environmental assumption?

8. REQUIRED RECORDS AND FINAL RESPONSE
Update only applicable canonical documents: phase tracker, master ledger, implementation status, defect register, relevant API/frontend/pipeline inventories, audit report and `docs/engineering/AI_DECISION_LOG.md`. Preserve old audit records and append corrections instead of rewriting history. Make status consistent everywhere.
Record work-item ID, before/after working-tree status, root cause, option comparison and rationale, files changed and purpose, relevant hashes if practical, each pass and test result, evidence tier (source/unit/mock/API/in-process/live worker/browser/full E2E), risks, limitations and next dependency.
Report statuses honestly: DELIVERED & VERIFIED, PARTIALLY VERIFIED, BLOCKED or REOPENED. Do not say full E2E without the real required components running together.

9. STOP / CONTINUE RULE
Do not start a different implementation item in parallel or expand this scope to unrelated fixes. Complete all three passes, update records and then continue automatically to the next unblocked item in the master execution queue without waiting for routine approval. Stop only for a real blocker, unresolved high-impact product choice, credential/account action, real publication, destructive action against actual data, or an environment change that requires owner authorization. If blocked, document exact evidence and work safely on independent unblocked work only if it does not depend on the blocker.
Never use `git reset`, `git clean`, blanket reverts, destructive DB resets, `docker compose down -v`, or broad file deletion. Do not reintroduce captions/subtitles; preserve transcription for internal scoring/semantic analysis; retain the frozen Shorts duration limit unless the owner explicitly changes it.
```


# PART B — Legacy product roadmap prompts, phases 0.1–7

These prompts originate from the supplied ClipForge roadmap. The AI must map each `ROADMAP-*` task to current canonical status before implementation and must not duplicate already completed canonical work.


## Main phase prompt — ROADMAP Phase 0.1: Reconcile baseline

```text
You are the ClipForge engineering agent. Coordinate Phase 0.1: Reconcile baseline as a sequence of independently testable child work items, not a single broad implementation.

PROBLEM / OBJECTIVE
Establish accurate, evidence-backed repository baseline before trusting historical status. Execute 0.1.1–0.1.4 sequentially, each as its own bounded item.

DISCOVERY AND METHOD
Read the current project rules and phase ledger; establish whether each child is already delivered, unverified, blocked or open. Compare viable approaches for each child before implementation. Prefer the smallest evidence-backed fix that reuses current architecture. Record a qualitative comparison of correctness, data safety, compatibility, concurrency/idempotency, operational burden, reversibility and testability. Explain the chosen approach and why other options were rejected. Never rely on old phase numbers when they conflict with canonical records.

PHASE ACCEPTANCE CRITERIA
- Branch/commit/dirty tree and migration graph/current DB revision reconciled.
- Route and frontend inventories complete.
- Historical test evidence classified by evidence tier.
- Defect register deduplicated and dependency-aware.

EXECUTION SEQUENCE
Execute the child subphases in the order shown in the index. For each child: inspect/reproduce; implement only that child; run Pass 1, Pass 2 and Pass 3 as defined in the companion rules; update `AI_DECISION_LOG.md` and canonical status; then move autonomously to the next unblocked child. Do not bundle unrelated children into one diff.

CROSS-VERIFICATION
Before phase close, independently check every child status against final source, test outputs and runtime evidence. Recheck frozen invariants, changed files and working-tree state. A completed build alone does not prove runtime behavior. A task ID/toast does not prove a worker finished.

BOUNDARIES
Read-only. Do not fix code findings in this coordinator; create separate queue items.
Preserve existing changes and untracked files. No real publishing. No caption/subtitle framework. Never use destructive Git operations or broad DB/storage deletion. High-impact irreversible actions against real user data require explicit owner authorization.

PHASE EXIT
Close this main phase only when all required children are either independently verified or explicitly documented as blocked with owner-relevant rationale. If blocked, do not mislabel the phase complete. Record the next unblocked dependency and continue autonomously when safe.
```


### Copy-ready prompt — ROADMAP-0.1.1: Git state and migration history

```text
You are the ClipForge engineering agent working in `D:\automation video clips\clipforge`.

WORK ITEM: ROADMAP-0.1.1 — Git state and migration history
STATE: Reconcile current repository state before acting. Do not assume this item is open just because it appears in the roadmap.

1. PROBLEM / OBJECTIVE
Record the precise repository and database baseline.

2. PREFLIGHT AND EVIDENCE COLLECTION
Read `AGENTS.md`, the applicable freeze/rule files, `docs/engineering/PHASE_TRACKER.md`, `MASTER_EXECUTION_LEDGER.md`, `IMPLEMENTATION_STATUS.md`, `ENGINEERING_DEFECT_REGISTER.md`, `PIPELINE_CATALOG_AND_DEPENDENCY_GRAPH.md`, `FRONTEND_PAGE_FEATURE_INVENTORY.md`, `PROJECT_CONTINUITY.md`, and the newest relevant audit/decision-log entries. Read only files relevant to this scope in depth, but reconcile any status claims before editing.
Inspect actual current source, schema, runtime route/client/task contracts, tests and caller/callee relationships. Reproduce the reported behavior with a safe isolated fixture where feasible. Separate VERIFIED FACTS, INFERENCES and UNKNOWNS. Record exact file paths, line ranges, commands and observed outputs.
Inspect `git status --short`, branch, current commit and diff summaries without resetting anything; inspect Alembic config, migration files, graph, runtime `alembic current`, database identity and revision. Distinguish repository revision, container filesystem and live database state.
Capture `git status --short`, branch/commit, existing diff/untracked inventory and relevant environment/container identity before editing. Protect all pre-existing changes. Do not assume old hashes, route counts, schema revisions or historic reports still reflect the current environment.

3. COMPARE APPROACHES AND JUSTIFY THE CHOICE
Approach selection method: Compare at least two plausible approaches where meaningful: (A) smallest local repair, (B) reuse an established repository abstraction/pattern, and (C) architectural change only if the first two cannot meet verified requirements. Use evidence, not preference. Evaluate correctness, data safety, architectural consistency, backwards compatibility, idempotency/concurrency, performance, testability, reversibility, scope and maintenance cost. Record the chosen approach and specific reasons each alternative was rejected. If the problem is already solved in current source, choose the no-op verification path.
Before coding, write a small comparison table in the decision log: option; correctness against acceptance criteria; data/security risk; compatibility; concurrency/idempotency; complexity/maintenance; reversibility; evidence for/against. Do not create arbitrary numerical scores. Explain why the chosen approach is proportionate to the proven root cause and why each rejected alternative is inferior for this evidence.
If the current implementation already meets the requirement, choose verification-only and avoid a redundant change. If requirements remain ambiguous and a wrong choice would be consequential, stop at a documented blocker rather than invent behavior.

4. IMPLEMENTATION BOUNDARY
Implement only this work item. Prefer the smallest complete, maintainable fix using existing models, APIs, task lifecycle, storage/artifact and frontend patterns. Avoid duplicate frameworks, helpers, routes, state machines, database fields or tests when an existing abstraction meets the requirement.
Preserve all unrelated behavior and frozen components. Do not remove code based on apparent lack of callers without a call-site/dependency audit. Do not change public API semantics without documenting callers, compatibility plan and tests. Any migration must be justified, forward-only and data-preserving.
Scope-specific acceptance criteria:
- Resolve migration branch heads, missing revisions, duplicated revisions and mismatch between model and migration state.
- Use read-only DB queries. Do not upgrade/downgrade or modify schema.
- Record all pre-existing changes and untracked files as protected state.

5. REQUIRED TESTING
Add focused regression tests for the root cause and relevant negative, failure, boundary, retry, concurrency and stale-state paths. Assert durable database/filesystem/worker state as applicable, not only mocked return values. Use synthetic media, disposable test records and test provider mode. Never publish to real YouTube or destructive-clean real data.
- Migration graph is connected or known split points documented.
- Current DB identity/revision captured from actual environment.
- Before/after Git status shows no accidental mutation.
- Second pass independently compares migration filenames, graph and DB current.
Run the exact focused suite, relevant regressions, static checks and build/browser/integration tests required by the changed layers. Capture actual commands, counts, exit codes, warning/failure output and environment. Do not claim a test ran if only drafted or launched without a completed result.

6. THREE VERIFICATION PASSES — REQUIRED FOR THIS ITEM
PASS 1 — Implementation verification: review diff against every acceptance criterion; run focused tests and the affected workflow; prove expected state and failure behavior.
PASS 2 — Independent challenge: stop thinking like the implementation author. Re-read the requirement and original defect evidence. Try to falsify the fix with adversarial inputs, conflicts, retries, parallel requests, stale state and failure injection. Compare alternative approaches again. Inspect whether the tests could pass while production is still broken. Fix any issue discovered and record changes since Pass 1.
PASS 3 — Differential re-verification: re-read the final diff and working tree from scratch. Compare final code with Passes 1 and 2, identify all changes introduced after each earlier pass, rerun affected focused tests and relevant regressions against the final tree, and verify reports/status files match the final code. Any new code change invalidates the affected previous pass; repeat it.

7. EXPLICIT SELF-CHALLENGE QUESTIONS
- What concrete evidence proves the original problem existed?
- Why does each changed line/function need to exist?
- What alternative was considered and why was it rejected?
- Could a real production record or untrusted caller reach the test/mock path?
- What happens on failure, retry, concurrency, restart and stale response?
- What does this test prove, and what does it not prove?
- Did I preserve all previous working-tree files and frozen behavior?
- What changed between verification passes and why?
- Which claims remain unverified or depend on an environmental assumption?

8. REQUIRED RECORDS AND FINAL RESPONSE
Update only applicable canonical documents: phase tracker, master ledger, implementation status, defect register, relevant API/frontend/pipeline inventories, audit report and `docs/engineering/AI_DECISION_LOG.md`. Preserve old audit records and append corrections instead of rewriting history. Make status consistent everywhere.
Record work-item ID, before/after working-tree status, root cause, option comparison and rationale, files changed and purpose, relevant hashes if practical, each pass and test result, evidence tier (source/unit/mock/API/in-process/live worker/browser/full E2E), risks, limitations and next dependency.
Report statuses honestly: DELIVERED & VERIFIED, PARTIALLY VERIFIED, BLOCKED or REOPENED. Do not say full E2E without the real required components running together.

9. STOP / CONTINUE RULE
Do not start a different implementation item in parallel or expand this scope to unrelated fixes. Complete all three passes, update records and then continue automatically to the next unblocked item in the master execution queue without waiting for routine approval. Stop only for a real blocker, unresolved high-impact product choice, credential/account action, real publication, destructive action against actual data, or an environment change that requires owner authorization. If blocked, document exact evidence and work safely on independent unblocked work only if it does not depend on the blocker.
Never use `git reset`, `git clean`, blanket reverts, destructive DB resets, `docker compose down -v`, or broad file deletion. Do not reintroduce captions/subtitles; preserve transcription for internal scoring/semantic analysis; retain the frozen Shorts duration limit unless the owner explicitly changes it.
```


### Copy-ready prompt — ROADMAP-0.1.2: API and frontend inventories

```text
You are the ClipForge engineering agent working in `D:\automation video clips\clipforge`.

WORK ITEM: ROADMAP-0.1.2 — API and frontend inventories
STATE: Reconcile current repository state before acting. Do not assume this item is open just because it appears in the roadmap.

1. PROBLEM / OBJECTIVE
Create accurate inventories of server routes and user-facing workflows.

2. PREFLIGHT AND EVIDENCE COLLECTION
Read `AGENTS.md`, the applicable freeze/rule files, `docs/engineering/PHASE_TRACKER.md`, `MASTER_EXECUTION_LEDGER.md`, `IMPLEMENTATION_STATUS.md`, `ENGINEERING_DEFECT_REGISTER.md`, `PIPELINE_CATALOG_AND_DEPENDENCY_GRAPH.md`, `FRONTEND_PAGE_FEATURE_INVENTORY.md`, `PROJECT_CONTINUITY.md`, and the newest relevant audit/decision-log entries. Read only files relevant to this scope in depth, but reconcile any status claims before editing.
Inspect actual current source, schema, runtime route/client/task contracts, tests and caller/callee relationships. Reproduce the reported behavior with a safe isolated fixture where feasible. Separate VERIFIED FACTS, INFERENCES and UNKNOWNS. Record exact file paths, line ranges, commands and observed outputs.
Reflect on the actual `backend.main:app.routes`; distinguish HTTP route objects, methods, WebSockets, OpenAPI/docs routes and static mounts. Inspect Next.js app routes, visible controls, API client functions and actual handlers.
Capture `git status --short`, branch/commit, existing diff/untracked inventory and relevant environment/container identity before editing. Protect all pre-existing changes. Do not assume old hashes, route counts, schema revisions or historic reports still reflect the current environment.

3. COMPARE APPROACHES AND JUSTIFY THE CHOICE
Approach selection method: Compare at least two plausible approaches where meaningful: (A) smallest local repair, (B) reuse an established repository abstraction/pattern, and (C) architectural change only if the first two cannot meet verified requirements. Use evidence, not preference. Evaluate correctness, data safety, architectural consistency, backwards compatibility, idempotency/concurrency, performance, testability, reversibility, scope and maintenance cost. Record the chosen approach and specific reasons each alternative was rejected. If the problem is already solved in current source, choose the no-op verification path.
Before coding, write a small comparison table in the decision log: option; correctness against acceptance criteria; data/security risk; compatibility; concurrency/idempotency; complexity/maintenance; reversibility; evidence for/against. Do not create arbitrary numerical scores. Explain why the chosen approach is proportionate to the proven root cause and why each rejected alternative is inferior for this evidence.
If the current implementation already meets the requirement, choose verification-only and avoid a redundant change. If requirements remain ambiguous and a wrong choice would be consequential, stop at a documented blocker rather than invent behavior.

4. IMPLEMENTATION BOUNDARY
Implement only this work item. Prefer the smallest complete, maintainable fix using existing models, APIs, task lifecycle, storage/artifact and frontend patterns. Avoid duplicate frameworks, helpers, routes, state machines, database fields or tests when an existing abstraction meets the requirement.
Preserve all unrelated behavior and frozen components. Do not remove code based on apparent lack of callers without a call-site/dependency audit. Do not change public API semantics without documenting callers, compatibility plan and tests. Any migration must be justified, forward-only and data-preserving.
Scope-specific acceptance criteria:
- Inventory routes and their actual schemas/status semantics.
- Inventory pages/control ID/action/handler/API target/state effect/error handling.
- Identify broken links, relative URL usage, dead buttons, duplicate endpoints and routes with no known caller.
- Separate confirmed defects from uncertain unused-code observations.

5. REQUIRED TESTING
Add focused regression tests for the root cause and relevant negative, failure, boundary, retry, concurrency and stale-state paths. Assert durable database/filesystem/worker state as applicable, not only mocked return values. Use synthetic media, disposable test records and test provider mode. Never publish to real YouTube or destructive-clean real data.
- Route counts reconcile arithmetically and to runtime reflection.
- Each listed control links to source and intended endpoint/local operation.
- No count is inferred from old docs.
- Second pass checks static/dynamic routes and path precedence.
Run the exact focused suite, relevant regressions, static checks and build/browser/integration tests required by the changed layers. Capture actual commands, counts, exit codes, warning/failure output and environment. Do not claim a test ran if only drafted or launched without a completed result.

6. THREE VERIFICATION PASSES — REQUIRED FOR THIS ITEM
PASS 1 — Implementation verification: review diff against every acceptance criterion; run focused tests and the affected workflow; prove expected state and failure behavior.
PASS 2 — Independent challenge: stop thinking like the implementation author. Re-read the requirement and original defect evidence. Try to falsify the fix with adversarial inputs, conflicts, retries, parallel requests, stale state and failure injection. Compare alternative approaches again. Inspect whether the tests could pass while production is still broken. Fix any issue discovered and record changes since Pass 1.
PASS 3 — Differential re-verification: re-read the final diff and working tree from scratch. Compare final code with Passes 1 and 2, identify all changes introduced after each earlier pass, rerun affected focused tests and relevant regressions against the final tree, and verify reports/status files match the final code. Any new code change invalidates the affected previous pass; repeat it.

7. EXPLICIT SELF-CHALLENGE QUESTIONS
- What concrete evidence proves the original problem existed?
- Why does each changed line/function need to exist?
- What alternative was considered and why was it rejected?
- Could a real production record or untrusted caller reach the test/mock path?
- What happens on failure, retry, concurrency, restart and stale response?
- What does this test prove, and what does it not prove?
- Did I preserve all previous working-tree files and frozen behavior?
- What changed between verification passes and why?
- Which claims remain unverified or depend on an environmental assumption?

8. REQUIRED RECORDS AND FINAL RESPONSE
Update only applicable canonical documents: phase tracker, master ledger, implementation status, defect register, relevant API/frontend/pipeline inventories, audit report and `docs/engineering/AI_DECISION_LOG.md`. Preserve old audit records and append corrections instead of rewriting history. Make status consistent everywhere.
Record work-item ID, before/after working-tree status, root cause, option comparison and rationale, files changed and purpose, relevant hashes if practical, each pass and test result, evidence tier (source/unit/mock/API/in-process/live worker/browser/full E2E), risks, limitations and next dependency.
Report statuses honestly: DELIVERED & VERIFIED, PARTIALLY VERIFIED, BLOCKED or REOPENED. Do not say full E2E without the real required components running together.

9. STOP / CONTINUE RULE
Do not start a different implementation item in parallel or expand this scope to unrelated fixes. Complete all three passes, update records and then continue automatically to the next unblocked item in the master execution queue without waiting for routine approval. Stop only for a real blocker, unresolved high-impact product choice, credential/account action, real publication, destructive action against actual data, or an environment change that requires owner authorization. If blocked, document exact evidence and work safely on independent unblocked work only if it does not depend on the blocker.
Never use `git reset`, `git clean`, blanket reverts, destructive DB resets, `docker compose down -v`, or broad file deletion. Do not reintroduce captions/subtitles; preserve transcription for internal scoring/semantic analysis; retain the frozen Shorts duration limit unless the owner explicitly changes it.
```


### Copy-ready prompt — ROADMAP-0.1.3: Historical test evidence reconciliation

```text
You are the ClipForge engineering agent working in `D:\automation video clips\clipforge`.

WORK ITEM: ROADMAP-0.1.3 — Historical test evidence reconciliation
STATE: Reconcile current repository state before acting. Do not assume this item is open just because it appears in the roadmap.

1. PROBLEM / OBJECTIVE
Make previous test claims auditable and avoid trusting unsupported green labels.

2. PREFLIGHT AND EVIDENCE COLLECTION
Read `AGENTS.md`, the applicable freeze/rule files, `docs/engineering/PHASE_TRACKER.md`, `MASTER_EXECUTION_LEDGER.md`, `IMPLEMENTATION_STATUS.md`, `ENGINEERING_DEFECT_REGISTER.md`, `PIPELINE_CATALOG_AND_DEPENDENCY_GRAPH.md`, `FRONTEND_PAGE_FEATURE_INVENTORY.md`, `PROJECT_CONTINUITY.md`, and the newest relevant audit/decision-log entries. Read only files relevant to this scope in depth, but reconcile any status claims before editing.
Inspect actual current source, schema, runtime route/client/task contracts, tests and caller/callee relationships. Reproduce the reported behavior with a safe isolated fixture where feasible. Separate VERIFIED FACTS, INFERENCES and UNKNOWNS. Record exact file paths, line ranges, commands and observed outputs.
Inspect reports, commands, test sources, recorded output, timestamps, fixture identity and environment. Match each claimed pass count to exact tests and determine whether mocking, in-process tasks, real workers or browser backend requests were involved.
Capture `git status --short`, branch/commit, existing diff/untracked inventory and relevant environment/container identity before editing. Protect all pre-existing changes. Do not assume old hashes, route counts, schema revisions or historic reports still reflect the current environment.

3. COMPARE APPROACHES AND JUSTIFY THE CHOICE
Approach selection method: Compare at least two plausible approaches where meaningful: (A) smallest local repair, (B) reuse an established repository abstraction/pattern, and (C) architectural change only if the first two cannot meet verified requirements. Use evidence, not preference. Evaluate correctness, data safety, architectural consistency, backwards compatibility, idempotency/concurrency, performance, testability, reversibility, scope and maintenance cost. Record the chosen approach and specific reasons each alternative was rejected. If the problem is already solved in current source, choose the no-op verification path.
Before coding, write a small comparison table in the decision log: option; correctness against acceptance criteria; data/security risk; compatibility; concurrency/idempotency; complexity/maintenance; reversibility; evidence for/against. Do not create arbitrary numerical scores. Explain why the chosen approach is proportionate to the proven root cause and why each rejected alternative is inferior for this evidence.
If the current implementation already meets the requirement, choose verification-only and avoid a redundant change. If requirements remain ambiguous and a wrong choice would be consequential, stop at a documented blocker rather than invent behavior.

4. IMPLEMENTATION BOUNDARY
Implement only this work item. Prefer the smallest complete, maintainable fix using existing models, APIs, task lifecycle, storage/artifact and frontend patterns. Avoid duplicate frameworks, helpers, routes, state machines, database fields or tests when an existing abstraction meets the requirement.
Preserve all unrelated behavior and frozen components. Do not remove code based on apparent lack of callers without a call-site/dependency audit. Do not change public API semantics without documenting callers, compatibility plan and tests. Any migration must be justified, forward-only and data-preserving.
Scope-specific acceptance criteria:
- Tag source inspection, unit/mocked, API integration, in-process task, live-worker, browser and full E2E tiers separately.
- Mark reports with missing logs or mismatched totals as unverified rather than filling gaps.
- Preserve historical claims as history; append correction notes rather than silently rewriting the past.

5. REQUIRED TESTING
Add focused regression tests for the root cause and relevant negative, failure, boundary, retry, concurrency and stale-state paths. Assert durable database/filesystem/worker state as applicable, not only mocked return values. Use synthetic media, disposable test records and test provider mode. Never publish to real YouTube or destructive-clean real data.
- Representative acceptance claims have direct command/output evidence.
- Test count not double-counted or confused with parameterized cases.
- Every material limitation documented.
- Independent pass attempts to falsify the headline claims.
Run the exact focused suite, relevant regressions, static checks and build/browser/integration tests required by the changed layers. Capture actual commands, counts, exit codes, warning/failure output and environment. Do not claim a test ran if only drafted or launched without a completed result.

6. THREE VERIFICATION PASSES — REQUIRED FOR THIS ITEM
PASS 1 — Implementation verification: review diff against every acceptance criterion; run focused tests and the affected workflow; prove expected state and failure behavior.
PASS 2 — Independent challenge: stop thinking like the implementation author. Re-read the requirement and original defect evidence. Try to falsify the fix with adversarial inputs, conflicts, retries, parallel requests, stale state and failure injection. Compare alternative approaches again. Inspect whether the tests could pass while production is still broken. Fix any issue discovered and record changes since Pass 1.
PASS 3 — Differential re-verification: re-read the final diff and working tree from scratch. Compare final code with Passes 1 and 2, identify all changes introduced after each earlier pass, rerun affected focused tests and relevant regressions against the final tree, and verify reports/status files match the final code. Any new code change invalidates the affected previous pass; repeat it.

7. EXPLICIT SELF-CHALLENGE QUESTIONS
- What concrete evidence proves the original problem existed?
- Why does each changed line/function need to exist?
- What alternative was considered and why was it rejected?
- Could a real production record or untrusted caller reach the test/mock path?
- What happens on failure, retry, concurrency, restart and stale response?
- What does this test prove, and what does it not prove?
- Did I preserve all previous working-tree files and frozen behavior?
- What changed between verification passes and why?
- Which claims remain unverified or depend on an environmental assumption?

8. REQUIRED RECORDS AND FINAL RESPONSE
Update only applicable canonical documents: phase tracker, master ledger, implementation status, defect register, relevant API/frontend/pipeline inventories, audit report and `docs/engineering/AI_DECISION_LOG.md`. Preserve old audit records and append corrections instead of rewriting history. Make status consistent everywhere.
Record work-item ID, before/after working-tree status, root cause, option comparison and rationale, files changed and purpose, relevant hashes if practical, each pass and test result, evidence tier (source/unit/mock/API/in-process/live worker/browser/full E2E), risks, limitations and next dependency.
Report statuses honestly: DELIVERED & VERIFIED, PARTIALLY VERIFIED, BLOCKED or REOPENED. Do not say full E2E without the real required components running together.

9. STOP / CONTINUE RULE
Do not start a different implementation item in parallel or expand this scope to unrelated fixes. Complete all three passes, update records and then continue automatically to the next unblocked item in the master execution queue without waiting for routine approval. Stop only for a real blocker, unresolved high-impact product choice, credential/account action, real publication, destructive action against actual data, or an environment change that requires owner authorization. If blocked, document exact evidence and work safely on independent unblocked work only if it does not depend on the blocker.
Never use `git reset`, `git clean`, blanket reverts, destructive DB resets, `docker compose down -v`, or broad file deletion. Do not reintroduce captions/subtitles; preserve transcription for internal scoring/semantic analysis; retain the frozen Shorts duration limit unless the owner explicitly changes it.
```


### Copy-ready prompt — ROADMAP-0.1.4: Active defect register

```text
You are the ClipForge engineering agent working in `D:\automation video clips\clipforge`.

WORK ITEM: ROADMAP-0.1.4 — Active defect register
STATE: Reconcile current repository state before acting. Do not assume this item is open just because it appears in the roadmap.

1. PROBLEM / OBJECTIVE
Establish a durable, dependency-aware active defect list.

2. PREFLIGHT AND EVIDENCE COLLECTION
Read `AGENTS.md`, the applicable freeze/rule files, `docs/engineering/PHASE_TRACKER.md`, `MASTER_EXECUTION_LEDGER.md`, `IMPLEMENTATION_STATUS.md`, `ENGINEERING_DEFECT_REGISTER.md`, `PIPELINE_CATALOG_AND_DEPENDENCY_GRAPH.md`, `FRONTEND_PAGE_FEATURE_INVENTORY.md`, `PROJECT_CONTINUITY.md`, and the newest relevant audit/decision-log entries. Read only files relevant to this scope in depth, but reconcile any status claims before editing.
Inspect actual current source, schema, runtime route/client/task contracts, tests and caller/callee relationships. Reproduce the reported behavior with a safe isolated fixture where feasible. Separate VERIFIED FACTS, INFERENCES and UNKNOWNS. Record exact file paths, line ranges, commands and observed outputs.
Read the defect register and compare it to current code, issues, audit reports and latest phase state. Check each candidate for existing ID and status before creating a new record.
Capture `git status --short`, branch/commit, existing diff/untracked inventory and relevant environment/container identity before editing. Protect all pre-existing changes. Do not assume old hashes, route counts, schema revisions or historic reports still reflect the current environment.

3. COMPARE APPROACHES AND JUSTIFY THE CHOICE
Approach selection method: Compare at least two plausible approaches where meaningful: (A) smallest local repair, (B) reuse an established repository abstraction/pattern, and (C) architectural change only if the first two cannot meet verified requirements. Use evidence, not preference. Evaluate correctness, data safety, architectural consistency, backwards compatibility, idempotency/concurrency, performance, testability, reversibility, scope and maintenance cost. Record the chosen approach and specific reasons each alternative was rejected. If the problem is already solved in current source, choose the no-op verification path.
Before coding, write a small comparison table in the decision log: option; correctness against acceptance criteria; data/security risk; compatibility; concurrency/idempotency; complexity/maintenance; reversibility; evidence for/against. Do not create arbitrary numerical scores. Explain why the chosen approach is proportionate to the proven root cause and why each rejected alternative is inferior for this evidence.
If the current implementation already meets the requirement, choose verification-only and avoid a redundant change. If requirements remain ambiguous and a wrong choice would be consequential, stop at a documented blocker rather than invent behavior.

4. IMPLEMENTATION BOUNDARY
Implement only this work item. Prefer the smallest complete, maintainable fix using existing models, APIs, task lifecycle, storage/artifact and frontend patterns. Avoid duplicate frameworks, helpers, routes, state machines, database fields or tests when an existing abstraction meets the requirement.
Preserve all unrelated behavior and frozen components. Do not remove code based on apparent lack of callers without a call-site/dependency audit. Do not change public API semantics without documenting callers, compatibility plan and tests. Any migration must be justified, forward-only and data-preserving.
Scope-specific acceptance criteria:
- Each defect records evidence, root cause confidence, impact, reproduction, owner area, dependencies, proposed scope, test plan and status.
- Do not close on code changes alone.
- Separate duplicate symptom reports from distinct root causes.
- Map proposed work to a unique semantic ID when legacy phase numbering conflicts.

5. REQUIRED TESTING
Add focused regression tests for the root cause and relevant negative, failure, boundary, retry, concurrency and stale-state paths. Assert durable database/filesystem/worker state as applicable, not only mocked return values. Use synthetic media, disposable test records and test provider mode. Never publish to real YouTube or destructive-clean real data.
- No resolved ID reused.
- No unsupported “verified” status.
- Dependencies/next eligible task are clear.
- Ledger and tracker agree after reconciliation.
Run the exact focused suite, relevant regressions, static checks and build/browser/integration tests required by the changed layers. Capture actual commands, counts, exit codes, warning/failure output and environment. Do not claim a test ran if only drafted or launched without a completed result.

6. THREE VERIFICATION PASSES — REQUIRED FOR THIS ITEM
PASS 1 — Implementation verification: review diff against every acceptance criterion; run focused tests and the affected workflow; prove expected state and failure behavior.
PASS 2 — Independent challenge: stop thinking like the implementation author. Re-read the requirement and original defect evidence. Try to falsify the fix with adversarial inputs, conflicts, retries, parallel requests, stale state and failure injection. Compare alternative approaches again. Inspect whether the tests could pass while production is still broken. Fix any issue discovered and record changes since Pass 1.
PASS 3 — Differential re-verification: re-read the final diff and working tree from scratch. Compare final code with Passes 1 and 2, identify all changes introduced after each earlier pass, rerun affected focused tests and relevant regressions against the final tree, and verify reports/status files match the final code. Any new code change invalidates the affected previous pass; repeat it.

7. EXPLICIT SELF-CHALLENGE QUESTIONS
- What concrete evidence proves the original problem existed?
- Why does each changed line/function need to exist?
- What alternative was considered and why was it rejected?
- Could a real production record or untrusted caller reach the test/mock path?
- What happens on failure, retry, concurrency, restart and stale response?
- What does this test prove, and what does it not prove?
- Did I preserve all previous working-tree files and frozen behavior?
- What changed between verification passes and why?
- Which claims remain unverified or depend on an environmental assumption?

8. REQUIRED RECORDS AND FINAL RESPONSE
Update only applicable canonical documents: phase tracker, master ledger, implementation status, defect register, relevant API/frontend/pipeline inventories, audit report and `docs/engineering/AI_DECISION_LOG.md`. Preserve old audit records and append corrections instead of rewriting history. Make status consistent everywhere.
Record work-item ID, before/after working-tree status, root cause, option comparison and rationale, files changed and purpose, relevant hashes if practical, each pass and test result, evidence tier (source/unit/mock/API/in-process/live worker/browser/full E2E), risks, limitations and next dependency.
Report statuses honestly: DELIVERED & VERIFIED, PARTIALLY VERIFIED, BLOCKED or REOPENED. Do not say full E2E without the real required components running together.

9. STOP / CONTINUE RULE
Do not start a different implementation item in parallel or expand this scope to unrelated fixes. Complete all three passes, update records and then continue automatically to the next unblocked item in the master execution queue without waiting for routine approval. Stop only for a real blocker, unresolved high-impact product choice, credential/account action, real publication, destructive action against actual data, or an environment change that requires owner authorization. If blocked, document exact evidence and work safely on independent unblocked work only if it does not depend on the blocker.
Never use `git reset`, `git clean`, blanket reverts, destructive DB resets, `docker compose down -v`, or broad file deletion. Do not reintroduce captions/subtitles; preserve transcription for internal scoring/semantic analysis; retain the frozen Shorts duration limit unless the owner explicitly changes it.
```


## Main phase prompt — ROADMAP Phase 1: Automation and channel integrity

```text
You are the ClipForge engineering agent. Coordinate Phase 1: Automation and channel integrity as a sequence of independently testable child work items, not a single broad implementation.

PROBLEM / OBJECTIVE
Protect batch processing, Dashboard job lifecycle, channel/destination separation, OAuth, analytics classification and publishing settings. Execute ROADMAP-1.1–1.6 one at a time.

DISCOVERY AND METHOD
Read the current project rules and phase ledger; establish whether each child is already delivered, unverified, blocked or open. Compare viable approaches for each child before implementation. Prefer the smallest evidence-backed fix that reuses current architecture. Record a qualitative comparison of correctness, data safety, compatibility, concurrency/idempotency, operational burden, reversibility and testability. Explain the chosen approach and why other options were rejected. Never rely on old phase numbers when they conflict with canonical records.

PHASE ACCEPTANCE CRITERIA
- Each workflow independently confirmed against current source, DB and runtime.
- Previously repaired 1.1/1.2 audited before changes.
- Channel/source/destination and account data remain isolated.
- No unsupported metrics or settings claims.

EXECUTION SEQUENCE
Execute the child subphases in the order shown in the index. For each child: inspect/reproduce; implement only that child; run Pass 1, Pass 2 and Pass 3 as defined in the companion rules; update `AI_DECISION_LOG.md` and canonical status; then move autonomously to the next unblocked child. Do not bundle unrelated children into one diff.

CROSS-VERIFICATION
Before phase close, independently check every child status against final source, test outputs and runtime evidence. Recheck frozen invariants, changed files and working-tree state. A completed build alone does not prove runtime behavior. A task ID/toast does not prove a worker finished.

BOUNDARIES
Do not patch all six features together.
Preserve existing changes and untracked files. No real publishing. No caption/subtitle framework. Never use destructive Git operations or broad DB/storage deletion. High-impact irreversible actions against real user data require explicit owner authorization.

PHASE EXIT
Close this main phase only when all required children are either independently verified or explicitly documented as blocked with owner-relevant rationale. If blocked, do not mislabel the phase complete. Record the next unblocked dependency and continue autonomously when safe.
```


### Copy-ready prompt — ROADMAP-1.1: Multi-video batch processing

```text
You are the ClipForge engineering agent working in `D:\automation video clips\clipforge`.

WORK ITEM: ROADMAP-1.1 — Multi-video batch processing
STATE: Reconcile current repository state before acting. Do not assume this item is open just because it appears in the roadmap.

1. PROBLEM / OBJECTIVE
Ensure selected clips/videos are dispatched exactly once to the right source/destination group and UI accurately preserves failed selections.

2. PREFLIGHT AND EVIDENCE COLLECTION
Read `AGENTS.md`, the applicable freeze/rule files, `docs/engineering/PHASE_TRACKER.md`, `MASTER_EXECUTION_LEDGER.md`, `IMPLEMENTATION_STATUS.md`, `ENGINEERING_DEFECT_REGISTER.md`, `PIPELINE_CATALOG_AND_DEPENDENCY_GRAPH.md`, `FRONTEND_PAGE_FEATURE_INVENTORY.md`, `PROJECT_CONTINUITY.md`, and the newest relevant audit/decision-log entries. Read only files relevant to this scope in depth, but reconcile any status claims before editing.
Inspect actual current source, schema, runtime route/client/task contracts, tests and caller/callee relationships. Reproduce the reported behavior with a safe isolated fixture where feasible. Separate VERIFIED FACTS, INFERENCES and UNKNOWNS. Record exact file paths, line ranges, commands and observed outputs.
Audit the current global and channel-scoped actions, selection state, local persistence, request IDs, backend validation, batching, task dispatch and result reconciliation. Recent work reportedly fixed cross-channel selection; reproduce it first.
Capture `git status --short`, branch/commit, existing diff/untracked inventory and relevant environment/container identity before editing. Protect all pre-existing changes. Do not assume old hashes, route counts, schema revisions or historic reports still reflect the current environment.

3. COMPARE APPROACHES AND JUSTIFY THE CHOICE
Approach selection method: Compare at least two plausible approaches where meaningful: (A) smallest local repair, (B) reuse an established repository abstraction/pattern, and (C) architectural change only if the first two cannot meet verified requirements. Use evidence, not preference. Evaluate correctness, data safety, architectural consistency, backwards compatibility, idempotency/concurrency, performance, testability, reversibility, scope and maintenance cost. Record the chosen approach and specific reasons each alternative was rejected. If the problem is already solved in current source, choose the no-op verification path.
Before coding, write a small comparison table in the decision log: option; correctness against acceptance criteria; data/security risk; compatibility; concurrency/idempotency; complexity/maintenance; reversibility; evidence for/against. Do not create arbitrary numerical scores. Explain why the chosen approach is proportionate to the proven root cause and why each rejected alternative is inferior for this evidence.
If the current implementation already meets the requirement, choose verification-only and avoid a redundant change. If requirements remain ambiguous and a wrong choice would be consequential, stop at a documented blocker rather than invent behavior.

4. IMPLEMENTATION BOUNDARY
Implement only this work item. Prefer the smallest complete, maintainable fix using existing models, APIs, task lifecycle, storage/artifact and frontend patterns. Avoid duplicate frameworks, helpers, routes, state machines, database fields or tests when an existing abstraction meets the requirement.
Preserve all unrelated behavior and frozen components. Do not remove code based on apparent lack of callers without a call-site/dependency audit. Do not change public API semantics without documenting callers, compatibility plan and tests. Any migration must be justified, forward-only and data-preserving.
Scope-specific acceptance criteria:
- Group by each selected item’s actual source/channel and keep destination identity explicit.
- Clear selection only for items confirmed queued/already-processing per contract.
- Preserve failed, rejected and unresolved items for retry.
- Prevent double-click/double-submit and stale selections leaking across channel changes.

5. REQUIRED TESTING
Add focused regression tests for the root cause and relevant negative, failure, boundary, retry, concurrency and stale-state paths. Assert durable database/filesystem/worker state as applicable, not only mocked return values. Use synthetic media, disposable test records and test provider mode. Never publish to real YouTube or destructive-clean real data.
- Multi-channel selection; channel-scoped action; partial transport failure; per-item rejection; duplicate click; stale item; refresh/navigation.
- Assert exact request groups and payloads, resulting Job rows and visible selected state.
- Browser tests plus backend contract tests.
Run the exact focused suite, relevant regressions, static checks and build/browser/integration tests required by the changed layers. Capture actual commands, counts, exit codes, warning/failure output and environment. Do not claim a test ran if only drafted or launched without a completed result.

6. THREE VERIFICATION PASSES — REQUIRED FOR THIS ITEM
PASS 1 — Implementation verification: review diff against every acceptance criterion; run focused tests and the affected workflow; prove expected state and failure behavior.
PASS 2 — Independent challenge: stop thinking like the implementation author. Re-read the requirement and original defect evidence. Try to falsify the fix with adversarial inputs, conflicts, retries, parallel requests, stale state and failure injection. Compare alternative approaches again. Inspect whether the tests could pass while production is still broken. Fix any issue discovered and record changes since Pass 1.
PASS 3 — Differential re-verification: re-read the final diff and working tree from scratch. Compare final code with Passes 1 and 2, identify all changes introduced after each earlier pass, rerun affected focused tests and relevant regressions against the final tree, and verify reports/status files match the final code. Any new code change invalidates the affected previous pass; repeat it.

7. EXPLICIT SELF-CHALLENGE QUESTIONS
- What concrete evidence proves the original problem existed?
- Why does each changed line/function need to exist?
- What alternative was considered and why was it rejected?
- Could a real production record or untrusted caller reach the test/mock path?
- What happens on failure, retry, concurrency, restart and stale response?
- What does this test prove, and what does it not prove?
- Did I preserve all previous working-tree files and frozen behavior?
- What changed between verification passes and why?
- Which claims remain unverified or depend on an environmental assumption?

8. REQUIRED RECORDS AND FINAL RESPONSE
Update only applicable canonical documents: phase tracker, master ledger, implementation status, defect register, relevant API/frontend/pipeline inventories, audit report and `docs/engineering/AI_DECISION_LOG.md`. Preserve old audit records and append corrections instead of rewriting history. Make status consistent everywhere.
Record work-item ID, before/after working-tree status, root cause, option comparison and rationale, files changed and purpose, relevant hashes if practical, each pass and test result, evidence tier (source/unit/mock/API/in-process/live worker/browser/full E2E), risks, limitations and next dependency.
Report statuses honestly: DELIVERED & VERIFIED, PARTIALLY VERIFIED, BLOCKED or REOPENED. Do not say full E2E without the real required components running together.

9. STOP / CONTINUE RULE
Do not start a different implementation item in parallel or expand this scope to unrelated fixes. Complete all three passes, update records and then continue automatically to the next unblocked item in the master execution queue without waiting for routine approval. Stop only for a real blocker, unresolved high-impact product choice, credential/account action, real publication, destructive action against actual data, or an environment change that requires owner authorization. If blocked, document exact evidence and work safely on independent unblocked work only if it does not depend on the blocker.
Never use `git reset`, `git clean`, blanket reverts, destructive DB resets, `docker compose down -v`, or broad file deletion. Do not reintroduce captions/subtitles; preserve transcription for internal scoring/semantic analysis; retain the frozen Shorts duration limit unless the owner explicitly changes it.
```


### Copy-ready prompt — ROADMAP-1.2: Start Processing to Dashboard

```text
You are the ClipForge engineering agent working in `D:\automation video clips\clipforge`.

WORK ITEM: ROADMAP-1.2 — Start Processing to Dashboard
STATE: Reconcile current repository state before acting. Do not assume this item is open just because it appears in the roadmap.

1. PROBLEM / OBJECTIVE
Prove that accepted work appears and progresses in Dashboard based on durable Job state.

2. PREFLIGHT AND EVIDENCE COLLECTION
Read `AGENTS.md`, the applicable freeze/rule files, `docs/engineering/PHASE_TRACKER.md`, `MASTER_EXECUTION_LEDGER.md`, `IMPLEMENTATION_STATUS.md`, `ENGINEERING_DEFECT_REGISTER.md`, `PIPELINE_CATALOG_AND_DEPENDENCY_GRAPH.md`, `FRONTEND_PAGE_FEATURE_INVENTORY.md`, `PROJECT_CONTINUITY.md`, and the newest relevant audit/decision-log entries. Read only files relevant to this scope in depth, but reconcile any status claims before editing.
Inspect actual current source, schema, runtime route/client/task contracts, tests and caller/callee relationships. Reproduce the reported behavior with a safe isolated fixture where feasible. Separate VERIFIED FACTS, INFERENCES and UNKNOWNS. Record exact file paths, line ranges, commands and observed outputs.
Trace UI action → API response → persisted Job → Celery dispatch → worker → progress writes/events → active card → history/refresh. Recent records claim this was repaired; revalidate against the current container and code.
Capture `git status --short`, branch/commit, existing diff/untracked inventory and relevant environment/container identity before editing. Protect all pre-existing changes. Do not assume old hashes, route counts, schema revisions or historic reports still reflect the current environment.

3. COMPARE APPROACHES AND JUSTIFY THE CHOICE
Approach selection method: Compare at least two plausible approaches where meaningful: (A) smallest local repair, (B) reuse an established repository abstraction/pattern, and (C) architectural change only if the first two cannot meet verified requirements. Use evidence, not preference. Evaluate correctness, data safety, architectural consistency, backwards compatibility, idempotency/concurrency, performance, testability, reversibility, scope and maintenance cost. Record the chosen approach and specific reasons each alternative was rejected. If the problem is already solved in current source, choose the no-op verification path.
Before coding, write a small comparison table in the decision log: option; correctness against acceptance criteria; data/security risk; compatibility; concurrency/idempotency; complexity/maintenance; reversibility; evidence for/against. Do not create arbitrary numerical scores. Explain why the chosen approach is proportionate to the proven root cause and why each rejected alternative is inferior for this evidence.
If the current implementation already meets the requirement, choose verification-only and avoid a redundant change. If requirements remain ambiguous and a wrong choice would be consequential, stop at a documented blocker rather than invent behavior.

4. IMPLEMENTATION BOUNDARY
Implement only this work item. Prefer the smallest complete, maintainable fix using existing models, APIs, task lifecycle, storage/artifact and frontend patterns. Avoid duplicate frameworks, helpers, routes, state machines, database fields or tests when an existing abstraction meets the requirement.
Preserve all unrelated behavior and frozen components. Do not remove code based on apparent lack of callers without a call-site/dependency audit. Do not change public API semantics without documenting callers, compatibility plan and tests. Any migration must be justified, forward-only and data-preserving.
Scope-specific acceptance criteria:
- Persist Job before dispatch; ensure dispatch failure marks the durable job as failed.
- Verify progress monotonicity, terminal-state protections, cancellation distinction and refresh persistence.
- Differentiate queued, executing and completed states.

5. REQUIRED TESTING
Add focused regression tests for the root cause and relevant negative, failure, boundary, retry, concurrency and stale-state paths. Assert durable database/filesystem/worker state as applicable, not only mocked return values. Use synthetic media, disposable test records and test provider mode. Never publish to real YouTube or destructive-clean real data.
- Successful synthetic job through actual worker; broker/dispatch failure; worker task failure; cancel; refresh; terminal history.
- Assert DB status/progress and UI agree.
- Mock publisher only.
Run the exact focused suite, relevant regressions, static checks and build/browser/integration tests required by the changed layers. Capture actual commands, counts, exit codes, warning/failure output and environment. Do not claim a test ran if only drafted or launched without a completed result.

6. THREE VERIFICATION PASSES — REQUIRED FOR THIS ITEM
PASS 1 — Implementation verification: review diff against every acceptance criterion; run focused tests and the affected workflow; prove expected state and failure behavior.
PASS 2 — Independent challenge: stop thinking like the implementation author. Re-read the requirement and original defect evidence. Try to falsify the fix with adversarial inputs, conflicts, retries, parallel requests, stale state and failure injection. Compare alternative approaches again. Inspect whether the tests could pass while production is still broken. Fix any issue discovered and record changes since Pass 1.
PASS 3 — Differential re-verification: re-read the final diff and working tree from scratch. Compare final code with Passes 1 and 2, identify all changes introduced after each earlier pass, rerun affected focused tests and relevant regressions against the final tree, and verify reports/status files match the final code. Any new code change invalidates the affected previous pass; repeat it.

7. EXPLICIT SELF-CHALLENGE QUESTIONS
- What concrete evidence proves the original problem existed?
- Why does each changed line/function need to exist?
- What alternative was considered and why was it rejected?
- Could a real production record or untrusted caller reach the test/mock path?
- What happens on failure, retry, concurrency, restart and stale response?
- What does this test prove, and what does it not prove?
- Did I preserve all previous working-tree files and frozen behavior?
- What changed between verification passes and why?
- Which claims remain unverified or depend on an environmental assumption?

8. REQUIRED RECORDS AND FINAL RESPONSE
Update only applicable canonical documents: phase tracker, master ledger, implementation status, defect register, relevant API/frontend/pipeline inventories, audit report and `docs/engineering/AI_DECISION_LOG.md`. Preserve old audit records and append corrections instead of rewriting history. Make status consistent everywhere.
Record work-item ID, before/after working-tree status, root cause, option comparison and rationale, files changed and purpose, relevant hashes if practical, each pass and test result, evidence tier (source/unit/mock/API/in-process/live worker/browser/full E2E), risks, limitations and next dependency.
Report statuses honestly: DELIVERED & VERIFIED, PARTIALLY VERIFIED, BLOCKED or REOPENED. Do not say full E2E without the real required components running together.

9. STOP / CONTINUE RULE
Do not start a different implementation item in parallel or expand this scope to unrelated fixes. Complete all three passes, update records and then continue automatically to the next unblocked item in the master execution queue without waiting for routine approval. Stop only for a real blocker, unresolved high-impact product choice, credential/account action, real publication, destructive action against actual data, or an environment change that requires owner authorization. If blocked, document exact evidence and work safely on independent unblocked work only if it does not depend on the blocker.
Never use `git reset`, `git clean`, blanket reverts, destructive DB resets, `docker compose down -v`, or broad file deletion. Do not reintroduce captions/subtitles; preserve transcription for internal scoring/semantic analysis; retain the frozen Shorts duration limit unless the owner explicitly changes it.
```


### Copy-ready prompt — ROADMAP-1.3: Channel disconnection and source/destination role separation

```text
You are the ClipForge engineering agent working in `D:\automation video clips\clipforge`.

WORK ITEM: ROADMAP-1.3 — Channel disconnection and source/destination role separation
STATE: Reconcile current repository state before acting. Do not assume this item is open just because it appears in the roadmap.

1. PROBLEM / OBJECTIVE
Ensure disconnecting a publishing destination never silently removes a monitored source channel or historical records.

2. PREFLIGHT AND EVIDENCE COLLECTION
Read `AGENTS.md`, the applicable freeze/rule files, `docs/engineering/PHASE_TRACKER.md`, `MASTER_EXECUTION_LEDGER.md`, `IMPLEMENTATION_STATUS.md`, `ENGINEERING_DEFECT_REGISTER.md`, `PIPELINE_CATALOG_AND_DEPENDENCY_GRAPH.md`, `FRONTEND_PAGE_FEATURE_INVENTORY.md`, `PROJECT_CONTINUITY.md`, and the newest relevant audit/decision-log entries. Read only files relevant to this scope in depth, but reconcile any status claims before editing.
Inspect actual current source, schema, runtime route/client/task contracts, tests and caller/callee relationships. Reproduce the reported behavior with a safe isolated fixture where feasible. Separate VERIFIED FACTS, INFERENCES and UNKNOWNS. Record exact file paths, line ranges, commands and observed outputs.
Inspect Channel roles/flags, OAuth credential associations, channel-monitor scheduler, destination selectors, published clips and disconnect/delete routes. Verify current implementation because historic subphase numbering conflicts with canonical Phase 1.3 storage cleanup.
Capture `git status --short`, branch/commit, existing diff/untracked inventory and relevant environment/container identity before editing. Protect all pre-existing changes. Do not assume old hashes, route counts, schema revisions or historic reports still reflect the current environment.

3. COMPARE APPROACHES AND JUSTIFY THE CHOICE
Approach selection method: Compare at least two plausible approaches where meaningful: (A) smallest local repair, (B) reuse an established repository abstraction/pattern, and (C) architectural change only if the first two cannot meet verified requirements. Use evidence, not preference. Evaluate correctness, data safety, architectural consistency, backwards compatibility, idempotency/concurrency, performance, testability, reversibility, scope and maintenance cost. Record the chosen approach and specific reasons each alternative was rejected. If the problem is already solved in current source, choose the no-op verification path.
Before coding, write a small comparison table in the decision log: option; correctness against acceptance criteria; data/security risk; compatibility; concurrency/idempotency; complexity/maintenance; reversibility; evidence for/against. Do not create arbitrary numerical scores. Explain why the chosen approach is proportionate to the proven root cause and why each rejected alternative is inferior for this evidence.
If the current implementation already meets the requirement, choose verification-only and avoid a redundant change. If requirements remain ambiguous and a wrong choice would be consequential, stop at a documented blocker rather than invent behavior.

4. IMPLEMENTATION BOUNDARY
Implement only this work item. Prefer the smallest complete, maintainable fix using existing models, APIs, task lifecycle, storage/artifact and frontend patterns. Avoid duplicate frameworks, helpers, routes, state machines, database fields or tests when an existing abstraction meets the requirement.
Preserve all unrelated behavior and frozen components. Do not remove code based on apparent lack of callers without a call-site/dependency audit. Do not change public API semantics without documenting callers, compatibility plan and tests. Any migration must be justified, forward-only and data-preserving.
Scope-specific acceptance criteria:
- Represent source-monitoring and publish-destination roles explicitly using existing model contract.
- Make disconnect behavior account-scoped, preserve history, stop only appropriate monitors and revoke only intended credentials.
- Avoid irreversible deletion when a role association can be safely detached.

5. REQUIRED TESTING
Add focused regression tests for the root cause and relevant negative, failure, boundary, retry, concurrency and stale-state paths. Assert durable database/filesystem/worker state as applicable, not only mocked return values. Use synthetic media, disposable test records and test provider mode. Never publish to real YouTube or destructive-clean real data.
- Source-only, destination-only, combined-role, disconnect one of multiple accounts, reconnect and refresh scenarios.
- Verify scheduler behavior, DB relations, historical clips/jobs, publish availability and OAuth tokens.
- Check authorization at the server boundary.
Run the exact focused suite, relevant regressions, static checks and build/browser/integration tests required by the changed layers. Capture actual commands, counts, exit codes, warning/failure output and environment. Do not claim a test ran if only drafted or launched without a completed result.

6. THREE VERIFICATION PASSES — REQUIRED FOR THIS ITEM
PASS 1 — Implementation verification: review diff against every acceptance criterion; run focused tests and the affected workflow; prove expected state and failure behavior.
PASS 2 — Independent challenge: stop thinking like the implementation author. Re-read the requirement and original defect evidence. Try to falsify the fix with adversarial inputs, conflicts, retries, parallel requests, stale state and failure injection. Compare alternative approaches again. Inspect whether the tests could pass while production is still broken. Fix any issue discovered and record changes since Pass 1.
PASS 3 — Differential re-verification: re-read the final diff and working tree from scratch. Compare final code with Passes 1 and 2, identify all changes introduced after each earlier pass, rerun affected focused tests and relevant regressions against the final tree, and verify reports/status files match the final code. Any new code change invalidates the affected previous pass; repeat it.

7. EXPLICIT SELF-CHALLENGE QUESTIONS
- What concrete evidence proves the original problem existed?
- Why does each changed line/function need to exist?
- What alternative was considered and why was it rejected?
- Could a real production record or untrusted caller reach the test/mock path?
- What happens on failure, retry, concurrency, restart and stale response?
- What does this test prove, and what does it not prove?
- Did I preserve all previous working-tree files and frozen behavior?
- What changed between verification passes and why?
- Which claims remain unverified or depend on an environmental assumption?

8. REQUIRED RECORDS AND FINAL RESPONSE
Update only applicable canonical documents: phase tracker, master ledger, implementation status, defect register, relevant API/frontend/pipeline inventories, audit report and `docs/engineering/AI_DECISION_LOG.md`. Preserve old audit records and append corrections instead of rewriting history. Make status consistent everywhere.
Record work-item ID, before/after working-tree status, root cause, option comparison and rationale, files changed and purpose, relevant hashes if practical, each pass and test result, evidence tier (source/unit/mock/API/in-process/live worker/browser/full E2E), risks, limitations and next dependency.
Report statuses honestly: DELIVERED & VERIFIED, PARTIALLY VERIFIED, BLOCKED or REOPENED. Do not say full E2E without the real required components running together.

9. STOP / CONTINUE RULE
Do not start a different implementation item in parallel or expand this scope to unrelated fixes. Complete all three passes, update records and then continue automatically to the next unblocked item in the master execution queue without waiting for routine approval. Stop only for a real blocker, unresolved high-impact product choice, credential/account action, real publication, destructive action against actual data, or an environment change that requires owner authorization. If blocked, document exact evidence and work safely on independent unblocked work only if it does not depend on the blocker.
Never use `git reset`, `git clean`, blanket reverts, destructive DB resets, `docker compose down -v`, or broad file deletion. Do not reintroduce captions/subtitles; preserve transcription for internal scoring/semantic analysis; retain the frozen Shorts duration limit unless the owner explicitly changes it.
```


### Copy-ready prompt — ROADMAP-1.4: Multi-account OAuth security

```text
You are the ClipForge engineering agent working in `D:\automation video clips\clipforge`.

WORK ITEM: ROADMAP-1.4 — Multi-account OAuth security
STATE: Reconcile current repository state before acting. Do not assume this item is open just because it appears in the roadmap.

1. PROBLEM / OBJECTIVE
Keep OAuth accounts isolated and prevent state, redirect or credential cross-contamination.

2. PREFLIGHT AND EVIDENCE COLLECTION
Read `AGENTS.md`, the applicable freeze/rule files, `docs/engineering/PHASE_TRACKER.md`, `MASTER_EXECUTION_LEDGER.md`, `IMPLEMENTATION_STATUS.md`, `ENGINEERING_DEFECT_REGISTER.md`, `PIPELINE_CATALOG_AND_DEPENDENCY_GRAPH.md`, `FRONTEND_PAGE_FEATURE_INVENTORY.md`, `PROJECT_CONTINUITY.md`, and the newest relevant audit/decision-log entries. Read only files relevant to this scope in depth, but reconcile any status claims before editing.
Inspect actual current source, schema, runtime route/client/task contracts, tests and caller/callee relationships. Reproduce the reported behavior with a safe isolated fixture where feasible. Separate VERIFIED FACTS, INFERENCES and UNKNOWNS. Record exact file paths, line ranges, commands and observed outputs.
Inspect OAuth route/service, state nonce, redirect validation, token storage mounts, channel-to-account relationship, refresh process, disconnect and UI identity display.
Capture `git status --short`, branch/commit, existing diff/untracked inventory and relevant environment/container identity before editing. Protect all pre-existing changes. Do not assume old hashes, route counts, schema revisions or historic reports still reflect the current environment.

3. COMPARE APPROACHES AND JUSTIFY THE CHOICE
Approach selection method: Compare at least two plausible approaches where meaningful: (A) smallest local repair, (B) reuse an established repository abstraction/pattern, and (C) architectural change only if the first two cannot meet verified requirements. Use evidence, not preference. Evaluate correctness, data safety, architectural consistency, backwards compatibility, idempotency/concurrency, performance, testability, reversibility, scope and maintenance cost. Record the chosen approach and specific reasons each alternative was rejected. If the problem is already solved in current source, choose the no-op verification path.
Before coding, write a small comparison table in the decision log: option; correctness against acceptance criteria; data/security risk; compatibility; concurrency/idempotency; complexity/maintenance; reversibility; evidence for/against. Do not create arbitrary numerical scores. Explain why the chosen approach is proportionate to the proven root cause and why each rejected alternative is inferior for this evidence.
If the current implementation already meets the requirement, choose verification-only and avoid a redundant change. If requirements remain ambiguous and a wrong choice would be consequential, stop at a documented blocker rather than invent behavior.

4. IMPLEMENTATION BOUNDARY
Implement only this work item. Prefer the smallest complete, maintainable fix using existing models, APIs, task lifecycle, storage/artifact and frontend patterns. Avoid duplicate frameworks, helpers, routes, state machines, database fields or tests when an existing abstraction meets the requirement.
Preserve all unrelated behavior and frozen components. Do not remove code based on apparent lack of callers without a call-site/dependency audit. Do not change public API semantics without documenting callers, compatibility plan and tests. Any migration must be justified, forward-only and data-preserving.
Scope-specific acceptance criteria:
- Validate state/redirect using existing secure conventions; do not log tokens or codes.
- Ensure one account refresh/disconnect does not mutate another account credentials.
- Handle expired/revoked/missing tokens explicitly.
- Preserve tokens volume and existing OAuth contract unless evidence requires migration.

5. REQUIRED TESTING
Add focused regression tests for the root cause and relevant negative, failure, boundary, retry, concurrency and stale-state paths. Assert durable database/filesystem/worker state as applicable, not only mocked return values. Use synthetic media, disposable test records and test provider mode. Never publish to real YouTube or destructive-clean real data.
- Two independent accounts; forged/missing/replayed state; mismatched channel/account; refresh failure; disconnect one account; restart persistence.
- Assert secrets remain outside logs/response/UI.
- Use mock OAuth/provider responses in tests.
Run the exact focused suite, relevant regressions, static checks and build/browser/integration tests required by the changed layers. Capture actual commands, counts, exit codes, warning/failure output and environment. Do not claim a test ran if only drafted or launched without a completed result.

6. THREE VERIFICATION PASSES — REQUIRED FOR THIS ITEM
PASS 1 — Implementation verification: review diff against every acceptance criterion; run focused tests and the affected workflow; prove expected state and failure behavior.
PASS 2 — Independent challenge: stop thinking like the implementation author. Re-read the requirement and original defect evidence. Try to falsify the fix with adversarial inputs, conflicts, retries, parallel requests, stale state and failure injection. Compare alternative approaches again. Inspect whether the tests could pass while production is still broken. Fix any issue discovered and record changes since Pass 1.
PASS 3 — Differential re-verification: re-read the final diff and working tree from scratch. Compare final code with Passes 1 and 2, identify all changes introduced after each earlier pass, rerun affected focused tests and relevant regressions against the final tree, and verify reports/status files match the final code. Any new code change invalidates the affected previous pass; repeat it.

7. EXPLICIT SELF-CHALLENGE QUESTIONS
- What concrete evidence proves the original problem existed?
- Why does each changed line/function need to exist?
- What alternative was considered and why was it rejected?
- Could a real production record or untrusted caller reach the test/mock path?
- What happens on failure, retry, concurrency, restart and stale response?
- What does this test prove, and what does it not prove?
- Did I preserve all previous working-tree files and frozen behavior?
- What changed between verification passes and why?
- Which claims remain unverified or depend on an environmental assumption?

8. REQUIRED RECORDS AND FINAL RESPONSE
Update only applicable canonical documents: phase tracker, master ledger, implementation status, defect register, relevant API/frontend/pipeline inventories, audit report and `docs/engineering/AI_DECISION_LOG.md`. Preserve old audit records and append corrections instead of rewriting history. Make status consistent everywhere.
Record work-item ID, before/after working-tree status, root cause, option comparison and rationale, files changed and purpose, relevant hashes if practical, each pass and test result, evidence tier (source/unit/mock/API/in-process/live worker/browser/full E2E), risks, limitations and next dependency.
Report statuses honestly: DELIVERED & VERIFIED, PARTIALLY VERIFIED, BLOCKED or REOPENED. Do not say full E2E without the real required components running together.

9. STOP / CONTINUE RULE
Do not start a different implementation item in parallel or expand this scope to unrelated fixes. Complete all three passes, update records and then continue automatically to the next unblocked item in the master execution queue without waiting for routine approval. Stop only for a real blocker, unresolved high-impact product choice, credential/account action, real publication, destructive action against actual data, or an environment change that requires owner authorization. If blocked, document exact evidence and work safely on independent unblocked work only if it does not depend on the blocker.
Never use `git reset`, `git clean`, blanket reverts, destructive DB resets, `docker compose down -v`, or broad file deletion. Do not reintroduce captions/subtitles; preserve transcription for internal scoring/semantic analysis; retain the frozen Shorts duration limit unless the owner explicitly changes it.
```


### Copy-ready prompt — ROADMAP-1.5: Shorts analytics accuracy

```text
You are the ClipForge engineering agent working in `D:\automation video clips\clipforge`.

WORK ITEM: ROADMAP-1.5 — Shorts analytics accuracy
STATE: Reconcile current repository state before acting. Do not assume this item is open just because it appears in the roadmap.

1. PROBLEM / OBJECTIVE
Ensure labels and metrics are based on supported evidence, not unsupported lifetime totals or heuristic certainty.

2. PREFLIGHT AND EVIDENCE COLLECTION
Read `AGENTS.md`, the applicable freeze/rule files, `docs/engineering/PHASE_TRACKER.md`, `MASTER_EXECUTION_LEDGER.md`, `IMPLEMENTATION_STATUS.md`, `ENGINEERING_DEFECT_REGISTER.md`, `PIPELINE_CATALOG_AND_DEPENDENCY_GRAPH.md`, `FRONTEND_PAGE_FEATURE_INVENTORY.md`, `PROJECT_CONTINUITY.md`, and the newest relevant audit/decision-log entries. Read only files relevant to this scope in depth, but reconcile any status claims before editing.
Inspect actual current source, schema, runtime route/client/task contracts, tests and caller/callee relationships. Reproduce the reported behavior with a safe isolated fixture where feasible. Separate VERIFIED FACTS, INFERENCES and UNKNOWNS. Record exact file paths, line ranges, commands and observed outputs.
Trace analytics ingestion/provider endpoints, source metadata, Shorts classification, pagination and time-range semantics. Inspect API schemas and UI labels.
Capture `git status --short`, branch/commit, existing diff/untracked inventory and relevant environment/container identity before editing. Protect all pre-existing changes. Do not assume old hashes, route counts, schema revisions or historic reports still reflect the current environment.

3. COMPARE APPROACHES AND JUSTIFY THE CHOICE
Approach selection method: Compare at least two plausible approaches where meaningful: (A) smallest local repair, (B) reuse an established repository abstraction/pattern, and (C) architectural change only if the first two cannot meet verified requirements. Use evidence, not preference. Evaluate correctness, data safety, architectural consistency, backwards compatibility, idempotency/concurrency, performance, testability, reversibility, scope and maintenance cost. Record the chosen approach and specific reasons each alternative was rejected. If the problem is already solved in current source, choose the no-op verification path.
Before coding, write a small comparison table in the decision log: option; correctness against acceptance criteria; data/security risk; compatibility; concurrency/idempotency; complexity/maintenance; reversibility; evidence for/against. Do not create arbitrary numerical scores. Explain why the chosen approach is proportionate to the proven root cause and why each rejected alternative is inferior for this evidence.
If the current implementation already meets the requirement, choose verification-only and avoid a redundant change. If requirements remain ambiguous and a wrong choice would be consequential, stop at a documented blocker rather than invent behavior.

4. IMPLEMENTATION BOUNDARY
Implement only this work item. Prefer the smallest complete, maintainable fix using existing models, APIs, task lifecycle, storage/artifact and frontend patterns. Avoid duplicate frameworks, helpers, routes, state machines, database fields or tests when an existing abstraction meets the requirement.
Preserve all unrelated behavior and frozen components. Do not remove code based on apparent lack of callers without a call-site/dependency audit. Do not change public API semantics without documenting callers, compatibility plan and tests. Any migration must be justified, forward-only and data-preserving.
Scope-specific acceptance criteria:
- Define classification using actual available duration/format/metadata rules supported by the project.
- Label scan coverage and time window; distinguish partial results from lifetime totals.
- Handle pagination, missing stats and provider limits without inventing values.

5. REQUIRED TESTING
Add focused regression tests for the root cause and relevant negative, failure, boundary, retry, concurrency and stale-state paths. Assert durable database/filesystem/worker state as applicable, not only mocked return values. Use synthetic media, disposable test records and test provider mode. Never publish to real YouTube or destructive-clean real data.
- Known Shorts/non-Shorts fixtures; boundary durations; unknown metadata; paginated and partial data; provider errors.
- Compare displayed numbers and labels with raw normalized responses.
- Document assumptions and unsupported metrics.
Run the exact focused suite, relevant regressions, static checks and build/browser/integration tests required by the changed layers. Capture actual commands, counts, exit codes, warning/failure output and environment. Do not claim a test ran if only drafted or launched without a completed result.

6. THREE VERIFICATION PASSES — REQUIRED FOR THIS ITEM
PASS 1 — Implementation verification: review diff against every acceptance criterion; run focused tests and the affected workflow; prove expected state and failure behavior.
PASS 2 — Independent challenge: stop thinking like the implementation author. Re-read the requirement and original defect evidence. Try to falsify the fix with adversarial inputs, conflicts, retries, parallel requests, stale state and failure injection. Compare alternative approaches again. Inspect whether the tests could pass while production is still broken. Fix any issue discovered and record changes since Pass 1.
PASS 3 — Differential re-verification: re-read the final diff and working tree from scratch. Compare final code with Passes 1 and 2, identify all changes introduced after each earlier pass, rerun affected focused tests and relevant regressions against the final tree, and verify reports/status files match the final code. Any new code change invalidates the affected previous pass; repeat it.

7. EXPLICIT SELF-CHALLENGE QUESTIONS
- What concrete evidence proves the original problem existed?
- Why does each changed line/function need to exist?
- What alternative was considered and why was it rejected?
- Could a real production record or untrusted caller reach the test/mock path?
- What happens on failure, retry, concurrency, restart and stale response?
- What does this test prove, and what does it not prove?
- Did I preserve all previous working-tree files and frozen behavior?
- What changed between verification passes and why?
- Which claims remain unverified or depend on an environmental assumption?

8. REQUIRED RECORDS AND FINAL RESPONSE
Update only applicable canonical documents: phase tracker, master ledger, implementation status, defect register, relevant API/frontend/pipeline inventories, audit report and `docs/engineering/AI_DECISION_LOG.md`. Preserve old audit records and append corrections instead of rewriting history. Make status consistent everywhere.
Record work-item ID, before/after working-tree status, root cause, option comparison and rationale, files changed and purpose, relevant hashes if practical, each pass and test result, evidence tier (source/unit/mock/API/in-process/live worker/browser/full E2E), risks, limitations and next dependency.
Report statuses honestly: DELIVERED & VERIFIED, PARTIALLY VERIFIED, BLOCKED or REOPENED. Do not say full E2E without the real required components running together.

9. STOP / CONTINUE RULE
Do not start a different implementation item in parallel or expand this scope to unrelated fixes. Complete all three passes, update records and then continue automatically to the next unblocked item in the master execution queue without waiting for routine approval. Stop only for a real blocker, unresolved high-impact product choice, credential/account action, real publication, destructive action against actual data, or an environment change that requires owner authorization. If blocked, document exact evidence and work safely on independent unblocked work only if it does not depend on the blocker.
Never use `git reset`, `git clean`, blanket reverts, destructive DB resets, `docker compose down -v`, or broad file deletion. Do not reintroduce captions/subtitles; preserve transcription for internal scoring/semantic analysis; retain the frozen Shorts duration limit unless the owner explicitly changes it.
```


### Copy-ready prompt — ROADMAP-1.6: Publishing settings application

```text
You are the ClipForge engineering agent working in `D:\automation video clips\clipforge`.

WORK ITEM: ROADMAP-1.6 — Publishing settings application
STATE: Reconcile current repository state before acting. Do not assume this item is open just because it appears in the roadmap.

1. PROBLEM / OBJECTIVE
Verify saved settings reach the actual provider request and unsupported settings are disclosed honestly.

2. PREFLIGHT AND EVIDENCE COLLECTION
Read `AGENTS.md`, the applicable freeze/rule files, `docs/engineering/PHASE_TRACKER.md`, `MASTER_EXECUTION_LEDGER.md`, `IMPLEMENTATION_STATUS.md`, `ENGINEERING_DEFECT_REGISTER.md`, `PIPELINE_CATALOG_AND_DEPENDENCY_GRAPH.md`, `FRONTEND_PAGE_FEATURE_INVENTORY.md`, `PROJECT_CONTINUITY.md`, and the newest relevant audit/decision-log entries. Read only files relevant to this scope in depth, but reconcile any status claims before editing.
Inspect actual current source, schema, runtime route/client/task contracts, tests and caller/callee relationships. Reproduce the reported behavior with a safe isolated fixture where feasible. Separate VERIFIED FACTS, INFERENCES and UNKNOWNS. Record exact file paths, line ranges, commands and observed outputs.
Trace title, description, tags, category, privacy, license and supported flags from UI → API schema → durable model/defaults → publisher request → mock provider capture.
Capture `git status --short`, branch/commit, existing diff/untracked inventory and relevant environment/container identity before editing. Protect all pre-existing changes. Do not assume old hashes, route counts, schema revisions or historic reports still reflect the current environment.

3. COMPARE APPROACHES AND JUSTIFY THE CHOICE
Approach selection method: Compare at least two plausible approaches where meaningful: (A) smallest local repair, (B) reuse an established repository abstraction/pattern, and (C) architectural change only if the first two cannot meet verified requirements. Use evidence, not preference. Evaluate correctness, data safety, architectural consistency, backwards compatibility, idempotency/concurrency, performance, testability, reversibility, scope and maintenance cost. Record the chosen approach and specific reasons each alternative was rejected. If the problem is already solved in current source, choose the no-op verification path.
Before coding, write a small comparison table in the decision log: option; correctness against acceptance criteria; data/security risk; compatibility; concurrency/idempotency; complexity/maintenance; reversibility; evidence for/against. Do not create arbitrary numerical scores. Explain why the chosen approach is proportionate to the proven root cause and why each rejected alternative is inferior for this evidence.
If the current implementation already meets the requirement, choose verification-only and avoid a redundant change. If requirements remain ambiguous and a wrong choice would be consequential, stop at a documented blocker rather than invent behavior.

4. IMPLEMENTATION BOUNDARY
Implement only this work item. Prefer the smallest complete, maintainable fix using existing models, APIs, task lifecycle, storage/artifact and frontend patterns. Avoid duplicate frameworks, helpers, routes, state machines, database fields or tests when an existing abstraction meets the requirement.
Preserve all unrelated behavior and frozen components. Do not remove code based on apparent lack of callers without a call-site/dependency audit. Do not change public API semantics without documenting callers, compatibility plan and tests. Any migration must be justified, forward-only and data-preserving.
Scope-specific acceptance criteria:
- Keep clip-level and destination-level fields distinct according to current schema.
- Do not show success before persistence/provider acceptance.
- Respect defaults, empty-vs-omitted semantics, validation and destination authorization.
- Mark unsupported preferences clearly rather than persisting a no-op.

5. REQUIRED TESTING
Add focused regression tests for the root cause and relevant negative, failure, boundary, retry, concurrency and stale-state paths. Assert durable database/filesystem/worker state as applicable, not only mocked return values. Use synthetic media, disposable test records and test provider mode. Never publish to real YouTube or destructive-clean real data.
- Round trip save/load; invalid values; omitted vs empty fields; provider rejection; multi-destination settings if supported; refresh after save.
- Inspect exact mock upload payload and persisted values.
- Run publishing regression tests.
Run the exact focused suite, relevant regressions, static checks and build/browser/integration tests required by the changed layers. Capture actual commands, counts, exit codes, warning/failure output and environment. Do not claim a test ran if only drafted or launched without a completed result.

6. THREE VERIFICATION PASSES — REQUIRED FOR THIS ITEM
PASS 1 — Implementation verification: review diff against every acceptance criterion; run focused tests and the affected workflow; prove expected state and failure behavior.
PASS 2 — Independent challenge: stop thinking like the implementation author. Re-read the requirement and original defect evidence. Try to falsify the fix with adversarial inputs, conflicts, retries, parallel requests, stale state and failure injection. Compare alternative approaches again. Inspect whether the tests could pass while production is still broken. Fix any issue discovered and record changes since Pass 1.
PASS 3 — Differential re-verification: re-read the final diff and working tree from scratch. Compare final code with Passes 1 and 2, identify all changes introduced after each earlier pass, rerun affected focused tests and relevant regressions against the final tree, and verify reports/status files match the final code. Any new code change invalidates the affected previous pass; repeat it.

7. EXPLICIT SELF-CHALLENGE QUESTIONS
- What concrete evidence proves the original problem existed?
- Why does each changed line/function need to exist?
- What alternative was considered and why was it rejected?
- Could a real production record or untrusted caller reach the test/mock path?
- What happens on failure, retry, concurrency, restart and stale response?
- What does this test prove, and what does it not prove?
- Did I preserve all previous working-tree files and frozen behavior?
- What changed between verification passes and why?
- Which claims remain unverified or depend on an environmental assumption?

8. REQUIRED RECORDS AND FINAL RESPONSE
Update only applicable canonical documents: phase tracker, master ledger, implementation status, defect register, relevant API/frontend/pipeline inventories, audit report and `docs/engineering/AI_DECISION_LOG.md`. Preserve old audit records and append corrections instead of rewriting history. Make status consistent everywhere.
Record work-item ID, before/after working-tree status, root cause, option comparison and rationale, files changed and purpose, relevant hashes if practical, each pass and test result, evidence tier (source/unit/mock/API/in-process/live worker/browser/full E2E), risks, limitations and next dependency.
Report statuses honestly: DELIVERED & VERIFIED, PARTIALLY VERIFIED, BLOCKED or REOPENED. Do not say full E2E without the real required components running together.

9. STOP / CONTINUE RULE
Do not start a different implementation item in parallel or expand this scope to unrelated fixes. Complete all three passes, update records and then continue automatically to the next unblocked item in the master execution queue without waiting for routine approval. Stop only for a real blocker, unresolved high-impact product choice, credential/account action, real publication, destructive action against actual data, or an environment change that requires owner authorization. If blocked, document exact evidence and work safely on independent unblocked work only if it does not depend on the blocker.
Never use `git reset`, `git clean`, blanket reverts, destructive DB resets, `docker compose down -v`, or broad file deletion. Do not reintroduce captions/subtitles; preserve transcription for internal scoring/semantic analysis; retain the frozen Shorts duration limit unless the owner explicitly changes it.
```


## Main phase prompt — ROADMAP Phase 2: API connections and safe cleanup

```text
You are the ClipForge engineering agent. Coordinate Phase 2: API connections and safe cleanup as a sequence of independently testable child work items, not a single broad implementation.

PROBLEM / OBJECTIVE
Ensure frontend API origins/contracts and cleanup lifecycle are correct. Execute ROADMAP-2.1–2.4 one at a time.

DISCOVERY AND METHOD
Read the current project rules and phase ledger; establish whether each child is already delivered, unverified, blocked or open. Compare viable approaches for each child before implementation. Prefer the smallest evidence-backed fix that reuses current architecture. Record a qualitative comparison of correctness, data safety, compatibility, concurrency/idempotency, operational burden, reversibility and testability. Explain the chosen approach and why other options were rejected. Never rely on old phase numbers when they conflict with canonical records.

PHASE ACCEPTANCE CRITERIA
- Current `RetentionHeatmap` contract confirmed.
- Cleanup preview read-only and accurate.
- Execution revalidates targets with durable recovery safeguards.
- Route/client inventories reconciled.

EXECUTION SEQUENCE
Execute the child subphases in the order shown in the index. For each child: inspect/reproduce; implement only that child; run Pass 1, Pass 2 and Pass 3 as defined in the companion rules; update `AI_DECISION_LOG.md` and canonical status; then move autonomously to the next unblocked child. Do not bundle unrelated children into one diff.

CROSS-VERIFICATION
Before phase close, independently check every child status against final source, test outputs and runtime evidence. Recheck frozen invariants, changed files and working-tree state. A completed build alone does not prove runtime behavior. A task ID/toast does not prove a worker finished.

BOUNDARIES
Current canonical implementation may already satisfy some items; audit instead of duplicating.
Preserve existing changes and untracked files. No real publishing. No caption/subtitle framework. Never use destructive Git operations or broad DB/storage deletion. High-impact irreversible actions against real user data require explicit owner authorization.

PHASE EXIT
Close this main phase only when all required children are either independently verified or explicitly documented as blocked with owner-relevant rationale. If blocked, do not mislabel the phase complete. Record the next unblocked dependency and continue autonomously when safe.
```


### Copy-ready prompt — ROADMAP-2.1: RetentionHeatmap API URLs

```text
You are the ClipForge engineering agent working in `D:\automation video clips\clipforge`.

WORK ITEM: ROADMAP-2.1 — RetentionHeatmap API URLs
STATE: Reconcile current repository state before acting. Do not assume this item is open just because it appears in the roadmap.

1. PROBLEM / OBJECTIVE
Ensure retention heatmap calls the configured backend API rather than the Next.js origin by accident.

2. PREFLIGHT AND EVIDENCE COLLECTION
Read `AGENTS.md`, the applicable freeze/rule files, `docs/engineering/PHASE_TRACKER.md`, `MASTER_EXECUTION_LEDGER.md`, `IMPLEMENTATION_STATUS.md`, `ENGINEERING_DEFECT_REGISTER.md`, `PIPELINE_CATALOG_AND_DEPENDENCY_GRAPH.md`, `FRONTEND_PAGE_FEATURE_INVENTORY.md`, `PROJECT_CONTINUITY.md`, and the newest relevant audit/decision-log entries. Read only files relevant to this scope in depth, but reconcile any status claims before editing.
Inspect actual current source, schema, runtime route/client/task contracts, tests and caller/callee relationships. Reproduce the reported behavior with a safe isolated fixture where feasible. Separate VERIFIED FACTS, INFERENCES and UNKNOWNS. Record exact file paths, line ranges, commands and observed outputs.
Inspect `RetentionHeatmap.tsx`, shared API base configuration, the get-retention/autofix helpers, actual backend prefixes and frontend test environment.
Capture `git status --short`, branch/commit, existing diff/untracked inventory and relevant environment/container identity before editing. Protect all pre-existing changes. Do not assume old hashes, route counts, schema revisions or historic reports still reflect the current environment.

3. COMPARE APPROACHES AND JUSTIFY THE CHOICE
Approach selection method: Compare at least two plausible approaches where meaningful: (A) smallest local repair, (B) reuse an established repository abstraction/pattern, and (C) architectural change only if the first two cannot meet verified requirements. Use evidence, not preference. Evaluate correctness, data safety, architectural consistency, backwards compatibility, idempotency/concurrency, performance, testability, reversibility, scope and maintenance cost. Record the chosen approach and specific reasons each alternative was rejected. If the problem is already solved in current source, choose the no-op verification path.
Before coding, write a small comparison table in the decision log: option; correctness against acceptance criteria; data/security risk; compatibility; concurrency/idempotency; complexity/maintenance; reversibility; evidence for/against. Do not create arbitrary numerical scores. Explain why the chosen approach is proportionate to the proven root cause and why each rejected alternative is inferior for this evidence.
If the current implementation already meets the requirement, choose verification-only and avoid a redundant change. If requirements remain ambiguous and a wrong choice would be consequential, stop at a documented blocker rather than invent behavior.

4. IMPLEMENTATION BOUNDARY
Implement only this work item. Prefer the smallest complete, maintainable fix using existing models, APIs, task lifecycle, storage/artifact and frontend patterns. Avoid duplicate frameworks, helpers, routes, state machines, database fields or tests when an existing abstraction meets the requirement.
Preserve all unrelated behavior and frozen components. Do not remove code based on apparent lack of callers without a call-site/dependency audit. Do not change public API semantics without documenting callers, compatibility plan and tests. Any migration must be justified, forward-only and data-preserving.
Scope-specific acceptance criteria:
- Replace raw relative fetch with shared typed API client when that is the repository convention.
- Handle configured base URL, HTTP errors, loading and response shape consistently.
- Preserve current UI and avoid changing endpoint semantics unnecessarily.

5. REQUIRED TESTING
Add focused regression tests for the root cause and relevant negative, failure, boundary, retry, concurrency and stale-state paths. Assert durable database/filesystem/worker state as applicable, not only mocked return values. Use synthetic media, disposable test records and test provider mode. Never publish to real YouTube or destructive-clean real data.
- Browser network inspection proves correct backend host/port and path.
- Success, empty, 4xx/5xx and network error.
- No console errors and correct rendered state.
- Typecheck/build and API contract tests.
Run the exact focused suite, relevant regressions, static checks and build/browser/integration tests required by the changed layers. Capture actual commands, counts, exit codes, warning/failure output and environment. Do not claim a test ran if only drafted or launched without a completed result.

6. THREE VERIFICATION PASSES — REQUIRED FOR THIS ITEM
PASS 1 — Implementation verification: review diff against every acceptance criterion; run focused tests and the affected workflow; prove expected state and failure behavior.
PASS 2 — Independent challenge: stop thinking like the implementation author. Re-read the requirement and original defect evidence. Try to falsify the fix with adversarial inputs, conflicts, retries, parallel requests, stale state and failure injection. Compare alternative approaches again. Inspect whether the tests could pass while production is still broken. Fix any issue discovered and record changes since Pass 1.
PASS 3 — Differential re-verification: re-read the final diff and working tree from scratch. Compare final code with Passes 1 and 2, identify all changes introduced after each earlier pass, rerun affected focused tests and relevant regressions against the final tree, and verify reports/status files match the final code. Any new code change invalidates the affected previous pass; repeat it.

7. EXPLICIT SELF-CHALLENGE QUESTIONS
- What concrete evidence proves the original problem existed?
- Why does each changed line/function need to exist?
- What alternative was considered and why was it rejected?
- Could a real production record or untrusted caller reach the test/mock path?
- What happens on failure, retry, concurrency, restart and stale response?
- What does this test prove, and what does it not prove?
- Did I preserve all previous working-tree files and frozen behavior?
- What changed between verification passes and why?
- Which claims remain unverified or depend on an environmental assumption?

8. REQUIRED RECORDS AND FINAL RESPONSE
Update only applicable canonical documents: phase tracker, master ledger, implementation status, defect register, relevant API/frontend/pipeline inventories, audit report and `docs/engineering/AI_DECISION_LOG.md`. Preserve old audit records and append corrections instead of rewriting history. Make status consistent everywhere.
Record work-item ID, before/after working-tree status, root cause, option comparison and rationale, files changed and purpose, relevant hashes if practical, each pass and test result, evidence tier (source/unit/mock/API/in-process/live worker/browser/full E2E), risks, limitations and next dependency.
Report statuses honestly: DELIVERED & VERIFIED, PARTIALLY VERIFIED, BLOCKED or REOPENED. Do not say full E2E without the real required components running together.

9. STOP / CONTINUE RULE
Do not start a different implementation item in parallel or expand this scope to unrelated fixes. Complete all three passes, update records and then continue automatically to the next unblocked item in the master execution queue without waiting for routine approval. Stop only for a real blocker, unresolved high-impact product choice, credential/account action, real publication, destructive action against actual data, or an environment change that requires owner authorization. If blocked, document exact evidence and work safely on independent unblocked work only if it does not depend on the blocker.
Never use `git reset`, `git clean`, blanket reverts, destructive DB resets, `docker compose down -v`, or broad file deletion. Do not reintroduce captions/subtitles; preserve transcription for internal scoring/semantic analysis; retain the frozen Shorts duration limit unless the owner explicitly changes it.
```


### Copy-ready prompt — ROADMAP-2.2: Cleanup preview endpoint

```text
You are the ClipForge engineering agent working in `D:\automation video clips\clipforge`.

WORK ITEM: ROADMAP-2.2 — Cleanup preview endpoint
STATE: Reconcile current repository state before acting. Do not assume this item is open just because it appears in the roadmap.

1. PROBLEM / OBJECTIVE
Provide a read-only preview of eligible removable artifacts with defensible reclaim estimates.

2. PREFLIGHT AND EVIDENCE COLLECTION
Read `AGENTS.md`, the applicable freeze/rule files, `docs/engineering/PHASE_TRACKER.md`, `MASTER_EXECUTION_LEDGER.md`, `IMPLEMENTATION_STATUS.md`, `ENGINEERING_DEFECT_REGISTER.md`, `PIPELINE_CATALOG_AND_DEPENDENCY_GRAPH.md`, `FRONTEND_PAGE_FEATURE_INVENTORY.md`, `PROJECT_CONTINUITY.md`, and the newest relevant audit/decision-log entries. Read only files relevant to this scope in depth, but reconcile any status claims before editing.
Inspect actual current source, schema, runtime route/client/task contracts, tests and caller/callee relationships. Reproduce the reported behavior with a safe isolated fixture where feasible. Separate VERIFIED FACTS, INFERENCES and UNKNOWNS. Record exact file paths, line ranges, commands and observed outputs.
Inspect `backend/cleanup_storage.py`, existing clip cleanup routes, artifact/reference models, active tasks/jobs, reservation markers, published status and quarantine journal. Determine whether the current Phase 1.3 preview fully satisfies this old roadmap item.
Capture `git status --short`, branch/commit, existing diff/untracked inventory and relevant environment/container identity before editing. Protect all pre-existing changes. Do not assume old hashes, route counts, schema revisions or historic reports still reflect the current environment.

3. COMPARE APPROACHES AND JUSTIFY THE CHOICE
Approach selection method: Compare at least two plausible approaches where meaningful: (A) smallest local repair, (B) reuse an established repository abstraction/pattern, and (C) architectural change only if the first two cannot meet verified requirements. Use evidence, not preference. Evaluate correctness, data safety, architectural consistency, backwards compatibility, idempotency/concurrency, performance, testability, reversibility, scope and maintenance cost. Record the chosen approach and specific reasons each alternative was rejected. If the problem is already solved in current source, choose the no-op verification path.
Before coding, write a small comparison table in the decision log: option; correctness against acceptance criteria; data/security risk; compatibility; concurrency/idempotency; complexity/maintenance; reversibility; evidence for/against. Do not create arbitrary numerical scores. Explain why the chosen approach is proportionate to the proven root cause and why each rejected alternative is inferior for this evidence.
If the current implementation already meets the requirement, choose verification-only and avoid a redundant change. If requirements remain ambiguous and a wrong choice would be consequential, stop at a documented blocker rather than invent behavior.

4. IMPLEMENTATION BOUNDARY
Implement only this work item. Prefer the smallest complete, maintainable fix using existing models, APIs, task lifecycle, storage/artifact and frontend patterns. Avoid duplicate frameworks, helpers, routes, state machines, database fields or tests when an existing abstraction meets the requirement.
Preserve all unrelated behavior and frozen components. Do not remove code based on apparent lack of callers without a call-site/dependency audit. Do not change public API semantics without documenting callers, compatibility plan and tests. Any migration must be justified, forward-only and data-preserving.
Scope-specific acceptance criteria:
- Preview must never delete, move, quarantine or write lifecycle state.
- Define eligibility and exclusion reasons from actual product rules; missing-media records should remain visible/preserved by default.
- Report bytes and paths through stable IDs/keys; never trust client paths.
- Ensure preview and execute candidates are token/identity-bound if existing contract uses signed preview.

5. REQUIRED TESTING
Add focused regression tests for the root cause and relevant negative, failure, boundary, retry, concurrency and stale-state paths. Assert durable database/filesystem/worker state as applicable, not only mocked return values. Use synthetic media, disposable test records and test provider mode. Never publish to real YouTube or destructive-clean real data.
- Repeated preview has no DB/filesystem change.
- Published, high-score, active, shared, reserved, missing and eligible fixtures classified accurately.
- Path traversal/symlink/out-of-root cases excluded.
- Reported reclaim estimate agrees with isolated fixture sizes.
Run the exact focused suite, relevant regressions, static checks and build/browser/integration tests required by the changed layers. Capture actual commands, counts, exit codes, warning/failure output and environment. Do not claim a test ran if only drafted or launched without a completed result.

6. THREE VERIFICATION PASSES — REQUIRED FOR THIS ITEM
PASS 1 — Implementation verification: review diff against every acceptance criterion; run focused tests and the affected workflow; prove expected state and failure behavior.
PASS 2 — Independent challenge: stop thinking like the implementation author. Re-read the requirement and original defect evidence. Try to falsify the fix with adversarial inputs, conflicts, retries, parallel requests, stale state and failure injection. Compare alternative approaches again. Inspect whether the tests could pass while production is still broken. Fix any issue discovered and record changes since Pass 1.
PASS 3 — Differential re-verification: re-read the final diff and working tree from scratch. Compare final code with Passes 1 and 2, identify all changes introduced after each earlier pass, rerun affected focused tests and relevant regressions against the final tree, and verify reports/status files match the final code. Any new code change invalidates the affected previous pass; repeat it.

7. EXPLICIT SELF-CHALLENGE QUESTIONS
- What concrete evidence proves the original problem existed?
- Why does each changed line/function need to exist?
- What alternative was considered and why was it rejected?
- Could a real production record or untrusted caller reach the test/mock path?
- What happens on failure, retry, concurrency, restart and stale response?
- What does this test prove, and what does it not prove?
- Did I preserve all previous working-tree files and frozen behavior?
- What changed between verification passes and why?
- Which claims remain unverified or depend on an environmental assumption?

8. REQUIRED RECORDS AND FINAL RESPONSE
Update only applicable canonical documents: phase tracker, master ledger, implementation status, defect register, relevant API/frontend/pipeline inventories, audit report and `docs/engineering/AI_DECISION_LOG.md`. Preserve old audit records and append corrections instead of rewriting history. Make status consistent everywhere.
Record work-item ID, before/after working-tree status, root cause, option comparison and rationale, files changed and purpose, relevant hashes if practical, each pass and test result, evidence tier (source/unit/mock/API/in-process/live worker/browser/full E2E), risks, limitations and next dependency.
Report statuses honestly: DELIVERED & VERIFIED, PARTIALLY VERIFIED, BLOCKED or REOPENED. Do not say full E2E without the real required components running together.

9. STOP / CONTINUE RULE
Do not start a different implementation item in parallel or expand this scope to unrelated fixes. Complete all three passes, update records and then continue automatically to the next unblocked item in the master execution queue without waiting for routine approval. Stop only for a real blocker, unresolved high-impact product choice, credential/account action, real publication, destructive action against actual data, or an environment change that requires owner authorization. If blocked, document exact evidence and work safely on independent unblocked work only if it does not depend on the blocker.
Never use `git reset`, `git clean`, blanket reverts, destructive DB resets, `docker compose down -v`, or broad file deletion. Do not reintroduce captions/subtitles; preserve transcription for internal scoring/semantic analysis; retain the frozen Shorts duration limit unless the owner explicitly changes it.
```


### Copy-ready prompt — ROADMAP-2.3: Cleanup execution endpoint

```text
You are the ClipForge engineering agent working in `D:\automation video clips\clipforge`.

WORK ITEM: ROADMAP-2.3 — Cleanup execution endpoint
STATE: Reconcile current repository state before acting. Do not assume this item is open just because it appears in the roadmap.

1. PROBLEM / OBJECTIVE
Safely execute only the eligible targets confirmed in a valid preview.

2. PREFLIGHT AND EVIDENCE COLLECTION
Read `AGENTS.md`, the applicable freeze/rule files, `docs/engineering/PHASE_TRACKER.md`, `MASTER_EXECUTION_LEDGER.md`, `IMPLEMENTATION_STATUS.md`, `ENGINEERING_DEFECT_REGISTER.md`, `PIPELINE_CATALOG_AND_DEPENDENCY_GRAPH.md`, `FRONTEND_PAGE_FEATURE_INVENTORY.md`, `PROJECT_CONTINUITY.md`, and the newest relevant audit/decision-log entries. Read only files relevant to this scope in depth, but reconcile any status claims before editing.
Inspect actual current source, schema, runtime route/client/task contracts, tests and caller/callee relationships. Reproduce the reported behavior with a safe isolated fixture where feasible. Separate VERIFIED FACTS, INFERENCES and UNKNOWNS. Record exact file paths, line ranges, commands and observed outputs.
Inspect signed preview/token validation, same-filesystem quarantine, durable journal/recovery, route order before static mounts, task/reservation writers and all eligible database refs.
Capture `git status --short`, branch/commit, existing diff/untracked inventory and relevant environment/container identity before editing. Protect all pre-existing changes. Do not assume old hashes, route counts, schema revisions or historic reports still reflect the current environment.

3. COMPARE APPROACHES AND JUSTIFY THE CHOICE
Approach selection method: Compare at least two plausible approaches where meaningful: (A) smallest local repair, (B) reuse an established repository abstraction/pattern, and (C) architectural change only if the first two cannot meet verified requirements. Use evidence, not preference. Evaluate correctness, data safety, architectural consistency, backwards compatibility, idempotency/concurrency, performance, testability, reversibility, scope and maintenance cost. Record the chosen approach and specific reasons each alternative was rejected. If the problem is already solved in current source, choose the no-op verification path.
Before coding, write a small comparison table in the decision log: option; correctness against acceptance criteria; data/security risk; compatibility; concurrency/idempotency; complexity/maintenance; reversibility; evidence for/against. Do not create arbitrary numerical scores. Explain why the chosen approach is proportionate to the proven root cause and why each rejected alternative is inferior for this evidence.
If the current implementation already meets the requirement, choose verification-only and avoid a redundant change. If requirements remain ambiguous and a wrong choice would be consequential, stop at a documented blocker rather than invent behavior.

4. IMPLEMENTATION BOUNDARY
Implement only this work item. Prefer the smallest complete, maintainable fix using existing models, APIs, task lifecycle, storage/artifact and frontend patterns. Avoid duplicate frameworks, helpers, routes, state machines, database fields or tests when an existing abstraction meets the requirement.
Preserve all unrelated behavior and frozen components. Do not remove code based on apparent lack of callers without a call-site/dependency audit. Do not change public API semantics without documenting callers, compatibility plan and tests. Any migration must be justified, forward-only and data-preserving.
Scope-specific acceptance criteria:
- Revalidate eligibility and exact target identity at execution time.
- Use the current safe quarantine/journal lifecycle; never replace cross-device atomic move with unsafe copy-delete fallback.
- Maintain recovery behavior and record per-item outcomes.
- Ensure no active writer/reservation or shared reference is deleted.
- Return truthful partial failure status.

5. REQUIRED TESTING
Add focused regression tests for the root cause and relevant negative, failure, boundary, retry, concurrency and stale-state paths. Assert durable database/filesystem/worker state as applicable, not only mocked return values. Use synthetic media, disposable test records and test provider mode. Never publish to real YouTube or destructive-clean real data.
- Isolated candidates; expired/tampered token; changed target; active writer; shared ref; missing file; permission error; crash at each journal step; startup reconciliation.
- Assert retained data remains untouched, reservations reconcile, and retry is idempotent.
- Use disposable/test storage only.
Run the exact focused suite, relevant regressions, static checks and build/browser/integration tests required by the changed layers. Capture actual commands, counts, exit codes, warning/failure output and environment. Do not claim a test ran if only drafted or launched without a completed result.

6. THREE VERIFICATION PASSES — REQUIRED FOR THIS ITEM
PASS 1 — Implementation verification: review diff against every acceptance criterion; run focused tests and the affected workflow; prove expected state and failure behavior.
PASS 2 — Independent challenge: stop thinking like the implementation author. Re-read the requirement and original defect evidence. Try to falsify the fix with adversarial inputs, conflicts, retries, parallel requests, stale state and failure injection. Compare alternative approaches again. Inspect whether the tests could pass while production is still broken. Fix any issue discovered and record changes since Pass 1.
PASS 3 — Differential re-verification: re-read the final diff and working tree from scratch. Compare final code with Passes 1 and 2, identify all changes introduced after each earlier pass, rerun affected focused tests and relevant regressions against the final tree, and verify reports/status files match the final code. Any new code change invalidates the affected previous pass; repeat it.

7. EXPLICIT SELF-CHALLENGE QUESTIONS
- What concrete evidence proves the original problem existed?
- Why does each changed line/function need to exist?
- What alternative was considered and why was it rejected?
- Could a real production record or untrusted caller reach the test/mock path?
- What happens on failure, retry, concurrency, restart and stale response?
- What does this test prove, and what does it not prove?
- Did I preserve all previous working-tree files and frozen behavior?
- What changed between verification passes and why?
- Which claims remain unverified or depend on an environmental assumption?

8. REQUIRED RECORDS AND FINAL RESPONSE
Update only applicable canonical documents: phase tracker, master ledger, implementation status, defect register, relevant API/frontend/pipeline inventories, audit report and `docs/engineering/AI_DECISION_LOG.md`. Preserve old audit records and append corrections instead of rewriting history. Make status consistent everywhere.
Record work-item ID, before/after working-tree status, root cause, option comparison and rationale, files changed and purpose, relevant hashes if practical, each pass and test result, evidence tier (source/unit/mock/API/in-process/live worker/browser/full E2E), risks, limitations and next dependency.
Report statuses honestly: DELIVERED & VERIFIED, PARTIALLY VERIFIED, BLOCKED or REOPENED. Do not say full E2E without the real required components running together.

9. STOP / CONTINUE RULE
Do not start a different implementation item in parallel or expand this scope to unrelated fixes. Complete all three passes, update records and then continue automatically to the next unblocked item in the master execution queue without waiting for routine approval. Stop only for a real blocker, unresolved high-impact product choice, credential/account action, real publication, destructive action against actual data, or an environment change that requires owner authorization. If blocked, document exact evidence and work safely on independent unblocked work only if it does not depend on the blocker.
Never use `git reset`, `git clean`, blanket reverts, destructive DB resets, `docker compose down -v`, or broad file deletion. Do not reintroduce captions/subtitles; preserve transcription for internal scoring/semantic analysis; retain the frozen Shorts duration limit unless the owner explicitly changes it.
```


### Copy-ready prompt — ROADMAP-2.4: Inventory and contract reconciliation

```text
You are the ClipForge engineering agent working in `D:\automation video clips\clipforge`.

WORK ITEM: ROADMAP-2.4 — Inventory and contract reconciliation
STATE: Reconcile current repository state before acting. Do not assume this item is open just because it appears in the roadmap.

1. PROBLEM / OBJECTIVE
Make route inventory, frontend action inventory and cleanup/RetentionHeatmap API contracts match runtime.

2. PREFLIGHT AND EVIDENCE COLLECTION
Read `AGENTS.md`, the applicable freeze/rule files, `docs/engineering/PHASE_TRACKER.md`, `MASTER_EXECUTION_LEDGER.md`, `IMPLEMENTATION_STATUS.md`, `ENGINEERING_DEFECT_REGISTER.md`, `PIPELINE_CATALOG_AND_DEPENDENCY_GRAPH.md`, `FRONTEND_PAGE_FEATURE_INVENTORY.md`, `PROJECT_CONTINUITY.md`, and the newest relevant audit/decision-log entries. Read only files relevant to this scope in depth, but reconcile any status claims before editing.
Inspect actual current source, schema, runtime route/client/task contracts, tests and caller/callee relationships. Reproduce the reported behavior with a safe isolated fixture where feasible. Separate VERIFIED FACTS, INFERENCES and UNKNOWNS. Record exact file paths, line ranges, commands and observed outputs.
Enumerate current routes using app reflection and inspect client functions and UI call sites. Include exact method/path, schemas, auth/trust boundary, side effects and task behavior.
Capture `git status --short`, branch/commit, existing diff/untracked inventory and relevant environment/container identity before editing. Protect all pre-existing changes. Do not assume old hashes, route counts, schema revisions or historic reports still reflect the current environment.

3. COMPARE APPROACHES AND JUSTIFY THE CHOICE
Approach selection method: Compare at least two plausible approaches where meaningful: (A) smallest local repair, (B) reuse an established repository abstraction/pattern, and (C) architectural change only if the first two cannot meet verified requirements. Use evidence, not preference. Evaluate correctness, data safety, architectural consistency, backwards compatibility, idempotency/concurrency, performance, testability, reversibility, scope and maintenance cost. Record the chosen approach and specific reasons each alternative was rejected. If the problem is already solved in current source, choose the no-op verification path.
Before coding, write a small comparison table in the decision log: option; correctness against acceptance criteria; data/security risk; compatibility; concurrency/idempotency; complexity/maintenance; reversibility; evidence for/against. Do not create arbitrary numerical scores. Explain why the chosen approach is proportionate to the proven root cause and why each rejected alternative is inferior for this evidence.
If the current implementation already meets the requirement, choose verification-only and avoid a redundant change. If requirements remain ambiguous and a wrong choice would be consequential, stop at a documented blocker rather than invent behavior.

4. IMPLEMENTATION BOUNDARY
Implement only this work item. Prefer the smallest complete, maintainable fix using existing models, APIs, task lifecycle, storage/artifact and frontend patterns. Avoid duplicate frameworks, helpers, routes, state machines, database fields or tests when an existing abstraction meets the requirement.
Preserve all unrelated behavior and frozen components. Do not remove code based on apparent lack of callers without a call-site/dependency audit. Do not change public API semantics without documenting callers, compatibility plan and tests. Any migration must be justified, forward-only and data-preserving.
Scope-specific acceptance criteria:
- Use one canonical route identity; distinguish route objects from method/path pairs.
- Document static route precedence and quarantine block route if still present.
- Update inventory only from actual source/runtime evidence.
- Keep historical audit snapshots unchanged; append correction/version.

5. REQUIRED TESTING
Add focused regression tests for the root cause and relevant negative, failure, boundary, retry, concurrency and stale-state paths. Assert durable database/filesystem/worker state as applicable, not only mocked return values. Use synthetic media, disposable test records and test provider mode. Never publish to real YouTube or destructive-clean real data.
- All client calls resolve to existing paths or are documented as intentionally local/external.
- No duplicated or orphan endpoints claimed active without evidence.
- Totals arithmetically reconcile.
- Independent reader rechecks counts.
Run the exact focused suite, relevant regressions, static checks and build/browser/integration tests required by the changed layers. Capture actual commands, counts, exit codes, warning/failure output and environment. Do not claim a test ran if only drafted or launched without a completed result.

6. THREE VERIFICATION PASSES — REQUIRED FOR THIS ITEM
PASS 1 — Implementation verification: review diff against every acceptance criterion; run focused tests and the affected workflow; prove expected state and failure behavior.
PASS 2 — Independent challenge: stop thinking like the implementation author. Re-read the requirement and original defect evidence. Try to falsify the fix with adversarial inputs, conflicts, retries, parallel requests, stale state and failure injection. Compare alternative approaches again. Inspect whether the tests could pass while production is still broken. Fix any issue discovered and record changes since Pass 1.
PASS 3 — Differential re-verification: re-read the final diff and working tree from scratch. Compare final code with Passes 1 and 2, identify all changes introduced after each earlier pass, rerun affected focused tests and relevant regressions against the final tree, and verify reports/status files match the final code. Any new code change invalidates the affected previous pass; repeat it.

7. EXPLICIT SELF-CHALLENGE QUESTIONS
- What concrete evidence proves the original problem existed?
- Why does each changed line/function need to exist?
- What alternative was considered and why was it rejected?
- Could a real production record or untrusted caller reach the test/mock path?
- What happens on failure, retry, concurrency, restart and stale response?
- What does this test prove, and what does it not prove?
- Did I preserve all previous working-tree files and frozen behavior?
- What changed between verification passes and why?
- Which claims remain unverified or depend on an environmental assumption?

8. REQUIRED RECORDS AND FINAL RESPONSE
Update only applicable canonical documents: phase tracker, master ledger, implementation status, defect register, relevant API/frontend/pipeline inventories, audit report and `docs/engineering/AI_DECISION_LOG.md`. Preserve old audit records and append corrections instead of rewriting history. Make status consistent everywhere.
Record work-item ID, before/after working-tree status, root cause, option comparison and rationale, files changed and purpose, relevant hashes if practical, each pass and test result, evidence tier (source/unit/mock/API/in-process/live worker/browser/full E2E), risks, limitations and next dependency.
Report statuses honestly: DELIVERED & VERIFIED, PARTIALLY VERIFIED, BLOCKED or REOPENED. Do not say full E2E without the real required components running together.

9. STOP / CONTINUE RULE
Do not start a different implementation item in parallel or expand this scope to unrelated fixes. Complete all three passes, update records and then continue automatically to the next unblocked item in the master execution queue without waiting for routine approval. Stop only for a real blocker, unresolved high-impact product choice, credential/account action, real publication, destructive action against actual data, or an environment change that requires owner authorization. If blocked, document exact evidence and work safely on independent unblocked work only if it does not depend on the blocker.
Never use `git reset`, `git clean`, blanket reverts, destructive DB resets, `docker compose down -v`, or broad file deletion. Do not reintroduce captions/subtitles; preserve transcription for internal scoring/semantic analysis; retain the frozen Shorts duration limit unless the owner explicitly changes it.
```


## Main phase prompt — ROADMAP Phase 3: Clips and AI enhancement workflows

```text
You are the ClipForge engineering agent. Coordinate Phase 3: Clips and AI enhancement workflows as a sequence of independently testable child work items, not a single broad implementation.

PROBLEM / OBJECTIVE
Verify Hook/B-roll/SFX as real end-to-end workflows; execute ROADMAP-3.1–3.4 one at a time.

DISCOVERY AND METHOD
Read the current project rules and phase ledger; establish whether each child is already delivered, unverified, blocked or open. Compare viable approaches for each child before implementation. Prefer the smallest evidence-backed fix that reuses current architecture. Record a qualitative comparison of correctness, data safety, compatibility, concurrency/idempotency, operational burden, reversibility and testability. Explain the chosen approach and why other options were rejected. Never rely on old phase numbers when they conflict with canonical records.

PHASE ACCEPTANCE CRITERIA
- Plans valid and explicit generation behavior clear.
- Real worker creates valid variants and artifact records.
- UI status agrees with DB and files after refresh.
- Production SFX fallback is trusted-test-only.

EXECUTION SEQUENCE
Execute the child subphases in the order shown in the index. For each child: inspect/reproduce; implement only that child; run Pass 1, Pass 2 and Pass 3 as defined in the companion rules; update `AI_DECISION_LOG.md` and canonical status; then move autonomously to the next unblocked child. Do not bundle unrelated children into one diff.

CROSS-VERIFICATION
Before phase close, independently check every child status against final source, test outputs and runtime evidence. Recheck frozen invariants, changed files and working-tree state. A completed build alone does not prove runtime behavior. A task ID/toast does not prove a worker finished.

BOUNDARIES
No caption/subtitle system. Do not rebuild existing UI wiring absent proven defect.
Preserve existing changes and untracked files. No real publishing. No caption/subtitle framework. Never use destructive Git operations or broad DB/storage deletion. High-impact irreversible actions against real user data require explicit owner authorization.

PHASE EXIT
Close this main phase only when all required children are either independently verified or explicitly documented as blocked with owner-relevant rationale. If blocked, do not mislabel the phase complete. Record the next unblocked dependency and continue autonomously when safe.
```


### Copy-ready prompt — ROADMAP-3.1: Hook generation and application

```text
You are the ClipForge engineering agent working in `D:\automation video clips\clipforge`.

WORK ITEM: ROADMAP-3.1 — Hook generation and application
STATE: Reconcile current repository state before acting. Do not assume this item is open just because it appears in the roadmap.

1. PROBLEM / OBJECTIVE
Generate, inspect and apply a valid Hook plan and correctly persist the final overlay variant.

2. PREFLIGHT AND EVIDENCE COLLECTION
Read `AGENTS.md`, the applicable freeze/rule files, `docs/engineering/PHASE_TRACKER.md`, `MASTER_EXECUTION_LEDGER.md`, `IMPLEMENTATION_STATUS.md`, `ENGINEERING_DEFECT_REGISTER.md`, `PIPELINE_CATALOG_AND_DEPENDENCY_GRAPH.md`, `FRONTEND_PAGE_FEATURE_INVENTORY.md`, `PROJECT_CONTINUITY.md`, and the newest relevant audit/decision-log entries. Read only files relevant to this scope in depth, but reconcile any status claims before editing.
Inspect actual current source, schema, runtime route/client/task contracts, tests and caller/callee relationships. Reproduce the reported behavior with a safe isolated fixture where feasible. Separate VERIFIED FACTS, INFERENCES and UNKNOWNS. Record exact file paths, line ranges, commands and observed outputs.
Inspect Hook plan endpoints and models, retention predictor payloads, `hook_tasks.py`, FFmpeg overlay path, UI controls and artifact manager.
Capture `git status --short`, branch/commit, existing diff/untracked inventory and relevant environment/container identity before editing. Protect all pre-existing changes. Do not assume old hashes, route counts, schema revisions or historic reports still reflect the current environment.

3. COMPARE APPROACHES AND JUSTIFY THE CHOICE
Approach selection method: Compare at least two plausible approaches where meaningful: (A) smallest local repair, (B) reuse an established repository abstraction/pattern, and (C) architectural change only if the first two cannot meet verified requirements. Use evidence, not preference. Evaluate correctness, data safety, architectural consistency, backwards compatibility, idempotency/concurrency, performance, testability, reversibility, scope and maintenance cost. Record the chosen approach and specific reasons each alternative was rejected. If the problem is already solved in current source, choose the no-op verification path.
Before coding, write a small comparison table in the decision log: option; correctness against acceptance criteria; data/security risk; compatibility; concurrency/idempotency; complexity/maintenance; reversibility; evidence for/against. Do not create arbitrary numerical scores. Explain why the chosen approach is proportionate to the proven root cause and why each rejected alternative is inferior for this evidence.
If the current implementation already meets the requirement, choose verification-only and avoid a redundant change. If requirements remain ambiguous and a wrong choice would be consequential, stop at a documented blocker rather than invent behavior.

4. IMPLEMENTATION BOUNDARY
Implement only this work item. Prefer the smallest complete, maintainable fix using existing models, APIs, task lifecycle, storage/artifact and frontend patterns. Avoid duplicate frameworks, helpers, routes, state machines, database fields or tests when an existing abstraction meets the requirement.
Preserve all unrelated behavior and frozen components. Do not remove code based on apparent lack of callers without a call-site/dependency audit. Do not change public API semantics without documenting callers, compatibility plan and tests. Any migration must be justified, forward-only and data-preserving.
Scope-specific acceptance criteria:
- Confirm valid Hook concepts, text length, style and timing constraints from existing schema.
- Handle the actual retained-analysis JSON format explicitly.
- Use correct async boundary and managed download/upload contexts.
- Persist plan/variant/artifacts only when their corresponding operation succeeds.

5. REQUIRED TESTING
Add focused regression tests for the root cause and relevant negative, failure, boundary, retry, concurrency and stale-state paths. Assert durable database/filesystem/worker state as applicable, not only mocked return values. Use synthetic media, disposable test records and test provider mode. Never publish to real YouTube or destructive-clean real data.
- Valid plan; missing/malformed retention; missing source; invalid selection; FFmpeg failure; successful variant; repeat/refresh; worker failure.
- Check final media is playable and records point to its actual object.
- Real worker required to claim full E2E.
Run the exact focused suite, relevant regressions, static checks and build/browser/integration tests required by the changed layers. Capture actual commands, counts, exit codes, warning/failure output and environment. Do not claim a test ran if only drafted or launched without a completed result.

6. THREE VERIFICATION PASSES — REQUIRED FOR THIS ITEM
PASS 1 — Implementation verification: review diff against every acceptance criterion; run focused tests and the affected workflow; prove expected state and failure behavior.
PASS 2 — Independent challenge: stop thinking like the implementation author. Re-read the requirement and original defect evidence. Try to falsify the fix with adversarial inputs, conflicts, retries, parallel requests, stale state and failure injection. Compare alternative approaches again. Inspect whether the tests could pass while production is still broken. Fix any issue discovered and record changes since Pass 1.
PASS 3 — Differential re-verification: re-read the final diff and working tree from scratch. Compare final code with Passes 1 and 2, identify all changes introduced after each earlier pass, rerun affected focused tests and relevant regressions against the final tree, and verify reports/status files match the final code. Any new code change invalidates the affected previous pass; repeat it.

7. EXPLICIT SELF-CHALLENGE QUESTIONS
- What concrete evidence proves the original problem existed?
- Why does each changed line/function need to exist?
- What alternative was considered and why was it rejected?
- Could a real production record or untrusted caller reach the test/mock path?
- What happens on failure, retry, concurrency, restart and stale response?
- What does this test prove, and what does it not prove?
- Did I preserve all previous working-tree files and frozen behavior?
- What changed between verification passes and why?
- Which claims remain unverified or depend on an environmental assumption?

8. REQUIRED RECORDS AND FINAL RESPONSE
Update only applicable canonical documents: phase tracker, master ledger, implementation status, defect register, relevant API/frontend/pipeline inventories, audit report and `docs/engineering/AI_DECISION_LOG.md`. Preserve old audit records and append corrections instead of rewriting history. Make status consistent everywhere.
Record work-item ID, before/after working-tree status, root cause, option comparison and rationale, files changed and purpose, relevant hashes if practical, each pass and test result, evidence tier (source/unit/mock/API/in-process/live worker/browser/full E2E), risks, limitations and next dependency.
Report statuses honestly: DELIVERED & VERIFIED, PARTIALLY VERIFIED, BLOCKED or REOPENED. Do not say full E2E without the real required components running together.

9. STOP / CONTINUE RULE
Do not start a different implementation item in parallel or expand this scope to unrelated fixes. Complete all three passes, update records and then continue automatically to the next unblocked item in the master execution queue without waiting for routine approval. Stop only for a real blocker, unresolved high-impact product choice, credential/account action, real publication, destructive action against actual data, or an environment change that requires owner authorization. If blocked, document exact evidence and work safely on independent unblocked work only if it does not depend on the blocker.
Never use `git reset`, `git clean`, blanket reverts, destructive DB resets, `docker compose down -v`, or broad file deletion. Do not reintroduce captions/subtitles; preserve transcription for internal scoring/semantic analysis; retain the frozen Shorts duration limit unless the owner explicitly changes it.
```


### Copy-ready prompt — ROADMAP-3.2: B-roll planning and application

```text
You are the ClipForge engineering agent working in `D:\automation video clips\clipforge`.

WORK ITEM: ROADMAP-3.2 — B-roll planning and application
STATE: Reconcile current repository state before acting. Do not assume this item is open just because it appears in the roadmap.

1. PROBLEM / OBJECTIVE
Plan and composite valid visual assets on the clip using existing layout/render infrastructure.

2. PREFLIGHT AND EVIDENCE COLLECTION
Read `AGENTS.md`, the applicable freeze/rule files, `docs/engineering/PHASE_TRACKER.md`, `MASTER_EXECUTION_LEDGER.md`, `IMPLEMENTATION_STATUS.md`, `ENGINEERING_DEFECT_REGISTER.md`, `PIPELINE_CATALOG_AND_DEPENDENCY_GRAPH.md`, `FRONTEND_PAGE_FEATURE_INVENTORY.md`, `PROJECT_CONTINUITY.md`, and the newest relevant audit/decision-log entries. Read only files relevant to this scope in depth, but reconcile any status claims before editing.
Inspect actual current source, schema, runtime route/client/task contracts, tests and caller/callee relationships. Reproduce the reported behavior with a safe isolated fixture where feasible. Separate VERIFIED FACTS, INFERENCES and UNKNOWNS. Record exact file paths, line ranges, commands and observed outputs.
Inspect existing planner, VisualAsset records/providers, placement schema/timeline, `apply_broll_task`, layout graph, storage contexts and frontend state.
Capture `git status --short`, branch/commit, existing diff/untracked inventory and relevant environment/container identity before editing. Protect all pre-existing changes. Do not assume old hashes, route counts, schema revisions or historic reports still reflect the current environment.

3. COMPARE APPROACHES AND JUSTIFY THE CHOICE
Approach selection method: Compare at least two plausible approaches where meaningful: (A) smallest local repair, (B) reuse an established repository abstraction/pattern, and (C) architectural change only if the first two cannot meet verified requirements. Use evidence, not preference. Evaluate correctness, data safety, architectural consistency, backwards compatibility, idempotency/concurrency, performance, testability, reversibility, scope and maintenance cost. Record the chosen approach and specific reasons each alternative was rejected. If the problem is already solved in current source, choose the no-op verification path.
Before coding, write a small comparison table in the decision log: option; correctness against acceptance criteria; data/security risk; compatibility; concurrency/idempotency; complexity/maintenance; reversibility; evidence for/against. Do not create arbitrary numerical scores. Explain why the chosen approach is proportionate to the proven root cause and why each rejected alternative is inferior for this evidence.
If the current implementation already meets the requirement, choose verification-only and avoid a redundant change. If requirements remain ambiguous and a wrong choice would be consequential, stop at a documented blocker rather than invent behavior.

4. IMPLEMENTATION BOUNDARY
Implement only this work item. Prefer the smallest complete, maintainable fix using existing models, APIs, task lifecycle, storage/artifact and frontend patterns. Avoid duplicate frameworks, helpers, routes, state machines, database fields or tests when an existing abstraction meets the requirement.
Preserve all unrelated behavior and frozen components. Do not remove code based on apparent lack of callers without a call-site/dependency audit. Do not change public API semantics without documenting callers, compatibility plan and tests. Any migration must be justified, forward-only and data-preserving.
Scope-specific acceptance criteria:
- Reuse existing render/layout engine; do not introduce a second compositor.
- Validate asset existence, timing, overlap, dimensions and display modes against schema.
- Preserve original audio policy and video duration/output requirements.
- Register variant/artifacts correctly, with real failure status.

5. REQUIRED TESTING
Add focused regression tests for the root cause and relevant negative, failure, boundary, retry, concurrency and stale-state paths. Assert durable database/filesystem/worker state as applicable, not only mocked return values. Use synthetic media, disposable test records and test provider mode. Never publish to real YouTube or destructive-clean real data.
- Full cutaway, PiP, no assets, bad asset, out-of-range placement, FFmpeg failure, output stream probe and refresh.
- Use synthetic visual fixtures and live worker for full verification.
Run the exact focused suite, relevant regressions, static checks and build/browser/integration tests required by the changed layers. Capture actual commands, counts, exit codes, warning/failure output and environment. Do not claim a test ran if only drafted or launched without a completed result.

6. THREE VERIFICATION PASSES — REQUIRED FOR THIS ITEM
PASS 1 — Implementation verification: review diff against every acceptance criterion; run focused tests and the affected workflow; prove expected state and failure behavior.
PASS 2 — Independent challenge: stop thinking like the implementation author. Re-read the requirement and original defect evidence. Try to falsify the fix with adversarial inputs, conflicts, retries, parallel requests, stale state and failure injection. Compare alternative approaches again. Inspect whether the tests could pass while production is still broken. Fix any issue discovered and record changes since Pass 1.
PASS 3 — Differential re-verification: re-read the final diff and working tree from scratch. Compare final code with Passes 1 and 2, identify all changes introduced after each earlier pass, rerun affected focused tests and relevant regressions against the final tree, and verify reports/status files match the final code. Any new code change invalidates the affected previous pass; repeat it.

7. EXPLICIT SELF-CHALLENGE QUESTIONS
- What concrete evidence proves the original problem existed?
- Why does each changed line/function need to exist?
- What alternative was considered and why was it rejected?
- Could a real production record or untrusted caller reach the test/mock path?
- What happens on failure, retry, concurrency, restart and stale response?
- What does this test prove, and what does it not prove?
- Did I preserve all previous working-tree files and frozen behavior?
- What changed between verification passes and why?
- Which claims remain unverified or depend on an environmental assumption?

8. REQUIRED RECORDS AND FINAL RESPONSE
Update only applicable canonical documents: phase tracker, master ledger, implementation status, defect register, relevant API/frontend/pipeline inventories, audit report and `docs/engineering/AI_DECISION_LOG.md`. Preserve old audit records and append corrections instead of rewriting history. Make status consistent everywhere.
Record work-item ID, before/after working-tree status, root cause, option comparison and rationale, files changed and purpose, relevant hashes if practical, each pass and test result, evidence tier (source/unit/mock/API/in-process/live worker/browser/full E2E), risks, limitations and next dependency.
Report statuses honestly: DELIVERED & VERIFIED, PARTIALLY VERIFIED, BLOCKED or REOPENED. Do not say full E2E without the real required components running together.

9. STOP / CONTINUE RULE
Do not start a different implementation item in parallel or expand this scope to unrelated fixes. Complete all three passes, update records and then continue automatically to the next unblocked item in the master execution queue without waiting for routine approval. Stop only for a real blocker, unresolved high-impact product choice, credential/account action, real publication, destructive action against actual data, or an environment change that requires owner authorization. If blocked, document exact evidence and work safely on independent unblocked work only if it does not depend on the blocker.
Never use `git reset`, `git clean`, blanket reverts, destructive DB resets, `docker compose down -v`, or broad file deletion. Do not reintroduce captions/subtitles; preserve transcription for internal scoring/semantic analysis; retain the frozen Shorts duration limit unless the owner explicitly changes it.
```


### Copy-ready prompt — ROADMAP-3.3: SFX planning and application

```text
You are the ClipForge engineering agent working in `D:\automation video clips\clipforge`.

WORK ITEM: ROADMAP-3.3 — SFX planning and application
STATE: Reconcile current repository state before acting. Do not assume this item is open just because it appears in the roadmap.

1. PROBLEM / OBJECTIVE
Create/apply a valid SFX plan while isolating test fallback and preserving sound and artifact integrity.

2. PREFLIGHT AND EVIDENCE COLLECTION
Read `AGENTS.md`, the applicable freeze/rule files, `docs/engineering/PHASE_TRACKER.md`, `MASTER_EXECUTION_LEDGER.md`, `IMPLEMENTATION_STATUS.md`, `ENGINEERING_DEFECT_REGISTER.md`, `PIPELINE_CATALOG_AND_DEPENDENCY_GRAPH.md`, `FRONTEND_PAGE_FEATURE_INVENTORY.md`, `PROJECT_CONTINUITY.md`, and the newest relevant audit/decision-log entries. Read only files relevant to this scope in depth, but reconcile any status claims before editing.
Inspect actual current source, schema, runtime route/client/task contracts, tests and caller/callee relationships. Reproduce the reported behavior with a safe isolated fixture where feasible. Separate VERIFIED FACTS, INFERENCES and UNKNOWNS. Record exact file paths, line ranges, commands and observed outputs.
Inspect current planner, SFXAsset library, plan GET/generate contract, SFX mixer, ducking/volume values, artifact records and task state.
Capture `git status --short`, branch/commit, existing diff/untracked inventory and relevant environment/container identity before editing. Protect all pre-existing changes. Do not assume old hashes, route counts, schema revisions or historic reports still reflect the current environment.

3. COMPARE APPROACHES AND JUSTIFY THE CHOICE
Approach selection method: Compare at least two plausible approaches where meaningful: (A) smallest local repair, (B) reuse an established repository abstraction/pattern, and (C) architectural change only if the first two cannot meet verified requirements. Use evidence, not preference. Evaluate correctness, data safety, architectural consistency, backwards compatibility, idempotency/concurrency, performance, testability, reversibility, scope and maintenance cost. Record the chosen approach and specific reasons each alternative was rejected. If the problem is already solved in current source, choose the no-op verification path.
Before coding, write a small comparison table in the decision log: option; correctness against acceptance criteria; data/security risk; compatibility; concurrency/idempotency; complexity/maintenance; reversibility; evidence for/against. Do not create arbitrary numerical scores. Explain why the chosen approach is proportionate to the proven root cause and why each rejected alternative is inferior for this evidence.
If the current implementation already meets the requirement, choose verification-only and avoid a redundant change. If requirements remain ambiguous and a wrong choice would be consequential, stop at a documented blocker rather than invent behavior.

4. IMPLEMENTATION BOUNDARY
Implement only this work item. Prefer the smallest complete, maintainable fix using existing models, APIs, task lifecycle, storage/artifact and frontend patterns. Avoid duplicate frameworks, helpers, routes, state machines, database fields or tests when an existing abstraction meets the requirement.
Preserve all unrelated behavior and frozen components. Do not remove code based on apparent lack of callers without a call-site/dependency audit. Do not change public API semantics without documenting callers, compatibility plan and tests. Any migration must be justified, forward-only and data-preserving.
Scope-specific acceptance criteria:
- GET must be read-only once its dedicated fix is delivered; generation explicit.
- No production placeholder tone generation from empty assets or untrusted identifiers.
- Validate timing/volume/ducking and preserve source audio according to existing contract.
- Use actual assets where available; safe empty/no-plan semantics when none exist in production.

5. REQUIRED TESTING
Add focused regression tests for the root cause and relevant negative, failure, boundary, retry, concurrency and stale-state paths. Assert durable database/filesystem/worker state as applicable, not only mocked return values. Use synthetic media, disposable test records and test provider mode. Never publish to real YouTube or destructive-clean real data.
- Trusted test fixture fallback; production empty library; valid production assets; invalid timeline; missing source; FFmpeg failure; repeated/concurrent plan generation.
- Check final stream audio, DB/physical artifact agreement and worker completion.
Run the exact focused suite, relevant regressions, static checks and build/browser/integration tests required by the changed layers. Capture actual commands, counts, exit codes, warning/failure output and environment. Do not claim a test ran if only drafted or launched without a completed result.

6. THREE VERIFICATION PASSES — REQUIRED FOR THIS ITEM
PASS 1 — Implementation verification: review diff against every acceptance criterion; run focused tests and the affected workflow; prove expected state and failure behavior.
PASS 2 — Independent challenge: stop thinking like the implementation author. Re-read the requirement and original defect evidence. Try to falsify the fix with adversarial inputs, conflicts, retries, parallel requests, stale state and failure injection. Compare alternative approaches again. Inspect whether the tests could pass while production is still broken. Fix any issue discovered and record changes since Pass 1.
PASS 3 — Differential re-verification: re-read the final diff and working tree from scratch. Compare final code with Passes 1 and 2, identify all changes introduced after each earlier pass, rerun affected focused tests and relevant regressions against the final tree, and verify reports/status files match the final code. Any new code change invalidates the affected previous pass; repeat it.

7. EXPLICIT SELF-CHALLENGE QUESTIONS
- What concrete evidence proves the original problem existed?
- Why does each changed line/function need to exist?
- What alternative was considered and why was it rejected?
- Could a real production record or untrusted caller reach the test/mock path?
- What happens on failure, retry, concurrency, restart and stale response?
- What does this test prove, and what does it not prove?
- Did I preserve all previous working-tree files and frozen behavior?
- What changed between verification passes and why?
- Which claims remain unverified or depend on an environmental assumption?

8. REQUIRED RECORDS AND FINAL RESPONSE
Update only applicable canonical documents: phase tracker, master ledger, implementation status, defect register, relevant API/frontend/pipeline inventories, audit report and `docs/engineering/AI_DECISION_LOG.md`. Preserve old audit records and append corrections instead of rewriting history. Make status consistent everywhere.
Record work-item ID, before/after working-tree status, root cause, option comparison and rationale, files changed and purpose, relevant hashes if practical, each pass and test result, evidence tier (source/unit/mock/API/in-process/live worker/browser/full E2E), risks, limitations and next dependency.
Report statuses honestly: DELIVERED & VERIFIED, PARTIALLY VERIFIED, BLOCKED or REOPENED. Do not say full E2E without the real required components running together.

9. STOP / CONTINUE RULE
Do not start a different implementation item in parallel or expand this scope to unrelated fixes. Complete all three passes, update records and then continue automatically to the next unblocked item in the master execution queue without waiting for routine approval. Stop only for a real blocker, unresolved high-impact product choice, credential/account action, real publication, destructive action against actual data, or an environment change that requires owner authorization. If blocked, document exact evidence and work safely on independent unblocked work only if it does not depend on the blocker.
Never use `git reset`, `git clean`, blanket reverts, destructive DB resets, `docker compose down -v`, or broad file deletion. Do not reintroduce captions/subtitles; preserve transcription for internal scoring/semantic analysis; retain the frozen Shorts duration limit unless the owner explicitly changes it.
```


### Copy-ready prompt — ROADMAP-3.4: Clips workflow consistency

```text
You are the ClipForge engineering agent working in `D:\automation video clips\clipforge`.

WORK ITEM: ROADMAP-3.4 — Clips workflow consistency
STATE: Reconcile current repository state before acting. Do not assume this item is open just because it appears in the roadmap.

1. PROBLEM / OBJECTIVE
Keep plan/variant/output metadata, preview UI and persisted task state consistent across refresh and failure.

2. PREFLIGHT AND EVIDENCE COLLECTION
Read `AGENTS.md`, the applicable freeze/rule files, `docs/engineering/PHASE_TRACKER.md`, `MASTER_EXECUTION_LEDGER.md`, `IMPLEMENTATION_STATUS.md`, `ENGINEERING_DEFECT_REGISTER.md`, `PIPELINE_CATALOG_AND_DEPENDENCY_GRAPH.md`, `FRONTEND_PAGE_FEATURE_INVENTORY.md`, `PROJECT_CONTINUITY.md`, and the newest relevant audit/decision-log entries. Read only files relevant to this scope in depth, but reconcile any status claims before editing.
Inspect actual current source, schema, runtime route/client/task contracts, tests and caller/callee relationships. Reproduce the reported behavior with a safe isolated fixture where feasible. Separate VERIFIED FACTS, INFERENCES and UNKNOWNS. Record exact file paths, line ranges, commands and observed outputs.
Trace Clip list, preview modal, variant retrieval, media URL resolution, task completion and state hydration after close/reopen and page refresh.
Capture `git status --short`, branch/commit, existing diff/untracked inventory and relevant environment/container identity before editing. Protect all pre-existing changes. Do not assume old hashes, route counts, schema revisions or historic reports still reflect the current environment.

3. COMPARE APPROACHES AND JUSTIFY THE CHOICE
Approach selection method: Compare at least two plausible approaches where meaningful: (A) smallest local repair, (B) reuse an established repository abstraction/pattern, and (C) architectural change only if the first two cannot meet verified requirements. Use evidence, not preference. Evaluate correctness, data safety, architectural consistency, backwards compatibility, idempotency/concurrency, performance, testability, reversibility, scope and maintenance cost. Record the chosen approach and specific reasons each alternative was rejected. If the problem is already solved in current source, choose the no-op verification path.
Before coding, write a small comparison table in the decision log: option; correctness against acceptance criteria; data/security risk; compatibility; concurrency/idempotency; complexity/maintenance; reversibility; evidence for/against. Do not create arbitrary numerical scores. Explain why the chosen approach is proportionate to the proven root cause and why each rejected alternative is inferior for this evidence.
If the current implementation already meets the requirement, choose verification-only and avoid a redundant change. If requirements remain ambiguous and a wrong choice would be consequential, stop at a documented blocker rather than invent behavior.

4. IMPLEMENTATION BOUNDARY
Implement only this work item. Prefer the smallest complete, maintainable fix using existing models, APIs, task lifecycle, storage/artifact and frontend patterns. Avoid duplicate frameworks, helpers, routes, state machines, database fields or tests when an existing abstraction meets the requirement.
Preserve all unrelated behavior and frozen components. Do not remove code based on apparent lack of callers without a call-site/dependency audit. Do not change public API semantics without documenting callers, compatibility plan and tests. Any migration must be justified, forward-only and data-preserving.
Scope-specific acceptance criteria:
- Show queued/running/completed/failed distinctly.
- Do not infer completion from HTTP 202/task ID/toast.
- Maintain media URLs after reload and preserve other selected items.
- Handle missing artifact record without destructive cleanup.

5. REQUIRED TESTING
Add focused regression tests for the root cause and relevant negative, failure, boundary, retry, concurrency and stale-state paths. Assert durable database/filesystem/worker state as applicable, not only mocked return values. Use synthetic media, disposable test records and test provider mode. Never publish to real YouTube or destructive-clean real data.
- Hook/B-roll/SFX success and failure; reload; close/reopen; stale task response; missing media; network failure.
- Verify DB, API and browser state in one test scenario where feasible.
Run the exact focused suite, relevant regressions, static checks and build/browser/integration tests required by the changed layers. Capture actual commands, counts, exit codes, warning/failure output and environment. Do not claim a test ran if only drafted or launched without a completed result.

6. THREE VERIFICATION PASSES — REQUIRED FOR THIS ITEM
PASS 1 — Implementation verification: review diff against every acceptance criterion; run focused tests and the affected workflow; prove expected state and failure behavior.
PASS 2 — Independent challenge: stop thinking like the implementation author. Re-read the requirement and original defect evidence. Try to falsify the fix with adversarial inputs, conflicts, retries, parallel requests, stale state and failure injection. Compare alternative approaches again. Inspect whether the tests could pass while production is still broken. Fix any issue discovered and record changes since Pass 1.
PASS 3 — Differential re-verification: re-read the final diff and working tree from scratch. Compare final code with Passes 1 and 2, identify all changes introduced after each earlier pass, rerun affected focused tests and relevant regressions against the final tree, and verify reports/status files match the final code. Any new code change invalidates the affected previous pass; repeat it.

7. EXPLICIT SELF-CHALLENGE QUESTIONS
- What concrete evidence proves the original problem existed?
- Why does each changed line/function need to exist?
- What alternative was considered and why was it rejected?
- Could a real production record or untrusted caller reach the test/mock path?
- What happens on failure, retry, concurrency, restart and stale response?
- What does this test prove, and what does it not prove?
- Did I preserve all previous working-tree files and frozen behavior?
- What changed between verification passes and why?
- Which claims remain unverified or depend on an environmental assumption?

8. REQUIRED RECORDS AND FINAL RESPONSE
Update only applicable canonical documents: phase tracker, master ledger, implementation status, defect register, relevant API/frontend/pipeline inventories, audit report and `docs/engineering/AI_DECISION_LOG.md`. Preserve old audit records and append corrections instead of rewriting history. Make status consistent everywhere.
Record work-item ID, before/after working-tree status, root cause, option comparison and rationale, files changed and purpose, relevant hashes if practical, each pass and test result, evidence tier (source/unit/mock/API/in-process/live worker/browser/full E2E), risks, limitations and next dependency.
Report statuses honestly: DELIVERED & VERIFIED, PARTIALLY VERIFIED, BLOCKED or REOPENED. Do not say full E2E without the real required components running together.

9. STOP / CONTINUE RULE
Do not start a different implementation item in parallel or expand this scope to unrelated fixes. Complete all three passes, update records and then continue automatically to the next unblocked item in the master execution queue without waiting for routine approval. Stop only for a real blocker, unresolved high-impact product choice, credential/account action, real publication, destructive action against actual data, or an environment change that requires owner authorization. If blocked, document exact evidence and work safely on independent unblocked work only if it does not depend on the blocker.
Never use `git reset`, `git clean`, blanket reverts, destructive DB resets, `docker compose down -v`, or broad file deletion. Do not reintroduce captions/subtitles; preserve transcription for internal scoring/semantic analysis; retain the frozen Shorts duration limit unless the owner explicitly changes it.
```


## Main phase prompt — ROADMAP Phase 4: Publishing management

```text
You are the ClipForge engineering agent. Coordinate Phase 4: Publishing management as a sequence of independently testable child work items, not a single broad implementation.

PROBLEM / OBJECTIVE
Harden cancel, retry, status polling and metadata editor. Execute 4.1–4.4 separately.

DISCOVERY AND METHOD
Read the current project rules and phase ledger; establish whether each child is already delivered, unverified, blocked or open. Compare viable approaches for each child before implementation. Prefer the smallest evidence-backed fix that reuses current architecture. Record a qualitative comparison of correctness, data safety, compatibility, concurrency/idempotency, operational burden, reversibility and testability. Explain the chosen approach and why other options were rejected. Never rely on old phase numbers when they conflict with canonical records.

PHASE ACCEPTANCE CRITERIA
- Terminal status/idempotency correct.
- No stale UI state or duplicate retry.
- Metadata contract maps to provider payload.
- All tests use mock publication.

EXECUTION SEQUENCE
Execute the child subphases in the order shown in the index. For each child: inspect/reproduce; implement only that child; run Pass 1, Pass 2 and Pass 3 as defined in the companion rules; update `AI_DECISION_LOG.md` and canonical status; then move autonomously to the next unblocked child. Do not bundle unrelated children into one diff.

CROSS-VERIFICATION
Before phase close, independently check every child status against final source, test outputs and runtime evidence. Recheck frozen invariants, changed files and working-tree state. A completed build alone does not prove runtime behavior. A task ID/toast does not prove a worker finished.

BOUNDARIES
Do not combine queue actions into a single broad patch.
Preserve existing changes and untracked files. No real publishing. No caption/subtitle framework. Never use destructive Git operations or broad DB/storage deletion. High-impact irreversible actions against real user data require explicit owner authorization.

PHASE EXIT
Close this main phase only when all required children are either independently verified or explicitly documented as blocked with owner-relevant rationale. If blocked, do not mislabel the phase complete. Record the next unblocked dependency and continue autonomously when safe.
```


### Copy-ready prompt — ROADMAP-4.1: Cancel publishing

```text
You are the ClipForge engineering agent working in `D:\automation video clips\clipforge`.

WORK ITEM: ROADMAP-4.1 — Cancel publishing
STATE: Reconcile current repository state before acting. Do not assume this item is open just because it appears in the roadmap.

1. PROBLEM / OBJECTIVE
Request and verify cancellation of the correct queued/running publish task.

2. PREFLIGHT AND EVIDENCE COLLECTION
Read `AGENTS.md`, the applicable freeze/rule files, `docs/engineering/PHASE_TRACKER.md`, `MASTER_EXECUTION_LEDGER.md`, `IMPLEMENTATION_STATUS.md`, `ENGINEERING_DEFECT_REGISTER.md`, `PIPELINE_CATALOG_AND_DEPENDENCY_GRAPH.md`, `FRONTEND_PAGE_FEATURE_INVENTORY.md`, `PROJECT_CONTINUITY.md`, and the newest relevant audit/decision-log entries. Read only files relevant to this scope in depth, but reconcile any status claims before editing.
Inspect actual current source, schema, runtime route/client/task contracts, tests and caller/callee relationships. Reproduce the reported behavior with a safe isolated fixture where feasible. Separate VERIFIED FACTS, INFERENCES and UNKNOWNS. Record exact file paths, line ranges, commands and observed outputs.
Inspect durable cancellation field/state, Celery task ID, subprocess/provider boundaries, cancellation endpoint and queue UI.
Capture `git status --short`, branch/commit, existing diff/untracked inventory and relevant environment/container identity before editing. Protect all pre-existing changes. Do not assume old hashes, route counts, schema revisions or historic reports still reflect the current environment.

3. COMPARE APPROACHES AND JUSTIFY THE CHOICE
Approach selection method: Compare at least two plausible approaches where meaningful: (A) smallest local repair, (B) reuse an established repository abstraction/pattern, and (C) architectural change only if the first two cannot meet verified requirements. Use evidence, not preference. Evaluate correctness, data safety, architectural consistency, backwards compatibility, idempotency/concurrency, performance, testability, reversibility, scope and maintenance cost. Record the chosen approach and specific reasons each alternative was rejected. If the problem is already solved in current source, choose the no-op verification path.
Before coding, write a small comparison table in the decision log: option; correctness against acceptance criteria; data/security risk; compatibility; concurrency/idempotency; complexity/maintenance; reversibility; evidence for/against. Do not create arbitrary numerical scores. Explain why the chosen approach is proportionate to the proven root cause and why each rejected alternative is inferior for this evidence.
If the current implementation already meets the requirement, choose verification-only and avoid a redundant change. If requirements remain ambiguous and a wrong choice would be consequential, stop at a documented blocker rather than invent behavior.

4. IMPLEMENTATION BOUNDARY
Implement only this work item. Prefer the smallest complete, maintainable fix using existing models, APIs, task lifecycle, storage/artifact and frontend patterns. Avoid duplicate frameworks, helpers, routes, state machines, database fields or tests when an existing abstraction meets the requirement.
Preserve all unrelated behavior and frozen components. Do not remove code based on apparent lack of callers without a call-site/dependency audit. Do not change public API semantics without documenting callers, compatibility plan and tests. Any migration must be justified, forward-only and data-preserving.
Scope-specific acceptance criteria:
- Persist cancellation intent before signalling worker.
- Idempotently handle repeat requests and already-terminal tasks.
- Do not mark cancelled before active writes/provider operation reach safe boundary.
- Prevent stale worker callbacks from replacing cancelled state.

5. REQUIRED TESTING
Add focused regression tests for the root cause and relevant negative, failure, boundary, retry, concurrency and stale-state paths. Assert durable database/filesystem/worker state as applicable, not only mocked return values. Use synthetic media, disposable test records and test provider mode. Never publish to real YouTube or destructive-clean real data.
- Queued, running, completed, failed, already-cancelled, repeated click, simultaneous cancel/complete, worker unavailable.
- Assert durable final status and honest UI state.
Run the exact focused suite, relevant regressions, static checks and build/browser/integration tests required by the changed layers. Capture actual commands, counts, exit codes, warning/failure output and environment. Do not claim a test ran if only drafted or launched without a completed result.

6. THREE VERIFICATION PASSES — REQUIRED FOR THIS ITEM
PASS 1 — Implementation verification: review diff against every acceptance criterion; run focused tests and the affected workflow; prove expected state and failure behavior.
PASS 2 — Independent challenge: stop thinking like the implementation author. Re-read the requirement and original defect evidence. Try to falsify the fix with adversarial inputs, conflicts, retries, parallel requests, stale state and failure injection. Compare alternative approaches again. Inspect whether the tests could pass while production is still broken. Fix any issue discovered and record changes since Pass 1.
PASS 3 — Differential re-verification: re-read the final diff and working tree from scratch. Compare final code with Passes 1 and 2, identify all changes introduced after each earlier pass, rerun affected focused tests and relevant regressions against the final tree, and verify reports/status files match the final code. Any new code change invalidates the affected previous pass; repeat it.

7. EXPLICIT SELF-CHALLENGE QUESTIONS
- What concrete evidence proves the original problem existed?
- Why does each changed line/function need to exist?
- What alternative was considered and why was it rejected?
- Could a real production record or untrusted caller reach the test/mock path?
- What happens on failure, retry, concurrency, restart and stale response?
- What does this test prove, and what does it not prove?
- Did I preserve all previous working-tree files and frozen behavior?
- What changed between verification passes and why?
- Which claims remain unverified or depend on an environmental assumption?

8. REQUIRED RECORDS AND FINAL RESPONSE
Update only applicable canonical documents: phase tracker, master ledger, implementation status, defect register, relevant API/frontend/pipeline inventories, audit report and `docs/engineering/AI_DECISION_LOG.md`. Preserve old audit records and append corrections instead of rewriting history. Make status consistent everywhere.
Record work-item ID, before/after working-tree status, root cause, option comparison and rationale, files changed and purpose, relevant hashes if practical, each pass and test result, evidence tier (source/unit/mock/API/in-process/live worker/browser/full E2E), risks, limitations and next dependency.
Report statuses honestly: DELIVERED & VERIFIED, PARTIALLY VERIFIED, BLOCKED or REOPENED. Do not say full E2E without the real required components running together.

9. STOP / CONTINUE RULE
Do not start a different implementation item in parallel or expand this scope to unrelated fixes. Complete all three passes, update records and then continue automatically to the next unblocked item in the master execution queue without waiting for routine approval. Stop only for a real blocker, unresolved high-impact product choice, credential/account action, real publication, destructive action against actual data, or an environment change that requires owner authorization. If blocked, document exact evidence and work safely on independent unblocked work only if it does not depend on the blocker.
Never use `git reset`, `git clean`, blanket reverts, destructive DB resets, `docker compose down -v`, or broad file deletion. Do not reintroduce captions/subtitles; preserve transcription for internal scoring/semantic analysis; retain the frozen Shorts duration limit unless the owner explicitly changes it.
```


### Copy-ready prompt — ROADMAP-4.2: Retry publishing

```text
You are the ClipForge engineering agent working in `D:\automation video clips\clipforge`.

WORK ITEM: ROADMAP-4.2 — Retry publishing
STATE: Reconcile current repository state before acting. Do not assume this item is open just because it appears in the roadmap.

1. PROBLEM / OBJECTIVE
Retry only eligible failed attempts without duplicate external side effects.

2. PREFLIGHT AND EVIDENCE COLLECTION
Read `AGENTS.md`, the applicable freeze/rule files, `docs/engineering/PHASE_TRACKER.md`, `MASTER_EXECUTION_LEDGER.md`, `IMPLEMENTATION_STATUS.md`, `ENGINEERING_DEFECT_REGISTER.md`, `PIPELINE_CATALOG_AND_DEPENDENCY_GRAPH.md`, `FRONTEND_PAGE_FEATURE_INVENTORY.md`, `PROJECT_CONTINUITY.md`, and the newest relevant audit/decision-log entries. Read only files relevant to this scope in depth, but reconcile any status claims before editing.
Inspect actual current source, schema, runtime route/client/task contracts, tests and caller/callee relationships. Reproduce the reported behavior with a safe isolated fixture where feasible. Separate VERIFIED FACTS, INFERENCES and UNKNOWNS. Record exact file paths, line ranges, commands and observed outputs.
Inspect retryable status rules, attempts/retry_count, destination/PublishTarget semantics, provider idempotency and error taxonomy.
Capture `git status --short`, branch/commit, existing diff/untracked inventory and relevant environment/container identity before editing. Protect all pre-existing changes. Do not assume old hashes, route counts, schema revisions or historic reports still reflect the current environment.

3. COMPARE APPROACHES AND JUSTIFY THE CHOICE
Approach selection method: Compare at least two plausible approaches where meaningful: (A) smallest local repair, (B) reuse an established repository abstraction/pattern, and (C) architectural change only if the first two cannot meet verified requirements. Use evidence, not preference. Evaluate correctness, data safety, architectural consistency, backwards compatibility, idempotency/concurrency, performance, testability, reversibility, scope and maintenance cost. Record the chosen approach and specific reasons each alternative was rejected. If the problem is already solved in current source, choose the no-op verification path.
Before coding, write a small comparison table in the decision log: option; correctness against acceptance criteria; data/security risk; compatibility; concurrency/idempotency; complexity/maintenance; reversibility; evidence for/against. Do not create arbitrary numerical scores. Explain why the chosen approach is proportionate to the proven root cause and why each rejected alternative is inferior for this evidence.
If the current implementation already meets the requirement, choose verification-only and avoid a redundant change. If requirements remain ambiguous and a wrong choice would be consequential, stop at a documented blocker rather than invent behavior.

4. IMPLEMENTATION BOUNDARY
Implement only this work item. Prefer the smallest complete, maintainable fix using existing models, APIs, task lifecycle, storage/artifact and frontend patterns. Avoid duplicate frameworks, helpers, routes, state machines, database fields or tests when an existing abstraction meets the requirement.
Preserve all unrelated behavior and frozen components. Do not remove code based on apparent lack of callers without a call-site/dependency audit. Do not change public API semantics without documenting callers, compatibility plan and tests. Any migration must be justified, forward-only and data-preserving.
Scope-specific acceptance criteria:
- Define transient vs permanent failures from current contract.
- Preserve prior attempt history and successful destination outcomes.
- Protect against concurrent double retry using established idempotency/claim patterns.
- Do not promise exactly-once provider semantics unless supported.

5. REQUIRED TESTING
Add focused regression tests for the root cause and relevant negative, failure, boundary, retry, concurrency and stale-state paths. Assert durable database/filesystem/worker state as applicable, not only mocked return values. Use synthetic media, disposable test records and test provider mode. Never publish to real YouTube or destructive-clean real data.
- Transient/permanent failure, repeated click, concurrent retry, partial destination success, cancelled/completed task, stale browser state.
- Mock provider asserts upload count and idempotency keys.
Run the exact focused suite, relevant regressions, static checks and build/browser/integration tests required by the changed layers. Capture actual commands, counts, exit codes, warning/failure output and environment. Do not claim a test ran if only drafted or launched without a completed result.

6. THREE VERIFICATION PASSES — REQUIRED FOR THIS ITEM
PASS 1 — Implementation verification: review diff against every acceptance criterion; run focused tests and the affected workflow; prove expected state and failure behavior.
PASS 2 — Independent challenge: stop thinking like the implementation author. Re-read the requirement and original defect evidence. Try to falsify the fix with adversarial inputs, conflicts, retries, parallel requests, stale state and failure injection. Compare alternative approaches again. Inspect whether the tests could pass while production is still broken. Fix any issue discovered and record changes since Pass 1.
PASS 3 — Differential re-verification: re-read the final diff and working tree from scratch. Compare final code with Passes 1 and 2, identify all changes introduced after each earlier pass, rerun affected focused tests and relevant regressions against the final tree, and verify reports/status files match the final code. Any new code change invalidates the affected previous pass; repeat it.

7. EXPLICIT SELF-CHALLENGE QUESTIONS
- What concrete evidence proves the original problem existed?
- Why does each changed line/function need to exist?
- What alternative was considered and why was it rejected?
- Could a real production record or untrusted caller reach the test/mock path?
- What happens on failure, retry, concurrency, restart and stale response?
- What does this test prove, and what does it not prove?
- Did I preserve all previous working-tree files and frozen behavior?
- What changed between verification passes and why?
- Which claims remain unverified or depend on an environmental assumption?

8. REQUIRED RECORDS AND FINAL RESPONSE
Update only applicable canonical documents: phase tracker, master ledger, implementation status, defect register, relevant API/frontend/pipeline inventories, audit report and `docs/engineering/AI_DECISION_LOG.md`. Preserve old audit records and append corrections instead of rewriting history. Make status consistent everywhere.
Record work-item ID, before/after working-tree status, root cause, option comparison and rationale, files changed and purpose, relevant hashes if practical, each pass and test result, evidence tier (source/unit/mock/API/in-process/live worker/browser/full E2E), risks, limitations and next dependency.
Report statuses honestly: DELIVERED & VERIFIED, PARTIALLY VERIFIED, BLOCKED or REOPENED. Do not say full E2E without the real required components running together.

9. STOP / CONTINUE RULE
Do not start a different implementation item in parallel or expand this scope to unrelated fixes. Complete all three passes, update records and then continue automatically to the next unblocked item in the master execution queue without waiting for routine approval. Stop only for a real blocker, unresolved high-impact product choice, credential/account action, real publication, destructive action against actual data, or an environment change that requires owner authorization. If blocked, document exact evidence and work safely on independent unblocked work only if it does not depend on the blocker.
Never use `git reset`, `git clean`, blanket reverts, destructive DB resets, `docker compose down -v`, or broad file deletion. Do not reintroduce captions/subtitles; preserve transcription for internal scoring/semantic analysis; retain the frozen Shorts duration limit unless the owner explicitly changes it.
```


### Copy-ready prompt — ROADMAP-4.3: Publish-status polling

```text
You are the ClipForge engineering agent working in `D:\automation video clips\clipforge`.

WORK ITEM: ROADMAP-4.3 — Publish-status polling
STATE: Reconcile current repository state before acting. Do not assume this item is open just because it appears in the roadmap.

1. PROBLEM / OBJECTIVE
Reflect authoritative status without stale overwrites or wasteful polling.

2. PREFLIGHT AND EVIDENCE COLLECTION
Read `AGENTS.md`, the applicable freeze/rule files, `docs/engineering/PHASE_TRACKER.md`, `MASTER_EXECUTION_LEDGER.md`, `IMPLEMENTATION_STATUS.md`, `ENGINEERING_DEFECT_REGISTER.md`, `PIPELINE_CATALOG_AND_DEPENDENCY_GRAPH.md`, `FRONTEND_PAGE_FEATURE_INVENTORY.md`, `PROJECT_CONTINUITY.md`, and the newest relevant audit/decision-log entries. Read only files relevant to this scope in depth, but reconcile any status claims before editing.
Inspect actual current source, schema, runtime route/client/task contracts, tests and caller/callee relationships. Reproduce the reported behavior with a safe isolated fixture where feasible. Separate VERIFIED FACTS, INFERENCES and UNKNOWNS. Record exact file paths, line ranges, commands and observed outputs.
Inspect poll/WebSocket API, frontend cache/state, timestamps/versioning and terminal status rules.
Capture `git status --short`, branch/commit, existing diff/untracked inventory and relevant environment/container identity before editing. Protect all pre-existing changes. Do not assume old hashes, route counts, schema revisions or historic reports still reflect the current environment.

3. COMPARE APPROACHES AND JUSTIFY THE CHOICE
Approach selection method: Compare at least two plausible approaches where meaningful: (A) smallest local repair, (B) reuse an established repository abstraction/pattern, and (C) architectural change only if the first two cannot meet verified requirements. Use evidence, not preference. Evaluate correctness, data safety, architectural consistency, backwards compatibility, idempotency/concurrency, performance, testability, reversibility, scope and maintenance cost. Record the chosen approach and specific reasons each alternative was rejected. If the problem is already solved in current source, choose the no-op verification path.
Before coding, write a small comparison table in the decision log: option; correctness against acceptance criteria; data/security risk; compatibility; concurrency/idempotency; complexity/maintenance; reversibility; evidence for/against. Do not create arbitrary numerical scores. Explain why the chosen approach is proportionate to the proven root cause and why each rejected alternative is inferior for this evidence.
If the current implementation already meets the requirement, choose verification-only and avoid a redundant change. If requirements remain ambiguous and a wrong choice would be consequential, stop at a documented blocker rather than invent behavior.

4. IMPLEMENTATION BOUNDARY
Implement only this work item. Prefer the smallest complete, maintainable fix using existing models, APIs, task lifecycle, storage/artifact and frontend patterns. Avoid duplicate frameworks, helpers, routes, state machines, database fields or tests when an existing abstraction meets the requirement.
Preserve all unrelated behavior and frozen components. Do not remove code based on apparent lack of callers without a call-site/dependency audit. Do not change public API semantics without documenting callers, compatibility plan and tests. Any migration must be justified, forward-only and data-preserving.
Scope-specific acceptance criteria:
- Use durable status as source of truth.
- Backoff/stop polling on terminal state and component unmount.
- Ignore stale/out-of-order responses.
- Reconnect safely and refresh state from backend.

5. REQUIRED TESTING
Add focused regression tests for the root cause and relevant negative, failure, boundary, retry, concurrency and stale-state paths. Assert durable database/filesystem/worker state as applicable, not only mocked return values. Use synthetic media, disposable test records and test provider mode. Never publish to real YouTube or destructive-clean real data.
- Out-of-order status results, transient outage, reconnect, stuck status, terminal state then stale progress, component navigation.
- Check network request rates and UI consistency.
Run the exact focused suite, relevant regressions, static checks and build/browser/integration tests required by the changed layers. Capture actual commands, counts, exit codes, warning/failure output and environment. Do not claim a test ran if only drafted or launched without a completed result.

6. THREE VERIFICATION PASSES — REQUIRED FOR THIS ITEM
PASS 1 — Implementation verification: review diff against every acceptance criterion; run focused tests and the affected workflow; prove expected state and failure behavior.
PASS 2 — Independent challenge: stop thinking like the implementation author. Re-read the requirement and original defect evidence. Try to falsify the fix with adversarial inputs, conflicts, retries, parallel requests, stale state and failure injection. Compare alternative approaches again. Inspect whether the tests could pass while production is still broken. Fix any issue discovered and record changes since Pass 1.
PASS 3 — Differential re-verification: re-read the final diff and working tree from scratch. Compare final code with Passes 1 and 2, identify all changes introduced after each earlier pass, rerun affected focused tests and relevant regressions against the final tree, and verify reports/status files match the final code. Any new code change invalidates the affected previous pass; repeat it.

7. EXPLICIT SELF-CHALLENGE QUESTIONS
- What concrete evidence proves the original problem existed?
- Why does each changed line/function need to exist?
- What alternative was considered and why was it rejected?
- Could a real production record or untrusted caller reach the test/mock path?
- What happens on failure, retry, concurrency, restart and stale response?
- What does this test prove, and what does it not prove?
- Did I preserve all previous working-tree files and frozen behavior?
- What changed between verification passes and why?
- Which claims remain unverified or depend on an environmental assumption?

8. REQUIRED RECORDS AND FINAL RESPONSE
Update only applicable canonical documents: phase tracker, master ledger, implementation status, defect register, relevant API/frontend/pipeline inventories, audit report and `docs/engineering/AI_DECISION_LOG.md`. Preserve old audit records and append corrections instead of rewriting history. Make status consistent everywhere.
Record work-item ID, before/after working-tree status, root cause, option comparison and rationale, files changed and purpose, relevant hashes if practical, each pass and test result, evidence tier (source/unit/mock/API/in-process/live worker/browser/full E2E), risks, limitations and next dependency.
Report statuses honestly: DELIVERED & VERIFIED, PARTIALLY VERIFIED, BLOCKED or REOPENED. Do not say full E2E without the real required components running together.

9. STOP / CONTINUE RULE
Do not start a different implementation item in parallel or expand this scope to unrelated fixes. Complete all three passes, update records and then continue automatically to the next unblocked item in the master execution queue without waiting for routine approval. Stop only for a real blocker, unresolved high-impact product choice, credential/account action, real publication, destructive action against actual data, or an environment change that requires owner authorization. If blocked, document exact evidence and work safely on independent unblocked work only if it does not depend on the blocker.
Never use `git reset`, `git clean`, blanket reverts, destructive DB resets, `docker compose down -v`, or broad file deletion. Do not reintroduce captions/subtitles; preserve transcription for internal scoring/semantic analysis; retain the frozen Shorts duration limit unless the owner explicitly changes it.
```


### Copy-ready prompt — ROADMAP-4.4: Metadata editor integration

```text
You are the ClipForge engineering agent working in `D:\automation video clips\clipforge`.

WORK ITEM: ROADMAP-4.4 — Metadata editor integration
STATE: Reconcile current repository state before acting. Do not assume this item is open just because it appears in the roadmap.

1. PROBLEM / OBJECTIVE
Load/save supported publishing metadata through actual backend contract.

2. PREFLIGHT AND EVIDENCE COLLECTION
Read `AGENTS.md`, the applicable freeze/rule files, `docs/engineering/PHASE_TRACKER.md`, `MASTER_EXECUTION_LEDGER.md`, `IMPLEMENTATION_STATUS.md`, `ENGINEERING_DEFECT_REGISTER.md`, `PIPELINE_CATALOG_AND_DEPENDENCY_GRAPH.md`, `FRONTEND_PAGE_FEATURE_INVENTORY.md`, `PROJECT_CONTINUITY.md`, and the newest relevant audit/decision-log entries. Read only files relevant to this scope in depth, but reconcile any status claims before editing.
Inspect actual current source, schema, runtime route/client/task contracts, tests and caller/callee relationships. Reproduce the reported behavior with a safe isolated fixture where feasible. Separate VERIFIED FACTS, INFERENCES and UNKNOWNS. Record exact file paths, line ranges, commands and observed outputs.
Inspect editor components, schema, validation, content vs destination-level fields and publisher payload.
Capture `git status --short`, branch/commit, existing diff/untracked inventory and relevant environment/container identity before editing. Protect all pre-existing changes. Do not assume old hashes, route counts, schema revisions or historic reports still reflect the current environment.

3. COMPARE APPROACHES AND JUSTIFY THE CHOICE
Approach selection method: Compare at least two plausible approaches where meaningful: (A) smallest local repair, (B) reuse an established repository abstraction/pattern, and (C) architectural change only if the first two cannot meet verified requirements. Use evidence, not preference. Evaluate correctness, data safety, architectural consistency, backwards compatibility, idempotency/concurrency, performance, testability, reversibility, scope and maintenance cost. Record the chosen approach and specific reasons each alternative was rejected. If the problem is already solved in current source, choose the no-op verification path.
Before coding, write a small comparison table in the decision log: option; correctness against acceptance criteria; data/security risk; compatibility; concurrency/idempotency; complexity/maintenance; reversibility; evidence for/against. Do not create arbitrary numerical scores. Explain why the chosen approach is proportionate to the proven root cause and why each rejected alternative is inferior for this evidence.
If the current implementation already meets the requirement, choose verification-only and avoid a redundant change. If requirements remain ambiguous and a wrong choice would be consequential, stop at a documented blocker rather than invent behavior.

4. IMPLEMENTATION BOUNDARY
Implement only this work item. Prefer the smallest complete, maintainable fix using existing models, APIs, task lifecycle, storage/artifact and frontend patterns. Avoid duplicate frameworks, helpers, routes, state machines, database fields or tests when an existing abstraction meets the requirement.
Preserve all unrelated behavior and frozen components. Do not remove code based on apparent lack of callers without a call-site/dependency audit. Do not change public API semantics without documenting callers, compatibility plan and tests. Any migration must be justified, forward-only and data-preserving.
Scope-specific acceptance criteria:
- Only supported fields are editable; show unknown/unsupported behavior explicitly.
- Validate at UI and server; preserve omitted fields in partial updates.
- Update UI only after persistence succeeds.
- Keep account/destination scoping correct.

5. REQUIRED TESTING
Add focused regression tests for the root cause and relevant negative, failure, boundary, retry, concurrency and stale-state paths. Assert durable database/filesystem/worker state as applicable, not only mocked return values. Use synthetic media, disposable test records and test provider mode. Never publish to real YouTube or destructive-clean real data.
- Load/save/reload, invalid length/value, partial patch, provider rejection, concurrent edits, missing destination.
- Assert actual mock publish payload reflects saved values.
Run the exact focused suite, relevant regressions, static checks and build/browser/integration tests required by the changed layers. Capture actual commands, counts, exit codes, warning/failure output and environment. Do not claim a test ran if only drafted or launched without a completed result.

6. THREE VERIFICATION PASSES — REQUIRED FOR THIS ITEM
PASS 1 — Implementation verification: review diff against every acceptance criterion; run focused tests and the affected workflow; prove expected state and failure behavior.
PASS 2 — Independent challenge: stop thinking like the implementation author. Re-read the requirement and original defect evidence. Try to falsify the fix with adversarial inputs, conflicts, retries, parallel requests, stale state and failure injection. Compare alternative approaches again. Inspect whether the tests could pass while production is still broken. Fix any issue discovered and record changes since Pass 1.
PASS 3 — Differential re-verification: re-read the final diff and working tree from scratch. Compare final code with Passes 1 and 2, identify all changes introduced after each earlier pass, rerun affected focused tests and relevant regressions against the final tree, and verify reports/status files match the final code. Any new code change invalidates the affected previous pass; repeat it.

7. EXPLICIT SELF-CHALLENGE QUESTIONS
- What concrete evidence proves the original problem existed?
- Why does each changed line/function need to exist?
- What alternative was considered and why was it rejected?
- Could a real production record or untrusted caller reach the test/mock path?
- What happens on failure, retry, concurrency, restart and stale response?
- What does this test prove, and what does it not prove?
- Did I preserve all previous working-tree files and frozen behavior?
- What changed between verification passes and why?
- Which claims remain unverified or depend on an environmental assumption?

8. REQUIRED RECORDS AND FINAL RESPONSE
Update only applicable canonical documents: phase tracker, master ledger, implementation status, defect register, relevant API/frontend/pipeline inventories, audit report and `docs/engineering/AI_DECISION_LOG.md`. Preserve old audit records and append corrections instead of rewriting history. Make status consistent everywhere.
Record work-item ID, before/after working-tree status, root cause, option comparison and rationale, files changed and purpose, relevant hashes if practical, each pass and test result, evidence tier (source/unit/mock/API/in-process/live worker/browser/full E2E), risks, limitations and next dependency.
Report statuses honestly: DELIVERED & VERIFIED, PARTIALLY VERIFIED, BLOCKED or REOPENED. Do not say full E2E without the real required components running together.

9. STOP / CONTINUE RULE
Do not start a different implementation item in parallel or expand this scope to unrelated fixes. Complete all three passes, update records and then continue automatically to the next unblocked item in the master execution queue without waiting for routine approval. Stop only for a real blocker, unresolved high-impact product choice, credential/account action, real publication, destructive action against actual data, or an environment change that requires owner authorization. If blocked, document exact evidence and work safely on independent unblocked work only if it does not depend on the blocker.
Never use `git reset`, `git clean`, blanket reverts, destructive DB resets, `docker compose down -v`, or broad file deletion. Do not reintroduce captions/subtitles; preserve transcription for internal scoring/semantic analysis; retain the frozen Shorts duration limit unless the owner explicitly changes it.
```


## Main phase prompt — ROADMAP Phase 5: Analytics and optimization

```text
You are the ClipForge engineering agent. Coordinate Phase 5: Analytics and optimization as a sequence of independently testable child work items, not a single broad implementation.

PROBLEM / OBJECTIVE
Expose real per-video metrics, SEO diagnostics, tracking queue and optimization lifecycle. Execute 5.1–5.4 separately.

DISCOVERY AND METHOD
Read the current project rules and phase ledger; establish whether each child is already delivered, unverified, blocked or open. Compare viable approaches for each child before implementation. Prefer the smallest evidence-backed fix that reuses current architecture. Record a qualitative comparison of correctness, data safety, compatibility, concurrency/idempotency, operational burden, reversibility and testability. Explain the chosen approach and why other options were rejected. Never rely on old phase numbers when they conflict with canonical records.

PHASE ACCEPTANCE CRITERIA
- Metric semantics supported and scoped.
- No invented metrics or decorative controls.
- Tracking/optimization tasks have durable lifecycle.
- Actual backend effects match labels.

EXECUTION SEQUENCE
Execute the child subphases in the order shown in the index. For each child: inspect/reproduce; implement only that child; run Pass 1, Pass 2 and Pass 3 as defined in the companion rules; update `AI_DECISION_LOG.md` and canonical status; then move autonomously to the next unblocked child. Do not bundle unrelated children into one diff.

CROSS-VERIFICATION
Before phase close, independently check every child status against final source, test outputs and runtime evidence. Recheck frozen invariants, changed files and working-tree state. A completed build alone does not prove runtime behavior. A task ID/toast does not prove a worker finished.

BOUNDARIES
Do not expose prototype routes as production functionality without verifying behavior.
Preserve existing changes and untracked files. No real publishing. No caption/subtitle framework. Never use destructive Git operations or broad DB/storage deletion. High-impact irreversible actions against real user data require explicit owner authorization.

PHASE EXIT
Close this main phase only when all required children are either independently verified or explicitly documented as blocked with owner-relevant rationale. If blocked, do not mislabel the phase complete. Record the next unblocked dependency and continue autonomously when safe.
```


### Copy-ready prompt — ROADMAP-5.1: Per-video performance details

```text
You are the ClipForge engineering agent working in `D:\automation video clips\clipforge`.

WORK ITEM: ROADMAP-5.1 — Per-video performance details
STATE: Reconcile current repository state before acting. Do not assume this item is open just because it appears in the roadmap.

1. PROBLEM / OBJECTIVE
Show correctly scoped performance metrics for the selected video and time period.

2. PREFLIGHT AND EVIDENCE COLLECTION
Read `AGENTS.md`, the applicable freeze/rule files, `docs/engineering/PHASE_TRACKER.md`, `MASTER_EXECUTION_LEDGER.md`, `IMPLEMENTATION_STATUS.md`, `ENGINEERING_DEFECT_REGISTER.md`, `PIPELINE_CATALOG_AND_DEPENDENCY_GRAPH.md`, `FRONTEND_PAGE_FEATURE_INVENTORY.md`, `PROJECT_CONTINUITY.md`, and the newest relevant audit/decision-log entries. Read only files relevant to this scope in depth, but reconcile any status claims before editing.
Inspect actual current source, schema, runtime route/client/task contracts, tests and caller/callee relationships. Reproduce the reported behavior with a safe isolated fixture where feasible. Separate VERIFIED FACTS, INFERENCES and UNKNOWNS. Record exact file paths, line ranges, commands and observed outputs.
Inspect analytics endpoint/provider, metric definitions, channel and video identity, pagination/timezone and stale-data behavior.
Capture `git status --short`, branch/commit, existing diff/untracked inventory and relevant environment/container identity before editing. Protect all pre-existing changes. Do not assume old hashes, route counts, schema revisions or historic reports still reflect the current environment.

3. COMPARE APPROACHES AND JUSTIFY THE CHOICE
Approach selection method: Compare at least two plausible approaches where meaningful: (A) smallest local repair, (B) reuse an established repository abstraction/pattern, and (C) architectural change only if the first two cannot meet verified requirements. Use evidence, not preference. Evaluate correctness, data safety, architectural consistency, backwards compatibility, idempotency/concurrency, performance, testability, reversibility, scope and maintenance cost. Record the chosen approach and specific reasons each alternative was rejected. If the problem is already solved in current source, choose the no-op verification path.
Before coding, write a small comparison table in the decision log: option; correctness against acceptance criteria; data/security risk; compatibility; concurrency/idempotency; complexity/maintenance; reversibility; evidence for/against. Do not create arbitrary numerical scores. Explain why the chosen approach is proportionate to the proven root cause and why each rejected alternative is inferior for this evidence.
If the current implementation already meets the requirement, choose verification-only and avoid a redundant change. If requirements remain ambiguous and a wrong choice would be consequential, stop at a documented blocker rather than invent behavior.

4. IMPLEMENTATION BOUNDARY
Implement only this work item. Prefer the smallest complete, maintainable fix using existing models, APIs, task lifecycle, storage/artifact and frontend patterns. Avoid duplicate frameworks, helpers, routes, state machines, database fields or tests when an existing abstraction meets the requirement.
Preserve all unrelated behavior and frozen components. Do not remove code based on apparent lack of callers without a call-site/dependency audit. Do not change public API semantics without documenting callers, compatibility plan and tests. Any migration must be justified, forward-only and data-preserving.
Scope-specific acceptance criteria:
- Document exact metric meaning and period.
- Prevent cross-channel data mixing.
- Differentiate missing/partial vs zero.
- Do not label a scanned window as lifetime total.

5. REQUIRED TESTING
Add focused regression tests for the root cause and relevant negative, failure, boundary, retry, concurrency and stale-state paths. Assert durable database/filesystem/worker state as applicable, not only mocked return values. Use synthetic media, disposable test records and test provider mode. Never publish to real YouTube or destructive-clean real data.
- Known fixture, unknown/missing stats, paginated results, provider limit, timezone/date boundary, wrong ID.
- Compare raw response, normalization and UI value.
Run the exact focused suite, relevant regressions, static checks and build/browser/integration tests required by the changed layers. Capture actual commands, counts, exit codes, warning/failure output and environment. Do not claim a test ran if only drafted or launched without a completed result.

6. THREE VERIFICATION PASSES — REQUIRED FOR THIS ITEM
PASS 1 — Implementation verification: review diff against every acceptance criterion; run focused tests and the affected workflow; prove expected state and failure behavior.
PASS 2 — Independent challenge: stop thinking like the implementation author. Re-read the requirement and original defect evidence. Try to falsify the fix with adversarial inputs, conflicts, retries, parallel requests, stale state and failure injection. Compare alternative approaches again. Inspect whether the tests could pass while production is still broken. Fix any issue discovered and record changes since Pass 1.
PASS 3 — Differential re-verification: re-read the final diff and working tree from scratch. Compare final code with Passes 1 and 2, identify all changes introduced after each earlier pass, rerun affected focused tests and relevant regressions against the final tree, and verify reports/status files match the final code. Any new code change invalidates the affected previous pass; repeat it.

7. EXPLICIT SELF-CHALLENGE QUESTIONS
- What concrete evidence proves the original problem existed?
- Why does each changed line/function need to exist?
- What alternative was considered and why was it rejected?
- Could a real production record or untrusted caller reach the test/mock path?
- What happens on failure, retry, concurrency, restart and stale response?
- What does this test prove, and what does it not prove?
- Did I preserve all previous working-tree files and frozen behavior?
- What changed between verification passes and why?
- Which claims remain unverified or depend on an environmental assumption?

8. REQUIRED RECORDS AND FINAL RESPONSE
Update only applicable canonical documents: phase tracker, master ledger, implementation status, defect register, relevant API/frontend/pipeline inventories, audit report and `docs/engineering/AI_DECISION_LOG.md`. Preserve old audit records and append corrections instead of rewriting history. Make status consistent everywhere.
Record work-item ID, before/after working-tree status, root cause, option comparison and rationale, files changed and purpose, relevant hashes if practical, each pass and test result, evidence tier (source/unit/mock/API/in-process/live worker/browser/full E2E), risks, limitations and next dependency.
Report statuses honestly: DELIVERED & VERIFIED, PARTIALLY VERIFIED, BLOCKED or REOPENED. Do not say full E2E without the real required components running together.

9. STOP / CONTINUE RULE
Do not start a different implementation item in parallel or expand this scope to unrelated fixes. Complete all three passes, update records and then continue automatically to the next unblocked item in the master execution queue without waiting for routine approval. Stop only for a real blocker, unresolved high-impact product choice, credential/account action, real publication, destructive action against actual data, or an environment change that requires owner authorization. If blocked, document exact evidence and work safely on independent unblocked work only if it does not depend on the blocker.
Never use `git reset`, `git clean`, blanket reverts, destructive DB resets, `docker compose down -v`, or broad file deletion. Do not reintroduce captions/subtitles; preserve transcription for internal scoring/semantic analysis; retain the frozen Shorts duration limit unless the owner explicitly changes it.
```


### Copy-ready prompt — ROADMAP-5.2: SEO diagnostics

```text
You are the ClipForge engineering agent working in `D:\automation video clips\clipforge`.

WORK ITEM: ROADMAP-5.2 — SEO diagnostics
STATE: Reconcile current repository state before acting. Do not assume this item is open just because it appears in the roadmap.

1. PROBLEM / OBJECTIVE
Wire diagnostics to an actual supported endpoint and show recommendations honestly.

2. PREFLIGHT AND EVIDENCE COLLECTION
Read `AGENTS.md`, the applicable freeze/rule files, `docs/engineering/PHASE_TRACKER.md`, `MASTER_EXECUTION_LEDGER.md`, `IMPLEMENTATION_STATUS.md`, `ENGINEERING_DEFECT_REGISTER.md`, `PIPELINE_CATALOG_AND_DEPENDENCY_GRAPH.md`, `FRONTEND_PAGE_FEATURE_INVENTORY.md`, `PROJECT_CONTINUITY.md`, and the newest relevant audit/decision-log entries. Read only files relevant to this scope in depth, but reconcile any status claims before editing.
Inspect actual current source, schema, runtime route/client/task contracts, tests and caller/callee relationships. Reproduce the reported behavior with a safe isolated fixture where feasible. Separate VERIFIED FACTS, INFERENCES and UNKNOWNS. Record exact file paths, line ranges, commands and observed outputs.
Inspect API, scoring/analysis model, input contract, response schema and existing SEO UI.
Capture `git status --short`, branch/commit, existing diff/untracked inventory and relevant environment/container identity before editing. Protect all pre-existing changes. Do not assume old hashes, route counts, schema revisions or historic reports still reflect the current environment.

3. COMPARE APPROACHES AND JUSTIFY THE CHOICE
Approach selection method: Compare at least two plausible approaches where meaningful: (A) smallest local repair, (B) reuse an established repository abstraction/pattern, and (C) architectural change only if the first two cannot meet verified requirements. Use evidence, not preference. Evaluate correctness, data safety, architectural consistency, backwards compatibility, idempotency/concurrency, performance, testability, reversibility, scope and maintenance cost. Record the chosen approach and specific reasons each alternative was rejected. If the problem is already solved in current source, choose the no-op verification path.
Before coding, write a small comparison table in the decision log: option; correctness against acceptance criteria; data/security risk; compatibility; concurrency/idempotency; complexity/maintenance; reversibility; evidence for/against. Do not create arbitrary numerical scores. Explain why the chosen approach is proportionate to the proven root cause and why each rejected alternative is inferior for this evidence.
If the current implementation already meets the requirement, choose verification-only and avoid a redundant change. If requirements remain ambiguous and a wrong choice would be consequential, stop at a documented blocker rather than invent behavior.

4. IMPLEMENTATION BOUNDARY
Implement only this work item. Prefer the smallest complete, maintainable fix using existing models, APIs, task lifecycle, storage/artifact and frontend patterns. Avoid duplicate frameworks, helpers, routes, state machines, database fields or tests when an existing abstraction meets the requirement.
Preserve all unrelated behavior and frozen components. Do not remove code based on apparent lack of callers without a call-site/dependency audit. Do not change public API semantics without documenting callers, compatibility plan and tests. Any migration must be justified, forward-only and data-preserving.
Scope-specific acceptance criteria:
- Validate text limits and required inputs.
- Show actual diagnostic output; distinguish suggestion from applied metadata.
- Handle rate limiting and malformed response.
- Do not save/apply suggestions implicitly.

5. REQUIRED TESTING
Add focused regression tests for the root cause and relevant negative, failure, boundary, retry, concurrency and stale-state paths. Assert durable database/filesystem/worker state as applicable, not only mocked return values. Use synthetic media, disposable test records and test provider mode. Never publish to real YouTube or destructive-clean real data.
- Empty/long text, error, rate limiting, malformed payload, successful result and reload.
- No synthetic score outside explicit test fixtures.
Run the exact focused suite, relevant regressions, static checks and build/browser/integration tests required by the changed layers. Capture actual commands, counts, exit codes, warning/failure output and environment. Do not claim a test ran if only drafted or launched without a completed result.

6. THREE VERIFICATION PASSES — REQUIRED FOR THIS ITEM
PASS 1 — Implementation verification: review diff against every acceptance criterion; run focused tests and the affected workflow; prove expected state and failure behavior.
PASS 2 — Independent challenge: stop thinking like the implementation author. Re-read the requirement and original defect evidence. Try to falsify the fix with adversarial inputs, conflicts, retries, parallel requests, stale state and failure injection. Compare alternative approaches again. Inspect whether the tests could pass while production is still broken. Fix any issue discovered and record changes since Pass 1.
PASS 3 — Differential re-verification: re-read the final diff and working tree from scratch. Compare final code with Passes 1 and 2, identify all changes introduced after each earlier pass, rerun affected focused tests and relevant regressions against the final tree, and verify reports/status files match the final code. Any new code change invalidates the affected previous pass; repeat it.

7. EXPLICIT SELF-CHALLENGE QUESTIONS
- What concrete evidence proves the original problem existed?
- Why does each changed line/function need to exist?
- What alternative was considered and why was it rejected?
- Could a real production record or untrusted caller reach the test/mock path?
- What happens on failure, retry, concurrency, restart and stale response?
- What does this test prove, and what does it not prove?
- Did I preserve all previous working-tree files and frozen behavior?
- What changed between verification passes and why?
- Which claims remain unverified or depend on an environmental assumption?

8. REQUIRED RECORDS AND FINAL RESPONSE
Update only applicable canonical documents: phase tracker, master ledger, implementation status, defect register, relevant API/frontend/pipeline inventories, audit report and `docs/engineering/AI_DECISION_LOG.md`. Preserve old audit records and append corrections instead of rewriting history. Make status consistent everywhere.
Record work-item ID, before/after working-tree status, root cause, option comparison and rationale, files changed and purpose, relevant hashes if practical, each pass and test result, evidence tier (source/unit/mock/API/in-process/live worker/browser/full E2E), risks, limitations and next dependency.
Report statuses honestly: DELIVERED & VERIFIED, PARTIALLY VERIFIED, BLOCKED or REOPENED. Do not say full E2E without the real required components running together.

9. STOP / CONTINUE RULE
Do not start a different implementation item in parallel or expand this scope to unrelated fixes. Complete all three passes, update records and then continue automatically to the next unblocked item in the master execution queue without waiting for routine approval. Stop only for a real blocker, unresolved high-impact product choice, credential/account action, real publication, destructive action against actual data, or an environment change that requires owner authorization. If blocked, document exact evidence and work safely on independent unblocked work only if it does not depend on the blocker.
Never use `git reset`, `git clean`, blanket reverts, destructive DB resets, `docker compose down -v`, or broad file deletion. Do not reintroduce captions/subtitles; preserve transcription for internal scoring/semantic analysis; retain the frozen Shorts duration limit unless the owner explicitly changes it.
```


### Copy-ready prompt — ROADMAP-5.3: Tracking queue lifecycle

```text
You are the ClipForge engineering agent working in `D:\automation video clips\clipforge`.

WORK ITEM: ROADMAP-5.3 — Tracking queue lifecycle
STATE: Reconcile current repository state before acting. Do not assume this item is open just because it appears in the roadmap.

1. PROBLEM / OBJECTIVE
Make starting, listing, refreshing and cancelling tracking work durable and scoped.

2. PREFLIGHT AND EVIDENCE COLLECTION
Read `AGENTS.md`, the applicable freeze/rule files, `docs/engineering/PHASE_TRACKER.md`, `MASTER_EXECUTION_LEDGER.md`, `IMPLEMENTATION_STATUS.md`, `ENGINEERING_DEFECT_REGISTER.md`, `PIPELINE_CATALOG_AND_DEPENDENCY_GRAPH.md`, `FRONTEND_PAGE_FEATURE_INVENTORY.md`, `PROJECT_CONTINUITY.md`, and the newest relevant audit/decision-log entries. Read only files relevant to this scope in depth, but reconcile any status claims before editing.
Inspect actual current source, schema, runtime route/client/task contracts, tests and caller/callee relationships. Reproduce the reported behavior with a safe isolated fixture where feasible. Separate VERIFIED FACTS, INFERENCES and UNKNOWNS. Record exact file paths, line ranges, commands and observed outputs.
Inspect tracking models, route/task lifecycle, channel monitor, Celery scheduling, credentials and frontend queue.
Capture `git status --short`, branch/commit, existing diff/untracked inventory and relevant environment/container identity before editing. Protect all pre-existing changes. Do not assume old hashes, route counts, schema revisions or historic reports still reflect the current environment.

3. COMPARE APPROACHES AND JUSTIFY THE CHOICE
Approach selection method: Compare at least two plausible approaches where meaningful: (A) smallest local repair, (B) reuse an established repository abstraction/pattern, and (C) architectural change only if the first two cannot meet verified requirements. Use evidence, not preference. Evaluate correctness, data safety, architectural consistency, backwards compatibility, idempotency/concurrency, performance, testability, reversibility, scope and maintenance cost. Record the chosen approach and specific reasons each alternative was rejected. If the problem is already solved in current source, choose the no-op verification path.
Before coding, write a small comparison table in the decision log: option; correctness against acceptance criteria; data/security risk; compatibility; concurrency/idempotency; complexity/maintenance; reversibility; evidence for/against. Do not create arbitrary numerical scores. Explain why the chosen approach is proportionate to the proven root cause and why each rejected alternative is inferior for this evidence.
If the current implementation already meets the requirement, choose verification-only and avoid a redundant change. If requirements remain ambiguous and a wrong choice would be consequential, stop at a documented blocker rather than invent behavior.

4. IMPLEMENTATION BOUNDARY
Implement only this work item. Prefer the smallest complete, maintainable fix using existing models, APIs, task lifecycle, storage/artifact and frontend patterns. Avoid duplicate frameworks, helpers, routes, state machines, database fields or tests when an existing abstraction meets the requirement.
Preserve all unrelated behavior and frozen components. Do not remove code based on apparent lack of callers without a call-site/dependency audit. Do not change public API semantics without documenting callers, compatibility plan and tests. Any migration must be justified, forward-only and data-preserving.
Scope-specific acceptance criteria:
- Only one authoritative tracking job/lease per intended scope.
- Record bounded scan coverage and terminal outcome.
- Cancel safely and stop future scheduled work when requested.
- Handle OAuth failures without leaking secrets.

5. REQUIRED TESTING
Add focused regression tests for the root cause and relevant negative, failure, boundary, retry, concurrency and stale-state paths. Assert durable database/filesystem/worker state as applicable, not only mocked return values. Use synthetic media, disposable test records and test provider mode. Never publish to real YouTube or destructive-clean real data.
- Start/repeat/list/refresh/cancel, missing token, provider failure, worker restart, stale state, multiple channels.
- Assert DB queue state and scheduler behavior.
Run the exact focused suite, relevant regressions, static checks and build/browser/integration tests required by the changed layers. Capture actual commands, counts, exit codes, warning/failure output and environment. Do not claim a test ran if only drafted or launched without a completed result.

6. THREE VERIFICATION PASSES — REQUIRED FOR THIS ITEM
PASS 1 — Implementation verification: review diff against every acceptance criterion; run focused tests and the affected workflow; prove expected state and failure behavior.
PASS 2 — Independent challenge: stop thinking like the implementation author. Re-read the requirement and original defect evidence. Try to falsify the fix with adversarial inputs, conflicts, retries, parallel requests, stale state and failure injection. Compare alternative approaches again. Inspect whether the tests could pass while production is still broken. Fix any issue discovered and record changes since Pass 1.
PASS 3 — Differential re-verification: re-read the final diff and working tree from scratch. Compare final code with Passes 1 and 2, identify all changes introduced after each earlier pass, rerun affected focused tests and relevant regressions against the final tree, and verify reports/status files match the final code. Any new code change invalidates the affected previous pass; repeat it.

7. EXPLICIT SELF-CHALLENGE QUESTIONS
- What concrete evidence proves the original problem existed?
- Why does each changed line/function need to exist?
- What alternative was considered and why was it rejected?
- Could a real production record or untrusted caller reach the test/mock path?
- What happens on failure, retry, concurrency, restart and stale response?
- What does this test prove, and what does it not prove?
- Did I preserve all previous working-tree files and frozen behavior?
- What changed between verification passes and why?
- Which claims remain unverified or depend on an environmental assumption?

8. REQUIRED RECORDS AND FINAL RESPONSE
Update only applicable canonical documents: phase tracker, master ledger, implementation status, defect register, relevant API/frontend/pipeline inventories, audit report and `docs/engineering/AI_DECISION_LOG.md`. Preserve old audit records and append corrections instead of rewriting history. Make status consistent everywhere.
Record work-item ID, before/after working-tree status, root cause, option comparison and rationale, files changed and purpose, relevant hashes if practical, each pass and test result, evidence tier (source/unit/mock/API/in-process/live worker/browser/full E2E), risks, limitations and next dependency.
Report statuses honestly: DELIVERED & VERIFIED, PARTIALLY VERIFIED, BLOCKED or REOPENED. Do not say full E2E without the real required components running together.

9. STOP / CONTINUE RULE
Do not start a different implementation item in parallel or expand this scope to unrelated fixes. Complete all three passes, update records and then continue automatically to the next unblocked item in the master execution queue without waiting for routine approval. Stop only for a real blocker, unresolved high-impact product choice, credential/account action, real publication, destructive action against actual data, or an environment change that requires owner authorization. If blocked, document exact evidence and work safely on independent unblocked work only if it does not depend on the blocker.
Never use `git reset`, `git clean`, blanket reverts, destructive DB resets, `docker compose down -v`, or broad file deletion. Do not reintroduce captions/subtitles; preserve transcription for internal scoring/semantic analysis; retain the frozen Shorts duration limit unless the owner explicitly changes it.
```


### Copy-ready prompt — ROADMAP-5.4: Optimization lifecycle

```text
You are the ClipForge engineering agent working in `D:\automation video clips\clipforge`.

WORK ITEM: ROADMAP-5.4 — Optimization lifecycle
STATE: Reconcile current repository state before acting. Do not assume this item is open just because it appears in the roadmap.

1. PROBLEM / OBJECTIVE
Ensure manual/automatic optimization settings and logs reflect real worker behavior.

2. PREFLIGHT AND EVIDENCE COLLECTION
Read `AGENTS.md`, the applicable freeze/rule files, `docs/engineering/PHASE_TRACKER.md`, `MASTER_EXECUTION_LEDGER.md`, `IMPLEMENTATION_STATUS.md`, `ENGINEERING_DEFECT_REGISTER.md`, `PIPELINE_CATALOG_AND_DEPENDENCY_GRAPH.md`, `FRONTEND_PAGE_FEATURE_INVENTORY.md`, `PROJECT_CONTINUITY.md`, and the newest relevant audit/decision-log entries. Read only files relevant to this scope in depth, but reconcile any status claims before editing.
Inspect actual current source, schema, runtime route/client/task contracts, tests and caller/callee relationships. Reproduce the reported behavior with a safe isolated fixture where feasible. Separate VERIFIED FACTS, INFERENCES and UNKNOWNS. Record exact file paths, line ranges, commands and observed outputs.
Inspect `auto_optimizer`, optimization route/task/log records, settings contract and current controls.
Capture `git status --short`, branch/commit, existing diff/untracked inventory and relevant environment/container identity before editing. Protect all pre-existing changes. Do not assume old hashes, route counts, schema revisions or historic reports still reflect the current environment.

3. COMPARE APPROACHES AND JUSTIFY THE CHOICE
Approach selection method: Compare at least two plausible approaches where meaningful: (A) smallest local repair, (B) reuse an established repository abstraction/pattern, and (C) architectural change only if the first two cannot meet verified requirements. Use evidence, not preference. Evaluate correctness, data safety, architectural consistency, backwards compatibility, idempotency/concurrency, performance, testability, reversibility, scope and maintenance cost. Record the chosen approach and specific reasons each alternative was rejected. If the problem is already solved in current source, choose the no-op verification path.
Before coding, write a small comparison table in the decision log: option; correctness against acceptance criteria; data/security risk; compatibility; concurrency/idempotency; complexity/maintenance; reversibility; evidence for/against. Do not create arbitrary numerical scores. Explain why the chosen approach is proportionate to the proven root cause and why each rejected alternative is inferior for this evidence.
If the current implementation already meets the requirement, choose verification-only and avoid a redundant change. If requirements remain ambiguous and a wrong choice would be consequential, stop at a documented blocker rather than invent behavior.

4. IMPLEMENTATION BOUNDARY
Implement only this work item. Prefer the smallest complete, maintainable fix using existing models, APIs, task lifecycle, storage/artifact and frontend patterns. Avoid duplicate frameworks, helpers, routes, state machines, database fields or tests when an existing abstraction meets the requirement.
Preserve all unrelated behavior and frozen components. Do not remove code based on apparent lack of callers without a call-site/dependency audit. Do not change public API semantics without documenting callers, compatibility plan and tests. Any migration must be justified, forward-only and data-preserving.
Scope-specific acceptance criteria:
- Define each knob’s actual runtime effect from source; do not claim unsupported toggles work.
- Persist before using new config; explain restart/hot reload semantics.
- Record the specific inputs/outputs and failures of each optimization run.
- Do not automatically apply/publish changes beyond current contract.

5. REQUIRED TESTING
Add focused regression tests for the root cause and relevant negative, failure, boundary, retry, concurrency and stale-state paths. Assert durable database/filesystem/worker state as applicable, not only mocked return values. Use synthetic media, disposable test records and test provider mode. Never publish to real YouTube or destructive-clean real data.
- Enabled/disabled, invalid settings, duplicate request, concurrent changes, task failure, log view and reload.
- Assert observed runtime behavior, not just UI state.
Run the exact focused suite, relevant regressions, static checks and build/browser/integration tests required by the changed layers. Capture actual commands, counts, exit codes, warning/failure output and environment. Do not claim a test ran if only drafted or launched without a completed result.

6. THREE VERIFICATION PASSES — REQUIRED FOR THIS ITEM
PASS 1 — Implementation verification: review diff against every acceptance criterion; run focused tests and the affected workflow; prove expected state and failure behavior.
PASS 2 — Independent challenge: stop thinking like the implementation author. Re-read the requirement and original defect evidence. Try to falsify the fix with adversarial inputs, conflicts, retries, parallel requests, stale state and failure injection. Compare alternative approaches again. Inspect whether the tests could pass while production is still broken. Fix any issue discovered and record changes since Pass 1.
PASS 3 — Differential re-verification: re-read the final diff and working tree from scratch. Compare final code with Passes 1 and 2, identify all changes introduced after each earlier pass, rerun affected focused tests and relevant regressions against the final tree, and verify reports/status files match the final code. Any new code change invalidates the affected previous pass; repeat it.

7. EXPLICIT SELF-CHALLENGE QUESTIONS
- What concrete evidence proves the original problem existed?
- Why does each changed line/function need to exist?
- What alternative was considered and why was it rejected?
- Could a real production record or untrusted caller reach the test/mock path?
- What happens on failure, retry, concurrency, restart and stale response?
- What does this test prove, and what does it not prove?
- Did I preserve all previous working-tree files and frozen behavior?
- What changed between verification passes and why?
- Which claims remain unverified or depend on an environmental assumption?

8. REQUIRED RECORDS AND FINAL RESPONSE
Update only applicable canonical documents: phase tracker, master ledger, implementation status, defect register, relevant API/frontend/pipeline inventories, audit report and `docs/engineering/AI_DECISION_LOG.md`. Preserve old audit records and append corrections instead of rewriting history. Make status consistent everywhere.
Record work-item ID, before/after working-tree status, root cause, option comparison and rationale, files changed and purpose, relevant hashes if practical, each pass and test result, evidence tier (source/unit/mock/API/in-process/live worker/browser/full E2E), risks, limitations and next dependency.
Report statuses honestly: DELIVERED & VERIFIED, PARTIALLY VERIFIED, BLOCKED or REOPENED. Do not say full E2E without the real required components running together.

9. STOP / CONTINUE RULE
Do not start a different implementation item in parallel or expand this scope to unrelated fixes. Complete all three passes, update records and then continue automatically to the next unblocked item in the master execution queue without waiting for routine approval. Stop only for a real blocker, unresolved high-impact product choice, credential/account action, real publication, destructive action against actual data, or an environment change that requires owner authorization. If blocked, document exact evidence and work safely on independent unblocked work only if it does not depend on the blocker.
Never use `git reset`, `git clean`, blanket reverts, destructive DB resets, `docker compose down -v`, or broad file deletion. Do not reintroduce captions/subtitles; preserve transcription for internal scoring/semantic analysis; retain the frozen Shorts duration limit unless the owner explicitly changes it.
```


## Main phase prompt — ROADMAP Phase 6: Settings persistence

```text
You are the ClipForge engineering agent. Coordinate Phase 6: Settings persistence as a sequence of independently testable child work items, not a single broad implementation.

PROBLEM / OBJECTIVE
Replace false browser-only persistence with a secure, allowlisted backend contract. Execute 6.1–6.4 in order.

DISCOVERY AND METHOD
Read the current project rules and phase ledger; establish whether each child is already delivered, unverified, blocked or open. Compare viable approaches for each child before implementation. Prefer the smallest evidence-backed fix that reuses current architecture. Record a qualitative comparison of correctness, data safety, compatibility, concurrency/idempotency, operational burden, reversibility and testability. Explain the chosen approach and why other options were rejected. Never rely on old phase numbers when they conflict with canonical records.

PHASE ACCEPTANCE CRITERIA
- Contract and trust boundary established first.
- Backend validation and secret redaction.
- Frontend truthful load/save/error behavior.
- Runtime effect proven or setting labelled restart-required/informational.

EXECUTION SEQUENCE
Execute the child subphases in the order shown in the index. For each child: inspect/reproduce; implement only that child; run Pass 1, Pass 2 and Pass 3 as defined in the companion rules; update `AI_DECISION_LOG.md` and canonical status; then move autonomously to the next unblocked child. Do not bundle unrelated children into one diff.

CROSS-VERIFICATION
Before phase close, independently check every child status against final source, test outputs and runtime evidence. Recheck frozen invariants, changed files and working-tree state. A completed build alone does not prove runtime behavior. A task ID/toast does not prove a worker finished.

BOUNDARIES
Never write arbitrary env keys or blindly rewrite `.env`.
Preserve existing changes and untracked files. No real publishing. No caption/subtitle framework. Never use destructive Git operations or broad DB/storage deletion. High-impact irreversible actions against real user data require explicit owner authorization.

PHASE EXIT
Close this main phase only when all required children are either independently verified or explicitly documented as blocked with owner-relevant rationale. If blocked, do not mislabel the phase complete. Record the next unblocked dependency and continue autonomously when safe.
```


### Copy-ready prompt — ROADMAP-6.1: Settings contract and security

```text
You are the ClipForge engineering agent working in `D:\automation video clips\clipforge`.

WORK ITEM: ROADMAP-6.1 — Settings contract and security
STATE: Reconcile current repository state before acting. Do not assume this item is open just because it appears in the roadmap.

1. PROBLEM / OBJECTIVE
Define a minimal, explicit contract before implementing settings persistence.

2. PREFLIGHT AND EVIDENCE COLLECTION
Read `AGENTS.md`, the applicable freeze/rule files, `docs/engineering/PHASE_TRACKER.md`, `MASTER_EXECUTION_LEDGER.md`, `IMPLEMENTATION_STATUS.md`, `ENGINEERING_DEFECT_REGISTER.md`, `PIPELINE_CATALOG_AND_DEPENDENCY_GRAPH.md`, `FRONTEND_PAGE_FEATURE_INVENTORY.md`, `PROJECT_CONTINUITY.md`, and the newest relevant audit/decision-log entries. Read only files relevant to this scope in depth, but reconcile any status claims before editing.
Inspect actual current source, schema, runtime route/client/task contracts, tests and caller/callee relationships. Reproduce the reported behavior with a safe isolated fixture where feasible. Separate VERIFIED FACTS, INFERENCES and UNKNOWNS. Record exact file paths, line ranges, commands and observed outputs.
Inventory UI controls, defaults, current localStorage behavior, config model, secrets, supported provider/worker settings and restart semantics.
Capture `git status --short`, branch/commit, existing diff/untracked inventory and relevant environment/container identity before editing. Protect all pre-existing changes. Do not assume old hashes, route counts, schema revisions or historic reports still reflect the current environment.

3. COMPARE APPROACHES AND JUSTIFY THE CHOICE
Approach selection method: Compare at least two plausible approaches where meaningful: (A) smallest local repair, (B) reuse an established repository abstraction/pattern, and (C) architectural change only if the first two cannot meet verified requirements. Use evidence, not preference. Evaluate correctness, data safety, architectural consistency, backwards compatibility, idempotency/concurrency, performance, testability, reversibility, scope and maintenance cost. Record the chosen approach and specific reasons each alternative was rejected. If the problem is already solved in current source, choose the no-op verification path.
Before coding, write a small comparison table in the decision log: option; correctness against acceptance criteria; data/security risk; compatibility; concurrency/idempotency; complexity/maintenance; reversibility; evidence for/against. Do not create arbitrary numerical scores. Explain why the chosen approach is proportionate to the proven root cause and why each rejected alternative is inferior for this evidence.
If the current implementation already meets the requirement, choose verification-only and avoid a redundant change. If requirements remain ambiguous and a wrong choice would be consequential, stop at a documented blocker rather than invent behavior.

4. IMPLEMENTATION BOUNDARY
Implement only this work item. Prefer the smallest complete, maintainable fix using existing models, APIs, task lifecycle, storage/artifact and frontend patterns. Avoid duplicate frameworks, helpers, routes, state machines, database fields or tests when an existing abstraction meets the requirement.
Preserve all unrelated behavior and frozen components. Do not remove code based on apparent lack of callers without a call-site/dependency audit. Do not change public API semantics without documenting callers, compatibility plan and tests. Any migration must be justified, forward-only and data-preserving.
Scope-specific acceptance criteria:
- For each setting document type, valid range, default, secret status, storage scope, who can change it, live/restart behavior and observable effect.
- Mark informational/unsupported controls as such.
- Threat-model arbitrary keys, secret retrieval and invalid configuration.

5. REQUIRED TESTING
Add focused regression tests for the root cause and relevant negative, failure, boundary, retry, concurrency and stale-state paths. Assert durable database/filesystem/worker state as applicable, not only mocked return values. Use synthetic media, disposable test records and test provider mode. Never publish to real YouTube or destructive-clean real data.
- Contract covers every visible setting and no unexposed secret keys.
- Alternative choices and rationale recorded.
- No code changes during spec-only work.
Run the exact focused suite, relevant regressions, static checks and build/browser/integration tests required by the changed layers. Capture actual commands, counts, exit codes, warning/failure output and environment. Do not claim a test ran if only drafted or launched without a completed result.

6. THREE VERIFICATION PASSES — REQUIRED FOR THIS ITEM
PASS 1 — Implementation verification: review diff against every acceptance criterion; run focused tests and the affected workflow; prove expected state and failure behavior.
PASS 2 — Independent challenge: stop thinking like the implementation author. Re-read the requirement and original defect evidence. Try to falsify the fix with adversarial inputs, conflicts, retries, parallel requests, stale state and failure injection. Compare alternative approaches again. Inspect whether the tests could pass while production is still broken. Fix any issue discovered and record changes since Pass 1.
PASS 3 — Differential re-verification: re-read the final diff and working tree from scratch. Compare final code with Passes 1 and 2, identify all changes introduced after each earlier pass, rerun affected focused tests and relevant regressions against the final tree, and verify reports/status files match the final code. Any new code change invalidates the affected previous pass; repeat it.

7. EXPLICIT SELF-CHALLENGE QUESTIONS
- What concrete evidence proves the original problem existed?
- Why does each changed line/function need to exist?
- What alternative was considered and why was it rejected?
- Could a real production record or untrusted caller reach the test/mock path?
- What happens on failure, retry, concurrency, restart and stale response?
- What does this test prove, and what does it not prove?
- Did I preserve all previous working-tree files and frozen behavior?
- What changed between verification passes and why?
- Which claims remain unverified or depend on an environmental assumption?

8. REQUIRED RECORDS AND FINAL RESPONSE
Update only applicable canonical documents: phase tracker, master ledger, implementation status, defect register, relevant API/frontend/pipeline inventories, audit report and `docs/engineering/AI_DECISION_LOG.md`. Preserve old audit records and append corrections instead of rewriting history. Make status consistent everywhere.
Record work-item ID, before/after working-tree status, root cause, option comparison and rationale, files changed and purpose, relevant hashes if practical, each pass and test result, evidence tier (source/unit/mock/API/in-process/live worker/browser/full E2E), risks, limitations and next dependency.
Report statuses honestly: DELIVERED & VERIFIED, PARTIALLY VERIFIED, BLOCKED or REOPENED. Do not say full E2E without the real required components running together.

9. STOP / CONTINUE RULE
Do not start a different implementation item in parallel or expand this scope to unrelated fixes. Complete all three passes, update records and then continue automatically to the next unblocked item in the master execution queue without waiting for routine approval. Stop only for a real blocker, unresolved high-impact product choice, credential/account action, real publication, destructive action against actual data, or an environment change that requires owner authorization. If blocked, document exact evidence and work safely on independent unblocked work only if it does not depend on the blocker.
Never use `git reset`, `git clean`, blanket reverts, destructive DB resets, `docker compose down -v`, or broad file deletion. Do not reintroduce captions/subtitles; preserve transcription for internal scoring/semantic analysis; retain the frozen Shorts duration limit unless the owner explicitly changes it.
```


### Copy-ready prompt — ROADMAP-6.2: Backend settings API

```text
You are the ClipForge engineering agent working in `D:\automation video clips\clipforge`.

WORK ITEM: ROADMAP-6.2 — Backend settings API
STATE: Reconcile current repository state before acting. Do not assume this item is open just because it appears in the roadmap.

1. PROBLEM / OBJECTIVE
Implement the approved safe settings contract server-side.

2. PREFLIGHT AND EVIDENCE COLLECTION
Read `AGENTS.md`, the applicable freeze/rule files, `docs/engineering/PHASE_TRACKER.md`, `MASTER_EXECUTION_LEDGER.md`, `IMPLEMENTATION_STATUS.md`, `ENGINEERING_DEFECT_REGISTER.md`, `PIPELINE_CATALOG_AND_DEPENDENCY_GRAPH.md`, `FRONTEND_PAGE_FEATURE_INVENTORY.md`, `PROJECT_CONTINUITY.md`, and the newest relevant audit/decision-log entries. Read only files relevant to this scope in depth, but reconcile any status claims before editing.
Inspect actual current source, schema, runtime route/client/task contracts, tests and caller/callee relationships. Reproduce the reported behavior with a safe isolated fixture where feasible. Separate VERIFIED FACTS, INFERENCES and UNKNOWNS. Record exact file paths, line ranges, commands and observed outputs.
Reconcile config schema, secure storage location, API patterns, runtime loaders and authorization/trust boundary.
Capture `git status --short`, branch/commit, existing diff/untracked inventory and relevant environment/container identity before editing. Protect all pre-existing changes. Do not assume old hashes, route counts, schema revisions or historic reports still reflect the current environment.

3. COMPARE APPROACHES AND JUSTIFY THE CHOICE
Approach selection method: Compare at least two plausible approaches where meaningful: (A) smallest local repair, (B) reuse an established repository abstraction/pattern, and (C) architectural change only if the first two cannot meet verified requirements. Use evidence, not preference. Evaluate correctness, data safety, architectural consistency, backwards compatibility, idempotency/concurrency, performance, testability, reversibility, scope and maintenance cost. Record the chosen approach and specific reasons each alternative was rejected. If the problem is already solved in current source, choose the no-op verification path.
Before coding, write a small comparison table in the decision log: option; correctness against acceptance criteria; data/security risk; compatibility; concurrency/idempotency; complexity/maintenance; reversibility; evidence for/against. Do not create arbitrary numerical scores. Explain why the chosen approach is proportionate to the proven root cause and why each rejected alternative is inferior for this evidence.
If the current implementation already meets the requirement, choose verification-only and avoid a redundant change. If requirements remain ambiguous and a wrong choice would be consequential, stop at a documented blocker rather than invent behavior.

4. IMPLEMENTATION BOUNDARY
Implement only this work item. Prefer the smallest complete, maintainable fix using existing models, APIs, task lifecycle, storage/artifact and frontend patterns. Avoid duplicate frameworks, helpers, routes, state machines, database fields or tests when an existing abstraction meets the requirement.
Preserve all unrelated behavior and frozen components. Do not remove code based on apparent lack of callers without a call-site/dependency audit. Do not change public API semantics without documenting callers, compatibility plan and tests. Any migration must be justified, forward-only and data-preserving.
Scope-specific acceptance criteria:
- Strict allowlist/type/range validation.
- Atomic durable updates and audit events using existing architecture.
- No raw secret response; support redacted configured/not-configured indicators.
- Handle restart-required values distinctly.

5. REQUIRED TESTING
Add focused regression tests for the root cause and relevant negative, failure, boundary, retry, concurrency and stale-state paths. Assert durable database/filesystem/worker state as applicable, not only mocked return values. Use synthetic media, disposable test records and test provider mode. Never publish to real YouTube or destructive-clean real data.
- Unknown key/type/range rejected; secret omitted; rollback on persistence error; reload semantics; authorization/trust boundaries.
- No unintended runtime change after failed update.
Run the exact focused suite, relevant regressions, static checks and build/browser/integration tests required by the changed layers. Capture actual commands, counts, exit codes, warning/failure output and environment. Do not claim a test ran if only drafted or launched without a completed result.

6. THREE VERIFICATION PASSES — REQUIRED FOR THIS ITEM
PASS 1 — Implementation verification: review diff against every acceptance criterion; run focused tests and the affected workflow; prove expected state and failure behavior.
PASS 2 — Independent challenge: stop thinking like the implementation author. Re-read the requirement and original defect evidence. Try to falsify the fix with adversarial inputs, conflicts, retries, parallel requests, stale state and failure injection. Compare alternative approaches again. Inspect whether the tests could pass while production is still broken. Fix any issue discovered and record changes since Pass 1.
PASS 3 — Differential re-verification: re-read the final diff and working tree from scratch. Compare final code with Passes 1 and 2, identify all changes introduced after each earlier pass, rerun affected focused tests and relevant regressions against the final tree, and verify reports/status files match the final code. Any new code change invalidates the affected previous pass; repeat it.

7. EXPLICIT SELF-CHALLENGE QUESTIONS
- What concrete evidence proves the original problem existed?
- Why does each changed line/function need to exist?
- What alternative was considered and why was it rejected?
- Could a real production record or untrusted caller reach the test/mock path?
- What happens on failure, retry, concurrency, restart and stale response?
- What does this test prove, and what does it not prove?
- Did I preserve all previous working-tree files and frozen behavior?
- What changed between verification passes and why?
- Which claims remain unverified or depend on an environmental assumption?

8. REQUIRED RECORDS AND FINAL RESPONSE
Update only applicable canonical documents: phase tracker, master ledger, implementation status, defect register, relevant API/frontend/pipeline inventories, audit report and `docs/engineering/AI_DECISION_LOG.md`. Preserve old audit records and append corrections instead of rewriting history. Make status consistent everywhere.
Record work-item ID, before/after working-tree status, root cause, option comparison and rationale, files changed and purpose, relevant hashes if practical, each pass and test result, evidence tier (source/unit/mock/API/in-process/live worker/browser/full E2E), risks, limitations and next dependency.
Report statuses honestly: DELIVERED & VERIFIED, PARTIALLY VERIFIED, BLOCKED or REOPENED. Do not say full E2E without the real required components running together.

9. STOP / CONTINUE RULE
Do not start a different implementation item in parallel or expand this scope to unrelated fixes. Complete all three passes, update records and then continue automatically to the next unblocked item in the master execution queue without waiting for routine approval. Stop only for a real blocker, unresolved high-impact product choice, credential/account action, real publication, destructive action against actual data, or an environment change that requires owner authorization. If blocked, document exact evidence and work safely on independent unblocked work only if it does not depend on the blocker.
Never use `git reset`, `git clean`, blanket reverts, destructive DB resets, `docker compose down -v`, or broad file deletion. Do not reintroduce captions/subtitles; preserve transcription for internal scoring/semantic analysis; retain the frozen Shorts duration limit unless the owner explicitly changes it.
```


### Copy-ready prompt — ROADMAP-6.3: Frontend settings persistence

```text
You are the ClipForge engineering agent working in `D:\automation video clips\clipforge`.

WORK ITEM: ROADMAP-6.3 — Frontend settings persistence
STATE: Reconcile current repository state before acting. Do not assume this item is open just because it appears in the roadmap.

1. PROBLEM / OBJECTIVE
Connect settings UI to the backend contract and report truthful state.

2. PREFLIGHT AND EVIDENCE COLLECTION
Read `AGENTS.md`, the applicable freeze/rule files, `docs/engineering/PHASE_TRACKER.md`, `MASTER_EXECUTION_LEDGER.md`, `IMPLEMENTATION_STATUS.md`, `ENGINEERING_DEFECT_REGISTER.md`, `PIPELINE_CATALOG_AND_DEPENDENCY_GRAPH.md`, `FRONTEND_PAGE_FEATURE_INVENTORY.md`, `PROJECT_CONTINUITY.md`, and the newest relevant audit/decision-log entries. Read only files relevant to this scope in depth, but reconcile any status claims before editing.
Inspect actual current source, schema, runtime route/client/task contracts, tests and caller/callee relationships. Reproduce the reported behavior with a safe isolated fixture where feasible. Separate VERIFIED FACTS, INFERENCES and UNKNOWNS. Record exact file paths, line ranges, commands and observed outputs.
Inspect current controls/localStorage, typed API client, loading/error primitives, optimistic UI and accessibility.
Capture `git status --short`, branch/commit, existing diff/untracked inventory and relevant environment/container identity before editing. Protect all pre-existing changes. Do not assume old hashes, route counts, schema revisions or historic reports still reflect the current environment.

3. COMPARE APPROACHES AND JUSTIFY THE CHOICE
Approach selection method: Compare at least two plausible approaches where meaningful: (A) smallest local repair, (B) reuse an established repository abstraction/pattern, and (C) architectural change only if the first two cannot meet verified requirements. Use evidence, not preference. Evaluate correctness, data safety, architectural consistency, backwards compatibility, idempotency/concurrency, performance, testability, reversibility, scope and maintenance cost. Record the chosen approach and specific reasons each alternative was rejected. If the problem is already solved in current source, choose the no-op verification path.
Before coding, write a small comparison table in the decision log: option; correctness against acceptance criteria; data/security risk; compatibility; concurrency/idempotency; complexity/maintenance; reversibility; evidence for/against. Do not create arbitrary numerical scores. Explain why the chosen approach is proportionate to the proven root cause and why each rejected alternative is inferior for this evidence.
If the current implementation already meets the requirement, choose verification-only and avoid a redundant change. If requirements remain ambiguous and a wrong choice would be consequential, stop at a documented blocker rather than invent behavior.

4. IMPLEMENTATION BOUNDARY
Implement only this work item. Prefer the smallest complete, maintainable fix using existing models, APIs, task lifecycle, storage/artifact and frontend patterns. Avoid duplicate frameworks, helpers, routes, state machines, database fields or tests when an existing abstraction meets the requirement.
Preserve all unrelated behavior and frozen components. Do not remove code based on apparent lack of callers without a call-site/dependency audit. Do not change public API semantics without documenting callers, compatibility plan and tests. Any migration must be justified, forward-only and data-preserving.
Scope-specific acceptance criteria:
- Load actual backend settings; save allowlisted deltas; update UI only after successful response.
- Handle unavailable backend, validation errors, concurrent save and reload.
- Do not show or prefill secrets.
- Communicate restart-required setting state.

5. REQUIRED TESTING
Add focused regression tests for the root cause and relevant negative, failure, boundary, retry, concurrency and stale-state paths. Assert durable database/filesystem/worker state as applicable, not only mocked return values. Use synthetic media, disposable test records and test provider mode. Never publish to real YouTube or destructive-clean real data.
- Browser success/error/reload; stale state; invalid value; API outage; no duplicate save.
- TypeScript/build and browser network contract.
Run the exact focused suite, relevant regressions, static checks and build/browser/integration tests required by the changed layers. Capture actual commands, counts, exit codes, warning/failure output and environment. Do not claim a test ran if only drafted or launched without a completed result.

6. THREE VERIFICATION PASSES — REQUIRED FOR THIS ITEM
PASS 1 — Implementation verification: review diff against every acceptance criterion; run focused tests and the affected workflow; prove expected state and failure behavior.
PASS 2 — Independent challenge: stop thinking like the implementation author. Re-read the requirement and original defect evidence. Try to falsify the fix with adversarial inputs, conflicts, retries, parallel requests, stale state and failure injection. Compare alternative approaches again. Inspect whether the tests could pass while production is still broken. Fix any issue discovered and record changes since Pass 1.
PASS 3 — Differential re-verification: re-read the final diff and working tree from scratch. Compare final code with Passes 1 and 2, identify all changes introduced after each earlier pass, rerun affected focused tests and relevant regressions against the final tree, and verify reports/status files match the final code. Any new code change invalidates the affected previous pass; repeat it.

7. EXPLICIT SELF-CHALLENGE QUESTIONS
- What concrete evidence proves the original problem existed?
- Why does each changed line/function need to exist?
- What alternative was considered and why was it rejected?
- Could a real production record or untrusted caller reach the test/mock path?
- What happens on failure, retry, concurrency, restart and stale response?
- What does this test prove, and what does it not prove?
- Did I preserve all previous working-tree files and frozen behavior?
- What changed between verification passes and why?
- Which claims remain unverified or depend on an environmental assumption?

8. REQUIRED RECORDS AND FINAL RESPONSE
Update only applicable canonical documents: phase tracker, master ledger, implementation status, defect register, relevant API/frontend/pipeline inventories, audit report and `docs/engineering/AI_DECISION_LOG.md`. Preserve old audit records and append corrections instead of rewriting history. Make status consistent everywhere.
Record work-item ID, before/after working-tree status, root cause, option comparison and rationale, files changed and purpose, relevant hashes if practical, each pass and test result, evidence tier (source/unit/mock/API/in-process/live worker/browser/full E2E), risks, limitations and next dependency.
Report statuses honestly: DELIVERED & VERIFIED, PARTIALLY VERIFIED, BLOCKED or REOPENED. Do not say full E2E without the real required components running together.

9. STOP / CONTINUE RULE
Do not start a different implementation item in parallel or expand this scope to unrelated fixes. Complete all three passes, update records and then continue automatically to the next unblocked item in the master execution queue without waiting for routine approval. Stop only for a real blocker, unresolved high-impact product choice, credential/account action, real publication, destructive action against actual data, or an environment change that requires owner authorization. If blocked, document exact evidence and work safely on independent unblocked work only if it does not depend on the blocker.
Never use `git reset`, `git clean`, blanket reverts, destructive DB resets, `docker compose down -v`, or broad file deletion. Do not reintroduce captions/subtitles; preserve transcription for internal scoring/semantic analysis; retain the frozen Shorts duration limit unless the owner explicitly changes it.
```


### Copy-ready prompt — ROADMAP-6.4: Runtime-effect verification

```text
You are the ClipForge engineering agent working in `D:\automation video clips\clipforge`.

WORK ITEM: ROADMAP-6.4 — Runtime-effect verification
STATE: Reconcile current repository state before acting. Do not assume this item is open just because it appears in the roadmap.

1. PROBLEM / OBJECTIVE
Prove each advertised setting changes the intended actual behavior or is relabeled honestly.

2. PREFLIGHT AND EVIDENCE COLLECTION
Read `AGENTS.md`, the applicable freeze/rule files, `docs/engineering/PHASE_TRACKER.md`, `MASTER_EXECUTION_LEDGER.md`, `IMPLEMENTATION_STATUS.md`, `ENGINEERING_DEFECT_REGISTER.md`, `PIPELINE_CATALOG_AND_DEPENDENCY_GRAPH.md`, `FRONTEND_PAGE_FEATURE_INVENTORY.md`, `PROJECT_CONTINUITY.md`, and the newest relevant audit/decision-log entries. Read only files relevant to this scope in depth, but reconcile any status claims before editing.
Inspect actual current source, schema, runtime route/client/task contracts, tests and caller/callee relationships. Reproduce the reported behavior with a safe isolated fixture where feasible. Separate VERIFIED FACTS, INFERENCES and UNKNOWNS. Record exact file paths, line ranges, commands and observed outputs.
Trace each saved setting to its runtime consumer, worker/backend reload mechanism and observed outcome.
Capture `git status --short`, branch/commit, existing diff/untracked inventory and relevant environment/container identity before editing. Protect all pre-existing changes. Do not assume old hashes, route counts, schema revisions or historic reports still reflect the current environment.

3. COMPARE APPROACHES AND JUSTIFY THE CHOICE
Approach selection method: Compare at least two plausible approaches where meaningful: (A) smallest local repair, (B) reuse an established repository abstraction/pattern, and (C) architectural change only if the first two cannot meet verified requirements. Use evidence, not preference. Evaluate correctness, data safety, architectural consistency, backwards compatibility, idempotency/concurrency, performance, testability, reversibility, scope and maintenance cost. Record the chosen approach and specific reasons each alternative was rejected. If the problem is already solved in current source, choose the no-op verification path.
Before coding, write a small comparison table in the decision log: option; correctness against acceptance criteria; data/security risk; compatibility; concurrency/idempotency; complexity/maintenance; reversibility; evidence for/against. Do not create arbitrary numerical scores. Explain why the chosen approach is proportionate to the proven root cause and why each rejected alternative is inferior for this evidence.
If the current implementation already meets the requirement, choose verification-only and avoid a redundant change. If requirements remain ambiguous and a wrong choice would be consequential, stop at a documented blocker rather than invent behavior.

4. IMPLEMENTATION BOUNDARY
Implement only this work item. Prefer the smallest complete, maintainable fix using existing models, APIs, task lifecycle, storage/artifact and frontend patterns. Avoid duplicate frameworks, helpers, routes, state machines, database fields or tests when an existing abstraction meets the requirement.
Preserve all unrelated behavior and frozen components. Do not remove code based on apparent lack of callers without a call-site/dependency audit. Do not change public API semantics without documenting callers, compatibility plan and tests. Any migration must be justified, forward-only and data-preserving.
Scope-specific acceptance criteria:
- For hot settings, test effect without restart.
- For restart-required settings, verify current-vs-pending state and safe activation procedure.
- Remove false claims from UI/docs if no runtime consumer exists.
- Ensure no secret appears in logs or responses.

5. REQUIRED TESTING
Add focused regression tests for the root cause and relevant negative, failure, boundary, retry, concurrency and stale-state paths. Assert durable database/filesystem/worker state as applicable, not only mocked return values. Use synthetic media, disposable test records and test provider mode. Never publish to real YouTube or destructive-clean real data.
- At least one evidence test per supported setting; negative/no-op check when unsupported.
- Compare saved DB/config and actual runtime value.
Run the exact focused suite, relevant regressions, static checks and build/browser/integration tests required by the changed layers. Capture actual commands, counts, exit codes, warning/failure output and environment. Do not claim a test ran if only drafted or launched without a completed result.

6. THREE VERIFICATION PASSES — REQUIRED FOR THIS ITEM
PASS 1 — Implementation verification: review diff against every acceptance criterion; run focused tests and the affected workflow; prove expected state and failure behavior.
PASS 2 — Independent challenge: stop thinking like the implementation author. Re-read the requirement and original defect evidence. Try to falsify the fix with adversarial inputs, conflicts, retries, parallel requests, stale state and failure injection. Compare alternative approaches again. Inspect whether the tests could pass while production is still broken. Fix any issue discovered and record changes since Pass 1.
PASS 3 — Differential re-verification: re-read the final diff and working tree from scratch. Compare final code with Passes 1 and 2, identify all changes introduced after each earlier pass, rerun affected focused tests and relevant regressions against the final tree, and verify reports/status files match the final code. Any new code change invalidates the affected previous pass; repeat it.

7. EXPLICIT SELF-CHALLENGE QUESTIONS
- What concrete evidence proves the original problem existed?
- Why does each changed line/function need to exist?
- What alternative was considered and why was it rejected?
- Could a real production record or untrusted caller reach the test/mock path?
- What happens on failure, retry, concurrency, restart and stale response?
- What does this test prove, and what does it not prove?
- Did I preserve all previous working-tree files and frozen behavior?
- What changed between verification passes and why?
- Which claims remain unverified or depend on an environmental assumption?

8. REQUIRED RECORDS AND FINAL RESPONSE
Update only applicable canonical documents: phase tracker, master ledger, implementation status, defect register, relevant API/frontend/pipeline inventories, audit report and `docs/engineering/AI_DECISION_LOG.md`. Preserve old audit records and append corrections instead of rewriting history. Make status consistent everywhere.
Record work-item ID, before/after working-tree status, root cause, option comparison and rationale, files changed and purpose, relevant hashes if practical, each pass and test result, evidence tier (source/unit/mock/API/in-process/live worker/browser/full E2E), risks, limitations and next dependency.
Report statuses honestly: DELIVERED & VERIFIED, PARTIALLY VERIFIED, BLOCKED or REOPENED. Do not say full E2E without the real required components running together.

9. STOP / CONTINUE RULE
Do not start a different implementation item in parallel or expand this scope to unrelated fixes. Complete all three passes, update records and then continue automatically to the next unblocked item in the master execution queue without waiting for routine approval. Stop only for a real blocker, unresolved high-impact product choice, credential/account action, real publication, destructive action against actual data, or an environment change that requires owner authorization. If blocked, document exact evidence and work safely on independent unblocked work only if it does not depend on the blocker.
Never use `git reset`, `git clean`, blanket reverts, destructive DB resets, `docker compose down -v`, or broad file deletion. Do not reintroduce captions/subtitles; preserve transcription for internal scoring/semantic analysis; retain the frozen Shorts duration limit unless the owner explicitly changes it.
```


## Main phase prompt — ROADMAP Phase 7: Final integration and regression

```text
You are the ClipForge engineering agent. Coordinate Phase 7: Final integration and regression as a sequence of independently testable child work items, not a single broad implementation.

PROBLEM / OBJECTIVE
Run final cross-system acceptance using 7.1–7.3; patch only demonstrated integration defects.

DISCOVERY AND METHOD
Read the current project rules and phase ledger; establish whether each child is already delivered, unverified, blocked or open. Compare viable approaches for each child before implementation. Prefer the smallest evidence-backed fix that reuses current architecture. Record a qualitative comparison of correctness, data safety, compatibility, concurrency/idempotency, operational burden, reversibility and testability. Explain the chosen approach and why other options were rejected. Never rely on old phase numbers when they conflict with canonical records.

PHASE ACCEPTANCE CRITERIA
- E2E acceptance matrix executed.
- Cross-system identity/state/artifact invariants verified.
- Freeze/documentation records match final source/runtime.

EXECUTION SEQUENCE
Execute the child subphases in the order shown in the index. For each child: inspect/reproduce; implement only that child; run Pass 1, Pass 2 and Pass 3 as defined in the companion rules; update `AI_DECISION_LOG.md` and canonical status; then move autonomously to the next unblocked child. Do not bundle unrelated children into one diff.

CROSS-VERIFICATION
Before phase close, independently check every child status against final source, test outputs and runtime evidence. Recheck frozen invariants, changed files and working-tree state. A completed build alone does not prove runtime behavior. A task ID/toast does not prove a worker finished.

BOUNDARIES
Not a broad refactor phase; reopen only affected boundaries.
Preserve existing changes and untracked files. No real publishing. No caption/subtitle framework. Never use destructive Git operations or broad DB/storage deletion. High-impact irreversible actions against real user data require explicit owner authorization.

PHASE EXIT
Close this main phase only when all required children are either independently verified or explicitly documented as blocked with owner-relevant rationale. If blocked, do not mislabel the phase complete. Record the next unblocked dependency and continue autonomously when safe.
```


### Copy-ready prompt — ROADMAP-7.1: End-to-end acceptance matrix

```text
You are the ClipForge engineering agent working in `D:\automation video clips\clipforge`.

WORK ITEM: ROADMAP-7.1 — End-to-end acceptance matrix
STATE: Reconcile current repository state before acting. Do not assume this item is open just because it appears in the roadmap.

1. PROBLEM / OBJECTIVE
Define and execute a traceable set of critical user journeys across UI/API/DB/worker.

2. PREFLIGHT AND EVIDENCE COLLECTION
Read `AGENTS.md`, the applicable freeze/rule files, `docs/engineering/PHASE_TRACKER.md`, `MASTER_EXECUTION_LEDGER.md`, `IMPLEMENTATION_STATUS.md`, `ENGINEERING_DEFECT_REGISTER.md`, `PIPELINE_CATALOG_AND_DEPENDENCY_GRAPH.md`, `FRONTEND_PAGE_FEATURE_INVENTORY.md`, `PROJECT_CONTINUITY.md`, and the newest relevant audit/decision-log entries. Read only files relevant to this scope in depth, but reconcile any status claims before editing.
Inspect actual current source, schema, runtime route/client/task contracts, tests and caller/callee relationships. Reproduce the reported behavior with a safe isolated fixture where feasible. Separate VERIFIED FACTS, INFERENCES and UNKNOWNS. Record exact file paths, line ranges, commands and observed outputs.
Inspect requirements and current test suites. Build a matrix with journey, fixture, preconditions, request path, DB assertions, worker proof, UI proof, failure mode and owner.
Capture `git status --short`, branch/commit, existing diff/untracked inventory and relevant environment/container identity before editing. Protect all pre-existing changes. Do not assume old hashes, route counts, schema revisions or historic reports still reflect the current environment.

3. COMPARE APPROACHES AND JUSTIFY THE CHOICE
Approach selection method: Compare at least two plausible approaches where meaningful: (A) smallest local repair, (B) reuse an established repository abstraction/pattern, and (C) architectural change only if the first two cannot meet verified requirements. Use evidence, not preference. Evaluate correctness, data safety, architectural consistency, backwards compatibility, idempotency/concurrency, performance, testability, reversibility, scope and maintenance cost. Record the chosen approach and specific reasons each alternative was rejected. If the problem is already solved in current source, choose the no-op verification path.
Before coding, write a small comparison table in the decision log: option; correctness against acceptance criteria; data/security risk; compatibility; concurrency/idempotency; complexity/maintenance; reversibility; evidence for/against. Do not create arbitrary numerical scores. Explain why the chosen approach is proportionate to the proven root cause and why each rejected alternative is inferior for this evidence.
If the current implementation already meets the requirement, choose verification-only and avoid a redundant change. If requirements remain ambiguous and a wrong choice would be consequential, stop at a documented blocker rather than invent behavior.

4. IMPLEMENTATION BOUNDARY
Implement only this work item. Prefer the smallest complete, maintainable fix using existing models, APIs, task lifecycle, storage/artifact and frontend patterns. Avoid duplicate frameworks, helpers, routes, state machines, database fields or tests when an existing abstraction meets the requirement.
Preserve all unrelated behavior and frozen components. Do not remove code based on apparent lack of callers without a call-site/dependency audit. Do not change public API semantics without documenting callers, compatibility plan and tests. Any migration must be justified, forward-only and data-preserving.
Scope-specific acceptance criteria:
- Select representative normal, boundary, concurrency and failure journeys.
- Use synthetic media and test-only provider.
- Map each journey to exact test command/evidence tier.
- Do not claim every branch is covered unless it is.

5. REQUIRED TESTING
Add focused regression tests for the root cause and relevant negative, failure, boundary, retry, concurrency and stale-state paths. Assert durable database/filesystem/worker state as applicable, not only mocked return values. Use synthetic media, disposable test records and test provider mode. Never publish to real YouTube or destructive-clean real data.
- Upload/processing to history; multi-video partial failure; cancel; cleanup preview; AI enhancement apply; settings persistence; mock publish queue.
- Run feasible E2E with live worker and real browser backed by backend.
Run the exact focused suite, relevant regressions, static checks and build/browser/integration tests required by the changed layers. Capture actual commands, counts, exit codes, warning/failure output and environment. Do not claim a test ran if only drafted or launched without a completed result.

6. THREE VERIFICATION PASSES — REQUIRED FOR THIS ITEM
PASS 1 — Implementation verification: review diff against every acceptance criterion; run focused tests and the affected workflow; prove expected state and failure behavior.
PASS 2 — Independent challenge: stop thinking like the implementation author. Re-read the requirement and original defect evidence. Try to falsify the fix with adversarial inputs, conflicts, retries, parallel requests, stale state and failure injection. Compare alternative approaches again. Inspect whether the tests could pass while production is still broken. Fix any issue discovered and record changes since Pass 1.
PASS 3 — Differential re-verification: re-read the final diff and working tree from scratch. Compare final code with Passes 1 and 2, identify all changes introduced after each earlier pass, rerun affected focused tests and relevant regressions against the final tree, and verify reports/status files match the final code. Any new code change invalidates the affected previous pass; repeat it.

7. EXPLICIT SELF-CHALLENGE QUESTIONS
- What concrete evidence proves the original problem existed?
- Why does each changed line/function need to exist?
- What alternative was considered and why was it rejected?
- Could a real production record or untrusted caller reach the test/mock path?
- What happens on failure, retry, concurrency, restart and stale response?
- What does this test prove, and what does it not prove?
- Did I preserve all previous working-tree files and frozen behavior?
- What changed between verification passes and why?
- Which claims remain unverified or depend on an environmental assumption?

8. REQUIRED RECORDS AND FINAL RESPONSE
Update only applicable canonical documents: phase tracker, master ledger, implementation status, defect register, relevant API/frontend/pipeline inventories, audit report and `docs/engineering/AI_DECISION_LOG.md`. Preserve old audit records and append corrections instead of rewriting history. Make status consistent everywhere.
Record work-item ID, before/after working-tree status, root cause, option comparison and rationale, files changed and purpose, relevant hashes if practical, each pass and test result, evidence tier (source/unit/mock/API/in-process/live worker/browser/full E2E), risks, limitations and next dependency.
Report statuses honestly: DELIVERED & VERIFIED, PARTIALLY VERIFIED, BLOCKED or REOPENED. Do not say full E2E without the real required components running together.

9. STOP / CONTINUE RULE
Do not start a different implementation item in parallel or expand this scope to unrelated fixes. Complete all three passes, update records and then continue automatically to the next unblocked item in the master execution queue without waiting for routine approval. Stop only for a real blocker, unresolved high-impact product choice, credential/account action, real publication, destructive action against actual data, or an environment change that requires owner authorization. If blocked, document exact evidence and work safely on independent unblocked work only if it does not depend on the blocker.
Never use `git reset`, `git clean`, blanket reverts, destructive DB resets, `docker compose down -v`, or broad file deletion. Do not reintroduce captions/subtitles; preserve transcription for internal scoring/semantic analysis; retain the frozen Shorts duration limit unless the owner explicitly changes it.
```


### Copy-ready prompt — ROADMAP-7.2: Cross-subsystem data consistency

```text
You are the ClipForge engineering agent working in `D:\automation video clips\clipforge`.

WORK ITEM: ROADMAP-7.2 — Cross-subsystem data consistency
STATE: Reconcile current repository state before acting. Do not assume this item is open just because it appears in the roadmap.

1. PROBLEM / OBJECTIVE
Verify IDs, state transitions, artifacts and selected channel/destination remain consistent across subsystems.

2. PREFLIGHT AND EVIDENCE COLLECTION
Read `AGENTS.md`, the applicable freeze/rule files, `docs/engineering/PHASE_TRACKER.md`, `MASTER_EXECUTION_LEDGER.md`, `IMPLEMENTATION_STATUS.md`, `ENGINEERING_DEFECT_REGISTER.md`, `PIPELINE_CATALOG_AND_DEPENDENCY_GRAPH.md`, `FRONTEND_PAGE_FEATURE_INVENTORY.md`, `PROJECT_CONTINUITY.md`, and the newest relevant audit/decision-log entries. Read only files relevant to this scope in depth, but reconcile any status claims before editing.
Inspect actual current source, schema, runtime route/client/task contracts, tests and caller/callee relationships. Reproduce the reported behavior with a safe isolated fixture where feasible. Separate VERIFIED FACTS, INFERENCES and UNKNOWNS. Record exact file paths, line ranges, commands and observed outputs.
Trace Job, Video, Clip, Variant, ArtifactRecord, Channel, destination and publish records from real isolated journeys.
Capture `git status --short`, branch/commit, existing diff/untracked inventory and relevant environment/container identity before editing. Protect all pre-existing changes. Do not assume old hashes, route counts, schema revisions or historic reports still reflect the current environment.

3. COMPARE APPROACHES AND JUSTIFY THE CHOICE
Approach selection method: Compare at least two plausible approaches where meaningful: (A) smallest local repair, (B) reuse an established repository abstraction/pattern, and (C) architectural change only if the first two cannot meet verified requirements. Use evidence, not preference. Evaluate correctness, data safety, architectural consistency, backwards compatibility, idempotency/concurrency, performance, testability, reversibility, scope and maintenance cost. Record the chosen approach and specific reasons each alternative was rejected. If the problem is already solved in current source, choose the no-op verification path.
Before coding, write a small comparison table in the decision log: option; correctness against acceptance criteria; data/security risk; compatibility; concurrency/idempotency; complexity/maintenance; reversibility; evidence for/against. Do not create arbitrary numerical scores. Explain why the chosen approach is proportionate to the proven root cause and why each rejected alternative is inferior for this evidence.
If the current implementation already meets the requirement, choose verification-only and avoid a redundant change. If requirements remain ambiguous and a wrong choice would be consequential, stop at a documented blocker rather than invent behavior.

4. IMPLEMENTATION BOUNDARY
Implement only this work item. Prefer the smallest complete, maintainable fix using existing models, APIs, task lifecycle, storage/artifact and frontend patterns. Avoid duplicate frameworks, helpers, routes, state machines, database fields or tests when an existing abstraction meets the requirement.
Preserve all unrelated behavior and frozen components. Do not remove code based on apparent lack of callers without a call-site/dependency audit. Do not change public API semantics without documenting callers, compatibility plan and tests. Any migration must be justified, forward-only and data-preserving.
Scope-specific acceptance criteria:
- Validate referential integrity, status vocabulary, ownership and storage key resolution.
- Check terminal status never changes incorrectly.
- Check shared artifacts are protected from deletion.
- Check source and destination identities are not conflated.

5. REQUIRED TESTING
Add focused regression tests for the root cause and relevant negative, failure, boundary, retry, concurrency and stale-state paths. Assert durable database/filesystem/worker state as applicable, not only mocked return values. Use synthetic media, disposable test records and test provider mode. Never publish to real YouTube or destructive-clean real data.
- DB query assertions, artifact probes, refresh/restart where safe, partial failure/retry and orphan scan in read-only mode.
- No cleanup mutation from a reconciliation audit.
Run the exact focused suite, relevant regressions, static checks and build/browser/integration tests required by the changed layers. Capture actual commands, counts, exit codes, warning/failure output and environment. Do not claim a test ran if only drafted or launched without a completed result.

6. THREE VERIFICATION PASSES — REQUIRED FOR THIS ITEM
PASS 1 — Implementation verification: review diff against every acceptance criterion; run focused tests and the affected workflow; prove expected state and failure behavior.
PASS 2 — Independent challenge: stop thinking like the implementation author. Re-read the requirement and original defect evidence. Try to falsify the fix with adversarial inputs, conflicts, retries, parallel requests, stale state and failure injection. Compare alternative approaches again. Inspect whether the tests could pass while production is still broken. Fix any issue discovered and record changes since Pass 1.
PASS 3 — Differential re-verification: re-read the final diff and working tree from scratch. Compare final code with Passes 1 and 2, identify all changes introduced after each earlier pass, rerun affected focused tests and relevant regressions against the final tree, and verify reports/status files match the final code. Any new code change invalidates the affected previous pass; repeat it.

7. EXPLICIT SELF-CHALLENGE QUESTIONS
- What concrete evidence proves the original problem existed?
- Why does each changed line/function need to exist?
- What alternative was considered and why was it rejected?
- Could a real production record or untrusted caller reach the test/mock path?
- What happens on failure, retry, concurrency, restart and stale response?
- What does this test prove, and what does it not prove?
- Did I preserve all previous working-tree files and frozen behavior?
- What changed between verification passes and why?
- Which claims remain unverified or depend on an environmental assumption?

8. REQUIRED RECORDS AND FINAL RESPONSE
Update only applicable canonical documents: phase tracker, master ledger, implementation status, defect register, relevant API/frontend/pipeline inventories, audit report and `docs/engineering/AI_DECISION_LOG.md`. Preserve old audit records and append corrections instead of rewriting history. Make status consistent everywhere.
Record work-item ID, before/after working-tree status, root cause, option comparison and rationale, files changed and purpose, relevant hashes if practical, each pass and test result, evidence tier (source/unit/mock/API/in-process/live worker/browser/full E2E), risks, limitations and next dependency.
Report statuses honestly: DELIVERED & VERIFIED, PARTIALLY VERIFIED, BLOCKED or REOPENED. Do not say full E2E without the real required components running together.

9. STOP / CONTINUE RULE
Do not start a different implementation item in parallel or expand this scope to unrelated fixes. Complete all three passes, update records and then continue automatically to the next unblocked item in the master execution queue without waiting for routine approval. Stop only for a real blocker, unresolved high-impact product choice, credential/account action, real publication, destructive action against actual data, or an environment change that requires owner authorization. If blocked, document exact evidence and work safely on independent unblocked work only if it does not depend on the blocker.
Never use `git reset`, `git clean`, blanket reverts, destructive DB resets, `docker compose down -v`, or broad file deletion. Do not reintroduce captions/subtitles; preserve transcription for internal scoring/semantic analysis; retain the frozen Shorts duration limit unless the owner explicitly changes it.
```


### Copy-ready prompt — ROADMAP-7.3: Documentation and freeze

```text
You are the ClipForge engineering agent working in `D:\automation video clips\clipforge`.

WORK ITEM: ROADMAP-7.3 — Documentation and freeze
STATE: Reconcile current repository state before acting. Do not assume this item is open just because it appears in the roadmap.

1. PROBLEM / OBJECTIVE
Freeze verified components and make the engineering record match final state.

2. PREFLIGHT AND EVIDENCE COLLECTION
Read `AGENTS.md`, the applicable freeze/rule files, `docs/engineering/PHASE_TRACKER.md`, `MASTER_EXECUTION_LEDGER.md`, `IMPLEMENTATION_STATUS.md`, `ENGINEERING_DEFECT_REGISTER.md`, `PIPELINE_CATALOG_AND_DEPENDENCY_GRAPH.md`, `FRONTEND_PAGE_FEATURE_INVENTORY.md`, `PROJECT_CONTINUITY.md`, and the newest relevant audit/decision-log entries. Read only files relevant to this scope in depth, but reconcile any status claims before editing.
Inspect actual current source, schema, runtime route/client/task contracts, tests and caller/callee relationships. Reproduce the reported behavior with a safe isolated fixture where feasible. Separate VERIFIED FACTS, INFERENCES and UNKNOWNS. Record exact file paths, line ranges, commands and observed outputs.
Compare phase tracker, master ledger, defect register, route/client inventory, pipeline graph, frontend inventory, audits and decision log to code, tests and runtime.
Capture `git status --short`, branch/commit, existing diff/untracked inventory and relevant environment/container identity before editing. Protect all pre-existing changes. Do not assume old hashes, route counts, schema revisions or historic reports still reflect the current environment.

3. COMPARE APPROACHES AND JUSTIFY THE CHOICE
Approach selection method: Compare at least two plausible approaches where meaningful: (A) smallest local repair, (B) reuse an established repository abstraction/pattern, and (C) architectural change only if the first two cannot meet verified requirements. Use evidence, not preference. Evaluate correctness, data safety, architectural consistency, backwards compatibility, idempotency/concurrency, performance, testability, reversibility, scope and maintenance cost. Record the chosen approach and specific reasons each alternative was rejected. If the problem is already solved in current source, choose the no-op verification path.
Before coding, write a small comparison table in the decision log: option; correctness against acceptance criteria; data/security risk; compatibility; concurrency/idempotency; complexity/maintenance; reversibility; evidence for/against. Do not create arbitrary numerical scores. Explain why the chosen approach is proportionate to the proven root cause and why each rejected alternative is inferior for this evidence.
If the current implementation already meets the requirement, choose verification-only and avoid a redundant change. If requirements remain ambiguous and a wrong choice would be consequential, stop at a documented blocker rather than invent behavior.

4. IMPLEMENTATION BOUNDARY
Implement only this work item. Prefer the smallest complete, maintainable fix using existing models, APIs, task lifecycle, storage/artifact and frontend patterns. Avoid duplicate frameworks, helpers, routes, state machines, database fields or tests when an existing abstraction meets the requirement.
Preserve all unrelated behavior and frozen components. Do not remove code based on apparent lack of callers without a call-site/dependency audit. Do not change public API semantics without documenting callers, compatibility plan and tests. Any migration must be justified, forward-only and data-preserving.
Scope-specific acceptance criteria:
- Record exact final status, hashes/diff summaries and evidence tiers.
- Keep old audit reports and append correction records.
- List unsupported/blocked behaviors and operational prerequisites.
- Mark freeze boundaries and permitted change exceptions.

5. REQUIRED TESTING
Add focused regression tests for the root cause and relevant negative, failure, boundary, retry, concurrency and stale-state paths. Assert durable database/filesystem/worker state as applicable, not only mocked return values. Use synthetic media, disposable test records and test provider mode. Never publish to real YouTube or destructive-clean real data.
- Independent consistency sweep; no contradictory status, count or “verified” claim.
- Clean release handoff with residual defects and next action.
Run the exact focused suite, relevant regressions, static checks and build/browser/integration tests required by the changed layers. Capture actual commands, counts, exit codes, warning/failure output and environment. Do not claim a test ran if only drafted or launched without a completed result.

6. THREE VERIFICATION PASSES — REQUIRED FOR THIS ITEM
PASS 1 — Implementation verification: review diff against every acceptance criterion; run focused tests and the affected workflow; prove expected state and failure behavior.
PASS 2 — Independent challenge: stop thinking like the implementation author. Re-read the requirement and original defect evidence. Try to falsify the fix with adversarial inputs, conflicts, retries, parallel requests, stale state and failure injection. Compare alternative approaches again. Inspect whether the tests could pass while production is still broken. Fix any issue discovered and record changes since Pass 1.
PASS 3 — Differential re-verification: re-read the final diff and working tree from scratch. Compare final code with Passes 1 and 2, identify all changes introduced after each earlier pass, rerun affected focused tests and relevant regressions against the final tree, and verify reports/status files match the final code. Any new code change invalidates the affected previous pass; repeat it.

7. EXPLICIT SELF-CHALLENGE QUESTIONS
- What concrete evidence proves the original problem existed?
- Why does each changed line/function need to exist?
- What alternative was considered and why was it rejected?
- Could a real production record or untrusted caller reach the test/mock path?
- What happens on failure, retry, concurrency, restart and stale response?
- What does this test prove, and what does it not prove?
- Did I preserve all previous working-tree files and frozen behavior?
- What changed between verification passes and why?
- Which claims remain unverified or depend on an environmental assumption?

8. REQUIRED RECORDS AND FINAL RESPONSE
Update only applicable canonical documents: phase tracker, master ledger, implementation status, defect register, relevant API/frontend/pipeline inventories, audit report and `docs/engineering/AI_DECISION_LOG.md`. Preserve old audit records and append corrections instead of rewriting history. Make status consistent everywhere.
Record work-item ID, before/after working-tree status, root cause, option comparison and rationale, files changed and purpose, relevant hashes if practical, each pass and test result, evidence tier (source/unit/mock/API/in-process/live worker/browser/full E2E), risks, limitations and next dependency.
Report statuses honestly: DELIVERED & VERIFIED, PARTIALLY VERIFIED, BLOCKED or REOPENED. Do not say full E2E without the real required components running together.

9. STOP / CONTINUE RULE
Do not start a different implementation item in parallel or expand this scope to unrelated fixes. Complete all three passes, update records and then continue automatically to the next unblocked item in the master execution queue without waiting for routine approval. Stop only for a real blocker, unresolved high-impact product choice, credential/account action, real publication, destructive action against actual data, or an environment change that requires owner authorization. If blocked, document exact evidence and work safely on independent unblocked work only if it does not depend on the blocker.
Never use `git reset`, `git clean`, blanket reverts, destructive DB resets, `docker compose down -v`, or broad file deletion. Do not reintroduce captions/subtitles; preserve transcription for internal scoring/semantic analysis; retain the frozen Shorts duration limit unless the owner explicitly changes it.
```


# PART C — Proposed roadmap extension prompts, phases 8–10

The source roadmap does not define these phases. They are included because the user requested a prompt library through Phase 10, but they are **not authoritative existing requirements**. The agent must begin with discovery/planning and map each proposed item to actual evidence. If there is no approved need, produce a no-op report for that item rather than inventing features.


## Main phase prompt — ROADMAP Phase 8 (PROPOSED): Proposed production hardening

```text
You are the ClipForge engineering agent. Phase 8 is a proposed extension, not a feature specification. Do not invent product requirements to fill the roadmap gap.

PROBLEM / OBJECTIVE
This phase is proposed because the source roadmap formally ends at Phase 7. First perform risk discovery and establish explicit acceptance criteria for 8.1–8.5.

FIRST ACTION — DISCOVERY BEFORE IMPLEMENTATION
Read current rules, roadmap, defect register, decision log, implementation status, deployment constraints and evidence from the prior phase. For every proposed child item, determine whether a real issue/requirement exists, whether it is already solved, and what evidence supports doing the work. If no genuine gap exists, verify and close the item without edits. If product intent or target operating environment is ambiguous, document a blocker/proposal; do not implement a guessed product behavior.

APPROACH SELECTION
For each substantiated finding, compare at least two plausible approaches (minimal repair, reuse existing architecture, larger redesign only when necessary). Compare evidence-backed correctness, security/data safety, compatibility, operating cost, reversibility, testability and maintenance. Record decision and rejected alternatives.

PHASE ACCEPTANCE CRITERIA
- Security, reproducibility, credentials, operational errors, recovery assessed.
- Each proposed task mapped to existing defect or evidence.
- No new implementation begins where requirements or authorization are missing.

EXECUTION
Execute each child separately, with the three verification passes, decision log and project-record updates. Do not merge multiple hardening/performance/release tasks into one broad change.

BOUNDARIES
Planning and safe independent tasks only until activation is documented in canonical roadmap.
No destructive production action, no real external publishing, no secrets in logs, no DB resets or deletion of persistent volumes. Stop for owner authorization where a real account, real user data, irreversible migration, or deployment cutover is affected.

EXIT
Mark the extension active only after the canonical roadmap is updated with evidence and the phase has an explicit acceptance definition. Otherwise retain PROPOSED status and report the missing requirement or approval.
```


### Copy-ready prompt — ROADMAP-8.1: Trust-boundary and security audit

```text
You are the ClipForge engineering agent working in `D:\automation video clips\clipforge`.

WORK ITEM: ROADMAP-8.1 — Trust-boundary and security audit
STATE: Reconcile current repository state before acting. Do not assume this item is open just because it appears in the roadmap.

1. PROBLEM / OBJECTIVE
Establish whether local-only services, API endpoints and service-to-service calls match the real threat model.

2. PREFLIGHT AND EVIDENCE COLLECTION
Read `AGENTS.md`, the applicable freeze/rule files, `docs/engineering/PHASE_TRACKER.md`, `MASTER_EXECUTION_LEDGER.md`, `IMPLEMENTATION_STATUS.md`, `ENGINEERING_DEFECT_REGISTER.md`, `PIPELINE_CATALOG_AND_DEPENDENCY_GRAPH.md`, `FRONTEND_PAGE_FEATURE_INVENTORY.md`, `PROJECT_CONTINUITY.md`, and the newest relevant audit/decision-log entries. Read only files relevant to this scope in depth, but reconcile any status claims before editing.
Inspect actual current source, schema, runtime route/client/task contracts, tests and caller/callee relationships. Reproduce the reported behavior with a safe isolated fixture where feasible. Separate VERIFIED FACTS, INFERENCES and UNKNOWNS. Record exact file paths, line ranges, commands and observed outputs.
Inspect bind addresses, CORS, route auth, loopback assumptions, reverse proxies, frontend deployment and secrets flow.
Capture `git status --short`, branch/commit, existing diff/untracked inventory and relevant environment/container identity before editing. Protect all pre-existing changes. Do not assume old hashes, route counts, schema revisions or historic reports still reflect the current environment.

3. COMPARE APPROACHES AND JUSTIFY THE CHOICE
Approach selection method: Compare at least two plausible approaches where meaningful: (A) smallest local repair, (B) reuse an established repository abstraction/pattern, and (C) architectural change only if the first two cannot meet verified requirements. Use evidence, not preference. Evaluate correctness, data safety, architectural consistency, backwards compatibility, idempotency/concurrency, performance, testability, reversibility, scope and maintenance cost. Record the chosen approach and specific reasons each alternative was rejected. If the problem is already solved in current source, choose the no-op verification path.
Before coding, write a small comparison table in the decision log: option; correctness against acceptance criteria; data/security risk; compatibility; concurrency/idempotency; complexity/maintenance; reversibility; evidence for/against. Do not create arbitrary numerical scores. Explain why the chosen approach is proportionate to the proven root cause and why each rejected alternative is inferior for this evidence.
If the current implementation already meets the requirement, choose verification-only and avoid a redundant change. If requirements remain ambiguous and a wrong choice would be consequential, stop at a documented blocker rather than invent behavior.

4. IMPLEMENTATION BOUNDARY
Implement only this work item. Prefer the smallest complete, maintainable fix using existing models, APIs, task lifecycle, storage/artifact and frontend patterns. Avoid duplicate frameworks, helpers, routes, state machines, database fields or tests when an existing abstraction meets the requirement.
Preserve all unrelated behavior and frozen components. Do not remove code based on apparent lack of callers without a call-site/dependency audit. Do not change public API semantics without documenting callers, compatibility plan and tests. Any migration must be justified, forward-only and data-preserving.
Scope-specific acceptance criteria:
- Enumerate exposure surfaces and assets.
- Compare options such as loopback-only, authenticated proxy or application auth; explain trade-offs, do not add architecture by reflex.
- Prioritize externally reachable destructive or credential-bearing endpoints.

5. REQUIRED TESTING
Add focused regression tests for the root cause and relevant negative, failure, boundary, retry, concurrency and stale-state paths. Assert durable database/filesystem/worker state as applicable, not only mocked return values. Use synthetic media, disposable test records and test provider mode. Never publish to real YouTube or destructive-clean real data.
- Verify effective listeners and request access from intended/unintended interfaces in a safe environment.
- Tests for missing/invalid auth if auth exists; document if no auth exists.
- No real secret disclosure.
Run the exact focused suite, relevant regressions, static checks and build/browser/integration tests required by the changed layers. Capture actual commands, counts, exit codes, warning/failure output and environment. Do not claim a test ran if only drafted or launched without a completed result.

6. THREE VERIFICATION PASSES — REQUIRED FOR THIS ITEM
PASS 1 — Implementation verification: review diff against every acceptance criterion; run focused tests and the affected workflow; prove expected state and failure behavior.
PASS 2 — Independent challenge: stop thinking like the implementation author. Re-read the requirement and original defect evidence. Try to falsify the fix with adversarial inputs, conflicts, retries, parallel requests, stale state and failure injection. Compare alternative approaches again. Inspect whether the tests could pass while production is still broken. Fix any issue discovered and record changes since Pass 1.
PASS 3 — Differential re-verification: re-read the final diff and working tree from scratch. Compare final code with Passes 1 and 2, identify all changes introduced after each earlier pass, rerun affected focused tests and relevant regressions against the final tree, and verify reports/status files match the final code. Any new code change invalidates the affected previous pass; repeat it.

7. EXPLICIT SELF-CHALLENGE QUESTIONS
- What concrete evidence proves the original problem existed?
- Why does each changed line/function need to exist?
- What alternative was considered and why was it rejected?
- Could a real production record or untrusted caller reach the test/mock path?
- What happens on failure, retry, concurrency, restart and stale response?
- What does this test prove, and what does it not prove?
- Did I preserve all previous working-tree files and frozen behavior?
- What changed between verification passes and why?
- Which claims remain unverified or depend on an environmental assumption?

8. REQUIRED RECORDS AND FINAL RESPONSE
Update only applicable canonical documents: phase tracker, master ledger, implementation status, defect register, relevant API/frontend/pipeline inventories, audit report and `docs/engineering/AI_DECISION_LOG.md`. Preserve old audit records and append corrections instead of rewriting history. Make status consistent everywhere.
Record work-item ID, before/after working-tree status, root cause, option comparison and rationale, files changed and purpose, relevant hashes if practical, each pass and test result, evidence tier (source/unit/mock/API/in-process/live worker/browser/full E2E), risks, limitations and next dependency.
Report statuses honestly: DELIVERED & VERIFIED, PARTIALLY VERIFIED, BLOCKED or REOPENED. Do not say full E2E without the real required components running together.

9. STOP / CONTINUE RULE
Do not start a different implementation item in parallel or expand this scope to unrelated fixes. Complete all three passes, update records and then continue automatically to the next unblocked item in the master execution queue without waiting for routine approval. Stop only for a real blocker, unresolved high-impact product choice, credential/account action, real publication, destructive action against actual data, or an environment change that requires owner authorization. If blocked, document exact evidence and work safely on independent unblocked work only if it does not depend on the blocker.
Never use `git reset`, `git clean`, blanket reverts, destructive DB resets, `docker compose down -v`, or broad file deletion. Do not reintroduce captions/subtitles; preserve transcription for internal scoring/semantic analysis; retain the frozen Shorts duration limit unless the owner explicitly changes it.
```


### Copy-ready prompt — ROADMAP-8.2: Dependency and container reproducibility

```text
You are the ClipForge engineering agent working in `D:\automation video clips\clipforge`.

WORK ITEM: ROADMAP-8.2 — Dependency and container reproducibility
STATE: Reconcile current repository state before acting. Do not assume this item is open just because it appears in the roadmap.

1. PROBLEM / OBJECTIVE
Verify a clean installation can reproduce the intended app/worker environment.

2. PREFLIGHT AND EVIDENCE COLLECTION
Read `AGENTS.md`, the applicable freeze/rule files, `docs/engineering/PHASE_TRACKER.md`, `MASTER_EXECUTION_LEDGER.md`, `IMPLEMENTATION_STATUS.md`, `ENGINEERING_DEFECT_REGISTER.md`, `PIPELINE_CATALOG_AND_DEPENDENCY_GRAPH.md`, `FRONTEND_PAGE_FEATURE_INVENTORY.md`, `PROJECT_CONTINUITY.md`, and the newest relevant audit/decision-log entries. Read only files relevant to this scope in depth, but reconcile any status claims before editing.
Inspect actual current source, schema, runtime route/client/task contracts, tests and caller/callee relationships. Reproduce the reported behavior with a safe isolated fixture where feasible. Separate VERIFIED FACTS, INFERENCES and UNKNOWNS. Record exact file paths, line ranges, commands and observed outputs.
Inspect lockfiles, Dockerfiles, Compose builds, dependency pins, native tools (FFmpeg/ffprobe), Python/Node versions and container mounts.
Capture `git status --short`, branch/commit, existing diff/untracked inventory and relevant environment/container identity before editing. Protect all pre-existing changes. Do not assume old hashes, route counts, schema revisions or historic reports still reflect the current environment.

3. COMPARE APPROACHES AND JUSTIFY THE CHOICE
Approach selection method: Compare at least two plausible approaches where meaningful: (A) smallest local repair, (B) reuse an established repository abstraction/pattern, and (C) architectural change only if the first two cannot meet verified requirements. Use evidence, not preference. Evaluate correctness, data safety, architectural consistency, backwards compatibility, idempotency/concurrency, performance, testability, reversibility, scope and maintenance cost. Record the chosen approach and specific reasons each alternative was rejected. If the problem is already solved in current source, choose the no-op verification path.
Before coding, write a small comparison table in the decision log: option; correctness against acceptance criteria; data/security risk; compatibility; concurrency/idempotency; complexity/maintenance; reversibility; evidence for/against. Do not create arbitrary numerical scores. Explain why the chosen approach is proportionate to the proven root cause and why each rejected alternative is inferior for this evidence.
If the current implementation already meets the requirement, choose verification-only and avoid a redundant change. If requirements remain ambiguous and a wrong choice would be consequential, stop at a documented blocker rather than invent behavior.

4. IMPLEMENTATION BOUNDARY
Implement only this work item. Prefer the smallest complete, maintainable fix using existing models, APIs, task lifecycle, storage/artifact and frontend patterns. Avoid duplicate frameworks, helpers, routes, state machines, database fields or tests when an existing abstraction meets the requirement.
Preserve all unrelated behavior and frozen components. Do not remove code based on apparent lack of callers without a call-site/dependency audit. Do not change public API semantics without documenting callers, compatibility plan and tests. Any migration must be justified, forward-only and data-preserving.
Scope-specific acceptance criteria:
- Compare current workflow against clean-build, pinned-image, locally installed dependency options.
- Select reproducible approach based on compatibility, cacheability, security and maintenance evidence.
- Avoid broad dependency upgrades.

5. REQUIRED TESTING
Add focused regression tests for the root cause and relevant negative, failure, boundary, retry, concurrency and stale-state paths. Assert durable database/filesystem/worker state as applicable, not only mocked return values. Use synthetic media, disposable test records and test provider mode. Never publish to real YouTube or destructive-clean real data.
- Clean build from known lockfiles; version report; backend/frontend tests; worker imports required task modules.
- Record image/source identity.
Run the exact focused suite, relevant regressions, static checks and build/browser/integration tests required by the changed layers. Capture actual commands, counts, exit codes, warning/failure output and environment. Do not claim a test ran if only drafted or launched without a completed result.

6. THREE VERIFICATION PASSES — REQUIRED FOR THIS ITEM
PASS 1 — Implementation verification: review diff against every acceptance criterion; run focused tests and the affected workflow; prove expected state and failure behavior.
PASS 2 — Independent challenge: stop thinking like the implementation author. Re-read the requirement and original defect evidence. Try to falsify the fix with adversarial inputs, conflicts, retries, parallel requests, stale state and failure injection. Compare alternative approaches again. Inspect whether the tests could pass while production is still broken. Fix any issue discovered and record changes since Pass 1.
PASS 3 — Differential re-verification: re-read the final diff and working tree from scratch. Compare final code with Passes 1 and 2, identify all changes introduced after each earlier pass, rerun affected focused tests and relevant regressions against the final tree, and verify reports/status files match the final code. Any new code change invalidates the affected previous pass; repeat it.

7. EXPLICIT SELF-CHALLENGE QUESTIONS
- What concrete evidence proves the original problem existed?
- Why does each changed line/function need to exist?
- What alternative was considered and why was it rejected?
- Could a real production record or untrusted caller reach the test/mock path?
- What happens on failure, retry, concurrency, restart and stale response?
- What does this test prove, and what does it not prove?
- Did I preserve all previous working-tree files and frozen behavior?
- What changed between verification passes and why?
- Which claims remain unverified or depend on an environmental assumption?

8. REQUIRED RECORDS AND FINAL RESPONSE
Update only applicable canonical documents: phase tracker, master ledger, implementation status, defect register, relevant API/frontend/pipeline inventories, audit report and `docs/engineering/AI_DECISION_LOG.md`. Preserve old audit records and append corrections instead of rewriting history. Make status consistent everywhere.
Record work-item ID, before/after working-tree status, root cause, option comparison and rationale, files changed and purpose, relevant hashes if practical, each pass and test result, evidence tier (source/unit/mock/API/in-process/live worker/browser/full E2E), risks, limitations and next dependency.
Report statuses honestly: DELIVERED & VERIFIED, PARTIALLY VERIFIED, BLOCKED or REOPENED. Do not say full E2E without the real required components running together.

9. STOP / CONTINUE RULE
Do not start a different implementation item in parallel or expand this scope to unrelated fixes. Complete all three passes, update records and then continue automatically to the next unblocked item in the master execution queue without waiting for routine approval. Stop only for a real blocker, unresolved high-impact product choice, credential/account action, real publication, destructive action against actual data, or an environment change that requires owner authorization. If blocked, document exact evidence and work safely on independent unblocked work only if it does not depend on the blocker.
Never use `git reset`, `git clean`, blanket reverts, destructive DB resets, `docker compose down -v`, or broad file deletion. Do not reintroduce captions/subtitles; preserve transcription for internal scoring/semantic analysis; retain the frozen Shorts duration limit unless the owner explicitly changes it.
```


### Copy-ready prompt — ROADMAP-8.3: Secrets and credential lifecycle

```text
You are the ClipForge engineering agent working in `D:\automation video clips\clipforge`.

WORK ITEM: ROADMAP-8.3 — Secrets and credential lifecycle
STATE: Reconcile current repository state before acting. Do not assume this item is open just because it appears in the roadmap.

1. PROBLEM / OBJECTIVE
Review credential storage, redaction, rotation/disconnect and account isolation.

2. PREFLIGHT AND EVIDENCE COLLECTION
Read `AGENTS.md`, the applicable freeze/rule files, `docs/engineering/PHASE_TRACKER.md`, `MASTER_EXECUTION_LEDGER.md`, `IMPLEMENTATION_STATUS.md`, `ENGINEERING_DEFECT_REGISTER.md`, `PIPELINE_CATALOG_AND_DEPENDENCY_GRAPH.md`, `FRONTEND_PAGE_FEATURE_INVENTORY.md`, `PROJECT_CONTINUITY.md`, and the newest relevant audit/decision-log entries. Read only files relevant to this scope in depth, but reconcile any status claims before editing.
Inspect actual current source, schema, runtime route/client/task contracts, tests and caller/callee relationships. Reproduce the reported behavior with a safe isolated fixture where feasible. Separate VERIFIED FACTS, INFERENCES and UNKNOWNS. Record exact file paths, line ranges, commands and observed outputs.
Inventory env values, token paths/mounts, logs, API responses, OAuth refresh, error reporting and backup handling.
Capture `git status --short`, branch/commit, existing diff/untracked inventory and relevant environment/container identity before editing. Protect all pre-existing changes. Do not assume old hashes, route counts, schema revisions or historic reports still reflect the current environment.

3. COMPARE APPROACHES AND JUSTIFY THE CHOICE
Approach selection method: Compare at least two plausible approaches where meaningful: (A) smallest local repair, (B) reuse an established repository abstraction/pattern, and (C) architectural change only if the first two cannot meet verified requirements. Use evidence, not preference. Evaluate correctness, data safety, architectural consistency, backwards compatibility, idempotency/concurrency, performance, testability, reversibility, scope and maintenance cost. Record the chosen approach and specific reasons each alternative was rejected. If the problem is already solved in current source, choose the no-op verification path.
Before coding, write a small comparison table in the decision log: option; correctness against acceptance criteria; data/security risk; compatibility; concurrency/idempotency; complexity/maintenance; reversibility; evidence for/against. Do not create arbitrary numerical scores. Explain why the chosen approach is proportionate to the proven root cause and why each rejected alternative is inferior for this evidence.
If the current implementation already meets the requirement, choose verification-only and avoid a redundant change. If requirements remain ambiguous and a wrong choice would be consequential, stop at a documented blocker rather than invent behavior.

4. IMPLEMENTATION BOUNDARY
Implement only this work item. Prefer the smallest complete, maintainable fix using existing models, APIs, task lifecycle, storage/artifact and frontend patterns. Avoid duplicate frameworks, helpers, routes, state machines, database fields or tests when an existing abstraction meets the requirement.
Preserve all unrelated behavior and frozen components. Do not remove code based on apparent lack of callers without a call-site/dependency audit. Do not change public API semantics without documenting callers, compatibility plan and tests. Any migration must be justified, forward-only and data-preserving.
Scope-specific acceptance criteria:
- Classify each secret and intended readers.
- Compare storage/redaction/rotation choices with project architecture.
- No credentials printed into logs or included in generated artifacts.

5. REQUIRED TESTING
Add focused regression tests for the root cause and relevant negative, failure, boundary, retry, concurrency and stale-state paths. Assert durable database/filesystem/worker state as applicable, not only mocked return values. Use synthetic media, disposable test records and test provider mode. Never publish to real YouTube or destructive-clean real data.
- Static secret scan, response/log redaction tests, per-account isolation and token persistence test with fake credentials.
- Document rotation and incident response.
Run the exact focused suite, relevant regressions, static checks and build/browser/integration tests required by the changed layers. Capture actual commands, counts, exit codes, warning/failure output and environment. Do not claim a test ran if only drafted or launched without a completed result.

6. THREE VERIFICATION PASSES — REQUIRED FOR THIS ITEM
PASS 1 — Implementation verification: review diff against every acceptance criterion; run focused tests and the affected workflow; prove expected state and failure behavior.
PASS 2 — Independent challenge: stop thinking like the implementation author. Re-read the requirement and original defect evidence. Try to falsify the fix with adversarial inputs, conflicts, retries, parallel requests, stale state and failure injection. Compare alternative approaches again. Inspect whether the tests could pass while production is still broken. Fix any issue discovered and record changes since Pass 1.
PASS 3 — Differential re-verification: re-read the final diff and working tree from scratch. Compare final code with Passes 1 and 2, identify all changes introduced after each earlier pass, rerun affected focused tests and relevant regressions against the final tree, and verify reports/status files match the final code. Any new code change invalidates the affected previous pass; repeat it.

7. EXPLICIT SELF-CHALLENGE QUESTIONS
- What concrete evidence proves the original problem existed?
- Why does each changed line/function need to exist?
- What alternative was considered and why was it rejected?
- Could a real production record or untrusted caller reach the test/mock path?
- What happens on failure, retry, concurrency, restart and stale response?
- What does this test prove, and what does it not prove?
- Did I preserve all previous working-tree files and frozen behavior?
- What changed between verification passes and why?
- Which claims remain unverified or depend on an environmental assumption?

8. REQUIRED RECORDS AND FINAL RESPONSE
Update only applicable canonical documents: phase tracker, master ledger, implementation status, defect register, relevant API/frontend/pipeline inventories, audit report and `docs/engineering/AI_DECISION_LOG.md`. Preserve old audit records and append corrections instead of rewriting history. Make status consistent everywhere.
Record work-item ID, before/after working-tree status, root cause, option comparison and rationale, files changed and purpose, relevant hashes if practical, each pass and test result, evidence tier (source/unit/mock/API/in-process/live worker/browser/full E2E), risks, limitations and next dependency.
Report statuses honestly: DELIVERED & VERIFIED, PARTIALLY VERIFIED, BLOCKED or REOPENED. Do not say full E2E without the real required components running together.

9. STOP / CONTINUE RULE
Do not start a different implementation item in parallel or expand this scope to unrelated fixes. Complete all three passes, update records and then continue automatically to the next unblocked item in the master execution queue without waiting for routine approval. Stop only for a real blocker, unresolved high-impact product choice, credential/account action, real publication, destructive action against actual data, or an environment change that requires owner authorization. If blocked, document exact evidence and work safely on independent unblocked work only if it does not depend on the blocker.
Never use `git reset`, `git clean`, blanket reverts, destructive DB resets, `docker compose down -v`, or broad file deletion. Do not reintroduce captions/subtitles; preserve transcription for internal scoring/semantic analysis; retain the frozen Shorts duration limit unless the owner explicitly changes it.
```


### Copy-ready prompt — ROADMAP-8.4: Error handling and operational health

```text
You are the ClipForge engineering agent working in `D:\automation video clips\clipforge`.

WORK ITEM: ROADMAP-8.4 — Error handling and operational health
STATE: Reconcile current repository state before acting. Do not assume this item is open just because it appears in the roadmap.

1. PROBLEM / OBJECTIVE
Make task and API failures diagnosable without false success or secret leakage.

2. PREFLIGHT AND EVIDENCE COLLECTION
Read `AGENTS.md`, the applicable freeze/rule files, `docs/engineering/PHASE_TRACKER.md`, `MASTER_EXECUTION_LEDGER.md`, `IMPLEMENTATION_STATUS.md`, `ENGINEERING_DEFECT_REGISTER.md`, `PIPELINE_CATALOG_AND_DEPENDENCY_GRAPH.md`, `FRONTEND_PAGE_FEATURE_INVENTORY.md`, `PROJECT_CONTINUITY.md`, and the newest relevant audit/decision-log entries. Read only files relevant to this scope in depth, but reconcile any status claims before editing.
Inspect actual current source, schema, runtime route/client/task contracts, tests and caller/callee relationships. Reproduce the reported behavior with a safe isolated fixture where feasible. Separate VERIFIED FACTS, INFERENCES and UNKNOWNS. Record exact file paths, line ranges, commands and observed outputs.
Inspect log structure, request/task IDs, health checks, retry loops, timeouts, status transitions and frontend errors.
Capture `git status --short`, branch/commit, existing diff/untracked inventory and relevant environment/container identity before editing. Protect all pre-existing changes. Do not assume old hashes, route counts, schema revisions or historic reports still reflect the current environment.

3. COMPARE APPROACHES AND JUSTIFY THE CHOICE
Approach selection method: Compare at least two plausible approaches where meaningful: (A) smallest local repair, (B) reuse an established repository abstraction/pattern, and (C) architectural change only if the first two cannot meet verified requirements. Use evidence, not preference. Evaluate correctness, data safety, architectural consistency, backwards compatibility, idempotency/concurrency, performance, testability, reversibility, scope and maintenance cost. Record the chosen approach and specific reasons each alternative was rejected. If the problem is already solved in current source, choose the no-op verification path.
Before coding, write a small comparison table in the decision log: option; correctness against acceptance criteria; data/security risk; compatibility; concurrency/idempotency; complexity/maintenance; reversibility; evidence for/against. Do not create arbitrary numerical scores. Explain why the chosen approach is proportionate to the proven root cause and why each rejected alternative is inferior for this evidence.
If the current implementation already meets the requirement, choose verification-only and avoid a redundant change. If requirements remain ambiguous and a wrong choice would be consequential, stop at a documented blocker rather than invent behavior.

4. IMPLEMENTATION BOUNDARY
Implement only this work item. Prefer the smallest complete, maintainable fix using existing models, APIs, task lifecycle, storage/artifact and frontend patterns. Avoid duplicate frameworks, helpers, routes, state machines, database fields or tests when an existing abstraction meets the requirement.
Preserve all unrelated behavior and frozen components. Do not remove code based on apparent lack of callers without a call-site/dependency audit. Do not change public API semantics without documenting callers, compatibility plan and tests. Any migration must be justified, forward-only and data-preserving.
Scope-specific acceptance criteria:
- Define actionable error classes and correlation IDs reusing current conventions.
- Ensure retries are bounded and idempotent.
- Keep user-visible errors safe while retaining useful internal context.

5. REQUIRED TESTING
Add focused regression tests for the root cause and relevant negative, failure, boundary, retry, concurrency and stale-state paths. Assert durable database/filesystem/worker state as applicable, not only mocked return values. Use synthetic media, disposable test records and test provider mode. Never publish to real YouTube or destructive-clean real data.
- Timeout, provider failure, DB failure, worker unavailable, malformed input and redaction tests.
- Verify task/UI/DB status agree.
Run the exact focused suite, relevant regressions, static checks and build/browser/integration tests required by the changed layers. Capture actual commands, counts, exit codes, warning/failure output and environment. Do not claim a test ran if only drafted or launched without a completed result.

6. THREE VERIFICATION PASSES — REQUIRED FOR THIS ITEM
PASS 1 — Implementation verification: review diff against every acceptance criterion; run focused tests and the affected workflow; prove expected state and failure behavior.
PASS 2 — Independent challenge: stop thinking like the implementation author. Re-read the requirement and original defect evidence. Try to falsify the fix with adversarial inputs, conflicts, retries, parallel requests, stale state and failure injection. Compare alternative approaches again. Inspect whether the tests could pass while production is still broken. Fix any issue discovered and record changes since Pass 1.
PASS 3 — Differential re-verification: re-read the final diff and working tree from scratch. Compare final code with Passes 1 and 2, identify all changes introduced after each earlier pass, rerun affected focused tests and relevant regressions against the final tree, and verify reports/status files match the final code. Any new code change invalidates the affected previous pass; repeat it.

7. EXPLICIT SELF-CHALLENGE QUESTIONS
- What concrete evidence proves the original problem existed?
- Why does each changed line/function need to exist?
- What alternative was considered and why was it rejected?
- Could a real production record or untrusted caller reach the test/mock path?
- What happens on failure, retry, concurrency, restart and stale response?
- What does this test prove, and what does it not prove?
- Did I preserve all previous working-tree files and frozen behavior?
- What changed between verification passes and why?
- Which claims remain unverified or depend on an environmental assumption?

8. REQUIRED RECORDS AND FINAL RESPONSE
Update only applicable canonical documents: phase tracker, master ledger, implementation status, defect register, relevant API/frontend/pipeline inventories, audit report and `docs/engineering/AI_DECISION_LOG.md`. Preserve old audit records and append corrections instead of rewriting history. Make status consistent everywhere.
Record work-item ID, before/after working-tree status, root cause, option comparison and rationale, files changed and purpose, relevant hashes if practical, each pass and test result, evidence tier (source/unit/mock/API/in-process/live worker/browser/full E2E), risks, limitations and next dependency.
Report statuses honestly: DELIVERED & VERIFIED, PARTIALLY VERIFIED, BLOCKED or REOPENED. Do not say full E2E without the real required components running together.

9. STOP / CONTINUE RULE
Do not start a different implementation item in parallel or expand this scope to unrelated fixes. Complete all three passes, update records and then continue automatically to the next unblocked item in the master execution queue without waiting for routine approval. Stop only for a real blocker, unresolved high-impact product choice, credential/account action, real publication, destructive action against actual data, or an environment change that requires owner authorization. If blocked, document exact evidence and work safely on independent unblocked work only if it does not depend on the blocker.
Never use `git reset`, `git clean`, blanket reverts, destructive DB resets, `docker compose down -v`, or broad file deletion. Do not reintroduce captions/subtitles; preserve transcription for internal scoring/semantic analysis; retain the frozen Shorts duration limit unless the owner explicitly changes it.
```


### Copy-ready prompt — ROADMAP-8.5: Backup, restore and recovery drill

```text
You are the ClipForge engineering agent working in `D:\automation video clips\clipforge`.

WORK ITEM: ROADMAP-8.5 — Backup, restore and recovery drill
STATE: Reconcile current repository state before acting. Do not assume this item is open just because it appears in the roadmap.

1. PROBLEM / OBJECTIVE
Demonstrate recoverability of database and persistent media without modifying primary data.

2. PREFLIGHT AND EVIDENCE COLLECTION
Read `AGENTS.md`, the applicable freeze/rule files, `docs/engineering/PHASE_TRACKER.md`, `MASTER_EXECUTION_LEDGER.md`, `IMPLEMENTATION_STATUS.md`, `ENGINEERING_DEFECT_REGISTER.md`, `PIPELINE_CATALOG_AND_DEPENDENCY_GRAPH.md`, `FRONTEND_PAGE_FEATURE_INVENTORY.md`, `PROJECT_CONTINUITY.md`, and the newest relevant audit/decision-log entries. Read only files relevant to this scope in depth, but reconcile any status claims before editing.
Inspect actual current source, schema, runtime route/client/task contracts, tests and caller/callee relationships. Reproduce the reported behavior with a safe isolated fixture where feasible. Separate VERIFIED FACTS, INFERENCES and UNKNOWNS. Record exact file paths, line ranges, commands and observed outputs.
Inspect backup procedures, volumes, database restore method, file manifests, encryption/retention and recovery documentation.
Capture `git status --short`, branch/commit, existing diff/untracked inventory and relevant environment/container identity before editing. Protect all pre-existing changes. Do not assume old hashes, route counts, schema revisions or historic reports still reflect the current environment.

3. COMPARE APPROACHES AND JUSTIFY THE CHOICE
Approach selection method: Compare at least two plausible approaches where meaningful: (A) smallest local repair, (B) reuse an established repository abstraction/pattern, and (C) architectural change only if the first two cannot meet verified requirements. Use evidence, not preference. Evaluate correctness, data safety, architectural consistency, backwards compatibility, idempotency/concurrency, performance, testability, reversibility, scope and maintenance cost. Record the chosen approach and specific reasons each alternative was rejected. If the problem is already solved in current source, choose the no-op verification path.
Before coding, write a small comparison table in the decision log: option; correctness against acceptance criteria; data/security risk; compatibility; concurrency/idempotency; complexity/maintenance; reversibility; evidence for/against. Do not create arbitrary numerical scores. Explain why the chosen approach is proportionate to the proven root cause and why each rejected alternative is inferior for this evidence.
If the current implementation already meets the requirement, choose verification-only and avoid a redundant change. If requirements remain ambiguous and a wrong choice would be consequential, stop at a documented blocker rather than invent behavior.

4. IMPLEMENTATION BOUNDARY
Implement only this work item. Prefer the smallest complete, maintainable fix using existing models, APIs, task lifecycle, storage/artifact and frontend patterns. Avoid duplicate frameworks, helpers, routes, state machines, database fields or tests when an existing abstraction meets the requirement.
Preserve all unrelated behavior and frozen components. Do not remove code based on apparent lack of callers without a call-site/dependency audit. Do not change public API semantics without documenting callers, compatibility plan and tests. Any migration must be justified, forward-only and data-preserving.
Scope-specific acceptance criteria:
- Design a restore rehearsal against disposable targets first.
- Compare snapshot/backup options against consistency across DB and media.
- Verify checksums and reference consistency.

5. REQUIRED TESTING
Add focused regression tests for the root cause and relevant negative, failure, boundary, retry, concurrency and stale-state paths. Assert durable database/filesystem/worker state as applicable, not only mocked return values. Use synthetic media, disposable test records and test provider mode. Never publish to real YouTube or destructive-clean real data.
- Restore into isolated environment; validate migration head, core rows, file hashes, storage key resolution and service boot.
- Record RPO/RTO measured in rehearsal rather than inventing targets.
Run the exact focused suite, relevant regressions, static checks and build/browser/integration tests required by the changed layers. Capture actual commands, counts, exit codes, warning/failure output and environment. Do not claim a test ran if only drafted or launched without a completed result.

6. THREE VERIFICATION PASSES — REQUIRED FOR THIS ITEM
PASS 1 — Implementation verification: review diff against every acceptance criterion; run focused tests and the affected workflow; prove expected state and failure behavior.
PASS 2 — Independent challenge: stop thinking like the implementation author. Re-read the requirement and original defect evidence. Try to falsify the fix with adversarial inputs, conflicts, retries, parallel requests, stale state and failure injection. Compare alternative approaches again. Inspect whether the tests could pass while production is still broken. Fix any issue discovered and record changes since Pass 1.
PASS 3 — Differential re-verification: re-read the final diff and working tree from scratch. Compare final code with Passes 1 and 2, identify all changes introduced after each earlier pass, rerun affected focused tests and relevant regressions against the final tree, and verify reports/status files match the final code. Any new code change invalidates the affected previous pass; repeat it.

7. EXPLICIT SELF-CHALLENGE QUESTIONS
- What concrete evidence proves the original problem existed?
- Why does each changed line/function need to exist?
- What alternative was considered and why was it rejected?
- Could a real production record or untrusted caller reach the test/mock path?
- What happens on failure, retry, concurrency, restart and stale response?
- What does this test prove, and what does it not prove?
- Did I preserve all previous working-tree files and frozen behavior?
- What changed between verification passes and why?
- Which claims remain unverified or depend on an environmental assumption?

8. REQUIRED RECORDS AND FINAL RESPONSE
Update only applicable canonical documents: phase tracker, master ledger, implementation status, defect register, relevant API/frontend/pipeline inventories, audit report and `docs/engineering/AI_DECISION_LOG.md`. Preserve old audit records and append corrections instead of rewriting history. Make status consistent everywhere.
Record work-item ID, before/after working-tree status, root cause, option comparison and rationale, files changed and purpose, relevant hashes if practical, each pass and test result, evidence tier (source/unit/mock/API/in-process/live worker/browser/full E2E), risks, limitations and next dependency.
Report statuses honestly: DELIVERED & VERIFIED, PARTIALLY VERIFIED, BLOCKED or REOPENED. Do not say full E2E without the real required components running together.

9. STOP / CONTINUE RULE
Do not start a different implementation item in parallel or expand this scope to unrelated fixes. Complete all three passes, update records and then continue automatically to the next unblocked item in the master execution queue without waiting for routine approval. Stop only for a real blocker, unresolved high-impact product choice, credential/account action, real publication, destructive action against actual data, or an environment change that requires owner authorization. If blocked, document exact evidence and work safely on independent unblocked work only if it does not depend on the blocker.
Never use `git reset`, `git clean`, blanket reverts, destructive DB resets, `docker compose down -v`, or broad file deletion. Do not reintroduce captions/subtitles; preserve transcription for internal scoring/semantic analysis; retain the frozen Shorts duration limit unless the owner explicitly changes it.
```


## Main phase prompt — ROADMAP Phase 9 (PROPOSED): Proposed performance and reliability

```text
You are the ClipForge engineering agent. Phase 9 is a proposed extension, not a feature specification. Do not invent product requirements to fill the roadmap gap.

PROBLEM / OBJECTIVE
This proposed phase begins with measurement and maps 9.1–9.5 to measured bottlenecks.

FIRST ACTION — DISCOVERY BEFORE IMPLEMENTATION
Read current rules, roadmap, defect register, decision log, implementation status, deployment constraints and evidence from the prior phase. For every proposed child item, determine whether a real issue/requirement exists, whether it is already solved, and what evidence supports doing the work. If no genuine gap exists, verify and close the item without edits. If product intent or target operating environment is ambiguous, document a blocker/proposal; do not implement a guessed product behavior.

APPROACH SELECTION
For each substantiated finding, compare at least two plausible approaches (minimal repair, reuse existing architecture, larger redesign only when necessary). Compare evidence-backed correctness, security/data safety, compatibility, operating cost, reversibility, testability and maintenance. Record decision and rejected alternatives.

PHASE ACCEPTANCE CRITERIA
- Baseline measurements exist.
- Changes have quantifiable acceptance criteria.
- No unjustified concurrency/architecture changes.

EXECUTION
Execute each child separately, with the three verification passes, decision log and project-record updates. Do not merge multiple hardening/performance/release tasks into one broad change.

BOUNDARIES
No load testing against real accounts or data; no performance tuning by intuition.
No destructive production action, no real external publishing, no secrets in logs, no DB resets or deletion of persistent volumes. Stop for owner authorization where a real account, real user data, irreversible migration, or deployment cutover is affected.

EXIT
Mark the extension active only after the canonical roadmap is updated with evidence and the phase has an explicit acceptance definition. Otherwise retain PROPOSED status and report the missing requirement or approval.
```


### Copy-ready prompt — ROADMAP-9.1: Queue and worker capacity baseline

```text
You are the ClipForge engineering agent working in `D:\automation video clips\clipforge`.

WORK ITEM: ROADMAP-9.1 — Queue and worker capacity baseline
STATE: Reconcile current repository state before acting. Do not assume this item is open just because it appears in the roadmap.

1. PROBLEM / OBJECTIVE
Measure throughput, queue latency and concurrency limits across worker types.

2. PREFLIGHT AND EVIDENCE COLLECTION
Read `AGENTS.md`, the applicable freeze/rule files, `docs/engineering/PHASE_TRACKER.md`, `MASTER_EXECUTION_LEDGER.md`, `IMPLEMENTATION_STATUS.md`, `ENGINEERING_DEFECT_REGISTER.md`, `PIPELINE_CATALOG_AND_DEPENDENCY_GRAPH.md`, `FRONTEND_PAGE_FEATURE_INVENTORY.md`, `PROJECT_CONTINUITY.md`, and the newest relevant audit/decision-log entries. Read only files relevant to this scope in depth, but reconcile any status claims before editing.
Inspect actual current source, schema, runtime route/client/task contracts, tests and caller/callee relationships. Reproduce the reported behavior with a safe isolated fixture where feasible. Separate VERIFIED FACTS, INFERENCES and UNKNOWNS. Record exact file paths, line ranges, commands and observed outputs.
Inspect Celery config, task routing, concurrency, CPU/memory, provider limits and current workload patterns.
Capture `git status --short`, branch/commit, existing diff/untracked inventory and relevant environment/container identity before editing. Protect all pre-existing changes. Do not assume old hashes, route counts, schema revisions or historic reports still reflect the current environment.

3. COMPARE APPROACHES AND JUSTIFY THE CHOICE
Approach selection method: Compare at least two plausible approaches where meaningful: (A) smallest local repair, (B) reuse an established repository abstraction/pattern, and (C) architectural change only if the first two cannot meet verified requirements. Use evidence, not preference. Evaluate correctness, data safety, architectural consistency, backwards compatibility, idempotency/concurrency, performance, testability, reversibility, scope and maintenance cost. Record the chosen approach and specific reasons each alternative was rejected. If the problem is already solved in current source, choose the no-op verification path.
Before coding, write a small comparison table in the decision log: option; correctness against acceptance criteria; data/security risk; compatibility; concurrency/idempotency; complexity/maintenance; reversibility; evidence for/against. Do not create arbitrary numerical scores. Explain why the chosen approach is proportionate to the proven root cause and why each rejected alternative is inferior for this evidence.
If the current implementation already meets the requirement, choose verification-only and avoid a redundant change. If requirements remain ambiguous and a wrong choice would be consequential, stop at a documented blocker rather than invent behavior.

4. IMPLEMENTATION BOUNDARY
Implement only this work item. Prefer the smallest complete, maintainable fix using existing models, APIs, task lifecycle, storage/artifact and frontend patterns. Avoid duplicate frameworks, helpers, routes, state machines, database fields or tests when an existing abstraction meets the requirement.
Preserve all unrelated behavior and frozen components. Do not remove code based on apparent lack of callers without a call-site/dependency audit. Do not change public API semantics without documenting callers, compatibility plan and tests. Any migration must be justified, forward-only and data-preserving.
Scope-specific acceptance criteria:
- Run bounded representative synthetic jobs.
- Compare serial/concurrent tuning using output correctness and resource pressure.
- Set no guessed concurrency defaults without measurements.

5. REQUIRED TESTING
Add focused regression tests for the root cause and relevant negative, failure, boundary, retry, concurrency and stale-state paths. Assert durable database/filesystem/worker state as applicable, not only mocked return values. Use synthetic media, disposable test records and test provider mode. Never publish to real YouTube or destructive-clean real data.
- Capture queue wait, runtime, peak resource use, failures and tail latency.
- Verify queue order and idempotency remain intact.
Run the exact focused suite, relevant regressions, static checks and build/browser/integration tests required by the changed layers. Capture actual commands, counts, exit codes, warning/failure output and environment. Do not claim a test ran if only drafted or launched without a completed result.

6. THREE VERIFICATION PASSES — REQUIRED FOR THIS ITEM
PASS 1 — Implementation verification: review diff against every acceptance criterion; run focused tests and the affected workflow; prove expected state and failure behavior.
PASS 2 — Independent challenge: stop thinking like the implementation author. Re-read the requirement and original defect evidence. Try to falsify the fix with adversarial inputs, conflicts, retries, parallel requests, stale state and failure injection. Compare alternative approaches again. Inspect whether the tests could pass while production is still broken. Fix any issue discovered and record changes since Pass 1.
PASS 3 — Differential re-verification: re-read the final diff and working tree from scratch. Compare final code with Passes 1 and 2, identify all changes introduced after each earlier pass, rerun affected focused tests and relevant regressions against the final tree, and verify reports/status files match the final code. Any new code change invalidates the affected previous pass; repeat it.

7. EXPLICIT SELF-CHALLENGE QUESTIONS
- What concrete evidence proves the original problem existed?
- Why does each changed line/function need to exist?
- What alternative was considered and why was it rejected?
- Could a real production record or untrusted caller reach the test/mock path?
- What happens on failure, retry, concurrency, restart and stale response?
- What does this test prove, and what does it not prove?
- Did I preserve all previous working-tree files and frozen behavior?
- What changed between verification passes and why?
- Which claims remain unverified or depend on an environmental assumption?

8. REQUIRED RECORDS AND FINAL RESPONSE
Update only applicable canonical documents: phase tracker, master ledger, implementation status, defect register, relevant API/frontend/pipeline inventories, audit report and `docs/engineering/AI_DECISION_LOG.md`. Preserve old audit records and append corrections instead of rewriting history. Make status consistent everywhere.
Record work-item ID, before/after working-tree status, root cause, option comparison and rationale, files changed and purpose, relevant hashes if practical, each pass and test result, evidence tier (source/unit/mock/API/in-process/live worker/browser/full E2E), risks, limitations and next dependency.
Report statuses honestly: DELIVERED & VERIFIED, PARTIALLY VERIFIED, BLOCKED or REOPENED. Do not say full E2E without the real required components running together.

9. STOP / CONTINUE RULE
Do not start a different implementation item in parallel or expand this scope to unrelated fixes. Complete all three passes, update records and then continue automatically to the next unblocked item in the master execution queue without waiting for routine approval. Stop only for a real blocker, unresolved high-impact product choice, credential/account action, real publication, destructive action against actual data, or an environment change that requires owner authorization. If blocked, document exact evidence and work safely on independent unblocked work only if it does not depend on the blocker.
Never use `git reset`, `git clean`, blanket reverts, destructive DB resets, `docker compose down -v`, or broad file deletion. Do not reintroduce captions/subtitles; preserve transcription for internal scoring/semantic analysis; retain the frozen Shorts duration limit unless the owner explicitly changes it.
```


### Copy-ready prompt — ROADMAP-9.2: Timeouts, retries and idempotency

```text
You are the ClipForge engineering agent working in `D:\automation video clips\clipforge`.

WORK ITEM: ROADMAP-9.2 — Timeouts, retries and idempotency
STATE: Reconcile current repository state before acting. Do not assume this item is open just because it appears in the roadmap.

1. PROBLEM / OBJECTIVE
Make external calls and task retries bounded and recoverable.

2. PREFLIGHT AND EVIDENCE COLLECTION
Read `AGENTS.md`, the applicable freeze/rule files, `docs/engineering/PHASE_TRACKER.md`, `MASTER_EXECUTION_LEDGER.md`, `IMPLEMENTATION_STATUS.md`, `ENGINEERING_DEFECT_REGISTER.md`, `PIPELINE_CATALOG_AND_DEPENDENCY_GRAPH.md`, `FRONTEND_PAGE_FEATURE_INVENTORY.md`, `PROJECT_CONTINUITY.md`, and the newest relevant audit/decision-log entries. Read only files relevant to this scope in depth, but reconcile any status claims before editing.
Inspect actual current source, schema, runtime route/client/task contracts, tests and caller/callee relationships. Reproduce the reported behavior with a safe isolated fixture where feasible. Separate VERIFIED FACTS, INFERENCES and UNKNOWNS. Record exact file paths, line ranges, commands and observed outputs.
Inventory network calls, FFmpeg subprocesses, provider timeouts, Celery retry policy and duplicate-output handling.
Capture `git status --short`, branch/commit, existing diff/untracked inventory and relevant environment/container identity before editing. Protect all pre-existing changes. Do not assume old hashes, route counts, schema revisions or historic reports still reflect the current environment.

3. COMPARE APPROACHES AND JUSTIFY THE CHOICE
Approach selection method: Compare at least two plausible approaches where meaningful: (A) smallest local repair, (B) reuse an established repository abstraction/pattern, and (C) architectural change only if the first two cannot meet verified requirements. Use evidence, not preference. Evaluate correctness, data safety, architectural consistency, backwards compatibility, idempotency/concurrency, performance, testability, reversibility, scope and maintenance cost. Record the chosen approach and specific reasons each alternative was rejected. If the problem is already solved in current source, choose the no-op verification path.
Before coding, write a small comparison table in the decision log: option; correctness against acceptance criteria; data/security risk; compatibility; concurrency/idempotency; complexity/maintenance; reversibility; evidence for/against. Do not create arbitrary numerical scores. Explain why the chosen approach is proportionate to the proven root cause and why each rejected alternative is inferior for this evidence.
If the current implementation already meets the requirement, choose verification-only and avoid a redundant change. If requirements remain ambiguous and a wrong choice would be consequential, stop at a documented blocker rather than invent behavior.

4. IMPLEMENTATION BOUNDARY
Implement only this work item. Prefer the smallest complete, maintainable fix using existing models, APIs, task lifecycle, storage/artifact and frontend patterns. Avoid duplicate frameworks, helpers, routes, state machines, database fields or tests when an existing abstraction meets the requirement.
Preserve all unrelated behavior and frozen components. Do not remove code based on apparent lack of callers without a call-site/dependency audit. Do not change public API semantics without documenting callers, compatibility plan and tests. Any migration must be justified, forward-only and data-preserving.
Scope-specific acceptance criteria:
- Classify errors transient/permanent/cancelled.
- Compare retry placement and backoff with current idempotency model.
- Avoid retrying irreversible publish calls without provider-safe identity.

5. REQUIRED TESTING
Add focused regression tests for the root cause and relevant negative, failure, boundary, retry, concurrency and stale-state paths. Assert durable database/filesystem/worker state as applicable, not only mocked return values. Use synthetic media, disposable test records and test provider mode. Never publish to real YouTube or destructive-clean real data.
- Hung provider, timeout, retry budget exhausted, worker restart, duplicate task and partial success.
- Check no duplicates/orphan files and truthful task terminal states.
Run the exact focused suite, relevant regressions, static checks and build/browser/integration tests required by the changed layers. Capture actual commands, counts, exit codes, warning/failure output and environment. Do not claim a test ran if only drafted or launched without a completed result.

6. THREE VERIFICATION PASSES — REQUIRED FOR THIS ITEM
PASS 1 — Implementation verification: review diff against every acceptance criterion; run focused tests and the affected workflow; prove expected state and failure behavior.
PASS 2 — Independent challenge: stop thinking like the implementation author. Re-read the requirement and original defect evidence. Try to falsify the fix with adversarial inputs, conflicts, retries, parallel requests, stale state and failure injection. Compare alternative approaches again. Inspect whether the tests could pass while production is still broken. Fix any issue discovered and record changes since Pass 1.
PASS 3 — Differential re-verification: re-read the final diff and working tree from scratch. Compare final code with Passes 1 and 2, identify all changes introduced after each earlier pass, rerun affected focused tests and relevant regressions against the final tree, and verify reports/status files match the final code. Any new code change invalidates the affected previous pass; repeat it.

7. EXPLICIT SELF-CHALLENGE QUESTIONS
- What concrete evidence proves the original problem existed?
- Why does each changed line/function need to exist?
- What alternative was considered and why was it rejected?
- Could a real production record or untrusted caller reach the test/mock path?
- What happens on failure, retry, concurrency, restart and stale response?
- What does this test prove, and what does it not prove?
- Did I preserve all previous working-tree files and frozen behavior?
- What changed between verification passes and why?
- Which claims remain unverified or depend on an environmental assumption?

8. REQUIRED RECORDS AND FINAL RESPONSE
Update only applicable canonical documents: phase tracker, master ledger, implementation status, defect register, relevant API/frontend/pipeline inventories, audit report and `docs/engineering/AI_DECISION_LOG.md`. Preserve old audit records and append corrections instead of rewriting history. Make status consistent everywhere.
Record work-item ID, before/after working-tree status, root cause, option comparison and rationale, files changed and purpose, relevant hashes if practical, each pass and test result, evidence tier (source/unit/mock/API/in-process/live worker/browser/full E2E), risks, limitations and next dependency.
Report statuses honestly: DELIVERED & VERIFIED, PARTIALLY VERIFIED, BLOCKED or REOPENED. Do not say full E2E without the real required components running together.

9. STOP / CONTINUE RULE
Do not start a different implementation item in parallel or expand this scope to unrelated fixes. Complete all three passes, update records and then continue automatically to the next unblocked item in the master execution queue without waiting for routine approval. Stop only for a real blocker, unresolved high-impact product choice, credential/account action, real publication, destructive action against actual data, or an environment change that requires owner authorization. If blocked, document exact evidence and work safely on independent unblocked work only if it does not depend on the blocker.
Never use `git reset`, `git clean`, blanket reverts, destructive DB resets, `docker compose down -v`, or broad file deletion. Do not reintroduce captions/subtitles; preserve transcription for internal scoring/semantic analysis; retain the frozen Shorts duration limit unless the owner explicitly changes it.
```


### Copy-ready prompt — ROADMAP-9.3: Storage lifecycle and artifact reconciliation

```text
You are the ClipForge engineering agent working in `D:\automation video clips\clipforge`.

WORK ITEM: ROADMAP-9.3 — Storage lifecycle and artifact reconciliation
STATE: Reconcile current repository state before acting. Do not assume this item is open just because it appears in the roadmap.

1. PROBLEM / OBJECTIVE
Measure and detect orphan artifacts, missing files and stale temporary records without unsafe deletion.

2. PREFLIGHT AND EVIDENCE COLLECTION
Read `AGENTS.md`, the applicable freeze/rule files, `docs/engineering/PHASE_TRACKER.md`, `MASTER_EXECUTION_LEDGER.md`, `IMPLEMENTATION_STATUS.md`, `ENGINEERING_DEFECT_REGISTER.md`, `PIPELINE_CATALOG_AND_DEPENDENCY_GRAPH.md`, `FRONTEND_PAGE_FEATURE_INVENTORY.md`, `PROJECT_CONTINUITY.md`, and the newest relevant audit/decision-log entries. Read only files relevant to this scope in depth, but reconcile any status claims before editing.
Inspect actual current source, schema, runtime route/client/task contracts, tests and caller/callee relationships. Reproduce the reported behavior with a safe isolated fixture where feasible. Separate VERIFIED FACTS, INFERENCES and UNKNOWNS. Record exact file paths, line ranges, commands and observed outputs.
Inspect artifact manager, keys, reservations, quarantine, temp naming, retention policies and existing safe cleanup.
Capture `git status --short`, branch/commit, existing diff/untracked inventory and relevant environment/container identity before editing. Protect all pre-existing changes. Do not assume old hashes, route counts, schema revisions or historic reports still reflect the current environment.

3. COMPARE APPROACHES AND JUSTIFY THE CHOICE
Approach selection method: Compare at least two plausible approaches where meaningful: (A) smallest local repair, (B) reuse an established repository abstraction/pattern, and (C) architectural change only if the first two cannot meet verified requirements. Use evidence, not preference. Evaluate correctness, data safety, architectural consistency, backwards compatibility, idempotency/concurrency, performance, testability, reversibility, scope and maintenance cost. Record the chosen approach and specific reasons each alternative was rejected. If the problem is already solved in current source, choose the no-op verification path.
Before coding, write a small comparison table in the decision log: option; correctness against acceptance criteria; data/security risk; compatibility; concurrency/idempotency; complexity/maintenance; reversibility; evidence for/against. Do not create arbitrary numerical scores. Explain why the chosen approach is proportionate to the proven root cause and why each rejected alternative is inferior for this evidence.
If the current implementation already meets the requirement, choose verification-only and avoid a redundant change. If requirements remain ambiguous and a wrong choice would be consequential, stop at a documented blocker rather than invent behavior.

4. IMPLEMENTATION BOUNDARY
Implement only this work item. Prefer the smallest complete, maintainable fix using existing models, APIs, task lifecycle, storage/artifact and frontend patterns. Avoid duplicate frameworks, helpers, routes, state machines, database fields or tests when an existing abstraction meets the requirement.
Preserve all unrelated behavior and frozen components. Do not remove code based on apparent lack of callers without a call-site/dependency audit. Do not change public API semantics without documenting callers, compatibility plan and tests. Any migration must be justified, forward-only and data-preserving.
Scope-specific acceptance criteria:
- Start read-only report; compare DB-reference scan with filesystem object inventory.
- Categorize, do not delete, on first pass.
- Compare repair options including re-register, quarantine, retain/missing marker or delete, based on owner/data-safety constraints.

5. REQUIRED TESTING
Add focused regression tests for the root cause and relevant negative, failure, boundary, retry, concurrency and stale-state paths. Assert durable database/filesystem/worker state as applicable, not only mocked return values. Use synthetic media, disposable test records and test provider mode. Never publish to real YouTube or destructive-clean real data.
- Synthetic orphan/missing/shared/active-writer cases.
- Reference counts and reservation bytes reconcile.
- Deletion remains a separately authorized operation.
Run the exact focused suite, relevant regressions, static checks and build/browser/integration tests required by the changed layers. Capture actual commands, counts, exit codes, warning/failure output and environment. Do not claim a test ran if only drafted or launched without a completed result.

6. THREE VERIFICATION PASSES — REQUIRED FOR THIS ITEM
PASS 1 — Implementation verification: review diff against every acceptance criterion; run focused tests and the affected workflow; prove expected state and failure behavior.
PASS 2 — Independent challenge: stop thinking like the implementation author. Re-read the requirement and original defect evidence. Try to falsify the fix with adversarial inputs, conflicts, retries, parallel requests, stale state and failure injection. Compare alternative approaches again. Inspect whether the tests could pass while production is still broken. Fix any issue discovered and record changes since Pass 1.
PASS 3 — Differential re-verification: re-read the final diff and working tree from scratch. Compare final code with Passes 1 and 2, identify all changes introduced after each earlier pass, rerun affected focused tests and relevant regressions against the final tree, and verify reports/status files match the final code. Any new code change invalidates the affected previous pass; repeat it.

7. EXPLICIT SELF-CHALLENGE QUESTIONS
- What concrete evidence proves the original problem existed?
- Why does each changed line/function need to exist?
- What alternative was considered and why was it rejected?
- Could a real production record or untrusted caller reach the test/mock path?
- What happens on failure, retry, concurrency, restart and stale response?
- What does this test prove, and what does it not prove?
- Did I preserve all previous working-tree files and frozen behavior?
- What changed between verification passes and why?
- Which claims remain unverified or depend on an environmental assumption?

8. REQUIRED RECORDS AND FINAL RESPONSE
Update only applicable canonical documents: phase tracker, master ledger, implementation status, defect register, relevant API/frontend/pipeline inventories, audit report and `docs/engineering/AI_DECISION_LOG.md`. Preserve old audit records and append corrections instead of rewriting history. Make status consistent everywhere.
Record work-item ID, before/after working-tree status, root cause, option comparison and rationale, files changed and purpose, relevant hashes if practical, each pass and test result, evidence tier (source/unit/mock/API/in-process/live worker/browser/full E2E), risks, limitations and next dependency.
Report statuses honestly: DELIVERED & VERIFIED, PARTIALLY VERIFIED, BLOCKED or REOPENED. Do not say full E2E without the real required components running together.

9. STOP / CONTINUE RULE
Do not start a different implementation item in parallel or expand this scope to unrelated fixes. Complete all three passes, update records and then continue automatically to the next unblocked item in the master execution queue without waiting for routine approval. Stop only for a real blocker, unresolved high-impact product choice, credential/account action, real publication, destructive action against actual data, or an environment change that requires owner authorization. If blocked, document exact evidence and work safely on independent unblocked work only if it does not depend on the blocker.
Never use `git reset`, `git clean`, blanket reverts, destructive DB resets, `docker compose down -v`, or broad file deletion. Do not reintroduce captions/subtitles; preserve transcription for internal scoring/semantic analysis; retain the frozen Shorts duration limit unless the owner explicitly changes it.
```


### Copy-ready prompt — ROADMAP-9.4: Database performance and concurrency

```text
You are the ClipForge engineering agent working in `D:\automation video clips\clipforge`.

WORK ITEM: ROADMAP-9.4 — Database performance and concurrency
STATE: Reconcile current repository state before acting. Do not assume this item is open just because it appears in the roadmap.

1. PROBLEM / OBJECTIVE
Find slow or unsafe query/transaction patterns and address the measured hot path only.

2. PREFLIGHT AND EVIDENCE COLLECTION
Read `AGENTS.md`, the applicable freeze/rule files, `docs/engineering/PHASE_TRACKER.md`, `MASTER_EXECUTION_LEDGER.md`, `IMPLEMENTATION_STATUS.md`, `ENGINEERING_DEFECT_REGISTER.md`, `PIPELINE_CATALOG_AND_DEPENDENCY_GRAPH.md`, `FRONTEND_PAGE_FEATURE_INVENTORY.md`, `PROJECT_CONTINUITY.md`, and the newest relevant audit/decision-log entries. Read only files relevant to this scope in depth, but reconcile any status claims before editing.
Inspect actual current source, schema, runtime route/client/task contracts, tests and caller/callee relationships. Reproduce the reported behavior with a safe isolated fixture where feasible. Separate VERIFIED FACTS, INFERENCES and UNKNOWNS. Record exact file paths, line ranges, commands and observed outputs.
Inspect query counts, indexes, lock waits, transaction spans, ORM session lifecycle and concurrency tests.
Capture `git status --short`, branch/commit, existing diff/untracked inventory and relevant environment/container identity before editing. Protect all pre-existing changes. Do not assume old hashes, route counts, schema revisions or historic reports still reflect the current environment.

3. COMPARE APPROACHES AND JUSTIFY THE CHOICE
Approach selection method: Compare at least two plausible approaches where meaningful: (A) smallest local repair, (B) reuse an established repository abstraction/pattern, and (C) architectural change only if the first two cannot meet verified requirements. Use evidence, not preference. Evaluate correctness, data safety, architectural consistency, backwards compatibility, idempotency/concurrency, performance, testability, reversibility, scope and maintenance cost. Record the chosen approach and specific reasons each alternative was rejected. If the problem is already solved in current source, choose the no-op verification path.
Before coding, write a small comparison table in the decision log: option; correctness against acceptance criteria; data/security risk; compatibility; concurrency/idempotency; complexity/maintenance; reversibility; evidence for/against. Do not create arbitrary numerical scores. Explain why the chosen approach is proportionate to the proven root cause and why each rejected alternative is inferior for this evidence.
If the current implementation already meets the requirement, choose verification-only and avoid a redundant change. If requirements remain ambiguous and a wrong choice would be consequential, stop at a documented blocker rather than invent behavior.

4. IMPLEMENTATION BOUNDARY
Implement only this work item. Prefer the smallest complete, maintainable fix using existing models, APIs, task lifecycle, storage/artifact and frontend patterns. Avoid duplicate frameworks, helpers, routes, state machines, database fields or tests when an existing abstraction meets the requirement.
Preserve all unrelated behavior and frozen components. Do not remove code based on apparent lack of callers without a call-site/dependency audit. Do not change public API semantics without documenting callers, compatibility plan and tests. Any migration must be justified, forward-only and data-preserving.
Scope-specific acceptance criteria:
- Capture profiling evidence before adding indexes or rewriting queries.
- Compare targeted index, query change and transaction reduction for correctness/write contention.
- Check migration size/backfill risk.

5. REQUIRED TESTING
Add focused regression tests for the root cause and relevant negative, failure, boundary, retry, concurrency and stale-state paths. Assert durable database/filesystem/worker state as applicable, not only mocked return values. Use synthetic media, disposable test records and test provider mode. Never publish to real YouTube or destructive-clean real data.
- Representative query latency, concurrent writes, deadlock/conflict paths, data correctness and migration upgrade/downgrade expectations.
- No destructive schema reset.
Run the exact focused suite, relevant regressions, static checks and build/browser/integration tests required by the changed layers. Capture actual commands, counts, exit codes, warning/failure output and environment. Do not claim a test ran if only drafted or launched without a completed result.

6. THREE VERIFICATION PASSES — REQUIRED FOR THIS ITEM
PASS 1 — Implementation verification: review diff against every acceptance criterion; run focused tests and the affected workflow; prove expected state and failure behavior.
PASS 2 — Independent challenge: stop thinking like the implementation author. Re-read the requirement and original defect evidence. Try to falsify the fix with adversarial inputs, conflicts, retries, parallel requests, stale state and failure injection. Compare alternative approaches again. Inspect whether the tests could pass while production is still broken. Fix any issue discovered and record changes since Pass 1.
PASS 3 — Differential re-verification: re-read the final diff and working tree from scratch. Compare final code with Passes 1 and 2, identify all changes introduced after each earlier pass, rerun affected focused tests and relevant regressions against the final tree, and verify reports/status files match the final code. Any new code change invalidates the affected previous pass; repeat it.

7. EXPLICIT SELF-CHALLENGE QUESTIONS
- What concrete evidence proves the original problem existed?
- Why does each changed line/function need to exist?
- What alternative was considered and why was it rejected?
- Could a real production record or untrusted caller reach the test/mock path?
- What happens on failure, retry, concurrency, restart and stale response?
- What does this test prove, and what does it not prove?
- Did I preserve all previous working-tree files and frozen behavior?
- What changed between verification passes and why?
- Which claims remain unverified or depend on an environmental assumption?

8. REQUIRED RECORDS AND FINAL RESPONSE
Update only applicable canonical documents: phase tracker, master ledger, implementation status, defect register, relevant API/frontend/pipeline inventories, audit report and `docs/engineering/AI_DECISION_LOG.md`. Preserve old audit records and append corrections instead of rewriting history. Make status consistent everywhere.
Record work-item ID, before/after working-tree status, root cause, option comparison and rationale, files changed and purpose, relevant hashes if practical, each pass and test result, evidence tier (source/unit/mock/API/in-process/live worker/browser/full E2E), risks, limitations and next dependency.
Report statuses honestly: DELIVERED & VERIFIED, PARTIALLY VERIFIED, BLOCKED or REOPENED. Do not say full E2E without the real required components running together.

9. STOP / CONTINUE RULE
Do not start a different implementation item in parallel or expand this scope to unrelated fixes. Complete all three passes, update records and then continue automatically to the next unblocked item in the master execution queue without waiting for routine approval. Stop only for a real blocker, unresolved high-impact product choice, credential/account action, real publication, destructive action against actual data, or an environment change that requires owner authorization. If blocked, document exact evidence and work safely on independent unblocked work only if it does not depend on the blocker.
Never use `git reset`, `git clean`, blanket reverts, destructive DB resets, `docker compose down -v`, or broad file deletion. Do not reintroduce captions/subtitles; preserve transcription for internal scoring/semantic analysis; retain the frozen Shorts duration limit unless the owner explicitly changes it.
```


### Copy-ready prompt — ROADMAP-9.5: Observability and incident diagnosis

```text
You are the ClipForge engineering agent working in `D:\automation video clips\clipforge`.

WORK ITEM: ROADMAP-9.5 — Observability and incident diagnosis
STATE: Reconcile current repository state before acting. Do not assume this item is open just because it appears in the roadmap.

1. PROBLEM / OBJECTIVE
Ensure a job can be traced across API, broker, worker and artifact state.

2. PREFLIGHT AND EVIDENCE COLLECTION
Read `AGENTS.md`, the applicable freeze/rule files, `docs/engineering/PHASE_TRACKER.md`, `MASTER_EXECUTION_LEDGER.md`, `IMPLEMENTATION_STATUS.md`, `ENGINEERING_DEFECT_REGISTER.md`, `PIPELINE_CATALOG_AND_DEPENDENCY_GRAPH.md`, `FRONTEND_PAGE_FEATURE_INVENTORY.md`, `PROJECT_CONTINUITY.md`, and the newest relevant audit/decision-log entries. Read only files relevant to this scope in depth, but reconcile any status claims before editing.
Inspect actual current source, schema, runtime route/client/task contracts, tests and caller/callee relationships. Reproduce the reported behavior with a safe isolated fixture where feasible. Separate VERIFIED FACTS, INFERENCES and UNKNOWNS. Record exact file paths, line ranges, commands and observed outputs.
Trace task IDs, job IDs, request IDs, structured logs, progress timestamps, task events and error records.
Capture `git status --short`, branch/commit, existing diff/untracked inventory and relevant environment/container identity before editing. Protect all pre-existing changes. Do not assume old hashes, route counts, schema revisions or historic reports still reflect the current environment.

3. COMPARE APPROACHES AND JUSTIFY THE CHOICE
Approach selection method: Compare at least two plausible approaches where meaningful: (A) smallest local repair, (B) reuse an established repository abstraction/pattern, and (C) architectural change only if the first two cannot meet verified requirements. Use evidence, not preference. Evaluate correctness, data safety, architectural consistency, backwards compatibility, idempotency/concurrency, performance, testability, reversibility, scope and maintenance cost. Record the chosen approach and specific reasons each alternative was rejected. If the problem is already solved in current source, choose the no-op verification path.
Before coding, write a small comparison table in the decision log: option; correctness against acceptance criteria; data/security risk; compatibility; concurrency/idempotency; complexity/maintenance; reversibility; evidence for/against. Do not create arbitrary numerical scores. Explain why the chosen approach is proportionate to the proven root cause and why each rejected alternative is inferior for this evidence.
If the current implementation already meets the requirement, choose verification-only and avoid a redundant change. If requirements remain ambiguous and a wrong choice would be consequential, stop at a documented blocker rather than invent behavior.

4. IMPLEMENTATION BOUNDARY
Implement only this work item. Prefer the smallest complete, maintainable fix using existing models, APIs, task lifecycle, storage/artifact and frontend patterns. Avoid duplicate frameworks, helpers, routes, state machines, database fields or tests when an existing abstraction meets the requirement.
Preserve all unrelated behavior and frozen components. Do not remove code based on apparent lack of callers without a call-site/dependency audit. Do not change public API semantics without documenting callers, compatibility plan and tests. Any migration must be justified, forward-only and data-preserving.
Scope-specific acceptance criteria:
- Design minimal correlation additions that reuse current identifiers.
- Compare logs-only vs DB status vs metrics options; retain data minimization.
- Do not log media content, tokens or secrets.

5. REQUIRED TESTING
Add focused regression tests for the root cause and relevant negative, failure, boundary, retry, concurrency and stale-state paths. Assert durable database/filesystem/worker state as applicable, not only mocked return values. Use synthetic media, disposable test records and test provider mode. Never publish to real YouTube or destructive-clean real data.
- A synthetic failure traced from UI request to terminal job state/artifact outcome.
- Test log redaction and missing correlation cases.
Run the exact focused suite, relevant regressions, static checks and build/browser/integration tests required by the changed layers. Capture actual commands, counts, exit codes, warning/failure output and environment. Do not claim a test ran if only drafted or launched without a completed result.

6. THREE VERIFICATION PASSES — REQUIRED FOR THIS ITEM
PASS 1 — Implementation verification: review diff against every acceptance criterion; run focused tests and the affected workflow; prove expected state and failure behavior.
PASS 2 — Independent challenge: stop thinking like the implementation author. Re-read the requirement and original defect evidence. Try to falsify the fix with adversarial inputs, conflicts, retries, parallel requests, stale state and failure injection. Compare alternative approaches again. Inspect whether the tests could pass while production is still broken. Fix any issue discovered and record changes since Pass 1.
PASS 3 — Differential re-verification: re-read the final diff and working tree from scratch. Compare final code with Passes 1 and 2, identify all changes introduced after each earlier pass, rerun affected focused tests and relevant regressions against the final tree, and verify reports/status files match the final code. Any new code change invalidates the affected previous pass; repeat it.

7. EXPLICIT SELF-CHALLENGE QUESTIONS
- What concrete evidence proves the original problem existed?
- Why does each changed line/function need to exist?
- What alternative was considered and why was it rejected?
- Could a real production record or untrusted caller reach the test/mock path?
- What happens on failure, retry, concurrency, restart and stale response?
- What does this test prove, and what does it not prove?
- Did I preserve all previous working-tree files and frozen behavior?
- What changed between verification passes and why?
- Which claims remain unverified or depend on an environmental assumption?

8. REQUIRED RECORDS AND FINAL RESPONSE
Update only applicable canonical documents: phase tracker, master ledger, implementation status, defect register, relevant API/frontend/pipeline inventories, audit report and `docs/engineering/AI_DECISION_LOG.md`. Preserve old audit records and append corrections instead of rewriting history. Make status consistent everywhere.
Record work-item ID, before/after working-tree status, root cause, option comparison and rationale, files changed and purpose, relevant hashes if practical, each pass and test result, evidence tier (source/unit/mock/API/in-process/live worker/browser/full E2E), risks, limitations and next dependency.
Report statuses honestly: DELIVERED & VERIFIED, PARTIALLY VERIFIED, BLOCKED or REOPENED. Do not say full E2E without the real required components running together.

9. STOP / CONTINUE RULE
Do not start a different implementation item in parallel or expand this scope to unrelated fixes. Complete all three passes, update records and then continue automatically to the next unblocked item in the master execution queue without waiting for routine approval. Stop only for a real blocker, unresolved high-impact product choice, credential/account action, real publication, destructive action against actual data, or an environment change that requires owner authorization. If blocked, document exact evidence and work safely on independent unblocked work only if it does not depend on the blocker.
Never use `git reset`, `git clean`, blanket reverts, destructive DB resets, `docker compose down -v`, or broad file deletion. Do not reintroduce captions/subtitles; preserve transcription for internal scoring/semantic analysis; retain the frozen Shorts duration limit unless the owner explicitly changes it.
```


## Main phase prompt — ROADMAP Phase 10 (PROPOSED): Proposed release readiness and maintenance

```text
You are the ClipForge engineering agent. Phase 10 is a proposed extension, not a feature specification. Do not invent product requirements to fill the roadmap gap.

PROBLEM / OBJECTIVE
This proposed phase builds evidence-based release readiness through 10.1–10.5.

FIRST ACTION — DISCOVERY BEFORE IMPLEMENTATION
Read current rules, roadmap, defect register, decision log, implementation status, deployment constraints and evidence from the prior phase. For every proposed child item, determine whether a real issue/requirement exists, whether it is already solved, and what evidence supports doing the work. If no genuine gap exists, verify and close the item without edits. If product intent or target operating environment is ambiguous, document a blocker/proposal; do not implement a guessed product behavior.

APPROACH SELECTION
For each substantiated finding, compare at least two plausible approaches (minimal repair, reuse existing architecture, larger redesign only when necessary). Compare evidence-backed correctness, security/data safety, compatibility, operating cost, reversibility, testability and maintenance. Record decision and rejected alternatives.

PHASE ACCEPTANCE CRITERIA
- Requirements traced to tests/evidence.
- Clean-environment install and recovery rehearsed on disposable environment.
- Operational handoff and final release decision documented.

EXECUTION
Execute each child separately, with the three verification passes, decision log and project-record updates. Do not merge multiple hardening/performance/release tasks into one broad change.

BOUNDARIES
Do not declare production readiness if critical worker/security/data recovery evidence is missing.
No destructive production action, no real external publishing, no secrets in logs, no DB resets or deletion of persistent volumes. Stop for owner authorization where a real account, real user data, irreversible migration, or deployment cutover is affected.

EXIT
Mark the extension active only after the canonical roadmap is updated with evidence and the phase has an explicit acceptance definition. Otherwise retain PROPOSED status and report the missing requirement or approval.
```


### Copy-ready prompt — ROADMAP-10.1: Requirements and acceptance closure

```text
You are the ClipForge engineering agent working in `D:\automation video clips\clipforge`.

WORK ITEM: ROADMAP-10.1 — Requirements and acceptance closure
STATE: Reconcile current repository state before acting. Do not assume this item is open just because it appears in the roadmap.

1. PROBLEM / OBJECTIVE
Map every approved requirement to implementation evidence and a reproducible test.

2. PREFLIGHT AND EVIDENCE COLLECTION
Read `AGENTS.md`, the applicable freeze/rule files, `docs/engineering/PHASE_TRACKER.md`, `MASTER_EXECUTION_LEDGER.md`, `IMPLEMENTATION_STATUS.md`, `ENGINEERING_DEFECT_REGISTER.md`, `PIPELINE_CATALOG_AND_DEPENDENCY_GRAPH.md`, `FRONTEND_PAGE_FEATURE_INVENTORY.md`, `PROJECT_CONTINUITY.md`, and the newest relevant audit/decision-log entries. Read only files relevant to this scope in depth, but reconcile any status claims before editing.
Inspect actual current source, schema, runtime route/client/task contracts, tests and caller/callee relationships. Reproduce the reported behavior with a safe isolated fixture where feasible. Separate VERIFIED FACTS, INFERENCES and UNKNOWNS. Record exact file paths, line ranges, commands and observed outputs.
Reconcile roadmap, defect register, phase tracker, user-approved product constraints and actual UI/API behavior.
Capture `git status --short`, branch/commit, existing diff/untracked inventory and relevant environment/container identity before editing. Protect all pre-existing changes. Do not assume old hashes, route counts, schema revisions or historic reports still reflect the current environment.

3. COMPARE APPROACHES AND JUSTIFY THE CHOICE
Approach selection method: Compare at least two plausible approaches where meaningful: (A) smallest local repair, (B) reuse an established repository abstraction/pattern, and (C) architectural change only if the first two cannot meet verified requirements. Use evidence, not preference. Evaluate correctness, data safety, architectural consistency, backwards compatibility, idempotency/concurrency, performance, testability, reversibility, scope and maintenance cost. Record the chosen approach and specific reasons each alternative was rejected. If the problem is already solved in current source, choose the no-op verification path.
Before coding, write a small comparison table in the decision log: option; correctness against acceptance criteria; data/security risk; compatibility; concurrency/idempotency; complexity/maintenance; reversibility; evidence for/against. Do not create arbitrary numerical scores. Explain why the chosen approach is proportionate to the proven root cause and why each rejected alternative is inferior for this evidence.
If the current implementation already meets the requirement, choose verification-only and avoid a redundant change. If requirements remain ambiguous and a wrong choice would be consequential, stop at a documented blocker rather than invent behavior.

4. IMPLEMENTATION BOUNDARY
Implement only this work item. Prefer the smallest complete, maintainable fix using existing models, APIs, task lifecycle, storage/artifact and frontend patterns. Avoid duplicate frameworks, helpers, routes, state machines, database fields or tests when an existing abstraction meets the requirement.
Preserve all unrelated behavior and frozen components. Do not remove code based on apparent lack of callers without a call-site/dependency audit. Do not change public API semantics without documenting callers, compatibility plan and tests. Any migration must be justified, forward-only and data-preserving.
Scope-specific acceptance criteria:
- Identify unsupported, partially implemented and obsolete requirements.
- Trace requirement → code → tests → runtime evidence.
- Resolve terminology conflicts without rewriting historical phase IDs.

5. REQUIRED TESTING
Add focused regression tests for the root cause and relevant negative, failure, boundary, retry, concurrency and stale-state paths. Assert durable database/filesystem/worker state as applicable, not only mocked return values. Use synthetic media, disposable test records and test provider mode. Never publish to real YouTube or destructive-clean real data.
- No requirement is marked complete from source inspection alone when runtime is required.
- List clear residuals and owner decisions.
Run the exact focused suite, relevant regressions, static checks and build/browser/integration tests required by the changed layers. Capture actual commands, counts, exit codes, warning/failure output and environment. Do not claim a test ran if only drafted or launched without a completed result.

6. THREE VERIFICATION PASSES — REQUIRED FOR THIS ITEM
PASS 1 — Implementation verification: review diff against every acceptance criterion; run focused tests and the affected workflow; prove expected state and failure behavior.
PASS 2 — Independent challenge: stop thinking like the implementation author. Re-read the requirement and original defect evidence. Try to falsify the fix with adversarial inputs, conflicts, retries, parallel requests, stale state and failure injection. Compare alternative approaches again. Inspect whether the tests could pass while production is still broken. Fix any issue discovered and record changes since Pass 1.
PASS 3 — Differential re-verification: re-read the final diff and working tree from scratch. Compare final code with Passes 1 and 2, identify all changes introduced after each earlier pass, rerun affected focused tests and relevant regressions against the final tree, and verify reports/status files match the final code. Any new code change invalidates the affected previous pass; repeat it.

7. EXPLICIT SELF-CHALLENGE QUESTIONS
- What concrete evidence proves the original problem existed?
- Why does each changed line/function need to exist?
- What alternative was considered and why was it rejected?
- Could a real production record or untrusted caller reach the test/mock path?
- What happens on failure, retry, concurrency, restart and stale response?
- What does this test prove, and what does it not prove?
- Did I preserve all previous working-tree files and frozen behavior?
- What changed between verification passes and why?
- Which claims remain unverified or depend on an environmental assumption?

8. REQUIRED RECORDS AND FINAL RESPONSE
Update only applicable canonical documents: phase tracker, master ledger, implementation status, defect register, relevant API/frontend/pipeline inventories, audit report and `docs/engineering/AI_DECISION_LOG.md`. Preserve old audit records and append corrections instead of rewriting history. Make status consistent everywhere.
Record work-item ID, before/after working-tree status, root cause, option comparison and rationale, files changed and purpose, relevant hashes if practical, each pass and test result, evidence tier (source/unit/mock/API/in-process/live worker/browser/full E2E), risks, limitations and next dependency.
Report statuses honestly: DELIVERED & VERIFIED, PARTIALLY VERIFIED, BLOCKED or REOPENED. Do not say full E2E without the real required components running together.

9. STOP / CONTINUE RULE
Do not start a different implementation item in parallel or expand this scope to unrelated fixes. Complete all three passes, update records and then continue automatically to the next unblocked item in the master execution queue without waiting for routine approval. Stop only for a real blocker, unresolved high-impact product choice, credential/account action, real publication, destructive action against actual data, or an environment change that requires owner authorization. If blocked, document exact evidence and work safely on independent unblocked work only if it does not depend on the blocker.
Never use `git reset`, `git clean`, blanket reverts, destructive DB resets, `docker compose down -v`, or broad file deletion. Do not reintroduce captions/subtitles; preserve transcription for internal scoring/semantic analysis; retain the frozen Shorts duration limit unless the owner explicitly changes it.
```


### Copy-ready prompt — ROADMAP-10.2: Clean-environment installation rehearsal

```text
You are the ClipForge engineering agent working in `D:\automation video clips\clipforge`.

WORK ITEM: ROADMAP-10.2 — Clean-environment installation rehearsal
STATE: Reconcile current repository state before acting. Do not assume this item is open just because it appears in the roadmap.

1. PROBLEM / OBJECTIVE
Validate documented setup using a clean disposable checkout/environment.

2. PREFLIGHT AND EVIDENCE COLLECTION
Read `AGENTS.md`, the applicable freeze/rule files, `docs/engineering/PHASE_TRACKER.md`, `MASTER_EXECUTION_LEDGER.md`, `IMPLEMENTATION_STATUS.md`, `ENGINEERING_DEFECT_REGISTER.md`, `PIPELINE_CATALOG_AND_DEPENDENCY_GRAPH.md`, `FRONTEND_PAGE_FEATURE_INVENTORY.md`, `PROJECT_CONTINUITY.md`, and the newest relevant audit/decision-log entries. Read only files relevant to this scope in depth, but reconcile any status claims before editing.
Inspect actual current source, schema, runtime route/client/task contracts, tests and caller/callee relationships. Reproduce the reported behavior with a safe isolated fixture where feasible. Separate VERIFIED FACTS, INFERENCES and UNKNOWNS. Record exact file paths, line ranges, commands and observed outputs.
Inspect setup scripts, pinned dependencies, env example, volumes, migrations, service startup and health checks.
Capture `git status --short`, branch/commit, existing diff/untracked inventory and relevant environment/container identity before editing. Protect all pre-existing changes. Do not assume old hashes, route counts, schema revisions or historic reports still reflect the current environment.

3. COMPARE APPROACHES AND JUSTIFY THE CHOICE
Approach selection method: Compare at least two plausible approaches where meaningful: (A) smallest local repair, (B) reuse an established repository abstraction/pattern, and (C) architectural change only if the first two cannot meet verified requirements. Use evidence, not preference. Evaluate correctness, data safety, architectural consistency, backwards compatibility, idempotency/concurrency, performance, testability, reversibility, scope and maintenance cost. Record the chosen approach and specific reasons each alternative was rejected. If the problem is already solved in current source, choose the no-op verification path.
Before coding, write a small comparison table in the decision log: option; correctness against acceptance criteria; data/security risk; compatibility; concurrency/idempotency; complexity/maintenance; reversibility; evidence for/against. Do not create arbitrary numerical scores. Explain why the chosen approach is proportionate to the proven root cause and why each rejected alternative is inferior for this evidence.
If the current implementation already meets the requirement, choose verification-only and avoid a redundant change. If requirements remain ambiguous and a wrong choice would be consequential, stop at a documented blocker rather than invent behavior.

4. IMPLEMENTATION BOUNDARY
Implement only this work item. Prefer the smallest complete, maintainable fix using existing models, APIs, task lifecycle, storage/artifact and frontend patterns. Avoid duplicate frameworks, helpers, routes, state machines, database fields or tests when an existing abstraction meets the requirement.
Preserve all unrelated behavior and frozen components. Do not remove code based on apparent lack of callers without a call-site/dependency audit. Do not change public API semantics without documenting callers, compatibility plan and tests. Any migration must be justified, forward-only and data-preserving.
Scope-specific acceptance criteria:
- Compare documented vs automated setup and choose a repeatable path.
- Use synthetic secrets/config.
- Avoid copying production data into the rehearsal.

5. REQUIRED TESTING
Add focused regression tests for the root cause and relevant negative, failure, boundary, retry, concurrency and stale-state paths. Assert durable database/filesystem/worker state as applicable, not only mocked return values. Use synthetic media, disposable test records and test provider mode. Never publish to real YouTube or destructive-clean real data.
- Clean clone/install/build/start/migrate/test smoke path reproducible.
- Record all manual interventions and missing prerequisites.
Run the exact focused suite, relevant regressions, static checks and build/browser/integration tests required by the changed layers. Capture actual commands, counts, exit codes, warning/failure output and environment. Do not claim a test ran if only drafted or launched without a completed result.

6. THREE VERIFICATION PASSES — REQUIRED FOR THIS ITEM
PASS 1 — Implementation verification: review diff against every acceptance criterion; run focused tests and the affected workflow; prove expected state and failure behavior.
PASS 2 — Independent challenge: stop thinking like the implementation author. Re-read the requirement and original defect evidence. Try to falsify the fix with adversarial inputs, conflicts, retries, parallel requests, stale state and failure injection. Compare alternative approaches again. Inspect whether the tests could pass while production is still broken. Fix any issue discovered and record changes since Pass 1.
PASS 3 — Differential re-verification: re-read the final diff and working tree from scratch. Compare final code with Passes 1 and 2, identify all changes introduced after each earlier pass, rerun affected focused tests and relevant regressions against the final tree, and verify reports/status files match the final code. Any new code change invalidates the affected previous pass; repeat it.

7. EXPLICIT SELF-CHALLENGE QUESTIONS
- What concrete evidence proves the original problem existed?
- Why does each changed line/function need to exist?
- What alternative was considered and why was it rejected?
- Could a real production record or untrusted caller reach the test/mock path?
- What happens on failure, retry, concurrency, restart and stale response?
- What does this test prove, and what does it not prove?
- Did I preserve all previous working-tree files and frozen behavior?
- What changed between verification passes and why?
- Which claims remain unverified or depend on an environmental assumption?

8. REQUIRED RECORDS AND FINAL RESPONSE
Update only applicable canonical documents: phase tracker, master ledger, implementation status, defect register, relevant API/frontend/pipeline inventories, audit report and `docs/engineering/AI_DECISION_LOG.md`. Preserve old audit records and append corrections instead of rewriting history. Make status consistent everywhere.
Record work-item ID, before/after working-tree status, root cause, option comparison and rationale, files changed and purpose, relevant hashes if practical, each pass and test result, evidence tier (source/unit/mock/API/in-process/live worker/browser/full E2E), risks, limitations and next dependency.
Report statuses honestly: DELIVERED & VERIFIED, PARTIALLY VERIFIED, BLOCKED or REOPENED. Do not say full E2E without the real required components running together.

9. STOP / CONTINUE RULE
Do not start a different implementation item in parallel or expand this scope to unrelated fixes. Complete all three passes, update records and then continue automatically to the next unblocked item in the master execution queue without waiting for routine approval. Stop only for a real blocker, unresolved high-impact product choice, credential/account action, real publication, destructive action against actual data, or an environment change that requires owner authorization. If blocked, document exact evidence and work safely on independent unblocked work only if it does not depend on the blocker.
Never use `git reset`, `git clean`, blanket reverts, destructive DB resets, `docker compose down -v`, or broad file deletion. Do not reintroduce captions/subtitles; preserve transcription for internal scoring/semantic analysis; retain the frozen Shorts duration limit unless the owner explicitly changes it.
```


### Copy-ready prompt — ROADMAP-10.3: Production deployment checklist

```text
You are the ClipForge engineering agent working in `D:\automation video clips\clipforge`.

WORK ITEM: ROADMAP-10.3 — Production deployment checklist
STATE: Reconcile current repository state before acting. Do not assume this item is open just because it appears in the roadmap.

1. PROBLEM / OBJECTIVE
Produce a deployable operational checklist grounded in actual service topology.

2. PREFLIGHT AND EVIDENCE COLLECTION
Read `AGENTS.md`, the applicable freeze/rule files, `docs/engineering/PHASE_TRACKER.md`, `MASTER_EXECUTION_LEDGER.md`, `IMPLEMENTATION_STATUS.md`, `ENGINEERING_DEFECT_REGISTER.md`, `PIPELINE_CATALOG_AND_DEPENDENCY_GRAPH.md`, `FRONTEND_PAGE_FEATURE_INVENTORY.md`, `PROJECT_CONTINUITY.md`, and the newest relevant audit/decision-log entries. Read only files relevant to this scope in depth, but reconcile any status claims before editing.
Inspect actual current source, schema, runtime route/client/task contracts, tests and caller/callee relationships. Reproduce the reported behavior with a safe isolated fixture where feasible. Separate VERIFIED FACTS, INFERENCES and UNKNOWNS. Record exact file paths, line ranges, commands and observed outputs.
Inspect Compose/services, listeners, secrets, persistent volumes, migration approach, health checks, resource assumptions and OAuth setup.
Capture `git status --short`, branch/commit, existing diff/untracked inventory and relevant environment/container identity before editing. Protect all pre-existing changes. Do not assume old hashes, route counts, schema revisions or historic reports still reflect the current environment.

3. COMPARE APPROACHES AND JUSTIFY THE CHOICE
Approach selection method: Compare at least two plausible approaches where meaningful: (A) smallest local repair, (B) reuse an established repository abstraction/pattern, and (C) architectural change only if the first two cannot meet verified requirements. Use evidence, not preference. Evaluate correctness, data safety, architectural consistency, backwards compatibility, idempotency/concurrency, performance, testability, reversibility, scope and maintenance cost. Record the chosen approach and specific reasons each alternative was rejected. If the problem is already solved in current source, choose the no-op verification path.
Before coding, write a small comparison table in the decision log: option; correctness against acceptance criteria; data/security risk; compatibility; concurrency/idempotency; complexity/maintenance; reversibility; evidence for/against. Do not create arbitrary numerical scores. Explain why the chosen approach is proportionate to the proven root cause and why each rejected alternative is inferior for this evidence.
If the current implementation already meets the requirement, choose verification-only and avoid a redundant change. If requirements remain ambiguous and a wrong choice would be consequential, stop at a documented blocker rather than invent behavior.

4. IMPLEMENTATION BOUNDARY
Implement only this work item. Prefer the smallest complete, maintainable fix using existing models, APIs, task lifecycle, storage/artifact and frontend patterns. Avoid duplicate frameworks, helpers, routes, state machines, database fields or tests when an existing abstraction meets the requirement.
Preserve all unrelated behavior and frozen components. Do not remove code based on apparent lack of callers without a call-site/dependency audit. Do not change public API semantics without documenting callers, compatibility plan and tests. Any migration must be justified, forward-only and data-preserving.
Scope-specific acceptance criteria:
- Separate pre-deploy, deploy, post-deploy and rollback steps.
- Mark each command as read-only, reversible or destructive.
- Include worker code freshness and source/image identity.

5. REQUIRED TESTING
Add focused regression tests for the root cause and relevant negative, failure, boundary, retry, concurrency and stale-state paths. Assert durable database/filesystem/worker state as applicable, not only mocked return values. Use synthetic media, disposable test records and test provider mode. Never publish to real YouTube or destructive-clean real data.
- Checklist tested in disposable staging/rehearsal.
- No invented environment values or exposed secrets.
- Operator knows how to verify health and task completion.
Run the exact focused suite, relevant regressions, static checks and build/browser/integration tests required by the changed layers. Capture actual commands, counts, exit codes, warning/failure output and environment. Do not claim a test ran if only drafted or launched without a completed result.

6. THREE VERIFICATION PASSES — REQUIRED FOR THIS ITEM
PASS 1 — Implementation verification: review diff against every acceptance criterion; run focused tests and the affected workflow; prove expected state and failure behavior.
PASS 2 — Independent challenge: stop thinking like the implementation author. Re-read the requirement and original defect evidence. Try to falsify the fix with adversarial inputs, conflicts, retries, parallel requests, stale state and failure injection. Compare alternative approaches again. Inspect whether the tests could pass while production is still broken. Fix any issue discovered and record changes since Pass 1.
PASS 3 — Differential re-verification: re-read the final diff and working tree from scratch. Compare final code with Passes 1 and 2, identify all changes introduced after each earlier pass, rerun affected focused tests and relevant regressions against the final tree, and verify reports/status files match the final code. Any new code change invalidates the affected previous pass; repeat it.

7. EXPLICIT SELF-CHALLENGE QUESTIONS
- What concrete evidence proves the original problem existed?
- Why does each changed line/function need to exist?
- What alternative was considered and why was it rejected?
- Could a real production record or untrusted caller reach the test/mock path?
- What happens on failure, retry, concurrency, restart and stale response?
- What does this test prove, and what does it not prove?
- Did I preserve all previous working-tree files and frozen behavior?
- What changed between verification passes and why?
- Which claims remain unverified or depend on an environmental assumption?

8. REQUIRED RECORDS AND FINAL RESPONSE
Update only applicable canonical documents: phase tracker, master ledger, implementation status, defect register, relevant API/frontend/pipeline inventories, audit report and `docs/engineering/AI_DECISION_LOG.md`. Preserve old audit records and append corrections instead of rewriting history. Make status consistent everywhere.
Record work-item ID, before/after working-tree status, root cause, option comparison and rationale, files changed and purpose, relevant hashes if practical, each pass and test result, evidence tier (source/unit/mock/API/in-process/live worker/browser/full E2E), risks, limitations and next dependency.
Report statuses honestly: DELIVERED & VERIFIED, PARTIALLY VERIFIED, BLOCKED or REOPENED. Do not say full E2E without the real required components running together.

9. STOP / CONTINUE RULE
Do not start a different implementation item in parallel or expand this scope to unrelated fixes. Complete all three passes, update records and then continue automatically to the next unblocked item in the master execution queue without waiting for routine approval. Stop only for a real blocker, unresolved high-impact product choice, credential/account action, real publication, destructive action against actual data, or an environment change that requires owner authorization. If blocked, document exact evidence and work safely on independent unblocked work only if it does not depend on the blocker.
Never use `git reset`, `git clean`, blanket reverts, destructive DB resets, `docker compose down -v`, or broad file deletion. Do not reintroduce captions/subtitles; preserve transcription for internal scoring/semantic analysis; retain the frozen Shorts duration limit unless the owner explicitly changes it.
```


### Copy-ready prompt — ROADMAP-10.4: Rollback and incident recovery rehearsal

```text
You are the ClipForge engineering agent working in `D:\automation video clips\clipforge`.

WORK ITEM: ROADMAP-10.4 — Rollback and incident recovery rehearsal
STATE: Reconcile current repository state before acting. Do not assume this item is open just because it appears in the roadmap.

1. PROBLEM / OBJECTIVE
Verify recovery paths for failed deploy, schema change and stuck task without destroying data.

2. PREFLIGHT AND EVIDENCE COLLECTION
Read `AGENTS.md`, the applicable freeze/rule files, `docs/engineering/PHASE_TRACKER.md`, `MASTER_EXECUTION_LEDGER.md`, `IMPLEMENTATION_STATUS.md`, `ENGINEERING_DEFECT_REGISTER.md`, `PIPELINE_CATALOG_AND_DEPENDENCY_GRAPH.md`, `FRONTEND_PAGE_FEATURE_INVENTORY.md`, `PROJECT_CONTINUITY.md`, and the newest relevant audit/decision-log entries. Read only files relevant to this scope in depth, but reconcile any status claims before editing.
Inspect actual current source, schema, runtime route/client/task contracts, tests and caller/callee relationships. Reproduce the reported behavior with a safe isolated fixture where feasible. Separate VERIFIED FACTS, INFERENCES and UNKNOWNS. Record exact file paths, line ranges, commands and observed outputs.
Inspect forward migrations, backups, worker restart, task terminal states, storage journal recovery and publish idempotency.
Capture `git status --short`, branch/commit, existing diff/untracked inventory and relevant environment/container identity before editing. Protect all pre-existing changes. Do not assume old hashes, route counts, schema revisions or historic reports still reflect the current environment.

3. COMPARE APPROACHES AND JUSTIFY THE CHOICE
Approach selection method: Compare at least two plausible approaches where meaningful: (A) smallest local repair, (B) reuse an established repository abstraction/pattern, and (C) architectural change only if the first two cannot meet verified requirements. Use evidence, not preference. Evaluate correctness, data safety, architectural consistency, backwards compatibility, idempotency/concurrency, performance, testability, reversibility, scope and maintenance cost. Record the chosen approach and specific reasons each alternative was rejected. If the problem is already solved in current source, choose the no-op verification path.
Before coding, write a small comparison table in the decision log: option; correctness against acceptance criteria; data/security risk; compatibility; concurrency/idempotency; complexity/maintenance; reversibility; evidence for/against. Do not create arbitrary numerical scores. Explain why the chosen approach is proportionate to the proven root cause and why each rejected alternative is inferior for this evidence.
If the current implementation already meets the requirement, choose verification-only and avoid a redundant change. If requirements remain ambiguous and a wrong choice would be consequential, stop at a documented blocker rather than invent behavior.

4. IMPLEMENTATION BOUNDARY
Implement only this work item. Prefer the smallest complete, maintainable fix using existing models, APIs, task lifecycle, storage/artifact and frontend patterns. Avoid duplicate frameworks, helpers, routes, state machines, database fields or tests when an existing abstraction meets the requirement.
Preserve all unrelated behavior and frozen components. Do not remove code based on apparent lack of callers without a call-site/dependency audit. Do not change public API semantics without documenting callers, compatibility plan and tests. Any migration must be justified, forward-only and data-preserving.
Scope-specific acceptance criteria:
- Prefer forward fix where down migration risks data loss.
- Exercise rollback only in disposable environment.
- Document which operations require operator confirmation.

5. REQUIRED TESTING
Add focused regression tests for the root cause and relevant negative, failure, boundary, retry, concurrency and stale-state paths. Assert durable database/filesystem/worker state as applicable, not only mocked return values. Use synthetic media, disposable test records and test provider mode. Never publish to real YouTube or destructive-clean real data.
- Simulated startup failure, worker stale code, migration incompatibility and orphan recovery.
- Persistent data, credentials and artifact references survive.
Run the exact focused suite, relevant regressions, static checks and build/browser/integration tests required by the changed layers. Capture actual commands, counts, exit codes, warning/failure output and environment. Do not claim a test ran if only drafted or launched without a completed result.

6. THREE VERIFICATION PASSES — REQUIRED FOR THIS ITEM
PASS 1 — Implementation verification: review diff against every acceptance criterion; run focused tests and the affected workflow; prove expected state and failure behavior.
PASS 2 — Independent challenge: stop thinking like the implementation author. Re-read the requirement and original defect evidence. Try to falsify the fix with adversarial inputs, conflicts, retries, parallel requests, stale state and failure injection. Compare alternative approaches again. Inspect whether the tests could pass while production is still broken. Fix any issue discovered and record changes since Pass 1.
PASS 3 — Differential re-verification: re-read the final diff and working tree from scratch. Compare final code with Passes 1 and 2, identify all changes introduced after each earlier pass, rerun affected focused tests and relevant regressions against the final tree, and verify reports/status files match the final code. Any new code change invalidates the affected previous pass; repeat it.

7. EXPLICIT SELF-CHALLENGE QUESTIONS
- What concrete evidence proves the original problem existed?
- Why does each changed line/function need to exist?
- What alternative was considered and why was it rejected?
- Could a real production record or untrusted caller reach the test/mock path?
- What happens on failure, retry, concurrency, restart and stale response?
- What does this test prove, and what does it not prove?
- Did I preserve all previous working-tree files and frozen behavior?
- What changed between verification passes and why?
- Which claims remain unverified or depend on an environmental assumption?

8. REQUIRED RECORDS AND FINAL RESPONSE
Update only applicable canonical documents: phase tracker, master ledger, implementation status, defect register, relevant API/frontend/pipeline inventories, audit report and `docs/engineering/AI_DECISION_LOG.md`. Preserve old audit records and append corrections instead of rewriting history. Make status consistent everywhere.
Record work-item ID, before/after working-tree status, root cause, option comparison and rationale, files changed and purpose, relevant hashes if practical, each pass and test result, evidence tier (source/unit/mock/API/in-process/live worker/browser/full E2E), risks, limitations and next dependency.
Report statuses honestly: DELIVERED & VERIFIED, PARTIALLY VERIFIED, BLOCKED or REOPENED. Do not say full E2E without the real required components running together.

9. STOP / CONTINUE RULE
Do not start a different implementation item in parallel or expand this scope to unrelated fixes. Complete all three passes, update records and then continue automatically to the next unblocked item in the master execution queue without waiting for routine approval. Stop only for a real blocker, unresolved high-impact product choice, credential/account action, real publication, destructive action against actual data, or an environment change that requires owner authorization. If blocked, document exact evidence and work safely on independent unblocked work only if it does not depend on the blocker.
Never use `git reset`, `git clean`, blanket reverts, destructive DB resets, `docker compose down -v`, or broad file deletion. Do not reintroduce captions/subtitles; preserve transcription for internal scoring/semantic analysis; retain the frozen Shorts duration limit unless the owner explicitly changes it.
```


### Copy-ready prompt — ROADMAP-10.5: Final release gate and maintenance handoff

```text
You are the ClipForge engineering agent working in `D:\automation video clips\clipforge`.

WORK ITEM: ROADMAP-10.5 — Final release gate and maintenance handoff
STATE: Reconcile current repository state before acting. Do not assume this item is open just because it appears in the roadmap.

1. PROBLEM / OBJECTIVE
Produce an evidence-backed release decision and ongoing maintenance package.

2. PREFLIGHT AND EVIDENCE COLLECTION
Read `AGENTS.md`, the applicable freeze/rule files, `docs/engineering/PHASE_TRACKER.md`, `MASTER_EXECUTION_LEDGER.md`, `IMPLEMENTATION_STATUS.md`, `ENGINEERING_DEFECT_REGISTER.md`, `PIPELINE_CATALOG_AND_DEPENDENCY_GRAPH.md`, `FRONTEND_PAGE_FEATURE_INVENTORY.md`, `PROJECT_CONTINUITY.md`, and the newest relevant audit/decision-log entries. Read only files relevant to this scope in depth, but reconcile any status claims before editing.
Inspect actual current source, schema, runtime route/client/task contracts, tests and caller/callee relationships. Reproduce the reported behavior with a safe isolated fixture where feasible. Separate VERIFIED FACTS, INFERENCES and UNKNOWNS. Record exact file paths, line ranges, commands and observed outputs.
Reconcile all final records and verify the latest source diff, tests, runtime evidence, open defects, security posture and known limitations.
Capture `git status --short`, branch/commit, existing diff/untracked inventory and relevant environment/container identity before editing. Protect all pre-existing changes. Do not assume old hashes, route counts, schema revisions or historic reports still reflect the current environment.

3. COMPARE APPROACHES AND JUSTIFY THE CHOICE
Approach selection method: Compare at least two plausible approaches where meaningful: (A) smallest local repair, (B) reuse an established repository abstraction/pattern, and (C) architectural change only if the first two cannot meet verified requirements. Use evidence, not preference. Evaluate correctness, data safety, architectural consistency, backwards compatibility, idempotency/concurrency, performance, testability, reversibility, scope and maintenance cost. Record the chosen approach and specific reasons each alternative was rejected. If the problem is already solved in current source, choose the no-op verification path.
Before coding, write a small comparison table in the decision log: option; correctness against acceptance criteria; data/security risk; compatibility; concurrency/idempotency; complexity/maintenance; reversibility; evidence for/against. Do not create arbitrary numerical scores. Explain why the chosen approach is proportionate to the proven root cause and why each rejected alternative is inferior for this evidence.
If the current implementation already meets the requirement, choose verification-only and avoid a redundant change. If requirements remain ambiguous and a wrong choice would be consequential, stop at a documented blocker rather than invent behavior.

4. IMPLEMENTATION BOUNDARY
Implement only this work item. Prefer the smallest complete, maintainable fix using existing models, APIs, task lifecycle, storage/artifact and frontend patterns. Avoid duplicate frameworks, helpers, routes, state machines, database fields or tests when an existing abstraction meets the requirement.
Preserve all unrelated behavior and frozen components. Do not remove code based on apparent lack of callers without a call-site/dependency audit. Do not change public API semantics without documenting callers, compatibility plan and tests. Any migration must be justified, forward-only and data-preserving.
Scope-specific acceptance criteria:
- Classify each release criterion pass/fail/blocked and cite evidence.
- State deployment steps, monitoring, backups, credential lifecycle, escalation and maintenance owner.
- Keep unsupported feature flags documented and no false production-ready language.

5. REQUIRED TESTING
Add focused regression tests for the root cause and relevant negative, failure, boundary, retry, concurrency and stale-state paths. Assert durable database/filesystem/worker state as applicable, not only mocked return values. Use synthetic media, disposable test records and test provider mode. Never publish to real YouTube or destructive-clean real data.
- Final regression, install rehearsal, live-worker/browser tests for critical workflows, restore evidence and ledger consistency.
- No unreviewed diff after verification passes.
Run the exact focused suite, relevant regressions, static checks and build/browser/integration tests required by the changed layers. Capture actual commands, counts, exit codes, warning/failure output and environment. Do not claim a test ran if only drafted or launched without a completed result.

6. THREE VERIFICATION PASSES — REQUIRED FOR THIS ITEM
PASS 1 — Implementation verification: review diff against every acceptance criterion; run focused tests and the affected workflow; prove expected state and failure behavior.
PASS 2 — Independent challenge: stop thinking like the implementation author. Re-read the requirement and original defect evidence. Try to falsify the fix with adversarial inputs, conflicts, retries, parallel requests, stale state and failure injection. Compare alternative approaches again. Inspect whether the tests could pass while production is still broken. Fix any issue discovered and record changes since Pass 1.
PASS 3 — Differential re-verification: re-read the final diff and working tree from scratch. Compare final code with Passes 1 and 2, identify all changes introduced after each earlier pass, rerun affected focused tests and relevant regressions against the final tree, and verify reports/status files match the final code. Any new code change invalidates the affected previous pass; repeat it.

7. EXPLICIT SELF-CHALLENGE QUESTIONS
- What concrete evidence proves the original problem existed?
- Why does each changed line/function need to exist?
- What alternative was considered and why was it rejected?
- Could a real production record or untrusted caller reach the test/mock path?
- What happens on failure, retry, concurrency, restart and stale response?
- What does this test prove, and what does it not prove?
- Did I preserve all previous working-tree files and frozen behavior?
- What changed between verification passes and why?
- Which claims remain unverified or depend on an environmental assumption?

8. REQUIRED RECORDS AND FINAL RESPONSE
Update only applicable canonical documents: phase tracker, master ledger, implementation status, defect register, relevant API/frontend/pipeline inventories, audit report and `docs/engineering/AI_DECISION_LOG.md`. Preserve old audit records and append corrections instead of rewriting history. Make status consistent everywhere.
Record work-item ID, before/after working-tree status, root cause, option comparison and rationale, files changed and purpose, relevant hashes if practical, each pass and test result, evidence tier (source/unit/mock/API/in-process/live worker/browser/full E2E), risks, limitations and next dependency.
Report statuses honestly: DELIVERED & VERIFIED, PARTIALLY VERIFIED, BLOCKED or REOPENED. Do not say full E2E without the real required components running together.

9. STOP / CONTINUE RULE
Do not start a different implementation item in parallel or expand this scope to unrelated fixes. Complete all three passes, update records and then continue automatically to the next unblocked item in the master execution queue without waiting for routine approval. Stop only for a real blocker, unresolved high-impact product choice, credential/account action, real publication, destructive action against actual data, or an environment change that requires owner authorization. If blocked, document exact evidence and work safely on independent unblocked work only if it does not depend on the blocker.
Never use `git reset`, `git clean`, blanket reverts, destructive DB resets, `docker compose down -v`, or broad file deletion. Do not reintroduce captions/subtitles; preserve transcription for internal scoring/semantic analysis; retain the frozen Shorts duration limit unless the owner explicitly changes it.
```


# PART D — Required deliverables for every prompt

For each work item, the AI must produce all of the following before moving on:

1. **Problem record:** exact symptom, reproduction and objective evidence; state whether the issue was reproduced.
2. **Source trace:** caller-to-callee path, schema/data model, task/worker, storage lifecycle and UI state as applicable.
3. **Options analysis:** at least two plausible options when meaningful, trade-offs and evidence-based rejection reasons. Do not invent numeric scores.
4. **Implementation record:** files changed and one-line purpose for each; migrations/API contract changes and compatibility impact if any.
5. **Verification Pass 1:** acceptance tests and original defect reproduction/closure evidence.
6. **Verification Pass 2:** independent adversarial challenge, alternative comparison, failure/concurrency/stale-data tests and changes after Pass 1.
7. **Verification Pass 3:** final diff review, repeat tests against final tree, compare with earlier passes and reconcile docs.
8. **Decision log:** facts/inferences/unknowns separated; decision rationale; alternatives rejected; risks and next dependency.
9. **Final status:** Delivered & Verified / Partially Verified / Blocked / Reopened. State actual evidence tier.
10. **Autonomous continuation:** identify the next unblocked work item and continue without routine approval, but stop on high-impact irreversible actions or genuine blockers.

The agent must not claim that it has provided private hidden chain-of-thought. `AI_DECISION_LOG.md` is an audit trail of evidence, technical options, decisions, rationale and verification deltas.
