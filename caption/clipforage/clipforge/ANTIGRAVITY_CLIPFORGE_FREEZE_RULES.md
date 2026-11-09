# Antigravity Project Rules: Logic Domains, Dependency Gates, and Verified-Code Freeze

**Applies to:** Every Antigravity/Gemini coding session, prompt, tool run, edit, test run, refactor, migration, and delivery for ClipForge.

**Primary objective:** Stop regressions caused by fixing one feature and accidentally breaking another. Preserve verified behavior, keep logic domains isolated, and allow work to advance only after dependency checks pass.

## 0. Highest-priority rules

1. **Understand before editing.** Trace a file's purpose, callers, dependencies, contracts, persistent data, runtime effects, and tests before changing it.
2. **Verified means frozen.** After a logic domain passes its verification gate and is recorded as `FROZEN`, treat its protected files and behavior as read-only. Do not modify, rename, move, delete, reformat, regenerate, or refactor them as part of ordinary feature work.
3. **Check upstream domains before downstream work.** Before starting a new logic domain, run its dependency gate against all required upstream domains and confirm their frozen baselines remain intact.
4. **Repair the new change first.** If a downstream change breaks an upstream domain, first fix or revert the downstream change. Do not “fix” a frozen upstream implementation merely to make the new feature work.
5. **No silent exceptions.** If changing frozen logic appears truly necessary, stop and create a `FROZEN LOGIC CHANGE-EXCEPTION REPORT`. Do not edit the frozen logic until the user explicitly approves that specific change.
6. **Evidence over claims.** Never mark code verified, frozen, or tests passed unless current execution output or a recorded baseline supports the statement.
7. **No endless audits.** Run the required gates once per relevant change, fix real regressions, and move forward. Do not repeatedly rerun unchanged passing tests without a reason.
8. **User data and pre-existing work are protected.** Never discard existing user edits, reset their work, wipe a database, or perform a destructive production action as a shortcut.

These rules apply to every tool call and every iteration. A task prompt does not override them unless the user explicitly instructs a change to this rulebook.

---

## 1. Initial repository inventory — required before the first implementation

Before declaring any part of ClipForge frozen:

1. Inspect `git status`, staged and unstaged diffs, untracked files, recent commits, and project instructions. Record pre-existing user work; do not overwrite it.
2. Inspect the actual repository structure, runtime configuration, migration chain, model relationships, API routes, task registration, external integrations, tests, and deployment configuration relevant to the application.
3. Trace important execution paths end-to-end rather than relying only on filenames or documentation.
4. Run the applicable baseline tests where possible. Record existing failures separately from new failures. Do not “fix” baseline failures silently while establishing a baseline.
5. Create or update the two living files described below:
   - `docs/engineering/LOGIC_FREEZE_LEDGER.md`
   - `docs/engineering/LOGIC_DEPENDENCY_MAP.md`
6. If the paths do not exist, create them in a suitable existing documentation location and record the chosen paths. Do not overwrite similarly named user documents without checking their contents.

**Important:** The inventory is not proof that every feature is correct. Freeze a domain only after its relevant tests and behavior checks have passed or its limitations are explicitly recorded.

## 2. Ten logic domains

Use these ten domains as the initial map. Inspect the repository and map the real files, functions, tables, queues, and tests into them. Do not assume a particular file belongs to a domain merely because its name looks relevant. A shared file can belong to multiple domains and must be protected against unintended cross-domain edits.

| Logic | Domain | Typical responsibilities | Example dependencies |
|---|---|---|---|
| **L1** | Runtime, configuration, security foundations | Environment variables, settings, container wiring, secret handling, auth foundations, startup and health checks | Foundation for all other logic |
| **L2** | Data model and schema lifecycle | ORM models, relationships, constraints, indexes, Alembic migrations, DB sessions and transaction conventions | L1; supports L3–L10 |
| **L3** | Storage and artifact lifecycle | Storage-root identity, path boundaries, reservation accounting, artifact ownership, deletion, cleanup and reconciliation | L1, L2 |
| **L4** | Upload intake and media validation | Upload Studio initialization, resumable/chunk upload, byte-range handling, FFprobe/pre-flight validation | L1–L3 |
| **L5** | Batch and job orchestration | Batch status, queue order, task dispatch, idempotency, ownership tokens, leases, retries, cancellation and worker recovery | L1–L4 |
| **L6** | Core video-processing pipeline | Processing task entry points, cuts/outputs, FFmpeg orchestration, processing progress and safe artifact writes | L1–L5 |
| **L7** | Clip outputs and internal analysis | Clip records, scoring, transcription for internal analysis, semantic analysis, metadata generation and output association | L2, L3, L5, L6 |
| **L8** | Publishing and external integrations | OAuth/channel selection, YouTube/API clients, publishing jobs, remote state reconciliation, retries and results | L1–L3, L5, L7 |
| **L9** | Backend API contracts | Request/response schemas, routes, authentication/authorization, error contracts and API compatibility | Relevant upstream domains L1–L8 |
| **L10** | Frontend workflows and user-facing state | UI components, API clients, staging persistence, queue rendering, progress, retry/cancel actions and user-visible status | L9 and the relevant upstream behavior |

