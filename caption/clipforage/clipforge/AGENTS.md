# ClipForge Subproject Governance & Agent Rules

All agent interactions and code modifications within `clipforge` are governed by:

1. **[MASTER_ENGINEERING_RULEBOOK.md](file:///d:/automation%20video%20clips/.agents/rules/MASTER_ENGINEERING_RULEBOOK.md)**: The supreme 18-rule engineering standard.
2. **[ANTIGRAVITY_CLIPFORGE_FREEZE_RULES.md](file:///d:/automation%20video%20clips/clipforge/ANTIGRAVITY_CLIPFORGE_FREEZE_RULES.md)**: Logic domains L1–L10 and freeze rules.
3. **[LOGIC_FREEZE_LEDGER.md](file:///d:/automation%20video%20clips/clipforge/docs/engineering/LOGIC_FREEZE_LEDGER.md)**: Active status of all 10 domains.
4. **[LOGIC_DEPENDENCY_MAP.md](file:///d:/automation%20video%20clips/clipforge/docs/engineering/LOGIC_DEPENDENCY_MAP.md)**: Dependency matrix and gates.
5. **[PROJECT_CONTINUITY.md](file:///d:/automation%20video%20clips/clipforge/docs/engineering/PROJECT_CONTINUITY.md)**: Canonical persistent system memory and read-first architecture guide.
6. **[IMPLEMENTATION_STATUS.md](file:///d:/automation%20video%20clips/clipforge/docs/engineering/IMPLEMENTATION_STATUS.md)**: System-wide implementation inventory and evidence log.

### ClipForge Specific Invariants:
- **Database Schema**: Preserved at Alembic head `c3d4e5f6a7b8`. Never drop or reset database tables.
- **Strict Decoupling**: Uploading, processing, and publishing are independent lifecycle stages. Video processing completion must never auto-publish.
- **Storage Accounting**: 1.5x disk reservations are allocated during upload intake and released exactly once.
- **No Captions / Subtitles**: No subtitle/caption generation, burning, font drawing, or filter usage in the video pipeline.
- **Verified Code Freeze**: All 10 logic domains (L1 through L10) are verified and `FROZEN`. Modifications require an explicit `FROZEN LOGIC CHANGE-EXCEPTION REPORT` approved by the user.

---

## Mandatory Project Continuity, Endpoint Inventory and Handoff Protocol

### 1. Before Every Task
Every AI coding agent MUST:
1. Resolve the actual repository root (`d:\automation video clips\clipforge`).
2. Read the root `AGENTS.md` and this subproject `AGENTS.md`.
3. Read `docs/engineering/PROJECT_CONTINUITY.md`.
4. Read `docs/engineering/IMPLEMENTATION_STATUS.md`.
5. Read the applicable engineering rulebook, freeze rules, dependency map, and logic-freeze ledger.
6. Read the two endpoint inventory files before changing routes, API clients, or frontend controls:
   - **[BACKEND_ENDPOINT_INVENTORY.md](file:///d:/automation%20video%20clips/clipforge/docs/engineering/api_audit/BACKEND_ENDPOINT_INVENTORY.md)**
   - **[FRONTEND_INTERACTION_ENDPOINT_MAP.md](file:///d:/automation%20video%20clips/clipforge/docs/engineering/api_audit/FRONTEND_INTERACTION_ENDPOINT_MAP.md)**
7. Read the relevant feature specification or archived implementation prompt in `docs/engineering/prompts/`.
8. Inspect the actual code and Git working-tree state before editing rather than trusting historical reports.
9. Compare relevant documentation against the current code instead of blindly trusting old status claims.

### 2. No Guessing and No Fabricated History
An agent must never:
- Claim that a feature was previously implemented without evidence.
- Claim that tests passed when there is no execution evidence.
- Assume an old migration is the current database head.
- Assume a database record is genuine merely because it exists.
- Treat a design proposal as proof of implementation.
- Invent credentials, statistics, production data, or channel-authorization states.
- Infer that an earlier coding agent completed work correctly without inspection.
- Distinguish verified facts, earlier reports, assumptions, and open questions.

### 3. Frozen Logic and Dependency Protection
Before changing existing code:
1. Identify the affected logic domain (L1 through L10).
2. Read its freeze entry in `LOGIC_FREEZE_LEDGER.md` and dependency map.
3. Trace its callers and downstream effects.
4. Establish a concrete reason for the change.
5. Make the smallest necessary change.
6. Record a change exception when required by the project's freeze rules.
7. Run focused tests for the defect and regression checks for the affected dependants.

### 4. Documentation and Inventories are Part of Implementation
Every substantive feature, schema change, bug fix, or behavior change must update the relevant implementation records:
- Update `IMPLEMENTATION_STATUS.md` and `PROJECT_CONTINUITY.md` to record actual changes and verified status.
- Update **[BACKEND_ENDPOINT_INVENTORY.md](file:///d:/automation%20video%20clips/clipforge/docs/engineering/api_audit/BACKEND_ENDPOINT_INVENTORY.md)** whenever an API route or externally accessible backend interface changes.
- Update **[FRONTEND_INTERACTION_ENDPOINT_MAP.md](file:///d:/automation%20video%20clips/clipforge/docs/engineering/api_audit/FRONTEND_INTERACTION_ENDPOINT_MAP.md)** whenever a user-facing action, API call, navigation path, or interaction changes.
- Update the cross-layer mappings whenever an API contract or route-to-UI relationship changes.
- Before changing code, capture the task and intended scope.
- As the work progresses, record actual changes and findings.
- At the end, update the verified status, tests, limitations, and remaining work.
- Never update a documentation entry to "completed" solely because implementation has started.
- Record failed commands or tests when their failure reveals an unresolved issue.

### 5. Multi-Agent Safety
Assume another agent may be working from a separate chat and may not know the current task:
- Before editing, inspect recent changes and `git status`. Do not overwrite another agent's uncommitted work or replace a file with an older version of its contents.
- For overlapping work, make small, clearly scoped edits. Reinspect the final file after modifications and validate its actual resulting contents.

### 6. Completion Gate
Before declaring completion, the agent must:
- Run the required focused tests.
- Check affected integrations.
- Verify migrations when applicable.
- Perform type-checking (`npx tsc --noEmit`) and build checks (`npm run build`) for frontend changes.
- Perform real browser verification when required and available.
- Record the actual results.
- Update the continuity and implementation records.
- Identify unresolved limitations.
- If verification is unavailable, record it as unverified. Do not manufacture evidence.

### 7. Safe Operations
- Do not perform irreversible or externally consequential operations simply to test a feature.
- Use isolated test data (`is_test = true`) and mocked external APIs where practical.
- Never modify actual YouTube content or perform a real upload during verification.
- Explicit approval is still required for genuinely destructive or external actions.
- Do not expose secrets or credentials in continuity documents, prompt archives, or logs.

### 8. Mandatory Recording Protocol for Future Phases
For every subsequent remediation phase (Phase 1.1 through Phase 7.0), every executing agent must follow this strict 3-stage protocol:

#### A. Pre-Stage Entry (Before Making Edits):
1. **Preserve Baseline:** Check `git status --short`. Never clean, reset, or discard working-tree modifications. Record changed files snapshot if needed.
2. **Read Master Ledgers:** Read `docs/engineering/PHASE_TRACKER.md` and `docs/engineering/MASTER_EXECUTION_LEDGER.md` to confirm the currently active phase, subphase, and dependencies.
3. **Trace Impact:** Check `docs/engineering/PIPELINE_CATALOG_AND_DEPENDENCY_GRAPH.md` and `docs/engineering/LOGIC_FREEZE_LEDGER.md` for callers, downstream effects, and freeze gates.
4. **Update Status to IN PROGRESS:** Mark the active phase as `IN PROGRESS` in `PHASE_TRACKER.md`.

#### B. During Execution (Mid-Stage):
1. **Narrow Scope:** Edit only the exact files authorized for the active subphase. Never fix unrelated issues or side defects.
2. **Stable Defect Referencing:** Always reference defects by their registered ID (`CF-DEF-001` through `CF-DEF-007`, `REQ-GAP-001`, `CAP-001`) from `docs/engineering/ENGINEERING_DEFECT_REGISTER.md`.
3. **Non-Destructive Testing:** Use isolated test flags (`is_test = true`), mock external services, and execute safe in-container commands.

#### C. Post-Stage Completion (Handoff Gate):
1. **Verify Integrity:** Run `git diff --stat` to verify that no files outside the subphase scope were modified.
2. **Execute Tests:** Run focused test suite and capture exact pass/fail counts.
3. **Frontend Validation:** If frontend files changed, verify `npx tsc --noEmit` (0 errors), `npm run build` (clean), and real browser behavior.
4. **Update Authoritative Documents:**
   - Update `docs/engineering/PHASE_TRACKER.md` (set status to `DELIVERED`).
   - Update `docs/engineering/MASTER_EXECUTION_LEDGER.md` with execution summary.
   - Update `docs/engineering/IMPLEMENTATION_STATUS.md` and `docs/engineering/PROJECT_CONTINUITY.md`.
   - Update endpoint inventories if routes or UI actions changed.
5. **Generate Handoff:** Fill out `docs/engineering/SESSION_HANDOFF_TEMPLATE.md` with complete evidence.
6. **Stop Condition:** Halt and await explicit user approval before beginning the next subphase.

