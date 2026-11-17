# Execution Plan: ANY-616 Brief Decoder Structured Copy

## Status

- State: active
- Owner: agent
- Created: 2026-11-17
- Last updated: 2026-11-17
- Review date: 2026-11-17
- Next action: commit and push validated corrections to feature/ANY-616 as authorized; no GitHub comments.
- Blocker: baseline runner tests depend on local env-file presence and passwordless sudo; implementation checks pass.

## Goal

Copy currently serializes a model-written summary, which can distort facts or omit questions
that the structured view preserves. Build copy deterministically from the structured result.

## Scope

Update the Brief Decoder parser/composer, result view and CSS, all seven message catalogs,
renderer contract, Python contract test, frontend unit/language tests, browser smoke and
frontend architecture documentation. Preserve the four displayed sections and shared copy
control, including its manual-selection fallback.

## Out of scope

- Handoff preview: `handoffs.yaml` still uses `document.summary`.
- Summary prompt quality and live three-run QA acceptance belong to ANY-591.
- Separate Copy questions control belongs to ANY-850.
- Other products already copy structured results or their canonical message text.

## Relevant docs

- `docs/architecture/frontend-boundaries.md`
- `docs/agent/coding-conventions.md`
- `DESIGN.md`

## Contracts touched

No API, DB, workflow or event change. The product renderer's copy authority becomes
`brief.values`, `brief.missing_fields`, `issues`, `questions`; `document` and confidence are
excluded. Copy blocks are brief, optional missing fields, issues, numbered questions, separated
by one blank line. UI-locale labels name fields/categories/severity; content is verbatim.
Missing fields are derived from values in schema order. Supplied metadata must list exactly
those fields once each; absent legacy metadata is accepted, and malformed metadata is rejected. Empty issues/questions retain explicit empty-state text.

## Implementation steps

- [x] Update parsing, composition, rendering and locale messages.
- [x] Update config, documentation and regression coverage.
- [x] Run checks, inspect the diff and record limitations.

## Validation

- `python scripts/agent/runner.py doctor`
- `python scripts/agent/runner.py quick-check`
- `python scripts/agent/runner.py frontend-check`
- `python scripts/agent/runner.py validate-docs`
- `python scripts/agent/runner.py generate-docs --check`
- `python scripts/agent/runner.py full-check`
- `python scripts/agent/runner.py brief-decoder-smoke`
- `python scripts/agent/runner.py acceptance-builder-smoke` if it covers this handoff

## Decision log

| Date | Decision | Why |
|---|---|---|
| 2026-11-17 | Keep the existing TypeScript UI and Python contract tests | Clipboard formatting is product-owned frontend behavior; no Python service is needed. |
| 2026-11-17 | Reuse ResultView hideText and existing visual tokens | Preserve clipboard error recovery without duplicating the structured result on screen. |

## Progress log

| Date | Progress | Next |
|---|---|---|
| 2026-11-17 | Confirmed document-based copy defect and all callers. System-Python doctor lacks pytest/pydantic; inspect managed environment. | Implement and validate. |

## Open questions

None for implementation. Parent-task confirmation and live QA remain prerequisites for closing
ANY-591/ANY-616 in Linear; this change does not close tickets.

### Validation progress

- Managed Python 3.12 doctor passed; system Python 3.14 lacks test dependencies.
- Brief Decoder Python product tests passed. All 39 focused UI tests passed; the complete
  web-mirror suite passed (1,124 tests), including locale and shared-UI checks.
- Workspace lint and typecheck passed after aligning the test translator with the host's
  Translate signature. The first broader frontend test run timed out in an unchanged CE-kit
  ESLint-rule test; its isolated rerun passed.
- Documentation validation passed; quick-check's generated-document drift check passed.
- Initial browser attempt failed because the derived API port was unused. A subsequent dev-up
  mistakenly recreated the existing custom-port live stack under the same Compose identity;
  migration failed on authentication. Restored its saved profile and credentials, verified API
  health on port 8015 and PostgreSQL on port 5455, without resetting the database. Browser
  preparation now uses an explicitly separate anytoolai-any616-smoke project and database volume.