Tests, logs, metrics, documentation, and deployment checks are **cross-cutting controls** and apply to all ten domains. The table is a starting map, not permission to force an unsuitable architecture. If actual repository architecture requires a different dependency, document the evidence and update the dependency map without silently moving frozen ownership boundaries.

### ClipForge product invariants

Record these in the freeze ledger and verify them wherever relevant:

- Preserve existing working upload, processing, storage, and legacy API behavior.
- Preserve PostgreSQL/Alembic lifecycle and existing records; never reset the active database to make a test pass.
- Uploading, processing, and publishing are separate lifecycle stages. Processing completion must not unexpectedly auto-publish.
- Batch processing remains sequential in persisted queue order unless the user explicitly approves a product change.
- Storage reservations are managed by their owning lifecycle operation and released exactly once; publishing must not release processing/storage reservations.
- Stale workers and obsolete callbacks must not overwrite newer job state, write conflicting artifacts, or release reservations twice.
- Preserve all existing supported OAuth and publishing functionality unless a replacement is implemented and tested.
- **No active caption/subtitle feature:** do not reintroduce caption or subtitle generation, rendering, burning, editing, configuration, storage, UI, ASS/SRT processing, karaoke styling, caption fonts, or FFmpeg caption/subtitle/drawtext filters. Internal transcription remains allowed for scoring, semantic analysis, and metadata generation.
- Never expose secrets in code, frontend bundles, logs, reports, screenshots, or test output.

---

## 3. Freeze states and what they mean

Every logic domain must have exactly one explicit state in the ledger:

- `UNMAPPED`: relevant components have not been identified yet.
- `BASELINING`: inventory or baseline tests are still in progress.
- `ACTIVE`: this is the logic domain currently allowed to change for the approved task.
- `VERIFYING`: implementation is complete and required gates are running.
- `FROZEN`: verification has passed, the baseline has been recorded, and routine changes are prohibited.
- `BLOCKED`: evidence is insufficient or a known issue prevents safe progression.

A domain is not `FROZEN` just because code was written, a plan was produced, or an agent says it is done.

### What a freeze protects

The ledger must list, as precisely as practical:

- Protected file paths and important symbols.
- Public contracts and invariants.
- Relevant database tables/fields and migration revision, when applicable.
- Commands and tests that verify the domain.
- Most recent pass/fail/skip result and date/time.
- Git baseline commit and relevant baseline diff/patch identifier.
- Checksums for explicitly protected critical artifacts when useful.
- Known limitations and environmental restrictions.
- Upstream and downstream dependencies.

A Git commit, tag, patch, or documented baseline is the primary way to identify source state. SHA-256 may be used to detect unexpected changes in important protected files. Do not depend on an MD5 hash as a cryptographic authenticity guarantee. A hash detects a difference; it does not prove that the file is correct.

## 4. Frozen-code policy — do not touch without an approved exception

For files/symbols in a `FROZEN` domain, do not:

- Edit logic, change signatures, adjust defaults, or alter return shapes.
- Refactor, reformat, reorder code, rename symbols, or move files.
- Delete “unused-looking” functions before proving all direct and indirect callers are obsolete.
- Change shared schemas, DB columns, enum values, task names, event payloads, or API contracts used by the frozen domain.
- Weaken, delete, skip, or rewrite tests just to get a green result.
- Modify migrations already applied to a database; use a new migration with an appropriate rollback/recovery plan.
- Change dependencies, configuration defaults, ports, environment-variable names, or container wiring that the domain relies on without impact analysis.
- Replace established behavior with a parallel implementation and leave old callers dangling.

Reading frozen code, tracing its behavior, running its tests, comparing it to its recorded baseline, and writing a compatibility adapter outside the frozen domain are allowed.

### Exception procedure

If a frozen change is genuinely required, do the following **before editing the frozen domain**:

1. Stop the change that creates the conflict.
2. Confirm the failure is reproducible and not caused by the active domain's implementation or test harness.
3. Attempt a fix in the active/new domain or a backward-compatible adapter.
4. If no safe alternative exists, write a `FROZEN LOGIC CHANGE-EXCEPTION REPORT` containing:
   - Exact frozen domain, files, symbols, and contracts affected.
   - Reproducible evidence and exact failing test/output.
   - Why the active-domain fix or adapter cannot work.
   - Minimum proposed diff and alternatives considered.
   - All downstream and upstream dependencies affected.
   - Data migration, security, concurrency, deployment, and rollback implications.
   - Tests to add/run before the freeze can be restored.
   - Whether the proposed change alters behavior or only repairs an established defect.
