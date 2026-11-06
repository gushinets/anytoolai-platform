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
