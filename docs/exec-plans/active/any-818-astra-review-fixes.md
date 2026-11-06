# ANY-818: eight independent review fixes

## Status

- State: active
- Owner: agent
- Created: 2026-11-06
- Last updated: 2026-11-07
- Review date: 2026-11-06
- Next action: parent review, commit and push, then fresh independent Astra review and CI.
- Blocker: none.

Scope: address [PR #259](https://github.com/gushinets/anytoolai-platform/pull/259)
Astra review findings 1–8 without changing product runtime,
working acceptance data, or the unrelated experiment files.

Follow-up scope: prevent framing of the Atom Lab HTML shell, remove the independent
saved-prompt character ceiling in favor of configured UTF-8 bytes, preserve known
successful trial evidence through unchanged preset saves and retired-model history
restores, clarify the local-only no-code launch contract, and share the identical
atom-not-found OpenAPI response across its three operations. Existing trust checks,
new-run model admission, production ingress and the 404 error envelope remain intact.

Follow-up validation: focused API and Chromium regressions, canonical OpenAPI/client
generation, docs generation checks, and frontend-check. Use only isolated test fixtures
and mocked browser transport; no working DB, migrations, deployment or paid calls.

## Plan

1. Reproduce and fix local no-code Host/Origin authorization, saved prompt UTF-8
   limit, and prompt-route 404 documentation with API regression tests.
2. Fix prompt-source loading/reset, restored successful trial provenance, explicit
   preset provenance restoration, background error navigation, and preset prompt
   labels with focused browser regressions.
3. Regenerate canonical OpenAPI/client artifacts and run focused plus repository
   checks. Leave changes uncommitted for parent review and PR update.

## Validation and risks

- Doctor passed before edits (2026-11-06).
- API storage tests use isolated test fixtures; browser tests use mocked transport.
- No paid provider calls, deployment, migration, or working acceptance DB access.
- Regression reproduction, implementation, generated artifacts and local checks are complete.
  Commit, push, independent review and required CI are owned by the parent agent.

## Repairs

All eight findings were reproduced before production edits:

1. No-code access now checks loopback Host and same Origin on every protected route;
   code-protected remote access is unchanged. Local origin-free CLI reads still work.
2. Saved prompts load the same environment-backed settings as run admission and reject
   oversized UTF-8 text with the existing `422 prompt_invalid` field envelope.
3. Reset is disabled and its handler guarded until a historical prompt source resolves.
   Failed loads preserve that guard; missing sources detach before platform reset is allowed.
4. Restoring a compatible successful history snapshot initializes trial evidence from that
   exact snapshot. Existing text/source/model/reasoning/input comparisons invalidate it.
5. Explicit preset reopen compares `source_run_id` too, confirms discard, and restores the
   immutable version's provenance without leaving an immediately dirty preset.
6. Delayed prompt admission errors reveal the editor only while its owner draft and laboratory
   are current; the explicit field-error link continues to navigate.
7. Preset prompt metadata displays `prompt_source_ref` with `prompt_ref` as fallback.
8. Both prompt endpoints document `404 AtomLabErrorResponse`; canonical OpenAPI and CE-kit
   generated types were regenerated.

Focused verification: 213 DB-free API tests and 16 Chromium journeys passed. The latter include
delayed source reads, unavailable/missing/stale sources, successful versus failed/adapted history,
and cancellation/reopen with changed provenance. Connected catalog/history/presets/access API
validation passed 240 tests (overlaps the access cases in the first run). Focused Atom Lab
architecture validation passed 9 tests. Canonical `frontend-check` passed lint, typecheck, all
frontend tests (including 118 Chromium journeys), generated type drift, and production builds.
`validate-docs`, `generate-docs --check`, and `git diff --check` passed.

The full backend/production PostgreSQL and deployment gates remain for CI. They were not repeated:
this fix adds no schema, concurrency, or execution-runtime changes, and the parent already recorded
unrelated ignored-snapshot architecture scans and a Windows Temp ACL full-check limitation.

Regeneration commands (the managed environment owns the backend dependencies):

```powershell
./.quick-check-venv/Scripts/python.exe scripts/agent/runner.py generate-docs
pnpm --filter @anytoolai/ce-kit generate-api-types
```

Windows sandbox tests stalled at SQLite fixtures; the same isolated tests passed outside the
sandbox using `runner.baseline_env()`. Chromium used the installed cache at
`C:/Users/gushinets/AppData/Local/ms-playwright`. The system Python lacks `markdown_it`, so
documentation generation uses the existing managed environment. No dependency was added.
The pnpm update notice request timed out during install; the frozen install and every subsequent
frontend-check step still completed successfully. Test imports used the bundled LiteLLM cost map
(`LITELLM_LOCAL_MODEL_COST_MAP=True`) without any provider call.

## Follow-up review repairs

The independent follow-up found five related defects; all are repaired:

1. The HTML response now sends `Content-Security-Policy: frame-ancestors 'none'`
   alongside its existing no-store policy in both access modes. API regressions
   verify the real headers; Chromium's mocked HTTP contract blocks same-origin and
   cross-origin framing while top-level no-code loading still works.
2. Saved-prompt requests rely on the existing configured UTF-8 byte validator rather
   than a separate 65,536-character ceiling. Boundary tests cover a lower limit,
   65,537-byte ASCII, a raised 70,000-byte limit, and one-byte-over UTF-8/ASCII rejection.
3. Reapplying a configuration preserves only an already known successful trial whose
   snapshot exactly matches the resulting draft. Tests cover successful and failed
   preset readback, later setting changes, and an unknown preset source-run ID.
4. Snapshot comparison reads the retained model selector value even when that model
   has left the catalog. Compatible successful history keeps its trial; admission
   still requires an available model. Failed/adapted history remains unproven.
5. The deployment runbook now limits no-code access to a separately launched API or
   custom local stand and explains that standard Compose and `atom-lab-*` keep code protection.

The canonical exporter shares `components.responses.AtomLabAtomNotFound` across atom
detail and both prompt operations. A regression resolves the three references and
compares the complete schema with live FastAPI, preserving every other response and
the exact error envelope; Markdown retains both prompt 404 entries. Regeneration
removed 14 lines from the generated TypeScript without exclusions, suppressions or
hand-editing generated files. Sonar's final quality-gate decision remains for CI.

Follow-up verification passed: 397 connected API/docs/Atom Lab architecture tests;
canonical `frontend-check` (including all 122 Chromium journeys, lint, typecheck,
Node/Vitest tests, generated type drift and production builds); `validate-docs`;
`generate-docs --check`; and `git diff --check`. A Ruff comparison against HEAD for
all six changed Python files found no new diagnostics and two fewer existing ones.
The focused follow-up regressions failed before fixes at the expected CSP, raised
ASCII-byte limit, preset readback and retired-model boundaries.

The first frontend-check attempt hit the sandbox's pnpm-store symlink permission;
the same canonical command passed with escalation. SQLite tests used the existing
managed interpreter and `runner.baseline_env()` outside the sandbox, with the bundled
LiteLLM cost map. No working DB, provider, deployment, migration, commit or push was used.

## Final review follow-up: prompt admission and delayed trial completion

Doctor passed before edits on 2026-11-07. Reproduce and repair two remaining findings:

1. Authenticate saved-prompt creation before consuming any request bytes, then bound
   the request stream with the existing configured run body budget before JSON parsing.
   Preserve configured UTF-8 prompt limits, access modes, error envelopes and OpenAPI.
2. Carry an actual successful trial to the active editor after an equivalent preset
   readback replaces its session. Require an exact immutable snapshot match; changed
   drafts and unrelated late operations must retain their current state.

Reach: Atom Lab router admission helpers and prompt operation, API stream regressions,
editor configuration/completion handling, preset creation/version Chromium regressions,
and generated contracts only if the API schema changes. No new dependencies or settings.

Validation: prove focused regressions fail first, then run connected API/docs/architecture
checks, canonical frontend-check, generation drift and diff checks. Use isolated SQLite
fixtures and mocked browser transport only; no acceptance DB, provider calls, commit or push.

Both findings are repaired and verified. The unauthorized 1 MiB stream regression
first consumed all chunks before returning 401; it now reads zero bytes in protected
and untrusted no-code access modes. Prompt creation and run admission share the same
bounded stream reader. Prompt JSON validation retains the `request_validation_failed`
envelope, and the configured UTF-8 prompt validator still owns prompt byte limits.
Authorized tests cover chunked, actual and falsely short Content-Length, exact/over
body boundaries, code access, local same-origin access and origin-free local CLI access.

Delayed successful completion now copies actual trial evidence to the active session
only when its immutable request snapshot matches exactly. Chromium covers completion
before and after preset readback, both new presets and new versions, failed output
validation, changed text/source/input/model/reasoning and navigation to another atom.
All cases use one mocked run submission; no provider rerun or unknown source-run
inference is involved.

The wire request fields and constraints are unchanged. FastAPI now represents the
manually bounded prompt request schema inline, as it already does for run admission;
the only semantic OpenAPI addition is the documented 413 error envelope. A regression
checks the complete request schema and 413 response. Canonical OpenAPI, Markdown and
CE-kit types were regenerated without hand edits or exporter special cases.

Final verification (2026-11-07):

- Connected API/catalog/history/presets/access, docs generation and Atom Lab architecture:
  434 passed in 216.16 seconds; the subsequently added exact OpenAPI contract check also passed.
- Canonical `frontend-check`: passed lint, typecheck, 131 Chromium journeys, all
  Node/Vitest suites, API-type drift and production builds.
- `validate-docs`, `generate-docs --check`, and `git diff --check`: passed.
- Ruff comparison for the three changed Python files: seven existing diagnostics,
  no new diagnostics versus HEAD.

The sandbox again stalled isolated API setup and denied documentation Temp writes;
the same checks passed with escalation. The managed Python environment used
`runner.baseline_env()` and the bundled LiteLLM model cost map; Chromium used the
installed browser cache. Production PostgreSQL, full backend CI, clean independent
review, commit and push remain with the parent. No acceptance data, dependency,
Sonar rule/threshold/exclusion, deployment, migration or paid provider was changed.

## Remaining review follow-up: reversible drafts and preset cancellation

Doctor passed before edits on 2026-11-07. Reproduce the remaining delayed-trial
finding and the new-preset cancellation finding before changing production code.

1. Keep the existing single successful-trial record independent of editor-session
   replacement, recording only confirmed run/history success. Preserve exact snapshot checks
   across preset creation/version readback, edits and reverts, history/new drafts,
   failed runs and subsequent operations; never infer success from a source-run ID.
   Require the same loaded catalog atom and clear evidence on explicit adaptation
   across incompatible action, prompt or schema contracts.
2. Keep an editor's real preset binding while preparing a new preset. Cancellation
   must leave its input, prompt, source-run provenance and dirty state intact;
   only a committed new preset may replace its binding.

Reach: the shared Atom Lab editor lifecycle, focused browser/Node regressions,
and this plan. Validate with mocked browser transport, canonical frontend-check,
connected API/docs/architecture checks and generation/diff checks. No live DB,
provider calls, dependencies, commit, push, migrations or deployment.

Both regressions failed before production edits: returning from Y to X after
delayed completion lost the successful trial for both creation and version
readback; clean and dirty editor launches after cancellation sent `preset_ref: null`.

The existing single successful-trial record now outlives editor-session recreation.
Only a validated successful accepted run or compatible successful history restore
sets it. Status and prompt saves still require exact text, source, atom, input,
model and reasoning matches. Catalog object identity prevents reuse after a fresh
unlock/catalog load; explicit adaptation clears evidence for incompatible schema,
action configuration or prompt contracts. Failed runs do not erase actual success.
No history cache, source-run inference or output/run reassignment was added.

Preparing a new preset now changes only preset metadata. The working editor keeps
its binding until a committed save reapplies the new immutable version. Clean/dirty
cancellation tests compare the complete run payload, assert zero preset writes,
verify the original fixed fields/provenance, and verify normal new-preset rebinding.

Verification (2026-11-07):

- Thirteen focused delayed-completion/cancellation Chromium journeys passed;
  compatible/failed/retired/adapted history and new-catalog guards also passed.
- Canonical `python scripts/agent/runner.py frontend-check` passed lint, typecheck,
  all Node/Vitest suites, 139 Chromium journeys, API-type drift and production builds.
- Connected catalog/history/presets/access API, docs generation/validation and Atom
  Lab boundary tests passed: 289 tests, with existing managed dependencies and
  `runner.baseline_env()` (the exact collection count was checked without rerunning tests).
- `validate-docs`, `generate-docs --check`, and `git diff --check` passed.

The first canonical frontend run hit the sandbox pnpm-store symlink permission;
the identical escalated command passed. Isolated SQLite tests and documentation
Temp checks used the previously established escalation. Chromium used the existing
browser cache; LiteLLM used the bundled cost map. No API/generated artifact,
dependency, Sonar rule/threshold/exclusion, working DB or paid provider changed.
All changes remain uncommitted for parent review, PR update and independent CI/review.
Full backend, production PostgreSQL and deployment gates were not repeated for this
JavaScript-only behavior fix.

## Confirmed prompt-save catalog synchronization

Doctor passed before edits on 2026-11-07. Repair the confirmed successful-write
finding from [PR discussion](https://github.com/gushinets/anytoolai-platform/pull/259#discussion_r4495906101).
An A06 prompt save may complete after A06 -> A05 -> A06 navigation, leaving the
replacement editor's already loaded library unaware of the confirmed saved record.

Reach: shared prompt-save success handling and prompt-option request fencing,
focused Chromium regressions, and this plan. Materialize confirmed saved options
only for the identical loaded catalog atom; fence any pre-write GET so it cannot
replace that library. Preserve active text/source and replacement-editor state,
including same-session edits during POST. Keep unchanged-owner direct-save UX.

Validation: first reproduce both GET/POST orderings, then verify edits/source,
another atom, new unlock/catalog, normal saving, and existing malformed/failed-write
behavior with mocked transport. Run canonical frontend-check and docs/diff checks.
No backend/API change, working DB, provider call, dependency, commit or push is needed.
Ambiguous-write retry and the unbounded library remain separate follow-ups.

The new regressions first reproduced both list/save orderings and loss of the
replacement editor's saved option (four failures); two additional cases reproduced
the edited owner's form being closed and cleared. The ordinary unchanged owner,
another atom and a newly loaded catalog already passed. A further failing regression
proved that cancelling the unlock's atom switch retains the old editor while the
catalog has changed, so the success guard checks actual current catalog membership.

Confirmed saves now materialize one deduplicated option into the current library
only for that same catalog atom. A pending pre-write GET is superseded through the
existing loader; request identity fences its success, failure and cleanup. The
replacement editor keeps its current source/text. An edited owner also keeps its
open form/name/focus; an unchanged owner keeps automatic saved-prompt selection,
form close and focus. Failed, malformed and indeterminate writes retain their
previous safe reconciliation path, without inventing a confirmed option.

Two more regressions reproduced an inert Retry after materialization: a forced
post-save refresh failed with 503, or the replacement GET had already failed before
201. The shared Retry handler now explicitly refreshes despite a populated list.
Both cases retain the confirmed option through the error, issue a new GET on Retry,
and return to a usable loaded library after 200.

Verification (2026-11-07):

- Focused Chromium: 15 passed, covering both GET/POST orderings, edited current
  text/source in both owner and replacement editors, another atom, new catalog
  with accepted/cancelled atom switch, unchanged-owner UX, three failed write
  outcomes and both failed-read/retry orderings.
- Canonical `python scripts/agent/runner.py frontend-check`: passed lint,
  typecheck, 154 Chromium journeys, 53 Atom Lab Node tests, six demo Node tests,
  824 Vitest tests, API-type drift and all production builds.
- `validate-docs`, `generate-docs --check`, and `git diff --check`: passed.

The sandbox denied the pnpm-store symlink and generator Temp writes; the identical
commands passed with escalation. Chromium used the existing browser cache and the
successful docs check used the bundled LiteLLM cost map. No generated API artifact,
backend/API code, dependency, Sonar setting, working DB, migration or provider call
changed. Full backend/production PostgreSQL/deployment checks were not repeated for
this JavaScript-only fix. Changes remain uncommitted for parent review and PR/CI.

## Confirmed final review: prompt storage and save-form ownership

Doctor passed before edits on 2026-11-07. Reproduce and repair the three confirmed
findings from PR #259's latest independent review:

1. Contain prompt-creation database failures around the complete transaction,
   return the existing safe 503 envelope, and log only the exception type. Preserve
   input validation, rollback and uncertain-commit behavior without retrying writes.
2. Render Save availability whenever prompt options materialize, including a
   replacement editor whose Prompt tab has never loaded. Preserve unresolved-source
   and in-flight-save guards, list request fencing and the existing forced Retry.
3. Include the actual editable name in successful-save ownership checks so a delayed
   201 preserves a newer name, source, text, open form and focus.

Reach: the prompt-creation router boundary, shared editor rendering/completion,
focused API/Chromium regressions, and this plan. No wire/schema changes are planned.
Prove the regressions before production edits, then run relevant API/architecture,
canonical frontend, docs generation/drift and diff checks. Use isolated SQLite and
mocked browser transport; no working DB, migrations, provider calls, commit or push.

All three regressions were reproduced before production edits. The isolated API
tests escaped DBAPI errors before the insert, during insertion, at commit and after
commit; real Uvicorn with access logging disabled exposed the refused SQLite INSERT's
prompt parameter. Chromium reproduced permanent Save disablement and automatic
source switching after both a changed name and a whitespace-only name edit.

Prompt creation now catches expected database failures around the complete existing
transaction. It logs only the fixed event/code and exception type, returning the
existing 503 envelope without chaining the database exception. NUL input remains
an explicit 422. A simulated failure after commit keeps its one persisted row and
never retries the write; the client continues to classify this 503 as an uncertain
outcome and preserves the draft for its existing read reconciliation.

Shared prompt-status rendering owns Save availability from known options, current
save state and unresolved source validation. Confirmed option materialization uses
that same path even before the replacement editor's first Prompt-tab visit. Exact
raw form-name comparison keeps an edited owner's name, prompt/source, open form and
focus; unchanged-owner automatic selection and closing remain intact. Browser
regressions include current/replacement editors, both GET/POST and two-POST response
orders, unresolved historical sources, failed reads with forced Retry, scope fences,
and rejected/malformed/uncertain writes. No API schema or generated artifact changed.

Verification (2026-11-07):

- Connected run/catalog/history/preset/access API, real Uvicorn access logging,
  docs generation/validation and Atom Lab architecture: 457 passed in 235.39 seconds.
- Canonical `python scripts/agent/runner.py frontend-check`: passed lint, typecheck,
  161 Chromium journeys, 53 Atom Lab Node tests, six demo Node tests, 824 Vitest
  tests, generated API-type drift and production builds. The additional 503 case
  was added after discovery started; the final focused Chromium suite passed all
  23 cases, including that case, and final Atom Lab lint also passed.
- `validate-docs`, `generate-docs --check` and `git diff --check`: passed.
- Ruff against HEAD: no new diagnostics; the router has four existing diagnostics
  versus six before, and the API test file has none.

The sandbox stalled isolated SQLite setup and denied pnpm-store symlink creation;
the identical checks passed with escalation. Tests used the managed interpreter,
`runner.baseline_env()`, bundled LiteLLM cost map and installed Chromium cache.
Only five intended files changed; staging is empty and unrelated untracked reports
are preserved. Full backend/production PostgreSQL, required CI and the next fresh
independent review remain with the parent. No dependencies, Sonar rules/thresholds,
API schemas, generated files, working DB, migration, deployment or provider call changed.

## Final P3: attribution of retained accepted-run data

Doctor passed before edits on 2026-11-07. Reproduce PR #259 discussion
`discussion_r4496503470`: an invalid accepted run A retains raw output and provider-call
metadata after an identical request B is rejected for quota, without a visible source
marker because the successful-result section is hidden.

Reach: the shared run-status attribution in `atom_lab.mjs`, Chromium regressions and
this plan. Use the existing displayed/active submission identities so all retained
accepted-run data has a visible run ID, including invalid output and metadata-only
failures. Keep accepted configuration, source, full JSON, IDs and diagnostics intact;
preserve the separate semantic draft warning. A new accepted run replaces the source.

First prove the regression with mocked Chromium transport, then make the smallest
shared fix and cover successful, invalid and diagnostic-only runs across quota,
validation and network outcomes. Run focused Chromium, canonical `frontend-check`,
documentation generation/validation and diff checks. No backend changes, working DB,
migration, provider calls, dependencies, Sonar changes, staging, commit or push.

The exact Chromium regression failed before production edits: invalid A's raw text,
metadata and IDs were retained after identical B's quota rejection, while the visible
help contained only the rejection guidance. Shared status help now always names the
displayed accepted run and marks it as previous when its submission differs from the
active submission. It no longer depends on success tone or result-section visibility.
The separate draft warning still follows semantic configuration changes.

A real-format long run ID also reproduced horizontal overflow (1454px at a 1280px
viewport). The existing help rule now wraps long tokens. Chromium verifies the narrow
desktop response column and a 320px viewport without page or help overflow. An ignored
320px screenshot is saved at `.quick-check-tmp/atom-lab-invalid-quota-320.png`.

Verification (2026-11-07):

- Final focused Chromium: 14 passed, including nine success/invalid/metadata-only ×
  quota/validation/network cases. They check identical requests, visible source text,
  raw/result/metadata visibility and retention, unchanged full JSON/config/IDs/source,
  draft edits/reverts and a newly accepted run's replacement identity.
- Canonical `python scripts/agent/runner.py frontend-check`: passed lint, typecheck,
  171 Chromium journeys, 53 Atom Lab Node tests, six demo Node tests, 824 Vitest tests,
  generated API-type drift and production builds. The final focused run also covers
  the explicit panel-visibility assertions added after full-suite discovery.
- `validate-docs`, `generate-docs --check`, and `git diff --check`: passed.

The identical frontend command passed with escalation after the sandbox denied the
pnpm-store symlink. Documentation generation passed with its temporary directory
inside the ignored workspace directory and the bundled LiteLLM cost map. Four intended
files changed, staging is empty and unrelated untracked reports remain untouched.
No backend/API, schema, generated artifact, dependency, Sonar setting, working DB,
migration, provider call, deployment, commit or push changed. Full backend/PostgreSQL,
required CI and a fresh independent review remain with the parent.

## Final P2: interactive HTML framing and refreshed history details

Doctor passed before edits on 2026-11-07. Repair the two confirmed findings from
review `5805900263`, discussions `4496748281` and `4496748298`:

1. Protect interactive API HTML entry points, including Swagger, ReDoc and its
   OAuth redirect, against framing. Use the existing response middleware; preserve
   other CSP directives, response headers, top-level docs and all Lab authorization.
   Inspect the demo shell and documented browser journeys before choosing scope.
2. Reconcile the selected history detail with refreshed summaries. Changed status
   must invalidate the cached result before restore/save can use it, fetch actual
   detail, and fence delayed reads and failures. Preserve drafts, selection and
   successful-trial provenance; immutable terminal details may remain cached.

Reach: API response boundary and header tests, shared history loading/actions,
focused Chromium regressions, and this plan. Prove focused regressions before the
production fixes, then run connected API, canonical frontend and docs checks.
Use isolated SQLite/in-memory Uvicorn and mocked transport only; no working DB,
migration, provider call, new dependency, Sonar change, staging, commit or push.

The parallel CSS owner exclusively adds `overflow-wrap: anywhere` to the existing
`.invalid-response` rule. Its exact CI reproduction uses
`mcr.microsoft.com/playwright:v1.62.1-noble` plus Ubuntu `fonts-dejavu-core`: the
320px document was 332px, with an unbroken invalid-response identifier measuring
283px inside a 226px container. Keep the existing exact overflow assertion intact.

The new regressions first reproduced the missing HTML headers (nine failures;
the existing two Lab-shell cases already passed) and all four queued/running to
succeeded/failed stale cards. An additional failing regression showed that an
unsuccessful summary refresh also left the running snapshot actionable.

The existing API response middleware now appends an independent
`frame-ancestors 'none'` CSP policy to HTML responses. The Lab route retains its
no-store policy and gets framing protection from that shared boundary. Swagger,
ReDoc, OAuth redirect and demo headers are covered in both access modes. A test
retains a route's existing script/ancestor CSP, X-Frame-Options and cache headers;
non-HTML API responses are unchanged. No documented API iframe journey exists;
product result/consent navigation is owned by the separate web host. No Portal
identity, scope or producer/consumer contract changed.

History now retains selection separately from the cached detail, invalidates
nonterminal snapshots before refreshing the list, and fetches selected details
when summaries differ or a fresh nonterminal read is needed. Existing generation
fences reject delayed reads. Restore/save remain disabled while list/detail reads
are pending and after failed or malformed detail reads; invalidated data is hidden.
Reopening, older-page loading, selecting another run, failed reads and retry all
preserve the current draft. Stable terminal snapshots may reuse their detail.
Successful fresh history restores the exact trial and saves its source run without
issuing an execution POST; failed history does not invent successful evidence.

Real browser proof: `.quick-check-tmp/framing-probe.py` starts actual Uvicorn with
SQLite RAM (a fixture-only `clock_timestamp` shim), then
`.quick-check-tmp/framing-probe.mjs` drives installed Chromium against the real
FastAPI HTML/OpenAPI and official default Swagger UI 5 CDN assets. There is no
mock Swagger UI or mocked refresh endpoint. In both no-code and code-protected
modes, direct foreign-Origin POST returns 401 and same-origin/foreign-origin
iframes are blocked, leaving zero catalog-state rows. Top-level Swagger's
Try it out / Execute returns 202 and creates exactly one pending row. Code mode
also proves missing-code 401 before entering the header. Both servers and browser
are closed after each run; no worker or provider is launched. Logs:
`.quick-check-tmp/framing-probe-local.log` and `framing-probe-code.log`.

Verification (2026-11-07): 11 new API header cases passed; focused Chromium
20 passed, then all 11 final refresh cases passed including the added older-page
append case. Connected API/demo/docs/Atom Lab architecture passed 471 cases
(`.quick-check-tmp/p2-api-docs-architecture.log`). `validate-docs` and
`generate-docs --check` passed. Ruff comparison against HEAD found no new
diagnostics in any changed Python file (main 0/0, router 4/4, access tests 1/1).

The parallel CSS owner separately proved 3/3 exact Linux viewport cases and all
171 original Chromium cases on frozen `1ae5819` plus only the CSS fix. That
isolated snapshot does not include these new API/JavaScript/tests. Evidence:
`.quick-check-tmp/atomlab-viewport-linux/fixed-target.log`, `full-linux.log` and
`reproduction.md`. The final canonical
`python scripts/agent/runner.py frontend-check` passed lint, typecheck, all 182
Chromium journeys, 53 Atom Lab Node tests, six demo Node tests, 824 Vitest tests,
generated API-type drift and production builds. Log:
`.quick-check-tmp/p2-frontend-check-final.log`. No test tolerance, skip or retry
was added.

Isolated API tests used the managed interpreter and `runner.baseline_env()`;
Chromium used the installed browser cache and the bundled LiteLLM cost map. The
sandbox again stalled async setup; the isolated checks passed with escalation.
Documentation, final diff and staging checks passed; staging is empty and unrelated
untracked reports remain untouched. Six owned files changed, plus the parallel
owner's CSS. Full backend/production PostgreSQL, required CI and fresh independent
review remain with the parent. No schema/generated contract, dependency, Sonar
setting, working DB, migration, deployment, provider call, commit or push changed.

## Final P2: fresh history summaries and independent successful trials

Doctor passed before edits on 2026-11-07. Reproduce and repair review
`5806319558`, discussions `4497080777` and `4497080785`:

1. A run may finish between its list and detail reads. Reconcile the accepted
   detail's status/times into its row; compare a known terminal detail only with
   a genuinely fresh selected summary, preserving it when appending other rows.
   Keep nonterminal refresh, failure/action guards and request generations.
2. Keep explicitly restored successful draft evidence independent of the latest
   successful asynchronous submission. Match either exact configuration at use
   and save time, retaining catalog identity, adaptation and failed-run guards.

Reach: shared Atom Lab JavaScript, focused Chromium regressions and this plan.
Prove both failures before production edits, then run related history/trial
journeys, Node checks, canonical frontend-check, docs/drift and diff checks.
No new polling/cache framework, backend/CSS changes, working DB, migration,
provider call, dependency, staging, commit or push is needed.

The six new core cases first produced four expected failures: a Running row
beside a successful detail, an unrelated-page append that unnecessarily reread
the selected run and hid it after 503, and loss of one trial in each completion /
restore ordering. Fresh selected status and timestamp changes already refetched.
The accepted detail now reconciles only its existing row's status and times;
terminal-detail comparison reads only the freshly returned page. Nonterminal
invalidation and existing list/detail generations and action locks remain intact.

Successful evidence now has exactly two bounded owners: the explicitly restored
successful draft and the latest successful asynchronous submission. The existing
exact configuration match chooses the restored proof first, then the completed
submission. Failures preserve both; explicit incompatible adaptation clears both.
A further failing catalog-cancellation case proved that a new unlock may retain
the old dirty editor. Exact trial matching now also requires current catalog
membership, so neither old record can qualify through that retained editor.

Focused Chromium passed all 40 history/trial cases, including both completion
orders, B -> A -> B prompt-save provenance, later failure, editor replacement,
retired model values, incompatible/adapted/failed history, accepted and cancelled
catalog switches, status/time advance, unrelated pagination, delayed/out-of-order
reads, malformed/detail/list failures, retry and selection changes. The unchanged
run snapshot, result and draft warning remain attributed to the actual submission;
restoring or saving a prompt never starts an execution. Atom Lab lint and all 53
Node tests passed. Architecture validation passed.

Verification (2026-11-07):

- Canonical `python scripts/agent/runner.py frontend-check` passed using the
  managed interpreter: lint, typecheck, all 189 Chromium journeys, 53 Atom Lab
  Node tests, six demo Node tests, 824 Vitest tests, generated API-type drift and
  production builds. Log: `.quick-check-tmp/p2-history-trials-frontend.log`.
- `validate-architecture`, `validate-docs`, `generate-docs --check` and
  `git diff --check` passed. Staging is empty; HEAD remains `6e7dc986`.

The identical frontend command passed with escalation after the sandbox denied
the local pnpm-store symlink. Documentation generation used the existing managed
Python environment, workspace Temp directory and bundled LiteLLM cost map after
the system interpreter lacked `markdown_it`. Chromium used its installed cache.
Three owned files changed; unrelated untracked reports remain untouched. No
backend/CSS, schema/generated contract, dependency, Sonar setting, working DB,
migration, provider call, deployment, commit or push changed. Existing exact
viewport assertions remain intact. Full backend/production PostgreSQL checks were
not repeated for these JavaScript fixes; PR update, CI and independent review
remain with the parent. Ambiguous-save retry/idempotency and unbounded library
pagination remain the previously documented separate follow-ups.

## Source refresh and library presentation

Doctor passed before edits on 2026-11-07. Address review `5806688876`,
discussions `4497362859`, `4497362869` and `4497362876`:

1. Revalidate a still-selected source after confirmed `prompt_source_invalid` run
   rejection. Preserve manual prompt/input edits, detach missing references, expose
   read-error Retry, and fence changed sources, replacement editors and catalogs.
2. Wrap full user-supplied preset names/descriptions in the shared item list.
   API limits remain 256 name characters and 4096 description characters.
3. Reflect only a visible selected history detail in expansion ARIA and detail
   rows; preserve selection and allow the same date button to retry a failed read.

Reach: shared Atom Lab JavaScript/CSS, focused Chromium regressions and this plan.
First reproduce the three failures, then run focused/connected browser journeys,
canonical frontend-check, docs/generation and diff checks. Visually inspect narrow
screenshots. Use existing mocked fixtures only; no backend/API changes, live DB,
provider calls, migration, dependency, staging, commit, push or GitHub publication.

All three reported defects were reproduced before production edits: two source
recovery cases remained at one GET, allowed unbroken preset text stretched the
desktop document to 41235px, and detail 503 left `aria-expanded=true`. Logs:
`.quick-check-tmp/p3-regressions-before.log` and `p3-fencing-before.log`.

Confirmed source rejection now targets the existing source selector and refreshes
through the shared loader only for the same editor, selected reference and loaded
catalog atom. Pending/failed revalidation blocks launch, reset and saves; Retry
forces a new GET despite populated options. Fresh options detach retired refs
without replacing manual prompt/input text, retire the field error, and admit a
new submission with a new key. No successful trial is inferred. Delayed rejection
after source/editor/catalog change and delayed refresh after source/editor change
preserve the current draft. A further regression caught explicit platform selection
during refresh: reconciliation now compares its effective reference, rather than
mistaking the platform's null override for a missing source.

The shared list button wraps full names and descriptions without truncation or API
limit changes. Desktop 1440px and mobile 360px keep the exact document width with
256/4096-character values. History expansion requires the selected visible detail;
failed detail reads retain selection and explain retry through the date button.
The same render now handles nonterminal detail invalidation during list refresh:
an added assertion reproduced stale ARIA/empty expansion on list 503 too. Log:
`.quick-check-tmp/p3-history-list-before.log`.

Focused final Chromium verification passed 16 cases (nine new and seven connected
history refresh cases); the broader prompt/history/trial/admission set passed 96.
Logs: `.quick-check-tmp/p3-final-focused.log` and `p3-connected-chromium.log`.
Atom Lab lint and all 53 Node tests passed. Narrow screenshots were visually
inspected for long preset text, collapsed history failure and successful retry;
artifacts live under `.quick-check-tmp/p3-final-focused/`.

Final canonical `frontend-check` passed (2026-11-07): lint, typecheck, 198 Chromium
journeys, 53 Atom Lab Node tests, six demo Node tests, 824 Vitest tests, generated
API-type drift and production builds. Log: `.quick-check-tmp/p3-frontend-check-final.log`.
The full command was repeated after the last history invalidation change.
`validate-docs`, `generate-docs --check` and `git diff --check` passed; documentation
logs are `.quick-check-tmp/p3-validate-docs.log` and `p3-generate-docs-check.log`.

The pnpm-store symlink and generator Temp ACL required the established escalation;
the same commands then passed. Chromium used the installed cache; no dependency or
generated contract changed. Four owned files remain uncommitted, staging is empty
and HEAD is `3bc8025ce14c2aed23d1ccc1a28c8b2e23741d9b`. Unrelated untracked
reports remain untouched. Backend/production PostgreSQL checks were not repeated
for these UI fixes. Parent owns commit/push, fresh independent review and required
CI. Working DB, migrations, deployment, provider calls and GitHub writes were not
used. Ambiguous-save retry/idempotency and unbounded library pagination remain
the previously documented separate follow-ups.
