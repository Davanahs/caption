# ClipForge — Page-by-Page and Component-by-Component Execution Prompts

**Companion to:** `ClipForge_Autonomous_UI_Execution_and_Cross_Verification_Framework.md`  
**Execution policy:** The master framework governs all prompts. Work autonomously through approved Phase 1–7 requirements. Do not stop after building the UI; every component must be traced end-to-end to the backend.

## How to execute this file

1. Read the master framework first.
2. Inspect the live repository and enumerate all components actually present on each page. The prompt list below covers known surfaces from prior audits and examples; extend the discovered inventory to include **every additional real control** found in the current checkout.
3. Execute each component prompt in order within its page. The 100 steps in each component prompt are a complete control-specific execution contract, supplemented by the component focus and the global safety/testing/publishing rules in the master file.
4. Every prompt requires Pass A and Pass B. Do not skip Pass B just because Pass A or a test suite passed.
5. When a defect is fixed in a shared component/API/service, re-run the affected components on all pages.
6. Continue through all pages without requesting intermediate status approvals for routine fixes inside approved scope. Record genuine governance, credentials, ambiguity, and safety blockers for the final summary.
7. At the end, deliver one combined control-level matrix, defect register, test evidence, private-upload evidence or blocker, and overall frontend verdict.

## Mandatory private publishing requirement

The project owner has explicitly requested **one real YouTube acceptance upload with Private visibility**. First finish mock/sandbox checks, verify the configured authorized destination and ensure idempotency, then perform exactly one actual private upload through the integrated workflow. Never use public or unlisted visibility. Do not upload if the destination is ambiguous, credentials are not authorized, privacy cannot be guaranteed, or duplicate risk cannot be controlled; mark the item blocked and continue the rest of the work. Do not delete the private test artifact automatically. Full gates are specified in the master framework, Section 13.

## Actual UI inventory rule

If a component named below does not exist, do not create it simply to match the prompt. Search the current UI and specification to identify the real equivalent. Mark it `NOT PRESENT` where it is not required, or `MANDATORY GAP` where the approved acceptance criteria require it. Every discovered control must receive a child ID and the complete 100-step verification process from its page/component prompt.

---


## Page 1 — Dashboard (`/`)

### Page orchestration prompt

1. Work on Page 1 — Dashboard (`/`) as a page-level integration owner, using the master framework and all child prompts in this section.

2. Discover every actual child component and every interactive control from the current source, accessibility tree, and rendered page where browser inspection is available.

3. Create a route inventory and map each control to the relevant API endpoint, backend route/service, persistence or task path, and acceptance criterion.

4. Execute every child component prompt listed below, then inspect interactions between sibling components, shared state and cross-page navigation.

5. Test loading, empty, success, validation, auth failure, conflict, network failure, server failure and retry states applicable to the page.

6. Use component and integration tests. Run browser/E2E checks where available; label missing browser evidence as NOT VERIFIED.

7. Verify that every layout selection displays a real reference image and that selected layout ID reaches the correct renderer and appears in actual rendered output.

8. For monitoring, trace channel selection → poll → candidate discovery → decision → processing dispatch → persisted job progress → publishing destination → status result.

9. For Publish, verify normal mocked paths first and coordinate with the single central private YouTube upload gate; never create additional live uploads from component tests.

10. After all child components pass, test page-wide interactions, reloading, navigation away/back, shared API cache invalidation, stale response handling and component cleanup.

11. Perform a distinct Page Pass B using alternate evidence and record each finding against Page Pass A.

12. Fix authorized defects and rerun impacted tests until every mandatory page criterion passes or a specific governance/safety/external dependency blocks it.

13. Do not implement the proposed Phase 8 watermark feature. Keep the approved Phase 1–7 scope boundary.

14. Finish with a control-level matrix, endpoint coverage map, actual tests/results, files changed, evidence for both passes and unresolved blockers.


### Independent component prompts — each contains 100 required steps

### DASH-01 — Dashboard page shell, navigation and shared header

**Primary files to discover:** frontend/app/page.tsx and actual shared layout components  
**Component focus:** Dashboard route, shared navigation, active-job summary, route links, global page state  
**Acceptance focus:** Verify every navigation item, page title, active route marker, responsive menu, links, keyboard action, auth/context assumptions, and consistency with actual page routes.

Copy this complete prompt into the autonomous execution context for this component. Do not execute it in isolation from the master framework.

**100-step component prompt:**
1. Act as the autonomous owner of Dashboard page shell, navigation and shared header. Work only on the actual component discovered in the current checkout, not on an assumed or reconstructed UI.
2. Inspect frontend/app/page.tsx and actual shared layout components; follow imports and references to identify the real source files, tests, route and backend dependencies.
3. Component inventory: Dashboard route, shared navigation, active-job summary, route links, global page state. Discover the full list from the current UI and source. The list above is a focus guide, not permission to invent missing controls.
4. Acceptance focus: Verify every navigation item, page title, active route marker, responsive menu, links, keyboard action, auth/context assumptions, and consistency with actual page routes.
5. Create or update dossier ID `DASH-01` and link this component to its authoritative Phase/C-series acceptance criterion without redefining phase numbering.
6. Capture current behavior first: record the visible state, control labels, current handler, API call, server response, persisted state and known failure behavior.
7. List every individual button, input, dropdown, link, tab, selector, icon action, modal action and keyboard action in this component; give each a stable child control ID.
8. For every control, specify one positive test, one invalid/error test, one repeated-action/idempotency test where relevant, and one refresh/persistence or cross-page sync test where relevant.
9. Trace every mutation from browser event to API client, backend route, service, persistence/task/external provider and the final returned UI state.
10. Record the precise success assertion and the objective failure condition before changing code; never count a cosmetic animation or toast as proof of backend success.
11. Begin by opening the actual component, its parent, child components, types, API-client methods, and tests; do not trust a previous report without checking the current checkout.
12. List the exact visible controls that belong to this component, including icon-only buttons, links styled as buttons, keyboard shortcuts, toggles, dropdown options, modal actions, and any hidden action revealed by state.
13. For each control, state the requirement and observable success condition before testing it; map each requirement to the approved roadmap item without changing canonical phase numbers.
14. Check whether the control is intentionally non-interactive. If so, it must be semantically non-interactive and cannot imply that an unavailable action will occur.
15. Check accessible name, label/description, role, focusability, keyboard activation, disabled state, focus order, and whether focus returns appropriately after a dialog closes.
16. Trace the real event handler. Reject empty callbacks, console-only callbacks, hard-coded results, no-op links, timer-only simulation, and UI-only state mutation for backend operations.
17. Locate the corresponding API-client method and verify HTTP method, route path, body/query parameters, identifiers, headers/auth, response type, status-code handling, and timeout behavior.
18. Confirm that the route exists in the current backend application and is included under the actual router prefix. Do not infer endpoint existence from a frontend URL string.
19. Inspect backend validation, authorization, ownership checks, service calls, transaction boundaries, queue/task dispatch, and error mapping for the operation.
20. Identify the authoritative persisted record or external response that proves success. Do not use only a toast, button animation, or HTTP 200 as proof of the intended side effect.
21. Check that the frontend consumes the real response and maps returned identifiers/state correctly. Detect hard-coded status strings and mismatched field names.
22. Test the normal successful action using an isolated fixture or safe test record wherever available.
23. Test missing, malformed, stale, or unauthorized identifiers without modifying real user data.
24. Test the expected validation boundary conditions and verify the UI shows a useful message rather than silently dropping the request.
25. Test a server-side failure and confirm no false success indicator appears.
26. Test a network timeout/connection reset and verify the UI does not assume that the backend definitely failed if the outcome may be ambiguous.
27. Test loading indicators and confirm they clear on success, error, cancellation, component unmount, and every supported early return.
28. Test double-click, repeated Enter, quick toggle changes, duplicate network retries, and stale component state for unintended duplicate actions.
29. Check race handling if the action operates on mutable status, queue positions, decisions, settings, uploads, or publishing state.
30. Check that stale/out-of-order responses cannot overwrite a newer state. Use request cancellation, version checks, or existing conventions where needed and approved.
31. Check the response status is translated to the correct UI state, including pending/in-progress, completed, partial failure, failed, cancelled, and conflict states where applicable.
32. Check whether optimistic UI is used. If so, ensure rollback or reconciliation occurs when the backend rejects the change.
33. Check whether the changed state should survive page refresh/reopen; if yes, reload and compare the visible state to the backend-authoritative result.
34. Check whether the state is shared with other pages/components. Trigger the action and inspect every relevant surface for stale data.
35. Check that filters, sorting, selection, pagination, tabs, and the current detail item behave correctly after the operation changes data.
36. Check behavior when the list is empty, the API returns null/partial optional data, a media asset is missing, or a provider is temporarily unavailable.
37. Check timezones, timestamps, duration units, percentages, byte sizes, numeric formatting, and enum labels against backend semantics.
38. Check no credential, OAuth token, API key, signed URL, or private user payload is exposed in visible UI, ordinary logs, test output, or screenshots.
39. Check that test-mode fallbacks or synthetic fixtures can only be activated by the repository-defined trusted test context, never by user-controlled substring or arbitrary request fields.
40. Check the action does not add, restore, expose, or invoke caption/subtitle features. Internal transcription may remain for approved analysis and metadata purposes.
41. Check the action does not route to Ollama or require Ollama environment variables. Preserve approved cloud-hosted models even if their names contain Llama.
42. Check the operation cannot accidentally publish to a source/monitoring channel instead of an explicitly configured destination.
43. Where an action creates a job/task, verify the persisted job ID is retained and Celery dispatch occurs only at the intended transition.
44. Where an action updates a task, verify the backend state transition is valid, durable, and visible on subsequent reads.
45. Where an action creates or deletes a file, verify storage path containment, ownership, retention policy, and cleanup behavior using isolated files only.
46. Where a control selects a layout, verify the selected ID maps to a supported renderer option rather than only changing the visual highlight.
47. Where a control shows a layout thumbnail, verify the reference asset exists in the production build, has the correct accessible text, and truthfully represents output composition.
48. Where the component displays progress, verify it is sourced from authoritative progress/status fields and cannot display completion before the task completes.
49. Where the component refreshes/polls, verify intervals, overlap, cooldown, backoff, and unmount cleanup against the actual code contract.
50. Where external providers are involved, test mocked/sandbox cases first and ensure no accidental external side effect is triggered by an ordinary test.
51. For the private YouTube acceptance upload, do not use this component test to generate another upload. The one real upload is centrally orchestrated and idempotently gated under the master framework.
52. Inspect the relevant unit/component test and add a regression test for each repaired defect where test infrastructure permits.
53. Run the smallest test covering this component first and record the exact command and actual exit result.
54. Run the relevant API/backend integration test where it can be proven safe and isolated.
55. Run the relevant browser/E2E test if available; do not describe static source inspection as a browser test.
56. Collect actual request/response evidence with secrets redacted. Link to the logs or test output that substantiate the result.
57. Compare the user-visible message/status with the actual backend response and persisted state.
58. Conduct Pass A by tracing requirements to implementation and successful tests.
59. Conduct Pass B independently using an alternate path such as persisted state, route registration, event log, task state, rendered output, refresh behavior, or a different test assertion.
60. If Pass A and Pass B disagree, investigate and document the discrepancy; do not average the results or silently pick the favorable one.
61. Classify a failure as UI defect, API contract mismatch, backend behavior defect, persistence defect, concurrency defect, configuration defect, missing test/evidence, or scope ambiguity.
62. Fix only defects within approved Phase 1–7 requirements and only through the governance process required by the freeze rules.
63. Before changing a shared API client, component, schema, backend route, or frozen domain, identify all affected pages and regression tests.
64. Keep the code change minimal and preserve pre-existing Git modifications and untracked files.
65. Never execute blanket Git reset/clean/checkout/restore commands or replace a whole file to make a small repair.
66. After a repair, rerun the failing reproduction, relevant component test, API/backend tests, and affected page regression checks.
67. Independently repeat Pass B after the repair, using evidence distinct from the original fix path where reasonably possible.
68. If the test fails, continue the diagnose/fix/retest loop within scope; if the failure requires unavailable authorization or unsafe operation, mark it blocked and continue unrelated work.
69. Do not stop at the first failed test if the cause is repairable within scope. Do not loop indefinitely if a genuine external or governance blocker exists.
70. Check that test teardown completes and does not silently mask failures; do not change global fixtures unless required and governed.
71. Confirm test DB isolation before any database mutation. Never migrate, drop, reset, or clean the operational clipforge database.
72. Confirm no test publishes an actual video except the one centralized, explicit, private acceptance upload authorized by the user.
73. Confirm no generated test file overwrites existing uploads or outputs and no cleanup task deletes user-owned media.
74. Run TypeScript and lint checks against the changed frontend where possible. Report repository-wide legacy issues separately from new introduced issues.
75. Run the production build after page/component changes and distinguish build output count from the number of user-facing pages.
76. Inspect browser console errors, failed network requests, React warnings, hydration issues, and unhandled promise rejections where browser execution is available.
77. Check responsive layout at narrow and wide viewport sizes, avoiding horizontal overflow, clipped dialogs, invisible controls, and inaccessible hover-only actions.
78. Check error messages are actionable, avoid secrets, and preserve user-entered form data where retry is expected.
79. Check the component handles loading, empty, success, partial-success, validation, unauthorized, not-found, conflict, rate-limit, server-error, and offline states as applicable.
80. Check that stale UI cache does not outlive a mutation. Invalidate/refetch only the relevant query/state according to the existing architecture.
81. Check a successful response has not been mistaken for semantic success when the backend returns a task ID with pending execution.
82. Check task completion is awaited or polled appropriately and the user can identify pending versus completed processing.
83. Check external provider errors propagate to a truthful status rather than being caught and converted into fabricated success.
84. Check any retry operation cannot create duplicate jobs, settings writes, uploads, publications, or cleanup operations.
85. Check the component has no hidden coupling to unapproved Phase 8 watermark branding or unsupported layouts.
86. Cross-reference actual behavior with `PHASE_TRACKER.md`, the relevant approved prompt, and the actual backend route/service. Do not assume draft/archived prompts are mandatory scope.
87. Check related documentation only if it is directly affected by the verified implementation; preserve historical audit evidence.
88. Update the component dossier with actual file paths, symbols, endpoint, backend behavior, test commands, Pass A evidence and Pass B evidence.
89. If a required operation is not present in the current UI, mark it absent and verify whether the approved specification requires it; do not silently invent UI.
90. If a required capability is absent, identify the exact implementation/API/test gap and fix it only when inside approved scope and governance permits.
91. Before any edit, record targeted Git status/diff; after edits, verify unrelated working-tree changes and untracked assets remain untouched.
92. Do not make changes beyond approved Phase 1–7 scope; Phase 8 watermark branding remains deferred unless separately authorized.
93. If this component offers a layout choice, require a real local reference thumbnail for every supported option and verify the output renderer matches it.
94. If this component participates in monitoring/publishing, check destination identity and state synchronization, and obey the central private-upload gate; do not create a second real upload.
95. Never expose secrets, run destructive database operations, publish public/unlisted test videos, or delete user media while verifying this component.
96. Perform Pass A: independently map every acceptance criterion to implementation and test evidence. Record exact paths, symbols, commands and actual results.
97. Perform Pass B independently using alternate evidence; explicitly confirm, contradict or leave uncertain every material Pass A claim.
98. Repair eligible defects and repeat the complete relevant test loop; if governance or safety blocks a fix, record the exact blocker and continue independent work.
99. Final acceptance for `DASH-01`: every mandatory control in Dashboard page shell, navigation and shared header must have a real handler/contract, verified backend result, correct UI synchronization, passing relevant test, and independent Pass A/Pass B evidence.
100. Return a concise per-control matrix, exact files changed, tests and results, unresolved issues, and final component verdict. Do not declare PASS when evidence is missing.


---

### DASH-02 — URL/search input and submit action

**Primary files to discover:** Discover the actual Dashboard URL input/search form and API client  
**Component focus:** URL input, paste/search/submit control, validation, backend ingestion or job creation  
**Acceptance focus:** Verify valid/invalid URLs, whitespace, unsupported URL/provider, rapid repeated submit, request payload, backend result, resulting job/video record, loading state, error display, and navigation to the persisted job.

Copy this complete prompt into the autonomous execution context for this component. Do not execute it in isolation from the master framework.

**100-step component prompt:**
1. Act as the autonomous owner of URL/search input and submit action. Work only on the actual component discovered in the current checkout, not on an assumed or reconstructed UI.
2. Inspect Discover the actual Dashboard URL input/search form and API client; follow imports and references to identify the real source files, tests, route and backend dependencies.
3. Component inventory: URL input, paste/search/submit control, validation, backend ingestion or job creation. Discover the full list from the current UI and source. The list above is a focus guide, not permission to invent missing controls.
4. Acceptance focus: Verify valid/invalid URLs, whitespace, unsupported URL/provider, rapid repeated submit, request payload, backend result, resulting job/video record, loading state, error display, and navigation to the persisted job.
5. Create or update dossier ID `DASH-02` and link this component to its authoritative Phase/C-series acceptance criterion without redefining phase numbering.
6. Capture current behavior first: record the visible state, control labels, current handler, API call, server response, persisted state and known failure behavior.
7. List every individual button, input, dropdown, link, tab, selector, icon action, modal action and keyboard action in this component; give each a stable child control ID.
8. For every control, specify one positive test, one invalid/error test, one repeated-action/idempotency test where relevant, and one refresh/persistence or cross-page sync test where relevant.
9. Trace every mutation from browser event to API client, backend route, service, persistence/task/external provider and the final returned UI state.
10. Record the precise success assertion and the objective failure condition before changing code; never count a cosmetic animation or toast as proof of backend success.
11. Begin by opening the actual component, its parent, child components, types, API-client methods, and tests; do not trust a previous report without checking the current checkout.
12. List the exact visible controls that belong to this component, including icon-only buttons, links styled as buttons, keyboard shortcuts, toggles, dropdown options, modal actions, and any hidden action revealed by state.
13. For each control, state the requirement and observable success condition before testing it; map each requirement to the approved roadmap item without changing canonical phase numbers.
14. Check whether the control is intentionally non-interactive. If so, it must be semantically non-interactive and cannot imply that an unavailable action will occur.
15. Check accessible name, label/description, role, focusability, keyboard activation, disabled state, focus order, and whether focus returns appropriately after a dialog closes.
16. Trace the real event handler. Reject empty callbacks, console-only callbacks, hard-coded results, no-op links, timer-only simulation, and UI-only state mutation for backend operations.
17. Locate the corresponding API-client method and verify HTTP method, route path, body/query parameters, identifiers, headers/auth, response type, status-code handling, and timeout behavior.
18. Confirm that the route exists in the current backend application and is included under the actual router prefix. Do not infer endpoint existence from a frontend URL string.
19. Inspect backend validation, authorization, ownership checks, service calls, transaction boundaries, queue/task dispatch, and error mapping for the operation.
20. Identify the authoritative persisted record or external response that proves success. Do not use only a toast, button animation, or HTTP 200 as proof of the intended side effect.
21. Check that the frontend consumes the real response and maps returned identifiers/state correctly. Detect hard-coded status strings and mismatched field names.
22. Test the normal successful action using an isolated fixture or safe test record wherever available.
23. Test missing, malformed, stale, or unauthorized identifiers without modifying real user data.
24. Test the expected validation boundary conditions and verify the UI shows a useful message rather than silently dropping the request.
25. Test a server-side failure and confirm no false success indicator appears.
26. Test a network timeout/connection reset and verify the UI does not assume that the backend definitely failed if the outcome may be ambiguous.
27. Test loading indicators and confirm they clear on success, error, cancellation, component unmount, and every supported early return.
28. Test double-click, repeated Enter, quick toggle changes, duplicate network retries, and stale component state for unintended duplicate actions.
29. Check race handling if the action operates on mutable status, queue positions, decisions, settings, uploads, or publishing state.
30. Check that stale/out-of-order responses cannot overwrite a newer state. Use request cancellation, version checks, or existing conventions where needed and approved.
31. Check the response status is translated to the correct UI state, including pending/in-progress, completed, partial failure, failed, cancelled, and conflict states where applicable.
32. Check whether optimistic UI is used. If so, ensure rollback or reconciliation occurs when the backend rejects the change.
33. Check whether the changed state should survive page refresh/reopen; if yes, reload and compare the visible state to the backend-authoritative result.
34. Check whether the state is shared with other pages/components. Trigger the action and inspect every relevant surface for stale data.
35. Check that filters, sorting, selection, pagination, tabs, and the current detail item behave correctly after the operation changes data.
36. Check behavior when the list is empty, the API returns null/partial optional data, a media asset is missing, or a provider is temporarily unavailable.
37. Check timezones, timestamps, duration units, percentages, byte sizes, numeric formatting, and enum labels against backend semantics.
38. Check no credential, OAuth token, API key, signed URL, or private user payload is exposed in visible UI, ordinary logs, test output, or screenshots.
39. Check that test-mode fallbacks or synthetic fixtures can only be activated by the repository-defined trusted test context, never by user-controlled substring or arbitrary request fields.
40. Check the action does not add, restore, expose, or invoke caption/subtitle features. Internal transcription may remain for approved analysis and metadata purposes.
41. Check the action does not route to Ollama or require Ollama environment variables. Preserve approved cloud-hosted models even if their names contain Llama.
42. Check the operation cannot accidentally publish to a source/monitoring channel instead of an explicitly configured destination.
43. Where an action creates a job/task, verify the persisted job ID is retained and Celery dispatch occurs only at the intended transition.
44. Where an action updates a task, verify the backend state transition is valid, durable, and visible on subsequent reads.
45. Where an action creates or deletes a file, verify storage path containment, ownership, retention policy, and cleanup behavior using isolated files only.
46. Where a control selects a layout, verify the selected ID maps to a supported renderer option rather than only changing the visual highlight.
47. Where a control shows a layout thumbnail, verify the reference asset exists in the production build, has the correct accessible text, and truthfully represents output composition.
48. Where the component displays progress, verify it is sourced from authoritative progress/status fields and cannot display completion before the task completes.
49. Where the component refreshes/polls, verify intervals, overlap, cooldown, backoff, and unmount cleanup against the actual code contract.
50. Where external providers are involved, test mocked/sandbox cases first and ensure no accidental external side effect is triggered by an ordinary test.
51. For the private YouTube acceptance upload, do not use this component test to generate another upload. The one real upload is centrally orchestrated and idempotently gated under the master framework.
52. Inspect the relevant unit/component test and add a regression test for each repaired defect where test infrastructure permits.
53. Run the smallest test covering this component first and record the exact command and actual exit result.
54. Run the relevant API/backend integration test where it can be proven safe and isolated.
55. Run the relevant browser/E2E test if available; do not describe static source inspection as a browser test.
56. Collect actual request/response evidence with secrets redacted. Link to the logs or test output that substantiate the result.
57. Compare the user-visible message/status with the actual backend response and persisted state.
58. Conduct Pass A by tracing requirements to implementation and successful tests.
59. Conduct Pass B independently using an alternate path such as persisted state, route registration, event log, task state, rendered output, refresh behavior, or a different test assertion.
60. If Pass A and Pass B disagree, investigate and document the discrepancy; do not average the results or silently pick the favorable one.
61. Classify a failure as UI defect, API contract mismatch, backend behavior defect, persistence defect, concurrency defect, configuration defect, missing test/evidence, or scope ambiguity.
62. Fix only defects within approved Phase 1–7 requirements and only through the governance process required by the freeze rules.
63. Before changing a shared API client, component, schema, backend route, or frozen domain, identify all affected pages and regression tests.
64. Keep the code change minimal and preserve pre-existing Git modifications and untracked files.
65. Never execute blanket Git reset/clean/checkout/restore commands or replace a whole file to make a small repair.
66. After a repair, rerun the failing reproduction, relevant component test, API/backend tests, and affected page regression checks.
67. Independently repeat Pass B after the repair, using evidence distinct from the original fix path where reasonably possible.
68. If the test fails, continue the diagnose/fix/retest loop within scope; if the failure requires unavailable authorization or unsafe operation, mark it blocked and continue unrelated work.
69. Do not stop at the first failed test if the cause is repairable within scope. Do not loop indefinitely if a genuine external or governance blocker exists.
70. Check that test teardown completes and does not silently mask failures; do not change global fixtures unless required and governed.
71. Confirm test DB isolation before any database mutation. Never migrate, drop, reset, or clean the operational clipforge database.
72. Confirm no test publishes an actual video except the one centralized, explicit, private acceptance upload authorized by the user.
73. Confirm no generated test file overwrites existing uploads or outputs and no cleanup task deletes user-owned media.
74. Run TypeScript and lint checks against the changed frontend where possible. Report repository-wide legacy issues separately from new introduced issues.
75. Run the production build after page/component changes and distinguish build output count from the number of user-facing pages.
76. Inspect browser console errors, failed network requests, React warnings, hydration issues, and unhandled promise rejections where browser execution is available.
77. Check responsive layout at narrow and wide viewport sizes, avoiding horizontal overflow, clipped dialogs, invisible controls, and inaccessible hover-only actions.
78. Check error messages are actionable, avoid secrets, and preserve user-entered form data where retry is expected.
79. Check the component handles loading, empty, success, partial-success, validation, unauthorized, not-found, conflict, rate-limit, server-error, and offline states as applicable.
80. Check that stale UI cache does not outlive a mutation. Invalidate/refetch only the relevant query/state according to the existing architecture.
81. Check a successful response has not been mistaken for semantic success when the backend returns a task ID with pending execution.
82. Check task completion is awaited or polled appropriately and the user can identify pending versus completed processing.
83. Check external provider errors propagate to a truthful status rather than being caught and converted into fabricated success.
84. Check any retry operation cannot create duplicate jobs, settings writes, uploads, publications, or cleanup operations.
85. Check the component has no hidden coupling to unapproved Phase 8 watermark branding or unsupported layouts.
86. Cross-reference actual behavior with `PHASE_TRACKER.md`, the relevant approved prompt, and the actual backend route/service. Do not assume draft/archived prompts are mandatory scope.
87. Check related documentation only if it is directly affected by the verified implementation; preserve historical audit evidence.
88. Update the component dossier with actual file paths, symbols, endpoint, backend behavior, test commands, Pass A evidence and Pass B evidence.
89. If a required operation is not present in the current UI, mark it absent and verify whether the approved specification requires it; do not silently invent UI.
90. If a required capability is absent, identify the exact implementation/API/test gap and fix it only when inside approved scope and governance permits.
91. Before any edit, record targeted Git status/diff; after edits, verify unrelated working-tree changes and untracked assets remain untouched.
92. Do not make changes beyond approved Phase 1–7 scope; Phase 8 watermark branding remains deferred unless separately authorized.
93. If this component offers a layout choice, require a real local reference thumbnail for every supported option and verify the output renderer matches it.
94. If this component participates in monitoring/publishing, check destination identity and state synchronization, and obey the central private-upload gate; do not create a second real upload.
95. Never expose secrets, run destructive database operations, publish public/unlisted test videos, or delete user media while verifying this component.
96. Perform Pass A: independently map every acceptance criterion to implementation and test evidence. Record exact paths, symbols, commands and actual results.
97. Perform Pass B independently using alternate evidence; explicitly confirm, contradict or leave uncertain every material Pass A claim.
98. Repair eligible defects and repeat the complete relevant test loop; if governance or safety blocks a fix, record the exact blocker and continue independent work.
99. Final acceptance for `DASH-02`: every mandatory control in URL/search input and submit action must have a real handler/contract, verified backend result, correct UI synchronization, passing relevant test, and independent Pass A/Pass B evidence.
100. Return a concise per-control matrix, exact files changed, tests and results, unresolved issues, and final component verdict. Do not declare PASS when evidence is missing.


---

### DASH-03 — Jobs/history list and filters

**Primary files to discover:** Dashboard job/history list and its actual API methods  
**Component focus:** Job cards/rows, filters, refresh, empty state, error state, pagination if present  
**Acceptance focus:** Verify rows match backend jobs, identifiers and statuses; sorting/filtering; refresh; no duplicate rows; correct links; empty/error/retry behavior; persisted results after reload.

Copy this complete prompt into the autonomous execution context for this component. Do not execute it in isolation from the master framework.

**100-step component prompt:**
1. Act as the autonomous owner of Jobs/history list and filters. Work only on the actual component discovered in the current checkout, not on an assumed or reconstructed UI.
2. Inspect Dashboard job/history list and its actual API methods; follow imports and references to identify the real source files, tests, route and backend dependencies.
3. Component inventory: Job cards/rows, filters, refresh, empty state, error state, pagination if present. Discover the full list from the current UI and source. The list above is a focus guide, not permission to invent missing controls.
4. Acceptance focus: Verify rows match backend jobs, identifiers and statuses; sorting/filtering; refresh; no duplicate rows; correct links; empty/error/retry behavior; persisted results after reload.
5. Create or update dossier ID `DASH-03` and link this component to its authoritative Phase/C-series acceptance criterion without redefining phase numbering.
6. Capture current behavior first: record the visible state, control labels, current handler, API call, server response, persisted state and known failure behavior.
7. List every individual button, input, dropdown, link, tab, selector, icon action, modal action and keyboard action in this component; give each a stable child control ID.
8. For every control, specify one positive test, one invalid/error test, one repeated-action/idempotency test where relevant, and one refresh/persistence or cross-page sync test where relevant.
9. Trace every mutation from browser event to API client, backend route, service, persistence/task/external provider and the final returned UI state.
10. Record the precise success assertion and the objective failure condition before changing code; never count a cosmetic animation or toast as proof of backend success.
11. Begin by opening the actual component, its parent, child components, types, API-client methods, and tests; do not trust a previous report without checking the current checkout.
12. List the exact visible controls that belong to this component, including icon-only buttons, links styled as buttons, keyboard shortcuts, toggles, dropdown options, modal actions, and any hidden action revealed by state.
13. For each control, state the requirement and observable success condition before testing it; map each requirement to the approved roadmap item without changing canonical phase numbers.
14. Check whether the control is intentionally non-interactive. If so, it must be semantically non-interactive and cannot imply that an unavailable action will occur.
15. Check accessible name, label/description, role, focusability, keyboard activation, disabled state, focus order, and whether focus returns appropriately after a dialog closes.
16. Trace the real event handler. Reject empty callbacks, console-only callbacks, hard-coded results, no-op links, timer-only simulation, and UI-only state mutation for backend operations.
17. Locate the corresponding API-client method and verify HTTP method, route path, body/query parameters, identifiers, headers/auth, response type, status-code handling, and timeout behavior.
18. Confirm that the route exists in the current backend application and is included under the actual router prefix. Do not infer endpoint existence from a frontend URL string.
19. Inspect backend validation, authorization, ownership checks, service calls, transaction boundaries, queue/task dispatch, and error mapping for the operation.
20. Identify the authoritative persisted record or external response that proves success. Do not use only a toast, button animation, or HTTP 200 as proof of the intended side effect.
21. Check that the frontend consumes the real response and maps returned identifiers/state correctly. Detect hard-coded status strings and mismatched field names.
22. Test the normal successful action using an isolated fixture or safe test record wherever available.
23. Test missing, malformed, stale, or unauthorized identifiers without modifying real user data.
24. Test the expected validation boundary conditions and verify the UI shows a useful message rather than silently dropping the request.
25. Test a server-side failure and confirm no false success indicator appears.
26. Test a network timeout/connection reset and verify the UI does not assume that the backend definitely failed if the outcome may be ambiguous.
27. Test loading indicators and confirm they clear on success, error, cancellation, component unmount, and every supported early return.
28. Test double-click, repeated Enter, quick toggle changes, duplicate network retries, and stale component state for unintended duplicate actions.
29. Check race handling if the action operates on mutable status, queue positions, decisions, settings, uploads, or publishing state.
30. Check that stale/out-of-order responses cannot overwrite a newer state. Use request cancellation, version checks, or existing conventions where needed and approved.
31. Check the response status is translated to the correct UI state, including pending/in-progress, completed, partial failure, failed, cancelled, and conflict states where applicable.
32. Check whether optimistic UI is used. If so, ensure rollback or reconciliation occurs when the backend rejects the change.
33. Check whether the changed state should survive page refresh/reopen; if yes, reload and compare the visible state to the backend-authoritative result.
34. Check whether the state is shared with other pages/components. Trigger the action and inspect every relevant surface for stale data.
35. Check that filters, sorting, selection, pagination, tabs, and the current detail item behave correctly after the operation changes data.
36. Check behavior when the list is empty, the API returns null/partial optional data, a media asset is missing, or a provider is temporarily unavailable.
37. Check timezones, timestamps, duration units, percentages, byte sizes, numeric formatting, and enum labels against backend semantics.
38. Check no credential, OAuth token, API key, signed URL, or private user payload is exposed in visible UI, ordinary logs, test output, or screenshots.
39. Check that test-mode fallbacks or synthetic fixtures can only be activated by the repository-defined trusted test context, never by user-controlled substring or arbitrary request fields.
40. Check the action does not add, restore, expose, or invoke caption/subtitle features. Internal transcription may remain for approved analysis and metadata purposes.
41. Check the action does not route to Ollama or require Ollama environment variables. Preserve approved cloud-hosted models even if their names contain Llama.
42. Check the operation cannot accidentally publish to a source/monitoring channel instead of an explicitly configured destination.
43. Where an action creates a job/task, verify the persisted job ID is retained and Celery dispatch occurs only at the intended transition.
44. Where an action updates a task, verify the backend state transition is valid, durable, and visible on subsequent reads.
45. Where an action creates or deletes a file, verify storage path containment, ownership, retention policy, and cleanup behavior using isolated files only.
46. Where a control selects a layout, verify the selected ID maps to a supported renderer option rather than only changing the visual highlight.
47. Where a control shows a layout thumbnail, verify the reference asset exists in the production build, has the correct accessible text, and truthfully represents output composition.
48. Where the component displays progress, verify it is sourced from authoritative progress/status fields and cannot display completion before the task completes.
49. Where the component refreshes/polls, verify intervals, overlap, cooldown, backoff, and unmount cleanup against the actual code contract.
50. Where external providers are involved, test mocked/sandbox cases first and ensure no accidental external side effect is triggered by an ordinary test.
51. For the private YouTube acceptance upload, do not use this component test to generate another upload. The one real upload is centrally orchestrated and idempotently gated under the master framework.
52. Inspect the relevant unit/component test and add a regression test for each repaired defect where test infrastructure permits.
53. Run the smallest test covering this component first and record the exact command and actual exit result.
54. Run the relevant API/backend integration test where it can be proven safe and isolated.
55. Run the relevant browser/E2E test if available; do not describe static source inspection as a browser test.
56. Collect actual request/response evidence with secrets redacted. Link to the logs or test output that substantiate the result.
57. Compare the user-visible message/status with the actual backend response and persisted state.
58. Conduct Pass A by tracing requirements to implementation and successful tests.
59. Conduct Pass B independently using an alternate path such as persisted state, route registration, event log, task state, rendered output, refresh behavior, or a different test assertion.
60. If Pass A and Pass B disagree, investigate and document the discrepancy; do not average the results or silently pick the favorable one.
61. Classify a failure as UI defect, API contract mismatch, backend behavior defect, persistence defect, concurrency defect, configuration defect, missing test/evidence, or scope ambiguity.
62. Fix only defects within approved Phase 1–7 requirements and only through the governance process required by the freeze rules.
63. Before changing a shared API client, component, schema, backend route, or frozen domain, identify all affected pages and regression tests.
64. Keep the code change minimal and preserve pre-existing Git modifications and untracked files.
65. Never execute blanket Git reset/clean/checkout/restore commands or replace a whole file to make a small repair.
66. After a repair, rerun the failing reproduction, relevant component test, API/backend tests, and affected page regression checks.
67. Independently repeat Pass B after the repair, using evidence distinct from the original fix path where reasonably possible.
68. If the test fails, continue the diagnose/fix/retest loop within scope; if the failure requires unavailable authorization or unsafe operation, mark it blocked and continue unrelated work.
69. Do not stop at the first failed test if the cause is repairable within scope. Do not loop indefinitely if a genuine external or governance blocker exists.
70. Check that test teardown completes and does not silently mask failures; do not change global fixtures unless required and governed.
71. Confirm test DB isolation before any database mutation. Never migrate, drop, reset, or clean the operational clipforge database.
72. Confirm no test publishes an actual video except the one centralized, explicit, private acceptance upload authorized by the user.
73. Confirm no generated test file overwrites existing uploads or outputs and no cleanup task deletes user-owned media.
74. Run TypeScript and lint checks against the changed frontend where possible. Report repository-wide legacy issues separately from new introduced issues.
75. Run the production build after page/component changes and distinguish build output count from the number of user-facing pages.
76. Inspect browser console errors, failed network requests, React warnings, hydration issues, and unhandled promise rejections where browser execution is available.
77. Check responsive layout at narrow and wide viewport sizes, avoiding horizontal overflow, clipped dialogs, invisible controls, and inaccessible hover-only actions.
78. Check error messages are actionable, avoid secrets, and preserve user-entered form data where retry is expected.
79. Check the component handles loading, empty, success, partial-success, validation, unauthorized, not-found, conflict, rate-limit, server-error, and offline states as applicable.
80. Check that stale UI cache does not outlive a mutation. Invalidate/refetch only the relevant query/state according to the existing architecture.
81. Check a successful response has not been mistaken for semantic success when the backend returns a task ID with pending execution.
82. Check task completion is awaited or polled appropriately and the user can identify pending versus completed processing.
83. Check external provider errors propagate to a truthful status rather than being caught and converted into fabricated success.
84. Check any retry operation cannot create duplicate jobs, settings writes, uploads, publications, or cleanup operations.
85. Check the component has no hidden coupling to unapproved Phase 8 watermark branding or unsupported layouts.
86. Cross-reference actual behavior with `PHASE_TRACKER.md`, the relevant approved prompt, and the actual backend route/service. Do not assume draft/archived prompts are mandatory scope.
87. Check related documentation only if it is directly affected by the verified implementation; preserve historical audit evidence.
88. Update the component dossier with actual file paths, symbols, endpoint, backend behavior, test commands, Pass A evidence and Pass B evidence.
89. If a required operation is not present in the current UI, mark it absent and verify whether the approved specification requires it; do not silently invent UI.
90. If a required capability is absent, identify the exact implementation/API/test gap and fix it only when inside approved scope and governance permits.
91. Before any edit, record targeted Git status/diff; after edits, verify unrelated working-tree changes and untracked assets remain untouched.
92. Do not make changes beyond approved Phase 1–7 scope; Phase 8 watermark branding remains deferred unless separately authorized.
93. If this component offers a layout choice, require a real local reference thumbnail for every supported option and verify the output renderer matches it.
94. If this component participates in monitoring/publishing, check destination identity and state synchronization, and obey the central private-upload gate; do not create a second real upload.
95. Never expose secrets, run destructive database operations, publish public/unlisted test videos, or delete user media while verifying this component.
96. Perform Pass A: independently map every acceptance criterion to implementation and test evidence. Record exact paths, symbols, commands and actual results.
97. Perform Pass B independently using alternate evidence; explicitly confirm, contradict or leave uncertain every material Pass A claim.
98. Repair eligible defects and repeat the complete relevant test loop; if governance or safety blocks a fix, record the exact blocker and continue independent work.
99. Final acceptance for `DASH-03`: every mandatory control in Jobs/history list and filters must have a real handler/contract, verified backend result, correct UI synchronization, passing relevant test, and independent Pass A/Pass B evidence.
100. Return a concise per-control matrix, exact files changed, tests and results, unresolved issues, and final component verdict. Do not declare PASS when evidence is missing.


---

### DASH-04 — Job progress and status display

**Primary files to discover:** Dashboard progress components and real job status APIs/polling  
**Component focus:** Progress bar/stepper, status labels, timestamps, failure details, detail links  
**Acceptance focus:** Verify progress uses persisted state, stages do not regress due to out-of-order polling, terminal states are accurate, time/percentage units are correct, failures are visible, and refresh reproduces the same truth.

Copy this complete prompt into the autonomous execution context for this component. Do not execute it in isolation from the master framework.

**100-step component prompt:**
1. Act as the autonomous owner of Job progress and status display. Work only on the actual component discovered in the current checkout, not on an assumed or reconstructed UI.
2. Inspect Dashboard progress components and real job status APIs/polling; follow imports and references to identify the real source files, tests, route and backend dependencies.
3. Component inventory: Progress bar/stepper, status labels, timestamps, failure details, detail links. Discover the full list from the current UI and source. The list above is a focus guide, not permission to invent missing controls.
4. Acceptance focus: Verify progress uses persisted state, stages do not regress due to out-of-order polling, terminal states are accurate, time/percentage units are correct, failures are visible, and refresh reproduces the same truth.
5. Create or update dossier ID `DASH-04` and link this component to its authoritative Phase/C-series acceptance criterion without redefining phase numbering.
6. Capture current behavior first: record the visible state, control labels, current handler, API call, server response, persisted state and known failure behavior.
7. List every individual button, input, dropdown, link, tab, selector, icon action, modal action and keyboard action in this component; give each a stable child control ID.
8. For every control, specify one positive test, one invalid/error test, one repeated-action/idempotency test where relevant, and one refresh/persistence or cross-page sync test where relevant.
9. Trace every mutation from browser event to API client, backend route, service, persistence/task/external provider and the final returned UI state.
10. Record the precise success assertion and the objective failure condition before changing code; never count a cosmetic animation or toast as proof of backend success.
11. Begin by opening the actual component, its parent, child components, types, API-client methods, and tests; do not trust a previous report without checking the current checkout.
12. List the exact visible controls that belong to this component, including icon-only buttons, links styled as buttons, keyboard shortcuts, toggles, dropdown options, modal actions, and any hidden action revealed by state.
13. For each control, state the requirement and observable success condition before testing it; map each requirement to the approved roadmap item without changing canonical phase numbers.
14. Check whether the control is intentionally non-interactive. If so, it must be semantically non-interactive and cannot imply that an unavailable action will occur.
15. Check accessible name, label/description, role, focusability, keyboard activation, disabled state, focus order, and whether focus returns appropriately after a dialog closes.
16. Trace the real event handler. Reject empty callbacks, console-only callbacks, hard-coded results, no-op links, timer-only simulation, and UI-only state mutation for backend operations.
17. Locate the corresponding API-client method and verify HTTP method, route path, body/query parameters, identifiers, headers/auth, response type, status-code handling, and timeout behavior.
18. Confirm that the route exists in the current backend application and is included under the actual router prefix. Do not infer endpoint existence from a frontend URL string.
19. Inspect backend validation, authorization, ownership checks, service calls, transaction boundaries, queue/task dispatch, and error mapping for the operation.
20. Identify the authoritative persisted record or external response that proves success. Do not use only a toast, button animation, or HTTP 200 as proof of the intended side effect.
21. Check that the frontend consumes the real response and maps returned identifiers/state correctly. Detect hard-coded status strings and mismatched field names.
22. Test the normal successful action using an isolated fixture or safe test record wherever available.
23. Test missing, malformed, stale, or unauthorized identifiers without modifying real user data.
24. Test the expected validation boundary conditions and verify the UI shows a useful message rather than silently dropping the request.
25. Test a server-side failure and confirm no false success indicator appears.
26. Test a network timeout/connection reset and verify the UI does not assume that the backend definitely failed if the outcome may be ambiguous.
27. Test loading indicators and confirm they clear on success, error, cancellation, component unmount, and every supported early return.
28. Test double-click, repeated Enter, quick toggle changes, duplicate network retries, and stale component state for unintended duplicate actions.
29. Check race handling if the action operates on mutable status, queue positions, decisions, settings, uploads, or publishing state.
30. Check that stale/out-of-order responses cannot overwrite a newer state. Use request cancellation, version checks, or existing conventions where needed and approved.
31. Check the response status is translated to the correct UI state, including pending/in-progress, completed, partial failure, failed, cancelled, and conflict states where applicable.
32. Check whether optimistic UI is used. If so, ensure rollback or reconciliation occurs when the backend rejects the change.
33. Check whether the changed state should survive page refresh/reopen; if yes, reload and compare the visible state to the backend-authoritative result.
34. Check whether the state is shared with other pages/components. Trigger the action and inspect every relevant surface for stale data.
35. Check that filters, sorting, selection, pagination, tabs, and the current detail item behave correctly after the operation changes data.
36. Check behavior when the list is empty, the API returns null/partial optional data, a media asset is missing, or a provider is temporarily unavailable.
37. Check timezones, timestamps, duration units, percentages, byte sizes, numeric formatting, and enum labels against backend semantics.
38. Check no credential, OAuth token, API key, signed URL, or private user payload is exposed in visible UI, ordinary logs, test output, or screenshots.
39. Check that test-mode fallbacks or synthetic fixtures can only be activated by the repository-defined trusted test context, never by user-controlled substring or arbitrary request fields.
40. Check the action does not add, restore, expose, or invoke caption/subtitle features. Internal transcription may remain for approved analysis and metadata purposes.
41. Check the action does not route to Ollama or require Ollama environment variables. Preserve approved cloud-hosted models even if their names contain Llama.
42. Check the operation cannot accidentally publish to a source/monitoring channel instead of an explicitly configured destination.
43. Where an action creates a job/task, verify the persisted job ID is retained and Celery dispatch occurs only at the intended transition.
44. Where an action updates a task, verify the backend state transition is valid, durable, and visible on subsequent reads.
45. Where an action creates or deletes a file, verify storage path containment, ownership, retention policy, and cleanup behavior using isolated files only.
46. Where a control selects a layout, verify the selected ID maps to a supported renderer option rather than only changing the visual highlight.
47. Where a control shows a layout thumbnail, verify the reference asset exists in the production build, has the correct accessible text, and truthfully represents output composition.
48. Where the component displays progress, verify it is sourced from authoritative progress/status fields and cannot display completion before the task completes.
49. Where the component refreshes/polls, verify intervals, overlap, cooldown, backoff, and unmount cleanup against the actual code contract.
50. Where external providers are involved, test mocked/sandbox cases first and ensure no accidental external side effect is triggered by an ordinary test.
51. For the private YouTube acceptance upload, do not use this component test to generate another upload. The one real upload is centrally orchestrated and idempotently gated under the master framework.
52. Inspect the relevant unit/component test and add a regression test for each repaired defect where test infrastructure permits.
53. Run the smallest test covering this component first and record the exact command and actual exit result.
54. Run the relevant API/backend integration test where it can be proven safe and isolated.
55. Run the relevant browser/E2E test if available; do not describe static source inspection as a browser test.
56. Collect actual request/response evidence with secrets redacted. Link to the logs or test output that substantiate the result.
57. Compare the user-visible message/status with the actual backend response and persisted state.
58. Conduct Pass A by tracing requirements to implementation and successful tests.
59. Conduct Pass B independently using an alternate path such as persisted state, route registration, event log, task state, rendered output, refresh behavior, or a different test assertion.
60. If Pass A and Pass B disagree, investigate and document the discrepancy; do not average the results or silently pick the favorable one.
61. Classify a failure as UI defect, API contract mismatch, backend behavior defect, persistence defect, concurrency defect, configuration defect, missing test/evidence, or scope ambiguity.
62. Fix only defects within approved Phase 1–7 requirements and only through the governance process required by the freeze rules.
63. Before changing a shared API client, component, schema, backend route, or frozen domain, identify all affected pages and regression tests.
64. Keep the code change minimal and preserve pre-existing Git modifications and untracked files.
65. Never execute blanket Git reset/clean/checkout/restore commands or replace a whole file to make a small repair.
66. After a repair, rerun the failing reproduction, relevant component test, API/backend tests, and affected page regression checks.
67. Independently repeat Pass B after the repair, using evidence distinct from the original fix path where reasonably possible.
68. If the test fails, continue the diagnose/fix/retest loop within scope; if the failure requires unavailable authorization or unsafe operation, mark it blocked and continue unrelated work.
69. Do not stop at the first failed test if the cause is repairable within scope. Do not loop indefinitely if a genuine external or governance blocker exists.
70. Check that test teardown completes and does not silently mask failures; do not change global fixtures unless required and governed.
71. Confirm test DB isolation before any database mutation. Never migrate, drop, reset, or clean the operational clipforge database.
72. Confirm no test publishes an actual video except the one centralized, explicit, private acceptance upload authorized by the user.
73. Confirm no generated test file overwrites existing uploads or outputs and no cleanup task deletes user-owned media.
74. Run TypeScript and lint checks against the changed frontend where possible. Report repository-wide legacy issues separately from new introduced issues.
75. Run the production build after page/component changes and distinguish build output count from the number of user-facing pages.
76. Inspect browser console errors, failed network requests, React warnings, hydration issues, and unhandled promise rejections where browser execution is available.
77. Check responsive layout at narrow and wide viewport sizes, avoiding horizontal overflow, clipped dialogs, invisible controls, and inaccessible hover-only actions.
78. Check error messages are actionable, avoid secrets, and preserve user-entered form data where retry is expected.
79. Check the component handles loading, empty, success, partial-success, validation, unauthorized, not-found, conflict, rate-limit, server-error, and offline states as applicable.
80. Check that stale UI cache does not outlive a mutation. Invalidate/refetch only the relevant query/state according to the existing architecture.
81. Check a successful response has not been mistaken for semantic success when the backend returns a task ID with pending execution.
82. Check task completion is awaited or polled appropriately and the user can identify pending versus completed processing.
83. Check external provider errors propagate to a truthful status rather than being caught and converted into fabricated success.
84. Check any retry operation cannot create duplicate jobs, settings writes, uploads, publications, or cleanup operations.
85. Check the component has no hidden coupling to unapproved Phase 8 watermark branding or unsupported layouts.
86. Cross-reference actual behavior with `PHASE_TRACKER.md`, the relevant approved prompt, and the actual backend route/service. Do not assume draft/archived prompts are mandatory scope.
87. Check related documentation only if it is directly affected by the verified implementation; preserve historical audit evidence.
88. Update the component dossier with actual file paths, symbols, endpoint, backend behavior, test commands, Pass A evidence and Pass B evidence.
89. If a required operation is not present in the current UI, mark it absent and verify whether the approved specification requires it; do not silently invent UI.
90. If a required capability is absent, identify the exact implementation/API/test gap and fix it only when inside approved scope and governance permits.
91. Before any edit, record targeted Git status/diff; after edits, verify unrelated working-tree changes and untracked assets remain untouched.
92. Do not make changes beyond approved Phase 1–7 scope; Phase 8 watermark branding remains deferred unless separately authorized.
93. If this component offers a layout choice, require a real local reference thumbnail for every supported option and verify the output renderer matches it.
94. If this component participates in monitoring/publishing, check destination identity and state synchronization, and obey the central private-upload gate; do not create a second real upload.
95. Never expose secrets, run destructive database operations, publish public/unlisted test videos, or delete user media while verifying this component.
96. Perform Pass A: independently map every acceptance criterion to implementation and test evidence. Record exact paths, symbols, commands and actual results.
97. Perform Pass B independently using alternate evidence; explicitly confirm, contradict or leave uncertain every material Pass A claim.
98. Repair eligible defects and repeat the complete relevant test loop; if governance or safety blocks a fix, record the exact blocker and continue independent work.
99. Final acceptance for `DASH-04`: every mandatory control in Job progress and status display must have a real handler/contract, verified backend result, correct UI synchronization, passing relevant test, and independent Pass A/Pass B evidence.
100. Return a concise per-control matrix, exact files changed, tests and results, unresolved issues, and final component verdict. Do not declare PASS when evidence is missing.


---

### DASH-05 — Per-job action buttons (retry/cancel/open/details where present)

**Primary files to discover:** Enumerate the actual actions on Dashboard job rows/details  
**Component focus:** Each discovered row action; only actions actually present  
**Acceptance focus:** Verify each action separately end to end, correct job ID and endpoint, permission checks, idempotency, confirmations for destructive actions, backend transition, UI refresh, and behavior on failure or already-terminal jobs.

Copy this complete prompt into the autonomous execution context for this component. Do not execute it in isolation from the master framework.

**100-step component prompt:**
1. Act as the autonomous owner of Per-job action buttons (retry/cancel/open/details where present). Work only on the actual component discovered in the current checkout, not on an assumed or reconstructed UI.
2. Inspect Enumerate the actual actions on Dashboard job rows/details; follow imports and references to identify the real source files, tests, route and backend dependencies.
3. Component inventory: Each discovered row action; only actions actually present. Discover the full list from the current UI and source. The list above is a focus guide, not permission to invent missing controls.
4. Acceptance focus: Verify each action separately end to end, correct job ID and endpoint, permission checks, idempotency, confirmations for destructive actions, backend transition, UI refresh, and behavior on failure or already-terminal jobs.
5. Create or update dossier ID `DASH-05` and link this component to its authoritative Phase/C-series acceptance criterion without redefining phase numbering.
6. Capture current behavior first: record the visible state, control labels, current handler, API call, server response, persisted state and known failure behavior.
7. List every individual button, input, dropdown, link, tab, selector, icon action, modal action and keyboard action in this component; give each a stable child control ID.
8. For every control, specify one positive test, one invalid/error test, one repeated-action/idempotency test where relevant, and one refresh/persistence or cross-page sync test where relevant.
9. Trace every mutation from browser event to API client, backend route, service, persistence/task/external provider and the final returned UI state.
10. Record the precise success assertion and the objective failure condition before changing code; never count a cosmetic animation or toast as proof of backend success.
11. Begin by opening the actual component, its parent, child components, types, API-client methods, and tests; do not trust a previous report without checking the current checkout.
12. List the exact visible controls that belong to this component, including icon-only buttons, links styled as buttons, keyboard shortcuts, toggles, dropdown options, modal actions, and any hidden action revealed by state.
13. For each control, state the requirement and observable success condition before testing it; map each requirement to the approved roadmap item without changing canonical phase numbers.
14. Check whether the control is intentionally non-interactive. If so, it must be semantically non-interactive and cannot imply that an unavailable action will occur.
15. Check accessible name, label/description, role, focusability, keyboard activation, disabled state, focus order, and whether focus returns appropriately after a dialog closes.
16. Trace the real event handler. Reject empty callbacks, console-only callbacks, hard-coded results, no-op links, timer-only simulation, and UI-only state mutation for backend operations.
17. Locate the corresponding API-client method and verify HTTP method, route path, body/query parameters, identifiers, headers/auth, response type, status-code handling, and timeout behavior.
18. Confirm that the route exists in the current backend application and is included under the actual router prefix. Do not infer endpoint existence from a frontend URL string.
19. Inspect backend validation, authorization, ownership checks, service calls, transaction boundaries, queue/task dispatch, and error mapping for the operation.
20. Identify the authoritative persisted record or external response that proves success. Do not use only a toast, button animation, or HTTP 200 as proof of the intended side effect.
21. Check that the frontend consumes the real response and maps returned identifiers/state correctly. Detect hard-coded status strings and mismatched field names.
22. Test the normal successful action using an isolated fixture or safe test record wherever available.
23. Test missing, malformed, stale, or unauthorized identifiers without modifying real user data.
24. Test the expected validation boundary conditions and verify the UI shows a useful message rather than silently dropping the request.
25. Test a server-side failure and confirm no false success indicator appears.
26. Test a network timeout/connection reset and verify the UI does not assume that the backend definitely failed if the outcome may be ambiguous.
27. Test loading indicators and confirm they clear on success, error, cancellation, component unmount, and every supported early return.
28. Test double-click, repeated Enter, quick toggle changes, duplicate network retries, and stale component state for unintended duplicate actions.
29. Check race handling if the action operates on mutable status, queue positions, decisions, settings, uploads, or publishing state.
30. Check that stale/out-of-order responses cannot overwrite a newer state. Use request cancellation, version checks, or existing conventions where needed and approved.
31. Check the response status is translated to the correct UI state, including pending/in-progress, completed, partial failure, failed, cancelled, and conflict states where applicable.
32. Check whether optimistic UI is used. If so, ensure rollback or reconciliation occurs when the backend rejects the change.
33. Check whether the changed state should survive page refresh/reopen; if yes, reload and compare the visible state to the backend-authoritative result.
34. Check whether the state is shared with other pages/components. Trigger the action and inspect every relevant surface for stale data.
35. Check that filters, sorting, selection, pagination, tabs, and the current detail item behave correctly after the operation changes data.
36. Check behavior when the list is empty, the API returns null/partial optional data, a media asset is missing, or a provider is temporarily unavailable.
37. Check timezones, timestamps, duration units, percentages, byte sizes, numeric formatting, and enum labels against backend semantics.
38. Check no credential, OAuth token, API key, signed URL, or private user payload is exposed in visible UI, ordinary logs, test output, or screenshots.
39. Check that test-mode fallbacks or synthetic fixtures can only be activated by the repository-defined trusted test context, never by user-controlled substring or arbitrary request fields.
40. Check the action does not add, restore, expose, or invoke caption/subtitle features. Internal transcription may remain for approved analysis and metadata purposes.
41. Check the action does not route to Ollama or require Ollama environment variables. Preserve approved cloud-hosted models even if their names contain Llama.
42. Check the operation cannot accidentally publish to a source/monitoring channel instead of an explicitly configured destination.
43. Where an action creates a job/task, verify the persisted job ID is retained and Celery dispatch occurs only at the intended transition.
44. Where an action updates a task, verify the backend state transition is valid, durable, and visible on subsequent reads.
45. Where an action creates or deletes a file, verify storage path containment, ownership, retention policy, and cleanup behavior using isolated files only.
46. Where a control selects a layout, verify the selected ID maps to a supported renderer option rather than only changing the visual highlight.
47. Where a control shows a layout thumbnail, verify the reference asset exists in the production build, has the correct accessible text, and truthfully represents output composition.
48. Where the component displays progress, verify it is sourced from authoritative progress/status fields and cannot display completion before the task completes.
49. Where the component refreshes/polls, verify intervals, overlap, cooldown, backoff, and unmount cleanup against the actual code contract.
50. Where external providers are involved, test mocked/sandbox cases first and ensure no accidental external side effect is triggered by an ordinary test.
51. For the private YouTube acceptance upload, do not use this component test to generate another upload. The one real upload is centrally orchestrated and idempotently gated under the master framework.
52. Inspect the relevant unit/component test and add a regression test for each repaired defect where test infrastructure permits.
53. Run the smallest test covering this component first and record the exact command and actual exit result.
54. Run the relevant API/backend integration test where it can be proven safe and isolated.
55. Run the relevant browser/E2E test if available; do not describe static source inspection as a browser test.
56. Collect actual request/response evidence with secrets redacted. Link to the logs or test output that substantiate the result.
57. Compare the user-visible message/status with the actual backend response and persisted state.
58. Conduct Pass A by tracing requirements to implementation and successful tests.
59. Conduct Pass B independently using an alternate path such as persisted state, route registration, event log, task state, rendered output, refresh behavior, or a different test assertion.
60. If Pass A and Pass B disagree, investigate and document the discrepancy; do not average the results or silently pick the favorable one.
61. Classify a failure as UI defect, API contract mismatch, backend behavior defect, persistence defect, concurrency defect, configuration defect, missing test/evidence, or scope ambiguity.
62. Fix only defects within approved Phase 1–7 requirements and only through the governance process required by the freeze rules.
63. Before changing a shared API client, component, schema, backend route, or frozen domain, identify all affected pages and regression tests.
64. Keep the code change minimal and preserve pre-existing Git modifications and untracked files.
65. Never execute blanket Git reset/clean/checkout/restore commands or replace a whole file to make a small repair.
66. After a repair, rerun the failing reproduction, relevant component test, API/backend tests, and affected page regression checks.
67. Independently repeat Pass B after the repair, using evidence distinct from the original fix path where reasonably possible.
68. If the test fails, continue the diagnose/fix/retest loop within scope; if the failure requires unavailable authorization or unsafe operation, mark it blocked and continue unrelated work.
69. Do not stop at the first failed test if the cause is repairable within scope. Do not loop indefinitely if a genuine external or governance blocker exists.
70. Check that test teardown completes and does not silently mask failures; do not change global fixtures unless required and governed.
71. Confirm test DB isolation before any database mutation. Never migrate, drop, reset, or clean the operational clipforge database.
72. Confirm no test publishes an actual video except the one centralized, explicit, private acceptance upload authorized by the user.
73. Confirm no generated test file overwrites existing uploads or outputs and no cleanup task deletes user-owned media.
74. Run TypeScript and lint checks against the changed frontend where possible. Report repository-wide legacy issues separately from new introduced issues.
75. Run the production build after page/component changes and distinguish build output count from the number of user-facing pages.
76. Inspect browser console errors, failed network requests, React warnings, hydration issues, and unhandled promise rejections where browser execution is available.
77. Check responsive layout at narrow and wide viewport sizes, avoiding horizontal overflow, clipped dialogs, invisible controls, and inaccessible hover-only actions.
78. Check error messages are actionable, avoid secrets, and preserve user-entered form data where retry is expected.
79. Check the component handles loading, empty, success, partial-success, validation, unauthorized, not-found, conflict, rate-limit, server-error, and offline states as applicable.
80. Check that stale UI cache does not outlive a mutation. Invalidate/refetch only the relevant query/state according to the existing architecture.
81. Check a successful response has not been mistaken for semantic success when the backend returns a task ID with pending execution.
82. Check task completion is awaited or polled appropriately and the user can identify pending versus completed processing.
83. Check external provider errors propagate to a truthful status rather than being caught and converted into fabricated success.
84. Check any retry operation cannot create duplicate jobs, settings writes, uploads, publications, or cleanup operations.
85. Check the component has no hidden coupling to unapproved Phase 8 watermark branding or unsupported layouts.
86. Cross-reference actual behavior with `PHASE_TRACKER.md`, the relevant approved prompt, and the actual backend route/service. Do not assume draft/archived prompts are mandatory scope.
87. Check related documentation only if it is directly affected by the verified implementation; preserve historical audit evidence.
88. Update the component dossier with actual file paths, symbols, endpoint, backend behavior, test commands, Pass A evidence and Pass B evidence.
89. If a required operation is not present in the current UI, mark it absent and verify whether the approved specification requires it; do not silently invent UI.
90. If a required capability is absent, identify the exact implementation/API/test gap and fix it only when inside approved scope and governance permits.
91. Before any edit, record targeted Git status/diff; after edits, verify unrelated working-tree changes and untracked assets remain untouched.
92. Do not make changes beyond approved Phase 1–7 scope; Phase 8 watermark branding remains deferred unless separately authorized.
93. If this component offers a layout choice, require a real local reference thumbnail for every supported option and verify the output renderer matches it.
94. If this component participates in monitoring/publishing, check destination identity and state synchronization, and obey the central private-upload gate; do not create a second real upload.
95. Never expose secrets, run destructive database operations, publish public/unlisted test videos, or delete user media while verifying this component.
96. Perform Pass A: independently map every acceptance criterion to implementation and test evidence. Record exact paths, symbols, commands and actual results.
97. Perform Pass B independently using alternate evidence; explicitly confirm, contradict or leave uncertain every material Pass A claim.
98. Repair eligible defects and repeat the complete relevant test loop; if governance or safety blocks a fix, record the exact blocker and continue independent work.
99. Final acceptance for `DASH-05`: every mandatory control in Per-job action buttons (retry/cancel/open/details where present) must have a real handler/contract, verified backend result, correct UI synchronization, passing relevant test, and independent Pass A/Pass B evidence.
100. Return a concise per-control matrix, exact files changed, tests and results, unresolved issues, and final component verdict. Do not declare PASS when evidence is missing.


---


## Page 2 — Automation / Monitoring (`/automation`)

### Page orchestration prompt

1. Work on Page 2 — Automation / Monitoring (`/automation`) as a page-level integration owner, using the master framework and all child prompts in this section.

2. Discover every actual child component and every interactive control from the current source, accessibility tree, and rendered page where browser inspection is available.

3. Create a route inventory and map each control to the relevant API endpoint, backend route/service, persistence or task path, and acceptance criterion.

4. Execute every child component prompt listed below, then inspect interactions between sibling components, shared state and cross-page navigation.

5. Test loading, empty, success, validation, auth failure, conflict, network failure, server failure and retry states applicable to the page.

6. Use component and integration tests. Run browser/E2E checks where available; label missing browser evidence as NOT VERIFIED.

7. Verify that every layout selection displays a real reference image and that selected layout ID reaches the correct renderer and appears in actual rendered output.

8. For monitoring, trace channel selection → poll → candidate discovery → decision → processing dispatch → persisted job progress → publishing destination → status result.

9. For Publish, verify normal mocked paths first and coordinate with the single central private YouTube upload gate; never create additional live uploads from component tests.

10. After all child components pass, test page-wide interactions, reloading, navigation away/back, shared API cache invalidation, stale response handling and component cleanup.

11. Perform a distinct Page Pass B using alternate evidence and record each finding against Page Pass A.

12. Fix authorized defects and rerun impacted tests until every mandatory page criterion passes or a specific governance/safety/external dependency blocks it.

13. Do not implement the proposed Phase 8 watermark feature. Keep the approved Phase 1–7 scope boundary.

14. Finish with a control-level matrix, endpoint coverage map, actual tests/results, files changed, evidence for both passes and unresolved blockers.


### Independent component prompts — each contains 100 required steps

### AUTO-01 — Monitoring channel selector and monitor/refresh controls

**Primary files to discover:** frontend/app/automation/page.tsx and related monitoring/channel APIs  
**Component focus:** Source-channel selection, monitor toggle, manual poll/refresh, loading and polling indicators  
**Acceptance focus:** Verify the correct authorized source channel is selected, persisted monitoring configuration is loaded, poll/refresh calls the real endpoint, duplicate requests are prevented, cooldown/rate-limit rules are honored, and channel state matches the backend.

Copy this complete prompt into the autonomous execution context for this component. Do not execute it in isolation from the master framework.

**100-step component prompt:**
1. Act as the autonomous owner of Monitoring channel selector and monitor/refresh controls. Work only on the actual component discovered in the current checkout, not on an assumed or reconstructed UI.
2. Inspect frontend/app/automation/page.tsx and related monitoring/channel APIs; follow imports and references to identify the real source files, tests, route and backend dependencies.
3. Component inventory: Source-channel selection, monitor toggle, manual poll/refresh, loading and polling indicators. Discover the full list from the current UI and source. The list above is a focus guide, not permission to invent missing controls.
4. Acceptance focus: Verify the correct authorized source channel is selected, persisted monitoring configuration is loaded, poll/refresh calls the real endpoint, duplicate requests are prevented, cooldown/rate-limit rules are honored, and channel state matches the backend.
5. Create or update dossier ID `AUTO-01` and link this component to its authoritative Phase/C-series acceptance criterion without redefining phase numbering.
6. Capture current behavior first: record the visible state, control labels, current handler, API call, server response, persisted state and known failure behavior.
7. List every individual button, input, dropdown, link, tab, selector, icon action, modal action and keyboard action in this component; give each a stable child control ID.
8. For every control, specify one positive test, one invalid/error test, one repeated-action/idempotency test where relevant, and one refresh/persistence or cross-page sync test where relevant.
9. Trace every mutation from browser event to API client, backend route, service, persistence/task/external provider and the final returned UI state.
10. Record the precise success assertion and the objective failure condition before changing code; never count a cosmetic animation or toast as proof of backend success.
11. Begin by opening the actual component, its parent, child components, types, API-client methods, and tests; do not trust a previous report without checking the current checkout.
12. List the exact visible controls that belong to this component, including icon-only buttons, links styled as buttons, keyboard shortcuts, toggles, dropdown options, modal actions, and any hidden action revealed by state.
13. For each control, state the requirement and observable success condition before testing it; map each requirement to the approved roadmap item without changing canonical phase numbers.
14. Check whether the control is intentionally non-interactive. If so, it must be semantically non-interactive and cannot imply that an unavailable action will occur.
15. Check accessible name, label/description, role, focusability, keyboard activation, disabled state, focus order, and whether focus returns appropriately after a dialog closes.
16. Trace the real event handler. Reject empty callbacks, console-only callbacks, hard-coded results, no-op links, timer-only simulation, and UI-only state mutation for backend operations.
17. Locate the corresponding API-client method and verify HTTP method, route path, body/query parameters, identifiers, headers/auth, response type, status-code handling, and timeout behavior.
18. Confirm that the route exists in the current backend application and is included under the actual router prefix. Do not infer endpoint existence from a frontend URL string.
19. Inspect backend validation, authorization, ownership checks, service calls, transaction boundaries, queue/task dispatch, and error mapping for the operation.
20. Identify the authoritative persisted record or external response that proves success. Do not use only a toast, button animation, or HTTP 200 as proof of the intended side effect.
21. Check that the frontend consumes the real response and maps returned identifiers/state correctly. Detect hard-coded status strings and mismatched field names.
22. Test the normal successful action using an isolated fixture or safe test record wherever available.
23. Test missing, malformed, stale, or unauthorized identifiers without modifying real user data.
24. Test the expected validation boundary conditions and verify the UI shows a useful message rather than silently dropping the request.
25. Test a server-side failure and confirm no false success indicator appears.
26. Test a network timeout/connection reset and verify the UI does not assume that the backend definitely failed if the outcome may be ambiguous.
27. Test loading indicators and confirm they clear on success, error, cancellation, component unmount, and every supported early return.
28. Test double-click, repeated Enter, quick toggle changes, duplicate network retries, and stale component state for unintended duplicate actions.
29. Check race handling if the action operates on mutable status, queue positions, decisions, settings, uploads, or publishing state.
30. Check that stale/out-of-order responses cannot overwrite a newer state. Use request cancellation, version checks, or existing conventions where needed and approved.
31. Check the response status is translated to the correct UI state, including pending/in-progress, completed, partial failure, failed, cancelled, and conflict states where applicable.
32. Check whether optimistic UI is used. If so, ensure rollback or reconciliation occurs when the backend rejects the change.
33. Check whether the changed state should survive page refresh/reopen; if yes, reload and compare the visible state to the backend-authoritative result.
34. Check whether the state is shared with other pages/components. Trigger the action and inspect every relevant surface for stale data.
35. Check that filters, sorting, selection, pagination, tabs, and the current detail item behave correctly after the operation changes data.
36. Check behavior when the list is empty, the API returns null/partial optional data, a media asset is missing, or a provider is temporarily unavailable.
37. Check timezones, timestamps, duration units, percentages, byte sizes, numeric formatting, and enum labels against backend semantics.
38. Check no credential, OAuth token, API key, signed URL, or private user payload is exposed in visible UI, ordinary logs, test output, or screenshots.
39. Check that test-mode fallbacks or synthetic fixtures can only be activated by the repository-defined trusted test context, never by user-controlled substring or arbitrary request fields.
40. Check the action does not add, restore, expose, or invoke caption/subtitle features. Internal transcription may remain for approved analysis and metadata purposes.
41. Check the action does not route to Ollama or require Ollama environment variables. Preserve approved cloud-hosted models even if their names contain Llama.
42. Check the operation cannot accidentally publish to a source/monitoring channel instead of an explicitly configured destination.
43. Where an action creates a job/task, verify the persisted job ID is retained and Celery dispatch occurs only at the intended transition.
44. Where an action updates a task, verify the backend state transition is valid, durable, and visible on subsequent reads.
45. Where an action creates or deletes a file, verify storage path containment, ownership, retention policy, and cleanup behavior using isolated files only.
46. Where a control selects a layout, verify the selected ID maps to a supported renderer option rather than only changing the visual highlight.
47. Where a control shows a layout thumbnail, verify the reference asset exists in the production build, has the correct accessible text, and truthfully represents output composition.
48. Where the component displays progress, verify it is sourced from authoritative progress/status fields and cannot display completion before the task completes.
49. Where the component refreshes/polls, verify intervals, overlap, cooldown, backoff, and unmount cleanup against the actual code contract.
50. Where external providers are involved, test mocked/sandbox cases first and ensure no accidental external side effect is triggered by an ordinary test.
51. For the private YouTube acceptance upload, do not use this component test to generate another upload. The one real upload is centrally orchestrated and idempotently gated under the master framework.
52. Inspect the relevant unit/component test and add a regression test for each repaired defect where test infrastructure permits.
53. Run the smallest test covering this component first and record the exact command and actual exit result.
54. Run the relevant API/backend integration test where it can be proven safe and isolated.
55. Run the relevant browser/E2E test if available; do not describe static source inspection as a browser test.
56. Collect actual request/response evidence with secrets redacted. Link to the logs or test output that substantiate the result.
57. Compare the user-visible message/status with the actual backend response and persisted state.
58. Conduct Pass A by tracing requirements to implementation and successful tests.
59. Conduct Pass B independently using an alternate path such as persisted state, route registration, event log, task state, rendered output, refresh behavior, or a different test assertion.
60. If Pass A and Pass B disagree, investigate and document the discrepancy; do not average the results or silently pick the favorable one.
61. Classify a failure as UI defect, API contract mismatch, backend behavior defect, persistence defect, concurrency defect, configuration defect, missing test/evidence, or scope ambiguity.
62. Fix only defects within approved Phase 1–7 requirements and only through the governance process required by the freeze rules.
63. Before changing a shared API client, component, schema, backend route, or frozen domain, identify all affected pages and regression tests.
64. Keep the code change minimal and preserve pre-existing Git modifications and untracked files.
65. Never execute blanket Git reset/clean/checkout/restore commands or replace a whole file to make a small repair.
66. After a repair, rerun the failing reproduction, relevant component test, API/backend tests, and affected page regression checks.
67. Independently repeat Pass B after the repair, using evidence distinct from the original fix path where reasonably possible.
68. If the test fails, continue the diagnose/fix/retest loop within scope; if the failure requires unavailable authorization or unsafe operation, mark it blocked and continue unrelated work.
69. Do not stop at the first failed test if the cause is repairable within scope. Do not loop indefinitely if a genuine external or governance blocker exists.
70. Check that test teardown completes and does not silently mask failures; do not change global fixtures unless required and governed.
71. Confirm test DB isolation before any database mutation. Never migrate, drop, reset, or clean the operational clipforge database.
72. Confirm no test publishes an actual video except the one centralized, explicit, private acceptance upload authorized by the user.
73. Confirm no generated test file overwrites existing uploads or outputs and no cleanup task deletes user-owned media.
74. Run TypeScript and lint checks against the changed frontend where possible. Report repository-wide legacy issues separately from new introduced issues.
75. Run the production build after page/component changes and distinguish build output count from the number of user-facing pages.
76. Inspect browser console errors, failed network requests, React warnings, hydration issues, and unhandled promise rejections where browser execution is available.
77. Check responsive layout at narrow and wide viewport sizes, avoiding horizontal overflow, clipped dialogs, invisible controls, and inaccessible hover-only actions.
78. Check error messages are actionable, avoid secrets, and preserve user-entered form data where retry is expected.
79. Check the component handles loading, empty, success, partial-success, validation, unauthorized, not-found, conflict, rate-limit, server-error, and offline states as applicable.
80. Check that stale UI cache does not outlive a mutation. Invalidate/refetch only the relevant query/state according to the existing architecture.
81. Check a successful response has not been mistaken for semantic success when the backend returns a task ID with pending execution.
82. Check task completion is awaited or polled appropriately and the user can identify pending versus completed processing.
83. Check external provider errors propagate to a truthful status rather than being caught and converted into fabricated success.
84. Check any retry operation cannot create duplicate jobs, settings writes, uploads, publications, or cleanup operations.
85. Check the component has no hidden coupling to unapproved Phase 8 watermark branding or unsupported layouts.
86. Cross-reference actual behavior with `PHASE_TRACKER.md`, the relevant approved prompt, and the actual backend route/service. Do not assume draft/archived prompts are mandatory scope.
87. Check related documentation only if it is directly affected by the verified implementation; preserve historical audit evidence.
88. Update the component dossier with actual file paths, symbols, endpoint, backend behavior, test commands, Pass A evidence and Pass B evidence.
89. If a required operation is not present in the current UI, mark it absent and verify whether the approved specification requires it; do not silently invent UI.
90. If a required capability is absent, identify the exact implementation/API/test gap and fix it only when inside approved scope and governance permits.
91. Before any edit, record targeted Git status/diff; after edits, verify unrelated working-tree changes and untracked assets remain untouched.
92. Do not make changes beyond approved Phase 1–7 scope; Phase 8 watermark branding remains deferred unless separately authorized.
93. If this component offers a layout choice, require a real local reference thumbnail for every supported option and verify the output renderer matches it.
94. If this component participates in monitoring/publishing, check destination identity and state synchronization, and obey the central private-upload gate; do not create a second real upload.
95. Never expose secrets, run destructive database operations, publish public/unlisted test videos, or delete user media while verifying this component.
96. Perform Pass A: independently map every acceptance criterion to implementation and test evidence. Record exact paths, symbols, commands and actual results.
97. Perform Pass B independently using alternate evidence; explicitly confirm, contradict or leave uncertain every material Pass A claim.
98. Repair eligible defects and repeat the complete relevant test loop; if governance or safety blocks a fix, record the exact blocker and continue independent work.
99. Final acceptance for `AUTO-01`: every mandatory control in Monitoring channel selector and monitor/refresh controls must have a real handler/contract, verified backend result, correct UI synchronization, passing relevant test, and independent Pass A/Pass B evidence.
100. Return a concise per-control matrix, exact files changed, tests and results, unresolved issues, and final component verdict. Do not declare PASS when evidence is missing.


---

### AUTO-02 — Video candidate queue, search and filters

**Primary files to discover:** Automation candidate list and actual discovery/decision endpoints  
**Component focus:** Candidate cards/rows, URL/title/date/channel details, search/filter/empty/error state  
**Acceptance focus:** Verify candidates originate from backend data, stable IDs are used, search/filter is accurate, duplicate candidates are suppressed, selected IDs remain correct, and a newly discovered candidate becomes visible without stale state.

Copy this complete prompt into the autonomous execution context for this component. Do not execute it in isolation from the master framework.

**100-step component prompt:**
1. Act as the autonomous owner of Video candidate queue, search and filters. Work only on the actual component discovered in the current checkout, not on an assumed or reconstructed UI.
2. Inspect Automation candidate list and actual discovery/decision endpoints; follow imports and references to identify the real source files, tests, route and backend dependencies.
3. Component inventory: Candidate cards/rows, URL/title/date/channel details, search/filter/empty/error state. Discover the full list from the current UI and source. The list above is a focus guide, not permission to invent missing controls.
4. Acceptance focus: Verify candidates originate from backend data, stable IDs are used, search/filter is accurate, duplicate candidates are suppressed, selected IDs remain correct, and a newly discovered candidate becomes visible without stale state.
5. Create or update dossier ID `AUTO-02` and link this component to its authoritative Phase/C-series acceptance criterion without redefining phase numbering.
6. Capture current behavior first: record the visible state, control labels, current handler, API call, server response, persisted state and known failure behavior.
7. List every individual button, input, dropdown, link, tab, selector, icon action, modal action and keyboard action in this component; give each a stable child control ID.
8. For every control, specify one positive test, one invalid/error test, one repeated-action/idempotency test where relevant, and one refresh/persistence or cross-page sync test where relevant.
9. Trace every mutation from browser event to API client, backend route, service, persistence/task/external provider and the final returned UI state.
10. Record the precise success assertion and the objective failure condition before changing code; never count a cosmetic animation or toast as proof of backend success.
11. Begin by opening the actual component, its parent, child components, types, API-client methods, and tests; do not trust a previous report without checking the current checkout.
12. List the exact visible controls that belong to this component, including icon-only buttons, links styled as buttons, keyboard shortcuts, toggles, dropdown options, modal actions, and any hidden action revealed by state.
13. For each control, state the requirement and observable success condition before testing it; map each requirement to the approved roadmap item without changing canonical phase numbers.
14. Check whether the control is intentionally non-interactive. If so, it must be semantically non-interactive and cannot imply that an unavailable action will occur.
15. Check accessible name, label/description, role, focusability, keyboard activation, disabled state, focus order, and whether focus returns appropriately after a dialog closes.
16. Trace the real event handler. Reject empty callbacks, console-only callbacks, hard-coded results, no-op links, timer-only simulation, and UI-only state mutation for backend operations.
17. Locate the corresponding API-client method and verify HTTP method, route path, body/query parameters, identifiers, headers/auth, response type, status-code handling, and timeout behavior.
18. Confirm that the route exists in the current backend application and is included under the actual router prefix. Do not infer endpoint existence from a frontend URL string.
19. Inspect backend validation, authorization, ownership checks, service calls, transaction boundaries, queue/task dispatch, and error mapping for the operation.
20. Identify the authoritative persisted record or external response that proves success. Do not use only a toast, button animation, or HTTP 200 as proof of the intended side effect.
21. Check that the frontend consumes the real response and maps returned identifiers/state correctly. Detect hard-coded status strings and mismatched field names.
22. Test the normal successful action using an isolated fixture or safe test record wherever available.
23. Test missing, malformed, stale, or unauthorized identifiers without modifying real user data.
24. Test the expected validation boundary conditions and verify the UI shows a useful message rather than silently dropping the request.
25. Test a server-side failure and confirm no false success indicator appears.
26. Test a network timeout/connection reset and verify the UI does not assume that the backend definitely failed if the outcome may be ambiguous.
27. Test loading indicators and confirm they clear on success, error, cancellation, component unmount, and every supported early return.
28. Test double-click, repeated Enter, quick toggle changes, duplicate network retries, and stale component state for unintended duplicate actions.
29. Check race handling if the action operates on mutable status, queue positions, decisions, settings, uploads, or publishing state.
30. Check that stale/out-of-order responses cannot overwrite a newer state. Use request cancellation, version checks, or existing conventions where needed and approved.
31. Check the response status is translated to the correct UI state, including pending/in-progress, completed, partial failure, failed, cancelled, and conflict states where applicable.
32. Check whether optimistic UI is used. If so, ensure rollback or reconciliation occurs when the backend rejects the change.
33. Check whether the changed state should survive page refresh/reopen; if yes, reload and compare the visible state to the backend-authoritative result.
34. Check whether the state is shared with other pages/components. Trigger the action and inspect every relevant surface for stale data.
35. Check that filters, sorting, selection, pagination, tabs, and the current detail item behave correctly after the operation changes data.
36. Check behavior when the list is empty, the API returns null/partial optional data, a media asset is missing, or a provider is temporarily unavailable.
37. Check timezones, timestamps, duration units, percentages, byte sizes, numeric formatting, and enum labels against backend semantics.
38. Check no credential, OAuth token, API key, signed URL, or private user payload is exposed in visible UI, ordinary logs, test output, or screenshots.
39. Check that test-mode fallbacks or synthetic fixtures can only be activated by the repository-defined trusted test context, never by user-controlled substring or arbitrary request fields.
40. Check the action does not add, restore, expose, or invoke caption/subtitle features. Internal transcription may remain for approved analysis and metadata purposes.
41. Check the action does not route to Ollama or require Ollama environment variables. Preserve approved cloud-hosted models even if their names contain Llama.
42. Check the operation cannot accidentally publish to a source/monitoring channel instead of an explicitly configured destination.
43. Where an action creates a job/task, verify the persisted job ID is retained and Celery dispatch occurs only at the intended transition.
44. Where an action updates a task, verify the backend state transition is valid, durable, and visible on subsequent reads.
45. Where an action creates or deletes a file, verify storage path containment, ownership, retention policy, and cleanup behavior using isolated files only.
46. Where a control selects a layout, verify the selected ID maps to a supported renderer option rather than only changing the visual highlight.
47. Where a control shows a layout thumbnail, verify the reference asset exists in the production build, has the correct accessible text, and truthfully represents output composition.
48. Where the component displays progress, verify it is sourced from authoritative progress/status fields and cannot display completion before the task completes.
49. Where the component refreshes/polls, verify intervals, overlap, cooldown, backoff, and unmount cleanup against the actual code contract.
50. Where external providers are involved, test mocked/sandbox cases first and ensure no accidental external side effect is triggered by an ordinary test.
51. For the private YouTube acceptance upload, do not use this component test to generate another upload. The one real upload is centrally orchestrated and idempotently gated under the master framework.
52. Inspect the relevant unit/component test and add a regression test for each repaired defect where test infrastructure permits.
53. Run the smallest test covering this component first and record the exact command and actual exit result.
54. Run the relevant API/backend integration test where it can be proven safe and isolated.
55. Run the relevant browser/E2E test if available; do not describe static source inspection as a browser test.
56. Collect actual request/response evidence with secrets redacted. Link to the logs or test output that substantiate the result.
57. Compare the user-visible message/status with the actual backend response and persisted state.
58. Conduct Pass A by tracing requirements to implementation and successful tests.
59. Conduct Pass B independently using an alternate path such as persisted state, route registration, event log, task state, rendered output, refresh behavior, or a different test assertion.
60. If Pass A and Pass B disagree, investigate and document the discrepancy; do not average the results or silently pick the favorable one.
61. Classify a failure as UI defect, API contract mismatch, backend behavior defect, persistence defect, concurrency defect, configuration defect, missing test/evidence, or scope ambiguity.
62. Fix only defects within approved Phase 1–7 requirements and only through the governance process required by the freeze rules.
63. Before changing a shared API client, component, schema, backend route, or frozen domain, identify all affected pages and regression tests.
64. Keep the code change minimal and preserve pre-existing Git modifications and untracked files.
65. Never execute blanket Git reset/clean/checkout/restore commands or replace a whole file to make a small repair.
66. After a repair, rerun the failing reproduction, relevant component test, API/backend tests, and affected page regression checks.
67. Independently repeat Pass B after the repair, using evidence distinct from the original fix path where reasonably possible.
68. If the test fails, continue the diagnose/fix/retest loop within scope; if the failure requires unavailable authorization or unsafe operation, mark it blocked and continue unrelated work.
69. Do not stop at the first failed test if the cause is repairable within scope. Do not loop indefinitely if a genuine external or governance blocker exists.
70. Check that test teardown completes and does not silently mask failures; do not change global fixtures unless required and governed.
71. Confirm test DB isolation before any database mutation. Never migrate, drop, reset, or clean the operational clipforge database.
72. Confirm no test publishes an actual video except the one centralized, explicit, private acceptance upload authorized by the user.
73. Confirm no generated test file overwrites existing uploads or outputs and no cleanup task deletes user-owned media.
74. Run TypeScript and lint checks against the changed frontend where possible. Report repository-wide legacy issues separately from new introduced issues.
75. Run the production build after page/component changes and distinguish build output count from the number of user-facing pages.
76. Inspect browser console errors, failed network requests, React warnings, hydration issues, and unhandled promise rejections where browser execution is available.
77. Check responsive layout at narrow and wide viewport sizes, avoiding horizontal overflow, clipped dialogs, invisible controls, and inaccessible hover-only actions.
78. Check error messages are actionable, avoid secrets, and preserve user-entered form data where retry is expected.
79. Check the component handles loading, empty, success, partial-success, validation, unauthorized, not-found, conflict, rate-limit, server-error, and offline states as applicable.
80. Check that stale UI cache does not outlive a mutation. Invalidate/refetch only the relevant query/state according to the existing architecture.
81. Check a successful response has not been mistaken for semantic success when the backend returns a task ID with pending execution.
82. Check task completion is awaited or polled appropriately and the user can identify pending versus completed processing.
83. Check external provider errors propagate to a truthful status rather than being caught and converted into fabricated success.
84. Check any retry operation cannot create duplicate jobs, settings writes, uploads, publications, or cleanup operations.
85. Check the component has no hidden coupling to unapproved Phase 8 watermark branding or unsupported layouts.
86. Cross-reference actual behavior with `PHASE_TRACKER.md`, the relevant approved prompt, and the actual backend route/service. Do not assume draft/archived prompts are mandatory scope.
87. Check related documentation only if it is directly affected by the verified implementation; preserve historical audit evidence.
88. Update the component dossier with actual file paths, symbols, endpoint, backend behavior, test commands, Pass A evidence and Pass B evidence.
89. If a required operation is not present in the current UI, mark it absent and verify whether the approved specification requires it; do not silently invent UI.
90. If a required capability is absent, identify the exact implementation/API/test gap and fix it only when inside approved scope and governance permits.
91. Before any edit, record targeted Git status/diff; after edits, verify unrelated working-tree changes and untracked assets remain untouched.
92. Do not make changes beyond approved Phase 1–7 scope; Phase 8 watermark branding remains deferred unless separately authorized.
93. If this component offers a layout choice, require a real local reference thumbnail for every supported option and verify the output renderer matches it.
94. If this component participates in monitoring/publishing, check destination identity and state synchronization, and obey the central private-upload gate; do not create a second real upload.
95. Never expose secrets, run destructive database operations, publish public/unlisted test videos, or delete user media while verifying this component.
96. Perform Pass A: independently map every acceptance criterion to implementation and test evidence. Record exact paths, symbols, commands and actual results.
97. Perform Pass B independently using alternate evidence; explicitly confirm, contradict or leave uncertain every material Pass A claim.
98. Repair eligible defects and repeat the complete relevant test loop; if governance or safety blocks a fix, record the exact blocker and continue independent work.
99. Final acceptance for `AUTO-02`: every mandatory control in Video candidate queue, search and filters must have a real handler/contract, verified backend result, correct UI synchronization, passing relevant test, and independent Pass A/Pass B evidence.
100. Return a concise per-control matrix, exact files changed, tests and results, unresolved issues, and final component verdict. Do not declare PASS when evidence is missing.


---

### AUTO-03 — Approve/reject/defer and batch decision actions

**Primary files to discover:** Automation decision controls and race-guarded APIs  
**Component focus:** Individual and bulk decision buttons, selection grouping, confirmation and conflict messages  
**Acceptance focus:** Verify each decision updates the correct video/channel decision, expected status/lease token is sent, conflicts return useful feedback, repeated actions are safe, UI selection is preserved on network failure, and database/UI state agree after reload.

Copy this complete prompt into the autonomous execution context for this component. Do not execute it in isolation from the master framework.

**100-step component prompt:**
1. Act as the autonomous owner of Approve/reject/defer and batch decision actions. Work only on the actual component discovered in the current checkout, not on an assumed or reconstructed UI.
2. Inspect Automation decision controls and race-guarded APIs; follow imports and references to identify the real source files, tests, route and backend dependencies.
3. Component inventory: Individual and bulk decision buttons, selection grouping, confirmation and conflict messages. Discover the full list from the current UI and source. The list above is a focus guide, not permission to invent missing controls.
4. Acceptance focus: Verify each decision updates the correct video/channel decision, expected status/lease token is sent, conflicts return useful feedback, repeated actions are safe, UI selection is preserved on network failure, and database/UI state agree after reload.
5. Create or update dossier ID `AUTO-03` and link this component to its authoritative Phase/C-series acceptance criterion without redefining phase numbering.
6. Capture current behavior first: record the visible state, control labels, current handler, API call, server response, persisted state and known failure behavior.
7. List every individual button, input, dropdown, link, tab, selector, icon action, modal action and keyboard action in this component; give each a stable child control ID.
8. For every control, specify one positive test, one invalid/error test, one repeated-action/idempotency test where relevant, and one refresh/persistence or cross-page sync test where relevant.
9. Trace every mutation from browser event to API client, backend route, service, persistence/task/external provider and the final returned UI state.
10. Record the precise success assertion and the objective failure condition before changing code; never count a cosmetic animation or toast as proof of backend success.
11. Begin by opening the actual component, its parent, child components, types, API-client methods, and tests; do not trust a previous report without checking the current checkout.
12. List the exact visible controls that belong to this component, including icon-only buttons, links styled as buttons, keyboard shortcuts, toggles, dropdown options, modal actions, and any hidden action revealed by state.
13. For each control, state the requirement and observable success condition before testing it; map each requirement to the approved roadmap item without changing canonical phase numbers.
14. Check whether the control is intentionally non-interactive. If so, it must be semantically non-interactive and cannot imply that an unavailable action will occur.
15. Check accessible name, label/description, role, focusability, keyboard activation, disabled state, focus order, and whether focus returns appropriately after a dialog closes.
16. Trace the real event handler. Reject empty callbacks, console-only callbacks, hard-coded results, no-op links, timer-only simulation, and UI-only state mutation for backend operations.
17. Locate the corresponding API-client method and verify HTTP method, route path, body/query parameters, identifiers, headers/auth, response type, status-code handling, and timeout behavior.
18. Confirm that the route exists in the current backend application and is included under the actual router prefix. Do not infer endpoint existence from a frontend URL string.
19. Inspect backend validation, authorization, ownership checks, service calls, transaction boundaries, queue/task dispatch, and error mapping for the operation.
20. Identify the authoritative persisted record or external response that proves success. Do not use only a toast, button animation, or HTTP 200 as proof of the intended side effect.
21. Check that the frontend consumes the real response and maps returned identifiers/state correctly. Detect hard-coded status strings and mismatched field names.
22. Test the normal successful action using an isolated fixture or safe test record wherever available.
23. Test missing, malformed, stale, or unauthorized identifiers without modifying real user data.
24. Test the expected validation boundary conditions and verify the UI shows a useful message rather than silently dropping the request.
25. Test a server-side failure and confirm no false success indicator appears.
26. Test a network timeout/connection reset and verify the UI does not assume that the backend definitely failed if the outcome may be ambiguous.
27. Test loading indicators and confirm they clear on success, error, cancellation, component unmount, and every supported early return.
28. Test double-click, repeated Enter, quick toggle changes, duplicate network retries, and stale component state for unintended duplicate actions.
29. Check race handling if the action operates on mutable status, queue positions, decisions, settings, uploads, or publishing state.
30. Check that stale/out-of-order responses cannot overwrite a newer state. Use request cancellation, version checks, or existing conventions where needed and approved.
31. Check the response status is translated to the correct UI state, including pending/in-progress, completed, partial failure, failed, cancelled, and conflict states where applicable.
32. Check whether optimistic UI is used. If so, ensure rollback or reconciliation occurs when the backend rejects the change.
33. Check whether the changed state should survive page refresh/reopen; if yes, reload and compare the visible state to the backend-authoritative result.
34. Check whether the state is shared with other pages/components. Trigger the action and inspect every relevant surface for stale data.
35. Check that filters, sorting, selection, pagination, tabs, and the current detail item behave correctly after the operation changes data.
36. Check behavior when the list is empty, the API returns null/partial optional data, a media asset is missing, or a provider is temporarily unavailable.
37. Check timezones, timestamps, duration units, percentages, byte sizes, numeric formatting, and enum labels against backend semantics.
38. Check no credential, OAuth token, API key, signed URL, or private user payload is exposed in visible UI, ordinary logs, test output, or screenshots.
39. Check that test-mode fallbacks or synthetic fixtures can only be activated by the repository-defined trusted test context, never by user-controlled substring or arbitrary request fields.
40. Check the action does not add, restore, expose, or invoke caption/subtitle features. Internal transcription may remain for approved analysis and metadata purposes.
41. Check the action does not route to Ollama or require Ollama environment variables. Preserve approved cloud-hosted models even if their names contain Llama.
42. Check the operation cannot accidentally publish to a source/monitoring channel instead of an explicitly configured destination.
43. Where an action creates a job/task, verify the persisted job ID is retained and Celery dispatch occurs only at the intended transition.
44. Where an action updates a task, verify the backend state transition is valid, durable, and visible on subsequent reads.
45. Where an action creates or deletes a file, verify storage path containment, ownership, retention policy, and cleanup behavior using isolated files only.
46. Where a control selects a layout, verify the selected ID maps to a supported renderer option rather than only changing the visual highlight.
47. Where a control shows a layout thumbnail, verify the reference asset exists in the production build, has the correct accessible text, and truthfully represents output composition.
48. Where the component displays progress, verify it is sourced from authoritative progress/status fields and cannot display completion before the task completes.
49. Where the component refreshes/polls, verify intervals, overlap, cooldown, backoff, and unmount cleanup against the actual code contract.
50. Where external providers are involved, test mocked/sandbox cases first and ensure no accidental external side effect is triggered by an ordinary test.
51. For the private YouTube acceptance upload, do not use this component test to generate another upload. The one real upload is centrally orchestrated and idempotently gated under the master framework.
52. Inspect the relevant unit/component test and add a regression test for each repaired defect where test infrastructure permits.
53. Run the smallest test covering this component first and record the exact command and actual exit result.
54. Run the relevant API/backend integration test where it can be proven safe and isolated.
55. Run the relevant browser/E2E test if available; do not describe static source inspection as a browser test.
56. Collect actual request/response evidence with secrets redacted. Link to the logs or test output that substantiate the result.
57. Compare the user-visible message/status with the actual backend response and persisted state.
58. Conduct Pass A by tracing requirements to implementation and successful tests.
59. Conduct Pass B independently using an alternate path such as persisted state, route registration, event log, task state, rendered output, refresh behavior, or a different test assertion.
60. If Pass A and Pass B disagree, investigate and document the discrepancy; do not average the results or silently pick the favorable one.
61. Classify a failure as UI defect, API contract mismatch, backend behavior defect, persistence defect, concurrency defect, configuration defect, missing test/evidence, or scope ambiguity.
62. Fix only defects within approved Phase 1–7 requirements and only through the governance process required by the freeze rules.
63. Before changing a shared API client, component, schema, backend route, or frozen domain, identify all affected pages and regression tests.
64. Keep the code change minimal and preserve pre-existing Git modifications and untracked files.
65. Never execute blanket Git reset/clean/checkout/restore commands or replace a whole file to make a small repair.
66. After a repair, rerun the failing reproduction, relevant component test, API/backend tests, and affected page regression checks.
67. Independently repeat Pass B after the repair, using evidence distinct from the original fix path where reasonably possible.
68. If the test fails, continue the diagnose/fix/retest loop within scope; if the failure requires unavailable authorization or unsafe operation, mark it blocked and continue unrelated work.
69. Do not stop at the first failed test if the cause is repairable within scope. Do not loop indefinitely if a genuine external or governance blocker exists.
70. Check that test teardown completes and does not silently mask failures; do not change global fixtures unless required and governed.
71. Confirm test DB isolation before any database mutation. Never migrate, drop, reset, or clean the operational clipforge database.
72. Confirm no test publishes an actual video except the one centralized, explicit, private acceptance upload authorized by the user.
73. Confirm no generated test file overwrites existing uploads or outputs and no cleanup task deletes user-owned media.
74. Run TypeScript and lint checks against the changed frontend where possible. Report repository-wide legacy issues separately from new introduced issues.
75. Run the production build after page/component changes and distinguish build output count from the number of user-facing pages.
76. Inspect browser console errors, failed network requests, React warnings, hydration issues, and unhandled promise rejections where browser execution is available.
77. Check responsive layout at narrow and wide viewport sizes, avoiding horizontal overflow, clipped dialogs, invisible controls, and inaccessible hover-only actions.
78. Check error messages are actionable, avoid secrets, and preserve user-entered form data where retry is expected.
79. Check the component handles loading, empty, success, partial-success, validation, unauthorized, not-found, conflict, rate-limit, server-error, and offline states as applicable.
80. Check that stale UI cache does not outlive a mutation. Invalidate/refetch only the relevant query/state according to the existing architecture.
81. Check a successful response has not been mistaken for semantic success when the backend returns a task ID with pending execution.
82. Check task completion is awaited or polled appropriately and the user can identify pending versus completed processing.
83. Check external provider errors propagate to a truthful status rather than being caught and converted into fabricated success.
84. Check any retry operation cannot create duplicate jobs, settings writes, uploads, publications, or cleanup operations.
85. Check the component has no hidden coupling to unapproved Phase 8 watermark branding or unsupported layouts.
86. Cross-reference actual behavior with `PHASE_TRACKER.md`, the relevant approved prompt, and the actual backend route/service. Do not assume draft/archived prompts are mandatory scope.
87. Check related documentation only if it is directly affected by the verified implementation; preserve historical audit evidence.
88. Update the component dossier with actual file paths, symbols, endpoint, backend behavior, test commands, Pass A evidence and Pass B evidence.
89. If a required operation is not present in the current UI, mark it absent and verify whether the approved specification requires it; do not silently invent UI.
90. If a required capability is absent, identify the exact implementation/API/test gap and fix it only when inside approved scope and governance permits.
91. Before any edit, record targeted Git status/diff; after edits, verify unrelated working-tree changes and untracked assets remain untouched.
92. Do not make changes beyond approved Phase 1–7 scope; Phase 8 watermark branding remains deferred unless separately authorized.
93. If this component offers a layout choice, require a real local reference thumbnail for every supported option and verify the output renderer matches it.
94. If this component participates in monitoring/publishing, check destination identity and state synchronization, and obey the central private-upload gate; do not create a second real upload.
95. Never expose secrets, run destructive database operations, publish public/unlisted test videos, or delete user media while verifying this component.
96. Perform Pass A: independently map every acceptance criterion to implementation and test evidence. Record exact paths, symbols, commands and actual results.
97. Perform Pass B independently using alternate evidence; explicitly confirm, contradict or leave uncertain every material Pass A claim.
98. Repair eligible defects and repeat the complete relevant test loop; if governance or safety blocks a fix, record the exact blocker and continue independent work.
99. Final acceptance for `AUTO-03`: every mandatory control in Approve/reject/defer and batch decision actions must have a real handler/contract, verified backend result, correct UI synchronization, passing relevant test, and independent Pass A/Pass B evidence.
100. Return a concise per-control matrix, exact files changed, tests and results, unresolved issues, and final component verdict. Do not declare PASS when evidence is missing.


---

### AUTO-04 — Start processing and Dashboard handoff

**Primary files to discover:** Automation Start Processing control and orchestration/Celery dispatch path  
**Component focus:** Single and any approved batch processing triggers  
**Acceptance focus:** Verify the request creates exactly one intended job/chord, correct IDs are passed, job progress is persisted, task/worker execution begins, failures are surfaced, and navigation to Dashboard shows the same persisted job.

Copy this complete prompt into the autonomous execution context for this component. Do not execute it in isolation from the master framework.

**100-step component prompt:**
1. Act as the autonomous owner of Start processing and Dashboard handoff. Work only on the actual component discovered in the current checkout, not on an assumed or reconstructed UI.
2. Inspect Automation Start Processing control and orchestration/Celery dispatch path; follow imports and references to identify the real source files, tests, route and backend dependencies.
3. Component inventory: Single and any approved batch processing triggers. Discover the full list from the current UI and source. The list above is a focus guide, not permission to invent missing controls.
4. Acceptance focus: Verify the request creates exactly one intended job/chord, correct IDs are passed, job progress is persisted, task/worker execution begins, failures are surfaced, and navigation to Dashboard shows the same persisted job.
5. Create or update dossier ID `AUTO-04` and link this component to its authoritative Phase/C-series acceptance criterion without redefining phase numbering.
6. Capture current behavior first: record the visible state, control labels, current handler, API call, server response, persisted state and known failure behavior.
7. List every individual button, input, dropdown, link, tab, selector, icon action, modal action and keyboard action in this component; give each a stable child control ID.
8. For every control, specify one positive test, one invalid/error test, one repeated-action/idempotency test where relevant, and one refresh/persistence or cross-page sync test where relevant.
9. Trace every mutation from browser event to API client, backend route, service, persistence/task/external provider and the final returned UI state.
10. Record the precise success assertion and the objective failure condition before changing code; never count a cosmetic animation or toast as proof of backend success.
11. Begin by opening the actual component, its parent, child components, types, API-client methods, and tests; do not trust a previous report without checking the current checkout.
12. List the exact visible controls that belong to this component, including icon-only buttons, links styled as buttons, keyboard shortcuts, toggles, dropdown options, modal actions, and any hidden action revealed by state.
13. For each control, state the requirement and observable success condition before testing it; map each requirement to the approved roadmap item without changing canonical phase numbers.
14. Check whether the control is intentionally non-interactive. If so, it must be semantically non-interactive and cannot imply that an unavailable action will occur.
15. Check accessible name, label/description, role, focusability, keyboard activation, disabled state, focus order, and whether focus returns appropriately after a dialog closes.
16. Trace the real event handler. Reject empty callbacks, console-only callbacks, hard-coded results, no-op links, timer-only simulation, and UI-only state mutation for backend operations.
17. Locate the corresponding API-client method and verify HTTP method, route path, body/query parameters, identifiers, headers/auth, response type, status-code handling, and timeout behavior.
18. Confirm that the route exists in the current backend application and is included under the actual router prefix. Do not infer endpoint existence from a frontend URL string.
19. Inspect backend validation, authorization, ownership checks, service calls, transaction boundaries, queue/task dispatch, and error mapping for the operation.
20. Identify the authoritative persisted record or external response that proves success. Do not use only a toast, button animation, or HTTP 200 as proof of the intended side effect.
21. Check that the frontend consumes the real response and maps returned identifiers/state correctly. Detect hard-coded status strings and mismatched field names.
22. Test the normal successful action using an isolated fixture or safe test record wherever available.
23. Test missing, malformed, stale, or unauthorized identifiers without modifying real user data.
24. Test the expected validation boundary conditions and verify the UI shows a useful message rather than silently dropping the request.
25. Test a server-side failure and confirm no false success indicator appears.
26. Test a network timeout/connection reset and verify the UI does not assume that the backend definitely failed if the outcome may be ambiguous.
27. Test loading indicators and confirm they clear on success, error, cancellation, component unmount, and every supported early return.
28. Test double-click, repeated Enter, quick toggle changes, duplicate network retries, and stale component state for unintended duplicate actions.
29. Check race handling if the action operates on mutable status, queue positions, decisions, settings, uploads, or publishing state.
30. Check that stale/out-of-order responses cannot overwrite a newer state. Use request cancellation, version checks, or existing conventions where needed and approved.
31. Check the response status is translated to the correct UI state, including pending/in-progress, completed, partial failure, failed, cancelled, and conflict states where applicable.
32. Check whether optimistic UI is used. If so, ensure rollback or reconciliation occurs when the backend rejects the change.
33. Check whether the changed state should survive page refresh/reopen; if yes, reload and compare the visible state to the backend-authoritative result.
34. Check whether the state is shared with other pages/components. Trigger the action and inspect every relevant surface for stale data.
35. Check that filters, sorting, selection, pagination, tabs, and the current detail item behave correctly after the operation changes data.
36. Check behavior when the list is empty, the API returns null/partial optional data, a media asset is missing, or a provider is temporarily unavailable.
37. Check timezones, timestamps, duration units, percentages, byte sizes, numeric formatting, and enum labels against backend semantics.
38. Check no credential, OAuth token, API key, signed URL, or private user payload is exposed in visible UI, ordinary logs, test output, or screenshots.
39. Check that test-mode fallbacks or synthetic fixtures can only be activated by the repository-defined trusted test context, never by user-controlled substring or arbitrary request fields.
40. Check the action does not add, restore, expose, or invoke caption/subtitle features. Internal transcription may remain for approved analysis and metadata purposes.
41. Check the action does not route to Ollama or require Ollama environment variables. Preserve approved cloud-hosted models even if their names contain Llama.
42. Check the operation cannot accidentally publish to a source/monitoring channel instead of an explicitly configured destination.
43. Where an action creates a job/task, verify the persisted job ID is retained and Celery dispatch occurs only at the intended transition.
44. Where an action updates a task, verify the backend state transition is valid, durable, and visible on subsequent reads.
45. Where an action creates or deletes a file, verify storage path containment, ownership, retention policy, and cleanup behavior using isolated files only.
46. Where a control selects a layout, verify the selected ID maps to a supported renderer option rather than only changing the visual highlight.
47. Where a control shows a layout thumbnail, verify the reference asset exists in the production build, has the correct accessible text, and truthfully represents output composition.
48. Where the component displays progress, verify it is sourced from authoritative progress/status fields and cannot display completion before the task completes.
49. Where the component refreshes/polls, verify intervals, overlap, cooldown, backoff, and unmount cleanup against the actual code contract.
50. Where external providers are involved, test mocked/sandbox cases first and ensure no accidental external side effect is triggered by an ordinary test.
51. For the private YouTube acceptance upload, do not use this component test to generate another upload. The one real upload is centrally orchestrated and idempotently gated under the master framework.
52. Inspect the relevant unit/component test and add a regression test for each repaired defect where test infrastructure permits.
53. Run the smallest test covering this component first and record the exact command and actual exit result.
54. Run the relevant API/backend integration test where it can be proven safe and isolated.
55. Run the relevant browser/E2E test if available; do not describe static source inspection as a browser test.
56. Collect actual request/response evidence with secrets redacted. Link to the logs or test output that substantiate the result.
57. Compare the user-visible message/status with the actual backend response and persisted state.
58. Conduct Pass A by tracing requirements to implementation and successful tests.
59. Conduct Pass B independently using an alternate path such as persisted state, route registration, event log, task state, rendered output, refresh behavior, or a different test assertion.
60. If Pass A and Pass B disagree, investigate and document the discrepancy; do not average the results or silently pick the favorable one.
61. Classify a failure as UI defect, API contract mismatch, backend behavior defect, persistence defect, concurrency defect, configuration defect, missing test/evidence, or scope ambiguity.
62. Fix only defects within approved Phase 1–7 requirements and only through the governance process required by the freeze rules.
63. Before changing a shared API client, component, schema, backend route, or frozen domain, identify all affected pages and regression tests.
64. Keep the code change minimal and preserve pre-existing Git modifications and untracked files.
65. Never execute blanket Git reset/clean/checkout/restore commands or replace a whole file to make a small repair.
66. After a repair, rerun the failing reproduction, relevant component test, API/backend tests, and affected page regression checks.
67. Independently repeat Pass B after the repair, using evidence distinct from the original fix path where reasonably possible.
68. If the test fails, continue the diagnose/fix/retest loop within scope; if the failure requires unavailable authorization or unsafe operation, mark it blocked and continue unrelated work.
69. Do not stop at the first failed test if the cause is repairable within scope. Do not loop indefinitely if a genuine external or governance blocker exists.
70. Check that test teardown completes and does not silently mask failures; do not change global fixtures unless required and governed.
71. Confirm test DB isolation before any database mutation. Never migrate, drop, reset, or clean the operational clipforge database.
72. Confirm no test publishes an actual video except the one centralized, explicit, private acceptance upload authorized by the user.
73. Confirm no generated test file overwrites existing uploads or outputs and no cleanup task deletes user-owned media.
74. Run TypeScript and lint checks against the changed frontend where possible. Report repository-wide legacy issues separately from new introduced issues.
75. Run the production build after page/component changes and distinguish build output count from the number of user-facing pages.
76. Inspect browser console errors, failed network requests, React warnings, hydration issues, and unhandled promise rejections where browser execution is available.
77. Check responsive layout at narrow and wide viewport sizes, avoiding horizontal overflow, clipped dialogs, invisible controls, and inaccessible hover-only actions.
78. Check error messages are actionable, avoid secrets, and preserve user-entered form data where retry is expected.
79. Check the component handles loading, empty, success, partial-success, validation, unauthorized, not-found, conflict, rate-limit, server-error, and offline states as applicable.
80. Check that stale UI cache does not outlive a mutation. Invalidate/refetch only the relevant query/state according to the existing architecture.
81. Check a successful response has not been mistaken for semantic success when the backend returns a task ID with pending execution.
82. Check task completion is awaited or polled appropriately and the user can identify pending versus completed processing.
83. Check external provider errors propagate to a truthful status rather than being caught and converted into fabricated success.
84. Check any retry operation cannot create duplicate jobs, settings writes, uploads, publications, or cleanup operations.
85. Check the component has no hidden coupling to unapproved Phase 8 watermark branding or unsupported layouts.
86. Cross-reference actual behavior with `PHASE_TRACKER.md`, the relevant approved prompt, and the actual backend route/service. Do not assume draft/archived prompts are mandatory scope.
87. Check related documentation only if it is directly affected by the verified implementation; preserve historical audit evidence.
88. Update the component dossier with actual file paths, symbols, endpoint, backend behavior, test commands, Pass A evidence and Pass B evidence.
89. If a required operation is not present in the current UI, mark it absent and verify whether the approved specification requires it; do not silently invent UI.
90. If a required capability is absent, identify the exact implementation/API/test gap and fix it only when inside approved scope and governance permits.
91. Before any edit, record targeted Git status/diff; after edits, verify unrelated working-tree changes and untracked assets remain untouched.
92. Do not make changes beyond approved Phase 1–7 scope; Phase 8 watermark branding remains deferred unless separately authorized.
93. If this component offers a layout choice, require a real local reference thumbnail for every supported option and verify the output renderer matches it.
94. If this component participates in monitoring/publishing, check destination identity and state synchronization, and obey the central private-upload gate; do not create a second real upload.
95. Never expose secrets, run destructive database operations, publish public/unlisted test videos, or delete user media while verifying this component.
96. Perform Pass A: independently map every acceptance criterion to implementation and test evidence. Record exact paths, symbols, commands and actual results.
97. Perform Pass B independently using alternate evidence; explicitly confirm, contradict or leave uncertain every material Pass A claim.
98. Repair eligible defects and repeat the complete relevant test loop; if governance or safety blocks a fix, record the exact blocker and continue independent work.
99. Final acceptance for `AUTO-04`: every mandatory control in Start processing and Dashboard handoff must have a real handler/contract, verified backend result, correct UI synchronization, passing relevant test, and independent Pass A/Pass B evidence.
100. Return a concise per-control matrix, exact files changed, tests and results, unresolved issues, and final component verdict. Do not declare PASS when evidence is missing.


---

### AUTO-05 — Layout gallery, layout selector and reference thumbnails

**Primary files to discover:** Actual layout gallery and layout_engine.py/reframe_engine.py mappings  
**Component focus:** Every currently exposed approved layout option and its image/thumbnail  
**Acceptance focus:** Inventory every renderer-supported option; provide a truthful visual reference image for each; verify accessibility label, preview, selection ID, save/submit request, backend renderer mapping, rendered output, selection persistence, unsupported-option fallback, and visual-regression evidence.

Copy this complete prompt into the autonomous execution context for this component. Do not execute it in isolation from the master framework.

**100-step component prompt:**
1. Act as the autonomous owner of Layout gallery, layout selector and reference thumbnails. Work only on the actual component discovered in the current checkout, not on an assumed or reconstructed UI.
2. Inspect Actual layout gallery and layout_engine.py/reframe_engine.py mappings; follow imports and references to identify the real source files, tests, route and backend dependencies.
3. Component inventory: Every currently exposed approved layout option and its image/thumbnail. Discover the full list from the current UI and source. The list above is a focus guide, not permission to invent missing controls.
4. Acceptance focus: Inventory every renderer-supported option; provide a truthful visual reference image for each; verify accessibility label, preview, selection ID, save/submit request, backend renderer mapping, rendered output, selection persistence, unsupported-option fallback, and visual-regression evidence.
5. Create or update dossier ID `AUTO-05` and link this component to its authoritative Phase/C-series acceptance criterion without redefining phase numbering.
6. Capture current behavior first: record the visible state, control labels, current handler, API call, server response, persisted state and known failure behavior.
7. List every individual button, input, dropdown, link, tab, selector, icon action, modal action and keyboard action in this component; give each a stable child control ID.
8. For every control, specify one positive test, one invalid/error test, one repeated-action/idempotency test where relevant, and one refresh/persistence or cross-page sync test where relevant.
9. Trace every mutation from browser event to API client, backend route, service, persistence/task/external provider and the final returned UI state.
10. Record the precise success assertion and the objective failure condition before changing code; never count a cosmetic animation or toast as proof of backend success.
11. Begin by opening the actual component, its parent, child components, types, API-client methods, and tests; do not trust a previous report without checking the current checkout.
12. List the exact visible controls that belong to this component, including icon-only buttons, links styled as buttons, keyboard shortcuts, toggles, dropdown options, modal actions, and any hidden action revealed by state.
13. For each control, state the requirement and observable success condition before testing it; map each requirement to the approved roadmap item without changing canonical phase numbers.
14. Check whether the control is intentionally non-interactive. If so, it must be semantically non-interactive and cannot imply that an unavailable action will occur.
15. Check accessible name, label/description, role, focusability, keyboard activation, disabled state, focus order, and whether focus returns appropriately after a dialog closes.
16. Trace the real event handler. Reject empty callbacks, console-only callbacks, hard-coded results, no-op links, timer-only simulation, and UI-only state mutation for backend operations.
17. Locate the corresponding API-client method and verify HTTP method, route path, body/query parameters, identifiers, headers/auth, response type, status-code handling, and timeout behavior.
18. Confirm that the route exists in the current backend application and is included under the actual router prefix. Do not infer endpoint existence from a frontend URL string.
19. Inspect backend validation, authorization, ownership checks, service calls, transaction boundaries, queue/task dispatch, and error mapping for the operation.
20. Identify the authoritative persisted record or external response that proves success. Do not use only a toast, button animation, or HTTP 200 as proof of the intended side effect.
21. Check that the frontend consumes the real response and maps returned identifiers/state correctly. Detect hard-coded status strings and mismatched field names.
22. Test the normal successful action using an isolated fixture or safe test record wherever available.
23. Test missing, malformed, stale, or unauthorized identifiers without modifying real user data.
24. Test the expected validation boundary conditions and verify the UI shows a useful message rather than silently dropping the request.
25. Test a server-side failure and confirm no false success indicator appears.
26. Test a network timeout/connection reset and verify the UI does not assume that the backend definitely failed if the outcome may be ambiguous.
27. Test loading indicators and confirm they clear on success, error, cancellation, component unmount, and every supported early return.
28. Test double-click, repeated Enter, quick toggle changes, duplicate network retries, and stale component state for unintended duplicate actions.
29. Check race handling if the action operates on mutable status, queue positions, decisions, settings, uploads, or publishing state.
30. Check that stale/out-of-order responses cannot overwrite a newer state. Use request cancellation, version checks, or existing conventions where needed and approved.
31. Check the response status is translated to the correct UI state, including pending/in-progress, completed, partial failure, failed, cancelled, and conflict states where applicable.
32. Check whether optimistic UI is used. If so, ensure rollback or reconciliation occurs when the backend rejects the change.
33. Check whether the changed state should survive page refresh/reopen; if yes, reload and compare the visible state to the backend-authoritative result.
34. Check whether the state is shared with other pages/components. Trigger the action and inspect every relevant surface for stale data.
35. Check that filters, sorting, selection, pagination, tabs, and the current detail item behave correctly after the operation changes data.
36. Check behavior when the list is empty, the API returns null/partial optional data, a media asset is missing, or a provider is temporarily unavailable.
37. Check timezones, timestamps, duration units, percentages, byte sizes, numeric formatting, and enum labels against backend semantics.
38. Check no credential, OAuth token, API key, signed URL, or private user payload is exposed in visible UI, ordinary logs, test output, or screenshots.
39. Check that test-mode fallbacks or synthetic fixtures can only be activated by the repository-defined trusted test context, never by user-controlled substring or arbitrary request fields.
40. Check the action does not add, restore, expose, or invoke caption/subtitle features. Internal transcription may remain for approved analysis and metadata purposes.
41. Check the action does not route to Ollama or require Ollama environment variables. Preserve approved cloud-hosted models even if their names contain Llama.
42. Check the operation cannot accidentally publish to a source/monitoring channel instead of an explicitly configured destination.
43. Where an action creates a job/task, verify the persisted job ID is retained and Celery dispatch occurs only at the intended transition.
44. Where an action updates a task, verify the backend state transition is valid, durable, and visible on subsequent reads.
45. Where an action creates or deletes a file, verify storage path containment, ownership, retention policy, and cleanup behavior using isolated files only.
46. Where a control selects a layout, verify the selected ID maps to a supported renderer option rather than only changing the visual highlight.
47. Where a control shows a layout thumbnail, verify the reference asset exists in the production build, has the correct accessible text, and truthfully represents output composition.
48. Where the component displays progress, verify it is sourced from authoritative progress/status fields and cannot display completion before the task completes.
49. Where the component refreshes/polls, verify intervals, overlap, cooldown, backoff, and unmount cleanup against the actual code contract.
50. Where external providers are involved, test mocked/sandbox cases first and ensure no accidental external side effect is triggered by an ordinary test.
51. For the private YouTube acceptance upload, do not use this component test to generate another upload. The one real upload is centrally orchestrated and idempotently gated under the master framework.
52. Inspect the relevant unit/component test and add a regression test for each repaired defect where test infrastructure permits.
53. Run the smallest test covering this component first and record the exact command and actual exit result.
54. Run the relevant API/backend integration test where it can be proven safe and isolated.
55. Run the relevant browser/E2E test if available; do not describe static source inspection as a browser test.
56. Collect actual request/response evidence with secrets redacted. Link to the logs or test output that substantiate the result.
57. Compare the user-visible message/status with the actual backend response and persisted state.
58. Conduct Pass A by tracing requirements to implementation and successful tests.
59. Conduct Pass B independently using an alternate path such as persisted state, route registration, event log, task state, rendered output, refresh behavior, or a different test assertion.
60. If Pass A and Pass B disagree, investigate and document the discrepancy; do not average the results or silently pick the favorable one.
61. Classify a failure as UI defect, API contract mismatch, backend behavior defect, persistence defect, concurrency defect, configuration defect, missing test/evidence, or scope ambiguity.
62. Fix only defects within approved Phase 1–7 requirements and only through the governance process required by the freeze rules.
63. Before changing a shared API client, component, schema, backend route, or frozen domain, identify all affected pages and regression tests.
64. Keep the code change minimal and preserve pre-existing Git modifications and untracked files.
65. Never execute blanket Git reset/clean/checkout/restore commands or replace a whole file to make a small repair.
66. After a repair, rerun the failing reproduction, relevant component test, API/backend tests, and affected page regression checks.
67. Independently repeat Pass B after the repair, using evidence distinct from the original fix path where reasonably possible.
68. If the test fails, continue the diagnose/fix/retest loop within scope; if the failure requires unavailable authorization or unsafe operation, mark it blocked and continue unrelated work.
69. Do not stop at the first failed test if the cause is repairable within scope. Do not loop indefinitely if a genuine external or governance blocker exists.
70. Check that test teardown completes and does not silently mask failures; do not change global fixtures unless required and governed.
71. Confirm test DB isolation before any database mutation. Never migrate, drop, reset, or clean the operational clipforge database.
72. Confirm no test publishes an actual video except the one centralized, explicit, private acceptance upload authorized by the user.
73. Confirm no generated test file overwrites existing uploads or outputs and no cleanup task deletes user-owned media.
74. Run TypeScript and lint checks against the changed frontend where possible. Report repository-wide legacy issues separately from new introduced issues.
75. Run the production build after page/component changes and distinguish build output count from the number of user-facing pages.
76. Inspect browser console errors, failed network requests, React warnings, hydration issues, and unhandled promise rejections where browser execution is available.
77. Check responsive layout at narrow and wide viewport sizes, avoiding horizontal overflow, clipped dialogs, invisible controls, and inaccessible hover-only actions.
78. Check error messages are actionable, avoid secrets, and preserve user-entered form data where retry is expected.
79. Check the component handles loading, empty, success, partial-success, validation, unauthorized, not-found, conflict, rate-limit, server-error, and offline states as applicable.
80. Check that stale UI cache does not outlive a mutation. Invalidate/refetch only the relevant query/state according to the existing architecture.
81. Check a successful response has not been mistaken for semantic success when the backend returns a task ID with pending execution.
82. Check task completion is awaited or polled appropriately and the user can identify pending versus completed processing.
83. Check external provider errors propagate to a truthful status rather than being caught and converted into fabricated success.
84. Check any retry operation cannot create duplicate jobs, settings writes, uploads, publications, or cleanup operations.
85. Check the component has no hidden coupling to unapproved Phase 8 watermark branding or unsupported layouts.
86. Cross-reference actual behavior with `PHASE_TRACKER.md`, the relevant approved prompt, and the actual backend route/service. Do not assume draft/archived prompts are mandatory scope.
87. Check related documentation only if it is directly affected by the verified implementation; preserve historical audit evidence.
88. Update the component dossier with actual file paths, symbols, endpoint, backend behavior, test commands, Pass A evidence and Pass B evidence.
89. If a required operation is not present in the current UI, mark it absent and verify whether the approved specification requires it; do not silently invent UI.
90. If a required capability is absent, identify the exact implementation/API/test gap and fix it only when inside approved scope and governance permits.
91. Before any edit, record targeted Git status/diff; after edits, verify unrelated working-tree changes and untracked assets remain untouched.
92. Do not make changes beyond approved Phase 1–7 scope; Phase 8 watermark branding remains deferred unless separately authorized.
93. If this component offers a layout choice, require a real local reference thumbnail for every supported option and verify the output renderer matches it.
94. If this component participates in monitoring/publishing, check destination identity and state synchronization, and obey the central private-upload gate; do not create a second real upload.
95. Never expose secrets, run destructive database operations, publish public/unlisted test videos, or delete user media while verifying this component.
96. Perform Pass A: independently map every acceptance criterion to implementation and test evidence. Record exact paths, symbols, commands and actual results.
97. Perform Pass B independently using alternate evidence; explicitly confirm, contradict or leave uncertain every material Pass A claim.
98. Repair eligible defects and repeat the complete relevant test loop; if governance or safety blocks a fix, record the exact blocker and continue independent work.
99. Final acceptance for `AUTO-05`: every mandatory control in Layout gallery, layout selector and reference thumbnails must have a real handler/contract, verified backend result, correct UI synchronization, passing relevant test, and independent Pass A/Pass B evidence.
100. Return a concise per-control matrix, exact files changed, tests and results, unresolved issues, and final component verdict. Do not declare PASS when evidence is missing.


---


## Page 3 — Clips (`/clips`)

### Page orchestration prompt

1. Work on Page 3 — Clips (`/clips`) as a page-level integration owner, using the master framework and all child prompts in this section.

2. Discover every actual child component and every interactive control from the current source, accessibility tree, and rendered page where browser inspection is available.

3. Create a route inventory and map each control to the relevant API endpoint, backend route/service, persistence or task path, and acceptance criterion.

4. Execute every child component prompt listed below, then inspect interactions between sibling components, shared state and cross-page navigation.

5. Test loading, empty, success, validation, auth failure, conflict, network failure, server failure and retry states applicable to the page.

6. Use component and integration tests. Run browser/E2E checks where available; label missing browser evidence as NOT VERIFIED.

7. Verify that every layout selection displays a real reference image and that selected layout ID reaches the correct renderer and appears in actual rendered output.

8. For monitoring, trace channel selection → poll → candidate discovery → decision → processing dispatch → persisted job progress → publishing destination → status result.

9. For Publish, verify normal mocked paths first and coordinate with the single central private YouTube upload gate; never create additional live uploads from component tests.

10. After all child components pass, test page-wide interactions, reloading, navigation away/back, shared API cache invalidation, stale response handling and component cleanup.

11. Perform a distinct Page Pass B using alternate evidence and record each finding against Page Pass A.

12. Fix authorized defects and rerun impacted tests until every mandatory page criterion passes or a specific governance/safety/external dependency blocks it.

13. Do not implement the proposed Phase 8 watermark feature. Keep the approved Phase 1–7 scope boundary.

14. Finish with a control-level matrix, endpoint coverage map, actual tests/results, files changed, evidence for both passes and unresolved blockers.


### Independent component prompts — each contains 100 required steps

### CLIP-01 — Clips search, filters, cards and selection

**Primary files to discover:** frontend/app/clips/page.tsx and clip-list APIs  
**Component focus:** Search/input, filter/select controls, clip cards, loading/empty/error/retry states  
**Acceptance focus:** Verify correct clip list and IDs, filter and search behavior, selection consistency, pagination if present, accurate metadata/status, API errors, no false success, and state after refresh.

Copy this complete prompt into the autonomous execution context for this component. Do not execute it in isolation from the master framework.

**100-step component prompt:**
1. Act as the autonomous owner of Clips search, filters, cards and selection. Work only on the actual component discovered in the current checkout, not on an assumed or reconstructed UI.
2. Inspect frontend/app/clips/page.tsx and clip-list APIs; follow imports and references to identify the real source files, tests, route and backend dependencies.
3. Component inventory: Search/input, filter/select controls, clip cards, loading/empty/error/retry states. Discover the full list from the current UI and source. The list above is a focus guide, not permission to invent missing controls.
4. Acceptance focus: Verify correct clip list and IDs, filter and search behavior, selection consistency, pagination if present, accurate metadata/status, API errors, no false success, and state after refresh.
5. Create or update dossier ID `CLIP-01` and link this component to its authoritative Phase/C-series acceptance criterion without redefining phase numbering.
6. Capture current behavior first: record the visible state, control labels, current handler, API call, server response, persisted state and known failure behavior.
7. List every individual button, input, dropdown, link, tab, selector, icon action, modal action and keyboard action in this component; give each a stable child control ID.
8. For every control, specify one positive test, one invalid/error test, one repeated-action/idempotency test where relevant, and one refresh/persistence or cross-page sync test where relevant.
9. Trace every mutation from browser event to API client, backend route, service, persistence/task/external provider and the final returned UI state.
10. Record the precise success assertion and the objective failure condition before changing code; never count a cosmetic animation or toast as proof of backend success.
11. Begin by opening the actual component, its parent, child components, types, API-client methods, and tests; do not trust a previous report without checking the current checkout.
12. List the exact visible controls that belong to this component, including icon-only buttons, links styled as buttons, keyboard shortcuts, toggles, dropdown options, modal actions, and any hidden action revealed by state.
13. For each control, state the requirement and observable success condition before testing it; map each requirement to the approved roadmap item without changing canonical phase numbers.
14. Check whether the control is intentionally non-interactive. If so, it must be semantically non-interactive and cannot imply that an unavailable action will occur.
15. Check accessible name, label/description, role, focusability, keyboard activation, disabled state, focus order, and whether focus returns appropriately after a dialog closes.
16. Trace the real event handler. Reject empty callbacks, console-only callbacks, hard-coded results, no-op links, timer-only simulation, and UI-only state mutation for backend operations.
17. Locate the corresponding API-client method and verify HTTP method, route path, body/query parameters, identifiers, headers/auth, response type, status-code handling, and timeout behavior.
18. Confirm that the route exists in the current backend application and is included under the actual router prefix. Do not infer endpoint existence from a frontend URL string.
19. Inspect backend validation, authorization, ownership checks, service calls, transaction boundaries, queue/task dispatch, and error mapping for the operation.
20. Identify the authoritative persisted record or external response that proves success. Do not use only a toast, button animation, or HTTP 200 as proof of the intended side effect.
21. Check that the frontend consumes the real response and maps returned identifiers/state correctly. Detect hard-coded status strings and mismatched field names.
22. Test the normal successful action using an isolated fixture or safe test record wherever available.
23. Test missing, malformed, stale, or unauthorized identifiers without modifying real user data.
24. Test the expected validation boundary conditions and verify the UI shows a useful message rather than silently dropping the request.
25. Test a server-side failure and confirm no false success indicator appears.
26. Test a network timeout/connection reset and verify the UI does not assume that the backend definitely failed if the outcome may be ambiguous.
27. Test loading indicators and confirm they clear on success, error, cancellation, component unmount, and every supported early return.
28. Test double-click, repeated Enter, quick toggle changes, duplicate network retries, and stale component state for unintended duplicate actions.
29. Check race handling if the action operates on mutable status, queue positions, decisions, settings, uploads, or publishing state.
30. Check that stale/out-of-order responses cannot overwrite a newer state. Use request cancellation, version checks, or existing conventions where needed and approved.
31. Check the response status is translated to the correct UI state, including pending/in-progress, completed, partial failure, failed, cancelled, and conflict states where applicable.
32. Check whether optimistic UI is used. If so, ensure rollback or reconciliation occurs when the backend rejects the change.
33. Check whether the changed state should survive page refresh/reopen; if yes, reload and compare the visible state to the backend-authoritative result.
34. Check whether the state is shared with other pages/components. Trigger the action and inspect every relevant surface for stale data.
35. Check that filters, sorting, selection, pagination, tabs, and the current detail item behave correctly after the operation changes data.
36. Check behavior when the list is empty, the API returns null/partial optional data, a media asset is missing, or a provider is temporarily unavailable.
37. Check timezones, timestamps, duration units, percentages, byte sizes, numeric formatting, and enum labels against backend semantics.
38. Check no credential, OAuth token, API key, signed URL, or private user payload is exposed in visible UI, ordinary logs, test output, or screenshots.
39. Check that test-mode fallbacks or synthetic fixtures can only be activated by the repository-defined trusted test context, never by user-controlled substring or arbitrary request fields.
40. Check the action does not add, restore, expose, or invoke caption/subtitle features. Internal transcription may remain for approved analysis and metadata purposes.
41. Check the action does not route to Ollama or require Ollama environment variables. Preserve approved cloud-hosted models even if their names contain Llama.
42. Check the operation cannot accidentally publish to a source/monitoring channel instead of an explicitly configured destination.
43. Where an action creates a job/task, verify the persisted job ID is retained and Celery dispatch occurs only at the intended transition.
44. Where an action updates a task, verify the backend state transition is valid, durable, and visible on subsequent reads.
45. Where an action creates or deletes a file, verify storage path containment, ownership, retention policy, and cleanup behavior using isolated files only.
46. Where a control selects a layout, verify the selected ID maps to a supported renderer option rather than only changing the visual highlight.
47. Where a control shows a layout thumbnail, verify the reference asset exists in the production build, has the correct accessible text, and truthfully represents output composition.
48. Where the component displays progress, verify it is sourced from authoritative progress/status fields and cannot display completion before the task completes.
49. Where the component refreshes/polls, verify intervals, overlap, cooldown, backoff, and unmount cleanup against the actual code contract.
50. Where external providers are involved, test mocked/sandbox cases first and ensure no accidental external side effect is triggered by an ordinary test.
51. For the private YouTube acceptance upload, do not use this component test to generate another upload. The one real upload is centrally orchestrated and idempotently gated under the master framework.
52. Inspect the relevant unit/component test and add a regression test for each repaired defect where test infrastructure permits.
53. Run the smallest test covering this component first and record the exact command and actual exit result.
54. Run the relevant API/backend integration test where it can be proven safe and isolated.
55. Run the relevant browser/E2E test if available; do not describe static source inspection as a browser test.
56. Collect actual request/response evidence with secrets redacted. Link to the logs or test output that substantiate the result.
57. Compare the user-visible message/status with the actual backend response and persisted state.
58. Conduct Pass A by tracing requirements to implementation and successful tests.
59. Conduct Pass B independently using an alternate path such as persisted state, route registration, event log, task state, rendered output, refresh behavior, or a different test assertion.
60. If Pass A and Pass B disagree, investigate and document the discrepancy; do not average the results or silently pick the favorable one.
61. Classify a failure as UI defect, API contract mismatch, backend behavior defect, persistence defect, concurrency defect, configuration defect, missing test/evidence, or scope ambiguity.
62. Fix only defects within approved Phase 1–7 requirements and only through the governance process required by the freeze rules.
63. Before changing a shared API client, component, schema, backend route, or frozen domain, identify all affected pages and regression tests.
64. Keep the code change minimal and preserve pre-existing Git modifications and untracked files.
65. Never execute blanket Git reset/clean/checkout/restore commands or replace a whole file to make a small repair.
66. After a repair, rerun the failing reproduction, relevant component test, API/backend tests, and affected page regression checks.
67. Independently repeat Pass B after the repair, using evidence distinct from the original fix path where reasonably possible.
68. If the test fails, continue the diagnose/fix/retest loop within scope; if the failure requires unavailable authorization or unsafe operation, mark it blocked and continue unrelated work.
69. Do not stop at the first failed test if the cause is repairable within scope. Do not loop indefinitely if a genuine external or governance blocker exists.
70. Check that test teardown completes and does not silently mask failures; do not change global fixtures unless required and governed.
71. Confirm test DB isolation before any database mutation. Never migrate, drop, reset, or clean the operational clipforge database.
72. Confirm no test publishes an actual video except the one centralized, explicit, private acceptance upload authorized by the user.
73. Confirm no generated test file overwrites existing uploads or outputs and no cleanup task deletes user-owned media.
74. Run TypeScript and lint checks against the changed frontend where possible. Report repository-wide legacy issues separately from new introduced issues.
75. Run the production build after page/component changes and distinguish build output count from the number of user-facing pages.
76. Inspect browser console errors, failed network requests, React warnings, hydration issues, and unhandled promise rejections where browser execution is available.
77. Check responsive layout at narrow and wide viewport sizes, avoiding horizontal overflow, clipped dialogs, invisible controls, and inaccessible hover-only actions.
78. Check error messages are actionable, avoid secrets, and preserve user-entered form data where retry is expected.
79. Check the component handles loading, empty, success, partial-success, validation, unauthorized, not-found, conflict, rate-limit, server-error, and offline states as applicable.
80. Check that stale UI cache does not outlive a mutation. Invalidate/refetch only the relevant query/state according to the existing architecture.
81. Check a successful response has not been mistaken for semantic success when the backend returns a task ID with pending execution.
82. Check task completion is awaited or polled appropriately and the user can identify pending versus completed processing.
83. Check external provider errors propagate to a truthful status rather than being caught and converted into fabricated success.
84. Check any retry operation cannot create duplicate jobs, settings writes, uploads, publications, or cleanup operations.
85. Check the component has no hidden coupling to unapproved Phase 8 watermark branding or unsupported layouts.
86. Cross-reference actual behavior with `PHASE_TRACKER.md`, the relevant approved prompt, and the actual backend route/service. Do not assume draft/archived prompts are mandatory scope.
87. Check related documentation only if it is directly affected by the verified implementation; preserve historical audit evidence.
88. Update the component dossier with actual file paths, symbols, endpoint, backend behavior, test commands, Pass A evidence and Pass B evidence.
89. If a required operation is not present in the current UI, mark it absent and verify whether the approved specification requires it; do not silently invent UI.
90. If a required capability is absent, identify the exact implementation/API/test gap and fix it only when inside approved scope and governance permits.
91. Before any edit, record targeted Git status/diff; after edits, verify unrelated working-tree changes and untracked assets remain untouched.
92. Do not make changes beyond approved Phase 1–7 scope; Phase 8 watermark branding remains deferred unless separately authorized.
93. If this component offers a layout choice, require a real local reference thumbnail for every supported option and verify the output renderer matches it.
94. If this component participates in monitoring/publishing, check destination identity and state synchronization, and obey the central private-upload gate; do not create a second real upload.
95. Never expose secrets, run destructive database operations, publish public/unlisted test videos, or delete user media while verifying this component.
96. Perform Pass A: independently map every acceptance criterion to implementation and test evidence. Record exact paths, symbols, commands and actual results.
97. Perform Pass B independently using alternate evidence; explicitly confirm, contradict or leave uncertain every material Pass A claim.
98. Repair eligible defects and repeat the complete relevant test loop; if governance or safety blocks a fix, record the exact blocker and continue independent work.
99. Final acceptance for `CLIP-01`: every mandatory control in Clips search, filters, cards and selection must have a real handler/contract, verified backend result, correct UI synchronization, passing relevant test, and independent Pass A/Pass B evidence.
100. Return a concise per-control matrix, exact files changed, tests and results, unresolved issues, and final component verdict. Do not declare PASS when evidence is missing.


---

### CLIP-02 — Clip preview modal and playback controls

**Primary files to discover:** Clips preview modal, playback component and clip detail API  
**Component focus:** Open/close modal, preview player, metadata, tabs, links, keyboard/focus state  
**Acceptance focus:** Verify selected clip identity, correct media URL, playback and failed-media states, focus handling, modal close/escape behavior, no stale previous clip details, and API-backed values match persisted clip records.

Copy this complete prompt into the autonomous execution context for this component. Do not execute it in isolation from the master framework.

**100-step component prompt:**
1. Act as the autonomous owner of Clip preview modal and playback controls. Work only on the actual component discovered in the current checkout, not on an assumed or reconstructed UI.
2. Inspect Clips preview modal, playback component and clip detail API; follow imports and references to identify the real source files, tests, route and backend dependencies.
3. Component inventory: Open/close modal, preview player, metadata, tabs, links, keyboard/focus state. Discover the full list from the current UI and source. The list above is a focus guide, not permission to invent missing controls.
4. Acceptance focus: Verify selected clip identity, correct media URL, playback and failed-media states, focus handling, modal close/escape behavior, no stale previous clip details, and API-backed values match persisted clip records.
5. Create or update dossier ID `CLIP-02` and link this component to its authoritative Phase/C-series acceptance criterion without redefining phase numbering.
6. Capture current behavior first: record the visible state, control labels, current handler, API call, server response, persisted state and known failure behavior.
7. List every individual button, input, dropdown, link, tab, selector, icon action, modal action and keyboard action in this component; give each a stable child control ID.
8. For every control, specify one positive test, one invalid/error test, one repeated-action/idempotency test where relevant, and one refresh/persistence or cross-page sync test where relevant.
9. Trace every mutation from browser event to API client, backend route, service, persistence/task/external provider and the final returned UI state.
10. Record the precise success assertion and the objective failure condition before changing code; never count a cosmetic animation or toast as proof of backend success.
11. Begin by opening the actual component, its parent, child components, types, API-client methods, and tests; do not trust a previous report without checking the current checkout.
12. List the exact visible controls that belong to this component, including icon-only buttons, links styled as buttons, keyboard shortcuts, toggles, dropdown options, modal actions, and any hidden action revealed by state.
13. For each control, state the requirement and observable success condition before testing it; map each requirement to the approved roadmap item without changing canonical phase numbers.
14. Check whether the control is intentionally non-interactive. If so, it must be semantically non-interactive and cannot imply that an unavailable action will occur.
15. Check accessible name, label/description, role, focusability, keyboard activation, disabled state, focus order, and whether focus returns appropriately after a dialog closes.
16. Trace the real event handler. Reject empty callbacks, console-only callbacks, hard-coded results, no-op links, timer-only simulation, and UI-only state mutation for backend operations.
17. Locate the corresponding API-client method and verify HTTP method, route path, body/query parameters, identifiers, headers/auth, response type, status-code handling, and timeout behavior.
18. Confirm that the route exists in the current backend application and is included under the actual router prefix. Do not infer endpoint existence from a frontend URL string.
19. Inspect backend validation, authorization, ownership checks, service calls, transaction boundaries, queue/task dispatch, and error mapping for the operation.
20. Identify the authoritative persisted record or external response that proves success. Do not use only a toast, button animation, or HTTP 200 as proof of the intended side effect.
21. Check that the frontend consumes the real response and maps returned identifiers/state correctly. Detect hard-coded status strings and mismatched field names.
22. Test the normal successful action using an isolated fixture or safe test record wherever available.
23. Test missing, malformed, stale, or unauthorized identifiers without modifying real user data.
24. Test the expected validation boundary conditions and verify the UI shows a useful message rather than silently dropping the request.
25. Test a server-side failure and confirm no false success indicator appears.
26. Test a network timeout/connection reset and verify the UI does not assume that the backend definitely failed if the outcome may be ambiguous.
27. Test loading indicators and confirm they clear on success, error, cancellation, component unmount, and every supported early return.
28. Test double-click, repeated Enter, quick toggle changes, duplicate network retries, and stale component state for unintended duplicate actions.
29. Check race handling if the action operates on mutable status, queue positions, decisions, settings, uploads, or publishing state.
30. Check that stale/out-of-order responses cannot overwrite a newer state. Use request cancellation, version checks, or existing conventions where needed and approved.
31. Check the response status is translated to the correct UI state, including pending/in-progress, completed, partial failure, failed, cancelled, and conflict states where applicable.
32. Check whether optimistic UI is used. If so, ensure rollback or reconciliation occurs when the backend rejects the change.
33. Check whether the changed state should survive page refresh/reopen; if yes, reload and compare the visible state to the backend-authoritative result.
34. Check whether the state is shared with other pages/components. Trigger the action and inspect every relevant surface for stale data.
35. Check that filters, sorting, selection, pagination, tabs, and the current detail item behave correctly after the operation changes data.
36. Check behavior when the list is empty, the API returns null/partial optional data, a media asset is missing, or a provider is temporarily unavailable.
37. Check timezones, timestamps, duration units, percentages, byte sizes, numeric formatting, and enum labels against backend semantics.
38. Check no credential, OAuth token, API key, signed URL, or private user payload is exposed in visible UI, ordinary logs, test output, or screenshots.
39. Check that test-mode fallbacks or synthetic fixtures can only be activated by the repository-defined trusted test context, never by user-controlled substring or arbitrary request fields.
40. Check the action does not add, restore, expose, or invoke caption/subtitle features. Internal transcription may remain for approved analysis and metadata purposes.
41. Check the action does not route to Ollama or require Ollama environment variables. Preserve approved cloud-hosted models even if their names contain Llama.
42. Check the operation cannot accidentally publish to a source/monitoring channel instead of an explicitly configured destination.
43. Where an action creates a job/task, verify the persisted job ID is retained and Celery dispatch occurs only at the intended transition.
44. Where an action updates a task, verify the backend state transition is valid, durable, and visible on subsequent reads.
45. Where an action creates or deletes a file, verify storage path containment, ownership, retention policy, and cleanup behavior using isolated files only.
46. Where a control selects a layout, verify the selected ID maps to a supported renderer option rather than only changing the visual highlight.
47. Where a control shows a layout thumbnail, verify the reference asset exists in the production build, has the correct accessible text, and truthfully represents output composition.
48. Where the component displays progress, verify it is sourced from authoritative progress/status fields and cannot display completion before the task completes.
49. Where the component refreshes/polls, verify intervals, overlap, cooldown, backoff, and unmount cleanup against the actual code contract.
50. Where external providers are involved, test mocked/sandbox cases first and ensure no accidental external side effect is triggered by an ordinary test.
51. For the private YouTube acceptance upload, do not use this component test to generate another upload. The one real upload is centrally orchestrated and idempotently gated under the master framework.
52. Inspect the relevant unit/component test and add a regression test for each repaired defect where test infrastructure permits.
53. Run the smallest test covering this component first and record the exact command and actual exit result.
54. Run the relevant API/backend integration test where it can be proven safe and isolated.
55. Run the relevant browser/E2E test if available; do not describe static source inspection as a browser test.
56. Collect actual request/response evidence with secrets redacted. Link to the logs or test output that substantiate the result.
57. Compare the user-visible message/status with the actual backend response and persisted state.
58. Conduct Pass A by tracing requirements to implementation and successful tests.
59. Conduct Pass B independently using an alternate path such as persisted state, route registration, event log, task state, rendered output, refresh behavior, or a different test assertion.
60. If Pass A and Pass B disagree, investigate and document the discrepancy; do not average the results or silently pick the favorable one.
61. Classify a failure as UI defect, API contract mismatch, backend behavior defect, persistence defect, concurrency defect, configuration defect, missing test/evidence, or scope ambiguity.
62. Fix only defects within approved Phase 1–7 requirements and only through the governance process required by the freeze rules.
63. Before changing a shared API client, component, schema, backend route, or frozen domain, identify all affected pages and regression tests.
64. Keep the code change minimal and preserve pre-existing Git modifications and untracked files.
65. Never execute blanket Git reset/clean/checkout/restore commands or replace a whole file to make a small repair.
66. After a repair, rerun the failing reproduction, relevant component test, API/backend tests, and affected page regression checks.
67. Independently repeat Pass B after the repair, using evidence distinct from the original fix path where reasonably possible.
68. If the test fails, continue the diagnose/fix/retest loop within scope; if the failure requires unavailable authorization or unsafe operation, mark it blocked and continue unrelated work.
69. Do not stop at the first failed test if the cause is repairable within scope. Do not loop indefinitely if a genuine external or governance blocker exists.
70. Check that test teardown completes and does not silently mask failures; do not change global fixtures unless required and governed.
71. Confirm test DB isolation before any database mutation. Never migrate, drop, reset, or clean the operational clipforge database.
72. Confirm no test publishes an actual video except the one centralized, explicit, private acceptance upload authorized by the user.
73. Confirm no generated test file overwrites existing uploads or outputs and no cleanup task deletes user-owned media.
74. Run TypeScript and lint checks against the changed frontend where possible. Report repository-wide legacy issues separately from new introduced issues.
75. Run the production build after page/component changes and distinguish build output count from the number of user-facing pages.
76. Inspect browser console errors, failed network requests, React warnings, hydration issues, and unhandled promise rejections where browser execution is available.
77. Check responsive layout at narrow and wide viewport sizes, avoiding horizontal overflow, clipped dialogs, invisible controls, and inaccessible hover-only actions.
78. Check error messages are actionable, avoid secrets, and preserve user-entered form data where retry is expected.
79. Check the component handles loading, empty, success, partial-success, validation, unauthorized, not-found, conflict, rate-limit, server-error, and offline states as applicable.
80. Check that stale UI cache does not outlive a mutation. Invalidate/refetch only the relevant query/state according to the existing architecture.
81. Check a successful response has not been mistaken for semantic success when the backend returns a task ID with pending execution.
82. Check task completion is awaited or polled appropriately and the user can identify pending versus completed processing.
83. Check external provider errors propagate to a truthful status rather than being caught and converted into fabricated success.
84. Check any retry operation cannot create duplicate jobs, settings writes, uploads, publications, or cleanup operations.
85. Check the component has no hidden coupling to unapproved Phase 8 watermark branding or unsupported layouts.
86. Cross-reference actual behavior with `PHASE_TRACKER.md`, the relevant approved prompt, and the actual backend route/service. Do not assume draft/archived prompts are mandatory scope.
87. Check related documentation only if it is directly affected by the verified implementation; preserve historical audit evidence.
88. Update the component dossier with actual file paths, symbols, endpoint, backend behavior, test commands, Pass A evidence and Pass B evidence.
89. If a required operation is not present in the current UI, mark it absent and verify whether the approved specification requires it; do not silently invent UI.
90. If a required capability is absent, identify the exact implementation/API/test gap and fix it only when inside approved scope and governance permits.
91. Before any edit, record targeted Git status/diff; after edits, verify unrelated working-tree changes and untracked assets remain untouched.
92. Do not make changes beyond approved Phase 1–7 scope; Phase 8 watermark branding remains deferred unless separately authorized.
93. If this component offers a layout choice, require a real local reference thumbnail for every supported option and verify the output renderer matches it.
94. If this component participates in monitoring/publishing, check destination identity and state synchronization, and obey the central private-upload gate; do not create a second real upload.
95. Never expose secrets, run destructive database operations, publish public/unlisted test videos, or delete user media while verifying this component.
96. Perform Pass A: independently map every acceptance criterion to implementation and test evidence. Record exact paths, symbols, commands and actual results.
97. Perform Pass B independently using alternate evidence; explicitly confirm, contradict or leave uncertain every material Pass A claim.
98. Repair eligible defects and repeat the complete relevant test loop; if governance or safety blocks a fix, record the exact blocker and continue independent work.
99. Final acceptance for `CLIP-02`: every mandatory control in Clip preview modal and playback controls must have a real handler/contract, verified backend result, correct UI synchronization, passing relevant test, and independent Pass A/Pass B evidence.
100. Return a concise per-control matrix, exact files changed, tests and results, unresolved issues, and final component verdict. Do not declare PASS when evidence is missing.


---

### CLIP-03 — Hook/SFX/B-roll controls and preview tabs

**Primary files to discover:** Actual Clips Preview AI enhancement tabs and their GET/POST API contracts  
**Component focus:** Hook controls, SFX-plan read/generate actions, B-roll controls, any audio/ducking controls  
**Acceptance focus:** Verify read GET operations remain read-only; generation uses the intended POST/task; production cannot receive synthetic test assets; each control displays real returned state; task completion/failure is reflected; retry does not duplicate tasks; no caption features appear.

Copy this complete prompt into the autonomous execution context for this component. Do not execute it in isolation from the master framework.

**100-step component prompt:**
1. Act as the autonomous owner of Hook/SFX/B-roll controls and preview tabs. Work only on the actual component discovered in the current checkout, not on an assumed or reconstructed UI.
2. Inspect Actual Clips Preview AI enhancement tabs and their GET/POST API contracts; follow imports and references to identify the real source files, tests, route and backend dependencies.
3. Component inventory: Hook controls, SFX-plan read/generate actions, B-roll controls, any audio/ducking controls. Discover the full list from the current UI and source. The list above is a focus guide, not permission to invent missing controls.
4. Acceptance focus: Verify read GET operations remain read-only; generation uses the intended POST/task; production cannot receive synthetic test assets; each control displays real returned state; task completion/failure is reflected; retry does not duplicate tasks; no caption features appear.
5. Create or update dossier ID `CLIP-03` and link this component to its authoritative Phase/C-series acceptance criterion without redefining phase numbering.
6. Capture current behavior first: record the visible state, control labels, current handler, API call, server response, persisted state and known failure behavior.
7. List every individual button, input, dropdown, link, tab, selector, icon action, modal action and keyboard action in this component; give each a stable child control ID.
8. For every control, specify one positive test, one invalid/error test, one repeated-action/idempotency test where relevant, and one refresh/persistence or cross-page sync test where relevant.
9. Trace every mutation from browser event to API client, backend route, service, persistence/task/external provider and the final returned UI state.
10. Record the precise success assertion and the objective failure condition before changing code; never count a cosmetic animation or toast as proof of backend success.
11. Begin by opening the actual component, its parent, child components, types, API-client methods, and tests; do not trust a previous report without checking the current checkout.
12. List the exact visible controls that belong to this component, including icon-only buttons, links styled as buttons, keyboard shortcuts, toggles, dropdown options, modal actions, and any hidden action revealed by state.
13. For each control, state the requirement and observable success condition before testing it; map each requirement to the approved roadmap item without changing canonical phase numbers.
14. Check whether the control is intentionally non-interactive. If so, it must be semantically non-interactive and cannot imply that an unavailable action will occur.
15. Check accessible name, label/description, role, focusability, keyboard activation, disabled state, focus order, and whether focus returns appropriately after a dialog closes.
16. Trace the real event handler. Reject empty callbacks, console-only callbacks, hard-coded results, no-op links, timer-only simulation, and UI-only state mutation for backend operations.
17. Locate the corresponding API-client method and verify HTTP method, route path, body/query parameters, identifiers, headers/auth, response type, status-code handling, and timeout behavior.
18. Confirm that the route exists in the current backend application and is included under the actual router prefix. Do not infer endpoint existence from a frontend URL string.
19. Inspect backend validation, authorization, ownership checks, service calls, transaction boundaries, queue/task dispatch, and error mapping for the operation.
20. Identify the authoritative persisted record or external response that proves success. Do not use only a toast, button animation, or HTTP 200 as proof of the intended side effect.
21. Check that the frontend consumes the real response and maps returned identifiers/state correctly. Detect hard-coded status strings and mismatched field names.
22. Test the normal successful action using an isolated fixture or safe test record wherever available.
23. Test missing, malformed, stale, or unauthorized identifiers without modifying real user data.
24. Test the expected validation boundary conditions and verify the UI shows a useful message rather than silently dropping the request.
25. Test a server-side failure and confirm no false success indicator appears.
26. Test a network timeout/connection reset and verify the UI does not assume that the backend definitely failed if the outcome may be ambiguous.
27. Test loading indicators and confirm they clear on success, error, cancellation, component unmount, and every supported early return.
28. Test double-click, repeated Enter, quick toggle changes, duplicate network retries, and stale component state for unintended duplicate actions.
29. Check race handling if the action operates on mutable status, queue positions, decisions, settings, uploads, or publishing state.
30. Check that stale/out-of-order responses cannot overwrite a newer state. Use request cancellation, version checks, or existing conventions where needed and approved.
31. Check the response status is translated to the correct UI state, including pending/in-progress, completed, partial failure, failed, cancelled, and conflict states where applicable.
32. Check whether optimistic UI is used. If so, ensure rollback or reconciliation occurs when the backend rejects the change.
33. Check whether the changed state should survive page refresh/reopen; if yes, reload and compare the visible state to the backend-authoritative result.
34. Check whether the state is shared with other pages/components. Trigger the action and inspect every relevant surface for stale data.
35. Check that filters, sorting, selection, pagination, tabs, and the current detail item behave correctly after the operation changes data.
36. Check behavior when the list is empty, the API returns null/partial optional data, a media asset is missing, or a provider is temporarily unavailable.
37. Check timezones, timestamps, duration units, percentages, byte sizes, numeric formatting, and enum labels against backend semantics.
38. Check no credential, OAuth token, API key, signed URL, or private user payload is exposed in visible UI, ordinary logs, test output, or screenshots.
39. Check that test-mode fallbacks or synthetic fixtures can only be activated by the repository-defined trusted test context, never by user-controlled substring or arbitrary request fields.
40. Check the action does not add, restore, expose, or invoke caption/subtitle features. Internal transcription may remain for approved analysis and metadata purposes.
41. Check the action does not route to Ollama or require Ollama environment variables. Preserve approved cloud-hosted models even if their names contain Llama.
42. Check the operation cannot accidentally publish to a source/monitoring channel instead of an explicitly configured destination.
43. Where an action creates a job/task, verify the persisted job ID is retained and Celery dispatch occurs only at the intended transition.
44. Where an action updates a task, verify the backend state transition is valid, durable, and visible on subsequent reads.
45. Where an action creates or deletes a file, verify storage path containment, ownership, retention policy, and cleanup behavior using isolated files only.
46. Where a control selects a layout, verify the selected ID maps to a supported renderer option rather than only changing the visual highlight.
47. Where a control shows a layout thumbnail, verify the reference asset exists in the production build, has the correct accessible text, and truthfully represents output composition.
48. Where the component displays progress, verify it is sourced from authoritative progress/status fields and cannot display completion before the task completes.
49. Where the component refreshes/polls, verify intervals, overlap, cooldown, backoff, and unmount cleanup against the actual code contract.
50. Where external providers are involved, test mocked/sandbox cases first and ensure no accidental external side effect is triggered by an ordinary test.
51. For the private YouTube acceptance upload, do not use this component test to generate another upload. The one real upload is centrally orchestrated and idempotently gated under the master framework.
52. Inspect the relevant unit/component test and add a regression test for each repaired defect where test infrastructure permits.
53. Run the smallest test covering this component first and record the exact command and actual exit result.
54. Run the relevant API/backend integration test where it can be proven safe and isolated.
55. Run the relevant browser/E2E test if available; do not describe static source inspection as a browser test.
56. Collect actual request/response evidence with secrets redacted. Link to the logs or test output that substantiate the result.
57. Compare the user-visible message/status with the actual backend response and persisted state.
58. Conduct Pass A by tracing requirements to implementation and successful tests.
59. Conduct Pass B independently using an alternate path such as persisted state, route registration, event log, task state, rendered output, refresh behavior, or a different test assertion.
60. If Pass A and Pass B disagree, investigate and document the discrepancy; do not average the results or silently pick the favorable one.
61. Classify a failure as UI defect, API contract mismatch, backend behavior defect, persistence defect, concurrency defect, configuration defect, missing test/evidence, or scope ambiguity.
62. Fix only defects within approved Phase 1–7 requirements and only through the governance process required by the freeze rules.
63. Before changing a shared API client, component, schema, backend route, or frozen domain, identify all affected pages and regression tests.
64. Keep the code change minimal and preserve pre-existing Git modifications and untracked files.
65. Never execute blanket Git reset/clean/checkout/restore commands or replace a whole file to make a small repair.
66. After a repair, rerun the failing reproduction, relevant component test, API/backend tests, and affected page regression checks.
67. Independently repeat Pass B after the repair, using evidence distinct from the original fix path where reasonably possible.
68. If the test fails, continue the diagnose/fix/retest loop within scope; if the failure requires unavailable authorization or unsafe operation, mark it blocked and continue unrelated work.
69. Do not stop at the first failed test if the cause is repairable within scope. Do not loop indefinitely if a genuine external or governance blocker exists.
70. Check that test teardown completes and does not silently mask failures; do not change global fixtures unless required and governed.
71. Confirm test DB isolation before any database mutation. Never migrate, drop, reset, or clean the operational clipforge database.
72. Confirm no test publishes an actual video except the one centralized, explicit, private acceptance upload authorized by the user.
73. Confirm no generated test file overwrites existing uploads or outputs and no cleanup task deletes user-owned media.
74. Run TypeScript and lint checks against the changed frontend where possible. Report repository-wide legacy issues separately from new introduced issues.
75. Run the production build after page/component changes and distinguish build output count from the number of user-facing pages.
76. Inspect browser console errors, failed network requests, React warnings, hydration issues, and unhandled promise rejections where browser execution is available.
77. Check responsive layout at narrow and wide viewport sizes, avoiding horizontal overflow, clipped dialogs, invisible controls, and inaccessible hover-only actions.
78. Check error messages are actionable, avoid secrets, and preserve user-entered form data where retry is expected.
79. Check the component handles loading, empty, success, partial-success, validation, unauthorized, not-found, conflict, rate-limit, server-error, and offline states as applicable.
80. Check that stale UI cache does not outlive a mutation. Invalidate/refetch only the relevant query/state according to the existing architecture.
81. Check a successful response has not been mistaken for semantic success when the backend returns a task ID with pending execution.
82. Check task completion is awaited or polled appropriately and the user can identify pending versus completed processing.
83. Check external provider errors propagate to a truthful status rather than being caught and converted into fabricated success.
84. Check any retry operation cannot create duplicate jobs, settings writes, uploads, publications, or cleanup operations.
85. Check the component has no hidden coupling to unapproved Phase 8 watermark branding or unsupported layouts.
86. Cross-reference actual behavior with `PHASE_TRACKER.md`, the relevant approved prompt, and the actual backend route/service. Do not assume draft/archived prompts are mandatory scope.
87. Check related documentation only if it is directly affected by the verified implementation; preserve historical audit evidence.
88. Update the component dossier with actual file paths, symbols, endpoint, backend behavior, test commands, Pass A evidence and Pass B evidence.
89. If a required operation is not present in the current UI, mark it absent and verify whether the approved specification requires it; do not silently invent UI.
90. If a required capability is absent, identify the exact implementation/API/test gap and fix it only when inside approved scope and governance permits.
91. Before any edit, record targeted Git status/diff; after edits, verify unrelated working-tree changes and untracked assets remain untouched.
92. Do not make changes beyond approved Phase 1–7 scope; Phase 8 watermark branding remains deferred unless separately authorized.
93. If this component offers a layout choice, require a real local reference thumbnail for every supported option and verify the output renderer matches it.
94. If this component participates in monitoring/publishing, check destination identity and state synchronization, and obey the central private-upload gate; do not create a second real upload.
95. Never expose secrets, run destructive database operations, publish public/unlisted test videos, or delete user media while verifying this component.
96. Perform Pass A: independently map every acceptance criterion to implementation and test evidence. Record exact paths, symbols, commands and actual results.
97. Perform Pass B independently using alternate evidence; explicitly confirm, contradict or leave uncertain every material Pass A claim.
98. Repair eligible defects and repeat the complete relevant test loop; if governance or safety blocks a fix, record the exact blocker and continue independent work.
99. Final acceptance for `CLIP-03`: every mandatory control in Hook/SFX/B-roll controls and preview tabs must have a real handler/contract, verified backend result, correct UI synchronization, passing relevant test, and independent Pass A/Pass B evidence.
100. Return a concise per-control matrix, exact files changed, tests and results, unresolved issues, and final component verdict. Do not declare PASS when evidence is missing.


---

### CLIP-04 — Layout selector and rendered-output verification

**Primary files to discover:** Actual clip-level layout selector, layout/reframe API, renderer and metadata  
**Component focus:** Every actual layout option when selecting layout for a clip  
**Acceptance focus:** Require a real reference thumbnail per option, exact layout enum mapping, successful API submit, renderer invocation, persisted output location, output dimension/aspect ratio, crop/split/blur matching thumbnail, and visual evidence from a safe test asset.

Copy this complete prompt into the autonomous execution context for this component. Do not execute it in isolation from the master framework.

**100-step component prompt:**
1. Act as the autonomous owner of Layout selector and rendered-output verification. Work only on the actual component discovered in the current checkout, not on an assumed or reconstructed UI.
2. Inspect Actual clip-level layout selector, layout/reframe API, renderer and metadata; follow imports and references to identify the real source files, tests, route and backend dependencies.
3. Component inventory: Every actual layout option when selecting layout for a clip. Discover the full list from the current UI and source. The list above is a focus guide, not permission to invent missing controls.
4. Acceptance focus: Require a real reference thumbnail per option, exact layout enum mapping, successful API submit, renderer invocation, persisted output location, output dimension/aspect ratio, crop/split/blur matching thumbnail, and visual evidence from a safe test asset.
5. Create or update dossier ID `CLIP-04` and link this component to its authoritative Phase/C-series acceptance criterion without redefining phase numbering.
6. Capture current behavior first: record the visible state, control labels, current handler, API call, server response, persisted state and known failure behavior.
7. List every individual button, input, dropdown, link, tab, selector, icon action, modal action and keyboard action in this component; give each a stable child control ID.
8. For every control, specify one positive test, one invalid/error test, one repeated-action/idempotency test where relevant, and one refresh/persistence or cross-page sync test where relevant.
9. Trace every mutation from browser event to API client, backend route, service, persistence/task/external provider and the final returned UI state.
10. Record the precise success assertion and the objective failure condition before changing code; never count a cosmetic animation or toast as proof of backend success.
11. Begin by opening the actual component, its parent, child components, types, API-client methods, and tests; do not trust a previous report without checking the current checkout.
12. List the exact visible controls that belong to this component, including icon-only buttons, links styled as buttons, keyboard shortcuts, toggles, dropdown options, modal actions, and any hidden action revealed by state.
13. For each control, state the requirement and observable success condition before testing it; map each requirement to the approved roadmap item without changing canonical phase numbers.
14. Check whether the control is intentionally non-interactive. If so, it must be semantically non-interactive and cannot imply that an unavailable action will occur.
15. Check accessible name, label/description, role, focusability, keyboard activation, disabled state, focus order, and whether focus returns appropriately after a dialog closes.
16. Trace the real event handler. Reject empty callbacks, console-only callbacks, hard-coded results, no-op links, timer-only simulation, and UI-only state mutation for backend operations.
17. Locate the corresponding API-client method and verify HTTP method, route path, body/query parameters, identifiers, headers/auth, response type, status-code handling, and timeout behavior.
18. Confirm that the route exists in the current backend application and is included under the actual router prefix. Do not infer endpoint existence from a frontend URL string.
19. Inspect backend validation, authorization, ownership checks, service calls, transaction boundaries, queue/task dispatch, and error mapping for the operation.
20. Identify the authoritative persisted record or external response that proves success. Do not use only a toast, button animation, or HTTP 200 as proof of the intended side effect.
21. Check that the frontend consumes the real response and maps returned identifiers/state correctly. Detect hard-coded status strings and mismatched field names.
22. Test the normal successful action using an isolated fixture or safe test record wherever available.
23. Test missing, malformed, stale, or unauthorized identifiers without modifying real user data.
24. Test the expected validation boundary conditions and verify the UI shows a useful message rather than silently dropping the request.
25. Test a server-side failure and confirm no false success indicator appears.
26. Test a network timeout/connection reset and verify the UI does not assume that the backend definitely failed if the outcome may be ambiguous.
27. Test loading indicators and confirm they clear on success, error, cancellation, component unmount, and every supported early return.
28. Test double-click, repeated Enter, quick toggle changes, duplicate network retries, and stale component state for unintended duplicate actions.
29. Check race handling if the action operates on mutable status, queue positions, decisions, settings, uploads, or publishing state.
30. Check that stale/out-of-order responses cannot overwrite a newer state. Use request cancellation, version checks, or existing conventions where needed and approved.
31. Check the response status is translated to the correct UI state, including pending/in-progress, completed, partial failure, failed, cancelled, and conflict states where applicable.
32. Check whether optimistic UI is used. If so, ensure rollback or reconciliation occurs when the backend rejects the change.
33. Check whether the changed state should survive page refresh/reopen; if yes, reload and compare the visible state to the backend-authoritative result.
34. Check whether the state is shared with other pages/components. Trigger the action and inspect every relevant surface for stale data.
35. Check that filters, sorting, selection, pagination, tabs, and the current detail item behave correctly after the operation changes data.
36. Check behavior when the list is empty, the API returns null/partial optional data, a media asset is missing, or a provider is temporarily unavailable.
37. Check timezones, timestamps, duration units, percentages, byte sizes, numeric formatting, and enum labels against backend semantics.
38. Check no credential, OAuth token, API key, signed URL, or private user payload is exposed in visible UI, ordinary logs, test output, or screenshots.
39. Check that test-mode fallbacks or synthetic fixtures can only be activated by the repository-defined trusted test context, never by user-controlled substring or arbitrary request fields.
40. Check the action does not add, restore, expose, or invoke caption/subtitle features. Internal transcription may remain for approved analysis and metadata purposes.
41. Check the action does not route to Ollama or require Ollama environment variables. Preserve approved cloud-hosted models even if their names contain Llama.
42. Check the operation cannot accidentally publish to a source/monitoring channel instead of an explicitly configured destination.
43. Where an action creates a job/task, verify the persisted job ID is retained and Celery dispatch occurs only at the intended transition.
44. Where an action updates a task, verify the backend state transition is valid, durable, and visible on subsequent reads.
45. Where an action creates or deletes a file, verify storage path containment, ownership, retention policy, and cleanup behavior using isolated files only.
46. Where a control selects a layout, verify the selected ID maps to a supported renderer option rather than only changing the visual highlight.
47. Where a control shows a layout thumbnail, verify the reference asset exists in the production build, has the correct accessible text, and truthfully represents output composition.
48. Where the component displays progress, verify it is sourced from authoritative progress/status fields and cannot display completion before the task completes.
49. Where the component refreshes/polls, verify intervals, overlap, cooldown, backoff, and unmount cleanup against the actual code contract.
50. Where external providers are involved, test mocked/sandbox cases first and ensure no accidental external side effect is triggered by an ordinary test.
51. For the private YouTube acceptance upload, do not use this component test to generate another upload. The one real upload is centrally orchestrated and idempotently gated under the master framework.
52. Inspect the relevant unit/component test and add a regression test for each repaired defect where test infrastructure permits.
53. Run the smallest test covering this component first and record the exact command and actual exit result.
54. Run the relevant API/backend integration test where it can be proven safe and isolated.
55. Run the relevant browser/E2E test if available; do not describe static source inspection as a browser test.
56. Collect actual request/response evidence with secrets redacted. Link to the logs or test output that substantiate the result.
57. Compare the user-visible message/status with the actual backend response and persisted state.
58. Conduct Pass A by tracing requirements to implementation and successful tests.
59. Conduct Pass B independently using an alternate path such as persisted state, route registration, event log, task state, rendered output, refresh behavior, or a different test assertion.
60. If Pass A and Pass B disagree, investigate and document the discrepancy; do not average the results or silently pick the favorable one.
61. Classify a failure as UI defect, API contract mismatch, backend behavior defect, persistence defect, concurrency defect, configuration defect, missing test/evidence, or scope ambiguity.
62. Fix only defects within approved Phase 1–7 requirements and only through the governance process required by the freeze rules.
63. Before changing a shared API client, component, schema, backend route, or frozen domain, identify all affected pages and regression tests.
64. Keep the code change minimal and preserve pre-existing Git modifications and untracked files.
65. Never execute blanket Git reset/clean/checkout/restore commands or replace a whole file to make a small repair.
66. After a repair, rerun the failing reproduction, relevant component test, API/backend tests, and affected page regression checks.
67. Independently repeat Pass B after the repair, using evidence distinct from the original fix path where reasonably possible.
68. If the test fails, continue the diagnose/fix/retest loop within scope; if the failure requires unavailable authorization or unsafe operation, mark it blocked and continue unrelated work.
69. Do not stop at the first failed test if the cause is repairable within scope. Do not loop indefinitely if a genuine external or governance blocker exists.
70. Check that test teardown completes and does not silently mask failures; do not change global fixtures unless required and governed.
71. Confirm test DB isolation before any database mutation. Never migrate, drop, reset, or clean the operational clipforge database.
72. Confirm no test publishes an actual video except the one centralized, explicit, private acceptance upload authorized by the user.
73. Confirm no generated test file overwrites existing uploads or outputs and no cleanup task deletes user-owned media.
74. Run TypeScript and lint checks against the changed frontend where possible. Report repository-wide legacy issues separately from new introduced issues.
75. Run the production build after page/component changes and distinguish build output count from the number of user-facing pages.
76. Inspect browser console errors, failed network requests, React warnings, hydration issues, and unhandled promise rejections where browser execution is available.
77. Check responsive layout at narrow and wide viewport sizes, avoiding horizontal overflow, clipped dialogs, invisible controls, and inaccessible hover-only actions.
78. Check error messages are actionable, avoid secrets, and preserve user-entered form data where retry is expected.
79. Check the component handles loading, empty, success, partial-success, validation, unauthorized, not-found, conflict, rate-limit, server-error, and offline states as applicable.
80. Check that stale UI cache does not outlive a mutation. Invalidate/refetch only the relevant query/state according to the existing architecture.
81. Check a successful response has not been mistaken for semantic success when the backend returns a task ID with pending execution.
82. Check task completion is awaited or polled appropriately and the user can identify pending versus completed processing.
83. Check external provider errors propagate to a truthful status rather than being caught and converted into fabricated success.
84. Check any retry operation cannot create duplicate jobs, settings writes, uploads, publications, or cleanup operations.
85. Check the component has no hidden coupling to unapproved Phase 8 watermark branding or unsupported layouts.
86. Cross-reference actual behavior with `PHASE_TRACKER.md`, the relevant approved prompt, and the actual backend route/service. Do not assume draft/archived prompts are mandatory scope.
87. Check related documentation only if it is directly affected by the verified implementation; preserve historical audit evidence.
88. Update the component dossier with actual file paths, symbols, endpoint, backend behavior, test commands, Pass A evidence and Pass B evidence.
89. If a required operation is not present in the current UI, mark it absent and verify whether the approved specification requires it; do not silently invent UI.
90. If a required capability is absent, identify the exact implementation/API/test gap and fix it only when inside approved scope and governance permits.
91. Before any edit, record targeted Git status/diff; after edits, verify unrelated working-tree changes and untracked assets remain untouched.
92. Do not make changes beyond approved Phase 1–7 scope; Phase 8 watermark branding remains deferred unless separately authorized.
93. If this component offers a layout choice, require a real local reference thumbnail for every supported option and verify the output renderer matches it.
94. If this component participates in monitoring/publishing, check destination identity and state synchronization, and obey the central private-upload gate; do not create a second real upload.
95. Never expose secrets, run destructive database operations, publish public/unlisted test videos, or delete user media while verifying this component.
96. Perform Pass A: independently map every acceptance criterion to implementation and test evidence. Record exact paths, symbols, commands and actual results.
97. Perform Pass B independently using alternate evidence; explicitly confirm, contradict or leave uncertain every material Pass A claim.
98. Repair eligible defects and repeat the complete relevant test loop; if governance or safety blocks a fix, record the exact blocker and continue independent work.
99. Final acceptance for `CLIP-04`: every mandatory control in Layout selector and rendered-output verification must have a real handler/contract, verified backend result, correct UI synchronization, passing relevant test, and independent Pass A/Pass B evidence.
100. Return a concise per-control matrix, exact files changed, tests and results, unresolved issues, and final component verdict. Do not declare PASS when evidence is missing.


---

### CLIP-05 — Storage cleanup preview and execute flow

**Primary files to discover:** Clip cleanup UI and preview/execute endpoints  
**Component focus:** Preview candidate files, token/lease display, selection/confirmation, execute result  
**Acceptance focus:** Verify preview has no deletion side effects, token is tied to the right user/lease/expiry, canonical containment and quarantine rules hold, execute requires valid preview authorization, report matches actual cleanup journal, and no unrelated media is removed.

Copy this complete prompt into the autonomous execution context for this component. Do not execute it in isolation from the master framework.

**100-step component prompt:**
1. Act as the autonomous owner of Storage cleanup preview and execute flow. Work only on the actual component discovered in the current checkout, not on an assumed or reconstructed UI.
2. Inspect Clip cleanup UI and preview/execute endpoints; follow imports and references to identify the real source files, tests, route and backend dependencies.
3. Component inventory: Preview candidate files, token/lease display, selection/confirmation, execute result. Discover the full list from the current UI and source. The list above is a focus guide, not permission to invent missing controls.
4. Acceptance focus: Verify preview has no deletion side effects, token is tied to the right user/lease/expiry, canonical containment and quarantine rules hold, execute requires valid preview authorization, report matches actual cleanup journal, and no unrelated media is removed.
5. Create or update dossier ID `CLIP-05` and link this component to its authoritative Phase/C-series acceptance criterion without redefining phase numbering.
6. Capture current behavior first: record the visible state, control labels, current handler, API call, server response, persisted state and known failure behavior.
7. List every individual button, input, dropdown, link, tab, selector, icon action, modal action and keyboard action in this component; give each a stable child control ID.
8. For every control, specify one positive test, one invalid/error test, one repeated-action/idempotency test where relevant, and one refresh/persistence or cross-page sync test where relevant.
9. Trace every mutation from browser event to API client, backend route, service, persistence/task/external provider and the final returned UI state.
10. Record the precise success assertion and the objective failure condition before changing code; never count a cosmetic animation or toast as proof of backend success.
11. Begin by opening the actual component, its parent, child components, types, API-client methods, and tests; do not trust a previous report without checking the current checkout.
12. List the exact visible controls that belong to this component, including icon-only buttons, links styled as buttons, keyboard shortcuts, toggles, dropdown options, modal actions, and any hidden action revealed by state.
13. For each control, state the requirement and observable success condition before testing it; map each requirement to the approved roadmap item without changing canonical phase numbers.
14. Check whether the control is intentionally non-interactive. If so, it must be semantically non-interactive and cannot imply that an unavailable action will occur.
15. Check accessible name, label/description, role, focusability, keyboard activation, disabled state, focus order, and whether focus returns appropriately after a dialog closes.
16. Trace the real event handler. Reject empty callbacks, console-only callbacks, hard-coded results, no-op links, timer-only simulation, and UI-only state mutation for backend operations.
17. Locate the corresponding API-client method and verify HTTP method, route path, body/query parameters, identifiers, headers/auth, response type, status-code handling, and timeout behavior.
18. Confirm that the route exists in the current backend application and is included under the actual router prefix. Do not infer endpoint existence from a frontend URL string.
19. Inspect backend validation, authorization, ownership checks, service calls, transaction boundaries, queue/task dispatch, and error mapping for the operation.
20. Identify the authoritative persisted record or external response that proves success. Do not use only a toast, button animation, or HTTP 200 as proof of the intended side effect.
21. Check that the frontend consumes the real response and maps returned identifiers/state correctly. Detect hard-coded status strings and mismatched field names.
22. Test the normal successful action using an isolated fixture or safe test record wherever available.
23. Test missing, malformed, stale, or unauthorized identifiers without modifying real user data.
24. Test the expected validation boundary conditions and verify the UI shows a useful message rather than silently dropping the request.
25. Test a server-side failure and confirm no false success indicator appears.
26. Test a network timeout/connection reset and verify the UI does not assume that the backend definitely failed if the outcome may be ambiguous.
27. Test loading indicators and confirm they clear on success, error, cancellation, component unmount, and every supported early return.
28. Test double-click, repeated Enter, quick toggle changes, duplicate network retries, and stale component state for unintended duplicate actions.
29. Check race handling if the action operates on mutable status, queue positions, decisions, settings, uploads, or publishing state.
30. Check that stale/out-of-order responses cannot overwrite a newer state. Use request cancellation, version checks, or existing conventions where needed and approved.
31. Check the response status is translated to the correct UI state, including pending/in-progress, completed, partial failure, failed, cancelled, and conflict states where applicable.
32. Check whether optimistic UI is used. If so, ensure rollback or reconciliation occurs when the backend rejects the change.
33. Check whether the changed state should survive page refresh/reopen; if yes, reload and compare the visible state to the backend-authoritative result.
34. Check whether the state is shared with other pages/components. Trigger the action and inspect every relevant surface for stale data.
35. Check that filters, sorting, selection, pagination, tabs, and the current detail item behave correctly after the operation changes data.
36. Check behavior when the list is empty, the API returns null/partial optional data, a media asset is missing, or a provider is temporarily unavailable.
37. Check timezones, timestamps, duration units, percentages, byte sizes, numeric formatting, and enum labels against backend semantics.
38. Check no credential, OAuth token, API key, signed URL, or private user payload is exposed in visible UI, ordinary logs, test output, or screenshots.
39. Check that test-mode fallbacks or synthetic fixtures can only be activated by the repository-defined trusted test context, never by user-controlled substring or arbitrary request fields.
40. Check the action does not add, restore, expose, or invoke caption/subtitle features. Internal transcription may remain for approved analysis and metadata purposes.
41. Check the action does not route to Ollama or require Ollama environment variables. Preserve approved cloud-hosted models even if their names contain Llama.
42. Check the operation cannot accidentally publish to a source/monitoring channel instead of an explicitly configured destination.
43. Where an action creates a job/task, verify the persisted job ID is retained and Celery dispatch occurs only at the intended transition.
44. Where an action updates a task, verify the backend state transition is valid, durable, and visible on subsequent reads.
45. Where an action creates or deletes a file, verify storage path containment, ownership, retention policy, and cleanup behavior using isolated files only.
46. Where a control selects a layout, verify the selected ID maps to a supported renderer option rather than only changing the visual highlight.
47. Where a control shows a layout thumbnail, verify the reference asset exists in the production build, has the correct accessible text, and truthfully represents output composition.
48. Where the component displays progress, verify it is sourced from authoritative progress/status fields and cannot display completion before the task completes.
49. Where the component refreshes/polls, verify intervals, overlap, cooldown, backoff, and unmount cleanup against the actual code contract.
50. Where external providers are involved, test mocked/sandbox cases first and ensure no accidental external side effect is triggered by an ordinary test.
51. For the private YouTube acceptance upload, do not use this component test to generate another upload. The one real upload is centrally orchestrated and idempotently gated under the master framework.
52. Inspect the relevant unit/component test and add a regression test for each repaired defect where test infrastructure permits.
53. Run the smallest test covering this component first and record the exact command and actual exit result.
54. Run the relevant API/backend integration test where it can be proven safe and isolated.
55. Run the relevant browser/E2E test if available; do not describe static source inspection as a browser test.
56. Collect actual request/response evidence with secrets redacted. Link to the logs or test output that substantiate the result.
57. Compare the user-visible message/status with the actual backend response and persisted state.
58. Conduct Pass A by tracing requirements to implementation and successful tests.
59. Conduct Pass B independently using an alternate path such as persisted state, route registration, event log, task state, rendered output, refresh behavior, or a different test assertion.
60. If Pass A and Pass B disagree, investigate and document the discrepancy; do not average the results or silently pick the favorable one.
61. Classify a failure as UI defect, API contract mismatch, backend behavior defect, persistence defect, concurrency defect, configuration defect, missing test/evidence, or scope ambiguity.
62. Fix only defects within approved Phase 1–7 requirements and only through the governance process required by the freeze rules.
63. Before changing a shared API client, component, schema, backend route, or frozen domain, identify all affected pages and regression tests.
64. Keep the code change minimal and preserve pre-existing Git modifications and untracked files.
65. Never execute blanket Git reset/clean/checkout/restore commands or replace a whole file to make a small repair.
66. After a repair, rerun the failing reproduction, relevant component test, API/backend tests, and affected page regression checks.
67. Independently repeat Pass B after the repair, using evidence distinct from the original fix path where reasonably possible.
68. If the test fails, continue the diagnose/fix/retest loop within scope; if the failure requires unavailable authorization or unsafe operation, mark it blocked and continue unrelated work.
69. Do not stop at the first failed test if the cause is repairable within scope. Do not loop indefinitely if a genuine external or governance blocker exists.
70. Check that test teardown completes and does not silently mask failures; do not change global fixtures unless required and governed.
71. Confirm test DB isolation before any database mutation. Never migrate, drop, reset, or clean the operational clipforge database.
72. Confirm no test publishes an actual video except the one centralized, explicit, private acceptance upload authorized by the user.
73. Confirm no generated test file overwrites existing uploads or outputs and no cleanup task deletes user-owned media.
74. Run TypeScript and lint checks against the changed frontend where possible. Report repository-wide legacy issues separately from new introduced issues.
75. Run the production build after page/component changes and distinguish build output count from the number of user-facing pages.
76. Inspect browser console errors, failed network requests, React warnings, hydration issues, and unhandled promise rejections where browser execution is available.
77. Check responsive layout at narrow and wide viewport sizes, avoiding horizontal overflow, clipped dialogs, invisible controls, and inaccessible hover-only actions.
78. Check error messages are actionable, avoid secrets, and preserve user-entered form data where retry is expected.
79. Check the component handles loading, empty, success, partial-success, validation, unauthorized, not-found, conflict, rate-limit, server-error, and offline states as applicable.
80. Check that stale UI cache does not outlive a mutation. Invalidate/refetch only the relevant query/state according to the existing architecture.
81. Check a successful response has not been mistaken for semantic success when the backend returns a task ID with pending execution.
82. Check task completion is awaited or polled appropriately and the user can identify pending versus completed processing.
83. Check external provider errors propagate to a truthful status rather than being caught and converted into fabricated success.
84. Check any retry operation cannot create duplicate jobs, settings writes, uploads, publications, or cleanup operations.
85. Check the component has no hidden coupling to unapproved Phase 8 watermark branding or unsupported layouts.
86. Cross-reference actual behavior with `PHASE_TRACKER.md`, the relevant approved prompt, and the actual backend route/service. Do not assume draft/archived prompts are mandatory scope.
87. Check related documentation only if it is directly affected by the verified implementation; preserve historical audit evidence.
88. Update the component dossier with actual file paths, symbols, endpoint, backend behavior, test commands, Pass A evidence and Pass B evidence.
89. If a required operation is not present in the current UI, mark it absent and verify whether the approved specification requires it; do not silently invent UI.
90. If a required capability is absent, identify the exact implementation/API/test gap and fix it only when inside approved scope and governance permits.
91. Before any edit, record targeted Git status/diff; after edits, verify unrelated working-tree changes and untracked assets remain untouched.
92. Do not make changes beyond approved Phase 1–7 scope; Phase 8 watermark branding remains deferred unless separately authorized.
93. If this component offers a layout choice, require a real local reference thumbnail for every supported option and verify the output renderer matches it.
94. If this component participates in monitoring/publishing, check destination identity and state synchronization, and obey the central private-upload gate; do not create a second real upload.
95. Never expose secrets, run destructive database operations, publish public/unlisted test videos, or delete user media while verifying this component.
96. Perform Pass A: independently map every acceptance criterion to implementation and test evidence. Record exact paths, symbols, commands and actual results.
97. Perform Pass B independently using alternate evidence; explicitly confirm, contradict or leave uncertain every material Pass A claim.
98. Repair eligible defects and repeat the complete relevant test loop; if governance or safety blocks a fix, record the exact blocker and continue independent work.
99. Final acceptance for `CLIP-05`: every mandatory control in Storage cleanup preview and execute flow must have a real handler/contract, verified backend result, correct UI synchronization, passing relevant test, and independent Pass A/Pass B evidence.
100. Return a concise per-control matrix, exact files changed, tests and results, unresolved issues, and final component verdict. Do not declare PASS when evidence is missing.


---


## Page 4 — Publish (`/publish`)

### Page orchestration prompt

1. Work on Page 4 — Publish (`/publish`) as a page-level integration owner, using the master framework and all child prompts in this section.

2. Discover every actual child component and every interactive control from the current source, accessibility tree, and rendered page where browser inspection is available.

3. Create a route inventory and map each control to the relevant API endpoint, backend route/service, persistence or task path, and acceptance criterion.

4. Execute every child component prompt listed below, then inspect interactions between sibling components, shared state and cross-page navigation.

5. Test loading, empty, success, validation, auth failure, conflict, network failure, server failure and retry states applicable to the page.

6. Use component and integration tests. Run browser/E2E checks where available; label missing browser evidence as NOT VERIFIED.

7. Verify that every layout selection displays a real reference image and that selected layout ID reaches the correct renderer and appears in actual rendered output.

8. For monitoring, trace channel selection → poll → candidate discovery → decision → processing dispatch → persisted job progress → publishing destination → status result.

9. For Publish, verify normal mocked paths first and coordinate with the single central private YouTube upload gate; never create additional live uploads from component tests.

10. After all child components pass, test page-wide interactions, reloading, navigation away/back, shared API cache invalidation, stale response handling and component cleanup.

11. Perform a distinct Page Pass B using alternate evidence and record each finding against Page Pass A.

12. Fix authorized defects and rerun impacted tests until every mandatory page criterion passes or a specific governance/safety/external dependency blocks it.

13. Do not implement the proposed Phase 8 watermark feature. Keep the approved Phase 1–7 scope boundary.

14. Finish with a control-level matrix, endpoint coverage map, actual tests/results, files changed, evidence for both passes and unresolved blockers.


### Independent component prompts — each contains 100 required steps

### PUB-01 — Publish queue list, filters and refresh

**Primary files to discover:** frontend/app/publish/page.tsx and publishing queue APIs  
**Component focus:** Queue cards/rows, status filters, refresh, pagination if present  
**Acceptance focus:** Verify UI shows persisted jobs and destinations, status/time formatting is accurate, refresh does not duplicate/reorder incorrectly, pending and terminal states match backend, and failures have a retryable/diagnostic state.

Copy this complete prompt into the autonomous execution context for this component. Do not execute it in isolation from the master framework.

**100-step component prompt:**
1. Act as the autonomous owner of Publish queue list, filters and refresh. Work only on the actual component discovered in the current checkout, not on an assumed or reconstructed UI.
2. Inspect frontend/app/publish/page.tsx and publishing queue APIs; follow imports and references to identify the real source files, tests, route and backend dependencies.
3. Component inventory: Queue cards/rows, status filters, refresh, pagination if present. Discover the full list from the current UI and source. The list above is a focus guide, not permission to invent missing controls.
4. Acceptance focus: Verify UI shows persisted jobs and destinations, status/time formatting is accurate, refresh does not duplicate/reorder incorrectly, pending and terminal states match backend, and failures have a retryable/diagnostic state.
5. Create or update dossier ID `PUB-01` and link this component to its authoritative Phase/C-series acceptance criterion without redefining phase numbering.
6. Capture current behavior first: record the visible state, control labels, current handler, API call, server response, persisted state and known failure behavior.
7. List every individual button, input, dropdown, link, tab, selector, icon action, modal action and keyboard action in this component; give each a stable child control ID.
8. For every control, specify one positive test, one invalid/error test, one repeated-action/idempotency test where relevant, and one refresh/persistence or cross-page sync test where relevant.
9. Trace every mutation from browser event to API client, backend route, service, persistence/task/external provider and the final returned UI state.
10. Record the precise success assertion and the objective failure condition before changing code; never count a cosmetic animation or toast as proof of backend success.
11. Begin by opening the actual component, its parent, child components, types, API-client methods, and tests; do not trust a previous report without checking the current checkout.
12. List the exact visible controls that belong to this component, including icon-only buttons, links styled as buttons, keyboard shortcuts, toggles, dropdown options, modal actions, and any hidden action revealed by state.
13. For each control, state the requirement and observable success condition before testing it; map each requirement to the approved roadmap item without changing canonical phase numbers.
14. Check whether the control is intentionally non-interactive. If so, it must be semantically non-interactive and cannot imply that an unavailable action will occur.
15. Check accessible name, label/description, role, focusability, keyboard activation, disabled state, focus order, and whether focus returns appropriately after a dialog closes.
16. Trace the real event handler. Reject empty callbacks, console-only callbacks, hard-coded results, no-op links, timer-only simulation, and UI-only state mutation for backend operations.
17. Locate the corresponding API-client method and verify HTTP method, route path, body/query parameters, identifiers, headers/auth, response type, status-code handling, and timeout behavior.
18. Confirm that the route exists in the current backend application and is included under the actual router prefix. Do not infer endpoint existence from a frontend URL string.
19. Inspect backend validation, authorization, ownership checks, service calls, transaction boundaries, queue/task dispatch, and error mapping for the operation.
20. Identify the authoritative persisted record or external response that proves success. Do not use only a toast, button animation, or HTTP 200 as proof of the intended side effect.
21. Check that the frontend consumes the real response and maps returned identifiers/state correctly. Detect hard-coded status strings and mismatched field names.
22. Test the normal successful action using an isolated fixture or safe test record wherever available.
23. Test missing, malformed, stale, or unauthorized identifiers without modifying real user data.
24. Test the expected validation boundary conditions and verify the UI shows a useful message rather than silently dropping the request.
25. Test a server-side failure and confirm no false success indicator appears.
26. Test a network timeout/connection reset and verify the UI does not assume that the backend definitely failed if the outcome may be ambiguous.
27. Test loading indicators and confirm they clear on success, error, cancellation, component unmount, and every supported early return.
28. Test double-click, repeated Enter, quick toggle changes, duplicate network retries, and stale component state for unintended duplicate actions.
29. Check race handling if the action operates on mutable status, queue positions, decisions, settings, uploads, or publishing state.
30. Check that stale/out-of-order responses cannot overwrite a newer state. Use request cancellation, version checks, or existing conventions where needed and approved.
31. Check the response status is translated to the correct UI state, including pending/in-progress, completed, partial failure, failed, cancelled, and conflict states where applicable.
32. Check whether optimistic UI is used. If so, ensure rollback or reconciliation occurs when the backend rejects the change.
33. Check whether the changed state should survive page refresh/reopen; if yes, reload and compare the visible state to the backend-authoritative result.
34. Check whether the state is shared with other pages/components. Trigger the action and inspect every relevant surface for stale data.
35. Check that filters, sorting, selection, pagination, tabs, and the current detail item behave correctly after the operation changes data.
36. Check behavior when the list is empty, the API returns null/partial optional data, a media asset is missing, or a provider is temporarily unavailable.
37. Check timezones, timestamps, duration units, percentages, byte sizes, numeric formatting, and enum labels against backend semantics.
38. Check no credential, OAuth token, API key, signed URL, or private user payload is exposed in visible UI, ordinary logs, test output, or screenshots.
39. Check that test-mode fallbacks or synthetic fixtures can only be activated by the repository-defined trusted test context, never by user-controlled substring or arbitrary request fields.
40. Check the action does not add, restore, expose, or invoke caption/subtitle features. Internal transcription may remain for approved analysis and metadata purposes.
41. Check the action does not route to Ollama or require Ollama environment variables. Preserve approved cloud-hosted models even if their names contain Llama.
42. Check the operation cannot accidentally publish to a source/monitoring channel instead of an explicitly configured destination.
43. Where an action creates a job/task, verify the persisted job ID is retained and Celery dispatch occurs only at the intended transition.
44. Where an action updates a task, verify the backend state transition is valid, durable, and visible on subsequent reads.
45. Where an action creates or deletes a file, verify storage path containment, ownership, retention policy, and cleanup behavior using isolated files only.
46. Where a control selects a layout, verify the selected ID maps to a supported renderer option rather than only changing the visual highlight.
47. Where a control shows a layout thumbnail, verify the reference asset exists in the production build, has the correct accessible text, and truthfully represents output composition.
48. Where the component displays progress, verify it is sourced from authoritative progress/status fields and cannot display completion before the task completes.
49. Where the component refreshes/polls, verify intervals, overlap, cooldown, backoff, and unmount cleanup against the actual code contract.
50. Where external providers are involved, test mocked/sandbox cases first and ensure no accidental external side effect is triggered by an ordinary test.
51. For the private YouTube acceptance upload, do not use this component test to generate another upload. The one real upload is centrally orchestrated and idempotently gated under the master framework.
52. Inspect the relevant unit/component test and add a regression test for each repaired defect where test infrastructure permits.
53. Run the smallest test covering this component first and record the exact command and actual exit result.
54. Run the relevant API/backend integration test where it can be proven safe and isolated.
55. Run the relevant browser/E2E test if available; do not describe static source inspection as a browser test.
56. Collect actual request/response evidence with secrets redacted. Link to the logs or test output that substantiate the result.
57. Compare the user-visible message/status with the actual backend response and persisted state.
58. Conduct Pass A by tracing requirements to implementation and successful tests.
59. Conduct Pass B independently using an alternate path such as persisted state, route registration, event log, task state, rendered output, refresh behavior, or a different test assertion.
60. If Pass A and Pass B disagree, investigate and document the discrepancy; do not average the results or silently pick the favorable one.
61. Classify a failure as UI defect, API contract mismatch, backend behavior defect, persistence defect, concurrency defect, configuration defect, missing test/evidence, or scope ambiguity.
62. Fix only defects within approved Phase 1–7 requirements and only through the governance process required by the freeze rules.
63. Before changing a shared API client, component, schema, backend route, or frozen domain, identify all affected pages and regression tests.
64. Keep the code change minimal and preserve pre-existing Git modifications and untracked files.
65. Never execute blanket Git reset/clean/checkout/restore commands or replace a whole file to make a small repair.
66. After a repair, rerun the failing reproduction, relevant component test, API/backend tests, and affected page regression checks.
67. Independently repeat Pass B after the repair, using evidence distinct from the original fix path where reasonably possible.
68. If the test fails, continue the diagnose/fix/retest loop within scope; if the failure requires unavailable authorization or unsafe operation, mark it blocked and continue unrelated work.
69. Do not stop at the first failed test if the cause is repairable within scope. Do not loop indefinitely if a genuine external or governance blocker exists.
70. Check that test teardown completes and does not silently mask failures; do not change global fixtures unless required and governed.
71. Confirm test DB isolation before any database mutation. Never migrate, drop, reset, or clean the operational clipforge database.
72. Confirm no test publishes an actual video except the one centralized, explicit, private acceptance upload authorized by the user.
73. Confirm no generated test file overwrites existing uploads or outputs and no cleanup task deletes user-owned media.
74. Run TypeScript and lint checks against the changed frontend where possible. Report repository-wide legacy issues separately from new introduced issues.
75. Run the production build after page/component changes and distinguish build output count from the number of user-facing pages.
76. Inspect browser console errors, failed network requests, React warnings, hydration issues, and unhandled promise rejections where browser execution is available.
77. Check responsive layout at narrow and wide viewport sizes, avoiding horizontal overflow, clipped dialogs, invisible controls, and inaccessible hover-only actions.
78. Check error messages are actionable, avoid secrets, and preserve user-entered form data where retry is expected.
79. Check the component handles loading, empty, success, partial-success, validation, unauthorized, not-found, conflict, rate-limit, server-error, and offline states as applicable.
80. Check that stale UI cache does not outlive a mutation. Invalidate/refetch only the relevant query/state according to the existing architecture.
81. Check a successful response has not been mistaken for semantic success when the backend returns a task ID with pending execution.
82. Check task completion is awaited or polled appropriately and the user can identify pending versus completed processing.
83. Check external provider errors propagate to a truthful status rather than being caught and converted into fabricated success.
84. Check any retry operation cannot create duplicate jobs, settings writes, uploads, publications, or cleanup operations.
85. Check the component has no hidden coupling to unapproved Phase 8 watermark branding or unsupported layouts.
86. Cross-reference actual behavior with `PHASE_TRACKER.md`, the relevant approved prompt, and the actual backend route/service. Do not assume draft/archived prompts are mandatory scope.
87. Check related documentation only if it is directly affected by the verified implementation; preserve historical audit evidence.
88. Update the component dossier with actual file paths, symbols, endpoint, backend behavior, test commands, Pass A evidence and Pass B evidence.
89. If a required operation is not present in the current UI, mark it absent and verify whether the approved specification requires it; do not silently invent UI.
90. If a required capability is absent, identify the exact implementation/API/test gap and fix it only when inside approved scope and governance permits.
91. Before any edit, record targeted Git status/diff; after edits, verify unrelated working-tree changes and untracked assets remain untouched.
92. Do not make changes beyond approved Phase 1–7 scope; Phase 8 watermark branding remains deferred unless separately authorized.
93. If this component offers a layout choice, require a real local reference thumbnail for every supported option and verify the output renderer matches it.
94. If this component participates in monitoring/publishing, check destination identity and state synchronization, and obey the central private-upload gate; do not create a second real upload.
95. Never expose secrets, run destructive database operations, publish public/unlisted test videos, or delete user media while verifying this component.
96. Perform Pass A: independently map every acceptance criterion to implementation and test evidence. Record exact paths, symbols, commands and actual results.
97. Perform Pass B independently using alternate evidence; explicitly confirm, contradict or leave uncertain every material Pass A claim.
98. Repair eligible defects and repeat the complete relevant test loop; if governance or safety blocks a fix, record the exact blocker and continue independent work.
99. Final acceptance for `PUB-01`: every mandatory control in Publish queue list, filters and refresh must have a real handler/contract, verified backend result, correct UI synchronization, passing relevant test, and independent Pass A/Pass B evidence.
100. Return a concise per-control matrix, exact files changed, tests and results, unresolved issues, and final component verdict. Do not declare PASS when evidence is missing.


---

### PUB-02 — Cancel and retry controls

**Primary files to discover:** Publishing cancel/retry buttons, API routes and Celery revocation/state transitions  
**Component focus:** Cancel, retry, disabled/loading state, confirmation, terminal/race states  
**Acceptance focus:** Verify correct publication/job ID, proper task revocation/transition, idempotency, race conditions, retry restrictions, UI updates after server response, and authoritative status after reload/polling.

Copy this complete prompt into the autonomous execution context for this component. Do not execute it in isolation from the master framework.

**100-step component prompt:**
1. Act as the autonomous owner of Cancel and retry controls. Work only on the actual component discovered in the current checkout, not on an assumed or reconstructed UI.
2. Inspect Publishing cancel/retry buttons, API routes and Celery revocation/state transitions; follow imports and references to identify the real source files, tests, route and backend dependencies.
3. Component inventory: Cancel, retry, disabled/loading state, confirmation, terminal/race states. Discover the full list from the current UI and source. The list above is a focus guide, not permission to invent missing controls.
4. Acceptance focus: Verify correct publication/job ID, proper task revocation/transition, idempotency, race conditions, retry restrictions, UI updates after server response, and authoritative status after reload/polling.
5. Create or update dossier ID `PUB-02` and link this component to its authoritative Phase/C-series acceptance criterion without redefining phase numbering.
6. Capture current behavior first: record the visible state, control labels, current handler, API call, server response, persisted state and known failure behavior.
7. List every individual button, input, dropdown, link, tab, selector, icon action, modal action and keyboard action in this component; give each a stable child control ID.
8. For every control, specify one positive test, one invalid/error test, one repeated-action/idempotency test where relevant, and one refresh/persistence or cross-page sync test where relevant.
9. Trace every mutation from browser event to API client, backend route, service, persistence/task/external provider and the final returned UI state.
10. Record the precise success assertion and the objective failure condition before changing code; never count a cosmetic animation or toast as proof of backend success.
11. Begin by opening the actual component, its parent, child components, types, API-client methods, and tests; do not trust a previous report without checking the current checkout.
12. List the exact visible controls that belong to this component, including icon-only buttons, links styled as buttons, keyboard shortcuts, toggles, dropdown options, modal actions, and any hidden action revealed by state.
13. For each control, state the requirement and observable success condition before testing it; map each requirement to the approved roadmap item without changing canonical phase numbers.
14. Check whether the control is intentionally non-interactive. If so, it must be semantically non-interactive and cannot imply that an unavailable action will occur.
15. Check accessible name, label/description, role, focusability, keyboard activation, disabled state, focus order, and whether focus returns appropriately after a dialog closes.
16. Trace the real event handler. Reject empty callbacks, console-only callbacks, hard-coded results, no-op links, timer-only simulation, and UI-only state mutation for backend operations.
17. Locate the corresponding API-client method and verify HTTP method, route path, body/query parameters, identifiers, headers/auth, response type, status-code handling, and timeout behavior.
18. Confirm that the route exists in the current backend application and is included under the actual router prefix. Do not infer endpoint existence from a frontend URL string.
19. Inspect backend validation, authorization, ownership checks, service calls, transaction boundaries, queue/task dispatch, and error mapping for the operation.
20. Identify the authoritative persisted record or external response that proves success. Do not use only a toast, button animation, or HTTP 200 as proof of the intended side effect.
21. Check that the frontend consumes the real response and maps returned identifiers/state correctly. Detect hard-coded status strings and mismatched field names.
22. Test the normal successful action using an isolated fixture or safe test record wherever available.
23. Test missing, malformed, stale, or unauthorized identifiers without modifying real user data.
24. Test the expected validation boundary conditions and verify the UI shows a useful message rather than silently dropping the request.
25. Test a server-side failure and confirm no false success indicator appears.
26. Test a network timeout/connection reset and verify the UI does not assume that the backend definitely failed if the outcome may be ambiguous.
27. Test loading indicators and confirm they clear on success, error, cancellation, component unmount, and every supported early return.
28. Test double-click, repeated Enter, quick toggle changes, duplicate network retries, and stale component state for unintended duplicate actions.
29. Check race handling if the action operates on mutable status, queue positions, decisions, settings, uploads, or publishing state.
30. Check that stale/out-of-order responses cannot overwrite a newer state. Use request cancellation, version checks, or existing conventions where needed and approved.
31. Check the response status is translated to the correct UI state, including pending/in-progress, completed, partial failure, failed, cancelled, and conflict states where applicable.
32. Check whether optimistic UI is used. If so, ensure rollback or reconciliation occurs when the backend rejects the change.
33. Check whether the changed state should survive page refresh/reopen; if yes, reload and compare the visible state to the backend-authoritative result.
34. Check whether the state is shared with other pages/components. Trigger the action and inspect every relevant surface for stale data.
35. Check that filters, sorting, selection, pagination, tabs, and the current detail item behave correctly after the operation changes data.
36. Check behavior when the list is empty, the API returns null/partial optional data, a media asset is missing, or a provider is temporarily unavailable.
37. Check timezones, timestamps, duration units, percentages, byte sizes, numeric formatting, and enum labels against backend semantics.
38. Check no credential, OAuth token, API key, signed URL, or private user payload is exposed in visible UI, ordinary logs, test output, or screenshots.
39. Check that test-mode fallbacks or synthetic fixtures can only be activated by the repository-defined trusted test context, never by user-controlled substring or arbitrary request fields.
40. Check the action does not add, restore, expose, or invoke caption/subtitle features. Internal transcription may remain for approved analysis and metadata purposes.
41. Check the action does not route to Ollama or require Ollama environment variables. Preserve approved cloud-hosted models even if their names contain Llama.
42. Check the operation cannot accidentally publish to a source/monitoring channel instead of an explicitly configured destination.
43. Where an action creates a job/task, verify the persisted job ID is retained and Celery dispatch occurs only at the intended transition.
44. Where an action updates a task, verify the backend state transition is valid, durable, and visible on subsequent reads.
45. Where an action creates or deletes a file, verify storage path containment, ownership, retention policy, and cleanup behavior using isolated files only.
46. Where a control selects a layout, verify the selected ID maps to a supported renderer option rather than only changing the visual highlight.
47. Where a control shows a layout thumbnail, verify the reference asset exists in the production build, has the correct accessible text, and truthfully represents output composition.
48. Where the component displays progress, verify it is sourced from authoritative progress/status fields and cannot display completion before the task completes.
49. Where the component refreshes/polls, verify intervals, overlap, cooldown, backoff, and unmount cleanup against the actual code contract.
50. Where external providers are involved, test mocked/sandbox cases first and ensure no accidental external side effect is triggered by an ordinary test.
51. For the private YouTube acceptance upload, do not use this component test to generate another upload. The one real upload is centrally orchestrated and idempotently gated under the master framework.
52. Inspect the relevant unit/component test and add a regression test for each repaired defect where test infrastructure permits.
53. Run the smallest test covering this component first and record the exact command and actual exit result.
54. Run the relevant API/backend integration test where it can be proven safe and isolated.
55. Run the relevant browser/E2E test if available; do not describe static source inspection as a browser test.
56. Collect actual request/response evidence with secrets redacted. Link to the logs or test output that substantiate the result.
57. Compare the user-visible message/status with the actual backend response and persisted state.
58. Conduct Pass A by tracing requirements to implementation and successful tests.
59. Conduct Pass B independently using an alternate path such as persisted state, route registration, event log, task state, rendered output, refresh behavior, or a different test assertion.
60. If Pass A and Pass B disagree, investigate and document the discrepancy; do not average the results or silently pick the favorable one.
61. Classify a failure as UI defect, API contract mismatch, backend behavior defect, persistence defect, concurrency defect, configuration defect, missing test/evidence, or scope ambiguity.
62. Fix only defects within approved Phase 1–7 requirements and only through the governance process required by the freeze rules.
63. Before changing a shared API client, component, schema, backend route, or frozen domain, identify all affected pages and regression tests.
64. Keep the code change minimal and preserve pre-existing Git modifications and untracked files.
65. Never execute blanket Git reset/clean/checkout/restore commands or replace a whole file to make a small repair.
66. After a repair, rerun the failing reproduction, relevant component test, API/backend tests, and affected page regression checks.
67. Independently repeat Pass B after the repair, using evidence distinct from the original fix path where reasonably possible.
68. If the test fails, continue the diagnose/fix/retest loop within scope; if the failure requires unavailable authorization or unsafe operation, mark it blocked and continue unrelated work.
69. Do not stop at the first failed test if the cause is repairable within scope. Do not loop indefinitely if a genuine external or governance blocker exists.
70. Check that test teardown completes and does not silently mask failures; do not change global fixtures unless required and governed.
71. Confirm test DB isolation before any database mutation. Never migrate, drop, reset, or clean the operational clipforge database.
72. Confirm no test publishes an actual video except the one centralized, explicit, private acceptance upload authorized by the user.
73. Confirm no generated test file overwrites existing uploads or outputs and no cleanup task deletes user-owned media.
74. Run TypeScript and lint checks against the changed frontend where possible. Report repository-wide legacy issues separately from new introduced issues.
75. Run the production build after page/component changes and distinguish build output count from the number of user-facing pages.
76. Inspect browser console errors, failed network requests, React warnings, hydration issues, and unhandled promise rejections where browser execution is available.
77. Check responsive layout at narrow and wide viewport sizes, avoiding horizontal overflow, clipped dialogs, invisible controls, and inaccessible hover-only actions.
78. Check error messages are actionable, avoid secrets, and preserve user-entered form data where retry is expected.
79. Check the component handles loading, empty, success, partial-success, validation, unauthorized, not-found, conflict, rate-limit, server-error, and offline states as applicable.
80. Check that stale UI cache does not outlive a mutation. Invalidate/refetch only the relevant query/state according to the existing architecture.
81. Check a successful response has not been mistaken for semantic success when the backend returns a task ID with pending execution.
82. Check task completion is awaited or polled appropriately and the user can identify pending versus completed processing.
83. Check external provider errors propagate to a truthful status rather than being caught and converted into fabricated success.
84. Check any retry operation cannot create duplicate jobs, settings writes, uploads, publications, or cleanup operations.
85. Check the component has no hidden coupling to unapproved Phase 8 watermark branding or unsupported layouts.
86. Cross-reference actual behavior with `PHASE_TRACKER.md`, the relevant approved prompt, and the actual backend route/service. Do not assume draft/archived prompts are mandatory scope.
87. Check related documentation only if it is directly affected by the verified implementation; preserve historical audit evidence.
88. Update the component dossier with actual file paths, symbols, endpoint, backend behavior, test commands, Pass A evidence and Pass B evidence.
89. If a required operation is not present in the current UI, mark it absent and verify whether the approved specification requires it; do not silently invent UI.
90. If a required capability is absent, identify the exact implementation/API/test gap and fix it only when inside approved scope and governance permits.
91. Before any edit, record targeted Git status/diff; after edits, verify unrelated working-tree changes and untracked assets remain untouched.
92. Do not make changes beyond approved Phase 1–7 scope; Phase 8 watermark branding remains deferred unless separately authorized.
93. If this component offers a layout choice, require a real local reference thumbnail for every supported option and verify the output renderer matches it.
94. If this component participates in monitoring/publishing, check destination identity and state synchronization, and obey the central private-upload gate; do not create a second real upload.
95. Never expose secrets, run destructive database operations, publish public/unlisted test videos, or delete user media while verifying this component.
96. Perform Pass A: independently map every acceptance criterion to implementation and test evidence. Record exact paths, symbols, commands and actual results.
97. Perform Pass B independently using alternate evidence; explicitly confirm, contradict or leave uncertain every material Pass A claim.
98. Repair eligible defects and repeat the complete relevant test loop; if governance or safety blocks a fix, record the exact blocker and continue independent work.
99. Final acceptance for `PUB-02`: every mandatory control in Cancel and retry controls must have a real handler/contract, verified backend result, correct UI synchronization, passing relevant test, and independent Pass A/Pass B evidence.
100. Return a concise per-control matrix, exact files changed, tests and results, unresolved issues, and final component verdict. Do not declare PASS when evidence is missing.


---

### PUB-03 — Metadata editor and persistence

**Primary files to discover:** In-place title/description/tags/privacy editor and metadata APIs  
**Component focus:** Edit/save/cancel, validation errors, tags tokenization, privacy selector  
**Acceptance focus:** Verify length boundaries, tokenization, unsaved-change behavior, submit payload, backend persistence, reload persistence, escaped output, error recovery, and that metadata on the final upload matches saved values.

Copy this complete prompt into the autonomous execution context for this component. Do not execute it in isolation from the master framework.

**100-step component prompt:**
1. Act as the autonomous owner of Metadata editor and persistence. Work only on the actual component discovered in the current checkout, not on an assumed or reconstructed UI.
2. Inspect In-place title/description/tags/privacy editor and metadata APIs; follow imports and references to identify the real source files, tests, route and backend dependencies.
3. Component inventory: Edit/save/cancel, validation errors, tags tokenization, privacy selector. Discover the full list from the current UI and source. The list above is a focus guide, not permission to invent missing controls.
4. Acceptance focus: Verify length boundaries, tokenization, unsaved-change behavior, submit payload, backend persistence, reload persistence, escaped output, error recovery, and that metadata on the final upload matches saved values.
5. Create or update dossier ID `PUB-03` and link this component to its authoritative Phase/C-series acceptance criterion without redefining phase numbering.
6. Capture current behavior first: record the visible state, control labels, current handler, API call, server response, persisted state and known failure behavior.
7. List every individual button, input, dropdown, link, tab, selector, icon action, modal action and keyboard action in this component; give each a stable child control ID.
8. For every control, specify one positive test, one invalid/error test, one repeated-action/idempotency test where relevant, and one refresh/persistence or cross-page sync test where relevant.
9. Trace every mutation from browser event to API client, backend route, service, persistence/task/external provider and the final returned UI state.
10. Record the precise success assertion and the objective failure condition before changing code; never count a cosmetic animation or toast as proof of backend success.
11. Begin by opening the actual component, its parent, child components, types, API-client methods, and tests; do not trust a previous report without checking the current checkout.
12. List the exact visible controls that belong to this component, including icon-only buttons, links styled as buttons, keyboard shortcuts, toggles, dropdown options, modal actions, and any hidden action revealed by state.
13. For each control, state the requirement and observable success condition before testing it; map each requirement to the approved roadmap item without changing canonical phase numbers.
14. Check whether the control is intentionally non-interactive. If so, it must be semantically non-interactive and cannot imply that an unavailable action will occur.
15. Check accessible name, label/description, role, focusability, keyboard activation, disabled state, focus order, and whether focus returns appropriately after a dialog closes.
16. Trace the real event handler. Reject empty callbacks, console-only callbacks, hard-coded results, no-op links, timer-only simulation, and UI-only state mutation for backend operations.
17. Locate the corresponding API-client method and verify HTTP method, route path, body/query parameters, identifiers, headers/auth, response type, status-code handling, and timeout behavior.
18. Confirm that the route exists in the current backend application and is included under the actual router prefix. Do not infer endpoint existence from a frontend URL string.
19. Inspect backend validation, authorization, ownership checks, service calls, transaction boundaries, queue/task dispatch, and error mapping for the operation.
20. Identify the authoritative persisted record or external response that proves success. Do not use only a toast, button animation, or HTTP 200 as proof of the intended side effect.
21. Check that the frontend consumes the real response and maps returned identifiers/state correctly. Detect hard-coded status strings and mismatched field names.
22. Test the normal successful action using an isolated fixture or safe test record wherever available.
23. Test missing, malformed, stale, or unauthorized identifiers without modifying real user data.
24. Test the expected validation boundary conditions and verify the UI shows a useful message rather than silently dropping the request.
25. Test a server-side failure and confirm no false success indicator appears.
26. Test a network timeout/connection reset and verify the UI does not assume that the backend definitely failed if the outcome may be ambiguous.
27. Test loading indicators and confirm they clear on success, error, cancellation, component unmount, and every supported early return.
28. Test double-click, repeated Enter, quick toggle changes, duplicate network retries, and stale component state for unintended duplicate actions.
29. Check race handling if the action operates on mutable status, queue positions, decisions, settings, uploads, or publishing state.
30. Check that stale/out-of-order responses cannot overwrite a newer state. Use request cancellation, version checks, or existing conventions where needed and approved.
31. Check the response status is translated to the correct UI state, including pending/in-progress, completed, partial failure, failed, cancelled, and conflict states where applicable.
32. Check whether optimistic UI is used. If so, ensure rollback or reconciliation occurs when the backend rejects the change.
33. Check whether the changed state should survive page refresh/reopen; if yes, reload and compare the visible state to the backend-authoritative result.
34. Check whether the state is shared with other pages/components. Trigger the action and inspect every relevant surface for stale data.
35. Check that filters, sorting, selection, pagination, tabs, and the current detail item behave correctly after the operation changes data.
36. Check behavior when the list is empty, the API returns null/partial optional data, a media asset is missing, or a provider is temporarily unavailable.
37. Check timezones, timestamps, duration units, percentages, byte sizes, numeric formatting, and enum labels against backend semantics.
38. Check no credential, OAuth token, API key, signed URL, or private user payload is exposed in visible UI, ordinary logs, test output, or screenshots.
39. Check that test-mode fallbacks or synthetic fixtures can only be activated by the repository-defined trusted test context, never by user-controlled substring or arbitrary request fields.
40. Check the action does not add, restore, expose, or invoke caption/subtitle features. Internal transcription may remain for approved analysis and metadata purposes.
41. Check the action does not route to Ollama or require Ollama environment variables. Preserve approved cloud-hosted models even if their names contain Llama.
42. Check the operation cannot accidentally publish to a source/monitoring channel instead of an explicitly configured destination.
43. Where an action creates a job/task, verify the persisted job ID is retained and Celery dispatch occurs only at the intended transition.
44. Where an action updates a task, verify the backend state transition is valid, durable, and visible on subsequent reads.
45. Where an action creates or deletes a file, verify storage path containment, ownership, retention policy, and cleanup behavior using isolated files only.
46. Where a control selects a layout, verify the selected ID maps to a supported renderer option rather than only changing the visual highlight.
47. Where a control shows a layout thumbnail, verify the reference asset exists in the production build, has the correct accessible text, and truthfully represents output composition.
48. Where the component displays progress, verify it is sourced from authoritative progress/status fields and cannot display completion before the task completes.
49. Where the component refreshes/polls, verify intervals, overlap, cooldown, backoff, and unmount cleanup against the actual code contract.
50. Where external providers are involved, test mocked/sandbox cases first and ensure no accidental external side effect is triggered by an ordinary test.
51. For the private YouTube acceptance upload, do not use this component test to generate another upload. The one real upload is centrally orchestrated and idempotently gated under the master framework.
52. Inspect the relevant unit/component test and add a regression test for each repaired defect where test infrastructure permits.
53. Run the smallest test covering this component first and record the exact command and actual exit result.
54. Run the relevant API/backend integration test where it can be proven safe and isolated.
55. Run the relevant browser/E2E test if available; do not describe static source inspection as a browser test.
56. Collect actual request/response evidence with secrets redacted. Link to the logs or test output that substantiate the result.
57. Compare the user-visible message/status with the actual backend response and persisted state.
58. Conduct Pass A by tracing requirements to implementation and successful tests.
59. Conduct Pass B independently using an alternate path such as persisted state, route registration, event log, task state, rendered output, refresh behavior, or a different test assertion.
60. If Pass A and Pass B disagree, investigate and document the discrepancy; do not average the results or silently pick the favorable one.
61. Classify a failure as UI defect, API contract mismatch, backend behavior defect, persistence defect, concurrency defect, configuration defect, missing test/evidence, or scope ambiguity.
62. Fix only defects within approved Phase 1–7 requirements and only through the governance process required by the freeze rules.
63. Before changing a shared API client, component, schema, backend route, or frozen domain, identify all affected pages and regression tests.
64. Keep the code change minimal and preserve pre-existing Git modifications and untracked files.
65. Never execute blanket Git reset/clean/checkout/restore commands or replace a whole file to make a small repair.
66. After a repair, rerun the failing reproduction, relevant component test, API/backend tests, and affected page regression checks.
67. Independently repeat Pass B after the repair, using evidence distinct from the original fix path where reasonably possible.
68. If the test fails, continue the diagnose/fix/retest loop within scope; if the failure requires unavailable authorization or unsafe operation, mark it blocked and continue unrelated work.
69. Do not stop at the first failed test if the cause is repairable within scope. Do not loop indefinitely if a genuine external or governance blocker exists.
70. Check that test teardown completes and does not silently mask failures; do not change global fixtures unless required and governed.
71. Confirm test DB isolation before any database mutation. Never migrate, drop, reset, or clean the operational clipforge database.
72. Confirm no test publishes an actual video except the one centralized, explicit, private acceptance upload authorized by the user.
73. Confirm no generated test file overwrites existing uploads or outputs and no cleanup task deletes user-owned media.
74. Run TypeScript and lint checks against the changed frontend where possible. Report repository-wide legacy issues separately from new introduced issues.
75. Run the production build after page/component changes and distinguish build output count from the number of user-facing pages.
76. Inspect browser console errors, failed network requests, React warnings, hydration issues, and unhandled promise rejections where browser execution is available.
77. Check responsive layout at narrow and wide viewport sizes, avoiding horizontal overflow, clipped dialogs, invisible controls, and inaccessible hover-only actions.
78. Check error messages are actionable, avoid secrets, and preserve user-entered form data where retry is expected.
79. Check the component handles loading, empty, success, partial-success, validation, unauthorized, not-found, conflict, rate-limit, server-error, and offline states as applicable.
80. Check that stale UI cache does not outlive a mutation. Invalidate/refetch only the relevant query/state according to the existing architecture.
81. Check a successful response has not been mistaken for semantic success when the backend returns a task ID with pending execution.
82. Check task completion is awaited or polled appropriately and the user can identify pending versus completed processing.
83. Check external provider errors propagate to a truthful status rather than being caught and converted into fabricated success.
84. Check any retry operation cannot create duplicate jobs, settings writes, uploads, publications, or cleanup operations.
85. Check the component has no hidden coupling to unapproved Phase 8 watermark branding or unsupported layouts.
86. Cross-reference actual behavior with `PHASE_TRACKER.md`, the relevant approved prompt, and the actual backend route/service. Do not assume draft/archived prompts are mandatory scope.
87. Check related documentation only if it is directly affected by the verified implementation; preserve historical audit evidence.
88. Update the component dossier with actual file paths, symbols, endpoint, backend behavior, test commands, Pass A evidence and Pass B evidence.
89. If a required operation is not present in the current UI, mark it absent and verify whether the approved specification requires it; do not silently invent UI.
90. If a required capability is absent, identify the exact implementation/API/test gap and fix it only when inside approved scope and governance permits.
91. Before any edit, record targeted Git status/diff; after edits, verify unrelated working-tree changes and untracked assets remain untouched.
92. Do not make changes beyond approved Phase 1–7 scope; Phase 8 watermark branding remains deferred unless separately authorized.
93. If this component offers a layout choice, require a real local reference thumbnail for every supported option and verify the output renderer matches it.
94. If this component participates in monitoring/publishing, check destination identity and state synchronization, and obey the central private-upload gate; do not create a second real upload.
95. Never expose secrets, run destructive database operations, publish public/unlisted test videos, or delete user media while verifying this component.
96. Perform Pass A: independently map every acceptance criterion to implementation and test evidence. Record exact paths, symbols, commands and actual results.
97. Perform Pass B independently using alternate evidence; explicitly confirm, contradict or leave uncertain every material Pass A claim.
98. Repair eligible defects and repeat the complete relevant test loop; if governance or safety blocks a fix, record the exact blocker and continue independent work.
99. Final acceptance for `PUB-03`: every mandatory control in Metadata editor and persistence must have a real handler/contract, verified backend result, correct UI synchronization, passing relevant test, and independent Pass A/Pass B evidence.
100. Return a concise per-control matrix, exact files changed, tests and results, unresolved issues, and final component verdict. Do not declare PASS when evidence is missing.


---

### PUB-04 — Destination selector, schedule and publish action

**Primary files to discover:** Publish destination chooser/scheduler/publish endpoint  
**Component focus:** Destination cards/dropdown, schedule/time controls, publish-now action where present  
**Acceptance focus:** Verify source channels cannot be accidentally selected as publishing destinations, exact destination identity is carried through jobs, schedule/timezone validations are correct, private visibility is honored for the authorized test, and duplicate submissions are blocked.

Copy this complete prompt into the autonomous execution context for this component. Do not execute it in isolation from the master framework.

**100-step component prompt:**
1. Act as the autonomous owner of Destination selector, schedule and publish action. Work only on the actual component discovered in the current checkout, not on an assumed or reconstructed UI.
2. Inspect Publish destination chooser/scheduler/publish endpoint; follow imports and references to identify the real source files, tests, route and backend dependencies.
3. Component inventory: Destination cards/dropdown, schedule/time controls, publish-now action where present. Discover the full list from the current UI and source. The list above is a focus guide, not permission to invent missing controls.
4. Acceptance focus: Verify source channels cannot be accidentally selected as publishing destinations, exact destination identity is carried through jobs, schedule/timezone validations are correct, private visibility is honored for the authorized test, and duplicate submissions are blocked.
5. Create or update dossier ID `PUB-04` and link this component to its authoritative Phase/C-series acceptance criterion without redefining phase numbering.
6. Capture current behavior first: record the visible state, control labels, current handler, API call, server response, persisted state and known failure behavior.
7. List every individual button, input, dropdown, link, tab, selector, icon action, modal action and keyboard action in this component; give each a stable child control ID.
8. For every control, specify one positive test, one invalid/error test, one repeated-action/idempotency test where relevant, and one refresh/persistence or cross-page sync test where relevant.
9. Trace every mutation from browser event to API client, backend route, service, persistence/task/external provider and the final returned UI state.
10. Record the precise success assertion and the objective failure condition before changing code; never count a cosmetic animation or toast as proof of backend success.
11. Begin by opening the actual component, its parent, child components, types, API-client methods, and tests; do not trust a previous report without checking the current checkout.
12. List the exact visible controls that belong to this component, including icon-only buttons, links styled as buttons, keyboard shortcuts, toggles, dropdown options, modal actions, and any hidden action revealed by state.
13. For each control, state the requirement and observable success condition before testing it; map each requirement to the approved roadmap item without changing canonical phase numbers.
14. Check whether the control is intentionally non-interactive. If so, it must be semantically non-interactive and cannot imply that an unavailable action will occur.
15. Check accessible name, label/description, role, focusability, keyboard activation, disabled state, focus order, and whether focus returns appropriately after a dialog closes.
16. Trace the real event handler. Reject empty callbacks, console-only callbacks, hard-coded results, no-op links, timer-only simulation, and UI-only state mutation for backend operations.
17. Locate the corresponding API-client method and verify HTTP method, route path, body/query parameters, identifiers, headers/auth, response type, status-code handling, and timeout behavior.
18. Confirm that the route exists in the current backend application and is included under the actual router prefix. Do not infer endpoint existence from a frontend URL string.
19. Inspect backend validation, authorization, ownership checks, service calls, transaction boundaries, queue/task dispatch, and error mapping for the operation.
20. Identify the authoritative persisted record or external response that proves success. Do not use only a toast, button animation, or HTTP 200 as proof of the intended side effect.
21. Check that the frontend consumes the real response and maps returned identifiers/state correctly. Detect hard-coded status strings and mismatched field names.
22. Test the normal successful action using an isolated fixture or safe test record wherever available.
23. Test missing, malformed, stale, or unauthorized identifiers without modifying real user data.
24. Test the expected validation boundary conditions and verify the UI shows a useful message rather than silently dropping the request.
25. Test a server-side failure and confirm no false success indicator appears.
26. Test a network timeout/connection reset and verify the UI does not assume that the backend definitely failed if the outcome may be ambiguous.
27. Test loading indicators and confirm they clear on success, error, cancellation, component unmount, and every supported early return.
28. Test double-click, repeated Enter, quick toggle changes, duplicate network retries, and stale component state for unintended duplicate actions.
29. Check race handling if the action operates on mutable status, queue positions, decisions, settings, uploads, or publishing state.
30. Check that stale/out-of-order responses cannot overwrite a newer state. Use request cancellation, version checks, or existing conventions where needed and approved.
31. Check the response status is translated to the correct UI state, including pending/in-progress, completed, partial failure, failed, cancelled, and conflict states where applicable.
32. Check whether optimistic UI is used. If so, ensure rollback or reconciliation occurs when the backend rejects the change.
33. Check whether the changed state should survive page refresh/reopen; if yes, reload and compare the visible state to the backend-authoritative result.
34. Check whether the state is shared with other pages/components. Trigger the action and inspect every relevant surface for stale data.
35. Check that filters, sorting, selection, pagination, tabs, and the current detail item behave correctly after the operation changes data.
36. Check behavior when the list is empty, the API returns null/partial optional data, a media asset is missing, or a provider is temporarily unavailable.
37. Check timezones, timestamps, duration units, percentages, byte sizes, numeric formatting, and enum labels against backend semantics.
38. Check no credential, OAuth token, API key, signed URL, or private user payload is exposed in visible UI, ordinary logs, test output, or screenshots.
39. Check that test-mode fallbacks or synthetic fixtures can only be activated by the repository-defined trusted test context, never by user-controlled substring or arbitrary request fields.
40. Check the action does not add, restore, expose, or invoke caption/subtitle features. Internal transcription may remain for approved analysis and metadata purposes.
41. Check the action does not route to Ollama or require Ollama environment variables. Preserve approved cloud-hosted models even if their names contain Llama.
42. Check the operation cannot accidentally publish to a source/monitoring channel instead of an explicitly configured destination.
43. Where an action creates a job/task, verify the persisted job ID is retained and Celery dispatch occurs only at the intended transition.
44. Where an action updates a task, verify the backend state transition is valid, durable, and visible on subsequent reads.
45. Where an action creates or deletes a file, verify storage path containment, ownership, retention policy, and cleanup behavior using isolated files only.
46. Where a control selects a layout, verify the selected ID maps to a supported renderer option rather than only changing the visual highlight.
47. Where a control shows a layout thumbnail, verify the reference asset exists in the production build, has the correct accessible text, and truthfully represents output composition.
48. Where the component displays progress, verify it is sourced from authoritative progress/status fields and cannot display completion before the task completes.
49. Where the component refreshes/polls, verify intervals, overlap, cooldown, backoff, and unmount cleanup against the actual code contract.
50. Where external providers are involved, test mocked/sandbox cases first and ensure no accidental external side effect is triggered by an ordinary test.
51. For the private YouTube acceptance upload, do not use this component test to generate another upload. The one real upload is centrally orchestrated and idempotently gated under the master framework.
52. Inspect the relevant unit/component test and add a regression test for each repaired defect where test infrastructure permits.
53. Run the smallest test covering this component first and record the exact command and actual exit result.
54. Run the relevant API/backend integration test where it can be proven safe and isolated.
55. Run the relevant browser/E2E test if available; do not describe static source inspection as a browser test.
56. Collect actual request/response evidence with secrets redacted. Link to the logs or test output that substantiate the result.
57. Compare the user-visible message/status with the actual backend response and persisted state.
58. Conduct Pass A by tracing requirements to implementation and successful tests.
59. Conduct Pass B independently using an alternate path such as persisted state, route registration, event log, task state, rendered output, refresh behavior, or a different test assertion.
60. If Pass A and Pass B disagree, investigate and document the discrepancy; do not average the results or silently pick the favorable one.
61. Classify a failure as UI defect, API contract mismatch, backend behavior defect, persistence defect, concurrency defect, configuration defect, missing test/evidence, or scope ambiguity.
62. Fix only defects within approved Phase 1–7 requirements and only through the governance process required by the freeze rules.
63. Before changing a shared API client, component, schema, backend route, or frozen domain, identify all affected pages and regression tests.
64. Keep the code change minimal and preserve pre-existing Git modifications and untracked files.
65. Never execute blanket Git reset/clean/checkout/restore commands or replace a whole file to make a small repair.
66. After a repair, rerun the failing reproduction, relevant component test, API/backend tests, and affected page regression checks.
67. Independently repeat Pass B after the repair, using evidence distinct from the original fix path where reasonably possible.
68. If the test fails, continue the diagnose/fix/retest loop within scope; if the failure requires unavailable authorization or unsafe operation, mark it blocked and continue unrelated work.
69. Do not stop at the first failed test if the cause is repairable within scope. Do not loop indefinitely if a genuine external or governance blocker exists.
70. Check that test teardown completes and does not silently mask failures; do not change global fixtures unless required and governed.
71. Confirm test DB isolation before any database mutation. Never migrate, drop, reset, or clean the operational clipforge database.
72. Confirm no test publishes an actual video except the one centralized, explicit, private acceptance upload authorized by the user.
73. Confirm no generated test file overwrites existing uploads or outputs and no cleanup task deletes user-owned media.
74. Run TypeScript and lint checks against the changed frontend where possible. Report repository-wide legacy issues separately from new introduced issues.
75. Run the production build after page/component changes and distinguish build output count from the number of user-facing pages.
76. Inspect browser console errors, failed network requests, React warnings, hydration issues, and unhandled promise rejections where browser execution is available.
77. Check responsive layout at narrow and wide viewport sizes, avoiding horizontal overflow, clipped dialogs, invisible controls, and inaccessible hover-only actions.
78. Check error messages are actionable, avoid secrets, and preserve user-entered form data where retry is expected.
79. Check the component handles loading, empty, success, partial-success, validation, unauthorized, not-found, conflict, rate-limit, server-error, and offline states as applicable.
80. Check that stale UI cache does not outlive a mutation. Invalidate/refetch only the relevant query/state according to the existing architecture.
81. Check a successful response has not been mistaken for semantic success when the backend returns a task ID with pending execution.
82. Check task completion is awaited or polled appropriately and the user can identify pending versus completed processing.
83. Check external provider errors propagate to a truthful status rather than being caught and converted into fabricated success.
84. Check any retry operation cannot create duplicate jobs, settings writes, uploads, publications, or cleanup operations.
85. Check the component has no hidden coupling to unapproved Phase 8 watermark branding or unsupported layouts.
86. Cross-reference actual behavior with `PHASE_TRACKER.md`, the relevant approved prompt, and the actual backend route/service. Do not assume draft/archived prompts are mandatory scope.
87. Check related documentation only if it is directly affected by the verified implementation; preserve historical audit evidence.
88. Update the component dossier with actual file paths, symbols, endpoint, backend behavior, test commands, Pass A evidence and Pass B evidence.
89. If a required operation is not present in the current UI, mark it absent and verify whether the approved specification requires it; do not silently invent UI.
90. If a required capability is absent, identify the exact implementation/API/test gap and fix it only when inside approved scope and governance permits.
91. Before any edit, record targeted Git status/diff; after edits, verify unrelated working-tree changes and untracked assets remain untouched.
92. Do not make changes beyond approved Phase 1–7 scope; Phase 8 watermark branding remains deferred unless separately authorized.
93. If this component offers a layout choice, require a real local reference thumbnail for every supported option and verify the output renderer matches it.
94. If this component participates in monitoring/publishing, check destination identity and state synchronization, and obey the central private-upload gate; do not create a second real upload.
95. Never expose secrets, run destructive database operations, publish public/unlisted test videos, or delete user media while verifying this component.
96. Perform Pass A: independently map every acceptance criterion to implementation and test evidence. Record exact paths, symbols, commands and actual results.
97. Perform Pass B independently using alternate evidence; explicitly confirm, contradict or leave uncertain every material Pass A claim.
98. Repair eligible defects and repeat the complete relevant test loop; if governance or safety blocks a fix, record the exact blocker and continue independent work.
99. Final acceptance for `PUB-04`: every mandatory control in Destination selector, schedule and publish action must have a real handler/contract, verified backend result, correct UI synchronization, passing relevant test, and independent Pass A/Pass B evidence.
100. Return a concise per-control matrix, exact files changed, tests and results, unresolved issues, and final component verdict. Do not declare PASS when evidence is missing.


---

### PUB-05 — Publication result, error and status synchronization

**Primary files to discover:** Publish result links/details, backend status APIs and task updates  
**Component focus:** Video ID/link, upload/publish states, failure detail, refresh/polling  
**Acceptance focus:** Verify local job status corresponds to provider response, external ID is retained, privacy is verifiable, errors are not swallowed, retries are safe, polling is consistent, and UI does not claim published before backend/provider confirmation.

Copy this complete prompt into the autonomous execution context for this component. Do not execute it in isolation from the master framework.

**100-step component prompt:**
1. Act as the autonomous owner of Publication result, error and status synchronization. Work only on the actual component discovered in the current checkout, not on an assumed or reconstructed UI.
2. Inspect Publish result links/details, backend status APIs and task updates; follow imports and references to identify the real source files, tests, route and backend dependencies.
3. Component inventory: Video ID/link, upload/publish states, failure detail, refresh/polling. Discover the full list from the current UI and source. The list above is a focus guide, not permission to invent missing controls.
4. Acceptance focus: Verify local job status corresponds to provider response, external ID is retained, privacy is verifiable, errors are not swallowed, retries are safe, polling is consistent, and UI does not claim published before backend/provider confirmation.
5. Create or update dossier ID `PUB-05` and link this component to its authoritative Phase/C-series acceptance criterion without redefining phase numbering.
6. Capture current behavior first: record the visible state, control labels, current handler, API call, server response, persisted state and known failure behavior.
7. List every individual button, input, dropdown, link, tab, selector, icon action, modal action and keyboard action in this component; give each a stable child control ID.
8. For every control, specify one positive test, one invalid/error test, one repeated-action/idempotency test where relevant, and one refresh/persistence or cross-page sync test where relevant.
9. Trace every mutation from browser event to API client, backend route, service, persistence/task/external provider and the final returned UI state.
10. Record the precise success assertion and the objective failure condition before changing code; never count a cosmetic animation or toast as proof of backend success.
11. Begin by opening the actual component, its parent, child components, types, API-client methods, and tests; do not trust a previous report without checking the current checkout.
12. List the exact visible controls that belong to this component, including icon-only buttons, links styled as buttons, keyboard shortcuts, toggles, dropdown options, modal actions, and any hidden action revealed by state.
13. For each control, state the requirement and observable success condition before testing it; map each requirement to the approved roadmap item without changing canonical phase numbers.
14. Check whether the control is intentionally non-interactive. If so, it must be semantically non-interactive and cannot imply that an unavailable action will occur.
15. Check accessible name, label/description, role, focusability, keyboard activation, disabled state, focus order, and whether focus returns appropriately after a dialog closes.
16. Trace the real event handler. Reject empty callbacks, console-only callbacks, hard-coded results, no-op links, timer-only simulation, and UI-only state mutation for backend operations.
17. Locate the corresponding API-client method and verify HTTP method, route path, body/query parameters, identifiers, headers/auth, response type, status-code handling, and timeout behavior.
18. Confirm that the route exists in the current backend application and is included under the actual router prefix. Do not infer endpoint existence from a frontend URL string.
19. Inspect backend validation, authorization, ownership checks, service calls, transaction boundaries, queue/task dispatch, and error mapping for the operation.
20. Identify the authoritative persisted record or external response that proves success. Do not use only a toast, button animation, or HTTP 200 as proof of the intended side effect.
21. Check that the frontend consumes the real response and maps returned identifiers/state correctly. Detect hard-coded status strings and mismatched field names.
22. Test the normal successful action using an isolated fixture or safe test record wherever available.
23. Test missing, malformed, stale, or unauthorized identifiers without modifying real user data.
24. Test the expected validation boundary conditions and verify the UI shows a useful message rather than silently dropping the request.
25. Test a server-side failure and confirm no false success indicator appears.
26. Test a network timeout/connection reset and verify the UI does not assume that the backend definitely failed if the outcome may be ambiguous.
27. Test loading indicators and confirm they clear on success, error, cancellation, component unmount, and every supported early return.
28. Test double-click, repeated Enter, quick toggle changes, duplicate network retries, and stale component state for unintended duplicate actions.
29. Check race handling if the action operates on mutable status, queue positions, decisions, settings, uploads, or publishing state.
30. Check that stale/out-of-order responses cannot overwrite a newer state. Use request cancellation, version checks, or existing conventions where needed and approved.
31. Check the response status is translated to the correct UI state, including pending/in-progress, completed, partial failure, failed, cancelled, and conflict states where applicable.
32. Check whether optimistic UI is used. If so, ensure rollback or reconciliation occurs when the backend rejects the change.
33. Check whether the changed state should survive page refresh/reopen; if yes, reload and compare the visible state to the backend-authoritative result.
34. Check whether the state is shared with other pages/components. Trigger the action and inspect every relevant surface for stale data.
35. Check that filters, sorting, selection, pagination, tabs, and the current detail item behave correctly after the operation changes data.
36. Check behavior when the list is empty, the API returns null/partial optional data, a media asset is missing, or a provider is temporarily unavailable.
37. Check timezones, timestamps, duration units, percentages, byte sizes, numeric formatting, and enum labels against backend semantics.
38. Check no credential, OAuth token, API key, signed URL, or private user payload is exposed in visible UI, ordinary logs, test output, or screenshots.
39. Check that test-mode fallbacks or synthetic fixtures can only be activated by the repository-defined trusted test context, never by user-controlled substring or arbitrary request fields.
40. Check the action does not add, restore, expose, or invoke caption/subtitle features. Internal transcription may remain for approved analysis and metadata purposes.
41. Check the action does not route to Ollama or require Ollama environment variables. Preserve approved cloud-hosted models even if their names contain Llama.
42. Check the operation cannot accidentally publish to a source/monitoring channel instead of an explicitly configured destination.
43. Where an action creates a job/task, verify the persisted job ID is retained and Celery dispatch occurs only at the intended transition.
44. Where an action updates a task, verify the backend state transition is valid, durable, and visible on subsequent reads.
45. Where an action creates or deletes a file, verify storage path containment, ownership, retention policy, and cleanup behavior using isolated files only.
46. Where a control selects a layout, verify the selected ID maps to a supported renderer option rather than only changing the visual highlight.
47. Where a control shows a layout thumbnail, verify the reference asset exists in the production build, has the correct accessible text, and truthfully represents output composition.
48. Where the component displays progress, verify it is sourced from authoritative progress/status fields and cannot display completion before the task completes.
49. Where the component refreshes/polls, verify intervals, overlap, cooldown, backoff, and unmount cleanup against the actual code contract.
50. Where external providers are involved, test mocked/sandbox cases first and ensure no accidental external side effect is triggered by an ordinary test.
51. For the private YouTube acceptance upload, do not use this component test to generate another upload. The one real upload is centrally orchestrated and idempotently gated under the master framework.
52. Inspect the relevant unit/component test and add a regression test for each repaired defect where test infrastructure permits.
53. Run the smallest test covering this component first and record the exact command and actual exit result.
54. Run the relevant API/backend integration test where it can be proven safe and isolated.
55. Run the relevant browser/E2E test if available; do not describe static source inspection as a browser test.
56. Collect actual request/response evidence with secrets redacted. Link to the logs or test output that substantiate the result.
57. Compare the user-visible message/status with the actual backend response and persisted state.
58. Conduct Pass A by tracing requirements to implementation and successful tests.
59. Conduct Pass B independently using an alternate path such as persisted state, route registration, event log, task state, rendered output, refresh behavior, or a different test assertion.
60. If Pass A and Pass B disagree, investigate and document the discrepancy; do not average the results or silently pick the favorable one.
61. Classify a failure as UI defect, API contract mismatch, backend behavior defect, persistence defect, concurrency defect, configuration defect, missing test/evidence, or scope ambiguity.
62. Fix only defects within approved Phase 1–7 requirements and only through the governance process required by the freeze rules.
63. Before changing a shared API client, component, schema, backend route, or frozen domain, identify all affected pages and regression tests.
64. Keep the code change minimal and preserve pre-existing Git modifications and untracked files.
65. Never execute blanket Git reset/clean/checkout/restore commands or replace a whole file to make a small repair.
66. After a repair, rerun the failing reproduction, relevant component test, API/backend tests, and affected page regression checks.
67. Independently repeat Pass B after the repair, using evidence distinct from the original fix path where reasonably possible.
68. If the test fails, continue the diagnose/fix/retest loop within scope; if the failure requires unavailable authorization or unsafe operation, mark it blocked and continue unrelated work.
69. Do not stop at the first failed test if the cause is repairable within scope. Do not loop indefinitely if a genuine external or governance blocker exists.
70. Check that test teardown completes and does not silently mask failures; do not change global fixtures unless required and governed.
71. Confirm test DB isolation before any database mutation. Never migrate, drop, reset, or clean the operational clipforge database.
72. Confirm no test publishes an actual video except the one centralized, explicit, private acceptance upload authorized by the user.
73. Confirm no generated test file overwrites existing uploads or outputs and no cleanup task deletes user-owned media.
74. Run TypeScript and lint checks against the changed frontend where possible. Report repository-wide legacy issues separately from new introduced issues.
75. Run the production build after page/component changes and distinguish build output count from the number of user-facing pages.
76. Inspect browser console errors, failed network requests, React warnings, hydration issues, and unhandled promise rejections where browser execution is available.
77. Check responsive layout at narrow and wide viewport sizes, avoiding horizontal overflow, clipped dialogs, invisible controls, and inaccessible hover-only actions.
78. Check error messages are actionable, avoid secrets, and preserve user-entered form data where retry is expected.
79. Check the component handles loading, empty, success, partial-success, validation, unauthorized, not-found, conflict, rate-limit, server-error, and offline states as applicable.
80. Check that stale UI cache does not outlive a mutation. Invalidate/refetch only the relevant query/state according to the existing architecture.
81. Check a successful response has not been mistaken for semantic success when the backend returns a task ID with pending execution.
82. Check task completion is awaited or polled appropriately and the user can identify pending versus completed processing.
83. Check external provider errors propagate to a truthful status rather than being caught and converted into fabricated success.
84. Check any retry operation cannot create duplicate jobs, settings writes, uploads, publications, or cleanup operations.
85. Check the component has no hidden coupling to unapproved Phase 8 watermark branding or unsupported layouts.
86. Cross-reference actual behavior with `PHASE_TRACKER.md`, the relevant approved prompt, and the actual backend route/service. Do not assume draft/archived prompts are mandatory scope.
87. Check related documentation only if it is directly affected by the verified implementation; preserve historical audit evidence.
88. Update the component dossier with actual file paths, symbols, endpoint, backend behavior, test commands, Pass A evidence and Pass B evidence.
89. If a required operation is not present in the current UI, mark it absent and verify whether the approved specification requires it; do not silently invent UI.
90. If a required capability is absent, identify the exact implementation/API/test gap and fix it only when inside approved scope and governance permits.
91. Before any edit, record targeted Git status/diff; after edits, verify unrelated working-tree changes and untracked assets remain untouched.
92. Do not make changes beyond approved Phase 1–7 scope; Phase 8 watermark branding remains deferred unless separately authorized.
93. If this component offers a layout choice, require a real local reference thumbnail for every supported option and verify the output renderer matches it.
94. If this component participates in monitoring/publishing, check destination identity and state synchronization, and obey the central private-upload gate; do not create a second real upload.
95. Never expose secrets, run destructive database operations, publish public/unlisted test videos, or delete user media while verifying this component.
96. Perform Pass A: independently map every acceptance criterion to implementation and test evidence. Record exact paths, symbols, commands and actual results.
97. Perform Pass B independently using alternate evidence; explicitly confirm, contradict or leave uncertain every material Pass A claim.
98. Repair eligible defects and repeat the complete relevant test loop; if governance or safety blocks a fix, record the exact blocker and continue independent work.
99. Final acceptance for `PUB-05`: every mandatory control in Publication result, error and status synchronization must have a real handler/contract, verified backend result, correct UI synchronization, passing relevant test, and independent Pass A/Pass B evidence.
100. Return a concise per-control matrix, exact files changed, tests and results, unresolved issues, and final component verdict. Do not declare PASS when evidence is missing.


---


## Page 5 — Analytics (`/analytics`)

### Page orchestration prompt

1. Work on Page 5 — Analytics (`/analytics`) as a page-level integration owner, using the master framework and all child prompts in this section.

2. Discover every actual child component and every interactive control from the current source, accessibility tree, and rendered page where browser inspection is available.

3. Create a route inventory and map each control to the relevant API endpoint, backend route/service, persistence or task path, and acceptance criterion.

4. Execute every child component prompt listed below, then inspect interactions between sibling components, shared state and cross-page navigation.

5. Test loading, empty, success, validation, auth failure, conflict, network failure, server failure and retry states applicable to the page.

6. Use component and integration tests. Run browser/E2E checks where available; label missing browser evidence as NOT VERIFIED.

7. Verify that every layout selection displays a real reference image and that selected layout ID reaches the correct renderer and appears in actual rendered output.

8. For monitoring, trace channel selection → poll → candidate discovery → decision → processing dispatch → persisted job progress → publishing destination → status result.

9. For Publish, verify normal mocked paths first and coordinate with the single central private YouTube upload gate; never create additional live uploads from component tests.

10. After all child components pass, test page-wide interactions, reloading, navigation away/back, shared API cache invalidation, stale response handling and component cleanup.

11. Perform a distinct Page Pass B using alternate evidence and record each finding against Page Pass A.

12. Fix authorized defects and rerun impacted tests until every mandatory page criterion passes or a specific governance/safety/external dependency blocks it.

13. Do not implement the proposed Phase 8 watermark feature. Keep the approved Phase 1–7 scope boundary.

14. Finish with a control-level matrix, endpoint coverage map, actual tests/results, files changed, evidence for both passes and unresolved blockers.


### Independent component prompts — each contains 100 required steps

### AN-01 — Analytics overview KPIs, filters and date range

**Primary files to discover:** frontend/app/analytics/page.tsx and overview metrics APIs  
**Component focus:** KPI cards, filters, dates, loading/empty/error states  
**Acceptance focus:** Verify every displayed metric maps to a response field, aggregation/time boundaries are correct, units and rounding are sensible, filters actually change API query/data, and error states do not show stale values as current.

Copy this complete prompt into the autonomous execution context for this component. Do not execute it in isolation from the master framework.

**100-step component prompt:**
1. Act as the autonomous owner of Analytics overview KPIs, filters and date range. Work only on the actual component discovered in the current checkout, not on an assumed or reconstructed UI.
2. Inspect frontend/app/analytics/page.tsx and overview metrics APIs; follow imports and references to identify the real source files, tests, route and backend dependencies.
3. Component inventory: KPI cards, filters, dates, loading/empty/error states. Discover the full list from the current UI and source. The list above is a focus guide, not permission to invent missing controls.
4. Acceptance focus: Verify every displayed metric maps to a response field, aggregation/time boundaries are correct, units and rounding are sensible, filters actually change API query/data, and error states do not show stale values as current.
5. Create or update dossier ID `AN-01` and link this component to its authoritative Phase/C-series acceptance criterion without redefining phase numbering.
6. Capture current behavior first: record the visible state, control labels, current handler, API call, server response, persisted state and known failure behavior.
7. List every individual button, input, dropdown, link, tab, selector, icon action, modal action and keyboard action in this component; give each a stable child control ID.
8. For every control, specify one positive test, one invalid/error test, one repeated-action/idempotency test where relevant, and one refresh/persistence or cross-page sync test where relevant.
9. Trace every mutation from browser event to API client, backend route, service, persistence/task/external provider and the final returned UI state.
10. Record the precise success assertion and the objective failure condition before changing code; never count a cosmetic animation or toast as proof of backend success.
11. Begin by opening the actual component, its parent, child components, types, API-client methods, and tests; do not trust a previous report without checking the current checkout.
12. List the exact visible controls that belong to this component, including icon-only buttons, links styled as buttons, keyboard shortcuts, toggles, dropdown options, modal actions, and any hidden action revealed by state.
13. For each control, state the requirement and observable success condition before testing it; map each requirement to the approved roadmap item without changing canonical phase numbers.
14. Check whether the control is intentionally non-interactive. If so, it must be semantically non-interactive and cannot imply that an unavailable action will occur.
15. Check accessible name, label/description, role, focusability, keyboard activation, disabled state, focus order, and whether focus returns appropriately after a dialog closes.
16. Trace the real event handler. Reject empty callbacks, console-only callbacks, hard-coded results, no-op links, timer-only simulation, and UI-only state mutation for backend operations.
17. Locate the corresponding API-client method and verify HTTP method, route path, body/query parameters, identifiers, headers/auth, response type, status-code handling, and timeout behavior.
18. Confirm that the route exists in the current backend application and is included under the actual router prefix. Do not infer endpoint existence from a frontend URL string.
19. Inspect backend validation, authorization, ownership checks, service calls, transaction boundaries, queue/task dispatch, and error mapping for the operation.
20. Identify the authoritative persisted record or external response that proves success. Do not use only a toast, button animation, or HTTP 200 as proof of the intended side effect.
21. Check that the frontend consumes the real response and maps returned identifiers/state correctly. Detect hard-coded status strings and mismatched field names.
22. Test the normal successful action using an isolated fixture or safe test record wherever available.
23. Test missing, malformed, stale, or unauthorized identifiers without modifying real user data.
24. Test the expected validation boundary conditions and verify the UI shows a useful message rather than silently dropping the request.
25. Test a server-side failure and confirm no false success indicator appears.
26. Test a network timeout/connection reset and verify the UI does not assume that the backend definitely failed if the outcome may be ambiguous.
27. Test loading indicators and confirm they clear on success, error, cancellation, component unmount, and every supported early return.
28. Test double-click, repeated Enter, quick toggle changes, duplicate network retries, and stale component state for unintended duplicate actions.
29. Check race handling if the action operates on mutable status, queue positions, decisions, settings, uploads, or publishing state.
30. Check that stale/out-of-order responses cannot overwrite a newer state. Use request cancellation, version checks, or existing conventions where needed and approved.
31. Check the response status is translated to the correct UI state, including pending/in-progress, completed, partial failure, failed, cancelled, and conflict states where applicable.
32. Check whether optimistic UI is used. If so, ensure rollback or reconciliation occurs when the backend rejects the change.
33. Check whether the changed state should survive page refresh/reopen; if yes, reload and compare the visible state to the backend-authoritative result.
34. Check whether the state is shared with other pages/components. Trigger the action and inspect every relevant surface for stale data.
35. Check that filters, sorting, selection, pagination, tabs, and the current detail item behave correctly after the operation changes data.
36. Check behavior when the list is empty, the API returns null/partial optional data, a media asset is missing, or a provider is temporarily unavailable.
37. Check timezones, timestamps, duration units, percentages, byte sizes, numeric formatting, and enum labels against backend semantics.
38. Check no credential, OAuth token, API key, signed URL, or private user payload is exposed in visible UI, ordinary logs, test output, or screenshots.
39. Check that test-mode fallbacks or synthetic fixtures can only be activated by the repository-defined trusted test context, never by user-controlled substring or arbitrary request fields.
40. Check the action does not add, restore, expose, or invoke caption/subtitle features. Internal transcription may remain for approved analysis and metadata purposes.
41. Check the action does not route to Ollama or require Ollama environment variables. Preserve approved cloud-hosted models even if their names contain Llama.
42. Check the operation cannot accidentally publish to a source/monitoring channel instead of an explicitly configured destination.
43. Where an action creates a job/task, verify the persisted job ID is retained and Celery dispatch occurs only at the intended transition.
44. Where an action updates a task, verify the backend state transition is valid, durable, and visible on subsequent reads.
45. Where an action creates or deletes a file, verify storage path containment, ownership, retention policy, and cleanup behavior using isolated files only.
46. Where a control selects a layout, verify the selected ID maps to a supported renderer option rather than only changing the visual highlight.
47. Where a control shows a layout thumbnail, verify the reference asset exists in the production build, has the correct accessible text, and truthfully represents output composition.
48. Where the component displays progress, verify it is sourced from authoritative progress/status fields and cannot display completion before the task completes.
49. Where the component refreshes/polls, verify intervals, overlap, cooldown, backoff, and unmount cleanup against the actual code contract.
50. Where external providers are involved, test mocked/sandbox cases first and ensure no accidental external side effect is triggered by an ordinary test.
51. For the private YouTube acceptance upload, do not use this component test to generate another upload. The one real upload is centrally orchestrated and idempotently gated under the master framework.
52. Inspect the relevant unit/component test and add a regression test for each repaired defect where test infrastructure permits.
53. Run the smallest test covering this component first and record the exact command and actual exit result.
54. Run the relevant API/backend integration test where it can be proven safe and isolated.
55. Run the relevant browser/E2E test if available; do not describe static source inspection as a browser test.
56. Collect actual request/response evidence with secrets redacted. Link to the logs or test output that substantiate the result.
57. Compare the user-visible message/status with the actual backend response and persisted state.
58. Conduct Pass A by tracing requirements to implementation and successful tests.
59. Conduct Pass B independently using an alternate path such as persisted state, route registration, event log, task state, rendered output, refresh behavior, or a different test assertion.
60. If Pass A and Pass B disagree, investigate and document the discrepancy; do not average the results or silently pick the favorable one.
61. Classify a failure as UI defect, API contract mismatch, backend behavior defect, persistence defect, concurrency defect, configuration defect, missing test/evidence, or scope ambiguity.
62. Fix only defects within approved Phase 1–7 requirements and only through the governance process required by the freeze rules.
63. Before changing a shared API client, component, schema, backend route, or frozen domain, identify all affected pages and regression tests.
64. Keep the code change minimal and preserve pre-existing Git modifications and untracked files.
65. Never execute blanket Git reset/clean/checkout/restore commands or replace a whole file to make a small repair.
66. After a repair, rerun the failing reproduction, relevant component test, API/backend tests, and affected page regression checks.
67. Independently repeat Pass B after the repair, using evidence distinct from the original fix path where reasonably possible.
68. If the test fails, continue the diagnose/fix/retest loop within scope; if the failure requires unavailable authorization or unsafe operation, mark it blocked and continue unrelated work.
69. Do not stop at the first failed test if the cause is repairable within scope. Do not loop indefinitely if a genuine external or governance blocker exists.
70. Check that test teardown completes and does not silently mask failures; do not change global fixtures unless required and governed.
71. Confirm test DB isolation before any database mutation. Never migrate, drop, reset, or clean the operational clipforge database.
72. Confirm no test publishes an actual video except the one centralized, explicit, private acceptance upload authorized by the user.
73. Confirm no generated test file overwrites existing uploads or outputs and no cleanup task deletes user-owned media.
74. Run TypeScript and lint checks against the changed frontend where possible. Report repository-wide legacy issues separately from new introduced issues.
75. Run the production build after page/component changes and distinguish build output count from the number of user-facing pages.
76. Inspect browser console errors, failed network requests, React warnings, hydration issues, and unhandled promise rejections where browser execution is available.
77. Check responsive layout at narrow and wide viewport sizes, avoiding horizontal overflow, clipped dialogs, invisible controls, and inaccessible hover-only actions.
78. Check error messages are actionable, avoid secrets, and preserve user-entered form data where retry is expected.
79. Check the component handles loading, empty, success, partial-success, validation, unauthorized, not-found, conflict, rate-limit, server-error, and offline states as applicable.
80. Check that stale UI cache does not outlive a mutation. Invalidate/refetch only the relevant query/state according to the existing architecture.
81. Check a successful response has not been mistaken for semantic success when the backend returns a task ID with pending execution.
82. Check task completion is awaited or polled appropriately and the user can identify pending versus completed processing.
83. Check external provider errors propagate to a truthful status rather than being caught and converted into fabricated success.
84. Check any retry operation cannot create duplicate jobs, settings writes, uploads, publications, or cleanup operations.
85. Check the component has no hidden coupling to unapproved Phase 8 watermark branding or unsupported layouts.
86. Cross-reference actual behavior with `PHASE_TRACKER.md`, the relevant approved prompt, and the actual backend route/service. Do not assume draft/archived prompts are mandatory scope.
87. Check related documentation only if it is directly affected by the verified implementation; preserve historical audit evidence.
88. Update the component dossier with actual file paths, symbols, endpoint, backend behavior, test commands, Pass A evidence and Pass B evidence.
89. If a required operation is not present in the current UI, mark it absent and verify whether the approved specification requires it; do not silently invent UI.
90. If a required capability is absent, identify the exact implementation/API/test gap and fix it only when inside approved scope and governance permits.
91. Before any edit, record targeted Git status/diff; after edits, verify unrelated working-tree changes and untracked assets remain untouched.
92. Do not make changes beyond approved Phase 1–7 scope; Phase 8 watermark branding remains deferred unless separately authorized.
93. If this component offers a layout choice, require a real local reference thumbnail for every supported option and verify the output renderer matches it.
94. If this component participates in monitoring/publishing, check destination identity and state synchronization, and obey the central private-upload gate; do not create a second real upload.
95. Never expose secrets, run destructive database operations, publish public/unlisted test videos, or delete user media while verifying this component.
96. Perform Pass A: independently map every acceptance criterion to implementation and test evidence. Record exact paths, symbols, commands and actual results.
97. Perform Pass B independently using alternate evidence; explicitly confirm, contradict or leave uncertain every material Pass A claim.
98. Repair eligible defects and repeat the complete relevant test loop; if governance or safety blocks a fix, record the exact blocker and continue independent work.
99. Final acceptance for `AN-01`: every mandatory control in Analytics overview KPIs, filters and date range must have a real handler/contract, verified backend result, correct UI synchronization, passing relevant test, and independent Pass A/Pass B evidence.
100. Return a concise per-control matrix, exact files changed, tests and results, unresolved issues, and final component verdict. Do not declare PASS when evidence is missing.


---

### AN-02 — Per-video performance table/charts

**Primary files to discover:** Per-video analytics components and API endpoints  
**Component focus:** Per-video rows, chart tooltips, metric selection, video detail links  
**Acceptance focus:** Verify each chart/table uses the selected video's actual ID, series and time windows match API data, tooltips/legends are correct, missing data renders honestly, links navigate to the right video, and refresh does not mix data across videos.

Copy this complete prompt into the autonomous execution context for this component. Do not execute it in isolation from the master framework.

**100-step component prompt:**
1. Act as the autonomous owner of Per-video performance table/charts. Work only on the actual component discovered in the current checkout, not on an assumed or reconstructed UI.
2. Inspect Per-video analytics components and API endpoints; follow imports and references to identify the real source files, tests, route and backend dependencies.
3. Component inventory: Per-video rows, chart tooltips, metric selection, video detail links. Discover the full list from the current UI and source. The list above is a focus guide, not permission to invent missing controls.
4. Acceptance focus: Verify each chart/table uses the selected video's actual ID, series and time windows match API data, tooltips/legends are correct, missing data renders honestly, links navigate to the right video, and refresh does not mix data across videos.
5. Create or update dossier ID `AN-02` and link this component to its authoritative Phase/C-series acceptance criterion without redefining phase numbering.
6. Capture current behavior first: record the visible state, control labels, current handler, API call, server response, persisted state and known failure behavior.
7. List every individual button, input, dropdown, link, tab, selector, icon action, modal action and keyboard action in this component; give each a stable child control ID.
8. For every control, specify one positive test, one invalid/error test, one repeated-action/idempotency test where relevant, and one refresh/persistence or cross-page sync test where relevant.
9. Trace every mutation from browser event to API client, backend route, service, persistence/task/external provider and the final returned UI state.
10. Record the precise success assertion and the objective failure condition before changing code; never count a cosmetic animation or toast as proof of backend success.
11. Begin by opening the actual component, its parent, child components, types, API-client methods, and tests; do not trust a previous report without checking the current checkout.
12. List the exact visible controls that belong to this component, including icon-only buttons, links styled as buttons, keyboard shortcuts, toggles, dropdown options, modal actions, and any hidden action revealed by state.
13. For each control, state the requirement and observable success condition before testing it; map each requirement to the approved roadmap item without changing canonical phase numbers.
14. Check whether the control is intentionally non-interactive. If so, it must be semantically non-interactive and cannot imply that an unavailable action will occur.
15. Check accessible name, label/description, role, focusability, keyboard activation, disabled state, focus order, and whether focus returns appropriately after a dialog closes.
16. Trace the real event handler. Reject empty callbacks, console-only callbacks, hard-coded results, no-op links, timer-only simulation, and UI-only state mutation for backend operations.
17. Locate the corresponding API-client method and verify HTTP method, route path, body/query parameters, identifiers, headers/auth, response type, status-code handling, and timeout behavior.
18. Confirm that the route exists in the current backend application and is included under the actual router prefix. Do not infer endpoint existence from a frontend URL string.
19. Inspect backend validation, authorization, ownership checks, service calls, transaction boundaries, queue/task dispatch, and error mapping for the operation.
20. Identify the authoritative persisted record or external response that proves success. Do not use only a toast, button animation, or HTTP 200 as proof of the intended side effect.
21. Check that the frontend consumes the real response and maps returned identifiers/state correctly. Detect hard-coded status strings and mismatched field names.
22. Test the normal successful action using an isolated fixture or safe test record wherever available.
23. Test missing, malformed, stale, or unauthorized identifiers without modifying real user data.
24. Test the expected validation boundary conditions and verify the UI shows a useful message rather than silently dropping the request.
25. Test a server-side failure and confirm no false success indicator appears.
26. Test a network timeout/connection reset and verify the UI does not assume that the backend definitely failed if the outcome may be ambiguous.
27. Test loading indicators and confirm they clear on success, error, cancellation, component unmount, and every supported early return.
28. Test double-click, repeated Enter, quick toggle changes, duplicate network retries, and stale component state for unintended duplicate actions.
29. Check race handling if the action operates on mutable status, queue positions, decisions, settings, uploads, or publishing state.
30. Check that stale/out-of-order responses cannot overwrite a newer state. Use request cancellation, version checks, or existing conventions where needed and approved.
31. Check the response status is translated to the correct UI state, including pending/in-progress, completed, partial failure, failed, cancelled, and conflict states where applicable.
32. Check whether optimistic UI is used. If so, ensure rollback or reconciliation occurs when the backend rejects the change.
33. Check whether the changed state should survive page refresh/reopen; if yes, reload and compare the visible state to the backend-authoritative result.
34. Check whether the state is shared with other pages/components. Trigger the action and inspect every relevant surface for stale data.
35. Check that filters, sorting, selection, pagination, tabs, and the current detail item behave correctly after the operation changes data.
36. Check behavior when the list is empty, the API returns null/partial optional data, a media asset is missing, or a provider is temporarily unavailable.
37. Check timezones, timestamps, duration units, percentages, byte sizes, numeric formatting, and enum labels against backend semantics.
38. Check no credential, OAuth token, API key, signed URL, or private user payload is exposed in visible UI, ordinary logs, test output, or screenshots.
39. Check that test-mode fallbacks or synthetic fixtures can only be activated by the repository-defined trusted test context, never by user-controlled substring or arbitrary request fields.
40. Check the action does not add, restore, expose, or invoke caption/subtitle features. Internal transcription may remain for approved analysis and metadata purposes.
41. Check the action does not route to Ollama or require Ollama environment variables. Preserve approved cloud-hosted models even if their names contain Llama.
42. Check the operation cannot accidentally publish to a source/monitoring channel instead of an explicitly configured destination.
43. Where an action creates a job/task, verify the persisted job ID is retained and Celery dispatch occurs only at the intended transition.
44. Where an action updates a task, verify the backend state transition is valid, durable, and visible on subsequent reads.
45. Where an action creates or deletes a file, verify storage path containment, ownership, retention policy, and cleanup behavior using isolated files only.
46. Where a control selects a layout, verify the selected ID maps to a supported renderer option rather than only changing the visual highlight.
47. Where a control shows a layout thumbnail, verify the reference asset exists in the production build, has the correct accessible text, and truthfully represents output composition.
48. Where the component displays progress, verify it is sourced from authoritative progress/status fields and cannot display completion before the task completes.
49. Where the component refreshes/polls, verify intervals, overlap, cooldown, backoff, and unmount cleanup against the actual code contract.
50. Where external providers are involved, test mocked/sandbox cases first and ensure no accidental external side effect is triggered by an ordinary test.
51. For the private YouTube acceptance upload, do not use this component test to generate another upload. The one real upload is centrally orchestrated and idempotently gated under the master framework.
52. Inspect the relevant unit/component test and add a regression test for each repaired defect where test infrastructure permits.
53. Run the smallest test covering this component first and record the exact command and actual exit result.
54. Run the relevant API/backend integration test where it can be proven safe and isolated.
55. Run the relevant browser/E2E test if available; do not describe static source inspection as a browser test.
56. Collect actual request/response evidence with secrets redacted. Link to the logs or test output that substantiate the result.
57. Compare the user-visible message/status with the actual backend response and persisted state.
58. Conduct Pass A by tracing requirements to implementation and successful tests.
59. Conduct Pass B independently using an alternate path such as persisted state, route registration, event log, task state, rendered output, refresh behavior, or a different test assertion.
60. If Pass A and Pass B disagree, investigate and document the discrepancy; do not average the results or silently pick the favorable one.
61. Classify a failure as UI defect, API contract mismatch, backend behavior defect, persistence defect, concurrency defect, configuration defect, missing test/evidence, or scope ambiguity.
62. Fix only defects within approved Phase 1–7 requirements and only through the governance process required by the freeze rules.
63. Before changing a shared API client, component, schema, backend route, or frozen domain, identify all affected pages and regression tests.
64. Keep the code change minimal and preserve pre-existing Git modifications and untracked files.
65. Never execute blanket Git reset/clean/checkout/restore commands or replace a whole file to make a small repair.
66. After a repair, rerun the failing reproduction, relevant component test, API/backend tests, and affected page regression checks.
67. Independently repeat Pass B after the repair, using evidence distinct from the original fix path where reasonably possible.
68. If the test fails, continue the diagnose/fix/retest loop within scope; if the failure requires unavailable authorization or unsafe operation, mark it blocked and continue unrelated work.
69. Do not stop at the first failed test if the cause is repairable within scope. Do not loop indefinitely if a genuine external or governance blocker exists.
70. Check that test teardown completes and does not silently mask failures; do not change global fixtures unless required and governed.
71. Confirm test DB isolation before any database mutation. Never migrate, drop, reset, or clean the operational clipforge database.
72. Confirm no test publishes an actual video except the one centralized, explicit, private acceptance upload authorized by the user.
73. Confirm no generated test file overwrites existing uploads or outputs and no cleanup task deletes user-owned media.
74. Run TypeScript and lint checks against the changed frontend where possible. Report repository-wide legacy issues separately from new introduced issues.
75. Run the production build after page/component changes and distinguish build output count from the number of user-facing pages.
76. Inspect browser console errors, failed network requests, React warnings, hydration issues, and unhandled promise rejections where browser execution is available.
77. Check responsive layout at narrow and wide viewport sizes, avoiding horizontal overflow, clipped dialogs, invisible controls, and inaccessible hover-only actions.
78. Check error messages are actionable, avoid secrets, and preserve user-entered form data where retry is expected.
79. Check the component handles loading, empty, success, partial-success, validation, unauthorized, not-found, conflict, rate-limit, server-error, and offline states as applicable.
80. Check that stale UI cache does not outlive a mutation. Invalidate/refetch only the relevant query/state according to the existing architecture.
81. Check a successful response has not been mistaken for semantic success when the backend returns a task ID with pending execution.
82. Check task completion is awaited or polled appropriately and the user can identify pending versus completed processing.
83. Check external provider errors propagate to a truthful status rather than being caught and converted into fabricated success.
84. Check any retry operation cannot create duplicate jobs, settings writes, uploads, publications, or cleanup operations.
85. Check the component has no hidden coupling to unapproved Phase 8 watermark branding or unsupported layouts.
86. Cross-reference actual behavior with `PHASE_TRACKER.md`, the relevant approved prompt, and the actual backend route/service. Do not assume draft/archived prompts are mandatory scope.
87. Check related documentation only if it is directly affected by the verified implementation; preserve historical audit evidence.
88. Update the component dossier with actual file paths, symbols, endpoint, backend behavior, test commands, Pass A evidence and Pass B evidence.
89. If a required operation is not present in the current UI, mark it absent and verify whether the approved specification requires it; do not silently invent UI.
90. If a required capability is absent, identify the exact implementation/API/test gap and fix it only when inside approved scope and governance permits.
91. Before any edit, record targeted Git status/diff; after edits, verify unrelated working-tree changes and untracked assets remain untouched.
92. Do not make changes beyond approved Phase 1–7 scope; Phase 8 watermark branding remains deferred unless separately authorized.
93. If this component offers a layout choice, require a real local reference thumbnail for every supported option and verify the output renderer matches it.
94. If this component participates in monitoring/publishing, check destination identity and state synchronization, and obey the central private-upload gate; do not create a second real upload.
95. Never expose secrets, run destructive database operations, publish public/unlisted test videos, or delete user media while verifying this component.
96. Perform Pass A: independently map every acceptance criterion to implementation and test evidence. Record exact paths, symbols, commands and actual results.
97. Perform Pass B independently using alternate evidence; explicitly confirm, contradict or leave uncertain every material Pass A claim.
98. Repair eligible defects and repeat the complete relevant test loop; if governance or safety blocks a fix, record the exact blocker and continue independent work.
99. Final acceptance for `AN-02`: every mandatory control in Per-video performance table/charts must have a real handler/contract, verified backend result, correct UI synchronization, passing relevant test, and independent Pass A/Pass B evidence.
100. Return a concise per-control matrix, exact files changed, tests and results, unresolved issues, and final component verdict. Do not declare PASS when evidence is missing.


---

### AN-03 — SEO keywords and optimization history

**Primary files to discover:** Keyword chips, optimization log list and related endpoints  
**Component focus:** Add/remove/filter keyword controls if present; optimization events/history  
**Acceptance focus:** Verify keyword normalization and persistence, correct video association, no invented success, accurate timestamps, and the UI only displays optimization actions actually persisted by the backend.

Copy this complete prompt into the autonomous execution context for this component. Do not execute it in isolation from the master framework.

**100-step component prompt:**
1. Act as the autonomous owner of SEO keywords and optimization history. Work only on the actual component discovered in the current checkout, not on an assumed or reconstructed UI.
2. Inspect Keyword chips, optimization log list and related endpoints; follow imports and references to identify the real source files, tests, route and backend dependencies.
3. Component inventory: Add/remove/filter keyword controls if present; optimization events/history. Discover the full list from the current UI and source. The list above is a focus guide, not permission to invent missing controls.
4. Acceptance focus: Verify keyword normalization and persistence, correct video association, no invented success, accurate timestamps, and the UI only displays optimization actions actually persisted by the backend.
5. Create or update dossier ID `AN-03` and link this component to its authoritative Phase/C-series acceptance criterion without redefining phase numbering.
6. Capture current behavior first: record the visible state, control labels, current handler, API call, server response, persisted state and known failure behavior.
7. List every individual button, input, dropdown, link, tab, selector, icon action, modal action and keyboard action in this component; give each a stable child control ID.
8. For every control, specify one positive test, one invalid/error test, one repeated-action/idempotency test where relevant, and one refresh/persistence or cross-page sync test where relevant.
9. Trace every mutation from browser event to API client, backend route, service, persistence/task/external provider and the final returned UI state.
10. Record the precise success assertion and the objective failure condition before changing code; never count a cosmetic animation or toast as proof of backend success.
11. Begin by opening the actual component, its parent, child components, types, API-client methods, and tests; do not trust a previous report without checking the current checkout.
12. List the exact visible controls that belong to this component, including icon-only buttons, links styled as buttons, keyboard shortcuts, toggles, dropdown options, modal actions, and any hidden action revealed by state.
13. For each control, state the requirement and observable success condition before testing it; map each requirement to the approved roadmap item without changing canonical phase numbers.
14. Check whether the control is intentionally non-interactive. If so, it must be semantically non-interactive and cannot imply that an unavailable action will occur.
15. Check accessible name, label/description, role, focusability, keyboard activation, disabled state, focus order, and whether focus returns appropriately after a dialog closes.
16. Trace the real event handler. Reject empty callbacks, console-only callbacks, hard-coded results, no-op links, timer-only simulation, and UI-only state mutation for backend operations.
17. Locate the corresponding API-client method and verify HTTP method, route path, body/query parameters, identifiers, headers/auth, response type, status-code handling, and timeout behavior.
18. Confirm that the route exists in the current backend application and is included under the actual router prefix. Do not infer endpoint existence from a frontend URL string.
19. Inspect backend validation, authorization, ownership checks, service calls, transaction boundaries, queue/task dispatch, and error mapping for the operation.
20. Identify the authoritative persisted record or external response that proves success. Do not use only a toast, button animation, or HTTP 200 as proof of the intended side effect.
21. Check that the frontend consumes the real response and maps returned identifiers/state correctly. Detect hard-coded status strings and mismatched field names.
22. Test the normal successful action using an isolated fixture or safe test record wherever available.
23. Test missing, malformed, stale, or unauthorized identifiers without modifying real user data.
24. Test the expected validation boundary conditions and verify the UI shows a useful message rather than silently dropping the request.
25. Test a server-side failure and confirm no false success indicator appears.
26. Test a network timeout/connection reset and verify the UI does not assume that the backend definitely failed if the outcome may be ambiguous.
27. Test loading indicators and confirm they clear on success, error, cancellation, component unmount, and every supported early return.
28. Test double-click, repeated Enter, quick toggle changes, duplicate network retries, and stale component state for unintended duplicate actions.
29. Check race handling if the action operates on mutable status, queue positions, decisions, settings, uploads, or publishing state.
30. Check that stale/out-of-order responses cannot overwrite a newer state. Use request cancellation, version checks, or existing conventions where needed and approved.
31. Check the response status is translated to the correct UI state, including pending/in-progress, completed, partial failure, failed, cancelled, and conflict states where applicable.
32. Check whether optimistic UI is used. If so, ensure rollback or reconciliation occurs when the backend rejects the change.
33. Check whether the changed state should survive page refresh/reopen; if yes, reload and compare the visible state to the backend-authoritative result.
34. Check whether the state is shared with other pages/components. Trigger the action and inspect every relevant surface for stale data.
35. Check that filters, sorting, selection, pagination, tabs, and the current detail item behave correctly after the operation changes data.
36. Check behavior when the list is empty, the API returns null/partial optional data, a media asset is missing, or a provider is temporarily unavailable.
37. Check timezones, timestamps, duration units, percentages, byte sizes, numeric formatting, and enum labels against backend semantics.
38. Check no credential, OAuth token, API key, signed URL, or private user payload is exposed in visible UI, ordinary logs, test output, or screenshots.
39. Check that test-mode fallbacks or synthetic fixtures can only be activated by the repository-defined trusted test context, never by user-controlled substring or arbitrary request fields.
40. Check the action does not add, restore, expose, or invoke caption/subtitle features. Internal transcription may remain for approved analysis and metadata purposes.
41. Check the action does not route to Ollama or require Ollama environment variables. Preserve approved cloud-hosted models even if their names contain Llama.
42. Check the operation cannot accidentally publish to a source/monitoring channel instead of an explicitly configured destination.
43. Where an action creates a job/task, verify the persisted job ID is retained and Celery dispatch occurs only at the intended transition.
44. Where an action updates a task, verify the backend state transition is valid, durable, and visible on subsequent reads.
45. Where an action creates or deletes a file, verify storage path containment, ownership, retention policy, and cleanup behavior using isolated files only.
46. Where a control selects a layout, verify the selected ID maps to a supported renderer option rather than only changing the visual highlight.
47. Where a control shows a layout thumbnail, verify the reference asset exists in the production build, has the correct accessible text, and truthfully represents output composition.
48. Where the component displays progress, verify it is sourced from authoritative progress/status fields and cannot display completion before the task completes.
49. Where the component refreshes/polls, verify intervals, overlap, cooldown, backoff, and unmount cleanup against the actual code contract.
50. Where external providers are involved, test mocked/sandbox cases first and ensure no accidental external side effect is triggered by an ordinary test.
51. For the private YouTube acceptance upload, do not use this component test to generate another upload. The one real upload is centrally orchestrated and idempotently gated under the master framework.
52. Inspect the relevant unit/component test and add a regression test for each repaired defect where test infrastructure permits.
53. Run the smallest test covering this component first and record the exact command and actual exit result.
54. Run the relevant API/backend integration test where it can be proven safe and isolated.
55. Run the relevant browser/E2E test if available; do not describe static source inspection as a browser test.
56. Collect actual request/response evidence with secrets redacted. Link to the logs or test output that substantiate the result.
57. Compare the user-visible message/status with the actual backend response and persisted state.
58. Conduct Pass A by tracing requirements to implementation and successful tests.
59. Conduct Pass B independently using an alternate path such as persisted state, route registration, event log, task state, rendered output, refresh behavior, or a different test assertion.
60. If Pass A and Pass B disagree, investigate and document the discrepancy; do not average the results or silently pick the favorable one.
61. Classify a failure as UI defect, API contract mismatch, backend behavior defect, persistence defect, concurrency defect, configuration defect, missing test/evidence, or scope ambiguity.
62. Fix only defects within approved Phase 1–7 requirements and only through the governance process required by the freeze rules.
63. Before changing a shared API client, component, schema, backend route, or frozen domain, identify all affected pages and regression tests.
64. Keep the code change minimal and preserve pre-existing Git modifications and untracked files.
65. Never execute blanket Git reset/clean/checkout/restore commands or replace a whole file to make a small repair.
66. After a repair, rerun the failing reproduction, relevant component test, API/backend tests, and affected page regression checks.
67. Independently repeat Pass B after the repair, using evidence distinct from the original fix path where reasonably possible.
68. If the test fails, continue the diagnose/fix/retest loop within scope; if the failure requires unavailable authorization or unsafe operation, mark it blocked and continue unrelated work.
69. Do not stop at the first failed test if the cause is repairable within scope. Do not loop indefinitely if a genuine external or governance blocker exists.
70. Check that test teardown completes and does not silently mask failures; do not change global fixtures unless required and governed.
71. Confirm test DB isolation before any database mutation. Never migrate, drop, reset, or clean the operational clipforge database.
72. Confirm no test publishes an actual video except the one centralized, explicit, private acceptance upload authorized by the user.
73. Confirm no generated test file overwrites existing uploads or outputs and no cleanup task deletes user-owned media.
74. Run TypeScript and lint checks against the changed frontend where possible. Report repository-wide legacy issues separately from new introduced issues.
75. Run the production build after page/component changes and distinguish build output count from the number of user-facing pages.
76. Inspect browser console errors, failed network requests, React warnings, hydration issues, and unhandled promise rejections where browser execution is available.
77. Check responsive layout at narrow and wide viewport sizes, avoiding horizontal overflow, clipped dialogs, invisible controls, and inaccessible hover-only actions.
78. Check error messages are actionable, avoid secrets, and preserve user-entered form data where retry is expected.
79. Check the component handles loading, empty, success, partial-success, validation, unauthorized, not-found, conflict, rate-limit, server-error, and offline states as applicable.
80. Check that stale UI cache does not outlive a mutation. Invalidate/refetch only the relevant query/state according to the existing architecture.
81. Check a successful response has not been mistaken for semantic success when the backend returns a task ID with pending execution.
82. Check task completion is awaited or polled appropriately and the user can identify pending versus completed processing.
83. Check external provider errors propagate to a truthful status rather than being caught and converted into fabricated success.
84. Check any retry operation cannot create duplicate jobs, settings writes, uploads, publications, or cleanup operations.
85. Check the component has no hidden coupling to unapproved Phase 8 watermark branding or unsupported layouts.
86. Cross-reference actual behavior with `PHASE_TRACKER.md`, the relevant approved prompt, and the actual backend route/service. Do not assume draft/archived prompts are mandatory scope.
87. Check related documentation only if it is directly affected by the verified implementation; preserve historical audit evidence.
88. Update the component dossier with actual file paths, symbols, endpoint, backend behavior, test commands, Pass A evidence and Pass B evidence.
89. If a required operation is not present in the current UI, mark it absent and verify whether the approved specification requires it; do not silently invent UI.
90. If a required capability is absent, identify the exact implementation/API/test gap and fix it only when inside approved scope and governance permits.
91. Before any edit, record targeted Git status/diff; after edits, verify unrelated working-tree changes and untracked assets remain untouched.
92. Do not make changes beyond approved Phase 1–7 scope; Phase 8 watermark branding remains deferred unless separately authorized.
93. If this component offers a layout choice, require a real local reference thumbnail for every supported option and verify the output renderer matches it.
94. If this component participates in monitoring/publishing, check destination identity and state synchronization, and obey the central private-upload gate; do not create a second real upload.
95. Never expose secrets, run destructive database operations, publish public/unlisted test videos, or delete user media while verifying this component.
96. Perform Pass A: independently map every acceptance criterion to implementation and test evidence. Record exact paths, symbols, commands and actual results.
97. Perform Pass B independently using alternate evidence; explicitly confirm, contradict or leave uncertain every material Pass A claim.
98. Repair eligible defects and repeat the complete relevant test loop; if governance or safety blocks a fix, record the exact blocker and continue independent work.
99. Final acceptance for `AN-03`: every mandatory control in SEO keywords and optimization history must have a real handler/contract, verified backend result, correct UI synchronization, passing relevant test, and independent Pass A/Pass B evidence.
100. Return a concise per-control matrix, exact files changed, tests and results, unresolved issues, and final component verdict. Do not declare PASS when evidence is missing.


---

### AN-04 — Channel analytics polling, refresh and cooldown

**Primary files to discover:** Analytics channel widgets and channel stats endpoints  
**Component focus:** Auto-refresh toggle, manual refresh, cooldown feedback, loading/error states  
**Acceptance focus:** Verify poll intervals, 60-second rate/cooldown logic where approved, async coalescing, no overlapping duplicate requests, freshness timestamp, API response handling, and stopping polling on unmount/navigation.

Copy this complete prompt into the autonomous execution context for this component. Do not execute it in isolation from the master framework.

**100-step component prompt:**
1. Act as the autonomous owner of Channel analytics polling, refresh and cooldown. Work only on the actual component discovered in the current checkout, not on an assumed or reconstructed UI.
2. Inspect Analytics channel widgets and channel stats endpoints; follow imports and references to identify the real source files, tests, route and backend dependencies.
3. Component inventory: Auto-refresh toggle, manual refresh, cooldown feedback, loading/error states. Discover the full list from the current UI and source. The list above is a focus guide, not permission to invent missing controls.
4. Acceptance focus: Verify poll intervals, 60-second rate/cooldown logic where approved, async coalescing, no overlapping duplicate requests, freshness timestamp, API response handling, and stopping polling on unmount/navigation.
5. Create or update dossier ID `AN-04` and link this component to its authoritative Phase/C-series acceptance criterion without redefining phase numbering.
6. Capture current behavior first: record the visible state, control labels, current handler, API call, server response, persisted state and known failure behavior.
7. List every individual button, input, dropdown, link, tab, selector, icon action, modal action and keyboard action in this component; give each a stable child control ID.
8. For every control, specify one positive test, one invalid/error test, one repeated-action/idempotency test where relevant, and one refresh/persistence or cross-page sync test where relevant.
9. Trace every mutation from browser event to API client, backend route, service, persistence/task/external provider and the final returned UI state.
10. Record the precise success assertion and the objective failure condition before changing code; never count a cosmetic animation or toast as proof of backend success.
11. Begin by opening the actual component, its parent, child components, types, API-client methods, and tests; do not trust a previous report without checking the current checkout.
12. List the exact visible controls that belong to this component, including icon-only buttons, links styled as buttons, keyboard shortcuts, toggles, dropdown options, modal actions, and any hidden action revealed by state.
13. For each control, state the requirement and observable success condition before testing it; map each requirement to the approved roadmap item without changing canonical phase numbers.
14. Check whether the control is intentionally non-interactive. If so, it must be semantically non-interactive and cannot imply that an unavailable action will occur.
15. Check accessible name, label/description, role, focusability, keyboard activation, disabled state, focus order, and whether focus returns appropriately after a dialog closes.
16. Trace the real event handler. Reject empty callbacks, console-only callbacks, hard-coded results, no-op links, timer-only simulation, and UI-only state mutation for backend operations.
17. Locate the corresponding API-client method and verify HTTP method, route path, body/query parameters, identifiers, headers/auth, response type, status-code handling, and timeout behavior.
18. Confirm that the route exists in the current backend application and is included under the actual router prefix. Do not infer endpoint existence from a frontend URL string.
19. Inspect backend validation, authorization, ownership checks, service calls, transaction boundaries, queue/task dispatch, and error mapping for the operation.
20. Identify the authoritative persisted record or external response that proves success. Do not use only a toast, button animation, or HTTP 200 as proof of the intended side effect.
21. Check that the frontend consumes the real response and maps returned identifiers/state correctly. Detect hard-coded status strings and mismatched field names.
22. Test the normal successful action using an isolated fixture or safe test record wherever available.
23. Test missing, malformed, stale, or unauthorized identifiers without modifying real user data.
24. Test the expected validation boundary conditions and verify the UI shows a useful message rather than silently dropping the request.
25. Test a server-side failure and confirm no false success indicator appears.
26. Test a network timeout/connection reset and verify the UI does not assume that the backend definitely failed if the outcome may be ambiguous.
27. Test loading indicators and confirm they clear on success, error, cancellation, component unmount, and every supported early return.
28. Test double-click, repeated Enter, quick toggle changes, duplicate network retries, and stale component state for unintended duplicate actions.
29. Check race handling if the action operates on mutable status, queue positions, decisions, settings, uploads, or publishing state.
30. Check that stale/out-of-order responses cannot overwrite a newer state. Use request cancellation, version checks, or existing conventions where needed and approved.
31. Check the response status is translated to the correct UI state, including pending/in-progress, completed, partial failure, failed, cancelled, and conflict states where applicable.
32. Check whether optimistic UI is used. If so, ensure rollback or reconciliation occurs when the backend rejects the change.
33. Check whether the changed state should survive page refresh/reopen; if yes, reload and compare the visible state to the backend-authoritative result.
34. Check whether the state is shared with other pages/components. Trigger the action and inspect every relevant surface for stale data.
35. Check that filters, sorting, selection, pagination, tabs, and the current detail item behave correctly after the operation changes data.
36. Check behavior when the list is empty, the API returns null/partial optional data, a media asset is missing, or a provider is temporarily unavailable.
37. Check timezones, timestamps, duration units, percentages, byte sizes, numeric formatting, and enum labels against backend semantics.
38. Check no credential, OAuth token, API key, signed URL, or private user payload is exposed in visible UI, ordinary logs, test output, or screenshots.
39. Check that test-mode fallbacks or synthetic fixtures can only be activated by the repository-defined trusted test context, never by user-controlled substring or arbitrary request fields.
40. Check the action does not add, restore, expose, or invoke caption/subtitle features. Internal transcription may remain for approved analysis and metadata purposes.
41. Check the action does not route to Ollama or require Ollama environment variables. Preserve approved cloud-hosted models even if their names contain Llama.
42. Check the operation cannot accidentally publish to a source/monitoring channel instead of an explicitly configured destination.
43. Where an action creates a job/task, verify the persisted job ID is retained and Celery dispatch occurs only at the intended transition.
44. Where an action updates a task, verify the backend state transition is valid, durable, and visible on subsequent reads.
45. Where an action creates or deletes a file, verify storage path containment, ownership, retention policy, and cleanup behavior using isolated files only.
46. Where a control selects a layout, verify the selected ID maps to a supported renderer option rather than only changing the visual highlight.
47. Where a control shows a layout thumbnail, verify the reference asset exists in the production build, has the correct accessible text, and truthfully represents output composition.
48. Where the component displays progress, verify it is sourced from authoritative progress/status fields and cannot display completion before the task completes.
49. Where the component refreshes/polls, verify intervals, overlap, cooldown, backoff, and unmount cleanup against the actual code contract.
50. Where external providers are involved, test mocked/sandbox cases first and ensure no accidental external side effect is triggered by an ordinary test.
51. For the private YouTube acceptance upload, do not use this component test to generate another upload. The one real upload is centrally orchestrated and idempotently gated under the master framework.
52. Inspect the relevant unit/component test and add a regression test for each repaired defect where test infrastructure permits.
53. Run the smallest test covering this component first and record the exact command and actual exit result.
54. Run the relevant API/backend integration test where it can be proven safe and isolated.
55. Run the relevant browser/E2E test if available; do not describe static source inspection as a browser test.
56. Collect actual request/response evidence with secrets redacted. Link to the logs or test output that substantiate the result.
57. Compare the user-visible message/status with the actual backend response and persisted state.
58. Conduct Pass A by tracing requirements to implementation and successful tests.
59. Conduct Pass B independently using an alternate path such as persisted state, route registration, event log, task state, rendered output, refresh behavior, or a different test assertion.
60. If Pass A and Pass B disagree, investigate and document the discrepancy; do not average the results or silently pick the favorable one.
61. Classify a failure as UI defect, API contract mismatch, backend behavior defect, persistence defect, concurrency defect, configuration defect, missing test/evidence, or scope ambiguity.
62. Fix only defects within approved Phase 1–7 requirements and only through the governance process required by the freeze rules.
63. Before changing a shared API client, component, schema, backend route, or frozen domain, identify all affected pages and regression tests.
64. Keep the code change minimal and preserve pre-existing Git modifications and untracked files.
65. Never execute blanket Git reset/clean/checkout/restore commands or replace a whole file to make a small repair.
66. After a repair, rerun the failing reproduction, relevant component test, API/backend tests, and affected page regression checks.
67. Independently repeat Pass B after the repair, using evidence distinct from the original fix path where reasonably possible.
68. If the test fails, continue the diagnose/fix/retest loop within scope; if the failure requires unavailable authorization or unsafe operation, mark it blocked and continue unrelated work.
69. Do not stop at the first failed test if the cause is repairable within scope. Do not loop indefinitely if a genuine external or governance blocker exists.
70. Check that test teardown completes and does not silently mask failures; do not change global fixtures unless required and governed.
71. Confirm test DB isolation before any database mutation. Never migrate, drop, reset, or clean the operational clipforge database.
72. Confirm no test publishes an actual video except the one centralized, explicit, private acceptance upload authorized by the user.
73. Confirm no generated test file overwrites existing uploads or outputs and no cleanup task deletes user-owned media.
74. Run TypeScript and lint checks against the changed frontend where possible. Report repository-wide legacy issues separately from new introduced issues.
75. Run the production build after page/component changes and distinguish build output count from the number of user-facing pages.
76. Inspect browser console errors, failed network requests, React warnings, hydration issues, and unhandled promise rejections where browser execution is available.
77. Check responsive layout at narrow and wide viewport sizes, avoiding horizontal overflow, clipped dialogs, invisible controls, and inaccessible hover-only actions.
78. Check error messages are actionable, avoid secrets, and preserve user-entered form data where retry is expected.
79. Check the component handles loading, empty, success, partial-success, validation, unauthorized, not-found, conflict, rate-limit, server-error, and offline states as applicable.
80. Check that stale UI cache does not outlive a mutation. Invalidate/refetch only the relevant query/state according to the existing architecture.
81. Check a successful response has not been mistaken for semantic success when the backend returns a task ID with pending execution.
82. Check task completion is awaited or polled appropriately and the user can identify pending versus completed processing.
83. Check external provider errors propagate to a truthful status rather than being caught and converted into fabricated success.
84. Check any retry operation cannot create duplicate jobs, settings writes, uploads, publications, or cleanup operations.
85. Check the component has no hidden coupling to unapproved Phase 8 watermark branding or unsupported layouts.
86. Cross-reference actual behavior with `PHASE_TRACKER.md`, the relevant approved prompt, and the actual backend route/service. Do not assume draft/archived prompts are mandatory scope.
87. Check related documentation only if it is directly affected by the verified implementation; preserve historical audit evidence.
88. Update the component dossier with actual file paths, symbols, endpoint, backend behavior, test commands, Pass A evidence and Pass B evidence.
89. If a required operation is not present in the current UI, mark it absent and verify whether the approved specification requires it; do not silently invent UI.
90. If a required capability is absent, identify the exact implementation/API/test gap and fix it only when inside approved scope and governance permits.
91. Before any edit, record targeted Git status/diff; after edits, verify unrelated working-tree changes and untracked assets remain untouched.
92. Do not make changes beyond approved Phase 1–7 scope; Phase 8 watermark branding remains deferred unless separately authorized.
93. If this component offers a layout choice, require a real local reference thumbnail for every supported option and verify the output renderer matches it.
94. If this component participates in monitoring/publishing, check destination identity and state synchronization, and obey the central private-upload gate; do not create a second real upload.
95. Never expose secrets, run destructive database operations, publish public/unlisted test videos, or delete user media while verifying this component.
96. Perform Pass A: independently map every acceptance criterion to implementation and test evidence. Record exact paths, symbols, commands and actual results.
97. Perform Pass B independently using alternate evidence; explicitly confirm, contradict or leave uncertain every material Pass A claim.
98. Repair eligible defects and repeat the complete relevant test loop; if governance or safety blocks a fix, record the exact blocker and continue independent work.
99. Final acceptance for `AN-04`: every mandatory control in Channel analytics polling, refresh and cooldown must have a real handler/contract, verified backend result, correct UI synchronization, passing relevant test, and independent Pass A/Pass B evidence.
100. Return a concise per-control matrix, exact files changed, tests and results, unresolved issues, and final component verdict. Do not declare PASS when evidence is missing.


---


## Page 6 — YouTube Channels (`/youtube-channels`)

### Page orchestration prompt

1. Work on Page 6 — YouTube Channels (`/youtube-channels`) as a page-level integration owner, using the master framework and all child prompts in this section.

2. Discover every actual child component and every interactive control from the current source, accessibility tree, and rendered page where browser inspection is available.

3. Create a route inventory and map each control to the relevant API endpoint, backend route/service, persistence or task path, and acceptance criterion.

4. Execute every child component prompt listed below, then inspect interactions between sibling components, shared state and cross-page navigation.

5. Test loading, empty, success, validation, auth failure, conflict, network failure, server failure and retry states applicable to the page.

6. Use component and integration tests. Run browser/E2E checks where available; label missing browser evidence as NOT VERIFIED.

7. Verify that every layout selection displays a real reference image and that selected layout ID reaches the correct renderer and appears in actual rendered output.

8. For monitoring, trace channel selection → poll → candidate discovery → decision → processing dispatch → persisted job progress → publishing destination → status result.

9. For Publish, verify normal mocked paths first and coordinate with the single central private YouTube upload gate; never create additional live uploads from component tests.

10. After all child components pass, test page-wide interactions, reloading, navigation away/back, shared API cache invalidation, stale response handling and component cleanup.

11. Perform a distinct Page Pass B using alternate evidence and record each finding against Page Pass A.

12. Fix authorized defects and rerun impacted tests until every mandatory page criterion passes or a specific governance/safety/external dependency blocks it.

13. Do not implement the proposed Phase 8 watermark feature. Keep the approved Phase 1–7 scope boundary.

14. Finish with a control-level matrix, endpoint coverage map, actual tests/results, files changed, evidence for both passes and unresolved blockers.


### Independent component prompts — each contains 100 required steps

### YT-01 — YouTube OAuth connect/callback/disconnect controls

**Primary files to discover:** frontend/app/youtube-channels/page.tsx and OAuth routes  
**Component focus:** Connect, callback/return state, disconnect/reconnect UI if present  
**Acceptance focus:** Verify state/CSRF correlation, failure and cancellation paths, token secrecy, backend account identity, stale authorization errors, and channel list refresh after OAuth. Never expose tokens in UI or logs.

Copy this complete prompt into the autonomous execution context for this component. Do not execute it in isolation from the master framework.

**100-step component prompt:**
1. Act as the autonomous owner of YouTube OAuth connect/callback/disconnect controls. Work only on the actual component discovered in the current checkout, not on an assumed or reconstructed UI.
2. Inspect frontend/app/youtube-channels/page.tsx and OAuth routes; follow imports and references to identify the real source files, tests, route and backend dependencies.
3. Component inventory: Connect, callback/return state, disconnect/reconnect UI if present. Discover the full list from the current UI and source. The list above is a focus guide, not permission to invent missing controls.
4. Acceptance focus: Verify state/CSRF correlation, failure and cancellation paths, token secrecy, backend account identity, stale authorization errors, and channel list refresh after OAuth. Never expose tokens in UI or logs.
5. Create or update dossier ID `YT-01` and link this component to its authoritative Phase/C-series acceptance criterion without redefining phase numbering.
6. Capture current behavior first: record the visible state, control labels, current handler, API call, server response, persisted state and known failure behavior.
7. List every individual button, input, dropdown, link, tab, selector, icon action, modal action and keyboard action in this component; give each a stable child control ID.
8. For every control, specify one positive test, one invalid/error test, one repeated-action/idempotency test where relevant, and one refresh/persistence or cross-page sync test where relevant.
9. Trace every mutation from browser event to API client, backend route, service, persistence/task/external provider and the final returned UI state.
10. Record the precise success assertion and the objective failure condition before changing code; never count a cosmetic animation or toast as proof of backend success.
11. Begin by opening the actual component, its parent, child components, types, API-client methods, and tests; do not trust a previous report without checking the current checkout.
12. List the exact visible controls that belong to this component, including icon-only buttons, links styled as buttons, keyboard shortcuts, toggles, dropdown options, modal actions, and any hidden action revealed by state.
13. For each control, state the requirement and observable success condition before testing it; map each requirement to the approved roadmap item without changing canonical phase numbers.
14. Check whether the control is intentionally non-interactive. If so, it must be semantically non-interactive and cannot imply that an unavailable action will occur.
15. Check accessible name, label/description, role, focusability, keyboard activation, disabled state, focus order, and whether focus returns appropriately after a dialog closes.
16. Trace the real event handler. Reject empty callbacks, console-only callbacks, hard-coded results, no-op links, timer-only simulation, and UI-only state mutation for backend operations.
17. Locate the corresponding API-client method and verify HTTP method, route path, body/query parameters, identifiers, headers/auth, response type, status-code handling, and timeout behavior.
18. Confirm that the route exists in the current backend application and is included under the actual router prefix. Do not infer endpoint existence from a frontend URL string.
19. Inspect backend validation, authorization, ownership checks, service calls, transaction boundaries, queue/task dispatch, and error mapping for the operation.
20. Identify the authoritative persisted record or external response that proves success. Do not use only a toast, button animation, or HTTP 200 as proof of the intended side effect.
21. Check that the frontend consumes the real response and maps returned identifiers/state correctly. Detect hard-coded status strings and mismatched field names.
22. Test the normal successful action using an isolated fixture or safe test record wherever available.
23. Test missing, malformed, stale, or unauthorized identifiers without modifying real user data.
24. Test the expected validation boundary conditions and verify the UI shows a useful message rather than silently dropping the request.
25. Test a server-side failure and confirm no false success indicator appears.
26. Test a network timeout/connection reset and verify the UI does not assume that the backend definitely failed if the outcome may be ambiguous.
27. Test loading indicators and confirm they clear on success, error, cancellation, component unmount, and every supported early return.
28. Test double-click, repeated Enter, quick toggle changes, duplicate network retries, and stale component state for unintended duplicate actions.
29. Check race handling if the action operates on mutable status, queue positions, decisions, settings, uploads, or publishing state.
30. Check that stale/out-of-order responses cannot overwrite a newer state. Use request cancellation, version checks, or existing conventions where needed and approved.
31. Check the response status is translated to the correct UI state, including pending/in-progress, completed, partial failure, failed, cancelled, and conflict states where applicable.
32. Check whether optimistic UI is used. If so, ensure rollback or reconciliation occurs when the backend rejects the change.
33. Check whether the changed state should survive page refresh/reopen; if yes, reload and compare the visible state to the backend-authoritative result.
34. Check whether the state is shared with other pages/components. Trigger the action and inspect every relevant surface for stale data.
35. Check that filters, sorting, selection, pagination, tabs, and the current detail item behave correctly after the operation changes data.
36. Check behavior when the list is empty, the API returns null/partial optional data, a media asset is missing, or a provider is temporarily unavailable.
37. Check timezones, timestamps, duration units, percentages, byte sizes, numeric formatting, and enum labels against backend semantics.
38. Check no credential, OAuth token, API key, signed URL, or private user payload is exposed in visible UI, ordinary logs, test output, or screenshots.
39. Check that test-mode fallbacks or synthetic fixtures can only be activated by the repository-defined trusted test context, never by user-controlled substring or arbitrary request fields.
40. Check the action does not add, restore, expose, or invoke caption/subtitle features. Internal transcription may remain for approved analysis and metadata purposes.
41. Check the action does not route to Ollama or require Ollama environment variables. Preserve approved cloud-hosted models even if their names contain Llama.
42. Check the operation cannot accidentally publish to a source/monitoring channel instead of an explicitly configured destination.
43. Where an action creates a job/task, verify the persisted job ID is retained and Celery dispatch occurs only at the intended transition.
44. Where an action updates a task, verify the backend state transition is valid, durable, and visible on subsequent reads.
45. Where an action creates or deletes a file, verify storage path containment, ownership, retention policy, and cleanup behavior using isolated files only.
46. Where a control selects a layout, verify the selected ID maps to a supported renderer option rather than only changing the visual highlight.
47. Where a control shows a layout thumbnail, verify the reference asset exists in the production build, has the correct accessible text, and truthfully represents output composition.
48. Where the component displays progress, verify it is sourced from authoritative progress/status fields and cannot display completion before the task completes.
49. Where the component refreshes/polls, verify intervals, overlap, cooldown, backoff, and unmount cleanup against the actual code contract.
50. Where external providers are involved, test mocked/sandbox cases first and ensure no accidental external side effect is triggered by an ordinary test.
51. For the private YouTube acceptance upload, do not use this component test to generate another upload. The one real upload is centrally orchestrated and idempotently gated under the master framework.
52. Inspect the relevant unit/component test and add a regression test for each repaired defect where test infrastructure permits.
53. Run the smallest test covering this component first and record the exact command and actual exit result.
54. Run the relevant API/backend integration test where it can be proven safe and isolated.
55. Run the relevant browser/E2E test if available; do not describe static source inspection as a browser test.
56. Collect actual request/response evidence with secrets redacted. Link to the logs or test output that substantiate the result.
57. Compare the user-visible message/status with the actual backend response and persisted state.
58. Conduct Pass A by tracing requirements to implementation and successful tests.
59. Conduct Pass B independently using an alternate path such as persisted state, route registration, event log, task state, rendered output, refresh behavior, or a different test assertion.
60. If Pass A and Pass B disagree, investigate and document the discrepancy; do not average the results or silently pick the favorable one.
61. Classify a failure as UI defect, API contract mismatch, backend behavior defect, persistence defect, concurrency defect, configuration defect, missing test/evidence, or scope ambiguity.
62. Fix only defects within approved Phase 1–7 requirements and only through the governance process required by the freeze rules.
63. Before changing a shared API client, component, schema, backend route, or frozen domain, identify all affected pages and regression tests.
64. Keep the code change minimal and preserve pre-existing Git modifications and untracked files.
65. Never execute blanket Git reset/clean/checkout/restore commands or replace a whole file to make a small repair.
66. After a repair, rerun the failing reproduction, relevant component test, API/backend tests, and affected page regression checks.
67. Independently repeat Pass B after the repair, using evidence distinct from the original fix path where reasonably possible.
68. If the test fails, continue the diagnose/fix/retest loop within scope; if the failure requires unavailable authorization or unsafe operation, mark it blocked and continue unrelated work.
69. Do not stop at the first failed test if the cause is repairable within scope. Do not loop indefinitely if a genuine external or governance blocker exists.
70. Check that test teardown completes and does not silently mask failures; do not change global fixtures unless required and governed.
71. Confirm test DB isolation before any database mutation. Never migrate, drop, reset, or clean the operational clipforge database.
72. Confirm no test publishes an actual video except the one centralized, explicit, private acceptance upload authorized by the user.
73. Confirm no generated test file overwrites existing uploads or outputs and no cleanup task deletes user-owned media.
74. Run TypeScript and lint checks against the changed frontend where possible. Report repository-wide legacy issues separately from new introduced issues.
75. Run the production build after page/component changes and distinguish build output count from the number of user-facing pages.
76. Inspect browser console errors, failed network requests, React warnings, hydration issues, and unhandled promise rejections where browser execution is available.
77. Check responsive layout at narrow and wide viewport sizes, avoiding horizontal overflow, clipped dialogs, invisible controls, and inaccessible hover-only actions.
78. Check error messages are actionable, avoid secrets, and preserve user-entered form data where retry is expected.
79. Check the component handles loading, empty, success, partial-success, validation, unauthorized, not-found, conflict, rate-limit, server-error, and offline states as applicable.
80. Check that stale UI cache does not outlive a mutation. Invalidate/refetch only the relevant query/state according to the existing architecture.
81. Check a successful response has not been mistaken for semantic success when the backend returns a task ID with pending execution.
82. Check task completion is awaited or polled appropriately and the user can identify pending versus completed processing.
83. Check external provider errors propagate to a truthful status rather than being caught and converted into fabricated success.
84. Check any retry operation cannot create duplicate jobs, settings writes, uploads, publications, or cleanup operations.
85. Check the component has no hidden coupling to unapproved Phase 8 watermark branding or unsupported layouts.
86. Cross-reference actual behavior with `PHASE_TRACKER.md`, the relevant approved prompt, and the actual backend route/service. Do not assume draft/archived prompts are mandatory scope.
87. Check related documentation only if it is directly affected by the verified implementation; preserve historical audit evidence.
88. Update the component dossier with actual file paths, symbols, endpoint, backend behavior, test commands, Pass A evidence and Pass B evidence.
89. If a required operation is not present in the current UI, mark it absent and verify whether the approved specification requires it; do not silently invent UI.
90. If a required capability is absent, identify the exact implementation/API/test gap and fix it only when inside approved scope and governance permits.
91. Before any edit, record targeted Git status/diff; after edits, verify unrelated working-tree changes and untracked assets remain untouched.
92. Do not make changes beyond approved Phase 1–7 scope; Phase 8 watermark branding remains deferred unless separately authorized.
93. If this component offers a layout choice, require a real local reference thumbnail for every supported option and verify the output renderer matches it.
94. If this component participates in monitoring/publishing, check destination identity and state synchronization, and obey the central private-upload gate; do not create a second real upload.
95. Never expose secrets, run destructive database operations, publish public/unlisted test videos, or delete user media while verifying this component.
96. Perform Pass A: independently map every acceptance criterion to implementation and test evidence. Record exact paths, symbols, commands and actual results.
97. Perform Pass B independently using alternate evidence; explicitly confirm, contradict or leave uncertain every material Pass A claim.
98. Repair eligible defects and repeat the complete relevant test loop; if governance or safety blocks a fix, record the exact blocker and continue independent work.
99. Final acceptance for `YT-01`: every mandatory control in YouTube OAuth connect/callback/disconnect controls must have a real handler/contract, verified backend result, correct UI synchronization, passing relevant test, and independent Pass A/Pass B evidence.
100. Return a concise per-control matrix, exact files changed, tests and results, unresolved issues, and final component verdict. Do not declare PASS when evidence is missing.


---

### YT-02 — Channel list and source-vs-destination classification

**Primary files to discover:** Channel-management UI and channel management APIs/models  
**Component focus:** Channel rows/cards, set destination/source role, select/remove actions where present  
**Acceptance focus:** Verify unique channel IDs, `is_destination` semantics, separation between monitored sources and publishing destinations, persistence, selection stability, and publishing restrictions against source-only channels.

Copy this complete prompt into the autonomous execution context for this component. Do not execute it in isolation from the master framework.

**100-step component prompt:**
1. Act as the autonomous owner of Channel list and source-vs-destination classification. Work only on the actual component discovered in the current checkout, not on an assumed or reconstructed UI.
2. Inspect Channel-management UI and channel management APIs/models; follow imports and references to identify the real source files, tests, route and backend dependencies.
3. Component inventory: Channel rows/cards, set destination/source role, select/remove actions where present. Discover the full list from the current UI and source. The list above is a focus guide, not permission to invent missing controls.
4. Acceptance focus: Verify unique channel IDs, `is_destination` semantics, separation between monitored sources and publishing destinations, persistence, selection stability, and publishing restrictions against source-only channels.
5. Create or update dossier ID `YT-02` and link this component to its authoritative Phase/C-series acceptance criterion without redefining phase numbering.
6. Capture current behavior first: record the visible state, control labels, current handler, API call, server response, persisted state and known failure behavior.
7. List every individual button, input, dropdown, link, tab, selector, icon action, modal action and keyboard action in this component; give each a stable child control ID.
8. For every control, specify one positive test, one invalid/error test, one repeated-action/idempotency test where relevant, and one refresh/persistence or cross-page sync test where relevant.
9. Trace every mutation from browser event to API client, backend route, service, persistence/task/external provider and the final returned UI state.
10. Record the precise success assertion and the objective failure condition before changing code; never count a cosmetic animation or toast as proof of backend success.
11. Begin by opening the actual component, its parent, child components, types, API-client methods, and tests; do not trust a previous report without checking the current checkout.
12. List the exact visible controls that belong to this component, including icon-only buttons, links styled as buttons, keyboard shortcuts, toggles, dropdown options, modal actions, and any hidden action revealed by state.
13. For each control, state the requirement and observable success condition before testing it; map each requirement to the approved roadmap item without changing canonical phase numbers.
14. Check whether the control is intentionally non-interactive. If so, it must be semantically non-interactive and cannot imply that an unavailable action will occur.
15. Check accessible name, label/description, role, focusability, keyboard activation, disabled state, focus order, and whether focus returns appropriately after a dialog closes.
16. Trace the real event handler. Reject empty callbacks, console-only callbacks, hard-coded results, no-op links, timer-only simulation, and UI-only state mutation for backend operations.
17. Locate the corresponding API-client method and verify HTTP method, route path, body/query parameters, identifiers, headers/auth, response type, status-code handling, and timeout behavior.
18. Confirm that the route exists in the current backend application and is included under the actual router prefix. Do not infer endpoint existence from a frontend URL string.
19. Inspect backend validation, authorization, ownership checks, service calls, transaction boundaries, queue/task dispatch, and error mapping for the operation.
20. Identify the authoritative persisted record or external response that proves success. Do not use only a toast, button animation, or HTTP 200 as proof of the intended side effect.
21. Check that the frontend consumes the real response and maps returned identifiers/state correctly. Detect hard-coded status strings and mismatched field names.
22. Test the normal successful action using an isolated fixture or safe test record wherever available.
23. Test missing, malformed, stale, or unauthorized identifiers without modifying real user data.
24. Test the expected validation boundary conditions and verify the UI shows a useful message rather than silently dropping the request.
25. Test a server-side failure and confirm no false success indicator appears.
26. Test a network timeout/connection reset and verify the UI does not assume that the backend definitely failed if the outcome may be ambiguous.
27. Test loading indicators and confirm they clear on success, error, cancellation, component unmount, and every supported early return.
28. Test double-click, repeated Enter, quick toggle changes, duplicate network retries, and stale component state for unintended duplicate actions.
29. Check race handling if the action operates on mutable status, queue positions, decisions, settings, uploads, or publishing state.
30. Check that stale/out-of-order responses cannot overwrite a newer state. Use request cancellation, version checks, or existing conventions where needed and approved.
31. Check the response status is translated to the correct UI state, including pending/in-progress, completed, partial failure, failed, cancelled, and conflict states where applicable.
32. Check whether optimistic UI is used. If so, ensure rollback or reconciliation occurs when the backend rejects the change.
33. Check whether the changed state should survive page refresh/reopen; if yes, reload and compare the visible state to the backend-authoritative result.
34. Check whether the state is shared with other pages/components. Trigger the action and inspect every relevant surface for stale data.
35. Check that filters, sorting, selection, pagination, tabs, and the current detail item behave correctly after the operation changes data.
36. Check behavior when the list is empty, the API returns null/partial optional data, a media asset is missing, or a provider is temporarily unavailable.
37. Check timezones, timestamps, duration units, percentages, byte sizes, numeric formatting, and enum labels against backend semantics.
38. Check no credential, OAuth token, API key, signed URL, or private user payload is exposed in visible UI, ordinary logs, test output, or screenshots.
39. Check that test-mode fallbacks or synthetic fixtures can only be activated by the repository-defined trusted test context, never by user-controlled substring or arbitrary request fields.
40. Check the action does not add, restore, expose, or invoke caption/subtitle features. Internal transcription may remain for approved analysis and metadata purposes.
41. Check the action does not route to Ollama or require Ollama environment variables. Preserve approved cloud-hosted models even if their names contain Llama.
42. Check the operation cannot accidentally publish to a source/monitoring channel instead of an explicitly configured destination.
43. Where an action creates a job/task, verify the persisted job ID is retained and Celery dispatch occurs only at the intended transition.
44. Where an action updates a task, verify the backend state transition is valid, durable, and visible on subsequent reads.
45. Where an action creates or deletes a file, verify storage path containment, ownership, retention policy, and cleanup behavior using isolated files only.
46. Where a control selects a layout, verify the selected ID maps to a supported renderer option rather than only changing the visual highlight.
47. Where a control shows a layout thumbnail, verify the reference asset exists in the production build, has the correct accessible text, and truthfully represents output composition.
48. Where the component displays progress, verify it is sourced from authoritative progress/status fields and cannot display completion before the task completes.
49. Where the component refreshes/polls, verify intervals, overlap, cooldown, backoff, and unmount cleanup against the actual code contract.
50. Where external providers are involved, test mocked/sandbox cases first and ensure no accidental external side effect is triggered by an ordinary test.
51. For the private YouTube acceptance upload, do not use this component test to generate another upload. The one real upload is centrally orchestrated and idempotently gated under the master framework.
52. Inspect the relevant unit/component test and add a regression test for each repaired defect where test infrastructure permits.
53. Run the smallest test covering this component first and record the exact command and actual exit result.
54. Run the relevant API/backend integration test where it can be proven safe and isolated.
55. Run the relevant browser/E2E test if available; do not describe static source inspection as a browser test.
56. Collect actual request/response evidence with secrets redacted. Link to the logs or test output that substantiate the result.
57. Compare the user-visible message/status with the actual backend response and persisted state.
58. Conduct Pass A by tracing requirements to implementation and successful tests.
59. Conduct Pass B independently using an alternate path such as persisted state, route registration, event log, task state, rendered output, refresh behavior, or a different test assertion.
60. If Pass A and Pass B disagree, investigate and document the discrepancy; do not average the results or silently pick the favorable one.
61. Classify a failure as UI defect, API contract mismatch, backend behavior defect, persistence defect, concurrency defect, configuration defect, missing test/evidence, or scope ambiguity.
62. Fix only defects within approved Phase 1–7 requirements and only through the governance process required by the freeze rules.
63. Before changing a shared API client, component, schema, backend route, or frozen domain, identify all affected pages and regression tests.
64. Keep the code change minimal and preserve pre-existing Git modifications and untracked files.
65. Never execute blanket Git reset/clean/checkout/restore commands or replace a whole file to make a small repair.
66. After a repair, rerun the failing reproduction, relevant component test, API/backend tests, and affected page regression checks.
67. Independently repeat Pass B after the repair, using evidence distinct from the original fix path where reasonably possible.
68. If the test fails, continue the diagnose/fix/retest loop within scope; if the failure requires unavailable authorization or unsafe operation, mark it blocked and continue unrelated work.
69. Do not stop at the first failed test if the cause is repairable within scope. Do not loop indefinitely if a genuine external or governance blocker exists.
70. Check that test teardown completes and does not silently mask failures; do not change global fixtures unless required and governed.
71. Confirm test DB isolation before any database mutation. Never migrate, drop, reset, or clean the operational clipforge database.
72. Confirm no test publishes an actual video except the one centralized, explicit, private acceptance upload authorized by the user.
73. Confirm no generated test file overwrites existing uploads or outputs and no cleanup task deletes user-owned media.
74. Run TypeScript and lint checks against the changed frontend where possible. Report repository-wide legacy issues separately from new introduced issues.
75. Run the production build after page/component changes and distinguish build output count from the number of user-facing pages.
76. Inspect browser console errors, failed network requests, React warnings, hydration issues, and unhandled promise rejections where browser execution is available.
77. Check responsive layout at narrow and wide viewport sizes, avoiding horizontal overflow, clipped dialogs, invisible controls, and inaccessible hover-only actions.
78. Check error messages are actionable, avoid secrets, and preserve user-entered form data where retry is expected.
79. Check the component handles loading, empty, success, partial-success, validation, unauthorized, not-found, conflict, rate-limit, server-error, and offline states as applicable.
80. Check that stale UI cache does not outlive a mutation. Invalidate/refetch only the relevant query/state according to the existing architecture.
81. Check a successful response has not been mistaken for semantic success when the backend returns a task ID with pending execution.
82. Check task completion is awaited or polled appropriately and the user can identify pending versus completed processing.
83. Check external provider errors propagate to a truthful status rather than being caught and converted into fabricated success.
84. Check any retry operation cannot create duplicate jobs, settings writes, uploads, publications, or cleanup operations.
85. Check the component has no hidden coupling to unapproved Phase 8 watermark branding or unsupported layouts.
86. Cross-reference actual behavior with `PHASE_TRACKER.md`, the relevant approved prompt, and the actual backend route/service. Do not assume draft/archived prompts are mandatory scope.
87. Check related documentation only if it is directly affected by the verified implementation; preserve historical audit evidence.
88. Update the component dossier with actual file paths, symbols, endpoint, backend behavior, test commands, Pass A evidence and Pass B evidence.
89. If a required operation is not present in the current UI, mark it absent and verify whether the approved specification requires it; do not silently invent UI.
90. If a required capability is absent, identify the exact implementation/API/test gap and fix it only when inside approved scope and governance permits.
91. Before any edit, record targeted Git status/diff; after edits, verify unrelated working-tree changes and untracked assets remain untouched.
92. Do not make changes beyond approved Phase 1–7 scope; Phase 8 watermark branding remains deferred unless separately authorized.
93. If this component offers a layout choice, require a real local reference thumbnail for every supported option and verify the output renderer matches it.
94. If this component participates in monitoring/publishing, check destination identity and state synchronization, and obey the central private-upload gate; do not create a second real upload.
95. Never expose secrets, run destructive database operations, publish public/unlisted test videos, or delete user media while verifying this component.
96. Perform Pass A: independently map every acceptance criterion to implementation and test evidence. Record exact paths, symbols, commands and actual results.
97. Perform Pass B independently using alternate evidence; explicitly confirm, contradict or leave uncertain every material Pass A claim.
98. Repair eligible defects and repeat the complete relevant test loop; if governance or safety blocks a fix, record the exact blocker and continue independent work.
99. Final acceptance for `YT-02`: every mandatory control in Channel list and source-vs-destination classification must have a real handler/contract, verified backend result, correct UI synchronization, passing relevant test, and independent Pass A/Pass B evidence.
100. Return a concise per-control matrix, exact files changed, tests and results, unresolved issues, and final component verdict. Do not declare PASS when evidence is missing.


---

### YT-03 — Channel monitoring configuration and polling controls

**Primary files to discover:** YouTube channel management UI and monitor configuration/polling APIs  
**Component focus:** Per-channel monitor toggle/configuration, refresh status, interval control if present  
**Acceptance focus:** Verify monitoring actually starts/stops through backend configuration, persisted state, correct channel ID, polling/cooldown/rate limit, error/retry behavior, and discovered-video synchronization into Automation.

Copy this complete prompt into the autonomous execution context for this component. Do not execute it in isolation from the master framework.

**100-step component prompt:**
1. Act as the autonomous owner of Channel monitoring configuration and polling controls. Work only on the actual component discovered in the current checkout, not on an assumed or reconstructed UI.
2. Inspect YouTube channel management UI and monitor configuration/polling APIs; follow imports and references to identify the real source files, tests, route and backend dependencies.
3. Component inventory: Per-channel monitor toggle/configuration, refresh status, interval control if present. Discover the full list from the current UI and source. The list above is a focus guide, not permission to invent missing controls.
4. Acceptance focus: Verify monitoring actually starts/stops through backend configuration, persisted state, correct channel ID, polling/cooldown/rate limit, error/retry behavior, and discovered-video synchronization into Automation.
5. Create or update dossier ID `YT-03` and link this component to its authoritative Phase/C-series acceptance criterion without redefining phase numbering.
6. Capture current behavior first: record the visible state, control labels, current handler, API call, server response, persisted state and known failure behavior.
7. List every individual button, input, dropdown, link, tab, selector, icon action, modal action and keyboard action in this component; give each a stable child control ID.
8. For every control, specify one positive test, one invalid/error test, one repeated-action/idempotency test where relevant, and one refresh/persistence or cross-page sync test where relevant.
9. Trace every mutation from browser event to API client, backend route, service, persistence/task/external provider and the final returned UI state.
10. Record the precise success assertion and the objective failure condition before changing code; never count a cosmetic animation or toast as proof of backend success.
11. Begin by opening the actual component, its parent, child components, types, API-client methods, and tests; do not trust a previous report without checking the current checkout.
12. List the exact visible controls that belong to this component, including icon-only buttons, links styled as buttons, keyboard shortcuts, toggles, dropdown options, modal actions, and any hidden action revealed by state.
13. For each control, state the requirement and observable success condition before testing it; map each requirement to the approved roadmap item without changing canonical phase numbers.
14. Check whether the control is intentionally non-interactive. If so, it must be semantically non-interactive and cannot imply that an unavailable action will occur.
15. Check accessible name, label/description, role, focusability, keyboard activation, disabled state, focus order, and whether focus returns appropriately after a dialog closes.
16. Trace the real event handler. Reject empty callbacks, console-only callbacks, hard-coded results, no-op links, timer-only simulation, and UI-only state mutation for backend operations.
17. Locate the corresponding API-client method and verify HTTP method, route path, body/query parameters, identifiers, headers/auth, response type, status-code handling, and timeout behavior.
18. Confirm that the route exists in the current backend application and is included under the actual router prefix. Do not infer endpoint existence from a frontend URL string.
19. Inspect backend validation, authorization, ownership checks, service calls, transaction boundaries, queue/task dispatch, and error mapping for the operation.
20. Identify the authoritative persisted record or external response that proves success. Do not use only a toast, button animation, or HTTP 200 as proof of the intended side effect.
21. Check that the frontend consumes the real response and maps returned identifiers/state correctly. Detect hard-coded status strings and mismatched field names.
22. Test the normal successful action using an isolated fixture or safe test record wherever available.
23. Test missing, malformed, stale, or unauthorized identifiers without modifying real user data.
24. Test the expected validation boundary conditions and verify the UI shows a useful message rather than silently dropping the request.
25. Test a server-side failure and confirm no false success indicator appears.
26. Test a network timeout/connection reset and verify the UI does not assume that the backend definitely failed if the outcome may be ambiguous.
27. Test loading indicators and confirm they clear on success, error, cancellation, component unmount, and every supported early return.
28. Test double-click, repeated Enter, quick toggle changes, duplicate network retries, and stale component state for unintended duplicate actions.
29. Check race handling if the action operates on mutable status, queue positions, decisions, settings, uploads, or publishing state.
30. Check that stale/out-of-order responses cannot overwrite a newer state. Use request cancellation, version checks, or existing conventions where needed and approved.
31. Check the response status is translated to the correct UI state, including pending/in-progress, completed, partial failure, failed, cancelled, and conflict states where applicable.
32. Check whether optimistic UI is used. If so, ensure rollback or reconciliation occurs when the backend rejects the change.
33. Check whether the changed state should survive page refresh/reopen; if yes, reload and compare the visible state to the backend-authoritative result.
34. Check whether the state is shared with other pages/components. Trigger the action and inspect every relevant surface for stale data.
35. Check that filters, sorting, selection, pagination, tabs, and the current detail item behave correctly after the operation changes data.
36. Check behavior when the list is empty, the API returns null/partial optional data, a media asset is missing, or a provider is temporarily unavailable.
37. Check timezones, timestamps, duration units, percentages, byte sizes, numeric formatting, and enum labels against backend semantics.
38. Check no credential, OAuth token, API key, signed URL, or private user payload is exposed in visible UI, ordinary logs, test output, or screenshots.
39. Check that test-mode fallbacks or synthetic fixtures can only be activated by the repository-defined trusted test context, never by user-controlled substring or arbitrary request fields.
40. Check the action does not add, restore, expose, or invoke caption/subtitle features. Internal transcription may remain for approved analysis and metadata purposes.
41. Check the action does not route to Ollama or require Ollama environment variables. Preserve approved cloud-hosted models even if their names contain Llama.
42. Check the operation cannot accidentally publish to a source/monitoring channel instead of an explicitly configured destination.
43. Where an action creates a job/task, verify the persisted job ID is retained and Celery dispatch occurs only at the intended transition.
44. Where an action updates a task, verify the backend state transition is valid, durable, and visible on subsequent reads.
45. Where an action creates or deletes a file, verify storage path containment, ownership, retention policy, and cleanup behavior using isolated files only.
46. Where a control selects a layout, verify the selected ID maps to a supported renderer option rather than only changing the visual highlight.
47. Where a control shows a layout thumbnail, verify the reference asset exists in the production build, has the correct accessible text, and truthfully represents output composition.
48. Where the component displays progress, verify it is sourced from authoritative progress/status fields and cannot display completion before the task completes.
49. Where the component refreshes/polls, verify intervals, overlap, cooldown, backoff, and unmount cleanup against the actual code contract.
50. Where external providers are involved, test mocked/sandbox cases first and ensure no accidental external side effect is triggered by an ordinary test.
51. For the private YouTube acceptance upload, do not use this component test to generate another upload. The one real upload is centrally orchestrated and idempotently gated under the master framework.
52. Inspect the relevant unit/component test and add a regression test for each repaired defect where test infrastructure permits.
53. Run the smallest test covering this component first and record the exact command and actual exit result.
54. Run the relevant API/backend integration test where it can be proven safe and isolated.
55. Run the relevant browser/E2E test if available; do not describe static source inspection as a browser test.
56. Collect actual request/response evidence with secrets redacted. Link to the logs or test output that substantiate the result.
57. Compare the user-visible message/status with the actual backend response and persisted state.
58. Conduct Pass A by tracing requirements to implementation and successful tests.
59. Conduct Pass B independently using an alternate path such as persisted state, route registration, event log, task state, rendered output, refresh behavior, or a different test assertion.
60. If Pass A and Pass B disagree, investigate and document the discrepancy; do not average the results or silently pick the favorable one.
61. Classify a failure as UI defect, API contract mismatch, backend behavior defect, persistence defect, concurrency defect, configuration defect, missing test/evidence, or scope ambiguity.
62. Fix only defects within approved Phase 1–7 requirements and only through the governance process required by the freeze rules.
63. Before changing a shared API client, component, schema, backend route, or frozen domain, identify all affected pages and regression tests.
64. Keep the code change minimal and preserve pre-existing Git modifications and untracked files.
65. Never execute blanket Git reset/clean/checkout/restore commands or replace a whole file to make a small repair.
66. After a repair, rerun the failing reproduction, relevant component test, API/backend tests, and affected page regression checks.
67. Independently repeat Pass B after the repair, using evidence distinct from the original fix path where reasonably possible.
68. If the test fails, continue the diagnose/fix/retest loop within scope; if the failure requires unavailable authorization or unsafe operation, mark it blocked and continue unrelated work.
69. Do not stop at the first failed test if the cause is repairable within scope. Do not loop indefinitely if a genuine external or governance blocker exists.
70. Check that test teardown completes and does not silently mask failures; do not change global fixtures unless required and governed.
71. Confirm test DB isolation before any database mutation. Never migrate, drop, reset, or clean the operational clipforge database.
72. Confirm no test publishes an actual video except the one centralized, explicit, private acceptance upload authorized by the user.
73. Confirm no generated test file overwrites existing uploads or outputs and no cleanup task deletes user-owned media.
74. Run TypeScript and lint checks against the changed frontend where possible. Report repository-wide legacy issues separately from new introduced issues.
75. Run the production build after page/component changes and distinguish build output count from the number of user-facing pages.
76. Inspect browser console errors, failed network requests, React warnings, hydration issues, and unhandled promise rejections where browser execution is available.
77. Check responsive layout at narrow and wide viewport sizes, avoiding horizontal overflow, clipped dialogs, invisible controls, and inaccessible hover-only actions.
78. Check error messages are actionable, avoid secrets, and preserve user-entered form data where retry is expected.
79. Check the component handles loading, empty, success, partial-success, validation, unauthorized, not-found, conflict, rate-limit, server-error, and offline states as applicable.
80. Check that stale UI cache does not outlive a mutation. Invalidate/refetch only the relevant query/state according to the existing architecture.
81. Check a successful response has not been mistaken for semantic success when the backend returns a task ID with pending execution.
82. Check task completion is awaited or polled appropriately and the user can identify pending versus completed processing.
83. Check external provider errors propagate to a truthful status rather than being caught and converted into fabricated success.
84. Check any retry operation cannot create duplicate jobs, settings writes, uploads, publications, or cleanup operations.
85. Check the component has no hidden coupling to unapproved Phase 8 watermark branding or unsupported layouts.
86. Cross-reference actual behavior with `PHASE_TRACKER.md`, the relevant approved prompt, and the actual backend route/service. Do not assume draft/archived prompts are mandatory scope.
87. Check related documentation only if it is directly affected by the verified implementation; preserve historical audit evidence.
88. Update the component dossier with actual file paths, symbols, endpoint, backend behavior, test commands, Pass A evidence and Pass B evidence.
89. If a required operation is not present in the current UI, mark it absent and verify whether the approved specification requires it; do not silently invent UI.
90. If a required capability is absent, identify the exact implementation/API/test gap and fix it only when inside approved scope and governance permits.
91. Before any edit, record targeted Git status/diff; after edits, verify unrelated working-tree changes and untracked assets remain untouched.
92. Do not make changes beyond approved Phase 1–7 scope; Phase 8 watermark branding remains deferred unless separately authorized.
93. If this component offers a layout choice, require a real local reference thumbnail for every supported option and verify the output renderer matches it.
94. If this component participates in monitoring/publishing, check destination identity and state synchronization, and obey the central private-upload gate; do not create a second real upload.
95. Never expose secrets, run destructive database operations, publish public/unlisted test videos, or delete user media while verifying this component.
96. Perform Pass A: independently map every acceptance criterion to implementation and test evidence. Record exact paths, symbols, commands and actual results.
97. Perform Pass B independently using alternate evidence; explicitly confirm, contradict or leave uncertain every material Pass A claim.
98. Repair eligible defects and repeat the complete relevant test loop; if governance or safety blocks a fix, record the exact blocker and continue independent work.
99. Final acceptance for `YT-03`: every mandatory control in Channel monitoring configuration and polling controls must have a real handler/contract, verified backend result, correct UI synchronization, passing relevant test, and independent Pass A/Pass B evidence.
100. Return a concise per-control matrix, exact files changed, tests and results, unresolved issues, and final component verdict. Do not declare PASS when evidence is missing.


---

### YT-04 — Channel statistics, refresh and failures

**Primary files to discover:** Channel stats cards and `/stats`/metrics endpoints as actually registered  
**Component focus:** Manual refresh, auto-poll state, KPI fields, rate-limit feedback  
**Acceptance focus:** Verify correct endpoint, coalescing and cooldown behavior, data and timestamp freshness, stale-state indicators, backoff after provider errors, and no unhandled polling after leaving the page.

Copy this complete prompt into the autonomous execution context for this component. Do not execute it in isolation from the master framework.

**100-step component prompt:**
1. Act as the autonomous owner of Channel statistics, refresh and failures. Work only on the actual component discovered in the current checkout, not on an assumed or reconstructed UI.
2. Inspect Channel stats cards and `/stats`/metrics endpoints as actually registered; follow imports and references to identify the real source files, tests, route and backend dependencies.
3. Component inventory: Manual refresh, auto-poll state, KPI fields, rate-limit feedback. Discover the full list from the current UI and source. The list above is a focus guide, not permission to invent missing controls.
4. Acceptance focus: Verify correct endpoint, coalescing and cooldown behavior, data and timestamp freshness, stale-state indicators, backoff after provider errors, and no unhandled polling after leaving the page.
5. Create or update dossier ID `YT-04` and link this component to its authoritative Phase/C-series acceptance criterion without redefining phase numbering.
6. Capture current behavior first: record the visible state, control labels, current handler, API call, server response, persisted state and known failure behavior.
7. List every individual button, input, dropdown, link, tab, selector, icon action, modal action and keyboard action in this component; give each a stable child control ID.
8. For every control, specify one positive test, one invalid/error test, one repeated-action/idempotency test where relevant, and one refresh/persistence or cross-page sync test where relevant.
9. Trace every mutation from browser event to API client, backend route, service, persistence/task/external provider and the final returned UI state.
10. Record the precise success assertion and the objective failure condition before changing code; never count a cosmetic animation or toast as proof of backend success.
11. Begin by opening the actual component, its parent, child components, types, API-client methods, and tests; do not trust a previous report without checking the current checkout.
12. List the exact visible controls that belong to this component, including icon-only buttons, links styled as buttons, keyboard shortcuts, toggles, dropdown options, modal actions, and any hidden action revealed by state.
13. For each control, state the requirement and observable success condition before testing it; map each requirement to the approved roadmap item without changing canonical phase numbers.
14. Check whether the control is intentionally non-interactive. If so, it must be semantically non-interactive and cannot imply that an unavailable action will occur.
15. Check accessible name, label/description, role, focusability, keyboard activation, disabled state, focus order, and whether focus returns appropriately after a dialog closes.
16. Trace the real event handler. Reject empty callbacks, console-only callbacks, hard-coded results, no-op links, timer-only simulation, and UI-only state mutation for backend operations.
17. Locate the corresponding API-client method and verify HTTP method, route path, body/query parameters, identifiers, headers/auth, response type, status-code handling, and timeout behavior.
18. Confirm that the route exists in the current backend application and is included under the actual router prefix. Do not infer endpoint existence from a frontend URL string.
19. Inspect backend validation, authorization, ownership checks, service calls, transaction boundaries, queue/task dispatch, and error mapping for the operation.
20. Identify the authoritative persisted record or external response that proves success. Do not use only a toast, button animation, or HTTP 200 as proof of the intended side effect.
21. Check that the frontend consumes the real response and maps returned identifiers/state correctly. Detect hard-coded status strings and mismatched field names.
22. Test the normal successful action using an isolated fixture or safe test record wherever available.
23. Test missing, malformed, stale, or unauthorized identifiers without modifying real user data.
24. Test the expected validation boundary conditions and verify the UI shows a useful message rather than silently dropping the request.
25. Test a server-side failure and confirm no false success indicator appears.
26. Test a network timeout/connection reset and verify the UI does not assume that the backend definitely failed if the outcome may be ambiguous.
27. Test loading indicators and confirm they clear on success, error, cancellation, component unmount, and every supported early return.
28. Test double-click, repeated Enter, quick toggle changes, duplicate network retries, and stale component state for unintended duplicate actions.
29. Check race handling if the action operates on mutable status, queue positions, decisions, settings, uploads, or publishing state.
30. Check that stale/out-of-order responses cannot overwrite a newer state. Use request cancellation, version checks, or existing conventions where needed and approved.
31. Check the response status is translated to the correct UI state, including pending/in-progress, completed, partial failure, failed, cancelled, and conflict states where applicable.
32. Check whether optimistic UI is used. If so, ensure rollback or reconciliation occurs when the backend rejects the change.
33. Check whether the changed state should survive page refresh/reopen; if yes, reload and compare the visible state to the backend-authoritative result.
34. Check whether the state is shared with other pages/components. Trigger the action and inspect every relevant surface for stale data.
35. Check that filters, sorting, selection, pagination, tabs, and the current detail item behave correctly after the operation changes data.
36. Check behavior when the list is empty, the API returns null/partial optional data, a media asset is missing, or a provider is temporarily unavailable.
37. Check timezones, timestamps, duration units, percentages, byte sizes, numeric formatting, and enum labels against backend semantics.
38. Check no credential, OAuth token, API key, signed URL, or private user payload is exposed in visible UI, ordinary logs, test output, or screenshots.
39. Check that test-mode fallbacks or synthetic fixtures can only be activated by the repository-defined trusted test context, never by user-controlled substring or arbitrary request fields.
40. Check the action does not add, restore, expose, or invoke caption/subtitle features. Internal transcription may remain for approved analysis and metadata purposes.
41. Check the action does not route to Ollama or require Ollama environment variables. Preserve approved cloud-hosted models even if their names contain Llama.
42. Check the operation cannot accidentally publish to a source/monitoring channel instead of an explicitly configured destination.
43. Where an action creates a job/task, verify the persisted job ID is retained and Celery dispatch occurs only at the intended transition.
44. Where an action updates a task, verify the backend state transition is valid, durable, and visible on subsequent reads.
45. Where an action creates or deletes a file, verify storage path containment, ownership, retention policy, and cleanup behavior using isolated files only.
46. Where a control selects a layout, verify the selected ID maps to a supported renderer option rather than only changing the visual highlight.
47. Where a control shows a layout thumbnail, verify the reference asset exists in the production build, has the correct accessible text, and truthfully represents output composition.
48. Where the component displays progress, verify it is sourced from authoritative progress/status fields and cannot display completion before the task completes.
49. Where the component refreshes/polls, verify intervals, overlap, cooldown, backoff, and unmount cleanup against the actual code contract.
50. Where external providers are involved, test mocked/sandbox cases first and ensure no accidental external side effect is triggered by an ordinary test.
51. For the private YouTube acceptance upload, do not use this component test to generate another upload. The one real upload is centrally orchestrated and idempotently gated under the master framework.
52. Inspect the relevant unit/component test and add a regression test for each repaired defect where test infrastructure permits.
53. Run the smallest test covering this component first and record the exact command and actual exit result.
54. Run the relevant API/backend integration test where it can be proven safe and isolated.
55. Run the relevant browser/E2E test if available; do not describe static source inspection as a browser test.
56. Collect actual request/response evidence with secrets redacted. Link to the logs or test output that substantiate the result.
57. Compare the user-visible message/status with the actual backend response and persisted state.
58. Conduct Pass A by tracing requirements to implementation and successful tests.
59. Conduct Pass B independently using an alternate path such as persisted state, route registration, event log, task state, rendered output, refresh behavior, or a different test assertion.
60. If Pass A and Pass B disagree, investigate and document the discrepancy; do not average the results or silently pick the favorable one.
61. Classify a failure as UI defect, API contract mismatch, backend behavior defect, persistence defect, concurrency defect, configuration defect, missing test/evidence, or scope ambiguity.
62. Fix only defects within approved Phase 1–7 requirements and only through the governance process required by the freeze rules.
63. Before changing a shared API client, component, schema, backend route, or frozen domain, identify all affected pages and regression tests.
64. Keep the code change minimal and preserve pre-existing Git modifications and untracked files.
65. Never execute blanket Git reset/clean/checkout/restore commands or replace a whole file to make a small repair.
66. After a repair, rerun the failing reproduction, relevant component test, API/backend tests, and affected page regression checks.
67. Independently repeat Pass B after the repair, using evidence distinct from the original fix path where reasonably possible.
68. If the test fails, continue the diagnose/fix/retest loop within scope; if the failure requires unavailable authorization or unsafe operation, mark it blocked and continue unrelated work.
69. Do not stop at the first failed test if the cause is repairable within scope. Do not loop indefinitely if a genuine external or governance blocker exists.
70. Check that test teardown completes and does not silently mask failures; do not change global fixtures unless required and governed.
71. Confirm test DB isolation before any database mutation. Never migrate, drop, reset, or clean the operational clipforge database.
72. Confirm no test publishes an actual video except the one centralized, explicit, private acceptance upload authorized by the user.
73. Confirm no generated test file overwrites existing uploads or outputs and no cleanup task deletes user-owned media.
74. Run TypeScript and lint checks against the changed frontend where possible. Report repository-wide legacy issues separately from new introduced issues.
75. Run the production build after page/component changes and distinguish build output count from the number of user-facing pages.
76. Inspect browser console errors, failed network requests, React warnings, hydration issues, and unhandled promise rejections where browser execution is available.
77. Check responsive layout at narrow and wide viewport sizes, avoiding horizontal overflow, clipped dialogs, invisible controls, and inaccessible hover-only actions.
78. Check error messages are actionable, avoid secrets, and preserve user-entered form data where retry is expected.
79. Check the component handles loading, empty, success, partial-success, validation, unauthorized, not-found, conflict, rate-limit, server-error, and offline states as applicable.
80. Check that stale UI cache does not outlive a mutation. Invalidate/refetch only the relevant query/state according to the existing architecture.
81. Check a successful response has not been mistaken for semantic success when the backend returns a task ID with pending execution.
82. Check task completion is awaited or polled appropriately and the user can identify pending versus completed processing.
83. Check external provider errors propagate to a truthful status rather than being caught and converted into fabricated success.
84. Check any retry operation cannot create duplicate jobs, settings writes, uploads, publications, or cleanup operations.
85. Check the component has no hidden coupling to unapproved Phase 8 watermark branding or unsupported layouts.
86. Cross-reference actual behavior with `PHASE_TRACKER.md`, the relevant approved prompt, and the actual backend route/service. Do not assume draft/archived prompts are mandatory scope.
87. Check related documentation only if it is directly affected by the verified implementation; preserve historical audit evidence.
88. Update the component dossier with actual file paths, symbols, endpoint, backend behavior, test commands, Pass A evidence and Pass B evidence.
89. If a required operation is not present in the current UI, mark it absent and verify whether the approved specification requires it; do not silently invent UI.
90. If a required capability is absent, identify the exact implementation/API/test gap and fix it only when inside approved scope and governance permits.
91. Before any edit, record targeted Git status/diff; after edits, verify unrelated working-tree changes and untracked assets remain untouched.
92. Do not make changes beyond approved Phase 1–7 scope; Phase 8 watermark branding remains deferred unless separately authorized.
93. If this component offers a layout choice, require a real local reference thumbnail for every supported option and verify the output renderer matches it.
94. If this component participates in monitoring/publishing, check destination identity and state synchronization, and obey the central private-upload gate; do not create a second real upload.
95. Never expose secrets, run destructive database operations, publish public/unlisted test videos, or delete user media while verifying this component.
96. Perform Pass A: independently map every acceptance criterion to implementation and test evidence. Record exact paths, symbols, commands and actual results.
97. Perform Pass B independently using alternate evidence; explicitly confirm, contradict or leave uncertain every material Pass A claim.
98. Repair eligible defects and repeat the complete relevant test loop; if governance or safety blocks a fix, record the exact blocker and continue independent work.
99. Final acceptance for `YT-04`: every mandatory control in Channel statistics, refresh and failures must have a real handler/contract, verified backend result, correct UI synchronization, passing relevant test, and independent Pass A/Pass B evidence.
100. Return a concise per-control matrix, exact files changed, tests and results, unresolved issues, and final component verdict. Do not declare PASS when evidence is missing.


---


## Page 7 — Settings (`/settings`)

### Page orchestration prompt

1. Work on Page 7 — Settings (`/settings`) as a page-level integration owner, using the master framework and all child prompts in this section.

2. Discover every actual child component and every interactive control from the current source, accessibility tree, and rendered page where browser inspection is available.

3. Create a route inventory and map each control to the relevant API endpoint, backend route/service, persistence or task path, and acceptance criterion.

4. Execute every child component prompt listed below, then inspect interactions between sibling components, shared state and cross-page navigation.

5. Test loading, empty, success, validation, auth failure, conflict, network failure, server failure and retry states applicable to the page.

6. Use component and integration tests. Run browser/E2E checks where available; label missing browser evidence as NOT VERIFIED.

7. Verify that every layout selection displays a real reference image and that selected layout ID reaches the correct renderer and appears in actual rendered output.

8. For monitoring, trace channel selection → poll → candidate discovery → decision → processing dispatch → persisted job progress → publishing destination → status result.

9. For Publish, verify normal mocked paths first and coordinate with the single central private YouTube upload gate; never create additional live uploads from component tests.

10. After all child components pass, test page-wide interactions, reloading, navigation away/back, shared API cache invalidation, stale response handling and component cleanup.

11. Perform a distinct Page Pass B using alternate evidence and record each finding against Page Pass A.

12. Fix authorized defects and rerun impacted tests until every mandatory page criterion passes or a specific governance/safety/external dependency blocks it.

13. Do not implement the proposed Phase 8 watermark feature. Keep the approved Phase 1–7 scope boundary.

14. Finish with a control-level matrix, endpoint coverage map, actual tests/results, files changed, evidence for both passes and unresolved blockers.


### Independent component prompts — each contains 100 required steps

### SET-01 — Cloud AI provider configuration form

**Primary files to discover:** frontend/app/settings/page.tsx and actual `/api/settings` API  
**Component focus:** OpenRouter/Nvidia/Groq fields actually present, model selector, validation  
**Acceptance focus:** Verify API keys are never exposed after saving, provider/model choices are valid, field changes map to correct backend schema, error handling is accurate, and no active Ollama settings or setup instructions remain.

Copy this complete prompt into the autonomous execution context for this component. Do not execute it in isolation from the master framework.

**100-step component prompt:**
1. Act as the autonomous owner of Cloud AI provider configuration form. Work only on the actual component discovered in the current checkout, not on an assumed or reconstructed UI.
2. Inspect frontend/app/settings/page.tsx and actual `/api/settings` API; follow imports and references to identify the real source files, tests, route and backend dependencies.
3. Component inventory: OpenRouter/Nvidia/Groq fields actually present, model selector, validation. Discover the full list from the current UI and source. The list above is a focus guide, not permission to invent missing controls.
4. Acceptance focus: Verify API keys are never exposed after saving, provider/model choices are valid, field changes map to correct backend schema, error handling is accurate, and no active Ollama settings or setup instructions remain.
5. Create or update dossier ID `SET-01` and link this component to its authoritative Phase/C-series acceptance criterion without redefining phase numbering.
6. Capture current behavior first: record the visible state, control labels, current handler, API call, server response, persisted state and known failure behavior.
7. List every individual button, input, dropdown, link, tab, selector, icon action, modal action and keyboard action in this component; give each a stable child control ID.
8. For every control, specify one positive test, one invalid/error test, one repeated-action/idempotency test where relevant, and one refresh/persistence or cross-page sync test where relevant.
9. Trace every mutation from browser event to API client, backend route, service, persistence/task/external provider and the final returned UI state.
10. Record the precise success assertion and the objective failure condition before changing code; never count a cosmetic animation or toast as proof of backend success.
11. Begin by opening the actual component, its parent, child components, types, API-client methods, and tests; do not trust a previous report without checking the current checkout.
12. List the exact visible controls that belong to this component, including icon-only buttons, links styled as buttons, keyboard shortcuts, toggles, dropdown options, modal actions, and any hidden action revealed by state.
13. For each control, state the requirement and observable success condition before testing it; map each requirement to the approved roadmap item without changing canonical phase numbers.
14. Check whether the control is intentionally non-interactive. If so, it must be semantically non-interactive and cannot imply that an unavailable action will occur.
15. Check accessible name, label/description, role, focusability, keyboard activation, disabled state, focus order, and whether focus returns appropriately after a dialog closes.
16. Trace the real event handler. Reject empty callbacks, console-only callbacks, hard-coded results, no-op links, timer-only simulation, and UI-only state mutation for backend operations.
17. Locate the corresponding API-client method and verify HTTP method, route path, body/query parameters, identifiers, headers/auth, response type, status-code handling, and timeout behavior.
18. Confirm that the route exists in the current backend application and is included under the actual router prefix. Do not infer endpoint existence from a frontend URL string.
19. Inspect backend validation, authorization, ownership checks, service calls, transaction boundaries, queue/task dispatch, and error mapping for the operation.
20. Identify the authoritative persisted record or external response that proves success. Do not use only a toast, button animation, or HTTP 200 as proof of the intended side effect.
21. Check that the frontend consumes the real response and maps returned identifiers/state correctly. Detect hard-coded status strings and mismatched field names.
22. Test the normal successful action using an isolated fixture or safe test record wherever available.
23. Test missing, malformed, stale, or unauthorized identifiers without modifying real user data.
24. Test the expected validation boundary conditions and verify the UI shows a useful message rather than silently dropping the request.
25. Test a server-side failure and confirm no false success indicator appears.
26. Test a network timeout/connection reset and verify the UI does not assume that the backend definitely failed if the outcome may be ambiguous.
27. Test loading indicators and confirm they clear on success, error, cancellation, component unmount, and every supported early return.
28. Test double-click, repeated Enter, quick toggle changes, duplicate network retries, and stale component state for unintended duplicate actions.
29. Check race handling if the action operates on mutable status, queue positions, decisions, settings, uploads, or publishing state.
30. Check that stale/out-of-order responses cannot overwrite a newer state. Use request cancellation, version checks, or existing conventions where needed and approved.
31. Check the response status is translated to the correct UI state, including pending/in-progress, completed, partial failure, failed, cancelled, and conflict states where applicable.
32. Check whether optimistic UI is used. If so, ensure rollback or reconciliation occurs when the backend rejects the change.
33. Check whether the changed state should survive page refresh/reopen; if yes, reload and compare the visible state to the backend-authoritative result.
34. Check whether the state is shared with other pages/components. Trigger the action and inspect every relevant surface for stale data.
35. Check that filters, sorting, selection, pagination, tabs, and the current detail item behave correctly after the operation changes data.
36. Check behavior when the list is empty, the API returns null/partial optional data, a media asset is missing, or a provider is temporarily unavailable.
37. Check timezones, timestamps, duration units, percentages, byte sizes, numeric formatting, and enum labels against backend semantics.
38. Check no credential, OAuth token, API key, signed URL, or private user payload is exposed in visible UI, ordinary logs, test output, or screenshots.
39. Check that test-mode fallbacks or synthetic fixtures can only be activated by the repository-defined trusted test context, never by user-controlled substring or arbitrary request fields.
40. Check the action does not add, restore, expose, or invoke caption/subtitle features. Internal transcription may remain for approved analysis and metadata purposes.
41. Check the action does not route to Ollama or require Ollama environment variables. Preserve approved cloud-hosted models even if their names contain Llama.
42. Check the operation cannot accidentally publish to a source/monitoring channel instead of an explicitly configured destination.
43. Where an action creates a job/task, verify the persisted job ID is retained and Celery dispatch occurs only at the intended transition.
44. Where an action updates a task, verify the backend state transition is valid, durable, and visible on subsequent reads.
45. Where an action creates or deletes a file, verify storage path containment, ownership, retention policy, and cleanup behavior using isolated files only.
46. Where a control selects a layout, verify the selected ID maps to a supported renderer option rather than only changing the visual highlight.
47. Where a control shows a layout thumbnail, verify the reference asset exists in the production build, has the correct accessible text, and truthfully represents output composition.
48. Where the component displays progress, verify it is sourced from authoritative progress/status fields and cannot display completion before the task completes.
49. Where the component refreshes/polls, verify intervals, overlap, cooldown, backoff, and unmount cleanup against the actual code contract.
50. Where external providers are involved, test mocked/sandbox cases first and ensure no accidental external side effect is triggered by an ordinary test.
51. For the private YouTube acceptance upload, do not use this component test to generate another upload. The one real upload is centrally orchestrated and idempotently gated under the master framework.
52. Inspect the relevant unit/component test and add a regression test for each repaired defect where test infrastructure permits.
53. Run the smallest test covering this component first and record the exact command and actual exit result.
54. Run the relevant API/backend integration test where it can be proven safe and isolated.
55. Run the relevant browser/E2E test if available; do not describe static source inspection as a browser test.
56. Collect actual request/response evidence with secrets redacted. Link to the logs or test output that substantiate the result.
57. Compare the user-visible message/status with the actual backend response and persisted state.
58. Conduct Pass A by tracing requirements to implementation and successful tests.
59. Conduct Pass B independently using an alternate path such as persisted state, route registration, event log, task state, rendered output, refresh behavior, or a different test assertion.
60. If Pass A and Pass B disagree, investigate and document the discrepancy; do not average the results or silently pick the favorable one.
61. Classify a failure as UI defect, API contract mismatch, backend behavior defect, persistence defect, concurrency defect, configuration defect, missing test/evidence, or scope ambiguity.
62. Fix only defects within approved Phase 1–7 requirements and only through the governance process required by the freeze rules.
63. Before changing a shared API client, component, schema, backend route, or frozen domain, identify all affected pages and regression tests.
64. Keep the code change minimal and preserve pre-existing Git modifications and untracked files.
65. Never execute blanket Git reset/clean/checkout/restore commands or replace a whole file to make a small repair.
66. After a repair, rerun the failing reproduction, relevant component test, API/backend tests, and affected page regression checks.
67. Independently repeat Pass B after the repair, using evidence distinct from the original fix path where reasonably possible.
68. If the test fails, continue the diagnose/fix/retest loop within scope; if the failure requires unavailable authorization or unsafe operation, mark it blocked and continue unrelated work.
69. Do not stop at the first failed test if the cause is repairable within scope. Do not loop indefinitely if a genuine external or governance blocker exists.
70. Check that test teardown completes and does not silently mask failures; do not change global fixtures unless required and governed.
71. Confirm test DB isolation before any database mutation. Never migrate, drop, reset, or clean the operational clipforge database.
72. Confirm no test publishes an actual video except the one centralized, explicit, private acceptance upload authorized by the user.
73. Confirm no generated test file overwrites existing uploads or outputs and no cleanup task deletes user-owned media.
74. Run TypeScript and lint checks against the changed frontend where possible. Report repository-wide legacy issues separately from new introduced issues.
75. Run the production build after page/component changes and distinguish build output count from the number of user-facing pages.
76. Inspect browser console errors, failed network requests, React warnings, hydration issues, and unhandled promise rejections where browser execution is available.
77. Check responsive layout at narrow and wide viewport sizes, avoiding horizontal overflow, clipped dialogs, invisible controls, and inaccessible hover-only actions.
78. Check error messages are actionable, avoid secrets, and preserve user-entered form data where retry is expected.
79. Check the component handles loading, empty, success, partial-success, validation, unauthorized, not-found, conflict, rate-limit, server-error, and offline states as applicable.
80. Check that stale UI cache does not outlive a mutation. Invalidate/refetch only the relevant query/state according to the existing architecture.
81. Check a successful response has not been mistaken for semantic success when the backend returns a task ID with pending execution.
82. Check task completion is awaited or polled appropriately and the user can identify pending versus completed processing.
83. Check external provider errors propagate to a truthful status rather than being caught and converted into fabricated success.
84. Check any retry operation cannot create duplicate jobs, settings writes, uploads, publications, or cleanup operations.
85. Check the component has no hidden coupling to unapproved Phase 8 watermark branding or unsupported layouts.
86. Cross-reference actual behavior with `PHASE_TRACKER.md`, the relevant approved prompt, and the actual backend route/service. Do not assume draft/archived prompts are mandatory scope.
87. Check related documentation only if it is directly affected by the verified implementation; preserve historical audit evidence.
88. Update the component dossier with actual file paths, symbols, endpoint, backend behavior, test commands, Pass A evidence and Pass B evidence.
89. If a required operation is not present in the current UI, mark it absent and verify whether the approved specification requires it; do not silently invent UI.
90. If a required capability is absent, identify the exact implementation/API/test gap and fix it only when inside approved scope and governance permits.
91. Before any edit, record targeted Git status/diff; after edits, verify unrelated working-tree changes and untracked assets remain untouched.
92. Do not make changes beyond approved Phase 1–7 scope; Phase 8 watermark branding remains deferred unless separately authorized.
93. If this component offers a layout choice, require a real local reference thumbnail for every supported option and verify the output renderer matches it.
94. If this component participates in monitoring/publishing, check destination identity and state synchronization, and obey the central private-upload gate; do not create a second real upload.
95. Never expose secrets, run destructive database operations, publish public/unlisted test videos, or delete user media while verifying this component.
96. Perform Pass A: independently map every acceptance criterion to implementation and test evidence. Record exact paths, symbols, commands and actual results.
97. Perform Pass B independently using alternate evidence; explicitly confirm, contradict or leave uncertain every material Pass A claim.
98. Repair eligible defects and repeat the complete relevant test loop; if governance or safety blocks a fix, record the exact blocker and continue independent work.
99. Final acceptance for `SET-01`: every mandatory control in Cloud AI provider configuration form must have a real handler/contract, verified backend result, correct UI synchronization, passing relevant test, and independent Pass A/Pass B evidence.
100. Return a concise per-control matrix, exact files changed, tests and results, unresolved issues, and final component verdict. Do not declare PASS when evidence is missing.


---

### SET-02 — Settings load/save/reset and masking

**Primary files to discover:** Settings load/persistence API and data/settings.json contract  
**Component focus:** Save, reload, validation, secret masking, reset/default behavior if present  
**Acceptance focus:** Verify atomic persistence, no overwriting settings on stale requests, masked secrets are not accidentally replaced by mask text, invalid updates are rejected, and reopening/refreshing shows persisted values.

Copy this complete prompt into the autonomous execution context for this component. Do not execute it in isolation from the master framework.

**100-step component prompt:**
1. Act as the autonomous owner of Settings load/save/reset and masking. Work only on the actual component discovered in the current checkout, not on an assumed or reconstructed UI.
2. Inspect Settings load/persistence API and data/settings.json contract; follow imports and references to identify the real source files, tests, route and backend dependencies.
3. Component inventory: Save, reload, validation, secret masking, reset/default behavior if present. Discover the full list from the current UI and source. The list above is a focus guide, not permission to invent missing controls.
4. Acceptance focus: Verify atomic persistence, no overwriting settings on stale requests, masked secrets are not accidentally replaced by mask text, invalid updates are rejected, and reopening/refreshing shows persisted values.
5. Create or update dossier ID `SET-02` and link this component to its authoritative Phase/C-series acceptance criterion without redefining phase numbering.
6. Capture current behavior first: record the visible state, control labels, current handler, API call, server response, persisted state and known failure behavior.
7. List every individual button, input, dropdown, link, tab, selector, icon action, modal action and keyboard action in this component; give each a stable child control ID.
8. For every control, specify one positive test, one invalid/error test, one repeated-action/idempotency test where relevant, and one refresh/persistence or cross-page sync test where relevant.
9. Trace every mutation from browser event to API client, backend route, service, persistence/task/external provider and the final returned UI state.
10. Record the precise success assertion and the objective failure condition before changing code; never count a cosmetic animation or toast as proof of backend success.
11. Begin by opening the actual component, its parent, child components, types, API-client methods, and tests; do not trust a previous report without checking the current checkout.
12. List the exact visible controls that belong to this component, including icon-only buttons, links styled as buttons, keyboard shortcuts, toggles, dropdown options, modal actions, and any hidden action revealed by state.
13. For each control, state the requirement and observable success condition before testing it; map each requirement to the approved roadmap item without changing canonical phase numbers.
14. Check whether the control is intentionally non-interactive. If so, it must be semantically non-interactive and cannot imply that an unavailable action will occur.
15. Check accessible name, label/description, role, focusability, keyboard activation, disabled state, focus order, and whether focus returns appropriately after a dialog closes.
16. Trace the real event handler. Reject empty callbacks, console-only callbacks, hard-coded results, no-op links, timer-only simulation, and UI-only state mutation for backend operations.
17. Locate the corresponding API-client method and verify HTTP method, route path, body/query parameters, identifiers, headers/auth, response type, status-code handling, and timeout behavior.
18. Confirm that the route exists in the current backend application and is included under the actual router prefix. Do not infer endpoint existence from a frontend URL string.
19. Inspect backend validation, authorization, ownership checks, service calls, transaction boundaries, queue/task dispatch, and error mapping for the operation.
20. Identify the authoritative persisted record or external response that proves success. Do not use only a toast, button animation, or HTTP 200 as proof of the intended side effect.
21. Check that the frontend consumes the real response and maps returned identifiers/state correctly. Detect hard-coded status strings and mismatched field names.
22. Test the normal successful action using an isolated fixture or safe test record wherever available.
23. Test missing, malformed, stale, or unauthorized identifiers without modifying real user data.
24. Test the expected validation boundary conditions and verify the UI shows a useful message rather than silently dropping the request.
25. Test a server-side failure and confirm no false success indicator appears.
26. Test a network timeout/connection reset and verify the UI does not assume that the backend definitely failed if the outcome may be ambiguous.
27. Test loading indicators and confirm they clear on success, error, cancellation, component unmount, and every supported early return.
28. Test double-click, repeated Enter, quick toggle changes, duplicate network retries, and stale component state for unintended duplicate actions.
29. Check race handling if the action operates on mutable status, queue positions, decisions, settings, uploads, or publishing state.
30. Check that stale/out-of-order responses cannot overwrite a newer state. Use request cancellation, version checks, or existing conventions where needed and approved.
31. Check the response status is translated to the correct UI state, including pending/in-progress, completed, partial failure, failed, cancelled, and conflict states where applicable.
32. Check whether optimistic UI is used. If so, ensure rollback or reconciliation occurs when the backend rejects the change.
33. Check whether the changed state should survive page refresh/reopen; if yes, reload and compare the visible state to the backend-authoritative result.
34. Check whether the state is shared with other pages/components. Trigger the action and inspect every relevant surface for stale data.
35. Check that filters, sorting, selection, pagination, tabs, and the current detail item behave correctly after the operation changes data.
36. Check behavior when the list is empty, the API returns null/partial optional data, a media asset is missing, or a provider is temporarily unavailable.
37. Check timezones, timestamps, duration units, percentages, byte sizes, numeric formatting, and enum labels against backend semantics.
38. Check no credential, OAuth token, API key, signed URL, or private user payload is exposed in visible UI, ordinary logs, test output, or screenshots.
39. Check that test-mode fallbacks or synthetic fixtures can only be activated by the repository-defined trusted test context, never by user-controlled substring or arbitrary request fields.
40. Check the action does not add, restore, expose, or invoke caption/subtitle features. Internal transcription may remain for approved analysis and metadata purposes.
41. Check the action does not route to Ollama or require Ollama environment variables. Preserve approved cloud-hosted models even if their names contain Llama.
42. Check the operation cannot accidentally publish to a source/monitoring channel instead of an explicitly configured destination.
43. Where an action creates a job/task, verify the persisted job ID is retained and Celery dispatch occurs only at the intended transition.
44. Where an action updates a task, verify the backend state transition is valid, durable, and visible on subsequent reads.
45. Where an action creates or deletes a file, verify storage path containment, ownership, retention policy, and cleanup behavior using isolated files only.
46. Where a control selects a layout, verify the selected ID maps to a supported renderer option rather than only changing the visual highlight.
47. Where a control shows a layout thumbnail, verify the reference asset exists in the production build, has the correct accessible text, and truthfully represents output composition.
48. Where the component displays progress, verify it is sourced from authoritative progress/status fields and cannot display completion before the task completes.
49. Where the component refreshes/polls, verify intervals, overlap, cooldown, backoff, and unmount cleanup against the actual code contract.
50. Where external providers are involved, test mocked/sandbox cases first and ensure no accidental external side effect is triggered by an ordinary test.
51. For the private YouTube acceptance upload, do not use this component test to generate another upload. The one real upload is centrally orchestrated and idempotently gated under the master framework.
52. Inspect the relevant unit/component test and add a regression test for each repaired defect where test infrastructure permits.
53. Run the smallest test covering this component first and record the exact command and actual exit result.
54. Run the relevant API/backend integration test where it can be proven safe and isolated.
55. Run the relevant browser/E2E test if available; do not describe static source inspection as a browser test.
56. Collect actual request/response evidence with secrets redacted. Link to the logs or test output that substantiate the result.
57. Compare the user-visible message/status with the actual backend response and persisted state.
58. Conduct Pass A by tracing requirements to implementation and successful tests.
59. Conduct Pass B independently using an alternate path such as persisted state, route registration, event log, task state, rendered output, refresh behavior, or a different test assertion.
60. If Pass A and Pass B disagree, investigate and document the discrepancy; do not average the results or silently pick the favorable one.
61. Classify a failure as UI defect, API contract mismatch, backend behavior defect, persistence defect, concurrency defect, configuration defect, missing test/evidence, or scope ambiguity.
62. Fix only defects within approved Phase 1–7 requirements and only through the governance process required by the freeze rules.
63. Before changing a shared API client, component, schema, backend route, or frozen domain, identify all affected pages and regression tests.
64. Keep the code change minimal and preserve pre-existing Git modifications and untracked files.
65. Never execute blanket Git reset/clean/checkout/restore commands or replace a whole file to make a small repair.
66. After a repair, rerun the failing reproduction, relevant component test, API/backend tests, and affected page regression checks.
67. Independently repeat Pass B after the repair, using evidence distinct from the original fix path where reasonably possible.
68. If the test fails, continue the diagnose/fix/retest loop within scope; if the failure requires unavailable authorization or unsafe operation, mark it blocked and continue unrelated work.
69. Do not stop at the first failed test if the cause is repairable within scope. Do not loop indefinitely if a genuine external or governance blocker exists.
70. Check that test teardown completes and does not silently mask failures; do not change global fixtures unless required and governed.
71. Confirm test DB isolation before any database mutation. Never migrate, drop, reset, or clean the operational clipforge database.
72. Confirm no test publishes an actual video except the one centralized, explicit, private acceptance upload authorized by the user.
73. Confirm no generated test file overwrites existing uploads or outputs and no cleanup task deletes user-owned media.
74. Run TypeScript and lint checks against the changed frontend where possible. Report repository-wide legacy issues separately from new introduced issues.
75. Run the production build after page/component changes and distinguish build output count from the number of user-facing pages.
76. Inspect browser console errors, failed network requests, React warnings, hydration issues, and unhandled promise rejections where browser execution is available.
77. Check responsive layout at narrow and wide viewport sizes, avoiding horizontal overflow, clipped dialogs, invisible controls, and inaccessible hover-only actions.
78. Check error messages are actionable, avoid secrets, and preserve user-entered form data where retry is expected.
79. Check the component handles loading, empty, success, partial-success, validation, unauthorized, not-found, conflict, rate-limit, server-error, and offline states as applicable.
80. Check that stale UI cache does not outlive a mutation. Invalidate/refetch only the relevant query/state according to the existing architecture.
81. Check a successful response has not been mistaken for semantic success when the backend returns a task ID with pending execution.
82. Check task completion is awaited or polled appropriately and the user can identify pending versus completed processing.
83. Check external provider errors propagate to a truthful status rather than being caught and converted into fabricated success.
84. Check any retry operation cannot create duplicate jobs, settings writes, uploads, publications, or cleanup operations.
85. Check the component has no hidden coupling to unapproved Phase 8 watermark branding or unsupported layouts.
86. Cross-reference actual behavior with `PHASE_TRACKER.md`, the relevant approved prompt, and the actual backend route/service. Do not assume draft/archived prompts are mandatory scope.
87. Check related documentation only if it is directly affected by the verified implementation; preserve historical audit evidence.
88. Update the component dossier with actual file paths, symbols, endpoint, backend behavior, test commands, Pass A evidence and Pass B evidence.
89. If a required operation is not present in the current UI, mark it absent and verify whether the approved specification requires it; do not silently invent UI.
90. If a required capability is absent, identify the exact implementation/API/test gap and fix it only when inside approved scope and governance permits.
91. Before any edit, record targeted Git status/diff; after edits, verify unrelated working-tree changes and untracked assets remain untouched.
92. Do not make changes beyond approved Phase 1–7 scope; Phase 8 watermark branding remains deferred unless separately authorized.
93. If this component offers a layout choice, require a real local reference thumbnail for every supported option and verify the output renderer matches it.
94. If this component participates in monitoring/publishing, check destination identity and state synchronization, and obey the central private-upload gate; do not create a second real upload.
95. Never expose secrets, run destructive database operations, publish public/unlisted test videos, or delete user media while verifying this component.
96. Perform Pass A: independently map every acceptance criterion to implementation and test evidence. Record exact paths, symbols, commands and actual results.
97. Perform Pass B independently using alternate evidence; explicitly confirm, contradict or leave uncertain every material Pass A claim.
98. Repair eligible defects and repeat the complete relevant test loop; if governance or safety blocks a fix, record the exact blocker and continue independent work.
99. Final acceptance for `SET-02`: every mandatory control in Settings load/save/reset and masking must have a real handler/contract, verified backend result, correct UI synchronization, passing relevant test, and independent Pass A/Pass B evidence.
100. Return a concise per-control matrix, exact files changed, tests and results, unresolved issues, and final component verdict. Do not declare PASS when evidence is missing.


---

### SET-03 — Whisper/transcription, limits and other settings

**Primary files to discover:** Actual transcription/settings/quota controls present in Settings  
**Component focus:** Whisper choices, limits, storage/retention/provider fields that are present  
**Acceptance focus:** Verify controls correspond to supported backend fields, limits validate boundary values, local Whisper fallback remains intact, Groq remains transcription-only if that is actual architecture, and internal transcription is retained.

Copy this complete prompt into the autonomous execution context for this component. Do not execute it in isolation from the master framework.

**100-step component prompt:**
1. Act as the autonomous owner of Whisper/transcription, limits and other settings. Work only on the actual component discovered in the current checkout, not on an assumed or reconstructed UI.
2. Inspect Actual transcription/settings/quota controls present in Settings; follow imports and references to identify the real source files, tests, route and backend dependencies.
3. Component inventory: Whisper choices, limits, storage/retention/provider fields that are present. Discover the full list from the current UI and source. The list above is a focus guide, not permission to invent missing controls.
4. Acceptance focus: Verify controls correspond to supported backend fields, limits validate boundary values, local Whisper fallback remains intact, Groq remains transcription-only if that is actual architecture, and internal transcription is retained.
5. Create or update dossier ID `SET-03` and link this component to its authoritative Phase/C-series acceptance criterion without redefining phase numbering.
6. Capture current behavior first: record the visible state, control labels, current handler, API call, server response, persisted state and known failure behavior.
7. List every individual button, input, dropdown, link, tab, selector, icon action, modal action and keyboard action in this component; give each a stable child control ID.
8. For every control, specify one positive test, one invalid/error test, one repeated-action/idempotency test where relevant, and one refresh/persistence or cross-page sync test where relevant.
9. Trace every mutation from browser event to API client, backend route, service, persistence/task/external provider and the final returned UI state.
10. Record the precise success assertion and the objective failure condition before changing code; never count a cosmetic animation or toast as proof of backend success.
11. Begin by opening the actual component, its parent, child components, types, API-client methods, and tests; do not trust a previous report without checking the current checkout.
12. List the exact visible controls that belong to this component, including icon-only buttons, links styled as buttons, keyboard shortcuts, toggles, dropdown options, modal actions, and any hidden action revealed by state.
13. For each control, state the requirement and observable success condition before testing it; map each requirement to the approved roadmap item without changing canonical phase numbers.
14. Check whether the control is intentionally non-interactive. If so, it must be semantically non-interactive and cannot imply that an unavailable action will occur.
15. Check accessible name, label/description, role, focusability, keyboard activation, disabled state, focus order, and whether focus returns appropriately after a dialog closes.
16. Trace the real event handler. Reject empty callbacks, console-only callbacks, hard-coded results, no-op links, timer-only simulation, and UI-only state mutation for backend operations.
17. Locate the corresponding API-client method and verify HTTP method, route path, body/query parameters, identifiers, headers/auth, response type, status-code handling, and timeout behavior.
18. Confirm that the route exists in the current backend application and is included under the actual router prefix. Do not infer endpoint existence from a frontend URL string.
19. Inspect backend validation, authorization, ownership checks, service calls, transaction boundaries, queue/task dispatch, and error mapping for the operation.
20. Identify the authoritative persisted record or external response that proves success. Do not use only a toast, button animation, or HTTP 200 as proof of the intended side effect.
21. Check that the frontend consumes the real response and maps returned identifiers/state correctly. Detect hard-coded status strings and mismatched field names.
22. Test the normal successful action using an isolated fixture or safe test record wherever available.
23. Test missing, malformed, stale, or unauthorized identifiers without modifying real user data.
24. Test the expected validation boundary conditions and verify the UI shows a useful message rather than silently dropping the request.
25. Test a server-side failure and confirm no false success indicator appears.
26. Test a network timeout/connection reset and verify the UI does not assume that the backend definitely failed if the outcome may be ambiguous.
27. Test loading indicators and confirm they clear on success, error, cancellation, component unmount, and every supported early return.
28. Test double-click, repeated Enter, quick toggle changes, duplicate network retries, and stale component state for unintended duplicate actions.
29. Check race handling if the action operates on mutable status, queue positions, decisions, settings, uploads, or publishing state.
30. Check that stale/out-of-order responses cannot overwrite a newer state. Use request cancellation, version checks, or existing conventions where needed and approved.
31. Check the response status is translated to the correct UI state, including pending/in-progress, completed, partial failure, failed, cancelled, and conflict states where applicable.
32. Check whether optimistic UI is used. If so, ensure rollback or reconciliation occurs when the backend rejects the change.
33. Check whether the changed state should survive page refresh/reopen; if yes, reload and compare the visible state to the backend-authoritative result.
34. Check whether the state is shared with other pages/components. Trigger the action and inspect every relevant surface for stale data.
35. Check that filters, sorting, selection, pagination, tabs, and the current detail item behave correctly after the operation changes data.
36. Check behavior when the list is empty, the API returns null/partial optional data, a media asset is missing, or a provider is temporarily unavailable.
37. Check timezones, timestamps, duration units, percentages, byte sizes, numeric formatting, and enum labels against backend semantics.
38. Check no credential, OAuth token, API key, signed URL, or private user payload is exposed in visible UI, ordinary logs, test output, or screenshots.
39. Check that test-mode fallbacks or synthetic fixtures can only be activated by the repository-defined trusted test context, never by user-controlled substring or arbitrary request fields.
40. Check the action does not add, restore, expose, or invoke caption/subtitle features. Internal transcription may remain for approved analysis and metadata purposes.
41. Check the action does not route to Ollama or require Ollama environment variables. Preserve approved cloud-hosted models even if their names contain Llama.
42. Check the operation cannot accidentally publish to a source/monitoring channel instead of an explicitly configured destination.
43. Where an action creates a job/task, verify the persisted job ID is retained and Celery dispatch occurs only at the intended transition.
44. Where an action updates a task, verify the backend state transition is valid, durable, and visible on subsequent reads.
45. Where an action creates or deletes a file, verify storage path containment, ownership, retention policy, and cleanup behavior using isolated files only.
46. Where a control selects a layout, verify the selected ID maps to a supported renderer option rather than only changing the visual highlight.
47. Where a control shows a layout thumbnail, verify the reference asset exists in the production build, has the correct accessible text, and truthfully represents output composition.
48. Where the component displays progress, verify it is sourced from authoritative progress/status fields and cannot display completion before the task completes.
49. Where the component refreshes/polls, verify intervals, overlap, cooldown, backoff, and unmount cleanup against the actual code contract.
50. Where external providers are involved, test mocked/sandbox cases first and ensure no accidental external side effect is triggered by an ordinary test.
51. For the private YouTube acceptance upload, do not use this component test to generate another upload. The one real upload is centrally orchestrated and idempotently gated under the master framework.
52. Inspect the relevant unit/component test and add a regression test for each repaired defect where test infrastructure permits.
53. Run the smallest test covering this component first and record the exact command and actual exit result.
54. Run the relevant API/backend integration test where it can be proven safe and isolated.
55. Run the relevant browser/E2E test if available; do not describe static source inspection as a browser test.
56. Collect actual request/response evidence with secrets redacted. Link to the logs or test output that substantiate the result.
57. Compare the user-visible message/status with the actual backend response and persisted state.
58. Conduct Pass A by tracing requirements to implementation and successful tests.
59. Conduct Pass B independently using an alternate path such as persisted state, route registration, event log, task state, rendered output, refresh behavior, or a different test assertion.
60. If Pass A and Pass B disagree, investigate and document the discrepancy; do not average the results or silently pick the favorable one.
61. Classify a failure as UI defect, API contract mismatch, backend behavior defect, persistence defect, concurrency defect, configuration defect, missing test/evidence, or scope ambiguity.
62. Fix only defects within approved Phase 1–7 requirements and only through the governance process required by the freeze rules.
63. Before changing a shared API client, component, schema, backend route, or frozen domain, identify all affected pages and regression tests.
64. Keep the code change minimal and preserve pre-existing Git modifications and untracked files.
65. Never execute blanket Git reset/clean/checkout/restore commands or replace a whole file to make a small repair.
66. After a repair, rerun the failing reproduction, relevant component test, API/backend tests, and affected page regression checks.
67. Independently repeat Pass B after the repair, using evidence distinct from the original fix path where reasonably possible.
68. If the test fails, continue the diagnose/fix/retest loop within scope; if the failure requires unavailable authorization or unsafe operation, mark it blocked and continue unrelated work.
69. Do not stop at the first failed test if the cause is repairable within scope. Do not loop indefinitely if a genuine external or governance blocker exists.
70. Check that test teardown completes and does not silently mask failures; do not change global fixtures unless required and governed.
71. Confirm test DB isolation before any database mutation. Never migrate, drop, reset, or clean the operational clipforge database.
72. Confirm no test publishes an actual video except the one centralized, explicit, private acceptance upload authorized by the user.
73. Confirm no generated test file overwrites existing uploads or outputs and no cleanup task deletes user-owned media.
74. Run TypeScript and lint checks against the changed frontend where possible. Report repository-wide legacy issues separately from new introduced issues.
75. Run the production build after page/component changes and distinguish build output count from the number of user-facing pages.
76. Inspect browser console errors, failed network requests, React warnings, hydration issues, and unhandled promise rejections where browser execution is available.
77. Check responsive layout at narrow and wide viewport sizes, avoiding horizontal overflow, clipped dialogs, invisible controls, and inaccessible hover-only actions.
78. Check error messages are actionable, avoid secrets, and preserve user-entered form data where retry is expected.
79. Check the component handles loading, empty, success, partial-success, validation, unauthorized, not-found, conflict, rate-limit, server-error, and offline states as applicable.
80. Check that stale UI cache does not outlive a mutation. Invalidate/refetch only the relevant query/state according to the existing architecture.
81. Check a successful response has not been mistaken for semantic success when the backend returns a task ID with pending execution.
82. Check task completion is awaited or polled appropriately and the user can identify pending versus completed processing.
83. Check external provider errors propagate to a truthful status rather than being caught and converted into fabricated success.
84. Check any retry operation cannot create duplicate jobs, settings writes, uploads, publications, or cleanup operations.
85. Check the component has no hidden coupling to unapproved Phase 8 watermark branding or unsupported layouts.
86. Cross-reference actual behavior with `PHASE_TRACKER.md`, the relevant approved prompt, and the actual backend route/service. Do not assume draft/archived prompts are mandatory scope.
87. Check related documentation only if it is directly affected by the verified implementation; preserve historical audit evidence.
88. Update the component dossier with actual file paths, symbols, endpoint, backend behavior, test commands, Pass A evidence and Pass B evidence.
89. If a required operation is not present in the current UI, mark it absent and verify whether the approved specification requires it; do not silently invent UI.
90. If a required capability is absent, identify the exact implementation/API/test gap and fix it only when inside approved scope and governance permits.
91. Before any edit, record targeted Git status/diff; after edits, verify unrelated working-tree changes and untracked assets remain untouched.
92. Do not make changes beyond approved Phase 1–7 scope; Phase 8 watermark branding remains deferred unless separately authorized.
93. If this component offers a layout choice, require a real local reference thumbnail for every supported option and verify the output renderer matches it.
94. If this component participates in monitoring/publishing, check destination identity and state synchronization, and obey the central private-upload gate; do not create a second real upload.
95. Never expose secrets, run destructive database operations, publish public/unlisted test videos, or delete user media while verifying this component.
96. Perform Pass A: independently map every acceptance criterion to implementation and test evidence. Record exact paths, symbols, commands and actual results.
97. Perform Pass B independently using alternate evidence; explicitly confirm, contradict or leave uncertain every material Pass A claim.
98. Repair eligible defects and repeat the complete relevant test loop; if governance or safety blocks a fix, record the exact blocker and continue independent work.
99. Final acceptance for `SET-03`: every mandatory control in Whisper/transcription, limits and other settings must have a real handler/contract, verified backend result, correct UI synchronization, passing relevant test, and independent Pass A/Pass B evidence.
100. Return a concise per-control matrix, exact files changed, tests and results, unresolved issues, and final component verdict. Do not declare PASS when evidence is missing.


---

### SET-04 — Settings feedback, alerts and failure recovery

**Primary files to discover:** All settings form notifications and error boundaries  
**Component focus:** Success/error banners, validation messages, disabled states, retry actions  
**Acceptance focus:** Verify messages correspond to actual API outcomes, errors are accessible, save buttons prevent duplicate writes, failed saves preserve user input, and state is consistent after retry or refresh.

Copy this complete prompt into the autonomous execution context for this component. Do not execute it in isolation from the master framework.

**100-step component prompt:**
1. Act as the autonomous owner of Settings feedback, alerts and failure recovery. Work only on the actual component discovered in the current checkout, not on an assumed or reconstructed UI.
2. Inspect All settings form notifications and error boundaries; follow imports and references to identify the real source files, tests, route and backend dependencies.
3. Component inventory: Success/error banners, validation messages, disabled states, retry actions. Discover the full list from the current UI and source. The list above is a focus guide, not permission to invent missing controls.
4. Acceptance focus: Verify messages correspond to actual API outcomes, errors are accessible, save buttons prevent duplicate writes, failed saves preserve user input, and state is consistent after retry or refresh.
5. Create or update dossier ID `SET-04` and link this component to its authoritative Phase/C-series acceptance criterion without redefining phase numbering.
6. Capture current behavior first: record the visible state, control labels, current handler, API call, server response, persisted state and known failure behavior.
7. List every individual button, input, dropdown, link, tab, selector, icon action, modal action and keyboard action in this component; give each a stable child control ID.
8. For every control, specify one positive test, one invalid/error test, one repeated-action/idempotency test where relevant, and one refresh/persistence or cross-page sync test where relevant.
9. Trace every mutation from browser event to API client, backend route, service, persistence/task/external provider and the final returned UI state.
10. Record the precise success assertion and the objective failure condition before changing code; never count a cosmetic animation or toast as proof of backend success.
11. Begin by opening the actual component, its parent, child components, types, API-client methods, and tests; do not trust a previous report without checking the current checkout.
12. List the exact visible controls that belong to this component, including icon-only buttons, links styled as buttons, keyboard shortcuts, toggles, dropdown options, modal actions, and any hidden action revealed by state.
13. For each control, state the requirement and observable success condition before testing it; map each requirement to the approved roadmap item without changing canonical phase numbers.
14. Check whether the control is intentionally non-interactive. If so, it must be semantically non-interactive and cannot imply that an unavailable action will occur.
15. Check accessible name, label/description, role, focusability, keyboard activation, disabled state, focus order, and whether focus returns appropriately after a dialog closes.
16. Trace the real event handler. Reject empty callbacks, console-only callbacks, hard-coded results, no-op links, timer-only simulation, and UI-only state mutation for backend operations.
17. Locate the corresponding API-client method and verify HTTP method, route path, body/query parameters, identifiers, headers/auth, response type, status-code handling, and timeout behavior.
18. Confirm that the route exists in the current backend application and is included under the actual router prefix. Do not infer endpoint existence from a frontend URL string.
19. Inspect backend validation, authorization, ownership checks, service calls, transaction boundaries, queue/task dispatch, and error mapping for the operation.
20. Identify the authoritative persisted record or external response that proves success. Do not use only a toast, button animation, or HTTP 200 as proof of the intended side effect.
21. Check that the frontend consumes the real response and maps returned identifiers/state correctly. Detect hard-coded status strings and mismatched field names.
22. Test the normal successful action using an isolated fixture or safe test record wherever available.
23. Test missing, malformed, stale, or unauthorized identifiers without modifying real user data.
24. Test the expected validation boundary conditions and verify the UI shows a useful message rather than silently dropping the request.
25. Test a server-side failure and confirm no false success indicator appears.
26. Test a network timeout/connection reset and verify the UI does not assume that the backend definitely failed if the outcome may be ambiguous.
27. Test loading indicators and confirm they clear on success, error, cancellation, component unmount, and every supported early return.
28. Test double-click, repeated Enter, quick toggle changes, duplicate network retries, and stale component state for unintended duplicate actions.
29. Check race handling if the action operates on mutable status, queue positions, decisions, settings, uploads, or publishing state.
30. Check that stale/out-of-order responses cannot overwrite a newer state. Use request cancellation, version checks, or existing conventions where needed and approved.
31. Check the response status is translated to the correct UI state, including pending/in-progress, completed, partial failure, failed, cancelled, and conflict states where applicable.
32. Check whether optimistic UI is used. If so, ensure rollback or reconciliation occurs when the backend rejects the change.
33. Check whether the changed state should survive page refresh/reopen; if yes, reload and compare the visible state to the backend-authoritative result.
34. Check whether the state is shared with other pages/components. Trigger the action and inspect every relevant surface for stale data.
35. Check that filters, sorting, selection, pagination, tabs, and the current detail item behave correctly after the operation changes data.
36. Check behavior when the list is empty, the API returns null/partial optional data, a media asset is missing, or a provider is temporarily unavailable.
37. Check timezones, timestamps, duration units, percentages, byte sizes, numeric formatting, and enum labels against backend semantics.
38. Check no credential, OAuth token, API key, signed URL, or private user payload is exposed in visible UI, ordinary logs, test output, or screenshots.
39. Check that test-mode fallbacks or synthetic fixtures can only be activated by the repository-defined trusted test context, never by user-controlled substring or arbitrary request fields.
40. Check the action does not add, restore, expose, or invoke caption/subtitle features. Internal transcription may remain for approved analysis and metadata purposes.
41. Check the action does not route to Ollama or require Ollama environment variables. Preserve approved cloud-hosted models even if their names contain Llama.
42. Check the operation cannot accidentally publish to a source/monitoring channel instead of an explicitly configured destination.
43. Where an action creates a job/task, verify the persisted job ID is retained and Celery dispatch occurs only at the intended transition.
44. Where an action updates a task, verify the backend state transition is valid, durable, and visible on subsequent reads.
45. Where an action creates or deletes a file, verify storage path containment, ownership, retention policy, and cleanup behavior using isolated files only.
46. Where a control selects a layout, verify the selected ID maps to a supported renderer option rather than only changing the visual highlight.
47. Where a control shows a layout thumbnail, verify the reference asset exists in the production build, has the correct accessible text, and truthfully represents output composition.
48. Where the component displays progress, verify it is sourced from authoritative progress/status fields and cannot display completion before the task completes.
49. Where the component refreshes/polls, verify intervals, overlap, cooldown, backoff, and unmount cleanup against the actual code contract.
50. Where external providers are involved, test mocked/sandbox cases first and ensure no accidental external side effect is triggered by an ordinary test.
51. For the private YouTube acceptance upload, do not use this component test to generate another upload. The one real upload is centrally orchestrated and idempotently gated under the master framework.
52. Inspect the relevant unit/component test and add a regression test for each repaired defect where test infrastructure permits.
53. Run the smallest test covering this component first and record the exact command and actual exit result.
54. Run the relevant API/backend integration test where it can be proven safe and isolated.
55. Run the relevant browser/E2E test if available; do not describe static source inspection as a browser test.
56. Collect actual request/response evidence with secrets redacted. Link to the logs or test output that substantiate the result.
57. Compare the user-visible message/status with the actual backend response and persisted state.
58. Conduct Pass A by tracing requirements to implementation and successful tests.
59. Conduct Pass B independently using an alternate path such as persisted state, route registration, event log, task state, rendered output, refresh behavior, or a different test assertion.
60. If Pass A and Pass B disagree, investigate and document the discrepancy; do not average the results or silently pick the favorable one.
61. Classify a failure as UI defect, API contract mismatch, backend behavior defect, persistence defect, concurrency defect, configuration defect, missing test/evidence, or scope ambiguity.
62. Fix only defects within approved Phase 1–7 requirements and only through the governance process required by the freeze rules.
63. Before changing a shared API client, component, schema, backend route, or frozen domain, identify all affected pages and regression tests.
64. Keep the code change minimal and preserve pre-existing Git modifications and untracked files.
65. Never execute blanket Git reset/clean/checkout/restore commands or replace a whole file to make a small repair.
66. After a repair, rerun the failing reproduction, relevant component test, API/backend tests, and affected page regression checks.
67. Independently repeat Pass B after the repair, using evidence distinct from the original fix path where reasonably possible.
68. If the test fails, continue the diagnose/fix/retest loop within scope; if the failure requires unavailable authorization or unsafe operation, mark it blocked and continue unrelated work.
69. Do not stop at the first failed test if the cause is repairable within scope. Do not loop indefinitely if a genuine external or governance blocker exists.
70. Check that test teardown completes and does not silently mask failures; do not change global fixtures unless required and governed.
71. Confirm test DB isolation before any database mutation. Never migrate, drop, reset, or clean the operational clipforge database.
72. Confirm no test publishes an actual video except the one centralized, explicit, private acceptance upload authorized by the user.
73. Confirm no generated test file overwrites existing uploads or outputs and no cleanup task deletes user-owned media.
74. Run TypeScript and lint checks against the changed frontend where possible. Report repository-wide legacy issues separately from new introduced issues.
75. Run the production build after page/component changes and distinguish build output count from the number of user-facing pages.
76. Inspect browser console errors, failed network requests, React warnings, hydration issues, and unhandled promise rejections where browser execution is available.
77. Check responsive layout at narrow and wide viewport sizes, avoiding horizontal overflow, clipped dialogs, invisible controls, and inaccessible hover-only actions.
78. Check error messages are actionable, avoid secrets, and preserve user-entered form data where retry is expected.
79. Check the component handles loading, empty, success, partial-success, validation, unauthorized, not-found, conflict, rate-limit, server-error, and offline states as applicable.
80. Check that stale UI cache does not outlive a mutation. Invalidate/refetch only the relevant query/state according to the existing architecture.
81. Check a successful response has not been mistaken for semantic success when the backend returns a task ID with pending execution.
82. Check task completion is awaited or polled appropriately and the user can identify pending versus completed processing.
83. Check external provider errors propagate to a truthful status rather than being caught and converted into fabricated success.
84. Check any retry operation cannot create duplicate jobs, settings writes, uploads, publications, or cleanup operations.
85. Check the component has no hidden coupling to unapproved Phase 8 watermark branding or unsupported layouts.
86. Cross-reference actual behavior with `PHASE_TRACKER.md`, the relevant approved prompt, and the actual backend route/service. Do not assume draft/archived prompts are mandatory scope.
87. Check related documentation only if it is directly affected by the verified implementation; preserve historical audit evidence.
88. Update the component dossier with actual file paths, symbols, endpoint, backend behavior, test commands, Pass A evidence and Pass B evidence.
89. If a required operation is not present in the current UI, mark it absent and verify whether the approved specification requires it; do not silently invent UI.
90. If a required capability is absent, identify the exact implementation/API/test gap and fix it only when inside approved scope and governance permits.
91. Before any edit, record targeted Git status/diff; after edits, verify unrelated working-tree changes and untracked assets remain untouched.
92. Do not make changes beyond approved Phase 1–7 scope; Phase 8 watermark branding remains deferred unless separately authorized.
93. If this component offers a layout choice, require a real local reference thumbnail for every supported option and verify the output renderer matches it.
94. If this component participates in monitoring/publishing, check destination identity and state synchronization, and obey the central private-upload gate; do not create a second real upload.
95. Never expose secrets, run destructive database operations, publish public/unlisted test videos, or delete user media while verifying this component.
96. Perform Pass A: independently map every acceptance criterion to implementation and test evidence. Record exact paths, symbols, commands and actual results.
97. Perform Pass B independently using alternate evidence; explicitly confirm, contradict or leave uncertain every material Pass A claim.
98. Repair eligible defects and repeat the complete relevant test loop; if governance or safety blocks a fix, record the exact blocker and continue independent work.
99. Final acceptance for `SET-04`: every mandatory control in Settings feedback, alerts and failure recovery must have a real handler/contract, verified backend result, correct UI synchronization, passing relevant test, and independent Pass A/Pass B evidence.
100. Return a concise per-control matrix, exact files changed, tests and results, unresolved issues, and final component verdict. Do not declare PASS when evidence is missing.


---


## Page 8 — Upload Studio (`/studio`)

### Page orchestration prompt

1. Work on Page 8 — Upload Studio (`/studio`) as a page-level integration owner, using the master framework and all child prompts in this section.

2. Discover every actual child component and every interactive control from the current source, accessibility tree, and rendered page where browser inspection is available.

3. Create a route inventory and map each control to the relevant API endpoint, backend route/service, persistence or task path, and acceptance criterion.

4. Execute every child component prompt listed below, then inspect interactions between sibling components, shared state and cross-page navigation.

5. Test loading, empty, success, validation, auth failure, conflict, network failure, server failure and retry states applicable to the page.

6. Use component and integration tests. Run browser/E2E checks where available; label missing browser evidence as NOT VERIFIED.

7. Verify that every layout selection displays a real reference image and that selected layout ID reaches the correct renderer and appears in actual rendered output.

8. For monitoring, trace channel selection → poll → candidate discovery → decision → processing dispatch → persisted job progress → publishing destination → status result.

9. For Publish, verify normal mocked paths first and coordinate with the single central private YouTube upload gate; never create additional live uploads from component tests.

10. After all child components pass, test page-wide interactions, reloading, navigation away/back, shared API cache invalidation, stale response handling and component cleanup.

11. Perform a distinct Page Pass B using alternate evidence and record each finding against Page Pass A.

12. Fix authorized defects and rerun impacted tests until every mandatory page criterion passes or a specific governance/safety/external dependency blocks it.

13. Do not implement the proposed Phase 8 watermark feature. Keep the approved Phase 1–7 scope boundary.

14. Finish with a control-level matrix, endpoint coverage map, actual tests/results, files changed, evidence for both passes and unresolved blockers.


### Independent component prompts — each contains 100 required steps

### STU-01 — Upload Studio file picker and session initialization

**Primary files to discover:** frontend/app/studio/page.tsx and actual Upload Studio session endpoints  
**Component focus:** File selection, file validation, create session/batch, metadata input  
**Acceptance focus:** Verify file constraints, upload session identity, manifest fields, duplicate file handling, initialization errors, and no false upload state before the backend accepts the session.

Copy this complete prompt into the autonomous execution context for this component. Do not execute it in isolation from the master framework.

**100-step component prompt:**
1. Act as the autonomous owner of Upload Studio file picker and session initialization. Work only on the actual component discovered in the current checkout, not on an assumed or reconstructed UI.
2. Inspect frontend/app/studio/page.tsx and actual Upload Studio session endpoints; follow imports and references to identify the real source files, tests, route and backend dependencies.
3. Component inventory: File selection, file validation, create session/batch, metadata input. Discover the full list from the current UI and source. The list above is a focus guide, not permission to invent missing controls.
4. Acceptance focus: Verify file constraints, upload session identity, manifest fields, duplicate file handling, initialization errors, and no false upload state before the backend accepts the session.
5. Create or update dossier ID `STU-01` and link this component to its authoritative Phase/C-series acceptance criterion without redefining phase numbering.
6. Capture current behavior first: record the visible state, control labels, current handler, API call, server response, persisted state and known failure behavior.
7. List every individual button, input, dropdown, link, tab, selector, icon action, modal action and keyboard action in this component; give each a stable child control ID.
8. For every control, specify one positive test, one invalid/error test, one repeated-action/idempotency test where relevant, and one refresh/persistence or cross-page sync test where relevant.
9. Trace every mutation from browser event to API client, backend route, service, persistence/task/external provider and the final returned UI state.
10. Record the precise success assertion and the objective failure condition before changing code; never count a cosmetic animation or toast as proof of backend success.
11. Begin by opening the actual component, its parent, child components, types, API-client methods, and tests; do not trust a previous report without checking the current checkout.
12. List the exact visible controls that belong to this component, including icon-only buttons, links styled as buttons, keyboard shortcuts, toggles, dropdown options, modal actions, and any hidden action revealed by state.
13. For each control, state the requirement and observable success condition before testing it; map each requirement to the approved roadmap item without changing canonical phase numbers.
14. Check whether the control is intentionally non-interactive. If so, it must be semantically non-interactive and cannot imply that an unavailable action will occur.
15. Check accessible name, label/description, role, focusability, keyboard activation, disabled state, focus order, and whether focus returns appropriately after a dialog closes.
16. Trace the real event handler. Reject empty callbacks, console-only callbacks, hard-coded results, no-op links, timer-only simulation, and UI-only state mutation for backend operations.
17. Locate the corresponding API-client method and verify HTTP method, route path, body/query parameters, identifiers, headers/auth, response type, status-code handling, and timeout behavior.
18. Confirm that the route exists in the current backend application and is included under the actual router prefix. Do not infer endpoint existence from a frontend URL string.
19. Inspect backend validation, authorization, ownership checks, service calls, transaction boundaries, queue/task dispatch, and error mapping for the operation.
20. Identify the authoritative persisted record or external response that proves success. Do not use only a toast, button animation, or HTTP 200 as proof of the intended side effect.
21. Check that the frontend consumes the real response and maps returned identifiers/state correctly. Detect hard-coded status strings and mismatched field names.
22. Test the normal successful action using an isolated fixture or safe test record wherever available.
23. Test missing, malformed, stale, or unauthorized identifiers without modifying real user data.
24. Test the expected validation boundary conditions and verify the UI shows a useful message rather than silently dropping the request.
25. Test a server-side failure and confirm no false success indicator appears.
26. Test a network timeout/connection reset and verify the UI does not assume that the backend definitely failed if the outcome may be ambiguous.
27. Test loading indicators and confirm they clear on success, error, cancellation, component unmount, and every supported early return.
28. Test double-click, repeated Enter, quick toggle changes, duplicate network retries, and stale component state for unintended duplicate actions.
29. Check race handling if the action operates on mutable status, queue positions, decisions, settings, uploads, or publishing state.
30. Check that stale/out-of-order responses cannot overwrite a newer state. Use request cancellation, version checks, or existing conventions where needed and approved.
31. Check the response status is translated to the correct UI state, including pending/in-progress, completed, partial failure, failed, cancelled, and conflict states where applicable.
32. Check whether optimistic UI is used. If so, ensure rollback or reconciliation occurs when the backend rejects the change.
33. Check whether the changed state should survive page refresh/reopen; if yes, reload and compare the visible state to the backend-authoritative result.
34. Check whether the state is shared with other pages/components. Trigger the action and inspect every relevant surface for stale data.
35. Check that filters, sorting, selection, pagination, tabs, and the current detail item behave correctly after the operation changes data.
36. Check behavior when the list is empty, the API returns null/partial optional data, a media asset is missing, or a provider is temporarily unavailable.
37. Check timezones, timestamps, duration units, percentages, byte sizes, numeric formatting, and enum labels against backend semantics.
38. Check no credential, OAuth token, API key, signed URL, or private user payload is exposed in visible UI, ordinary logs, test output, or screenshots.
39. Check that test-mode fallbacks or synthetic fixtures can only be activated by the repository-defined trusted test context, never by user-controlled substring or arbitrary request fields.
40. Check the action does not add, restore, expose, or invoke caption/subtitle features. Internal transcription may remain for approved analysis and metadata purposes.
41. Check the action does not route to Ollama or require Ollama environment variables. Preserve approved cloud-hosted models even if their names contain Llama.
42. Check the operation cannot accidentally publish to a source/monitoring channel instead of an explicitly configured destination.
43. Where an action creates a job/task, verify the persisted job ID is retained and Celery dispatch occurs only at the intended transition.
44. Where an action updates a task, verify the backend state transition is valid, durable, and visible on subsequent reads.
45. Where an action creates or deletes a file, verify storage path containment, ownership, retention policy, and cleanup behavior using isolated files only.
46. Where a control selects a layout, verify the selected ID maps to a supported renderer option rather than only changing the visual highlight.
47. Where a control shows a layout thumbnail, verify the reference asset exists in the production build, has the correct accessible text, and truthfully represents output composition.
48. Where the component displays progress, verify it is sourced from authoritative progress/status fields and cannot display completion before the task completes.
49. Where the component refreshes/polls, verify intervals, overlap, cooldown, backoff, and unmount cleanup against the actual code contract.
50. Where external providers are involved, test mocked/sandbox cases first and ensure no accidental external side effect is triggered by an ordinary test.
51. For the private YouTube acceptance upload, do not use this component test to generate another upload. The one real upload is centrally orchestrated and idempotently gated under the master framework.
52. Inspect the relevant unit/component test and add a regression test for each repaired defect where test infrastructure permits.
53. Run the smallest test covering this component first and record the exact command and actual exit result.
54. Run the relevant API/backend integration test where it can be proven safe and isolated.
55. Run the relevant browser/E2E test if available; do not describe static source inspection as a browser test.
56. Collect actual request/response evidence with secrets redacted. Link to the logs or test output that substantiate the result.
57. Compare the user-visible message/status with the actual backend response and persisted state.
58. Conduct Pass A by tracing requirements to implementation and successful tests.
59. Conduct Pass B independently using an alternate path such as persisted state, route registration, event log, task state, rendered output, refresh behavior, or a different test assertion.
60. If Pass A and Pass B disagree, investigate and document the discrepancy; do not average the results or silently pick the favorable one.
61. Classify a failure as UI defect, API contract mismatch, backend behavior defect, persistence defect, concurrency defect, configuration defect, missing test/evidence, or scope ambiguity.
62. Fix only defects within approved Phase 1–7 requirements and only through the governance process required by the freeze rules.
63. Before changing a shared API client, component, schema, backend route, or frozen domain, identify all affected pages and regression tests.
64. Keep the code change minimal and preserve pre-existing Git modifications and untracked files.
65. Never execute blanket Git reset/clean/checkout/restore commands or replace a whole file to make a small repair.
66. After a repair, rerun the failing reproduction, relevant component test, API/backend tests, and affected page regression checks.
67. Independently repeat Pass B after the repair, using evidence distinct from the original fix path where reasonably possible.
68. If the test fails, continue the diagnose/fix/retest loop within scope; if the failure requires unavailable authorization or unsafe operation, mark it blocked and continue unrelated work.
69. Do not stop at the first failed test if the cause is repairable within scope. Do not loop indefinitely if a genuine external or governance blocker exists.
70. Check that test teardown completes and does not silently mask failures; do not change global fixtures unless required and governed.
71. Confirm test DB isolation before any database mutation. Never migrate, drop, reset, or clean the operational clipforge database.
72. Confirm no test publishes an actual video except the one centralized, explicit, private acceptance upload authorized by the user.
73. Confirm no generated test file overwrites existing uploads or outputs and no cleanup task deletes user-owned media.
74. Run TypeScript and lint checks against the changed frontend where possible. Report repository-wide legacy issues separately from new introduced issues.
75. Run the production build after page/component changes and distinguish build output count from the number of user-facing pages.
76. Inspect browser console errors, failed network requests, React warnings, hydration issues, and unhandled promise rejections where browser execution is available.
77. Check responsive layout at narrow and wide viewport sizes, avoiding horizontal overflow, clipped dialogs, invisible controls, and inaccessible hover-only actions.
78. Check error messages are actionable, avoid secrets, and preserve user-entered form data where retry is expected.
79. Check the component handles loading, empty, success, partial-success, validation, unauthorized, not-found, conflict, rate-limit, server-error, and offline states as applicable.
80. Check that stale UI cache does not outlive a mutation. Invalidate/refetch only the relevant query/state according to the existing architecture.
81. Check a successful response has not been mistaken for semantic success when the backend returns a task ID with pending execution.
82. Check task completion is awaited or polled appropriately and the user can identify pending versus completed processing.
83. Check external provider errors propagate to a truthful status rather than being caught and converted into fabricated success.
84. Check any retry operation cannot create duplicate jobs, settings writes, uploads, publications, or cleanup operations.
85. Check the component has no hidden coupling to unapproved Phase 8 watermark branding or unsupported layouts.
86. Cross-reference actual behavior with `PHASE_TRACKER.md`, the relevant approved prompt, and the actual backend route/service. Do not assume draft/archived prompts are mandatory scope.
87. Check related documentation only if it is directly affected by the verified implementation; preserve historical audit evidence.
88. Update the component dossier with actual file paths, symbols, endpoint, backend behavior, test commands, Pass A evidence and Pass B evidence.
89. If a required operation is not present in the current UI, mark it absent and verify whether the approved specification requires it; do not silently invent UI.
90. If a required capability is absent, identify the exact implementation/API/test gap and fix it only when inside approved scope and governance permits.
91. Before any edit, record targeted Git status/diff; after edits, verify unrelated working-tree changes and untracked assets remain untouched.
92. Do not make changes beyond approved Phase 1–7 scope; Phase 8 watermark branding remains deferred unless separately authorized.
93. If this component offers a layout choice, require a real local reference thumbnail for every supported option and verify the output renderer matches it.
94. If this component participates in monitoring/publishing, check destination identity and state synchronization, and obey the central private-upload gate; do not create a second real upload.
95. Never expose secrets, run destructive database operations, publish public/unlisted test videos, or delete user media while verifying this component.
96. Perform Pass A: independently map every acceptance criterion to implementation and test evidence. Record exact paths, symbols, commands and actual results.
97. Perform Pass B independently using alternate evidence; explicitly confirm, contradict or leave uncertain every material Pass A claim.
98. Repair eligible defects and repeat the complete relevant test loop; if governance or safety blocks a fix, record the exact blocker and continue independent work.
99. Final acceptance for `STU-01`: every mandatory control in Upload Studio file picker and session initialization must have a real handler/contract, verified backend result, correct UI synchronization, passing relevant test, and independent Pass A/Pass B evidence.
100. Return a concise per-control matrix, exact files changed, tests and results, unresolved issues, and final component verdict. Do not declare PASS when evidence is missing.


---

### STU-02 — Chunk upload, progress, retry and resume

**Primary files to discover:** Upload Studio chunk APIs/client and backend session/chunk handling  
**Component focus:** Chunk progress, retry, resume/reorder if supported, cancel/error feedback  
**Acceptance focus:** Verify chunk numbering and hashes if implemented, idempotent retries, partial failure handling, progress reflects acknowledged server chunks, interrupted-upload recovery, and no completed state before server validation.

Copy this complete prompt into the autonomous execution context for this component. Do not execute it in isolation from the master framework.

**100-step component prompt:**
1. Act as the autonomous owner of Chunk upload, progress, retry and resume. Work only on the actual component discovered in the current checkout, not on an assumed or reconstructed UI.
2. Inspect Upload Studio chunk APIs/client and backend session/chunk handling; follow imports and references to identify the real source files, tests, route and backend dependencies.
3. Component inventory: Chunk progress, retry, resume/reorder if supported, cancel/error feedback. Discover the full list from the current UI and source. The list above is a focus guide, not permission to invent missing controls.
4. Acceptance focus: Verify chunk numbering and hashes if implemented, idempotent retries, partial failure handling, progress reflects acknowledged server chunks, interrupted-upload recovery, and no completed state before server validation.
5. Create or update dossier ID `STU-02` and link this component to its authoritative Phase/C-series acceptance criterion without redefining phase numbering.
6. Capture current behavior first: record the visible state, control labels, current handler, API call, server response, persisted state and known failure behavior.
7. List every individual button, input, dropdown, link, tab, selector, icon action, modal action and keyboard action in this component; give each a stable child control ID.
8. For every control, specify one positive test, one invalid/error test, one repeated-action/idempotency test where relevant, and one refresh/persistence or cross-page sync test where relevant.
9. Trace every mutation from browser event to API client, backend route, service, persistence/task/external provider and the final returned UI state.
10. Record the precise success assertion and the objective failure condition before changing code; never count a cosmetic animation or toast as proof of backend success.
11. Begin by opening the actual component, its parent, child components, types, API-client methods, and tests; do not trust a previous report without checking the current checkout.
12. List the exact visible controls that belong to this component, including icon-only buttons, links styled as buttons, keyboard shortcuts, toggles, dropdown options, modal actions, and any hidden action revealed by state.
13. For each control, state the requirement and observable success condition before testing it; map each requirement to the approved roadmap item without changing canonical phase numbers.
14. Check whether the control is intentionally non-interactive. If so, it must be semantically non-interactive and cannot imply that an unavailable action will occur.
15. Check accessible name, label/description, role, focusability, keyboard activation, disabled state, focus order, and whether focus returns appropriately after a dialog closes.
16. Trace the real event handler. Reject empty callbacks, console-only callbacks, hard-coded results, no-op links, timer-only simulation, and UI-only state mutation for backend operations.
17. Locate the corresponding API-client method and verify HTTP method, route path, body/query parameters, identifiers, headers/auth, response type, status-code handling, and timeout behavior.
18. Confirm that the route exists in the current backend application and is included under the actual router prefix. Do not infer endpoint existence from a frontend URL string.
19. Inspect backend validation, authorization, ownership checks, service calls, transaction boundaries, queue/task dispatch, and error mapping for the operation.
20. Identify the authoritative persisted record or external response that proves success. Do not use only a toast, button animation, or HTTP 200 as proof of the intended side effect.
21. Check that the frontend consumes the real response and maps returned identifiers/state correctly. Detect hard-coded status strings and mismatched field names.
22. Test the normal successful action using an isolated fixture or safe test record wherever available.
23. Test missing, malformed, stale, or unauthorized identifiers without modifying real user data.
24. Test the expected validation boundary conditions and verify the UI shows a useful message rather than silently dropping the request.
25. Test a server-side failure and confirm no false success indicator appears.
26. Test a network timeout/connection reset and verify the UI does not assume that the backend definitely failed if the outcome may be ambiguous.
27. Test loading indicators and confirm they clear on success, error, cancellation, component unmount, and every supported early return.
28. Test double-click, repeated Enter, quick toggle changes, duplicate network retries, and stale component state for unintended duplicate actions.
29. Check race handling if the action operates on mutable status, queue positions, decisions, settings, uploads, or publishing state.
30. Check that stale/out-of-order responses cannot overwrite a newer state. Use request cancellation, version checks, or existing conventions where needed and approved.
31. Check the response status is translated to the correct UI state, including pending/in-progress, completed, partial failure, failed, cancelled, and conflict states where applicable.
32. Check whether optimistic UI is used. If so, ensure rollback or reconciliation occurs when the backend rejects the change.
33. Check whether the changed state should survive page refresh/reopen; if yes, reload and compare the visible state to the backend-authoritative result.
34. Check whether the state is shared with other pages/components. Trigger the action and inspect every relevant surface for stale data.
35. Check that filters, sorting, selection, pagination, tabs, and the current detail item behave correctly after the operation changes data.
36. Check behavior when the list is empty, the API returns null/partial optional data, a media asset is missing, or a provider is temporarily unavailable.
37. Check timezones, timestamps, duration units, percentages, byte sizes, numeric formatting, and enum labels against backend semantics.
38. Check no credential, OAuth token, API key, signed URL, or private user payload is exposed in visible UI, ordinary logs, test output, or screenshots.
39. Check that test-mode fallbacks or synthetic fixtures can only be activated by the repository-defined trusted test context, never by user-controlled substring or arbitrary request fields.
40. Check the action does not add, restore, expose, or invoke caption/subtitle features. Internal transcription may remain for approved analysis and metadata purposes.
41. Check the action does not route to Ollama or require Ollama environment variables. Preserve approved cloud-hosted models even if their names contain Llama.
42. Check the operation cannot accidentally publish to a source/monitoring channel instead of an explicitly configured destination.
43. Where an action creates a job/task, verify the persisted job ID is retained and Celery dispatch occurs only at the intended transition.
44. Where an action updates a task, verify the backend state transition is valid, durable, and visible on subsequent reads.
45. Where an action creates or deletes a file, verify storage path containment, ownership, retention policy, and cleanup behavior using isolated files only.
46. Where a control selects a layout, verify the selected ID maps to a supported renderer option rather than only changing the visual highlight.
47. Where a control shows a layout thumbnail, verify the reference asset exists in the production build, has the correct accessible text, and truthfully represents output composition.
48. Where the component displays progress, verify it is sourced from authoritative progress/status fields and cannot display completion before the task completes.
49. Where the component refreshes/polls, verify intervals, overlap, cooldown, backoff, and unmount cleanup against the actual code contract.
50. Where external providers are involved, test mocked/sandbox cases first and ensure no accidental external side effect is triggered by an ordinary test.
51. For the private YouTube acceptance upload, do not use this component test to generate another upload. The one real upload is centrally orchestrated and idempotently gated under the master framework.
52. Inspect the relevant unit/component test and add a regression test for each repaired defect where test infrastructure permits.
53. Run the smallest test covering this component first and record the exact command and actual exit result.
54. Run the relevant API/backend integration test where it can be proven safe and isolated.
55. Run the relevant browser/E2E test if available; do not describe static source inspection as a browser test.
56. Collect actual request/response evidence with secrets redacted. Link to the logs or test output that substantiate the result.
57. Compare the user-visible message/status with the actual backend response and persisted state.
58. Conduct Pass A by tracing requirements to implementation and successful tests.
59. Conduct Pass B independently using an alternate path such as persisted state, route registration, event log, task state, rendered output, refresh behavior, or a different test assertion.
60. If Pass A and Pass B disagree, investigate and document the discrepancy; do not average the results or silently pick the favorable one.
61. Classify a failure as UI defect, API contract mismatch, backend behavior defect, persistence defect, concurrency defect, configuration defect, missing test/evidence, or scope ambiguity.
62. Fix only defects within approved Phase 1–7 requirements and only through the governance process required by the freeze rules.
63. Before changing a shared API client, component, schema, backend route, or frozen domain, identify all affected pages and regression tests.
64. Keep the code change minimal and preserve pre-existing Git modifications and untracked files.
65. Never execute blanket Git reset/clean/checkout/restore commands or replace a whole file to make a small repair.
66. After a repair, rerun the failing reproduction, relevant component test, API/backend tests, and affected page regression checks.
67. Independently repeat Pass B after the repair, using evidence distinct from the original fix path where reasonably possible.
68. If the test fails, continue the diagnose/fix/retest loop within scope; if the failure requires unavailable authorization or unsafe operation, mark it blocked and continue unrelated work.
69. Do not stop at the first failed test if the cause is repairable within scope. Do not loop indefinitely if a genuine external or governance blocker exists.
70. Check that test teardown completes and does not silently mask failures; do not change global fixtures unless required and governed.
71. Confirm test DB isolation before any database mutation. Never migrate, drop, reset, or clean the operational clipforge database.
72. Confirm no test publishes an actual video except the one centralized, explicit, private acceptance upload authorized by the user.
73. Confirm no generated test file overwrites existing uploads or outputs and no cleanup task deletes user-owned media.
74. Run TypeScript and lint checks against the changed frontend where possible. Report repository-wide legacy issues separately from new introduced issues.
75. Run the production build after page/component changes and distinguish build output count from the number of user-facing pages.
76. Inspect browser console errors, failed network requests, React warnings, hydration issues, and unhandled promise rejections where browser execution is available.
77. Check responsive layout at narrow and wide viewport sizes, avoiding horizontal overflow, clipped dialogs, invisible controls, and inaccessible hover-only actions.
78. Check error messages are actionable, avoid secrets, and preserve user-entered form data where retry is expected.
79. Check the component handles loading, empty, success, partial-success, validation, unauthorized, not-found, conflict, rate-limit, server-error, and offline states as applicable.
80. Check that stale UI cache does not outlive a mutation. Invalidate/refetch only the relevant query/state according to the existing architecture.
81. Check a successful response has not been mistaken for semantic success when the backend returns a task ID with pending execution.
82. Check task completion is awaited or polled appropriately and the user can identify pending versus completed processing.
83. Check external provider errors propagate to a truthful status rather than being caught and converted into fabricated success.
84. Check any retry operation cannot create duplicate jobs, settings writes, uploads, publications, or cleanup operations.
85. Check the component has no hidden coupling to unapproved Phase 8 watermark branding or unsupported layouts.
86. Cross-reference actual behavior with `PHASE_TRACKER.md`, the relevant approved prompt, and the actual backend route/service. Do not assume draft/archived prompts are mandatory scope.
87. Check related documentation only if it is directly affected by the verified implementation; preserve historical audit evidence.
88. Update the component dossier with actual file paths, symbols, endpoint, backend behavior, test commands, Pass A evidence and Pass B evidence.
89. If a required operation is not present in the current UI, mark it absent and verify whether the approved specification requires it; do not silently invent UI.
90. If a required capability is absent, identify the exact implementation/API/test gap and fix it only when inside approved scope and governance permits.
91. Before any edit, record targeted Git status/diff; after edits, verify unrelated working-tree changes and untracked assets remain untouched.
92. Do not make changes beyond approved Phase 1–7 scope; Phase 8 watermark branding remains deferred unless separately authorized.
93. If this component offers a layout choice, require a real local reference thumbnail for every supported option and verify the output renderer matches it.
94. If this component participates in monitoring/publishing, check destination identity and state synchronization, and obey the central private-upload gate; do not create a second real upload.
95. Never expose secrets, run destructive database operations, publish public/unlisted test videos, or delete user media while verifying this component.
96. Perform Pass A: independently map every acceptance criterion to implementation and test evidence. Record exact paths, symbols, commands and actual results.
97. Perform Pass B independently using alternate evidence; explicitly confirm, contradict or leave uncertain every material Pass A claim.
98. Repair eligible defects and repeat the complete relevant test loop; if governance or safety blocks a fix, record the exact blocker and continue independent work.
99. Final acceptance for `STU-02`: every mandatory control in Chunk upload, progress, retry and resume must have a real handler/contract, verified backend result, correct UI synchronization, passing relevant test, and independent Pass A/Pass B evidence.
100. Return a concise per-control matrix, exact files changed, tests and results, unresolved issues, and final component verdict. Do not declare PASS when evidence is missing.


---

### STU-03 — Manifest validation, commit and session lifecycle

**Primary files to discover:** Upload Studio manifest/commit APIs and database state model  
**Component focus:** Validate, commit/finalize, duplicate commit, expired/missing session states  
**Acceptance focus:** Verify server validates the complete manifest, commit is idempotent, invalid/missing chunks are rejected, transaction/session transitions are coherent, and refresh recovers the true server state.

Copy this complete prompt into the autonomous execution context for this component. Do not execute it in isolation from the master framework.

**100-step component prompt:**
1. Act as the autonomous owner of Manifest validation, commit and session lifecycle. Work only on the actual component discovered in the current checkout, not on an assumed or reconstructed UI.
2. Inspect Upload Studio manifest/commit APIs and database state model; follow imports and references to identify the real source files, tests, route and backend dependencies.
3. Component inventory: Validate, commit/finalize, duplicate commit, expired/missing session states. Discover the full list from the current UI and source. The list above is a focus guide, not permission to invent missing controls.
4. Acceptance focus: Verify server validates the complete manifest, commit is idempotent, invalid/missing chunks are rejected, transaction/session transitions are coherent, and refresh recovers the true server state.
5. Create or update dossier ID `STU-03` and link this component to its authoritative Phase/C-series acceptance criterion without redefining phase numbering.
6. Capture current behavior first: record the visible state, control labels, current handler, API call, server response, persisted state and known failure behavior.
7. List every individual button, input, dropdown, link, tab, selector, icon action, modal action and keyboard action in this component; give each a stable child control ID.
8. For every control, specify one positive test, one invalid/error test, one repeated-action/idempotency test where relevant, and one refresh/persistence or cross-page sync test where relevant.
9. Trace every mutation from browser event to API client, backend route, service, persistence/task/external provider and the final returned UI state.
10. Record the precise success assertion and the objective failure condition before changing code; never count a cosmetic animation or toast as proof of backend success.
11. Begin by opening the actual component, its parent, child components, types, API-client methods, and tests; do not trust a previous report without checking the current checkout.
12. List the exact visible controls that belong to this component, including icon-only buttons, links styled as buttons, keyboard shortcuts, toggles, dropdown options, modal actions, and any hidden action revealed by state.
13. For each control, state the requirement and observable success condition before testing it; map each requirement to the approved roadmap item without changing canonical phase numbers.
14. Check whether the control is intentionally non-interactive. If so, it must be semantically non-interactive and cannot imply that an unavailable action will occur.
15. Check accessible name, label/description, role, focusability, keyboard activation, disabled state, focus order, and whether focus returns appropriately after a dialog closes.
16. Trace the real event handler. Reject empty callbacks, console-only callbacks, hard-coded results, no-op links, timer-only simulation, and UI-only state mutation for backend operations.
17. Locate the corresponding API-client method and verify HTTP method, route path, body/query parameters, identifiers, headers/auth, response type, status-code handling, and timeout behavior.
18. Confirm that the route exists in the current backend application and is included under the actual router prefix. Do not infer endpoint existence from a frontend URL string.
19. Inspect backend validation, authorization, ownership checks, service calls, transaction boundaries, queue/task dispatch, and error mapping for the operation.
20. Identify the authoritative persisted record or external response that proves success. Do not use only a toast, button animation, or HTTP 200 as proof of the intended side effect.
21. Check that the frontend consumes the real response and maps returned identifiers/state correctly. Detect hard-coded status strings and mismatched field names.
22. Test the normal successful action using an isolated fixture or safe test record wherever available.
23. Test missing, malformed, stale, or unauthorized identifiers without modifying real user data.
24. Test the expected validation boundary conditions and verify the UI shows a useful message rather than silently dropping the request.
25. Test a server-side failure and confirm no false success indicator appears.
26. Test a network timeout/connection reset and verify the UI does not assume that the backend definitely failed if the outcome may be ambiguous.
27. Test loading indicators and confirm they clear on success, error, cancellation, component unmount, and every supported early return.
28. Test double-click, repeated Enter, quick toggle changes, duplicate network retries, and stale component state for unintended duplicate actions.
29. Check race handling if the action operates on mutable status, queue positions, decisions, settings, uploads, or publishing state.
30. Check that stale/out-of-order responses cannot overwrite a newer state. Use request cancellation, version checks, or existing conventions where needed and approved.
31. Check the response status is translated to the correct UI state, including pending/in-progress, completed, partial failure, failed, cancelled, and conflict states where applicable.
32. Check whether optimistic UI is used. If so, ensure rollback or reconciliation occurs when the backend rejects the change.
33. Check whether the changed state should survive page refresh/reopen; if yes, reload and compare the visible state to the backend-authoritative result.
34. Check whether the state is shared with other pages/components. Trigger the action and inspect every relevant surface for stale data.
35. Check that filters, sorting, selection, pagination, tabs, and the current detail item behave correctly after the operation changes data.
36. Check behavior when the list is empty, the API returns null/partial optional data, a media asset is missing, or a provider is temporarily unavailable.
37. Check timezones, timestamps, duration units, percentages, byte sizes, numeric formatting, and enum labels against backend semantics.
38. Check no credential, OAuth token, API key, signed URL, or private user payload is exposed in visible UI, ordinary logs, test output, or screenshots.
39. Check that test-mode fallbacks or synthetic fixtures can only be activated by the repository-defined trusted test context, never by user-controlled substring or arbitrary request fields.
40. Check the action does not add, restore, expose, or invoke caption/subtitle features. Internal transcription may remain for approved analysis and metadata purposes.
41. Check the action does not route to Ollama or require Ollama environment variables. Preserve approved cloud-hosted models even if their names contain Llama.
42. Check the operation cannot accidentally publish to a source/monitoring channel instead of an explicitly configured destination.
43. Where an action creates a job/task, verify the persisted job ID is retained and Celery dispatch occurs only at the intended transition.
44. Where an action updates a task, verify the backend state transition is valid, durable, and visible on subsequent reads.
45. Where an action creates or deletes a file, verify storage path containment, ownership, retention policy, and cleanup behavior using isolated files only.
46. Where a control selects a layout, verify the selected ID maps to a supported renderer option rather than only changing the visual highlight.
47. Where a control shows a layout thumbnail, verify the reference asset exists in the production build, has the correct accessible text, and truthfully represents output composition.
48. Where the component displays progress, verify it is sourced from authoritative progress/status fields and cannot display completion before the task completes.
49. Where the component refreshes/polls, verify intervals, overlap, cooldown, backoff, and unmount cleanup against the actual code contract.
50. Where external providers are involved, test mocked/sandbox cases first and ensure no accidental external side effect is triggered by an ordinary test.
51. For the private YouTube acceptance upload, do not use this component test to generate another upload. The one real upload is centrally orchestrated and idempotently gated under the master framework.
52. Inspect the relevant unit/component test and add a regression test for each repaired defect where test infrastructure permits.
53. Run the smallest test covering this component first and record the exact command and actual exit result.
54. Run the relevant API/backend integration test where it can be proven safe and isolated.
55. Run the relevant browser/E2E test if available; do not describe static source inspection as a browser test.
56. Collect actual request/response evidence with secrets redacted. Link to the logs or test output that substantiate the result.
57. Compare the user-visible message/status with the actual backend response and persisted state.
58. Conduct Pass A by tracing requirements to implementation and successful tests.
59. Conduct Pass B independently using an alternate path such as persisted state, route registration, event log, task state, rendered output, refresh behavior, or a different test assertion.
60. If Pass A and Pass B disagree, investigate and document the discrepancy; do not average the results or silently pick the favorable one.
61. Classify a failure as UI defect, API contract mismatch, backend behavior defect, persistence defect, concurrency defect, configuration defect, missing test/evidence, or scope ambiguity.
62. Fix only defects within approved Phase 1–7 requirements and only through the governance process required by the freeze rules.
63. Before changing a shared API client, component, schema, backend route, or frozen domain, identify all affected pages and regression tests.
64. Keep the code change minimal and preserve pre-existing Git modifications and untracked files.
65. Never execute blanket Git reset/clean/checkout/restore commands or replace a whole file to make a small repair.
66. After a repair, rerun the failing reproduction, relevant component test, API/backend tests, and affected page regression checks.
67. Independently repeat Pass B after the repair, using evidence distinct from the original fix path where reasonably possible.
68. If the test fails, continue the diagnose/fix/retest loop within scope; if the failure requires unavailable authorization or unsafe operation, mark it blocked and continue unrelated work.
69. Do not stop at the first failed test if the cause is repairable within scope. Do not loop indefinitely if a genuine external or governance blocker exists.
70. Check that test teardown completes and does not silently mask failures; do not change global fixtures unless required and governed.
71. Confirm test DB isolation before any database mutation. Never migrate, drop, reset, or clean the operational clipforge database.
72. Confirm no test publishes an actual video except the one centralized, explicit, private acceptance upload authorized by the user.
73. Confirm no generated test file overwrites existing uploads or outputs and no cleanup task deletes user-owned media.
74. Run TypeScript and lint checks against the changed frontend where possible. Report repository-wide legacy issues separately from new introduced issues.
75. Run the production build after page/component changes and distinguish build output count from the number of user-facing pages.
76. Inspect browser console errors, failed network requests, React warnings, hydration issues, and unhandled promise rejections where browser execution is available.
77. Check responsive layout at narrow and wide viewport sizes, avoiding horizontal overflow, clipped dialogs, invisible controls, and inaccessible hover-only actions.
78. Check error messages are actionable, avoid secrets, and preserve user-entered form data where retry is expected.
79. Check the component handles loading, empty, success, partial-success, validation, unauthorized, not-found, conflict, rate-limit, server-error, and offline states as applicable.
80. Check that stale UI cache does not outlive a mutation. Invalidate/refetch only the relevant query/state according to the existing architecture.
81. Check a successful response has not been mistaken for semantic success when the backend returns a task ID with pending execution.
82. Check task completion is awaited or polled appropriately and the user can identify pending versus completed processing.
83. Check external provider errors propagate to a truthful status rather than being caught and converted into fabricated success.
84. Check any retry operation cannot create duplicate jobs, settings writes, uploads, publications, or cleanup operations.
85. Check the component has no hidden coupling to unapproved Phase 8 watermark branding or unsupported layouts.
86. Cross-reference actual behavior with `PHASE_TRACKER.md`, the relevant approved prompt, and the actual backend route/service. Do not assume draft/archived prompts are mandatory scope.
87. Check related documentation only if it is directly affected by the verified implementation; preserve historical audit evidence.
88. Update the component dossier with actual file paths, symbols, endpoint, backend behavior, test commands, Pass A evidence and Pass B evidence.
89. If a required operation is not present in the current UI, mark it absent and verify whether the approved specification requires it; do not silently invent UI.
90. If a required capability is absent, identify the exact implementation/API/test gap and fix it only when inside approved scope and governance permits.
91. Before any edit, record targeted Git status/diff; after edits, verify unrelated working-tree changes and untracked assets remain untouched.
92. Do not make changes beyond approved Phase 1–7 scope; Phase 8 watermark branding remains deferred unless separately authorized.
93. If this component offers a layout choice, require a real local reference thumbnail for every supported option and verify the output renderer matches it.
94. If this component participates in monitoring/publishing, check destination identity and state synchronization, and obey the central private-upload gate; do not create a second real upload.
95. Never expose secrets, run destructive database operations, publish public/unlisted test videos, or delete user media while verifying this component.
96. Perform Pass A: independently map every acceptance criterion to implementation and test evidence. Record exact paths, symbols, commands and actual results.
97. Perform Pass B independently using alternate evidence; explicitly confirm, contradict or leave uncertain every material Pass A claim.
98. Repair eligible defects and repeat the complete relevant test loop; if governance or safety blocks a fix, record the exact blocker and continue independent work.
99. Final acceptance for `STU-03`: every mandatory control in Manifest validation, commit and session lifecycle must have a real handler/contract, verified backend result, correct UI synchronization, passing relevant test, and independent Pass A/Pass B evidence.
100. Return a concise per-control matrix, exact files changed, tests and results, unresolved issues, and final component verdict. Do not declare PASS when evidence is missing.


---

### STU-04 — Thumbnail generation and preview

**Primary files to discover:** Upload Studio thumbnail endpoint/UI and returned artifact path  
**Component focus:** Generate/retry, thumbnail display, loading/error state  
**Acceptance focus:** Verify generation calls the actual endpoint, artifact belongs to the selected upload/video, failed generation is recoverable, returned path is accessible, and UI never shows a stale thumbnail from another item.

Copy this complete prompt into the autonomous execution context for this component. Do not execute it in isolation from the master framework.

**100-step component prompt:**
1. Act as the autonomous owner of Thumbnail generation and preview. Work only on the actual component discovered in the current checkout, not on an assumed or reconstructed UI.
2. Inspect Upload Studio thumbnail endpoint/UI and returned artifact path; follow imports and references to identify the real source files, tests, route and backend dependencies.
3. Component inventory: Generate/retry, thumbnail display, loading/error state. Discover the full list from the current UI and source. The list above is a focus guide, not permission to invent missing controls.
4. Acceptance focus: Verify generation calls the actual endpoint, artifact belongs to the selected upload/video, failed generation is recoverable, returned path is accessible, and UI never shows a stale thumbnail from another item.
5. Create or update dossier ID `STU-04` and link this component to its authoritative Phase/C-series acceptance criterion without redefining phase numbering.
6. Capture current behavior first: record the visible state, control labels, current handler, API call, server response, persisted state and known failure behavior.
7. List every individual button, input, dropdown, link, tab, selector, icon action, modal action and keyboard action in this component; give each a stable child control ID.
8. For every control, specify one positive test, one invalid/error test, one repeated-action/idempotency test where relevant, and one refresh/persistence or cross-page sync test where relevant.
9. Trace every mutation from browser event to API client, backend route, service, persistence/task/external provider and the final returned UI state.
10. Record the precise success assertion and the objective failure condition before changing code; never count a cosmetic animation or toast as proof of backend success.
11. Begin by opening the actual component, its parent, child components, types, API-client methods, and tests; do not trust a previous report without checking the current checkout.
12. List the exact visible controls that belong to this component, including icon-only buttons, links styled as buttons, keyboard shortcuts, toggles, dropdown options, modal actions, and any hidden action revealed by state.
13. For each control, state the requirement and observable success condition before testing it; map each requirement to the approved roadmap item without changing canonical phase numbers.
14. Check whether the control is intentionally non-interactive. If so, it must be semantically non-interactive and cannot imply that an unavailable action will occur.
15. Check accessible name, label/description, role, focusability, keyboard activation, disabled state, focus order, and whether focus returns appropriately after a dialog closes.
16. Trace the real event handler. Reject empty callbacks, console-only callbacks, hard-coded results, no-op links, timer-only simulation, and UI-only state mutation for backend operations.
17. Locate the corresponding API-client method and verify HTTP method, route path, body/query parameters, identifiers, headers/auth, response type, status-code handling, and timeout behavior.
18. Confirm that the route exists in the current backend application and is included under the actual router prefix. Do not infer endpoint existence from a frontend URL string.
19. Inspect backend validation, authorization, ownership checks, service calls, transaction boundaries, queue/task dispatch, and error mapping for the operation.
20. Identify the authoritative persisted record or external response that proves success. Do not use only a toast, button animation, or HTTP 200 as proof of the intended side effect.
21. Check that the frontend consumes the real response and maps returned identifiers/state correctly. Detect hard-coded status strings and mismatched field names.
22. Test the normal successful action using an isolated fixture or safe test record wherever available.
23. Test missing, malformed, stale, or unauthorized identifiers without modifying real user data.
24. Test the expected validation boundary conditions and verify the UI shows a useful message rather than silently dropping the request.
25. Test a server-side failure and confirm no false success indicator appears.
26. Test a network timeout/connection reset and verify the UI does not assume that the backend definitely failed if the outcome may be ambiguous.
27. Test loading indicators and confirm they clear on success, error, cancellation, component unmount, and every supported early return.
28. Test double-click, repeated Enter, quick toggle changes, duplicate network retries, and stale component state for unintended duplicate actions.
29. Check race handling if the action operates on mutable status, queue positions, decisions, settings, uploads, or publishing state.
30. Check that stale/out-of-order responses cannot overwrite a newer state. Use request cancellation, version checks, or existing conventions where needed and approved.
31. Check the response status is translated to the correct UI state, including pending/in-progress, completed, partial failure, failed, cancelled, and conflict states where applicable.
32. Check whether optimistic UI is used. If so, ensure rollback or reconciliation occurs when the backend rejects the change.
33. Check whether the changed state should survive page refresh/reopen; if yes, reload and compare the visible state to the backend-authoritative result.
34. Check whether the state is shared with other pages/components. Trigger the action and inspect every relevant surface for stale data.
35. Check that filters, sorting, selection, pagination, tabs, and the current detail item behave correctly after the operation changes data.
36. Check behavior when the list is empty, the API returns null/partial optional data, a media asset is missing, or a provider is temporarily unavailable.
37. Check timezones, timestamps, duration units, percentages, byte sizes, numeric formatting, and enum labels against backend semantics.
38. Check no credential, OAuth token, API key, signed URL, or private user payload is exposed in visible UI, ordinary logs, test output, or screenshots.
39. Check that test-mode fallbacks or synthetic fixtures can only be activated by the repository-defined trusted test context, never by user-controlled substring or arbitrary request fields.
40. Check the action does not add, restore, expose, or invoke caption/subtitle features. Internal transcription may remain for approved analysis and metadata purposes.
41. Check the action does not route to Ollama or require Ollama environment variables. Preserve approved cloud-hosted models even if their names contain Llama.
42. Check the operation cannot accidentally publish to a source/monitoring channel instead of an explicitly configured destination.
43. Where an action creates a job/task, verify the persisted job ID is retained and Celery dispatch occurs only at the intended transition.
44. Where an action updates a task, verify the backend state transition is valid, durable, and visible on subsequent reads.
45. Where an action creates or deletes a file, verify storage path containment, ownership, retention policy, and cleanup behavior using isolated files only.
46. Where a control selects a layout, verify the selected ID maps to a supported renderer option rather than only changing the visual highlight.
47. Where a control shows a layout thumbnail, verify the reference asset exists in the production build, has the correct accessible text, and truthfully represents output composition.
48. Where the component displays progress, verify it is sourced from authoritative progress/status fields and cannot display completion before the task completes.
49. Where the component refreshes/polls, verify intervals, overlap, cooldown, backoff, and unmount cleanup against the actual code contract.
50. Where external providers are involved, test mocked/sandbox cases first and ensure no accidental external side effect is triggered by an ordinary test.
51. For the private YouTube acceptance upload, do not use this component test to generate another upload. The one real upload is centrally orchestrated and idempotently gated under the master framework.
52. Inspect the relevant unit/component test and add a regression test for each repaired defect where test infrastructure permits.
53. Run the smallest test covering this component first and record the exact command and actual exit result.
54. Run the relevant API/backend integration test where it can be proven safe and isolated.
55. Run the relevant browser/E2E test if available; do not describe static source inspection as a browser test.
56. Collect actual request/response evidence with secrets redacted. Link to the logs or test output that substantiate the result.
57. Compare the user-visible message/status with the actual backend response and persisted state.
58. Conduct Pass A by tracing requirements to implementation and successful tests.
59. Conduct Pass B independently using an alternate path such as persisted state, route registration, event log, task state, rendered output, refresh behavior, or a different test assertion.
60. If Pass A and Pass B disagree, investigate and document the discrepancy; do not average the results or silently pick the favorable one.
61. Classify a failure as UI defect, API contract mismatch, backend behavior defect, persistence defect, concurrency defect, configuration defect, missing test/evidence, or scope ambiguity.
62. Fix only defects within approved Phase 1–7 requirements and only through the governance process required by the freeze rules.
63. Before changing a shared API client, component, schema, backend route, or frozen domain, identify all affected pages and regression tests.
64. Keep the code change minimal and preserve pre-existing Git modifications and untracked files.
65. Never execute blanket Git reset/clean/checkout/restore commands or replace a whole file to make a small repair.
66. After a repair, rerun the failing reproduction, relevant component test, API/backend tests, and affected page regression checks.
67. Independently repeat Pass B after the repair, using evidence distinct from the original fix path where reasonably possible.
68. If the test fails, continue the diagnose/fix/retest loop within scope; if the failure requires unavailable authorization or unsafe operation, mark it blocked and continue unrelated work.
69. Do not stop at the first failed test if the cause is repairable within scope. Do not loop indefinitely if a genuine external or governance blocker exists.
70. Check that test teardown completes and does not silently mask failures; do not change global fixtures unless required and governed.
71. Confirm test DB isolation before any database mutation. Never migrate, drop, reset, or clean the operational clipforge database.
72. Confirm no test publishes an actual video except the one centralized, explicit, private acceptance upload authorized by the user.
73. Confirm no generated test file overwrites existing uploads or outputs and no cleanup task deletes user-owned media.
74. Run TypeScript and lint checks against the changed frontend where possible. Report repository-wide legacy issues separately from new introduced issues.
75. Run the production build after page/component changes and distinguish build output count from the number of user-facing pages.
76. Inspect browser console errors, failed network requests, React warnings, hydration issues, and unhandled promise rejections where browser execution is available.
77. Check responsive layout at narrow and wide viewport sizes, avoiding horizontal overflow, clipped dialogs, invisible controls, and inaccessible hover-only actions.
78. Check error messages are actionable, avoid secrets, and preserve user-entered form data where retry is expected.
79. Check the component handles loading, empty, success, partial-success, validation, unauthorized, not-found, conflict, rate-limit, server-error, and offline states as applicable.
80. Check that stale UI cache does not outlive a mutation. Invalidate/refetch only the relevant query/state according to the existing architecture.
81. Check a successful response has not been mistaken for semantic success when the backend returns a task ID with pending execution.
82. Check task completion is awaited or polled appropriately and the user can identify pending versus completed processing.
83. Check external provider errors propagate to a truthful status rather than being caught and converted into fabricated success.
84. Check any retry operation cannot create duplicate jobs, settings writes, uploads, publications, or cleanup operations.
85. Check the component has no hidden coupling to unapproved Phase 8 watermark branding or unsupported layouts.
86. Cross-reference actual behavior with `PHASE_TRACKER.md`, the relevant approved prompt, and the actual backend route/service. Do not assume draft/archived prompts are mandatory scope.
87. Check related documentation only if it is directly affected by the verified implementation; preserve historical audit evidence.
88. Update the component dossier with actual file paths, symbols, endpoint, backend behavior, test commands, Pass A evidence and Pass B evidence.
89. If a required operation is not present in the current UI, mark it absent and verify whether the approved specification requires it; do not silently invent UI.
90. If a required capability is absent, identify the exact implementation/API/test gap and fix it only when inside approved scope and governance permits.
91. Before any edit, record targeted Git status/diff; after edits, verify unrelated working-tree changes and untracked assets remain untouched.
92. Do not make changes beyond approved Phase 1–7 scope; Phase 8 watermark branding remains deferred unless separately authorized.
93. If this component offers a layout choice, require a real local reference thumbnail for every supported option and verify the output renderer matches it.
94. If this component participates in monitoring/publishing, check destination identity and state synchronization, and obey the central private-upload gate; do not create a second real upload.
95. Never expose secrets, run destructive database operations, publish public/unlisted test videos, or delete user media while verifying this component.
96. Perform Pass A: independently map every acceptance criterion to implementation and test evidence. Record exact paths, symbols, commands and actual results.
97. Perform Pass B independently using alternate evidence; explicitly confirm, contradict or leave uncertain every material Pass A claim.
98. Repair eligible defects and repeat the complete relevant test loop; if governance or safety blocks a fix, record the exact blocker and continue independent work.
99. Final acceptance for `STU-04`: every mandatory control in Thumbnail generation and preview must have a real handler/contract, verified backend result, correct UI synchronization, passing relevant test, and independent Pass A/Pass B evidence.
100. Return a concise per-control matrix, exact files changed, tests and results, unresolved issues, and final component verdict. Do not declare PASS when evidence is missing.


---

### STU-05 — Upload-to-processing handoff and status synchronization

**Primary files to discover:** Studio commit → backend task dispatch → Dashboard/Jobs/Studio status  
**Component focus:** Start processing, task status, link to Dashboard/job detail  
**Acceptance focus:** Verify exact uploaded asset/session becomes the intended job, dispatch occurs only after valid commit, worker execution begins, every stage is persisted, progress is coherent across pages, and failures can be recovered.

Copy this complete prompt into the autonomous execution context for this component. Do not execute it in isolation from the master framework.

**100-step component prompt:**
1. Act as the autonomous owner of Upload-to-processing handoff and status synchronization. Work only on the actual component discovered in the current checkout, not on an assumed or reconstructed UI.
2. Inspect Studio commit → backend task dispatch → Dashboard/Jobs/Studio status; follow imports and references to identify the real source files, tests, route and backend dependencies.
3. Component inventory: Start processing, task status, link to Dashboard/job detail. Discover the full list from the current UI and source. The list above is a focus guide, not permission to invent missing controls.
4. Acceptance focus: Verify exact uploaded asset/session becomes the intended job, dispatch occurs only after valid commit, worker execution begins, every stage is persisted, progress is coherent across pages, and failures can be recovered.
5. Create or update dossier ID `STU-05` and link this component to its authoritative Phase/C-series acceptance criterion without redefining phase numbering.
6. Capture current behavior first: record the visible state, control labels, current handler, API call, server response, persisted state and known failure behavior.
7. List every individual button, input, dropdown, link, tab, selector, icon action, modal action and keyboard action in this component; give each a stable child control ID.
8. For every control, specify one positive test, one invalid/error test, one repeated-action/idempotency test where relevant, and one refresh/persistence or cross-page sync test where relevant.
9. Trace every mutation from browser event to API client, backend route, service, persistence/task/external provider and the final returned UI state.
10. Record the precise success assertion and the objective failure condition before changing code; never count a cosmetic animation or toast as proof of backend success.
11. Begin by opening the actual component, its parent, child components, types, API-client methods, and tests; do not trust a previous report without checking the current checkout.
12. List the exact visible controls that belong to this component, including icon-only buttons, links styled as buttons, keyboard shortcuts, toggles, dropdown options, modal actions, and any hidden action revealed by state.
13. For each control, state the requirement and observable success condition before testing it; map each requirement to the approved roadmap item without changing canonical phase numbers.
14. Check whether the control is intentionally non-interactive. If so, it must be semantically non-interactive and cannot imply that an unavailable action will occur.
15. Check accessible name, label/description, role, focusability, keyboard activation, disabled state, focus order, and whether focus returns appropriately after a dialog closes.
16. Trace the real event handler. Reject empty callbacks, console-only callbacks, hard-coded results, no-op links, timer-only simulation, and UI-only state mutation for backend operations.
17. Locate the corresponding API-client method and verify HTTP method, route path, body/query parameters, identifiers, headers/auth, response type, status-code handling, and timeout behavior.
18. Confirm that the route exists in the current backend application and is included under the actual router prefix. Do not infer endpoint existence from a frontend URL string.
19. Inspect backend validation, authorization, ownership checks, service calls, transaction boundaries, queue/task dispatch, and error mapping for the operation.
20. Identify the authoritative persisted record or external response that proves success. Do not use only a toast, button animation, or HTTP 200 as proof of the intended side effect.
21. Check that the frontend consumes the real response and maps returned identifiers/state correctly. Detect hard-coded status strings and mismatched field names.
22. Test the normal successful action using an isolated fixture or safe test record wherever available.
23. Test missing, malformed, stale, or unauthorized identifiers without modifying real user data.
24. Test the expected validation boundary conditions and verify the UI shows a useful message rather than silently dropping the request.
25. Test a server-side failure and confirm no false success indicator appears.
26. Test a network timeout/connection reset and verify the UI does not assume that the backend definitely failed if the outcome may be ambiguous.
27. Test loading indicators and confirm they clear on success, error, cancellation, component unmount, and every supported early return.
28. Test double-click, repeated Enter, quick toggle changes, duplicate network retries, and stale component state for unintended duplicate actions.
29. Check race handling if the action operates on mutable status, queue positions, decisions, settings, uploads, or publishing state.
30. Check that stale/out-of-order responses cannot overwrite a newer state. Use request cancellation, version checks, or existing conventions where needed and approved.
31. Check the response status is translated to the correct UI state, including pending/in-progress, completed, partial failure, failed, cancelled, and conflict states where applicable.
32. Check whether optimistic UI is used. If so, ensure rollback or reconciliation occurs when the backend rejects the change.
33. Check whether the changed state should survive page refresh/reopen; if yes, reload and compare the visible state to the backend-authoritative result.
34. Check whether the state is shared with other pages/components. Trigger the action and inspect every relevant surface for stale data.
35. Check that filters, sorting, selection, pagination, tabs, and the current detail item behave correctly after the operation changes data.
36. Check behavior when the list is empty, the API returns null/partial optional data, a media asset is missing, or a provider is temporarily unavailable.
37. Check timezones, timestamps, duration units, percentages, byte sizes, numeric formatting, and enum labels against backend semantics.
38. Check no credential, OAuth token, API key, signed URL, or private user payload is exposed in visible UI, ordinary logs, test output, or screenshots.
39. Check that test-mode fallbacks or synthetic fixtures can only be activated by the repository-defined trusted test context, never by user-controlled substring or arbitrary request fields.
40. Check the action does not add, restore, expose, or invoke caption/subtitle features. Internal transcription may remain for approved analysis and metadata purposes.
41. Check the action does not route to Ollama or require Ollama environment variables. Preserve approved cloud-hosted models even if their names contain Llama.
42. Check the operation cannot accidentally publish to a source/monitoring channel instead of an explicitly configured destination.
43. Where an action creates a job/task, verify the persisted job ID is retained and Celery dispatch occurs only at the intended transition.
44. Where an action updates a task, verify the backend state transition is valid, durable, and visible on subsequent reads.
45. Where an action creates or deletes a file, verify storage path containment, ownership, retention policy, and cleanup behavior using isolated files only.
46. Where a control selects a layout, verify the selected ID maps to a supported renderer option rather than only changing the visual highlight.
47. Where a control shows a layout thumbnail, verify the reference asset exists in the production build, has the correct accessible text, and truthfully represents output composition.
48. Where the component displays progress, verify it is sourced from authoritative progress/status fields and cannot display completion before the task completes.
49. Where the component refreshes/polls, verify intervals, overlap, cooldown, backoff, and unmount cleanup against the actual code contract.
50. Where external providers are involved, test mocked/sandbox cases first and ensure no accidental external side effect is triggered by an ordinary test.
51. For the private YouTube acceptance upload, do not use this component test to generate another upload. The one real upload is centrally orchestrated and idempotently gated under the master framework.
52. Inspect the relevant unit/component test and add a regression test for each repaired defect where test infrastructure permits.
53. Run the smallest test covering this component first and record the exact command and actual exit result.
54. Run the relevant API/backend integration test where it can be proven safe and isolated.
55. Run the relevant browser/E2E test if available; do not describe static source inspection as a browser test.
56. Collect actual request/response evidence with secrets redacted. Link to the logs or test output that substantiate the result.
57. Compare the user-visible message/status with the actual backend response and persisted state.
58. Conduct Pass A by tracing requirements to implementation and successful tests.
59. Conduct Pass B independently using an alternate path such as persisted state, route registration, event log, task state, rendered output, refresh behavior, or a different test assertion.
60. If Pass A and Pass B disagree, investigate and document the discrepancy; do not average the results or silently pick the favorable one.
61. Classify a failure as UI defect, API contract mismatch, backend behavior defect, persistence defect, concurrency defect, configuration defect, missing test/evidence, or scope ambiguity.
62. Fix only defects within approved Phase 1–7 requirements and only through the governance process required by the freeze rules.
63. Before changing a shared API client, component, schema, backend route, or frozen domain, identify all affected pages and regression tests.
64. Keep the code change minimal and preserve pre-existing Git modifications and untracked files.
65. Never execute blanket Git reset/clean/checkout/restore commands or replace a whole file to make a small repair.
66. After a repair, rerun the failing reproduction, relevant component test, API/backend tests, and affected page regression checks.
67. Independently repeat Pass B after the repair, using evidence distinct from the original fix path where reasonably possible.
68. If the test fails, continue the diagnose/fix/retest loop within scope; if the failure requires unavailable authorization or unsafe operation, mark it blocked and continue unrelated work.
69. Do not stop at the first failed test if the cause is repairable within scope. Do not loop indefinitely if a genuine external or governance blocker exists.
70. Check that test teardown completes and does not silently mask failures; do not change global fixtures unless required and governed.
71. Confirm test DB isolation before any database mutation. Never migrate, drop, reset, or clean the operational clipforge database.
72. Confirm no test publishes an actual video except the one centralized, explicit, private acceptance upload authorized by the user.
73. Confirm no generated test file overwrites existing uploads or outputs and no cleanup task deletes user-owned media.
74. Run TypeScript and lint checks against the changed frontend where possible. Report repository-wide legacy issues separately from new introduced issues.
75. Run the production build after page/component changes and distinguish build output count from the number of user-facing pages.
76. Inspect browser console errors, failed network requests, React warnings, hydration issues, and unhandled promise rejections where browser execution is available.
77. Check responsive layout at narrow and wide viewport sizes, avoiding horizontal overflow, clipped dialogs, invisible controls, and inaccessible hover-only actions.
78. Check error messages are actionable, avoid secrets, and preserve user-entered form data where retry is expected.
79. Check the component handles loading, empty, success, partial-success, validation, unauthorized, not-found, conflict, rate-limit, server-error, and offline states as applicable.
80. Check that stale UI cache does not outlive a mutation. Invalidate/refetch only the relevant query/state according to the existing architecture.
81. Check a successful response has not been mistaken for semantic success when the backend returns a task ID with pending execution.
82. Check task completion is awaited or polled appropriately and the user can identify pending versus completed processing.
83. Check external provider errors propagate to a truthful status rather than being caught and converted into fabricated success.
84. Check any retry operation cannot create duplicate jobs, settings writes, uploads, publications, or cleanup operations.
85. Check the component has no hidden coupling to unapproved Phase 8 watermark branding or unsupported layouts.
86. Cross-reference actual behavior with `PHASE_TRACKER.md`, the relevant approved prompt, and the actual backend route/service. Do not assume draft/archived prompts are mandatory scope.
87. Check related documentation only if it is directly affected by the verified implementation; preserve historical audit evidence.
88. Update the component dossier with actual file paths, symbols, endpoint, backend behavior, test commands, Pass A evidence and Pass B evidence.
89. If a required operation is not present in the current UI, mark it absent and verify whether the approved specification requires it; do not silently invent UI.
90. If a required capability is absent, identify the exact implementation/API/test gap and fix it only when inside approved scope and governance permits.
91. Before any edit, record targeted Git status/diff; after edits, verify unrelated working-tree changes and untracked assets remain untouched.
92. Do not make changes beyond approved Phase 1–7 scope; Phase 8 watermark branding remains deferred unless separately authorized.
93. If this component offers a layout choice, require a real local reference thumbnail for every supported option and verify the output renderer matches it.
94. If this component participates in monitoring/publishing, check destination identity and state synchronization, and obey the central private-upload gate; do not create a second real upload.
95. Never expose secrets, run destructive database operations, publish public/unlisted test videos, or delete user media while verifying this component.
96. Perform Pass A: independently map every acceptance criterion to implementation and test evidence. Record exact paths, symbols, commands and actual results.
97. Perform Pass B independently using alternate evidence; explicitly confirm, contradict or leave uncertain every material Pass A claim.
98. Repair eligible defects and repeat the complete relevant test loop; if governance or safety blocks a fix, record the exact blocker and continue independent work.
99. Final acceptance for `STU-05`: every mandatory control in Upload-to-processing handoff and status synchronization must have a real handler/contract, verified backend result, correct UI synchronization, passing relevant test, and independent Pass A/Pass B evidence.
100. Return a concise per-control matrix, exact files changed, tests and results, unresolved issues, and final component verdict. Do not declare PASS when evidence is missing.


---

### STU-06 — Upload-to-publishing handoff where implemented

**Primary files to discover:** Studio final publishing step and publish API if the approved UI has one  
**Component focus:** Destination, metadata, privacy selector, submit/status result  
**Acceptance focus:** Verify destination role and identity, required metadata, private visibility for the authorized real-channel test, unique operation ID, persisted publication job, and correct result on Publish page. If the current UI does not support this directly, mark not present and verify the approved alternate workflow.

Copy this complete prompt into the autonomous execution context for this component. Do not execute it in isolation from the master framework.

**100-step component prompt:**
1. Act as the autonomous owner of Upload-to-publishing handoff where implemented. Work only on the actual component discovered in the current checkout, not on an assumed or reconstructed UI.
2. Inspect Studio final publishing step and publish API if the approved UI has one; follow imports and references to identify the real source files, tests, route and backend dependencies.
3. Component inventory: Destination, metadata, privacy selector, submit/status result. Discover the full list from the current UI and source. The list above is a focus guide, not permission to invent missing controls.
4. Acceptance focus: Verify destination role and identity, required metadata, private visibility for the authorized real-channel test, unique operation ID, persisted publication job, and correct result on Publish page. If the current UI does not support this directly, mark not present and verify the approved alternate workflow.
5. Create or update dossier ID `STU-06` and link this component to its authoritative Phase/C-series acceptance criterion without redefining phase numbering.
6. Capture current behavior first: record the visible state, control labels, current handler, API call, server response, persisted state and known failure behavior.
7. List every individual button, input, dropdown, link, tab, selector, icon action, modal action and keyboard action in this component; give each a stable child control ID.
8. For every control, specify one positive test, one invalid/error test, one repeated-action/idempotency test where relevant, and one refresh/persistence or cross-page sync test where relevant.
9. Trace every mutation from browser event to API client, backend route, service, persistence/task/external provider and the final returned UI state.
10. Record the precise success assertion and the objective failure condition before changing code; never count a cosmetic animation or toast as proof of backend success.
11. Begin by opening the actual component, its parent, child components, types, API-client methods, and tests; do not trust a previous report without checking the current checkout.
12. List the exact visible controls that belong to this component, including icon-only buttons, links styled as buttons, keyboard shortcuts, toggles, dropdown options, modal actions, and any hidden action revealed by state.
13. For each control, state the requirement and observable success condition before testing it; map each requirement to the approved roadmap item without changing canonical phase numbers.
14. Check whether the control is intentionally non-interactive. If so, it must be semantically non-interactive and cannot imply that an unavailable action will occur.
15. Check accessible name, label/description, role, focusability, keyboard activation, disabled state, focus order, and whether focus returns appropriately after a dialog closes.
16. Trace the real event handler. Reject empty callbacks, console-only callbacks, hard-coded results, no-op links, timer-only simulation, and UI-only state mutation for backend operations.
17. Locate the corresponding API-client method and verify HTTP method, route path, body/query parameters, identifiers, headers/auth, response type, status-code handling, and timeout behavior.
18. Confirm that the route exists in the current backend application and is included under the actual router prefix. Do not infer endpoint existence from a frontend URL string.
19. Inspect backend validation, authorization, ownership checks, service calls, transaction boundaries, queue/task dispatch, and error mapping for the operation.
20. Identify the authoritative persisted record or external response that proves success. Do not use only a toast, button animation, or HTTP 200 as proof of the intended side effect.
21. Check that the frontend consumes the real response and maps returned identifiers/state correctly. Detect hard-coded status strings and mismatched field names.
22. Test the normal successful action using an isolated fixture or safe test record wherever available.
23. Test missing, malformed, stale, or unauthorized identifiers without modifying real user data.
24. Test the expected validation boundary conditions and verify the UI shows a useful message rather than silently dropping the request.
25. Test a server-side failure and confirm no false success indicator appears.
26. Test a network timeout/connection reset and verify the UI does not assume that the backend definitely failed if the outcome may be ambiguous.
27. Test loading indicators and confirm they clear on success, error, cancellation, component unmount, and every supported early return.
28. Test double-click, repeated Enter, quick toggle changes, duplicate network retries, and stale component state for unintended duplicate actions.
29. Check race handling if the action operates on mutable status, queue positions, decisions, settings, uploads, or publishing state.
30. Check that stale/out-of-order responses cannot overwrite a newer state. Use request cancellation, version checks, or existing conventions where needed and approved.
31. Check the response status is translated to the correct UI state, including pending/in-progress, completed, partial failure, failed, cancelled, and conflict states where applicable.
32. Check whether optimistic UI is used. If so, ensure rollback or reconciliation occurs when the backend rejects the change.
33. Check whether the changed state should survive page refresh/reopen; if yes, reload and compare the visible state to the backend-authoritative result.
34. Check whether the state is shared with other pages/components. Trigger the action and inspect every relevant surface for stale data.
35. Check that filters, sorting, selection, pagination, tabs, and the current detail item behave correctly after the operation changes data.
36. Check behavior when the list is empty, the API returns null/partial optional data, a media asset is missing, or a provider is temporarily unavailable.
37. Check timezones, timestamps, duration units, percentages, byte sizes, numeric formatting, and enum labels against backend semantics.
38. Check no credential, OAuth token, API key, signed URL, or private user payload is exposed in visible UI, ordinary logs, test output, or screenshots.
39. Check that test-mode fallbacks or synthetic fixtures can only be activated by the repository-defined trusted test context, never by user-controlled substring or arbitrary request fields.
40. Check the action does not add, restore, expose, or invoke caption/subtitle features. Internal transcription may remain for approved analysis and metadata purposes.
41. Check the action does not route to Ollama or require Ollama environment variables. Preserve approved cloud-hosted models even if their names contain Llama.
42. Check the operation cannot accidentally publish to a source/monitoring channel instead of an explicitly configured destination.
43. Where an action creates a job/task, verify the persisted job ID is retained and Celery dispatch occurs only at the intended transition.
44. Where an action updates a task, verify the backend state transition is valid, durable, and visible on subsequent reads.
45. Where an action creates or deletes a file, verify storage path containment, ownership, retention policy, and cleanup behavior using isolated files only.
46. Where a control selects a layout, verify the selected ID maps to a supported renderer option rather than only changing the visual highlight.
47. Where a control shows a layout thumbnail, verify the reference asset exists in the production build, has the correct accessible text, and truthfully represents output composition.
48. Where the component displays progress, verify it is sourced from authoritative progress/status fields and cannot display completion before the task completes.
49. Where the component refreshes/polls, verify intervals, overlap, cooldown, backoff, and unmount cleanup against the actual code contract.
50. Where external providers are involved, test mocked/sandbox cases first and ensure no accidental external side effect is triggered by an ordinary test.
51. For the private YouTube acceptance upload, do not use this component test to generate another upload. The one real upload is centrally orchestrated and idempotently gated under the master framework.
52. Inspect the relevant unit/component test and add a regression test for each repaired defect where test infrastructure permits.
53. Run the smallest test covering this component first and record the exact command and actual exit result.
54. Run the relevant API/backend integration test where it can be proven safe and isolated.
55. Run the relevant browser/E2E test if available; do not describe static source inspection as a browser test.
56. Collect actual request/response evidence with secrets redacted. Link to the logs or test output that substantiate the result.
57. Compare the user-visible message/status with the actual backend response and persisted state.
58. Conduct Pass A by tracing requirements to implementation and successful tests.
59. Conduct Pass B independently using an alternate path such as persisted state, route registration, event log, task state, rendered output, refresh behavior, or a different test assertion.
60. If Pass A and Pass B disagree, investigate and document the discrepancy; do not average the results or silently pick the favorable one.
61. Classify a failure as UI defect, API contract mismatch, backend behavior defect, persistence defect, concurrency defect, configuration defect, missing test/evidence, or scope ambiguity.
62. Fix only defects within approved Phase 1–7 requirements and only through the governance process required by the freeze rules.
63. Before changing a shared API client, component, schema, backend route, or frozen domain, identify all affected pages and regression tests.
64. Keep the code change minimal and preserve pre-existing Git modifications and untracked files.
65. Never execute blanket Git reset/clean/checkout/restore commands or replace a whole file to make a small repair.
66. After a repair, rerun the failing reproduction, relevant component test, API/backend tests, and affected page regression checks.
67. Independently repeat Pass B after the repair, using evidence distinct from the original fix path where reasonably possible.
68. If the test fails, continue the diagnose/fix/retest loop within scope; if the failure requires unavailable authorization or unsafe operation, mark it blocked and continue unrelated work.
69. Do not stop at the first failed test if the cause is repairable within scope. Do not loop indefinitely if a genuine external or governance blocker exists.
70. Check that test teardown completes and does not silently mask failures; do not change global fixtures unless required and governed.
71. Confirm test DB isolation before any database mutation. Never migrate, drop, reset, or clean the operational clipforge database.
72. Confirm no test publishes an actual video except the one centralized, explicit, private acceptance upload authorized by the user.
73. Confirm no generated test file overwrites existing uploads or outputs and no cleanup task deletes user-owned media.
74. Run TypeScript and lint checks against the changed frontend where possible. Report repository-wide legacy issues separately from new introduced issues.
75. Run the production build after page/component changes and distinguish build output count from the number of user-facing pages.
76. Inspect browser console errors, failed network requests, React warnings, hydration issues, and unhandled promise rejections where browser execution is available.
77. Check responsive layout at narrow and wide viewport sizes, avoiding horizontal overflow, clipped dialogs, invisible controls, and inaccessible hover-only actions.
78. Check error messages are actionable, avoid secrets, and preserve user-entered form data where retry is expected.
79. Check the component handles loading, empty, success, partial-success, validation, unauthorized, not-found, conflict, rate-limit, server-error, and offline states as applicable.
80. Check that stale UI cache does not outlive a mutation. Invalidate/refetch only the relevant query/state according to the existing architecture.
81. Check a successful response has not been mistaken for semantic success when the backend returns a task ID with pending execution.
82. Check task completion is awaited or polled appropriately and the user can identify pending versus completed processing.
83. Check external provider errors propagate to a truthful status rather than being caught and converted into fabricated success.
84. Check any retry operation cannot create duplicate jobs, settings writes, uploads, publications, or cleanup operations.
85. Check the component has no hidden coupling to unapproved Phase 8 watermark branding or unsupported layouts.
86. Cross-reference actual behavior with `PHASE_TRACKER.md`, the relevant approved prompt, and the actual backend route/service. Do not assume draft/archived prompts are mandatory scope.
87. Check related documentation only if it is directly affected by the verified implementation; preserve historical audit evidence.
88. Update the component dossier with actual file paths, symbols, endpoint, backend behavior, test commands, Pass A evidence and Pass B evidence.
89. If a required operation is not present in the current UI, mark it absent and verify whether the approved specification requires it; do not silently invent UI.
90. If a required capability is absent, identify the exact implementation/API/test gap and fix it only when inside approved scope and governance permits.
91. Before any edit, record targeted Git status/diff; after edits, verify unrelated working-tree changes and untracked assets remain untouched.
92. Do not make changes beyond approved Phase 1–7 scope; Phase 8 watermark branding remains deferred unless separately authorized.
93. If this component offers a layout choice, require a real local reference thumbnail for every supported option and verify the output renderer matches it.
94. If this component participates in monitoring/publishing, check destination identity and state synchronization, and obey the central private-upload gate; do not create a second real upload.
95. Never expose secrets, run destructive database operations, publish public/unlisted test videos, or delete user media while verifying this component.
96. Perform Pass A: independently map every acceptance criterion to implementation and test evidence. Record exact paths, symbols, commands and actual results.
97. Perform Pass B independently using alternate evidence; explicitly confirm, contradict or leave uncertain every material Pass A claim.
98. Repair eligible defects and repeat the complete relevant test loop; if governance or safety blocks a fix, record the exact blocker and continue independent work.
99. Final acceptance for `STU-06`: every mandatory control in Upload-to-publishing handoff where implemented must have a real handler/contract, verified backend result, correct UI synchronization, passing relevant test, and independent Pass A/Pass B evidence.
100. Return a concise per-control matrix, exact files changed, tests and results, unresolved issues, and final component verdict. Do not declare PASS when evidence is missing.


---


## Final whole-frontend reconciliation prompt

After all page prompts finish, execute this final instruction as part of the same autonomous run:

1. Compare the discovered component inventory with every prompt section above; add any missing actual controls to the audit register and execute their full component verification process.
2. Produce one endpoint coverage matrix: frontend method → HTTP method/path → backend route/function → service/task/provider → persisted side effect → UI reconciliation → test evidence.
3. Detect backend routes with no UI caller and UI controls with no valid backend route. Classify whether each is intentionally API-only, historical, orphaned, or an approved mandatory gap.
4. Produce a layout matrix listing every supported layout, its exact ID, local reference image, frontend control, API/schema mapping, backend renderer, output artifact, visual comparison result and test.
5. Produce a monitoring/publishing correlation for the single approved private acceptance upload: source channel, discovered video/candidate, job ID, processed artifact, configured destination ID, external YouTube video ID, privacy verification, persisted status and UI-visible result. Redact secrets and private tokens.
6. Confirm the real private upload happened exactly once; if preconditions were not met, identify the specific blocker and state that no live upload occurred. Never convert a blocked attempt into a claimed success.
7. Reconcile TypeScript, lint, build and backend test results from actual command output. Keep unique test counts distinct from repeated executions.
8. Inspect the final Git status and targeted diffs. Confirm no unrelated modifications or untracked files were removed or overwritten.
9. Confirm approved scope and freeze governance. Record any required but unapproved frozen-domain change as blocked; do not silently bypass governing approval requirements.
10. Mark each component `PASS`, `PASS WITH LIMITATIONS`, `FAIL`, `NOT VERIFIED`, `NOT PRESENT/NOT REQUIRED`, or `BLOCKED` with evidence.
11. Mark the whole frontend `COMPLETE` only if every approved mandatory control has both Pass A and Pass B evidence, every mandatory endpoint and side-effect chain is correct, layout reference images match actual rendering, the private upload test is verified or explicitly recorded as blocked under an approved exception, and no mandatory defect remains open.
12. Deliver the final report and stop. No unsupported claim of perfection or 100% coverage is permitted.
