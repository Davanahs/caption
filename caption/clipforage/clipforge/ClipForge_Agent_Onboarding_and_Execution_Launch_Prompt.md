# ClipForge — Agent Onboarding, Operating Instructions & Autonomous Execution Launch Prompt

**Target repository:** `D:\automation video clips\clipforge`  
**Governing framework:** `ClipForge_Autonomous_UI_Execution_and_Cross_Verification_Framework.md`  
**Component execution pack:** `ClipForge_Page_and_Component_Prompts.md`  
**Authorized mandatory scope:** Phases 1–7, as recorded in DEC-007  
**Deferred scope:** Phase 8 remains an unapproved proposed extension; do not activate watermark branding or wire `apply_watermark()`  
**Publishing acceptance test:** Exactly one real YouTube upload with **Private** visibility, but only after the publishing safety prerequisites in the framework pass  
**Execution mode:** Autonomous execution, repair, retest, and cross-verification; no routine user check-ins

---

## 1. Your role

You are the autonomous engineering agent responsible for carrying out the ClipForge page-by-page, component-by-component UI-to-backend verification and repair program. The two companion Markdown files are the governing work instructions. Read them completely before starting, then execute them against the actual repository and current runtime state.

This is an execution assignment, not an invitation to produce another plan or a high-level audit summary. Start examining the repository, build the real inventory, and begin with the first eligible component. Continue through all required pages and components until every approved, safe, in-scope item is verified, repaired and independently cross-verified, or a specific blocker is recorded.

Do not ask the project owner to approve routine inspection, ordinary tests, small in-scope repairs, or progress between pages. The owner has requested an autonomous run and a final consolidated result. Do not stop after the first defect, first page, first test suite, TypeScript check, or build success.

## 2. Read the two companion files first

### File A — `ClipForge_Autonomous_UI_Execution_and_Cross_Verification_Framework.md`

This is the master policy and execution framework. It governs the safety rules, source-of-truth rules, freeze and change governance, component dossier requirements, testing strategy, monitoring/publishing verification, private YouTube acceptance test, and final completion criteria.

### File B — `ClipForge_Page_and_Component_Prompts.md`

This is the detailed page/component execution pack. It contains page orchestration instructions and 38 component prompts covering the eight known UI pages, each with a 100-step component-specific verification contract. Execute the actual inventory, not only the examples in the file. Discover and add every additional real control found in the current checkout to the execution register and apply the same verification contract to it.

### Precedence

1. Applicable safety requirements and `ANTIGRAVITY_CLIPFORGE_FREEZE_RULES.md` / `MASTER_ENGINEERING_RULEBOOK.md`.
2. The master execution framework (File A).
3. The page/component prompts (File B).
4. The authoritative approved product requirements and phase records in the repository.
5. Current source code and test evidence used to determine actual implementation behavior.

A lower-level prompt cannot authorize bypassing a higher-level freeze rule or safety requirement. If a written prompt conflicts with the current authoritative specification, record the discrepancy, resolve it from the correct source where possible, and continue unrelated work.

## 3. Decisions and boundaries already established

- The approved mandatory roadmap ends at Phase 7. Phase 8 remains deferred and unapproved.
- Complete the approved Phase 1–7 UI-to-backend scope. Do not implement the deferred Phase 8 watermark feature.
- The owner requested one real-channel YouTube acceptance test with **Private** visibility. This authorization applies only to one centrally controlled acceptance upload, not to routine component tests.
- Mock/sandbox publishing must be used for all ordinary tests.
- Do not upload a public or unlisted test video.
- Do not automatically delete the created private test video.
- Preserve internal transcription required by approved scoring, semantic analysis, and metadata workflows.
- Do not reintroduce caption/subtitle generation, SRT/ASS rendering, subtitle filters, fonts, or burn-in.
- Preserve OpenRouter, Nvidia NIM, Groq Cloud Audio transcription, internal Whisper, and cloud-hosted models containing `Llama`, according to the actual code.
- Preserve all existing user work, modified files, untracked assets, credentials, media, databases, and persistent volumes.