5. Present the report and wait for the user's explicit approval of that specific modification.
6. After approval, edit only the approved scope, run the full dependency regression gate, update the ledger, and refreeze only after passing verification.

**Silence is not approval. A generic instruction to “fix it” does not automatically authorize unrelated changes to a frozen domain.** If a critical security or data-integrity defect is discovered, stop risky operations, preserve evidence, and immediately report it; do not silently modify protected code.

---

## 5. Dependency gates: every new logic must re-check what it depends on

Before starting `L(n)`, consult `LOGIC_DEPENDENCY_MAP.md` and run the gate for its required upstream domains. At minimum:

1. Confirm upstream protected files have not changed unexpectedly from their baselines.
2. Run the upstream domain's designated smoke/invariant tests or the lightest equivalent reliable checks.
3. Check the contracts used by the new logic: types, signatures, DB fields, state transitions, API request/response structures, task payloads, filesystem behavior, and error semantics as appropriate.
4. Confirm previously recorded invariants remain true.
5. Record the gate result before implementing the dependent domain.

Example: before starting L5, check L1–L4 requirements; before starting L8 publishing, check its required L1–L3, L5, and L7 interfaces. Do not automatically run unrelated, extremely expensive suites if targeted gates provide suitable evidence; run the full regression suite at milestone boundaries or when the risk warrants it.

### If an upstream gate fails

- **Before editing:** classify the failure as a pre-existing baseline issue, environment issue, or actual regression. Do not assume its cause.
- **If the active work caused it:** repair the active work first.
- **If a test harness or environment caused it:** fix or document the harness/environment without weakening product assertions.
- **If the frozen domain fails independently:** mark it `BLOCKED`, preserve the failure evidence, and produce a report. Do not modify the frozen implementation without exception approval.
- **Do not begin downstream implementation while required upstream contracts are failing or unresolved.** You may continue non-dependent analysis or tests, but not code that assumes the failed contract works.

### If a new change breaks a previously passed test

1. Stop adding features.
2. Reproduce the failure on the current diff.
3. Identify whether the changed domain or its interface caused it.
4. Fix the active/new domain or revert the offending edit.
5. Re-run the failing test and affected dependency gate.
6. Continue only once the required gate passes, or mark the task `BLOCKED` with evidence.

Do not “repair every logic automatically” by editing frozen code. Repair the active change first; require the exception report for any actual frozen-domain modification.

---

## 6. Required workflow for every implementation task

### Gate A — Understand
- Read task requirements and persistent project rules.
- Check repository state and existing user changes.
- Trace the requested behavior through source, contracts, data, runtime, and tests.
- Identify the active logic domain(s) and all frozen dependencies.

### Gate B — Plan the smallest change
- Name the exact requirement and intended outcome.
- List the files expected to change and why each is necessary.
- Identify files/domains explicitly protected from modification.
- List invariants and tests that must remain green.
- Do not stop after the plan if implementation was requested.

### Gate C — Baseline and protect
- Run relevant current tests where practical.
- Record known baseline failures.
- Confirm frozen paths, baseline commit/diff, and critical checksums where appropriate.
- Do not erase or overwrite user work.

### Gate D — Implement
- Change only approved active domains and necessary integration files.
- Keep the diff small and coherent.
- Do not touch frozen domains or unrelated files.
- Add tests for behavior and regression risk.
- Preserve existing interfaces unless the task explicitly requires a contract change and its consumers are updated.

### Gate E — Verify locally
- Run focused tests for the changed logic.
- Run relevant upstream dependency gates.
- Run failure, retry, concurrency, persistence, security, or migration tests proportionate to the change.
- Inspect logs and outputs for real execution evidence; distinguish skipped/blocked tests from passes.

### Gate F — Cross-verify before freezing
- Run the domain's defined acceptance tests.
- Run impacted dependent/consumer tests.
- Verify invariants and existing workflows.
- Inspect `git diff --check`, the complete final diff, unintended deletions, missing callers, and accidental unrelated edits.
- Recheck protected-path changes and checksums when used.
- Confirm no secrets or dangerous debug code were introduced.

### Gate G — Freeze and proceed
- Only after required tests pass, update the ledger with evidence and mark the domain `FROZEN`.
- Record the baseline commit/diff and relevant migration revision.
- Proceed to the next dependent domain only after its upstream gate passes.
- If tests fail, do not freeze the domain. Fix the active implementation and repeat the relevant verification, not the entire world.

---

## 7. Cross-verification standard

“Cross-verified” means evidence from more than one relevant angle, not blindly running the same command twice.

Use a combination appropriate to the domain:

- **Source/contract check:** inspect signatures, call sites, schema/DTO compatibility, task payloads, and state transitions.
- **Automated behavior check:** run focused unit/integration/API tests.
- **Regression check:** run downstream consumer tests or a real end-to-end path where appropriate.
- **Runtime/data check:** inspect real runtime status or database/file invariants when the environment supports it.
- **Diff/integrity check:** confirm only intended files changed and frozen baselines remain intact.

For high-impact changes such as migrations, storage lifecycle, task ownership, OAuth, or publishing, use at least three independent relevant checks, including a meaningful failure-path test when practical.

Do not call a domain cross-verified when only static inspection occurred. Report unavailable runtime/database/live-service checks honestly.

---

## 8. Logic ledger template

Maintain one row per logic domain in `docs/engineering/LOGIC_FREEZE_LEDGER.md`:

| Logic | State | Protected files/symbols | Baseline | Required gates | Latest evidence | Dependencies | Known limitations |
|---|---|---|---|---|---|---|---|
| L1 | UNMAPPED | TBD after repo inspection | TBD | TBD | Not verified | Foundation | TBD |
| L2 | UNMAPPED | TBD after repo inspection | TBD | TBD | Not verified | L1 | TBD |
| L3 | UNMAPPED | TBD after repo inspection | TBD | TBD | Not verified | L1, L2 | TBD |
| L4 | UNMAPPED | TBD after repo inspection | TBD | TBD | Not verified | L1–L3 | TBD |
| L5 | UNMAPPED | TBD after repo inspection | TBD | TBD | Not verified | L1–L4 | TBD |
| L6 | UNMAPPED | TBD after repo inspection | TBD | TBD | Not verified | L1–L5 | TBD |
| L7 | UNMAPPED | TBD after repo inspection | TBD | TBD | Not verified | L2, L3, L5, L6 | TBD |
| L8 | UNMAPPED | TBD after repo inspection | TBD | TBD | Not verified | L1–L3, L5, L7 | TBD |
| L9 | UNMAPPED | TBD after repo inspection | TBD | TBD | Not verified | Relevant L1–L8 contracts | TBD |
| L10 | UNMAPPED | TBD after repo inspection | TBD | TBD | Not verified | L9 and relevant upstream domains | TBD |

Replace every `TBD` only after inspecting the actual repository. Do not mark anything frozen solely from an earlier conversational report. If prior test output is not available in the current working environment, mark it as reported historical evidence until it is re-established.

## 9. Dependency map template

Maintain `docs/engineering/LOGIC_DEPENDENCY_MAP.md` with:

- Real file paths and symbols assigned to each logic domain.
- Direct and indirect dependencies.
- Public and internal contracts shared across domains.
- Upstream gates required before work starts.
- Downstream regression suites that must run after a change.
- Shared files that require extra approval because they cross a freeze boundary.
- The reason for each non-obvious dependency.

Every new integration must update this map if it introduces a genuine new dependency. Do not let the map drift away from the actual code.

## 10. Rules for prompts and every agent run

At the start of each new task, the agent must:

1. Read this rulebook, the freeze ledger, and the dependency map.
2. Identify the active logic domain(s).
3. List frozen upstream domains that must be checked.
4. State the intended scope and expected files before editing.
5. Verify that the planned diff does not cross a freeze boundary.

During execution, the agent must re-check these rules when changing scope or discovering new dependencies. A long task does not waive the rules, and tool retries do not waive them.

Before completion, the agent must report:
- Which logic domain(s) changed.
- Which frozen domains were read and regression-tested.
- Which files changed and why.
- Which frozen files remained untouched.
- Exact executed test counts: passed, failed, skipped, blocked, and not run.
- Baseline failures versus failures introduced by the change.
- Updated ledger state and evidence.
- Any frozen-change exception requested or unresolved blocker.

## 11. Frozen logic change-exception report template

When a frozen change is proposed, create a report containing:

```text
FROZEN LOGIC CHANGE-EXCEPTION REPORT

Task / issue:
Date:
Affected frozen domain(s):
Protected files and symbols:
Current baseline commit/diff:
Reproducible defect and evidence:
Failing tests and exact output:
Why the active/new logic cannot safely be fixed instead:
Backward-compatible alternatives attempted:
Minimum proposed change:
Upstream/downstream impact:
Database/data migration implications:
Security/concurrency/storage implications:
Rollback and recovery plan:
Tests required before refreezing:
Approval required: YES
Status: WAITING FOR EXPLICIT USER APPROVAL
```

Do not edit the protected code while the report is waiting for approval.

---

## Final invariant

**Every logic domain moves through `UNMAPPED → BASELINING → ACTIVE → VERIFYING → FROZEN`. A downstream domain cannot advance without passing its required dependency gates. A frozen domain is read-only by default. Regressions are fixed in the new/active change first. A frozen-domain change requires a specific evidence-based exception report and explicit user approval.**
