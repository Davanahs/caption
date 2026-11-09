# ClipForge — Full Roadmap Cross-Verification Prompt (Phases 0–7, 20 Canonical Work-Items)

> **Purpose:** Independently cross-verify every claimed-delivered phase and work-item one by one, in detail, against the actual repository, tests, database migration state, runtime containers, and durable engineering records. This is an audit—not a request to reimplement the roadmap.
>
> **Repository:** `D:\automation video clips\clipforge`
>
> **Reported baseline:** branch `version-4-gen`, commit `0ba85ff` (verify actual current state; do not assume it is unchanged).
>
> **Reported completion claim:** 20 of 20 canonical work-items delivered, verified and frozen; 270/270 tests passed; TypeScript check clean; Next.js build clean with 11/11 pages; six Docker containers healthy; Alembic head `c3d4e5f6a7b8`; logic domains L1–L10 frozen. **All of these are claims to independently verify, not facts to copy into the conclusion.**

---

## 0. Mission and required operating mode

Conduct a complete, evidence-led, read-only cross-verification of the 20 work-items listed in this prompt, in the exact order shown in the roadmap matrix. Assess each item individually before drawing an overall conclusion.

Do **not** trust a status label, previous audit, test summary, screenshot, green build, or statement such as “fully verified” without checking the strongest available underlying evidence. Preserve prior reports as historical evidence; compare their claims with the current repository and current runtime.

### Strict scope

- Do not reimplement, refactor, clean up, or redesign functionality during this audit.
- Do not change application source code, tests, schemas, migrations, Docker/Compose configuration, environment variables, secrets, or production database rows.
- Do not run `git reset`, `git clean`, blanket revert commands, broad file deletion, or storage cleanup.
- Do not publish, upload, schedule, or otherwise send any video to a real external account.
- Do not modify OAuth credentials, tokens, production artifacts, or user media.
- Do not restart a running worker or other service while active work could be interrupted. First inspect service health and active/reserved work. If a restart is needed to obtain reliable evidence and is not demonstrably safe, mark that check **BLOCKED / NOT VERIFIED** and report the exact blocker; do not silently proceed.
- Tests that create or mutate data must use an explicitly isolated test database, synthetic fixture, and temporary storage. Inspect the test code before executing any suite that may delete files, change production-like records, apply migrations, or invoke external APIs.
- Do not claim a check was performed if it was only planned, inspected in source, mocked, or simulated.
- Preserve all existing dirty working-tree changes and untracked files. Record initial and final `git status --short` and compare them.
- Do not pause for routine approval between work-items. Complete the audit sequentially in this one run unless a safety boundary, credential requirement, unavailable environment, destructive operation, or active-job risk requires a stop.
- Do not begin a new implementation phase. At the end, stop and await explicit user direction before any fixes.

### Required audit outputs

Create one report:

`docs/engineering/audits/FULL_ROADMAP_CROSS_VERIFICATION_AUDIT.md`

If the repository is unavailable or the audit cannot safely write documentation, produce the same report in the session output without fabricating a repository write. The report must include:

1. Repository identity, timestamp, branch, current commit and initial/final working-tree status.
2. An executive status table for all 20 canonical items.
3. Item-by-item evidence, exact commands, exit codes, test counts, test environment, and limitations.
4. The claimed `270/270` test tally reconciliation: exact suites and commands, no double-counting, and whether all 270 tests actually ran in the current verification.
5. Frontend TypeScript/build evidence, actual route/page counts as applicable, Docker container health evidence, current database migration head, and Logic Freeze Ledger evidence.
6. Every contradiction, missing artifact, stale report, route/API mismatch, hidden bypass, unverified assertion, failing test, and newly discovered risk.
7. A final decision: `VERIFIED`, `VERIFIED WITH LIMITATIONS`, `NOT VERIFIED`, or `FAILED` for the overall roadmap claim.
8. Explicit confirmation that no application code or production data was changed during the audit.

Do not change the official phase status labels solely to make documents consistent. If evidence contradicts a status, report the discrepancy and propose the smallest documentation correction separately.

---

## 1. Mandatory evidence standard

Use these evidence tiers and label the strongest tier actually achieved for each acceptance criterion:

- **E0 — Documentation only:** a claim appears in a report, ledger, screenshot caption, or scorecard, without direct corroboration.
- **E1 — Source inspection:** the current implementation is inspected and the relevant logic is traced. This is not proof that it works at runtime.
- **E2 — Unit / mocked test:** controlled tests prove a limited unit or contract. Mocked dispatch is not worker execution.
- **E3 — API/database integration:** actual HTTP/API behavior and isolated database persistence are exercised together.
- **E4 — Real local worker / media execution:** a real local task worker consumes the task, executes the path, persists terminal state, and produces or validates any expected artifact in isolated storage.
- **E5 — Browser end-to-end:** actual browser UI connects to the real local backend, the action executes, persisted state changes, and refreshed UI agrees with the authoritative state.
- **E6 — Cross-system operational evidence:** relevant live services, database, queue, storage and application version are correlated with task IDs and logs. No real external publishing is required or allowed for this audit.

For each claim, say what it proves and what it does **not** prove. A test suite passing against mocks cannot be called E4/E5. A healthy container does not prove that it is running the current source. A task ID returned to the UI proves dispatch acknowledgement only unless worker completion is independently verified.

