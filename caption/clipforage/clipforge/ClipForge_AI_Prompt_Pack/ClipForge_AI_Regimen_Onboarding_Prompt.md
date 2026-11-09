# ClipForge AI Regimen Onboarding and Full-File Ingestion Prompt

> **Use this prompt at the beginning of a fresh AI-agent session after placing the two companion Markdown files in the agent's accessible project/documentation location.**
>
> Companion files:
> 1. `ClipForge_AI_Execution_Rules_and_Triple_Verification.md`
> 2. `ClipForge_Master_Phase_Prompts_Phase_0_to_10.md`
>
> Repository: `D:\automation video clips\clipforge`

---

## Copy-ready prompt for the AI agent

You are working on **ClipForge**. Before implementing or changing anything, you must fully ingest and understand the two companion files listed above. They are not casual reference notes. Together they define the working regimen for planning, selecting approaches, implementing, testing, cross-examining decisions, recording rationale, and progressing through the roadmap.

### 1. Know what each file governs

**File A — `ClipForge_AI_Execution_Rules_and_Triple_Verification.md`**

This is the governing operating procedure. It defines autonomy, boundaries, the source of truth, preflight investigation, scope control, the required three verification passes, evidence tiers, post-implementation self-questioning, the AI decision/rationale log, required engineering ledgers, defect/risk handling, phase exit gates, approach-selection methodology, and the standard format required for every phase/subphase prompt. Where a prompt in File B and a general working habit conflict, follow this rules file unless a higher-priority system/developer instruction or an explicit user instruction requires otherwise. Do not use the rules file to override safety or irreversible-action restrictions.

**File B — `ClipForge_Master_Phase_Prompts_Phase_0_to_10.md`**

This is the phase and subphase prompt library. It contains the current canonical execution queue, a legacy product roadmap, and proposed roadmap extensions. Each copy-ready prompt is a task specification with its own scope and acceptance expectations. It is not proof that a phase is currently active, not proof that the phase is complete, and not permission to implement every prompt in sequence without checking current repository status and dependencies.

### 2. Read every part of both files — do not skim

Read each complete file from beginning to end, including all headings, prompt blocks, tables, notes, scope boundaries, acceptance criteria, safety rules, and stop conditions. Do not rely only on search snippets, table of contents, opening paragraphs, cached summaries, or your own memory. Do not skip prompts because their names resemble earlier prompts.

Confirm the full files actually opened and were readable. If either file is absent, truncated, unreadable, or has an unexpected version, stop and report exactly which file/section could not be read. Do not claim full ingestion unless you inspected the complete contents available in the current environment.

While reading, create a coverage map in your working notes that accounts for:

- Every major section of File A.
- Every named canonical queue item in Part A of File B.
- Every main phase prompt in Parts B and C.
- Every standalone prompt ID and subphase prompt in the prompt library.
- Every shared deliverable, invariant, verification requirement, and stop condition in Part D.

Do not replace the source's terminology with a different taxonomy without documenting the mapping. Preserve the exact prompt IDs and phase labels.

### 3. Build a complete regimen map

After reading both files, prepare a structured inventory that states for every prompt ID:

1. Exact prompt ID and title.
2. Whether it belongs to the **current canonical execution queue**, the **legacy roadmap**, or a **proposed extension**.
3. Its objective/problem statement.
4. Key systems/files/contracts to inspect before acting.
5. Prerequisites and dependencies.
6. Required implementation boundary and explicit non-goals.
7. Expected acceptance tests and evidence tiers.
8. Three-pass verification obligations.
9. Required documentation/rationale updates.
10. Its stop condition and what must be true before the next item can proceed.

Also summarize the shared operating regimen: how you establish the baseline; generate and compare approaches; justify the chosen approach; implement narrowly; run Pass 1, Pass 2 and Pass 3; compare the final diff against earlier verification passes; update the AI decision/rationale log; and classify results as unit/mocked, integration, in-process task, live worker, or actual browser verification. Never collapse these evidence levels into one generic statement that a feature is “verified.”

If the full inventory is large, store it in a durable project document such as `docs/engineering/AI_REGIMEN_INGESTION_REPORT.md`. Keep it factual and concise per prompt ID, but include **every** prompt ID and do not omit subphases. Preserve the source files unchanged.

### 4. Resolve roadmap/status carefully before selecting work

Inspect the current repository's authoritative records, especially:

- `AGENTS.md` and repository-specific freeze rules.
- `docs/engineering/MASTER_EXECUTION_LEDGER.md`.
- `docs/engineering/PHASE_TRACKER.md`.
- `docs/engineering/IMPLEMENTATION_STATUS.md`.
- `docs/engineering/ENGINEERING_DEFECT_REGISTER.md`.
- `docs/engineering/PROJECT_CONTINUITY.md`.
- Relevant phase audit reports.

Treat the current repository state and latest explicit audit evidence as the evidence of what is actually complete. A prompt's existence does not mean it was executed. A completion label does not supersede contradictory failure logs or missing verification evidence. A task-dispatch screenshot does not prove worker completion. Preserve distinctions between implemented, test-passed, in-process verified, live-worker verified, browser-verified, and fully accepted.

**Important phase-number collision rule:** the prompt pack intentionally separates the **current canonical execution queue** from the **legacy product roadmap** and the **proposed extensions**. Phase labels can refer to different scopes in those sections. Never select a prompt by its phase number alone. Use the exact prompt ID, title, section, defect ID, current tracker state, and dependencies together.

The supplied prompt pack marks Phases 8–10 as proposed extensions, not established user-approved product requirements. Do not treat those phases as authorized implementation work. First discover evidence, identify unresolved requirements, and propose scope; do not invent requirements just to fill a numbered phase.

### 5. Learn the required decision-making method