- Brief Decoder browser smoke passed all 8 tests; Acceptance Builder smoke passed all 11,
  including accepted and declined Brief Decoder handoffs. Inspected desktop (1280px) and
  mobile (390px) screenshots: all four sections and the shared action row remain readable.
- Freelancer Suite Python tests: 1,000 passed initially; the packaging test needed uv cache
  access and passed on its permitted rerun (1,001 tests covered overall).
- Baseline failures reproduced in unchanged runner tests:
  `test_prod_stack_running_reflects_compose_ps_output` and
  `test_prod_stack_running_propagates_timeout` assume no local production env file; the present
  file triggers env resolution that their subprocess mocks do not support.
  `test_activation_marker_is_readable_by_non_root_api_user` requires passwordless sudo as nobody,
  unavailable here. No tests or local credentials were weakened to bypass these failures.
- Repository text scan found existing forbidden local-command references in unrelated ANY-17,
  ANY-339, ANY-391, ANY-221 and ANY-227 plans; none occur in this ticket's changed files.

- The standalone quick-check was interrupted after 3,248 passes and the three known runner
  failures to avoid duplicating the baseline run inside full-check. Full-check repeats those
  same failures; it cannot certify a clean repository gate in this environment.
- Frontend gate rerun again passed lint/typecheck and hit the unchanged CE-kit ESLint-rule
  test's 5-second timeout. Its isolated run passed; web-mirror tests and both browser suites
  passed separately. This is not recorded as a passed frontend gate.
- Removed the temporary smoke containers/network/database volume after testing. Original live
  API remains healthy, worker running, and PostgreSQL healthy on the original ports.

- CE-kit rerun with `--maxWorkers=1` passed all 423 tests without changing timeouts or test
  code. All workspace builds and generated API-type drift checks passed independently.

### Final result

Implementation and task-specific validation are complete. Full-check stopped at its baseline:
4,251 passed, 3 failed (the runner environment issues above), 12 skipped, 720 deselected.
The frontend gate remains non-green because of the concurrent CE-kit test timeout; its 423
tests passed with one worker. All 1,124 web-mirror tests, 1,001 product Python tests, 19 browser
smoke tests, workspace lint/typechecks/builds, and generated-doc/API-type drift checks passed
independently. No source or test changes were made outside ANY-616 to make the gates green.

Ready for user review and a local commit. Push requires explicit user approval. Live-provider
QA and parent-task confirmation remain separate; no Linear or GitHub write was performed.

## Review round 1 corrections

The user authorized local fixes and tests only. The initial implementation's duplicate
normalization and pre-line choices are superseded by:

- Derive missing fields from values; supplied metadata must contain every absent field exactly
  once, rejecting overlap, omission, duplication and unknown entries. Preserve the legacy
  absent-metadata path and schema ordering.
- Restore pre-wrap for displayed section content and summary, retaining existing overflow rules.
- Add parser contract regressions and significant-whitespace coverage to the mobile browser test.
- Run frontend tests, typecheck, lint and an isolated browser check with mocked API responses.

The parser issue is defensive consistency with the schema: the current result API already
revalidates stored artifacts and refuses invalid complements. Whitespace loss was reproduced
in Chromium and affects valid content. No backend, Docker, live stack or GitHub changes are
needed for these corrections.

Validation:
- New parser regressions failed for all six fields before the fix; afterward the focused
  product, language and shared-UI suites passed all 58 tests. Valid metadata and legacy
  absence are checked for all 64 partitions of the six fields.
- Web-mirror and browser-smoke TypeScript checks passed; ESLint passed for changed TypeScript.
- Chromium rendered the actual product with mocked API responses at 390px and 1280px:
  section content and summary retained spaces, tabs and newlines, with no horizontal overflow
  from a long URL. External font requests were blocked. The temporary frontend was stopped.
- The persistent mobile smoke test now asserts significant whitespace. The full backend
  browser suite and full-check were not rerun for these local corrections; their earlier
  results and environment limitations remain recorded above.

Both corrections passed local validation. The user subsequently authorized committing and
pushing them to feature/ANY-616; GitHub comments remain outside the authorized scope.