### Status vocabulary

Use exactly one status per work-item:

- `VERIFIED` — all required acceptance criteria have direct evidence at the appropriate tier; no material blocker remains.
- `VERIFIED WITH LIMITATIONS` — the core behavior is demonstrated, but one or more criteria are evidenced only at a lower tier or have a documented bounded limitation.
- `NOT VERIFIED` — evidence is missing, stale, ambiguous, or insufficient to establish the claim.
- `FAILED` — a reproducible defect, regression, safety violation, data inconsistency, or failed acceptance criterion is found.
- `BLOCKED` — verification could not safely or technically proceed; include exact reason and next required evidence.
- `NOT APPLICABLE` may only be used where an acceptance criterion genuinely does not apply, with a reason.

A roadmap item may be marked verified only when all material required criteria pass. Do not average away a security, data-integrity, or real-worker failure.

---

## 2. Global preflight — do this before work-item 0.0

1. Read all governing instructions and ledgers in their current form:
   - `AGENTS.md`
   - applicable `.agents` rules and `MASTER_ENGINEERING_RULEBOOK.md`
   - `ANTIGRAVITY_CLIPFORGE_FREEZE_RULES.md`
   - `docs/engineering/MASTER_EXECUTION_LEDGER.md`
   - `docs/engineering/PHASE_TRACKER.md`
   - `docs/engineering/IMPLEMENTATION_STATUS.md`
   - `docs/engineering/ENGINEERING_DEFECT_REGISTER.md`
   - `docs/engineering/PIPELINE_CATALOG_AND_DEPENDENCY_GRAPH.md`
   - `docs/engineering/FRONTEND_PAGE_FEATURE_INVENTORY.md`
   - `docs/engineering/PROJECT_CONTINUITY.md`
   - `docs/engineering/LOGIC_FREEZE_LEDGER.md`
   - all relevant Phase 0–7 audit reports listed in the trackers.
2. Record the current `git rev-parse HEAD`, branch, `git status --short`, and any available hashes from historical reports. Do not assume the reported `0ba85ff` baseline is current.
3. Identify the current Python environment, frontend package manager/build scripts, Compose services, actual database connection target (without printing secrets), and current active worker/job status.
4. Confirm the code version used by backend and worker containers. Container health alone is insufficient; compare image/source revision or fingerprints and startup logs.
5. Inspect test suites before running them. Identify tests that delete files, mutate database state, apply migrations, launch real jobs, or contact providers. Use isolated safe runs only.
6. Do not begin with implementation. First establish what code and data actually exist.

---

## 3. Phase-by-phase cross-verification matrix

Verify every item below individually and in order. The descriptions below define what to investigate; they do not assert that an implementation exists or that it passes.

### Phase 0 — System discovery and baseline

#### Work-item 0.0 — Comprehensive System Discovery & Remediation Roadmap

**Reported outcome:** system discovery and remediation roadmap delivered.

**Cross-verify:**
1. Find the original discovery/audit report and its date, scope, repository commit, runtime environment, database revision, and explicit limitations.
2. Check whether the reported subsystems, APIs, pages, tasks, storage namespaces and providers actually existed at the audited revision.
3. Determine whether findings were recorded as evidence-based defects, hypotheses, or recommendations. Check that later ledgers did not silently convert hypotheses into confirmed defects.
4. Verify that every claimed remediation item maps to a unique tracked phase/work-item or defect ID, without duplicate/conflicting identities.
5. Check whether optional work such as dubbing, multi-destination publishing, or provider integrations was labeled separately rather than treated as delivered by implication.
6. Compare the roadmap with current code and note stale or superseded findings.

**Pass evidence:** a traceable original discovery artifact, scope/commit metadata, defect-to-work-item map, and explicit list of unresolved or unverified claims. If the original evidence is missing, do not infer what it contained.

#### Work-item 0.1 — Baseline Reconciliation, Master Ledgers & Tracking System

**Reported outcome:** canonical baseline and engineering records reconciled.

**Cross-verify:**
1. Current Git branch/HEAD/dirty-tree state and whether it is safely recorded.
2. Alembic revision graph, actual current revision, single-head status, and whether the reported `c3d4e5f6a7b8` is the real database head. Use read-only database inspection; do not migrate.
3. Current FastAPI route objects categorized separately as HTTP API routes, WebSocket routes, docs/OpenAPI routes, static mounts, and special guard routes. Reconcile them with the endpoint inventory; do not conflate route objects, HTTP method/path pairs, and user-facing APIs.
4. Current Next.js page inventory and UI-control/interaction inventory against actual files and components.
5. Defect register IDs, status definitions, duplicate IDs, unresolved findings and links to evidence.
6. Consistency across the master ledger, phase tracker, implementation status, dependency graph, frontend inventory, continuity file, and logic-freeze ledger.
7. Verify historical test claims against actual command, environment, output and date.

**Pass evidence:** repeatable read-only counts, coherent migration graph/database head, inventories tied to current source, and no unexplained contradiction in canonical records.

---

### Phase 1 — Automation, processing and channel integrity

#### Work-item 1.1 — Multi-Video Automation Selection & Dispatch Verification

**Reported outcome:** multi-channel/video selection and dispatch fixed and browser-verified.