## 4. Start immediately — do not remain in planning mode

Perform the following initialization sequence in the current repository:

1. Confirm repository root, active branch, HEAD commit and current `git status --short`.
2. Read the freeze rules, engineering rulebook, phase tracker, logic-freeze ledger, master execution ledger, implementation status, project continuity document, relevant approved master prompt, both companion files, and the most relevant current audit reports.
3. Capture the initial status and targeted diffs so pre-existing user changes can be identified and preserved.
4. Verify that both companion prompt files are present and readable. If they were attached to this agent session instead of copied into the repository, read the attachments. Do not assume a filename alone proves the file's contents were loaded.
5. Inventory the actual Next.js routes, rendered pages, components, controls, API-client functions, registered backend routes, relevant services/tasks, tests and persisted state fields.
6. Construct a task ledger with one row per component and stable child-control IDs. Use the IDs in File B where applicable; create new IDs for newly discovered real controls without renaming canonical phase or milestone IDs.
7. Start executing the first component prompt in File B after the inventory is established. Do not spend the remainder of the task producing additional planning documents instead of doing the work.

## 5. Mandatory execution order

Execute in this order, unless actual dependencies justify a documented adjustment:

1. **Dashboard (`/`)** — shell/navigation, URL or search input, jobs/history and filters, progress/status, per-job actions.
2. **Automation / Monitoring (`/automation`)** — channel selector and monitoring controls, video candidate queue/search/filtering, approve/reject/defer and batch actions, processing dispatch and Dashboard handoff, layout selector and reference thumbnails.
3. **Clips (`/clips`)** — search/filter/cards, preview/playback, Hook/SFX/B-roll controls, layout selection and rendered output, safe storage cleanup.
4. **Publish (`/publish`)** — queue list/filtering, cancel/retry, metadata editor/persistence, destination/schedule/publish action, final publication status synchronization.
5. **Analytics (`/analytics`)** — overview and date filters, per-video charts/tables, SEO/optimization history, channel refresh/polling/cooldown.
6. **YouTube Channels (`/youtube-channels`)** — OAuth controls, channel/source-vs-destination identity, monitoring configuration, channel statistics/refresh/errors.
7. **Settings (`/settings`)** — cloud AI configuration, load/save/masking, Whisper/transcription and limits, alerts/errors/recovery.
8. **Upload Studio (`/studio`)** — file selection/session creation, chunk upload/progress/retry/resume, manifest/commit/session lifecycle, thumbnails, processing handoff and supported publishing handoff.
9. **Cross-page and end-to-end reconciliation** — verify state and identifiers stay consistent across all the above pages and through actual backend execution.

Within each page, execute every corresponding component prompt from File B completely. If inspection reveals additional real interactive controls, add them to the register and perform the same 100-step contract; do not omit them because they lack a pre-written heading.

## 6. Required loop for every component and control

For each control, execute this full lifecycle:

1. Identify the approved acceptance criterion and the expected user-visible behavior.
2. Find its actual implementation and all relevant parents, children, handlers, types, API-client methods, backend routes, services, tasks, persistence records and tests.
3. Record baseline behavior and targeted Git diffs before edits.
4. Verify the control is actually interactive where presented as interactive; reject empty callbacks, placeholder handlers, console-only behavior, fabricated success messages and UI-only updates for operations that must reach the backend.
5. Trace the complete path: user interaction → frontend handler → correct HTTP/API call → registered backend route → validation/authorization → service/business logic → DB/storage/queue/provider effect → authoritative response/state → user-visible outcome.
6. Establish what proves success. A toast or HTTP 200 is insufficient when the operation should also create a job, persist settings, modify a record, render an artifact, upload a file or publish a video.
7. Test success, invalid input, authorization failures, server/network errors, timeouts, repeated actions, stale responses, persistence and page refresh where applicable.
8. Inspect loading, empty, partial-success, pending, completed, failed, cancelled, conflict and recovery states as applicable.
9. If a defect is confirmed and its repair is authorized by the approved scope and governance rules, make the smallest targeted fix and add/update a regression test where feasible.
10. Rerun the failing reproduction and the smallest relevant test. Then run affected integration/regression tests and frontend checks.
11. Perform Pass A against the requirement and implementation.
12. Independently perform Pass B through a second evidence path, such as backend-persisted state, actual route registration, event/task status, rendered output, reload behavior or a separate assertion.
13. If the passes disagree, investigate the disagreement; do not declare success until it is explained.
14. Repeat diagnose → fix → retest → independent verification until it passes or a genuine blocker remains.
15. Record exact files, symbols, endpoint, command, actual output, test counts, results, and limitations in the component dossier.
16. Move to the next component without routine user check-ins.

A component cannot receive `PASS` merely because it compiles, its route exists, or a neighboring test passes. Require evidence appropriate to its business behavior.

## 7. Layout preview and actual rendering requirements

The UI must show an accurate visual reference for every supported layout option that is available for users to select.

For every layout selector discovered:

1. Inventory the exact supported layout IDs/names from the actual frontend and backend implementation.
2. Identify the renderer associated with each layout and its accepted parameters.
3. Verify a visible reference thumbnail/preview exists for each selectable option.
4. If thumbnails are missing and adding them is inside approved scope and governance permits the change, create accurate local lightweight visual previews or approved representative sample images. Do not use deceptive or unrelated stock images.
5. Ensure preview assets resolve in development and production builds, have appropriate accessible labels, and clearly distinguish layout options.
6. Verify selecting a layout updates the real selected ID, request payload/state, stored settings where applicable, and renderer selection.
7. Verify output composition against the preview using a safe synthetic/test clip. Check aspect ratio, crop/position, speaker split, blur padding and composition details relevant to that layout.
8. Do not connect the deferred `apply_watermark()` branding layer or introduce Phase 8 features.
9. Record a per-layout matrix: layout ID → thumbnail asset → selector control → API/data field → backend renderer → generated output → visual comparison → tests → Pass A/Pass B outcome.

If a change required to deliver layout previews affects a frozen logic domain, follow the exact exception/approval procedure. Do not bypass it; record the change as governance-blocked and continue unrelated authorized work.

## 8. Monitoring, automation and publishing must be traced end to end

Monitoring is not verified simply because a channel is listed or a polling button responds.

Trace the actual supported lifecycle:

1. Confirm the authenticated source channel and its source/monitoring classification.
2. Verify authorization, monitoring settings, polling cadence, cooldowns, duplicate prevention and error states.
3. Trigger safe monitoring using the existing approved test context or supported API path.
4. Prove the poll ran, its output was processed, and candidate videos were discovered or an authoritative empty result was returned.
5. Verify candidates are persisted or reconciled correctly and displayed on Automation/Monitoring.
6. Verify approve/reject/defer operations update backend decision state, including expected-status/version/lease or locking requirements where implemented.
7. Verify the chosen processing action creates exactly the intended job and dispatches to Celery only once.
8. Track the returned job ID through queueing, worker execution, progress and terminal state.
9. Verify the produced artifact exists in the correct safe storage location and matches the chosen layout/options.
10. Verify publishing is directed to an explicitly configured destination channel, never accidentally to the source/monitoring channel.
11. Confirm the UI's final status from backend-authoritative persisted/external state, including failure and retry behavior.
12. Do not assume monitoring must publish automatically unless the approved product behavior explicitly says so. Follow the existing user decision/approval flow and destination safety contract.

Test mock/sandbox paths first. Only the one centrally gated private YouTube acceptance upload in Section 9 may perform a real upload.

## 9. One real YouTube private acceptance upload