For every phase or subphase, you must do the following before implementation:

1. State the observed problem and cite concrete evidence from current source, tests, logs, API responses, database state, or reproducible behavior.
2. Separate facts from hypotheses and unknowns.
3. Generate plausible technically distinct approaches, including a minimal correction and any reasonable alternative warranted by evidence.
4. Compare them against explicit criteria: correctness, failure behavior, security/trust boundaries, data integrity, concurrency, API compatibility, runtime cost, maintainability, reversibility, testability, and affected frozen components.
5. Select an approach and explain the trade-offs and why it addresses the actual root cause rather than only a symptom.
6. Define proof obligations: what tests or inspection would disprove the chosen design or expose a regression.
7. Implement only the smallest bounded scope that satisfies the requirements.

Do not choose an approach solely because it is easier to implement, makes a test green, creates a visually convincing UI, or matches your previous answer. Do not fabricate performance, quality, reliability, or safety results. If the alternatives cannot be evaluated without further evidence, gather evidence first.

### 6. Three verification passes are mandatory for every phase and subphase

**Pass 1 — Implementation and acceptance verification:** Run the focused tests and inspect the actual change. Check positive behavior, negative behavior, failure paths, state transitions, persistence, artifact handling, and the defined acceptance criteria. Record exact commands and results.

**Pass 2 — Independent adversarial self-challenge:** Re-read the requirements as a critical reviewer who did not write the fix. Ask: What assumption may be wrong? What competing approach was dismissed too quickly? Can malformed input, an exception, a retry, a race, a partial failure, a stale state, a legacy record, or a production/test boundary break it? Add/run targeted adversarial tests and relevant regressions. Correct issues found within the current authorized scope; unrelated findings go into the defect register.

**Pass 3 — Differential verification:** Re-read the final diff from the start, compare it with the Pass 1 and Pass 2 evidence, identify changes made after either pass, and rerun tests affected by those changes. Check for unintended files, missing tests, weakened assertions, stale docs, API/schema mismatch, and false success states. The final source tree must match the implementation that was actually verified.

A pass is not complete merely because you wrote a checklist. Record its actual evidence. If a test or runtime layer cannot be run, label it blocked/unverified and explain the limitation. Do not claim all three passes succeeded if the final change was not retested after a correction.

### 7. Keep a durable record of your engineering decisions

Create or maintain `docs/engineering/AI_DECISION_LOG.md` as specified by File A. For each phase/subphase, record:

- Date/session and exact phase/prompt ID.
- Evidence and baseline used.
- Facts, assumptions and unresolved questions.
- Alternatives considered and comparison criteria.
- Selected approach and rationale.
- Alternatives rejected and specific reasons.
- Expected risks and safeguards.
- Files changed and why.
- Pass 1, Pass 2 and Pass 3 evidence, including changes between passes.
- Verification tier achieved and any unverified tier.
- Remaining defects, deviations, and phase exit decision.

This is an engineering rationale and audit trail, not a request to expose private hidden chain-of-thought. Provide concise, evidence-based reasons, alternatives and trade-offs that another engineer can review. Never invent a rationale after the fact and present it as contemporaneous evidence; label retrospective explanations as retrospective.

### 8. Autonomy and phase progression

Once the user has authorized the overall execution regimen and the first canonical task is selected, continue automatically through routine, low-risk phases/subphases when the preceding exit gate passes. Do not ask the user for routine approval between every subphase or repeat questions already answered by project documentation.

However, autonomy never means unlimited scope. Stop and seek authorization for irreversible or high-impact operations, including destructive cleanup/deletion of existing user data, production database destructive migrations, credential or OAuth account changes, actual external publishing, security-boundary changes, or any operation the governing rules designate as requiring approval. Also stop if requirements conflict, the necessary test environment is unsafe, a dependency is fundamentally blocked, or the next work item is only a proposed extension not authorized by the user. When blocked, report the evidence and safe options; do not silently skip the gate or relabel an unverified task as complete.

### 9. Onboarding task — no implementation in this step

For this onboarding step only:

- Read and map the full two-file regimen.
- Inspect the current engineering records to identify the actual repository state and canonical next prompt ID.
- Create/update `docs/engineering/AI_REGIMEN_INGESTION_REPORT.md` if needed to preserve the full prompt coverage map.
- Create/update `docs/engineering/AI_DECISION_LOG.md` with an onboarding entry noting which source files were read, how the roadmap sections are distinguished, the current canonical execution item evidenced by current records, and known verification gaps.
- Do not modify application code, tests, schemas, Docker configuration, or user media during onboarding.
- Do not execute the next implementation phase as part of onboarding. This step establishes readiness and avoids accidentally starting the wrong prompt.

### 10. Required onboarding report

Return a report with:

1. Exact names, paths, byte sizes or line counts, and readability status of both files.
2. Confirmation that each file was read completely—not just sampled—and any limitation.
3. Number of main phases and number of individually identified work-item prompts found, based on an actual inventory. Do not guess these counts; calculate them from the files.
4. A coverage list of all prompt IDs by section, including the canonical queue, legacy roadmap, and proposed extensions.
5. A concise explanation of the operating rules, approach-selection method, three verification passes and evidence tiers.
6. The current canonical next prompt ID, justified by current repository status and the latest evidence—not chosen solely from the phase number.
7. Current worktree/known-risk notes relevant to choosing that prompt.
8. Paths to the ingestion report and decision log.
9. A statement that no application implementation was started during onboarding.

Do not merely reply “understood.” Demonstrate understanding through the coverage map and the concrete status reconciliation. Once the onboarding report is complete, follow the governing autonomy rule on the next authorized canonical task; do not invent or implement scope from the proposed Phase 8–10 extensions.

**End of onboarding prompt.**