**Cross-verify:**
1. Trace selection state from UI through channel grouping, request construction, backend validation, dispatch and selection reconciliation.
2. Verify global multi-channel selection does not accidentally use only the first selected channel.
3. Confirm channel-scoped actions do not consume or clear selections belonging to other channels.
4. Verify successful/accepted/already-processing items are reconciled separately from failed, rejected or unresolved items.
5. Test partial network failure, per-item backend rejection, duplicate clicks, deselection, retry and refresh behavior.
6. Review whether previous browser tests intercepted/mock network requests. Separate UI/request-construction proof from real backend dispatch proof.
7. Run safe focused tests and relevant browser tests; ensure no real videos are published.

**Pass evidence:** exact requests and item IDs correlate with expected per-channel groups; failure state remains recoverable; no selection loss or duplicate processing; claims accurately label mocked versus live API tests.

#### Work-item 1.2 — Start Processing → Dashboard E2E Verification

**Reported outcome:** job is persisted, dispatched to Celery, progresses, and appears in Dashboard/history.

**Cross-verify:**
1. Trace API request → durable Job creation → Celery task ID/dispatch → worker task → progress persistence → terminal status → Dashboard active/history UI.
2. Verify task dispatch errors update the persisted job to a truthful failure state instead of leaving a pending ghost.
3. Verify progress is monotonic/valid according to the existing state machine and terminal outcomes do not get overwritten by stale progress.
4. Verify page refresh reconstructs state from backend persistence rather than relying only on transient browser state.
5. Verify failed jobs, retry behavior, cancellation and duplicate dispatch protections without disturbing current jobs.
6. Inspect whether the historical synthetic fixture is still used and whether the fixture is clearly isolated.
7. Inspect evidence for the claimed real worker execution, output dimensions/duration, storage key and mock-publish status. Confirm no external YouTube call was made.

**Pass evidence:** a safe synthetic job has correlated IDs, real worker logs, durable progress/terminal status, valid expected artifact where required, and UI/history state that persists after refresh. If only a mocked test exists, record the lower evidence tier.

#### Work-item 1.2.1 — Synthetic Test-Fixture Isolation (`CF-DEF-009`)

**Reported outcome:** test fixtures are only substituted when explicit trusted test context is established.

**Cross-verify:**
1. Trace `is_test` from authoritative database records (`Job`, `Channel`, or the current canonical trusted context) into downloader, transcriber and relevant task entry points.
2. Confirm production URL substrings such as “synthetic biology”, “mock”, “test fixture” or similar are not sufficient to activate fixture substitution.
3. Confirm missing or ambiguous test context fails closed.
4. Verify test context is not inferred solely from a publishing environment variable.
5. Inspect all call sites and parameter defaults for `get_video_info`, `download_video`, `transcribe_video` and associated tasks.
6. Run the existing isolation suite and adversarial test cases using isolated data.

**Pass evidence:** synthetic substitution is impossible for ordinary production requests solely due to ID/URL content or config mode; trusted fixtures work deliberately; regression tests cover both sides.

#### Work-item 1.3 — Storage Cleanup Endpoint Backend Delivery & UI Wiring (`CF-DEF-001`)

**Reported outcome:** preview/execute endpoints and Safe Cleanup UI delivered with HMAC preview tokens, quarantine, durable journaling and protection of referenced files.

**Cross-verify:**
1. Verify preview endpoints are strictly read-only; record and filesystem state must not change on preview calls.
2. Confirm execute requires a valid, unexpired token that binds the correct preview and candidate identities/threshold.
3. Validate path canonicalization, path containment, symlink handling, same-filesystem guarantees, quarantine route suppression, journal recovery and startup reconciliation.
4. Confirm published media, high-scoring/protected clips, active jobs, task executions, storage reservations, active writers, and shared artifacts are protected.
5. Verify missing-media records are preserved by default and failures are surfaced without false success.
6. Inspect the test fixture seeding process and prove it only targets isolated synthetic records/files. **Do not run cleanup against real outputs as part of this audit.**
7. Verify localhost-only host bindings and document that loopback binding is a deployment boundary, not application authentication.
8. Check interrupted execution/recovery, partial failure and idempotency using isolated temp storage and test DB.

**Pass evidence:** tests and code prove preview/execute separation, token rejection cases, all protection rules, journal recovery and isolation. If destructive tests are unsafe, mark those criteria not verified instead of trying them on user data.

---

### Phase 2 — Clip preview AI enhancement integration and safety

#### Work-item 2.1 — Clip Preview AI Enhancements UI Wiring (`CF-DEF-004`)

**Reported outcome:** Hooks, B-roll and SFX controls are wired to backend APIs and task dispatch.

**Cross-verify:**
1. Trace each UI tab/action separately: Hooks plan retrieval/generation/application; B-roll planning/application; SFX planning/application.
2. Confirm client types, route paths, request/response schemas, task names and IDs agree across frontend and backend.
3. Verify loading, empty, error, queued, running and completed states are correctly represented.
4. Distinguish UI rendering and mocked dispatch from real worker execution and completed artifact retrieval.
5. Inspect artifacts, `ClipVariant`, `ArtifactRecord`, ownership, status and storage keys; check that failed tasks don't create false completed rows or orphans.
6. Verify Hook overlay is distinct from captions/subtitles; confirm no caption generation, ASS/SRT generation or subtitle burn-in was reintroduced.
7. Reconcile reported test counts, screenshots and `CF-DEF-004` status with actual evidence.