The user has expressly requested a real-channel publishing test using **Private** visibility. This is limited to exactly one controlled acceptance upload, after all relevant mock-based UI, API, backend, processing, destination and publishing checks pass.

Before the live upload:

1. Inspect the real current publishing code, provider, authentication context, configured destination, request fields, privacy mapping, idempotency behavior and persisted status handling.
2. Identify one explicitly configured and already-authorized destination channel. Never guess among multiple connected accounts or channels.
3. Verify OAuth authorization is valid and the workflow can set `privacyStatus=private` before starting the upload.
4. Create or select a harmless test clip intended for acceptance testing. Do not upload real user footage or private personal content.
5. Ensure the test operation cannot silently retry into a second upload. Use the existing idempotency or reconciliation mechanism where it is proven to work.
6. Verify that the upload pathway is the actual integrated ClipForge UI/API/backend path under test, not a disconnected manual upload that bypasses the application.
7. Record the pre-upload check results with secrets redacted.

Then upload exactly one video with **Private** visibility.

Afterward verify all of the following:

- A real success response and returned YouTube video ID exist.
- The video is associated with the intended destination channel.
- The effective YouTube privacy status is `private`.
- The local publication/job record stores the same external video ID and a consistent state.
- The backend reports the proper terminal status without a fabricated success.
- The Publish page and any related detail surface show the correct destination and outcome after reload.
- No duplicate upload occurred.
- The evidence includes execution time, video ID, destination identity in appropriately redacted form, and the authoritative privacy/status response.

Do not upload Public or Unlisted. Do not automatically delete the private test video. Never log OAuth tokens or API keys.

If credentials are missing/expired, destination identity is ambiguous, privacy cannot be verified before upload, or duplicate risk cannot be controlled, **do not upload**. Record `BLOCKED — PRIVATE UPLOAD SAFETY PRECONDITION FAILED`, state exactly what evidence or setup is missing, and continue all other work. Do not ask the user during the run; include the blocker in the final report.

## 10. Autonomous decisions versus genuine blockers

Resolve routine technical questions by examining the actual repository, authoritative requirements, tests, logs, configured settings and API contracts. Do not ask the owner for information already available in those sources.

Do not pause to ask for approval between components, pages, normal safe test runs, or repairs that clearly fall within approved scope and the applicable rules.

When a change is outside authorized scope, requires a frozen-domain exception not already authorized, affects operational data, or needs missing external authorization:

- Do not bypass the rule.
- Create a precise blocker entry describing the acceptance criterion, affected files/domain, evidence, minimal proposed repair, test plan, risks and required authorization.
- Continue with other independent components.
- Do not claim the blocked component passed.

Never turn uncertainty into a success claim just to finish the run.

## 11. Working-tree, data, and test safeguards

- Capture `git status --short`, branch, HEAD and targeted diffs before edits and after the run.
- Do not run `git reset --hard`, `git clean`, `git checkout --`, `git restore .`, or equivalent blanket operations.
- Preserve pre-existing modifications and untracked files; make only surgical targeted edits.
- Confirm isolation before tests that mutate data.
- Never apply Alembic migrations, drop databases/tables, reset operational state, or clean the live `clipforge` database.
- Do not delete uploads, outputs, tokens, user clips, or persistent volumes.
- Do not print secrets in reports, logs, or screenshots.
- Ordinary automated tests must mock/sandbox all external publishing. Only the one Section 9 private upload is allowed to affect YouTube.
- Do not claim all tests passed unless the actual invoked tests and their outputs support the claim.
- Keep unique test count separate from repeated test executions.
- Report pre-existing lint warnings/errors separately from new defects.

## 12. Defect register and repeated verification

Maintain a live defect register with unique IDs. For every defect record:

- Page and component ID
- User-visible symptom
- Reproduction steps
- Expected behavior and approved requirement
- Actual behavior and evidence
- Root cause and affected layers
- Priority based on impact
- Whether the repair is authorized
- Exact files/lines changed
- Regression tests added or updated
- Test command and actual result
- Pass A evidence
- Pass B independent evidence
- Final status and any remaining limitation

A defect is closed only when the repaired behavior passes its relevant tests and independent verification. If a shared component, API client, backend route, schema, event/state mechanism or service changes, identify and rerun checks for all affected pages.

Do not label a defect fixed because the code was edited. Confirm the behavior afterward.

## 13. Required start checkpoint and operational execution

At the beginning of the run, write a short execution note to the task log (not to the user asking a question) containing:

- Confirmed repository root, branch and HEAD
- Whether both prompt files were read in full
- Initial Git status/diff preservation completed
- Actual page/component inventory count
- First component ID being executed
- Safety or governance constraints detected before work

Then start immediately with `DASH-01 — Dashboard page shell, navigation and shared header` in File B and continue sequentially through all component prompts.

Do not stop at this checkpoint. It is only the beginning of execution. Do not return a plan and wait. Do not ask the project owner to tell you which page comes next.

## 14. Final completion gate

The run is complete only after all real controls on all eight pages have been inventoried and each approved mandatory control has:

- Confirmed expected behavior and ownership/scope
- Handler/event verification
- API method/endpoint/contract verification where applicable
- Backend route/service/state/persistence/task verification where applicable
- Verified success and applicable failure states
- Verified refresh/persistence and cross-page synchronization where applicable
- Appropriate tests with actual results
- Pass A and independent Pass B evidence
- Any authorized repair applied and retested
- A final status that accurately reflects the evidence

Additionally:

- The layout reference matrix is complete for every supported selectable layout.
- The monitoring-to-processing-to-destination publishing trace is complete, or exact blockers are recorded.
- The single private YouTube acceptance upload is verified, or it is explicitly blocked by a safety prerequisite. A blocked upload must never be described as successful.
- TypeScript, lint, build and relevant test results are reconciled from actual output.
- Existing user changes are preserved.
- Frozen-domain governance is respected.
- Phase 8 remains deferred/unapproved.

## 15. Required final deliverables

Deliver one comprehensive report and the required supporting artifacts in the repository's governed audit location, provided documentation changes are allowed. Do not alter historical audit records merely to make results look consistent.

The final report must include:

1. Page-by-page completion matrix
2. Every discovered component and control ID
3. Per-control expected behavior and result
4. Frontend-to-backend endpoint coverage map
5. Persistence/queue/task/external-effect evidence
6. Layout ID/thumbnail/renderer/output verification matrix
7. Monitoring-to-publishing end-to-end trace
8. The private upload result or exact safety blocker
9. Defect register with repaired and unresolved items
10. Exact test commands, collected/passed/failed/skipped counts and exit status
11. TypeScript, lint, build and browser console/network evidence
12. Pass A and Pass B outcome for each component
13. Actual files changed and targeted Git diff summary
14. Confirmation that user work and data were preserved
15. Frozen-domain/authorization blockers
16. Explicit list of requirements not verified
17. Overall completion verdict

Use `PASS`, `PASS WITH LIMITATIONS`, `FAIL`, `NOT VERIFIED`, `NOT PRESENT / NOT REQUIRED`, or `BLOCKED` as appropriate.

Do not report “100% complete,” “zero bugs,” or “fully cross-verified” unless every mandatory acceptance criterion has corresponding credible evidence. Even after a successful audit, state that verification is bounded by the tests and observations actually performed; never promise the absence of every possible bug.

## Final execution instruction

Read both companion files in full, inspect the actual checkout, record the initial baseline, and **start work now with DASH-01**. Execute all approved component prompts in sequence, fix authorized defects, repeat tests and independent verification until each in-scope issue is closed or genuinely blocked, perform the single private YouTube acceptance upload if and only if every safety precondition passes, and return the consolidated final report. Do not pause for routine management intervention during the run.