**Pass evidence:** per-feature contract and UI behavior verified. Do not claim end-to-end completion solely because the tab renders or a task ID is returned.

#### Work-item 2.1.1A — SFX Fallback Production Isolation (`CF-DEF-011`)

**Reported outcome:** an empty production SFX library returns a safe empty plan (or defined error) rather than synthesizing test tones.

**Cross-verify:**
1. Trace every call site of `_mock_generate_asset()` and prove it is reachable only after trusted test-context authorization.
2. Verify the production-empty-library path produces no tone audio, no mock `SFXAsset` row, no synthetic `ArtifactRecord`, and no mixing of tone into a real clip.
3. Check existing synthetic assets are filtered from production plan selection.
4. Verify FFmpeg failure paths do not leave half-written assets or orphan database records.
5. Verify ordinary valid SFX assets still plan and apply normally.
6. Re-run focused isolation tests only in isolated database/storage.

**Pass evidence:** assertions cover both result and database/filesystem side effects. Source inspection alone does not prove transaction safety.

#### Work-item 2.1.1A.1 — Trusted Test-Context Enforcement

**Reported outcome:** synthetic fallback is authorized by verified DB-backed test context; test-like identifiers alone cannot authorize it.

**Cross-verify:**
1. Read `_is_trusted_test_clip()` and its callers directly.
2. Ensure no `clip_id`, `channel_id`, `run_identity`, filename or prefix alone grants test status.
3. Inspect the origin of `explicit_is_test`; confirm callers cannot pass `True` from an untrusted API payload/task argument and elevate a production clip.
4. Resolve Job and Channel relationship logic and confirm missing/conflicting flags fail closed according to the current documented contract.
5. Confirm a DB-backed verified test Job/Channel still supports intentional synthetic tests.
6. Execute test-prefixed production-ID adversarial cases and assert zero synthetic assets/artifacts were added.

**Pass evidence:** current source and adversarial isolated tests prove prefix-only and caller-override authorization paths are absent.

#### Work-item 2.1.1B — SFX Plan GET Cleanup & Event-Loop Protection (`CF-DEF-012`)

**Reported outcome:** GET is read-only, plan generation is explicit, and expensive synchronous FFprobe work does not block the FastAPI event loop.

**Cross-verify:**
1. Inspect the actual GET route and all callees for commits, inserts, updates, task dispatches and hidden generation side effects.
2. Verify repeated GET and GET with a missing plan do not create/update `ClipSFXPlan`, `ClipRetention`, synthetic assets or artifacts.
3. Confirm explicit generation is handled by the intended POST/task contract and its response matches the frontend.
4. Inspect `ViralityPredictor.analyze_clip()` and all call sites; prove expensive subprocess work is off the ASGI event loop or safely executed in a worker.
5. Confirm async DB sessions are not shared across threads/tasks and error paths don't report false success.
6. Verify idempotency/concurrency for plan generation and that preview loading still works after refresh.

**Pass evidence:** DB snapshots before/after read-only requests, instrumentation proving GET does not invoke expensive analysis, and tests showing explicit generation/application work.

#### Canonical C-02 — Hook Task Runtime Remediation

**Reported outcome:** Hook analysis/application no longer fails on event-loop usage, retention schema parsing or non-canonical storage access.

**Cross-verify:**
1. Inspect all Hook tasks and identify exact async/sync boundaries.
2. Verify the previous `asyncio.get_event_loop()` failure is eliminated by a safe execution strategy appropriate to the actual task context.
3. Verify `RetentionAnalysis` JSON normalization handles the actual stored form(s), including list and structured object forms where supported; malformed data must fail clearly rather than be coerced silently.
4. Verify storage access uses the canonical artifact manager/context manager and never assumes a storage key is a host filesystem path.
5. Check Hook plan persistence, result lifecycle, artifact metadata and task status transitions.
6. Run isolated in-process and live worker tests if safely available; distinguish them explicitly.

**Pass evidence:** successful Hook plan and overlay execution with valid input, expected persistence/artifact output, and tested schema/event-loop/storage failures.

#### Canonical C-03 — Live Docker Worker Refresh & AI Enhancement Live Execution

**Reported outcome:** worker runs the intended current code and successfully executes Hook, B-roll and SFX tasks.

**Cross-verify:**
1. Inspect Compose configuration and identify actual container names, image IDs, creation/start times, health and code mount/build arrangement.
2. Correlate the code/version loaded by backend and worker. Do not assume source code changes are loaded just because containers are healthy.
3. Check for active/reserved tasks before any potential restart. Never interrupt active work. If a restart would be unsafe, mark the check blocked.
4. Using isolated synthetic fixtures and a test DB, dispatch one task per feature through the real configured queue/worker.
5. Record task IDs, worker logs, database terminal state, artifact keys and file validation results for each feature.
6. Confirm failure behavior and that no real YouTube publishing request is made.
7. Ensure the evidence proves worker consumption, not only `.delay()` return or `task.apply()` execution.

**Pass evidence:** correlated live worker task success for all three features, current worker/code identity, persisted completed status and valid artifacts. A healthy container alone is insufficient.

#### Canonical C-04 / Phase 2.2 — Decision Customization Race Guard (`CF-DEF-007`)

**Reported outcome:** row-level locking (reported `SELECT FOR UPDATE`) prevents conflicting concurrent single-video customization/decision updates.

**Cross-verify:**
1. Identify the exact model, route/task and transaction containing the race.
2. Inspect whether locking is supported by the actual PostgreSQL backend and applied inside the same transaction as validation and update.
3. Check that lock scope and order avoid deadlocks and don't serialize unrelated clips unnecessarily.
4. Run concurrent opposing customization requests against isolated PostgreSQL records; prove the final state satisfies the declared invariant and no lost updates occur.
5. Verify invalid/stale requests return the documented conflict/error and that the UI preserves clear state.
6. Confirm there is no misleading test that mocks the lock itself or uses SQLite semantics as proof of PostgreSQL behavior.

**Pass evidence:** repeatable concurrent integration test against PostgreSQL with assertions on final DB state, transaction isolation and error outcomes.

---

### Phase 3 — Publishing queue and metadata

#### Canonical C-05 / Phase 3.1 — Publish Queue Interactive Cancel/Retry & Error Recovery (`CF-DEF-003`)

**Reported outcome:** cancel, retry and error recovery controls are connected to durable backend/worker behavior.

**Cross-verify:**
1. Trace each UI action to route, persisted state change, Celery task/revoke behavior and terminal UI state.
2. Verify cancel is idempotent, respects terminal-state guards, records cancellation intent where required, and doesn't falsely claim a running worker stopped just because revoke was requested.
3. Verify retries are permitted only for eligible states, are idempotent, increment/report attempts correctly, and cannot double-publish.
4. Verify transient versus terminal errors are represented accurately and retryable errors don't lose their diagnostic details.
5. Test queued, active, already-cancelled, completed, failed and retry cases using isolated records and mock publishing.
6. Confirm UI state refresh and task/job state agree.

**Pass evidence:** API/DB/worker integration with correct task lifecycle and no external upload.

#### Canonical C-06 / Phase 3.2 — Video Metadata Publishing Editor

**Reported outcome:** title, description, tags and privacy editor loads, validates, saves and refreshes real backend metadata.

**Cross-verify:**
1. Trace each field from form to client types, API schema, backend validation, DB persistence and publisher request.
2. Verify supported limits/normalization, empty values, invalid values, privacy enums, tags and description length against the current contract.
3. Confirm unsaved edits, saving state, failure messages and post-save refresh are accurate.
4. Verify metadata used at publish time comes from the intended authoritative saved record, not a stale frontend-only value.
5. Use mock publishing; inspect the prepared payload but do not upload to YouTube.
6. Check that unsupported settings are clearly labelled rather than silently accepted.

**Pass evidence:** end-to-end metadata persistence and mock publisher payload assertions for valid and invalid inputs.

---

### Phase 4 — Analytics, tracking and rate governance

#### Canonical C-07 / Phase 4.1 — Per-Video Analytics, Tracking Queue & SEO Recommendations (`CF-DEF-005`)

**Reported outcome:** per-video performance data, tracking queue actions and SEO recommendation workflow are connected.

**Cross-verify:**
1. Trace selected video identity through each request, ensuring metrics cannot silently be assigned to the wrong video/channel.
2. Inspect metric provenance, timestamp, source, scan coverage and labels; verify no unsupported lifetime claims or guessed metrics.
3. Verify tracking queue create/list/refresh/cancel states and backend worker behavior.
4. Verify SEO UI uses actual backend output and distinguishes no recommendations, loading, failure and valid results.
5. Verify page refresh restores authoritative state and stale responses do not overwrite newer data.
6. Test expected empty/error cases and access boundaries without calling paid/external services unnecessarily.

**Pass evidence:** real local API/database integration and accurate frontend representation; clearly label any mocked provider data.

#### Canonical C-08 / Phase 4.2 — Channel Analytics Polling Governance & Rate-Limit Cooldown

**Reported outcome:** polling is governed, rate limited and respects provider cooldowns.

**Cross-verify:**
1. Trace polling initiator, scheduler/worker, refresh interval, concurrency controls and cancellation/unmount behavior.
2. Verify provider rate-limit signals lead to a persisted or authoritative cooldown used by all relevant callers.
3. Check exponential/backoff rules, jitter if specified, retry caps, `Retry-After` interpretation and prevention of request storms.
4. Confirm multiple frontend tabs/workers cannot bypass shared backend governance where global limits are required.
5. Use a mocked provider for 429/5xx/timeout responses and verify no tight retry loops.
6. Verify telemetry does not expose tokens/secrets.

**Pass evidence:** deterministic tests for cooldown and concurrency, plus source/runtime evidence of centrally enforced limits. Do not call a UI polling timer by itself “rate-limit governance.”

---

### Phase 5 — Dynamic settings persistence

#### Canonical C-09 / Phase 5.1 — Settings Backend Persistence (`REQ-GAP-001`)

**Reported outcome:** settings are stored and validated by the backend and have real runtime effects where promised.

**Cross-verify:**
1. Inventory every settings UI control and map it to an explicit supported backend setting, validation schema, persisted store and runtime consumer.
2. Check settings that remain only in `localStorage`; they must not be described as backend-persistent.
3. Inspect secrets handling, redaction, allowlisted keys, invalid key rejection, auth/trust boundary and unsafe arbitrary config writes.
4. Verify which settings apply immediately versus require restart; avoid claiming runtime impact without observing the consumer.
5. Test load/save/reload, invalid values, missing values, concurrent updates and secret response redaction using isolated config/test data.
6. Confirm settings survive frontend refresh and backend restart only when the declared storage guarantees support that claim.
7. Do not rewrite `.env` blindly or expose tokens through API responses/logs.

**Pass evidence:** every advertised setting has an explicit, tested contract; persisted values and runtime behavior agree; unsupported settings are honestly marked informational/restart-required.

---

### Phase 6 — Multi-language dubbing and Ollama removal

#### Canonical C-10 / Phase 6.1 — Dubbing Pipeline/UI Integration (`CAP-001`) and Complete Ollama Excision

**Reported outcome:** dubbing workflow is integrated and all Ollama dependencies are removed.

**Cross-verify dubbing:**
1. Map the entire dubbing UI workflow to API, tasks, models, storage, audio/video processing and final artifact state.
2. Verify route prefixes and correct async DB session use. Confirm no synchronous `.query()` calls are made on an `AsyncSession`.
3. Verify language/voice/translation inputs, unsupported language behavior, error reporting, retry and artifact lifecycle.
4. Use synthetic clips and local/mock providers; don't call paid APIs or publish externally.
5. Check real worker execution if the claimed phase includes it.

**Cross-verify Ollama excision:**
1. Search active source, imports, requirements/lockfiles, Compose files, environment variables, settings, docs, test helpers, scripts and runtime commands for Ollama endpoints, packages, service definitions and model names.
2. Classify each occurrence as active runtime dependency, test fixture, historical audit/migration reference or harmless documentation. Do not delete historical evidence merely to make grep return zero.
3. Verify no active service, fallback provider, config or dependency invokes Ollama.
4. Confirm model routing still has its explicitly supported behavior and no required provider path was accidentally removed.
5. Inspect dependency lockfile consistency and relevant tests/builds without reinstalling or changing dependency versions.

**Pass evidence:** documented active-dependency search with explained exceptions, valid dubbing route/task/storage flow, safe test results and no claim that mere text search proves runtime independence.

---

### Phase 7 — Final system lock and regression gate

#### Canonical C-11 / Phase 7.0 — End-to-End System Lock & Final Regression Gate

**Reported outcome:** complete system regression passed; ten logic domains L1–L10 are frozen.

**Cross-verify:**
1. Inspect the definitions and acceptance criteria for L1–L10 in `LOGIC_FREEZE_LEDGER.md`. Verify each frozen domain has concrete passing evidence and no unresolved blocker that contradicts its frozen label.
2. Re-run the final regression suite(s) in a cleanly described environment where safe; capture exact command, test IDs, counts, warnings, skips and failures. Avoid double counting overlapping suites.
3. Reconcile the “270/270 passed” claim to the exact unique tests and reports. Determine whether the number refers to one run, a sum across runs, or overlapping suites.
4. Run `npx tsc --noEmit` and the declared production build if safe; capture actual output and route/page totals.
5. Verify all six claimed Docker services and their roles, health, configured ports, actual running code version, active work and worker queues. Do not print secrets.
6. Verify database current Alembic revision is `c3d4e5f6a7b8` if that is still the recorded expected head. Inspect migration heads and drift without applying migrations.
7. Cross-check all API route/page/control inventories and ensure each user-visible action maps to a functioning route, intentional local-state operation, or documented external action.
8. Confirm no caption/subtitle generation or burn-in has reappeared; retain transcription for internal scoring/metadata/semantic analysis as the product rule requires.
9. Confirm storage safety, cleanup guards, test-fixture isolation, channel/destination authorization, cancellation behavior and no external publishing during tests.
10. Compare initial and final Git status; prove the audit did not alter application code or user data.

**Pass evidence:** final system state is demonstrably consistent, test count is reproducible and correctly described, all frozen domains have adequate evidence, and any gaps are documented. A green frontend build alone is not a final system lock.

---

## 4. Global reconciliation tasks after all 20 items

After assessing each item in order, perform these cross-cutting checks:

### A. Canonical work-item inventory

Confirm the scorecard contains exactly these 20 items:

1. 0.0 — Comprehensive System Discovery & Remediation Roadmap
2. 0.1 — Baseline Reconciliation, Master Ledgers & Tracking System
3. 1.1 — Multi-Video Automation Selection & Dispatch Verification
4. 1.2 — Start Processing → Dashboard E2E Verification
5. 1.2.1 — Synthetic Test-Fixture Isolation (`CF-DEF-009`)
6. 1.3 — Storage Cleanup Endpoint Backend Delivery & UI Wiring (`CF-DEF-001`)
7. 2.1 — Clip Preview AI Enhancements UI Wiring (`CF-DEF-004`)
8. 2.1.1A — SFX Fallback Production Isolation (`CF-DEF-011`)
9. 2.1.1A.1 — Trusted Test-Context Enforcement
10. 2.1.1B — SFX Plan GET Cleanup & Event-Loop Protection (`CF-DEF-012`)
11. C-02 — Hook Task Runtime Remediation
12. C-03 — Live Docker Worker Refresh & AI Enhancement Live Execution
13. C-04 / 2.2 — Decision Customization Race Guard (`CF-DEF-007`)
14. C-05 / 3.1 — Publish Queue Cancel/Retry & Error Recovery (`CF-DEF-003`)
15. C-06 / 3.2 — Video Metadata Publishing Editor
16. C-07 / 4.1 — Per-Video Analytics, Tracking Queue & SEO (`CF-DEF-005`)
17. C-08 / 4.2 — Channel Analytics Polling Governance & Cooldown
18. C-09 / 5.1 — Dynamic Settings Backend Persistence (`REQ-GAP-001`)
19. C-10 / 6.1 — Dubbing Pipeline/UI Integration (`CAP-001`) + Complete Ollama Excision
20. C-11 / 7.0 — End-to-End System Lock & Final Regression Gate

Do not quietly rename IDs, merge distinct items or create a new total. If canonical docs identify a different ID or dependency, record the discrepancy and show both names until explicitly reconciled.

### B. Cross-layer contract integrity

Check that frontend paths/types, backend routes/schemas, task signatures, database models/migrations, artifact keys and worker task registrations agree. A phase can pass locally while breaking a downstream consumer; inspect the dependency graph and use targeted integration tests for changed boundaries.

### C. Security and data integrity

Adversarially assess:

- Production/test identity separation and mock media fallback.
- Path traversal, symlinks, public exposure of quarantine/temp files.
- Active/published/shared artifact protection and reservation accounting.
- Stale tasks, cancellation races, duplicate retries and concurrent decisions.
- Untrusted settings keys, secrets in logs/API responses and OAuth account isolation.
- Provider timeouts, rate-limit storms and repeated expensive GET operations.
- Dubbing output access, media validation and provider error behavior.

Do not perform destructive or external actions to test these. Use isolated fixtures and state assertions.

### D. Documentation integrity

Verify that `MASTER_EXECUTION_LEDGER.md`, `PHASE_TRACKER.md`, `IMPLEMENTATION_STATUS.md`, `ENGINEERING_DEFECT_REGISTER.md`, `PIPELINE_CATALOG_AND_DEPENDENCY_GRAPH.md`, `FRONTEND_PAGE_FEATURE_INVENTORY.md`, `PROJECT_CONTINUITY.md`, `LOGIC_FREEZE_LEDGER.md` and all cited phase audit reports:

- Use consistent canonical IDs and current status.
- Link statuses to concrete evidence and test run context.
- Distinguish historical state from current state.
- Do not mark a defect resolved only because a UI control exists or a mocked test passes.
- Do not mark a logic domain frozen if relevant material evidence remains failed/unverified.
- Preserve historical reports and document corrections as addenda rather than rewriting what was known at the time.

---

## 5. Three-pass verification protocol (required for every item)

The same three passes must be completed separately for **each** of the 20 work-items, not just for the entire project at the end.

### Pass 1 — Direct implementation verification

- Read the relevant current source and contract definitions.
- Reproduce the original problem or establish the exact user-visible behavior.
- Run the most focused safe tests.
- Compare results against explicit acceptance criteria.
- Save exact test IDs and command output.

Write a Pass 1 note before continuing.

### Pass 2 — Independent adversarial engineering review

Temporarily challenge the Pass 1 conclusion. Do not merely repeat the same test. Ask:

1. What assumptions did Pass 1 make?
2. Does the test exercise the real production path or mock the crucial behavior?
3. Can malformed input, missing records, conflicting flags, concurrency, stale state, timeout, worker restart or partial failure bypass the fix?
4. What alternative implementation approaches exist? Compare correctness, security, concurrency, failure recovery, compatibility, complexity and maintenance cost.
5. Why does the selected existing design best satisfy the evidenced requirements? What evidence would disprove that conclusion?
6. Does the code preserve product invariants, including no captions/subtitles, internal-only transcription usage, test/production isolation and no external publishing during tests?
7. Are there downstream consumers, migrations, UI state or workers that Pass 1 did not exercise?

Run additional adversarial tests or read-only traces when safe. If one cannot be run, record why. Revise the item status if Pass 2 exposes a gap.

### Pass 3 — Delta and independent closeout verification

- Compare current source, test files, test outcomes and working tree to the exact baseline captured at the start of this item.
- Enumerate every file changed during the phase's original implementation, if Git history or audit hashes make this possible; if not, state that the delta could not be reconstructed.
- Re-run the narrow tests that prove the corrected behavior and any regression test introduced/identified by Pass 2.
- Re-read the acceptance criteria without relying on the prior conclusion, and answer each criterion explicitly `PASS`, `FAIL`, `NOT VERIFIED`, or `BLOCKED` with evidence.
- Ensure the documentation accurately describes exactly what was run—not what was intended or planned.
- Record any differences from Pass 1, why the conclusion changed or remained stable, and the evidence behind the final status.

Do not call three repetitions of the same mocked test three independent passes. The passes have different purposes.

---

## 6. Decision methodology required when defects are found

This is an audit-only task, so do not apply fixes. For every defect discovered, record a **proposed decision entry** with:

1. **Observed problem:** exact behavior, input, endpoint/task/file, timestamp or test ID.
2. **Evidence:** log excerpts with secrets redacted, source locations, DB state or artifact observations.
3. **Expected invariant:** what must always be true and which existing contract defines it.
4. **Root-cause confidence:** confirmed / probable / unknown, with reasons.
5. **Candidate approaches:** at least two plausible approaches where meaningful, including the least invasive option.
6. **Comparison criteria:** correctness, safety, concurrency, idempotency, data compatibility, runtime cost, observability, rollback/recovery, maintainability and testability as relevant.
7. **Selected recommendation:** the smallest approach that satisfies the evidence, and why.
8. **Rejected alternatives:** reasons, not merely “not chosen”.
9. **Risks and falsification test:** what could make the recommendation wrong and how to test it.
10. **Scope boundary:** files/components potentially affected, frozen domains protected, tests required, rollback strategy and whether a migration/external operation would be consequential.
11. **Approval boundary:** routine reversible fixes can follow the autonomous regimen after the audit; production data deletion, external publishing, credential changes, destructive migrations, or interrupting active jobs require explicit authorization.

Do not invent a private hidden chain-of-thought transcript. Keep a concise, evidence-based decision record explaining conclusions and alternatives, not speculative internal monologue.

---

## 7. Autonomous progression and stop rules

- Continue from one audit item to the next without asking the user for routine approval.
- Do not implement new fixes during the audit. If a failure is found, record it, assess dependencies, and continue auditing other items where safe.
- Do not block unrelated verification merely because one item fails; clearly record dependencies and whether a failure affects a downstream item.
- Stop an individual check if it would risk real user data, active jobs, credentials, production state or external publishing. Mark it `BLOCKED` and continue with independent safe checks.
- Stop the overall audit only for repository corruption/unavailability, inability to determine the actual target repository, unexpected real-data risk, or another condition where proceeding could cause harm.
- Do not restart services or apply migrations just to obtain a green result without first confirming no active work, an isolated environment and a safe operation. If not safe, document the evidence gap.
- Do not automatically change canonical phase statuses or delete/rewrite earlier audit records. Report suggested corrections for the user/authorized implementation pass.
- After all 20 items and global reconciliation, stop. Do not begin Phase 8–10 implementation or any remediation within this audit run.

---

## 8. Required per-item report format

Use this exact structure for every item:

### [Canonical ID] — [Title]

- **Scorecard claim:**
- **Current repository / runtime identity:**
- **Original defect or intended outcome:**
- **Acceptance criteria enumerated:**
- **Implementation trace:** frontend → API → service/task → DB/storage → worker/runtime, where applicable.
- **Pass 1 evidence and outcome:**
- **Pass 2 adversarial questions, tests and outcome:**
- **Pass 3 delta check, repeated tests and outcome:**
- **Actual tests:** commands, exact counts, warnings, skips, failures, runtime/environment.
- **Evidence tier:** E0–E6 per important criterion.
- **Known limitations / missing evidence:**
- **Decision rationale:** confirmed facts, alternatives assessed where a defect exists, recommended resolution if needed.
- **Cross-phase dependencies/regressions:**
- **Final status:** one required status from Section 1.
- **What would change this status:**

---

## 9. Final completion scorecard format

At the end, provide a matrix with all 20 entries and these columns:

| Canonical item | Reported status | Independently verified status | Highest evidence tier | Tests run in this audit | Major discrepancy/risk | Dependencies or follow-up |

Then include:

### A. Overall roadmap claim

State whether “20/20 delivered and frozen” is verified. Do not report “100% complete” unless every item meets its acceptance criteria at the appropriate evidence tier. If any item is `VERIFIED WITH LIMITATIONS`, `NOT VERIFIED`, `FAILED`, or `BLOCKED`, report the exact number in each category.

### B. The 270-test claim

Show:
- The exact suites and commands that total 270, if recoverable.
- Number of unique tests vs duplicated/overlapping runs.
- How many were executed now.
- Pass/fail/skip/error counts and warnings.
- Whether real worker/browser/integration behavior was included, or only unit/mocked tests.

If the count cannot be reconstructed, state `270/270 NOT INDEPENDENTLY RECONCILED` rather than repeating the claimed percentage.

### C. Environment snapshot

- Git branch, current commit and dirty-tree delta.
- Alembic migration head and heads count.
- Backend route objects categorized correctly.
- Frontend type check/build outcome and actual page count.
- Compose service status and worker version/source identity.
- Active/reserved jobs and whether a safe worker execution was performed.
- Logic Freeze Ledger domains L1–L10, each with evidence status.
- Caption/subtitle-removal guard status.

### D. Critical findings ranked by risk

Group findings into critical safety/data integrity, correctness/runtime, incomplete evidence, documentation inconsistency and optional future work. Assign a severity and justify it with evidence; do not use vague labels without a concrete consequence.

### E. Suggested next action

Recommend only the next single smallest remediation/audit item based on confirmed dependencies and severity. Do not execute it in this audit run.

### F. Final scope declaration

State clearly:
- Whether application code was modified (expected: no).
- Whether production DB rows or real user media changed (expected: no).
- Whether migrations, service restarts or external publishing occurred (expected: no unless separately authorized).
- Initial vs final working-tree status.
- Audit report path and any further evidence needed.

**Begin now with Global Preflight, then verify items 0.0, 0.1, 1.1, 1.2, 1.2.1, 1.3, and continue through C-11 in the exact sequence. Complete all three passes per item. Audit only. Do not repair defects or start new phases.**
